"""Database module for AI Employee task tracking.

Two implementations available:
1. Legacy: database.TaskDatabase (raw SQLite)
2. Modern: db_engine.Database (SQLModel ORM)

Recommended: Use SQLModel (db_engine) for new code.
"""
from .models import Task, TaskEvent, Metric, DashboardStats, TaskCreate, TaskUpdate
from .db_engine import Database, get_sqlite_url, get_postgresql_url, get_mysql_url

# Legacy import for backwards compatibility
from .database import TaskDatabase

__all__ = [
    # SQLModel (Recommended)
    'Task',
    'TaskEvent',
    'Metric',
    'DashboardStats',
    'TaskCreate',
    'TaskUpdate',
    'Database',
    'get_sqlite_url',
    'get_postgresql_url',
    'get_mysql_url',
    
    # Legacy
    'TaskDatabase',
]
