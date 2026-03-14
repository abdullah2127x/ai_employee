# ⚙️ Environment Variable Management - Complete Guide

**Answer to: "How are you managing env variables?"**

---

## 🎯 **Current Approach: Pydantic Settings**

We're using **Pydantic Settings** - the modern, type-safe way to manage configuration in Python applications.

---

## 📊 **Comparison: Before vs After**

### **❌ Before (Manual Management):**

```python
# Scattered across multiple files
from dotenv import load_dotenv
import os

load_dotenv()

# In orchestrator.py
VAULT_PATH = Path(os.getenv('VAULT_PATH', './vault'))
DATABASE_URL = os.getenv('DATABASE_URL', 'sqlite:///tasks.db')

# In database/db_engine.py  
database_url = os.getenv('DATABASE_URL', 'sqlite:///database/tasks.db')

# In watchers/filesystem_watcher.py
check_interval = int(os.getenv('CHECK_INTERVAL', '60'))

# Problems:
# - No type validation (what if CHECK_INTERVAL="abc"?)
# - Defaults scattered everywhere
# - Hard to track what env vars exist
# - No IDE autocomplete
# - Manual type conversion (int, bool, Path)
```

---

### **✅ After (Pydantic Settings):**

```python
# config.py - Single source of truth
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    vault_path: Path = Path("./vault")
    database_url: str = "sqlite:///database/tasks.db"
    check_interval: int = 60
    dry_run: bool = True
    log_level: str = "INFO"

settings = Settings()
```

```python
# Any file - just import and use
from config import settings

vault = settings.vault_path       # ✅ Already a Path object
db_url = settings.database_url    # ✅ Validated string
interval = settings.check_interval # ✅ Already an int
dry_run = settings.dry_run        # ✅ Already a bool

# IDE autocomplete works!
settings.  # ← Shows all available settings
```

---

## 📁 **File Structure**

```
GeneralAgentWithCursor/
├── .env                    # Environment variables (gitignored)
├── .env.example           # Template for .env
├── config.py              # Pydantic Settings definition
├── test_config.py         # Configuration test script
│
├── orchestrator.py        # Uses: from config import settings
├── database/
│   └── db_engine.py       # Uses: settings.database_url
└── watchers/
    └── filesystem_watcher.py  # Uses: settings.check_interval
```

---

## 🔧 **How It Works**

### **Step 1: Define Settings (config.py)**

```python
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from pathlib import Path

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Core settings
    vault_path: Path = Field(default=Path("./vault"))
    check_interval: int = Field(default=60, ge=10, le=3600)
    
    # Security
    dry_run: bool = Field(default=True)
    dev_mode: bool = Field(default=True)
    
    # Database
    database_url: str = Field(default="sqlite:///database/tasks.db")
    
    @field_validator("database_url")
    @classmethod
    def validate_db_url(cls, v):
        if not v.startswith(("sqlite", "postgresql", "mysql")):
            raise ValueError("Must be sqlite, postgresql, or mysql")
        return v
    
    # Logging
    log_level: str = Field(default="INFO")

# Singleton instance
settings = Settings()
```

---

### **Step 2: Create .env File**

```bash
# .env
VAULT_PATH=./vault
DATABASE_URL=sqlite:///database/tasks.db
DRY_RUN=true
DEV_MODE=true
CHECK_INTERVAL=60
LOG_LEVEL=INFO
CLAUDE_MODEL=claude-3-5-sonnet
CLAUDE_TIMEOUT=300
```

---

### **Step 3: Use in Your Code**

```python
# orchestrator.py
from config import settings, get_settings

class Orchestrator:
    def __init__(self, vault_path=None):
        # Use settings.vault_path if not provided
        self.vault_path = vault_path or settings.vault_path
        
        # Initialize database
        from database import Database
        self.db = Database(settings.database_url)
        
        # Setup logging
        from logging_utils import setup_logging
        self.logger = setup_logging(settings.log_dir)
        
        # Log configuration
        self.logger.info(f"Starting: {settings.summary()}")
```

---

## 🎯 **Key Benefits**

### **1. Type Safety**

```python
# ✅ Automatic type conversion
settings.check_interval      # int, not string
settings.vault_path          # Path, not string
settings.dry_run             # bool, not string
settings.log_level           # Validated literal

# ❌ No manual conversion needed!
interval = int(os.getenv("CHECK_INTERVAL"))  # Old way
```

---

### **2. Validation**

```python
# ✅ Caught at startup, not runtime

# Range validation
check_interval: int = Field(ge=10, le=3600)  # 10-3600

# Literal validation (must be one of these)
log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"]

# Custom validation
@field_validator("database_url")
def validate_db_url(cls, v):
    if not v.startswith(("sqlite", "postgresql", "mysql")):
        raise ValueError("Invalid database URL")
```

---

### **3. Centralization**

```python
# ✅ All settings in one place
# config.py is the single source of truth

# Find all settings? Just open config.py
# Need to add a setting? Add to Settings class
# Want to see defaults? Check Field() values
```

---

### **4. IDE Support**

```python
from config import settings

settings.  # ← IDE shows ALL available settings!
# - vault_path
# - database_url
# - check_interval
# - dry_run
# - etc.

# Plus type hints!
vault: Path = settings.vault_path  # ✅ No type errors
```

