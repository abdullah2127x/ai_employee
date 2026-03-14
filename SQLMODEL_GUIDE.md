# SQLModel Database Guide

**Purpose:** Migrate from raw SQLite to SQLModel ORM for better type safety, validation, and cloud deployment readiness.

---

## 🎯 **Why SQLModel?**

### **Current Setup (Raw SQLite):**

```python
# ❌ Manual SQL, no type safety
conn.execute("""
    INSERT INTO tasks (id, type, status, metadata)
    VALUES (?, ?, ?, ?)
""", (task_id, "file_drop", "pending", json.dumps(metadata)))

# ❌ Manual dict conversion
cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
row = cursor.fetchone()
task = dict(row) if row else None

# ❌ Hard to switch databases (SQLite → PostgreSQL requires rewrite)
```

**Problems:**
- No type checking
- Manual JSON serialization
- SQL injection risks
- Database coupling
- Hard to refactor

---

### **With SQLModel:**

```python
# ✅ Type-safe, validated models
from database import Task, Database

task = Task(
    id="task_123",
    type="file_drop",
    status="pending",
    metadata={"key": "value"}  # Auto-serialized to JSON
)

# ✅ Simple CRUD operations
db = Database("sqlite:///tasks.db")
db.create_tables()

with db.get_session() as session:
    session.add(task)
    session.commit()

# ✅ Query with type safety
from sqlmodel import select
statement = select(Task).where(Task.id == "task_123")
task = session.exec(statement).first()

# ✅ Switch database by changing URL (no code changes!)
db = Database("postgresql://user:pass@localhost/mydb")
```

**Benefits:**
- ✅ Full type safety and IDE support
- ✅ Automatic validation (Pydantic)
- ✅ Auto-serialization (JSON, datetime)
- ✅ Database agnostic (SQLite, PostgreSQL, MySQL)
- ✅ Easy refactoring
- ✅ Relationships and foreign keys handled automatically

---

## 📦 **Installation**

```bash
cd GeneralAgentWithCursor

# Install SQLModel and database drivers
uv sync

# New dependencies added:
# - sqlmodel>=0.0.22        (ORM with Pydantic)
# - psycopg2-binary>=2.9.0  (PostgreSQL driver)
# - mysqlclient>=2.2.0      (MySQL driver)
```

---

## 🚀 **Quick Start**

### **Step 1: Define Your Models**

Models are already defined in `database/models.py`:

```python
from database import Task, TaskEvent, Metric

# Task model example
task = Task(
    id="file_20260312_120000_test.txt",
    type="file_drop",
    source_file="vault/Inbox/Drop/test.txt",
    priority="normal",
    title="Process file: test.txt",
    metadata={"file_size": 1024}
)
```

### **Step 2: Initialize Database**

```python
from database import Database, get_sqlite_url

# For SQLite (local development)
db = Database(get_sqlite_url("database/tasks.db"))
db.create_tables()

# That's it! Tables are created.
```

### **Step 3: Use CRUD Operations**

```python
from database import TaskCreate, TaskUpdate

# Create a task
task_data = TaskCreate(
    id="task_001",
    type="file_drop",
    source_file="vault/Inbox/Drop/test.txt",
    priority="high",
    title="Process urgent file"
)

task = db.create_task(task_data)
print(f"Created: {task.id}")

# Get a task
task = db.get_task("task_001")
print(f"Status: {task.status}")

# Update a task
updates = TaskUpdate(status="processing", assigned_skill="file-processor")
task = db.update_task("task_001", updates)
print(f"Updated: {task.status}")

# Get dashboard stats
stats = db.get_dashboard_stats()
print(f"Pending tasks: {stats.queue['pending']}")
```

---

## 📊 **Complete Example: Migrating orchestrator.py**

### **Before (Raw SQLite):**

```python
from database import TaskDatabase

db = TaskDatabase("database/tasks.db")

# Create task
db.create_task(
    task_id="file_123",
    task_type="file_drop",
    source_file="vault/Inbox/Drop/test.txt",
    priority="high",
    title="Process file",
    metadata={"size": 1024}
)

# Update status
db.update_task_status("file_123", "processing")

# Get stats
stats = db.get_dashboard_stats()
```

### **After (SQLModel):**

```python
from database import Database, TaskCreate, TaskUpdate, get_sqlite_url

db = Database(get_sqlite_url("database/tasks.db"))
db.create_tables()

# Create task
task_data = TaskCreate(
    id="file_123",
    type="file_drop",
    source_file="vault/Inbox/Drop/test.txt",
    priority="high",
    title="Process file",
    metadata={"size": 1024}
)
task = db.create_task(task_data)

# Update status
updates = TaskUpdate(status="processing", assigned_skill="file-processor")
task = db.update_task("file_123", updates)

# Get stats
stats = db.get_dashboard_stats()
```

