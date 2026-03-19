# complex version before the claude code generated the simplified(actual current version)




#!/usr/bin/env python3
"""
orchestrator.py - AI Employee Orchestrator (All Bugs Fixed + CCR Support)

Fix log vs this uploaded version:

  FIX 1 (CRITICAL): --output-format text is not a valid Claude Code flag.
                    It caused every Claude invocation to fail with "unknown flag".
                    Removed entirely — "-p prompt" is all that's needed.

  FIX 2 (CRITICAL): _get_task_id() called inside NeedsActionMonitor timeout
                    handler but only defined on ApprovedMonitor → AttributeError.
                    Moved to module-level get_task_id_from_file() shared by both.
                    task_id now passed explicitly into _invoke_skill() so the
                    except block can use it without re-reading the file.

  FIX 3 (MODERATE): skill_mapping still had "email-triage" (wrong name),
                    "whatsapp_message" (wrong type key), and no linkedin_dm.
                    All three now correctly map to inbox-conductor.

  FIX 4 (MODERATE): _get_claude_env() called load_dotenv() mid-run, inside
                    every subprocess call — too late, wrong scope.
                    .env is now loaded once at module startup via load_dotenv()
                    at the top of the file. _get_claude_env() just reads the
                    already-loaded env and injects CCR vars if needed.

  FIX 5 (MODERATE): No CCR support. Added full CCR integration controlled
                    entirely by .env — flip CCR_MODE=true to route through
                    Gemini, OpenAI, Ollama, or any CCR-supported model.
                    Zero code changes needed to switch modes.

  FIX 6 (MINOR):    task_id scoped to _process_action_file but used in
                    _trigger_claude_skill's except block. Now passed explicitly
                    as a parameter so it's always available.
"""

import os
import sys
import time
import subprocess
import threading
import json
import logging
import traceback
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, List
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# ── Load .env ONCE at startup — before anything else reads os.environ ────────
# FIX 4: original code called load_dotenv() inside every subprocess call,
# which modifies os.environ of the current process too late to matter.
# Loading here ensures all os.getenv() calls below see the correct values.
try:
    from dotenv import load_dotenv
    _env_file = Path(__file__).parent.parent / ".env"
    if _env_file.exists():
        load_dotenv(str(_env_file))
        logging.getLogger(__name__).debug(f".env loaded from {_env_file}")
except ImportError:
    pass  # python-dotenv not installed — rely on shell environment

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import TaskDatabase
from logging_utils import setup_logging
from core import settings

logger = setup_logging(settings.log_dir)

DB_PATH = project_root / "database" / "tasks.db"

# ── CCR Configuration — read once from environment ───────────────────────────
# FIX 5: added full CCR support. Control everything from .env:
#
#   Standard mode (default):
#     CCR_MODE=false
#
#   CCR proxy mode (routes through local CCR server):
#     CCR_MODE=true
#     CCR_MODEL=gemini/gemini-2.0-flash
#     ANTHROPIC_BASE_URL=http://localhost:3000
#
#   CCR binary wrapper mode:
#     CCR_MODE=true
#     CCR_MODEL=gemini/gemini-2.0-flash
#     CCR_BINARY=ccr
#
CCR_MODE       = os.getenv("CCR_MODE", "false").lower() == "true"
CCR_MODEL      = os.getenv("CCR_MODEL", "gemini/gemini-2.0-flash")
CCR_BINARY     = os.getenv("CCR_BINARY", "ccr")
CLAUDE_BIN     = os.getenv("CLAUDE_BIN", "claude")
CCR_PROXY_URL  = os.getenv("ANTHROPIC_BASE_URL", "")   # e.g. http://localhost:3000


# =============================================================================
# Module-level helpers
# =============================================================================

def get_task_id_from_file(file_path: Path) -> str:
    """
    Extract task_id from a file's YAML frontmatter.
    Falls back to a timestamp ID if not found.

    FIX 2: was duplicated on ApprovedMonitor only, then called on
    NeedsActionMonitor — AttributeError on timeout. Now a shared
    module-level function used by both monitors.
    """
    try:
        content = file_path.read_text(encoding="utf-8")
        for line in content.split("\n")[1:]:
            if line.strip() == "---":
                break
            if line.startswith("task_id:"):
                return line.split(":", 1)[1].strip()
    except Exception:
        pass
    return f"task_{int(time.time())}"


