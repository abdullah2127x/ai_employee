# Watcher Architecture & Enabling Guide

**Purpose:** Explain where and how watchers are enabled in the AI Employee system, and clarify the relationship between `orchestrator.py` and `watchers/main.py`.

---

## 1. Where Watchers Are Enabled (Orchestrator)

### Location: `orchestrator.py` → `Orchestrator.__init__()`

**Lines 103-155** (approximately)

```python
def __init__(self):
    self.file_move_times: Dict[str, datetime] = {}
    self.timeout_seconds = 300  # Set to 300 (5 min) for production

    self.observer_threads = []

    # ─────────────────────────────────────────────────────────────
    # FILESYSTEM WATCHER (Drop/ folder)
    # ─────────────────────────────────────────────────────────────
    self.filesystem_watcher = None
    if settings.enable_filesystem_watcher:
        self.filesystem_watcher = FilesystemWatcher()
        logger.write_to_timeline(
            "Filesystem Watcher enabled (Drop/ monitored)",
            actor="orchestrator",
            message_level="INFO",
        )
    else:
        logger.write_to_timeline(
            "Filesystem Watcher disabled",
            actor="orchestrator",
            message_level="WARNING",
        )

    # ─────────────────────────────────────────────────────────────
    # GMAIL WATCHER (Gmail API)
    # ─────────────────────────────────────────────────────────────
    self.gmail_watcher = None
    self.gmail_watcher_thread = None
    if settings.enable_gmail_watcher:
        try:
            # Determine credentials path
            creds_path = settings.gmail_credentials_path
            if creds_path is None:
                creds_path = settings.vault_path / "credentials.json"

            self.gmail_watcher = GmailWatcher(
                credentials_path=creds_path,
                check_interval=settings.gmail_watcher_check_interval,
                gmail_query=settings.gmail_watcher_query,
            )
            logger.write_to_timeline(
                f"Gmail Watcher enabled | Query: {settings.gmail_watcher_query} | "
                f"Interval: {settings.gmail_watcher_check_interval}s",
                actor="orchestrator",
                message_level="INFO",
            )
        except ImportError as e:
            logger.log_warning(
                f"Gmail Watcher disabled - libraries not installed: {e}",
                actor="orchestrator",
            )
        except Exception as e:
            logger.log_error(
                f"Gmail Watcher initialization error: {e}",
                actor="orchestrator",
            )
    else:
        logger.write_to_timeline(
            "Gmail Watcher disabled (enable in settings)",
            actor="orchestrator",
            message_level="INFO",
        )
```

---

### Settings Control (from `.env` file)

| Setting | Controls | Default |
|---------|----------|---------|
| `ENABLE_FILESYSTEM_WATCHER` | Filesystem watcher on/off | `true` |
| `ENABLE_GMAIL_WATCHER` | Gmail watcher on/off | `false` |
| `GMAIL_WATCHER_CHECK_INTERVAL` | Gmail check frequency (seconds) | `120` |
| `GMAIL_WATCHER_QUERY` | Gmail filter query | `is:unread is:important` |
| `GMAIL_CREDENTIALS_PATH` | Path to Gmail credentials | `vault/credentials.json` |

---

### Starting Watchers (Orchestrator.start())

**Lines 189-215** (approximately)

```python
def start(self):
    logger.write_to_timeline(
        "Orchestrator starting", actor="orchestrator", message_level="INFO"
    )

    # ── Start Filesystem Watcher ──────────────────────────────────
    if self.filesystem_watcher:
        t = threading.Thread(target=self.filesystem_watcher.run, daemon=True)
        t.start()
        logger.write_to_timeline(
            "Filesystem Watcher started", actor="orchestrator", message_level="INFO"
        )

    # ── Start Gmail Watcher (background thread) ───────────────────
    if self.gmail_watcher and self.gmail_watcher.service:
        self.gmail_watcher_thread = threading.Thread(
            target=self.gmail_watcher.run,
            daemon=True,
            name="GmailWatcher"
        )
        self.gmail_watcher_thread.start()
        logger.write_to_timeline(
            "Gmail Watcher started (background thread)",
            actor="orchestrator",
            message_level="INFO",
        )

    # ── Start Folder Watchers (Needs_Action, Processing, etc.) ────
    for name, watcher in self.watchers.items():
        watcher.start()
        # ...
```

---

## 2. Why Does `watchers/main.py` Exist?

### Purpose: Standalone Watcher Runner (No Orchestrator)

**`watchers/main.py`** is a **standalone entry point** for running watchers **without** the full orchestrator.

---

### Use Cases for `watchers/main.py`

#### **Use Case 1: Testing Watchers Independently**

You want to test the Gmail watcher without Claude Code processing:

```bash
# Run only watchers (no orchestrator, no Claude processing)
python watchers/main.py
```

This is useful for:
- Debugging watcher issues
- Testing Gmail API connectivity
- Verifying task file creation format
- Development without full system overhead

---

#### **Use Case 2: Modular Deployment**

You want to run watchers on a different machine than the orchestrator:

```
┌─────────────────────────────────────────────────────────────┐
│  Machine A: Watcher Server                                  │
│  - Runs: python watchers/main.py                            │
│  - Creates task files in shared vault                       │
│  - No Claude Code, no processing                            │
└─────────────────────────────────────────────────────────────┘
                          │
                          │ Shared vault (network drive)
                          ↓
┌─────────────────────────────────────────────────────────────┐
│  Machine B: Processing Server                               │
│  - Runs: python orchestrator.py                             │
│  - Monitors Processing/ folder                              │
│  - Calls Claude Code for AI processing                      │
└─────────────────────────────────────────────────────────────┘
```

