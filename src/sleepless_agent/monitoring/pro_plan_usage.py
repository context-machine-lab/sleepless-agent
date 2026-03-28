"""Pro plan usage monitoring and checking"""

import os
import re
import shlex
import string
import subprocess
import sys
import time
from contextlib import suppress
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

try:  # pragma: no cover - platform dependent
    import pty
except (ImportError, AttributeError):
    pty = None  # type: ignore[misc,assignment]

if pty is not None:  # pragma: no cover - platform dependent
    import select
else:  # pragma: no cover - platform dependent
    select = None  # type: ignore[assignment]

from sleepless_agent.monitoring.logging import get_logger

logger = get_logger(__name__)

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class ProPlanUsageChecker:
    """Check Claude Code Pro plan usage via CLI, tracking percentage and reset time."""

    TIMEZONE_ALIASES = {
        "PT": "America/Los_Angeles",
        "PST": "America/Los_Angeles",
        "PDT": "America/Los_Angeles",
        "MT": "America/Denver",
        "MST": "America/Denver",
        "MDT": "America/Denver",
        "CT": "America/Chicago",
        "CST": "America/Chicago",
        "CDT": "America/Chicago",
        "ET": "America/New_York",
        "EST": "America/New_York",
        "EDT": "America/New_York",
        "AKST": "America/Anchorage",
        "AKDT": "America/Anchorage",
        "HST": "Pacific/Honolulu",
        "BST": "Europe/London",
        "CEST": "Europe/Berlin",
        "CET": "Europe/Berlin",
        "IST": "Asia/Kolkata",
        "AEST": "Australia/Sydney",
        "AEDT": "Australia/Sydney",
        "JST": "Asia/Tokyo",
        "KST": "Asia/Seoul",
    }

    def __init__(
        self,
        command: str = "claude usage",
    ):
        """Initialize usage checker

        Args:
            command: CLI command to run (default: "claude usage")
        """
        self.command = command
        self.last_check_time: Optional[datetime] = None
        self.cached_usage: Optional[Tuple[float, Optional[datetime]]] = None
        self.cache_duration_seconds = 60
        self.last_timezone_str: Optional[str] = None
        self._last_logged_usage: Optional[Tuple[float, Optional[datetime]]] = None

    def get_usage(self) -> Tuple[float, Optional[datetime]]:
        """Execute CLI command and parse usage response as percentage plus reset time."""
        try:
            # Check cache first (valid for 60 seconds)
            if self.cached_usage and self.last_check_time:
                cache_age = (datetime.now(timezone.utc).replace(tzinfo=None) - self.last_check_time).total_seconds()
                if cache_age < self.cache_duration_seconds:
                    logger.debug(
                        "usage.cache.hit",
                        age_seconds=int(cache_age),
                    )
                    return self.cached_usage

            try:
                command_args = tuple(shlex.split(self.command))
            except ValueError as exc:
                logger.error(
                    "usage.command.invalid",
                    command=self.command,
                    error=str(exc),
                )
                return self._fallback_usage()

            raw_output, return_code = self._execute_command(command_args)
            cleaned_output = self._clean_command_output(raw_output)

            # Check for errors
            # Accept: 0 (success), -15/-9 (Python signal convention), 143/137 (shell signal convention: 128+signal)
            if return_code not in (0, -15, -9, 143, 137):
                if cleaned_output:
                    logger.warning(
                        "usage.command.nonzero_exit",
                        return_code=return_code,
                    )
                else:
                    logger.error(
                        "usage.command.failed",
                        return_code=return_code,
                    )

            if not cleaned_output:
                logger.warning("usage.command.empty_output")
                return self._fallback_usage()

            # Detect API plan: no usage data is available, only a welcome screen.
            if self._is_api_plan_response(cleaned_output):
                logger.debug("usage.api_plan.not_supported")
                fallback = (0.0, None)
                self.cached_usage = fallback
                self.last_check_time = datetime.now(timezone.utc).replace(tzinfo=None)
                return fallback

            # Parse output
            try:
                usage_percent, reset_time = self._parse_usage_output(cleaned_output)
            except RuntimeError as parse_error:
                logger.warning(
                    "usage.parse_failed",
                    error=str(parse_error),
                )
                return self._fallback_usage()

            # Cache result
            self.cached_usage = (usage_percent, reset_time)
            self.last_check_time = datetime.now(timezone.utc).replace(tzinfo=None)

            # Format reset time with timezone info if available
            if reset_time:
                if self.last_timezone_str:
                    tz = self._resolve_timezone(self.last_timezone_str)
                    if tz:
                        reset_dt_tz = reset_time.replace(tzinfo=timezone.utc).astimezone(tz)
                        reset_label = reset_dt_tz.strftime("%I:%M%p").lower() + f" ({self.last_timezone_str})"
                    else:
                        reset_label = reset_time.strftime("%H:%M:%S")
                else:
                    reset_label = reset_time.strftime("%H:%M:%S")
            else:
                reset_label = "unknown"

            # Only log at significant milestones or major changes
            # This reduces log noise from small fluctuations
            previous_snapshot = self._last_logged_usage
            should_log = False

            if previous_snapshot is None:
                # On first check, only log if usage is already significant (>=50%)
                # This avoids startup noise when usage is low
                if usage_percent >= 50.0:
                    should_log = True
                # Always cache it even if not logging
                self._last_logged_usage = (usage_percent, reset_time)
            else:
                prev_percent, prev_reset = previous_snapshot
                percent_change = abs(usage_percent - prev_percent)
                reset_changed = reset_time != prev_reset

                # Log at 10% milestones (50%, 60%, 70%, 80%, 90%, 100%)
                current_milestone = int(usage_percent / 10) * 10
                prev_milestone = int(prev_percent / 10) * 10
                crossed_milestone = current_milestone != prev_milestone and current_milestone >= 50

                # Log if crossed a milestone OR if we're near threshold (every % counts)
                if crossed_milestone or usage_percent >= 80.0:
                    should_log = True
                # Also log if reset time changed (new day/period)
                elif reset_changed and prev_reset and reset_time:
                    # Only if the reset time jumped significantly (new reset period)
                    should_log = True

                if should_log:
                    self._last_logged_usage = (usage_percent, reset_time)

            if should_log:
                logger.info(
                    "usage.snapshot",
                    usage_percent=usage_percent,
                )

            return usage_percent, reset_time

        except RuntimeError:
            raise
        except Exception as e:
            logger.error("usage.command.exception", error=str(e))
            raise

    def _execute_command(self, command_args: Tuple[str, ...]) -> Tuple[str, int]:
        """Execute the configured CLI command and capture combined output."""

        # Attempt PTY capture first to support interactive commands like "claude /usage".
        if self._supports_pty():
            with suppress(Exception):
                return self._execute_with_pty(command_args)

        # Fall back to the simpler pipe-based execution.
        return self._execute_with_pipes(command_args)

    def _execute_with_pipes(self, command_args: Tuple[str, ...]) -> Tuple[str, int]:
        """Fallback execution path using plain stdout/stderr pipes."""

        process = subprocess.Popen(
            command_args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        output = ""
        stderr_output = ""
        try:
            output, stderr_output = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            logger.debug("usage.command.timeout", mode="pipes", timeout_seconds=5)
            process.terminate()
            try:
                output, stderr_output = process.communicate(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                output, stderr_output = process.communicate()

        combined_output = (output or "") + (stderr_output or "")
        return combined_output, process.returncode

    def _execute_with_pty(self, command_args: Tuple[str, ...]) -> Tuple[str, int]:
        """Execute the CLI command inside a PTY to capture interactive output."""

        if not self._supports_pty():
            raise RuntimeError("Pseudo-terminal capture not supported on this platform.")

        master_fd, slave_fd = pty.openpty()
        env = os.environ.copy()
        env.setdefault("TERM", "xterm-256color")

        process = subprocess.Popen(
            command_args,
            stdin=slave_fd,
            stdout=slave_fd,
            stderr=slave_fd,
            env=env,
            close_fds=True,
        )

        os.close(slave_fd)

        buffer: list[bytes] = []
        os.set_blocking(master_fd, False)

        try:
            capture_deadline = time.monotonic() + 5
            while time.monotonic() < capture_deadline:
                if process.poll() is not None:
                    break

                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if master_fd in ready:
                    try:
                        chunk = os.read(master_fd, 4096)
                    except OSError:
                        break

                    if not chunk:
                        break

                    buffer.append(chunk)

                    decoded = chunk.decode("utf-8", errors="ignore")
                    if "Resets" in decoded or "% used" in decoded:
                        # Slow down reading once we've seen the usage screen.
                        capture_deadline = min(capture_deadline, time.monotonic() + 0.5)

            # Request the CLI to exit gracefully (Esc), fallback to Ctrl+C/terminate if needed.
            with suppress(OSError):
                os.write(master_fd, b"\x1b")
            time.sleep(0.2)

            if process.poll() is None:
                with suppress(OSError):
                    os.write(master_fd, b"\x03")  # Ctrl+C
                time.sleep(0.2)

            if process.poll() is None:
                process.terminate()

            with suppress(subprocess.TimeoutExpired):
                process.wait(timeout=2)

            if process.poll() is None:
                process.kill()
                process.wait(timeout=2)

            # Drain any trailing output.
            drain_deadline = time.monotonic() + 0.5
            while time.monotonic() < drain_deadline:
                ready, _, _ = select.select([master_fd], [], [], 0.1)
                if master_fd not in ready:
                    break
                try:
                    chunk = os.read(master_fd, 4096)
                except OSError:
                    break
                if not chunk:
                    break
                buffer.append(chunk)
        finally:
            os.close(master_fd)

        combined = b"".join(buffer)
        return combined.decode("utf-8", errors="ignore"), process.returncode

    @staticmethod
    def _supports_pty() -> bool:
        """Detect whether PTY capture is supported on this platform."""
        if pty is None or select is None:
            return False
        if sys.platform.startswith("win"):  # Windows lacks native PTY support.
            return False
        return True

    @staticmethod
    def _clean_command_output(raw_output: str) -> str:
        """Strip ANSI/tui control sequences and non-printable characters."""

        if not raw_output:
            return ""

        text = raw_output.replace("\r", "\n")

        ansi_escape = re.compile(r"\x1B\[[0-?]*[ -/]*[@-~]")
        osc_escape = re.compile(r"\x1B\][^\x07]*(\x07|\x1B\\)")

        text = ansi_escape.sub("", text)
        text = osc_escape.sub("", text)

        printable = set(string.printable + "\n")
        text = ''.join(ch if ch in printable else ' ' for ch in text)

        lines = [line.rstrip() for line in text.splitlines()]
        cleaned_lines = [line for line in lines if line.strip()]

        return "\n".join(cleaned_lines)

    @staticmethod
    def _is_api_plan_response(output: str) -> bool:
        """Return True when output looks like the API-plan welcome screen.

        When Claude Code is authenticated via an API key rather than a Pro
        subscription, ``claude /usage`` prints a welcome/tips page instead of
        usage statistics.  Detecting this avoids spurious parse-failure warnings.
        """
        api_indicators = [
            r"Claude\s+Code\s+v\d+",
            r"Tips\s+for\s+getting\s+started",
            r"Welcome\s+to\s+Claude",
        ]
        usage_indicators = [
            r"\d+(?:\.\d+)?\s*%\s*(?:used|usage|remaining)",
            r"used\s+\d+\s+of\s+\d+\s+messages",
            r"Messages?\s*:\s*\d+\s*/\s*\d+",
            r"Resets?\s+(?:(?:at|in|@)\s+\d|\d{1,2}:)",
        ]

        has_api_indicator = any(
            re.search(pattern, output, re.IGNORECASE) for pattern in api_indicators
        )
        has_usage_data = any(
            re.search(pattern, output, re.IGNORECASE) for pattern in usage_indicators
        )
        return has_api_indicator and not has_usage_data

    def _parse_usage_output(self, output: str) -> Tuple[float, Optional[datetime]]:
        """Parse 'claude usage' command output for percentage and reset time."""
        lines = output.strip().split("\n")

        usage_percent: Optional[float] = None

        # Primary format: "<number>% used"
        for line in lines:
            if not re.search(r"(used|usage|messages|remaining|limit)", line, re.IGNORECASE):
                continue
            match = re.search(r'(\d+(?:\.\d+)?)\s*%\s*(?:used|usage|of|remaining)?', line, re.IGNORECASE)
            if match:
                usage_percent = float(match.group(1))
                logger.debug(
                    "usage.parse.format",
                    format="direct_percent",
                    usage_percent=usage_percent,
                )
                break

        # Ratios like "You have used 28 of 40 messages"
        if usage_percent is None:
            for line in lines:
                match = re.search(r"used\s+(\d+)\s+of\s+(\d+)\s+messages", line, re.IGNORECASE)
                if match:
                    used = int(match.group(1))
                    total = int(match.group(2))
                    if total > 0:
                        usage_percent = used / total * 100
                        logger.debug(
                            "usage.parse.format",
                            format="used_of_total",
                            used=used,
                            total=total,
                            usage_percent=usage_percent,
                        )
                        break

        # Ratios like "Messages: 28/40"
        if usage_percent is None:
            for line in lines:
                match = re.search(r"Messages?:\s*(\d+)\s*/\s*(\d+)", line, re.IGNORECASE)
                if match:
                    used = int(match.group(1))
                    total = int(match.group(2))
                    if total > 0:
                        usage_percent = used / total * 100
                        logger.debug(
                            "usage.parse.format",
                            format="messages_slash",
                            used=used,
                            total=total,
                            usage_percent=usage_percent,
                        )
                        break

        # Format "28 messages used, 12 remaining"
        if usage_percent is None:
            for line in lines:
                match = re.search(r"(\d+)\s+messages?\s+used", line, re.IGNORECASE)
                if match:
                    used = int(match.group(1))
                    remaining_match = re.search(r"(\d+)\s+remaining", line, re.IGNORECASE)
                    if remaining_match:
                        remaining = int(remaining_match.group(1))
                        total = used + remaining
                        if total > 0:
                            usage_percent = used / total * 100
                            logger.debug(
                                "usage.parse.format",
                                format="used_remaining",
                                used=used,
                                remaining=remaining,
                                usage_percent=usage_percent,
                            )
                    break

        if usage_percent is None:
            displayed = output.replace("\n", " ").strip()
            if len(displayed) > 120:
                displayed = f"{displayed[:117]}..."
            raise RuntimeError(f"Could not parse usage percentage from '{displayed}'")

        usage_percent = max(0.0, min(100.0, usage_percent))

        reset_time = self._parse_reset_time(output)
        return usage_percent, reset_time

    def _parse_reset_time(self, output: str) -> Optional[datetime]:
        """Parse reset time from output

        Formats:
        - "Resets 2:59am (America/New_York)" (Claude Code CLI format)
        - "Resets in 2 hours 45 minutes"
        - "Resets in 3h 15m"
        - "Next reset: 14:30 UTC"

        Args:
            output: Raw output string

        Returns:
            datetime of reset, or None if can't parse
        """
        now_utc = datetime.now(timezone.utc).replace(tzinfo=None)

        # Try: "Resets 2:59am (America/New_York)" or "Resets 7pm (America/New_York)"
        match = re.search(
            r"Resets\s+(\d{1,2})(?::(\d{2}))?\s*(am|pm)\s+\(([^)]+)\)",
            output,
            re.IGNORECASE,
        )
        if match:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2)) if match.group(2) else 0
                meridiem = match.group(3).lower()
                timezone_str = match.group(4)  # e.g., "America/New_York"
                self.last_timezone_str = timezone_str

                if meridiem == "pm" and hour != 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0

                reset_time = self._convert_with_timezone(hour, minute, 0, timezone_str)
                if reset_time is None:
                    reset_time = self._current_utc_with_time(hour, minute, 0, now_utc=now_utc)
                logger.debug(
                    "Parsed reset time: {:02d}:{:02d} {} ({}) → {}",
                    hour % 24,
                    minute,
                    meridiem,
                    timezone_str,
                    reset_time.strftime("%Y-%m-%d %H:%M:%S"),
                )
                return reset_time
            except ValueError as exc:
                logger.warning(f"Failed to parse timezone format reset time: {exc}")

        # Try: "Resets at 00:24" or "Resets @ 00:24:59 UTC"
        match = re.search(
            r"Resets?\s+(?:at|@)\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?(?:\s+\(([^)]+)\)|\s+(UTC|GMT|[A-Za-z/_-]+))?",
            output,
            re.IGNORECASE,
        )
        if match:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2))
                second = int(match.group(3)) if match.group(3) else 0
                meridiem = match.group(4).lower() if match.group(4) else None
                timezone_str = match.group(5) or match.group(6)
                if timezone_str:
                    self.last_timezone_str = timezone_str

                if meridiem:
                    if meridiem == "pm" and hour != 12:
                        hour += 12
                    elif meridiem == "am" and hour == 12:
                        hour = 0

                reset_time = self._convert_with_timezone(hour, minute, second, timezone_str)
                if reset_time is None:
                    reset_time = self._current_utc_with_time(hour, minute, second, now_utc=now_utc)
                return reset_time
            except ValueError:
                pass

        # Try: "Resets in X hours Y minutes"
        match = re.search(
            r"Resets?\s+in\s+(\d+)\s*(?:hours?|h)?\s+(\d+)\s*(?:minutes?|m)?",
            output,
            re.IGNORECASE,
        )
        if match:
            hours = int(match.group(1))
            minutes = int(match.group(2))
            return now_utc + timedelta(hours=hours, minutes=minutes)

        # Try: "Resets in 3h"
        match = re.search(r"Resets?\s+in\s+(\d+)\s*h", output, re.IGNORECASE)
        if match:
            hours = int(match.group(1))
            return now_utc + timedelta(hours=hours)

        # Try: "Resets in 45m"
        match = re.search(r"Resets?\s+in\s+(\d+)\s*m", output, re.IGNORECASE)
        if match:
            minutes = int(match.group(1))
            return now_utc + timedelta(minutes=minutes)

        # Try: "Next reset: 14:30"
        match = re.search(
            r"Next\s+reset[:\s]+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(UTC|GMT)?",
            output,
            re.IGNORECASE,
        )
        if match:
            try:
                hour = int(match.group(1))
                minute = int(match.group(2))
                second = int(match.group(3)) if match.group(3) else 0
                timezone_str = match.group(4)
                if timezone_str:
                    self.last_timezone_str = timezone_str
                reset_time = self._convert_with_timezone(hour, minute, second, timezone_str)
                if reset_time is None:
                    reset_time = self._current_utc_with_time(hour, minute, second, now_utc=now_utc)
                return reset_time
            except ValueError:
                pass

        return None

    def _convert_with_timezone(
        self,
        hour: int,
        minute: int,
        second: int,
        tz_label: Optional[str],
    ) -> Optional[datetime]:
        tzinfo = self._resolve_timezone(tz_label)
        if tzinfo is None:
            return None

        local_now = datetime.now(tz=tzinfo)
        reset_local = local_now.replace(hour=hour % 24, minute=minute, second=second, microsecond=0)
        if reset_local <= local_now:
            reset_local += timedelta(days=1)
        return reset_local.astimezone(timezone.utc).replace(tzinfo=None)

    @classmethod
    def _resolve_timezone(cls, tz_label: Optional[str]) -> Optional[timezone]:
        if tz_label is None:
            return None

        label = tz_label.strip()
        if not label:
            return None

        upper_label = label.upper()
        alias_target = cls.TIMEZONE_ALIASES.get(upper_label)
        if alias_target:
            label = alias_target
            upper_label = label.upper()

        if upper_label in {"UTC", "GMT"}:
            return timezone.utc

        offset_tz = cls._parse_utc_offset(label)
        if offset_tz is not None:
            return offset_tz

        try:
            return ZoneInfo(label)
        except ZoneInfoNotFoundError:
            logger.debug("usage.timezone.unknown", label=label)
            return None

    @staticmethod
    def _parse_utc_offset(label: str) -> Optional[timezone]:
        sanitized = label.strip().upper().replace(" ", "")
        match = re.fullmatch(r"(?:UTC|GMT)?([+-])(\d{1,2})(?::?(\d{2}))?", sanitized)
        if not match:
            return None

        sign = 1 if match.group(1) == "+" else -1
        hours = int(match.group(2))
        minutes = int(match.group(3)) if match.group(3) else 0
        if hours > 14 or minutes >= 60:
            return None

        delta = timedelta(hours=sign * hours, minutes=sign * minutes)
        return timezone(delta)

    @staticmethod
    def _current_utc_with_time(
        hour: int,
        minute: int,
        second: int,
        *,
        now_utc: Optional[datetime] = None,
    ) -> datetime:
        reference = now_utc or datetime.now(timezone.utc).replace(tzinfo=None)
        candidate = reference.replace(hour=hour % 24, minute=minute, second=second, microsecond=0)
        if candidate <= reference:
            candidate += timedelta(days=1)
        return candidate

    def check_should_pause(self, threshold_percent: float = 85.0) -> Tuple[bool, Optional[datetime]]:
        """Check if usage exceeds threshold

        Args:
            threshold_percent: Pause if usage >= this percent (default 85%)

        Returns:
            Tuple of (should_pause: bool, reset_time: datetime or None)
        """
        try:
            usage_percent, reset_time = self.get_usage()
            should_pause = usage_percent >= threshold_percent

            if should_pause:
                logger.warning(
                    "usage.threshold.exceeded",
                    usage_percent=usage_percent,
                    threshold_percent=threshold_percent,
                )

            return should_pause, reset_time

        except Exception as e:
            logger.error("usage.threshold.error", error=str(e))
            # Return False to not pause on error
            return False, None

    def _fallback_usage(self) -> Tuple[float, Optional[datetime]]:
        """
        Provide cached usage if available, otherwise return a conservative default.
        """
        if self.cached_usage and self.last_check_time:
            logger.debug("usage.cache.fallback")
            return self.cached_usage

        fallback = (0.0, None)
        self.cached_usage = fallback
        self.last_check_time = datetime.now(timezone.utc).replace(tzinfo=None)
        logger.info("usage.fallback.default")
        return fallback
