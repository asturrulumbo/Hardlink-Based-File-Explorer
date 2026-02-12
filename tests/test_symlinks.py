"""Tests for folder symlink operations and sync."""

import os
import pytest

from hardlink_manager.core.hardlink_ops import (
    create_folder_symlink,
    delete_folder_symlink,
)
from hardlink_manager.core.mirror_groups import MirrorGroup
from hardlink_manager.core.sync import (
    sync_symlink_to_group,
    delete_symlink_from_group,
    sync_group,
)
from hardlink_manager.utils.filesystem import (
    create_symlink,
    is_symlink,
    is_symlink_broken,
    read_symlink_target,
)


@pytest.fixture
def target_folder(tmp_path):
    """Create a target folder with some contents."""
    target = tmp_path / "target_data"
    target.mkdir()
    (target / "readme.txt").write_text("hello")
    (target / "subdir").mkdir()
    (target / "subdir" / "nested.txt").write_text("nested")
    return str(target)


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
    return MirrorGroup(name="Test Mirror", folders=mirror_folders, sync_enabled=True)


# -- filesystem helpers --


class TestFilesystemSymlinkHelpers:
    def test_create_symlink(self, tmp_path, target_folder):
        link_path = str(tmp_path / "my_link")
        result = create_symlink(target_folder, link_path)
        assert result == link_path
        assert os.path.islink(link_path)
        assert os.path.isdir(link_path)

    def test_create_symlink_target_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            create_symlink("/nonexistent/path", str(tmp_path / "link"))

    def test_create_symlink_target_not_dir(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        with pytest.raises(ValueError, match="directory"):
            create_symlink(str(f), str(tmp_path / "link"))

    def test_create_symlink_already_exists(self, tmp_path, target_folder):
        link_path = str(tmp_path / "existing")
        os.mkdir(link_path)
        with pytest.raises(FileExistsError):
            create_symlink(target_folder, link_path)

    def test_is_symlink(self, tmp_path, target_folder):
        link_path = str(tmp_path / "link")
        os.symlink(target_folder, link_path, target_is_directory=True)
        assert is_symlink(link_path)
        assert not is_symlink(target_folder)

    def test_read_symlink_target(self, tmp_path, target_folder):
        link_path = str(tmp_path / "link")
        os.symlink(target_folder, link_path, target_is_directory=True)
        assert os.path.normpath(read_symlink_target(link_path)) == os.path.normpath(target_folder)

    def test_is_symlink_broken(self, tmp_path):
        # Create a symlink to a folder, then remove the target
        target = tmp_path / "temp_target"
        target.mkdir()
        link_path = str(tmp_path / "link")
        os.symlink(str(target), link_path, target_is_directory=True)
        assert not is_symlink_broken(link_path)

        os.rmdir(str(target))
        assert is_symlink_broken(link_path)

    def test_is_symlink_broken_not_symlink(self, tmp_path):
        regular = tmp_path / "folder"
        regular.mkdir()
        assert not is_symlink_broken(str(regular))


# -- hardlink_ops symlink functions --


class TestCreateFolderSymlink:
    def test_creates_symlink_in_dest(self, tmp_path, target_folder):
        dest_dir = str(tmp_path / "dest")
        os.mkdir(dest_dir)

        result = create_folder_symlink(target_folder, dest_dir)

        assert os.path.islink(result)
        assert os.path.basename(result) == os.path.basename(target_folder)
        assert read_symlink_target(result) == os.path.abspath(target_folder)

    def test_creates_with_custom_name(self, tmp_path, target_folder):
        dest_dir = str(tmp_path / "dest")
        os.mkdir(dest_dir)

        result = create_folder_symlink(target_folder, dest_dir, link_name="see_also")

        assert os.path.basename(result) == "see_also"
        assert os.path.islink(result)

    def test_target_not_found(self, tmp_path):
        dest = str(tmp_path / "dest")
        os.mkdir(dest)
        with pytest.raises(FileNotFoundError):
            create_folder_symlink("/nonexistent", dest)

    def test_dest_not_directory(self, tmp_path, target_folder):
        with pytest.raises(NotADirectoryError):
            create_folder_symlink(target_folder, "/nonexistent/dir")

    def test_already_exists(self, tmp_path, target_folder):
        dest_dir = str(tmp_path / "dest")
        os.mkdir(dest_dir)
        # Create something with the target's name
        os.mkdir(os.path.join(dest_dir, os.path.basename(target_folder)))
        with pytest.raises(FileExistsError):
            create_folder_symlink(target_folder, dest_dir)


class TestDeleteFolderSymlink:
    def test_deletes_symlink(self, tmp_path, target_folder):
        link_path = str(tmp_path / "link")
        os.symlink(target_folder, link_path, target_is_directory=True)

        delete_folder_symlink(link_path)

        assert not os.path.exists(link_path)
        assert not os.path.islink(link_path)
        # Target is unaffected
        assert os.path.isdir(target_folder)

    def test_not_a_symlink(self, tmp_path):
        regular = str(tmp_path / "folder")
        os.mkdir(regular)
        with pytest.raises(ValueError, match="not a symlink"):
            delete_folder_symlink(regular)

    def test_not_found(self):
        with pytest.raises(FileNotFoundError):
            delete_folder_symlink("/nonexistent/symlink")


# -- sync operations --


class TestSyncSymlinkToGroup:
    def test_syncs_to_other_folders(self, mirror_group, mirror_folders, target_folder):
        # Create a symlink in mirror_a
        link = os.path.join(mirror_folders[0], "ref")
        os.symlink(target_folder, link, target_is_directory=True)

        created = sync_symlink_to_group(link, mirror_group)

        assert len(created) == 2
        for folder in mirror_folders[1:]:
            dest = os.path.join(folder, "ref")
            assert os.path.islink(dest)
            assert os.path.normpath(read_symlink_target(dest)) == os.path.normpath(target_folder)

    def test_skip_already_synced(self, mirror_group, mirror_folders, target_folder):
        link = os.path.join(mirror_folders[0], "ref")
        os.symlink(target_folder, link, target_is_directory=True)

        sync_symlink_to_group(link, mirror_group)
        # Second call should create nothing
        created = sync_symlink_to_group(link, mirror_group)
        assert created == []

    def test_skip_name_conflict(self, mirror_group, mirror_folders, target_folder):
        link = os.path.join(mirror_folders[0], "ref")
        os.symlink(target_folder, link, target_is_directory=True)

        # Create a regular directory with same name in mirror_b
        os.mkdir(os.path.join(mirror_folders[1], "ref"))

        created = sync_symlink_to_group(link, mirror_group)

        # Only mirror_c should get the symlink
        assert len(created) == 1
        assert mirror_folders[2] in created[0]

    def test_not_a_symlink(self, mirror_group, mirror_folders):
        regular = os.path.join(mirror_folders[0], "regular_dir")
        os.mkdir(regular)
        created = sync_symlink_to_group(regular, mirror_group)
        assert created == []

    def test_creates_intermediate_dirs(self, mirror_group, mirror_folders, target_folder):
        sub = os.path.join(mirror_folders[0], "subdir")
        os.makedirs(sub)
        link = os.path.join(sub, "ref")
        os.symlink(target_folder, link, target_is_directory=True)

        created = sync_symlink_to_group(link, mirror_group)

        assert len(created) == 2
        for folder in mirror_folders[1:]:
            dest = os.path.join(folder, "subdir", "ref")
            assert os.path.islink(dest)


class TestDeleteSymlinkFromGroup:
    def test_deletes_from_all_folders(self, mirror_group, mirror_folders, target_folder):
        # Create and sync a symlink
        link = os.path.join(mirror_folders[0], "ref")
        os.symlink(target_folder, link, target_is_directory=True)
        sync_symlink_to_group(link, mirror_group)

        deleted = delete_symlink_from_group(link, mirror_group)

        assert len(deleted) == 3
        for folder in mirror_folders:
            assert not os.path.islink(os.path.join(folder, "ref"))

    def test_only_deletes_matching_target(self, mirror_group, mirror_folders, tmp_path, target_folder):
        # Create symlink in mirror_a pointing to target_folder
        link = os.path.join(mirror_folders[0], "ref")
        os.symlink(target_folder, link, target_is_directory=True)
        sync_symlink_to_group(link, mirror_group)

        # Replace the symlink in mirror_b with one pointing elsewhere
        other = str(tmp_path / "other_target")
        os.mkdir(other)
        os.unlink(os.path.join(mirror_folders[1], "ref"))
        os.symlink(other, os.path.join(mirror_folders[1], "ref"), target_is_directory=True)

        deleted = delete_symlink_from_group(link, mirror_group)

        # Should delete from mirror_a and mirror_c, not mirror_b
        assert len(deleted) == 2
        assert os.path.islink(os.path.join(mirror_folders[1], "ref"))


class TestSyncGroupWithSymlinks:
    def test_full_sync_includes_symlinks(self, mirror_group, mirror_folders, target_folder):
        # Create a regular file and a symlink in mirror_a
        with open(os.path.join(mirror_folders[0], "file.txt"), "w") as f:
            f.write("data")
        os.symlink(target_folder, os.path.join(mirror_folders[0], "ref"),
                   target_is_directory=True)

        created = sync_group(mirror_group)

        # file.txt should be hardlinked to mirror_b and mirror_c (2 entries)
        # ref symlink should be replicated to mirror_b and mirror_c (2 entries)
        assert len(created) == 4

        for folder in mirror_folders:
            assert os.path.exists(os.path.join(folder, "file.txt"))
            ref = os.path.join(folder, "ref")
            assert os.path.islink(ref)
            assert os.path.normpath(read_symlink_target(ref)) == os.path.normpath(target_folder)

    def test_sync_does_not_descend_into_symlinks(self, mirror_group, mirror_folders, target_folder):
        # Create a symlink in mirror_a
        os.symlink(target_folder, os.path.join(mirror_folders[0], "ref"),
                   target_is_directory=True)

        created = sync_group(mirror_group)

        # The symlink's contents (readme.txt, subdir/) should NOT be synced
        for folder in mirror_folders:
            assert not os.path.exists(os.path.join(folder, "readme.txt"))
            # Only the symlink ref should exist
            assert os.path.islink(os.path.join(folder, "ref"))

    def test_sync_idempotent_with_symlinks(self, mirror_group, mirror_folders, target_folder):
        os.symlink(target_folder, os.path.join(mirror_folders[0], "ref"),
                   target_is_directory=True)

        sync_group(mirror_group)
        created = sync_group(mirror_group)
        assert len(created) == 0
