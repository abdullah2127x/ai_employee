# ⚙️ Configuration Management Guide

**Using Pydantic Settings for Type-Safe Environment Variable Management**

---

## 🎯 **Why Pydantic Settings?**

### **Before (Manual env var loading):**

```python
# ❌ Scattered os.getenv() calls
from dotenv import load_dotenv
import os

load_dotenv()

VAULT_PATH = Path(os.getenv('VAULT_PATH', './vault'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///tasks.db')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Problems:
# - No type validation
# - No centralization
# - Hard to track what's configured
# - Default values scattered everywhere
```

---

### **After (Pydantic Settings):**

```python
# ✅ Centralized, type-safe configuration
from config import settings

# All settings in one place
print(settings.vault_path)      # Path object, validated
print(settings.database_url)    # String, validated format
print(settings.dry_run)         # Boolean, auto-converted
print(settings.log_level)       # Literal, validated options

# IDE autocomplete!
settings.  # ← Shows all available settings
```

**Benefits:**
- ✅ **Type safety** - Automatic conversion and validation
- ✅ **Centralized** - One source of truth
- ✅ **Validated** - Errors caught early
- ✅ **Documented** - All settings described
- ✅ **IDE support** - Full autocomplete

---

## 📦 **Installation**

Already installed! Dependencies updated:

```toml
# pyproject.toml
dependencies = [
    "pydantic>=2.5.0",
    "pydantic-settings>=2.0.0",  # New!
    "python-dotenv>=1.0.0",
]
```

```bash
uv sync
```

---

## 🚀 **Quick Start**

### **Step 1: Create/Edit `.env` File**

```bash
# .env
VAULT_PATH=./vault
DATABASE_URL=sqlite:///database/tasks.db
DRY_RUN=true
DEV_MODE=true
LOG_LEVEL=INFO
```

### **Step 2: Use Settings in Code**

```python
from config import settings

# Access settings
print(f"Vault: {settings.vault_path}")
print(f"Database: {settings.database_url}")
print(f"Mode: {'Dev' if settings.dev_mode else 'Prod'}")

# Validate for production
try:
    settings.validate_for_production()
except ValueError as e:
    print(f"Not production-ready: {e}")
```

### **Step 3: Run Your App**

```bash
# Settings automatically loaded from .env
uv run python orchestrator.py

# Or check current settings
uv run python config.py
```

---

## 📋 **Available Settings**

### **Core Settings**

| Setting | Env Var | Type | Default | Description |
|---------|---------|------|---------|-------------|
| `vault_path` | `VAULT_PATH` | `Path` | `./vault` | Path to Obsidian vault |
| `check_interval` | `CHECK_INTERVAL` | `int` | `60` | Watcher check interval (seconds) |

---

### **Security Settings**

| Setting | Env Var | Type | Default | Description |
|---------|---------|------|---------|-------------|
| `dry_run` | `DRY_RUN` | `bool` | `True` | Safe mode (no real actions) |
| `dev_mode` | `DEV_MODE` | `bool` | `True` | Development features |

---

### **Claude Code Settings**

| Setting | Env Var | Type | Default | Description |
|---------|---------|------|---------|-------------|
| `claude_model` | `CLAUDE_MODEL` | `Literal` | `claude-3-5-sonnet` | Model to use |
| `claude_timeout` | `CLAUDE_TIMEOUT` | `int` | `300` | Timeout (seconds) |

**Valid models:**
- `claude-3-5-sonnet`
- `claude-3-opus`
- `claude-3-sonnet`
- `claude-3-haiku`

---

### **Database Settings**

| Setting | Env Var | Type | Default | Description |
|---------|---------|------|---------|-------------|
| `database_url` | `DATABASE_URL` | `str` | `sqlite:///database/tasks.db` | Database URL |

**Valid formats:**
- SQLite: `sqlite:///path/to/db.db`
- PostgreSQL: `postgresql://user:pass@host:port/db`
- MySQL: `mysql://user:pass@host:port/db`

---

### **Email Settings (Optional)**

