"""Tests for core hardlink operations."""

import os
import tempfile
import pytest

from hardlink_manager.core.hardlink_ops import (
    create_hardlink,
    delete_hardlink,
    find_all_hardlinks,
)
from hardlink_manager.utils.filesystem import get_inode, get_hardlink_count


@pytest.fixture
def tmp_workspace(tmp_path):
    """Create a temporary workspace with source and destination directories."""
    src_dir = tmp_path / "source"
    dst_dir = tmp_path / "dest"
    src_dir.mkdir()
    dst_dir.mkdir()

    # Create a test file
    test_file = src_dir / "test.txt"
    test_file.write_text("hello world")

    return {"root": tmp_path, "src_dir": src_dir, "dst_dir": dst_dir, "test_file": test_file}


class TestCreateHardlink:
    def test_creates_hardlink(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])

        result = create_hardlink(src, dst_dir)

        assert os.path.exists(result)
        assert os.path.basename(result) == "test.txt"
        assert get_inode(src) == get_inode(result)

    def test_creates_hardlink_with_custom_name(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])

        result = create_hardlink(src, dst_dir, dest_name="renamed.txt")

        assert os.path.basename(result) == "renamed.txt"
        assert get_inode(src) == get_inode(result)

    def test_hardlink_shares_content(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])

        result = create_hardlink(src, dst_dir)

        with open(result) as f:
            assert f.read() == "hello world"

    def test_hardlink_count_increases(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])

        assert get_hardlink_count(src) == 1
        create_hardlink(src, dst_dir)
        assert get_hardlink_count(src) == 2

    def test_source_not_found(self, tmp_workspace):
        dst_dir = str(tmp_workspace["dst_dir"])
        with pytest.raises(FileNotFoundError):
            create_hardlink("/nonexistent/file.txt", dst_dir)

    def test_source_is_directory(self, tmp_workspace):
        src_dir = str(tmp_workspace["src_dir"])
        dst_dir = str(tmp_workspace["dst_dir"])
        with pytest.raises(ValueError, match="regular file"):
            create_hardlink(src_dir, dst_dir)

    def test_dest_not_directory(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        with pytest.raises(NotADirectoryError):
            create_hardlink(src, "/nonexistent/dir")

    def test_file_already_exists(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])

        create_hardlink(src, dst_dir)
        with pytest.raises(FileExistsError):
            create_hardlink(src, dst_dir)


class TestDeleteHardlink:
    def test_deletes_hardlink(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])
        link = create_hardlink(src, dst_dir)

        delete_hardlink(link)

        assert not os.path.exists(link)
        assert os.path.exists(src)  # Original still exists

    def test_delete_preserves_data_with_other_links(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])
        link = create_hardlink(src, dst_dir)

        delete_hardlink(link)

        with open(src) as f:
            assert f.read() == "hello world"

    def test_delete_nonexistent(self):
        with pytest.raises(FileNotFoundError):
            delete_hardlink("/nonexistent/file.txt")

    def test_delete_directory_raises(self, tmp_workspace):
        with pytest.raises(ValueError, match="regular file"):
            delete_hardlink(str(tmp_workspace["src_dir"]))


class TestFindAllHardlinks:
    def test_finds_hardlinks_across_dirs(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])
        link = create_hardlink(src, dst_dir)

        results = find_all_hardlinks(src, [str(tmp_workspace["root"])])

        assert len(results) == 2
        normed = {os.path.normpath(r) for r in results}
        assert os.path.normpath(src) in normed
        assert os.path.normpath(link) in normed

    def test_finds_only_in_searched_dirs(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])
        dst_dir = str(tmp_workspace["dst_dir"])
        create_hardlink(src, dst_dir)

        # Only search in source dir
        results = find_all_hardlinks(src, [str(tmp_workspace["src_dir"])])

        assert len(results) == 1
        assert os.path.normpath(results[0]) == os.path.normpath(src)

    def test_no_extra_hardlinks(self, tmp_workspace):
        src = str(tmp_workspace["test_file"])

        results = find_all_hardlinks(src, [str(tmp_workspace["src_dir"])])

        assert len(results) == 1

    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            find_all_hardlinks("/nonexistent", ["/tmp"])
