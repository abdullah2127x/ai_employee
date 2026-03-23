#!/usr/bin/env python3
"""
claude_runner.py - Improved Claude Code executor for AI Employee (v2.1)

Reads a task file from Processing/, sends a SHORT prompt to Claude Code,
validates the JSON response, builds the output file, and moves files
based on Claude's decision.

New in v2.1:
- Status file protocol: writes Runner_Status/<task_id>.json when done
  so the orchestrator knows the exact outcome without guessing
- Fixed: "Processing_Arcchive" typo → "Processing_Archive"

Usage:
    python claude_runner.py Processing/file_drop_20260322_greeting2.md
"""

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings
from utils.logging_manager import LoggingManager
from utils.task_template import build_output_file, read_frontmatter

logger = LoggingManager()

# ============================================================================
# VALID VALUES — must match CLAUDE.md exactly
# ============================================================================

VALID_DECISIONS = {"complete_task", "create_approval_request", "needs_revision"}
VALID_CATEGORIES = {"general", "invoice", "payment", "email", "document", "urgent"}

# ============================================================================
# STATUS FILE PROTOCOL
# ============================================================================


def write_status(task_id: str, outcome: str, detail: str = ""):
    """
    Write a status file to Runner_Status/ so the orchestrator knows
    the exact outcome of this runner process.

    Called at the END of process_task() regardless of success or failure.

    outcome values:
        "done"             — task completed, output in Done/
        "pending_approval" — output in Pending_Approval/
        "needs_revision"   — output in Needs_Revision/
        "runner_error"     — runner crashed before finishing

    Args:
        task_id: Task identifier
        outcome: One of the four values above
        detail:  Optional error message or extra info
    """
    status_folder = settings.vault_path / "Runner_Status"
    status_folder.mkdir(parents=True, exist_ok=True)

    status = {
        "task_id": task_id,
        "outcome": outcome,
        "timestamp": datetime.now().isoformat(),
        "detail": detail,
    }

    status_path = status_folder / f"{task_id}.json"
    try:
        status_path.write_text(json.dumps(status, indent=2), encoding="utf-8")
        logger.write_to_timeline(
            f"Status written: {outcome} → Runner_Status/{task_id}.json",
            actor="claude_runner",
        )
    except Exception as e:
        logger.log_error(f"Failed to write status file: {e}", error=e, actor="claude_runner")


# ============================================================================
# PROMPT BUILDER
# ============================================================================

SKILL_MAP = {
    "file_drop": ".claude/skills/process-file-drop/SKILL.md",
    "email": ".claude/skills/process-email/SKILL.md",
    "whatsapp": ".claude/skills/process-whatsapp/SKILL.md",
}


def build_prompt(task_file: Path, task_content: str, task_type: str) -> str:
    """
    Build the short prompt sent to Claude Code.

    CLAUDE.md is auto-loaded by Claude Code (cwd=vault/).
    Skills are loaded by Claude per CLAUDE.md routing rules.
    """
    skill_path = SKILL_MAP.get(task_type, ".claude/skills/process-general/SKILL.md")

    return f"""Process this task using the skill at: {skill_path}

Task file: {task_file.name}

--- TASK CONTENT START ---
{task_content}
--- TASK CONTENT END ---

Return ONLY the JSON decision as defined in CLAUDE.md. No other text."""


# ============================================================================
# CLAUDE INVOCATION
# ============================================================================


def invoke_claude(prompt: str, timeout: int = 300) -> subprocess.CompletedProcess:
    """
    Invoke Claude Code with a prompt.
    Runs from vault/ so CLAUDE.md is auto-loaded.

    Uses shell=True so that ccr/claude is found on PATH exactly as it is
    in the terminal. Writes prompt to a temp file and reads it with
    PowerShell Get-Content (Windows-compatible, no bash required).
    """
    # Write prompt to temp file
    prompt_file = settings.vault_path / ".claude" / "_runner_prompt.tmp"
    prompt_file.parent.mkdir(parents=True, exist_ok=True)
    prompt_file.write_text(prompt, encoding="utf-8")

    # Full absolute path to prompt file, forward slashes for PowerShell
    prompt_file_abs = str(prompt_file.resolve()).replace("\\", "/")

    # Get the command from settings (e.g. "ccr code" or "claude")
    claude_cmd = getattr(settings, "claude_command", "claude")

    # PowerShell reads the file and passes content as the -p argument
    # Works on Windows regardless of bash availability
    cmd = f"powershell -Command \"{claude_cmd} -p (Get-Content -Raw '{prompt_file_abs}')\""

    logger.write_to_timeline(
        f"Invoking Claude | prompt length: {len(prompt)} chars",
        actor="claude_runner",
    )

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(settings.vault_path),  # vault/ so CLAUDE.md auto-loads
        )

        logger.write_to_timeline(
            f"Claude finished | returncode={result.returncode} "
            f"| stdout={len(result.stdout or '')} chars",
            actor="claude_runner",
        )

        if result.stderr:
            logger.write_to_timeline(
                f"Claude stderr: {result.stderr[:300]}",
                actor="claude_runner",
            )

        return result

    except subprocess.TimeoutExpired:
        logger.log_error(f"Claude timed out after {timeout}s", actor="claude_runner")
        return subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="Timeout")

    except Exception as e:
        logger.log_error(f"Claude invocation error: {e}", error=e, actor="claude_runner")
        return subprocess.CompletedProcess(cmd, returncode=-2, stdout="", stderr=str(e))

    finally:
        try:
            prompt_file.unlink(missing_ok=True)
        except Exception:
            pass


