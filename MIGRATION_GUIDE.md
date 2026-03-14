# 🔄 Configuration Migration Guide

**Date:** 2026-03-14
**Status:** ✅ **MIGRATION COMPLETE**

---

## 📁 **What Changed**

### **Old Structure:**
```
GeneralAgentWithCursor/
├── config.py              ❌ Root level
├── config.json            ❌ JSON config (deprecated)
├── config.example.json    ❌ JSON template (deprecated)
└── .env                   ✅ Environment variables
```

### **New Structure:**
```
GeneralAgentWithCursor/
├── core/
│   ├── __init__.py        ✅ Core module
│   └── config.py          ✅ Configuration (moved here)
├── .env                   ✅ Environment variables
├── config.py              ⚠️ Deprecated (shows migration error)
├── config.json            ⚠️ Deprecated (will be removed)
└── config.example.json    ⚠️ Deprecated (will be removed)
```

---

## ✅ **Migration Actions Completed**

### **1. Created `core/` Module**

```
core/
├── __init__.py            # Exports settings
└── config.py              # Pydantic Settings definition
```

**Purpose:**
- Centralizes all configuration in one module
- Makes it clear that `config.py` is core infrastructure
- Prevents namespace conflicts

---

### **2. Updated Imports**

**Files Updated:**

| File | Old Import | New Import |
|------|-----------|------------|
| `orchestrator.py` | `from config import settings` | `from core import settings` |
| `database/db_engine.py` | `from config import settings` | `from core import settings` |
| `test_config.py` | `from config import settings` | `from core import settings` |

---

### **3. Deprecated Old Files**

**`config.py` (root level):**
```python
# Now shows helpful error message:
raise ImportError(
    "config.py has been moved to core/config.py. "
    "Please update your import: 'from core import settings'"
)
```

**`config.json` and `config.example.json`:**
```json
# Now contain deprecation notice
# Will be deleted in next major version
```

---

## 🎯 **How to Update Your Code**

### **If You Have Existing Code:**

```python
# ❌ OLD - Will show deprecation warning/error
from config import settings

# ✅ NEW - Correct import
from core import settings

# Or explicitly:
from core.config import Settings, settings, get_settings
```

---

### **If You're Starting Fresh:**

```python
# Just use the new import
from core import settings

# Access any setting
vault = settings.vault_path
db_url = settings.database_url
log_level = settings.log_level
```

---

## 📋 **Available Settings**

All settings are defined in `core/config.py`:

```python
from core import settings

# Core
settings.vault_path          # Path to Obsidian vault
settings.check_interval      # Watcher interval (seconds)

# Security
settings.dry_run             # Safe mode
settings.dev_mode            # Development features

# Claude Code
settings.claude_model        # Model name
settings.claude_timeout      # Timeout (seconds)

# Database
settings.database_url        # Database URL
settings.is_sqlite           # True if SQLite
settings.is_postgresql       # True if PostgreSQL

# Logging
settings.log_level           # Log level
settings.log_dir             # Log directory

# Email (optional)
settings.gmail_address       # Gmail address
settings.gmail_app_password  # Gmail password
```

---

## 🧪 **Testing the Migration**

### **Test 1: Import Settings**

```bash
# Run this to test configuration
uv run python -c "from core import settings; print(settings.summary())"
```

**Expected Output:**
```
Settings Summary:
  Vault Path: vault
  Database: SQLite
  Mode: Development
  Dry Run: True
  Claude Model: claude-3-5-sonnet
  Log Level: INFO
  Gmail: Not configured
```

---

### **Test 2: Run Configuration Test**

```bash
uv run python test_config.py
```

**Expected:** All tests pass ✅

---

### **Test 3: Run Orchestrator**

```bash
uv run python orchestrator.py
```

**Expected:** Starts without import errors ✅

---

## 🚨 **Common Issues**

### **Issue 1: ImportError from config.py**

**Error:**
```
ImportError: config.py has been moved to core/config.py
```

**Solution:**
```python
# Update your import
from core import settings  # ✅
```

---

### **Issue 2: ModuleNotFoundError: core**

**Error:**
```
ModuleNotFoundError: No module named 'core'
```

**Solution:**
```bash
# Ensure you're running from project root
cd GeneralAgentWithCursor

# Or add project root to PYTHONPATH
export PYTHONPATH=/path/to/GeneralAgentWithCursor
```

---

### **Issue 3: Settings Not Loading**

**Error:**
```
ValidationError: 1 validation error for Settings
```

**Solution:**
```bash
# Check your .env file exists
ls -la .env

# Validate .env format
cat .env

# Test configuration
uv run python test_config.py
```

---

## 📚 **Documentation Updates**

### **Updated Files:**

| File | Status | Changes |
|------|--------|---------|
| `CONFIG_GUIDE.md` | ✅ Updated | References `core.config` |
| `ENV_MANAGEMENT.md` | ✅ Updated | New import paths |
| `test_config.py` | ✅ Updated | Uses `from core import` |
| `orchestrator.py` | ✅ Updated | Uses `from core import` |
| `database/db_engine.py` | ✅ Updated | Uses `from core import` |

---

## 🎯 **Benefits of New Structure**

### **Before:**
```
❌ config.py in root (namespace pollution)
❌ config.json (deprecated, still around)
❌ Confusing for new developers
❌ No clear module structure
```

### **After:**
```
✅ core/ module (clear purpose)
✅ core/config.py (obvious what it does)
✅ Deprecated files marked for removal
✅ Clean module structure
✅ Easy to add more core utilities later
```

---

## 🗑️ **Files to Delete (Next Version)**

These files are deprecated and will be removed:

- [ ] `config.py` (root level) - currently shows migration error
- [ ] `config.json` - deprecated JSON config
- [ ] `config.example.json` - deprecated template

**Keep:**
- ✅ `core/config.py` - new configuration location
- ✅ `core/__init__.py` - module exports
- ✅ `.env` - environment variables

---

## 📝 **Summary**

### **What Changed:**
- Configuration moved from `config.py` → `core/config.py`
- All imports updated: `from config import` → `from core import`
- Old files deprecated with migration messages

### **What You Need to Do:**
- Update imports in your custom code
- Test your code with new structure
- Delete deprecated files when ready

### **Benefits:**
- ✅ Cleaner project structure
- ✅ Clear module organization
- ✅ Easy to extend with more core utilities
- ✅ No namespace conflicts

---

**Migration Status:** ✅ **COMPLETE**

**Next Steps:**
1. ✅ Test all existing functionality
2. ✅ Update any custom scripts
3. ⏳ Remove deprecated files in next major version

---

*For questions, see CONFIG_GUIDE.md or ENV_MANAGEMENT.md*
