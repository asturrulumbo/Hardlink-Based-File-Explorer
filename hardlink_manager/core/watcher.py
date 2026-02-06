"""Filesystem watcher for mirror group auto-sync with debouncing."""

import os
import threading
import time
from typing import Callable, Optional

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler, FileCreatedEvent

from hardlink_manager.core.mirror_groups import MirrorGroup, MirrorGroupRegistry
from hardlink_manager.core.sync import sync_file_to_group


class _DebouncedHandler(FileSystemEventHandler):
    """Handles filesystem events with debouncing to avoid duplicate syncs."""

    def __init__(self, registry: MirrorGroupRegistry,
                 on_sync: Optional[Callable[[str, list[str]], None]] = None,
                 debounce_seconds: float = 0.5):
        super().__init__()
        self.registry = registry
        self.on_sync = on_sync
        self.debounce_seconds = debounce_seconds
        self._pending: dict[str, float] = {}  # path -> scheduled time
        self._lock = threading.Lock()
        self._timer: Optional[threading.Timer] = None

    def on_created(self, event):
        if event.is_directory:
            return
        if not isinstance(event, FileCreatedEvent):
            return

        src_path = os.path.abspath(event.src_path)
        folder = os.path.dirname(src_path)

        # Check if this folder belongs to a sync-enabled mirror group
        group = self.registry.find_group_for_folder(folder)
        if group is None or not group.sync_enabled:
            return

        # Debounce: schedule the sync
        with self._lock:
            self._pending[src_path] = time.time() + self.debounce_seconds
            if self._timer is None or not self._timer.is_alive():
                self._timer = threading.Timer(self.debounce_seconds, self._flush)
                self._timer.daemon = True
                self._timer.start()

    def _flush(self):
        """Process pending syncs whose debounce period has elapsed."""
        now = time.time()
        to_sync = []
        reschedule = False

        with self._lock:
            remaining = {}
            for path, scheduled_time in self._pending.items():
                if now >= scheduled_time:
                    to_sync.append(path)
                else:
                    remaining[path] = scheduled_time
                    reschedule = True
            self._pending = remaining

            if reschedule:
                delay = min(remaining.values()) - now
                self._timer = threading.Timer(max(delay, 0.05), self._flush)
                self._timer.daemon = True
                self._timer.start()
            else:
                self._timer = None

        # Perform syncs outside the lock
        for path in to_sync:
            if not os.path.exists(path):
                continue
            folder = os.path.dirname(path)
            group = self.registry.find_group_for_folder(folder)
            if group is None or not group.sync_enabled:
                continue
            try:
                created = sync_file_to_group(path, group)
                if created and self.on_sync:
                    self.on_sync(path, created)
            except Exception:
                pass  # Don't crash the watcher thread


class MirrorGroupWatcher:
    """Watches mirror group folders for file additions and auto-syncs."""

    def __init__(self, registry: MirrorGroupRegistry,
                 on_sync: Optional[Callable[[str, list[str]], None]] = None,
                 debounce_seconds: float = 0.5):
        self.registry = registry
        self.on_sync = on_sync
        self.debounce_seconds = debounce_seconds
        self._observer: Optional[Observer] = None
        self._handler: Optional[_DebouncedHandler] = None
        self._watched_paths: set[str] = set()

    def start(self):
        """Start watching all sync-enabled mirror group folders."""
        self.stop()
        self._handler = _DebouncedHandler(
            self.registry,
            on_sync=self.on_sync,
            debounce_seconds=self.debounce_seconds,
        )
        self._observer = Observer()
        self._watched_paths.clear()

        for group in self.registry.get_all_groups():
            if not group.sync_enabled:
                continue
            for folder in group.folders:
                folder = os.path.abspath(folder)
                if os.path.isdir(folder) and folder not in self._watched_paths:
                    self._observer.schedule(self._handler, folder, recursive=False)
                    self._watched_paths.add(folder)

        self._observer.daemon = True
        self._observer.start()

    def stop(self):
        """Stop watching all folders."""
        if self._observer is not None:
            self._observer.stop()
            self._observer.join(timeout=2)
            self._observer = None
        self._watched_paths.clear()

    def refresh(self):
        """Restart the watcher to pick up registry changes."""
        self.start()

    @property
    def is_running(self) -> bool:
        return self._observer is not None and self._observer.is_alive()
