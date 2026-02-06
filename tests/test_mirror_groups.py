"""Tests for mirror group registry: data model and JSON persistence."""

import json
import os
import pytest

from hardlink_manager.core.mirror_groups import MirrorGroup, MirrorGroupRegistry


@pytest.fixture
def registry_path(tmp_path):
    """Return a path for a temporary registry JSON file."""
    return str(tmp_path / "mirror_groups.json")


@pytest.fixture
def registry(registry_path):
    """Create a fresh registry backed by a temp file."""
    return MirrorGroupRegistry(path=registry_path)


@pytest.fixture
def two_folders(tmp_path):
    """Create two empty directories for use as mirror group folders."""
    a = tmp_path / "folder_a"
    b = tmp_path / "folder_b"
    a.mkdir()
    b.mkdir()
    return [str(a), str(b)]


class TestMirrorGroup:
    def test_defaults(self):
        g = MirrorGroup()
        assert g.id
        assert g.name == ""
        assert g.folders == []
        assert g.sync_enabled is True
        assert g.created_at
        assert g.modified_at

    def test_touch_updates_modified(self):
        g = MirrorGroup()
        old = g.modified_at
        g.touch()
        assert g.modified_at >= old


class TestRegistryPersistence:
    def test_save_and_load(self, registry, two_folders, registry_path):
        registry.create_group("Test Group", two_folders)
        assert os.path.exists(registry_path)

        # Load in a new registry instance
        reg2 = MirrorGroupRegistry(path=registry_path)
        groups = reg2.get_all_groups()
        assert len(groups) == 1
        assert groups[0].name == "Test Group"
        assert groups[0].folders == two_folders

    def test_load_nonexistent_file(self, tmp_path):
        path = str(tmp_path / "does_not_exist.json")
        reg = MirrorGroupRegistry(path=path)
        assert reg.get_all_groups() == []

    def test_load_corrupt_file(self, tmp_path):
        path = str(tmp_path / "corrupt.json")
        with open(path, "w") as f:
            f.write("not valid json{{{")
        reg = MirrorGroupRegistry(path=path)
        assert reg.get_all_groups() == []

    def test_json_structure(self, registry, two_folders, registry_path):
        registry.create_group("G1", two_folders, sync_enabled=False)
        with open(registry_path) as f:
            data = json.load(f)
        assert "groups" in data
        assert len(data["groups"]) == 1
        g = data["groups"][0]
        assert g["name"] == "G1"
        assert g["sync_enabled"] is False


class TestRegistryCRUD:
    def test_create_group(self, registry, two_folders):
        group = registry.create_group("My Group", two_folders)
        assert group.name == "My Group"
        assert group.folders == two_folders
        assert group.sync_enabled is True
        assert registry.get_group(group.id) is group

    def test_get_all_groups(self, registry, two_folders):
        registry.create_group("A", two_folders)
        registry.create_group("B", two_folders)
        assert len(registry.get_all_groups()) == 2

    def test_get_group_nonexistent(self, registry):
        assert registry.get_group("fake-id") is None

    def test_update_group(self, registry, two_folders):
        group = registry.create_group("Old Name", two_folders)
        updated = registry.update_group(group.id, name="New Name", sync_enabled=False)
        assert updated.name == "New Name"
        assert updated.sync_enabled is False

    def test_update_nonexistent(self, registry):
        assert registry.update_group("fake-id", name="X") is None

    def test_delete_group(self, registry, two_folders):
        group = registry.create_group("To Delete", two_folders)
        assert registry.delete_group(group.id) is True
        assert registry.get_group(group.id) is None
        assert len(registry.get_all_groups()) == 0

    def test_delete_nonexistent(self, registry):
        assert registry.delete_group("fake-id") is False

    def test_add_folder_to_group(self, registry, two_folders, tmp_path):
        group = registry.create_group("G", two_folders)
        new_folder = str(tmp_path / "folder_c")
        os.makedirs(new_folder)
        assert registry.add_folder_to_group(group.id, new_folder) is True
        assert os.path.abspath(new_folder) in group.folders

    def test_add_folder_nonexistent_group(self, registry):
        assert registry.add_folder_to_group("fake-id", "/tmp") is False

    def test_remove_folder_from_group(self, registry, two_folders):
        group = registry.create_group("G", two_folders)
        folder_to_remove = os.path.abspath(two_folders[0])
        assert registry.remove_folder_from_group(group.id, folder_to_remove) is True
        assert folder_to_remove not in group.folders

    def test_remove_folder_nonexistent_group(self, registry):
        assert registry.remove_folder_from_group("fake-id", "/tmp") is False


class TestRegistryQueries:
    def test_find_group_for_folder(self, registry, two_folders):
        group = registry.create_group("G", two_folders)
        found = registry.find_group_for_folder(two_folders[0])
        assert found is not None
        assert found.id == group.id

    def test_find_group_for_unknown_folder(self, registry, two_folders):
        registry.create_group("G", two_folders)
        assert registry.find_group_for_folder("/some/random/path") is None

    def test_is_folder_in_group(self, registry, two_folders):
        registry.create_group("G", two_folders)
        assert registry.is_folder_in_group(two_folders[0]) is True
        assert registry.is_folder_in_group("/unknown") is False
