"""Search/intersection panel for finding files across multiple folders."""

import os
import tkinter as tk
from tkinter import ttk, filedialog

from hardlink_manager.core.search import intersection_search
from hardlink_manager.utils.filesystem import format_file_size


class SearchPanel(ttk.Frame):
    """Panel for multi-folder intersection search."""

    def __init__(self, parent, status_callback=None):
        super().__init__(parent)
        self.status_callback = status_callback
        self._folder_list: list[str] = []

        self._build_ui()

    def _build_ui(self):
        # -- Folder selection area --
        folder_frame = ttk.LabelFrame(self, text="Folders to Intersect", padding=5)
        folder_frame.pack(fill=tk.X, padx=5, pady=5)

        btn_row = ttk.Frame(folder_frame)
        btn_row.pack(fill=tk.X, pady=(0, 5))
        ttk.Button(btn_row, text="Add Folder", command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Remove Selected", command=self._remove_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Clear All", command=self._clear_folders).pack(side=tk.LEFT, padx=2)

        self.folder_listbox = tk.Listbox(folder_frame, height=5)
        self.folder_listbox.pack(fill=tk.X)

        # -- Filter --
        filter_frame = ttk.Frame(self)
        filter_frame.pack(fill=tk.X, padx=5, pady=2)
        ttk.Label(filter_frame, text="Filename filter:").pack(side=tk.LEFT, padx=(0, 5))
        self.filter_var = tk.StringVar()
        ttk.Entry(filter_frame, textvariable=self.filter_var).pack(side=tk.LEFT, fill=tk.X, expand=True)

        # -- Search button --
        ttk.Button(self, text="Search Intersection", command=self._run_search).pack(pady=5)

        # -- Results --
        results_frame = ttk.LabelFrame(self, text="Results", padding=5)
        results_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("filename", "size", "inode", "locations")
        self.results_tree = ttk.Treeview(results_frame, columns=columns, show="headings", selectmode="browse")
        self.results_tree.heading("filename", text="Filename")
        self.results_tree.heading("size", text="Size")
        self.results_tree.heading("inode", text="Inode")
        self.results_tree.heading("locations", text="Locations")
        self.results_tree.column("filename", width=250)
        self.results_tree.column("size", width=80, anchor=tk.E)
        self.results_tree.column("inode", width=100, anchor=tk.E)
        self.results_tree.column("locations", width=300)

        scrollbar = ttk.Scrollbar(results_frame, orient=tk.VERTICAL, command=self.results_tree.yview)
        self.results_tree.configure(yscrollcommand=scrollbar.set)
        self.results_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        # Count label
        self.count_var = tk.StringVar(value="")
        ttk.Label(self, textvariable=self.count_var).pack(anchor=tk.W, padx=5)

    def _add_folder(self):
        d = filedialog.askdirectory(parent=self, title="Select Folder for Intersection Search")
        if d and d not in self._folder_list:
            self._folder_list.append(d)
            self.folder_listbox.insert(tk.END, d)

    def _remove_folder(self):
        sel = self.folder_listbox.curselection()
        if sel:
            idx = sel[0]
            self._folder_list.pop(idx)
            self.folder_listbox.delete(idx)

    def _clear_folders(self):
        self._folder_list.clear()
        self.folder_listbox.delete(0, tk.END)

    def _run_search(self):
        # Clear previous results
        for item in self.results_tree.get_children():
            self.results_tree.delete(item)
        self.count_var.set("")

        if len(self._folder_list) < 2:
            self.count_var.set("Please add at least 2 folders for intersection search.")
            return

        # Validate folders exist
        for folder in self._folder_list:
            if not os.path.isdir(folder):
                self.count_var.set(f"Folder not found: {folder}")
                return

        pattern = self.filter_var.get().strip() or None

        if self.status_callback:
            self.status_callback("Searching...")

        try:
            results = intersection_search(self._folder_list, filename_pattern=pattern)
        except Exception as e:
            self.count_var.set(f"Error: {e}")
            if self.status_callback:
                self.status_callback("Search failed.")
            return

        for r in results:
            locations = ", ".join(r.paths)
            self.results_tree.insert(
                "",
                tk.END,
                values=(r.filename, format_file_size(r.size), r.inode, locations),
            )

        self.count_var.set(f"Found {len(results)} file(s) in common across all {len(self._folder_list)} folders.")
        if self.status_callback:
            self.status_callback(f"Search complete: {len(results)} result(s).")
