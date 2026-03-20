#!/usr/bin/env python3
"""
Simple test for Folder Watchers - No Orchestrator

This script tests if Folder Watchers can detect file changes.
"""

import sys
import time
import logging
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from watchers.folder_watcher import FolderWatcher


def on_needs_action_change(event_type: str, file_path: str):
    """Callback for Needs_Action/ folder"""
    logger.info(f"✅ CALLBACK: Needs_Action/ - {event_type}: {file_path}")
    print(f"\n{'='*70}")
    print(f"📁 NEEDS_ACTION CHANGE DETECTED!")
    print(f"   Event: {event_type}")
    print(f"   File: {file_path}")
    print(f"{'='*70}\n")


def main():
    logger.info("="*70)
    logger.info("FOLDER WATCHER TEST")
    logger.info("="*70)
    
    # Define test folders
    needs_action_path = project_root / "vault" / "Needs_Action"
    needs_action_path.mkdir(parents=True, exist_ok=True)
    
    logger.info(f"Watching folder: {needs_action_path}")
    logger.info(f"Folder exists: {needs_action_path.exists()}")
    logger.info(f"Folder absolute path: {needs_action_path.absolute()}")
    
    # Create folder watcher
    logger.info("Creating FolderWatcher...")
    watcher = FolderWatcher(str(needs_action_path), on_needs_action_change)
    
    logger.info("Starting FolderWatcher...")
    watcher.start()
    
    logger.info("="*70)
    logger.info("FOLDER WATCHER IS NOW WATCHING")
    logger.info("="*70)
    logger.info(f"Observer alive: {watcher.observer.is_alive()}")
    logger.info(f"Active threads: {len(threading.enumerate())}")
    logger.info("="*70)
    logger.info("")
    logger.info("INSTRUCTIONS:")
    logger.info(f"1. Open another terminal")
    logger.info(f"2. Create a file in: {needs_action_path}")
    logger.info(f"   Example: echo 'test' > '{needs_action_path}\\test.txt'")
    logger.info(f"3. Watch this terminal for detection logs")
    logger.info(f"4. Press Ctrl+C to stop")
    logger.info("")
    
    # Keep running
    try:
        while True:
            time.sleep(1)
            # Periodic status
            if not watcher.observer.is_alive():
                logger.error("❌ OBSERVER DIED!")
                break
    except KeyboardInterrupt:
        logger.info("\nInterrupted by user")
    finally:
        logger.info("Stopping watcher...")
        watcher.stop()
        logger.info("Watcher stopped")


if __name__ == "__main__":
    main()
