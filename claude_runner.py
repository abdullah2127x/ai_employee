#!/usr/bin/env python3
"""
claude_runner.py - Standalone Claude Code executor for AI Employee

Reads task file, invokes Claude Code with system prompt, parses JSON output,
and moves files based on Claude's decision.

Usage:
    python claude_runner.py Processing/FILE_20260319_103000_invoice.pdf.md

Claude Output Format (JSON):
    {"decision": "create_approval_request", "type": "payment", ...}
    {"decision": "complete_task"}
    {"decision": "needs_revision", "reason": "..."}
    {"decision": "error", "message": "..."}

File Movement:
    - complete_task → Processing/ → Done/
    - create_approval_request → Processing/ → Pending_Approval/
    - needs_revision → Processing/ → Needs_Revision/
"""

import os
import sys
import json
import subprocess
import shutil
from pathlib import Path
from datetime import datetime

# Add project root to path
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings
from utils.logging_manager import LoggingManager

logger = LoggingManager()


def load_system_prompt() -> str:
    """Load system prompt from vault/CLAUDE.md"""
    claude_md = settings.vault_path / "CLAUDE.md"
    if claude_md.exists():
        return claude_md.read_text(encoding="utf-8")
    else:
        logger.log_warning("CLAUDE.md not found, using default prompt", actor="claude_runner")
        return """
You are an AI Employee assistant. Process the task and output your decision as JSON.

Decision types:
- complete_task: Task is done, move to Done/
- create_approval_request: Need human approval, move to Pending_Approval/
- needs_revision: Task needs rework, move to Needs_Revision/
- error: Something went wrong

Output ONLY the JSON, no other text.
""".strip()


def load_context_files() -> dict:
    """Load context files (Business_Goals.md, Company_Handbook.md)"""
    context = {}

    business_goals = settings.vault_path / "Business_Goals.md"
    if business_goals.exists():
        context["business_goals"] = business_goals.read_text(encoding="utf-8")

    company_handbook = settings.vault_path / "Company_Handbook.md"
    if company_handbook.exists():
        context["company_handbook"] = company_handbook.read_text(encoding="utf-8")

    return context


# getting the prompt string that contains the Business Goals and Company Handbook content and invoke the claude code with the prompt
def invoke_claude(prompt: str, timeout: int = 300) -> subprocess.CompletedProcess:
    """
    Invoke Claude Code with prompt.

    Args:
        prompt: The prompt to send to Claude
        timeout: Timeout in seconds (default: 300)

    Returns:
        subprocess.CompletedProcess with stdout containing Claude's response
    """
    # Build command for Claude Code
    # Escape quotes in prompt
    # escaped_prompt = "Hi"
    escaped_prompt = prompt.replace('"', '\\"').replace("\n", "\\n")
    cmd = f'ccr code -p "{escaped_prompt}"'

    # LOG THE EXACT COMMAND FOR DEBUGGING
    logger.write_to_timeline("="*70)
    logger.write_to_timeline("🔵 CLAUDE CODE COMMAND")
    logger.write_to_timeline("="*70)
    logger.write_to_timeline(f"Command: {cmd}")
    logger.write_to_timeline(f"Timeout: {timeout}s")
    logger.write_to_timeline(f"Prompt length: {len(prompt)} chars")
    logger.write_to_timeline(f"Prompt (first 300 chars): {prompt[:300]}...")
    logger.write_to_timeline("="*70)
    logger.write_to_timeline("🔄 Running subprocess.run()...")
    logger.write_to_timeline(f"   shell=True (required for .cmd on Windows)")
    logger.write_to_timeline(f"   capture_output={True}")
    logger.write_to_timeline(f"   text={True}")
    logger.write_to_timeline(f"   cwd={settings.vault_path}")
    logger.write_to_timeline("="*70)

    logger.write_to_timeline(f"Invoking Claude Code", actor="claude_runner", message_level="INFO")

    try:
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(settings.vault_path),
        )

        logger.write_to_timeline("✅ subprocess.run() completed")
        logger.write_to_timeline(f"   Return code: {result.returncode}")
        logger.write_to_timeline(f"   Stdout length: {len(result.stdout) if result.stdout else 0} chars")
        logger.write_to_timeline(f"   Stderr length: {len(result.stderr) if result.stderr else 0} chars")

        if result.stdout:
            logger.write_to_timeline(f"   Stdout (first 500 chars):\n{result.stdout[:500]}")
        if result.stderr:
            logger.write_to_timeline(f"   Stderr (first 500 chars):\n{result.stderr[:500]}")

        return result

    except subprocess.TimeoutExpired:
        logger.log_error(f"Claude Code timed out after {timeout} seconds", actor="claude_runner")
        result = subprocess.CompletedProcess(cmd, returncode=-1, stdout="", stderr="Timeout")
        return result

    except Exception as e:
        logger.log_error(f"Error invoking Claude Code: {e}", error=e, actor="claude_runner")
        result = subprocess.CompletedProcess(cmd, returncode=-2, stdout="", stderr=str(e))
        return result


