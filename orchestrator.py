#!/usr/bin/env python3
"""
orchestrator.py - Enhanced AI Employee Orchestrator

Main coordination process that:
- Manages all watchers (Gmail, WhatsApp, Filesystem, etc.)
- Routes events to appropriate Claude Skills
- Manages task state and lifecycle
- Handles human-in-the-loop approvals
- Tracks all actions in SQLite database
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
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from database import TaskDatabase
from logging_utils import setup_logging
from core import settings, get_settings

logger = setup_logging(settings.log_dir)

# Database path
DB_PATH = project_root / "database" / "tasks.db"


class EventRouter:
    """
    Routes events to appropriate handlers based on file type and metadata.

    Analyzes incoming files and determines:
    - What type of event this is
    - Which Claude Skill should handle it
    - What priority it should have
    - Whether approval is required
    """

    def __init__(self, db: TaskDatabase, vault_path: Path):
        self.db = db
        self.vault_path = vault_path
        self.logger = logging.getLogger(__name__)

    def classify_event(self, metadata_path: Path) -> Dict[str, Any]:
        """
        Classify an event based on its metadata file.

        Args:
            metadata_path: Path to the metadata .md file

        Returns:
            Classification result with skill assignment and routing info
        """
        # Read metadata
        content = metadata_path.read_text(encoding="utf-8")

        # Parse frontmatter (simple YAML-like parsing)
        metadata = self._parse_frontmatter(content)

        event_type = metadata.get("type", "unknown")
        priority = metadata.get("priority", "normal")

        # Determine which skill should handle this
        skill_assignment = self._assign_skill(event_type, metadata)

        # Determine if approval is required
        approval_required = self._check_approval_required(event_type, metadata)

        return {
            "event_type": event_type,
            "priority": priority,
            "assigned_skill": skill_assignment,
            "approval_required": approval_required,
            "metadata": metadata,
        }

    def _parse_frontmatter(self, content: str) -> Dict[str, Any]:
        """Parse YAML frontmatter from markdown content."""
        metadata = {}
        lines = content.split("\n")

        if not lines or lines[0].strip() != "---":
            return metadata

        in_frontmatter = False
        for line in lines[1:]:
            if line.strip() == "---":
                break

            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Parse value types
                if value.lower() == "true":
                    value = True
                elif value.lower() == "false":
                    value = False
                elif value.startswith("[") and value.endswith("]"):
                    # Simple list parsing
                    value = [v.strip() for v in value[1:-1].split(",")]

                metadata[key] = value

        return metadata

    def _assign_skill(self, event_type: str, metadata: Dict) -> str:
        """Assign appropriate skill based on event type."""
        skill_mapping = {
            "file_drop": "file-processor",
            "email": "email-triage",
            "whatsapp_message": "message-processor",
            "invoice": "invoice-generator",
            "payment_request": "payment-processor",
            "document": "document-analyzer",
        }

        return skill_mapping.get(event_type, "file-processor")

    def _check_approval_required(self, event_type: str, metadata: Dict) -> bool:
        """Check if this event type requires human approval."""
        # Events that always require approval
        approval_types = ["payment_request", "invoice"]

        if event_type in approval_types:
            return True

        # Check for specific keywords
        keywords = metadata.get("keywords", [])
        if isinstance(keywords, str):
            keywords = [keywords]

        approval_keywords = ["payment", "approve", "authorize", "urgent"]
        return any(kw in str(keywords).lower() for kw in approval_keywords)


class NeedsActionMonitor(FileSystemEventHandler):
    """
    Monitors Needs_Action folder for new items requiring processing.

    When a new file is detected:
    1. Classifies the event
    2. Updates task state in database
    3. Triggers Claude Code with appropriate skill
    4. Moves file to Processing folder
    """

    def __init__(self, db: TaskDatabase, vault_path: Path, router: EventRouter):
        self.db = db
        self.vault_path = vault_path
        self.router = router
        self.logger = logging.getLogger(__name__)

        # Folders
        self.needs_action = vault_path / "Needs_Action"
        self.processing = vault_path / "Processing"

        # Track files being processed to avoid duplicates
        self.processing_files = set()

    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return

        # Ignore system files
        src_path = Path(event.src_path)
        if src_path.name.startswith(".") or src_path.suffix != ".md":
            return

        # Avoid duplicate processing
        if src_path.name in self.processing_files:
            self.logger.debug(f"Already processing: {src_path.name}")
            return

        self.processing_files.add(src_path.name)

        try:
            # Wait for file to be fully written
            time.sleep(0.5)

            if not src_path.exists():
                self.logger.warning(f"File disappeared: {src_path.name}")
                return

            # Process the file
            self._process_action_file(src_path)

        except Exception as e:
            self.logger.error(f"Error processing {src_path.name}: {e}", exc_info=True)
        finally:
            self.processing_files.discard(src_path.name)

    def _process_action_file(self, file_path: Path):
        """
        Process an action file from Needs_Action.

        Args:
            file_path: Path to the action file
        """
        self.logger.info(f"📥 Processing: {file_path.name}")

        # Classify the event
        classification = self.router.classify_event(file_path)

        self.logger.info(f"   Type: {classification['event_type']}")
        self.logger.info(f"   Priority: {classification['priority']}")
        self.logger.info(f"   Skill: {classification['assigned_skill']}")
        self.logger.info(
            f"   Approval: {'Required' if classification['approval_required'] else 'Not required'}"
        )

        # Extract task_id from metadata
        content = file_path.read_text(encoding="utf-8")
        metadata = self.router._parse_frontmatter(content)
        task_id = metadata.get("task_id", f"task_{int(time.time())}")

        # Update task in database
        self.db.update_task_status(task_id, "processing")
        self.db.assign_skill(task_id, classification["assigned_skill"])

        # Move to Processing folder
        processing_path = self.processing / file_path.name
        try:
            file_path.rename(processing_path)
            self.logger.info(f"   Moved to Processing/")
        except Exception as e:
            self.logger.error(f"Error moving file: {e}")
            processing_path = file_path

        # Trigger Claude Code
        self._trigger_claude_skill(processing_path, classification)

    def _trigger_claude_skill(self, file_path: Path, classification: Dict):
        """
        Trigger Claude Code with the appropriate skill.
        
        Claude Code automatically loads skills from .claude/skills/ directory.
        Skills are referenced by name in the prompt.

        Args:
            file_path: Path to file in Processing folder
            classification: Event classification result
        """
        skill = classification["assigned_skill"]

        self.logger.info(f"🤖 Triggering Claude skill: {skill}")

        try:
            # Build Claude command with skill reference
            # Claude automatically loads skills from .claude/skills/{skill}/SKILL.md
            prompt = f"""Use the {skill} skill to process this file: {file_path.name}

