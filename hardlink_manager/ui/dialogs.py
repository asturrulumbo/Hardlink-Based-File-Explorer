"""Dialog windows for hardlink operations."""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from hardlink_manager.core.hardlink_ops import create_hardlink, delete_hardlink, find_all_hardlinks
from hardlink_manager.utils.filesystem import (
    format_file_size,
    get_hardlink_count,
    get_inode,
)


class CreateHardlinkDialog(tk.Toplevel):
    """Dialog for creating a hardlink to a file."""

    def __init__(self, parent, source_path: str):
        super().__init__(parent)
        self.title("Create Hardlink")
        self.source_path = source_path
        self.result = None
        self.transient(parent)
        self.grab_set()

        self.minsize(500, 200)
        self._build_ui()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # Source file info
        ttk.Label(frame, text="Source file:").grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(frame, text=self.source_path, wraplength=400).grid(
            row=0, column=1, columnspan=2, sticky=tk.W, pady=2
        )

        # Destination directory
        ttk.Label(frame, text="Destination folder:").grid(row=1, column=0, sticky=tk.W, pady=2)
        self.dest_var = tk.StringVar()
        dest_entry = ttk.Entry(frame, textvariable=self.dest_var, width=50)
        dest_entry.grid(row=1, column=1, sticky=tk.EW, pady=2, padx=(0, 5))
        ttk.Button(frame, text="Browse...", command=self._browse_dest).grid(
            row=1, column=2, pady=2
        )

        # Link name
        ttk.Label(frame, text="Link name:").grid(row=2, column=0, sticky=tk.W, pady=2)
        self.name_var = tk.StringVar(value=os.path.basename(self.source_path))
        ttk.Entry(frame, textvariable=self.name_var, width=50).grid(
            row=2, column=1, columnspan=2, sticky=tk.EW, pady=2
        )

        frame.columnconfigure(1, weight=1)

        # Buttons
        btn_frame = ttk.Frame(frame)
        btn_frame.grid(row=3, column=0, columnspan=3, pady=(15, 0))
        ttk.Button(btn_frame, text="Create", command=self._on_create).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def _browse_dest(self):
        d = filedialog.askdirectory(parent=self, title="Select Destination Folder")
        if d:
            self.dest_var.set(d)

    def _on_create(self):
        dest_dir = self.dest_var.get().strip()
        dest_name = self.name_var.get().strip()
        if not dest_dir:
            messagebox.showwarning("Missing Destination", "Please select a destination folder.", parent=self)
            return
        if not dest_name:
            messagebox.showwarning("Missing Name", "Please enter a name for the hardlink.", parent=self)
            return
        try:
            result_path = create_hardlink(self.source_path, dest_dir, dest_name)
            self.result = result_path
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error Creating Hardlink", str(e), parent=self)


class ViewHardlinksDialog(tk.Toplevel):
    """Dialog showing all hardlinks to a given file."""

    def __init__(self, parent, file_path: str, search_dirs: list[str]):
        super().__init__(parent)
        self.title("View Hardlinks")
        self.file_path = file_path
        self.search_dirs = search_dirs
        self.transient(parent)
        self.grab_set()

        self.minsize(550, 350)
        self._build_ui()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        # File info
        info_frame = ttk.LabelFrame(frame, text="File Information", padding=5)
        info_frame.pack(fill=tk.X, pady=(0, 10))

        try:
            inode = get_inode(self.file_path)
            nlinks = get_hardlink_count(self.file_path)
            size = os.path.getsize(self.file_path)
        except OSError:
            inode = nlinks = size = 0

        ttk.Label(info_frame, text=f"File: {os.path.basename(self.file_path)}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Inode / File Index: {inode}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Hardlink count: {nlinks}").pack(anchor=tk.W)
        ttk.Label(info_frame, text=f"Size: {format_file_size(size)}").pack(anchor=tk.W)

        # Hardlink list
        ttk.Label(frame, text="Hardlink locations found:").pack(anchor=tk.W)

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(5, 0))

        scrollbar = ttk.Scrollbar(list_frame)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, font=("TkDefaultFont", 9))
        self.listbox.pack(fill=tk.BOTH, expand=True)
        scrollbar.config(command=self.listbox.yview)

        # Populate
        try:
            links = find_all_hardlinks(self.file_path, self.search_dirs)
            if links:
                for link in links:
                    self.listbox.insert(tk.END, link)
            else:
                self.listbox.insert(tk.END, "(No additional hardlinks found in searched directories)")
        except Exception as e:
            self.listbox.insert(tk.END, f"Error: {e}")

        # Close button
        ttk.Button(frame, text="Close", command=self.destroy).pack(pady=(10, 0))


