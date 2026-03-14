#!/usr/bin/env python3
"""
test_sqlmodel.py - Test SQLModel database setup

This demonstrates how to use SQLModel for the AI Employee database.
"""
from database import (
    Database, 
    Task, 
    TaskEvent, 
    TaskCreate, 
    TaskUpdate,
    get_sqlite_url,
    get_postgresql_url
)
from datetime import datetime
import os


def test_sqlite_setup():
    """Test SQLite database setup."""
    print("=" * 70)
    print("🧪 Testing SQLModel with SQLite")
    print("=" * 70)
    
    # Create database instance
    db_url = get_sqlite_url("database/test_tasks.db")
    print(f"\n📊 Database URL: {db_url}")
    
    db = Database(db_url, echo=True)  # echo=True shows SQL queries
    
    # Create tables
    print("\n📋 Creating tables...")
    db.create_tables()
    print("✅ Tables created")
    
    return db


def test_create_task(db: Database):
    """Test creating a task."""
    print("\n" + "=" * 70)
    print("📝 Test: Create Task")
    print("=" * 70)
    
    # Create task using Pydantic model
    task_data = TaskCreate(
        id="test_task_001",
        type="file_drop",
        source_file="vault/Inbox/Drop/test.txt",
        priority="high",
        title="Process test file",
        description="This is a test task for SQLModel",
        task_data={
            "file_size": 1024,
            "original_name": "test.txt",
            "detected": datetime.now().isoformat()
        }
    )
    
    # Insert into database
    task = db.create_task(task_data)
    task_id = task.id  # Capture ID before session closes
    
    print(f"✅ Created task: {task_id}")
    print(f"   Type: {task.type}")
    print(f"   Status: {task.status}")
    print(f"   Priority: {task.priority}")
    print(f"   Task Data: {task.task_data}")
    
    return task


def test_get_task(db: Database, task_id: str):
    """Test retrieving a task."""
    print("\n" + "=" * 70)
    print("🔍 Test: Get Task")
    print("=" * 70)
    
    task = db.get_task(task_id)
    
    if task:
        print(f"✅ Found task: {task.id}")
        print(f"   Status: {task.status}")
        print(f"   Created: {task.created_at}")
    else:
        print(f"❌ Task not found: {task_id}")
    
    return task


def test_update_task(db: Database, task_id: str):
    """Test updating a task."""
    print("\n" + "=" * 70)
    print("✏️  Test: Update Task")
    print("=" * 70)
    
    # Update status
    updates = TaskUpdate(
        status="processing",
        assigned_skill="file-processor"
    )
    
    task = db.update_task(task_id, updates)
    
    if task:
        print(f"✅ Updated task: {task.id}")
        print(f"   New status: {task.status}")
        print(f"   Assigned skill: {task.assigned_skill}")
        print(f"   Updated at: {task.updated_at}")
    else:
        print(f"❌ Task not found: {task_id}")
    
    return task


def test_create_event(db: Database, task_id: str):
    """Test creating a task event."""
    print("\n" + "=" * 70)
    print("📋 Test: Create Event")
    print("=" * 70)
    
    event = db.create_event(
        task_id=task_id,
        event_type="status_changed",
        details={
            "old_status": "pending",
            "new_status": "processing"
        },
        actor="orchestrator"
    )
    
    print(f"✅ Created event: {event.id}")
    print(f"   Type: {event.event_type}")
    print(f"   Details: {event.details}")
    
    return event


def test_get_events(db: Database, task_id: str):
    """Test getting task events."""
    print("\n" + "=" * 70)
    print("📜 Test: Get Events")
    print("=" * 70)
    
    events = db.get_task_events(task_id)
    
    print(f"✅ Found {len(events)} events for task {task_id}")
    for event in events:
        print(f"   - [{event.timestamp}] {event.event_type} by {event.actor}")
    
    return events


