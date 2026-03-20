#!/usr/bin/env python3
"""
ULTRA SIMPLE Watchdog Test

Direct watchdog usage - no wrappers
"""

import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class SimpleHandler(FileSystemEventHandler):
    def __init__(self):
        logger.info("SimpleHandler created")
    
    def on_created(self, event):
        if not event.is_directory:
            logger.info(f"📁 FILE CREATED: {event.src_path}")
            print(f"\n{'='*70}")
            print(f"✅ FILE CREATED DETECTED!")
            print(f"   Path: {event.src_path}")
            print(f"{'='*70}\n")
    
    def on_moved(self, event):
        if not event.is_directory:
            logger.info(f"📁 FILE MOVED: {event.src_path} → {event.dest_path}")
            print(f"\n{'='*70}")
            print(f"✅ FILE MOVED DETECTED!")
            print(f"   From: {event.src_path}")
            print(f"   To: {event.dest_path}")
            print(f"{'='*70}\n")

# Test
folder = Path("./vault/Needs_Action").resolve()
logger.info(f"Watching: {folder}")
logger.info(f"Exists: {folder.exists()}")

handler = SimpleHandler()
observer = Observer()
observer.schedule(handler, str(folder), recursive=False)
observer.start()

logger.info("Observer started")
logger.info(f"Alive: {observer.is_alive()}")

print("\n" + "="*70)
print("WATCHING FOR FILE CREATION")
print(f"Folder: {folder}")
print("Create a file in this folder to test")
print("Press Ctrl+C to stop")
print("="*70 + "\n")

try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    observer.stop()
    observer.join()
    logger.info("Stopped")
