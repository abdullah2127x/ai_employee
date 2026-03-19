# AI Employee - Project Rules & Architecture Decisions

**Last Updated:** 2026-03-19  
**Version:** 1.0

---

## 📋 Overview

This document contains **mandatory rules** and **architectural decisions** that must be followed by all AI assistants and developers working on this project. These rules ensure consistency, maintainability, and alignment with the project's vision.

---

## 🏗️ Core Architecture Principles

### **1. File-Based System (NO DATABASE)**

✅ **DO:**
- Use file-based tracking for all operations
- Store task metadata in markdown files (`Needs_Action/*.md`)
- Use hash registry (`.hash_registry.json`) for deduplication
- Log all operations to markdown files in `Logs/`

❌ **DON'T:**
- Use databases (SQLite, PostgreSQL, etc.)
- Import or use `database/` module
- Create SQL models or ORM layers
- Store state in database tables

**Why:** The entire system is 100% file-based for simplicity and portability.

---

### **2. Centralized Configuration**

✅ **DO:**
- Get ALL paths from `core.config.settings`
- Use `settings.vault_path` as the base for all vault paths
- Use computed properties like `settings.logs_dir`, `settings.drop_folder_path`
- Read configuration from `.env` file via Pydantic Settings

❌ **DON'T:**
- Hardcode paths in code
- Create manual path construction (`vault_path / "Something"`)
- Add new config variables without adding to `core/config.py` first
- Store configuration in multiple places

**Example:**
```python
# ✅ CORRECT:
from core.config import settings
vault_path = settings.vault_path
logs_dir = settings.logs_dir  # Auto: vault_path / "Logs"
drop_folder = settings.drop_folder_path  # Auto: vault_path / "Inbox" / "Drop"

# ❌ WRONG:
vault_path = Path("./vault")
logs_dir = Path("./Logs")  # Don't hardcode!
```

---

### **3. Logging System**

✅ **DO:**
- Use `utils.logging_manager.LoggingManager` for ALL logging
- Import from `utils.logging_manager` (not root directory)
- Pass `log_level` as parameter to control verbosity
- Let settings control console output (`settings.dev_mode`)

❌ **DON'T:**
- Create new logging instances everywhere
- Use Python's standard `logging` module for business logs
- Import from `logging_utils` (deleted)
- Create log files manually

**Example:**
```python
# ✅ CORRECT:
from utils.logging_manager import LoggingManager
logger = LoggingManager(log_level="WARNING")  # Pass level as parameter
logger.write_to_timeline("Task completed", actor="orchestrator")
logger.log_error("Error occurred", error=e, actor="component")

# ❌ WRONG:
import logging
logger = logging.getLogger(__name__)  # Don't use standard logging!
logger.error("Error")
```

---

### **4. Path Management**

✅ **DO:**
- Use computed path properties from `settings`
- All paths derive from `vault_path`
- Call `settings.ensure_vault_directories()` on startup
- Store logs in `vault_path / "Logs"`

❌ **DON'T:**
- Create paths manually
- Use relative paths without base
- Create directories manually (use `ensure_vault_directories()`)

**Path Hierarchy:**
```
vault_path (from settings.vault_path)
├── Inbox/
│   ├── Drop/ (settings.drop_folder_path)
│   └── Drop_History/ (settings.drop_history_path)
├── Needs_Action/ (settings.needs_action_path)
├── Processing/ (settings.processing_path)
├── Done/ (settings.done_path)
├── Plans/ (settings.plans_path)
├── Pending_Approval/ (settings.pending_approval_path)
├── Approved/ (settings.approved_path)
├── In_Progress/ (settings.in_progress_path)
└── Logs/ (settings.logs_dir) ← Auto-created
```

---

### **5. Environment Variables**

✅ **DO:**
- Define all env variables in `core/config.py` using Pydantic Fields
- Document in `.env.example`
- Use `.env` for local configuration
- Keep `.env.example` in sync with actual usage

