from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from gui.theme import LIGHT_THEME, ThemePalette
from services.notification_manager import NotificationManager


class NotificationPane(tk.Frame):
    """UI for configuring restart notifications."""

    def __init__(
        self,
        master,
        config_manager,
        notifier: NotificationManager,
        **kwargs,
    ) -> None:
        super().__init__(master, **kwargs)
        self.config_manager = config_manager
        self.notifier = notifier
        self._theme: ThemePalette = LIGHT_THEME

        data = self.config_manager.data
        self._sound_var = tk.StringVar(
            value=str(data.get("restart_notification_sound_path", ""))
        )
        self._status_var = tk.StringVar(value="")

        self._build_ui()
        self.reload(data)
        self.apply_theme(self._theme)

    def _build_ui(self) -> None:
        notebook = ttk.Notebook(self)
        notebook.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        self._sound_tab = tk.Frame(notebook)
        self._trigger_tab = tk.Frame(notebook)
        notebook.add(self._sound_tab, text="Notification Sound")
        notebook.add(self._trigger_tab, text="Trigger Words")

        self._build_sound_tab()
        self._build_trigger_tab()

    def _build_sound_tab(self) -> None:
        tk.Label(
            self._sound_tab,
            text=(
                "Choose an MP3 file to play when the server restart cues are found in the logs."
            ),
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=8, pady=(10, 6))

        entry_frame = tk.Frame(self._sound_tab)
        entry_frame.pack(fill=tk.X, padx=8, pady=(0, 8))

        entry = tk.Entry(entry_frame, textvariable=self._sound_var)
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)

        tk.Button(entry_frame, text="Browse", command=self._select_sound).pack(
            side=tk.LEFT, padx=(6, 0)
        )

        tk.Button(
            self._sound_tab, text="Save Notification Sound", command=self._save_sound
        ).pack(anchor="e", padx=8, pady=(0, 8))

    def _build_trigger_tab(self) -> None:
        tk.Label(
            self._trigger_tab,
            text=(
                "Add one phrase per line. When any phrase appears in the live logs, the "
                "notification sound will play."
            ),
            wraplength=520,
            justify=tk.LEFT,
        ).pack(anchor="w", padx=8, pady=(10, 6))

        self._trigger_text = tk.Text(self._trigger_tab, height=12, width=40)
        self._trigger_text.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 6))

        tk.Button(
            self._trigger_tab, text="Save Triggers", command=self._save_triggers
        ).pack(anchor="e", padx=8, pady=(0, 8))

        self._status_lbl = tk.Label(self, textvariable=self._status_var, anchor="w")
        self._status_lbl.pack(fill=tk.X, padx=10, pady=(0, 4))

    def _select_sound(self) -> None:
        file_path = filedialog.askopenfilename(
            title="Select MP3 sound", filetypes=[("MP3 files", "*.mp3"), ("All", "*.*")]
        )
        if file_path:
            self._sound_var.set(file_path)

    def _save_sound(self) -> None:
        path = self._sound_var.get().strip()
        self.config_manager.update({"restart_notification_sound_path": path})
        self.notifier.update_config(self.config_manager.data)
        self._status_var.set("Notification sound updated.")
        messagebox.showinfo("Notification Sound", "Saved restart notification sound.")

    def _save_triggers(self) -> None:
        raw_text = self._trigger_text.get("1.0", tk.END)
        triggers = [line.strip() for line in raw_text.splitlines() if line.strip()]
        self.config_manager.update({"restart_notification_triggers": triggers})
        self.notifier.update_config(self.config_manager.data)
        self._status_var.set("Trigger list updated.")
        messagebox.showinfo("Triggers", "Saved restart notification triggers.")

    def reload(self, data: dict) -> None:
        sound_path = str(data.get("restart_notification_sound_path", "") or "")
        triggers = data.get("restart_notification_triggers", [])

        self._sound_var.set(sound_path)
        self._trigger_text.delete("1.0", tk.END)
        for trigger in triggers:
            if trigger:
                self._trigger_text.insert(tk.END, f"{trigger}\n")

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        for widget in (self, self._sound_tab, self._trigger_tab):
            widget.configure(bg=theme.panel_bg)

        for label in self._sound_tab.pack_slaves() + self._trigger_tab.pack_slaves():
            if isinstance(label, tk.Label):
                label.configure(bg=theme.panel_bg, fg=theme.fg, wraplength=520, justify=tk.LEFT)

        for entry in self._sound_tab.pack_slaves():
            if isinstance(entry, tk.Frame):
                entry.configure(bg=theme.panel_bg)
                for child in entry.pack_slaves():
                    if isinstance(child, tk.Entry):
                        child.configure(
                            bg=theme.entry_bg,
                            fg=theme.entry_fg,
                            insertbackground=theme.entry_fg,
                        )
                    elif isinstance(child, tk.Button):
                        child.configure(
                            bg=theme.button_bg,
                            fg=theme.button_fg,
                            activebackground=theme.accent,
                        )

        for button in self._trigger_tab.pack_slaves():
            if isinstance(button, tk.Button):
                button.configure(
                    bg=theme.button_bg,
                    fg=theme.button_fg,
                    activebackground=theme.accent,
                )

        self._trigger_text.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            insertbackground=theme.console_fg,
            highlightbackground=theme.panel_bg,
            selectbackground=theme.accent,
            selectforeground=theme.console_fg,
        )

        self._status_lbl.configure(bg=theme.panel_bg, fg=theme.muted)
