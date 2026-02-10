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

    def test_auto_name_from_folders(self):
        g = MirrorGroup(folders=["/home/user/Photos", "/mnt/backup/Photos"])
        assert g.auto_name() == "Photos + Photos"

    def test_auto_name_empty(self):
        g = MirrorGroup()
        assert g.auto_name() == "(empty)"

    def test_auto_name_single_folder(self):
        g = MirrorGroup(folders=["/data/docs"])
        assert g.auto_name() == "docs"


class TestRegistryPersistence:
    def test_save_and_load(self, registry, two_folders, registry_path):
        registry.create_group(two_folders)
        assert os.path.exists(registry_path)

        # Load in a new registry instance
        reg2 = MirrorGroupRegistry(path=registry_path)
        groups = reg2.get_all_groups()
        assert len(groups) == 1
        assert groups[0].folders == two_folders
        # Name should be auto-generated from folder basenames
        assert "folder_a" in groups[0].name
        assert "folder_b" in groups[0].name

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
        registry.create_group(two_folders, sync_enabled=False)
        with open(registry_path) as f:
            data = json.load(f)
        assert "groups" in data
        assert len(data["groups"]) == 1
        g = data["groups"][0]
        assert g["sync_enabled"] is False


class TestRegistryCRUD:
    def test_create_group_auto_name(self, registry, two_folders):
        group = registry.create_group(two_folders)
        assert "folder_a" in group.name
        assert "folder_b" in group.name
        assert group.folders == two_folders
        assert group.sync_enabled is True
        assert registry.get_group(group.id) is group

    def test_create_group_explicit_name(self, registry, two_folders):
        group = registry.create_group(two_folders, name="Custom Name")
        assert group.name == "Custom Name"

    def test_get_all_groups(self, registry, two_folders):
        registry.create_group(two_folders)
        registry.create_group(two_folders)
        assert len(registry.get_all_groups()) == 2

    def test_get_group_nonexistent(self, registry):
        assert registry.get_group("fake-id") is None

    def test_update_group_folders_updates_name(self, registry, two_folders, tmp_path):
        group = registry.create_group(two_folders)
        new_folder = str(tmp_path / "new_folder")
        os.makedirs(new_folder)
        updated = registry.update_group(group.id, folders=[two_folders[0], new_folder])
        assert "new_folder" in updated.name

    def test_update_group_sync(self, registry, two_folders):
        group = registry.create_group(two_folders)
        updated = registry.update_group(group.id, sync_enabled=False)
        assert updated.sync_enabled is False

    def test_update_nonexistent(self, registry):
        assert registry.update_group("fake-id", name="X") is None

    def test_delete_group(self, registry, two_folders):
        group = registry.create_group(two_folders)
        assert registry.delete_group(group.id) is True
        assert registry.get_group(group.id) is None
        assert len(registry.get_all_groups()) == 0

    def test_delete_nonexistent(self, registry):
        assert registry.delete_group("fake-id") is False

    def test_add_folder_to_group_updates_name(self, registry, two_folders, tmp_path):
        group = registry.create_group(two_folders)
        new_folder = str(tmp_path / "folder_c")
        os.makedirs(new_folder)
        assert registry.add_folder_to_group(group.id, new_folder) is True
        assert os.path.abspath(new_folder) in group.folders
        assert "folder_c" in group.name

    def test_add_folder_nonexistent_group(self, registry):
        assert registry.add_folder_to_group("fake-id", "/tmp") is False

    def test_remove_folder_from_group_updates_name(self, registry, two_folders):
        group = registry.create_group(two_folders)
        folder_to_remove = os.path.abspath(two_folders[0])
        assert registry.remove_folder_from_group(group.id, folder_to_remove) is True
        assert folder_to_remove not in group.folders
        assert "folder_a" not in group.name

    def test_remove_folder_nonexistent_group(self, registry):
        assert registry.remove_folder_from_group("fake-id", "/tmp") is False


class TestRegistryQueries:
    def test_find_group_for_folder(self, registry, two_folders):
        group = registry.create_group(two_folders)
        found = registry.find_group_for_folder(two_folders[0])
        assert found is not None
        assert found.id == group.id

    def test_find_group_for_unknown_folder(self, registry, two_folders):
        registry.create_group(two_folders)
        assert registry.find_group_for_folder("/some/random/path") is None

    def test_find_group_for_path_in_subfolder(self, registry, two_folders):
        group = registry.create_group(two_folders)
        sub = os.path.join(two_folders[0], "subdir", "file.txt")
        result = registry.find_group_for_path(sub)
        assert result is not None
        found_group, root = result
        assert found_group.id == group.id
        assert root == os.path.normpath(os.path.abspath(two_folders[0]))

    def test_find_group_for_path_not_found(self, registry, two_folders):
        registry.create_group(two_folders)
        assert registry.find_group_for_path("/some/random/path") is None

    def test_is_folder_in_group(self, registry, two_folders):
        registry.create_group(two_folders)
        assert registry.is_folder_in_group(two_folders[0]) is True
        assert registry.is_folder_in_group("/unknown") is False


