"""
base_watcher.py - Clean base class for all watchers (Option B)
"""

import time
from pathlib import Path
from abc import ABC, abstractmethod

from utils.logging_manager import LoggingManager


class BaseWatcher(ABC):
    """Base class for all watchers (Gmail, WhatsApp, etc.)."""

    def __init__(self, vault_path: str, check_interval: int = 180):
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval

        self.needs_action.mkdir(parents=True, exist_ok=True)

        # Use centralized LoggingManager
        self.logger = LoggingManager()

        self.logger.write_to_timeline(
            f"Initialized {self.__class__.__name__} | Interval: {check_interval}s",
            actor=self.__class__.__name__.lower().replace("watcher", ""),
            message_level="INFO"
        )

    @abstractmethod
    def check_for_updates(self) -> list:
        """Return list of new items to process."""
        pass

    @abstractmethod
    def create_action_file(self, item) -> Path:
        """Create .md file in Needs_Action/ and return the Path."""
        pass

    def run(self):
        """Main continuous loop."""
        self.logger.write_to_timeline(
            f"Starting {self.__class__.__name__} watcher",
            actor=self.__class__.__name__.lower().replace("watcher", ""),
            message_level="INFO"
        )

        while True:
            try:
                items = self.check_for_updates()

                if items:
                    self.logger.write_to_timeline(
                        f"Found {len(items)} new item(s)",
                        actor=self.__class__.__name__.lower().replace("watcher", ""),
                        message_level="INFO"
                    )
                    for item in items:
                        try:
                            filepath = self.create_action_file(item)
                            if filepath:
                                self.logger.write_to_timeline(
                                    f"Created task: {filepath.name}",
                                    actor=self.__class__.__name__.lower().replace("watcher", ""),
                                    message_level="INFO"
                                )
                        except Exception as e:
                            self.logger.log_error(
                                f"Failed to create action file for item",
                                error=e,
                                actor=self.__class__.__name__.lower().replace("watcher", "")
                            )
                # No else debug log to avoid spam

            except Exception as e:
                self.logger.log_error(
                    f"Error in {self.__class__.__name__} loop",
                    error=e,
                    actor=self.__class__.__name__.lower().replace("watcher", "")
                )

            time.sleep(self.check_interval)