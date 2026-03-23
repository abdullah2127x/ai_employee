# AI Employee — Improvement Handoff Guide

**Date:** 2026-03-23
**Purpose:** Drop-in replacement files for the existing AI Employee system.
**Who reads this:** The AI coding assistant implementing these changes.

---

## What Changed and Why

### The Core Problem with v1

The old system had one fundamental issue: Python was doing Claude's job, and
Claude was doing Python's job.

- **Python** was loading context files, building giant prompts, and managing
  Claude's "knowledge" — this is Claude's job.
- **Claude** was filling template placeholders with structured values — this is
  Python's job (string formatting).

### The v2 Fix

- **Claude** reads its own context (CLAUDE.md auto-loaded, skills read on demand,
  Business_Goals.md and Company_Handbook.md read by Claude via skill instructions).
- **Python** builds the output file from Claude's JSON — clean string formatting,
  no regex replacement of `[PENDING]` placeholders.

---

## Files in This Package

```
ai_employee_improved/
├── vault/
│   ├── CLAUDE.md                                    ← REPLACE existing vault/CLAUDE.md
│   └── .claude/
│       └── skills/
│           ├── process-file-drop/
│           │   └── SKILL.md                         ← NEW — create this
│           └── process-general/
│               └── SKILL.md                         ← NEW — create this
├── claude_runner.py                                 ← REPLACE existing claude_runner.py
└── task_template.py                                 ← REPLACE existing utils/task_template.py
```

---

## Integration Instructions

### 1. vault/CLAUDE.md

**Action:** Replace the existing `vault/CLAUDE.md` entirely.

**What changed:**
- Removed all context file content (Business_Goals, Company_Handbook) — Claude
  now reads these itself via skill instructions
- Added skill routing table — Claude knows which skill to load per task type
- Defined the exact 6-field JSON output schema Claude must return
- Added clear rules about what Claude must NOT do (move files, create files, etc.)

**Important:** Claude Code auto-loads `CLAUDE.md` when run with `cwd=vault/`.
The `invoke_claude()` function in `claude_runner.py` already sets `cwd=vault/`.
Do not inject CLAUDE.md content into the prompt — it will be loaded twice.

---

### 2. vault/.claude/skills/ (new directory)

**Action:** Create the directory `vault/.claude/skills/` and add both skill files.

**How Claude Code finds skills:**
Claude Code looks for skills in `.claude/skills/` relative to the working
directory (vault/ in this case). CLAUDE.md tells Claude which skill file path
to read for each task type. Claude reads the skill as part of its reasoning.

**Skill: process-file-drop/SKILL.md**
- Handles `type: file_drop` tasks
- Instructs Claude to identify file type, classify content, apply payment rules
- Contains examples of correct JSON output for different file types
- Currently handles: text files, code files, binary placeholders
- Future: add PDF extraction, image handling — just update this file

**Skill: process-general/SKILL.md**
- Fallback for any task type without a dedicated skill
- Conservative rules: financial mentions → approval, informational → complete
- Use until dedicated skills exist for email, WhatsApp, etc.

**Adding future skills:**
When a Gmail watcher is built, create:
`vault/.claude/skills/process-email/SKILL.md`
Then update the routing table in `CLAUDE.md` to point to it.

---

### 3. claude_runner.py

**Action:** Replace the existing `claude_runner.py` entirely.

**What changed:**

| Old behavior | New behavior |
|---|---|
| `load_system_prompt()` — reads CLAUDE.md, injects into prompt | Removed — CLAUDE.md auto-loaded by Claude Code |
| `load_context_files()` — reads Business_Goals, Company_Handbook, injects into prompt | Removed — Claude reads these via skill instructions |
| Giant 500+ char prompt with all context embedded | Short 3-line prompt: skill path + task content |
| `fill_ai_placeholders()` — regex replacement of `[PENDING]` | Removed — Python builds output from JSON directly |
| `validate_no_pending_placeholders()` | Removed — no placeholders exist |
| Claude returns JSON, Python moves file based on decision | Same — but cleaner. Python also builds the output file |

**Key function: `build_prompt()`**
```python
def build_prompt(task_file, task_content, task_type):
    skill_path = skill_map.get(task_type, ".claude/skills/process-general/SKILL.md")
    return f"""Process this task using the skill at: {skill_path}
Task file: {task_file.name}
--- TASK CONTENT START ---
{task_content}
--- TASK CONTENT END ---
Return ONLY the JSON decision as defined in CLAUDE.md. No other text."""
```

**Key function: `parse_and_validate()`**
Validates all 6 required fields. Validates enum values match CLAUDE.md exactly.
Normalizes `approval_reason` (Claude sometimes returns string "null").
Raises `ValueError` with a clear message — never silently falls back.

**Key function: `create_and_move_output_file()`**
Calls `build_output_file()` from `task_template.py`.
Determines destination folder from `decision["decision"]`.
Writes output file to dest folder. Moves task file to `Processing_Archive/`.

**Prompt file pattern:**
The runner writes the prompt to `.claude/_runner_prompt.tmp` and reads it with
`$(cat ...)` in the shell command. This avoids shell escaping issues with
multi-line prompts containing quotes, brackets, and special characters.