class DeleteHardlinkDialog(tk.Toplevel):
    """Confirmation dialog for deleting a hardlink."""

    def __init__(self, parent, file_path: str, search_dirs: list[str]):
        super().__init__(parent)
        self.title("Delete Hardlink")
        self.file_path = file_path
        self.search_dirs = search_dirs
        self.deleted = False
        self.transient(parent)
        self.grab_set()

        self.minsize(500, 300)
        self._build_ui()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        try:
            nlinks = get_hardlink_count(self.file_path)
            links = find_all_hardlinks(self.file_path, self.search_dirs)
        except OSError:
            nlinks = 1
            links = [self.file_path]

        ttk.Label(frame, text=f"Delete: {os.path.basename(self.file_path)}", font=("TkDefaultFont", 10, "bold")).pack(
            anchor=tk.W, pady=(0, 5)
        )
        ttk.Label(frame, text=f"Path: {self.file_path}", wraplength=450).pack(anchor=tk.W)

        if nlinks > 1:
            ttk.Label(
                frame,
                text=f"\nThis file has {nlinks} hardlink(s). The data will be preserved\n"
                     f"through the remaining link(s).",
                foreground="blue",
            ).pack(anchor=tk.W, pady=5)

            ttk.Label(frame, text="Other locations with this file:").pack(anchor=tk.W)
            list_frame = ttk.Frame(frame)
            list_frame.pack(fill=tk.BOTH, expand=True, pady=5)
            scrollbar = ttk.Scrollbar(list_frame)
            scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            listbox = tk.Listbox(list_frame, yscrollcommand=scrollbar.set, height=6)
            listbox.pack(fill=tk.BOTH, expand=True)
            scrollbar.config(command=listbox.yview)
            for link in links:
                if os.path.normpath(link) != os.path.normpath(self.file_path):
                    listbox.insert(tk.END, link)
        else:
            ttk.Label(
                frame,
                text="\nWARNING: This is the LAST hardlink to this file.\n"
                     "Deleting it will permanently remove the file data!",
                foreground="red",
                font=("TkDefaultFont", 9, "bold"),
            ).pack(anchor=tk.W, pady=10)

        btn_frame = ttk.Frame(frame)
        btn_frame.pack(pady=(10, 0))
        ttk.Button(btn_frame, text="Delete", command=self._on_delete).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def _on_delete(self):
        try:
            delete_hardlink(self.file_path)
            self.deleted = True
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error Deleting", str(e), parent=self)


class RenameDialog(tk.Toplevel):
    """Dialog for renaming a file."""

    def __init__(self, parent, file_path: str):
        super().__init__(parent)
        self.title("Rename File")
        self.file_path = file_path
        self.new_path = None  # set on success
        self.transient(parent)
        self.grab_set()

        self.minsize(450, 130)
        self._build_ui()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        x = px + (pw - w) // 2
        y = py + (ph - h) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="New name:").pack(anchor=tk.W, pady=(0, 2))

        old_name = os.path.basename(self.file_path)
        self.name_var = tk.StringVar(value=old_name)
        entry = ttk.Entry(frame, textvariable=self.name_var, width=60)
        entry.pack(fill=tk.X, pady=(0, 10))

        # Pre-select the name part before the extension
        dot = old_name.rfind(".")
        entry.focus_set()
        if dot > 0:
            entry.selection_range(0, dot)
            entry.icursor(dot)
        else:
            entry.selection_range(0, tk.END)

        entry.bind("<Return>", lambda e: self._on_rename())
        entry.bind("<Escape>", lambda e: self.destroy())

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="Rename", command=self._on_rename).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", command=self.destroy).pack(side=tk.LEFT, padx=5)

    def _on_rename(self):
        new_name = self.name_var.get().strip()
        if not new_name:
            messagebox.showwarning("Empty Name", "Please enter a file name.", parent=self)
            return

        old_name = os.path.basename(self.file_path)
        if new_name == old_name:
            self.destroy()
            return

        new_path = os.path.join(os.path.dirname(self.file_path), new_name)

        if os.path.exists(new_path):
            messagebox.showerror("Name Taken", f"A file named '{new_name}' already exists.", parent=self)
            return

        try:
            os.rename(self.file_path, new_path)
            self.new_path = new_path
            self.destroy()
        except Exception as e:
            messagebox.showerror("Error Renaming", str(e), parent=self)
