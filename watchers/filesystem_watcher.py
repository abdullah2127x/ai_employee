"""
filesystem_watcher.py - Enhanced file system watcher with event tracking

Monitors a specified directory for new files and creates action items in the vault.
Tracks all events in SQLite database for audit and analytics.
"""
import shutil
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from database import TaskDatabase

logger = logging.getLogger(__name__)


class DropFolderHandler(FileSystemEventHandler):
    """
    Handles file system events for the drop folder.
    
    When a new file is detected:
    1. Creates metadata markdown file in Needs_Action
    2. Copies the original file to vault
    3. Records event in SQLite database
    4. Triggers orchestrator notification
    """

    def __init__(
        self, 
        vault_path: Path,
        watch_folder: Path,
        db: TaskDatabase
    ):
        """
        Initialize the handler.

        Args:
            vault_path: Path to Obsidian vault
            watch_folder: Path to folder to watch for new files
            db: TaskDatabase instance for tracking
        """
        self.vault_path = vault_path
        self.watch_folder = watch_folder
        self.db = db
        
        # Ensure directories exist
        self.needs_action = vault_path / 'Needs_Action'
        self.processing = vault_path / 'Processing'
        self.done = vault_path / 'Done'
        
        for directory in [self.needs_action, self.processing, self.done]:
            directory.mkdir(parents=True, exist_ok=True)

        logger.info(f"DropFolderHandler initialized")
        logger.info(f"  Vault: {vault_path}")
        logger.info(f"  Watch: {watch_folder}")

    def on_created(self, event):
        """Called when a new file is created in the watched directory."""
        if event.is_directory:
            logger.debug(f"Ignoring directory creation: {event.src_path}")
            return

        # Ignore .gitkeep and hidden files
        src_path = Path(event.src_path)
        if src_path.name.startswith('.') or src_path.suffix == '.gitkeep':
            logger.debug(f"Ignoring system file: {src_path.name}")
            return

        logger.info(f"📁 New file detected: {src_path.name}")
        
        try:
            # Wait briefly for file to be fully written
            import time
            time.sleep(0.5)
            
            # Verify file still exists
            if not src_path.exists():
                logger.warning(f"File disappeared before processing: {src_path.name}")
                return

            # Process the file
            self._process_new_file(src_path)
            
        except Exception as e:
            logger.error(f"Error processing file {src_path.name}: {e}", exc_info=True)

    def _process_new_file(self, source: Path):
        """
        Process a newly detected file.

        Args:
            source: Path to the new file
        """
        timestamp = datetime.now()
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        
        # Generate unique task ID
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

        # Copy file to vault (if not already there)
        vault_file_path = None
        if not source.is_relative_to(self.vault_path):
            vault_file_path = self.needs_action / f"FILE_{timestamp_str}_{source.name}"
            try:
                shutil.copy2(source, vault_file_path)
                logger.info(f"Copied file to vault: {vault_file_path.name}")
            except Exception as e:
                logger.error(f"Error copying file: {e}")
                vault_file_path = None

        # Create metadata markdown file
        metadata_path = self._create_metadata_file(
            source=source,
            vault_file=vault_file_path,
            timestamp=timestamp,
            file_size=file_size,
            priority=priority
        )

        # Create task in database
        self.db.create_task(
            task_id=task_id,
            task_type="file_drop",
            source_file=str(metadata_path),
            priority=priority,
            title=f"Process file: {source.name}",
            description=f"New file dropped: {source.name} ({file_size} bytes)",
            metadata={
                "original_name": source.name,
                "original_path": str(source),
                "vault_file": str(vault_file_path) if vault_file_path else None,
                "file_size": file_size,
                "file_modified": file_modified.isoformat(),
                "metadata_file": str(metadata_path)
            }
        )

        logger.info(f"✅ Created task: {task_id}")
        logger.info(f"   Metadata: {metadata_path}")
        if vault_file_path:
            logger.info(f"   Vault file: {vault_file_path}")

    def _create_metadata_file(
        self,
        source: Path,
        vault_file: Optional[Path],
        timestamp: datetime,
        file_size: int,
        priority: str
    ) -> Path:
        """
        Create a markdown metadata file for the dropped file.
        
        Includes the actual file content so Claude can process it.

        Args:
            source: Original file path
            vault_file: Path in vault (if copied)
            timestamp: Detection timestamp
            file_size: File size in bytes
            priority: Task priority

        Returns:
            Path to created metadata file
        """
        timestamp_str = timestamp.strftime('%Y%m%d_%H%M%S')
        metadata_path = self.needs_action / f"FILE_{timestamp_str}_{source.name}.md"
        
        # Try to read file content
        file_content = ""
        try:
            if vault_file and vault_file.exists():
                file_content = vault_file.read_text(encoding='utf-8')
            elif source.exists():
                file_content = source.read_text(encoding='utf-8')
        except Exception as e:
            file_content = f"[Could not read file: {e}]"

        content = f"""---
type: file_drop
task_id: file_{timestamp_str}_{source.name}
original_name: {source.name}
original_path: {source}
vault_file: {vault_file.name if vault_file else 'N/A'}
size: {file_size}
detected: {timestamp.isoformat()}
priority: {priority}
status: pending
---

# File Drop: {source.name}

**Detected:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Priority:** {priority.title()}
**Size:** {self._format_size(file_size)}

---

## File Information

| Property | Value |
|----------|-------|
| Original Name | `{source.name}` |
| Original Path | `{source}` |
| Vault Location | `{vault_file.name if vault_file else 'Not copied'}` |
| Size | {self._format_size(file_size)} |
| Detected | {timestamp.strftime('%Y-%m-%d %H:%M:%S')} |

---

## File Content

```
{file_content}
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

        metadata_path.write_text(content, encoding='utf-8')
        logger.debug(f"Created metadata file: {metadata_path}")

        return metadata_path

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
        urgent_keywords = ['urgent', 'asap', 'emergency', 'deadline', 'today']
        if any(kw in name_lower for kw in urgent_keywords):
            return 'urgent'

        # High: Financial documents
        high_keywords = ['invoice', 'payment', 'billing', 'receipt', 'tax']
        if any(kw in name_lower for kw in high_keywords):
            return 'high'

        # Normal: Common business files
        normal_extensions = ['.pdf', '.doc', '.docx', '.xls', '.xlsx']
        if source.suffix.lower() in normal_extensions:
            return 'normal'

        # Low: Everything else
        return 'low'

    def _format_size(self, size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


class FilesystemWatcher:
    """
    Watches a drop folder for new files.
    
    Usage:
        watcher = FilesystemWatcher(vault_path, watch_folder, db)
        watcher.start()
    """

    def __init__(
        self, 
        vault_path: str, 
        watch_folder: str,
        db: TaskDatabase
    ):
        """
        Initialize the filesystem watcher.

        Args:
            vault_path: Path to Obsidian vault
            watch_folder: Path to folder to watch for new files
            db: TaskDatabase instance for tracking
        """
        self.vault_path = Path(vault_path)
        self.watch_folder = Path(watch_folder)
        self.db = db
        
        # Ensure watch folder exists
        self.watch_folder.mkdir(parents=True, exist_ok=True)

        # Create handler and observer
        self.handler = DropFolderHandler(self.vault_path, self.watch_folder, self.db)
        self.observer = Observer()
        
        logger.info(f"FilesystemWatcher initialized")
        logger.info(f"  Watching: {self.watch_folder}")

    def start(self):
        """Start watching the folder."""
        self.observer.schedule(
            self.handler, 
            str(self.watch_folder), 
            recursive=False
        )
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
        import time
        
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
