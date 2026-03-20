# Filesystem Watcher Management - Updated Architecture

**Date:** 2026-03-19  
**Version:** 2.1  
**Status:** Implementation Complete

---

## 🎯 Key Change: Orchestrator Manages Filesystem Watcher

### **Before:**
```
Filesystem Watcher = Separate service (run independently)
Orchestrator = Separate service (run independently)
User = Must start both manually
```

### **After:**
```
Filesystem Watcher = Managed by Orchestrator
Orchestrator = Single service (starts everything)
User = Only run Orchestrator
```

---

## 🔧 Configuration

### **New Setting in `.env`:**
```bash
# Watcher Enable Flags
ENABLE_FILESYSTEM_WATCHER=true  # Set to false to disable Drop/ folder monitoring
```

### **New Setting in `core/config.py`:**
```python
enable_filesystem_watcher: bool = Field(
    default=True,
    description="Enable Filesystem Watcher (watches Drop/ folder)"
)
```

---

## 🏗️ Architecture

### **Orchestrator Responsibilities:**

1. **Start Filesystem Watcher** (if enabled)
   - Runs in separate thread (non-blocking)
   - Monitors `Inbox/Drop/` folder
   - Creates metadata files in `Needs_Action/`

2. **Start Folder Watchers** (always enabled)
   - `Needs_Action/` - New tasks
   - `Processing/` - Timeout detection
   - `Approved/` - Execute actions
   - `Rejected/` - Log rejections
   - `Needs_Revision/` - Reprocess tasks

3. **Timeout Tracking**
   - Checks every 60 seconds
   - Tracks files in `Processing/` via `file_move_times`
   - Moves back to `Needs_Action/` on timeout

4. **Graceful Shutdown**
   - Stops Filesystem Watcher
   - Stops all Folder Watchers
   - Logs shutdown

---

## 📊 Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ User runs: python orchestrator.py                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator.__init__()                                         │
│ - Checks: ENABLE_FILESYSTEM_WATCHER flag                        │
│ - If True: Creates FilesystemWatcher instance                   │
│ - Creates: FolderWatcher instances for all workflow folders     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator.start()                                            │
│ - Starts Filesystem Watcher (in thread, if enabled)             │
│ - Starts all Folder Watchers                                    │
│ - Starts timeout check loop (every 60 seconds)                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Filesystem Watcher Thread                                       │
│ - Watches: Inbox/Drop/                                          │
│ - On file detected: Creates metadata in Needs_Action/           │
│ - Moves: Drop/ → Drop_History/                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Folder Watcher: Needs_Action/                                   │
│ - Detects: New metadata file                                    │
│ - Callback: on_needs_action_change()                            │
│ - Action: Move to Processing/, record timestamp, call Claude    │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Usage

### **Start Orchestrator (Manages Everything):**
```bash
python orchestrator.py
```

**What Happens:**
1. ✅ Reads `ENABLE_FILESYSTEM_WATCHER` from `.env`
2. ✅ Starts Filesystem Watcher (if enabled)
3. ✅ Starts all Folder Watchers
4. ✅ Starts timeout check loop

### **Disable Filesystem Watcher:**
```bash
# In .env:
ENABLE_FILESYSTEM_WATCHER=false
```

**Use Case:** If you want to manually drop files without automatic processing.

---

## 📁 Files Modified

### **1. `core/config.py`**
- Added `enable_filesystem_watcher` setting
- Reads from `ENABLE_FILESYSTEM_WATCHER` environment variable

### **2. `.env` and `.env.example`**
- Added `ENABLE_FILESYSTEM_WATCHER` flag
- Default: `true` (enabled)

### **3. `orchestrator.py`**
- Imports `FilesystemWatcher`
- Creates Filesystem Watcher instance (if enabled)
- Starts Filesystem Watcher in separate thread
- Stops Filesystem Watcher on shutdown

---

## 🔍 Code Changes

### **Orchestrator.__init__():**
```python
# Filesystem Watcher (managed by Orchestrator)
self.filesystem_watcher = None
if settings.enable_filesystem_watcher:
    logger.write_to_timeline(
        "Filesystem Watcher enabled (watches Drop/ folder)",
        actor="orchestrator",
        message_level="INFO"
    )
    # Create Filesystem Watcher (it has its own thread)
    self.filesystem_watcher = FilesystemWatcher()
else:
    logger.write_to_timeline(
        "Filesystem Watcher disabled (Drop/ folder not monitored)",
        actor="orchestrator",
        message_level="WARNING"
    )
```

### **Orchestrator.start():**
```python
# Start Filesystem Watcher (if enabled)
if self.filesystem_watcher:
    # Start in separate thread (non-blocking)
    watcher_thread = threading.Thread(
        target=self.filesystem_watcher.run,
        daemon=True
    )
    watcher_thread.start()
    logger.write_to_timeline(
        "Filesystem Watcher started (Drop/ folder monitored)",
        actor="orchestrator",
        message_level="INFO"
    )
```

### **Orchestrator.stop():**
```python
# Stop Filesystem Watcher (if running)
if self.filesystem_watcher:
    self.filesystem_watcher.stop()
```

---

## ✅ Benefits

| Benefit | Description |
|---------|-------------|
| **Single Service** | Only run `orchestrator.py` - everything else is managed |
| **Conditional** | Enable/disable Filesystem Watcher via flag |
| **Thread-Safe** | Filesystem Watcher runs in separate thread |
| **Graceful** | Proper shutdown of all watchers |
| **Logged** | All watcher start/stop events logged |

---

## 🧪 Testing

### **Test 1: Filesystem Watcher Enabled (Default)**
```bash
# In .env:
ENABLE_FILESYSTEM_WATCHER=true

# Run:
python orchestrator.py

# Expected:
# - "Filesystem Watcher enabled" message
# - "Filesystem Watcher started" message
# - Drop file in Inbox/Drop/ → Metadata created
```

### **Test 2: Filesystem Watcher Disabled**
```bash
# In .env:
ENABLE_FILESYSTEM_WATCHER=false

# Run:
python orchestrator.py

# Expected:
# - "Filesystem Watcher disabled" message
# - No Filesystem Watcher thread
# - Drop file in Inbox/Drop/ → Nothing happens (as expected)
```

---

## 📊 Settings Summary

| Setting | Location | Default | Description |
|---------|----------|---------|-------------|
| `ENABLE_FILESYSTEM_WATCHER` | `.env` | `true` | Enable Drop/ folder monitoring |
| `CHECK_INTERVAL` | `.env` | `60` | Timeout check interval (seconds) |
| `MIN_LOG_LEVEL` | `.env` | `INFO` | Logging verbosity |
| `DEV_MODE` | `.env` | `true` | Enable console output |

---

## 🎯 Next Steps

### **Ready to Test:**
1. ✅ Run `python orchestrator.py`
2. ✅ Drop test file in `Inbox/Drop/`
3. ✅ Verify metadata created in `Needs_Action/`
4. ✅ Verify file moves to `Processing/`
5. ✅ Verify Claude Runner called
6. ✅ Verify file moves to correct folder

### **Optional Enhancements:**
- [ ] Add more watcher enable flags (Gmail, WhatsApp, etc.)
- [ ] Add watcher health monitoring
- [ ] Add automatic restart on watcher crash
- [ ] Add watcher statistics (files processed, errors, etc.)

---

**Implementation Status:** ✅ Complete  
**Documentation Status:** ✅ Complete  
**Testing Status:** ⏳ Pending

---

*For questions or issues, refer to SETTINGS_AND_WORKFLOW.md or contact project maintainer.*
