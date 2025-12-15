# src/core/config_loader_dynamic.py
"""
Implements dynamic "hot reloading" of configuration files without service downtime.
"""
import asyncio
import threading
import time
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileModifiedEvent

# from . import logger
# from .config_loader import _hot_reload_callback # Import the callback to clear caches

class ConfigChangeHandler(FileSystemEventHandler):
    """
    An event handler that triggers the hot reload callback when a config file is modified.
    Implements debouncing to prevent multiple triggers for a single save action.
    """
    def __init__(self, callback, debounce_seconds=0.5):
        super().__init__()
        self.callback = callback
        self.debounce_seconds = debounce_seconds
        self.last_called_time = 0

    def on_modified(self, event: FileModifiedEvent):
        """
        Called when a file or directory is modified.
        """
        # We only care about file modifications
        if not event.is_directory:
            current_time = time.time()
            if (current_time - self.last_called_time) > self.debounce_seconds:
                self.last_called_time = current_time
                # logger.info(f"Configuration file changed: {event.src_path}. Triggering hot reload.")
                print(f"Configuration file changed: {event.src_path}. Triggering hot reload.")
                self.callback()

class DynamicConfigLoader:
    def __init__(self, config_dir: Path, reload_callback):
        """
        Initializes the file watcher.
        """
        if not config_dir.is_dir():
            raise ValueError(f"Config directory not found: {config_dir}")
            
        self.observer = Observer()
        event_handler = ConfigChangeHandler(reload_callback)
        self.observer.schedule(event_handler, str(config_dir), recursive=True)
        self._stop_event = threading.Event()
        self.thread = threading.Thread(target=self._run, daemon=True)
        print("DynamicConfigLoader initialized.")

    def _run(self):
        """Runs the observer loop in a background thread."""
        self.observer.start()
        # logger.info(f"Started monitoring config directory for changes.")
        self._stop_event.wait() # Wait until stop() is called
        self.observer.stop()
        self.observer.join()
        # logger.info("Stopped monitoring config directory.")

    def start(self):
        """Starts the background monitoring thread."""
        if not self.thread.is_alive():
            self.thread.start()

    def stop(self):
        """Stops the background monitoring thread."""
        self._stop_event.set()

# Example of how this would be integrated into the application startup
def start_config_hot_reloading():
    """
    Creates and starts the dynamic config loader.
    """
    # from .config_loader import CONFIG_DIR, _hot_reload_callback
    # loader = DynamicConfigLoader(config_dir=CONFIG_DIR, reload_callback=_hot_reload_callback)
    # loader.start()
    # return loader # Return instance so it can be stopped gracefully

# In main.py, you would have:
#
# hot_reload_loader = None
#
# @app.on_event("startup")
# async def startup_event():
#     global hot_reload_loader
#     hot_reload_loader = start_config_hot_reloading()
#
# @app.on_event("shutdown")
# async def shutdown_event():
#     if hot_reload_loader:
#         hot_reload_loader.stop()