❌ **DON'T:**
- Use `os.environ.get()` directly
- Add env variables without adding to `Settings` class
- Store secrets in code
- Commit `.env` file (it's in `.gitignore`)

**Current Variables:**
```bash
VAULT_PATH=./vault
CHECK_INTERVAL=60
DRY_RUN=true
DEV_MODE=true
CLAUDE_MODEL=claude-3-5-sonnet
CLAUDE_TIMEOUT=300
LOGS_PER_TASK_ENABLED=true
GMAIL_ADDRESS=your.email@gmail.com (optional)
GMAIL_APP_PASSWORD=your-password (optional)
```

---

## 📁 Project Structure Rules

### **Directory Organization**

```
project_root/
├── core/              ← Core configuration (config.py)
├── utils/             ← Utilities (logging_manager.py)
├── watchers/          ← File watchers (filesystem_watcher.py)
├── vault/             ← Obsidian vault (auto-created)
│   ├── Inbox/
│   │   ├── Drop/
│   │   └── Drop_History/
│   ├── Needs_Action/
│   ├── Processing/
│   ├── Done/
│   └── Logs/
├── .env               ← Local configuration (DO NOT COMMIT)
├── .env.example       ← Template (COMMIT THIS)
└── README.md          ← Main documentation
```

### **File Naming Conventions**

✅ **DO:**
- Use lowercase with underscores: `filesystem_watcher.py`
- Use `.md` for markdown files
- Prefix test files with `test_`: `test_logging_manager.py`
- Use templates in `templates/` directory

❌ **DON'T:**
- Use camelCase: `filesystemWatcher.py` ❌
- Use spaces in filenames
- Create files in root without good reason

---

## 🔧 Component Rules

### **Filesystem Watcher**

✅ **DO:**
- Use `FilesystemWatcher()` with no parameters (uses settings)
- Let it auto-create directories
- Use hash-based deduplication
- Move processed files to `Drop_History/`
- Create metadata in `Needs_Action/`

❌ **DON'T:**
- Pass paths to constructor
- Create duplicate detection logic
- Delete files from Drop (move to history)

**Example:**
```python
# ✅ CORRECT:
from watchers.filesystem_watcher import FilesystemWatcher
watcher = FilesystemWatcher()  # No parameters!
watcher.start()

# ❌ WRONG:
watcher = FilesystemWatcher(vault_path, drop_folder)  # Don't pass paths!
```

---

### **Orchestrator**

✅ **DO:**
- Use `LoggingManager` for all logging
- Get paths from `settings`
- Process files from `Needs_Action/`
- Move completed tasks to `Done/`

❌ **DON'T:**
- Use database for task tracking
- Create custom logging
- Hardcode paths

---

### **Logging**

✅ **DO:**
- Use `LoggingManager` with appropriate log level
- Write business events to timeline
- Write task details to task logs
- Log errors with stack traces to error files

❌ **DON'T:**
- Use `print()` for logging
- Create log files manually
- Mix logging systems

**Log Levels:**
- `DEBUG` - Development debugging (verbose)
- `INFO` - Normal operations
- `WARNING` - Warnings that need attention
- `ERROR` - Errors with stack traces
- `CRITICAL` - System-breaking errors

---

## 🚫 Deprecated Patterns (NEVER USE)

### **1. Database Usage** ❌

```python
# ❌ DELETED - DON'T USE:
from database import TaskDatabase
db = TaskDatabase("database/tasks.db")
db.create_task(...)
```

### **2. Manual Path Construction** ❌

```python
# ❌ WRONG - DON'T DO:
needs_action = Path("./vault/Needs_Action")
logs_dir = Path("./Logs")

# ✅ CORRECT - DO THIS:
from core.config import settings
needs_action = settings.needs_action_path
logs_dir = settings.logs_dir
```

### **3. Standard Python Logging** ❌

```python
# ❌ WRONG - DON'T DO:
import logging
logger = logging.getLogger(__name__)
logger.error("Error")

# ✅ CORRECT - DO THIS:
from utils.logging_manager import LoggingManager
logger = LoggingManager(log_level="WARNING")
logger.log_error("Error", error=e)
```

### **4. Hardcoded Configuration** ❌

```python
# ❌ WRONG - DON'T DO:
vault_path = Path("./vault")
dev_mode = True

# ✅ CORRECT - DO THIS:
from core.config import settings
vault_path = settings.vault_path
dev_mode = settings.dev_mode
```

---

## 📝 Code Style Rules

### **Imports**

```python
# Order of imports:
1. Standard library (os, sys, pathlib)
2. Third-party (watchdog, pydantic)
3. Local imports (core.config, utils.logging_manager)
4. Relative imports (.models, ..watchers)
```

### **Error Handling**

```python
# ✅ CORRECT:
try:
    process_file()
except Exception as e:
    logger.log_error("Failed to process file", error=e, actor="processor")
    raise  # Re-raise if critical

# ❌ WRONG:
try:
    process_file()
except:
    print("Error occurred")  # Don't use print!
    pass  # Don't swallow errors!
```

### **Type Hints**

```python
# ✅ DO use type hints:
def process_file(file_path: Path, force: bool = False) -> bool:
    ...

# ❌ DON'T skip type hints:
def process_file(file_path, force=False):
    ...
```

---

## 🔐 Security Rules

### **Secrets Management**

✅ **DO:**
- Store secrets in `.env` (gitignored)
- Use environment variables for production
- Rotate passwords regularly
- Use app passwords for Gmail

❌ **DON'T:**
- Commit `.env` file
- Hardcode passwords in code
- Log sensitive information
- Store credentials in vault

### **File Permissions**

✅ **DO:**
- Set appropriate file permissions
- Keep vault private
- Use secure file handling

---

## 🧪 Testing Rules

✅ **DO:**
- Put tests in `tests/` directory
- Prefix test files with `test_`
- Test with real file operations
- Clean up test files after tests

❌ **DON'T:**
- Test in production vault
- Leave test files behind
- Test without cleanup

---

## 📚 Documentation Rules

✅ **DO:**
- Update this file when making architectural changes
- Keep `.env.example` in sync with `core/config.py`
- Document new environment variables
- Add docstrings to public methods

❌ **DON'T:**
- Create summary files (they get deleted)
- Leave outdated documentation
- Document unused features

---

## 🎯 Quick Reference

### **Always Use:**

```python
from core.config import settings
from utils.logging_manager import LoggingManager
from watchers.filesystem_watcher import FilesystemWatcher

# Configuration
vault = settings.vault_path
logs = settings.logs_dir
drop = settings.drop_folder_path

# Logging
logger = LoggingManager(log_level="WARNING")

# Watcher
watcher = FilesystemWatcher()
```

### **Never Use:**

```python
# ❌ Database
from database import TaskDatabase

# ❌ Manual paths
Path("./vault/Needs_Action")

# ❌ Standard logging
import logging

# ❌ Hardcoded config
VAULT_PATH = "./vault"
```

---

## 📖 For AI Assistants

When helping with this project:

1. **READ THIS FILE FIRST** - Understand the architecture
2. **Check `core/config.py`** - See what settings exist
3. **Use existing patterns** - Don't introduce new patterns
4. **Keep it simple** - File-based, no database
5. **Test changes** - Verify nothing breaks

**Remember:** This is a **file-based**, **vault-centric** system with **centralized configuration** and **unified logging**. Everything derives from `vault_path` and all logging goes through `LoggingManager`.

---

**End of Rules Document**

*If you need to change any of these rules, update this file first and explain why.*
