"""Tests for intersection search functionality."""

import os
import pytest

from hardlink_manager.core.search import intersection_search, SearchResult


@pytest.fixture
def search_workspace(tmp_path):
    """Create folders with shared and unique files for intersection testing."""
    folder_a = tmp_path / "folder_a"
    folder_b = tmp_path / "folder_b"
    folder_c = tmp_path / "folder_c"
    folder_a.mkdir()
    folder_b.mkdir()
    folder_c.mkdir()

    # Shared file (hardlinked across A and B)
    shared = folder_a / "shared.txt"
    shared.write_text("shared content")
    os.link(str(shared), str(folder_b / "shared.txt"))

    # File in all three folders
    all_three = folder_a / "everywhere.txt"
    all_three.write_text("everywhere")
    os.link(str(all_three), str(folder_b / "everywhere.txt"))
    os.link(str(all_three), str(folder_c / "everywhere.txt"))

    # Unique files
    (folder_a / "only_a.txt").write_text("only in a")
    (folder_b / "only_b.txt").write_text("only in b")
    (folder_c / "only_c.txt").write_text("only in c")

    return {
        "root": tmp_path,
        "folder_a": str(folder_a),
        "folder_b": str(folder_b),
        "folder_c": str(folder_c),
    }


class TestIntersectionSearch:
    def test_finds_shared_files_between_two_folders(self, search_workspace):
        results = intersection_search([
            search_workspace["folder_a"],
            search_workspace["folder_b"],
        ])

        filenames = {r.filename for r in results}
        assert "shared.txt" in filenames
        assert "everywhere.txt" in filenames
        assert "only_a.txt" not in filenames
        assert "only_b.txt" not in filenames

    def test_finds_files_in_all_three_folders(self, search_workspace):
        results = intersection_search([
            search_workspace["folder_a"],
            search_workspace["folder_b"],
            search_workspace["folder_c"],
        ])

        filenames = {r.filename for r in results}
        assert "everywhere.txt" in filenames
        assert "shared.txt" not in filenames  # Not in folder_c
        assert len(results) == 1

    def test_filename_filter(self, search_workspace):
        results = intersection_search(
            [search_workspace["folder_a"], search_workspace["folder_b"]],
            filename_pattern="shared",
        )

        assert len(results) == 1
        assert results[0].filename == "shared.txt"

    def test_filename_filter_case_insensitive(self, search_workspace):
        results = intersection_search(
            [search_workspace["folder_a"], search_workspace["folder_b"]],
            filename_pattern="SHARED",
        )

        assert len(results) == 1

    def test_no_intersection(self, search_workspace):
        results = intersection_search(
            [search_workspace["folder_a"], search_workspace["folder_b"]],
            filename_pattern="nonexistent",
        )

        assert len(results) == 0

    def test_requires_two_folders(self):
        with pytest.raises(ValueError, match="at least 2"):
            intersection_search(["/tmp"])

    def test_result_has_correct_paths(self, search_workspace):
        results = intersection_search([
            search_workspace["folder_a"],
            search_workspace["folder_b"],
        ])

        shared_result = next(r for r in results if r.filename == "shared.txt")
        assert len(shared_result.paths) == 2

    def test_result_has_inode(self, search_workspace):
        results = intersection_search([
            search_workspace["folder_a"],
            search_workspace["folder_b"],
        ])

        for r in results:
            assert r.inode > 0

    def test_nonexistent_folder_skipped(self, search_workspace):
        results = intersection_search([
            search_workspace["folder_a"],
            "/nonexistent/path",
        ])

        # No intersection possible if one folder doesn't exist
        assert len(results) == 0
