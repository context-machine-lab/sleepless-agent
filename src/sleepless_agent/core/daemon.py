"""Main agent daemon orchestrating task execution."""

from __future__ import annotations

import asyncio
import signal
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy.orm import sessionmaker

from sleepless_agent.utils.config import get_config
from sleepless_agent.storage.results import ResultManager
from sleepless_agent.scheduling.auto_generator import AutoTaskGenerator
from sleepless_agent.scheduling.scheduler import BudgetManager, SmartScheduler
from sleepless_agent.core.models import TaskPriority, init_db
from sleepless_agent.core.queue import TaskQueue
from sleepless_agent.core.task_runtime import TaskRuntime
from sleepless_agent.core.timeout_manager import TaskTimeoutManager
from sleepless_agent.core.executor import ClaudeCodeExecutor
from sleepless_agent.storage.git import GitManager
from sleepless_agent.utils.live_status import LiveStatusTracker
from sleepless_agent.storage.workspace import WorkspaceSetup
from sleepless_agent.interfaces.bot import SlackBot
from sleepless_agent.monitoring.logging import get_logger
from sleepless_agent.monitoring.monitor import HealthMonitor, PerformanceLogger
from sleepless_agent.monitoring.report_generator import ReportGenerator

logger = get_logger(__name__)


