#!/usr/bin/env python3
"""Test FilesystemWatcher directly"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from database import TaskDatabase
from watchers.filesystem_watcher import FilesystemWatcher

# Paths
vault_path = Path("./vault").resolve()
drop_folder = vault_path / "Inbox" / "Drop"
db_path = Path("./database/tasks.db").resolve()

print(f"Vault: {vault_path}")
print(f"Drop: {drop_folder}")
print(f"DB: {db_path}")

try:
    db = TaskDatabase(db_path)
    print("✅ Database initialized")
    
    watcher = FilesystemWatcher(str(vault_path), str(drop_folder), db)
    print("✅ FilesystemWatcher created")
    
    print("Starting watcher... (Press Ctrl+C to stop)")
    watcher.run()
    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    input("Press Enter to exit...")
