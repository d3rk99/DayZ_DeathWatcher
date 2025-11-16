diff --git a/gui/path_setup.py b/gui/path_setup.py
new file mode 100644
index 0000000000000000000000000000000000000000..7c515e1eda793740aa01405374abab8e3a6120c9
--- /dev/null
+++ b/gui/path_setup.py
@@ -0,0 +1,254 @@
+from __future__ import annotations
+
+import os
+import tkinter as tk
+from tkinter import filedialog, messagebox, ttk
+from typing import Callable, Dict, Iterable, List, Sequence
+
+from services.bot_fields import BOT_FIELDS, BotField
+from services.config_manager import ConfigManager
+from services.path_fields import PATH_FIELDS, PathField
+
+
+class PathSetupDialog(tk.Toplevel):
+    """Collects the critical file paths required to launch the bot."""
+
+    def __init__(
+        self,
+        master,
+        config_manager: ConfigManager,
+        *,
+        missing_keys: Iterable[str] | None = None,
+        field_keys: Sequence[str] | None = None,
+        button_text: str = "Save",
+        on_complete: Callable[[], None] | None = None,
+    ) -> None:
+        super().__init__(master)
+        self.title("Configure Required Paths")
+        self.resizable(False, False)
+        self.config_manager = config_manager
+        self._on_complete = on_complete
+        self._entries: Dict[str, tk.StringVar] = {}
+        self._missing = set(missing_keys or [])
+        keys = [key for key in (field_keys or []) if key in PATH_FIELDS]
+        self._field_keys: List[str] = keys or list(PATH_FIELDS.keys())
+        self._button_text = button_text or "Save"
+
+        self.transient(master)
+        self.grab_set()
+        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
+
+        self._build_form()
+
+    def _build_form(self) -> None:
+        container = ttk.Frame(self)
+        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
+
+        action = "Next" if self._button_text.lower() == "next" else "Save"
+        intro = (
+            "Before the bot can run we need to know where your DayZ data files "
+            "live. Fill out the required paths below and click "
+            f"{action} to continue."
+        )
+        ttk.Label(container, text=intro, wraplength=420, justify=tk.LEFT).pack(
+            fill=tk.X, pady=(0, 12)
+        )
+
+        form = ttk.Frame(container)
+        form.pack(fill=tk.BOTH, expand=True)
+
+        for key in self._field_keys:
+            self._add_row(form, PATH_FIELDS[key])
+
+        ttk.Button(container, text=self._button_text, command=self._save).pack(pady=(16, 0))
+
+    def _add_row(self, parent, field: PathField) -> None:
+        row = ttk.Frame(parent)
+        row.pack(fill=tk.X, pady=4)
+
+        label_text = field.label
+        if field.key in self._missing:
+            label_text = f"* {label_text}"
+        ttk.Label(row, text=label_text).pack(anchor=tk.W)
+
+        entry_row = ttk.Frame(row)
+        entry_row.pack(fill=tk.X, expand=True)
+
+        initial = str(self.config_manager.data.get(field.key, ""))
+        var = tk.StringVar(value=initial)
+        entry = ttk.Entry(entry_row, textvariable=var)
+        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
+        self._entries[field.key] = var
+
+        ttk.Button(
+            entry_row,
+            text="Browse...",
+            command=lambda f=field: self._browse(f),
+        ).pack(side=tk.LEFT, padx=(6, 0))
+
+        if field.description:
+            ttk.Label(entry_row, text=field.description, wraplength=360, foreground="#666").pack(
+                side=tk.LEFT, padx=(6, 0)
+            )
+
+    def _browse(self, field: PathField) -> None:
+        current = self._entries[field.key].get()
+        options = {
+            "title": f"Select {field.label}",
+            "initialdir": os.path.dirname(current) if current else os.getcwd(),
+            "mustexist": field.must_exist,
+        }
+        chosen = filedialog.askopenfilename(**options)
+        if chosen:
+            self._entries[field.key].set(chosen)
+
+    def _save(self) -> None:
+        updated: Dict[str, str] = {}
+        errors = []
+        for key, var in self._entries.items():
+            value = var.get().strip()
+            updated[key] = value
+            field = PATH_FIELDS[key]
+            if field.must_exist:
+                if not value:
+                    errors.append(f"{field.label} is required.")
+                    continue
+                expanded = os.path.abspath(os.path.expanduser(value))
+                if not os.path.isfile(expanded):
+                    errors.append(f"Unable to find {field.label} at {value}.")
+        if errors:
+            messagebox.showerror("Missing information", "\n".join(errors), parent=self)
+            return
+        try:
+            self.config_manager.update(updated)
+        except Exception as exc:
+            messagebox.showerror("Save failed", str(exc), parent=self)
+            return
+        if self._on_complete:
+            self._on_complete()
+        self.destroy()
+
+    def _on_cancel(self) -> None:
+        # Keep the dialog open to encourage completing setup, but allow the
+        # window to be closed if necessary.
+        self.grab_release()
+        self.destroy()
+
+
+class BotSetupDialog(tk.Toplevel):
+    """Collects the Discord IDs and bot credentials needed after path setup."""
+
+    def __init__(
+        self,
+        master,
+        config_manager: ConfigManager,
+        *,
+        on_complete: Callable[[], None] | None = None,
+    ) -> None:
+        super().__init__(master)
+        self.title("Discord Bot Setup")
+        self.resizable(False, False)
+        self.config_manager = config_manager
+        self._on_complete = on_complete
+        self._entries: Dict[str, tk.Variable] = {}
+
+        self.transient(master)
+        self.grab_set()
+        self.protocol("WM_DELETE_WINDOW", self._on_cancel)
+
+        self._build_form()
+
+    def _build_form(self) -> None:
+        container = ttk.Frame(self)
+        container.pack(fill=tk.BOTH, expand=True, padx=16, pady=16)
+
+        intro = (
+            "Almost done! Provide the Discord bot token plus the IDs for your guild, roles, "
+            "and channels. You can copy these from Discord with Developer Mode enabled."
+        )
+        ttk.Label(container, text=intro, wraplength=460, justify=tk.LEFT).pack(
+            fill=tk.X, pady=(0, 12)
+        )
+
+        form = ttk.Frame(container)
+        form.pack(fill=tk.BOTH, expand=True)
+
+        for field in BOT_FIELDS:
+            self._add_field(form, field)
+
+        ttk.Button(container, text="Finish", command=self._save).pack(pady=(16, 0))
+
+    def _add_field(self, parent, field: BotField) -> None:
+        row = ttk.Frame(parent)
+        row.pack(fill=tk.X, pady=4)
+
+        label_text = field.label
+        if field.required:
+            label_text = f"* {label_text}"
+        ttk.Label(row, text=label_text).pack(anchor=tk.W)
+
+        if field.field_type is bool:
+            value = bool(self.config_manager.data.get(field.key, False))
+            var = tk.BooleanVar(value=value)
+            ttk.Checkbutton(row, text=field.description or "Enabled", variable=var).pack(
+                anchor=tk.W, pady=2
+            )
+        else:
+            entry_row = ttk.Frame(row)
+            entry_row.pack(fill=tk.X, expand=True)
+            stored = self.config_manager.data.get(field.key, "")
+            if field.field_type is int:
+                initial = "" if not stored else str(stored)
+            else:
+                initial = str(stored)
+            var = tk.StringVar(value=initial)
+            entry = ttk.Entry(entry_row, textvariable=var, width=48)
+            entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
+            if field.description:
+                ttk.Label(entry_row, text=field.description, wraplength=360, foreground="#666").pack(
+                    side=tk.LEFT, padx=(6, 0)
+                )
+        self._entries[field.key] = var
+
+    def _save(self) -> None:
+        updated: Dict[str, object] = {}
+        errors = []
+        for field in BOT_FIELDS:
+            var = self._entries[field.key]
+            if field.field_type is bool:
+                updated[field.key] = 1 if bool(var.get()) else 0
+                continue
+
+            value = str(var.get()).strip()
+            if not value:
+                if field.required:
+                    errors.append(f"{field.label} is required.")
+                else:
+                    updated[field.key] = "" if field.field_type is str else 0
+                continue
+
+            if field.field_type is int:
+                try:
+                    updated[field.key] = int(value)
+                except ValueError:
+                    errors.append(f"{field.label} must be a number.")
+            else:
+                updated[field.key] = value
+
+        if errors:
+            messagebox.showerror("Missing information", "\n".join(errors), parent=self)
+            return
+
+        try:
+            self.config_manager.update(updated)
+        except Exception as exc:
+            messagebox.showerror("Save failed", str(exc), parent=self)
+            return
+
+        if self._on_complete:
+            self._on_complete()
+        self.destroy()
+
+    def _on_cancel(self) -> None:
+        self.grab_release()
+        self.destroy()
