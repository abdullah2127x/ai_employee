# Watchers Module

This is a Python package within the main `ai-employee` project.

**Not a separate project** - uses parent project's virtual environment and dependencies.

## Modules

- `base_watcher.py` - Base class for all watchers
- `filesystem_watcher.py` - File drop monitoring
- `gmail_watcher.py` - Gmail API integration (future)

## Usage

```python
from watchers import FilesystemWatcher
from database import TaskDatabase

db = TaskDatabase('database/tasks.db')
watcher = FilesystemWatcher('./vault', './vault/Inbox/Drop', db)
watcher.run()
```
