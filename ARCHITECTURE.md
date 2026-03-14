# Project Structure Explained

**Date:** 2026-03-12
**Purpose:** Clarify the project architecture and package structure

---

## 📁 Current Structure

```
GeneralAgentWithCursor/
├── pyproject.toml              # ✅ Main (and only) project definition
├── .venv/                      # ✅ Single virtual environment
├── requirements.txt            # ✅ Dependencies (for pip users)
├── uv.lock                     # ✅ UV lock file
│
├── orchestrator.py             # Main application
├── database.py                 # Database module
├── logging_utils.py            # Logging utilities
│
├── database/                   # Python package
│   ├── __init__.py
│   └── database.py
│
├── watchers/                   # Python package (NOT a separate project)
│   ├── __init__.py
│   ├── base_watcher.py
│   ├── filesystem_watcher.py
│   └── gmail_watcher.py
│
├── skills/                     # Python package
│   ├── __init__.py
│   └── *.md
│
└── vault/                      # Obsidian vault (not Python code)
    └── ...
```

---

## ❓ Is `watchers/` a Separate UV Project?

### **Previous State (BEFORE cleanup):**
```
watchers/
├── pyproject.toml      ❌ Separate UV project definition
├── .python-version     ❌ Separate Python version
├── .gitignore
└── *.py
```

**Problem:** This created a **UV workspace** with two projects:
- `ai-employee` (parent)
- `watchers` (child workspace member)

This was **unnecessary complexity** because:
1. `watchers` wasn't being used as a separate package
2. It had no separate dependencies
3. It wasn't published to PyPI
4. It created confusion about which venv to use

---

### **Current State (AFTER cleanup):**
```
watchers/
├── __init__.py         ✅ Just a Python package
├── base_watcher.py
├── filesystem_watcher.py
└── gmail_watcher.py
```

**Solution:** `watchers/` is now **just a Python package** within the main project.

**Benefits:**
- ✅ Single `pyproject.toml` at project root
- ✅ Single `.venv` for everything
- ✅ Clear import structure: `from watchers import FilesystemWatcher`
- ✅ No workspace confusion
- ✅ Simpler dependency management

---

## 🔧 How Imports Work

### **Before (Workspace):**
```python
# Complex, ambiguous imports
import watchers  # From workspace member?

# Would need: uv sync --workspace
```

### **After (Simple Package):**
```python
# Clear, standard Python imports
from watchers import FilesystemWatcher
from watchers.filesystem_watcher import DropFolderHandler
from database import TaskDatabase

# Just works with: uv run python orchestrator.py
```

---

## 🎯 Why We Don't Need Separate UV Projects

### **When to Use UV Workspaces:**

✅ **Good use cases:**
- Multiple packages that need to be versioned separately
- Packages that will be published to PyPI independently
- Different teams working on different packages
- Packages with different dependency requirements

❌ **Not needed for:**
- Simple module organization (just use folders with `__init__.py`)
- Code that's always deployed together
- Projects with shared dependencies

### **Our Case:**

The AI Employee project is **a single application** with:
- One deployment unit (all code deploys together)
- Shared dependencies (all modules use same libs)
- No plans to publish `watchers` separately
- No separate teams

**Therefore:** Single project with multiple Python packages is the right choice.

---

## 📦 Python Package vs UV Project

### **Python Package:**
```
watchers/
├── __init__.py       # Makes it a package
└── module.py         # Code
```
- **Purpose:** Organize code within a project
- **Import:** `from watchers import module`
- **Dependencies:** Inherited from parent project
- **Version:** Same as parent project

### **UV Project:**
```
watchers/
├── pyproject.toml    # Project definition
├── src/watchers/     # Source code
└── tests/
```
- **Purpose:** Independent, versioned package
- **Install:** `uv add watchers` or `pip install watchers`
- **Dependencies:** Defined in own `pyproject.toml`
- **Version:** Independent (e.g., 1.0.0, 2.0.0)

---

## 🔍 Dependency Flow

```
┌─────────────────────────────────────────┐
│  pyproject.toml (root)                  │
│  dependencies: [watchdog, aiosqlite]    │
└─────────────────┬───────────────────────┘
                  │
                  ▼
┌─────────────────────────────────────────┐
│  .venv/                                  │
│  - watchdog installed                    │
│  - aiosqlite installed                   │
│  - all dependencies available            │
└─────────────────┬───────────────────────┘
                  │
                  ▼
        ┌─────────┴─────────┐
        │                   │
        ▼                   ▼
┌───────────────┐   ┌───────────────┐
│ watchers/     │   │ database/     │
│ (uses deps)   │   │ (uses deps)   │
│ ✅ watchdog   │   │ ✅ aiosqlite  │
└───────────────┘   └───────────────┘
```

**Key Point:** All packages (`watchers/`, `database/`, `skills/`) share the **same virtual environment** and **same dependencies**.

---

## 🚀 How to Use

### **Running the Application:**

```bash
# Activate virtual environment (optional with uv)
source .venv/bin/activate  # Or use uv run

# Run orchestrator
uv run python orchestrator.py --vault ./vault

# Run tests
uv run pytest
```

### **Importing Modules:**

```python
# From orchestrator.py or any module:

# Import from watchers package
from watchers import FilesystemWatcher
from watchers.filesystem_watcher import DropFolderHandler

# Import from database package
from database import TaskDatabase

# Import utilities
from logging_utils import setup_logging
```

### **No Special Configuration Needed:**

```bash
# ❌ DON'T need: uv sync --workspace
# ✅ DO: uv sync  (syncs all dependencies)

# ❌ DON'T need: separate venv for watchers
# ✅ DO: Use parent .venv
```

---

## 📝 Summary

| Aspect | Before | After |
|--------|--------|-------|
| **Project Structure** | UV Workspace | Single Project |
| **pyproject.toml** | 2 files | 1 file (root) |
| **Virtual Environment** | Potentially separate | Single `.venv` |
| **watchers/ Status** | Separate project | Python package |
| **Dependencies** | Defined in 2 places | Defined once |
| **Complexity** | Higher | Lower |
| **Import Clarity** | Ambiguous | Clear |

---

## ✅ Cleanup Actions Taken

1. **Removed:**
   - `watchers/pyproject.toml` ❌
   - `watchers/.python-version` ❌
   - `watchers/.gitignore` (replaced with simple version) ❌

2. **Updated:**
   - Parent `pyproject.toml` - removed workspace reference
   - `watchers/README.md` - clarified it's a package

3. **Kept:**
   - `watchers/__init__.py` - makes it a Python package
   - All `.py` files - actual code
   - Simple `.gitignore` - ignore build artifacts

---

## 🎯 Best Practices

### **For This Project:**

✅ **DO:**
- Keep all code in single project
- Use packages (`__init__.py`) for organization
- Define dependencies once in root `pyproject.toml`
- Use `uv run` for execution

❌ **DON'T:**
- Create separate `pyproject.toml` for subfolders
- Try to publish internal packages separately
- Over-engineer with workspaces unless necessary

### **When to Split:**

Consider separate projects **only if**:
- You need to version components independently
- Different deployment cycles
- External teams will use components separately
- Publishing to PyPI

---

## 🔗 References

- [UV Workspaces](https://docs.astral.sh/uv/concepts/workspaces/)
- [Python Packages](https://packaging.python.org/en/latest/glossary/#term-Package)
- [pyproject.toml](https://packaging.python.org/en/latest/specifications/pyproject-toml/)

---

*This document clarifies the project structure for new contributors.*