| Setting | Env Var | Type | Default | Description |
|---------|---------|------|---------|-------------|
| `gmail_address` | `GMAIL_ADDRESS` | `str` | `None` | Gmail address |
| `gmail_app_password` | `GMAIL_APP_PASSWORD` | `str` | `None` | Gmail app password |

---

### **Logging Settings**

| Setting | Env Var | Type | Default | Description |
|---------|---------|------|---------|-------------|
| `log_level` | `LOG_LEVEL` | `Literal` | `INFO` | Logging level |
| `log_dir` | `LOG_DIR` | `Path` | `./logs` | Log directory |

**Valid log levels:**
- `DEBUG`
- `INFO`
- `WARNING`
- `ERROR`
- `CRITICAL`

---

## 🔧 **Usage Examples**

### **Example 1: Basic Usage**

```python
from config import settings

# Simple access
vault = settings.vault_path
db_url = settings.database_url

# Use in your code
from database import Database

db = Database(settings.database_url)
db.create_tables()
```

---

### **Example 2: Conditional Logic**

```python
from config import settings

if settings.is_development:
    print("Running in development mode")
    settings.dry_run = True
else:
    print("Running in production mode")
    settings.validate_for_production()

if settings.is_sqlite:
    print("Using SQLite (local development)")
elif settings.is_postgresql:
    print("Using PostgreSQL (production)")
```

---

### **Example 3: Validation**

```python
from config import settings

# Check if ready for production
try:
    settings.validate_for_production()
    print("✅ Ready for production!")
except ValueError as e:
    print(f"❌ Not ready:\n{e}")
    # Fix issues before deploying
```

---

### **Example 4: Settings Summary**

```python
from config import settings

# Print safe summary (no secrets)
print(settings.summary())

# Output:
# Settings Summary:
#   Vault Path: ./vault
#   Database: SQLite
#   Mode: Development
#   Dry Run: True
#   Claude Model: claude-3-5-sonnet
#   Log Level: INFO
#   Gmail: Not configured
```

---

### **Example 5: Orchestrator Integration**

```python
# orchestrator.py
from config import settings, get_settings

class Orchestrator:
    def __init__(self, vault_path=None):
        # Use settings.vault_path if not provided
        self.vault_path = vault_path or settings.vault_path
        
        # Initialize database with settings
        from database import Database
        self.db = Database(settings.database_url)
        
        # Setup logging with settings
        from logging_utils import setup_logging
        self.logger = setup_logging(settings.log_dir)
        
        # Log configuration
        self.logger.info(f"Starting with config: {settings.summary()}")
```

---

## 🌐 **Environment-Specific Configurations**

### **Development (.env.local)**

```bash
# .env.local
VAULT_PATH=./vault
DATABASE_URL=sqlite:///database/tasks.db
DRY_RUN=true
DEV_MODE=true
LOG_LEVEL=DEBUG
CLAUDE_MODEL=claude-3-5-sonnet
CLAUDE_TIMEOUT=300
```

---

### **Production (.env.production)**

```bash
# .env.production
VAULT_PATH=/app/vault
DATABASE_URL=postgresql://user:pass@db.host.com:5432/ai_employee
DRY_RUN=false
DEV_MODE=false
LOG_LEVEL=INFO
CLAUDE_MODEL=claude-3-5-sonnet
CLAUDE_TIMEOUT=120
```

---

### **Cloud Deployment (Railway, Render, etc.)**

```bash
# Set in cloud provider's environment variables
VAULT_PATH=/app/vault
DATABASE_URL=postgresql://user:pass@db.railway.app:5432/railway
DRY_RUN=false
DEV_MODE=false
LOG_LEVEL=INFO

# Cloud providers automatically set these
# No .env file needed!
```

---

## 🎯 **Best Practices**

### **✅ DO:**

```python
# 1. Import settings at module level
from config import settings

# 2. Use settings throughout your code
db = Database(settings.database_url)

# 3. Validate for production before deploy
settings.validate_for_production()

# 4. Use helper properties
if settings.is_development:
    enable_debug_features()

# 5. Log settings summary (safe)
logger.info(f"Config: {settings.summary()}")
```

---

### **❌ DON'T:**

