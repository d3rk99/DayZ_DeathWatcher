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
        self._actions = self._build_actions()
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

    def _build_actions(self) -> tk.Frame:
        frame = tk.Frame(self)
        frame.pack(fill=tk.X, pady=(6, 0))
        self._revive_button = tk.Button(
            frame,
            text="Revive Selected",
            command=self._revive_selected,
        )
        self._revive_button.pack(side=tk.RIGHT, padx=(0, 6))
        return frame

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

    def _revive_selected(self) -> None:
        self._act(userdata_service.force_revive)

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
        tree_style = "Sidebar.Treeview"
        heading_style = f"{tree_style}.Heading"
        style.configure(
            tree_style,
            background=theme.panel_bg,
            fieldbackground=theme.panel_bg,
            foreground=theme.fg,
            rowheight=24,
            borderwidth=0,
        )
        style.map(
            tree_style,
            background=[("selected", theme.accent)],
            foreground=[("selected", theme.console_fg)],
        )
        style.configure(heading_style, background=theme.panel_bg, foreground=theme.fg)
        self._tree.configure(style=tree_style)
        if hasattr(self, "_actions"):
            self._actions.configure(bg=theme.panel_bg)
        if hasattr(self, "_revive_button"):
            self._revive_button.configure(
                bg=theme.button_bg,
                fg=theme.button_fg,
                activebackground=theme.accent,
                activeforeground=theme.console_fg,
                highlightbackground=theme.panel_bg,
                borderwidth=1,
                relief=tk.FLAT,
            )


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
        self._buttons: list[tk.Button] = []
        self._buttons.append(
            tk.Button(self._button_frame, text="Reload", command=self.reload)
        )
        self._buttons[-1].pack(side=tk.LEFT)
        self._buttons.append(
            tk.Button(self._button_frame, text="Open File", command=self._open)
        )
        self._buttons[-1].pack(side=tk.LEFT, padx=(6, 0))
        self._buttons.append(
            tk.Button(self._button_frame, text="Force Sync", command=self._force_sync)
        )
        self._buttons[-1].pack(side=tk.LEFT, padx=(6, 0))

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
        for btn in getattr(self, "_buttons", []):
            btn.configure(
                bg=theme.button_bg,
                fg=theme.button_fg,
                activebackground=theme.accent,
                activeforeground=theme.console_fg,
                highlightbackground=theme.panel_bg,
                borderwidth=1,
                relief=tk.FLAT,
            )
        self._listbox.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            selectbackground=theme.accent,
            selectforeground=theme.console_fg,
            highlightbackground=theme.panel_bg,
            highlightcolor=theme.panel_bg,
            relief=tk.FLAT,
            borderwidth=1,
        )


class DangerPanel(tk.Frame):
    def __init__(self, master, *, userdata_path: str) -> None:
        super().__init__(master)
        self.userdata_path = userdata_path
        self._theme: ThemePalette = LIGHT_THEME
        self._build_ui()

    def _build_ui(self) -> None:
        self._message = tk.Label(
            self,
            text="Danger Zone",
            font=("Segoe UI", 12, "bold"),
        )
        self._message.pack(anchor="w", padx=10, pady=(10, 4))
        self._description = tk.Label(
            self,
            text="Completely wipe the userdata database. This cannot be undone.",
            wraplength=220,
            justify=tk.LEFT,
        )
        self._description.pack(fill=tk.X, padx=10)
        self._wipe_button = tk.Button(
            self,
            text="Wipe Database",
            command=self._confirm_wipe,
            bg="#b3261e",
            fg="#ffffff",
            activebackground="#ff6659",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            padx=12,
            pady=6,
        )
        self._wipe_button.pack(pady=20)

    def _confirm_wipe(self) -> None:
        if not messagebox.askyesno(
            "Wipe Database",
            "This will delete ALL userdata entries and cannot be undone. Continue?",
        ):
            return
        if userdata_service.wipe_database(self.userdata_path):
            messagebox.showinfo("Database wiped", "The userdata database has been reset.")
        else:
            messagebox.showerror("Database wipe failed", "Unable to modify the userdata file.")

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        for widget in (self._message, self._description):
            widget.configure(bg=theme.panel_bg, fg=theme.fg)
        self._wipe_button.configure(highlightbackground=theme.panel_bg)


class SidebarPane(tk.Frame):
    def __init__(self, master, *, config: dict) -> None:
        super().__init__(master)
        self.config_data = config
        self._theme: ThemePalette = LIGHT_THEME
        self._build_ui()

    def _build_ui(self) -> None:
        self._container = tk.Frame(self, bg=self._theme.panel_bg)
        self._container.pack(fill=tk.BOTH, expand=True)

        self._notebook = ttk.Notebook(self._container, style="Sidebar.TNotebook")
        self._notebook.pack(fill=tk.BOTH, expand=True)

        self._dead_panel = DeadPlayersPanel(
            self._notebook,
            userdata_path=self.config_data.get("userdata_db_path", "userdata_db.json"),
        )
        self._notebook.add(self._dead_panel, text="Currently Dead")

        self._lists_notebook = ttk.Notebook(
            self._notebook, style="Sidebar.SubNotebook.TNotebook"
        )
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

        self._danger_panel = DangerPanel(
            self._notebook,
            userdata_path=self.config_data.get("userdata_db_path", "userdata_db.json"),
        )
        self._notebook.add(self._danger_panel, text="Danger")

    def reload_paths(self, config: dict) -> None:
        self.config_data = config
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Sidebar.TNotebook",
            background=theme.panel_bg,
            borderwidth=0,
            tabmargins=(0, 2, 0, 0),
            padding=0,
        )
        style.configure(
            "Sidebar.TNotebook.Tab",
            background=theme.panel_bg,
            foreground=theme.fg,
            padding=(12, 6),
            borderwidth=0,
        )
        style.map(
            "Sidebar.TNotebook.Tab",
            background=[("selected", theme.bg)],
            foreground=[("selected", theme.fg)],
        )
        style.configure(
            "Sidebar.SubNotebook.TNotebook",
            background=theme.panel_bg,
            borderwidth=0,
            tabmargins=(0, 2, 0, 0),
            padding=0,
        )
        style.configure(
            "Sidebar.SubNotebook.Tab",
            background=theme.panel_bg,
            foreground=theme.fg,
            padding=(10, 4),
            borderwidth=0,
        )
        style.map(
            "Sidebar.SubNotebook.Tab",
            background=[("selected", theme.bg)],
            foreground=[("selected", theme.fg)],
        )

        if hasattr(self, "_notebook"):
            self._notebook.configure(style="Sidebar.TNotebook")
        if hasattr(self, "_container"):
            self._container.configure(bg=theme.panel_bg)
        if hasattr(self, "_lists_notebook"):
            self._lists_notebook.configure(style="Sidebar.SubNotebook.TNotebook")
        if hasattr(self, "_dead_panel"):
            self._dead_panel.apply_theme(theme)
        if hasattr(self, "_whitelist_panel"):
            self._whitelist_panel.apply_theme(theme)
        if hasattr(self, "_banlist_panel"):
            self._banlist_panel.apply_theme(theme)
        if hasattr(self, "_danger_panel"):
            self._danger_panel.apply_theme(theme)