---

### 4. task_template.py (utils/task_template.py)

**Action:** Replace the existing `utils/task_template.py` entirely.

**What changed:**

| Old | New |
|---|---|
| `BASE_METADATA_TEMPLATE` with `[PENDING]` blocks | Removed entirely |
| `fill_ai_placeholders()` | Removed |
| `validate_no_pending_placeholders()` | Removed |
| `get_pending_count()` | Removed |
| `create_file_drop_metadata()` returns one string | `create_file_drop_task()` returns `(task_id, markdown)` tuple |
| Task file contained AI response sections | Task file is input-only — no AI sections |

**Two responsibilities now:**

1. `create_file_drop_task()` / `create_email_task()` — watcher calls these to
   create the input task file. Returns `(task_id, markdown_string)`.

2. `build_output_file()` — `claude_runner.py` calls this after Claude responds.
   Takes Claude's JSON dict. Returns the output markdown string. Python writes it.

**Content truncation:**
`_truncate_content()` caps text at 3000 chars. This keeps task files small.
Full content is always available in `Drop_History/` via the Obsidian `[[link]]`.

---

## Watcher Update Required

The filesystem watcher needs a small update to use the new `task_template.py`:

```python
# OLD watcher code:
from utils.task_template import create_file_drop_metadata
metadata_content = create_file_drop_metadata(
    original_name=src_path.name,
    ...
)
metadata_path.write_text(metadata_content)

# NEW watcher code:
from utils.task_template import create_file_drop_task
task_id, task_content = create_file_drop_task(
    original_name=src_path.name,
    original_path=drop_history / src_path.name,
    content=extracted_text,          # "" for binary files
    content_type="text",             # "text" | "binary"
    file_extension=src_path.suffix,
    file_hash=file_hash,
    size_bytes=src_path.stat().st_size,
    priority=determine_priority(src_path),
    timestamp=datetime.now(),
)
task_filename = f"{task_id}.md"
task_path = needs_action / task_filename
task_path.write_text(task_content, encoding="utf-8")
```

Note that `task_id` is now returned by the function — use it as the filename.
This ensures the task ID in the frontmatter always matches the filename.

---

## Folder Structure (Complete)

```
vault/
├── CLAUDE.md                        ← AI Employee instructions (auto-loaded)
├── Business_Goals.md                ← Claude reads this via skill instructions
├── Company_Handbook.md              ← Claude reads this via skill instructions
│
├── .claude/
│   └── skills/
│       ├── process-file-drop/
│       │   └── SKILL.md
│       └── process-general/
│           └── SKILL.md
│
├── Drop/                            ← User drops files here
├── Drop_History/                    ← Original files moved here by watcher
├── Needs_Action/                    ← Watcher creates task files here
├── Processing/                      ← Orchestrator moves task files here
├── Processing_Archive/              ← Processed task files archived here (NEW)
├── Pending_Approval/                ← Output files needing human review
├── Approved/                        ← Human moves files here to approve
├── Rejected/                        ← Human moves files here to reject
├── Needs_Revision/                  ← Failed or unclear tasks
└── Done/                            ← Completed output files
```

`Processing_Archive/` is new — keeps `Processing/` clean while preserving
the original task file for audit purposes.

---

## JSON Contract (CLAUDE.md ↔ claude_runner.py)

This contract is defined in `vault/CLAUDE.md` and enforced by `parse_and_validate()`.
If you change one, change both.

```json
{
  "decision":        "complete_task" | "create_approval_request" | "needs_revision",
  "category":        "general" | "invoice" | "payment" | "email" | "document" | "urgent",
  "summary":         "One sentence summary of task and decision",
  "action_taken":    "One sentence — what Claude did or determined",
  "response":        "Full details, extracted data, reasoning, next steps",
  "approval_reason": "Why human approval needed (string) OR null"
}
```

`approval_reason` must be a non-null string when `decision` is `create_approval_request`.
`approval_reason` must be `null` when `decision` is anything else.

---

## What NOT to Change

- Do not add context file loading back to `claude_runner.py` — Claude reads them
- Do not add `[PENDING]` placeholders back to task files — they are input-only now
- Do not change `cwd` in `invoke_claude()` — must stay `vault/` for CLAUDE.md auto-load
- Do not rename the 6 JSON fields — `parse_and_validate()` and `CLAUDE.md` must match

---

## Testing Checklist

After integration, verify:

- [ ] Drop a `.txt` file → task file created in `Needs_Action/` with correct frontmatter
- [ ] Run `claude_runner.py` on the task file → Claude returns valid JSON
- [ ] `parse_and_validate()` does not raise → output file created in `Done/`
- [ ] Drop a fake invoice with amount > $100 → output file lands in `Pending_Approval/`
- [ ] Drop a binary file → `content_type: binary` in frontmatter, `needs_revision` decision
- [ ] Verify `CLAUDE.md` is NOT being injected into the prompt (check log output)
- [ ] Verify `Business_Goals.md` is NOT being loaded by Python (check log output)

---

*Handoff generated 2026-03-23*