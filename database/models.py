"""
models.py - SQLModel database models for AI Employee

These models define the database schema and provide type-safe access.
"""
from sqlmodel import SQLModel, Field, Relationship, Column, JSON
from typing import Optional, List, Dict, Any
from datetime import datetime
import json


# ============================================================================
# Database Models
# ============================================================================

class Task(SQLModel, table=True):
    """
    Task model - represents a unit of work in the AI Employee system.
    
    Lifecycle:
    pending → processing → pending_approval → approved → done
                              ↓
                         failed/rejected
    """
    __tablename__ = "tasks"
    
    # Primary Key
    id: str = Field(primary_key=True)
    
    # Core Fields
    type: str = Field(..., max_length=50, description="Task type: file_drop, email, etc.")
    source_file: str = Field(..., description="Path to source file in vault")
    status: str = Field(default="pending", max_length=50)
    priority: str = Field(default="normal", max_length=20)
    
    # Content
    title: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None)
    
    # Processing
    assigned_skill: Optional[str] = Field(default=None, max_length=100)
    claude_output: Optional[str] = Field(default=None)
    
    # Approval
    approval_required: bool = Field(default=False)
    approved_by: Optional[str] = Field(default=None, max_length=100)
    approved_at: Optional[datetime] = Field(default=None)
    
    # Execution
    execution_time_ms: Optional[int] = Field(default=None)
    error_message: Optional[str] = Field(default=None)
    
    # Task Data (JSON) - renamed from 'metadata' to avoid conflict
    task_data: Optional[Dict[str, Any]] = Field(
        default=None, 
        sa_column=Column("task_data", JSON),
        description="Additional task metadata and context"
    )
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    events: List["TaskEvent"] = Relationship(back_populates="task")
    
    def __repr__(self) -> str:
        return f"<Task(id={self.id}, type={self.type}, status={self.status})>"


class TaskEvent(SQLModel, table=True):
    """
    Task Event model - audit trail for task state changes.
    
    Every significant action on a task creates an event.
    """
    __tablename__ = "task_events"
    
    # Primary Key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Foreign Key
    task_id: str = Field(..., foreign_key="tasks.id", index=True)
    
    # Event Data
    event_type: str = Field(..., max_length=50)
    actor: str = Field(default="system", max_length=100)
    details: Optional[Dict[str, Any]] = Field(default=None, sa_column=Column("details", JSON))
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    task: Optional[Task] = Relationship(back_populates="events")
    
    def __repr__(self) -> str:
        return f"<TaskEvent(id={self.id}, type={self.event_type}, task={self.task_id})>"


class Metric(SQLModel, table=True):
    """
    Metric model - time-series metrics for analytics.
    
    Examples:
    - task_completion_time
    - tasks_per_hour
    - error_rate
    - approval_rate
    """
    __tablename__ = "metrics"
    
    # Primary Key
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Metric Data
    metric_name: str = Field(..., max_length=100, index=True)
    metric_value: float = Field(...)
    labels: Optional[Dict[str, str]] = Field(default=None, sa_column=Column("labels", JSON))
    
    # Timestamp
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    
    def __repr__(self) -> str:
        return f"<Metric(name={self.metric_name}, value={self.metric_value})>"


# ============================================================================
# Pydantic-Only Models (for API responses, not stored in DB)
# ============================================================================

class TaskRead(SQLModel):
    """Task model for reading (includes computed fields)."""
    id: str
    type: str
    source_file: str
    status: str
    priority: str
    title: Optional[str]
    description: Optional[str]
    assigned_skill: Optional[str]
    approval_required: bool
    created_at: datetime
    updated_at: datetime


class DashboardStats(SQLModel):
    """Statistics for dashboard display."""
    queue: Dict[str, int] = Field(
        default_factory=lambda: {
            "pending": 0,
            "processing": 0,
            "pending_approval": 0,
            "done": 0,
            "failed": 0
        }
    )
    today_events: int = 0
    today_completions: int = 0
    avg_execution_time_ms: int = 0
    today_failures: int = 0


class TaskCreate(SQLModel):
    """Model for creating a new task."""
    id: str
    type: str
    source_file: str
    priority: str = "normal"
    title: str = ""
    description: str = ""
    task_data: Optional[Dict[str, Any]] = None


class TaskUpdate(SQLModel):
    """Model for updating an existing task."""
    status: Optional[str] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None
    assigned_skill: Optional[str] = None
