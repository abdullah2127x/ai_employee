"""
dashboard.py - Real-time Dashboard.md writer for AI Employee

Scans vault folders and writes a fresh Dashboard.md after every task.
Called by orchestrator.py after each runner status update.

Design:
- Python owns the dashboard entirely — no Claude involvement
- Atomic write (temp → rename) so Obsidian never sees a partial file
- Reads RESULT_*.md frontmatter for task details
- Keeps last 10 completions for the recent activity section
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Optional


# ============================================================================
# FRONTMATTER READER (local copy — avoids circular imports)
# ============================================================================

def _read_frontmatter(content: str) -> dict:
    """Extract flat key: value pairs from YAML frontmatter."""
    meta = {}
    in_fm = False
    for line in content.splitlines():
        stripped = line.strip()
        if stripped == "---":
            if not in_fm:
                in_fm = True
                continue
            else:
                break
        if in_fm and ":" in stripped:
            key, _, value = stripped.partition(":")
            meta[key.strip()] = value.strip().strip('"').strip("'")
    return meta


# ============================================================================
# FOLDER SCANNERS
# ============================================================================

def _count_md_files(folder: Path) -> int:
    """Count .md files in a folder (excludes hidden and .tmp files)."""
    if not folder.exists():
        return 0
    return sum(
        1 for f in folder.iterdir()
        if f.is_file()
        and f.suffix == ".md"
        and not f.name.startswith(".")
    )


def _get_approval_queue(pending_approval: Path) -> list[dict]:
    """
    Return list of files waiting for human approval.
    Each dict has: name, original_name, obsidian_link, detected_at
    """
    if not pending_approval.exists():
        return []

    items = []
    for f in sorted(
        pending_approval.glob("RESULT_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    ):
        try:
            meta = _read_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

        items.append({
            "name":          f.name,
            "original_name": meta.get("original_name", f.stem),
            "category":      meta.get("ai_category", "unknown"),
            "processed_at":  meta.get("processed_at", ""),
            "obsidian_link": f"[[Pending_Approval/{f.name}]]",
        })

    return items


def _get_recent_completions(done: Path, limit: int = 10) -> list[dict]:
    """
    Return the most recent completed tasks from Done/.
    Each dict has: original_name, decision, category, processed_at, obsidian_link
    """
    if not done.exists():
        return []

    files = sorted(
        done.glob("RESULT_*.md"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )[:limit]

    items = []
    for f in files:
        try:
            meta = _read_frontmatter(f.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

        # Format processed_at as HH:MM:SS if it's an ISO string
        processed_at = meta.get("processed_at", "")
        try:
            dt = datetime.fromisoformat(processed_at)
            time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
        except Exception:
            time_str = processed_at

        items.append({
            "original_name": meta.get("original_name", f.stem),
            "decision":      meta.get("ai_decision", "unknown"),
            "category":      meta.get("ai_category", "unknown"),
            "processed_at":  time_str,
            "obsidian_link": f"[[Done/{f.name}]]",
        })

    return items


def _get_attention_items(needs_revision: Path, dead_letter: Path) -> list[dict]:
    """
    Return tasks that need human attention:
    - Needs_Revision/ items (will be retried automatically)
    - Dead_Letter/ items (exceeded retry limit, need manual review)
    """
    items = []

    for folder, label in [
        (needs_revision, "Needs revision"),
        (dead_letter,    "Dead letter — manual review required"),
    ]:
        if not folder.exists():
            continue
        for f in folder.glob("*.md"):
            if f.name.startswith("."):
                continue
            items.append({
                "name":          f.name,
                "label":         label,
                "obsidian_link": f"[[{folder.name}/{f.name}]]",
            })

    return items


# ============================================================================
# DASHBOARD WRITER
# ============================================================================

def write_dashboard(vault_path: Path) -> bool:
    """
    Scan vault folders and write a fresh Dashboard.md.

    Called after every task completion by orchestrator.py.
    Uses atomic write (temp → rename) so Obsidian never sees partial content.

    Args:
        vault_path: Root path of the vault

    Returns:
        True on success, False on failure
    """
    # Folder references
    needs_action    = vault_path / "Needs_Action"
    processing      = vault_path / "Processing"
    pending_approval = vault_path / "Pending_Approval"
    done            = vault_path / "Done"
    needs_revision  = vault_path / "Needs_Revision"
    dead_letter     = vault_path / "Dead_Letter"

    # Counts
    pending_count  = _count_md_files(needs_action) + _count_md_files(processing)
    approval_count = _count_md_files(pending_approval)
    done_count     = _count_md_files(done)
    failed_count   = _count_md_files(needs_revision) + _count_md_files(dead_letter)

    # Detailed lists
    approval_queue  = _get_approval_queue(pending_approval)
    recent          = _get_recent_completions(done, limit=10)
    attention_items = _get_attention_items(needs_revision, dead_letter)

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # ── Build markdown ───────────────────────────────────────────────────────

    lines = [
        "# AI Employee Dashboard",
        f"*Last updated: {now}*",
        "",
        "---",
        "",
        "## Status",
        "",
        "| Queue | Count |",
        "|-------|-------|",
        f"| Pending (Needs Action + Processing) | {pending_count} |",
        f"| Awaiting approval | {approval_count} |",
        f"| Completed (all time) | {done_count} |",
        f"| Failed / needs attention | {failed_count} |",
        "",
        "---",
        "",
        "## Approval queue",
        "",
    ]

    if approval_queue:
        for item in approval_queue:
            ts = item["processed_at"][:19] if item["processed_at"] else ""
            lines.append(
                f"- {item['obsidian_link']} — "
                f"**{item['original_name']}** · {item['category']} · {ts}"
            )
    else:
        lines.append("*No items awaiting approval.*")

    lines += [
        "",
        "---",
        "",
        "## Recent completions",
        "",
    ]

    if recent:
        for item in recent:
            decision_label = {
                "complete_task":           "✅ Completed",
                "create_approval_request": "⏳ Sent for approval",
                "needs_revision":          "🔄 Needs revision",
            }.get(item["decision"], item["decision"])

            lines.append(
                f"- {item['processed_at']} · "
                f"{item['obsidian_link']} — "
                f"**{item['original_name']}** · "
                f"{decision_label} · {item['category']}"
            )
    else:
        lines.append("*No completed tasks yet.*")

    lines += [
        "",
        "---",
        "",
        "## Needs attention",
        "",
    ]

    if attention_items:
        for item in attention_items:
            lines.append(f"- {item['obsidian_link']} — {item['label']}")
    else:
        lines.append("*Nothing needs attention.*")

    lines += [
        "",
        "---",
        "",
        f"*AI Employee · Auto-generated · {now}*",
    ]

    content = "\n".join(lines) + "\n"

    # ── Atomic write ─────────────────────────────────────────────────────────
    dashboard_path = vault_path / "Dashboard.md"
    temp_path      = vault_path / "Dashboard.tmp"

    try:
        temp_path.write_text(content, encoding="utf-8")

        # Windows-safe atomic replace
        if dashboard_path.exists():
            dashboard_path.unlink()
        temp_path.rename(dashboard_path)

        return True

    except Exception as e:
        # Clean up temp file if it exists
        try:
            temp_path.unlink(missing_ok=True)
        except Exception:
            pass
        return False