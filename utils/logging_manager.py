"""
logging_manager.py - Centralized logging manager for AI Employee

Complete logging system with:
1. Timeline (daily, high-level, orchestrator only)
2. Task logs (detailed, per-task, all components)
3. Error logs (with stack traces)
4. Console output (optional)
5. Log level filtering (DEBUG, INFO, WARNING, ERROR, CRITICAL)

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
        All settings from core.config.settings:
        - logs_dir: Directory for log files (vault_path / "Logs")
        - enable_console: True in dev mode, False in production  
        - min_log_level: Minimum message level to log (from .env)
    """

    def __init__(self):
        """
        Initialize logging manager.
        
        All configuration is automatically obtained from core.config.settings:
        - logs_dir: Directory for log files
        - enable_console: True in dev mode, False in production
        - min_log_level: Minimum message level to log (from settings.min_log_level)
        """
        # Use centralized settings for paths and console output
        self.logs_dir = settings.logs_dir
        self.timeline_dir = self.logs_dir / "timeline"
        self.tasks_dir = self.logs_dir / "tasks"
        self.errors_dir = self.logs_dir / "errors"

        # Create directories
        settings.ensure_vault_directories()  # This creates logs_dir
        self.timeline_dir.mkdir(parents=True, exist_ok=True)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)
        self.errors_dir.mkdir(parents=True, exist_ok=True)

        # Console output - disabled in production mode
        self.enable_console = settings.dev_mode
        
        # Log level filtering - obtained from settings (centralized in .env)
        self.log_level_values = {
            "DEBUG": 0,
            "INFO": 1,
            "WARNING": 2,
            "ERROR": 3,
            "CRITICAL": 4
        }
        self.min_log_level_value = self.log_level_values.get(settings.min_log_level.upper(), 2)

    def _should_log(self, message_level: str) -> bool:
        """
        Check if message should be logged based on its level.
        
        Args:
            message_level: The level of this specific message (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        
        Returns:
            True if message_level >= min_log_level_value (message should be logged)
            False if message_level < min_log_level_value (message filtered out)
        """
        message_level_value = self.log_level_values.get(message_level.upper(), 1)
        return message_level_value >= self.min_log_level_value

    def _print_to_console(self, message_level: str, message: str, actor: str = ""):
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
        symbol = level_symbol.get(message_level.upper(), "•")

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
        message_level: str = "INFO"
    ):
        """
        Append to daily timeline (orchestrator only).

        Format: HH:MM:SS [actor] → message

        Args:
            message: Log message (can include emojis)
            actor: Component name (default: "orchestrator")
            message_level: Level of this message (INFO, WARNING, ERROR, etc.)
        """
        if not self._should_log(message_level):
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
        prefix = level_prefix.get(message_level.upper(), "")
        log_line = f"{timestamp} [{actor}] → {prefix}{message}\n"

        self._safe_append(timeline_path, log_line)
        self._print_to_console(message_level, message, actor)

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
        message_level: str = "INFO"
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
            message_level: Level of this message (INFO, WARNING, ERROR, etc.)
        """
        if not self._should_log(message_level):
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
        prefix = level_prefix.get(message_level.upper(), "")
        log_line = f"{timestamp} [{actor}] {prefix}{message}\n"

        self._safe_append(task_log_path, log_line)
        self._print_to_console(message_level, message, actor)

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

        self.write_to_timeline(error_message, actor=actor, message_level="ERROR")

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

        self.write_to_timeline(message, actor=actor, message_level="WARNING")
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

        self.write_to_timeline(error_message, actor=actor, message_level="CRITICAL")

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

        self.write_to_timeline(f"[DEBUG] {message}", actor=actor, message_level="DEBUG")
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
        # Find the level name from the value
        level_name = [name for name, value in self.log_level_values.items() if value == self.min_log_level_value][0]
        
        return f"""
Logging Configuration:
  Logs Directory: {self.logs_dir}
  Timeline: {self.timeline_dir}
  Tasks: {self.tasks_dir}
  Errors: {self.errors_dir}
  Console Output: {'Enabled' if self.enable_console else 'Disabled'}
  Minimum Log Level: {level_name} (messages at or above this level are logged)
  Mode: {'Development' if self.enable_console else 'Production'}
""".strip()


# ============================================================================
# Convenience Functions
# ============================================================================

def get_logger() -> LoggingManager:
    """
    Get a LoggingManager instance.
    
    All configuration is obtained from core.config.settings.
    
    Returns:
        LoggingManager instance
    """
    return LoggingManager()
