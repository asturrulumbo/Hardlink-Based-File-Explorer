"""Mirror group management panel and dialogs."""

import os
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import Callable, Optional

from hardlink_manager.core.mirror_groups import MirrorGroup, MirrorGroupRegistry
from hardlink_manager.core.sync import sync_group


class MirrorGroupPanel(ttk.Frame):
    """Panel for viewing and managing mirror groups."""

    def __init__(self, parent, registry: MirrorGroupRegistry,
                 on_change: Optional[Callable[[], None]] = None,
                 status_callback: Optional[Callable[[str], None]] = None,
                 on_navigate: Optional[Callable[[str], None]] = None,
                 get_scan_folders: Optional[Callable[[], list[str]]] = None):
        super().__init__(parent)
        self.registry = registry
        self.on_change = on_change
        self.status_callback = status_callback
        self.on_navigate = on_navigate
        self.get_scan_folders = get_scan_folders
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
        self._scan_btn = ttk.Button(toolbar, text="Scan for Mirrors", command=self._scan_for_mirrors)
        self._scan_btn.pack(side=tk.LEFT, padx=2)
        ttk.Button(toolbar, text="Sync Now", command=self._sync_group).pack(side=tk.LEFT, padx=2)

        self._scan_thread: threading.Thread | None = None

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

        self.detail_list.bind("<Double-1>", self._on_detail_double_click)

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

    def _on_detail_double_click(self, event):
        sel = self.detail_list.curselection()
        if not sel:
            return
        folder = self.detail_list.get(sel[0])
        if os.path.isdir(folder) and self.on_navigate:
            self.on_navigate(folder)

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

    # -- Background mirror scan --

    def _scan_for_mirrors(self):
        """Scan all folders opened in the File Browser for content-based mirrors."""
        if self._scan_thread is not None and self._scan_thread.is_alive():
            return  # already running

        if not self.get_scan_folders:
            messagebox.showinfo(
                "Not Available",
                "Scan folders source is not configured.",
                parent=self.winfo_toplevel(),
            )
            return

        root_folders = self.get_scan_folders()
        if not root_folders:
            messagebox.showinfo(
                "No Folders Open",
                "Open one or more folders in the File Browser first\n"
                "(File > Open Folder or File > Add Folder to Tree).",
                parent=self.winfo_toplevel(),
            )
            return

        # Disable button while scanning
        self._scan_btn.configure(state=tk.DISABLED)
        self._set_status("Scanning for content mirrors...")

        # Shared state between the worker thread and the UI
        self._scan_auto: list[list[str]] = []
        self._scan_candidates: list[list[str]] = []
        self._scan_error: str | None = None
        self._scan_progress = ""

        def _worker():
            def _on_progress(dirs_done: int, files_hashed: int):
                self._scan_progress = (
                    f"Scanning... {dirs_done} folder(s), "
                    f"{files_hashed} file(s) hashed"
                )

            try:
                auto, cands = self.registry.scan_content_mirrors(
                    root_folders, progress_callback=_on_progress,
                )
                self._scan_auto = auto
                self._scan_candidates = cands
            except Exception as e:
                self._scan_error = str(e)

        self._scan_thread = threading.Thread(target=_worker, daemon=True)
        self._scan_thread.start()
        self._poll_scan()

    def _poll_scan(self):
        """Check whether the background scan thread has finished."""
        if self._scan_thread is not None and self._scan_thread.is_alive():
            if self._scan_progress:
                self._set_status(self._scan_progress)
            self.after(200, self._poll_scan)
            return

        self._scan_btn.configure(state=tk.NORMAL)
        self._scan_thread = None

        if self._scan_error is not None:
            self._set_status("Scan failed.")
            messagebox.showerror(
                "Scan Error", self._scan_error,
                parent=self.winfo_toplevel(),
            )
            return

        auto = self._scan_auto
        candidates = self._scan_candidates

        # Auto-confirm groups whose folders already carry markers
        for folders in auto:
            self.registry.create_group(folders=folders)

        # Nothing found at all
        if not auto and not candidates:
            self._set_status("Scan complete: no new content mirrors found.")
            messagebox.showinfo(
                "Scan Complete",
                "No new content-mirror groups were found.",
                parent=self.winfo_toplevel(),
            )
            return

        # Show review dialog for unconfirmed candidates
        if candidates:
            dlg = ScanReviewDialog(self.winfo_toplevel(), candidates)
            self.winfo_toplevel().wait_window(dlg)
            for folders in dlg.accepted:
                self.registry.create_group(folders=folders)
            accepted_count = len(dlg.accepted)
        else:
            accepted_count = 0

        total = len(auto) + accepted_count
        if total:
            self.refresh_list()
            self._notify_change(
                f"Scan complete: {total} mirror group(s) confirmed."
            )
        else:
            self._set_status("Scan complete: no groups confirmed.")

    def _notify_change(self, msg: str):
        self._set_status(msg)
        if self.on_change:
            self.on_change()

    def _set_status(self, msg: str):
        if self.status_callback:
            self.status_callback(msg)


