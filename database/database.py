"""
database.py - SQLite database for task tracking and audit logs

Provides persistent storage for:
- Task state tracking
- Event history
- Metrics and analytics
"""
import sqlite3
import json
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any
from contextlib import contextmanager

logger = logging.getLogger(__name__)


class TaskDatabase:
    """SQLite database for task tracking."""

    def __init__(self, db_path: Path):
        """
        Initialize the database.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_schema(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            # Tasks table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS tasks (
                    id TEXT PRIMARY KEY,
                    type TEXT NOT NULL,
                    source_file TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    priority TEXT DEFAULT 'normal',
                    title TEXT,
                    description TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    assigned_skill TEXT,
                    claude_output TEXT,
                    approval_required BOOLEAN DEFAULT FALSE,
                    approved_by TEXT,
                    approved_at TIMESTAMP,
                    execution_time_ms INTEGER,
                    error_message TEXT,
                    metadata JSON
                )
            """)

            # Task events table (audit trail)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS task_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    details JSON,
                    actor TEXT,
                    FOREIGN KEY (task_id) REFERENCES tasks(id)
                )
            """)

            # Metrics table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    metric_name TEXT NOT NULL,
                    metric_value REAL NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    labels JSON
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_status 
                ON tasks(status)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_tasks_type 
                ON tasks(type)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_task_events_task_id 
                ON task_events(task_id)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_name 
                ON metrics(metric_name)
            """)

            logger.info(f"Database initialized at {self.db_path}")

    def create_task(
        self,
        task_id: str,
        task_type: str,
        source_file: str,
        priority: str = "normal",
        title: str = "",
        description: str = "",
        metadata: Optional[Dict] = None
    ) -> str:
        """
        Create a new task.

        Returns:
            Task ID
        """
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO tasks (id, type, source_file, priority, title, description, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (task_id, task_type, source_file, priority, title, description, 
                  json.dumps(metadata) if metadata else None))

            # Log event
            self._log_event(conn, task_id, "task_created", {
                "type": task_type,
                "priority": priority,
                "title": title
            })

        return task_id

    def update_task_status(
        self,
        task_id: str,
        status: str,
        error_message: Optional[str] = None,
        execution_time_ms: Optional[int] = None
    ):
        """Update task status."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE tasks 
                SET status = ?, 
                    error_message = ?,
                    execution_time_ms = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (status, error_message, execution_time_ms, task_id))

            # Log event
            self._log_event(conn, task_id, "status_changed", {
                "new_status": status,
                "error": error_message,
                "execution_time_ms": execution_time_ms
            })

    def assign_skill(self, task_id: str, skill_name: str):
        """Assign a skill to handle the task."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE tasks 
                SET assigned_skill = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (skill_name, task_id))

            self._log_event(conn, task_id, "skill_assigned", {
                "skill": skill_name
            })

    def set_approval_required(
        self, 
        task_id: str, 
        approval_file: Optional[str] = None
    ):
        """Mark task as requiring approval."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE tasks 
                SET approval_required = TRUE,
                    metadata = json_set(
                        COALESCE(metadata, '{}'),
                        '$.approval_file', ?
                    ),
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (approval_file, task_id))

            self._log_event(conn, task_id, "approval_required", {
                "approval_file": approval_file
            })

    def approve_task(self, task_id: str, approved_by: str):
        """Mark task as approved."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE tasks 
                SET approved_by = ?,
                    approved_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (approved_by, task_id))

            self._log_event(conn, task_id, "task_approved", {
                "approved_by": approved_by
            })

    def set_claude_output(self, task_id: str, output: str):
        """Store Claude's output for a task."""
        with self.get_connection() as conn:
            conn.execute("""
                UPDATE tasks 
                SET claude_output = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (output, task_id))

            self._log_event(conn, task_id, "output_generated", {
                "output_length": len(output)
            })

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get a task by ID."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE id = ?", 
                (task_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_tasks_by_status(self, status: str) -> List[Dict[str, Any]]:
        """Get all tasks with a specific status."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM tasks WHERE status = ? ORDER BY created_at DESC",
                (status,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all pending tasks."""
        return self.get_tasks_by_status("pending")

    def get_processing_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks currently being processed."""
        return self.get_tasks_by_status("processing")

    def get_approval_pending_tasks(self) -> List[Dict[str, Any]]:
        """Get all tasks awaiting approval."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                SELECT * FROM tasks 
                WHERE approval_required = TRUE 
                AND status = 'pending_approval'
                ORDER BY created_at DESC
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_task_events(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all events for a task (audit trail)."""
        with self.get_connection() as conn:
            cursor = conn.execute(
                """
                SELECT * FROM task_events 
                WHERE task_id = ? 
                ORDER BY timestamp ASC
                """,
                (task_id,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def record_metric(self, metric_name: str, value: float, labels: Optional[Dict] = None):
        """Record a metric."""
        with self.get_connection() as conn:
            conn.execute("""
                INSERT INTO metrics (metric_name, metric_value, labels)
                VALUES (?, ?, ?)
            """, (metric_name, value, json.dumps(labels) if labels else None))

    def get_metrics(
        self, 
        metric_name: str, 
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get metrics by name."""
        with self.get_connection() as conn:
            if since:
                cursor = conn.execute("""
                    SELECT * FROM metrics 
                    WHERE metric_name = ? 
                    AND timestamp >= ?
                    ORDER BY timestamp DESC
                """, (metric_name, since.isoformat()))
            else:
                cursor = conn.execute("""
                    SELECT * FROM metrics 
                    WHERE metric_name = ?
                    ORDER BY timestamp DESC
                """, (metric_name,))
            return [dict(row) for row in cursor.fetchall()]

    def get_dashboard_stats(self) -> Dict[str, Any]:
        """Get statistics for dashboard."""
        with self.get_connection() as conn:
            # Queue counts
            queue_stats = {}
            for status in ['pending', 'processing', 'pending_approval', 'done', 'failed']:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM tasks WHERE status = ?",
                    (status,)
                )
                queue_stats[status] = cursor.fetchone()[0]

            # Today's activity
            cursor = conn.execute("""
                SELECT COUNT(*) FROM task_events 
                WHERE DATE(timestamp) = DATE('now')
            """)
            today_events = cursor.fetchone()[0]

            # Today's completions
            cursor = conn.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE status = 'done' 
                AND DATE(updated_at) = DATE('now')
            """)
            today_completions = cursor.fetchone()[0]

            # Average execution time (today)
            cursor = conn.execute("""
                SELECT AVG(execution_time_ms) FROM tasks 
                WHERE execution_time_ms IS NOT NULL
                AND DATE(updated_at) = DATE('now')
            """)
            avg_exec_time = cursor.fetchone()[0] or 0

            # Failures today
            cursor = conn.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE status = 'failed' 
                AND DATE(updated_at) = DATE('now')
            """)
            today_failures = cursor.fetchone()[0]

            return {
                "queue": queue_stats,
                "today_events": today_events,
                "today_completions": today_completions,
                "avg_execution_time_ms": int(avg_exec_time),
                "today_failures": today_failures
            }

    def _log_event(
        self, 
        conn, 
        task_id: str, 
        event_type: str, 
        details: Optional[Dict] = None,
        actor: str = "system"
    ):
        """Log a task event (internal method)."""
        conn.execute("""
            INSERT INTO task_events (task_id, event_type, details, actor)
            VALUES (?, ?, ?, ?)
        """, (task_id, event_type, json.dumps(details) if details else None, actor))

    def cleanup_old_tasks(self, days: int = 90):
        """Clean up tasks older than specified days."""
        with self.get_connection() as conn:
            conn.execute("""
                DELETE FROM task_events 
                WHERE task_id IN (
                    SELECT id FROM tasks 
                    WHERE created_at < datetime('now', ?)
                )
            """, (f'-{days} days',))

            conn.execute("""
                DELETE FROM tasks 
                WHERE created_at < datetime('now', ?)
                AND status IN ('done', 'rejected')
            """, (f'-{days} days',))

            logger.info(f"Cleaned up tasks older than {days} days")
