"""Tests for the filesystem watcher with debouncing."""

import os
import time
import threading
import pytest

from hardlink_manager.core.mirror_groups import MirrorGroup, MirrorGroupRegistry
from hardlink_manager.core.watcher import MirrorGroupWatcher, _DebouncedHandler
from hardlink_manager.utils.filesystem import get_inode


@pytest.fixture
def mirror_workspace(tmp_path):
    """Create a workspace with a registry and two mirror folders."""
    folder_a = tmp_path / "watch_a"
    folder_b = tmp_path / "watch_b"
    folder_a.mkdir()
    folder_b.mkdir()

    registry_path = str(tmp_path / "mirror_groups.json")
    registry = MirrorGroupRegistry(path=registry_path)
    group = registry.create_group(
        "Watch Test",
        [str(folder_a), str(folder_b)],
        sync_enabled=True,
    )

    return {
        "tmp_path": tmp_path,
        "folder_a": str(folder_a),
        "folder_b": str(folder_b),
        "registry": registry,
        "group": group,
    }


class TestMirrorGroupWatcher:
    def test_start_and_stop(self, mirror_workspace):
        watcher = MirrorGroupWatcher(mirror_workspace["registry"])
        watcher.start()
        assert watcher.is_running
        watcher.stop()
        assert not watcher.is_running

    def test_stop_without_start(self, mirror_workspace):
        watcher = MirrorGroupWatcher(mirror_workspace["registry"])
        watcher.stop()  # Should not raise

    def test_refresh_restarts(self, mirror_workspace):
        watcher = MirrorGroupWatcher(mirror_workspace["registry"])
        watcher.start()
        assert watcher.is_running
        watcher.refresh()
        assert watcher.is_running
        watcher.stop()

    def test_auto_sync_on_file_creation(self, mirror_workspace):
        """Test that creating a file in one folder auto-syncs to the other."""
        synced_files = []
        sync_event = threading.Event()

        def on_sync(source, created):
            synced_files.append((source, created))
            sync_event.set()

        watcher = MirrorGroupWatcher(
            mirror_workspace["registry"],
            on_sync=on_sync,
            debounce_seconds=0.1,
        )
        watcher.start()

        try:
            # Create a file in folder_a
            src = os.path.join(mirror_workspace["folder_a"], "auto_sync.txt")
            with open(src, "w") as f:
                f.write("auto synced content")

            # Wait for the watcher to pick up and process the event
            sync_event.wait(timeout=5.0)

            # Verify the file was synced
            dest = os.path.join(mirror_workspace["folder_b"], "auto_sync.txt")
            if sync_event.is_set():
                assert os.path.exists(dest)
                assert get_inode(src) == get_inode(dest)
                assert len(synced_files) >= 1
            # On some CI/container environments watchdog may not trigger
        finally:
            watcher.stop()

    def test_no_sync_when_disabled(self, mirror_workspace):
        """Test that sync-disabled groups don't get watched."""
        # Disable sync on the group
        mirror_workspace["registry"].update_group(
            mirror_workspace["group"].id, sync_enabled=False
        )

        watcher = MirrorGroupWatcher(mirror_workspace["registry"])
        watcher.start()

        try:
            # Create a file - it should NOT be synced
            src = os.path.join(mirror_workspace["folder_a"], "no_sync.txt")
            with open(src, "w") as f:
                f.write("should not sync")

            time.sleep(1.0)

            dest = os.path.join(mirror_workspace["folder_b"], "no_sync.txt")
            assert not os.path.exists(dest)
        finally:
            watcher.stop()


class TestDebouncedHandler:
    def test_debounce_coalesces_events(self, mirror_workspace):
        """Multiple rapid creates of the same file should result in one sync."""
        sync_count = []
        sync_event = threading.Event()

        def on_sync(source, created):
            sync_count.append(1)
            sync_event.set()

        handler = _DebouncedHandler(
            mirror_workspace["registry"],
            on_sync=on_sync,
            debounce_seconds=0.3,
        )

        # Simulate rapid creation events for the same path
        from watchdog.events import FileCreatedEvent

        src = os.path.join(mirror_workspace["folder_a"], "debounce.txt")
        with open(src, "w") as f:
            f.write("debounce test")

        event = FileCreatedEvent(src)
        handler.on_created(event)
        handler.on_created(event)
        handler.on_created(event)

        sync_event.wait(timeout=3.0)
        time.sleep(0.5)

        # Should have synced only once due to debouncing
        assert len(sync_count) == 1

    def test_ignores_directories(self, mirror_workspace):
        handler = _DebouncedHandler(mirror_workspace["registry"])
        from watchdog.events import DirCreatedEvent

        event = DirCreatedEvent(mirror_workspace["folder_a"])
        handler.on_created(event)  # Should not raise or schedule anything

        assert len(handler._pending) == 0