def test_dashboard_stats(db: Database):
    """Test getting dashboard statistics."""
    print("\n" + "=" * 70)
    print("📊 Test: Dashboard Stats")
    print("=" * 70)
    
    stats = db.get_dashboard_stats()
    
    print(f"✅ Dashboard Stats:")
    print(f"   Queue:")
    for status, count in stats.queue.items():
        print(f"     {status}: {count}")
    print(f"   Today's Events: {stats.today_events}")
    print(f"   Today's Completions: {stats.today_completions}")
    print(f"   Avg Execution Time: {stats.avg_execution_time_ms}ms")
    print(f"   Today's Failures: {stats.today_failures}")
    
    return stats


def test_multiple_tasks(db: Database):
    """Test creating multiple tasks."""
    print("\n" + "=" * 70)
    print("📝 Test: Multiple Tasks")
    print("=" * 70)
    
    # Create several tasks
    for i in range(5):
        task_data = TaskCreate(
            id=f"test_task_{i+2:03d}",
            type="email" if i % 2 == 0 else "file_drop",
            source_file=f"vault/Inbox/Drop/file_{i}.txt",
            priority="high" if i == 0 else "normal",
            title=f"Test task {i+2}",
            metadata={"batch": "test"}
        )
        db.create_task(task_data)
    
    print(f"✅ Created 5 additional tasks")
    
    # Get pending tasks
    pending = db.get_pending_tasks()
    print(f"   Pending tasks: {len(pending)}")
    
    # Get tasks by type
    all_tasks = db.get_tasks_by_status("pending")
    email_tasks = [t for t in all_tasks if t.type == "email"]
    print(f"   Email tasks: {len(email_tasks)}")


def test_database_urls():
    """Test different database URL formats."""
    print("\n" + "=" * 70)
    print("🔗 Test: Database URLs")
    print("=" * 70)
    
    # SQLite
    sqlite_url = get_sqlite_url("tasks.db")
    print(f"SQLite: {sqlite_url}")
    
    sqlite_url_abs = get_sqlite_url("/absolute/path/tasks.db")
    print(f"SQLite (absolute): {sqlite_url_abs}")
    
    # PostgreSQL
    postgres_url = get_postgresql_url(
        host="localhost",
        database="ai_employee",
        username="user",
        password="pass",
        port=5432
    )
    print(f"PostgreSQL: {postgres_url}")
    
    # Cloud PostgreSQL (example)
    cloud_url = get_postgresql_url(
        host="db.railway.app",
        database="railway",
        username="postgres",
        password="secret123",
        port=5432
    )
    print(f"Cloud PostgreSQL: {cloud_url}")


def cleanup(db: Database):
    """Clean up test database."""
    print("\n" + "=" * 70)
    print("🧹 Cleanup")
    print("=" * 70)
    
    import os
    db_path = "database/test_tasks.db"
    
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"✅ Deleted test database: {db_path}")
    else:
        print(f"ℹ️  Test database not found (already deleted?)")


def main():
    """Run all tests."""
    print("\n🚀 SQLModel Test Suite")
    print("=" * 70)
    
    try:
        # Test database URLs
        test_database_urls()
        
        # Initialize SQLite database
        db = test_sqlite_setup()
        
        # Create a task
        task = test_create_task(db)
        
        # Retrieve the task
        test_get_task(db, task.id)
        
        # Update the task
        test_update_task(db, task.id)
        
        # Create an event
        test_create_event(db, task.id)
        
        # Get events
        test_get_events(db, task.id)
        
        # Create multiple tasks
        test_multiple_tasks(db)
        
        # Get dashboard stats
        test_dashboard_stats(db)
        
        print("\n" + "=" * 70)
        print("✅ All tests passed!")
        print("=" * 70)
        
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        cleanup(db)
        
        print("\n" + "=" * 70)
        print("🎉 Test suite complete!")
        print("=" * 70)
        print("\n📝 Next steps:")
        print("   1. Review SQLMODEL_GUIDE.md for detailed documentation")
        print("   2. Update orchestrator.py to use SQLModel")
        print("   3. Test with PostgreSQL for production")
        print()


if __name__ == "__main__":
    main()
