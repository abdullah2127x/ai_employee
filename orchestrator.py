#!/usr/bin/env python3
"""
orchestrator.py - AI Employee Orchestrator (Version 2.0)

Manages workflow with Folder Watchers, timeout tracking, and Claude Runner integration.
Also manages Filesystem Watcher (Drop/ folder monitoring) based on configuration.
No database dependency - pure file-based tracking.

Architecture:
- Filesystem Watcher (watchers/filesystem_watcher.py) - Watches Drop/, creates tasks
  - Managed by: Orchestrator (starts/stops based on ENABLE_FILESYSTEM_WATCHER flag)
- Folder Watchers (watchers/folder_watcher.py) - Orchestrator manages all workflow folders
- Timeout Tracking - file_move_times dictionary tracks files in Processing/
- Claude Runner (claude_runner.py) - Standalone Claude Code executor

Usage:
    python orchestrator.py
    
Configuration:
    Set ENABLE_FILESYSTEM_WATCHER=true in .env to enable Drop/ folder monitoring
"""

import os
import sys
import time
import subprocess
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict

# Add project root to path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings
from utils.logging_manager import LoggingManager
from watchers.folder_watcher import FolderWatcher
from watchers.filesystem_watcher import FilesystemWatcher

logger = LoggingManager()


