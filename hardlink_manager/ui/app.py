"""Main application window for the Hardlink Manager."""

import os
import platform
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from hardlink_manager.core.mirror_groups import MirrorGroupRegistry
from hardlink_manager.core.sync import delete_from_group, sync_group
from hardlink_manager.core.watcher import MirrorGroupWatcher
from hardlink_manager.ui.file_browser import DirectoryTree, FileListPanel
from hardlink_manager.ui.mirror_panel import MirrorGroupPanel
from hardlink_manager.ui.search_panel import SearchPanel
from hardlink_manager.ui.dialogs import (
    CreateHardlinkDialog,
    DeleteHardlinkDialog,
    RenameDialog,
    ViewHardlinksDialog,
)
from hardlink_manager.utils.filesystem import (
    copy_item,
    delete_item,
    format_file_size,
    get_hardlink_count,
    get_inode,
    move_item,
    open_file,
    open_file_with,
)


class HardlinkManagerApp:
    """Main application for the Hardlink Manager."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Hardlink Manager")
        self.root.geometry("1100x700")
        self.root.minsize(800, 500)

        # Track root directories for hardlink searches
        self._root_dirs: list[str] = []

        # Clipboard for copy/cut operations: (path, mode) where mode is "copy" or "cut"
        self._clipboard: tuple[str, str] | None = None

        # Mirror group registry and watcher
        self.registry = MirrorGroupRegistry()
        self.watcher = MirrorGroupWatcher(
            self.registry,
            on_sync=self._on_watcher_sync,
        )

        self._build_menu()
        self._build_ui()
        self._build_context_menu()
        self._bind_keyboard_shortcuts()

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

        # Edit menu
        edit_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        edit_menu.add_command(label="Copy", accelerator="Ctrl+C", command=self._copy_action)
        edit_menu.add_command(label="Cut", accelerator="Ctrl+X", command=self._cut_action)
        edit_menu.add_command(label="Paste", accelerator="Ctrl+V", command=self._paste_action)
        edit_menu.add_separator()
        edit_menu.add_command(label="Rename...", accelerator="F2", command=self._rename_action)
        edit_menu.add_command(label="Delete", accelerator="Del", command=self._delete_action)

        # Actions menu
        actions_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="Actions", menu=actions_menu)
        actions_menu.add_command(label="Open", command=self._open_file_action)
        actions_menu.add_command(label="Open With...", command=self._open_with_action)
        actions_menu.add_separator()
        actions_menu.add_command(label="Create Hardlink...", command=self._create_hardlink_action)
        actions_menu.add_command(label="View Hardlinks...", command=self._view_hardlinks_action)

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
        self.file_context_menu.add_command(label="Open With...", command=self._open_with_action)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="Copy", command=self._copy_action)
        self.file_context_menu.add_command(label="Cut", command=self._cut_action)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="Create Hardlink To...", command=self._create_hardlink_action)
        self.file_context_menu.add_command(label="View Hardlinks", command=self._view_hardlinks_action)
        self.file_context_menu.add_separator()
        self.file_context_menu.add_command(label="Rename...", command=self._rename_action)
        self.file_context_menu.add_command(label="Delete", command=self._delete_action)

        # -- Folder context menu --
        self.folder_context_menu = tk.Menu(self.root, tearoff=0)
        self.folder_context_menu.add_command(label="Open Folder", command=self._open_selected_folder)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Copy", command=self._copy_action)
        self.folder_context_menu.add_command(label="Cut", command=self._cut_action)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Create Hardlink Mirror...", command=self._create_mirror_from_folder)
        self.folder_context_menu.add_command(label="Add to Existing Mirror...", command=self._add_folder_to_mirror)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Rename...", command=self._rename_action)
        self.folder_context_menu.add_command(label="Delete", command=self._delete_action)

        # -- Background context menu (right-click on empty area) --
        self.bg_context_menu = tk.Menu(self.root, tearoff=0)
        self.bg_context_menu.add_command(label="Paste", command=self._paste_action)

        # Bind right-click on the file list
        self.file_list.file_tree.bind("<Button-3>", self._show_context_menu)
        if platform.system() == "Darwin":
            self.file_list.file_tree.bind("<Button-2>", self._show_context_menu)

    def _bind_keyboard_shortcuts(self):
        self.root.bind_all("<Control-c>", lambda e: self._copy_action())
        self.root.bind_all("<Control-x>", lambda e: self._cut_action())
        self.root.bind_all("<Control-v>", lambda e: self._paste_action())
        self.root.bind_all("<Delete>", lambda e: self._delete_action())
        self.root.bind_all("<F2>", lambda e: self._rename_action())

    def _show_context_menu(self, event):
        item = self.file_list.file_tree.identify_row(event.y)
        if item:
            self.file_list.file_tree.selection_set(item)
            if self.file_list.is_selected_dir():
                self.folder_context_menu.tk_popup(event.x_root, event.y_root)
            else:
                self.file_context_menu.tk_popup(event.x_root, event.y_root)
        else:
            # Right-click on empty area — show paste menu
            if self._clipboard and self.file_list.current_dir:
                self.bg_context_menu.tk_popup(event.x_root, event.y_root)

    # -- Watcher callbacks --

    def _on_watcher_sync(self, source: str, created: list[str]):
        """Called from the watcher thread when files are auto-synced."""
        n = len(created)
        msg = f"Auto-synced: {os.path.basename(source)} -> {n} mirror(s)"
        self.root.after(0, lambda: self._set_status(msg))

    def _on_mirror_groups_changed(self):
        self._restart_watcher()

    def _restart_watcher(self):
        has_sync = any(g.sync_enabled for g in self.registry.get_all_groups())
        if has_sync:
            self.watcher.refresh()
        else:
            self.watcher.stop()

    def _on_close(self):
        self.watcher.stop()
        self.root.destroy()

    # -- Folder navigation callbacks --

    def _on_dir_select(self, path: str):
        self._set_status(f"Folder: {os.path.basename(path)}")

    def _on_dir_open(self, path: str):
        self._set_status(f"Viewing: {path}")

    def _open_selected_folder(self):
        path = self.file_list.get_selected_path()
        if path and os.path.isdir(path):
            self.file_list.load_directory(path)
            self._set_status(f"Viewing: {path}")

    # -- Mirror group actions --

    def _create_mirror_from_folder(self):
        """Create a hardlink mirror of the selected folder at a chosen location."""
        source = self.file_list.get_selected_path()
        if not source or not os.path.isdir(source):
            return
        source = os.path.abspath(source)
        source_name = os.path.basename(source)

        # Ask for the mirror folder name (default = same as source)
        mirror_name = simpledialog.askstring(
            "Mirror Folder Name",
            "Name for the mirror folder:",
            initialvalue=source_name,
            parent=self.root,
        )
        if not mirror_name:
            return

        # Ask where to place the mirror folder
        dest_parent = filedialog.askdirectory(
            parent=self.root,
            title="Choose where to place the mirror folder",
        )
        if not dest_parent:
            return

        dest = os.path.join(dest_parent, mirror_name)

        if os.path.exists(dest):
            messagebox.showerror(
                "Folder Exists",
                f"A folder named '{mirror_name}' already exists at that location.",
                parent=self.root,
            )
            return

        try:
            os.makedirs(dest)
        except OSError as e:
            messagebox.showerror("Error", f"Could not create folder:\n{e}", parent=self.root)
            return

        group = self.registry.create_group(folders=[source, dest])

        try:
            created = sync_group(group)
            n = len(created)
            self._set_status(f"Mirror created: {dest}  ({n} file(s) hardlinked)")
        except Exception as e:
            self._set_status(f"Mirror created at {dest} (sync error: {e})")

        self.mirror_panel.refresh_list()
        self._on_mirror_groups_changed()
        if self.file_list.current_dir and os.path.normpath(self.file_list.current_dir) == os.path.normpath(dest_parent):
            self.file_list.load_directory(self.file_list.current_dir)

    def _add_folder_to_mirror(self):
        path = self.file_list.get_selected_path()
        if not path or not os.path.isdir(path):
            return
        path = os.path.abspath(path)

        existing = self.registry.find_group_for_folder(path)
        if existing:
            messagebox.showinfo(
                "Already Mirrored",
                f"This folder is already in a mirror group:\n{existing.auto_name()}",
                parent=self.root,
            )
            return

        groups = self.registry.get_all_groups()
        if not groups:
            messagebox.showinfo(
                "No Mirror Groups",
                "There are no mirror groups yet. Use 'Create Hardlink Mirror' first.",
                parent=self.root,
            )
            return

        dlg = _GroupPickerDialog(self.root, groups)
        self.root.wait_window(dlg)
        if dlg.selected_group_id:
            self.registry.add_folder_to_group(dlg.selected_group_id, path)
            group = self.registry.get_group(dlg.selected_group_id)
            self._set_status(f"Added folder to mirror: {group.name}")
            self.mirror_panel.refresh_list()
            self._on_mirror_groups_changed()

    # -- Clipboard operations --

    def _copy_action(self):
        selected = self.file_list.get_selected_path()
        if not selected:
            return
        self._clipboard = (selected, "copy")
        self._set_status(f"Copied: {os.path.basename(selected)}")

    def _cut_action(self):
        selected = self.file_list.get_selected_path()
        if not selected:
            return
        self._clipboard = (selected, "cut")
        self._set_status(f"Cut: {os.path.basename(selected)}")

    def _paste_action(self):
        if not self._clipboard:
            self._set_status("Nothing to paste.")
            return
        if not self.file_list.current_dir:
            self._set_status("Open a folder first.")
            return

        src, mode = self._clipboard
        dest_dir = self.file_list.current_dir

        if not os.path.exists(src):
            self._set_status(f"Source no longer exists: {src}")
            self._clipboard = None
            return

        try:
            if mode == "copy":
                result = copy_item(src, dest_dir)
                self._set_status(f"Pasted (copy): {os.path.basename(result)}")
            else:  # cut
                result = move_item(src, dest_dir)
                self._set_status(f"Moved: {os.path.basename(result)}")
                self._clipboard = None  # Clear clipboard after move
        except FileExistsError as e:
            messagebox.showerror("Paste Error", str(e), parent=self.root)
            return
        except Exception as e:
            messagebox.showerror("Paste Error", str(e), parent=self.root)
            return

        self.file_list.load_directory(self.file_list.current_dir)

    # -- File/folder menu actions --

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

    def _open_with_action(self):
        selected = self.file_list.get_selected_file()
        if not selected:
            messagebox.showinfo("No File Selected", "Please select a file first.", parent=self.root)
            return

        system = platform.system()
        if system == "Windows":
            # Use the Windows "Open With" dialog
            from hardlink_manager.utils.filesystem import _popen_safe
            try:
                _popen_safe(["rundll32.exe", "shell32.dll,OpenAs_RunDLL", selected])
                self._set_status(f"Open With: {os.path.basename(selected)}")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.root)
        else:
            # Let the user browse for a program
            filetypes = [("All files", "*")] if system != "Darwin" else [("Applications", "*.app"), ("All files", "*")]
            program = filedialog.askopenfilename(
                parent=self.root,
                title="Choose program to open with",
                filetypes=filetypes,
            )
            if program:
                try:
                    open_file_with(selected, program)
                    self._set_status(f"Opened with {os.path.basename(program)}: {os.path.basename(selected)}")
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=self.root)

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
            dlg.wait_window()
        except Exception as e:
            try:
                messagebox.showerror("Error", f"Could not view hardlinks:\n{e}", parent=self.root)
            except Exception:
                pass

    def _delete_action(self):
        """Delete the selected file or folder."""
        selected = self.file_list.get_selected_path()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a file or folder first.", parent=self.root)
            return

        is_dir = os.path.isdir(selected)

        if is_dir:
            # Folder deletion
            name = os.path.basename(selected)
            if not messagebox.askyesno(
                "Delete Folder",
                f"Delete folder '{name}' and all its contents?\n\n"
                f"Path: {selected}\n\n"
                "This cannot be undone.",
                parent=self.root,
            ):
                return
            try:
                delete_item(selected)
                self._set_status(f"Deleted folder: {name}")
            except Exception as e:
                messagebox.showerror("Error", str(e), parent=self.root)
                return
        else:
            # File deletion — mirror-group aware
            folder = os.path.dirname(os.path.abspath(selected))
            group = self.registry.find_group_for_folder(folder)

            if group is not None:
                folder_list = "\n".join(f"  - {f}" for f in group.folders)
                msg = (f"This file is mirrored across:\n\n"
                       f"{folder_list}\n\n"
                       f"Remove from all folders?")
                if messagebox.askyesno("Delete from Mirror Group", msg, parent=self.root):
                    try:
                        deleted = delete_from_group(selected, group)
                        self._set_status(f"Deleted from {len(deleted)} folder(s).")
                    except Exception as e:
                        messagebox.showerror("Error", str(e), parent=self.root)
            else:
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
            self._listbox.insert(tk.END, g.auto_name())
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