def build_claude_env() -> dict:
    """
    Build the environment dict for Claude Code subprocess calls.

    FIX 4: no longer calls load_dotenv() here — that runs once at module
    startup above. This function just reads the already-loaded environment
    and injects CCR-specific variables when CCR_MODE is enabled.

    FIX 5: in CCR proxy mode, ANTHROPIC_BASE_URL is injected here so
    Claude Code redirects all API calls to the CCR local proxy instead
    of hitting api.anthropic.com directly.
    """
    env = os.environ.copy()

    # Ensure API key is present (should already be from load_dotenv at top)
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if api_key:
        env["ANTHROPIC_API_KEY"] = api_key

    # CCR proxy mode: redirect Claude Code's API calls to CCR server
    if CCR_MODE and CCR_PROXY_URL:
        env["ANTHROPIC_BASE_URL"] = CCR_PROXY_URL

    return env


def build_claude_command(prompt: str, vault_path: Path) -> list:
    """
    Build the correct subprocess command for Claude Code.

    FIX 1: removed --output-format text — not a valid Claude Code flag,
    caused every invocation to fail with "unknown flag" error.

    FIX 5: CCR support added. Two CCR modes:
      - Proxy mode:  command identical to standard, env var does the work
      - Binary mode: "ccr claude -p prompt --cwd vault"

    Args:
        prompt:     The instruction for Claude Code.
        vault_path: Vault root — Claude Code loads skills from .claude/skills/.

    Returns:
        List of command parts ready for subprocess.run()
    """
    if not CCR_MODE:
        # Standard mode — direct Anthropic API
        return [
            CLAUDE_BIN,
            "-p", prompt,
            "--cwd", str(vault_path),
        ]

    if CCR_PROXY_URL:
        # CCR proxy mode — same command, ANTHROPIC_BASE_URL env var intercepts
        return [
            CLAUDE_BIN,
            "-p", prompt,
            "--cwd", str(vault_path),
            "--model", CCR_MODEL,
        ]

    # CCR binary wrapper mode — "ccr claude -p ..."
    return [
        CCR_BINARY,
        "claude",
        "-p", prompt,
        "--cwd", str(vault_path),
        "--model", CCR_MODEL,
    ]


def invoke_claude(
    prompt: str,
    vault_path: Path,
    timeout: int = 300,
) -> subprocess.CompletedProcess:
    """
    Single entry point for all Claude Code invocations.

    Handles standard mode, CCR proxy mode, and CCR binary mode
    transparently based on environment variables.

    Returns a CompletedProcess in all cases — callers don't need
    to handle TimeoutExpired or FileNotFoundError themselves.
    """
    cmd = build_claude_command(prompt, vault_path)
    env = build_claude_env()

    mode_label = f"CCR ({CCR_MODEL})" if CCR_MODE else "Standard"
    logger.debug(f"Invoking Claude [{mode_label}]: {' '.join(cmd[:3])}...")

    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(vault_path),
            env=env,
        )
    except subprocess.TimeoutExpired:
        fake = subprocess.CompletedProcess(cmd, returncode=-1)
        fake.stdout = ""
        fake.stderr = f"Claude Code timed out after {timeout}s"
        return fake
    except FileNotFoundError:
        binary = CCR_BINARY if CCR_MODE and not CCR_PROXY_URL else CLAUDE_BIN
        fake = subprocess.CompletedProcess(cmd, returncode=-2)
        fake.stdout = ""
        fake.stderr = (
            f"Binary '{binary}' not found. "
            f"{'Install CCR first.' if CCR_MODE else 'Install with: npm install -g @anthropic/claude-code'}"
        )
        return fake


# =============================================================================
# EventRouter
# =============================================================================

