from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Callable, Dict, Tuple

from services.config_manager import ConfigManager


class ConfigEditor(tk.Toplevel):
    def __init__(self, master, config_manager: ConfigManager, *, on_reload: Callable[[Dict], None]):
        super().__init__(master)
        self.title("Edit Config")
        self.geometry("520x520")
        self.config_manager = config_manager
        self.on_reload = on_reload
        self._entries: Dict[str, Tuple[tk.Variable, type]] = {}
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

        self._add_entry(paths_tab, "Server Log Path", "death_watcher_death_path")
        self._add_entry(paths_tab, "Whitelist Path", "whitelist_path")
        self._add_entry(paths_tab, "Banlist Path", "blacklist_path")
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

        button = tk.Button(self, text="Save & Reload", command=self._save)
        button.pack(pady=8)

    def _add_entry(self, parent, label: str, key: str) -> None:
        frame = ttk.Frame(parent)
        frame.pack(fill=tk.X, pady=4, padx=4)
        ttk.Label(frame, text=label).pack(anchor="w")
        value = self.config_manager.data.get(key, "")
        var = tk.StringVar(value=str(value))
        entry = ttk.Entry(frame, textvariable=var)
        entry.pack(fill=tk.X)
        self._entries[key] = (var, type(value))

    def _add_toggle(self, parent, label: str, key: str) -> None:
        value = int(self.config_manager.data.get(key, 0))
        var = tk.IntVar(value=value)
        cb = ttk.Checkbutton(parent, text=label, variable=var)
        cb.pack(anchor="w", padx=4, pady=4)
        self._entries[key] = (var, int)

    def _save(self) -> None:
        updated = {}
        for key, (var, original_type) in self._entries.items():
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
            updated[key] = casted
        try:
            self.config_manager.update(updated)
            self.on_reload(self.config_manager.data)
            messagebox.showinfo("Config", "Configuration updated successfully.")
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc))