```python
# 1. Don't use os.getenv() directly
import os
db_url = os.getenv("DATABASE_URL")  # ❌

# 2. Don't create multiple Settings instances
settings1 = Settings()
settings2 = Settings()  # ❌

# Use the singleton instead:
from config import settings  # ✅

# 3. Don't log sensitive values
print(f"DB URL: {settings.database_url}")  # ❌ May contain passwords

# 4. Don't modify settings at runtime
settings.dry_run = False  # ❌ (unless testing)
```

---

## 🧪 **Testing**

### **Test with Different Configurations**

```python
# test_config.py
from config import Settings, reload_settings
import os

def test_sqlite_config():
    os.environ["DATABASE_URL"] = "sqlite:///test.db"
    settings = reload_settings()
    assert settings.is_sqlite
    assert settings.is_development

def test_postgresql_config():
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/test"
    settings = reload_settings()
    assert settings.is_postgresql

def test_production_validation():
    os.environ["DRY_RUN"] = "false"
    os.environ["DEV_MODE"] = "false"
    os.environ["DATABASE_URL"] = "postgresql://user:pass@localhost/test"
    settings = reload_settings()
    
    try:
        settings.validate_for_production()
        print("✅ Valid for production")
    except ValueError as e:
        print(f"❌ {e}")
```

---

## 📊 **Migration Guide**

### **From Manual `os.getenv()` to Pydantic Settings**

#### **Before:**

```python
# ❌ Old way
from dotenv import load_dotenv
import os

load_dotenv()

VAULT_PATH = Path(os.getenv('VAULT_PATH', './vault'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///tasks.db')
LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')

# Use throughout code
db = Database(DATABASE_URL)
```

#### **After:**

```python
# ✅ New way
from config import settings

# Use throughout code
db = Database(settings.database_url)

# Access any setting
vault = settings.vault_path
log_level = settings.log_level
```

---

## 🔍 **Troubleshooting**

### **Issue: Settings not loading from .env**

**Solution:**
```bash
# Ensure .env file exists in project root
ls -la .env

# Check file encoding (should be UTF-8)
file .env

# Validate .env format (KEY=VALUE, no spaces around =)
cat .env
```

---

### **Issue: Type validation errors**

**Solution:**
```bash
# Check .env values match expected types
# Boolean: true/false (not True/False or 1/0)
DRY_RUN=true  # ✅
DRY_RUN=True  # ❌

# Path: string (will be converted to Path)
VAULT_PATH=./vault  # ✅

# Integer: numeric string
CHECK_INTERVAL=60  # ✅
```

---

### **Issue: Database URL validation fails**

**Solution:**
```bash
# Ensure URL starts with supported prefix
DATABASE_URL=sqlite:///database/tasks.db  # ✅
DATABASE_URL=postgresql://user:pass@host/db  # ✅
DATABASE_URL=mysql://user:pass@host/db  # ✅
DATABASE_URL=postgres://...  # ❌ (use postgresql://)
```

---

## 📚 **Resources**

- **Pydantic Settings Docs:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **Pydantic Docs:** https://docs.pydantic.dev/
- **12-Factor App Config:** https://12factor.net/config

---

## 🎉 **Summary**

### **What Changed:**

| Aspect | Before | After |
|--------|--------|-------|
| **Method** | `os.getenv()` | Pydantic Settings |
| **Type Safety** | ❌ Manual conversion | ✅ Automatic |
| **Validation** | ❌ Runtime errors | ✅ Startup validation |
| **Centralization** | ❌ Scattered | ✅ One source |
| **IDE Support** | ⚠️ Basic | ✅ Full autocomplete |
| **Documentation** | ❌ Comments | ✅ Type hints + descriptions |

---

### **Key Files:**

- `config.py` - Settings definition (single source of truth)
- `.env` - Environment variables (local configuration)
- `config.py` can be run directly: `uv run python config.py`

---

### **Quick Reference:**

```python
# Import
from config import settings, get_settings

# Access
settings.vault_path
settings.database_url
settings.is_development

# Validate
settings.validate_for_production()

# Summary
print(settings.summary())
```

---

*Configuration management done right! 🎉*