class Orchestrator:
    """
    AI Employee Orchestrator - Manages workflow with Folder Watchers.
    
    Responsibilities:
    - Manages Filesystem Watcher (if ENABLE_FILESYSTEM_WATCHER=true)
    - Manages Folder Watchers for all workflow folders
    - Tracks files in Processing/ with timeout detection
    - Calls Claude Runner for task processing
    - Executes approved actions
    - Logs all activities
    """
    
    def __init__(self):
        """Initialize orchestrator with watchers and timeout tracking."""
        self.file_move_times: Dict[str, datetime] = {}  # file_path → move_time
        self.timeout_seconds = 30  # Reduced timeout for testing (30 seconds)
        # self.timeout_seconds = 300  # 5 minutes
        
        # Keep references to observer threads to prevent them from dying
        self.observer_threads = []
        
        # Filesystem Watcher (managed by Orchestrator)
        self.filesystem_watcher = None
        if settings.enable_filesystem_watcher:
            logger.write_to_timeline(
                "Filesystem Watcher enabled (watches Drop/ folder)",
                actor="orchestrator",
                message_level="INFO"
            )
            # Create Filesystem Watcher (it has its own thread)
            self.filesystem_watcher = FilesystemWatcher()
        else:
            logger.write_to_timeline(
                "Filesystem Watcher disabled (Drop/ folder not monitored)",
                actor="orchestrator",
                message_level="WARNING"
            )
        
        # Folder watchers for each workflow folder
        self.watchers = {
            'needs_action': FolderWatcher(
                str(settings.needs_action_path),
                self.on_needs_action_change
            ),
            'processing': FolderWatcher(
                str(settings.processing_path),
                self.on_processing_change
            ),
            'approved': FolderWatcher(
                str(settings.approved_path),
                self.on_approved_change
            ),
            'rejected': FolderWatcher(
                str(settings.rejected_path),
                self.on_rejected_change
            ),
            'needs_revision': FolderWatcher(
                str(settings.needs_revision_path),
                self.on_revision_change
            ),
        }
        
        logger.write_to_timeline(
            "Orchestrator initialized",
            actor="orchestrator",
            message_level="INFO"
        )
    
    def start(self):
        """Start all watchers (Filesystem + Folder) and timeout check loop."""
        logger.write_to_timeline(
            "Orchestrator starting all watchers",
            actor="orchestrator",
            message_level="INFO"
        )
        
        # Start Filesystem Watcher (if enabled)
        if self.filesystem_watcher:
            # Start in separate thread (non-blocking)
            watcher_thread = threading.Thread(target=self.filesystem_watcher.run, daemon=True)
            watcher_thread.start()
            logger.write_to_timeline(
                "Filesystem Watcher started (Drop/ folder monitored)",
                actor="orchestrator",
                message_level="INFO"
            )
        
        # Start all folder watchers (they run in background)
        for name, watcher in self.watchers.items():
            watcher.start()
            # Keep reference to observer thread to prevent it from dying
            self.observer_threads.append(watcher.observer)
            logger.write_to_timeline(
                f"Folder Watcher started: {name} (watching: {watcher.folder_path})",
                actor="orchestrator",
                message_level="INFO"
            )
        
        logger.write_to_timeline(
            "All watchers started, beginning timeout check loop",
            actor="orchestrator",
            message_level="INFO"
        )
        
        # Verify all observers are running
        logger.write_to_timeline(
            f"Active threads: {threading.active_count()}",
            actor="orchestrator",
            message_level="INFO"
        )
        for name, watcher in self.watchers.items():
            is_alive = watcher.observer.is_alive() if watcher.observer else False
            logger.write_to_timeline(
                f"Folder Watcher '{name}' observer alive: {is_alive}",
                actor="orchestrator",
                message_level="INFO" if is_alive else "WARNING"
            )
        
        # Start timeout check loop (every 60 seconds)
        try:
            while True:
                time.sleep(60)
                self.check_timeouts()
        except KeyboardInterrupt:
            logger.write_to_timeline(
                "Orchestrator received interrupt signal",
                actor="orchestrator",
                message_level="INFO"
            )
            self.stop()
    
    def stop(self):
        """Stop all watchers (Filesystem + Folder)."""
        logger.write_to_timeline(
            "Orchestrator stopping all watchers",
            actor="orchestrator",
            message_level="INFO"
        )
        
        # Stop Filesystem Watcher (if running)
        if self.filesystem_watcher:
            self.filesystem_watcher.stop()
        
        # Stop all folder watchers
        for name, watcher in self.watchers.items():
            watcher.stop()
    
    def on_needs_action_change(self, event_type: str, file_path: str):
        """
        Handle changes in Needs_Action/ folder.
        
        Args:
            event_type: 'created', 'deleted', 'moved'
            file_path: Full path to file
        """
        if event_type != 'created':
            return
        
        file_path = Path(file_path)
        
        # Only process .md files
        if file_path.suffix != '.md' or file_path.name.startswith('.'):
            return
        
        logger.write_to_timeline(
            f"New task detected: {file_path.name}",
            actor="orchestrator",
            message_level="INFO"
        )
        
        # Move to Processing/
        self.move_to_processing(file_path)
        
        # Update file_path to point to Processing/ location
        file_path = settings.processing_path / file_path.name

        # Record timestamp for timeout tracking
        self.file_move_times[str(file_path)] = datetime.now()

        # Call Claude Runner (fire and forget)
        self.call_claude_runner(file_path)
    
    def on_processing_change(self, event_type: str, file_path: str):
        """
        Handle changes in Processing/ folder.
        
        Args:
            event_type: 'created', 'deleted', 'moved'
            file_path: Full path to file
        """
        if event_type not in ['deleted', 'moved']:
            return
        
        # File left Processing/ → Claude finished!
        if file_path in self.file_move_times:
            del self.file_move_times[file_path]
            logger.write_to_timeline(
                f"Task completed: {Path(file_path).name}",
                actor="orchestrator",
                message_level="INFO"
            )
    
    def on_approved_change(self, event_type: str, file_path: str):
        """
        Handle changes in Approved/ folder.
        
        Args:
            event_type: 'created', 'deleted', 'moved'
            file_path: Full path to file
        """
        if event_type != 'created':
            return
        
        file_path = Path(file_path)
        
        logger.write_to_timeline(
            f"Approved task detected: {file_path.name}",
            actor="orchestrator",
            message_level="INFO"
        )
        
        # Execute approved action
        self.execute_approved_action(file_path)
    
    def on_rejected_change(self, event_type: str, file_path: str):
        """
        Handle changes in Rejected/ folder.
        
        Args:
            event_type: 'created', 'deleted', 'moved'
            file_path: Full path to file
        """
        if event_type != 'created':
            return
        
        file_path = Path(file_path)
        
        logger.write_to_timeline(
            f"Task rejected: {file_path.name}",
            actor="orchestrator",
            message_level="WARNING"
        )
        
        # Log rejection (could update learning log here)
        # For now, just leave in Rejected/ as archive
    
    def on_revision_change(self, event_type: str, file_path: str):
        """
        Handle changes in Needs_Revision/ folder.
        
        Args:
            event_type: 'created', 'deleted', 'moved'
            file_path: Full path to file
        """
        if event_type != 'created':
            return
        
        file_path = Path(file_path)
        
        logger.write_to_timeline(
            f"Task needs revision: {file_path.name}",
            actor="orchestrator",
            message_level="WARNING"
        )
        
        # Move back to Needs_Action/ with high priority
        # (Folder Watcher will detect and reprocess)
        dest = settings.needs_action_path / file_path.name
        if dest.exists():
            dest.unlink()
        
        import shutil
        shutil.move(str(file_path), str(dest))
        
        logger.write_to_timeline(
            f"Moved to Needs_Action/ for reprocessing: {file_path.name}",
            actor="orchestrator",
            message_level="INFO"
        )
    
    def move_to_processing(self, file_path: Path):
        """
        Move file to Processing/ folder.
        
        Args:
            file_path: Path to file to move
        """
        dest = settings.processing_path / file_path.name
        
        if dest.exists():
            dest.unlink()
        
        import shutil
        shutil.move(str(file_path), str(dest))
        
        logger.write_to_timeline(
            f"Moved to Processing/: {file_path.name}",
            actor="orchestrator",
            message_level="INFO"
        )
    
    def call_claude_runner(self, file_path: Path):
        """
        Call Claude Runner to process task.

        Args:
            file_path: Path to task file in Processing/
        """
        # Build command
        cmd = [
            sys.executable,
            str(project_root / "claude_runner.py"),
            str(file_path)
        ]

        logger.write_to_timeline(
            f"Calling Claude Runner for: {file_path.name}",
            actor="orchestrator",
            message_level="INFO"
        )
        
        # Log the exact command for debugging
        logger.write_to_timeline(
            f"Claude Runner command: {' '.join(cmd)}",
            actor="orchestrator",
            message_level="DEBUG"
        )

        # Start Claude Runner as separate process
        # Keep reference to prevent garbage collection
        try:
            # Use Popen to start process (non-blocking)
            # Don't capture output - let Claude Runner log directly
            process = subprocess.Popen(
                cmd,
                stdout=None,    # Don't capture - show in console
                stderr=None,    # Don't capture - show errors
            )
            
            logger.write_to_timeline(
                f"Claude Runner started (PID: {process.pid})",
                actor="orchestrator",
                message_level="INFO"
            )
            
            # Store process reference to prevent garbage collection
            if not hasattr(self, 'claude_processes'):
                self.claude_processes = []
            self.claude_processes.append(process)
            
        except Exception as e:
            logger.log_error(
                f"Failed to call Claude Runner: {e}",
                error=e,
                actor="orchestrator"
            )
    
    def check_timeouts(self):
        """Check for timed out tasks (Claude crashed)."""
        now = datetime.now()
        
        for file_path_str, move_time in list(self.file_move_times.items()):
            elapsed = (now - move_time).seconds
            
            if elapsed > self.timeout_seconds:
                # Timeout! No watcher event = Claude crashed
                file_path = Path(file_path_str)
                
                logger.write_to_timeline(
                    f"Timeout detected for: {file_path.name} ({elapsed}s > {self.timeout_seconds}s)",
                    actor="orchestrator",
                    message_level="WARNING"
                )
                
                # Move back to Needs_Action/
                self.move_back_to_needs_action(file_path)
                
                # Clean up tracker
                del self.file_move_times[file_path_str]
    
    def move_back_to_needs_action(self, file_path: Path):
        """
        Move file back to Needs_Action/ on timeout.

        Args:
            file_path: Path to file (should be in Processing/)
        """
        # Check if file still exists
        if not file_path.exists():
            logger.write_to_timeline(
                f"Timeout check: File already moved (Claude finished): {file_path.name}",
                actor="orchestrator",
                message_level="INFO"
            )
            # File was already processed by Claude Runner, just clean up tracker
            return
        
        dest = settings.needs_action_path / file_path.name

        if dest.exists():
            dest.unlink()

        import shutil
        shutil.move(str(file_path), str(dest))

        logger.write_to_timeline(
            f"Timeout - moved back to Needs_Action/: {file_path.name}",
            actor="orchestrator",
            message_level="WARNING"
        )
    
    def execute_approved_action(self, file_path: Path):
        """
        Execute approved action.
        
        Args:
            file_path: Path to approved file
        """
        # Read approval file to determine action type
        try:
            content = file_path.read_text(encoding='utf-8')
            
            # Parse approval type from content
            # For now, just move to Done/ as placeholder
            # TODO: Implement actual action execution
            
            dest = settings.done_path / file_path.name
            
            if dest.exists():
                dest.unlink()
            
            import shutil
            shutil.move(str(file_path), str(dest))
            
            logger.write_to_timeline(
                f"Approved action executed: {file_path.name}",
                actor="orchestrator",
                message_level="INFO"
            )
            
        except Exception as e:
            logger.log_error(
                f"Failed to execute approved action: {e}",
                error=e,
                actor="orchestrator"
            )


def main():
    """Main entry point."""
    logger.write_to_timeline(
        "AI Employee Orchestrator v2.0 starting",
        actor="orchestrator",
        message_level="INFO"
    )
    
    # Ensure vault directories exist
    settings.ensure_vault_directories()
    
    # Create and start orchestrator
    orchestrator = Orchestrator()
    orchestrator.start()


if __name__ == "__main__":
    main()
