#!/usr/bin/env python3
"""Test watcher with verbose output"""

import os
import sys
import time
from pathlib import Path

# Change to project root
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

# Enable verbose logging
os.environ['DEV_MODE'] = 'true'

import logging
logging.basicConfig(level=logging.DEBUG, format='%(name)s - %(levelname)s - %(message)s')

from watchers.filesystem_watcher import FilesystemWatcher

print("=" * 60)
print("Testing Filesystem Watcher")
print("=" * 60)
print(f"Drop folder: {project_root / 'vault' / 'Inbox' / 'Drop'}")
print(f"Files in Drop: {list((project_root / 'vault' / 'Inbox' / 'Drop').iterdir())}")
print("=" * 60)

watcher = FilesystemWatcher()

print("\nStarting watcher for 5 seconds...")
watcher.start()

time.sleep(5)

print("\nStopping watcher...")
watcher.stop()

print("\nCheck Needs_Action folder:")
needs_action = project_root / 'vault' / 'Needs_Action'
if needs_action.exists():
    print(f"Files: {list(needs_action.glob('FILE_*.md'))}")
else:
    print("Needs_Action folder doesn't exist!")

print("\nCheck Drop_History folder:")
drop_history = project_root / 'vault' / 'Inbox' / 'Drop_History'
if drop_history.exists():
    print(f"Files: {list(drop_history.iterdir())}")
else:
    print("Drop_History folder doesn't exist!")
