from __future__ import annotations

import tkinter as tk
from datetime import datetime
from tkinter import filedialog, messagebox

try:
    import matplotlib.dates as mdates
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    _MATPLOTLIB_AVAILABLE = True
except ImportError:  # pragma: no cover - runtime dependency guard
    mdates = None
    FigureCanvasTkAgg = None
    Figure = None
    _MATPLOTLIB_AVAILABLE = False

from gui.theme import LIGHT_THEME, ThemePalette
from services.analytics_service import AnalyticsManager


class AnalyticsPane(tk.Frame):
    def __init__(self, master, manager: AnalyticsManager) -> None:
        super().__init__(master)
        self.manager = manager
        self._has_matplotlib = _MATPLOTLIB_AVAILABLE
        self._theme: ThemePalette = LIGHT_THEME
        if self._has_matplotlib:
            self._figure = Figure(figsize=(6, 5), dpi=100)
            self._timeline_ax = self._figure.add_subplot(211)
            self._pie_ax = self._figure.add_subplot(212)
            self._canvas = FigureCanvasTkAgg(self._figure, master=self)
            self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
            self._warning_label = None
        else:
            self._figure = None
            self._timeline_ax = None
            self._pie_ax = None
            self._canvas = None
            warning = (
                "Matplotlib is not installed. Install it (pip install matplotlib) "
                "to enable analytics charts."
            )
            self._warning_label = tk.Label(self, text=warning, wraplength=480, justify=tk.LEFT)
            self._warning_label.pack(fill=tk.BOTH, expand=True, padx=12, pady=12)

        self._export_button = tk.Button(self, text="Export Analytics", command=self._export_dialog)
        self._export_button.pack(anchor="e", padx=8, pady=6)
        if self._has_matplotlib:
            self.refresh()
        self.apply_theme(self._theme)

    def refresh(self) -> None:
        if not self._has_matplotlib:
            return
        self._draw_timeline()
        self._draw_pie()
        self._canvas.draw_idle()

    def _draw_timeline(self) -> None:
        if not self._has_matplotlib:
            return
        times, counts = self.manager.timeline()
        self._timeline_ax.clear()
        self._timeline_ax.set_title("Deaths Over Time")
        if times:
            if hasattr(mdates, "epoch2num"):
                dates = mdates.epoch2num(times)
            else:
                dates = [mdates.date2num(datetime.fromtimestamp(ts)) for ts in times]
            self._timeline_ax.plot_date(dates, counts, linestyle="solid", marker="o")
            self._timeline_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            self._timeline_ax.set_ylabel("Deaths")
        else:
            self._timeline_ax.text(0.5, 0.5, "No data yet", ha="center", va="center")

    def _draw_pie(self) -> None:
        if not self._has_matplotlib:
            return
        breakdown = self.manager.cause_breakdown()
        self._pie_ax.clear()
        self._pie_ax.set_title("Cause of Death")
        values = [value for value in breakdown.values() if value > 0]
        labels = [label for label, value in breakdown.items() if value > 0]
        if values:
            self._pie_ax.pie(values, labels=labels, autopct="%1.0f%%")
        else:
            self._pie_ax.text(0.5, 0.5, "No events", ha="center", va="center")

    def _export_dialog(self) -> None:
        file_path = filedialog.asksaveasfilename(
            title="Export Analytics",
            defaultextension=".json",
            filetypes=[("JSON", "*.json"), ("CSV", "*.csv"), ("All", "*.*")],
        )
        if not file_path:
            return
        fmt = "csv" if file_path.lower().endswith(".csv") else "json"
        try:
            self.manager.export(file_path, fmt=fmt)
            messagebox.showinfo("Export complete", f"Analytics saved to {file_path}")
        except Exception as exc:
            messagebox.showerror("Export failed", str(exc))

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.bg)
        self._export_button.configure(
            bg=theme.button_bg,
            fg=theme.button_fg,
            activebackground=theme.accent,
        )
        if self._warning_label:
            self._warning_label.configure(bg=theme.bg, fg=theme.fg)
        if self._has_matplotlib:
            self._figure.patch.set_facecolor(theme.bg)
            self._canvas.get_tk_widget().configure(bg=theme.bg)
            for ax in (self._timeline_ax, self._pie_ax):
                ax.set_facecolor(theme.canvas_bg)
                ax.title.set_color(theme.fg)
                ax.tick_params(colors=theme.fg)
                if ax.xaxis.label:
                    ax.xaxis.label.set_color(theme.fg)
                if ax.yaxis.label:
                    ax.yaxis.label.set_color(theme.fg)
                for spine in ax.spines.values():
                    spine.set_color(theme.fg)
            self.refresh()
