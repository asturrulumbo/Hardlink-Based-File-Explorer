"""Tests for filesystem utility functions."""

import os
import pytest

from unittest.mock import patch

from hardlink_manager.utils.filesystem import (
    copy_item,
    delete_item,
    format_file_size,
    get_hardlink_count,
    get_inode,
    is_regular_file,
    is_same_volume,
    move_item,
    reveal_in_explorer,
    sanitize_filename,
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


class TestCopyItem:
    def test_copy_file(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("content")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        result = copy_item(str(src), str(dest_dir))
        assert os.path.exists(result)
        assert open(result).read() == "content"
        # Original still exists
        assert os.path.exists(str(src))

    def test_copy_folder(self, tmp_path):
        src_dir = tmp_path / "src_folder"
        src_dir.mkdir()
        (src_dir / "a.txt").write_text("a")
        (src_dir / "b.txt").write_text("b")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        result = copy_item(str(src_dir), str(dest_dir))
        assert os.path.isdir(result)
        assert (dest_dir / "src_folder" / "a.txt").read_text() == "a"
        assert (dest_dir / "src_folder" / "b.txt").read_text() == "b"

    def test_copy_with_new_name(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("data")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        result = copy_item(str(src), str(dest_dir), new_name="renamed.txt")
        assert os.path.basename(result) == "renamed.txt"
        assert open(result).read() == "data"

    def test_copy_file_exists_error(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("data")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        (dest_dir / "source.txt").write_text("existing")
        with pytest.raises(FileExistsError):
            copy_item(str(src), str(dest_dir))


class TestMoveItem:
    def test_move_file(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("content")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        result = move_item(str(src), str(dest_dir))
        assert os.path.exists(result)
        assert not os.path.exists(str(src))

    def test_move_folder(self, tmp_path):
        src_dir = tmp_path / "src_folder"
        src_dir.mkdir()
        (src_dir / "file.txt").write_text("data")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        result = move_item(str(src_dir), str(dest_dir))
        assert os.path.isdir(result)
        assert not os.path.exists(str(src_dir))
        assert (dest_dir / "src_folder" / "file.txt").read_text() == "data"

    def test_move_with_new_name(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("data")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        result = move_item(str(src), str(dest_dir), new_name="moved.txt")
        assert os.path.basename(result) == "moved.txt"
        assert not os.path.exists(str(src))

    def test_move_file_exists_error(self, tmp_path):
        src = tmp_path / "source.txt"
        src.write_text("data")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        (dest_dir / "source.txt").write_text("existing")
        with pytest.raises(FileExistsError):
            move_item(str(src), str(dest_dir))


class TestSanitizeFilename:
    def test_plain_ascii(self):
        assert sanitize_filename("hello.txt") == "hello.txt"

    def test_arabic_preserved(self):
        assert sanitize_filename("احمد هاشم") == "احمد هاشم"

    def test_turkish_preserved(self):
        assert sanitize_filename("Ahmet Haşim") == "Ahmet Haşim"

    def test_strips_rtl_mark(self):
        # U+200F RIGHT-TO-LEFT MARK
        assert sanitize_filename("test\u200fname") == "testname"

    def test_strips_ltr_mark(self):
        # U+200E LEFT-TO-RIGHT MARK
        assert sanitize_filename("test\u200ename") == "testname"

    def test_strips_bidi_embedding(self):
        # U+202B RIGHT-TO-LEFT EMBEDDING, U+202C POP DIRECTIONAL FORMATTING
        assert sanitize_filename("\u202bاحمد\u202c") == "احمد"

    def test_strips_zero_width_joiner(self):
        assert sanitize_filename("a\u200db") == "ab"

    def test_strips_bom(self):
        assert sanitize_filename("\ufefftest") == "test"

    def test_removes_forbidden_chars(self):
        assert sanitize_filename('file<>:"/\\|?*name') == "filename"

    def test_strips_trailing_dots(self):
        assert sanitize_filename("folder...") == "folder"

    def test_strips_trailing_spaces(self):
        assert sanitize_filename("folder   ") == "folder"

    def test_empty_after_sanitize(self):
        assert sanitize_filename("\u200f\u200e") == ""

    def test_mixed_arabic_with_control_chars(self):
        # Simulates what tkinter might produce with Arabic input
        assert sanitize_filename("\u200fاحمد هاشم\u200f") == "احمد هاشم"


class TestRevealInExplorer:
    @patch("hardlink_manager.utils.filesystem.platform.system", return_value="Linux")
    @patch("hardlink_manager.utils.filesystem._popen_safe")
    def test_linux_file(self, mock_popen, mock_sys, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        reveal_in_explorer(str(f))
        mock_popen.assert_called_once_with(["xdg-open", str(tmp_path)])

    @patch("hardlink_manager.utils.filesystem.platform.system", return_value="Linux")
    @patch("hardlink_manager.utils.filesystem._popen_safe")
    def test_linux_folder(self, mock_popen, mock_sys, tmp_path):
        d = tmp_path / "subdir"
        d.mkdir()
        reveal_in_explorer(str(d))
        mock_popen.assert_called_once_with(["xdg-open", str(d)])

    @patch("hardlink_manager.utils.filesystem.platform.system", return_value="Darwin")
    @patch("hardlink_manager.utils.filesystem._popen_safe")
    def test_macos(self, mock_popen, mock_sys, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        reveal_in_explorer(str(f))
        mock_popen.assert_called_once_with(["open", "-R", str(f)])


class TestDeleteItem:
    def test_delete_file(self, tmp_path):
        f = tmp_path / "file.txt"
        f.write_text("data")
        delete_item(str(f))
        assert not os.path.exists(str(f))

    def test_delete_folder(self, tmp_path):
        d = tmp_path / "folder"
        d.mkdir()
        (d / "file.txt").write_text("data")
        delete_item(str(d))
        assert not os.path.exists(str(d))

    def test_delete_nonexistent(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            delete_item(str(tmp_path / "nonexistent"))
