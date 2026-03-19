# Logging Management Guide

**Last Updated:** 2026-03-19  
**Version:** 1.0  
**Status:** Production-Ready

---

## 📋 Overview

The AI Employee project uses a **custom centralized logging system** designed for business audit trails, task tracking, and error monitoring. This guide explains everything you need to know about logging in this project.

---

## 🎯 Core Principles

### **1. Single Logging System**

✅ **DO:** Use `LoggingManager` from `utils.logging_manager` for ALL logging  
❌ **DON'T:** Use Python's standard `logging` module

```python
# ✅ CORRECT:
from utils.logging_manager import LoggingManager
logger = LoggingManager()
logger.write_to_timeline("Message", actor="component", message_level="INFO")

# ❌ WRONG:
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
```

---

### **2. Centralized Configuration**

✅ **DO:** Configure logging via `.env` file  
❌ **DON'T:** Hardcode log levels in code

```bash
# In .env file:
MIN_LOG_LEVEL=INFO          # DEBUG, INFO, WARNING, ERROR, CRITICAL
LOGS_PER_TASK_ENABLED=true  # Enable detailed task logs
DEV_MODE=true               # Enable console output
```

---

### **3. Two-Tier Logging**

The logging system has **two tiers**:

| Tier | Purpose | Location | Written By |
|------|---------|----------|------------|
| **Timeline** | Business audit trail (high-level) | `vault/Logs/timeline/YYYY-MM-DD.md` | Orchestrator only |
| **Task Logs** | Detailed per-task forensic logs | `vault/Logs/tasks/task-<type>_<id>.md` | All components |
| **Error Logs** | Stack traces and error details | `vault/Logs/errors/errors_YYYY-MM-DD.md` | All components |

---

## 🔧 Configuration

### **Environment Variables (.env)**

```bash
# Logging Settings
MIN_LOG_LEVEL=INFO              # Minimum level to log
LOGS_PER_TASK_ENABLED=true      # Enable task-level logging
DEV_MODE=true                   # Enable console output
```

### **Log Levels**

| Level | Value | Description | When to Use |
|-------|-------|-------------|-------------|
| **DEBUG** | 0 | Everything (most verbose) | Development debugging |
| **INFO** | 1 | Normal operations | Default for development |
| **WARNING** | 2 | Warnings and above | Production (recommended) |
| **ERROR** | 3 | Errors only | Minimal logging |
| **CRITICAL** | 4 | Critical errors only | Almost silent |

**Filtering Logic:**
```
If MIN_LOG_LEVEL = "WARNING" (value = 2):
- DEBUG messages (0)   → ❌ Filtered (0 < 2)
- INFO messages (1)    → ❌ Filtered (1 < 2)
- WARNING messages (2) → ✅ Logged (2 >= 2)
- ERROR messages (3)   → ✅ Logged (3 >= 2)
- CRITICAL (4)         → ✅ Logged (4 >= 2)
```

---

## 📖 Usage Guide

### **1. Initialize LoggingManager**

```python
from utils.logging_manager import LoggingManager

# No parameters needed - reads from settings automatically!
logger = LoggingManager()
```

**Configuration is automatic:**
- `logs_dir` ← `settings.logs_dir` (vault_path / "Logs")
- `enable_console` ← `settings.dev_mode`
- `min_log_level_value` ← `settings.min_log_level`

---

### **2. Timeline Logging (High-Level)**

Use for business audit trail and daily activity summary:

```python
# Basic timeline entry
logger.write_to_timeline(
    message="📁 New file detected: invoice.pdf",
    actor="filesystem_watcher",
    message_level="INFO"
)

# Warning
logger.write_to_timeline(
    message="File disappeared before processing",
    actor="filesystem_watcher",
    message_level="WARNING"
)

# Error
logger.write_to_timeline(
    message="Failed to process file",
    actor="orchestrator",
    message_level="ERROR"
)
```

**Output:** `vault/Logs/timeline/2026-03-19.md`

```markdown
# 2026-03-19 Activity Log

10:30:00 [filesystem_watcher] → 📁 New file detected: invoice.pdf
10:30:05 [filesystem_watcher] → ⚠️ File disappeared before processing
10:30:10 [orchestrator] → ❌ ERROR: Failed to process file
```

