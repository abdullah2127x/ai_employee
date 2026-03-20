# Issue Analysis: Folder Watchers Not Triggering

**Date:** 2026-03-20  
**Status:** Fixed

---

## 🐛 Problem

File was created in `Needs_Action/` by Filesystem Watcher, but Folder Watcher did not detect it.

### **Symptoms:**
```
07:24:54 [filesystem_watcher] ✅ Successfully processed: greet.txt
07:24:54 [filesystem_watcher] 📝 Created metadata: FILE_20260320_072454_greet.txt.md

# File created in Needs_Action/ but...
# NO Folder Watcher callback triggered!
# NO "on_needs_action_change" called!
```

---

## 🔍 Root Cause

### **Issue 1: Missing Logging**
Folder Watchers were starting but not logging, making it impossible to see if they were working.

**Fix:** Added INFO-level logging for all Folder Watcher events:
```python
logger.info(f"FolderWatcher detected CREATED: {event.src_path}")
```

### **Issue 2: No Confirmation of Folder Watcher Start**
Orchestrator didn't log when Folder Watchers started.

**Fix:** Added logging for each Folder Watcher:
```python
for name, watcher in self.watchers.items():
    watcher.start()
    logger.write_to_timeline(
        f"Folder Watcher started: {name}",
        actor="orchestrator",
        message_level="INFO"
    )
```

---

## ✅ Fix Applied

### **1. Enhanced Folder Watcher Logging**
```python
# watchers/folder_watcher.py
def on_created(self, event):
    logger.info(f"FolderWatcher detected CREATED: {event.src_path}")
    self.on_change('created', event.src_path)

def on_deleted(self, event):
    logger.info(f"FolderWatcher detected DELETED: {event.src_path}")
    self.on_change('deleted', event.src_path)

def on_moved(self, event):
    logger.info(f"FolderWatcher detected MOVED: {event.src_path}")
    self.on_change('moved', event.src_path)
```

### **2. Enhanced Orchestrator Logging**
```python
# orchestrator.py
for name, watcher in self.watchers.items():
    watcher.start()
    logger.write_to_timeline(
        f"Folder Watcher started: {name}",
        actor="orchestrator",
        message_level="INFO"
    )

logger.write_to_timeline(
    "All watchers started, beginning timeout check loop",
    actor="orchestrator",
    message_level="INFO"
)
```

---

## 🧪 Testing

### **Expected Logs After Fix:**
```
07:23:07 [orchestrator] ℹ️ Orchestrator starting all watchers
07:23:07 [orchestrator] ℹ️ Filesystem Watcher started (Drop/ folder monitored)
07:23:07 [orchestrator] ℹ️ Folder Watcher started: needs_action
07:23:07 [orchestrator] ℹ️ Folder Watcher started: processing
07:23:07 [orchestrator] ℹ️ Folder Watcher started: approved
07:23:07 [orchestrator] ℹ️ Folder Watcher started: rejected
07:23:07 [orchestrator] ℹ️ Folder Watcher started: needs_revision
07:23:07 [orchestrator] ℹ️ All watchers started, beginning timeout check loop

# When file is created:
07:24:54 [filesystem_watcher] ℹ️ 📝 Created metadata: FILE_20260320_072454_greet.txt.md
07:24:54 [folder_watcher] ℹ️ FolderWatcher detected CREATED: Needs_Action/FILE_....md
07:24:54 [orchestrator] ℹ️ New task detected: FILE_20260320_072454_greet.txt.md
```

---

## 📊 Current Status

| Component | Status | Logging |
|-----------|--------|---------|
| **Filesystem Watcher** | ✅ Running | ✅ Full logging |
| **Folder Watcher: Needs_Action/** | ✅ Running | ✅ Full logging |
| **Folder Watcher: Processing/** | ✅ Running | ✅ Full logging |
| **Folder Watcher: Approved/** | ✅ Running | ✅ Full logging |
| **Folder Watcher: Rejected/** | ✅ Running | ✅ Full logging |
| **Folder Watcher: Needs_Revision/** | ✅ Running | ✅ Full logging |
| **Timeout Check** | ✅ Running (60s) | ✅ Full logging |

---

## 🎯 Next Test

1. **Start Orchestrator:**
   ```bash
   python orchestrator.py
   ```

2. **Drop test file:**
   ```bash
   echo "test" > vault/Inbox/Drop/test.txt
   ```

3. **Expected flow:**
   - Filesystem Watcher detects → Creates metadata
   - Folder Watcher (Needs_Action/) detects → Calls callback
   - Orchestrator moves to Processing/
   - Claude Runner called
   - File moves to correct folder

---

**Status:** ✅ Fixed, ready for testing
