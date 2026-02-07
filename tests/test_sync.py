"""Tests for mirror group sync operations."""

import os
import pytest

from hardlink_manager.core.mirror_groups import MirrorGroup
from hardlink_manager.core.sync import sync_file_to_group, sync_group, delete_from_group
from hardlink_manager.utils.filesystem import get_inode


@pytest.fixture
def mirror_folders(tmp_path):
    """Create three mirror group folders."""
    folders = []
    for name in ("mirror_a", "mirror_b", "mirror_c"):
        d = tmp_path / name
        d.mkdir()
        folders.append(str(d))
    return folders


@pytest.fixture
def mirror_group(mirror_folders):
    """Create a MirrorGroup with the three folders."""
    return MirrorGroup(name="Test Mirror", folders=mirror_folders, sync_enabled=True)


class TestSyncFileToGroup:
    def test_syncs_file_to_other_folders(self, mirror_group, mirror_folders):
        # Create a file in the first folder
        src = os.path.join(mirror_folders[0], "hello.txt")
        with open(src, "w") as f:
            f.write("hello")

        created = sync_file_to_group(src, mirror_group)

        assert len(created) == 2
        for folder in mirror_folders[1:]:
            dest = os.path.join(folder, "hello.txt")
            assert os.path.exists(dest)
            assert get_inode(dest) == get_inode(src)

    def test_skip_already_linked(self, mirror_group, mirror_folders):
        src = os.path.join(mirror_folders[0], "hello.txt")
        with open(src, "w") as f:
            f.write("hello")

        # First sync
        sync_file_to_group(src, mirror_group)
        # Second sync should create nothing new
        created = sync_file_to_group(src, mirror_group)
        assert created == []

    def test_skip_different_file_same_name(self, mirror_group, mirror_folders):
        src = os.path.join(mirror_folders[0], "conflict.txt")
        with open(src, "w") as f:
            f.write("original")

        # Create a different file with the same name in folder_b
        conflict = os.path.join(mirror_folders[1], "conflict.txt")
        with open(conflict, "w") as f:
            f.write("different content")

        created = sync_file_to_group(src, mirror_group)

        # Should only create in folder_c (folder_b has a conflict)
        assert len(created) == 1
        assert mirror_folders[2] in created[0]

    def test_creates_missing_directories(self, tmp_path, mirror_folders):
        new_folder = str(tmp_path / "new_folder")
        group = MirrorGroup(
            name="Test",
            folders=[mirror_folders[0], new_folder],
            sync_enabled=True,
        )

        src = os.path.join(mirror_folders[0], "test.txt")
        with open(src, "w") as f:
            f.write("data")

        created = sync_file_to_group(src, group)
        assert len(created) == 1
        assert os.path.isdir(new_folder)


    def test_syncs_file_in_subdirectory(self, mirror_group, mirror_folders):
        # Create a file in a subdirectory of the first folder
        sub = os.path.join(mirror_folders[0], "subdir")
        os.makedirs(sub)
        src = os.path.join(sub, "deep.txt")
        with open(src, "w") as f:
            f.write("deep content")

        created = sync_file_to_group(src, mirror_group)

        assert len(created) == 2
        for folder in mirror_folders[1:]:
            dest = os.path.join(folder, "subdir", "deep.txt")
            assert os.path.exists(dest)
            assert get_inode(dest) == get_inode(src)

    def test_syncs_file_in_nested_subdirectory(self, mirror_group, mirror_folders):
        sub = os.path.join(mirror_folders[0], "a", "b", "c")
        os.makedirs(sub)
        src = os.path.join(sub, "nested.txt")
        with open(src, "w") as f:
            f.write("nested")

        created = sync_file_to_group(src, mirror_group)

        assert len(created) == 2
        for folder in mirror_folders[1:]:
            dest = os.path.join(folder, "a", "b", "c", "nested.txt")
            assert os.path.exists(dest)
            assert get_inode(dest) == get_inode(src)


