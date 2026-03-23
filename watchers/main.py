#!/usr/bin/env python3
"""
watchers/main.py - Entry point for AI Employee watchers (v2)

Runs all enabled watchers (filesystem, gmail, whatsapp) to detect new tasks
and create metadata files in the vault.

v2 Changes:
- Integrated with LoggingManager
- Uses settings from core.config
- Supports Gmail watcher with enable flag
- WhatsApp watcher planned for future

Usage:
    python watchers/main.py

Or run a specific watcher:
    python -m watchers.filesystem_watcher
    python -m watchers.gmail_watcher
"""

import sys
import time
import threading
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from core.config import settings
from utils.logging_manager import LoggingManager

logger = LoggingManager()


def run_filesystem_watcher():
    """Run the filesystem watcher (Drop folder monitor)."""
    from watchers.filesystem_watcher import FilesystemWatcher

    logger.write_to_timeline("Starting Filesystem Watcher", actor="orchestrator", message_level="INFO")

    watcher = FilesystemWatcher()

    try:
        watcher.run()
    except KeyboardInterrupt:
        logger.write_to_timeline("Filesystem Watcher stopped by user", actor="orchestrator", message_level="INFO")


def run_gmail_watcher():
    """Run the Gmail watcher (watches for new emails)."""
    from watchers.gmail_watcher import GmailWatcher

    logger.write_to_timeline("Starting Gmail Watcher", actor="orchestrator", message_level="INFO")

    try:
        # Determine credentials path
        creds_path = settings.gmail_credentials_path
        if creds_path is None:
            creds_path = settings.vault_path / "credentials.json"

        watcher = GmailWatcher(
            credentials_path=creds_path,
            check_interval=settings.gmail_watcher_check_interval,
            gmail_query=settings.gmail_watcher_query,
        )

        if watcher.service:
            watcher.run()
        else:
            logger.log_warning(
                "Gmail Watcher not started - authentication failed",
                actor="gmail_watcher",
            )

    except ImportError as e:
        logger.log_error(
            f"Gmail Watcher not available - libraries not installed: {e}",
            actor="gmail_watcher",
        )
    except KeyboardInterrupt:
        logger.write_to_timeline("Gmail Watcher stopped by user", actor="orchestrator", message_level="INFO")
    except Exception as e:
        logger.log_error(
            f"Gmail Watcher error: {e}",
            actor="gmail_watcher",
        )


def run_all_watchers():
    """
    Run all enabled watchers.

    FilesystemWatcher: Watches Drop/ folder for new files
    GmailWatcher: Watches Gmail for new unread/important messages
    WhatsappWatcher: Planned for future
    """
    logger.write_to_timeline("Starting all enabled watchers", actor="orchestrator", message_level="INFO")

    threads = []

    # Run filesystem watcher if enabled
    if settings.enable_filesystem_watcher:
        logger.write_to_timeline("Filesystem watcher is enabled", actor="orchestrator", message_level="INFO")
        t = threading.Thread(target=run_filesystem_watcher, daemon=True, name="FilesystemWatcher")
        t.start()
        threads.append(t)
    else:
        logger.write_to_timeline("Filesystem watcher is disabled in settings", actor="orchestrator", message_level="INFO")

    # Run Gmail watcher if enabled
    if settings.enable_gmail_watcher:
        logger.write_to_timeline("Gmail watcher is enabled", actor="orchestrator", message_level="INFO")
        t = threading.Thread(target=run_gmail_watcher, daemon=True, name="GmailWatcher")
        t.start()
        threads.append(t)
    else:
        logger.write_to_timeline("Gmail watcher is disabled in settings", actor="orchestrator", message_level="INFO")

    if not threads:
        logger.write_to_timeline(
            "No watchers enabled - check settings in .env file",
            actor="orchestrator",
            message_level="WARNING",
        )
        return

    # Wait for all watcher threads
    try:
        while True:
            time.sleep(60)
            # Check if any threads are still alive
            alive_threads = [t for t in threads if t.is_alive()]
            if not alive_threads:
                logger.write_to_timeline(
                    "All watcher threads stopped",
                    actor="orchestrator",
                    message_level="WARNING",
                )
                break
    except KeyboardInterrupt:
        logger.write_to_timeline("Watcher service interrupted by user", actor="orchestrator", message_level="INFO")


def main():
    """Main entry point."""
    # Ensure vault directories exist
    settings.ensure_vault_directories()

    logger.write_to_timeline("=" * 70, actor="orchestrator", message_level="INFO")
    logger.write_to_timeline("AI Employee - Watcher Service v2", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline("=" * 70, actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Vault path: {settings.vault_path}", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Drop folder: {settings.drop_folder_path}", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Filesystem watcher: {'Enabled' if settings.enable_filesystem_watcher else 'Disabled'}", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Gmail watcher: {'Enabled' if settings.enable_gmail_watcher else 'Disabled'}", actor="orchestrator", message_level="INFO")
    if settings.enable_gmail_watcher:
        logger.write_to_timeline(f"Gmail query: {settings.gmail_watcher_query}", actor="orchestrator", message_level="INFO")
        logger.write_to_timeline(f"Gmail interval: {settings.gmail_watcher_check_interval}s", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline("=" * 70, actor="orchestrator", message_level="INFO")

    # Run all enabled watchers
    run_all_watchers()


if __name__ == "__main__":
    main()