---

### **5. Helper Methods**

```python
# Check database type
if settings.is_sqlite:
    print("Using SQLite")
elif settings.is_postgresql:
    print("Using PostgreSQL")

# Check mode
if settings.is_development:
    enable_debug_features()

# Validate for production
try:
    settings.validate_for_production()
except ValueError as e:
    print(f"Not ready: {e}")

# Print summary (safe to log)
print(settings.summary())
```

---

## 📋 **All Available Settings**

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `vault_path` | `Path` | `./vault` | Obsidian vault location |
| `check_interval` | `int` | `60` | Watcher interval (seconds) |
| `dry_run` | `bool` | `True` | Safe mode |
| `dev_mode` | `bool` | `True` | Development features |
| `claude_model` | `Literal` | `claude-3-5-sonnet` | Claude model |
| `claude_timeout` | `int` | `300` | Claude timeout (seconds) |
| `database_url` | `str` | `sqlite:///database/tasks.db` | Database URL |
| `log_level` | `Literal` | `INFO` | Logging level |
| `log_dir` | `Path` | `./logs` | Log directory |
| `gmail_address` | `str` | `None` | Gmail address |
| `gmail_app_password` | `str` | `None` | Gmail password |

---

## 🚀 **Usage Examples**

### **Example 1: Basic Usage**

```python
from config import settings

# Access settings
db = Database(settings.database_url)
logger = setup_logging(settings.log_dir)
```

---

### **Example 2: Conditional Logic**

```python
from config import settings

if settings.is_development:
    logger.debug("Debug mode enabled")
    
if settings.dry_run:
    logger.info("Safe mode: no real actions")
```

---

### **Example 3: Production Validation**

```python
from config import settings

try:
    settings.validate_for_production()
    print("✅ Ready for production")
except ValueError as e:
    print(f"❌ Issues:\n{e}")
    # Fix before deploying
```

---

### **Example 4: Testing**

```python
# test_something.py
import os
from config import reload_settings

# Override for testing
os.environ["DATABASE_URL"] = "sqlite:///test.db"
os.environ["DRY_RUN"] = "true"

settings = reload_settings()
# Now use settings in tests
```

---

## 🌐 **Environment-Specific Configs**

### **Development (.env)**

```bash
VAULT_PATH=./vault
DATABASE_URL=sqlite:///database/tasks.db
DRY_RUN=true
DEV_MODE=true
LOG_LEVEL=DEBUG
```

---

### **Production (.env.production)**

```bash
VAULT_PATH=/app/vault
DATABASE_URL=postgresql://user:pass@db.host.com/ai_employee
DRY_RUN=false
DEV_MODE=false
LOG_LEVEL=INFO
```

---

### **Cloud (Environment Variables)**

```bash
# Set in Railway/Render/Oracle Cloud dashboard
VAULT_PATH=/app/vault
DATABASE_URL=postgresql://user:pass@db.railway.app/ai_employee
DRY_RUN=false
DEV_MODE=false

# No .env file needed - reads from environment!
```

---

## 🧪 **Testing the Configuration**

```bash
# Run configuration test
uv run python test_config.py

# Output shows:
# - All current settings
# - Database connection test
# - Production validation
# - Next steps
```

---

## 📊 **Where Settings Are Used**

| File | Settings Used |
|------|---------------|
| `orchestrator.py` | `vault_path`, `log_dir`, `database_url` |
| `database/db_engine.py` | `database_url` |
| `watchers/filesystem_watcher.py` | `check_interval` |
| `logging_utils.py` | `log_dir`, `log_level` |
| `test_config.py` | All settings |

---

## 🎯 **Migration Status**

### **✅ Completed:**

- [x] `config.py` created with Pydantic Settings
- [x] `.env` updated with DATABASE_URL
- [x] `orchestrator.py` updated to use settings
- [x] `database/db_engine.py` updated to use settings
- [x] `test_config.py` created
- [x] Dependencies updated (`pydantic-settings`)

### **🔄 In Progress:**

- [ ] Update watchers to use settings
- [ ] Add more validation rules
- [ ] Create environment-specific .env templates

---

## 📚 **Resources**

- **Pydantic Settings:** https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- **Full Guide:** `CONFIG_GUIDE.md`
- **Test Script:** `uv run python test_config.py`

---

## 🎉 **Summary**

**Q: How are you managing env variables?**

**A:** Using **Pydantic Settings** - a modern, type-safe approach that provides:

1. ✅ **Type Safety** - Automatic conversion (no more `int()`, `bool()` casting)
2. ✅ **Validation** - Errors caught at startup, not runtime
3. ✅ **Centralization** - One source of truth (`config.py`)
4. ✅ **IDE Support** - Full autocomplete and type hints
5. ✅ **Helper Methods** - `is_sqlite`, `is_development`, `validate_for_production()`
6. ✅ **Documentation** - All settings described with types and defaults

**Files:**
- `config.py` - Settings definition
- `.env` - Environment variables
- `test_config.py` - Configuration test
- `CONFIG_GUIDE.md` - Full documentation

**Usage:**
```python
from config import settings

# That's it! Use anywhere in your code
db = Database(settings.database_url)
```

**Test it:**
```bash
uv run python test_config.py
```

---

*Configuration management done right! 🎉*
