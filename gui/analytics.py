from __future__ import annotations

import tkinter as tk
from tkinter import filedialog, messagebox

import matplotlib.dates as mdates
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.figure import Figure

from services.analytics_service import AnalyticsManager


class AnalyticsPane(tk.Frame):
    def __init__(self, master, manager: AnalyticsManager) -> None:
        super().__init__(master)
        self.manager = manager
        self._figure = Figure(figsize=(6, 5), dpi=100)
        self._timeline_ax = self._figure.add_subplot(211)
        self._pie_ax = self._figure.add_subplot(212)
        self._canvas = FigureCanvasTkAgg(self._figure, master=self)
        self._canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

        button = tk.Button(self, text="Export Analytics", command=self._export_dialog)
        button.pack(anchor="e", padx=8, pady=6)
        self.refresh()

    def refresh(self) -> None:
        self._draw_timeline()
        self._draw_pie()
        self._canvas.draw_idle()

    def _draw_timeline(self) -> None:
        times, counts = self.manager.timeline()
        self._timeline_ax.clear()
        self._timeline_ax.set_title("Deaths Over Time")
        if times:
            dates = mdates.epoch2num(times)
            self._timeline_ax.plot_date(dates, counts, linestyle="solid", marker="o")
            self._timeline_ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
            self._timeline_ax.set_ylabel("Deaths")
        else:
            self._timeline_ax.text(0.5, 0.5, "No data yet", ha="center", va="center")

    def _draw_pie(self) -> None:
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
