# monitor drop folder only
"""
filesystem_watcher.py - Enhanced file system watcher with event tracking

Monitors a specified directory for new files and creates action items in the vault.

Key Fixes (v2.1):
- RACE CONDITION FIX: recently_processed is set BEFORE the 0.5s sleep, not after.
  Previously both watchdog events passed the dedup check because Event 1 was still
  sleeping when Event 2 arrived. Now Event 2 is blocked immediately.
- Filename corruption fix is in task_template.py (_make_safe_stem strips extension).

Key Features:
- Atomic file writes (all-or-nothing, safe against crashes)
- MD5 hash-based deduplication (content-aware, not just filename)
- Moves processed files to Drop_History (preserves original filenames)
- Hash registry file for fast lookups
- Handles server restarts gracefully
- No database dependency - uses file-based tracking only
"""

import hashlib
import shutil
import time
import json
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from utils.logging_manager import LoggingManager
from utils.task_template import create_file_drop_task
from core.config import settings

logger = LoggingManager()

logger.logs_dir.mkdir(parents=True, exist_ok=True)
logger.timeline_dir.mkdir(parents=True, exist_ok=True)
logger.tasks_dir.mkdir(parents=True, exist_ok=True)
logger.errors_dir.mkdir(parents=True, exist_ok=True)