---

### **3. Task Logging (Detailed)**

Use for per-task detailed forensic logs:

```python
logger.write_to_task_log(
    task_type="file_drop",
    task_id="file_20260319_103000_invoice.pdf",
    message="📁 New file detected: invoice.pdf",
    actor="filesystem_watcher",
    trigger_file="D:/.../Drop/invoice.pdf",
    status="in_progress",
    message_level="INFO"
)
```

**Output:** `vault/Logs/tasks/task-file_drop_20260319_103000_file_....md`

```markdown
# Task file_drop_20260319_103000_invoice.pdf

trigger_file:    D:/.../Drop/invoice.pdf
created:         2026-03-19T10:30:00
status:          in_progress
final_result:    pending

## Event Timeline

10:30:00 [filesystem_watcher] 📁 New file detected: invoice.pdf
10:30:01 [filesystem_watcher] 🔍 Hash: abc123...
10:30:02 [filesystem_watcher] 📝 Created metadata
```

---

### **4. Error Logging (With Stack Traces)**

Use for errors and exceptions:

```python
# Simple error
logger.log_error(
    message="Failed to process file",
    error=exception_object,
    actor="filesystem_watcher"
)

# Error without stack trace
logger.log_error(
    message="Configuration missing",
    error=None,  # No exception object
    actor="orchestrator",
    log_stack_trace=False
)
```

**Output:** `vault/Logs/errors/errors_2026-03-19.md`

```markdown
# 2026-03-19 Error Log

## 2026-03-19 10:30:00 - filesystem_watcher

**Message:** Failed to process file

**Exception:** FileNotFoundError: File not found

### Stack Trace

```
Traceback (most recent call last):
  File "filesystem_watcher.py", line 100, in _process_new_file
    shutil.move(source, dest)
FileNotFoundError: File not found
```
```

---

### **5. Convenience Methods**

```python
# Warning
logger.log_warning("Low disk space", actor="monitor")

# Critical error (always logs stack trace)
logger.log_critical("System crash detected", error=e, actor="system")

# Debug message (only if MIN_LOG_LEVEL=DEBUG)
logger.log_debug("Variable x = 42", actor="debugger")
```

---

## 📁 Log File Locations

All logs are stored in `vault/Logs/`:

```
vault/
└── Logs/
    ├── timeline/
    │   ├── 2026-03-19.md          ← Daily activity timeline
    │   └── 2026-03-20.md
    ├── tasks/
    │   ├── task-file_drop_20260319_103000_....md
    │   └── task-email_20260319_104500_....md
    └── errors/
        ├── errors_2026-03-19.md    ← Error log with stack traces
        └── errors_2026-03-20.md
```

---

## 🎯 When to Use What

### **Use Timeline Logging When:**

- ✅ Logging high-level business events
- ✅ Creating audit trail
- ✅ Tracking task flow (start, complete, error)
- ✅ CEO briefing / daily summary

**Example:**
```python
logger.write_to_timeline("🔄 Started Needs_Action scan", actor="orchestrator")
logger.write_to_timeline("✅ Task completed: invoice.pdf", actor="orchestrator")
```

---

### **Use Task Logging When:**

- ✅ Logging detailed steps for a specific task
- ✅ Debugging task processing
- ✅ Creating forensic audit trail
- ✅ Compliance requirements

**Example:**
```python
logger.write_to_task_log(
    task_type="file_drop",
    task_id="file_20260319_103000_invoice.pdf",
    message="📝 Created metadata",
    actor="filesystem_watcher"
)
```

---

### **Use Error Logging When:**

- ✅ An exception occurs
- ✅ Something goes wrong
- ✅ Stack trace is needed for debugging
- ✅ Alert needs to be raised

**Example:**
```python
try:
    process_file()
except Exception as e:
    logger.log_error("Failed to process file", error=e, actor="processor")
```

---

## 🚫 Common Mistakes

### **Mistake 1: Using Python's logging Module**

```python
# ❌ WRONG:
import logging
logger = logging.getLogger(__name__)
logger.info("Message")
```

**Why Wrong:**
- Creates duplicate logging systems
- Doesn't write to timeline/task logs
- No audit trail
- Violates RULES.md