class TestScanForMirrors:
    def test_discovers_mirror_from_hardlinks(self, registry, tmp_path):
        a = tmp_path / "dir_a"
        b = tmp_path / "dir_b"
        a.mkdir()
        b.mkdir()
        # Create a file in dir_a and hardlink it into dir_b
        src = a / "file.txt"
        src.write_text("hello")
        os.link(str(src), str(b / "file.txt"))

        new_groups = registry.scan_for_mirrors([str(a), str(b)])
        assert len(new_groups) == 1
        folder_set = {os.path.normpath(f) for f in new_groups[0].folders}
        assert os.path.normpath(str(a)) in folder_set
        assert os.path.normpath(str(b)) in folder_set

    def test_no_shared_hardlinks(self, registry, tmp_path):
        a = tmp_path / "dir_a"
        b = tmp_path / "dir_b"
        a.mkdir()
        b.mkdir()
        (a / "file1.txt").write_text("aaa")
        (b / "file2.txt").write_text("bbb")

        new_groups = registry.scan_for_mirrors([str(a), str(b)])
        assert len(new_groups) == 0

    def test_skips_already_registered(self, registry, tmp_path):
        a = tmp_path / "dir_a"
        b = tmp_path / "dir_b"
        a.mkdir()
        b.mkdir()
        src = a / "file.txt"
        src.write_text("hello")
        os.link(str(src), str(b / "file.txt"))

        # Create the group manually first
        registry.create_group([str(a), str(b)])
        # Scan should find no NEW groups
        new_groups = registry.scan_for_mirrors([str(a), str(b)])
        assert len(new_groups) == 0

    def test_discovers_multiple_groups(self, registry, tmp_path):
        # Two independent pairs of mirrors
        a1 = tmp_path / "pair1_a"
        b1 = tmp_path / "pair1_b"
        a2 = tmp_path / "pair2_a"
        b2 = tmp_path / "pair2_b"
        for d in [a1, b1, a2, b2]:
            d.mkdir()
        src1 = a1 / "f.txt"
        src1.write_text("one")
        os.link(str(src1), str(b1 / "f.txt"))
        src2 = a2 / "g.txt"
        src2.write_text("two")
        os.link(str(src2), str(b2 / "g.txt"))

        new_groups = registry.scan_for_mirrors(
            [str(a1), str(b1), str(a2), str(b2)]
        )
        assert len(new_groups) == 2

    def test_needs_at_least_two_folders(self, registry, tmp_path):
        a = tmp_path / "only"
        a.mkdir()
        assert registry.scan_for_mirrors([str(a)]) == []

    def test_discovers_recursive_hardlinks(self, registry, tmp_path):
        a = tmp_path / "dir_a"
        b = tmp_path / "dir_b"
        sub_a = a / "sub"
        sub_b = b / "sub"
        sub_a.mkdir(parents=True)
        sub_b.mkdir(parents=True)
        src = sub_a / "deep.txt"
        src.write_text("nested")
        os.link(str(src), str(sub_b / "deep.txt"))

        new_groups = registry.scan_for_mirrors([str(a), str(b)])
        assert len(new_groups) == 1

    def test_skips_subfolders_of_registered_group(self, registry, tmp_path):
        """Subfolders of an existing mirror group should not appear as new groups."""
        a = tmp_path / "dir_a"
        b = tmp_path / "dir_b"
        sub_a = a / "sub"
        sub_b = b / "sub"
        sub_a.mkdir(parents=True)
        sub_b.mkdir(parents=True)
        # Create hardlinked files in the sub-directories
        src = sub_a / "file.txt"
        src.write_text("shared")
        os.link(str(src), str(sub_b / "file.txt"))

        # Register the parent folders as a mirror group first
        registry.create_group([str(a), str(b)])

        # Scanning the parent folders should not discover sub/ as a new group
        new_groups = registry.scan_for_mirrors([str(a), str(b)])
        assert len(new_groups) == 0


class TestClearAllGroups:
    def test_clears_all_groups(self, registry, two_folders, tmp_path):
        c = tmp_path / "folder_c"
        d = tmp_path / "folder_d"
        c.mkdir()
        d.mkdir()
        registry.create_group(two_folders)
        registry.create_group([str(c), str(d)])
        assert len(registry.get_all_groups()) == 2

        count = registry.clear_all_groups()
        assert count == 2
        assert len(registry.get_all_groups()) == 0

    def test_clear_empty_registry(self, registry):
        count = registry.clear_all_groups()
        assert count == 0

    def test_clear_removes_markers(self, registry, two_folders):
        from hardlink_manager.core.mirror_groups import has_mirror_marker
        registry.create_group(two_folders)
        assert has_mirror_marker(two_folders[0])
        assert has_mirror_marker(two_folders[1])

        registry.clear_all_groups()
        assert not has_mirror_marker(two_folders[0])
        assert not has_mirror_marker(two_folders[1])
