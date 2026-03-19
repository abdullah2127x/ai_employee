"""
logging_manager.py - Centralized logging manager for AI Employee

Complete logging system with:
1. Timeline (daily, high-level, orchestrator only)
2. Task logs (detailed, per-task, all components)
3. Error logging (with stack traces)
4. Console output (optional)
5. Log level filtering (ERROR, WARNING, INFO, DEBUG, CRITICAL)

Based on requirements in Logging_Requirements.md

Note: All configuration is obtained from core.config.settings
"""

from pathlib import Path
from datetime import datetime
from typing import Optional
import traceback
import sys

# File locking - different for Windows vs Unix
if sys.platform != 'win32':
    import fcntl

# Import settings from core.config
from core.config import settings


class LoggingManager:
    """
    Centralized logging manager for AI Employee.

    Provides complete logging solution:
    - Daily timeline logging (orchestrator only)
    - Per-task detailed logging (all components, optional)
    - Error logging with stack traces
    - Console output (enabled in dev mode, disabled in production)
    - Log level filtering (from settings)
    - Thread-safe file operations
    
    Configuration:
        All paths from core.config.settings:
        - logs_dir: settings.logs_dir (vault_path / "Logs")
        - enable_console: settings.dev_mode (disabled in production)
        
        Log level passed as parameter:
        - log_level: Passed to constructor (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                   Allows different components to use different log levels
    """

    def __init__(self, log_level: str = "WARNING"):
        """
        Initialize logging manager.
        
        Args:
            log_level: Minimum log level for filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                      Defaults to WARNING for balanced logging
        """
        # Use centralized settings for paths and console output
        self.logs_dir = settings.logs_dir
        self.timeline_dir = self.logs_dir / "timeline"
        self.tasks_dir = self.logs_dir / "tasks"
        self.errors_dir = self.logs_dir / "errors"

        # Create directories
        settings.ensure_vault_directories()  # This creates logs_dir too

        # Console output - disabled in production mode
        self.enable_console = settings.dev_mode
        
        # Log level filtering - passed as parameter (not from settings)
        # This allows different components to use different log levels
        self.log_levels = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4
        }
        self.min_log_level = self.log_levels.get(log_level.upper(), 2)

    def _should_log(self, level: str) -> bool:
        """Check if message should be logged based on level"""
        return self.log_levels.get(level.upper(), 1) >= self.min_log_level

    def _print_to_console(self, level: str, message: str, actor: str = ""):
        """Print to console if enabled"""
        if not self.enable_console:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        level_symbol = {
            "DEBUG": "🔍",
            "INFO": "ℹ️",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "CRITICAL": "🔥"
        }
        symbol = level_symbol.get(level.upper(), "•")

        if actor:
            print(f"{timestamp} [{actor}] {symbol} {message}")
        else:
            print(f"{timestamp} {symbol} {message}")

    def get_timeline_path(self) -> Path:
        """Get today's timeline file path"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.timeline_dir / f"{today}.md"

    def get_task_log_path(self, task_type: str, task_id: str) -> Path:
        """
        Get task log file path.

        Args:
            task_type: Type of task (file_drop, email, whatsapp, etc.)
            task_id: Unique task identifier

        Returns:
            Path to task log file
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        # Sanitize task_id for filename
        safe_id = task_id[:50].replace("/", "_").replace("\\", "_").replace(" ", "_")
        return self.tasks_dir / f"task-{task_type}_{timestamp}_{safe_id}.md"

    def get_error_log_path(self) -> Path:
        """Get today's error log file path"""
        today = datetime.now().strftime("%Y-%m-%d")
        return self.errors_dir / f"errors_{today}.md"

    # ========================================================================
    # Timeline Logging (Orchestrator Only)
    # ========================================================================

    def write_to_timeline(
        self,
        message: str,
        actor: str = "orchestrator",
        level: str = "INFO"
    ):
        """
        Append to daily timeline (orchestrator only).

        Format: HH:MM:SS [actor] → message

        Args:
            message: Log message (can include emojis)
            actor: Component name (default: "orchestrator")
            level: Log level (INFO, WARNING, ERROR, etc.)
        """
        if not self._should_log(level):
            return

        timeline_path = self.get_timeline_path()
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Create header if file doesn't exist
        if not timeline_path.exists():
            with open(timeline_path, 'w', encoding='utf-8') as f:
                f.write(f"# {datetime.now().strftime('%Y-%m-%d')} Activity Log\n\n")

        # Append log line with level indicator
        level_prefix = {
            "DEBUG": "[DEBUG] ",
            "INFO": "",
            "WARNING": "⚠️ ",
            "ERROR": "❌ ERROR: ",
            "CRITICAL": "🔥 CRITICAL: "
        }
        prefix = level_prefix.get(level.upper(), "")
        log_line = f"{timestamp} [{actor}] → {prefix}{message}\n"

        self._safe_append(timeline_path, log_line)
        self._print_to_console(level, message, actor)

    # ========================================================================
    # Task Logging (All Components)
    # ========================================================================

    def write_to_task_log(
        self,
        task_type: str,
        task_id: str,
        message: str,
        actor: str,
        trigger_file: Optional[str] = None,
        status: str = "in_progress",
        level: str = "INFO"
    ):
        """
        Append to per-task detailed log.

        Creates task log file with metadata header if new.

        Args:
            task_type: Type of task (file_drop, email, whatsapp, etc.)
            task_id: Unique task identifier
            message: Log message
            actor: Component name (filesystem_watcher, orchestrator, etc.)
            trigger_file: Path to file that triggered this task
            status: Task status (in_progress, completed, failed, skipped)
            level: Log level (INFO, WARNING, ERROR, etc.)
        """
        if not self._should_log(level):
            return

        task_log_path = self.get_task_log_path(task_type, task_id)
        timestamp = datetime.now().strftime("%H:%M:%S")
        iso_timestamp = datetime.now().isoformat()

        # Create header if file doesn't exist
        if not task_log_path.exists():
            with open(task_log_path, 'w', encoding='utf-8') as f:
                f.write(f"""# Task {task_id}

trigger_file:    {trigger_file or 'N/A'}
created:         {iso_timestamp}
status:          {status}
final_result:    pending
duration_sec:    0

## Event Timeline

""")

        # Append log line with level indicator
        level_prefix = {
            "DEBUG": "[DEBUG] ",
            "INFO": "",
            "WARNING": "⚠️ ",
            "ERROR": "❌ ERROR: ",
            "CRITICAL": "🔥 CRITICAL: "
        }
        prefix = level_prefix.get(level.upper(), "")
        log_line = f"{timestamp} [{actor}] {prefix}{message}\n"

        self._safe_append(task_log_path, log_line)
        self._print_to_console(level, message, actor)

    def update_task_status(
        self,
        task_type: str,
        task_id: str,
        status: str,
        final_result: Optional[str] = None
    ):
        """
        Update task log status (at end of processing).

        Args:
            task_type: Type of task
            task_id: Unique task identifier
            status: New status (completed, failed, skipped)
            final_result: Brief description of result
        """
        # Find the task log file (most recent for this task_id)
        task_log_path = self._find_task_log(task_type, task_id)

        if not task_log_path or not task_log_path.exists():
            return

        # Read file
        with open(task_log_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Update status in header
        content = content.replace("status:          in_progress", f"status:          {status}")
        if final_result:
            content = content.replace("final_result:    pending", f"final_result:    {final_result}")

        # Write back
        with open(task_log_path, 'w', encoding='utf-8') as f:
            f.write(content)

    # ========================================================================
    # Error Logging (With Stack Traces)
    # ========================================================================

    def log_error(
        self,
        message: str,
        error: Optional[Exception] = None,
        actor: str = "system",
        log_stack_trace: bool = True
    ):
        """
        Log an error with optional stack trace.

        Args:
            message: Error message
            error: Exception object (optional, for stack trace)
            actor: Component name
            log_stack_trace: Whether to log full stack trace (default: True)
        """
        if not self._should_log("ERROR"):
            return

        # Log to timeline
        error_message = f"{message}"
        if error:
            error_message += f" - {type(error).__name__}: {str(error)}"

        self.write_to_timeline(error_message, actor=actor, level="ERROR")

        # Log stack trace to error file if exception provided
        if error and log_stack_trace:
            self._log_stack_trace(message, error, actor)

        # Also print to console
        self._print_to_console("ERROR", error_message, actor)

    def _log_stack_trace(
        self,
        message: str,
        error: Exception,
        actor: str
    ):
        """
        Log full stack trace to error file.

        Args:
            message: Error message
            error: Exception object
            actor: Component name
        """
        error_path = self.get_error_log_path()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Create header if file doesn't exist
        if not error_path.exists():
            with open(error_path, 'w', encoding='utf-8') as f:
                f.write(f"# {datetime.now().strftime('%Y-%m-%d')} Error Log\n\n")

        # Append error entry
        with open(error_path, 'a', encoding='utf-8') as f:
            f.write(f"\n## {timestamp} - {actor}\n\n")
            f.write(f"**Message:** {message}\n\n")
            f.write(f"**Exception:** {type(error).__name__}: {str(error)}\n\n")
            f.write("### Stack Trace\n\n")
            f.write("```\n")
            f.write(traceback.format_exc())
            f.write("```\n\n")
            f.write("---\n\n")

    def log_warning(
        self,
        message: str,
        actor: str = "system"
    ):
        """
        Log a warning message.

        Args:
            message: Warning message
            actor: Component name
        """
        if not self._should_log("WARNING"):
            return

        self.write_to_timeline(message, actor=actor, level="WARNING")
        self._print_to_console("WARNING", message, actor)

    def log_critical(
        self,
        message: str,
        error: Optional[Exception] = None,
        actor: str = "system"
    ):
        """
        Log a critical error (system-breaking).

        Args:
            message: Critical error message
            error: Exception object (optional)
            actor: Component name
        """
        if not self._should_log("CRITICAL"):
            return

        error_message = f"{message}"
        if error:
            error_message += f" - {type(error).__name__}: {str(error)}"

        self.write_to_timeline(error_message, actor=actor, level="CRITICAL")

        # Always log stack trace for critical errors
        if error:
            self._log_stack_trace(message, error, actor)

        self._print_to_console("CRITICAL", error_message, actor)

    def log_debug(
        self,
        message: str,
        actor: str = "system"
    ):
        """
        Log a debug message (only in DEBUG mode).

        Args:
            message: Debug message
            actor: Component name
        """
        if not self._should_log("DEBUG"):
            return

        self.write_to_timeline(f"[DEBUG] {message}", actor=actor, level="DEBUG")
        self._print_to_console("DEBUG", message, actor)

    # ========================================================================
    # Utility Methods
    # ========================================================================

    def _find_task_log(self, task_type: str, task_id: str) -> Optional[Path]:
        """
        Find the most recent task log for a given task_id.

        Args:
            task_type: Type of task
            task_id: Unique task identifier

        Returns:
            Path to task log file or None if not found
        """
        # Search for existing task logs matching this task_id
        pattern = f"task-{task_type}*_{task_id[:30]}*.md"
        matching_files = list(self.tasks_dir.glob(pattern))

        if matching_files:
            # Return most recent (sorted by modification time)
            return max(matching_files, key=lambda p: p.stat().st_mtime)

        # Return path where it would be created
        return self.get_task_log_path(task_type, task_id)

    def _safe_append(self, file_path: Path, content: str):
        """
        Thread-safe file append with locking.

        Args:
            file_path: Path to file
            content: Content to append
        """
        with open(file_path, 'a', encoding='utf-8') as f:
            # Apply file locking on Unix systems
            if sys.platform != 'win32':
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)  # Acquire lock

            f.write(content)
            f.flush()  # Ensure written to disk

            # Release lock on Unix systems
            if sys.platform != 'win32':
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)

    def get_log_summary(self) -> str:
        """
        Get summary of logging configuration.

        Returns:
            Summary string
        """
        return f"""
Logging Configuration:
  Logs Directory: {self.logs_dir}
  Timeline: {self.timeline_dir}
  Tasks: {self.tasks_dir}
  Errors: {self.errors_dir}
  Console Output: {'Enabled' if self.enable_console else 'Disabled'}
  Minimum Log Level: {list(self.log_levels.keys())[list(self.log_levels.values()).index(self.min_log_level)]}
  Mode: {'Development' if self.enable_console else 'Production'}
""".strip()


# ============================================================================
# Convenience Functions
# ============================================================================

def get_logger(log_level: str = "WARNING") -> LoggingManager:
    """
    Get a LoggingManager instance.
    
    Args:
        log_level: Minimum log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
                  Defaults to WARNING for balanced logging
    
    Returns:
        LoggingManager instance
    """
    return LoggingManager(log_level=log_level)
