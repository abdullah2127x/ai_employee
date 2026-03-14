# 🗄️ Database Summary: SQLite → SQLModel → Cloud

**Quick Answer:** We've added **SQLModel** (ORM) to make switching from SQLite to PostgreSQL/MySQL as easy as changing one environment variable.

---

## 📊 **What Database Are We Using?**

### **Current (Development):** 
✅ **SQLite** - File-based, serverless, perfect for local development

```bash
# Database file location
database/tasks.db

# Connection URL (in .env)
DATABASE_URL=sqlite:///database/tasks.db
```

### **Production (Future):**
🔄 **PostgreSQL** or **MySQL** - Full client-server database

```bash
# PostgreSQL URL (in .env)
DATABASE_URL=postgresql://user:pass@localhost:5432/ai_employee

# Or cloud PostgreSQL (Railway, Render, etc.)
DATABASE_URL=postgresql://user:pass@db.railway.app:5432/railway
```

---

## 🔗 **What is SQLModel and Why Do We Need It?**

### **Before (Raw SQLite - Old Code):**

```python
# ❌ Manual SQL queries
conn.execute("""
    INSERT INTO tasks (id, type, status, metadata)
    VALUES (?, ?, ?, ?)
""", (task_id, "file_drop", "pending", json.dumps(metadata)))

# ❌ Manual dict conversion
cursor = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
task = dict(cursor.fetchone())
```

**Problems:**
- No type safety
- Manual JSON serialization
- Hard to switch databases
- SQL injection risks

---

### **After (SQLModel - New Code):**

```python
# ✅ Define models once
from database import Task, Database

class Task(SQLModel, table=True):
    id: str = Field(primary_key=True)
    type: str
    status: str = "pending"
    task_data: dict = Field(sa_column=Column("task_data", JSON))

# ✅ Simple CRUD
db = Database("sqlite:///tasks.db")
db.create_tables()

task = Task(id="task_1", type="file_drop", status="pending")
with db.get_session() as session:
    session.add(task)
    session.commit()

# ✅ Query with type safety
from sqlmodel import select
statement = select(Task).where(Task.id == "task_1")
task = session.exec(statement).first()
```

**Benefits:**
- ✅ Type safety (IDE autocomplete!)
- ✅ Auto-serialization (JSON, datetime)
- ✅ **Switch databases by changing URL** (SQLite → PostgreSQL)
- ✅ Validation (Pydantic)
- ✅ No SQL injection

---

## 🚀 **How to Use SQLModel (Quick Start)**

### **Step 1: Install**

Already done! Dependencies added:
```bash
uv sync
```

### **Step 2: Initialize Database**

```python
from database import Database, get_sqlite_url

# For local development (SQLite)
db = Database(get_sqlite_url("database/tasks.db"))
db.create_tables()  # Creates tables automatically
```

### **Step 3: CRUD Operations**

```python
from database import TaskCreate, TaskUpdate

# CREATE
task_data = TaskCreate(
    id="file_001",
    type="file_drop",
    source_file="vault/Inbox/Drop/test.txt",
    priority="high",
    task_data={"size": 1024}
)
task = db.create_task(task_data)

# READ
task = db.get_task("file_001")

# UPDATE
updates = TaskUpdate(status="processing")
task = db.update_task("file_001", updates)

# DELETE
db.delete_task("file_001")

# Dashboard stats
stats = db.get_dashboard_stats()
```

---

## 🌐 **Switching from SQLite to PostgreSQL**

### **Scenario 1: Local Development (SQLite)**

```bash
# .env
DATABASE_URL=sqlite:///database/tasks.db
```

```python
# Code (no changes needed!)
from database import Database
import os

db = Database(os.getenv("DATABASE_URL"))
db.create_tables()
```

---

### **Scenario 2: Production (PostgreSQL)**

```bash
# .env
DATABASE_URL=postgresql://user:password@localhost:5432/ai_employee
```

```python
# Code (STILL no changes!)
from database import Database
import os

db = Database(os.getenv("DATABASE_URL"))
db.create_tables()
```

**That's it!** Zero code changes. Just change the `DATABASE_URL`.

---

### **Scenario 3: Cloud Deployment (Railway, Render, etc.)**

```bash
# Railway.app automatically provides DATABASE_URL
# Just set it in your environment
DATABASE_URL=postgresql://user:pass@db.railway.app:5432/railway
```

```python
# Code (STILL no changes!)
from database import Database
import os

db = Database(os.getenv("DATABASE_URL"))  # Reads from environment
db.create_tables()
```

---

## ☁️ **Cloud Deployment Options**

### **Option 1: Railway.app (Easiest - Free Tier)**