class SleeplessAgent:
    """High-level controller that keeps the agent running continuously."""

    def __init__(self) -> None:
        self.config = get_config()
        self.running = False
        self.last_daily_summarization: datetime | None = None

        # Pass git config if it exists
        git_config = getattr(self.config, 'git', None)
        setup = WorkspaceSetup(self.config.agent, git_config=git_config)
        setup_result = setup.run()
        self.use_remote_repo = setup_result.use_remote_repo
        self.remote_repo_url = setup_result.remote_repo_url

        self._init_directories()

        engine = init_db(str(self.config.agent.db_path))
        self.task_queue = TaskQueue(str(self.config.agent.db_path))

        self._create_seed_task_if_needed()

        live_status_path = Path(self.config.agent.db_path).parent / "live_status.json"
        self.live_status_tracker = LiveStatusTracker(live_status_path)
        self.live_status_tracker.clear_all()

        Session = sessionmaker(bind=engine)
        self.db_session = Session()

        self.budget_manager = BudgetManager(
            session=self.db_session,
            daily_budget_usd=10.0,
            night_quota_percent=90.0,
        )

        self.scheduler = SmartScheduler(
            task_queue=self.task_queue,
            daily_budget_usd=10.0,
            night_quota_percent=90.0,
            usage_command=self.config.claude_code.usage_command,
            threshold_day=self.config.claude_code.threshold_day,
            threshold_night=self.config.claude_code.threshold_night,
            night_start_hour=self.config.claude_code.night_start_hour,
            night_end_hour=self.config.claude_code.night_end_hour,
        )

        self.auto_generator = AutoTaskGenerator(
            db_session=self.db_session,
            config=self.config.auto_generation,
            budget_manager=self.budget_manager,
            default_model=self.config.claude_code.model,
            usage_command=self.config.claude_code.usage_command,
            threshold_day=self.config.claude_code.threshold_day,
            threshold_night=self.config.claude_code.threshold_night,
            night_start_hour=self.config.claude_code.night_start_hour,
            night_end_hour=self.config.claude_code.night_end_hour,
        )

        self.claude = ClaudeCodeExecutor(
            workspace_root=str(self.config.agent.workspace_root),
            live_status_tracker=self.live_status_tracker,
            default_model=self.config.claude_code.model,
        )

        self.results = ResultManager(
            str(self.config.agent.db_path),
            str(self.config.agent.results_path),
        )

        auto_create_repo = git_config.get("auto_create_repo", False) if git_config else False
        git_enabled = git_config.get("enabled", True) if git_config else True
        self.git = GitManager(
            workspace_root=str(self.config.agent.workspace_root),
            auto_create_repo=auto_create_repo,
            enabled=git_enabled,
        )
        if git_enabled:
            self.git.init_repo()
            if self.use_remote_repo and self.remote_repo_url:
                try:
                    self.git.configure_remote(self.remote_repo_url)
                except Exception as exc:  # pragma: no cover - defensive
                    logger.error(f"Failed to configure remote repository: {exc}")
        else:
            logger.info("git.disabled", message="Git integration is disabled")

        self.monitor = HealthMonitor(
            db_path=str(self.config.agent.db_path),
            results_path=str(self.config.agent.results_path),
        )
        self.perf_logger = PerformanceLogger(log_dir=str(self.config.agent.db_path.parent))
        self.report_generator = ReportGenerator(
            base_path=str(self.config.agent.db_path.parent / "reports")
        )

        self.bot = SlackBot(
            bot_token=self.config.slack.bot_token,
            app_token=self.config.slack.app_token,
            task_queue=self.task_queue,
            scheduler=self.scheduler,
            monitor=self.monitor,
            report_generator=self.report_generator,
            live_status_tracker=self.live_status_tracker,
        )

        self.timeout_manager = TaskTimeoutManager(
            config=self.config,
            task_queue=self.task_queue,
            claude=self.claude,
            monitor=self.monitor,
            perf_logger=self.perf_logger,
            report_generator=self.report_generator,
            bot=self.bot,
            live_status_tracker=self.live_status_tracker,
        )

        self.task_runtime = TaskRuntime(
            config=self.config,
            task_queue=self.task_queue,
            scheduler=self.scheduler,
            claude=self.claude,
            results=self.results,
            git=self.git,
            monitor=self.monitor,
            perf_logger=self.perf_logger,
            report_generator=self.report_generator,
            bot=self.bot,
            live_status_tracker=self.live_status_tracker,
        )

        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _init_directories(self) -> None:
        self.config.agent.workspace_root.mkdir(parents=True, exist_ok=True)
        self.config.agent.shared_workspace.mkdir(parents=True, exist_ok=True)
        self.config.agent.results_path.mkdir(parents=True, exist_ok=True)
        self.config.agent.db_path.parent.mkdir(parents=True, exist_ok=True)

    def _create_seed_task_if_needed(self) -> None:
        pending_count = len(self.task_queue.get_pending_tasks())
        if pending_count > 0:
            logger.debug(
                "Workspace has %d pending tasks, skipping seed task creation",
                pending_count,
            )
            return

        seed_task_marker = self.config.agent.db_path.parent / ".seed_task_created"
        if seed_task_marker.exists():
            logger.debug("Seed task already created in previous runs")
            return

        seed_description = (
            "Research and document best practices for designing multi-agent systems in Python: "
            "explore architectural patterns for agent coordination, context sharing, task distribution, "
            "and state management. Investigate frameworks like LangChain, AutoGen, CrewAI, and custom approaches. "
            "Create comprehensive documentation with examples, trade-offs, and recommendations that can inform "
            "the evolution of this sleepless-agent system. Focus on practical patterns for 24/7 autonomous operation, "
            "budget management, and cross-agent knowledge sharing."
        )

        self.task_queue.add_task(
            description=seed_description,
            priority=TaskPriority.THOUGHT,
        )

        try:
            seed_task_marker.touch()
        except Exception as exc:  # pragma: no cover - defensive
            logger.debug(f"Failed to write seed task marker: {exc}")

        logger.info(
            "Created seed task for workspace bootstrap (context engineering on multi-agent systems)"
        )

    def _signal_handler(self, sig, _frame) -> None:
        logger.info(f"Received signal {sig}, shutting down...")
        self.running = False
        if self.live_status_tracker:
            self.live_status_tracker.clear_all()
        # Don't call bot.stop() here - let the finally block handle cleanup
        sys.exit(0)

    async def run(self) -> None:
        self.running = True
        logger.info("Sleepless Agent starting...")

        try:
            # Start bot in background thread to avoid blocking the async event loop
            # The Slack SDK's connect() is synchronous and would block forever
            import threading
            bot_thread = threading.Thread(target=self.bot.start, daemon=True, name="SlackBot")
            bot_thread.start()
            await asyncio.sleep(0.5)  # Give bot time to initialize
            logger.info("Slack bot started in background thread")
        except Exception as exc:
            logger.error(f"Failed to start bot: {exc}")
            return

        try:
            health_check_counter = 0
            while self.running:
                await self._process_tasks()

                pause_seconds = self.scheduler.get_pause_remaining_seconds()
                if pause_seconds is None:
                    try:
                        await self.auto_generator.check_and_generate()
                    except Exception as exc:
                        logger.error(f"Error in auto-generation: {exc}")

                health_check_counter += 1
                if health_check_counter >= 12:
                    self.monitor.log_health_report()
                    health_check_counter = 0

                self._check_and_summarize_daily_reports()

                sleep_seconds = 5.0
                pause_seconds = self.scheduler.get_pause_remaining_seconds()
                if pause_seconds:
                    sleep_seconds = max(5.0, min(pause_seconds, 300.0))
                await asyncio.sleep(sleep_seconds)

        except KeyboardInterrupt:
            logger.info("Agent interrupted by user")
        except Exception as exc:
            logger.error(f"Unexpected error in main loop: {exc}")
        finally:
            self.monitor.log_health_report()
            self.bot.stop()
            logger.info("Sleepless Agent stopped")

    async def _process_tasks(self) -> None:
        try:
            self.timeout_manager.enforce()
            tasks_to_execute = self.scheduler.get_next_tasks()

            for task in tasks_to_execute:
                if not self.running:
                    break

                await self.task_runtime.execute(task)
                await asyncio.sleep(1)
        except Exception as exc:
            logger.error(f"Error in task processing loop: {exc}")

    def _check_and_summarize_daily_reports(self) -> None:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)

        if self.last_daily_summarization is None or self.last_daily_summarization.date() != now.date():
            if now >= end_of_day:
                yesterday = (now - timedelta(days=1)).strftime("%Y-%m-%d")
                try:
                    self.report_generator.summarize_daily_report(yesterday)
                    logger.info(f"Summarized daily report for {yesterday}")

                    for project_id in self.report_generator.list_project_reports():
                        self.report_generator.summarize_project_report(project_id)

                    self.report_generator.update_recent_reports()
                    self.last_daily_summarization = now
                except Exception as exc:
                    logger.error(f"Failed to summarize daily reports: {exc}")


def main() -> None:
    agent = SleeplessAgent()
    asyncio.run(agent.run())


if __name__ == "__main__":
    main()
