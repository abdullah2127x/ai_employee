"""
task_template.py - Centralized task file templates for AI Employee

Fixes in v2.2:
- PATH FIX: original_path stored in frontmatter as a clean Obsidian link
  with forward slashes and no double-wrapping.
  Old: original_path: "[[vault\Inbox\Drop_History\greeting4.txt]]"
       → claude_runner read this back and wrapped it again → [[[[...]]]]
       → also backslashes break Obsidian links on Windows
  New: original_path stored as "[[Drop_History/greeting4.txt]]" — just the
       filename within Drop_History, forward slashes only, wrapped once.
       claude_runner passes it straight through to build_output_file() which
       embeds it as-is (no second wrapping).
- build_output_file() no longer wraps original_path_obsidian in [[ ]] —
  the value coming from frontmatter already contains the brackets.

Architecture (v2):
- Task files are INPUT-ONLY — no [PENDING] placeholders
- Claude reads task files and returns JSON decision
- Python builds output files from Claude's JSON using build_output_file()
"""

from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple, Dict, Any


# ============================================================================
# INTERNAL UTILITIES
# ============================================================================


def _format_size(size: int) -> str:
    """Format file size as human-readable string."""
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _make_safe_stem(name: str, max_len: int = 40) -> str:
    """
    Convert a filename into a safe task ID stem (no extension).

    Strips the file extension before using as task_id component.
    Prevents double-extension corruption like "greeting2.txtt.md".

    "greeting2.txt" → "greeting2"
    "invoice #1.pdf" → "invoice__1"
    """
    stem = Path(name).stem  # strips extension: "greeting2.txt" → "greeting2"
    safe = "".join(c if c.isalnum() or c in "._-" else "_" for c in stem)
    return safe[:max_len]


def _make_obsidian_link(file_path: Path, base_folder: str) -> str:
    """
    Build a clean Obsidian [[link]] for a file.

    Uses only the filename (not the full path) relative to base_folder.
    Always uses forward slashes — Obsidian requires this on all platforms.

    Args:
        file_path:   Path object pointing to the file
        base_folder: The vault folder name the file lives in (e.g. "Drop_History")

    Returns:
        "[[Drop_History/filename.ext]]"
    """
    filename = file_path.name  # just the filename, no parent directories
    return f"[[{base_folder}/{filename}]]"


def _truncate_content(content: str, max_length: int = 3000) -> str:
    """Truncate content to max_length characters with a notice."""
    if len(content) <= max_length:
        return content
    truncated = content[: max_length - 200]
    omitted = len(content) - max_length + 200
    return (
        truncated + f"\n\n---\n\n[Content truncated — {omitted} characters omitted. "
        f"Full content in Drop_History/]\n"
    )


# ============================================================================
# TASK FILE CREATION (Watcher calls these)
# ============================================================================


def create_file_drop_task(
    original_name: str,
    original_path: Path,
    content: str,
    content_type: str,
    file_extension: str,
    file_hash: str,
    size_bytes: int,
    priority: str,
    timestamp: datetime,
) -> Tuple[str, str]:
    """
    Create a minimal task file for a file drop event.

    INPUT file that Claude reads. No [PENDING] placeholders.

    PATH FIX: original_path stored as a clean Obsidian link:
        [[Drop_History/filename.ext]]
    — only the filename, forward slashes, wrapped once.
    claude_runner reads this back from frontmatter and passes it
    straight through to build_output_file() without re-wrapping.

    Returns:
        (task_id, markdown_content)
    """
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_stem = _make_safe_stem(original_name)
    task_id = f"file_drop_{timestamp_str}_{safe_stem}"

    size_formatted = _format_size(size_bytes)

    # Build clean Obsidian link — just filename, forward slash, wrapped once
    obsidian_link = _make_obsidian_link(original_path, "Drop_History")

    if content_type == "binary" or not content:
        content_section = (
            "_Binary file — content not extractable. "
            "Claude will base decision on filename and extension only._"
        )
    else:
        content_section = f"```\n{_truncate_content(content)}\n```"

    task_content = f"""---
type: file_drop
task_id: {task_id}
original_name: {original_name}
original_path: "{obsidian_link}"
file_extension: {file_extension}
content_type: {content_type}
file_hash: {file_hash}
size: {size_formatted}
detected: {timestamp.isoformat()}
priority: {priority}
status: pending
retry_count: 0
---

# File Drop: {original_name}

**Detected:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Size:** {size_formatted}
**Priority:** {priority.title()}
**Extension:** {file_extension}
**Content type:** {content_type}

---

## File content

{content_section}

---

*Generated by AI Employee Filesystem Watcher*
*Task ID: `{task_id}`*
"""

    return task_id, task_content


