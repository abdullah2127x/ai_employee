# Central Task Template Analysis

**Date:** 2026-03-25  
**Subject:** Should Gmail IMAP Watcher use central `task_template.py`?

---

## 🔄 Complete System Flow

### File System Watcher Flow (Uses Central Template)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. FILE DROP DETECTED                                          │
│    watchers/filesystem_watcher.py                               │
│    ↓                                                            │
│    from utils.task_template import create_file_drop_task()      │
│    ↓                                                            │
│    Creates: vault/Needs_Action/file_drop_*.md                   │
│    Format: Central template (minimal fields)                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. ORCHESTRATOR MOVES TO PROCESSING                            │
│    orchestrator.py                                              │
│    - Moves file: Needs_Action/ → Processing/                    │
│    - Starts claude_runner subprocess                            │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. CLAUDE RUNNER PROCESSES                                     │
│    claude_runner.py                                             │
│    ↓                                                            │
│    from utils.task_template import read_frontmatter()           │
│    ↓                                                            │
│    Reads: type, original_name, original_path                    │
│    ↓                                                            │
│    Invokes Claude with task content                             │
│    ↓                                                            │
│    Gets JSON decision from Claude                               │
│    ↓                                                            │
│    from utils.task_template import build_output_file()          │
│    ↓                                                            │
│    Creates: vault/Done/RESULT_*.md (or Pending_Approval/)       │
│    Format: Central template output                              │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 4. ORCHESTRATOR READS RESULT                                   │
│    orchestrator.py                                              │
│    - Reads Runner_Status/*.json                                 │
│    - Moves files based on outcome                               │
│    - Cleans up Processing/                                      │
└─────────────────────────────────────────────────────────────────┘
```

### Gmail IMAP Watcher Flow (Currently Custom Format)

```
┌─────────────────────────────────────────────────────────────────┐
│ 1. EMAIL DETECTED                                              │
│    watchers/gmail_watcher_imap.py                               │
│    ↓                                                            │
│    CUSTOM: create_action_file() method                          │
│    ↓                                                            │
│    Creates: vault/Needs_Action/email_*.md                       │
│    Format: Comprehensive custom (20+ fields)                    │
│    - filter_reason, is_reply, gmail_message_id, gmail_link      │
│    - AI Processing Status section                               │
│    - Email Information table                                    │
│    - Instructions for AI                                        │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 2. ORCHESTRATOR MOVES TO PROCESSING                            │
│    orchestrator.py                                              │
│    - Same as file drop flow                                     │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ 3. CLAUDE RUNNER PROCESSES                                     │
│    claude_runner.py                                             │
│    ↓                                                            │
│    from utils.task_template import read_frontmatter()           │
│    ↓                                                            │
│    Reads: type, subject, from (basic fields)                    │
│    ↓                                                            │
│    ⚠️ EXTRA FIELDS IGNORED: filter_reason, is_reply, etc.       │
│    ↓                                                            │
│    Invokes Claude with task content                             │
│    ↓                                                            │
│    Gets JSON decision from Claude                               │
│    ↓                                                            │
│    from utils.task_template import build_output_file()          │
│    ↓                                                            │
│    Creates: vault/Done/RESULT_*.md                              │
│    ⚠️ CUSTOM FIELDS LOST: ai_status, filter_reason, etc.        │
└─────────────────────────────────────────────────────────────────┘
```

---

## 📊 Template Usage Analysis

### Where `task_template.py` Functions Are Used

| Function | Used By | Purpose |
|----------|---------|---------|
| `create_file_drop_task()` | filesystem_watcher.py | Create file drop task files |
| `create_email_task()` | gmail_watcher_oauth.py | Create email task files (simple) |
| `create_whatsapp_task()` | (not used yet) | Create WhatsApp task files |
| `read_frontmatter()` | claude_runner.py | Read YAML frontmatter from any task |
| `build_output_file()` | claude_runner.py | Build output file from Claude's decision |
| `increment_retry_count()` | orchestrator.py | Increment retry count in Needs_Revision |

### Key Insight

**The central template is used at TWO stages:**

1. **INPUT Stage** (Watchers → Needs_Action/)
   - `create_*_task()` functions
   - Creates minimal task files for Claude to process

2. **OUTPUT Stage** (Claude Runner → Done/)
   - `read_frontmatter()` + `build_output_file()`
   - Reads task file, builds output from Claude's JSON

**What Claude Runner Actually Uses:**
```python
# From claude_runner.py
meta = read_frontmatter(task_content)

# Fields it reads:
task_id = meta.get("task_id")
task_type = meta.get("type")
file_name = meta.get("original_name") or meta.get("subject")
orig_path = meta.get("original_path", "")

# That's it! Only 4 fields!
```

---

## 🎯 The Real Question

### Should Gmail IMAP Watcher Use Central Template?

**Option A: Use `create_email_task()` from Central Template**

**Pros:**
- ✅ Consistent with file system watcher
- ✅ Consistent with Gmail OAuth watcher
- ✅ Single source of truth
- ✅ Easier maintenance

**Cons:**
- ❌ Loses all Gmail-specific fields:
  - `filter_reason` - Why was this email selected?
  - `is_reply` - Thread detection
  - `gmail_message_id` - Permanent Gmail ID
  - `gmail_link` - Direct link to email
  - `ai_status` fields - AI processing tracking
  - Email Information table
  - Instructions for AI section

**Verdict:** ❌ **NOT SUITABLE** - Central template is too minimal

---

**Option B: Keep Custom Format (Current Approach)**

**Pros:**
- ✅ All Gmail-specific features preserved
- ✅ Rich metadata for AI processing
- ✅ Thread awareness
- ✅ Filter transparency
- ✅ Gmail integration (links, IDs)

**Cons:**
- ❌ Inconsistent with other watchers
- ❌ Duplicate code (template logic)
- ❌ More maintenance burden

**Verdict:** ✅ **BETTER** but could be improved

---

**Option C: Enhanced Central Template (Recommended)**

Add new function to `task_template.py`:
```python
def create_email_task_enhanced(
    from_address: str,
    to_address: str,
    subject: str,
    content: str,
    timestamp: datetime,
    priority: str,
    filter_reason: str,
    is_reply: bool,
    gmail_message_id: str,
    gmail_link: str,
) -> Tuple[str, str]:
    """
    Create enhanced email task file with Gmail-specific metadata.
    
    Includes:
    - filter_reason: Why this email was selected
    - is_reply: Thread detection
    - gmail_message_id: Permanent Gmail ID
    - gmail_link: Direct link to email
    - AI Processing Status section
    """
```

**Pros:**
- ✅ Central location (single source of truth)
- ✅ All Gmail features preserved
- ✅ Can be used by both Gmail watchers
- ✅ Consistent across project
- ✅ Easier long-term maintenance

**Cons:**
- ⚠️ Requires updating `task_template.py`
- ⚠️ Gmail IMAP watcher still needs custom sections (Instructions for AI)

**Verdict:** ✅ **BEST** - Combines benefits of both approaches

---

## 🔍 What Fields Does Claude Runner Actually Need?

### Fields Read by `read_frontmatter()` in claude_runner.py:

```python
meta = read_frontmatter(task_content)
task_id = meta.get("task_id")           # ✅ Used
task_type = meta.get("type")            # ✅ Used
file_name = meta.get("original_name") or meta.get("subject")  # ✅ Used
orig_path = meta.get("original_path", "")  # ✅ Used (but empty for email)
```

### Fields Passed to `build_output_file()`:

```python
output_md = build_output_file(
    task_id=task_id,                    # ✅ From frontmatter
    task_type=task_type,                # ✅ From frontmatter
    original_name=file_name,            # ✅ From frontmatter
    original_path_obsidian=orig_path,   # ✅ From frontmatter (empty for email)
    decision=decision,                  # ✅ From Claude's JSON
    processed_at=processed_at,          # ✅ Generated
)
```

### Gmail IMAP Custom Fields (NOT used by Claude Runner):

```python
filter_reason         # ❌ Not read by claude_runner
is_reply              # ❌ Not read by claude_runner
gmail_message_id      # ❌ Not read by claude_runner
gmail_link            # ❌ Not read by claude_runner
ai_status             # ❌ Not read by claude_runner
ai_processed_at       # ❌ Not read by claude_runner
ai_decision           # ❌ Not read by claude_runner
ai_category           # ❌ Not read by claude_runner
ai_summary            # ❌ Not read by claude_runner
```

**Key Insight:** Claude Runner only cares about **4 fields** from frontmatter!

---

## 💡 Recommended Approach

### Update `task_template.py` with Enhanced Email Function

**Why:**
1. Gmail IMAP watcher needs fields that central template doesn't provide
2. These fields are IMPORTANT for Gmail workflow (filtering, threads, links)
3. Claude Runner doesn't use these fields, but HUMANS do (for tracking)
4. Central template should support all use cases

**What to Add:**
```python
def create_email_task_enhanced(
    from_address: str,
    to_address: str,
    subject: str,
    content: str,
    timestamp: datetime,
    priority: str,
    filter_reason: str = "",
    is_reply: bool = False,
    gmail_message_id: str = "",
    gmail_link: str = "",
) -> Tuple[str, str]:
    """
    Enhanced email task template with Gmail-specific metadata.
    
    For use with smart filtering and thread detection.
    """
```

**Keep Custom Sections:**
- "Instructions for AI" section (Gmail-specific)
- "Email Information" table (Gmail-specific)
- AI Processing Status fields (Gmail-specific)

These can be added to the returned string by `create_action_file()` after calling the template function.

---

## 📝 Implementation Plan

### Phase 1: Update `task_template.py`
- Add `create_email_task_enhanced()` function
- Include all Gmail-specific fields in frontmatter
- Keep backward compatible with existing `create_email_task()`

### Phase 2: Update Gmail IMAP Watcher
- Call `create_email_task_enhanced()` for basic structure
- Append custom sections (Instructions, AI Status, etc.)
- Maintain all current functionality

### Phase 3: Update Gmail OAuth Watcher (Optional)
- Migrate to `create_email_task_enhanced()` if needed
- Or keep using simple `create_email_task()`

---

## ✅ Conclusion

**Current State:**
- Gmail IMAP watcher uses custom format (NOT central template)
- This is **correct** because central template is too minimal
- Claude Runner only uses 4 fields, but Gmail needs 10+ fields

**Recommended:**
- Update central `task_template.py` to add enhanced email function
- Gmail IMAP watcher uses enhanced function + custom sections
- Best of both worlds: central template + Gmail-specific features

**Not Recommended:**
- Switching to simple `create_email_task()` - loses critical features
- Keeping completely separate template - harder to maintain

---

**Decision:** Update `task_template.py` with `create_email_task_enhanced()` to support Gmail's advanced features while maintaining central template architecture.