def parse_claude_output(stdout: str) -> dict:
    """
    Parse Claude's JSON output.

    Args:
        stdout: Claude's output (may contain JSON block)

    Returns:
        dict with 'decision' key and metadata
    """
    # Try to find JSON in output
    try:
        # Look for JSON block
        start = stdout.find("{")
        end = stdout.rfind("}") + 1

        if start >= 0 and end > start:
            json_str = stdout[start:end]
            decision = json.loads(json_str)
            return decision
        else:
            # No JSON found, assume completion
            return {"decision": "complete_task"}

    except json.JSONDecodeError as e:
        logger.log_warning(f"Could not parse JSON from Claude output: {e}", actor="claude_runner")
        return {"decision": "complete_task"}


def move_file(src: Path, dest_folder: Path, reason: str = ""):
    """
    Move file to destination folder.

    Args:
        src: Source file path
        dest_folder: Destination folder
        reason: Reason for move (for logging)
    """
    if not src.exists():
        logger.log_warning(f"Source file does not exist: {src}", actor="claude_runner")
        return

    dest_folder.mkdir(parents=True, exist_ok=True)
    dest = dest_folder / src.name

    try:
        shutil.move(str(src), str(dest))
        logger.write_to_timeline(
            f"Moved {src.name} to {dest_folder.name}/ - {reason}",
            actor="claude_runner",
            message_level="INFO",
        )
    except Exception as e:
        logger.log_error(f"Failed to move file: {e}", error=e, actor="claude_runner")


def add_response_to_file(task_file: Path, response: str, category: str, action_taken: str):
    """
    Add Claude's response to the task file's Processing Notes section.

    Args:
        task_file: Path to task markdown file
        response: Claude's response text
        category: Category assigned by Claude
        action_taken: Action taken by Claude
    """
    try:
        # Read current file content
        content = task_file.read_text(encoding='utf-8')
        
        # Find and replace the Processing Notes section
        old_section = "## Processing Notes\n\n(Add notes here during processing)\n"
        new_section = f"""## Processing Notes

**Category:** {category.title()}
**Action Taken:** {action_taken}
**AI Response:** {response}

---

## AI Processing Summary

- **Processed by:** Claude Code
- **Category:** {category.title()}
- **Response:** {response}
- **Action:** {action_taken}

"""
        
        if old_section in content:
            content = content.replace(old_section, new_section)
        else:
            # If section not found, append before the footer
            footer = "\n---\n\n*Generated by AI Employee Filesystem Watcher*"
            if footer in content:
                content = content.replace(footer, f"\n{new_section}{footer}")
            else:
                # Just append at the end
                content += f"\n{new_section}"
        
        # Write updated content
        task_file.write_text(content, encoding='utf-8')
        
        logger.write_to_timeline(
            f"Added response to file: {response[:50]}...",
            actor="claude_runner",
            message_level="INFO",
        )
        
    except Exception as e:
        logger.log_error(
            f"Failed to add response to file: {e}",
            error=e,
            actor="claude_runner"
        )


