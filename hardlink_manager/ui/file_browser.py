"""File browser panel with tree navigation and file listing."""

import os
import tkinter as tk
from tkinter import ttk
from typing import Callable, Optional

from hardlink_manager.utils.filesystem import format_file_size, get_hardlink_count, get_inode


class DirectoryTree(ttk.Frame):
    """Tree view for navigating the directory structure."""

    def __init__(self, parent, on_select: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.on_select = on_select

        self.tree = ttk.Treeview(self, show="tree", selectmode="browse")
        scrollbar = ttk.Scrollbar(self, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscrollcommand=scrollbar.set)

        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.tree.bind("<<TreeviewOpen>>", self._on_expand)
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        self._path_map: dict[str, str] = {}  # tree item id -> filesystem path

    def set_root(self, path: str, label: Optional[str] = None):
        """Set the root directory of the tree."""
        # Clear existing tree
        for item in self.tree.get_children():
            self.tree.delete(item)
        self._path_map.clear()

        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return

        display = label or os.path.basename(path) or path
        node_id = self.tree.insert("", tk.END, text=display, open=False)
        self._path_map[node_id] = path

        # Add a dummy child so the expand arrow shows
        if self._has_subdirs(path):
            self.tree.insert(node_id, tk.END, text="")

    def add_root(self, path: str, label: Optional[str] = None):
        """Add an additional root directory to the tree."""
        path = os.path.abspath(path)
        if not os.path.isdir(path):
            return

        display = label or os.path.basename(path) or path
        node_id = self.tree.insert("", tk.END, text=display, open=False)
        self._path_map[node_id] = path

        if self._has_subdirs(path):
            self.tree.insert(node_id, tk.END, text="")

    def _has_subdirs(self, path: str) -> bool:
        try:
            for entry in os.scandir(path):
                if entry.is_dir(follow_symlinks=False):
                    return True
        except PermissionError:
            pass
        return False

    def _on_expand(self, event):
        node_id = self.tree.focus()
        path = self._path_map.get(node_id)
        if not path:
            return

        # Remove dummy children
        children = self.tree.get_children(node_id)
        for child in children:
            if not self._path_map.get(child):
                self.tree.delete(child)

        # Already populated?
        if any(self._path_map.get(c) for c in self.tree.get_children(node_id)):
            return

        # Populate subdirectories
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name.lower())
            for entry in entries:
                if entry.is_dir(follow_symlinks=False):
                    child_id = self.tree.insert(node_id, tk.END, text=entry.name)
                    self._path_map[child_id] = entry.path
                    if self._has_subdirs(entry.path):
                        self.tree.insert(child_id, tk.END, text="")
        except PermissionError:
            pass

    def _on_select(self, event):
        sel = self.tree.selection()
        if sel and self.on_select:
            node_id = sel[0]
            path = self._path_map.get(node_id)
            if path:
                self.on_select(path)

    def get_selected_path(self) -> Optional[str]:
        sel = self.tree.selection()
        if sel:
            return self._path_map.get(sel[0])
        return None


