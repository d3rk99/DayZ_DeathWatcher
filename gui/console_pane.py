from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List, Optional, Tuple

from gui.theme import LIGHT_THEME, ThemePalette


class ConsolePane(tk.Frame):
    """Reusable console widget with filtering, auto-scroll, and export tools."""

    def __init__(self, master, *, title: str, description: str, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.title = title
        self.description = description
        self._log_buffer: List[Tuple[str, Optional[str]]] = []
        self._auto_scroll = tk.BooleanVar(value=True)
        self._filter_var = tk.StringVar()
        self._cleared_index = 0
        self._theme: ThemePalette = LIGHT_THEME

        self._build_ui()
        self.apply_theme(self._theme)

    def _build_ui(self) -> None:
        self._title_lbl = tk.Label(self, text=self.title, font=("Segoe UI", 12, "bold"))
        self._title_lbl.pack(anchor="w", padx=8, pady=(8, 0))

        self._desc_lbl = tk.Label(self, text=self.description, wraplength=420, justify=tk.LEFT)
        self._desc_lbl.pack(anchor="w", padx=8, pady=(0, 6))

        self._toolbar = tk.Frame(self)
        self._toolbar.pack(fill=tk.X, padx=8, pady=(0, 4))

        self._filter_var.set("Filter output…")
        self._filter_entry = tk.Entry(self._toolbar, textvariable=self._filter_var)
        self._filter_entry.bind("<FocusIn>", self._clear_placeholder)
        self._filter_entry.bind("<FocusOut>", self._restore_placeholder)
        self._filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._filter_var.trace_add("write", lambda *_: self._refresh_display())

        self._clear_btn = tk.Button(self._toolbar, text="Clear", command=self.clear_view)
        self._clear_btn.pack(side=tk.LEFT, padx=(6, 0))

        self._save_btn = tk.Button(self._toolbar, text="Save Log", command=self.save_log)
        self._save_btn.pack(side=tk.LEFT, padx=(6, 0))

        self._auto_box = tk.Checkbutton(
            self._toolbar, text="Auto-scroll", variable=self._auto_scroll
        )
        self._auto_box.pack(side=tk.LEFT, padx=(10, 0))

        self._text_container = tk.Frame(self)
        self._text_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._text = tk.Text(
            self._text_container,
            wrap=tk.WORD,
            height=30,
            font=("Consolas", 10),
            state="disabled",
        )
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._scrollbar = tk.Scrollbar(self._text_container, command=self._text.yview)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.configure(yscrollcommand=self._scrollbar.set)

    def append(self, message: str, *, tag: Optional[str] = None) -> None:
        if not message:
            return
        if not message.endswith("\n"):
            message += "\n"
        lines = message.splitlines(True)
        for line in lines:
            self._log_buffer.append((line, tag))
        if self._filter_active:
            self._refresh_display()
        else:
            self._append_visible([(line, tag) for line in lines])

    @property
    def _filter_active(self) -> bool:
        text = self._filter_var.get().strip()
        return bool(text and text != "Filter output…")

    def _append_visible(self, lines: List[Tuple[str, Optional[str]]]) -> None:
        self._text.configure(state="normal")
        for text, tag in lines:
            self._text.insert(tk.END, text, tag)
        if self._auto_scroll.get():
            self._text.see(tk.END)
        self._text.configure(state="disabled")

    def _refresh_display(self) -> None:
        filter_text = self._filter_var.get()
        if filter_text == "Filter output…":
            filter_text = ""
        lines = self._log_buffer[self._cleared_index :]
        if filter_text:
            lower = filter_text.lower()
            lines = [(line, tag) for line, tag in lines if lower in line.lower()]
        self._text.configure(state="normal")
        self._text.delete("1.0", tk.END)
        if lines:
            for text, tag in lines:
                self._text.insert(tk.END, text, tag)
        if self._auto_scroll.get():
            self._text.see(tk.END)
        self._text.configure(state="disabled")

    def clear_view(self) -> None:
        self._cleared_index = len(self._log_buffer)
        self._filter_var.set("")
        self._restore_placeholder(None)
        self._text.configure(state="normal")
        self._text.delete("1.0", tk.END)
        self._text.configure(state="disabled")

    def save_log(self) -> None:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".txt",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")],
            title=f"Save {self.title} log",
        )
        if not file_path:
            return
        try:
            visible_text = self._text.get("1.0", tk.END)
            full_buffer = "".join([text for text, _tag in self._log_buffer])
            if messagebox.askyesno("Save Log", "Save the full buffer instead of the visible text?"):
                to_write = full_buffer
            else:
                to_write = visible_text
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(to_write)
        except OSError as exc:
            messagebox.showerror("Save Failed", str(exc))

    def _clear_placeholder(self, _event) -> None:
        if self._is_placeholder_active():
            self._filter_entry.delete(0, tk.END)
        self._update_filter_entry_colors()

    def _restore_placeholder(self, _event) -> None:
        if not self._filter_entry.get():
            self._filter_entry.insert(0, "Filter output…")
        self._update_filter_entry_colors()

    def _is_placeholder_active(self) -> bool:
        return self._filter_entry.get() == "Filter output…"

    def _update_filter_entry_colors(self) -> None:
        fg = self._theme.placeholder if self._is_placeholder_active() else self._theme.entry_fg
        self._filter_entry.configure(
            fg=fg,
            bg=self._theme.entry_bg,
            insertbackground=self._theme.entry_fg,
            disabledforeground=self._theme.placeholder,
        )

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        for widget in (self._title_lbl, self._desc_lbl, self._toolbar, self._text_container):
            widget.configure(bg=theme.panel_bg)
        self._desc_lbl.configure(fg=theme.muted)
        for button in (self._clear_btn, self._save_btn):
            button.configure(bg=theme.button_bg, fg=theme.button_fg, activebackground=theme.accent)
        self._auto_box.configure(
            bg=theme.panel_bg,
            fg=theme.fg,
            selectcolor=theme.panel_bg,
            activebackground=theme.panel_bg,
        )
        self._text.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            insertbackground=theme.console_fg,
            selectbackground=theme.accent,
            selectforeground=theme.console_fg,
            highlightbackground=theme.panel_bg,
        )
        self._scrollbar.configure(bg=theme.panel_bg, troughcolor=theme.bg)
        self._update_filter_entry_colors()
        self._configure_tags()

    def _configure_tags(self) -> None:
        tags = {
            "death": "#ef4444",  # red
            "connect": "#a855f7",  # purple
            "disconnect": "#fb923c",  # orange
        }
        for name, color in tags.items():
            self._text.tag_configure(name, foreground=color)
