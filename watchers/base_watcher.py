"""
base_watcher.py - Template for all watchers

All watchers inherit from this base class to ensure consistent behavior.
"""
import time
import logging
from pathlib import Path
from abc import ABC, abstractmethod
from datetime import datetime


class BaseWatcher(ABC):
    """Base class for all watcher implementations."""
    
    def __init__(self, vault_path: str, check_interval: int = 60):
        """
        Initialize the watcher.
        
        Args:
            vault_path: Path to the Obsidian vault
            check_interval: Seconds between checks (default: 60)
        """
        self.vault_path = Path(vault_path)
        self.needs_action = self.vault_path / 'Needs_Action'
        self.check_interval = check_interval
        
        # Ensure Needs_Action directory exists
        self.needs_action.mkdir(parents=True, exist_ok=True)
        
        # Set up logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        self.logger = logging.getLogger(self.__class__.__name__)
        
    @abstractmethod
    def check_for_updates(self) -> list:
        """
        Check for new items to process.
        
        Returns:
            List of new items (format depends on watcher type)
        """
        pass
      
    @abstractmethod
    def create_action_file(self, item) -> Path:
        """
        Create a .md file in Needs_Action folder for the item.
        
        Args:
            item: Item to create action file for
            
        Returns:
            Path to the created file
        """
        pass
    
    def run(self):
        """Main loop - runs continuously checking for updates."""
        self.logger.info(f'Starting {self.__class__.__name__}')
        self.logger.info(f'Vault path: {self.vault_path}')
        self.logger.info(f'Check interval: {self.check_interval} seconds')
        
        while True:
            try:
                items = self.check_for_updates()
                if items:
                    self.logger.info(f'Found {len(items)} new item(s)')
                    for item in items:
                        filepath = self.create_action_file(item)
                        self.logger.info(f'Created action file: {filepath}')
                else:
                    self.logger.debug('No new items found')
                    
            except Exception as e:
                self.logger.error(f'Error in {self.__class__.__name__}: {e}', exc_info=True)
                
            time.sleep(self.check_interval)