class TestSyncGroup:
    def test_full_sync(self, mirror_group, mirror_folders):
        # Create different files in different folders
        with open(os.path.join(mirror_folders[0], "a.txt"), "w") as f:
            f.write("aaa")
        with open(os.path.join(mirror_folders[1], "b.txt"), "w") as f:
            f.write("bbb")

        created = sync_group(mirror_group)

        # a.txt should be synced to mirror_b and mirror_c
        # b.txt should be synced to mirror_a and mirror_c
        assert len(created) == 4

        # All folders should have both files
        for folder in mirror_folders:
            assert os.path.exists(os.path.join(folder, "a.txt"))
            assert os.path.exists(os.path.join(folder, "b.txt"))

    def test_sync_group_idempotent(self, mirror_group, mirror_folders):
        with open(os.path.join(mirror_folders[0], "file.txt"), "w") as f:
            f.write("content")

        sync_group(mirror_group)
        # Second sync should produce no new links
        created = sync_group(mirror_group)
        assert len(created) == 0

    def test_sync_empty_group(self, mirror_group):
        created = sync_group(mirror_group)
        assert created == {}

    def test_sync_group_less_than_two_folders(self):
        group = MirrorGroup(name="One", folders=["/tmp/one"])
        assert sync_group(group) == {}

    def test_sync_preserves_inodes(self, mirror_group, mirror_folders):
        src = os.path.join(mirror_folders[0], "linked.txt")
        with open(src, "w") as f:
            f.write("data")

        sync_group(mirror_group)

        src_inode = get_inode(src)
        for folder in mirror_folders[1:]:
            assert get_inode(os.path.join(folder, "linked.txt")) == src_inode


    def test_sync_group_recursive(self, mirror_group, mirror_folders):
        # Create files in subdirectories
        sub_a = os.path.join(mirror_folders[0], "docs")
        os.makedirs(sub_a)
        with open(os.path.join(sub_a, "readme.txt"), "w") as f:
            f.write("readme")

        sub_b = os.path.join(mirror_folders[1], "images")
        os.makedirs(sub_b)
        with open(os.path.join(sub_b, "photo.txt"), "w") as f:
            f.write("photo")

        created = sync_group(mirror_group)

        # docs/readme.txt synced to mirror_b and mirror_c
        # images/photo.txt synced to mirror_a and mirror_c
        assert len(created) == 4

        for folder in mirror_folders:
            assert os.path.exists(os.path.join(folder, "docs", "readme.txt"))
            assert os.path.exists(os.path.join(folder, "images", "photo.txt"))

    def test_sync_group_deeply_nested(self, mirror_group, mirror_folders):
        deep = os.path.join(mirror_folders[0], "a", "b", "c")
        os.makedirs(deep)
        src = os.path.join(deep, "file.txt")
        with open(src, "w") as f:
            f.write("deep")

        sync_group(mirror_group)

        for folder in mirror_folders:
            dest = os.path.join(folder, "a", "b", "c", "file.txt")
            assert os.path.exists(dest)
            assert get_inode(dest) == get_inode(src)


class TestDeleteFromGroup:
    def test_deletes_from_all_folders(self, mirror_group, mirror_folders):
        # Create and sync a file
        src = os.path.join(mirror_folders[0], "to_delete.txt")
        with open(src, "w") as f:
            f.write("data")
        sync_file_to_group(src, mirror_group)

        deleted = delete_from_group(src, mirror_group)

        assert len(deleted) == 3
        for folder in mirror_folders:
            assert not os.path.exists(os.path.join(folder, "to_delete.txt"))

    def test_delete_only_matching_inodes(self, mirror_group, mirror_folders):
        # Create file in folder_a and sync
        src = os.path.join(mirror_folders[0], "shared.txt")
        with open(src, "w") as f:
            f.write("shared")
        sync_file_to_group(src, mirror_group)

        # Replace the file in folder_b with a different file (different inode)
        conflict = os.path.join(mirror_folders[1], "shared.txt")
        os.unlink(conflict)
        with open(conflict, "w") as f:
            f.write("different")

        deleted = delete_from_group(src, mirror_group)

        # Should delete from folder_a and folder_c, but not folder_b
        assert len(deleted) == 2
        assert os.path.exists(conflict)

    def test_delete_from_subdirectory(self, mirror_group, mirror_folders):
        # Create a file in a subdirectory and sync
        sub = os.path.join(mirror_folders[0], "subdir")
        os.makedirs(sub)
        src = os.path.join(sub, "to_delete.txt")
        with open(src, "w") as f:
            f.write("delete me")
        sync_file_to_group(src, mirror_group)

        deleted = delete_from_group(src, mirror_group)

        assert len(deleted) == 3
        for folder in mirror_folders:
            assert not os.path.exists(os.path.join(folder, "subdir", "to_delete.txt"))

    def test_delete_nonexistent_file(self, mirror_group):
        deleted = delete_from_group("/nonexistent/file.txt", mirror_group)
        assert deleted == []
