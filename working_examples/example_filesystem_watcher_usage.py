from pathlib import Path
from watchers.filesystem_watcher import FilesystemWatcher

# Initialize watcher using centralized paths from settings
# No need to pass paths manually - uses settings.vault_path and settings.drop_folder_path
watcher = FilesystemWatcher()
watcher.run()  # Blocks until Ctrl+C


# with FilesystemWatcher() as watcher:
#     print("Watching for file changes. Press Ctrl+C to stop.")
#     print("Watcher is ", watcher)
#     # try:
#     #     while True:
#     #         pass  # Keep the main thread alive
#     # except KeyboardInterrupt:
#     #     print("Stopping watcher...")