---

#### **Use Case 3: Simple Deployments**

For simple setups where you only need file drop monitoring (no Gmail):

```bash
# Just run the filesystem watcher
python watchers/main.py
```

This is lighter than running the full orchestrator.

---

### Architecture Comparison

| Feature | `orchestrator.py` | `watchers/main.py` |
|---------|-------------------|-------------------|
| **Purpose** | Full workflow orchestration | Standalone watcher runner |
| **Watchers** | Filesystem + Gmail (both) | Filesystem + Gmail (both) |
| **Folder Monitoring** | ✅ Needs_Action/, Processing/, Runner_Status/, etc. | ❌ None |
| **Claude Runner** | ✅ Calls claude_runner.py subprocesses | ❌ No Claude integration |
| **Task Processing** | ✅ Moves files, tracks timeouts, retries | ❌ Only creates task files |
| **Dashboard** | ✅ Updates Dashboard.md | ❌ No dashboard |
| **Complexity** | High (full system) | Low (watchers only) |
| **Use Case** | Production deployment | Testing / Modular deployment |

---

### When to Use Each

**Use `orchestrator.py` when:**
- ✅ Running full AI Employee system
- ✅ You want automatic task processing by Claude Code
- ✅ You need retry logic and error handling
- ✅ You want Dashboard.md updates
- ✅ Production environment

**Use `watchers/main.py` when:**
- ✅ Testing watcher functionality
- ✅ Debugging Gmail API issues
- ✅ Running watchers on separate machine
- ✅ Simple file drop monitoring only (no AI processing needed)
- ✅ Development/testing environment

---

## 3. Complete Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                     ENTRY POINTS                                │
│                                                                 │
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │  orchestrator.py    │     │  watchers/main.py           │   │
│  │  (Full system)      │     │  (Watchers only)            │   │
│  │                     │     │                             │   │
│  │  - Watchers         │     │  - Watchers                 │   │
│  │  - Folder monitors  │     │  - No folder monitors       │   │
│  │  - Claude runner    │     │  - No Claude runner         │   │
│  │  - Dashboard        │     │  - No dashboard             │   │
│  └─────────────────────┘     └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
              │                              │
              │ (both can run watchers)      │
              ↓                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     WATCHERS LAYER                              │
│                                                                 │
│  ┌─────────────────────┐     ┌─────────────────────────────┐   │
│  │  FilesystemWatcher  │     │  GmailWatcher               │   │
│  │  - Watches Drop/    │     │  - Polls Gmail API          │   │
│  │  - Creates tasks    │     │  - Creates tasks            │   │
│  └─────────────────────┘     └─────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
              │                              │
              │ create_*_task()              │
              ↓                              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     TASK FILES                                  │
│                                                                 │
│              Needs_Action/*.md                                  │
│              - file_drop_*.md (from FilesystemWatcher)          │
│              - email_*.md (from GmailWatcher)                   │
└─────────────────────────────────────────────────────────────────┘
              │
              │ (orchestrator only)
              ↓
┌─────────────────────────────────────────────────────────────────┐
│                     PROCESSING LAYER                            │
│                                                                 │
│  1. FolderWatcher detects new file in Needs_Action/             │
│  2. Move to Processing/                                         │
│  3. Call claude_runner.py subprocess                            │
│  4. Claude Code processes task                                  │
│  5. Write RESULT_*.md to Done/ or Pending_Approval/             │
│  6. Archive original task file                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Quick Reference

### Enable/Disable Watchers (in `.env`)

```env
# Filesystem Watcher (Drop/ folder)
ENABLE_FILESYSTEM_WATCHER=true

# Gmail Watcher
ENABLE_GMAIL_WATCHER=false  # Set to true to enable
```

### Run Commands

```bash
# Full system (production)
python orchestrator.py

# Watchers only (testing)
python watchers/main.py

# Test Gmail watcher standalone
python -m watchers.gmail_watcher

# Test Filesystem watcher standalone
python -m watchers.filesystem_watcher
```

### Check Watcher Status

**In timeline logs:**
```
vault/Logs/timeline/YYYY-MM-DD.md
```

**Look for:**
```
10:00:00 [orchestrator] → Filesystem Watcher enabled (Drop/ monitored)
10:00:00 [orchestrator] → Gmail Watcher enabled | Query: is:unread is:important | Interval: 120s
10:00:01 [orchestrator] → Filesystem Watcher started
10:00:01 [orchestrator] → Gmail Watcher started (background thread)
```

---

## 5. Summary

| Question | Answer |
|----------|--------|
| **Where are watchers enabled?** | `orchestrator.py` → `Orchestrator.__init__()` (lines 103-155) |
| **What controls enabling?** | Settings from `.env`: `ENABLE_FILESYSTEM_WATCHER`, `ENABLE_GMAIL_WATCHER` |
| **Why does `main.py` exist?** | Standalone watcher runner for testing/modular deployment |
| **Should I use `main.py` or `orchestrator.py`?** | Use `orchestrator.py` for production, `main.py` for testing |
| **Can both run simultaneously?** | No - they would create duplicate task files |

---

*Last updated: 2026-03-23*
