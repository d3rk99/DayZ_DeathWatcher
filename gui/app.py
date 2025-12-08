from __future__ import annotations

import queue
import re
import threading
import tkinter as tk
import tkinter.ttk as ttk
from typing import Callable, Optional

from gui.analytics import AnalyticsPane
from gui.config_editor import ConfigEditor
from gui.console_pane import ConsolePane
from gui.notification_pane import NotificationPane
from gui.path_setup import BotSetupDialog, PathSetupDialog
from gui.sidebar import SidebarPane
from gui.theme import ThemePalette, get_theme
from services.analytics_service import AnalyticsManager
from services.config_manager import ConfigManager
from services.notification_manager import NotificationManager


class GuiApplication:
    """Tkinter front-end that visualizes bot output and server analytics."""

    def __init__(self, *, config_path: str = "config.json", on_close=None) -> None:
        self.root = tk.Tk()
        self.root.title("DayZ Death Watcher")
        self.root.geometry("1300x750")
        self.main_queue: queue.Queue[str] = queue.Queue()
        self.death_queue: queue.Queue[str | tuple[str, str]] = queue.Queue()
        self.counter_queue: queue.Queue[tuple[int, int]] = queue.Queue()
        self.bot_thread: Optional[threading.Thread] = None
        self._shutdown_callback = on_close
        self._dark_mode = tk.BooleanVar(value=False)
        self._theme: ThemePalette = get_theme(False)
        self._ready = False
        self._ready_callbacks: list[Callable[[], None]] = []
        self._path_dialog: Optional[PathSetupDialog] = None
        self._bot_dialog: Optional[BotSetupDialog] = None

        self.config_manager = ConfigManager(config_path)
        self._needs_full_setup = self.config_manager.needs_initial_setup
        self.analytics_manager = AnalyticsManager()
        self.notification_manager = NotificationManager(
            self.config_manager.data, on_status=self.append_main_log
        )

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
        logs_tab.columnconfigure(0, weight=1)
        logs_tab.columnconfigure(1, weight=1)
        logs_tab.rowconfigure(0, weight=1)
        notebook.add(logs_tab, text="Logs")

        self._main_console = ConsolePane(
            logs_tab,
            title="Life and Death Bot",
            description=(
                "Stream of Discord bot activity including command output "
                "and moderation events."
            ),
        )
        self._main_console.grid(row=0, column=0, sticky="nsew", padx=(10, 5), pady=10)

        self._death_console = ConsolePane(
            logs_tab,
            title="Death Watcher",
            description=(
                "Watcher log that tracks deaths from your DayZ server for "
                "revival timers and analytics."
            ),
        )
        self._death_console.grid(row=0, column=1, sticky="nsew", padx=(5, 10), pady=10)

        analytics_tab = tk.Frame(notebook)
        notebook.add(analytics_tab, text="Analytics")
        self._analytics = AnalyticsPane(analytics_tab, self.analytics_manager)
        self._analytics.pack(fill=tk.BOTH, expand=True, padx=8, pady=8)

        notifications_tab = NotificationPane(
            notebook, self.config_manager, self.notification_manager
        )
        notebook.add(notifications_tab, text="Notifications")
        self._notifications = notifications_tab

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
        if hasattr(self, "_notifications"):
            self._notifications.reload(data)
        self.notification_manager.update_config(data)
        self._ensure_initial_paths()

    def append_main_log(self, message: str) -> None:
        self.main_queue.put(message)

    def append_death_log(self, message: str) -> None:
        formatted, tag = self._format_death_log(message)
        if not formatted:
            return
        self.death_queue.put((formatted, message, tag))

    def handle_death_counter_update(self, count: int, last_reset: int) -> None:
        self.counter_queue.put((count, last_reset))

    def _poll_logs(self) -> None:
        self._drain_queue(self.main_queue, self._main_console)
        self._drain_queue(self.death_queue, self._death_console, analytics=True)
        self._process_counter_updates()
        self.root.after(100, self._poll_logs)

    def _drain_queue(
        self,
        q: "queue.Queue[str | tuple[str, ...]]",
        console: ConsolePane,
        *,
        analytics: bool = False,
    ) -> None:
        while not q.empty():
            payload = q.get_nowait()
            if isinstance(payload, tuple):
                if len(payload) == 3:
                    message, analytics_line, tag = payload
                else:
                    message, analytics_line = payload
                    tag = None
            else:
                message = payload
                analytics_line = payload if analytics else None
                tag = None
            raw_line = analytics_line or message
            console.append(message, tag=tag)
            if analytics and analytics_line and self.analytics_manager.record_line(analytics_line):
                self._analytics.refresh()
            self.notification_manager.handle_log_line(raw_line)

    def _process_counter_updates(self) -> None:
        while not self.counter_queue.empty():
            count, last_reset = self.counter_queue.get_nowait()
            if hasattr(self, "_sidebar"):
                self._sidebar.update_death_counter(count, last_reset)

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
        if hasattr(self, "_notifications"):
            self._notifications.apply_theme(palette)

    def _format_death_log(self, message: str) -> tuple[Optional[str], Optional[str]]:
        if not message:
            return None, None
        line = message.strip()
        lowered = line.lower()
        if lowered.startswith("[session]"):
            tag = "connect" if " connected " in lowered else "disconnect" if " disconnected " in lowered else None
            return line, tag
        if "(id=" in line:
            if any(token in lowered for token in ("connected", "has joined", "logged in")):
                summary = self._format_session_line(line, "connected")
                return summary, "connect"
            if any(token in lowered for token in ("disconnected", "has been disconnected", "logged off", "has left")):
                summary = self._format_session_line(line, "disconnected")
                return summary, "disconnect"
        cues = (
            "killed",
            "committed suicide",
            "bled out",
            "died.",
            "death",
            "(dead)",
            "murdered",
            "was brutally murdered by that psycho timmy",
        )
        if not any(cue in lowered for cue in cues):
            return None, None
        if "|" not in line or "(id=" not in line:
            return f"[{line}]", "death"
        timestamp_part, remainder = line.split("|", 1)
        timestamp_part = timestamp_part.strip()
        remainder = remainder.strip()
        player = remainder.split("(id=", 1)[0].strip()
        after_id = remainder.split(")", 1)
        cause_fragment = after_id[1].strip() if len(after_id) > 1 else ""
        cause_fragment = cause_fragment.split("(id=", 1)[0].strip()
        cause_fragment = cause_fragment.strip("- ")
        date_part = ""
        time_part = ""
        timestamp_bits = timestamp_part.split()
        if len(timestamp_bits) >= 2:
            date_part, time_part = timestamp_bits[0], timestamp_bits[1]
        elif timestamp_bits:
            text = timestamp_bits[0]
            if ":" in text:
                time_part = text
            else:
                date_part = text
        parts = [value for value in (date_part, player, cause_fragment, time_part) if value]
        if not parts:
            return None, None
        return "[" + " - ".join(parts) + "]", "death"

    def _format_session_line(self, line: str, verb: str) -> Optional[str]:
        match = re.search(r'Player "(?P<name>[^"]+)".*\(id=(?P<guid>[^\)]+)\)', line)
        if not match:
            return None
        player = match.group("name").strip()
        guid = match.group("guid").strip()
        timestamp_part = line.split("|", 1)[0].strip()
        return f"[{timestamp_part} - {player} ({guid}) {verb}]"

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
                # Surface errors elsewhere in the UI to avoid a tight loop here.
                pass

    def _ensure_initial_paths(self) -> None:
        from services.path_fields import find_missing_required_paths

        missing = find_missing_required_paths(self.config_manager.data)
        if missing:
            self._set_ready(False)
            self._show_path_dialog(missing, require_followup=self._needs_full_setup)
        elif self._path_dialog is None and self._bot_dialog is None:
            if self._needs_full_setup:
                self._show_bot_setup_dialog()
            else:
                self._set_ready(True)

    def require_path_setup(self, missing_keys: Optional[list[str]] = None) -> None:
        def _prompt() -> None:
            from services.path_fields import PATH_FIELDS, find_missing_required_paths

            keys = missing_keys or find_missing_required_paths(self.config_manager.data)
            keys = [key for key in keys if key in PATH_FIELDS]
            if not keys:
                keys = list(PATH_FIELDS.keys())
            self._set_ready(False)
            self._show_path_dialog(keys, require_followup=False)

        self.root.after(0, _prompt)

    def _show_path_dialog(self, missing_keys: list[str], *, require_followup: bool = False) -> None:
        if self._path_dialog and self._path_dialog.winfo_exists():
            return

        def _on_complete() -> None:
            from services.path_fields import find_missing_required_paths

            self._path_dialog = None
            missing = find_missing_required_paths(self.config_manager.data)
            if missing:
                self._show_path_dialog(missing, require_followup=require_followup)
            else:
                if require_followup:
                    self._show_bot_setup_dialog()
                else:
                    self._set_ready(True)

        self._path_dialog = PathSetupDialog(
            self.root,
            self.config_manager,
            missing_keys=missing_keys,
            button_text="Next" if require_followup else "Save",
            on_complete=_on_complete,
        )
        self._path_dialog.bind("<Destroy>", lambda _event: setattr(self, "_path_dialog", None))

    def _show_bot_setup_dialog(self) -> None:
        if self._bot_dialog and self._bot_dialog.winfo_exists():
            return

        def _on_complete() -> None:
            self._bot_dialog = None
            self._needs_full_setup = False
            self._set_ready(True)

        self._bot_dialog = BotSetupDialog(
            self.root,
            self.config_manager,
            on_complete=_on_complete,
        )
        self._bot_dialog.bind(
            "<Destroy>",
            lambda _event: self._on_bot_dialog_closed(),
        )

    def _on_bot_dialog_closed(self) -> None:
        self._bot_dialog = None
        if self._needs_full_setup:
            self.root.after(0, self._show_bot_setup_dialog)

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