File location: {file_path}

Instructions:
1. Read and understand the content
2. Perform the required actions based on the skill
3. Create any necessary output files (plans, approval requests, etc.)
4. Update the task status appropriately
5. If approval is required, create an approval request file in /Pending_Approval/
6. If complete, move the file to /Done/ with a summary

Remember to follow the Company Handbook rules and Business Goals.
"""

            # Run Claude Code with proper flags
            # Note: Claude Code loads skills automatically from .claude/skills/ directory
            result = subprocess.run(
                [
                    "ccr code",
                    "-p",  # Print mode - execute prompt and exit
                    "--output-format", "text",  # Plain text output
                    prompt
                ],
                cwd=str(self.vault_path),  # Set working directory
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
                env=self._get_claude_env()  # Ensure API key is available
            )

            if result.returncode == 0:
                self.logger.info(f"✅ Claude skill completed successfully")
                if result.stdout:
                    self.logger.debug(f"Output: {result.stdout[:500]}...")
            else:
                self.logger.error(f"❌ Claude skill failed: {result.stderr}")

        except subprocess.TimeoutExpired:
            self.logger.error(f"⏱️  Claude skill timed out (5 min limit)")
            self.db.update_task_status(
                self._get_task_id(file_path), "failed", error_message="Claude Code timeout"
            )
        except FileNotFoundError:
            self.logger.error("❌ Claude Code not found. Is it installed?")
            self.logger.error("   Install with: npm install -g @anthropic/claude-code")
        except Exception as e:
            self.logger.error(f"❌ Error triggering Claude: {e}", exc_info=True)


class ApprovedMonitor(FileSystemEventHandler):
    """
    Monitors Approved folder for items ready to execute.

    When a file appears in Approved:
    1. Reads the approval request
    2. Executes the requested action via MCP or direct action
    3. Logs the result
    4. Moves files to Done
    """

    def __init__(self, db: TaskDatabase, vault_path: Path):
        self.db = db
        self.vault_path = vault_path
        self.logger = logging.getLogger(__name__)

        self.approved = vault_path / "Approved"
        self.done = vault_path / "Done"
        self.processing_files = set()

    def on_created(self, event):
        """Handle approved file creation."""
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

            if not src_path.exists():
                return

            self._execute_approved_action(src_path)

        except Exception as e:
            self.logger.error(f"Error executing approved action: {e}", exc_info=True)
        finally:
            self.processing_files.discard(src_path.name)

    def _execute_approved_action(self, approval_file: Path):
        """Execute an approved action."""
        self.logger.info(f"✅ Executing approved action: {approval_file.name}")

        # Read approval file
        content = approval_file.read_text(encoding="utf-8")
        metadata = self._parse_frontmatter(content)

        action_type = metadata.get("action", "unknown")

        self.logger.info(f"   Action type: {action_type}")

        # Execute based on action type
        if action_type == "send_email":
            self._execute_email_send(approval_file, metadata)
        elif action_type == "payment":
            self._execute_payment(approval_file, metadata)
        else:
            self.logger.warning(f"Unknown action type: {action_type}")
            self._execute_generic_action(approval_file, metadata)

    def _execute_email_send(self, approval_file: Path, metadata: Dict):
        """Execute email send action."""
        self.logger.info("   📧 Sending email...")

        # For now, log the action (actual sending would use MCP)
        to = metadata.get("to", "unknown")
        subject = metadata.get("subject", "No subject")

        self.logger.info(f"   To: {to}")
        self.logger.info(f"   Subject: {subject}")

        # TODO: Integrate with email MCP server
        # For now, just move to Done
        self._complete_action(approval_file, "Email would be sent via MCP")

    def _execute_payment(self, approval_file: Path, metadata: Dict):
        """Execute payment action."""
        self.logger.info("   💰 Processing payment...")

        amount = metadata.get("amount", 0)
        recipient = metadata.get("recipient", "unknown")

        self.logger.info(f"   Amount: ${amount}")
        self.logger.info(f"   Recipient: {recipient}")

        # TODO: Integrate with payment MCP server
        # For now, just log
        self._complete_action(
            approval_file, f"Payment of ${amount} to {recipient} would be processed"
        )

    def _execute_generic_action(self, approval_file: Path, metadata: Dict):
        """Execute a generic approved action."""
        self.logger.info("   ⚙️  Executing generic action...")
        self._complete_action(approval_file, "Action executed")

    def _complete_action(self, approval_file: Path, result: str):
        """Mark an action as complete."""
        # Move to Done
        done_path = self.done / approval_file.name
        try:
            approval_file.rename(done_path)
            self.logger.info(f"   ✅ Moved to Done/")
        except Exception as e:
            self.logger.error(f"Error moving file: {e}")

        self.logger.info(f"   Result: {result}")

    def _parse_frontmatter(self, content: str) -> Dict:
        """Parse YAML frontmatter."""
        metadata = {}
        lines = content.split("\n")

        if not lines or lines[0].strip() != "---":
            return metadata

        for line in lines[1:]:
            if line.strip() == "---":
                break
            if ":" in line:
                key, value = line.split(":", 1)
                metadata[key.strip()] = value.strip()

        return metadata

    def _get_task_id(self, file_path: Path) -> str:
        """Extract task_id from filename or metadata."""
        # Try to get from metadata first
        try:
            content = file_path.read_text(encoding="utf-8")
            metadata = self._parse_frontmatter(content)
            if "task_id" in metadata:
                return metadata["task_id"]
        except:
            pass

        # Fallback to filename-based ID
        return f"task_{int(time.time())}"


class Orchestrator:
    """
    Main orchestrator that coordinates all components.

    Responsibilities:
    - Start/stop all watchers
    - Monitor folder state
    - Update dashboard
    - Handle shutdown gracefully
    """

    def __init__(self, vault_path: Optional[Path] = None, config: Optional[Dict] = None):
        """
        Initialize the orchestrator.

        Args:
            vault_path: Path to Obsidian vault (uses settings if None)
            config: Configuration dictionary (deprecated, use settings)
        """
        self.vault_path = vault_path or settings.vault_path
        self.config = config or {}

        # Initialize database
        self.db = TaskDatabase(DB_PATH)

        # Initialize event router
        self.router = EventRouter(self.db, self.vault_path)

        # Folder monitors
        self.observers: List[Observer] = []

        # Ensure vault structure exists
        self._setup_vault_structure()

        self.logger = logging.getLogger(__name__)

    def _setup_vault_structure(self):
        """Ensure all required vault directories exist."""
        required_dirs = [
            "Inbox",
            "Inbox/Drop",
            "Needs_Action",
            "Processing",
            "Done",
            "Plans",
            "Logs",
            "Pending_Approval",
            "Approved",
            "Rejected",
            "Needs_Revision",
            "Accounting",
        ]

        for dir_name in required_dirs:
            (self.vault_path / dir_name).mkdir(parents=True, exist_ok=True)

        self.logger.info(f"✅ Vault structure verified at: {self.vault_path}")

    def start_file_monitors(self):
        """Start monitoring vault folders."""
        self.logger.info("👁️  Starting folder monitors...")

        # Monitor Needs_Action folder
        needs_action_observer = Observer()
        needs_action_handler = NeedsActionMonitor(self.db, self.vault_path, self.router)
        needs_action_observer.schedule(
            needs_action_handler, str(self.vault_path / "Needs_Action"), recursive=False
        )
        needs_action_observer.start()
        self.observers.append(needs_action_observer)
        self.logger.info(f"   ✅ Monitoring: Needs_Action/")

        # Monitor Approved folder
        approved_observer = Observer()
        approved_handler = ApprovedMonitor(self.db, self.vault_path)
        approved_observer.schedule(
            approved_handler, str(self.vault_path / "Approved"), recursive=False
        )
        approved_observer.start()
        self.observers.append(approved_observer)
        self.logger.info(f"   ✅ Monitoring: Approved/")

    def run(self):
        """Run the orchestrator main loop."""
        self.logger.info("=" * 70)
        self.logger.info("🤖 AI EMPLOYEE ORCHESTRATOR")
        self.logger.info("=" * 70)
        self.logger.info(f"Vault: {self.vault_path}")
        self.logger.info(f"Database: {DB_PATH}")
        self.logger.info("=" * 70)

        # Start file monitors
        self.start_file_monitors()

        # Start watchers (filesystem, gmail, etc.) in separate threads
        self._start_watchers()

        self.logger.info("=" * 70)
        self.logger.info("✅ System is now running. Press Ctrl+C to stop.")
        self.logger.info("=" * 70)

        try:
            while True:
                time.sleep(1)

                # Periodic tasks could go here
                # - Dashboard updates
                # - Health checks
                # - Cleanup old tasks

        except KeyboardInterrupt:
            self.logger.info("\n⏹️  Received interrupt signal")
            self.stop()

    def _start_watchers(self):
        """Start all configured watchers."""
        self.logger.info("Starting watchers...")
        
        # Filesystem watcher
        if self.config.get("enable_filesystem_watcher", True):
            try:
                from watchers.filesystem_watcher import FilesystemWatcher

                drop_folder = self.vault_path / "Inbox" / "Drop"
                drop_folder.mkdir(parents=True, exist_ok=True)
                
                self.logger.info(f"Creating FilesystemWatcher for: {drop_folder}")
                fs_watcher = FilesystemWatcher(str(self.vault_path), str(drop_folder), self.db)

                # Run in background thread
                thread = threading.Thread(target=fs_watcher.run, daemon=True, name="FilesystemWatcher")
                thread.start()
                
                # Wait a moment for it to initialize
                time.sleep(1)
                
                if thread.is_alive():
                    self.logger.info("✅ Filesystem watcher started (Inbox/Drop)")
                else:
                    self.logger.error("❌ Filesystem watcher thread died immediately")
                    
            except Exception as e:
                self.logger.error(f"❌ Error starting FilesystemWatcher: {e}")
                self.logger.error(f"   Stack trace: {traceback.format_exc()}")
        else:
            self.logger.info("Filesystem watcher disabled in config")

    def stop(self):
        """Stop all observers and cleanup."""
        self.logger.info("Stopping orchestrator...")

        # Stop observers
        for observer in self.observers:
            observer.stop()
            observer.join()

        self.logger.info("✅ Orchestrator stopped")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="AI Employee Orchestrator")
    parser.add_argument(
        "--vault", type=str, default=None, help="Path to Obsidian vault (default: from settings)"
    )
    parser.add_argument("--config", type=str, help="Path to configuration file (JSON) (deprecated)")

    args = parser.parse_args()

    # Load config if provided (deprecated)
    config = {}
    if args.config and Path(args.config).exists():
        with open(args.config) as f:
            config = json.load(f)

    # Create and run orchestrator
    vault_path = Path(args.vault).resolve() if args.vault else None
    orchestrator = Orchestrator(vault_path, config)
    orchestrator.run()


if __name__ == "__main__":
    main()
