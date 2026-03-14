"""
db_engine.py - SQLModel database engine and session management

Provides database connection, session management, and CRUD operations.
Uses centralized configuration from config.py
"""
from sqlmodel import SQLModel, create_engine, Session, select
from typing import Optional, Generator, List, Dict, Any
from datetime import datetime, timedelta
from contextlib import contextmanager
import logging

from .models import Task, TaskEvent, Metric, DashboardStats, TaskCreate, TaskUpdate

logger = logging.getLogger(__name__)


class Database:
    """
    SQLModel database manager.
    
    Usage:
        # Option 1: Use settings from config.py (recommended)
        from config import settings
        db = Database(settings.database_url)
        
        # Option 2: Specify URL directly
        db = Database("sqlite:///database/tasks.db")
        
        # Create tables
        db.create_tables()
        
        # Use session
        with db.get_session() as session:
            task = Task(id="test", type="file_drop", source_file="/path")
            session.add(task)
            session.commit()
    """
    
    def __init__(self, database_url: Optional[str] = None, echo: bool = False):
        """
        Initialize database engine.
        
        Args:
            database_url: SQLAlchemy connection URL
                If None, uses settings from config.py
                Examples:
                - SQLite: "sqlite:///tasks.db"
                - PostgreSQL: "postgresql://user:pass@localhost/dbname"
                - MySQL: "mysql://user:pass@localhost/dbname"
            echo: If True, log all SQL statements (for debugging)
        """
        # Use provided URL or load from settings
        if database_url is None:
            from core import settings
            database_url = settings.database_url
        
        self.database_url = database_url
        self.echo = echo
        
        # Create engine with appropriate settings per database type
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False  # Needed for SQLite
        
        self.engine = create_engine(
            database_url,
            echo=echo,
            connect_args=connect_args
        )
        
        logger.info(f"Database engine created: {database_url}")

    def create_tables(self):
        """Create all database tables."""
        logger.info("Creating database tables...")
        SQLModel.metadata.create_all(self.engine)
        logger.info("✅ Database tables created")

    def drop_tables(self):
        """Drop all database tables (use with caution!)."""
        logger.warning("Dropping all database tables...")
        SQLModel.metadata.drop_all(self.engine)
        logger.warning("⚠️  Database tables dropped")

    @contextmanager
    def get_session(self) -> Generator[Session, None, None]:
        """
        Get database session (context manager).
        
        Usage:
            with db.get_session() as session:
                # Use session
                session.add(task)
                session.commit()
        """
        session = Session(self.engine)
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            raise e
        finally:
            session.close()

    # ========================================================================
    # Task CRUD Operations
    # ========================================================================

    def create_task(self, task_data: TaskCreate) -> Task:
        """Create a new task."""
        with self.get_session() as session:
            task = Task(
                id=task_data.id,
                type=task_data.type,
                source_file=task_data.source_file,
                priority=task_data.priority,
                title=task_data.title,
                description=task_data.description,
                task_data=task_data.task_data
            )
            session.add(task)
            
            # Create event
            event = TaskEvent(
                task_id=task.id,
                event_type="task_created",
                details={"type": task.type, "priority": task.priority}
            )
            session.add(event)
            
            logger.info(f"Created task: {task.id}")
            return task

    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        with self.get_session() as session:
            return session.get(Task, task_id)

    def get_task_with_events(self, task_id: str) -> Optional[Task]:
        """Get a task with its events."""
        with self.get_session() as session:
            statement = select(Task).where(Task.id == task_id)
            task = session.exec(statement).first()
            
            if task:
                # Load events
                statement = select(TaskEvent).where(TaskEvent.task_id == task_id)
                task.events = session.exec(statement).all()
            
            return task

    def update_task(self, task_id: str, updates: TaskUpdate) -> Optional[Task]:
        """Update a task."""
        with self.get_session() as session:
            task = session.get(Task, task_id)
            if not task:
                return None
            
            # Apply updates
            update_data = updates.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                setattr(task, field, value)
            
            task.updated_at = datetime.utcnow()
            session.add(task)
            
            # Log event
            if updates.status:
                event = TaskEvent(
                    task_id=task_id,
                    event_type="status_changed",
                    details={"new_status": updates.status}
                )
                session.add(event)
            
            logger.info(f"Updated task: {task_id}")
            return task

    def delete_task(self, task_id: str) -> bool:
        """Delete a task."""
        with self.get_session() as session:
            task = session.get(Task, task_id)
            if not task:
                return False
            
            session.delete(task)
            logger.info(f"Deleted task: {task_id}")
            return True

    def get_tasks_by_status(self, status: str) -> List[Task]:
        """Get all tasks with a specific status."""
        with self.get_session() as session:
            statement = select(Task).where(Task.status == status).order_by(Task.created_at.desc())
            return session.exec(statement).all()

    def get_pending_tasks(self) -> List[Task]:
        """Get all pending tasks."""
        return self.get_tasks_by_status("pending")

    def get_processing_tasks(self) -> List[Task]:
        """Get all tasks currently being processed."""
        return self.get_tasks_by_status("processing")

    def get_tasks_today(self) -> List[Task]:
        """Get all tasks created today."""
        with self.get_session() as session:
            today = datetime.utcnow().date()
            statement = select(Task).where(
                Task.created_at >= today
            ).order_by(Task.created_at.desc())
            return session.exec(statement).all()

    # ========================================================================
    # TaskEvent Operations
    # ========================================================================

    def create_event(
        self, 
        task_id: str, 
        event_type: str, 
        details: Optional[Dict[str, Any]] = None,
        actor: str = "system"
    ) -> TaskEvent:
        """Create a task event."""
        with self.get_session() as session:
            event = TaskEvent(
                task_id=task_id,
                event_type=event_type,
                details=details,
                actor=actor
            )
            session.add(event)
            logger.debug(f"Created event: {event_type} for task {task_id}")
            return event

    def get_task_events(self, task_id: str) -> List[TaskEvent]:
        """Get all events for a task."""
        with self.get_session() as session:
            statement = select(TaskEvent).where(
                TaskEvent.task_id == task_id
            ).order_by(TaskEvent.timestamp.asc())
            return session.exec(statement).all()

    # ========================================================================
    # Metric Operations
    # ========================================================================

    def record_metric(
        self, 
        metric_name: str, 
        value: float, 
        labels: Optional[Dict[str, str]] = None
    ) -> Metric:
        """Record a metric."""
        with self.get_session() as session:
            metric = Metric(
                metric_name=metric_name,
                metric_value=value,
                labels=labels
            )
            session.add(metric)
            return metric

    def get_metrics(
        self, 
        metric_name: str, 
        since: Optional[datetime] = None,
        limit: int = 100
    ) -> List[Metric]:
        """Get metrics by name."""
        with self.get_session() as session:
            statement = select(Metric).where(Metric.metric_name == metric_name)
            
            if since:
                statement = statement.where(Metric.timestamp >= since)
            
            statement = statement.order_by(Metric.timestamp.desc()).limit(limit)
            return session.exec(statement).all()

    # ========================================================================
    # Dashboard Statistics
    # ========================================================================

    def get_dashboard_stats(self) -> DashboardStats:
        """Get statistics for dashboard."""
        with self.get_session() as session:
            # Queue counts by status
            queue = {}
            for status in ["pending", "processing", "pending_approval", "done", "failed"]:
                statement = select(Task).where(Task.status == status)
                count = len(session.exec(statement).all())
                queue[status] = count
            
            # Today's stats
            today = datetime.utcnow().date()
            
            # Events today
            statement = select(TaskEvent).where(
                TaskEvent.timestamp >= today
            )
            today_events = len(session.exec(statement).all())
            
            # Completions today
            statement = select(Task).where(
                Task.status == "done",
                Task.updated_at >= today
            )
            today_completions = len(session.exec(statement).all())
            
            # Average execution time today
            statement = select(Task).where(
                Task.status == "done",
                Task.updated_at >= today,
                Task.execution_time_ms != None
            )
            tasks_with_time = session.exec(statement).all()
            avg_exec_time = (
                sum(t.execution_time_ms for t in tasks_with_time) // len(tasks_with_time)
                if tasks_with_time else 0
            )
            
            # Failures today
            statement = select(Task).where(
                Task.status == "failed",
                Task.updated_at >= today
            )
            today_failures = len(session.exec(statement).all())
            
            return DashboardStats(
                queue=queue,
                today_events=today_events,
                today_completions=today_completions,
                avg_execution_time_ms=avg_exec_time,
                today_failures=today_failures
            )

    # ========================================================================
    # Cleanup Operations
    # ========================================================================

    def cleanup_old_tasks(self, days: int = 90):
        """Clean up old completed tasks."""
        with self.get_session() as session:
            cutoff = datetime.utcnow() - timedelta(days=days)
            
            # Delete old events first (foreign key constraint)
            statement = select(Task).where(
                Task.status.in_(["done", "rejected"]),
                Task.created_at < cutoff
            )
            old_tasks = session.exec(statement).all()
            
            for task in old_tasks:
                # Delete events
                event_statement = select(TaskEvent).where(
                    TaskEvent.task_id == task.id
                )
                events = session.exec(event_statement).all()
                for event in events:
                    session.delete(event)
                
                # Delete task
                session.delete(task)
            
            logger.info(f"Cleaned up {len(old_tasks)} old tasks")