class FileListPanel(ttk.Frame):
    """Panel showing the contents of a directory with file metadata."""

    COLUMNS = ("name", "size", "hardlinks", "inode")
    HEADERS = {"name": "Name", "size": "Size", "hardlinks": "Links", "inode": "Inode"}
    WIDTHS = {"name": 300, "size": 80, "hardlinks": 60, "inode": 100}

    def __init__(self, parent, on_file_select: Optional[Callable[[str], None]] = None,
                 on_file_open: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.on_file_select = on_file_select
        self.on_file_open = on_file_open
        self.current_dir: Optional[str] = None
        self._file_paths: dict[str, str] = {}  # tree item id -> file path

        # Path bar
        self.path_var = tk.StringVar()
        path_bar = ttk.Frame(self)
        path_bar.pack(fill=tk.X, pady=(0, 2))
        ttk.Label(path_bar, text="Path:").pack(side=tk.LEFT, padx=(0, 5))
        ttk.Label(path_bar, textvariable=self.path_var, relief=tk.SUNKEN, padding=2).pack(
            side=tk.LEFT, fill=tk.X, expand=True
        )

        # File list (Treeview with columns)
        list_frame = ttk.Frame(self)
        list_frame.pack(fill=tk.BOTH, expand=True)

        self.file_tree = ttk.Treeview(
            list_frame,
            columns=self.COLUMNS,
            show="headings",
            selectmode="browse",
        )
        for col in self.COLUMNS:
            self.file_tree.heading(col, text=self.HEADERS[col], command=lambda c=col: self._sort_by(c))
            anchor = tk.W if col == "name" else tk.E
            self.file_tree.column(col, width=self.WIDTHS[col], anchor=anchor)

        scrollbar_y = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        scrollbar_x = ttk.Scrollbar(list_frame, orient=tk.HORIZONTAL, command=self.file_tree.xview)
        self.file_tree.configure(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)

        self.file_tree.grid(row=0, column=0, sticky="nsew")
        scrollbar_y.grid(row=0, column=1, sticky="ns")
        scrollbar_x.grid(row=1, column=0, sticky="ew")
        list_frame.columnconfigure(0, weight=1)
        list_frame.rowconfigure(0, weight=1)

        self.file_tree.bind("<<TreeviewSelect>>", self._on_select)
        self.file_tree.bind("<Double-1>", self._on_double_click)

        self._sort_col = "name"
        self._sort_reverse = False

    def load_directory(self, path: str):
        """Load and display the contents of a directory."""
        path = os.path.abspath(path)
        self.current_dir = path
        self.path_var.set(path)
        self._file_paths.clear()

        # Clear existing items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        if not os.path.isdir(path):
            return

        entries = []
        try:
            for entry in os.scandir(path):
                if entry.is_file(follow_symlinks=False):
                    try:
                        st = entry.stat()
                        entries.append({
                            "name": entry.name,
                            "size": st.st_size,
                            "hardlinks": st.st_nlink,
                            "inode": st.st_ino,
                            "path": entry.path,
                        })
                    except OSError:
                        entries.append({
                            "name": entry.name,
                            "size": 0,
                            "hardlinks": 0,
                            "inode": 0,
                            "path": entry.path,
                        })
        except PermissionError:
            return

        # Sort
        entries.sort(key=lambda e: e["name"].lower())

        for e in entries:
            item_id = self.file_tree.insert(
                "",
                tk.END,
                values=(
                    e["name"],
                    format_file_size(e["size"]),
                    e["hardlinks"],
                    e["inode"],
                ),
            )
            self._file_paths[item_id] = e["path"]

    def get_selected_file(self) -> Optional[str]:
        sel = self.file_tree.selection()
        if sel:
            return self._file_paths.get(sel[0])
        return None

    def _on_select(self, event):
        if self.on_file_select:
            path = self.get_selected_file()
            if path:
                self.on_file_select(path)

    def _on_double_click(self, event):
        path = self.get_selected_file()
        if path and self.on_file_open:
            self.on_file_open(path)

    def _sort_by(self, col: str):
        if col == self._sort_col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        items = [(self.file_tree.set(item, col), item) for item in self.file_tree.get_children()]

        if col in ("size", "hardlinks", "inode"):
            def sort_key(pair):
                val = pair[0]
                # Parse numeric values for proper sorting
                try:
                    # For size, strip unit suffix
                    num_str = val.split()[0] if val else "0"
                    return float(num_str)
                except (ValueError, IndexError):
                    return 0
            items.sort(key=sort_key, reverse=self._sort_reverse)
        else:
            items.sort(key=lambda pair: pair[0].lower(), reverse=self._sort_reverse)

        for index, (_val, item) in enumerate(items):
            self.file_tree.move(item, "", index)
