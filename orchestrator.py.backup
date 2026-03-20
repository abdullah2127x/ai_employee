#!/usr/bin/env python3
"""
orchestrator.py - Simplified AI Employee Orchestrator

Watches vault folders, forwards items to Claude Code for processing.
Claude makes all intelligent decisions — routing, approval, priority.

Your setup:
- Run Claude Code with: ccr code
- Vault structure is auto-created on startup
- Drop files into Inbox/Drop/ to trigger processing
"""

import os
import sys
import time
import subprocess
import threading
import logging
import traceback
from pathlib import Path
from typing import Optional, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Project setup ────────────────────────────────────────────────────────────
project_root = Path(__file__).parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings
from utils.logging_manager import LoggingManager

logger = LoggingManager()

# ── Your Claude command ───────────────────────────────────────────────────────
# This must match EXACTLY what works in your terminal.
# Your example: ["ccr", "code", "-p", "Hi"] with shell=True
CLAUDE_COMMAND = ["ccr", "code"]  # Base command - we'll add prompt and cwd in the function


# =============================================================================
# Claude Invocation — Matches Your Example Exactly
# =============================================================================


def invoke_claude(prompt: str, vault_path: Path, timeout: int = 300) -> subprocess.CompletedProcess:
    """
    Run Claude Code with a prompt.

    Fixed: Use shell=True with .cmd path for Windows.
    """
    # Build command string for Windows - must use shell=True for .cmd files
    # Escape double quotes in prompt by replacing " with \"
    escaped_prompt = prompt.replace('\\', '\\\\').replace('"', '\\"').replace('\n', '\\n').replace('\r', '')
    cmd = f'ccr code -p "{escaped_prompt}"'
    env = os.environ.copy()

    # LOG EVERYTHING for debugging
    logger.info("=" * 80)
    logger.info("🔵 CLAUDE INVOCATION DETAILS")
    logger.info("=" * 80)
    logger.info(f"Command: {cmd}")
    logger.info(f"Vault path: {vault_path}")
    logger.info(f"Timeout: {timeout}s")
    logger.info(f"Prompt (first 200 chars): {prompt[:200]}...")
    logger.info("=" * 80)

    try:
        logger.info("🔄 Running subprocess.run()...")
        logger.info(f"   shell=True (required for .cmd on Windows)")
        logger.info(f"   capture_output={True}")
        logger.info(f"   text={True}")
        logger.info(f"   cwd={vault_path}")

        # Fixed: Use shell=True with properly escaped command string
        result = subprocess.run(
            cmd,
            shell=True,  # Required for .cmd files on Windows
            capture_output=True,  # Capture stdout and stderr
            text=True,  # Return strings, not bytes
            timeout=timeout,  # Give up after timeout seconds
            cwd=str(vault_path),  # Set working directory for Claude
            env=env,  # Pass environment variables
        )

        logger.info("✅ subprocess.run() completed")
        logger.info(f"   Return code: {result.returncode}")
        logger.info(f"   Stdout length: {len(result.stdout) if result.stdout else 0} chars")
        logger.info(f"   Stderr length: {len(result.stderr) if result.stderr else 0} chars")

        if result.stdout:
            logger.info(f"   Stdout (first 500 chars):\n{result.stdout[:500]}")
        if result.stderr:
            logger.info(f"   Stderr (first 500 chars):\n{result.stderr[:500]}")

        return result

    except subprocess.TimeoutExpired as e:
        logger.error(f"⏱️  TIMEOUT after {timeout}s")
        logger.error(f"   Partial stdout: {e.stdout[:200] if e.stdout else 'None'}")
        logger.error(f"   Partial stderr: {e.stderr[:200] if e.stderr else 'None'}")
        result          = subprocess.CompletedProcess(cmd.split(), returncode=-1)
        result.stdout   = ""
        result.stderr   = f"Timed out after {timeout}s"
        return result

    except Exception as e:
        logger.error(f"❌ EXCEPTION: {type(e).__name__}: {e}")
        logger.error(f"   Traceback: {traceback.format_exc()}")
        result          = subprocess.CompletedProcess(cmd.split(), returncode=-2)
        result.stdout   = ""
        result.stderr   = str(e)
        return result


# =============================================================================
# NeedsActionMonitor
# =============================================================================