# ============================================================================
# Database URL Helpers
# ============================================================================

def get_sqlite_url(db_path: str, relative_to: Optional[str] = None) -> str:
    """
    Get SQLite database URL.
    
    Examples:
        get_sqlite_url("tasks.db") → "sqlite:///tasks.db"
        get_sqlite_url("/absolute/path/tasks.db") → "sqlite:////absolute/path/tasks.db"
    """
    from pathlib import Path
    
    if db_path.startswith("/") or db_path.startswith("\\"):
        # Absolute path
        return f"sqlite:///{db_path}"
    else:
        # Relative path
        if relative_to:
            db_path = str(Path(relative_to) / db_path)
        return f"sqlite:///{db_path}"


def get_postgresql_url(
    host: str,
    database: str,
    username: str,
    password: str,
    port: int = 5432
) -> str:
    """
    Get PostgreSQL database URL.
    
    Example:
        get_postgresql_url("localhost", "mydb", "user", "pass")
        → "postgresql://user:pass@localhost:5432/mydb"
    """
    return f"postgresql://{username}:{password}@{host}:{port}/{database}"


def get_mysql_url(
    host: str,
    database: str,
    username: str,
    password: str,
    port: int = 3306
) -> str:
    """
    Get MySQL database URL.
    
    Example:
        get_mysql_url("localhost", "mydb", "user", "pass")
        → "mysql://user:pass@localhost:3306/mydb"
    """
    return f"mysql://{username}:{password}@{host}:{port}/{database}"
