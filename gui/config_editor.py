from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Tuple

from services.config_manager import ConfigManager
from services.server_config import get_default_server_id, normalize_servers, server_map


class ConfigEditor(tk.Toplevel):
    def __init__(self, master, config_manager: ConfigManager, *, on_reload: Callable[[Dict], None]):
        super().__init__(master)
        self.title("Edit Config")
        self.geometry("520x520")
        self.config_manager = config_manager
        self.on_reload = on_reload
        self._entries: Dict[str, Tuple[tk.Variable, type, str]] = {}
        self._servers = normalize_servers(self.config_manager.data)
        self._server_lookup = server_map(self._servers)
        self._server_var = tk.StringVar()
        self._build_form()

    def _build_form(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        paths_tab = ttk.Frame(notebook)
        ids_tab = ttk.Frame(notebook)
        timers_tab = ttk.Frame(notebook)
        toggles_tab = ttk.Frame(notebook)
        notebook.add(paths_tab, text="Paths")
        notebook.add(ids_tab, text="IDs")
        notebook.add(timers_tab, text="Timers")
        notebook.add(toggles_tab, text="Toggles")

        server_row = ttk.Frame(paths_tab)
        server_row.pack(fill=tk.X, pady=4, padx=4)
        ttk.Label(server_row, text="Server").pack(anchor="w")
        server_names = [
            f"{server['display_name']} ({server['server_id']})" for server in self._servers
        ]
        default_id = get_default_server_id(self.config_manager.data, self._servers)
        default_idx = 0
        for idx, server in enumerate(self._servers):
            if server["server_id"] == default_id:
                default_idx = idx
                break
        self._server_var.set(default_id if self._servers else "")
        self._server_combo = ttk.Combobox(server_row, values=server_names, state="readonly")
        if server_names:
            self._server_combo.current(default_idx)
        self._server_combo.pack(fill=tk.X)
        self._server_combo.bind("<<ComboboxSelected>>", self._on_server_change)

        self._add_entry(paths_tab, "Logs Directory", "path_to_logs_directory", scope="server")
        self._add_entry(paths_tab, "Death Watcher Output", "death_watcher_death_path", scope="server")
        self._add_entry(paths_tab, "Whitelist Path", "path_to_whitelist", scope="server")
        self._add_entry(paths_tab, "Banlist Path", "path_to_bans", scope="server")
        self._add_entry(paths_tab, "Userdata DB Path", "userdata_db_path")

        self._add_entry(ids_tab, "Validate Steam Channel", "validate_steam_id_channel")
        self._add_entry(ids_tab, "Error Dump Channel", "error_dump_channel")
        self._add_entry(ids_tab, "Guild ID", "guild_id")
        self._add_entry(ids_tab, "Join VC ID", "join_vc_id")
        self._add_entry(ids_tab, "Join VC Category", "join_vc_category_id")

        self._add_entry(timers_tab, "Wait Time (seconds)", "wait_time_new_life_seconds")
        self._add_entry(timers_tab, "Season Pass Wait Time", "wait_time_new_life_seconds_season_pass")

        self._add_toggle(toggles_tab, "Watch Death Watcher", "watch_death_watcher")
        self._add_toggle(toggles_tab, "Run Death Watcher Cog", "run_death_watcher_cog")
        self._add_entry(toggles_tab, "Default Server ID", "default_server_id")
        self._add_entry(toggles_tab, "Unban Scope", "unban_scope")
        self._add_entry(toggles_tab, "Validate Whitelist Scope", "validate_whitelist_scope")

        button = tk.Button(self, text="Save & Reload", command=self._save)
        button.pack(pady=8)

    def _add_entry(self, parent, label: str, key: str, *, scope: str = "global") -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=4, padx=4)
        ttk.Label(frame, text=label).pack(anchor="w")
        if scope == "server":
            server = self._server_lookup.get(self._server_var.get(), {})
            value = server.get(key, "")
        else:
            value = self.config_manager.data.get(key, "")
        var = tk.StringVar(value=str(value))
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(fill=tk.X)
        self._entries[key] = (var, type(value), scope)

    def _add_toggle(self, parent, label: str, key: str) -> None:
        value = int(self.config_manager.data.get(key, 0))
        var = tk.IntVar(value=value)
        cb = ttk.Checkbutton(parent, text=label, variable=var)
        cb.pack(anchor="w", padx=4, pady=4)
        self._entries[key] = (var, int, "global")

    def _save(self) -> None:
        updated = {}
        server_updates: Dict[str, str] = {}
        for key, (var, original_type, scope) in self._entries.items():
            value = var.get()
            try:
                if original_type is int:
                    casted = int(value)
                elif original_type is float:
                    casted = float(value)
                else:
                    casted = str(value)
            except ValueError:
                messagebox.showerror("Invalid value", f"Unable to cast {value!r} for {key}")
                return
            if scope == "server":
                server_updates[key] = casted
            else:
                updated[key] = casted
        try:
            if server_updates:
                server_id = self._server_var.get()
                servers = normalize_servers(self.config_manager.data)
                for server in servers:
                    if server["server_id"] == server_id:
                        server.update(server_updates)
                        break
                updated["servers"] = servers
            self.config_manager.update(updated)
            self.on_reload(self.config_manager.data)
            messagebox.showinfo("Config", "Configuration updated successfully.")
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))

    def _on_server_change(self, _event=None) -> None:
        if not hasattr(self, "_server_combo"):
            return
        idx = self._server_combo.current()
        if idx < 0 or idx >= len(self._servers):
            return
        selected = self._servers[idx]["server_id"]
        self._server_var.set(selected)
        server = self._server_lookup.get(selected, {})
        for key, (var, _original_type, scope) in self._entries.items():
            if scope != "server":
                continue
            var.set(str(server.get(key, "")))
