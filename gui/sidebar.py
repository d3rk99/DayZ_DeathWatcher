from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from services import list_service, userdata_service


class DeadPlayersPanel(tk.Frame):
    def __init__(self, master, *, userdata_path: str, refresh_interval: int = 5_000) -> None:
        super().__init__(master)
        self.userdata_path = userdata_path
        self.refresh_interval = refresh_interval
        self._tree = self._build_tree()
        self._context_menu = self._build_menu()
        self._poll()

    def _build_tree(self) -> ttk.Treeview:
        columns = ("discord", "steam", "death", "status", "revive")
        tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        headings = {
            "discord": "Discord Name",
            "steam": "Steam64",
            "death": "Time Of Death",
            "status": "Alive Status",
            "revive": "Revival ETA",
        }
        for key, text in headings.items():
            tree.heading(key, text=text)
            tree.column(key, width=140 if key != "death" else 160, anchor=tk.CENTER)
        tree.pack(fill=tk.BOTH, expand=True)
        tree.bind("<Button-3>", self._show_context_menu)
        return tree

    def _build_menu(self) -> tk.Menu:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(label="Force Revive", command=lambda: self._act(userdata_service.force_revive))
        menu.add_command(label="Force Mark Dead", command=lambda: self._act(userdata_service.force_mark_dead))
        menu.add_command(label="Remove from DB", command=lambda: self._act(userdata_service.remove_user))
        menu.add_separator()
        menu.add_command(label="View death details", command=self._view_details)
        return menu

    def _show_context_menu(self, event) -> None:
        if not self._tree.selection():
            return
        self._context_menu.tk_popup(event.x_root, event.y_root)

    def _act(self, fn: Callable[[str, str], bool]) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        discord_id = selection[0]
        if fn(self.userdata_path, discord_id):
            self.refresh()
        else:
            messagebox.showwarning("Action failed", "Unable to modify that entry.")

    def _view_details(self) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        values = self._tree.item(selection[0], "values")
        message = (
            f"Discord: {values[0]}\n"
            f"Steam64: {values[1]}\n"
            f"Time of Death: {values[2]}\n"
            f"Status: {values[3]}\n"
            f"Revival ETA: {values[4]}"
        )
        messagebox.showinfo("Death Details", message)

    def refresh(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)
        for entry in userdata_service.list_dead_players(self.userdata_path):
            timestamp = entry.get("time_of_death")
            if timestamp:
                display_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
            else:
                display_time = "Unknown"
            self._tree.insert(
                "",
                tk.END,
                iid=entry["discord_id"],
                values=(
                    entry["discord_name"],
                    entry["steam64"],
                    display_time,
                    entry["alive_status"],
                    entry["revival_eta"],
                ),
            )

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        self.refresh()
        self.after(self.refresh_interval, self._poll)


class ListViewerPanel(tk.Frame):
    def __init__(self, master, *, title: str, path: str) -> None:
        super().__init__(master)
        self.title = title
        self.path = path
        tk.Label(self, text=title, font=("Segoe UI", 11, "bold")).pack(anchor="w", padx=6, pady=(6, 0))
        self._listbox = tk.Listbox(self)
        self._listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        button_frame = tk.Frame(self)
        button_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(button_frame, text="Reload", command=self.reload).pack(side=tk.LEFT)
        tk.Button(button_frame, text="Open File", command=self._open).pack(side=tk.LEFT, padx=(6, 0))
        tk.Button(button_frame, text="Force Sync", command=self._force_sync).pack(side=tk.LEFT, padx=(6, 0))

        self.reload()

    def reload(self) -> None:
        self._listbox.delete(0, tk.END)
        for entry in list_service.load_list(self.path):
            self._listbox.insert(tk.END, entry)

    def _open(self) -> None:
        try:
            list_service.open_in_system_editor(self.path)
        except Exception as exc:
            messagebox.showerror("Open File", str(exc))

    def _force_sync(self) -> None:
        try:
            list_service.force_sync(self.path)
            self.reload()
        except Exception as exc:
            messagebox.showerror("Force Sync", str(exc))


class SidebarPane(tk.Frame):
    def __init__(self, master, *, config: dict) -> None:
        super().__init__(master)
        self.config_data = config
        self._build_ui()

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True)

        dead_panel = DeadPlayersPanel(
            notebook,
            userdata_path=self.config_data.get("userdata_db_path", "userdata_db.json"),
        )
        notebook.add(dead_panel, text="Currently Dead")

        lists_frame = ttk.Notebook(notebook)
        whitelist_panel = ListViewerPanel(
            lists_frame,
            title="Whitelist",
            path=self.config_data.get("whitelist_path", "whitelist.txt"),
        )
        banlist_panel = ListViewerPanel(
            lists_frame,
            title="Banlist",
            path=self.config_data.get("blacklist_path", "banlist.txt"),
        )
        lists_frame.add(whitelist_panel, text="Whitelist")
        lists_frame.add(banlist_panel, text="Banlist")
        notebook.add(lists_frame, text="Lists")

    def reload_paths(self, config: dict) -> None:
        self.config_data = config
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
