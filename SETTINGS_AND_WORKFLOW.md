# AI Employee Settings & Workflow Configuration

**Document Version:** 2.0  
**Created:** 2026-03-19  
**Last Updated:** 2026-03-19  
**Status:** Active (Architecture Finalized)

---

## 📋 Overview

This document specifies all configurable settings, workflow decisions, and architectural choices for the AI Employee system. Settings marked as ✅ are finalized, while ⏳ are pending further discussion.

---

## 🏗️ System Architecture

### **Watcher Architecture (TWO Separate Watchers)**

```
┌─────────────────────────────────────────────────────────────────┐
│ Watcher Type 1: Filesystem Watcher                              │
│ File: watchers/filesystem_watcher.py                            │
│ Purpose: User input detection                                   │
│ Watches: Inbox/Drop/ ONLY                                       │
│ Managed By: Orchestrator (starts and runs it)                   │
│ Action: Creates metadata files in Needs_Action/                 │
│ Moves files: Drop/ → Drop_History/                              │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│ Watcher Type 2: Folder Watcher (Generic)                        │
│ File: watchers/folder_watcher.py                                │
│ Purpose: Workflow state management                              │
│ Watches: ANY folder Orchestrator specifies                      │
│ Managed By: Orchestrator (creates, starts, manages callbacks)   │
│ Action: Calls Orchestrator callbacks on file changes            │
│ Folders: Needs_Action/, Processing/, Approved/,                 │
│          Rejected/, Needs_Revision/                             │
└─────────────────────────────────────────────────────────────────┘
```

**Key Distinction:**
- **Filesystem Watcher** = Specialized for Drop/ folder, handles file intake
- **Folder Watcher** = Generic, reusable, Orchestrator controls what to watch

---

## 🔄 Complete Workflow Summary (Updated v2.0)

