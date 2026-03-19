#!/usr/bin/env python3
"""
Example: Filesystem Watcher Usage

This example shows how to use the FilesystemWatcher with centralized configuration.
The watcher automatically uses paths from core.config.settings.

Usage:
    python example_filesystem_watcher_usage.py
    
Note: This script should be run from the project root, or it will automatically
change to the project root directory to load .env configuration.
"""

import os
import sys
import time
from pathlib import Path

# Change to project root directory to load .env properly
script_dir = Path(__file__).parent.resolve()
project_root = script_dir.parent
os.chdir(project_root)
sys.path.insert(0, str(project_root))

# No logging configuration needed - LoggingManager handles everything!

from watchers.filesystem_watcher import FilesystemWatcher

# Initialize watcher using centralized paths from settings
# No need to pass paths manually - uses settings.vault_path and settings.drop_folder_path
print("=" * 70)
print("FILESYSTEM WATCHER - Starting...")
print("=" * 70)
print(f"📁 Vault:           {project_root / 'vault'}")
print(f"📂 Drop Folder:     {project_root / 'vault' / 'Inbox' / 'Drop'}")
print(f"📋 Needs Action:    {project_root / 'vault' / 'Needs_Action'}")
print(f"📚 Drop History:    {project_root / 'vault' / 'Inbox' / 'Drop_History'}")
print("=" * 70)
print("\n👁️  Watching for new files in Drop folder...")
print("   (Drop files here to trigger processing)")
print("\n💡 Tip: Files already in Drop folder will be processed on startup")
print("🛑  Press Ctrl+C to stop\n")

watcher = FilesystemWatcher()
watcher.run()  # Blocks until Ctrl+C


# with FilesystemWatcher() as watcher:
#     print("Watching for file changes. Press Ctrl+C to stop.")
#     print("Watcher is ", watcher)
#     # try:
#     #     while True:
#     #         pass  # Keep the main thread alive
#     # except KeyboardInterrupt:
#     #     print("Stopping watcher...")