**Fix:**
```python
# ✅ CORRECT:
from utils.logging_manager import LoggingManager
logger = LoggingManager()
logger.write_to_timeline("Message", actor="component", message_level="INFO")
```

---

### **Mistake 2: Hardcoding Log Level**

```python
# ❌ WRONG:
logger = LoggingManager(min_log_level="DEBUG")  # Hardcoded!
```

**Why Wrong:**
- Log level should be centralized in `.env`
- Different components shouldn't have different levels
- Hard to change in production

**Fix:**
```python
# ✅ CORRECT:
logger = LoggingManager()  # Reads MIN_LOG_LEVEL from settings
```

---

### **Mistake 3: Wrong Parameter Names**

```python
# ❌ WRONG:
logger.write_to_timeline("Message", level="INFO")  # Wrong parameter name!
```

**Why Wrong:**
- Parameter is `message_level`, not `level`
- Will cause TypeError

**Fix:**
```python
# ✅ CORRECT:
logger.write_to_timeline("Message", message_level="INFO")
```

---

### **Mistake 4: Not Checking logs_per_task_enabled**

```python
# ❌ WRONG:
# Always writing task logs even if disabled
self.logger.write_to_task_log(...)
```

**Why Wrong:**
- Wastes disk space if task logs disabled
- Ignores user configuration

**Fix:**
```python
# ✅ CORRECT:
if self.logs_per_task_enabled:
    self.logger.write_to_task_log(...)
```

---

## 🔍 Troubleshooting

### **Problem: No Logs Appearing**

