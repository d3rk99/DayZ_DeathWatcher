from __future__ import annotations

import os
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Callable, Dict, Iterable

from services.config_manager import ConfigManager
from services.path_fields import PATH_FIELDS, PathField


class PathSetupDialog(tk.Toplevel):
    """Collects the critical file paths required to launch the bot."""

    def __init__(
        self,
        master,
        config_manager: ConfigManager,
        *,
        missing_keys: Iterable[str] | None = None,
        on_complete: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(master)
        self.title("Configure Required Paths")
        self.resizable(False, False)
        self.config_manager = config_manager
        self._on_complete = on_complete
        self._entries: Dict[str, tk.StringVar] = {}
        self._missing = set(missing_keys or [])

        self.transient(master)
        self.grab_set()
        self.protocol("WM_DELETE_WINDOW", self._on_cancel)

        self._build_form()

    def _build_form(self) -> None:
        container = ttk.Frame(self)
        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)

        intro = (
            "Before the bot can run we need to know where your whitelist, "
            "banlist, and other DayZ files live. Fill out the paths below "
            "and click Save to continue."
        )
        ttk.Label(container, text=intro, wraplength=420, justify=tk.LEFT).pack(
            fill=tk.X, pady=(0, 12)
        )

        form = ttk.Frame(container)
        form.pack(fill=tk.BOTH, expand=True)

        for field in PATH_FIELDS.values():
            self._add_row(form, field)

        ttk.Button(container, text="Save", command=self._save).pack(pady=(16, 0))

    def _add_row(self, parent, field: PathField) -> None:
        row = ttk.Frame(parent)
        row.pack(fill=tk.X, pady=4)

        label_text = field.label
        if field.key in self._missing:
            label_text = f"* {label_text}"
        ttk.Label(row, text=label_text).pack(anchor=tk.W)

        entry_row = ttk.Frame(row)
        entry_row.pack(fill=tk.X, expand=True)

        initial = str(self.config_manager.data.get(field.key, ""))
        var = tk.StringVar(value=initial)
        entry = ttk.Entry(entry_row, textvariable=var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._entries[field.key] = var

        ttk.Button(
            entry_row,
            text="Browse...",
            command=lambda f=field: self._browse(f),
        ).pack(side=tk.LEFT, padx=(6, 0))

        if field.description:
            ttk.Label(entry_row, text=field.description, wraplength=360, foreground="#666").pack(
                side=tk.LEFT, padx=(6, 0)
            )

    def _browse(self, field: PathField) -> None:
        current = self._entries[field.key].get()
        options = {
            "title": f"Select {field.label}",
            "initialdir": os.path.dirname(current) if current else os.getcwd(),
            "mustexist": field.must_exist,
        }
        chosen = filedialog.askopenfilename(**options)
        if chosen:
            self._entries[field.key].set(chosen)

    def _save(self) -> None:
        updated: Dict[str, str] = {}
        errors = []
        for key, var in self._entries.items():
            value = var.get().strip()
            updated[key] = value
            field = PATH_FIELDS[key]
            if field.must_exist:
                if not value:
                    errors.append(f"{field.label} is required.")
                    continue
                expanded = os.path.abspath(os.path.expanduser(value))
                if not os.path.isfile(expanded):
                    errors.append(f"Unable to find {field.label} at {value}.")
        if errors:
            messagebox.showerror("Missing information", "\n".join(errors), parent=self)
            return
        try:
            self.config_manager.update(updated)
        except Exception as exc:
            messagebox.showerror("Save failed", str(exc), parent=self)
            return
        if self._on_complete:
            self._on_complete()
        self.destroy()

    def _on_cancel(self) -> None:
        # Keep the dialog open to encourage completing setup, but allow the
        # window to be closed if necessary.
        self.grab_release()
        self.destroy()