class NeedsActionMonitor(FileSystemEventHandler):
    """
    Watches Needs_Action/ for new .md files.
    Forwards each one to Claude Code for processing.
    Claude decides: skill, priority, approval needed — everything.
    """

    def __init__(self, db: TaskDatabase, vault_path: Path):
        self.db = db
        self.vault_path = vault_path
        self.needs_action = vault_path / "Needs_Action"
        self.processing = vault_path / "Processing"
        self.processing_files = set()

    def on_created(self, event):
        if event.is_directory:
            return

        src_path = Path(event.src_path)

        # Only care about .md files
        if src_path.suffix != ".md" or src_path.name.startswith("."):
            return

        # Skip if already being handled
        if src_path.name in self.processing_files:
            return

        self.processing_files.add(src_path.name)
        try:
            time.sleep(0.5)  # wait for file write to complete
            if src_path.exists():
                self._handle(src_path)
        except Exception as e:
            logger.error(f"Error handling {src_path.name}: {e}", exc_info=True)
        finally:
            self.processing_files.discard(src_path.name)

    def _handle(self, file_path: Path):
        logger.info(f"📥 New item: {file_path.name}")

        # FilesystemWatcher already created the task with ID like:
        # file_20260317_081226_abdullah.txt
        # Extract that ID from the filename
        timestamp_part = file_path.stem.replace("FILE_", "").replace("_", ":", 1).replace("_", " ")
        task_id = f"file_{timestamp_part.replace(' ', '_').replace(':', '_')}"

        # Try to get existing task (created by FilesystemWatcher)
        existing_task = self.db.get_task(task_id)

        if existing_task:
            logger.info(f"   → Found existing task: {task_id}")
            self.db.update_task_status(task_id, "processing")
        else:
            # Fallback: create new task if FilesystemWatcher didn't
            logger.info(f"   → Creating new task (FilesystemWatcher didn't)")
            task_id = f"task_{int(time.time())}_{file_path.stem}"
            self.db.create_task(
                task_id=task_id,
                task_type="incoming",
                source_file=str(file_path),
                priority="normal",
                title=file_path.name,
            )
            self.db.update_task_status(task_id, "processing")

        # Don't move the file - it's still being written by FilesystemWatcher
        # Just process it where it is
        logger.info(f"   → processing in place")

        # Hand off to Claude — Claude reads the file and decides everything
        self._run_claude(file_path, task_id)

    def _run_claude(self, file_path: Path, task_id: str):
        """
        Send the file to Claude Code for processing.

        Claude will:
        - Read the file
        - Read Company_Handbook.md and BUSINESS_GOALS.md
        - Decide what type of item this is
        - Decide if human approval is needed
        - WRITE OUTPUT FILES to the vault folders
        """
        original_filename = file_path.name

        content_preview = ""
        if file_path.suffix == ".md":
            try:
                content = file_path.read_text(encoding="utf-8")
                content_preview = content[:300] + ("..." if len(content) > 300 else "")
            except:
                content_preview = "Content could not be read"
        prompt = f"""
            You are my autonomous Personal AI Employee processing task: {task_id}

            File to handle right now: {file_path}
            Original dropped filename: {original_filename}   # <-- orchestrator will pass this
            Content preview: {content_preview}               # <-- first 300 chars (orchestrator adds this)

            === CLAUDE.md RULES ARE ACTIVE (read them first) ===

            Step-by-step thinking (do this in your mind first):

            1. Read the full file content + Company_Handbook.md + Business_Goals.md + Dashboard.md

            2. Detect type:
            - If filename or content contains "test" → THIS IS A TEST FILE
                → Quick path: create short DONE file, move original to Done/, update Dashboard, finish.
            - Otherwise → full production reasoning (reply, invoice, payment, social post, etc.)

            3. ALWAYS execute real file operations using filesystem tools or the inbox-conductor skill.
            Never say "I would create..." — actually create/move files right now.

            4. Follow exact folder & naming rules from CLAUDE.md

            5. After everything is done, output exactly:
            <COMPLETED_TASK_{task_id}>

            Begin processing now.
            """

        logger.info(f"   🤖 Sending to Claude...")
        result = invoke_claude(prompt, self.vault_path)

        if result.returncode == 0:
            logger.info(f"   ✅ Claude completed successfully")
            if result.stdout:
                logger.debug(f"   Output: {result.stdout[:200]}")
            self.db.update_task_status(task_id, "pending_approval")

        elif result.returncode == -1:
            logger.error(f"   ⏱️  Claude timed out")
            self.db.update_task_status(task_id, "failed", error_message="Timeout")

        else:
            logger.error(f"   ❌ Claude failed: {result.stderr[:200]}")
            self.db.update_task_status(task_id, "failed", error_message=result.stderr[:200])


# =============================================================================
# ApprovedMonitor
# =============================================================================