**Check:**
1. Is `MIN_LOG_LEVEL` too high? (e.g., "ERROR" won't show INFO messages)
2. Is `DEV_MODE=false`? (Console output disabled)
3. Is `LOGS_PER_TASK_ENABLED=false`? (Task logs disabled)

**Solution:**
```bash
# In .env:
MIN_LOG_LEVEL=INFO
DEV_MODE=true
LOGS_PER_TASK_ENABLED=true
```

---

### **Problem: Task Logs Not Created**

**Check:**
1. Is `LOGS_PER_TASK_ENABLED=true`?
2. Are you calling `write_to_task_log()` inside `if logs_per_task_enabled:` block?
3. Does `vault/Logs/tasks/` directory exist?

**Solution:**
```python
# In filesystem_watcher.py:
self.logs_per_task_enabled = settings.logs_per_task_enabled

if self.logs_per_task_enabled:
    self.logger.write_to_task_log(...)
```

---

### **Problem: Console Output Not Showing**

**Check:**
1. Is `DEV_MODE=true`?
2. Is console being buffered?

**Solution:**
```bash
# In .env:
DEV_MODE=true
```

```python
# Force flush:
print("Message", flush=True)
```

---

## 📊 Log Level Recommendations

### **Development:**

```bash
MIN_LOG_LEVEL=INFO          # See all normal operations
DEV_MODE=true               # Enable console output
LOGS_PER_TASK_ENABLED=true  # Create detailed task logs
```

**Why:** Maximum visibility for debugging

---

### **Production:**

```bash
MIN_LOG_LEVEL=WARNING       # Only warnings and above
DEV_MODE=false              # Disable console output
LOGS_PER_TASK_ENABLED=true  # Keep task logs for audit
```

**Why:**
- Reduces log volume (better performance)
- Saves disk space
- Still maintains audit trail
- Console output not needed in production

---

### **Debugging Specific Issue:**

```bash
MIN_LOG_LEVEL=DEBUG         # Log everything
DEV_MODE=true               # Enable console output
LOGS_PER_TASK_ENABLED=true  # Detailed task logs
```

**Why:** Maximum verbosity for troubleshooting

---

## 🎓 Best Practices

### **1. Use Appropriate Log Levels**

```python
# Normal operation
logger.write_to_timeline("Task started", message_level="INFO")

# Something needs attention but not critical
logger.write_to_timeline("Low disk space", message_level="WARNING")

# Something failed
logger.log_error("Task failed", error=e, message_level="ERROR")

# System breaking issue
logger.log_critical("Database connection lost", error=e, message_level="CRITICAL")
```

---

### **2. Be Consistent with Actor Names**

```python
# ✅ GOOD: Consistent actor names
logger.write_to_timeline("Message", actor="filesystem_watcher")
logger.write_to_timeline("Message", actor="orchestrator")
logger.write_to_timeline("Message", actor="gmail_watcher")

# ❌ BAD: Inconsistent actor names
logger.write_to_timeline("Message", actor="FileSystemWatcher")
logger.write_to_timeline("Message", actor="fs_watcher")
logger.write_to_timeline("Message", actor="watcher")
```

---

### **3. Include Context in Messages**

```python
# ✅ GOOD: Clear context
logger.write_to_timeline(
    f"📁 New file detected: {filename}",
    actor="filesystem_watcher"
)

# ❌ BAD: Unclear
logger.write_to_timeline(
    "File detected",
    actor="filesystem_watcher"
)
```

---

### **4. Always Log Errors with Exception Object**

```python
# ✅ GOOD: Includes stack trace
try:
    process_file()
except Exception as e:
    logger.log_error("Failed to process file", error=e, actor="processor")

# ❌ BAD: No stack trace
try:
    process_file()
except Exception as e:
    logger.write_to_timeline(f"Error: {e}", message_level="ERROR")
```

---

## 📚 Quick Reference

### **Import:**
```python
from utils.logging_manager import LoggingManager
```

### **Initialize:**
```python
logger = LoggingManager()  # No parameters!
```

### **Timeline:**
```python
logger.write_to_timeline("Message", actor="component", message_level="INFO")
```

### **Task Log:**
```python
logger.write_to_task_log(
    task_type="file_drop",
    task_id="task_001",
    message="Processing",
    actor="watcher",
    message_level="INFO"
)
```

### **Error:**
```python
logger.log_error("Failed", error=e, actor="component")
```

### **Warning:**
```python
logger.log_warning("Low disk space", actor="monitor")
```

### **Debug:**
```python
logger.log_debug("Debug info", actor="debugger")
```

---

## 🔗 Related Files

- `utils/logging_manager.py` - Main logging implementation
- `core/config.py` - Configuration with `min_log_level` setting
- `.env` - Environment variables (MIN_LOG_LEVEL, etc.)
- `.env.example` - Template with all settings documented
- `RULES.md` - Project rules (includes logging rules)

---

## 📖 Examples

### **Example 1: Filesystem Watcher**

```python
from utils.logging_manager import LoggingManager
from core.config import settings

logger = LoggingManager()

def on_file_detected(filename):
    # Log to timeline
    logger.write_to_timeline(
        f"📁 New file detected: {filename}",
        actor="filesystem_watcher",
        message_level="INFO"
    )
    
    # Log to task log (if enabled)
    if settings.logs_per_task_enabled:
        logger.write_to_task_log(
            task_type="file_drop",
            task_id=f"file_{timestamp}_{filename}",
            message=f"📁 New file detected: {filename}",
            actor="filesystem_watcher",
            message_level="INFO"
        )
    
    try:
        process_file(filename)
        logger.write_to_timeline(
            f"✅ Processed: {filename}",
            actor="filesystem_watcher",
            message_level="INFO"
        )
    except Exception as e:
        logger.log_error(
            f"Failed to process {filename}",
            error=e,
            actor="filesystem_watcher"
        )
```

---

### **Example 2: Orchestrator**

```python
from utils.logging_manager import LoggingManager

logger = LoggingManager()

def process_pending_tasks():
    logger.write_to_timeline(
        "🔄 Started Needs_Action scan",
        actor="orchestrator",
        message_level="INFO"
    )
    
    for task in pending_tasks:
        logger.write_to_timeline(
            f"🔒 Claimed task: {task.id}",
            actor="orchestrator",
            message_level="INFO"
        )
        
        try:
            result = execute_task(task)
            logger.write_to_timeline(
                f"✅ Task completed: {task.id}",
                actor="orchestrator",
                message_level="INFO"
            )
        except Exception as e:
            logger.log_error(
                f"Task failed: {task.id}",
                error=e,
                actor="orchestrator"
            )
```

---

**End of Logging Management Guide**

*For questions or updates, refer to RULES.md or contact the project maintainer.*
