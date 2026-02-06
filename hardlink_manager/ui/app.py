"""Main application window for the Hardlink Manager."""

import os
import platform
import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from hardlink_manager.core.mirror_groups import MirrorGroupRegistry
from hardlink_manager.core.sync import delete_from_group, sync_group
from hardlink_manager.core.watcher import MirrorGroupWatcher
from hardlink_manager.ui.file_browser import DirectoryTree, FileListPanel
from hardlink_manager.ui.mirror_panel import MirrorGroupPanel, MirrorGroupDialog
from hardlink_manager.ui.search_panel import SearchPanel
from hardlink_manager.ui.dialogs import (
    CreateHardlinkDialog,
    DeleteHardlinkDialog,
    RenameDialog,
    ViewHardlinksDialog,
)
from hardlink_manager.utils.filesystem import format_file_size, get_hardlink_count, get_inode, open_file


class HardlinkManagerApp:
    """Main application for the Hardlink Manager."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Hardlink Manager")
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)

        # Track root directories for hardlink searches
        self._root_dirs: list[str] = []

        # Mirror group registry and watcher
        self.registry = MirrorGroupRegistry()
        self.watcher = MirrorGroupWatcher(
            self.registry,
            on_sync=self._on_watcher_sync,
        )

        self._build_menu()
        self._build_ui()
        self._build_context_menu()

        # Start watcher if there are sync-enabled groups
        self._restart_watcher()

        # Clean shutdown
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_menu(self):
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)

        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Open Folder...", command=self._open_folder)
        file_menu.add_command(label="Add Folder to Tree...", command=self._add_folder_to_tree)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self._on_close)

        # Actions menu
        actions_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions_menu)
        actions_menu.add_command(label="Open File", command=self._open_file_action)
        actions_menu.add_command(label="Rename...", command=self._rename_action)
        actions_menu.add_separator()
        actions_menu.add_command(label="Create Hardlink...", command=self._create_hardlink_action)
        actions_menu.add_command(label="View Hardlinks...", command=self._view_hardlinks_action)
        actions_menu.add_command(label="Delete...", command=self._delete_hardlink_action)

        # Help menu
        help_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Help", menu=help_menu)
        help_menu.add_command(label="About", command=self._show_about)

    def _build_ui(self):
        # Main paned window: left (tree) | right (content)
        main_pane = ttk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        main_pane.pack(fill=tk.BOTH, expand=True)

        # -- Left: Directory tree --
        left_frame = ttk.Frame(main_pane, width=280)
        left_frame.pack_propagate(False)

        tree_label = ttk.Label(left_frame, text="Directory Tree", font=("TkDefaultFont", 10, "bold"))
        tree_label.pack(anchor=tk.W, padx=5, pady=(5, 2))

        self.dir_tree = DirectoryTree(left_frame, on_select=self._on_tree_select)
        self.dir_tree.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        main_pane.add(left_frame, weight=1)

        # -- Right: Notebook with file browser, search, and mirror groups --
        right_frame = ttk.Frame(main_pane)

        self.notebook = ttk.Notebook(right_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Tab 1: File Browser
        browser_tab = ttk.Frame(self.notebook)
        self.notebook.add(browser_tab, text="File Browser")

        self.file_list = FileListPanel(
            browser_tab,
            on_file_select=self._on_file_select,
            on_file_open=self._open_file_action,
            on_dir_select=self._on_dir_select,
            on_dir_open=self._on_dir_open,
        )
        self.file_list.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        # Tab 2: Mirror Groups
        mirror_tab = ttk.Frame(self.notebook)
        self.notebook.add(mirror_tab, text="Mirror Groups")

        self.mirror_panel = MirrorGroupPanel(
            mirror_tab,
            registry=self.registry,
            on_change=self._on_mirror_groups_changed,
            status_callback=self._set_status,
        )
        self.mirror_panel.pack(fill=tk.BOTH, expand=True)

        # Tab 3: Intersection Search
        search_tab = ttk.Frame(self.notebook)
        self.notebook.add(search_tab, text="Intersection Search")

        self.search_panel = SearchPanel(search_tab, status_callback=self._set_status)
        self.search_panel.pack(fill=tk.BOTH, expand=True)

        main_pane.add(right_frame, weight=3)

        # -- Status bar --
        self.status_var = tk.StringVar(value="Ready. Open a folder to begin.")
        status_bar = ttk.Label(
            self.root,
            textvariable=self.status_var,
            relief=tk.SUNKEN,
            padding=(5, 2),
        )
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

    def _build_context_menu(self):
        # -- File context menu --
        self.file_context_menu = tk.Menu(self.root, tearoff=0)
        self.file_context_menu.add_command(label="Open", command=self._open_file_action)
        self.file_context_menu.add_command(label="Rename...", command=self._rename_action)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="Create Hardlink To...", command=self._create_hardlink_action)
        self.file_context_menu.add_command(label="View Hardlinks", command=self._view_hardlinks_action)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="Delete...", command=self._delete_hardlink_action)

        # -- Folder context menu --
        self.folder_context_menu = tk.Menu(self.root, tearoff=0)
        self.folder_context_menu.add_command(label="Open Folder", command=self._open_selected_folder)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Create Mirror Group...", command=self._create_mirror_from_folder)
        self.folder_context_menu.add_command(label="Add to Mirror Group...", command=self._add_folder_to_mirror)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Rename...", command=self._rename_action)

        # Bind right-click on the file list
        self.file_list.file_tree.bind("<Button-3>", self._show_context_menu)
        if platform.system() == "Darwin":
            self.file_list.file_tree.bind("<Button-2>", self._show_context_menu)

    def _show_context_menu(self, event):
        item = self.file_list.file_tree.identify_row(event.y)
        if item:
            self.file_list.file_tree.selection_set(item)
            if self.file_list.is_selected_dir():
                self.folder_context_menu.tk_popup(event.x_root, event.y_root)
            else:
                self.file_context_menu.tk_popup(event.x_root, event.y_root)

    # -- Watcher callbacks --

    def _on_watcher_sync(self, source: str, created: list[str]):
        """Called from the watcher thread when files are auto-synced."""
        n = len(created)
        msg = f"Auto-synced: {os.path.basename(source)} -> {n} mirror(s)"
        # Schedule UI update on main thread
        self.root.after(0, lambda: self._set_status(msg))

    def _on_mirror_groups_changed(self):
        """Called when mirror groups are created/edited/deleted."""
        self._restart_watcher()

    def _restart_watcher(self):
        """Restart the filesystem watcher to reflect current registry."""
        has_sync = any(g.sync_enabled for g in self.registry.get_all_groups())
        if has_sync:
            self.watcher.refresh()
        else:
            self.watcher.stop()

    def _on_close(self):
        """Clean shutdown."""
        self.watcher.stop()
        self.root.destroy()

    # -- Folder navigation callbacks --

    def _on_dir_select(self, path: str):
        """Called when a directory is selected in the file list."""
        self._set_status(f"Folder: {os.path.basename(path)}")

    def _on_dir_open(self, path: str):
        """Called when a directory is opened (double-click or Up button)."""
        self._set_status(f"Viewing: {path}")

    def _open_selected_folder(self):
        """Navigate into the selected folder in the file list."""
        path = self.file_list.get_selected_path()
        if path and os.path.isdir(path):
            self.file_list.load_directory(path)
            self._set_status(f"Viewing: {path}")

    def _create_mirror_from_folder(self):
        """Create a new mirror group starting with the selected folder."""
        path = self.file_list.get_selected_path()
        if not path or not os.path.isdir(path):
            return
        path = os.path.abspath(path)
        dlg = MirrorGroupDialog(
            self.root,
            title="Create Mirror Group",
            initial_folders=[path],
        )
        self.root.wait_window(dlg)
        if dlg.result:
            group = self.registry.create_group(
                name=dlg.result["name"],
                folders=dlg.result["folders"],
                sync_enabled=dlg.result["sync_enabled"],
            )
            if dlg.result["sync_enabled"]:
                try:
                    created = sync_group(group)
                    if created:
                        self._set_status(
                            f"Mirror group '{group.name}' created. "
                            f"{len(created)} file(s) synced."
                        )
                    else:
                        self._set_status(f"Mirror group '{group.name}' created.")
                except Exception:
                    self._set_status(f"Mirror group '{group.name}' created.")
            else:
                self._set_status(f"Mirror group '{group.name}' created.")
            self.mirror_panel.refresh_list()
            self._on_mirror_groups_changed()

    def _add_folder_to_mirror(self):
        """Add the selected folder to an existing mirror group."""
        path = self.file_list.get_selected_path()
        if not path or not os.path.isdir(path):
            return
        path = os.path.abspath(path)

        # Check if already in a group
        existing = self.registry.find_group_for_folder(path)
        if existing:
            messagebox.showinfo(
                "Already in Group",
                f"This folder is already in mirror group '{existing.name}'.",
                parent=self.root,
            )
            return

        groups = self.registry.get_all_groups()
        if not groups:
            messagebox.showinfo(
                "No Mirror Groups",
                "There are no mirror groups yet. Use 'Create Mirror Group' first.",
                parent=self.root,
            )
            return

        # Show picker dialog
        dlg = _GroupPickerDialog(self.root, groups)
        self.root.wait_window(dlg)
        if dlg.selected_group_id:
            self.registry.add_folder_to_group(dlg.selected_group_id, path)
            group = self.registry.get_group(dlg.selected_group_id)
            self._set_status(f"Added folder to mirror group '{group.name}'.")
            self.mirror_panel.refresh_list()
            self._on_mirror_groups_changed()

    # -- Menu / action handlers --

    def _open_folder(self):
        d = filedialog.askdirectory(parent=self.root, title="Open Folder")
        if d:
            self._root_dirs.clear()
            self._root_dirs.append(d)
            self.dir_tree.set_root(d)
            self.file_list.load_directory(d)
            self._set_status(f"Opened: {d}")

    def _add_folder_to_tree(self):
        d = filedialog.askdirectory(parent=self.root, title="Add Folder to Tree")
        if d:
            if d not in self._root_dirs:
                self._root_dirs.append(d)
            self.dir_tree.add_root(d)
            self._set_status(f"Added: {d}")

    def _on_tree_select(self, path: str):
        self.file_list.load_directory(path)
        self._set_status(f"Viewing: {path}")

    def _on_file_select(self, path: str):
        try:
            size = os.path.getsize(path)
            nlinks = get_hardlink_count(path)
            inode = get_inode(path)
            self._set_status(
                f"{os.path.basename(path)}  |  "
                f"Size: {format_file_size(size)}  |  "
                f"Links: {nlinks}  |  "
                f"Inode: {inode}"
            )
        except OSError:
            self._set_status(os.path.basename(path))

    def _open_file_action(self, path: str = None):
        selected = path or self.file_list.get_selected_file()
        if not selected:
            messagebox.showinfo("No File Selected", "Please select a file first.", parent=self.root)
            return
        try:
            open_file(selected)
            self._set_status(f"Opened: {os.path.basename(selected)}")
        except Exception as e:
            messagebox.showerror("Error Opening File", str(e), parent=self.root)

    def _rename_action(self):
        selected = self.file_list.get_selected_path()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a file or folder first.", parent=self.root)
            return
        dlg = RenameDialog(self.root, selected)
        self.root.wait_window(dlg)
        if dlg.new_path:
            self._set_status(f"Renamed to: {os.path.basename(dlg.new_path)}")
            if self.file_list.current_dir:
                self.file_list.load_directory(self.file_list.current_dir)

    def _create_hardlink_action(self):
        selected = self.file_list.get_selected_file()
        if not selected:
            messagebox.showinfo("No File Selected", "Please select a file first.", parent=self.root)
            return
        dlg = CreateHardlinkDialog(self.root, selected)
        self.root.wait_window(dlg)
        if dlg.result:
            self._set_status(f"Hardlink created: {dlg.result}")
            if self.file_list.current_dir:
                dest_dir = os.path.dirname(dlg.result)
                if os.path.normpath(dest_dir) == os.path.normpath(self.file_list.current_dir):
                    self.file_list.load_directory(self.file_list.current_dir)

    def _view_hardlinks_action(self):
        selected = self.file_list.get_selected_file()
        if not selected:
            messagebox.showinfo("No File Selected", "Please select a file first.", parent=self.root)
            return
        search_dirs = self._root_dirs if self._root_dirs else [os.path.dirname(selected)]
        try:
            dlg = ViewHardlinksDialog(self.root, selected, search_dirs)
            self.root.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _delete_hardlink_action(self):
        selected = self.file_list.get_selected_file()
        if not selected:
            messagebox.showinfo("No File Selected", "Please select a file first.", parent=self.root)
            return

        # Check if this file's folder is in a mirror group
        folder = os.path.dirname(os.path.abspath(selected))
        group = self.registry.find_group_for_folder(folder)

        if group is not None:
            # Mirror group deletion: ask to remove from all group folders
            folder_list = "\n".join(f"  - {f}" for f in group.folders)
            msg = (f"This file exists in mirror group '{group.name}':\n\n"
                   f"{folder_list}\n\n"
                   f"Remove from all folders?")
            if messagebox.askyesno("Delete from Mirror Group", msg, parent=self.root):
                try:
                    deleted = delete_from_group(selected, group)
                    self._set_status(
                        f"Deleted from {len(deleted)} folder(s) in '{group.name}'."
                    )
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=self.root)
        else:
            # Independent folder: standard deletion dialog
            search_dirs = self._root_dirs if self._root_dirs else [os.path.dirname(selected)]
            dlg = DeleteHardlinkDialog(self.root, selected, search_dirs)
            self.root.wait_window(dlg)
            if dlg.deleted:
                self._set_status(f"Deleted: {selected}")

        if self.file_list.current_dir:
            self.file_list.load_directory(self.file_list.current_dir)

    def _show_about(self):
        watcher_status = "running" if self.watcher.is_running else "stopped"
        n_groups = len(self.registry.get_all_groups())
        messagebox.showinfo(
            "About Hardlink Manager",
            "Hardlink Manager v0.2.0\n\n"
            "A hardlink-based file indexing and management system.\n\n"
            f"Mirror groups: {n_groups}\n"
            f"File watcher: {watcher_status}",
            parent=self.root,
        )

    def _set_status(self, msg: str):
        self.status_var.set(msg)

    def run(self):
        self.root.mainloop()


class _GroupPickerDialog(tk.Toplevel):
    """Simple dialog for picking an existing mirror group."""

    def __init__(self, parent, groups: list):
        super().__init__(parent)
        self.title("Select Mirror Group")
        self.selected_group_id = None
        self.transient(parent)
        self.grab_set()
        self.minsize(350, 250)

        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frame, text="Add folder to which mirror group?").pack(anchor=tk.W, pady=(0, 5))

        list_frame = ttk.Frame(frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self._listbox = tk.Listbox(list_frame, height=8)
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self._listbox.yview)
        self._listbox.configure(yscrollcommand=scrollbar.set)
        self._listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._group_ids = []
        for g in groups:
            self._listbox.insert(tk.END, f"{g.name}  ({len(g.folders)} folders)")
            self._group_ids.append(g.id)

        self._listbox.bind("<Double-1>", lambda e: self._on_ok())

        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="OK", width=10, command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side=tk.LEFT, padx=5)

        # Center on parent
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _on_ok(self):
        sel = self._listbox.curselection()
        if not sel:
            return
        self.selected_group_id = self._group_ids[sel[0]]
        self.destroy()