**Key Differences:**
- ✅ Type-safe models instead of raw dicts
- ✅ Validation on field types and constraints
- ✅ Auto-serialization of metadata (no `json.dumps()`)
- ✅ Same API, just cleaner code

---

## 🌐 **Database URL Configuration**

### **Development (SQLite):**

```python
# .env
DATABASE_URL=sqlite:///database/tasks.db

# Code
from database import Database
from dotenv import load_dotenv
import os

load_dotenv()
db = Database(os.getenv("DATABASE_URL"))
db.create_tables()
```

### **Production (PostgreSQL):**

```python
# .env (production)
DATABASE_URL=postgresql://user:password@localhost:5432/ai_employee

# Code (no changes!)
db = Database(os.getenv("DATABASE_URL"))
db.create_tables()
```

### **Cloud (PostgreSQL as a Service):**

```python
# .env (Cloud: Railway, Render, Heroku, etc.)
DATABASE_URL=postgresql://user:pass@db.railway.app:5432/railway

# Code (still no changes!)
db = Database(os.getenv("DATABASE_URL"))
db.create_tables()
```

**The magic:** **Zero code changes** to switch databases!

---

## 🔧 **Migration Guide: SQLite → PostgreSQL**

### **Step 1: Install PostgreSQL Driver**

Already in `pyproject.toml`:
```toml
dependencies = [
    "sqlmodel>=0.0.22",
    "psycopg2-binary>=2.9.0",  # PostgreSQL driver
]
```

### **Step 2: Update Environment Variable**

```bash
# Development (.env.local)
DATABASE_URL=sqlite:///database/tasks.db

# Production (.env.production)
DATABASE_URL=postgresql://user:password@localhost:5432/ai_employee
```

### **Step 3: Migrate Data (Optional)**

```python
# migrate.py - Migrate from SQLite to PostgreSQL

from database import Database, Task

# Connect to both databases
sqlite_db = Database("sqlite:///database/tasks.db")
postgres_db = Database("postgresql://user:pass@localhost/ai_employee")

postgres_db.create_tables()

# Migrate tasks
with sqlite_db.get_session() as sqlite_session:
    tasks = sqlite_session.exec(select(Task)).all()
    
    with postgres_db.get_session() as postgres_session:
        for task in tasks:
            # Create new task in PostgreSQL
            new_task = Task(
                id=task.id,
                type=task.type,
                source_file=task.source_file,
                status=task.status,
                # ... copy all fields
            )
            postgres_session.add(new_task)
        
        postgres_session.commit()

print(f"Migrated {len(tasks)} tasks")
```

---

## ☁️ **Cloud Deployment**

### **Option 1: Railway.app (Easiest)**

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Create project
railway init

# 4. Add PostgreSQL
railway add postgresql

# 5. Deploy
railway up
```

**Railway automatically:**
- ✅ Provisions PostgreSQL database
- ✅ Sets `DATABASE_URL` environment variable
- ✅ Deploys your code
- ✅ Runs migrations

### **Option 2: Render.com**

```yaml
# render.yaml
services:
  - type: web
    name: ai-employee
    env: python
    buildCommand: pip install -r requirements.txt
    startCommand: python orchestrator.py
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: ai_employee_db
          property: connectionString

databases:
  - name: ai_employee_db
    databaseName: ai_employee
    user: ai_employee
```

### **Option 3: Docker + Cloud VM**

```dockerfile
# Dockerfile
FROM python:3.13-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .

CMD ["python", "orchestrator.py"]
```

```bash
# Deploy to any cloud VM (Oracle Cloud, AWS, DigitalOcean)
docker build -t ai-employee .
docker run -e DATABASE_URL=postgresql://... ai-employee
```

---

## 📝 **Using SQLModel in Your Code**

### **Example 1: Filesystem Watcher Integration**

```python
# watchers/filesystem_watcher.py

from database import Database, TaskCreate, Task, get_sqlite_url
from pathlib import Path

