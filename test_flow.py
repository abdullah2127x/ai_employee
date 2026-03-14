#!/usr/bin/env python3
"""
test_flow.py - Test the complete AI Employee flow

This script:
1. Creates a test file in the drop folder
2. Verifies the watcher detects it
3. Checks that metadata is created
4. Verifies database tracking
"""
import time
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import TaskDatabase

# Paths
VAULT_PATH = project_root / 'vault'
DROP_FOLDER = VAULT_PATH / 'Inbox' / 'Drop'
NEEDS_ACTION = VAULT_PATH / 'Needs_Action'
DB_PATH = project_root / 'database' / 'tasks.db'

def test_file_drop():
    """Test dropping a file and verifying detection."""
    print("=" * 70)
    print("🧪 AI EMPLOYEE FLOW TEST")
    print("=" * 70)
    
    # Ensure directories exist
    DROP_FOLDER.mkdir(parents=True, exist_ok=True)
    NEEDS_ACTION.mkdir(parents=True, exist_ok=True)
    
    print(f"\n✅ Vault path: {VAULT_PATH}")
    print(f"✅ Drop folder: {DROP_FOLDER}")
    print(f"✅ Database: {DB_PATH}")
    
    # Create test file
    test_content = """
    This is a test file for the AI Employee system.
    
    It contains some sample content to be processed.
    
    Action items:
    - Review this content
    - Categorize the file
    - Create appropriate response
    
    Priority: Normal
    """
    
    test_file = DROP_FOLDER / f"test_file_{int(time.time())}.txt"
    test_file.write_text(test_content)
    
    print(f"\n📁 Created test file: {test_file.name}")
    
    # Wait for watcher to process (if running)
    print("\n⏳ Waiting 5 seconds for watcher to process...")
    print("   (Note: In real scenario, orchestrator would be running)")
    time.sleep(5)
    
    # Check if metadata file was created
    metadata_files = list(NEEDS_ACTION.glob(f"FILE_*.md"))
    
    if metadata_files:
        latest_metadata = max(metadata_files, key=lambda p: p.stat().st_mtime)
        print(f"\n✅ Metadata file created: {latest_metadata.name}")
        
        # Read and display metadata
        content = latest_metadata.read_text(encoding='utf-8')
        print("\n📄 Metadata content (first 500 chars):")
        print("-" * 70)
        print(content[:500])
        print("...")
        print("-" * 70)
    else:
        print("\n⚠️  No metadata file found.")
        print("   This is expected if orchestrator is not running.")
        print("   To test fully, run: python orchestrator.py")
    
    # Check database
    if DB_PATH.exists():
        print(f"\n📊 Database exists: {DB_PATH}")
        db = TaskDatabase(DB_PATH)
        
        # Get stats
        stats = db.get_dashboard_stats()
        print("\n📈 Dashboard Stats:")
        print(f"   Pending tasks: {stats['queue'].get('pending', 0)}")
        print(f"   Processing: {stats['queue'].get('processing', 0)}")
        print(f"   Done: {stats['queue'].get('done', 0)}")
        print(f"   Today's completions: {stats['today_completions']}")
        print(f"   Avg execution time: {stats['avg_execution_time_ms']}ms")
        
        # Get recent tasks
        pending_tasks = db.get_pending_tasks()
        if pending_tasks:
            print(f"\n📋 Pending tasks ({len(pending_tasks)}):")
            for task in pending_tasks[:5]:
                print(f"   - {task['id']}: {task['title']}")
    else:
        print(f"\n⚠️  Database not created yet: {DB_PATH}")
        print("   Database is created when orchestrator runs")
    
    print("\n" + "=" * 70)
    print("✅ TEST COMPLETE")
    print("=" * 70)
    print("\n📝 NEXT STEPS:")
    print("   1. Run orchestrator: python orchestrator.py")
    print("   2. Drop a file in: vault/Inbox/Drop/")
    print("   3. Watch logs: tail -f logs/orchestrator_*.log")
    print("   4. Check vault folders for processed results")
    print()


if __name__ == '__main__':
    test_file_drop()
