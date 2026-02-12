"""Main application window for the Hardlink Manager."""

import os
import platform
import shutil
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog

from hardlink_manager.core.mirror_groups import MirrorGroupRegistry
from hardlink_manager.core.sync import (
    delete_from_group,
    delete_symlink_from_group,
    sync_group,
    sync_symlink_to_group,
)
from hardlink_manager.core.watcher import MirrorGroupWatcher
from hardlink_manager.ui.file_browser import DirectoryTree, FileListPanel, TabbedFileBrowser
from hardlink_manager.ui.mirror_panel import MirrorGroupPanel
from hardlink_manager.ui.search_panel import SearchPanel
from hardlink_manager.ui.dialogs import (
    CreateHardlinkDialog,
    CreateSymlinkDialog,
    DeleteHardlinkDialog,
    RenameDialog,
    ViewHardlinksDialog,
    ViewMirrorsDialog,
    ViewSymlinkDialog,
)
from hardlink_manager.utils.filesystem import (
    copy_item,
    delete_item,
    format_file_size,
    get_hardlink_count,
    get_inode,
    is_symlink,
    move_item,
    open_file,
    read_symlink_target,
    reveal_in_explorer,
    sanitize_filename,
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

        # Clipboard for copy/cut operations: (paths, mode) where mode is "copy" or "cut"
        self._clipboard: tuple[list[str], str] | None = None

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
        actions_menu.add_command(label="Open in Explorer", command=self._open_in_explorer_action)
        actions_menu.add_separator()
        actions_menu.add_command(label="Create Hardlink...", command=self._create_hardlink_action)
        actions_menu.add_command(label="View Hardlinks...", command=self._view_hardlinks_action)
        actions_menu.add_separator()
        actions_menu.add_command(label="Create Folder Symlink...", command=self._create_symlink_action)
        actions_menu.add_command(label="View Symlink Details...", command=self._view_symlink_action)

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

        self.file_list = TabbedFileBrowser(
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
            on_navigate=self._navigate_to_folder,
            get_scan_folders=lambda: list(self._root_dirs),
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
        self.file_context_menu.add_command(label="Open in Explorer", command=self._open_in_explorer_action)
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
        self.folder_context_menu.add_command(label="Open in New Tab", command=self._open_in_new_tab)
        self.folder_context_menu.add_command(label="Open in Explorer", command=self._open_in_explorer_action)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Copy", command=self._copy_action)
        self.folder_context_menu.add_command(label="Cut", command=self._cut_action)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Create Hardlink Mirror...", command=self._create_mirror_from_folder)
        self.folder_context_menu.add_command(label="Add to Existing Mirror...", command=self._add_folder_to_mirror)
        self.folder_context_menu.add_command(label="View Hardlink Mirrors", command=self._view_mirrors_action)
        self.folder_context_menu.add_separator()
        self.folder_context_menu.add_command(label="Rename...", command=self._rename_action)
        self.folder_context_menu.add_command(label="Delete", command=self._delete_action)

        # -- Symlink context menu --
        self.symlink_context_menu = tk.Menu(self.root, tearoff=0)
        self.symlink_context_menu.add_command(label="Open Target Folder", command=self._open_symlink_target)
        self.symlink_context_menu.add_command(label="Open in New Tab", command=self._open_in_new_tab)
        self.symlink_context_menu.add_command(label="View Symlink Details", command=self._view_symlink_action)
        self.symlink_context_menu.add_separator()
        self.symlink_context_menu.add_command(label="Delete Symlink", command=self._delete_action)

        # -- Background context menu (right-click on empty area) --
        self.bg_context_menu = tk.Menu(self.root, tearoff=0)
        self.bg_context_menu.add_command(label="Paste", command=self._paste_action)
        self.bg_context_menu.add_separator()
        self.bg_context_menu.add_command(label="Create Folder Symlink...", command=self._create_symlink_action)

        # Bind right-click on all file list tabs
        self.file_list.bind_tree("<Button-3>", self._show_context_menu)
        if platform.system() == "Darwin":
            self.file_list.bind_tree("<Button-2>", self._show_context_menu)

    def _bind_keyboard_shortcuts(self):
        self.root.bind_all("<Control-c>", lambda e: self._copy_action())
        self.root.bind_all("<Control-x>", lambda e: self._cut_action())
        self.root.bind_all("<Control-v>", lambda e: self._paste_action())
        self.root.bind_all("<Delete>", lambda e: self._delete_action())
        self.root.bind_all("<F2>", lambda e: self._rename_action())

    def _show_context_menu(self, event):
        tree = event.widget
        item = tree.identify_row(event.y)
        if item:
            # Only change selection if the clicked item isn't already selected
            # (preserves multi-selection for right-click)
            if item not in tree.selection():
                tree.selection_set(item)
            if self.file_list.is_selected_symlink():
                self.symlink_context_menu.tk_popup(event.x_root, event.y_root)
            elif self.file_list.is_selected_dir():
                self.folder_context_menu.tk_popup(event.x_root, event.y_root)
            else:
                self.file_context_menu.tk_popup(event.x_root, event.y_root)
        else:
            # Right-click on empty area — show paste/create-symlink menu
            if self.file_list.current_dir:
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

    def _navigate_to_folder(self, path: str):
        """Navigate the file browser to a folder and switch to the File Browser tab."""
        self.notebook.select(0)  # Switch to File Browser tab
        self.file_list.load_directory(path)
        self._set_status(f"Viewing: {path}")

    def _open_selected_folder(self):
        path = self.file_list.get_selected_path()
        if path and os.path.isdir(path):
            self.file_list.load_directory(path)
            self._set_status(f"Viewing: {path}")

    def _open_in_new_tab(self):
        path = self.file_list.get_selected_path()
        if path and os.path.isdir(path):
            self.file_list.open_in_new_tab(path)
            self._set_status(f"New tab: {path}")

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
        mirror_name = sanitize_filename(mirror_name)
        if not mirror_name:
            messagebox.showerror("Invalid Name", "The folder name is empty after removing invalid characters.", parent=self.root)
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
        selected = self.file_list.get_selected_paths()
        if not selected:
            return
        self._clipboard = (selected, "copy")
        names = ", ".join(os.path.basename(p) for p in selected)
        self._set_status(f"Copied {len(selected)} item(s): {names}")

    def _cut_action(self):
        selected = self.file_list.get_selected_paths()
        if not selected:
            return
        self._clipboard = (selected, "cut")
        names = ", ".join(os.path.basename(p) for p in selected)
        self._set_status(f"Cut {len(selected)} item(s): {names}")

    def _paste_action(self):
        if not self._clipboard:
            self._set_status("Nothing to paste.")
            return
        if not self.file_list.current_dir:
            self._set_status("Open a folder first.")
            return

        sources, mode = self._clipboard
        dest_dir = self.file_list.current_dir
        pasted = 0
        errors = []

        for src in sources:
            if not os.path.exists(src):
                continue
            try:
                if mode == "copy":
                    copy_item(src, dest_dir)
                else:
                    move_item(src, dest_dir)
                pasted += 1
            except (FileExistsError, OSError) as e:
                errors.append(str(e))

        if mode == "cut":
            self._clipboard = None

        if errors:
            messagebox.showerror("Paste Error", "\n".join(errors), parent=self.root)
        if pasted:
            verb = "Copied" if mode == "copy" else "Moved"
            self._set_status(f"{verb} {pasted} item(s).")
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

    def _open_in_explorer_action(self):
        selected = self.file_list.get_selected_path()
        if not selected:
            messagebox.showinfo("No Selection", "Please select a file or folder first.", parent=self.root)
            return
        try:
            reveal_in_explorer(selected)
            self._set_status(f"Opened in Explorer: {os.path.basename(selected)}")
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
            dlg = ViewHardlinksDialog(
                self.root, selected, search_dirs,
                on_navigate=self._navigate_to_folder,
            )
            dlg.wait_window()
        except Exception as e:
            try:
                messagebox.showerror("Error", f"Could not view hardlinks:\n{e}", parent=self.root)
            except Exception:
                pass

    def _view_mirrors_action(self):
        selected = self.file_list.get_selected_path()
        if not selected or not os.path.isdir(selected):
            messagebox.showinfo("No Folder Selected", "Please select a folder first.", parent=self.root)
            return
        group = self.registry.find_group_for_folder(selected)
        if not group:
            messagebox.showinfo(
                "Not Mirrored",
                f"'{os.path.basename(selected)}' is not part of any mirror group.",
                parent=self.root,
            )
            return
        dlg = ViewMirrorsDialog(
            self.root, selected, group,
            on_navigate=self._navigate_to_folder,
        )
        dlg.wait_window()

    # -- Symlink actions --

    def _create_symlink_action(self):
        """Create a folder symlink in the current directory."""
        if not self.file_list.current_dir:
            messagebox.showinfo("No Folder Open", "Open a folder first.", parent=self.root)
            return
        dlg = CreateSymlinkDialog(self.root, self.file_list.current_dir)
        self.root.wait_window(dlg)
        if dlg.result:
            self._set_status(f"Symlink created: {dlg.result}")
            # If the current dir is in a mirror group, sync the new symlink
            result = self.registry.find_group_for_path(dlg.result)
            if result:
                group, _root = result
                if group.sync_enabled:
                    try:
                        synced = sync_symlink_to_group(dlg.result, group)
                        if synced:
                            self._set_status(
                                f"Symlink created and synced to {len(synced)} mirror(s)"
                            )
                    except Exception:
                        pass
            self.file_list.load_directory(self.file_list.current_dir)

    def _view_symlink_action(self):
        """Show details of the selected symlink."""
        selected = self.file_list.get_selected_path()
        if not selected or not os.path.islink(selected):
            messagebox.showinfo("No Symlink Selected",
                                "Please select a symlink first.", parent=self.root)
            return
        dlg = ViewSymlinkDialog(
            self.root, selected,
            on_navigate=self._navigate_to_folder,
        )
        dlg.wait_window()

    def _open_symlink_target(self):
        """Navigate to the target folder of the selected symlink."""
        selected = self.file_list.get_selected_path()
        if not selected or not os.path.islink(selected):
            return
        try:
            target = read_symlink_target(selected)
            if os.path.isdir(target):
                self.file_list.load_directory(target)
                self._set_status(f"Viewing symlink target: {target}")
            else:
                messagebox.showwarning("Broken Symlink",
                                       f"Target no longer exists:\n{target}",
                                       parent=self.root)
        except OSError as e:
            messagebox.showerror("Error", str(e), parent=self.root)

    def _delete_action(self):
        """Delete the selected file(s) or folder(s)."""
        selected_paths = self.file_list.get_selected_paths()
        if not selected_paths:
            messagebox.showinfo("No Selection", "Please select a file or folder first.", parent=self.root)
            return

        # Single item: use detailed dialogs (mirror-group aware, hardlink info)
        if len(selected_paths) == 1:
            self._delete_single(selected_paths[0])
        else:
            self._delete_multiple(selected_paths)

        if self.file_list.current_dir:
            self.file_list.load_directory(self.file_list.current_dir)

    def _delete_single(self, selected: str):
        """Delete a single file, folder, or symlink with detailed confirmation."""
        if os.path.islink(selected):
            name = os.path.basename(selected)
            try:
                target = read_symlink_target(selected)
            except OSError:
                target = "(unreadable)"
            if not messagebox.askyesno(
                "Delete Symlink",
                f"Remove symlink '{name}'?\n\n"
                f"Points to: {target}\n\n"
                "Only the symlink is removed; the target folder is not affected.",
                parent=self.root,
            ):
                return
            # If in a mirror group, delete from all folders
            result = self.registry.find_group_for_path(selected)
            if result:
                group, _root = result
                try:
                    deleted = delete_symlink_from_group(selected, group)
                    self._set_status(f"Symlink removed from {len(deleted)} folder(s).")
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=self.root)
            else:
                try:
                    os.unlink(selected)
                    self._set_status(f"Deleted symlink: {name}")
                except Exception as e:
                    messagebox.showerror("Error", str(e), parent=self.root)
            return
        if os.path.isdir(selected):
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
        else:
            result = self.registry.find_group_for_path(selected)
            group = result[0] if result else None

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

    def _delete_multiple(self, paths: list[str]):
        """Delete multiple selected items with a single confirmation."""
        names = "\n".join(f"  - {os.path.basename(p)}" for p in paths[:10])
        if len(paths) > 10:
            names += f"\n  ... and {len(paths) - 10} more"
        if not messagebox.askyesno(
            "Delete Items",
            f"Delete {len(paths)} selected item(s)?\n\n{names}\n\n"
            "This cannot be undone.",
            parent=self.root,
        ):
            return

        deleted_count = 0
        errors = []
        for path in paths:
            try:
                if os.path.islink(path):
                    # Symlink: delete from mirror group or just unlink
                    result = self.registry.find_group_for_path(path)
                    if result:
                        delete_symlink_from_group(path, result[0])
                    else:
                        os.unlink(path)
                    deleted_count += 1
                    continue
                # Check mirror group membership for files
                if os.path.isfile(path):
                    result = self.registry.find_group_for_path(path)
                    if result:
                        delete_from_group(path, result[0])
                        deleted_count += 1
                        continue
                delete_item(path)
                deleted_count += 1
            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")
        if errors:
            messagebox.showerror("Delete Errors", "\n".join(errors), parent=self.root)
        self._set_status(f"Deleted {deleted_count} item(s).")

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
