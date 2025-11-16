from __future__ import annotations

import queue
import threading
import tkinter as tk
import tkinter.ttk as ttk
from typing import Callable, Optional

from gui.analytics import AnalyticsPane
from gui.config_editor import ConfigEditor
from gui.console_pane import ConsolePane
from gui.path_setup import PathSetupDialog
from gui.sidebar import SidebarPane
from gui.theme import ThemePalette, get_theme
from services.analytics_service import AnalyticsManager
from services.config_manager import ConfigManager


class GuiApplication:
    def __init__(self, *, config_path: str = "config.json", on_close=None) -> None:
        self.root = tk.Tk()
        self.root.title("DayZ Death Watcher")
        self.root.geometry("1300x750")
        self.main_queue: "queue.Queue[str]" = queue.Queue()
        self.death_queue: "queue.Queue[str]" = queue.Queue()
        self.bot_thread: Optional[threading.Thread] = None
        self._shutdown_callback = on_close
        self._dark_mode = tk.BooleanVar(value=False)
        self._theme: ThemePalette = get_theme(False)
        self._ready = False
        self._ready_callbacks: list[Callable[[], None]] = []
        self._path_dialog: Optional[PathSetupDialog] = None

        self.config_manager = ConfigManager(config_path)
        self.analytics_manager = AnalyticsManager()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.config_manager.add_listener(self._on_config_update)
        self.root.after(100, self._poll_logs)
        self._ensure_initial_paths()

    # region UI
    def _build_ui(self) -> None:
        self._create_menus()
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL)
        paned.pack(fill=tk.BOTH, expand=True)

        self._left = tk.Frame(paned)
        paned.add(self._left, stretch="always")
        self._sidebar = SidebarPane(paned, config=self.config_manager.data)
        paned.add(self._sidebar, minsize=360)

        notebook = ttk.Notebook(self._left)
        notebook.pack(fill=tk.BOTH, expand=True)

        logs_tab = tk.Frame(notebook)
        notebook.add(logs_tab, text="Logs")

        logs_tab.columnconfigure(0, weight=1)
        logs_tab.columnconfigure(1, weight=1)

        self._main_console = ConsolePane(
            logs_tab,
            title="Life and Death Bot",
            description=(
                "Shows everything the Discord bot is doing, including cog startup,"
                " voice channel automation, revive checks, and any unexpected errors."
            ),
        )
        self._main_console.grid(row=0, column=0, sticky="nsew", padx=6, pady=6)

        self._death_console = ConsolePane(
            logs_tab,
            title="DayZ Death Watcher",
            description=(
                "Mirrors the watcher thread that scans DayZ server logs for new deaths "
                "and queues bans. Use this to verify which players were detected and when."
            ),
        )
        self._death_console.grid(row=0, column=1, sticky="nsew", padx=6, pady=6)

        analytics_tab = tk.Frame(notebook)
        notebook.add(analytics_tab, text="Analytics")
        self._analytics = AnalyticsPane(analytics_tab, self.analytics_manager)
        self._analytics.pack(fill=tk.BOTH, expand=True)

        self._apply_theme()

    def _create_menus(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Config", command=self._open_config_editor)
        menubar.add_cascade(label="Edit", menu=edit_menu)

        view_menu = tk.Menu(menubar, tearoff=0)
        view_menu.add_checkbutton(
            label="Dark Mode",
            variable=self._dark_mode,
            command=self._apply_theme,
        )
        menubar.add_cascade(label="View", menu=view_menu)
        self.root.config(menu=menubar)

    # endregion

    def _open_config_editor(self) -> None:
        ConfigEditor(self.root, self.config_manager, on_reload=self._on_config_update)

    def _on_config_update(self, data: dict) -> None:
        self._sidebar.reload_paths(data)
        self._ensure_initial_paths()

    def append_main_log(self, message: str) -> None:
        self.main_queue.put(message)

    def append_death_log(self, message: str) -> None:
        self.death_queue.put(message)

    def _poll_logs(self) -> None:
        self._drain_queue(self.main_queue, self._main_console)
        self._drain_queue(self.death_queue, self._death_console, analytics=True)
        self.root.after(100, self._poll_logs)

    def _drain_queue(self, q: "queue.Queue[str]", console: ConsolePane, *, analytics: bool = False) -> None:
        while not q.empty():
            message = q.get_nowait()
            console.append(message)
            if analytics and self.analytics_manager.record_line(message):
                self._analytics.refresh()

    def _apply_theme(self) -> None:
        self._theme = get_theme(self._dark_mode.get())
        palette = self._theme
        self.root.tk_setPalette(
            background=palette.bg,
            foreground=palette.fg,
            activeBackground=palette.accent,
            activeForeground=palette.fg,
            highlightColor=palette.accent,
            selectBackground=palette.accent,
            selectForeground=palette.fg,
        )
        self.root.configure(bg=palette.bg)
        if hasattr(self, "_main_console"):
            self._main_console.apply_theme(palette)
        if hasattr(self, "_death_console"):
            self._death_console.apply_theme(palette)
        if hasattr(self, "_sidebar"):
            self._sidebar.apply_theme(palette)
        if hasattr(self, "_analytics"):
            self._analytics.apply_theme(palette)

    # region setup gating
    def on_ready(self, callback: Callable[[], None]) -> None:
        if callback in self._ready_callbacks:
            return
        self._ready_callbacks.append(callback)
        if self._ready:
            self._flush_ready_callbacks()

    def _set_ready(self, ready: bool) -> None:
        self._ready = ready
        if ready:
            self._flush_ready_callbacks()

    def _flush_ready_callbacks(self) -> None:
        if not self._ready:
            return
        while self._ready_callbacks:
            callback = self._ready_callbacks.pop(0)
            try:
                callback()
            except Exception:
                pass

    def _ensure_initial_paths(self) -> None:
        from services.path_fields import find_missing_required_paths

        missing = find_missing_required_paths(self.config_manager.data)
        if missing:
            self._set_ready(False)
            self._show_path_dialog(missing)
        elif self._path_dialog is None:
            self._set_ready(True)

    def require_path_setup(self, missing_keys: Optional[list[str]] = None) -> None:
        def _prompt() -> None:
            from services.path_fields import PATH_FIELDS, find_missing_required_paths

            keys = missing_keys or find_missing_required_paths(self.config_manager.data)
            keys = [key for key in keys if key in PATH_FIELDS]
            if not keys:
                keys = list(PATH_FIELDS.keys())
            self._set_ready(False)
            self._show_path_dialog(keys)

        self.root.after(0, _prompt)

    def _show_path_dialog(self, missing_keys: list[str]) -> None:
        if self._path_dialog and self._path_dialog.winfo_exists():
            return

        def _on_complete() -> None:
            from services.path_fields import find_missing_required_paths

            self._path_dialog = None
            missing = find_missing_required_paths(self.config_manager.data)
            if missing:
                self._show_path_dialog(missing)
            else:
                self._set_ready(True)

        self._path_dialog = PathSetupDialog(
            self.root,
            self.config_manager,
            missing_keys=missing_keys,
            on_complete=_on_complete,
        )
        self._path_dialog.bind("<Destroy>", lambda _event: setattr(self, "_path_dialog", None))

    # endregion

    def _on_close(self) -> None:
        if self._shutdown_callback:
            try:
                self._shutdown_callback()
            except Exception:
                pass
        self.root.quit()
        self.root.destroy()

    def run(self) -> None:
        self.root.mainloop()