```
┌─────────────────────────────────────────────────────────────────┐
│ STEP 1: Human drops file                                        │
│ Location: Inbox/Drop/invoice.pdf                                │
│ Actor: Human                                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 2: Filesystem Watcher detects                              │
│ Location: Orchestrator runs Filesystem Watcher                  │
│ Action: Creates metadata in Needs_Action/                       │
│ Moves: Drop/ → Drop_History/ (with hash in filename)            │
│ Actor: Filesystem Watcher (managed by Orchestrator)             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 3: Folder Watcher detects new task                         │
│ Location: Needs_Action/                                         │
│ Action: Orchestrator callback fired                             │
│ Actor: Folder Watcher → Orchestrator                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 4: Orchestrator moves to Processing/                       │
│ Action: Move file, record timestamp                             │
│ Records: file_move_times[task_file] = datetime.now()            │
│ Actor: Orchestrator                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 5: Orchestrator calls Claude Runner                        │
│ Command: python claude_runner.py Processing/FILE_....md         │
│ Mode: Fire and forget (subprocess, no wait)                     │
│ Actor: Orchestrator                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 6: Claude Runner processes task                            │
│ 1. Reads task file                                              │
│ 2. Loads CLAUDE.md (system prompt)                              │
│ 3. Loads Business_Goals.md, Company_Handbook.md                 │
│ 4. Invokes Claude Code                                          │
│ 5. Claude outputs JSON decision                                 │
│ 6. Claude Runner parses JSON                                    │
│ 7. Claude Runner moves file based on decision:                  │
│    - If approval needed: → Pending_Approval/                    │
│    - If simple task: → Done/                                    │
│    - If needs revision: → Needs_Revision/                       │
│ Actor: Claude Runner (standalone script)                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 7: Folder Watcher detects file movement                    │
│ Location: Processing/                                           │
│ Event: File deleted/moved (disappeared from Processing/)        │
│ Action: Orchestrator callback fired                             │
│ Orchestrator: Removes from file_move_times (timeout cancelled)  │
│ Actor: Folder Watcher → Orchestrator                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 8: Timeout Check (every 1 minute)                          │
│ Checks: All files in file_move_times                            │
│ Condition: elapsed_time > timeout_seconds (300 seconds)         │
│ If TRUE: Claude crashed → Move back to Needs_Action/            │
│ If FALSE: Claude still working → Do nothing                     │
│ Actor: Orchestrator                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 9a: File in Pending_Approval/                              │
│ Status: Waiting for human review                                │
│ Folder Watcher: Detects file creation                           │
│ Actor: Folder Watcher → Orchestrator (logs, tracks)             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 10a: Human reviews approval                                │
│ Options:                                                        │
│   A) Approve: Move to Approved/                                 │
│   B) Reject: Move to Rejected/                                  │
│   C) Revision: Move to Needs_Revision/ with comment             │
│ Actor: Human                                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 11a: If APPROVED                                           │
│ Folder Watcher: Detects file in Approved/                       │
│ Orchestrator: Executes approved action (via MCP or direct)      │
│ Moves: Approved/ → Done/                                        │
│ Logs: Action executed                                           │
│ Actor: Orchestrator                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 11b: If REJECTED                                           │
│ Folder Watcher: Detects file in Rejected/                       │
│ Orchestrator: Logs rejection, updates learning log              │
│ Records: Rejection reason (if provided)                         │
│ Moves: Rejected/ → Done/ (status: rejected)                     │
│ Actor: Orchestrator                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 11c: If NEEDS REVISION                                     │
│ Folder Watcher: Detects file in Needs_Revision/                 │
│ Orchestrator: Moves to Needs_Action/ (HIGH priority)            │
│ Adds metadata: revision_of, revision_note                       │
│ Loop: Goes back to STEP 3                                       │
│ Actor: Orchestrator                                             │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ STEP 12: Task Complete                                          │
│ Location: Done/                                                 │
│ Logs: Timeline + Task log updated                               │
│ Dashboard: Metrics updated                                      │
│ Actor: Orchestrator                                             │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⚙️ Settings Reference

### **1. Task Processing**

| Setting | Value | Status | Notes |
|---------|-------|--------|-------|
| **Processing Mode** | Sequential (one at a time) | ✅ Finalized | Processing/ holds max 1 file |
| **Priority Method** | YAML frontmatter `priority:` field | ✅ Finalized | urgent > high > normal > low |
| **Priority Fallback** | Filename keywords (urgent, asap, invoice) | ✅ Finalized | If no YAML field |
| **Filesystem Watcher** | Managed by Orchestrator | ✅ Finalized | Runs in separate thread |
| **Folder Watcher** | Generic, Orchestrator-managed | ✅ Finalized | Watches workflow folders |
| **Enable Flag** | `ENABLE_FILESYSTEM_WATCHER` | ✅ Finalized | Set in .env file |
| **Timeout Check Interval** | Every 60 seconds | ✅ Finalized | Orchestrator checks file_move_times |

---

### **2. Timeout & Retry**

| Setting | Value | Status | Notes |
|---------|-------|--------|-------|
| **Claude Timeout** | 300 seconds (5 minutes) | ✅ Finalized | Before assuming crash |
| **Timeout Check Interval** | Every 60 seconds | ✅ Finalized | Orchestrator checks file_move_times |
| **Max Retries** | 3 attempts | ⏳ Pending | Before moving to Needs_Revision/ |
| **Retry Delay** | Exponential backoff | ⏳ Pending | 1min, 2min, 4min |
| **Stuck Task Action** | Move back to Needs_Action/ | ✅ Finalized | With error note |
| **Timeout Detection** | File stays in Processing/ + timeout | ✅ Finalized | No watcher event = crash |

---

### **3. Claude Output & File Movement**

| Setting | Value | Status | Notes |
|---------|-------|--------|-------|
| **Decision Format** | JSON Block | ✅ Finalized | Easy to parse, human-readable |
| **Output Location** | Console stdout | ✅ Finalized | claude_runner.py parses |
| **Error Format** | JSON with error field | ✅ Finalized | `{"error": "message"}` |
| **File Movement** | Claude Runner moves after Claude | ✅ Finalized | Option B |
| **Completion Signal** | File disappearance from Processing/ | ✅ Finalized | No .complete files needed |

**Example JSON Output:**
```json
{
  "decision": "create_approval_request",
  "type": "payment",
  "amount": 500.00,
  "recipient": "Client A",
  "reason": "Invoice #123 payment",
  "metadata": {
    "invoice_number": "123",
    "due_date": "2026-03-30"
  }
}
```

**Special Decisions:**
```json
{"decision": "complete_task"}
{"decision": "create_approval_request", ...}
{"decision": "needs_revision", "reason": "..."}
{"decision": "error", "message": "..."}
```

**Claude Runner File Movement:**
```python
# claude_runner.py parses Claude's JSON output
if decision == "create_approval_request":
    # Create file in Pending_Approval/
    create_approval_file(decision.metadata)
    # Move task from Processing/ to Pending_Approval/
    shutil.move(task_file, f'Pending_Approval/{os.path.basename(task_file)}')