# ============================================================================
# JSON PARSING & VALIDATION
# ============================================================================


def parse_and_validate(stdout: str) -> dict:
    """
    Extract and validate Claude's JSON from stdout.

    Strips accidental markdown fences defensively.

    Raises:
        ValueError with a clear message if anything is wrong.
    """
    if not stdout or not stdout.strip():
        raise ValueError("Claude returned empty output")

    text = stdout.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()

    start = text.find("{")
    end = text.rfind("}") + 1
    if start < 0 or end <= start:
        raise ValueError(f"No JSON object found in Claude output. Got: {text[:200]}")

    json_str = text[start:end]

    try:
        decision = json.loads(json_str)
    except json.JSONDecodeError as e:
        raise ValueError(f"Claude returned invalid JSON: {e}. Raw: {json_str[:300]}")

    required = ["decision", "category", "summary", "action_taken", "response", "approval_reason"]
    missing = [f for f in required if f not in decision]
    if missing:
        raise ValueError(f"Missing required fields: {missing}")

    if decision["decision"] not in VALID_DECISIONS:
        raise ValueError(
            f"Invalid decision '{decision['decision']}'. Must be one of: {VALID_DECISIONS}"
        )

    if decision["category"] not in VALID_CATEGORIES:
        raise ValueError(
            f"Invalid category '{decision['category']}'. Must be one of: {VALID_CATEGORIES}"
        )

    # Normalize approval_reason
    if decision["decision"] == "create_approval_request":
        if not decision.get("approval_reason"):
            raise ValueError(
                "approval_reason must be non-empty when decision is create_approval_request"
            )
    else:
        if decision.get("approval_reason") in (None, "null", ""):
            decision["approval_reason"] = None

    return decision


# ============================================================================
# FILE MOVEMENT
# ============================================================================


def move_file(src: Path, dest_folder: Path, reason: str = "") -> Path | None:
    """Move src to dest_folder. Returns new path or None on failure."""
    if not src.exists():
        logger.log_warning(f"Cannot move — file missing: {src}", actor="claude_runner")
        return None

    dest_folder.mkdir(parents=True, exist_ok=True)
    dest = dest_folder / src.name

    try:
        shutil.move(str(src), str(dest))
        logger.write_to_timeline(
            f"Moved {src.name} → {dest_folder.name}/ ({reason})",
            actor="claude_runner",
        )
        return dest
    except Exception as e:
        logger.log_error(f"Failed to move {src.name}: {e}", error=e, actor="claude_runner")
        return None


# ============================================================================
# OUTPUT FILE CREATION
# ============================================================================


def create_and_move_output_file(
    task_file: Path,
    task_content: str,
    decision: dict,
    processed_at: datetime,
) -> tuple[Path | None, str]:
    """
    Build output markdown and write it to the correct destination folder.

    Returns:
        (output_path_or_None, outcome_string)
        outcome_string is one of: "done", "pending_approval", "needs_revision"
    """
    meta = read_frontmatter(task_content)
    task_id = meta.get("task_id", task_file.stem)
    task_type = meta.get("type", "unknown")
    file_name = meta.get("original_name") or meta.get("subject") or task_file.stem
    orig_path = meta.get("original_path", "")

    output_md = build_output_file(
        task_id=task_id,
        task_type=task_type,
        original_name=file_name,
        original_path_obsidian=orig_path,
        decision=decision,
        processed_at=processed_at,
    )

    dest_map = {
        "complete_task": (settings.vault_path / "Done", "done"),
        "create_approval_request": (settings.vault_path / "Pending_Approval", "pending_approval"),
        # needs_revision handled separately in process_task()
    }
    dest_folder, outcome = dest_map.get(
        decision["decision"],
        (settings.vault_path / "Done", "done"),
    )
    dest_folder.mkdir(parents=True, exist_ok=True)

    output_filename = f"RESULT_{task_id}.md"
    output_path = dest_folder / output_filename

    try:
        output_path.write_text(output_md, encoding="utf-8")
        logger.write_to_timeline(
            f"Output file created: {output_filename} → {dest_folder.name}/",
            actor="claude_runner",
        )
        return output_path, outcome
    except Exception as e:
        logger.log_error(f"Failed to write output file: {e}", error=e, actor="claude_runner")
        return None, "runner_error"


