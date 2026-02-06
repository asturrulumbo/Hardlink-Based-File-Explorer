"""Mirror group management panel and dialogs."""

import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

from hardlink_manager.core.mirror_groups import MirrorGroup, MirrorGroupRegistry
from hardlink_manager.core.sync import sync_group


class MirrorGroupPanel(ttk.Frame):
    """Panel for viewing and managing mirror groups."""

    def __init__(self, parent, registry: MirrorGroupRegistry,
                 on_change: Optional[Callable[[], None]] = None,
                 status_callback: Optional[Callable[[str], None]] = None):
        super().__init__(parent)
        self.registry = registry
        self.on_change = on_change
        self.status_callback = status_callback
        self._build_ui()
        self.refresh_list()

    def _build_ui(self):
        # -- Toolbar --
        toolbar = ttk.Frame(self)
        toolbar.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(toolbar, text="New Group", command=self._new_group).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Edit", command=self._edit_group).pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Delete", command=self._delete_group).pack(side=tk.LEFT, padx=2)
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)
        ttk.Button(toolbar, text="Sync Now", command=self._sync_group).pack(side=tk.LEFT, padx=2)

        # -- Group list --
        list_frame = ttk.LabelFrame(self, text="Mirror Groups", padding=5)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        columns = ("name", "folders", "sync")
        self.group_tree = ttk.Treeview(list_frame, columns=columns, show="headings",
                                       selectmode="browse", height=8)
        self.group_tree.heading("name", text="Group Name")
        self.group_tree.heading("folders", text="Folders")
        self.group_tree.heading("sync", text="Auto-Sync")
        self.group_tree.column("name", width=200)
        self.group_tree.column("folders", width=60, anchor=tk.CENTER)
        self.group_tree.column("sync", width=80, anchor=tk.CENTER)

        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.group_tree.yview)
        self.group_tree.configure(yscrollcommand=scrollbar.set)
        self.group_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self.group_tree.bind("<<TreeviewSelect>>", self._on_select)

        # -- Detail panel --
        detail_frame = ttk.LabelFrame(self, text="Group Details", padding=5)
        detail_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=(0, 5))

        self.detail_list = tk.Listbox(detail_frame, height=6, font=("TkDefaultFont", 9))
        detail_scroll = ttk.Scrollbar(detail_frame, orient=tk.VERTICAL, command=self.detail_list.yview)
        self.detail_list.configure(yscrollcommand=detail_scroll.set)
        self.detail_list.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        detail_scroll.pack(side=tk.RIGHT, fill=tk.Y)

    def refresh_list(self):
        """Refresh the group list from the registry."""
        # Remember selection
        sel = self._get_selected_group_id()

        for item in self.group_tree.get_children():
            self.group_tree.delete(item)
        self._group_ids: dict[str, str] = {}  # tree item id -> group id

        for group in self.registry.get_all_groups():
            sync_text = "On" if group.sync_enabled else "Off"
            item_id = self.group_tree.insert("", tk.END, values=(
                group.auto_name(), len(group.folders), sync_text
            ))
            self._group_ids[item_id] = group.id

        # Restore selection
        if sel:
            for item_id, gid in self._group_ids.items():
                if gid == sel:
                    self.group_tree.selection_set(item_id)
                    break

    def _get_selected_group_id(self) -> Optional[str]:
        sel = self.group_tree.selection()
        if sel:
            return self._group_ids.get(sel[0])
        return None

    def _on_select(self, event):
        group_id = self._get_selected_group_id()
        self.detail_list.delete(0, tk.END)
        if group_id is None:
            return
        group = self.registry.get_group(group_id)
        if group is None:
            return
        for folder in group.folders:
            self.detail_list.insert(tk.END, folder)

    def _new_group(self):
        dlg = MirrorGroupDialog(self.winfo_toplevel(), title="New Mirror Group")
        self.winfo_toplevel().wait_window(dlg)
        if dlg.result:
            self.registry.create_group(
                folders=dlg.result["folders"],
                sync_enabled=dlg.result["sync_enabled"],
            )
            self.refresh_list()
            self._notify_change("Mirror group created.")

    def _edit_group(self):
        group_id = self._get_selected_group_id()
        if group_id is None:
            messagebox.showinfo("No Selection", "Please select a group to edit.", parent=self)
            return
        group = self.registry.get_group(group_id)
        if group is None:
            return
        dlg = MirrorGroupDialog(self.winfo_toplevel(), title="Edit Mirror Group",
                                group=group)
        self.winfo_toplevel().wait_window(dlg)
        if dlg.result:
            self.registry.update_group(
                group_id,
                folders=dlg.result["folders"],
                sync_enabled=dlg.result["sync_enabled"],
            )
            self.refresh_list()
            self._notify_change("Mirror group updated.")

    def _delete_group(self):
        group_id = self._get_selected_group_id()
        if group_id is None:
            messagebox.showinfo("No Selection", "Please select a group to delete.", parent=self)
            return
        group = self.registry.get_group(group_id)
        if group is None:
            return
        if not messagebox.askyesno("Delete Mirror Group",
                                   f"Delete mirror group '{group.auto_name()}'?\n\n"
                                   "This only removes the group definition. "
                                   "Existing files and hardlinks are not affected.",
                                   parent=self.winfo_toplevel()):
            return
        self.registry.delete_group(group_id)
        self.detail_list.delete(0, tk.END)
        self.refresh_list()
        self._notify_change("Mirror group deleted.")

    def _sync_group(self):
        group_id = self._get_selected_group_id()
        if group_id is None:
            messagebox.showinfo("No Selection", "Please select a group to sync.", parent=self)
            return
        group = self.registry.get_group(group_id)
        if group is None:
            return
        try:
            created = sync_group(group)
            if created:
                msg = f"Synced '{group.auto_name()}': {len(created)} hardlink(s) created."
            else:
                msg = f"'{group.auto_name()}' is already in sync."
            self._set_status(msg)
            messagebox.showinfo("Sync Complete", msg, parent=self.winfo_toplevel())
        except Exception as e:
            messagebox.showerror("Sync Error", str(e), parent=self.winfo_toplevel())

    def _notify_change(self, msg: str):
        self._set_status(msg)
        if self.on_change:
            self.on_change()

    def _set_status(self, msg: str):
        if self.status_callback:
            self.status_callback(msg)


