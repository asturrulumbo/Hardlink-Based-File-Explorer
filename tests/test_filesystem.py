"""Tests for filesystem utility functions."""

import os
import pytest

from hardlink_manager.utils.filesystem import (
    format_file_size,
    get_hardlink_count,
    get_inode,
    is_regular_file,
    is_same_volume,
)


class TestGetInode:
    def test_returns_inode(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        inode = get_inode(str(f))
        assert isinstance(inode, int)
        assert inode > 0

    def test_hardlinks_share_inode(self, tmp_path):
        f = tmp_path / "original.txt"
        f.write_text("hello")
        link = tmp_path / "link.txt"
        os.link(str(f), str(link))

        assert get_inode(str(f)) == get_inode(str(link))

    def test_different_files_different_inodes(self, tmp_path):
        f1 = tmp_path / "file1.txt"
        f2 = tmp_path / "file2.txt"
        f1.write_text("hello")
        f2.write_text("world")

        assert get_inode(str(f1)) != get_inode(str(f2))


class TestGetHardlinkCount:
    def test_single_file_has_count_1(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert get_hardlink_count(str(f)) == 1

    def test_count_increases_with_links(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        os.link(str(f), str(tmp_path / "link1.txt"))
        assert get_hardlink_count(str(f)) == 2
        os.link(str(f), str(tmp_path / "link2.txt"))
        assert get_hardlink_count(str(f)) == 3


class TestFormatFileSize:
    def test_bytes(self):
        assert format_file_size(500) == "500 B"

    def test_kilobytes(self):
        assert format_file_size(1536) == "1.5 KB"

    def test_megabytes(self):
        assert format_file_size(5 * 1024 * 1024) == "5.0 MB"

    def test_gigabytes(self):
        assert format_file_size(2 * 1024 * 1024 * 1024) == "2.00 GB"

    def test_zero(self):
        assert format_file_size(0) == "0 B"


class TestIsSameVolume:
    def test_same_directory(self, tmp_path):
        f1 = tmp_path / "a.txt"
        f2 = tmp_path / "b.txt"
        f1.write_text("a")
        f2.write_text("b")
        assert is_same_volume(str(f1), str(f2))

    def test_same_volume_different_dirs(self, tmp_path):
        d1 = tmp_path / "dir1"
        d2 = tmp_path / "dir2"
        d1.mkdir()
        d2.mkdir()
        assert is_same_volume(str(d1), str(d2))


class TestIsRegularFile:
    def test_regular_file(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        assert is_regular_file(str(f))

    def test_directory(self, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        assert not is_regular_file(str(d))

    def test_symlink(self, tmp_path):
        f = tmp_path / "target.txt"
        f.write_text("hello")
        link = tmp_path / "symlink.txt"
        link.symlink_to(f)
        assert not is_regular_file(str(link))
