#!/usr/bin/env python3
"""
watchers/main.py - Entry point for AI Employee watchers

Runs all enabled watchers (filesystem, gmail, whatsapp) to detect new tasks
and create metadata files in the vault.

Usage:
    python watchers/main.py

Or run a specific watcher:
    python -m watchers.filesystem_watcher
"""

import sys
import time
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


def run_all_watchers():
    """
    Run all enabled watchers.

    Currently only runs FilesystemWatcher.
    GmailWatcher and WhatsappWatcher are planned for future.
    """
    logger.write_to_timeline("Starting all enabled watchers", actor="orchestrator", message_level="INFO")

    # Run filesystem watcher if enabled
    if settings.enable_filesystem_watcher:
        logger.write_to_timeline("Filesystem watcher is enabled", actor="orchestrator", message_level="INFO")
        run_filesystem_watcher()
    else:
        logger.write_to_timeline("Filesystem watcher is disabled in settings", actor="orchestrator", message_level="INFO")


def main():
    """Main entry point."""
    # Ensure vault directories exist
    settings.ensure_vault_directories()

    logger.write_to_timeline("=" * 70, actor="orchestrator", message_level="INFO")
    logger.write_to_timeline("AI Employee - Watcher Service", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline("=" * 70, actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Vault path: {settings.vault_path}", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Drop folder: {settings.drop_folder_path}", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Check interval: {settings.check_interval}s", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline(f"Dev mode: {settings.dev_mode}", actor="orchestrator", message_level="INFO")
    logger.write_to_timeline("=" * 70, actor="orchestrator", message_level="INFO")

    # Run all enabled watchers
    run_all_watchers()


if __name__ == "__main__":
    main()
