from __future__ import annotations

import queue
import threading
import tkinter as tk
import tkinter.ttk as ttk
from typing import Optional

from gui.analytics import AnalyticsPane
from gui.config_editor import ConfigEditor
from gui.console_pane import ConsolePane
from gui.sidebar import SidebarPane
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

        self.config_manager = ConfigManager(config_path)
        self.analytics_manager = AnalyticsManager()

        self._build_ui()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.config_manager.add_listener(self._on_config_update)
        self.root.after(100, self._poll_logs)

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

    def _create_menus(self) -> None:
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Exit", command=self._on_close)
        menubar.add_cascade(label="File", menu=file_menu)

        edit_menu = tk.Menu(menubar, tearoff=0)
        edit_menu.add_command(label="Config", command=self._open_config_editor)
        menubar.add_cascade(label="Edit", menu=edit_menu)
        self.root.config(menu=menubar)

    # endregion

    def _open_config_editor(self) -> None:
        ConfigEditor(self.root, self.config_manager, on_reload=self._on_config_update)

    def _on_config_update(self, data: dict) -> None:
        self._sidebar.reload_paths(data)

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