elif decision == "complete_task":
    # Move task from Processing/ to Done/
    shutil.move(task_file, f'Done/{os.path.basename(task_file)}')

elif decision == "needs_revision":
    # Move task from Processing/ to Needs_Revision/
    shutil.move(task_file, f'Needs_Revision/{os.path.basename(task_file)}')
```

---

### **4. File Ownership & Locking**

| Setting | Value | Status | Notes |
|---------|-------|--------|-------|
| **Locking Method** | Move-based locking | ✅ Finalized | File location = state |
| **Claim Tracking** | Implicit (by file location) | ✅ Finalized | No separate claim files |
| **Race Condition Prevention** | Atomic file moves | ✅ Finalized | OS-level atomic |
| **Timeout Tracking** | file_move_times dictionary | ✅ Finalized | Tracks when file moved to Processing/ |

---

### **5. Folder Watching (Event-Driven, No Polling)**

| Folder | Watch Method | Orchestrator Action on Detect |
|--------|-------------|-------------------------------|
| **Needs_Action/** | Folder Watcher (on_created) | Move to Processing/, record timestamp, call Claude Runner |
| **Processing/** | Folder Watcher (on_deleted/on_moved) | Remove from file_move_times (timeout cancelled) |
| **Pending_Approval/** | Folder Watcher (on_created) | Log, track (waits for human) |
| **Approved/** | Folder Watcher (on_created) | Execute action, move to Done/ |
| **Rejected/** | Folder Watcher (on_created) | Log rejection, update learning log, archive |
| **Needs_Revision/** | Folder Watcher (on_created) | Move to Needs_Action/ (HIGH priority) |

**Timeout Check (Every 60 Seconds):**
```python
# Orchestrator checks file_move_times
for file_path, move_time in list(self.file_move_times.items()):
    elapsed = (datetime.now() - move_time).seconds
    if elapsed > 300:  # 5 minutes
        # No watcher event = Claude crashed!
        move_back_to_needs_action(file_path)
        del self.file_move_times[file_path]
```

---

### **6. Claude Learning & Feedback**

| Setting | Value | Status | Notes |
|---------|-------|--------|-------|
| **Rejection Tracking** | Separate log file | ⏳ Pending | Track patterns |
| **Learning Log Location** | Logs/claude_rejections_YYYY-MM-DD.md | ⏳ Pending | Daily logs |
| **Feedback to Claude** | Include in CLAUDE.md context | ⏳ Pending | Recent rejections |
| **Review Frequency** | Weekly | ⏳ Pending | Human reviews patterns |

---

### **7. Action Execution**

| Setting | Value | Status | Notes |
|---------|-------|--------|-------|
| **Simple Actions** | Orchestrator executes | ⏳ Pending | File moves, renames |
| **Complex Actions** | Claude Runner executes | ⏳ Pending | MCP server calls |
| **Payment Actions** | Always via Claude Runner + MCP | ✅ Finalized | Safety requirement |
| **Email Actions** | Via Claude Runner + MCP | ⏳ Pending | Or direct SMTP? |
| **Social Media** | Via Claude Runner + MCP | ⏳ Pending | Draft first, approve |

---

## 📁 Folder Specifications (Updated)

### **Needs_Action/**

| Attribute | Value |
|-----------|-------|
| **Purpose** | Main task queue (all pending tasks) |
| **Watch Method** | Folder Watcher (on_created event) |
| **Selection Logic** | First created event (sequential processing) |
| **File Format** | Markdown with YAML frontmatter |
| **YAML Fields** | `type`, `task_id`, `priority`, `status`, `detected` |

**Priority Values:**
- `urgent` - Process immediately (top of queue)
- `high` - Process before normal tasks
- `normal` - Default priority
- `low` - Process when nothing else pending

---

### **Processing/**

| Attribute | Value |
|-----------|-------|
| **Purpose** | Currently being processed by Claude |
| **Capacity** | 1 file at a time (sequential processing) |
| **Watch Method** | Folder Watcher (on_deleted/on_moved) |
| **Timeout** | 300 seconds (5 minutes) |
| **Timeout Detection** | File stays + timeout reached + no watcher event |
| **On Timeout** | Move back to Needs_Action/, increment retry count |
| **Max Retries** | 3 (pending) - then move to Needs_Revision/ |

**Edge Cases:**
- **Claude crashes:** File stays in Processing/ → Timeout triggers → Move back
- **File corrupted:** Move to Needs_Revision/ with error note
- **API rate limit:** Retry with backoff, timeout if exceeds limit

**Timeout Logic (Inside Orchestrator):**
```python
# When file moves to Processing/
self.file_move_times[file_path] = datetime.now()