class EventRouter:
    """
    Classifies incoming vault files and assigns the correct Claude Skill.
    """

    def __init__(self, db: TaskDatabase, vault_path: Path):
        self.db         = db
        self.vault_path = vault_path
        self.logger     = logging.getLogger(__name__)

    def classify_event(self, metadata_path: Path) -> Dict[str, Any]:
        content  = metadata_path.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(content)

        event_type       = metadata.get("type", "unknown")
        priority         = metadata.get("priority", "normal")
        skill            = self._assign_skill(event_type, metadata)
        approval_needed  = self._check_approval_required(event_type, metadata)

        return {
            "event_type":        event_type,
            "priority":          priority,
            "assigned_skill":    skill,
            "approval_required": approval_needed,
            "metadata":          metadata,
        }

    def _assign_skill(self, event_type: str, metadata: Dict) -> str:
        """
        Map Watcher-produced file types to Claude Skill names.

        FIX 3: original mapping had three errors:
          - "email-triage"    → wrong name, skill is "inbox-conductor"
          - "whatsapp_message"→ wrong key, Watcher writes type: whatsapp
          - linkedin_dm       → missing entirely
        All three channels now correctly route to inbox-conductor.
        """
        skill_mapping = {
            # ── All communications → inbox-conductor ─────────────────────
            "email":        "inbox-conductor",   # Gmail Watcher
            "whatsapp":     "inbox-conductor",   # WhatsApp Watcher (was "whatsapp_message")
            "linkedin_dm":  "inbox-conductor",   # LinkedIn Watcher (was missing)
            "message":      "inbox-conductor",   # generic fallback

            # ── Business operations ───────────────────────────────────────
            "invoice":          "invoice-generator",
            "payment_request":  "payment-processor",

            # ── Files & documents ─────────────────────────────────────────
            "file_drop":    "file-processor",
            "document":     "document-analyzer",
        }

        skill = skill_mapping.get(event_type)

        if skill is None:
            self.logger.warning(
                f"Unknown event type '{event_type}' → defaulting to file-processor. "
                f"Add it to skill_mapping if this type recurs."
            )
            skill = "file-processor"

        return skill

    def _check_approval_required(self, event_type: str, metadata: Dict) -> bool:
        """Determine if this event requires human approval before execution."""
        # Always require approval for financial types
        if event_type in {"payment_request", "invoice"}:
            return True

        # WhatsApp and LinkedIn always need HITL (per inbox-conductor skill design)
        if event_type in {"whatsapp", "linkedin_dm"}:
            return True

        # Check keywords — iterate the list properly (not str(list))
        keywords = metadata.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [kw.strip() for kw in keywords.split(",")]

        approval_keywords = {"payment", "approve", "authorize", "urgent", "legal", "contract"}
        return any(
            kw.lower() in approval_keywords
            for kw in keywords
            if isinstance(kw, str)
        )

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown content."""
        metadata: Dict[str, Any] = {}
        lines = content.split("\n")

        if not lines or lines[0].strip() != "---":
            return metadata

        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" not in line:
                continue

            key, _, raw = line.partition(":")
            key = key.strip()
            val: Any = raw.strip()

            if val.lower() == "true":
                val = True
            elif val.lower() == "false":
                val = False
            elif val.startswith("[") and val.endswith("]"):
                val = [v.strip().strip("'\"") for v in val[1:-1].split(",") if v.strip()]

            metadata[key] = val

        return metadata


# =============================================================================
# NeedsActionMonitor
# =============================================================================

class NeedsActionMonitor(FileSystemEventHandler):
    """
    Watches /Needs_Action/ for Watcher-created files.
    Classifies each and invokes the correct Claude Skill.
    """

    def __init__(self, db: TaskDatabase, vault_path: Path, router: EventRouter):
        self.db           = db
        self.vault_path   = vault_path
        self.router       = router
        self.logger       = logging.getLogger(__name__)
        self.needs_action = vault_path / "Needs_Action"
        self.processing   = vault_path / "Processing"
        self.processing_files: set = set()

    def on_created(self, event):
        if event.is_directory:
            return

        src_path = Path(event.src_path)
        if src_path.name.startswith(".") or src_path.suffix != ".md":
            return

        if src_path.name in self.processing_files:
            self.logger.debug(f"Already processing: {src_path.name}")
            return

        self.processing_files.add(src_path.name)
        try:
            time.sleep(0.5)  # wait for file write to complete
            if src_path.exists():
                self._process_action_file(src_path)
            else:
                self.logger.warning(f"File disappeared before processing: {src_path.name}")
        except Exception as e:
            self.logger.error(f"Error processing {src_path.name}: {e}", exc_info=True)
        finally:
            self.processing_files.discard(src_path.name)

    def _process_action_file(self, file_path: Path):
        self.logger.info(f"📥 New item: {file_path.name}")

        classification = self.router.classify_event(file_path)
        skill          = classification["assigned_skill"]
        event_type     = classification["event_type"]
        priority       = classification["priority"]
        needs_approval = classification["approval_required"]

        self.logger.info(f"   Type:     {event_type}")
        self.logger.info(f"   Priority: {priority}")
        self.logger.info(f"   Skill:    {skill}")
        self.logger.info(f"   Approval: {'Required' if needs_approval else 'Not required'}")

        # Extract task_id here — shared helper, no AttributeError
        # FIX 2 + FIX 6: extracted here and passed explicitly to _invoke_skill
        task_id = get_task_id_from_file(file_path)

        self.db.update_task_status(task_id, "processing")
        self.db.assign_skill(task_id, skill)

        # Move to Processing/
        processing_path = self.processing / file_path.name
        try:
            if file_path.exists():
                file_path.rename(processing_path)
                self.logger.info(f"   → Processing/")
            else:
                self.logger.debug(f"   File already moved — using original path")
                processing_path = file_path
        except Exception as e:
            self.logger.error(f"Could not move to Processing/: {e}")
            processing_path = file_path

        # FIX 6: pass task_id explicitly so the timeout except block can use it
        self._invoke_skill(processing_path, skill, classification, task_id)

    def _invoke_skill(
        self,
        file_path: Path,
        skill: str,
        classification: Dict,
        task_id: str,          # FIX 6: now a parameter, not re-derived in except
    ):
        """
        Invoke Claude Code with the correct skill via -p flag.

        FIX 1: removed --output-format text (invalid flag).
        FIX 5: uses invoke_claude() which handles CCR transparently.
        Claude Code finds the skill automatically from .claude/skills/{skill}/SKILL.md
        because --cwd points to the vault root.
        """
        needs_approval = classification["approval_required"]

        prompt = (
            f"Use the {skill} skill to process this file: {file_path.name}\n\n"
            f"File location: {file_path}\n\n"
            f"Instructions:\n"
            f"1. Read the file and classify it following the skill's decision tree\n"
            f"2. Assign priority and determine the correct output type\n"
            f"3. Draft the appropriate response with all template variables filled\n"
            f"4. Write outputs to the correct vault folders:\n"
            f"   - Drafts and approval requests → /Pending_Approval/\n"
            f"   - Action plans → /Plans/\n"
            f"   - Archive entries → /Done/\n"
            f"5. Append an audit entry to /Logs/{datetime.now().strftime('%Y-%m-%d')}.json\n"
            f"6. Update the Recent Activity section of /Dashboard.md\n"
            + (
                "7. This item requires human approval — "
                "ensure requires_approval: true is set in all output files.\n"
                if needs_approval else ""
            )
            + "\nDo not send, post, or execute any action directly. "
            "Write approval files for the human to review first. "
            "Follow all rules in Company_Handbook.md."
        )

        mode_label = f"CCR ({CCR_MODEL})" if CCR_MODE else "Standard"
        self.logger.info(f"🤖 Invoking Claude [{mode_label}] with skill: {skill}")

        result = invoke_claude(prompt, self.vault_path)

        if result.returncode == 0:
            self.logger.info(f"✅ Skill completed: {skill}")
            if result.stdout:
                self.logger.debug(f"   Output: {result.stdout[:300]}...")
            self.db.update_task_status(task_id, "pending_approval" if needs_approval else "done")

        elif result.returncode == -1:
            # Timeout — FIX 2: task_id is now available here (was AttributeError before)
            self.logger.error(f"⏱️  Skill timed out after 5 min: {skill}")
            self.db.update_task_status(task_id, "failed", error_message="Claude Code timeout")

        elif result.returncode == -2:
            self.logger.error(f"❌ Claude binary not found: {result.stderr}")
            self.db.update_task_status(task_id, "failed", error_message="Binary not found")

        else:
            self.logger.error(
                f"❌ Skill failed (rc={result.returncode}): {result.stderr[:300]}"
            )
            self.db.update_task_status(
                task_id, "failed", error_message=result.stderr[:200]
            )


# =============================================================================
# ApprovedMonitor
# =============================================================================

class ApprovedMonitor(FileSystemEventHandler):
    """
    Watches /Approved/ for HITL-approved files.
    Executes the action via MCP and moves to /Done/.
    """

    def __init__(self, db: TaskDatabase, vault_path: Path):
        self.db           = db
        self.vault_path   = vault_path
        self.logger       = logging.getLogger(__name__)
        self.approved     = vault_path / "Approved"
        self.done         = vault_path / "Done"
        self.processing_files: set = set()

    def on_created(self, event):
        if event.is_directory:
            return

        src_path = Path(event.src_path)
        if src_path.name.startswith(".") or src_path.suffix != ".md":
            return

        if src_path.name in self.processing_files:
            return

        self.processing_files.add(src_path.name)
        try:
            time.sleep(0.5)
            if src_path.exists():
                self._execute_approved_action(src_path)
        except Exception as e:
            self.logger.error(f"Error executing approved action: {e}", exc_info=True)
        finally:
            self.processing_files.discard(src_path.name)

    def _execute_approved_action(self, approval_file: Path):
        self.logger.info(f"✅ Executing: {approval_file.name}")

        content     = approval_file.read_text(encoding="utf-8")
        metadata    = self._parse_frontmatter(content)
        action_type = metadata.get("action", "unknown")
        channel     = metadata.get("channel", "email")

        self.logger.info(f"   Action:  {action_type}")
        self.logger.info(f"   Channel: {channel}")

        dispatch = {
            "send_email":    self._execute_email_send,
            "send_whatsapp": self._execute_whatsapp_send,
            "payment":       self._execute_payment,
        }
        handler = dispatch.get(action_type, self._execute_generic_action)
        handler(approval_file, metadata)

    def _execute_email_send(self, approval_file: Path, metadata: Dict):
        self.logger.info(f"   📧 Email → {metadata.get('to', 'unknown')}")
        # TODO: replace with actual email-mcp call
        self._complete_action(approval_file, "Email queued via email-mcp")

    def _execute_whatsapp_send(self, approval_file: Path, metadata: Dict):
        self.logger.info(f"   💬 WhatsApp → {metadata.get('phone', 'unknown')}")
        # TODO: replace with actual whatsapp-mcp call
        self._complete_action(approval_file, "WhatsApp message queued via whatsapp-mcp")

    def _execute_payment(self, approval_file: Path, metadata: Dict):
        amount    = metadata.get("amount", 0)
        recipient = metadata.get("recipient", "unknown")
        self.logger.info(f"   💰 Payment ${amount} → {recipient}")
        # TODO: replace with actual payment-mcp call
        # NEVER auto-execute — always log and confirm
        self._complete_action(approval_file, f"Payment ${amount} to {recipient} queued")

    def _execute_generic_action(self, approval_file: Path, metadata: Dict):
        self.logger.warning(f"   ⚙️  Unknown action type — logged only")
        self._complete_action(approval_file, "Unknown action type — logged")

    def _complete_action(self, approval_file: Path, result_note: str):
        """Move to /Done/ and ask Claude to update Dashboard."""
        done_path = self.done / approval_file.name
        try:
            approval_file.rename(done_path)
            self.logger.info(f"   → Done/")
        except Exception as e:
            self.logger.error(f"Could not move to Done/: {e}")

        # Ask Claude to update Dashboard — short timeout, best-effort
        prompt = (
            f"The action file {approval_file.name} was approved and executed. "
            f"Result: {result_note}. "
            f"Append one line to the Recent Activity section of /Dashboard.md "
            f"with the current timestamp and this result."
        )
        invoke_claude(prompt, self.vault_path, timeout=60)

    def _parse_frontmatter(self, content: str) -> Dict:
        metadata: Dict = {}
        lines = content.split("\n")
        if not lines or lines[0].strip() != "---":
            return metadata
        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, _, val = line.partition(":")
                metadata[key.strip()] = val.strip()
        return metadata


# =============================================================================
# Orchestrator
# =============================================================================

class Orchestrator:
    """
    Master process: starts all monitors, all watchers, runs the event loop.
    """

    def __init__(self, vault_path: Optional[Path] = None, config: Optional[Dict] = None):
        self.vault_path = vault_path or settings.vault_path
        self.config     = config or {}
        self.logger     = logging.getLogger(__name__)
        self.db         = TaskDatabase(DB_PATH)
        self.router     = EventRouter(self.db, self.vault_path)
        self.observers: List[Observer] = []
        self._setup_vault_structure()

    def _setup_vault_structure(self):
        required = [
            "Inbox", "Inbox/Drop",
            "Needs_Action", "Processing",
            "Plans", "Pending_Approval",
            "Approved", "Rejected", "Done",
            "Logs", "Accounting", "Briefings",
            "Needs_Revision",
        ]
        for d in required:
            (self.vault_path / d).mkdir(parents=True, exist_ok=True)
        self.logger.info(f"✅ Vault structure verified: {self.vault_path}")

    def start_file_monitors(self):
        self.logger.info("👁️  Starting folder monitors...")

        monitors = [
            (
                "Needs_Action/",
                NeedsActionMonitor(self.db, self.vault_path, self.router),
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
            self.logger.info(f"   ✅ Monitoring: {label}")

    def _start_watchers(self):
        """Start all Watcher scripts as background daemon threads."""
        self.logger.info("Starting watchers...")

        # ── Filesystem Watcher ────────────────────────────────────────────
        if self.config.get("enable_filesystem_watcher", True):
            try:
                from watchers.filesystem_watcher import FilesystemWatcher
                drop_folder = self.vault_path / "Inbox" / "Drop"
                drop_folder.mkdir(parents=True, exist_ok=True)
                fs_watcher = FilesystemWatcher(
                    str(self.vault_path), str(drop_folder), self.db
                )
                t = threading.Thread(
                    target=fs_watcher.run, daemon=True, name="FilesystemWatcher"
                )
                t.start()
                time.sleep(1)
                if t.is_alive():
                    self.logger.info("✅ Filesystem watcher started (Inbox/Drop)")
                else:
                    self.logger.error("❌ Filesystem watcher thread died immediately")
            except ImportError:
                self.logger.warning("⚠️  FilesystemWatcher not found — skipping")
            except Exception as e:
                self.logger.error(f"❌ Filesystem watcher error: {e}\n{traceback.format_exc()}")

        # ── Gmail Watcher ─────────────────────────────────────────────────
        try:
            from watchers.gmail_watcher import GmailWatcher
            gmail_watcher = GmailWatcher(
                vault_path=str(self.vault_path),
                credentials_path=os.getenv("GMAIL_CREDENTIALS_PATH", "credentials.json"),
            )
            threading.Thread(
                target=gmail_watcher.run, daemon=True, name="GmailWatcher"
            ).start()
            self.logger.info("✅ Gmail watcher started")
        except ImportError:
            self.logger.warning(
                "⚠️  GmailWatcher not found — skipping "
                "(pip install google-api-python-client google-auth-oauthlib)"
            )
        except Exception as e:
            self.logger.warning(f"⚠️  Gmail watcher failed to start: {e}")

        # ── WhatsApp Watcher ──────────────────────────────────────────────
        try:
            from watchers.whatsapp_watcher import WhatsAppWatcher
            wa_watcher = WhatsAppWatcher(
                vault_path=str(self.vault_path),
                session_path=os.getenv("WHATSAPP_SESSION_PATH", ".whatsapp_session"),
            )
            threading.Thread(
                target=wa_watcher.run, daemon=True, name="WhatsAppWatcher"
            ).start()
            self.logger.info("✅ WhatsApp watcher started")
        except ImportError:
            self.logger.warning(
                "⚠️  WhatsAppWatcher not found — skipping (pip install playwright)"
            )
        except Exception as e:
            self.logger.warning(f"⚠️  WhatsApp watcher failed to start: {e}")

    def run(self):
        mode_label = f"CCR mode ({CCR_MODEL})" if CCR_MODE else "Standard mode"

        self.logger.info("=" * 70)
        self.logger.info("🤖  AI EMPLOYEE ORCHESTRATOR")
        self.logger.info("=" * 70)
        self.logger.info(f"Vault:    {self.vault_path}")
        self.logger.info(f"Database: {DB_PATH}")
        self.logger.info(f"Claude:   {mode_label}")
        self.logger.info("=" * 70)

        self.start_file_monitors()
        self._start_watchers()

        self.logger.info("✅ System running. Press Ctrl+C to stop.")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            self.logger.info("\n⏹️  Shutting down...")
            self.stop()

    def stop(self):
        for obs in self.observers:
            obs.stop()
            obs.join()
        self.logger.info("✅ Orchestrator stopped cleanly.")


# =============================================================================
# Entry point
# =============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI Employee Orchestrator")
    parser.add_argument("--vault",  type=str, help="Path to Obsidian vault")
    parser.add_argument("--config", type=str, help="Path to JSON config (deprecated)")
    args = parser.parse_args()

    config = {}
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            config = json.load(f)

    vault_path = Path(args.vault).resolve() if args.vault else None
    Orchestrator(vault_path, config).run()


if __name__ == "__main__":
    main()



