class DropFolderHandler(FileSystemEventHandler):
    """
    Handles file system events for the drop folder.

    When a new file is detected:
    1. Immediately marks file as "in-flight" to block duplicate events (RACE FIX)
    2. Waits 0.5s for file to be fully written
    3. Calculates MD5 hash for content-based deduplication
    4. Checks hash registry for already-processed content
    5. Reads file content into memory
    6. Creates task markdown file in Needs_Action/ (atomic write)
    7. Moves original file to Drop_History/
    8. Updates hash registry
    """

    def __init__(self):
        self.vault_path = settings.vault_path
        self.watch_folder = settings.drop_folder_path
        self.needs_action = settings.needs_action_path
        self.processing = settings.processing_path
        self.done = settings.done_path
        self.drop_history = settings.drop_history_path
        self.hash_registry_file = settings.hash_registry_path

        settings.ensure_vault_directories()

        # RACE CONDITION FIX:
        # Key: filename, Value: (file_hash_or_sentinel, timestamp)
        # Set to sentinel "PROCESSING" IMMEDIATELY on first event detection,
        # before any sleep. Second event checks this and bails out instantly.
        self.recently_processed: Dict[str, Tuple[str, float]] = {}

        self.hash_registry: Dict[str, Dict[str, Any]] = self._load_hash_registry()
        self.logger = LoggingManager()
        self.logs_per_task_enabled = settings.logs_per_task_enabled

        logger.write_to_timeline(
            "DropFolderHandler initialized", actor="filesystem_watcher", message_level="INFO"
        )
        logger.write_to_timeline(
            f"Vault: {self.vault_path}", actor="filesystem_watcher", message_level="INFO"
        )
        logger.write_to_timeline(
            f"Watch: {self.watch_folder}", actor="filesystem_watcher", message_level="INFO"
        )
        logger.write_to_timeline(
            f"History: {self.drop_history}", actor="filesystem_watcher", message_level="INFO"
        )

    def _load_hash_registry(self) -> Dict[str, Dict[str, Any]]:
        if self.hash_registry_file.exists():
            try:
                with open(self.hash_registry_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                logger.log_warning("Could not load hash registry", actor="filesystem_watcher")
                return {}
        return {}

    def _save_hash_registry(self):
        temp_path = self.hash_registry_file.with_suffix(".tmp")
        try:
            with open(temp_path, "w", encoding="utf-8") as f:
                json.dump(self.hash_registry, f, indent=2)
            if self.hash_registry_file.exists():
                self.hash_registry_file.unlink()
            temp_path.rename(self.hash_registry_file)
        except Exception as e:
            logger.log_error("Failed to save hash registry", error=e, actor="filesystem_watcher")
            if temp_path.exists():
                temp_path.unlink()

    def _add_to_hash_registry(self, filename: str, file_hash: str, timestamp: datetime):
        if filename not in self.hash_registry:
            self.hash_registry[filename] = {"hashes": [], "last_processed": None}
        if file_hash not in self.hash_registry[filename]["hashes"]:
            self.hash_registry[filename]["hashes"].append(file_hash)
        self.hash_registry[filename]["last_processed"] = timestamp.isoformat()
        self._save_hash_registry()

    def _is_hash_in_registry(self, filename: str, file_hash: str) -> bool:
        if filename not in self.hash_registry:
            return False
        return file_hash in self.hash_registry[filename].get("hashes", [])

    def on_created(self, event):
        """Called when a new file is created in the watched directory."""
        if event.is_directory:
            return

        src_path = Path(event.src_path)

        if src_path.name.startswith(".") or src_path.suffix in (".gitkeep", ".tmp"):
            return

        # ── RACE CONDITION FIX ─────────────────────────────────────────────
        # Set the sentinel IMMEDIATELY — before any sleep or hash calculation.
        # If a second watchdog event arrives for the same filename within the
        # dedup window (default 5s), it hits this check and returns instantly,
        # regardless of where the first event is in its processing.
        current_time = time.time()
        dedup_window_seconds = 5.0

        if src_path.name in self.recently_processed:
            _, last_time = self.recently_processed[src_path.name]
            if current_time - last_time < dedup_window_seconds:
                logger.write_to_timeline(
                    f"Duplicate event blocked (within {dedup_window_seconds}s window): {src_path.name}",
                    actor="filesystem_watcher",
                    message_level="DEBUG",
                )
                return

        # Claim this filename — sentinel value "PROCESSING" means in-flight
        self.recently_processed[src_path.name] = ("PROCESSING", current_time)
        # ──────────────────────────────────────────────────────────────────

        logger.write_to_timeline(
            f"📁 New file detected: {src_path.name}",
            actor="filesystem_watcher",
            message_level="INFO",
        )

        try:
            # Wait for file to be fully written to disk
            time.sleep(0.5)

            if not src_path.exists():
                logger.write_to_timeline(
                    f"File disappeared before processing: {src_path.name}",
                    actor="filesystem_watcher",
                    message_level="WARNING",
                )
                # Release claim so it can be retried
                self.recently_processed.pop(src_path.name, None)
                return

            # Calculate content hash
            try:
                file_hash = self._calculate_file_hash(src_path)
            except Exception as e:
                logger.log_error(
                    f"Could not hash {src_path.name}", error=e, actor="filesystem_watcher"
                )
                self.recently_processed.pop(src_path.name, None)
                return

            # Update sentinel with real hash now that we have it
            self.recently_processed[src_path.name] = (file_hash, current_time)

            # Check if this exact content was already processed
            if self._is_already_processed(src_path.name, file_hash):
                logger.write_to_timeline(
                    f"Skipping duplicate (already in history): {src_path.name}",
                    actor="filesystem_watcher",
                    message_level="INFO",
                )
                self._move_duplicate_to_history(src_path)
                return

            # Process the file
            self._process_new_file(src_path, file_hash)

        except Exception as e:
            logger.log_error(
                f"Error processing {src_path.name}", error=e, actor="filesystem_watcher"
            )
            # Release claim so orchestrator timeout can eventually retry
            self.recently_processed.pop(src_path.name, None)

    def _move_duplicate_to_history(self, src_path: Path):
        """Move a duplicate file to Drop_History without creating a task."""
        try:
            history_path = self.drop_history / src_path.name
            if history_path.exists():
                ts = datetime.now().strftime("%Y%m%d_%H%M%S")
                history_path = self.drop_history / f"{ts}_{src_path.name}"
            shutil.move(str(src_path), str(history_path))
            logger.write_to_timeline(
                f"Moved duplicate to history: {history_path.name}",
                actor="filesystem_watcher",
                message_level="INFO",
            )
        except Exception as e:
            logger.log_warning(
                f"Could not move duplicate {src_path.name} to history", actor="filesystem_watcher"
            )
            try:
                src_path.unlink()
            except Exception:
                pass

    def _calculate_file_hash(self, file_path: Path) -> str:
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _is_already_processed(self, filename: str, file_hash: str) -> bool:
        if self._is_hash_in_registry(filename, file_hash):
            return True
        for existing in self.drop_history.glob(f"{filename}*"):
            if existing.is_file():
                try:
                    if file_hash == self._calculate_file_hash(existing):
                        return True
                except Exception:
                    pass
        return False

    def _process_new_file(self, source: Path, file_hash: str):
        """
        Process a newly detected file.

        Reads content, creates task file in Needs_Action/, moves original
        to Drop_History/, updates registry.
        """
        timestamp = datetime.now()

        try:
            file_size = source.stat().st_size
        except Exception:
            file_size = 0

        priority = self._determine_priority(source)

        # Read content
        file_content = ""
        content_type = "text"
        try:
            file_content = source.read_text(encoding="utf-8")
        except Exception as e:
            content_type = "binary"
            logger.log_warning(
                f"Could not read text from {source.name}: {e}", actor="filesystem_watcher"
            )

        # Build task file using template
        task_id, task_content = create_file_drop_task(
            original_name=source.name,
            original_path=self.drop_history / source.name,
            content=file_content,
            content_type=content_type,
            file_extension=source.suffix,
            file_hash=file_hash,
            size_bytes=file_size,
            priority=priority,
            timestamp=timestamp,
        )

        # Write task file atomically
        metadata_path = self.needs_action / f"{task_id}.md"
        temp_path = metadata_path.with_suffix(".tmp")

        try:
            temp_path.write_text(task_content, encoding="utf-8")
            temp_path.rename(metadata_path)
            logger.write_to_timeline(
                f"📝 Created task: {metadata_path.name}",
                actor="filesystem_watcher",
                message_level="INFO",
            )
        except Exception as e:
            logger.log_error(
                f"Failed to write task file for {source.name}", error=e, actor="filesystem_watcher"
            )
            if temp_path.exists():
                temp_path.unlink()
            return

        # Move original to Drop_History/
        history_path = self.drop_history / source.name
        try:
            shutil.move(str(source), str(history_path))
            logger.write_to_timeline(
                f"📁 Moved to history: {source.name}",
                actor="filesystem_watcher",
                message_level="INFO",
            )
        except FileExistsError:
            ts = timestamp.strftime("%Y%m%d_%H%M%S")
            history_path = self.drop_history / f"{ts}_{source.name}"
            shutil.move(str(source), str(history_path))
            logger.write_to_timeline(
                f"📁 Moved to history (renamed): {history_path.name}",
                actor="filesystem_watcher",
                message_level="INFO",
            )
        except Exception as e:
            logger.log_error(
                f"Failed to move {source.name} to history", error=e, actor="filesystem_watcher"
            )

        # Update hash registry
        self._add_to_hash_registry(source.name, file_hash, timestamp)

        logger.write_to_timeline(
            f"✅ Successfully processed: {source.name}",
            actor="filesystem_watcher",
            message_level="INFO",
        )
        logger.write_to_timeline(
            f"Task ID: {task_id}", actor="filesystem_watcher", message_level="INFO"
        )
        logger.write_to_timeline(
            f"Hash: {file_hash}", actor="filesystem_watcher", message_level="INFO"
        )

        if self.logs_per_task_enabled:
            self.logger.write_to_task_log(
                task_type="file_drop",
                task_id=task_id,
                message=f"✅ Successfully processed - moved to history",
                actor="filesystem_watcher",
            )
            self.logger.update_task_status(
                task_type="file_drop",
                task_id=task_id,
                status="completed",
                final_result="processed successfully",
            )

    def _determine_priority(self, source: Path) -> str:
        name_lower = source.name.lower()
        if any(kw in name_lower for kw in ["urgent", "asap", "emergency", "deadline", "today"]):
            return "urgent"
        if any(kw in name_lower for kw in ["invoice", "payment", "billing", "receipt", "tax"]):
            return "high"
        if source.suffix.lower() in [".pdf", ".doc", ".docx", ".xls", ".xlsx"]:
            return "normal"
        return "low"


class FilesystemWatcher:
    """Watches a drop folder for new files."""

    def __init__(self):
        self.vault_path = settings.vault_path
        self.watch_folder = settings.drop_folder_path
        self.watch_folder.mkdir(parents=True, exist_ok=True)

        self.handler = DropFolderHandler()
        self.observer = Observer()

        logger.write_to_timeline(
            "FilesystemWatcher initialized", actor="filesystem_watcher", message_level="INFO"
        )
        logger.write_to_timeline(
            f"Watching: {self.watch_folder}", actor="filesystem_watcher", message_level="INFO"
        )

    def scan_existing_files(self):
        """Process any files that arrived while the server was down."""
        files = [
            f
            for f in self.watch_folder.iterdir()
            if f.is_file() and not f.name.startswith(".") and f.suffix not in (".gitkeep", ".tmp")
        ]

        if files:
            logger.write_to_timeline(
                f"Scanning {len(files)} existing file(s): {[f.name for f in files]}",
                actor="filesystem_watcher",
                message_level="INFO",
            )
        else:
            logger.write_to_timeline(
                "No existing files to scan", actor="filesystem_watcher", message_level="DEBUG"
            )

        for file in files:
            try:
                file_hash = self.handler._calculate_file_hash(file)
                self.handler._process_new_file(file, file_hash)
            except Exception as e:
                logger.log_error(
                    f"Error processing existing file {file.name}",
                    error=e,
                    actor="filesystem_watcher",
                )

    def start(self):
        self.scan_existing_files()
        self.observer.schedule(self.handler, str(self.watch_folder), recursive=False)
        self.observer.start()
        logger.write_to_timeline(
            "✅ Filesystem watcher started", actor="filesystem_watcher", message_level="INFO"
        )

    def stop(self):
        self.observer.stop()
        self.observer.join()
        logger.write_to_timeline(
            "Filesystem watcher stopped", actor="filesystem_watcher", message_level="INFO"
        )

    def run(self):
        self.start()
        logger.write_to_timeline(
            "Watching for files... (Ctrl+C to stop)",
            actor="filesystem_watcher",
            message_level="INFO",
        )
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.stop()

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.stop()
