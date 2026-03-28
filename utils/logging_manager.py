"""
logging_manager.py - Clean centralized logging for AI Employee (Option B)
"""

from pathlib import Path
from datetime import datetime
import traceback
import sys

from core.config import settings


class LoggingManager:
    """
    Simplified Logging Manager for Option B.
    
    Keeps only:
    - Daily Timeline (main high-level log)
    - Error logs with stack traces
    - Console output (controlled by dev_mode)
    """

    def __init__(self):
        self.logs_dir = settings.logs_dir
        self.timeline_dir = self.logs_dir / "timeline"
        self.errors_dir = self.logs_dir / "errors"

        # Create directories
        settings.ensure_vault_directories()
        self.timeline_dir.mkdir(parents=True, exist_ok=True)
        self.errors_dir.mkdir(parents=True, exist_ok=True)

        self.enable_console = settings.dev_mode

        # Log levels
        self.log_level_values = {
            "DEBUG": 0, "INFO": 1, "WARNING": 2, "ERROR": 3, "CRITICAL": 4
        }
        self.min_log_level_value = self.log_level_values.get(settings.min_log_level.upper(), 1)

    def _should_log(self, message_level: str) -> bool:
        message_level_value = self.log_level_values.get(message_level.upper(), 1)
        return message_level_value >= self.min_log_level_value

    def _print_to_console(self, message_level: str, message: str, actor: str = ""):
        if not self.enable_console:
            return
        timestamp = datetime.now().strftime("%H:%M:%S")
        symbol = {"DEBUG": "🔍", "INFO": "ℹ️", "WARNING": "⚠️", "ERROR": "❌", "CRITICAL": "🔥"}.get(message_level.upper(), "•")
        prefix = f"{timestamp} [{actor}]" if actor else f"{timestamp}"
        print(f"{prefix} {symbol} {message}")

    def get_timeline_path(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.timeline_dir / f"{today}.md"

    def get_error_log_path(self) -> Path:
        today = datetime.now().strftime("%Y-%m-%d")
        return self.errors_dir / f"errors_{today}.md"

    # ====================== Main Logging Methods ======================

    def write_to_timeline(self, message: str, actor: str = "system", message_level: str = "INFO"):
        """Main high-level logging method - used by watchers, orchestrator, etc."""
        if not self._should_log(message_level):
            return

        timeline_path = self.get_timeline_path()
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Create header if new file
        if not timeline_path.exists():
            with open(timeline_path, 'w', encoding='utf-8') as f:
                f.write(f"# {datetime.now().strftime('%Y-%m-%d')} AI Employee Timeline\n\n")

        level_prefix = {
            "DEBUG": "[DEBUG] ",
            "INFO": "",
            "WARNING": "⚠️ ",
            "ERROR": "❌ ERROR: ",
            "CRITICAL": "🔥 CRITICAL: "
        }.get(message_level.upper(), "")

        log_line = f"{timestamp} [{actor}] → {level_prefix}{message}\n"

        self._safe_append(timeline_path, log_line)
        self._print_to_console(message_level, message, actor)

    def log_error(self, message: str, error: Exception = None, actor: str = "system"):
        """Log error to timeline + detailed error file with stack trace."""
        if not self._should_log("ERROR"):
            return

        error_msg = message
        if error:
            error_msg += f" - {type(error).__name__}: {str(error)}"

        self.write_to_timeline(error_msg, actor=actor, message_level="ERROR")

        if error:
            self._log_stack_trace(message, error, actor)

        self._print_to_console("ERROR", error_msg, actor)

    def log_warning(self, message: str, actor: str = "system"):
        self.write_to_timeline(message, actor=actor, message_level="WARNING")
        self._print_to_console("WARNING", message, actor)

    def log_debug(self, message: str, actor: str = "system"):
        self.write_to_timeline(f"[DEBUG] {message}", actor=actor, message_level="DEBUG")
        self._print_to_console("DEBUG", message, actor)

    def _log_stack_trace(self, message: str, error: Exception, actor: str):
        """Append full stack trace to daily error log."""
        error_path = self.get_error_log_path()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if not error_path.exists():
            with open(error_path, 'w', encoding='utf-8') as f:
                f.write(f"# {datetime.now().strftime('%Y-%m-%d')} Error Log\n\n")

        with open(error_path, 'a', encoding='utf-8') as f:
            f.write(f"\n## {timestamp} - {actor}\n\n")
            f.write(f"**Message:** {message}\n\n")
            f.write(f"**Exception:** {type(error).__name__}: {str(error)}\n\n")
            f.write("### Stack Trace\n\n```\n")
            f.write(traceback.format_exc())
            f.write("```\n\n---\n\n")

    def _safe_append(self, file_path: Path, content: str):
        """Simple safe append."""
        with open(file_path, 'a', encoding='utf-8') as f:
            f.write(content)
            f.flush()


# Convenience function
def get_logger() -> LoggingManager:
    return LoggingManager()