def create_email_task(
    from_address: str,
    subject: str,
    content: str,
    timestamp: datetime,
    priority: str = "normal",
) -> Tuple[str, str]:
    """
    Create a task file for an incoming email.

    Returns:
        (task_id, markdown_content)
    """
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_stem = _make_safe_stem(subject)
    task_id = f"email_{timestamp_str}_{safe_stem}"

    task_content = f"""---
type: email
task_id: {task_id}
from: "{from_address}"
subject: "{subject}"
received: {timestamp.isoformat()}
priority: {priority}
status: pending
retry_count: 0
---

# Email: {subject}

**From:** {from_address}
**Received:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Priority:** {priority.title()}

---

## Body

{_truncate_content(content)}

---

*Generated by AI Employee Gmail Watcher*
*Task ID: `{task_id}`*
"""

    return task_id, task_content


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
    
    Includes:
    - filter_reason: Why this email was selected
    - is_reply: Thread detection
    - gmail_message_id: Permanent Gmail ID
    - gmail_link: Direct link to email (for humans)
    - Quick Actions section (for humans)
    - Email Information table (for humans)
    
    Excludes:
    - AI Processing Status (OUTPUT, not INPUT)
    - Instructions for AI (Claude uses CLAUDE.md)
    - [PENDING] placeholders (file is INPUT-ONLY)
    
    Returns:
        (task_id, markdown_content)
    """
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_stem = _make_safe_stem(subject)
    task_id = f"email_{timestamp_str}_{safe_stem}"
    
    # Convert decimal Gmail ID to hex for URL
    gmail_msgid_hex = format(int(gmail_message_id), 'x') if gmail_message_id else ""
    gmail_url = f"https://mail.google.com/mail/u/0/#inbox/{gmail_msgid_hex}" if gmail_msgid_hex else gmail_link
    
    # Thread info
    thread_text = "Yes (reply)" if is_reply else "No (original)"
    
    # Truncate content
    truncated_content = _truncate_content(content)
    
    task_content = f"""---
type: email
task_id: {task_id}
from: "{from_address}"
to: "{to_address}"
subject: "{subject}"
received: {timestamp.isoformat()}
priority: {priority}
status: pending
retry_count: 0
filter_reason: {filter_reason}
is_reply: {str(is_reply).lower()}
gmail_message_id: {gmail_message_id}
---

# Email: {subject}

## Quick Actions

📧 **[Open in Gmail]({gmail_url})**
📋 **Task ID:** `{task_id}`
🧵 **Thread:** {thread_text}

---

## Email Information

| Property | Value |
|----------|-------|
| From | `{from_address}` |
| To | `{to_address}` |
| Received | {timestamp.strftime('%Y-%m-%d %H:%M:%S')} |
| Priority | {priority.title()} |
| Filter Reason | {filter_reason} |

---

## Body

{truncated_content}

---

*Generated by AI Employee Gmail Watcher*
*Task ID: `{task_id}`*
"""
    
    return task_id, task_content


def create_whatsapp_task(
    from_number: str,
    content: str,
    timestamp: datetime,
    priority: str = "normal",
) -> Tuple[str, str]:
    """
    Create a task file for a WhatsApp message.

    Returns:
        (task_id, markdown_content)
    """
    timestamp_str = timestamp.strftime("%Y%m%d_%H%M%S")
    safe_number = "".join(c for c in from_number if c.isdigit())[:20]
    task_id = f"whatsapp_{timestamp_str}_{safe_number}"

    task_content = f"""---
