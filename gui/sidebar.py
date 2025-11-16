from __future__ import annotations

import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from gui.theme import LIGHT_THEME, ThemePalette
from services import list_service, userdata_service


class DeadPlayersPanel(tk.Frame):
    def __init__(self, master, *, userdata_path: str, refresh_interval: int = 5_000) -> None:
        super().__init__(master)
        self.userdata_path = userdata_path
        self.refresh_interval = refresh_interval
        self._theme: ThemePalette = LIGHT_THEME
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

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        style = ttk.Style(self)
        style.configure(
            "Treeview",
            background=theme.panel_bg,
            fieldbackground=theme.panel_bg,
            foreground=theme.fg,
            rowheight=24,
        )
        style.configure("Treeview.Heading", background=theme.bg, foreground=theme.fg)
        style.map(
            "Treeview",
            background=[("selected", theme.accent)],
            foreground=[("selected", theme.console_fg)],
        )
        self._tree.configure(style="Treeview")


class ListViewerPanel(tk.Frame):
    def __init__(self, master, *, title: str, path: str) -> None:
        super().__init__(master)
        self.title = title
        self.path = path
        self._theme: ThemePalette = LIGHT_THEME
        self._label = tk.Label(self, text=title, font=("Segoe UI", 11, "bold"))
        self._label.pack(anchor="w", padx=6, pady=(6, 0))
        self._listbox = tk.Listbox(self)
        self._listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self._button_frame = tk.Frame(self)
        self._button_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        tk.Button(self._button_frame, text="Reload", command=self.reload).pack(side=tk.LEFT)
        tk.Button(self._button_frame, text="Open File", command=self._open).pack(
            side=tk.LEFT, padx=(6, 0)
        )
        tk.Button(self._button_frame, text="Force Sync", command=self._force_sync).pack(
            side=tk.LEFT, padx=(6, 0)
        )

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

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        self._label.configure(bg=theme.panel_bg, fg=theme.fg)
        self._button_frame.configure(bg=theme.panel_bg)
        self._listbox.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            selectbackground=theme.accent,
            selectforeground=theme.console_fg,
            highlightbackground=theme.panel_bg,
        )


class SidebarPane(tk.Frame):
    def __init__(self, master, *, config: dict) -> None:
        super().__init__(master)
        self.config_data = config
        self._theme: ThemePalette = LIGHT_THEME
        self._build_ui()

    def _build_ui(self) -> None:
        self._notebook = ttk.Notebook(self, style="Sidebar.TNotebook")
        self._notebook.pack(fill=tk.BOTH, expand=True)

        self._dead_panel = DeadPlayersPanel(
            self._notebook,
            userdata_path=self.config_data.get("userdata_db_path", "userdata_db.json"),
        )
        self._notebook.add(self._dead_panel, text="Currently Dead")

        self._lists_notebook = ttk.Notebook(self._notebook, style="Sidebar.SubNotebook")
        self._whitelist_panel = ListViewerPanel(
            self._lists_notebook,
            title="Whitelist",
            path=self.config_data.get("whitelist_path", "whitelist.txt"),
        )
        self._banlist_panel = ListViewerPanel(
            self._lists_notebook,
            title="Banlist",
            path=self.config_data.get("blacklist_path", "banlist.txt"),
        )
        self._lists_notebook.add(self._whitelist_panel, text="Whitelist")
        self._lists_notebook.add(self._banlist_panel, text="Banlist")
        self._notebook.add(self._lists_notebook, text="Lists")

    def reload_paths(self, config: dict) -> None:
        self.config_data = config
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.bg)
        style = ttk.Style(self)
        style.configure("Sidebar.TNotebook", background=theme.bg, borderwidth=0)
        style.configure(
            "Sidebar.TNotebook.Tab",
            background=theme.panel_bg,
            foreground=theme.fg,
            padding=(12, 6),
        )
        style.map(
            "Sidebar.TNotebook.Tab",
            background=[("selected", theme.panel_bg)],
            foreground=[("selected", theme.fg)],
        )
        style.configure("Sidebar.SubNotebook", background=theme.bg, borderwidth=0)
        style.configure(
            "Sidebar.SubNotebook.Tab",
            background=theme.panel_bg,
            foreground=theme.fg,
            padding=(10, 4),
        )
        style.map(
            "Sidebar.SubNotebook.Tab",
            background=[("selected", theme.panel_bg)],
            foreground=[("selected", theme.fg)],
        )

        if hasattr(self, "_notebook"):
            self._notebook.configure(style="Sidebar.TNotebook")
        if hasattr(self, "_lists_notebook"):
            self._lists_notebook.configure(style="Sidebar.SubNotebook")
        if hasattr(self, "_dead_panel"):
            self._dead_panel.apply_theme(theme)
        if hasattr(self, "_whitelist_panel"):
            self._whitelist_panel.apply_theme(theme)
        if hasattr(self, "_banlist_panel"):
            self._banlist_panel.apply_theme(theme)
