from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox
from typing import List


class ConsolePane(tk.Frame):
    """Reusable console widget with filtering, auto-scroll, and export tools."""

    def __init__(self, master, *, title: str, description: str, **kwargs) -> None:
        super().__init__(master, **kwargs)
        self.title = title
        self.description = description
        self._log_buffer: List[str] = []
        self._auto_scroll = tk.BooleanVar(value=True)
        self._filter_var = tk.StringVar()
        self._cleared_index = 0

        self._build_ui()

    def _build_ui(self) -> None:
        title_lbl = tk.Label(self, text=self.title, font=("Segoe UI", 12, "bold"))
        title_lbl.pack(anchor="w", padx=8, pady=(8, 0))

        desc_lbl = tk.Label(self, text=self.description, wraplength=420, justify=tk.LEFT)
        desc_lbl.pack(anchor="w", padx=8, pady=(0, 6))

        toolbar = tk.Frame(self)
        toolbar.pack(fill=tk.X, padx=8, pady=(0, 4))

        self._filter_var.set("Filter output…")
        self._filter_entry = tk.Entry(toolbar, textvariable=self._filter_var)
        self._filter_entry.configure(fg="#666666")
        self._filter_entry.bind("<FocusIn>", self._clear_placeholder)
        self._filter_entry.bind("<FocusOut>", self._restore_placeholder)
        self._filter_entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._filter_var.trace_add("write", lambda *_: self._refresh_display())

        clear_btn = tk.Button(toolbar, text="Clear", command=self.clear_view)
        clear_btn.pack(side=tk.LEFT, padx=(6, 0))

        save_btn = tk.Button(toolbar, text="Save Log", command=self.save_log)
        save_btn.pack(side=tk.LEFT, padx=(6, 0))

        auto_box = tk.Checkbutton(toolbar, text="Auto-scroll", variable=self._auto_scroll)
        auto_box.pack(side=tk.LEFT, padx=(10, 0))

        text_container = tk.Frame(self)
        text_container.pack(fill=tk.BOTH, expand=True, padx=8, pady=(0, 8))

        self._text = tk.Text(
            text_container,
            wrap=tk.WORD,
            height=30,
            font=("Consolas", 10),
            state="disabled",
        )
        self._text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        scrollbar = tk.Scrollbar(text_container, command=self._text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self._text.configure(yscrollcommand=scrollbar.set)

    def append(self, message: str) -> None:
        if not message:
            return
        if not message.endswith("\n"):
            message += "\n"
        lines = message.splitlines(True)
        self._log_buffer.extend(lines)
        if self._filter_active:
            self._refresh_display()
        else:
            self._append_visible("".join(lines))

    @property
    def _filter_active(self) -> bool:
        text = self._filter_var.get().strip()
        return bool(text and text != "Filter output…")

    def _append_visible(self, text: str) -> None:
        self._text.configure(state="normal")
        self._text.insert(tk.END, text)
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
            lines = [line for line in lines if lower in line.lower()]
        self._text.configure(state="normal")
        self._text.delete("1.0", tk.END)
        if lines:
            self._text.insert(tk.END, "".join(lines))
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
            full_buffer = "".join(self._log_buffer)
            if messagebox.askyesno("Save Log", "Save the full buffer instead of the visible text?"):
                to_write = full_buffer
            else:
                to_write = visible_text
            with open(file_path, "w", encoding="utf-8") as file:
                file.write(to_write)
        except OSError as exc:
            messagebox.showerror("Save Failed", str(exc))

    def _clear_placeholder(self, _event) -> None:
        if self._filter_entry.get() == "Filter output…":
            self._filter_entry.delete(0, tk.END)
            self._filter_entry.configure(fg="black")

    def _restore_placeholder(self, _event) -> None:
        if not self._filter_entry.get():
            self._filter_entry.insert(0, "Filter output…")
            self._filter_entry.configure(fg="#666666")
