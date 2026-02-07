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
    """Panel showing the contents of a directory with file metadata.

    Displays both folders and files like Windows Explorer, with folders first.
    Double-clicking a folder navigates into it. Double-clicking a file opens it.
    """

    COLUMNS = ("name", "type", "size", "hardlinks", "inode")
    HEADERS = {"name": "Name", "type": "Type", "size": "Size", "hardlinks": "Links", "inode": "Inode"}
    WIDTHS = {"name": 280, "type": 70, "size": 80, "hardlinks": 60, "inode": 100}

    def __init__(self, parent, on_file_select: Optional[Callable[[str], None]] = None,
                 on_file_open: Optional[Callable[[str], None]] = None,
                 on_dir_select: Optional[Callable[[str], None]] = None,
                 on_dir_open: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.on_file_select = on_file_select
        self.on_file_open = on_file_open
        self.on_dir_select = on_dir_select
        self.on_dir_open = on_dir_open
        self.current_dir: Optional[str] = None
        self._item_paths: dict[str, str] = {}   # tree item id -> filesystem path
        self._item_is_dir: dict[str, bool] = {}  # tree item id -> True if directory

        # Path bar with Up button
        path_bar = ttk.Frame(self)
        path_bar.pack(fill=tk.X, pady=(0, 2))
        self._up_btn = ttk.Button(path_bar, text="\u2191 Up", width=5, command=self._go_up)
        self._up_btn.pack(side=tk.LEFT, padx=(0, 5))
        self.path_var = tk.StringVar()
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
            anchor = tk.W if col in ("name", "type") else tk.E
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
        """Load and display the contents of a directory (folders first, then files)."""
        path = os.path.abspath(path)
        self.current_dir = path
        self.path_var.set(path)
        self._item_paths.clear()
        self._item_is_dir.clear()

        # Clear existing items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        if not os.path.isdir(path):
            return

        dir_entries = []
        file_entries = []
        try:
            for entry in os.scandir(path):
                try:
                    if entry.is_dir(follow_symlinks=False):
                        dir_entries.append({
                            "name": entry.name,
                            "type": "Folder",
                            "size": "",
                            "hardlinks": "",
                            "inode": "",
                            "path": entry.path,
                            "is_dir": True,
                        })
                    elif entry.is_file(follow_symlinks=False):
                        # Use os.stat() instead of entry.stat() because
                        # DirEntry.stat() on Windows doesn't populate st_nlink
                        st = os.stat(entry.path)
                        file_entries.append({
                            "name": entry.name,
                            "type": "File",
                            "size": format_file_size(st.st_size),
                            "hardlinks": st.st_nlink,
                            "inode": st.st_ino,
                            "path": entry.path,
                            "is_dir": False,
                        })
                except OSError:
                    continue
        except PermissionError:
            return

        # Sort: folders first (alphabetical), then files (alphabetical)
        dir_entries.sort(key=lambda e: e["name"].lower())
        file_entries.sort(key=lambda e: e["name"].lower())

        for e in dir_entries + file_entries:
            item_id = self.file_tree.insert(
                "",
                tk.END,
                values=(
                    e["name"],
                    e["type"],
                    e["size"],
                    e["hardlinks"],
                    e["inode"],
                ),
            )
            self._item_paths[item_id] = e["path"]
            self._item_is_dir[item_id] = e["is_dir"]

    def get_selected_file(self) -> Optional[str]:
        """Get the selected file path (returns None if a folder is selected)."""
        sel = self.file_tree.selection()
        if sel:
            item_id = sel[0]
            if not self._item_is_dir.get(item_id, False):
                return self._item_paths.get(item_id)
        return None

    def get_selected_path(self) -> Optional[str]:
        """Get the selected path (file or folder)."""
        sel = self.file_tree.selection()
        if sel:
            return self._item_paths.get(sel[0])
        return None

    def is_selected_dir(self) -> bool:
        """Check whether the currently selected item is a directory."""
        sel = self.file_tree.selection()
        if sel:
            return self._item_is_dir.get(sel[0], False)
        return False

    def _go_up(self):
        """Navigate to the parent directory."""
        if self.current_dir:
            parent = os.path.dirname(self.current_dir)
            if parent and parent != self.current_dir:
                self.load_directory(parent)
                if self.on_dir_open:
                    self.on_dir_open(parent)

    def _on_select(self, event):
        sel = self.file_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        path = self._item_paths.get(item_id)
        if not path:
            return
        if self._item_is_dir.get(item_id, False):
            if self.on_dir_select:
                self.on_dir_select(path)
        else:
            if self.on_file_select:
                self.on_file_select(path)

    def _on_double_click(self, event):
        sel = self.file_tree.selection()
        if not sel:
            return
        item_id = sel[0]
        path = self._item_paths.get(item_id)
        if not path:
            return
        if self._item_is_dir.get(item_id, False):
            # Navigate into folder
            self.load_directory(path)
            if self.on_dir_open:
                self.on_dir_open(path)
        else:
            if self.on_file_open:
                self.on_file_open(path)

    def _sort_by(self, col: str):
        if col == self._sort_col:
            self._sort_reverse = not self._sort_reverse
        else:
            self._sort_col = col
            self._sort_reverse = False

        items = [(self.file_tree.set(item, col), item) for item in self.file_tree.get_children()]

        # Always keep folders before files, then sort within each group
        def sort_key(pair):
            val, item_id = pair
            is_dir = self._item_is_dir.get(item_id, False)
            if col in ("size", "hardlinks", "inode"):
                try:
                    num_str = val.split()[0] if val else "0"
                    num = float(num_str)
                except (ValueError, IndexError):
                    num = -1 if is_dir else 0
                return (0 if is_dir else 1, num)
            else:
                return (0 if is_dir else 1, val.lower())

        items.sort(key=sort_key, reverse=self._sort_reverse)

        for index, (_val, item) in enumerate(items):
            self.file_tree.move(item, "", index)
