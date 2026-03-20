"""
folder_watcher.py - Generic folder watcher for AI Employee

Orchestrator controls what folders to watch and provides callbacks.
Uses watchdog library for real-time file system event detection.

Usage:
    def on_change(event_type, file_path):
        print(f"{event_type}: {file_path}")
    
    watcher = FolderWatcher('Needs_Action/', on_change)
    watcher.start()
"""

# Use Windows-specific observer for better reliability
import sys
if sys.platform == 'win32':
    from watchdog.observers.read_directory_changes import WindowsApiObserver as Observer
else:
    from watchdog.observers import Observer

from watchdog.events import FileSystemEventHandler, FileCreatedEvent, FileDeletedEvent, FileMovedEvent
from pathlib import Path
from typing import Callable
import logging
import time

logger = logging.getLogger(__name__)


class FolderWatcher(FileSystemEventHandler):
    """
    Generic folder watcher - Orchestrator provides callback.
    
    Watches a single folder and calls the provided callback on file changes.
    Orchestrator manages multiple instances for different folders.
    """
    
    def __init__(self, folder_path: str, on_change_callback: Callable[[str, str], None]):
        """
        Initialize folder watcher.
        
        Args:
            folder_path: Path to folder to watch
            on_change_callback: Function to call on file changes
                              Signature: callback(event_type, file_path)
                              event_type: 'created', 'deleted', 'moved'
                              file_path: Full path to file
        """
        super().__init__()
        self.folder_path = Path(folder_path)
        self.on_change = on_change_callback
        self.observer = Observer()
        
        logger.info(f"FolderWatcher initialized for: {self.folder_path}")
    
    def start(self):
        """Start watching the folder."""
        if not self.folder_path.exists():
            logger.warning(f"Folder does not exist: {self.folder_path}")
            self.folder_path.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created folder: {self.folder_path}")
        
        logger.info(f"Scheduling observer for: {self.folder_path}")
        self.observer.schedule(self, str(self.folder_path), recursive=False)
        logger.info(f"Observer scheduled, starting...")
        self.observer.start()
        logger.info(f"✅ FolderWatcher observer started: {self.folder_path}")
        logger.info(f"Observer is alive: {self.observer.is_alive()}")
        
        # Give observer time to initialize
        time.sleep(0.1)
        logger.info(f"Observer ready, watching: {self.folder_path}")
    
    def stop(self):
        """Stop watching the folder."""
        self.observer.stop()
        self.observer.join()
        logger.info(f"FolderWatcher stopped: {self.folder_path}")
    
    def on_created(self, event):
        """Called when a file is created."""
        logger.info(f"📁 FolderWatcher.on_created() called for: {event.src_path}")
        
        if event.is_directory:
            logger.debug(f"Ignoring directory creation: {event.src_path}")
            return
        
        logger.debug(f"File created: {event.src_path}")
        logger.info(f"FolderWatcher detected CREATED: {event.src_path}")
        logger.info(f"Calling callback: on_change('created', '{event.src_path}')")
        self.on_change('created', event.src_path)
        logger.info(f"Callback completed for: {event.src_path}")
    
    def on_moved(self, event):
        """Called when a file is moved (includes rename operations)."""
        logger.info(f"📁 FolderWatcher.on_moved() called: {event.src_path} → {event.dest_path}")
        
        if event.is_directory:
            logger.debug(f"Ignoring directory move: {event.src_path}")
            return
        
        # Treat moved/renamed files as created (for atomic write pattern)
        logger.debug(f"File moved/renamed: {event.src_path} → {event.dest_path}")
        logger.info(f"FolderWatcher detected MOVED (treating as CREATED): {event.dest_path}")
        logger.info(f"Calling callback: on_change('created', '{event.dest_path}')")
        self.on_change('created', event.dest_path)
        logger.info(f"Callback completed for: {event.dest_path}")
    
    def on_deleted(self, event):
        """Called when a file is deleted."""
        if event.is_directory:
            return

        logger.debug(f"File deleted: {event.src_path}")
        logger.info(f"FolderWatcher detected DELETED: {event.src_path}")
        self.on_change('deleted', event.src_path)

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