# When Folder Watcher detects file left Processing/
if event_type in ['deleted', 'moved']:
    if file_path in self.file_move_times:
        del self.file_move_times[file_path]  # Timeout cancelled!

# Every 60 seconds, check timeouts
for file_path, move_time in list(self.file_move_times.items()):
    elapsed = (datetime.now() - move_time).seconds
    if elapsed > 300:
        # No watcher event = Claude crashed!
        move_back_to_needs_action(file_path)
```

---

### **Pending_Approval/**

| Attribute | Value |
|-----------|-------|
| **Purpose** | Awaiting human approval |
| **Created By** | Claude Runner (when Claude decides approval needed) |
| **Watch Method** | Folder Watcher (on_created) |
| **Human Actions** | Move to Approved/, Rejected/, or Needs_Revision/ |
| **Timeout** | None (waits indefinitely for human) |
| **Expiry** | Optional (configurable per task type) |

**File Naming:**
```
APPROVAL_{type}_{description}_{timestamp}.md

Examples:
- APPROVAL_payment_client_A_invoice123.md
- APPROVAL_email_new_client_proposal.md
```

**Human Decision Flow:**
```
Human sees file in Pending_Approval/
    ↓
Reviews details (amount, reason, metadata)
    ↓
Decision:
  - Approve → Move to Approved/
  - Reject → Move to Rejected/ (optional: add reason)
  - Revise → Move to Needs_Revision/ (must add comment)
```

---

### **Approved/**

| Attribute | Value |
|-----------|-------|
| **Purpose** | Approved actions ready for execution |
| **Created By** | Human (moves from Pending_Approval/) |
| **Watch Method** | Folder Watcher (on_created) |
| **Executor** | Orchestrator (simple) or Claude Runner (complex) |
| **Timeout** | 60 seconds (should execute quickly) |
| **On Failure** | Move back to Pending_Approval/ with error |

**Execution Flow:**
```
Folder Watcher detects file in Approved/
    ↓
Orchestrator parses approval request
    ↓
Determines execution method:
  - Simple (file op): Execute directly
  - Complex (payment, email): Call claude_runner.py
    ↓
Executes action
    ↓
Success: Move to Done/
Failure: Move back to Pending_Approval/ with error note
```

---

### **Rejected/**

| Attribute | Value |
|-----------|-------|
| **Purpose** | Human-rejected tasks |
| **Created By** | Human (moves from Pending_Approval/) |
| **Watch Method** | Folder Watcher (on_created) |
| **Action on Detect** | Log rejection, update learning log, archive |
| **Retention** | Indefinite (audit trail) |

**Rejection Logging:**
```markdown
# Rejection Log: 2026-03-19

## Rejected Task: APPROVAL_payment_client_A_invoice123

**Rejected At:** 2026-03-19 10:30:00  
**Rejected By:** Human (username)  
**Reason:** (if provided by human)

**Original Request:**
- Type: Payment
- Amount: $500
- Recipient: Client A

**Learning:**
- Claude should verify PO before requesting approval
- Client A has new payment terms (net-60, not net-30)
```

---

### **Needs_Revision/**

| Attribute | Value |
|-----------|-------|
| **Purpose** | Tasks needing rework/correction |
| **Created By** | Human (moves from Pending_Approval/) or Orchestrator (on max retries) |
| **Watch Method** | Folder Watcher (on_created) |
| **Action on Detect** | Move to Needs_Action/ with HIGH priority |
| **Human Comment** | Required (explains what needs fixing) |

**Revision Flow:**
```
Human moves file to Needs_Revision/
    ↓
Adds comment: "Fix tone, add signature, verify numbers"
    ↓
Folder Watcher detects (real-time)
    ↓
Orchestrator moves to Needs_Action/ with priority=urgent
    ↓