# ============================================================================
# MAIN TASK PROCESSOR
# ============================================================================


def process_task(task_file: Path) -> bool:
    """
    Process a single task file. Returns True on success, False on failure.

    FIX: needs_revision now moves the ORIGINAL task file to Needs_Revision/
    instead of writing a RESULT_ file there. This ensures:
    - Orchestrator retries Claude on the same input it failed on
    - retry_count in the original task frontmatter increments correctly
    - The retry loop terminates properly at MAX_RETRIES → Dead_Letter/
    """
    logger.write_to_timeline(f"Processing: {task_file.name}", actor="claude_runner")

    task_id = task_file.stem

    # ── Step 1: Read task file ──────────────────────────────────────────────
    try:
        task_content = task_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.log_error(f"Cannot read task file: {e}", error=e, actor="claude_runner")
        move_file(
            task_file,
            settings.vault_path / "Needs_Revision",
            "Could not read file",
        )
        write_status(task_id, "runner_error", f"Could not read task file: {e}")
        return False

    meta = read_frontmatter(task_content)
    task_type = meta.get("type", "unknown")
    task_id = meta.get("task_id", task_file.stem)

    # ── Step 2: Build prompt ────────────────────────────────────────────────
    prompt = build_prompt(task_file, task_content, task_type)

    # ── Step 3: Invoke Claude ───────────────────────────────────────────────
    result = invoke_claude(prompt)

    if result.returncode != 0:
        msg = f"Claude exited {result.returncode}: {result.stderr[:200]}"
        logger.log_error(msg, actor="claude_runner")
        move_file(
            task_file,
            settings.vault_path / "Needs_Revision",
            "Claude invocation failed",
        )
        write_status(task_id, "runner_error", msg)
        return False

    # ── Step 4: Parse and validate JSON ─────────────────────────────────────
    try:
        decision = parse_and_validate(result.stdout)
    except ValueError as e:
        logger.log_error(f"JSON validation failed: {e}", actor="claude_runner")
        move_file(
            task_file,
            settings.vault_path / "Needs_Revision",
            f"Bad JSON: {e}",
        )
        write_status(task_id, "runner_error", f"JSON validation failed: {e}")
        return False

    logger.write_to_timeline(
        f"Decision: {decision['decision']} | Category: {decision['category']}",
        actor="claude_runner",
    )

    processed_at = datetime.now()

    # ── Step 5: Handle needs_revision separately ─────────────────────────────
    # FIX: Do NOT write a RESULT_ file to Needs_Revision/.
    # Move the ORIGINAL task file there so the orchestrator retries
    # Claude on the same input. The retry_count in the task file's
    # frontmatter increments correctly each time through the loop.
    if decision["decision"] == "needs_revision":
        reason = decision.get("response", "Claude returned needs_revision")
        logger.write_to_timeline(
            f"Needs revision: {reason[:100]}",
            actor="claude_runner",
        )
        move_file(
            task_file,
            settings.vault_path / "Needs_Revision",
            f"Needs revision: {reason[:80]}",
        )
        write_status(task_id, "needs_revision", reason[:200])
        return False

    # ── Step 6: Build output file (done / pending_approval only) ────────────
    output_path, outcome = create_and_move_output_file(
        task_file, task_content, decision, processed_at
    )
    if output_path is None:
        move_file(
            task_file,
            settings.vault_path / "Needs_Revision",
            "Output file creation failed",
        )
        write_status(task_id, "runner_error", "Output file creation failed")
        return False

    # ── Step 7: Archive original task file ──────────────────────────────────
    archive_folder = settings.vault_path / "Processing_Archive"
    move_file(task_file, archive_folder, "Task processed — archived")

    # ── Step 8: Write status for orchestrator ───────────────────────────────
    write_status(task_id, outcome)

    logger.write_to_timeline(
        f"Done: {task_file.name} → {output_path.parent.name}/{output_path.name}",
        actor="claude_runner",
    )
    return True


# ============================================================================
# ENTRY POINT
# ============================================================================


def main():
    if len(sys.argv) < 2:
        print("Usage: python claude_runner.py <task_file>")
        print("Example: python claude_runner.py Processing/file_drop_20260322_greeting2.md")
        sys.exit(1)

    task_file = Path(sys.argv[1])

    if not task_file.exists():
        logger.log_error(f"Task file not found: {task_file}", actor="claude_runner")
        sys.exit(1)

    success = process_task(task_file)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
