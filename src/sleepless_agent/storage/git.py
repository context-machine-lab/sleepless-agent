"""Git integration helpers for consolidating task and project work."""

from __future__ import annotations

import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

from sleepless_agent.monitoring.logging import get_logger
logger = get_logger(__name__)


class GitManager:
    """Manage a single workspace repository with branch-per-project workflow."""

    def __init__(
        self,
        workspace_root: str,
        default_task_branch: str = "tasks",
        main_branch: str = "main",
        auto_create_repo: bool = False,
        enabled: bool = True,
    ):
        self.repo_path = Path(workspace_root).resolve()
        self.default_task_branch = default_task_branch
        self.main_branch = main_branch
        self.auto_create_repo = auto_create_repo
        self.enabled = enabled
        self._push_warning_logged = False

    # ------------------------------------------------------------------
    # Repository bootstrap
    # ------------------------------------------------------------------
    def init_repo(self) -> bool:
        """Ensure workspace repo exists with an initial commit."""
        if not self.enabled:
            return True  # Skip git operations when disabled
        try:
            self.repo_path.mkdir(parents=True, exist_ok=True)

            repo_initialized = False
            if not self._repo_exists():
                # Use -b to set initial branch name (avoids master/main mismatch)
                self._run_git("init", "-b", self.main_branch)
                self._run_git("config", "user.email", "agent@sleepless.local")
                self._run_git("config", "user.name", "Sleepless Agent")
                repo_initialized = True

            if not self._has_commits():
                gitkeep = self.repo_path / ".gitkeep"
                gitkeep.touch(exist_ok=True)
                self._run_git("add", ".gitkeep")
                self._run_git("commit", "-m", "Initial commit")
                if repo_initialized:
                    logger.info("git.workspace.initialized", path=str(self.repo_path))
                else:
                    logger.debug("Created initial commit in existing repo")

            # Ensure the default task branch exists
            if self.default_task_branch != self.main_branch:
                self.ensure_branch(self.default_task_branch)

            self._ensure_gitignore()

            return True
        except Exception as exc:  # pragma: no cover - defensive
            logger.error(f"Failed to initialize workspace git repo: {exc}")
            return False

    # ------------------------------------------------------------------
    # Public branch helpers
    # ------------------------------------------------------------------
    def ensure_branch(self, branch: str):
        """Create branch from main if it does not exist."""
        if self._branch_exists(branch):
            return

        self._checkout(self.main_branch)
        self._run_git("branch", branch, self.main_branch)
        logger.debug(f"Created branch '{branch}' from {self.main_branch}")

    def commit_workspace_changes(
        self,
        branch: str,
        workspace_path: Path,
        files: Iterable[str],
        message: str,
    ) -> Optional[str]:
        """Commit files from a task workspace into branch, merge to main, and push."""
        if not self.enabled:
            return None  # Skip git operations when disabled
        self.init_repo()
        self.ensure_branch(branch)

        repo_relative_files = self._normalize_files(workspace_path, files)
        if not repo_relative_files:
            logger.info(f"No tracked files to commit for branch '{branch}'")
            return None

        try:
            self._checkout(branch)
            self._fast_forward_with_main(branch)

            self._stage(repo_relative_files)
            commit_sha = self._commit_if_needed(message)
            if not commit_sha:
                logger.info(f"No changes to commit for branch '{branch}'")
                self._checkout(self.main_branch)
                return None

            self._merge_branch_into_main(branch)
            self.push_all()
            return commit_sha

        except Exception as exc:
            logger.error(f"Git workflow failed for branch '{branch}': {exc}")
            raise

    def push_all(self):
        """Push all branches to remote origin if configured."""
        if not self._has_remote("origin"):
            logger.debug("No remote 'origin' configured; skipping push")
            return

        # Auto-create GitHub repository if it doesn't exist
        if self.auto_create_repo:
            try:
                remote_url = self._run_git("remote", "get-url", "origin")
                if remote_url and not self._check_remote_exists(remote_url):
                    if self._create_github_repo(remote_url):
                        logger.info("Created remote repository and will push")
                    else:
                        logger.warning("Failed to create remote repository, push may fail")
            except Exception as exc:
                logger.debug(f"Failed to auto-create repository: {exc}")

        try:
            self._run_git("push", "--all", "origin")
            if self._push_warning_logged:
                logger.info("Git push to origin succeeded after previous failures.")
                self._push_warning_logged = False
        except RuntimeError as exc:
            message = str(exc)
            if (
                "Repository not found" in message
                or "Could not read from remote repository" in message
            ):
                if not self._push_warning_logged:
                    logger.warning(
                        "Push failed because remote repository is unavailable or access is denied. "
                        "Continuing without pushing; verify your remote configuration if pushes are required."
                    )
                    self._push_warning_logged = True
                else:
                    logger.debug(
                        "Skipping repeated push warning; remote repository still unreachable."
                    )
                return
            logger.error(f"Failed to push branches to origin: {exc}")
            raise
        except Exception as exc:
            logger.error(f"Failed to push branches to origin: {exc}")
            raise

    def configure_remote(self, remote_url: str, remote_name: str = "origin"):
        """Ensure a remote is set up for pushing updates."""
        self.init_repo()
        if not remote_url:
            logger.warning("Remote URL is empty; skipping remote configuration")
            return
        try:
            if self._has_remote(remote_name):
                self._run_git("remote", "set-url", remote_name, remote_url)
                logger.info("git.remote.updated", remote=remote_name, url=remote_url)
            else:
                self._run_git("remote", "add", remote_name, remote_url)
                logger.info("git.remote.added", remote=remote_name, url=remote_url)
        except Exception as exc:
            logger.error(f"Failed to configure remote '{remote_name}': {exc}")
            raise

    # ------------------------------------------------------------------
    # High-level task helpers
    # ------------------------------------------------------------------
    def determine_branch(self, project_id: Optional[str]) -> str:
        """Get branch name for a given project scope."""
        if project_id:
            return f"project/{project_id}"
        return self.default_task_branch

    def write_summary_file(
        self,
        workspace_path: Path,
        task_id: int,
        priority: str,
        description: str,
        result_output: str,
        limit: int = 2000,
    ) -> Optional[str]:
        """Create a summary file for lightweight tasks and return relative path."""
        try:
            workspace_path.mkdir(parents=True, exist_ok=True)
            summary_path = workspace_path / f"task_{task_id}_summary.md"

            truncated_output = result_output[:limit]
            if len(result_output) > limit:
                truncated_output += "\n\n[output truncated for summary]"

            summary_content = (
                f"# Task #{task_id} Summary\n\n"
                f"**When**: {datetime.now(timezone.utc).replace(tzinfo=None).isoformat()} UTC\n"
                f"**Priority**: {priority}\n"
                f"**Description**: {description}\n\n"
                f"## Output\n\n{truncated_output}\n"
            )
            summary_path.write_text(summary_content)
            return summary_path.relative_to(workspace_path).as_posix()
        except Exception as exc:
            logger.warning(f"Failed to write summary for task {task_id}: {exc}")
            return None

    # ------------------------------------------------------------------
    # Validation utilities reused by daemon
    # ------------------------------------------------------------------
    def validate_changes(self, workspace: Path, files: List[str]) -> Tuple[bool, str]:
        """Validate a set of files before committing."""
        if not self.enabled:
            return True, ""  # Skip validation when git is disabled
        issues: List[str] = []

        for file in files:
            file_path = workspace / file

            if self._contains_secrets(file_path):
                issues.append(f"Potential secret in {file}")

            if file.endswith(".py") and not self._validate_python_syntax(file_path):
                issues.append(f"Python syntax error in {file}")

        if issues:
            return False, "\n".join(issues)
        return True, "OK"

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _run_git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.repo_path,
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or "git command failed")
        return result.stdout.strip()

    def _ensure_gitignore(self):
        """Ensure mutable runtime artifacts stay out of version control."""
        gitignore_path = self.repo_path / ".gitignore"
        managed_header = "# Sleepless Agent managed ignores"
        ignore_entries = ["data/"]

        existing_lines = []
        if gitignore_path.exists():
            existing_lines = gitignore_path.read_text().splitlines()

        updated_lines = list(existing_lines)

        if managed_header not in updated_lines:
            if updated_lines and updated_lines[-1].strip():
                updated_lines.append("")
            updated_lines.append(managed_header)

        for entry in ignore_entries:
            if entry not in updated_lines:
                updated_lines.append(entry)

        if updated_lines != existing_lines:
            gitignore_path.write_text("\n".join(updated_lines) + "\n")

    def _repo_exists(self) -> bool:
        return (self.repo_path / ".git").exists()

    def _has_commits(self) -> bool:
        try:
            self._run_git("rev-parse", "HEAD")
            return True
        except Exception:
            return False

    def _branch_exists(self, branch: str) -> bool:
        try:
            self._run_git("rev-parse", "--verify", branch)
            return True
        except Exception:
            return False

    def _checkout(self, branch: str):
        self._run_git("checkout", branch)

    def _stage(self, files: Iterable[str]):
        paths = list(files)
        if not paths:
            return
        tracked = self._filter_tracked_paths(paths)
        if not tracked:
            logger.debug("All candidate paths are ignored; skipping staging.")
            return
        self._run_git("add", "--", *tracked)

    def _filter_tracked_paths(self, paths: Iterable[str]) -> List[str]:
        """Remove paths ignored by git, logging any that are skipped."""
        tracked: List[str] = []
        skipped: List[str] = []

        for path in paths:
            if self._is_ignored(path):
                skipped.append(path)
            else:
                tracked.append(path)

        if skipped:
            logger.debug(f"Skipping ignored paths: {skipped}")

        return tracked

    def _is_ignored(self, path: str) -> bool:
        """Return True if git would ignore the provided path."""
        try:
            result = subprocess.run(
                ["git", "check-ignore", path],
                cwd=self.repo_path,
                capture_output=True,
                text=True,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            logger.debug(f"Unable to determine ignore status for {path}: {exc}")
            return False

        if result.returncode == 0:
            # Path is ignored; git echoes it on stdout.
            return True

        if result.returncode == 1:
            return False

        logger.debug(
            f"git check-ignore exited with {result.returncode} for {path}: {result.stderr.strip()}"
        )
        return False

    def _commit_if_needed(self, message: str) -> Optional[str]:
        if not self._has_pending_changes():
            return None
        self._run_git("commit", "-m", message)
        return self._run_git("rev-parse", "HEAD")

    def _has_pending_changes(self) -> bool:
        status = self._run_git("status", "--porcelain")
        return bool(status.strip())

    def _fast_forward_with_main(self, branch: str):
        if branch == self.main_branch:
            return
        try:
            self._run_git("merge", "--ff-only", self.main_branch)
        except Exception:
            # If fast-forward fails (branch ahead), ignore – we'll merge later
            logger.debug(f"Branch '{branch}' not fast-forward from main; continuing")

    def _merge_branch_into_main(self, branch: str):
        if branch == self.main_branch:
            return

        self._checkout(self.main_branch)
        try:
            self._run_git("merge", "--ff-only", branch)
            logger.debug(f"Merged '{branch}' into {self.main_branch}")
        except RuntimeError:
            logger.debug(
                f"Fast-forward merge failed for '{branch}', using --no-ff merge"
            )
            self._run_git("merge", "--no-ff", branch, "-m", f"Merge branch '{branch}'")

    def _has_remote(self, name: str) -> bool:
        try:
            remotes = self._run_git("remote")
            return name in remotes.splitlines()
        except Exception:
            return False

    def _check_remote_exists(self, remote_url: str) -> bool:
        """Check if GitHub repository exists using gh CLI."""
        try:
            # Extract repo from URL (e.g., git@github.com:user/repo.git -> user/repo)
            if "@github.com:" in remote_url:
                repo = remote_url.split(":")[-1].replace(".git", "")
            elif "github.com/" in remote_url:
                repo = remote_url.split("github.com/")[-1].replace(".git", "")
            else:
                logger.debug(f"Non-GitHub URL, skipping repo check: {remote_url}")
                return True

            result = subprocess.run(
                ["gh", "repo", "view", repo],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as exc:
            logger.debug(f"Failed to check if remote exists: {exc}")
            return True

    def _create_github_repo(self, remote_url: str) -> bool:
        """Create GitHub repository using gh CLI."""
        try:
            # Extract repo from URL
            if "@github.com:" in remote_url:
                repo = remote_url.split(":")[-1].replace(".git", "")
            elif "github.com/" in remote_url:
                repo = remote_url.split("github.com/")[-1].replace(".git", "")
            else:
                logger.warning(f"Cannot create non-GitHub repo: {remote_url}")
                return False

            # Get repo name (last part)
            repo_name = repo.split("/")[-1]

            logger.debug(f"Creating GitHub repository: {repo}")
            result = subprocess.run(
                ["gh", "repo", "create", repo, "--private"],
                capture_output=True,
                text=True,
                timeout=30,
            )

            if result.returncode == 0:
                return True
            else:
                logger.error(f"Failed to create repository {repo}: {result.stderr.strip()}")
                return False
        except Exception as exc:
            logger.error(f"Failed to create repository: {exc}")
            return False

    def _normalize_files(self, workspace_path: Path, files: Iterable[str]) -> List[str]:
        normalized: List[str] = []
        for file in files:
            source = (workspace_path / file).resolve()
            try:
                rel_path = source.relative_to(self.repo_path)
            except ValueError:
                logger.warning(
                    f"Skipping file outside workspace repo: {source}"
                )
                continue
            normalized.append(str(rel_path))
        return normalized

    # ------------------------------------------------------------------
    # Simple static validation routines
    # ------------------------------------------------------------------
    def _contains_secrets(self, file_path: Path) -> bool:
        secret_patterns = [
            "PRIVATE_KEY",
            "API_KEY",
            "PASSWORD",
            "SECRET",
            "TOKEN",
            "credential",
        ]

        try:
            content = file_path.read_text()
            for pattern in secret_patterns:
                if pattern in content.upper():
                    return True
        except Exception:
            pass
        return False

    def _validate_python_syntax(self, file_path: Path) -> bool:
        try:
            import ast

            ast.parse(file_path.read_text())
            return True
        except Exception:
            return False