Adds metadata: revision_of: [original_task_id], revision_note: [human comment]
    ↓
Next Folder Watcher event: Picks up as urgent task
    ↓
Claude reprocesses with revision context
```

---

### **Done/**

| Attribute | Value |
|-----------|-------|
| **Purpose** | Completed tasks archive |
| **Created By** | Orchestrator (moves here after completion) |
| **Retention** | 90 days (then auto-archived) |
| **Status Values** | `completed`, `rejected`, `cancelled` |

**Completion Logging:**
```markdown
## Task Completed: file_20260319_103000_invoice.pdf

**Completed At:** 2026-03-19 10:35:00  
**Processing Time:** 5 minutes 10 seconds  
**Result:** Payment approved and processed  
**Approver:** Human (username)  
**Execution:** Via MCP payment server  
```

---

## 🔒 Edge Case Handling (Updated)

### **Edge Case 1: Claude Crashes Mid-Task**

**Detection:**
- File stays in Processing/ > 300 seconds (5 minutes)
- Folder Watcher did NOT fire on_deleted/on_moved
- Timeout check detects elapsed time > timeout

**Recovery:**
```
Orchestrator timeout check (every 60 seconds)
    ↓
Detects: file_move_times[file] > 300 seconds
    ↓
Checks: Folder Watcher did not fire (file still in Processing/)
    ↓
Assumes: Claude crashed
    ↓
Moves: Processing/ → Needs_Action/
    ↓
Adds note: "Claude crashed, retry 1/3"
    ↓
Increments: retry_count metadata field
```

**After 3 Failures:**
```
retry_count >= 3
    ↓
Move: Needs_Action/ → Needs_Revision/
    ↓
Adds note: "Failed 3 times, needs human review"
```

**Why This Works:**
- ✅ If Claude succeeds → File moves out → Folder Watcher fires → Removed from file_move_times
- ✅ If Claude crashes → File stays → No watcher event → Timeout triggers
- ✅ No polling every 30 seconds → Check every 60 seconds is enough
- ✅ Timeout logic inside Orchestrator → Centralized control

---

### **Edge Case 2: File Corrupted**

**Detection:**
- Can't read YAML frontmatter
- Can't parse metadata
- File is empty or binary

**Recovery:**
```
Claude Runner detects corruption
    ↓
Moves: Current location → Needs_Revision/
    ↓
Adds note: "File corrupted, can't read metadata"
    ↓
Alerts: Human (via log or notification)
```

---

### **Edge Case 3: API Rate Limit**

**Detection:**
- Claude API returns 429 (Too Many Requests)
- MCP server returns rate limit error

**Recovery:**
```
claude_runner.py catches rate limit error
    ↓
Waits: Exponential backoff (1min, 2min, 4min)
    ↓
Retries: Up to 3 attempts
    ↓
If still rate limited:
  - Moves: Processing/ → Needs_Action/
  - Adds note: "Rate limited, retry in 15 minutes"
  - Sets: retry_after timestamp
```

---

### **Edge Case 4: Human Never Reviews Approval**

**Detection:**
- File in Pending_Approval/ > 24 hours (configurable)

**Recovery:**
```
Orchestrator polls Pending_Approval/ metadata (every 60 seconds via Folder Watcher)
    ↓
Detects: File age > 24 hours
    ↓
Logs: "Approval pending > 24 hours"
    ↓
Optionally: Sends reminder to human
    ↓
Continues: Waiting (no automatic action)
```

---

### **Edge Case 5: Duplicate File Detected**

**Detection:**
- Hash matches existing entry in .hash_registry.json
- Same task_id already processed

**Recovery:**
```
Filesystem Watcher detects duplicate hash
    ↓
Moves: Drop/ → Drop_History/ (with duplicate suffix)
    ↓
Does NOT create Needs_Action/ entry
    ↓
