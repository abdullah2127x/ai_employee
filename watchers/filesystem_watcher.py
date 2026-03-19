"""
filesystem_watcher.py - Enhanced file system watcher with event tracking

Monitors a specified directory for new files and creates action items in the vault.
Tracks all events via hash registry and logging for audit.

Key Features:
- Atomic file writes (all-or-nothing, safe against crashes)
- MD5 hash-based deduplication (content-aware, not just filename)
- Moves processed files to Drop_History (preserves original filenames)
- Hash registry file for fast lookups (no need to hash all history files)
- Handles server restarts gracefully
- No database dependency - uses file-based tracking only
- Integrated with two-tier logging system (timeline + task logs)
"""

import hashlib
import shutil
import logging
import time
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from utils.logging_manager import LoggingManager
from core.config import settings

logger = logging.getLogger(__name__)


class DropFolderHandler(FileSystemEventHandler):
    """
    Handles file system events for the drop folder.

    When a new file is detected:
    1. Calculates MD5 hash for content-based deduplication
    2. Checks hash registry file for duplicates
    3. Reads entire file content into memory (safe against crashes)
    4. Creates metadata markdown file in Needs_Action (atomic write)
    5. Moves original file to Drop_History (preserves original filename)
    6. Updates hash registry file
    7. Logs all operations for audit trail
    
    Note: All paths are obtained from centralized settings in core.config
    """

    def __init__(self):
        """
        Initialize the handler using centralized paths from settings.
        """
        # Use centralized paths from settings
        self.vault_path = settings.vault_path
        self.watch_folder = settings.drop_folder_path
        self.needs_action = settings.needs_action_path
        self.processing = settings.processing_path
        self.done = settings.done_path
        self.drop_history = settings.drop_history_path
        self.hash_registry_file = settings.hash_registry_path

        # Ensure directories exist
        settings.ensure_vault_directories()

        # Track recently processed files: filename -> (hash, timestamp)
        # Prevents duplicate events within 2-second window
        self.recently_processed: Dict[str, Tuple[str, float]] = {}

        # Load hash registry into memory
        self.hash_registry: Dict[str, Dict[str, Any]] = self._load_hash_registry()

        # Initialize logging manager (uses settings for paths, log level as parameter)
        self.logger = LoggingManager(log_level="WARNING")
        self.logs_per_task_enabled = settings.logs_per_task_enabled

        logger.info(f"DropFolderHandler initialized")
        logger.info(f"  Vault: {self.vault_path}")
        logger.info(f"  Watch: {self.watch_folder}")
        logger.info(f"  History: {self.drop_history}")
        logger.info(f"  Hash Registry: {self.hash_registry_file}")
    
    def _load_hash_registry(self) -> Dict[str, Dict[str, Any]]:
        """
        Load hash registry from JSON file.
        
        Returns:
            Dictionary: {filename: {"hashes": [hash1, hash2, ...], "last_processed": timestamp}}
        """
        if self.hash_registry_file.exists():
            try:
                with open(self.hash_registry_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Could not load hash registry: {e}")
                return {}
        return {}
    
    def _save_hash_registry(self):
        """Save hash registry to JSON file (atomic write)."""
        temp_path = self.hash_registry_file.with_suffix('.tmp')
        try:
            with open(temp_path, 'w', encoding='utf-8') as f:
                json.dump(self.hash_registry, f, indent=2)
            
            # Remove existing file first (Windows compatibility)
            if self.hash_registry_file.exists():
                self.hash_registry_file.unlink()
            
            temp_path.rename(self.hash_registry_file)
            logger.debug("Hash registry saved")
        except Exception as e:
            logger.error(f"Failed to save hash registry: {e}")
            if temp_path.exists():
                temp_path.unlink()
    
    def _add_to_hash_registry(self, filename: str, file_hash: str, timestamp: datetime):
        """
        Add a file hash to the registry.
        
        Args:
            filename: Original filename
            file_hash: MD5 hash of file content
            timestamp: When it was processed
        """
        if filename not in self.hash_registry:
            self.hash_registry[filename] = {"hashes": [], "last_processed": None}
        
        # Add hash if not already present
        if file_hash not in self.hash_registry[filename]["hashes"]:
            self.hash_registry[filename]["hashes"].append(file_hash)
        
        self.hash_registry[filename]["last_processed"] = timestamp.isoformat()
        self._save_hash_registry()
    
    def _is_hash_in_registry(self, filename: str, file_hash: str) -> bool:
        """
        Check if a hash exists for a given filename in the registry.
        
        Args:
            filename: Name of the file
            file_hash: MD5 hash to check
            
        Returns:
            True if hash exists, False otherwise
        """
        if filename not in self.hash_registry:
            return False
        
        return file_hash in self.hash_registry[filename].get("hashes", [])

    def on_created(self, event):
        """Called when a new file is created in the watched directory."""
        if event.is_directory:
            logger.debug(f"Ignoring directory creation: {event.src_path}")
            return

        # Ignore .gitkeep and hidden files
        src_path = Path(event.src_path)
        if src_path.name.startswith(".") or src_path.suffix == ".gitkeep":
            logger.debug(f"Ignoring system file: {src_path.name}")
            return

        logger.info(f"📁 New file detected: {src_path.name}")

        # Log to task log if enabled
        if self.logs_per_task_enabled:
            self.logger.write_to_task_log(
                task_type="file_drop",
                task_id=f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{src_path.name}",
                message=f"📁 New file detected: {src_path.name}",
                actor="filesystem_watcher",
                trigger_file=str(src_path)
            )

        try:
            # Wait briefly for file to be fully written
            time.sleep(0.5)

            # Verify file still exists
            if not src_path.exists():
                logger.warning(f"File disappeared before processing: {src_path.name}")
                return

            # Calculate file hash (for content-based deduplication)
            try:
                file_hash = self._calculate_file_hash(src_path)
            except Exception as e:
                logger.error(f"Could not calculate hash for {src_path.name}: {e}")
                return

            # DEDUPLICATION 1: Check 2-second window (same filename + same hash)
            current_time = time.time()
            if src_path.name in self.recently_processed:
                last_hash, last_time = self.recently_processed[src_path.name]
                if current_time - last_time < 2.0:
                    if file_hash == last_hash:
                        logger.debug(f"Skipping duplicate event (2-sec window): {src_path.name}")
                        return
                    else:
                        logger.info(f"Same filename, different content: {src_path.name} (processing new version)")

            # DEDUPLICATION 2: Check if same content already processed
            if self._is_already_processed(src_path.name, file_hash):
                logger.info(f"⏭️  Skipping duplicate (already in history): {src_path.name}")
                
                # Log duplicate detection
                if self.logs_per_task_enabled:
                    self.logger.write_to_task_log(
                        task_type="file_drop",
                        task_id=f"file_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{src_path.name}",
                        message=f"⏭️  Skipped duplicate (already in history)",
                        actor="filesystem_watcher",
                        trigger_file=str(src_path),
                        status="skipped"
                    )
                
                # Move to Drop_History (don't delete - preserve for user reference)
                timestamp = datetime.now()
                timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
                
                try:
                    # Check if file with same name exists in Drop_History
                    history_path = self.drop_history / src_path.name
                    if history_path.exists():
                        # Add timestamp to avoid collision
                        history_name = f"{timestamp_str}_{src_path.name}"
                        history_path = self.drop_history / history_name
                    
                    shutil.move(str(src_path), str(history_path))
                    logger.info(f"📁 Moved duplicate to history: {history_path.name}")
                except Exception as e:
                    logger.warning(f"Could not move duplicate {src_path.name} to history: {e}")
                    # Fallback: just delete if move fails
                    try:
                        src_path.unlink()
                        logger.info(f"🗑️  Removed duplicate from Drop: {src_path.name}")
                    except:
                        pass
                
                return

            # Mark as recently processed
            self.recently_processed[src_path.name] = (file_hash, current_time)

            # Process the file
            self._process_new_file(src_path, file_hash)

        except Exception as e:
            logger.error(f"Error processing file {src_path.name}: {e}", exc_info=True)
            # File stays in Drop/ for retry on next scan

    def _calculate_file_hash(self, file_path: Path) -> str:
        """
        Calculate MD5 hash of file content.

        Args:
            file_path: Path to the file

        Returns:
            MD5 hash as hex string
        """
        hasher = hashlib.md5()
        with open(file_path, 'rb') as f:
            # Read in chunks for memory efficiency (handles large files)
            for chunk in iter(lambda: f.read(8192), b''):
                hasher.update(chunk)
        return hasher.hexdigest()

    def _is_already_processed(self, filename: str, file_hash: str) -> bool:
        """
        Check if this exact file (by content hash) was already processed.

        Args:
            filename: Name of the file
            file_hash: MD5 hash of file content

        Returns:
            True if already processed, False otherwise
        """
        # Method 1: Check hash registry file (fastest)
        if self._is_hash_in_registry(filename, file_hash):
            return True

        # Method 2: Fallback - scan Drop_History (slow, for backward compatibility)
        # Only needed if registry file was corrupted or missing
        for existing in self.drop_history.glob(f"{filename}*"):
            if existing.is_file():
                try:
                    existing_hash = self._calculate_file_hash(existing)
                    if file_hash == existing_hash:
                        return True
                except Exception as e:
                    logger.debug(f"Could not hash {existing.name}: {e}")

        return False

    def _process_new_file(self, source: Path, file_hash: str):
        """
        Process a newly detected file.

        All operations are done in memory first, then written atomically.
        If server crashes mid-process, file stays in Drop/ for retry.

        Args:
            source: Path to the new file
            file_hash: MD5 hash of file content
        """
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

        # Generate unique task ID (includes hash for better uniqueness)
        task_id = f"file_{timestamp_str}_{source.name}"

        # Get file metadata
        try:
            file_size = source.stat().st_size
            file_modified = datetime.fromtimestamp(source.stat().st_mtime)
        except Exception as e:
            logger.warning(f"Could not get file metadata: {e}")
            file_size = 0
            file_modified = timestamp

        # Determine priority based on file type
        priority = self._determine_priority(source)

        # Read file content into memory FIRST (before any writes)
        # This ensures we have everything ready for atomic write
        file_content = ""
        content_read_error = None
        try:
            file_content = source.read_text(encoding="utf-8")
        except Exception as e:
            content_read_error = f"[Could not read file: {e}]"
            logger.warning(f"Could not read content of {source.name}: {e}")

        # Prepare FULL metadata content in memory
        metadata_content = self._prepare_metadata_content(
            source=source,
            content=file_content if not content_read_error else content_read_error,
            size=file_size,
            file_hash=file_hash,
            priority=priority,
            timestamp=timestamp,
        )

        # Create metadata markdown file (ATOMIC WRITE)
        # Write to temp file first, then rename (ensures all-or-nothing)
        metadata_path = self.needs_action / f"FILE_{timestamp_str}_{source.name}.md"
        temp_path = metadata_path.with_suffix('.tmp')

        try:
            temp_path.write_text(metadata_content, encoding="utf-8")
            temp_path.rename(metadata_path)  # Atomic rename
            logger.info(f"📝 Created metadata: {metadata_path.name}")
            
            # Log metadata creation
            if self.logs_per_task_enabled:
                self.logger.write_to_task_log(
                    task_type="file_drop",
                    task_id=task_id,
                    message=f"📝 Created metadata: {metadata_path.name}",
                    actor="filesystem_watcher"
                )
        except Exception as e:
            logger.error(f"Failed to write metadata for {source.name}: {e}")
            # Clean up temp file if it exists
            if temp_path.exists():
                temp_path.unlink()
            # Don't move file to history, will retry on next scan
            return

        # Move original file to Drop_History (PRESERVE ORIGINAL FILENAME)
        history_path = self.drop_history / source.name

        try:
            shutil.move(str(source), str(history_path))
            logger.info(f"📁 Moved to history: {source.name}")
            
            # Log file move
            if self.logs_per_task_enabled:
                self.logger.write_to_task_log(
                    task_type="file_drop",
                    task_id=task_id,
                    message=f"📁 Moved to history: {source.name}",
                    actor="filesystem_watcher"
                )
        except FileExistsError:
            # File with same name already exists in history
            # Add timestamp to avoid collision
            timestamp_for_name = timestamp.strftime("%Y%m%d_%H%M%S")
            history_name = f"{timestamp_for_name}_{source.name}"
            history_path = self.drop_history / history_name
            shutil.move(str(source), str(history_path))
            logger.info(f"📁 Moved to history (renamed): {history_name}")
        except Exception as e:
            logger.error(f"Failed to move {source.name} to history: {e}")
            # File stays in Drop/, will be detected as duplicate on next scan

        # Add hash to registry (AFTER successful move)
        self._add_to_hash_registry(source.name, file_hash, timestamp)

        logger.info(f"✅ Successfully processed: {source.name}")
        logger.info(f"   Task ID: {task_id}")
        logger.info(f"   Hash: {file_hash}")
        logger.info(f"   Metadata: {metadata_path.name}")
        logger.info(f"   History: {history_path.name}")
        
        # Log task completion
        if self.logs_per_task_enabled:
            self.logger.write_to_task_log(
                task_type="file_drop",
                task_id=task_id,
                message=f"✅ Successfully processed - moved to history",
                actor="filesystem_watcher"
            )
            # Update task status to completed
            self.logger.update_task_status(
                task_type="file_drop",
                task_id=task_id,
                status="completed",
                final_result="processed successfully"
            )

    def _prepare_metadata_content(
        self,
        source: Path,
        content: str,
        size: int,
        file_hash: str,
        priority: str,
        timestamp: datetime,
    ) -> str:
        """
        Prepare full metadata markdown content (in memory).

        Args:
            source: Original file path
            content: File content (already read into memory)
            size: File size in bytes
            file_hash: MD5 hash of file content
            priority: Task priority
            timestamp: Detection timestamp

        Returns:
            Complete markdown content as string
        """
        timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")

        return f"""---
type: file_drop
task_id: file_{timestamp_str}_{source.name}
original_name: {source.name}
original_path: {source}
file_hash: {file_hash}
size: {size}
detected: {timestamp.isoformat()}
priority: {priority}
status: pending
---

# File Drop: {source.name}

**Detected:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Priority:** {priority.title()}
**Size:** {self._format_size(size)}
**Content Hash:** `{file_hash}`

---

## File Information

| Property | Value |
|----------|-------|
| Original Name | `{source.name}` |
| Original Path | `{source}` |
| Size | {self._format_size(size)} |
| Detected | {timestamp.strftime('%Y-%m-%d %H:%M:%S')} |
| Content Hash | `{file_hash}` |

---

## File Content

```
{content}
```

---

## Suggested Actions

- [ ] Review file contents
- [ ] Categorize and organize
- [ ] Process if needed (extract data, generate response, etc.)
- [ ] Archive after processing

---

## Processing Notes

(Add notes here during processing)

---

*Generated by AI Employee Filesystem Watcher*
*Task ID: `file_{timestamp_str}_{source.name}`*
"""

    def _determine_priority(self, source: Path) -> str:
        """
        Determine task priority based on file characteristics.

        Args:
            source: Path to the file

        Returns:
            Priority string: 'urgent', 'high', 'normal', or 'low'
        """
        name_lower = source.name.lower()

        # Urgent: Time-sensitive files
        urgent_keywords = ["urgent", "asap", "emergency", "deadline", "today"]
        if any(kw in name_lower for kw in urgent_keywords):
            return "urgent"

        # High: Financial documents
        high_keywords = ["invoice", "payment", "billing", "receipt", "tax"]
        if any(kw in name_lower for kw in high_keywords):
            return "high"

        # Normal: Common business files
        normal_extensions = [".pdf", ".doc", ".docx", ".xls", ".xlsx"]
        if source.suffix.lower() in normal_extensions:
            return "normal"

        # Low: Everything else
        return "low"

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class FilesystemWatcher:
    """
    Watches a drop folder for new files.

    Usage:
        watcher = FilesystemWatcher()
        watcher.start()
    
    Note: All paths are obtained from centralized settings in core.config
    """

    def __init__(self):
        """
        Initialize the filesystem watcher using centralized paths from settings.
        """
        # Use centralized paths from settings
        self.vault_path = settings.vault_path
        self.watch_folder = settings.drop_folder_path

        # Ensure watch folder exists
        self.watch_folder.mkdir(parents=True, exist_ok=True)

        # Create handler and observer
        self.handler = DropFolderHandler()
        self.observer = Observer()

        logger.info(f"FilesystemWatcher initialized")
        logger.info(f"  Watching: {self.watch_folder}")

    def scan_existing_files(self):
        """
        Scan and process any existing files in the watch folder.
        Called on startup to handle files that arrived while server was down.
        
        Skips:
        - .gitkeep files
        - Hidden files (starting with .)
        - Directories
        """
        files = list(self.watch_folder.iterdir())
        
        # Filter out system files and directories
        files_to_process = []
        for file in files:
            if file.is_file() and not file.name.startswith(".") and file.suffix != ".gitkeep":
                files_to_process.append(file)
        
        if files_to_process:
            logger.info(f"🔍 Scanning {len(files_to_process)} existing file(s) in watch folder")
        else:
            logger.debug("No existing files to scan")

        for file in files_to_process:
            try:
                # Calculate hash first (same as on_created does)
                file_hash = self.handler._calculate_file_hash(file)
                self.handler._process_new_file(file, file_hash)
            except Exception as e:
                logger.error(f"Error processing existing file {file.name}: {e}")

    def start(self):
        """Start watching the folder."""
        self.scan_existing_files()
        self.observer.schedule(self.handler, str(self.watch_folder), recursive=False)
        self.observer.start()
        logger.info("✅ Filesystem watcher started")
        logger.info(f"   Monitoring: {self.watch_folder}")

    def stop(self):
        """Stop watching the folder."""
        self.observer.stop()
        self.observer.join()
        logger.info("⏹️  Filesystem watcher stopped")

    def run(self):
        """Run the watcher (blocks until interrupted)."""
        self.start()
        logger.info("👁️  Watching for files... (Press Ctrl+C to stop)")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("Received interrupt signal")
            self.stop()

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
