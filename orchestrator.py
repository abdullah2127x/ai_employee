#!/usr/bin/env python3
"""
orchestrator.py - AI Employee Orchestrator (v2.2)

New in v2.1:
- Runner_Status/ watcher: orchestrator now sees EXACTLY what claude_runner
  produced (done / pending_approval / needs_revision / runner_error).
  No more blind spot — full visibility without changing the subprocess model.
- Retry limit: Needs_Revision tasks are re-queued up to MAX_RETRIES times.
  After that they move to Dead_Letter/ and a warning is logged.
  retry_count is tracked in the task file's YAML frontmatter.
- Dead_Letter/ folder: tasks that failed MAX_RETRIES times land here.

New in v2.2:
- Concurrent-safe: claude_runner now uses unique temp files per task_id
- Stale prompt cleanup: removes old temp prompt files on startup

Architecture unchanged:
- FilesystemWatcher (Drop/) → Needs_Action/
- Orchestrator FolderWatcher → Processing/ → claude_runner subprocess
- claude_runner writes Runner_Status/<task_id>.json when done
- Orchestrator FolderWatcher on Runner_Status/ reads outcome
"""

import os
import sys
import time
import json
import subprocess
import threading
import shutil
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict

project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings
from utils.logging_manager import LoggingManager
from utils.task_template import increment_retry_count
from utils.dashboard import write_dashboard

from watchers.folder_watcher import FolderWatcher
from watchers.filesystem_watcher import FilesystemWatcher
from watchers.gmail_watcher_oauth import GmailWatcher
from watchers.gmail_watcher_imap import GmailWatcherIMAP

logger = LoggingManager()

# Maximum times a task is retried from Needs_Revision before Dead_Letter
MAX_RETRIES = 3


def cleanup_stale_prompt_files():
    """
    Remove stale prompt temp files older than 1 hour.
    
    Called once at orchestrator startup to clean up after crashed runs.
    Prevents accumulation of _prompt_*.tmp files in vault/.claude/
    """
    prompt_folder = settings.vault_path / ".claude"
    if not prompt_folder.exists():
        return
    
    cutoff = datetime.now() - timedelta(hours=1)
    cleaned_count = 0
    
    for tmp_file in prompt_folder.glob("_prompt_*.tmp"):
        try:
            file_mtime = datetime.fromtimestamp(tmp_file.stat().st_mtime)
            if file_mtime < cutoff:
                tmp_file.unlink()
                cleaned_count += 1
                logger.write_to_timeline(
                    f"Cleaned up stale prompt file: {tmp_file.name}",
                    actor="orchestrator",
                    message_level="INFO",
                )
        except Exception:
            pass
    
    if cleaned_count > 0:
        logger.write_to_timeline(
            f"Startup cleanup: removed {cleaned_count} stale prompt file(s)",
            actor="orchestrator",
            message_level="INFO",
        )


