#!/usr/bin/env python3
"""Test watchdog observer directly"""

import time
import logging
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(message)s')
logger = logging.getLogger(__name__)

class TestHandler(FileSystemEventHandler):
    def __init__(self, name):
        self.name = name
        logger.info(f"TestHandler '{name}' created")
    
    def on_created(self, event):
        logger.info(f"📁 {self.name}.on_created() called for: {event.src_path}")
        if not event.is_directory:
            logger.info(f"File created: {event.src_path}")
    
    def dispatch_event(self, event):
        logger.info(f"🔍 {self.name}.dispatch_event() received: {type(event).__name__}")
        super().dispatch_event(event)

# Test
folder_to_watch = Path("./vault/Needs_Action").resolve()
logger.info(f"Watching folder: {folder_to_watch}")

handler = TestHandler("TestHandler")
observer = Observer()

logger.info(f"Scheduling observer for: {folder_to_watch}")
observer.schedule(handler, str(folder_to_watch), recursive=False)
logger.info("Observer scheduled")

observer.start()
logger.info(f"Observer started, alive={observer.is_alive()}")

# Wait for initialization
time.sleep(1)
logger.info("Observer ready")

# Keep running for 30 seconds
logger.info("Waiting for file creation events (30 seconds)...")
logger.info(f"Drop a file in: {folder_to_watch}")

try:
    for i in range(30):
        time.sleep(1)
        if i % 5 == 0:
            logger.info(f"Still watching... {30-i} seconds remaining")
except KeyboardInterrupt:
    logger.info("Interrupted")

observer.stop()
observer.join()
logger.info("Observer stopped")