class ScanReviewDialog(tk.Toplevel):
    """Dialog for reviewing scan results and confirming mirror groups."""

    def __init__(self, parent, candidates: list[list[str]]):
        super().__init__(parent)
        self.title("Review Scan Results")
        self.transient(parent)
        self.grab_set()
        self.minsize(600, 420)

        self.accepted: list[list[str]] = []
        self._candidates = candidates
        self._vars: list[tk.BooleanVar] = []

        self._build_ui()
        self._center_on_parent(parent)

    def _center_on_parent(self, parent):
        self.update_idletasks()
        pw, ph = parent.winfo_width(), parent.winfo_height()
        px, py = parent.winfo_rootx(), parent.winfo_rooty()
        w, h = self.winfo_width(), self.winfo_height()
        self.geometry(f"+{px + (pw - w) // 2}+{py + (ph - h) // 2}")

    def _build_ui(self):
        frame = ttk.Frame(self, padding=10)
        frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(
            frame,
            text=(f"The scan found {len(self._candidates)} candidate "
                  f"mirror group(s).\n"
                  "Check the ones you want to confirm as mirror groups:"),
            wraplength=560,
        ).pack(anchor=tk.W, pady=(0, 8))

        # Scrollable list of candidates with checkboxes
        canvas_frame = ttk.Frame(frame)
        canvas_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        canvas = tk.Canvas(canvas_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(canvas_frame, orient=tk.VERTICAL, command=canvas.yview)
        inner = ttk.Frame(canvas)

        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scrollbar.set)

        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        for idx, folders in enumerate(self._candidates):
            var = tk.BooleanVar(value=False)
            self._vars.append(var)

            group_frame = ttk.Frame(inner)
            group_frame.pack(fill=tk.X, padx=4, pady=2)

            names = " + ".join(os.path.basename(f) or f for f in folders)
            cb = ttk.Checkbutton(group_frame, text=names, variable=var)
            cb.pack(anchor=tk.W)

            for f in folders:
                ttk.Label(group_frame, text=f"    {f}",
                          font=("TkDefaultFont", 8),
                          foreground="gray").pack(anchor=tk.W)

        # Select all / none + OK / Cancel
        btn_bar = ttk.Frame(frame)
        btn_bar.pack(fill=tk.X)
        ttk.Button(btn_bar, text="Select All", command=self._select_all).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="Select None", command=self._select_none).pack(side=tk.LEFT, padx=2)
        ttk.Button(btn_bar, text="Confirm", width=10, command=self._on_ok).pack(side=tk.RIGHT, padx=2)
        ttk.Button(btn_bar, text="Cancel", width=10, command=self.destroy).pack(side=tk.RIGHT, padx=2)

    def _select_all(self):
        for v in self._vars:
            v.set(True)

    def _select_none(self):
        for v in self._vars:
            v.set(False)

    def _on_ok(self):
        self.accepted = [
            folders for folders, var in zip(self._candidates, self._vars)
            if var.get()
        ]
        self.destroy()


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