class Orchestrator:
    """
    AI Employee Orchestrator — manages all workflow folders and subprocesses.

    Folder responsibilities:
        Needs_Action/    → move to Processing/, call claude_runner
        Processing/      → timeout tracking only (file left = claude done)
        Runner_Status/   → read outcome from claude_runner, log, clean up
        Approved/        → execute approved action (stub → MCP future)
        Rejected/        → log, archive
        Needs_Revision/  → re-queue up to MAX_RETRIES, then Dead_Letter/
    """

    def __init__(self):
        self.file_move_times: Dict[str, datetime] = {}
        self.timeout_seconds = 300  # Set to 300 (5 min) for production

        self.observer_threads = []

        # Filesystem Watcher (Drop/ folder)
        self.filesystem_watcher = None
        if settings.enable_filesystem_watcher:
            self.filesystem_watcher = FilesystemWatcher()
            logger.write_to_timeline(
                "Filesystem Watcher enabled (Drop/ monitored)",
                actor="orchestrator",
                message_level="INFO",
            )
        else:
            logger.write_to_timeline(
                "Filesystem Watcher disabled",
                actor="orchestrator",
                message_level="WARNING",
            )

        # Gmail Watcher
        self.gmail_watcher = None
        self.gmail_watcher_thread = None
        if settings.enable_gmail_watcher:
            try:
                # Check mode: 'imap' (development) or 'oauth' (production)
                watcher_mode = settings.gmail_watcher_mode.lower()
                
                if watcher_mode == "imap":
                    # IMAP mode (development) - uses app password
                    if not settings.gmail_imap_address or not settings.gmail_imap_app_password:
                        logger.log_error(
                            "Gmail IMAP credentials missing. Set GMAIL_IMAP_ADDRESS "
                            "and GMAIL_IMAP_APP_PASSWORD in .env",
                            actor="orchestrator",
                        )
                    else:
                        self.gmail_watcher = GmailWatcherIMAP(
                            email_address=settings.gmail_imap_address,
                            app_password=settings.gmail_imap_app_password,
                            check_interval=settings.gmail_watcher_check_interval,
                            gmail_query=settings.gmail_watcher_query,
                        )
                        logger.write_to_timeline(
                            f"Gmail Watcher enabled (IMAP mode) | Email: {settings.gmail_imap_address} | "
                            f"Query: {settings.gmail_watcher_query} | Interval: {settings.gmail_watcher_check_interval}s",
                            actor="orchestrator",
                            message_level="INFO",
                        )
                
                elif watcher_mode == "oauth":
                    # OAuth mode (production) - uses credentials.json
                    creds_path = settings.gmail_credentials_path
                    if creds_path is None:
                        creds_path = settings.vault_path / "credentials.json"

                    self.gmail_watcher = GmailWatcher(
                        credentials_path=creds_path,
                        check_interval=settings.gmail_watcher_check_interval,
                        gmail_query=settings.gmail_watcher_query,
                    )
                    logger.write_to_timeline(
                        f"Gmail Watcher enabled (OAuth mode) | Query: {settings.gmail_watcher_query} | "
                        f"Interval: {settings.gmail_watcher_check_interval}s",
                        actor="orchestrator",
                        message_level="INFO",
                    )
                
                else:
                    logger.log_error(
                        f"Invalid GMAIL_WATCHER_MODE: {watcher_mode}. Must be 'imap' or 'oauth'",
                        actor="orchestrator",
                    )
                    
            except ImportError as e:
                logger.log_warning(
                    f"Gmail Watcher disabled - libraries not installed: {e}",
                    actor="orchestrator",
                )
            except Exception as e:
                logger.log_error(
                    f"Gmail Watcher initialization error: {e}",
                    actor="orchestrator",
                )
        else:
            logger.write_to_timeline(
                "Gmail Watcher disabled (enable in settings)",
                actor="orchestrator",
                message_level="INFO",
            )

        # Ensure Runner_Status/ and Dead_Letter/ exist
        (settings.vault_path / "Runner_Status").mkdir(parents=True, exist_ok=True)
        (settings.vault_path / "Dead_Letter").mkdir(parents=True, exist_ok=True)
        (settings.vault_path / "Processing_Archive").mkdir(parents=True, exist_ok=True)

        # Folder watchers
        self.watchers = {
            "needs_action": FolderWatcher(
                str(settings.needs_action_path), self.on_needs_action_change
            ),
            "processing": FolderWatcher(str(settings.processing_path), self.on_processing_change),
            "runner_status": FolderWatcher(
                str(settings.vault_path / "Runner_Status"), self.on_runner_status_change
            ),
            "approved": FolderWatcher(str(settings.approved_path), self.on_approved_change),
            "rejected": FolderWatcher(str(settings.rejected_path), self.on_rejected_change),
            "needs_revision": FolderWatcher(
                str(settings.needs_revision_path), self.on_revision_change
            ),
        }

        logger.write_to_timeline(
            "Orchestrator initialized", actor="orchestrator", message_level="INFO"
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    def start(self):
        logger.write_to_timeline(
            "Orchestrator starting", actor="orchestrator", message_level="INFO"
        )

        # Start Filesystem Watcher
        if self.filesystem_watcher:
            t = threading.Thread(target=self.filesystem_watcher.run, daemon=True)
            t.start()
            logger.write_to_timeline(
                "Filesystem Watcher started", actor="orchestrator", message_level="INFO"
            )

        # Start Gmail Watcher in background thread
        if self.gmail_watcher and self.gmail_watcher.service:
            self.gmail_watcher_thread = threading.Thread(
                target=self.gmail_watcher.run,
                daemon=True,
                name="GmailWatcher"
            )
            self.gmail_watcher_thread.start()
            logger.write_to_timeline(
                "Gmail Watcher started (background thread)",
                actor="orchestrator",
                message_level="INFO",
            )

        # Start folder watchers
        for name, watcher in self.watchers.items():
            watcher.start()
            self.observer_threads.append(watcher.observer)
            logger.write_to_timeline(
                f"Folder Watcher started: {name}",
                actor="orchestrator",
                message_level="INFO",
            )

        logger.write_to_timeline(
            f"All watchers started | active threads: {threading.active_count()}",
            actor="orchestrator",
            message_level="INFO",
        )

        for name, watcher in self.watchers.items():
            alive = watcher.observer.is_alive() if watcher.observer else False
            logger.write_to_timeline(
                f"Watcher '{name}' alive: {alive}",
                actor="orchestrator",
                message_level="INFO" if alive else "WARNING",
            )

        write_dashboard(settings.vault_path)
        logger.write_to_timeline(
            "Dashboard.md initialized",
            actor="orchestrator",
            message_level="INFO",
        )

        try:
            while True:
                time.sleep(60)
                self.check_timeouts()
        except KeyboardInterrupt:
            logger.write_to_timeline(
                "Interrupt received", actor="orchestrator", message_level="INFO"
            )
            self.stop()

    def stop(self):
        if self.filesystem_watcher:
            self.filesystem_watcher.stop()
        for watcher in self.watchers.values():
            watcher.stop()
        logger.write_to_timeline("Orchestrator stopped", actor="orchestrator", message_level="INFO")

    # ── Folder callbacks ──────────────────────────────────────────────────

    def on_needs_action_change(self, event_type: str, file_path: str):
        if event_type != "created":
            return

        path = Path(file_path)
        if path.suffix != ".md" or path.name.startswith("."):
            return

        logger.write_to_timeline(
            f"New task: {path.name}",
            actor="orchestrator",
            message_level="INFO",
        )

        self._move_to_processing(path)

        processing_path = settings.processing_path / path.name
        self.file_move_times[str(processing_path)] = datetime.now()
        self._call_claude_runner(processing_path)

    def on_processing_change(self, event_type: str, file_path: str):
        """File left Processing/ — Claude runner finished (or timed out)."""
        if event_type not in ("deleted", "moved"):
            return

        if file_path in self.file_move_times:
            del self.file_move_times[file_path]

    def on_runner_status_change(self, event_type: str, file_path: str):
        """
        Claude runner wrote a status file.
        Read it, log the outcome, update Dashboard.md, clean up.
        """
        if event_type != "created":
            return

        path = Path(file_path)
        if path.suffix != ".json" or path.name.startswith("."):
            return

        try:
            status = json.loads(path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.log_error(
                f"Could not read status file {path.name}: {e}",
                actor="orchestrator",
            )
            return

        task_id = status.get("task_id", "unknown")
        outcome = status.get("outcome", "unknown")
        detail = status.get("detail", "")

        level = "INFO" if outcome in ("done", "pending_approval") else "WARNING"
        msg = f"Runner outcome: {outcome} | task: {task_id}"
        if detail:
            msg += f" | {detail}"

        logger.write_to_timeline(msg, actor="orchestrator", message_level=level)

        if outcome == "runner_error":
            logger.log_error(
                f"Claude runner reported error for task {task_id}: {detail}",
                actor="orchestrator",
            )

        # Clean up status file
        try:
            path.unlink()
        except Exception:
            pass

        # Update Dashboard.md after every task outcome
        success = write_dashboard(settings.vault_path)
        if success:
            logger.write_to_timeline(
                "Dashboard.md updated",
                actor="orchestrator",
                message_level="INFO",
            )
        else:
            logger.log_warning(
                "Dashboard.md update failed",
                actor="orchestrator",
            )

    def on_approved_change(self, event_type: str, file_path: str):
        if event_type != "created":
            return

        path = Path(file_path)
        logger.write_to_timeline(
            f"Approved: {path.name}",
            actor="orchestrator",
            message_level="INFO",
        )

        # TODO: parse approval file, call appropriate MCP server
        # For now: move to Done/ as placeholder
        self._execute_approved_action(path)

    def on_rejected_change(self, event_type: str, file_path: str):
        if event_type != "created":
            return

        logger.write_to_timeline(
            f"Rejected: {Path(file_path).name}",
            actor="orchestrator",
            message_level="WARNING",
        )
        # Leave in Rejected/ as archive — no further action

    def on_revision_change(self, event_type: str, file_path: str):
        """
        Task needs revision. Re-queue up to MAX_RETRIES times.
        After that, move to Dead_Letter/ and log a warning.
        """
        if event_type != "created":
            return

        path = Path(file_path)
        if path.suffix != ".md" or path.name.startswith("."):
            return

        logger.write_to_timeline(
            f"Needs revision: {path.name}",
            actor="orchestrator",
            message_level="WARNING",
        )

        # Read task file to check retry count
        try:
            content = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.log_error(f"Cannot read revision file {path.name}: {e}", actor="orchestrator")
            return

        # Increment retry count
        updated_content, new_count = increment_retry_count(content)

        if new_count > MAX_RETRIES:
            # Too many retries — move to Dead_Letter/
            dead_letter = settings.vault_path / "Dead_Letter"
            dead_letter.mkdir(parents=True, exist_ok=True)
            dest = dead_letter / path.name

            if dest.exists():
                dest.unlink()
            shutil.move(str(path), str(dest))

            logger.write_to_timeline(
                f"DEAD LETTER: {path.name} failed {new_count - 1} times — moved to Dead_Letter/",
                actor="orchestrator",
                message_level="WARNING",
            )
            return

        # Write updated retry count back to file
        try:
            path.write_text(updated_content, encoding="utf-8")
        except Exception as e:
            logger.log_error(f"Cannot update retry_count in {path.name}: {e}", actor="orchestrator")
            return

        # Re-queue to Needs_Action/ — FolderWatcher will detect and reprocess
        dest = settings.needs_action_path / path.name
        if dest.exists():
            dest.unlink()

        shutil.move(str(path), str(dest))

        logger.write_to_timeline(
            f"Re-queued (attempt {new_count}/{MAX_RETRIES}): {path.name}",
            actor="orchestrator",
            message_level="INFO",
        )

    # ── Internal helpers ──────────────────────────────────────────────────

    def _move_to_processing(self, file_path: Path):
        dest = settings.processing_path / file_path.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(file_path), str(dest))
        logger.write_to_timeline(
            f"Moved to Processing/: {file_path.name}",
            actor="orchestrator",
            message_level="INFO",
        )

    def _call_claude_runner(self, file_path: Path):
        cmd = [sys.executable, str(project_root / "claude_runner.py"), str(file_path)]

        logger.write_to_timeline(
            f"Calling Claude Runner: {file_path.name}",
            actor="orchestrator",
            message_level="INFO",
        )

        try:
            process = subprocess.Popen(cmd)

            if not hasattr(self, "claude_processes"):
                self.claude_processes = []

            # Prune finished processes to prevent unbounded list growth
            self.claude_processes = [p for p in self.claude_processes if p.poll() is None]
            self.claude_processes.append(process)

            logger.write_to_timeline(
                f"Claude Runner started (PID: {process.pid})",
                actor="orchestrator",
                message_level="INFO",
            )

        except Exception as e:
            logger.log_error(f"Failed to start Claude Runner: {e}", error=e, actor="orchestrator")

    def _execute_approved_action(self, file_path: Path):
        """Execute an approved action. Currently moves to Done/ (MCP stub)."""
        try:
            dest = settings.done_path / file_path.name
            if dest.exists():
                dest.unlink()
            shutil.move(str(file_path), str(dest))
            logger.write_to_timeline(
                f"Approved action executed (stub → Done/): {file_path.name}",
                actor="orchestrator",
                message_level="INFO",
            )
        except Exception as e:
            logger.log_error(
                f"Failed to execute approved action: {e}", error=e, actor="orchestrator"
            )

    def check_timeouts(self):
        """
        Detect tasks stuck in Processing/ — means claude_runner crashed
        before writing a status file or touching any file.
        """
        now = datetime.now()

        for file_path_str, move_time in list(self.file_move_times.items()):
            elapsed = (now - move_time).seconds

            if elapsed > self.timeout_seconds:
                file_path = Path(file_path_str)

                logger.write_to_timeline(
                    f"Timeout: {file_path.name} stuck {elapsed}s > {self.timeout_seconds}s",
                    actor="orchestrator",
                    message_level="WARNING",
                )

                self._move_back_to_needs_action(file_path)

                # FIX: use pop() not del — on_processing_change() may have
                # already removed this key when the file move was detected
                self.file_move_times.pop(file_path_str, None)
                

    def _move_back_to_needs_action(self, file_path: Path):
        if not file_path.exists():
            # Claude runner already finished and moved the file — just clean up tracker
            logger.write_to_timeline(
                f"Timeout resolved — file already processed: {file_path.name}",
                actor="orchestrator",
                message_level="INFO",
            )
            return

        dest = settings.needs_action_path / file_path.name
        if dest.exists():
            dest.unlink()
        shutil.move(str(file_path), str(dest))

        logger.write_to_timeline(
            f"Timeout — moved back to Needs_Action/: {file_path.name}",
            actor="orchestrator",
            message_level="WARNING",
        )


def main():
    logger.write_to_timeline(
        "AI Employee Orchestrator v2.2 starting",
        actor="orchestrator",
        message_level="INFO",
    )

    settings.ensure_vault_directories()

    # Clean up stale prompt temp files from previous crashed runs
    cleanup_stale_prompt_files()

    orchestrator = Orchestrator()
    orchestrator.start()


if __name__ == "__main__":
    main()