Logs: "Duplicate file skipped: [filename]"
```

---

## 📊 State Machine (Updated v2.0)

```
┌─────────────────────────────────────────────────────────────────┐
│ Filesystem Watcher (managed by Orchestrator)                    │
│ Watches: Inbox/Drop/                                            │
│ Action: Creates task in Needs_Action/                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Folder Watcher: Needs_Action/ (on_created)                      │
│ Action: Move to Processing/, record timestamp                   │
│ Track: file_move_times[file] = datetime.now()                   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Orchestrator calls Claude Runner                                │
│ Command: python claude_runner.py Processing/FILE_....md         │
│ Mode: Fire and forget                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Claude Runner processes                                         │
│ 1. Reads task, loads CLAUDE.md, etc.                            │
│ 2. Invokes Claude Code                                          │
│ 3. Parses JSON output                                           │
│ 4. Moves file based on decision:                                │
│    - complete_task → Done/                                      │
│    - create_approval_request → Pending_Approval/                │
│    - needs_revision → Needs_Revision/                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Folder Watcher: Processing/ (on_deleted/on_moved)               │
│ Detects: File disappeared from Processing/                      │
│ Action: Remove from file_move_times (timeout cancelled)         │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ Timeout Check (every 60 seconds)                                │
│ for file_path, move_time in file_move_times.items():            │
│   if (now - move_time).seconds > 300:                           │
│     # No watcher event = Claude crashed!                        │
│     move_back_to_needs_action(file_path)                        │
│     del file_move_times[file_path]                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ If file in Pending_Approval/                                    │
│ Folder Watcher detects creation                                 │
│ Human reviews → moves to:                                       │
│   - Approved/ → Orchestrator executes → Done/                   │
│   - Rejected/ → Log rejection → Done/ (rejected)                │
│   - Needs_Revision/ → High priority → Needs_Action/             │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⏳ Pending Decisions

### **Pending 1: Max Retries**

**Question:** How many times to retry failed tasks?

**Options:**
- 3 attempts (standard)
- 5 attempts (more resilient)
- Unlimited with backoff (never give up)

**Impact:**
- More retries → Higher success rate, but may loop forever
- Fewer retries → Faster to Needs_Revision/, but may give up too soon

**Decision Needed:** [ ] 3 [ ] 5 [ ] Unlimited

---

### **Pending 2: Claude Learning Log Location**

**Question:** Where to track rejections for Claude learning?

**Options:**
- `vault/Claude_Learning_Log.md` (single file)
- `Logs/claude_rejections_YYYY-MM-DD.md` (daily logs)
- `vault/CLAUDE.md` appendix (auto-update main file)

**Impact:**
- Single file → Easy to reference, but grows large
- Daily logs → Organized, but scattered
- Appendix to CLAUDE.md → Always in context, but clutters main file

**Decision Needed:** [ ] Single file [ ] Daily logs [ ] CLAUDE.md appendix

---

### **Pending 3: Action Execution Method**

**Question:** Who executes approved actions?

**Options:**
- Orchestrator executes all (simpler, but limited)
- Claude Runner executes complex, Orchestrator does simple (hybrid)
- Separate `action_executor.py` (clean separation, more complex)

**Impact:**
- Orchestrator only → Simpler, but needs execution logic
- Hybrid → Best of both, but more coordination
- Separate executor → Clean, but another component

**Decision Needed:** [ ] Orchestrator [ ] Hybrid [ ] Separate executor

---

## 📝 Configuration Files Reference

| File | Purpose | Updated By | Read By |
|------|---------|------------|---------|
| `vault/CLAUDE.md` | System prompt, role, rules | Human | Claude (auto-load) |
| `vault/Business_Goals.md` | Q1/Q2 targets, metrics | Human (quarterly) | Claude (reference) |
| `vault/Company_Handbook.md` | Policies, procedures | Human (as needed) | Claude (reference) |
| `.env` | Environment variables | Human | All scripts |
| `core/config.py` | Python settings | Human | Python scripts |

---

## 🔄 Next Steps

### **Ready to Implement (Finalized Settings):**
- [ ] Create `watchers/folder_watcher.py` (generic folder watcher)
- [ ] Create `claude_runner.py` (Claude Code executor, moves files)
- [ ] Update `orchestrator.py` (manage both watchers, timeout logic)
- [ ] Enhance `vault/CLAUDE.md` (system prompt + role)
- [ ] Create `vault/Business_Goals.md` (Q1 2026 targets)
- [ ] Create `vault/Company_Handbook.md` (policies & rules)

### **Pending Discussion (Awaiting Decisions):**
- [ ] Max retries (3/5/unlimited)
- [ ] Learning log location
- [ ] Action execution method

---

**Last Updated:** 2026-03-19  
**Version:** 2.0 (Architecture Finalized)  
**Next Review:** After pending decisions are finalized

---

*For questions or updates, refer to RULES.md or contact the project maintainer.*