```bash
# 1. Install Railway CLI
npm install -g @railway/cli

# 2. Login
railway login

# 3. Create project
railway init

# 4. Add PostgreSQL database
railway add postgresql

# 5. Deploy
railway up
```

**What Railway does:**
- ✅ Provisions PostgreSQL automatically
- ✅ Sets `DATABASE_URL` environment variable
- ✅ Deploys your code
- ✅ Manages backups, updates, scaling

**Cost:** Free tier available ($5/month credit)

---

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
```

**Cost:** Free tier available

---

### **Option 3: Oracle Cloud Free Tier**

```bash
# 1. Create free VM (Always Free tier)
# 2. Install PostgreSQL
sudo apt install postgresql

# 3. Create database
sudo -u postgres psql
CREATE DATABASE ai_employee;

# 4. Get connection string
# postgresql://user:pass@your-vm-ip:5432/ai_employee

# 5. Set in .env
DATABASE_URL=postgresql://user:pass@vm-ip:5432/ai_employee
```

**Cost:** FREE (Always Free tier)

---

## 📝 **Migration Path**

### **Current State (SQLite):**

```bash
# Your code uses
database/tasks.db  # SQLite file
```

### **Step 1: Test with SQLModel Locally**

```bash
# Already done! SQLModel is installed
uv sync

# Test it
uv run python test_sqlmodel.py
```

### **Step 2: Deploy with SQLite (Quick)**

```bash
# Deploy to Railway/Render with SQLite
# Just upload your code + database file
# Works for small-scale testing
```

### **Step 3: Migrate to PostgreSQL (When Ready)**

```bash
# 1. Set up PostgreSQL (local or cloud)
# 2. Change DATABASE_URL in environment
DATABASE_URL=postgresql://user:pass@host:5432/dbname

# 3. Run migrations (create tables)
python -c "from database import Database; import os; db = Database(os.getenv('DATABASE_URL')); db.create_tables()"

# 4. Deploy!
```

---

## 🎯 **Key Files Created**

| File | Purpose |
|------|---------|
| `database/models.py` | SQLModel model definitions |
| `database/db_engine.py` | Database engine and CRUD operations |
| `database/__init__.py` | Module exports |
| `test_sqlmodel.py` | Test suite for SQLModel |
| `SQLMODEL_GUIDE.md` | Detailed documentation |
| `DATABASE_SUMMARY.md` | This file |

---

## 📊 **Comparison Table**

| Feature | Raw SQLite (Old) | SQLModel (New) |
|---------|-----------------|----------------|
| Type Safety | ❌ | ✅ |
| Validation | ❌ | ✅ |
| Auto-Serialization | ❌ | ✅ |
| Database Switching | ❌ (Rewrite needed) | ✅ (Change URL) |
| IDE Support | ⚠️ | ✅ (Full autocomplete) |
| Cloud Ready | ⚠️ | ✅ |
| Learning Curve | Low | Medium |

---

## 🎓 **What You Need to Remember**

### **For Local Development:**

```bash
# 1. Use SQLite (already set up)
DATABASE_URL=sqlite:///database/tasks.db

# 2. Run your code
uv run python orchestrator.py

# That's it!
```

### **For Production:**

```bash
# 1. Set up PostgreSQL (Railway, Render, Oracle Cloud, etc.)

# 2. Change one environment variable
DATABASE_URL=postgresql://user:pass@host:port/dbname

# 3. Deploy
# Zero code changes needed!
```

---

## 🔧 **Next Steps**

1. ✅ **SQLModel installed** - Done!
2. 🔄 **Update orchestrator.py** - Replace `TaskDatabase` with `Database`
3. 🧪 **Test locally** - Run `uv run python test_sqlmodel.py`
4. 🚀 **Deploy to cloud** - Railway/Render/Oracle Cloud
5. 📊 **Monitor and scale** - PostgreSQL handles growth

---

## 📚 **Resources**

- **SQLModel Tutorial:** https://sqlmodel.tiangolo.com/tutorial/
- **Railway Deploy:** https://docs.railway.app/
- **PostgreSQL:** https://www.postgresql.org/docs/
- **SQLAlchemy Docs:** https://docs.sqlalchemy.org/

---

## 🎉 **Summary**

**Question:** Which database are we using?

**Answer:** 
- **Now:** SQLite (local file, perfect for development)
- **Production:** PostgreSQL or MySQL (just change `DATABASE_URL`)
- **Magic:** SQLModel ORM makes it database-agnostic

**Key Benefit:** Switch from SQLite to PostgreSQL to MySQL by changing **ONE environment variable**. No code changes needed!

---

*Built for the AI Employee project - Ready for cloud deployment!* 🚀