class MirrorGroupDialog(tk.Toplevel):
    """Dialog for creating or editing a mirror group."""

    def __init__(self, parent, title: str = "Mirror Group",
                 group: Optional[MirrorGroup] = None,
                 initial_folders: Optional[list[str]] = None):
        super().__init__(parent)
        self.title(title)
        self.result = None  # set on OK
        if group:
            self._folders: list[str] = list(group.folders)
        elif initial_folders:
            self._folders = list(initial_folders)
        else:
            self._folders = []
        self._group = group
        self.transient(parent)
        self.grab_set()

        self.minsize(550, 400)
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

        # Folders
        ttk.Label(frame, text="Folders in this mirror group:").pack(anchor=tk.W, pady=(0, 2))

        folder_frame = ttk.Frame(frame)
        folder_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 5))

        self.folder_listbox = tk.Listbox(folder_frame, height=8)
        folder_scroll = ttk.Scrollbar(folder_frame, orient=tk.VERTICAL,
                                      command=self.folder_listbox.yview)
        self.folder_listbox.configure(yscrollcommand=folder_scroll.set)
        self.folder_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        folder_scroll.pack(side=tk.RIGHT, fill=tk.Y)

        for f in self._folders:
            self.folder_listbox.insert(tk.END, f)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill=tk.X, pady=(0, 10))
        ttk.Button(btn_row, text="Add Folder", command=self._add_folder).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_row, text="Remove Selected", command=self._remove_folder).pack(side=tk.LEFT, padx=2)

        # Sync toggle
        self.sync_var = tk.BooleanVar(value=self._group.sync_enabled if self._group else True)
        ttk.Checkbutton(frame, text="Enable auto-sync (watch for new files)",
                        variable=self.sync_var).pack(anchor=tk.W, pady=(0, 10))

        # OK / Cancel
        btn_frame = ttk.Frame(frame)
        btn_frame.pack()
        ttk.Button(btn_frame, text="OK", width=10, command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Cancel", width=10, command=self.destroy).pack(side=tk.LEFT, padx=5)

    def _add_folder(self):
        d = filedialog.askdirectory(parent=self, title="Add Folder to Mirror Group")
        if d and d not in self._folders:
            self._folders.append(d)
            self.folder_listbox.insert(tk.END, d)

    def _remove_folder(self):
        sel = self.folder_listbox.curselection()
        if sel:
            idx = sel[0]
            self._folders.pop(idx)
            self.folder_listbox.delete(idx)

    def _on_ok(self):
        if len(self._folders) < 2:
            messagebox.showwarning("Not Enough Folders",
                                   "A mirror group needs at least 2 folders.", parent=self)
            return
        self.result = {
            "folders": list(self._folders),
            "sync_enabled": self.sync_var.get(),
        }
        self.destroy()