def process_task(task_file: Path):
    """
    Process a single task file.

    Args:
        task_file: Path to task file in Processing/
    """
    logger.write_to_timeline("="*70)
    logger.write_to_timeline("🔵 CLAUDE RUNNER: PROCESS TASK")
    logger.write_to_timeline("="*70)
    logger.write_to_timeline(f"Task file: {task_file}")
    logger.write_to_timeline(f"Task file exists: {task_file.exists()}")
    logger.write_to_timeline(f"Task file absolute path: {task_file.absolute()}")
    logger.write_to_timeline("="*70)
    
    logger.write_to_timeline(
        f"Processing task: {task_file.name}", actor="claude_runner", message_level="INFO"
    )

    # Read task file
    try:
        task_content = task_file.read_text(encoding="utf-8")
    except Exception as e:
        logger.log_error(f"Could not read task file: {e}", error=e, actor="claude_runner")
        move_file(task_file, settings.vault_path / "Needs_Revision", "Could not read file")
        return

    # Load system prompt and context
    system_prompt = load_system_prompt()
    context = load_context_files()

    # Build prompt - Ask Claude for response too
    prompt = f"""You are an AI Employee assistant. Process the task.

Task file: {task_file.name}
Task content:
{task_content}

Output your response in this JSON format ONLY:
{{
  "decision": "complete_task" | "create_approval_request" | "needs_revision",
  "category": "general" | "important" | "urgent" | "invoice" | "payment",
  "response": "Your response or analysis here",
  "action_taken": "What you did"
}}

Examples:
- For "Hey I am abdullah" → {{"decision": "complete_task", "category": "general", "response": "Hello! Nice to meet you.", "action_taken": "Added greeting response"}}
- For important note → {{"decision": "complete_task", "category": "important", "response": "This has been categorized as important.", "action_taken": "Categorized and responded"}}

Output ONLY the JSON."""

    # Invoke Claude
    result = invoke_claude(prompt, timeout=300)

    # Check result
    if result.returncode != 0:
        logger.log_error(f"Claude Code failed: {result.stderr[:200]}", actor="claude_runner")
        move_file(task_file, settings.vault_path / "Needs_Revision", "Claude failed")
        return

    # Parse output
    decision = parse_claude_output(result.stdout)

    logger.write_to_timeline(
        f"Claude decision: {decision.get('decision', 'unknown')}",
        actor="claude_runner",
        message_level="INFO",
    )
    
    # Get response from Claude
    response = decision.get('response', '')
    category = decision.get('category', 'general')
    action_taken = decision.get('action_taken', '')
    
    # If Claude provided a response, add it to the file
    if response:
        logger.write_to_timeline(
            f"Adding Claude's response to file",
            actor="claude_runner",
            message_level="INFO",
        )
        add_response_to_file(task_file, response, category, action_taken)

    # Execute decision
    decision_type = decision.get("decision", "complete_task")

    if decision_type == "complete_task":
        # Move to Done/
        move_file(task_file, settings.vault_path / "Done", "Task completed")

    elif decision_type == "create_approval_request":
        # Create approval file in Pending_Approval/
        approval_content = f"""---
type: approval_request
action: {decision.get('type', 'unknown')}
created: {datetime.now().isoformat()}
status: pending
---

# Approval Required

**Action:** {decision.get('type', 'unknown')}

## Details

{json.dumps(decision, indent=2)}

## To Approve
Move this file to `/Approved/` folder

## To Reject
Move this file to `/Rejected/` folder

## To Request Changes
Move this file to `/Needs_Revision/` folder with comments
"""

        approval_file = settings.vault_path / "Pending_Approval" / f"APPROVAL_{task_file.stem}.md"
        approval_file.parent.mkdir(parents=True, exist_ok=True)
        approval_file.write_text(approval_content, encoding="utf-8")

        # Move task file to Pending_Approval/ as well
        move_file(task_file, settings.vault_path / "Pending_Approval", "Approval requested")

        logger.write_to_timeline(
            f"Created approval request: {approval_file.name}",
            actor="claude_runner",
            message_level="INFO",
        )

    elif decision_type == "needs_revision":
        reason = decision.get("reason", "Needs revision")
        move_file(task_file, settings.vault_path / "Needs_Revision", f"Needs revision: {reason}")

    elif decision_type == "error":
        message = decision.get("message", "Unknown error")
        logger.log_error(f"Claude reported error: {message}", actor="claude_runner")
        move_file(task_file, settings.vault_path / "Needs_Revision", f"Error: {message}")

    else:
        logger.log_warning(f"Unknown decision type: {decision_type}", actor="claude_runner")
        move_file(task_file, settings.vault_path / "Done", f"Unknown decision: {decision_type}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print("Usage: python claude_runner.py <task_file>")
        print("Example: python claude_runner.py Processing/FILE_20260319_103000_invoice.pdf.md")
        sys.exit(1)

    task_file = Path(sys.argv[1])

    if not task_file.exists():
        logger.log_error(f"Task file does not exist: {task_file}", actor="claude_runner")
        sys.exit(1)

    logger.write_to_timeline(
        f"Claude Runner started for: {task_file.name}", actor="claude_runner", message_level="INFO"
    )

    try:
        process_task(task_file)
        logger.write_to_timeline(
            f"Claude Runner completed: {task_file.name}",
            actor="claude_runner",
            message_level="INFO",
        )
    except Exception as e:
        logger.log_error(f"Error processing task: {e}", error=e, actor="claude_runner")
        # Move to Needs_Revision on error
        move_file(task_file, settings.vault_path / "Needs_Revision", f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