class FilesystemWatcher:
    def __init__(self, vault_path: str, watch_folder: str):
        self.vault_path = Path(vault_path)
        
        # Initialize database
        db_path = self.vault_path.parent / "database" / "tasks.db"
        self.db = Database(get_sqlite_url(str(db_path)))
        self.db.create_tables()
    
    def _process_new_file(self, source: Path):
        # Create task using SQLModel
        task_data = TaskCreate(
            id=f"file_{int(time.time())}_{source.name}",
            type="file_drop",
            source_file=str(source),
            priority=self._determine_priority(source),
            title=f"Process file: {source.name}",
            metadata={
                "original_name": source.name,
                "file_size": source.stat().st_size
            }
        )
        
        task = self.db.create_task(task_data)
        logger.info(f"Created task: {task.id}")
```

### **Example 2: Orchestrator Integration**

```python
# orchestrator.py

from database import Database, TaskUpdate, get_sqlite_url

class Orchestrator:
    def __init__(self, vault_path: Path):
        # Initialize from environment
        from dotenv import load_dotenv
        import os
        
        load_dotenv()
        
        database_url = os.getenv(
            "DATABASE_URL",
            get_sqlite_url("database/tasks.db")
        )
        
        self.db = Database(database_url)
        self.db.create_tables()
    
    def _process_action_file(self, file_path: Path):
        # Extract task_id from file
        task_id = self._extract_task_id(file_path)
        
        # Update task status
        updates = TaskUpdate(
            status="processing",
            assigned_skill="file-processor"
        )
        task = self.db.update_task(task_id, updates)
        
        logger.info(f"Processing task: {task.id}")
```

### **Example 3: Dashboard Stats**

```python
# dashboard_updater.py

from database import Database

def update_dashboard(db: Database, dashboard_path: Path):
    # Get stats
    stats = db.get_dashboard_stats()
    
    # Update Dashboard.md
    content = f"""
# Dashboard

## Queue Status
| Queue | Count |
|-------|-------|
| Pending | {stats.queue['pending']} |
| Processing | {stats.queue['processing']} |
| Done | {stats.queue['done']} |

## Today's Activity
- Completions: {stats.today_completions}
- Avg Execution Time: {stats.avg_execution_time_ms}ms
- Failures: {stats.today_failures}
"""
    
    dashboard_path.write_text(content)
```

---

## 🎯 **Best Practices**

### **1. Use Environment Variables**

```python
# ✅ Good
from dotenv import load_dotenv
import os

load_dotenv()
db = Database(os.getenv("DATABASE_URL"))

# ❌ Bad - hardcoded
db = Database("sqlite:///database/tasks.db")
```

### **2. Always Use Context Managers**

```python
# ✅ Good
with db.get_session() as session:
    session.add(task)
    session.commit()

# ❌ Bad - manual commit/rollback
session = Session(db.engine)
session.add(task)
session.commit()
```

### **3. Use Pydantic Models for Validation**

```python
# ✅ Good - validated
task_data = TaskCreate(
    id="task_123",
    type="file_drop",  # Validated: must be string
    source_file="/path"
)

# ❌ Bad - no validation
task_data = {
    "id": "task_123",
    "type": 123,  # Wrong type, no error!
}
```

### **4. Handle Errors Gracefully**

```python
# ✅ Good
try:
    task = db.get_task("task_123")
    if not task:
        logger.warning(f"Task not found: task_123")
        return
except Exception as e:
    logger.error(f"Database error: {e}")
    raise
```

---

## 📚 **Resources**

- **SQLModel Docs:** https://sqlmodel.tiangolo.com/
- **SQLAlchemy Docs:** https://docs.sqlalchemy.org/
- **Pydantic Docs:** https://docs.pydantic.dev/
- **PostgreSQL:** https://www.postgresql.org/docs/

---

## 🎉 **Summary**

### **What You Get with SQLModel:**

| Feature | Raw SQLite | SQLModel |
|---------|-----------|----------|
| Type Safety | ❌ | ✅ |
| Validation | ❌ | ✅ |
| Auto-serialization | ❌ | ✅ |
| Database Agnostic | ❌ | ✅ |
| IDE Support | ⚠️ | ✅ |
| Easy Refactoring | ❌ | ✅ |
| Cloud Ready | ⚠️ | ✅ |

### **Migration Path:**

1. ✅ Install SQLModel (`uv sync`)
2. ✅ Define models (`database/models.py`)
3. ✅ Use `Database` class instead of `TaskDatabase`
4. ✅ Change `DATABASE_URL` for production
5. ✅ Deploy to cloud (Railway, Render, etc.)

### **Next Steps:**

1. Run `uv sync` to install SQLModel
2. Test with SQLite locally
3. When ready, switch to PostgreSQL
4. Deploy to cloud with one environment variable change

---

*Built with ❤️ for the AI Employee project*