class ApprovedMonitor(FileSystemEventHandler):
    """
    Watches Approved/ for files you have approved.
    Tells Claude the item was approved and to proceed.
    Claude decides how to execute based on the file content.
    """

    def __init__(self, db: TaskDatabase, vault_path: Path):
        self.db = db
        self.vault_path = vault_path
        self.approved = vault_path / "Approved"
        self.done = vault_path / "Done"
        self.processing_files = set()

    def on_created(self, event):
        if event.is_directory:
            return

        src_path = Path(event.src_path)

        if src_path.suffix != ".md" or src_path.name.startswith("."):
            return

        if src_path.name in self.processing_files:
            return

        self.processing_files.add(src_path.name)
        try:
            time.sleep(0.5)
            if src_path.exists():
                self._handle(src_path)
        except Exception as e:
            logger.error(f"Error handling approved file: {e}", exc_info=True)
        finally:
            self.processing_files.discard(src_path.name)

    def _handle(self, approval_file: Path):
        logger.info(f"✅ Approved: {approval_file.name}")

        # Tell Claude this was approved
        # Claude reads the file and knows what action to take
        prompt = f"""The following item has been approved by the human: {approval_file.name}

File is located at: {approval_file}

Please:
1. Read the file to understand what was approved
2. Read Company_Handbook.md for execution rules
3. Execute or prepare the approved action
4. Move the file or create a completion record in Done/
5. Update Dashboard.md with the result
6. Note: For now log the intended action clearly
   since external integrations (email send, etc.) are not yet connected"""

        result = invoke_claude(prompt, self.vault_path, timeout=120)

        if result.returncode == 0:
            logger.info(f"   ✅ Executed successfully")
            # Move to Done/
            try:
                approval_file.rename(self.done / approval_file.name)
                logger.info(f"   → Done/")
            except Exception as e:
                logger.error(f"   Could not move to Done/: {e}")
        else:
            logger.error(f"   ❌ Execution failed: {result.stderr[:200]}")


# =============================================================================
# Orchestrator
# =============================================================================


class Orchestrator:
    """
    Starts all monitors and watchers.
    Manages the main event loop.
    """

    def __init__(self, vault_path: Optional[Path] = None):
        self.vault_path = vault_path or settings.vault_path
        self.db = TaskDatabase(DB_PATH)
        self.observers: List[Observer] = []

        self._setup_vault()

    def _setup_vault(self):
        """Create all required vault folders."""
        folders = [
            "Inbox",
            "Inbox/Drop",
            "Needs_Action",
            "Processing",
            "Plans",
            "Pending_Approval",
            "Approved",
            "Rejected",
            "Done",
            "Logs",
        ]
        for folder in folders:
            (self.vault_path / folder).mkdir(parents=True, exist_ok=True)

        logger.info(f"✅ Vault ready: {self.vault_path}")

    def _start_monitors(self):
        """Start folder monitors."""
        monitors = [
            (
                "Needs_Action/",
                NeedsActionMonitor(self.db, self.vault_path),
                self.vault_path / "Needs_Action",
            ),
            (
                "Approved/",
                ApprovedMonitor(self.db, self.vault_path),
                self.vault_path / "Approved",
            ),
        ]

        for label, handler, path in monitors:
            obs = Observer()
            obs.schedule(handler, str(path), recursive=False)
            obs.start()
            self.observers.append(obs)
            logger.info(f"   👁️  Watching: {label}")

    def _start_watchers(self):
        """Start input watchers as daemon threads."""

        # Filesystem watcher — watches Inbox/Drop/
        try:
            from watchers.filesystem_watcher import FilesystemWatcher

            drop_folder = self.vault_path / "Inbox" / "Drop"
            fs_watcher = FilesystemWatcher(str(self.vault_path), str(drop_folder), self.db)
            t = threading.Thread(target=fs_watcher.run, daemon=True, name="FilesystemWatcher")
            t.start()
            time.sleep(1)
            if t.is_alive():
                logger.info("   ✅ Filesystem watcher running (Inbox/Drop/)")
            else:
                logger.error("   ❌ Filesystem watcher died on startup")
        except ImportError:
            logger.warning("   ⚠️  FilesystemWatcher not found — skipping")
        except Exception as e:
            logger.error(f"   ❌ FilesystemWatcher error: {e}")

        # Gmail watcher — optional, skipped if not configured
        try:
            from watchers.gmail_watcher import GmailWatcher

            gmail = GmailWatcher(
                vault_path=str(self.vault_path),
                credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"),
            )
            threading.Thread(target=gmail.run, daemon=True, name="GmailWatcher").start()
            logger.info("   ✅ Gmail watcher running")
        except ImportError:
            logger.warning("   ⚠️  Gmail libraries not installed — skipping")
        except Exception as e:
            logger.warning(f"   ⚠️  Gmail watcher skipped: {e}")

    def run(self):
        logger.info("=" * 60)
        logger.info("🤖  AI EMPLOYEE — LOCAL MODE")
        logger.info("=" * 60)
        logger.info(f"Vault:    {self.vault_path}")
        logger.info(f"Database: {DB_PATH}")
        logger.info(f"Command:  {' '.join(CLAUDE_COMMAND)}")
        logger.info("=" * 60)

        self._start_monitors()
        self._start_watchers()

        logger.info("✅ Running. Drop files into Inbox/Drop/ to start.")
        logger.info("   Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            logger.info("\n⏹️  Stopping...")
            self.stop()

    def stop(self):
        for obs in self.observers:
            obs.stop()
            obs.join()
        logger.info("✅ Stopped cleanly.")


# =============================================================================
# Entry point
# =============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI Employee — Local Mode")
    parser.add_argument("--vault", type=str, help="Path to vault (overrides config)")
    args = parser.parse_args()

    vault_path = Path(args.vault).resolve() if args.vault else None
    Orchestrator(vault_path).run()


if __name__ == "__main__":
    main()