type: whatsapp
task_id: {task_id}
from: "{from_number}"
received: {timestamp.isoformat()}
priority: {priority}
status: pending
retry_count: 0
---

# WhatsApp: {from_number}

**From:** {from_number}
**Received:** {timestamp.strftime('%Y-%m-%d %H:%M:%S')}
**Priority:** {priority.title()}

---

## Message

{_truncate_content(content)}

---

*Generated by AI Employee WhatsApp Watcher*
*Task ID: `{task_id}`*
"""

    return task_id, task_content


# ============================================================================
# OUTPUT FILE BUILDING (Claude Runner calls this)
# ============================================================================


def build_output_file(
    task_id: str,
    task_type: str,
    original_name: str,
    original_path_obsidian: str,
    decision: dict,
    processed_at: datetime,
) -> str:
    """
    Build the output markdown file from Claude's JSON decision.

    PATH FIX: original_path_obsidian already contains [[Drop_History/file.ext]]
    as stored in the task file frontmatter. We embed it directly — no extra
    [[ ]] wrapping. Previously this function added wrapping, causing [[[[...]]]].

    Args:
        task_id:                 Unique task identifier
        task_type:               "file_drop" | "email" | "whatsapp"
        original_name:           Original file/task name
        original_path_obsidian:  Already-formatted Obsidian link from frontmatter
        decision:                Claude's validated JSON dict
        processed_at:            Processing timestamp

    Returns:
        Complete markdown string ready to write to disk
    """
    status_map = {
        "complete_task": "completed",
        "create_approval_request": "pending_approval",
        "needs_revision": "needs_revision",
    }
    status = status_map.get(decision.get("decision", "unknown"), "unknown")
    processed_str = processed_at.strftime("%Y-%m-%d %H:%M:%S")
    processed_iso = processed_at.isoformat()

    approval_section = ""
    if decision.get("decision") == "create_approval_request":
        approval_section = f"""
---

## Approval required

**Reason:** {decision.get("approval_reason", "Human review needed")}

- Move to `Approved/` to approve
- Move to `Rejected/` to reject
- Move to `Needs_Revision/` with a comment to request changes
"""

    # original_path_obsidian already has [[ ]] — embed directly, no extra wrapping
    output_md = f"""---
type: {task_type}_result
task_id: {task_id}
original_name: {original_name}
source_file: "{original_path_obsidian}"
original_task: "[[Processing_Archive/{task_id}.md]]"
status: {status}
processed_at: {processed_iso}
ai_decision: {decision.get("decision", "unknown")}
ai_category: {decision.get("category", "unknown")}
---

# {original_name}

**Processed:** {processed_str}
**Decision:** {decision.get("decision", "unknown")}
**Category:** {decision.get("category", "unknown").title()}

---

## Summary

{decision.get("summary", "No summary provided")}

---

## AI response

{decision.get("response", "No response provided")}

---

## Action taken

{decision.get("action_taken", "No action recorded")}
{approval_section}
---

*AI Employee · Task ID: `{task_id}`*
"""

    return output_md


# ============================================================================
# FRONTMATTER UTILITIES (used by claude_runner.py)
# ============================================================================


def read_frontmatter(task_content: str) -> dict:
    """
    Extract key: value pairs from YAML frontmatter.

    Handles flat scalar values only. Strips surrounding quotes from values.

    Returns:
        Dict of frontmatter key → string value
    """
    meta = {}
    in_frontmatter = False

    for line in task_content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_frontmatter:
                in_frontmatter = True
                continue
            else:
                break
        if in_frontmatter and ":" in stripped:
            key, _, value = stripped.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")

    return meta


def increment_retry_count(task_content: str) -> Tuple[str, int]:
    """
    Increment retry_count in task file frontmatter.

    Used by orchestrator when re-queuing from Needs_Revision/.

    Returns:
        (updated_content, new_retry_count)
    """
    meta = read_frontmatter(task_content)
    current = int(meta.get("retry_count", "0"))
    new = current + 1

    updated = task_content.replace(
        f"retry_count: {current}",
        f"retry_count: {new}",
        1,
    )

    return updated, new
