from __future__ import annotations

import datetime
import threading
import time
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable

from gui.theme import LIGHT_THEME, ThemePalette
from services import bot_control_service, list_service, userdata_service
from services.leaderboard_service import fetch_playtime_leaderboard


class DeadPlayersPanel(tk.Frame):
    def __init__(
        self,
        master,
        *,
        userdata_path: str,
        wait_time_seconds: int | None = None,
        refresh_interval: int = 5_000,
    ) -> None:
        super().__init__(master)
        self.userdata_path = userdata_path
        self.refresh_interval = refresh_interval
        self._default_wait_seconds = self._normalize_wait_time(wait_time_seconds)
        self._theme: ThemePalette = LIGHT_THEME
        self._tree = self._build_tree()
        self._context_menu = self._build_menu()
        self._actions = self._build_actions()
        self._poll()

    def _build_tree(self) -> ttk.Treeview:
        columns = ("discord", "steam", "death", "status", "revive")
        tree = ttk.Treeview(self, columns=columns, show="headings", height=14)
        headings = {
            "discord": "Discord Name",
            "steam": "Steam64",
            "death": "Time Of Death",
            "status": "Alive Status",
            "revive": "Revival ETA",
        }
        for key, text in headings.items():
            tree.heading(key, text=text)
            tree.column(key, width=140 if key != "death" else 160, anchor=tk.CENTER)
        tree.pack(fill=tk.BOTH, expand=True)
        tree.bind("<Button-3>", self._show_context_menu)
        return tree

    def _build_actions(self) -> tk.Frame:
        frame = tk.Frame(self)
        frame.pack(fill=tk.X, pady=(6, 0))
        self._revive_all_button = tk.Button(
            frame,
            text="Revive Everyone",
            command=self._revive_all,
        )
        self._revive_all_button.pack(side=tk.RIGHT, padx=(0, 6))
        self._revive_button = tk.Button(
            frame,
            text="Revive Selected",
            command=self._revive_selected,
        )
        self._revive_button.pack(side=tk.RIGHT)
        return frame

    def _build_menu(self) -> tk.Menu:
        menu = tk.Menu(self, tearoff=0)
        menu.add_command(
            label="Force Revive",
            command=lambda: self._act(bot_control_service.force_revive_user),
        )
        menu.add_command(
            label="Force Mark Dead",
            command=lambda: self._act(bot_control_service.force_mark_dead),
        )
        menu.add_command(
            label="Remove from DB",
            command=lambda: self._act(bot_control_service.remove_user_from_database),
        )
        menu.add_separator()
        menu.add_command(label="View death details", command=self._view_details)
        return menu

    def _show_context_menu(self, event) -> None:
        if not self._tree.selection():
            return
        self._context_menu.tk_popup(event.x_root, event.y_root)

    def _act(self, fn: Callable[[str, str], bool]) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        discord_id = selection[0]
        try:
            success = fn(self.userdata_path, discord_id)
        except Exception as exc:
            messagebox.showerror("Action failed", str(exc))
            return
        if success:
            self.refresh()
        else:
            messagebox.showwarning("Action failed", "Unable to modify that entry.")

    def _revive_selected(self) -> None:
        self._act(bot_control_service.force_revive_user)

    def _revive_all(self) -> None:
        if not messagebox.askyesno(
            "Revive Everyone",
            "Revive all dead players and restore their Discord roles?",
        ):
            return
        try:
            revived = bot_control_service.force_revive_all_users(self.userdata_path)
        except Exception as exc:
            messagebox.showerror("Revive Everyone", str(exc))
            return
        if revived == 0:
            messagebox.showinfo(
                "Revive Everyone",
                "No dead players were found in the database.",
            )
        else:
            messagebox.showinfo(
                "Revive Everyone",
                f"Successfully revived {revived} player{'s' if revived != 1 else ''}.",
            )
        self.refresh()

    def _view_details(self) -> None:
        selection = self._tree.selection()
        if not selection:
            return
        values = self._tree.item(selection[0], "values")
        message = (
            f"Discord: {values[0]}\n"
            f"Steam64: {values[1]}\n"
            f"Time of Death: {values[2]}\n"
            f"Status: {values[3]}\n"
            f"Revival ETA: {values[4]}"
        )
        messagebox.showinfo("Death Details", message)

    def refresh(self) -> None:
        previous_selection = self._tree.selection()
        previous_focus = self._tree.focus()
        for item in self._tree.get_children():
            self._tree.delete(item)
        available_items: list[str] = []
        for entry in userdata_service.list_dead_players(
            self.userdata_path, default_wait_seconds=self._default_wait_seconds
        ):
            timestamp = entry.get("time_of_death")
            if timestamp:
                display_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))
            else:
                display_time = "Unknown"
            iid = entry["discord_id"]
            self._tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    entry["discord_name"],
                    entry["steam64"],
                    display_time,
                    entry["alive_status"],
                    entry["revival_eta"],
                ),
            )
            available_items.append(iid)

        preserved_selection = [item for item in previous_selection if item in available_items]
        if preserved_selection:
            self._tree.selection_set(preserved_selection)
            focus_target = previous_focus if previous_focus in preserved_selection else preserved_selection[0]
            self._tree.focus(focus_target)

    def _poll(self) -> None:
        if not self.winfo_exists():
            return
        self.refresh()
        self.after(self.refresh_interval, self._poll)

    def _normalize_wait_time(self, value: int | None) -> int | None:
        try:
            seconds = int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
        if seconds and seconds > 0:
            return seconds
        return None

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        style = ttk.Style(self)
        tree_style = "Sidebar.Treeview"
        heading_style = f"{tree_style}.Heading"
        style.configure(
            tree_style,
            background=theme.panel_bg,
            fieldbackground=theme.panel_bg,
            foreground=theme.fg,
            rowheight=24,
            borderwidth=0,
        )
        style.map(
            tree_style,
            background=[("selected", theme.accent)],
            foreground=[("selected", theme.console_fg)],
        )
        style.configure(heading_style, background=theme.panel_bg, foreground=theme.fg)
        self._tree.configure(style=tree_style)
        if hasattr(self, "_actions"):
            self._actions.configure(bg=theme.panel_bg)
        for button_name in ("_revive_button", "_revive_all_button"):
            if hasattr(self, button_name):
                getattr(self, button_name).configure(
                    bg=theme.button_bg,
                    fg=theme.button_fg,
                    activebackground=theme.accent,
                    activeforeground=theme.console_fg,
                    highlightbackground=theme.panel_bg,
                    borderwidth=1,
                    relief=tk.FLAT,
                )


class DeathCounterPanel(tk.Frame):
    def __init__(self, master, *, death_counter_path: str) -> None:
        super().__init__(master)
        self.death_counter_path = death_counter_path
        self._theme: ThemePalette = LIGHT_THEME
        self._count_var = tk.StringVar(value="0")
        self._status_var = tk.StringVar(value="")
        self._input_var = tk.StringVar(value="0")
        self._since_var = tk.StringVar(value="")
        self._buttons: list[tk.Button] = []
        self._build_ui()
        self.refresh()
        # Give the Discord bot a few seconds to finish connecting before
        # forcing a presence refresh so the status update doesn't race the
        # client coming online.
        self.after(5_000, lambda: self._refresh_activity(show_feedback=False))

    def _build_ui(self) -> None:
        self._title = tk.Label(self, text="Death Counter", font=("Segoe UI", 12, "bold"))
        self._title.pack(anchor="w", padx=10, pady=(10, 4))

        self._count_display = tk.Label(
            self,
            textvariable=self._count_var,
            font=("Segoe UI", 28, "bold"),
            anchor=tk.CENTER,
        )
        self._count_display.pack(fill=tk.X, padx=10)

        self._since_label = tk.Label(
            self,
            textvariable=self._since_var,
            font=("Segoe UI", 11, "normal"),
            anchor=tk.CENTER,
        )
        self._since_label.pack(fill=tk.X, padx=10)

        self._status_label = tk.Label(
            self,
            textvariable=self._status_var,
            wraplength=250,
            justify=tk.LEFT,
        )
        self._status_label.pack(fill=tk.X, padx=10, pady=(4, 8))

        action_row = tk.Frame(self)
        action_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._refresh_button = tk.Button(action_row, text="Refresh", command=self.refresh)
        self._refresh_button.pack(side=tk.LEFT)
        self._buttons.append(self._refresh_button)
        self._activity_button = tk.Button(
            action_row,
            text="Update Activity",
            command=self._refresh_activity,
        )
        self._activity_button.pack(side=tk.LEFT, padx=(6, 0))
        self._buttons.append(self._activity_button)
        self._wipe_button = tk.Button(
            action_row,
            text="Wipe Counter",
            command=self._wipe_counter,
        )
        self._wipe_button.pack(side=tk.LEFT, padx=(6, 0))
        self._buttons.append(self._wipe_button)

        adjust_label = tk.Label(self, text="Set counter to:")
        adjust_label.pack(anchor="w", padx=10)
        entry_row = tk.Frame(self)
        entry_row.pack(fill=tk.X, padx=10, pady=(2, 6))
        self._entry = tk.Entry(entry_row, textvariable=self._input_var, justify=tk.CENTER)
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._set_button = tk.Button(entry_row, text="Apply", command=self._apply_value)
        self._set_button.pack(side=tk.LEFT, padx=(6, 0))
        self._buttons.append(self._set_button)

        delta_row = tk.Frame(self)
        delta_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._minus_button = tk.Button(delta_row, text="-1", command=lambda: self._adjust(-1))
        self._minus_button.pack(side=tk.LEFT)
        self._buttons.append(self._minus_button)
        self._plus_button = tk.Button(delta_row, text="+1", command=lambda: self._adjust(1))
        self._plus_button.pack(side=tk.LEFT, padx=(6, 0))
        self._buttons.append(self._plus_button)

    def refresh(self) -> None:
        try:
            count, last_reset, synced = bot_control_service.get_death_counter(self.death_counter_path)
        except Exception as exc:
            messagebox.showerror("Death Counter", str(exc))
            return
        self._count_var.set(str(count))
        self._since_var.set(self._format_since_text(last_reset))
        status_parts: list[str] = []
        if synced:
            status_parts.append("Synced with the running bot.")
        else:
            status_parts.append("Bot offline. Showing the saved file value.")
        if self._since_var.get():
            status_parts.append(self._since_var.get())
        self._status_var.set(" ".join(status_parts))

    def _apply_value(self) -> None:
        try:
            value = int(self._input_var.get())
        except ValueError:
            messagebox.showerror("Death Counter", "Please enter a valid integer value.")
            return
        self._update_counter(lambda: bot_control_service.set_death_counter(self.death_counter_path, value))

    def _adjust(self, delta: int) -> None:
        self._update_counter(lambda: bot_control_service.adjust_death_counter(self.death_counter_path, delta))

    def _update_counter(
        self,
        updater: Callable[[], tuple[int, int, bool]],
        *,
        success_messages: tuple[str, str] | None = None,
    ) -> None:
        try:
            count, last_reset, synced = updater()
        except Exception as exc:
            messagebox.showerror("Death Counter", str(exc))
            return
        self._count_var.set(str(count))
        self._since_var.set(self._format_since_text(last_reset))
        if success_messages:
            self._status_var.set(success_messages[0] if synced else success_messages[1])
        elif synced:
            self._status_var.set("Updated live counter and bot activity.")
        else:
            self._status_var.set("Bot offline. Saved update to disk only.")

    def _refresh_activity(self, *, show_feedback: bool = True) -> None:
        try:
            bot_control_service.refresh_activity()
            if show_feedback:
                messagebox.showinfo(
                    "Bot Activity",
                    "Presence updated with the latest counter value.",
                )
            else:
                self._status_var.set("Bot activity refreshed using the saved counter value.")
        except Exception as exc:
            if show_feedback:
                messagebox.showerror("Bot Activity", str(exc))
            else:
                self._status_var.set(f"Unable to refresh bot activity: {exc}")

    def _wipe_counter(self) -> None:
        confirm = messagebox.askyesno(
            "Death Counter",
            "Wipe the counter and stamp a new wipe date?",
        )
        if not confirm:
            return
        self._update_counter(
            lambda: bot_control_service.wipe_death_counter(self.death_counter_path),
            success_messages=(
                "Counter wiped and bot activity refreshed.",
                "Bot offline. Counter wiped and saved to disk.",
            ),
        )

    def _format_since_text(self, timestamp: int) -> str:
        if not timestamp:
            return ""
        dt = datetime.datetime.fromtimestamp(timestamp)
        day = dt.day
        if 10 <= day % 100 <= 20:
            suffix = "th"
        else:
            suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        month = dt.strftime("%b")
        year_suffix = f", {dt.year}" if dt.year != datetime.datetime.now().year else ""
        return f"Since {month} {day}{suffix}{year_suffix}"

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        for widget in (self._title, self._count_display, self._status_label):
            widget.configure(bg=theme.panel_bg, fg=theme.fg)
        self._since_label.configure(bg=theme.panel_bg, fg=theme.fg)
        for button in self._buttons:
            button.configure(
                bg=theme.button_bg,
                fg=theme.button_fg,
                activebackground=theme.accent,
                activeforeground=theme.console_fg,
                highlightbackground=theme.panel_bg,
                borderwidth=1,
                relief=tk.FLAT,
            )
        if hasattr(self, "_entry"):
            self._entry.configure(
                bg=theme.console_bg,
                fg=theme.console_fg,
                insertbackground=theme.console_fg,
                highlightbackground=theme.panel_bg,
                highlightcolor=theme.panel_bg,
                relief=tk.FLAT,
            )

    def apply_live_update(self, count: int, last_reset: int) -> None:
        self._count_var.set(str(count))
        self._since_var.set(self._format_since_text(last_reset))
        self._status_var.set("Counter auto-refreshed from the latest event.")


class AdminManagerPanel(tk.Frame):
    def __init__(self, master, *, userdata_path: str) -> None:
        super().__init__(master)
        self.userdata_path = userdata_path
        self._theme: ThemePalette = LIGHT_THEME
        self._entry_var = tk.StringVar()
        self._search_var = tk.StringVar()
        self._status_var = tk.StringVar(value="")
        self._buttons: list[tk.Button] = []
        self._all_users: list[dict[str, str]] = []
        self._current_suggestions: list[dict[str, str]] = []
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self._title = tk.Label(self, text="Admins", font=("Segoe UI", 12, "bold"))
        self._title.pack(anchor="w", padx=10, pady=(10, 4))

        columns = ("username", "discord", "steam")
        self._tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        headings = {
            "username": "Discord Name",
            "discord": "Discord ID",
            "steam": "Steam64",
        }
        for key, text in headings.items():
            self._tree.heading(key, text=text)
            width = 140 if key != "steam" else 160
            self._tree.column(key, width=width, anchor=tk.CENTER)
        self._tree.pack(fill=tk.BOTH, expand=True, padx=10, pady=(0, 6))
        self._tree.bind("<<TreeviewSelect>>", self._sync_entry_from_selection)

        self._status_label = tk.Label(
            self,
            textvariable=self._status_var,
            wraplength=250,
            justify=tk.LEFT,
        )
        self._status_label.pack(fill=tk.X, padx=10, pady=(0, 8))

        button_row = tk.Frame(self)
        button_row.pack(fill=tk.X, padx=10, pady=(0, 8))
        refresh_btn = tk.Button(button_row, text="Refresh", command=self.refresh)
        refresh_btn.pack(side=tk.LEFT)
        self._buttons.append(refresh_btn)
        remove_btn = tk.Button(
            button_row,
            text="Remove Selected",
            command=self._remove_selected_admin,
        )
        remove_btn.pack(side=tk.LEFT, padx=(6, 0))
        self._buttons.append(remove_btn)

        search_frame = tk.Frame(self)
        search_frame.pack(fill=tk.X, padx=10, pady=(0, 6))
        self._search_label = tk.Label(search_frame, text="Search members:")
        self._search_label.pack(side=tk.LEFT)
        self._search_entry = tk.Entry(search_frame, textvariable=self._search_var)
        self._search_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 0))
        self._search_var.trace_add("write", lambda *_: self._update_suggestions())

        self._suggestion_list = tk.Listbox(self, height=5)
        self._suggestion_list.pack(fill=tk.BOTH, expand=False, padx=10, pady=(0, 6))
        self._suggestion_list.bind("<<ListboxSelect>>", self._apply_suggestion_to_entry)
        self._suggestion_list.bind("<Double-Button-1>", self._promote_selected_suggestion)

        entry_row = tk.Frame(self)
        entry_row.pack(fill=tk.X, padx=10, pady=(0, 10))
        self._entry_label = tk.Label(entry_row, text="Discord ID:")
        self._entry_label.pack(side=tk.LEFT)
        self._entry = tk.Entry(entry_row, textvariable=self._entry_var)
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(6, 6))
        add_btn = tk.Button(entry_row, text="Add Admin", command=self._add_admin)
        add_btn.pack(side=tk.LEFT)
        self._buttons.append(add_btn)

    def refresh(self) -> None:
        try:
            admins = userdata_service.list_admins(self.userdata_path)
            self._all_users = userdata_service.list_all_users(self.userdata_path)
        except Exception as exc:
            messagebox.showerror("Admins", str(exc))
            return
        self._tree.delete(*self._tree.get_children())
        for entry in admins:
            self._tree.insert(
                "",
                tk.END,
                iid=entry["discord_id"],
                values=(entry["username"], entry["discord_id"], entry["steam_id"]),
            )
        count = len(admins)
        if count:
            self._status_var.set(f"{count} admin{'s' if count != 1 else ''} in the database.")
        else:
            self._status_var.set("No admins found in the database.")
        self._update_suggestions()

    def _sync_entry_from_selection(self, _event=None) -> None:
        selection = self._tree.selection()
        if selection:
            self._entry_var.set(selection[0])

    def _update_suggestions(self) -> None:
        query = self._search_var.get().strip().lower()
        if not self._all_users:
            self._current_suggestions = []
            self._suggestion_list.delete(0, tk.END)
            return
        matches: list[dict[str, str]] = []
        for entry in self._all_users:
            haystacks = [
                entry.get("username", "").lower(),
                entry.get("discord_id", ""),
                entry.get("steam_id", ""),
            ]
            if not query or any(query in hay for hay in haystacks if hay):
                matches.append(entry)
            if len(matches) >= 20:
                break
        self._current_suggestions = matches
        self._suggestion_list.delete(0, tk.END)
        for entry in matches:
            username = entry.get("username") or "Unknown"
            display = f"{username} ({entry.get('discord_id', '')})"
            self._suggestion_list.insert(tk.END, display)

    def _apply_suggestion_to_entry(self, _event=None) -> None:
        selection = self._suggestion_list.curselection()
        if not selection:
            return
        entry = self._current_suggestions[selection[0]]
        discord_id = entry.get("discord_id", "")
        self._entry_var.set(discord_id)

    def _promote_selected_suggestion(self, _event=None) -> None:
        self._apply_suggestion_to_entry()
        discord_id = self._entry_var.get().strip()
        if discord_id:
            self._apply_admin_change(discord_id, True)

    def _add_admin(self) -> None:
        discord_id = self._entry_var.get().strip()
        if not discord_id:
            messagebox.showwarning("Admins", "Enter the Discord ID you want to promote.")
            return
        self._apply_admin_change(discord_id, True)

    def _remove_selected_admin(self) -> None:
        selection = self._tree.selection()
        if not selection:
            messagebox.showwarning("Admins", "Select an admin to remove.")
            return
        discord_id = selection[0]
        self._apply_admin_change(discord_id, False)

    def _apply_admin_change(self, discord_id: str, is_admin: bool) -> None:
        success, message = userdata_service.set_admin_status(
            self.userdata_path, discord_id, is_admin
        )
        if not success:
            messagebox.showwarning("Admins", message)
            return
        self._status_var.set(message)
        if not is_admin and self._entry_var.get() == discord_id:
            self._entry_var.set("")
        self.refresh()

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        for widget in (
            self._title,
            self._status_label,
            self._entry_label,
            self._search_label,
        ):
            widget.configure(bg=theme.panel_bg, fg=theme.fg)
        style = ttk.Style(self)
        tree_style = "Sidebar.Admin.Treeview"
        heading_style = f"{tree_style}.Heading"
        style.configure(
            tree_style,
            background=theme.panel_bg,
            fieldbackground=theme.panel_bg,
            foreground=theme.fg,
            rowheight=24,
            borderwidth=0,
        )
        style.map(
            tree_style,
            background=[("selected", theme.accent)],
            foreground=[("selected", theme.console_fg)],
        )
        style.configure(heading_style, background=theme.panel_bg, foreground=theme.fg)
        self._tree.configure(style=tree_style)
        for button in self._buttons:
            button.configure(
                bg=theme.button_bg,
                fg=theme.button_fg,
                activebackground=theme.accent,
                activeforeground=theme.console_fg,
                highlightbackground=theme.panel_bg,
                borderwidth=1,
                relief=tk.FLAT,
            )
        self._entry.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            insertbackground=theme.console_fg,
            highlightbackground=theme.panel_bg,
            highlightcolor=theme.panel_bg,
            relief=tk.FLAT,
        )
        self._search_entry.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            insertbackground=theme.console_fg,
            highlightbackground=theme.panel_bg,
            highlightcolor=theme.panel_bg,
            relief=tk.FLAT,
        )
        self._suggestion_list.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            selectbackground=theme.accent,
            selectforeground=theme.console_fg,
            highlightbackground=theme.panel_bg,
            relief=tk.FLAT,
        )


class ListViewerPanel(tk.Frame):
    def __init__(self, master, *, title: str, path: str) -> None:
        super().__init__(master)
        self.title = title
        self.path = path
        self._theme: ThemePalette = LIGHT_THEME
        self._label = tk.Label(self, text=title, font=("Segoe UI", 11, "bold"))
        self._label.pack(anchor="w", padx=6, pady=(6, 0))
        self._listbox = tk.Listbox(self)
        self._listbox.pack(fill=tk.BOTH, expand=True, padx=6, pady=6)

        self._button_frame = tk.Frame(self)
        self._button_frame.pack(fill=tk.X, padx=6, pady=(0, 6))
        self._buttons: list[tk.Button] = []
        self._buttons.append(
            tk.Button(self._button_frame, text="Reload", command=self.reload)
        )
        self._buttons[-1].pack(side=tk.LEFT)
        self._buttons.append(
            tk.Button(self._button_frame, text="Open File", command=self._open)
        )
        self._buttons[-1].pack(side=tk.LEFT, padx=(6, 0))
        self._buttons.append(
            tk.Button(self._button_frame, text="Force Sync", command=self._force_sync)
        )
        self._buttons[-1].pack(side=tk.LEFT, padx=(6, 0))

        self.reload()

    def reload(self) -> None:
        self._listbox.delete(0, tk.END)
        for entry in list_service.load_list(self.path):
            self._listbox.insert(tk.END, entry)

    def _open(self) -> None:
        try:
            list_service.open_in_system_editor(self.path)
        except Exception as exc:
            messagebox.showerror("Open File", str(exc))

    def _force_sync(self) -> None:
        try:
            list_service.force_sync(self.path)
            self.reload()
        except Exception as exc:
            messagebox.showerror("Force Sync", str(exc))

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        self._label.configure(bg=theme.panel_bg, fg=theme.fg)
        self._button_frame.configure(bg=theme.panel_bg)
        for btn in getattr(self, "_buttons", []):
            btn.configure(
                bg=theme.button_bg,
                fg=theme.button_fg,
                activebackground=theme.accent,
                activeforeground=theme.console_fg,
                highlightbackground=theme.panel_bg,
                borderwidth=1,
                relief=tk.FLAT,
            )
        self._listbox.configure(
            bg=theme.console_bg,
            fg=theme.console_fg,
            selectbackground=theme.accent,
            selectforeground=theme.console_fg,
            highlightbackground=theme.panel_bg,
            highlightcolor=theme.panel_bg,
            relief=tk.FLAT,
            borderwidth=1,
        )


class DangerPanel(tk.Frame):
    def __init__(self, master, *, userdata_path: str) -> None:
        super().__init__(master)
        self.userdata_path = userdata_path
        self._theme: ThemePalette = LIGHT_THEME
        self._build_ui()

    def _build_ui(self) -> None:
        self._message = tk.Label(
            self,
            text="Danger Zone",
            font=("Segoe UI", 12, "bold"),
        )
        self._message.pack(anchor="w", padx=10, pady=(10, 4))
        self._description = tk.Label(
            self,
            text="Completely wipe the userdata database. This cannot be undone.",
            wraplength=220,
            justify=tk.LEFT,
        )
        self._description.pack(fill=tk.X, padx=10)
        self._wipe_button = tk.Button(
            self,
            text="Wipe Database",
            command=self._confirm_wipe,
            bg="#b3261e",
            fg="#ffffff",
            activebackground="#ff6659",
            activeforeground="#ffffff",
            relief=tk.RAISED,
            padx=12,
            pady=6,
        )
        self._wipe_button.pack(pady=20)

    def _confirm_wipe(self) -> None:
        if not messagebox.askyesno(
            "Wipe Database",
            "This will delete ALL userdata entries and cannot be undone. Continue?",
        ):
            return
        if userdata_service.wipe_database(self.userdata_path):
            messagebox.showinfo("Database wiped", "The userdata database has been reset.")
        else:
            messagebox.showerror("Database wipe failed", "Unable to modify the userdata file.")

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        for widget in (self._message, self._description):
            widget.configure(bg=theme.panel_bg, fg=theme.fg)
        self._wipe_button.configure(highlightbackground=theme.panel_bg)


class PlaytimeLeaderboardPanel(tk.Frame):
    def __init__(self, master, *, api_url: str | None = None) -> None:
        super().__init__(master)
        self.api_url = api_url or ""
        self._theme: ThemePalette = LIGHT_THEME
        self._status_var = tk.StringVar(value="Configure the leaderboard API URL to view playtime.")
        self._me_var = tk.StringVar(value="")
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        self._header = tk.Frame(self)
        self._header.pack(fill=tk.X, padx=10, pady=(10, 4))
        self._title = tk.Label(self._header, text="Playtime Leaderboard", font=("Segoe UI", 12, "bold"))
        self._title.pack(side=tk.LEFT)
        self._refresh_btn = tk.Button(self._header, text="Refresh", command=self.refresh)
        self._refresh_btn.pack(side=tk.RIGHT)

        columns = ("rank", "player", "hours", "last_session")
        self._tree = ttk.Treeview(self, columns=columns, show="headings", height=10)
        headings = {
            "rank": "#",
            "player": "Player",
            "hours": "Hours Played",
            "last_session": "Last Session",
        }
        widths = {"rank": 40, "player": 170, "hours": 110, "last_session": 180}
        for key in columns:
            self._tree.heading(key, text=headings[key])
            self._tree.column(key, width=widths.get(key, 140), anchor=tk.CENTER if key != "player" else tk.W)
        self._tree.pack(fill=tk.BOTH, expand=True, padx=10)

        self._me_label = tk.Label(self, textvariable=self._me_var, anchor=tk.W, justify=tk.LEFT)
        self._me_label.pack(fill=tk.X, padx=10, pady=(6, 0))

        self._status_label = tk.Label(self, textvariable=self._status_var, anchor=tk.W, wraplength=320, justify=tk.LEFT)
        self._status_label.pack(fill=tk.X, padx=10, pady=(4, 10))

    def refresh(self) -> None:
        if not self.api_url:
            self._status_var.set("Set `leaderboard_api_url` in config to load data.")
            self._clear_rows()
            return
        self._set_loading(True)
        threading.Thread(target=self._load_data, daemon=True).start()

    def _load_data(self) -> None:
        try:
            leaderboard, me = fetch_playtime_leaderboard(self.api_url)
        except Exception as exc:
            self.after(0, lambda exc=exc: self._handle_error(str(exc)))
            return
        self.after(0, lambda: self._apply_data(leaderboard, me))

    def _handle_error(self, message: str) -> None:
        self._status_var.set(message)
        self._clear_rows()
        self._set_loading(False)

    def _apply_data(self, leaderboard, me) -> None:
        self._clear_rows()
        for idx, row in enumerate(leaderboard, start=1):
            player = row.get("playerName") or row.get("steam64Id") or row.get("playerGuid") or "Unknown"
            hours = self._format_hours(row.get("totalSeconds"))
            last_session = row.get("lastSessionAt") or ""
            self._tree.insert("", tk.END, values=(idx, player, hours, last_session))
        if me:
            player = me.get("playerName") or me.get("steam64Id") or me.get("playerGuid") or "you"
            hours = self._format_hours(me.get("totalSeconds"))
            self._me_var.set(f"Your playtime: {player} — {hours} hours")
        else:
            self._me_var.set("")
        self._status_var.set("Updated playtime leaderboard.")
        self._set_loading(False)

    def _format_hours(self, seconds_value) -> str:
        try:
            total_seconds = float(seconds_value)
        except (TypeError, ValueError):
            total_seconds = 0.0
        hours = int(total_seconds // 3600)
        minutes = int((total_seconds % 3600) // 60)
        return f"{hours}h {minutes:02d}m"

    def _clear_rows(self) -> None:
        for item in self._tree.get_children():
            self._tree.delete(item)

    def _set_loading(self, loading: bool) -> None:
        if hasattr(self, "_refresh_btn"):
            self._refresh_btn.configure(state=tk.DISABLED if loading else tk.NORMAL)

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        if hasattr(self, "_header"):
            self._header.configure(bg=theme.panel_bg)
        if hasattr(self, "_title"):
            self._title.configure(bg=theme.panel_bg, fg=theme.fg)
        for widget in (self._me_label, self._status_label):
            widget.configure(bg=theme.panel_bg, fg=theme.fg)
        style = ttk.Style(self)
        tree_style = "Sidebar.Leaderboard.Treeview"
        heading_style = f"{tree_style}.Heading"
        style.configure(
            tree_style,
            background=theme.panel_bg,
            fieldbackground=theme.panel_bg,
            foreground=theme.fg,
            rowheight=24,
            borderwidth=0,
        )
        style.map(
            tree_style,
            background=[("selected", theme.accent)],
            foreground=[("selected", theme.console_fg)],
        )
        style.configure(heading_style, background=theme.panel_bg, foreground=theme.fg)
        self._tree.configure(style=tree_style)
        if hasattr(self, "_refresh_btn"):
            self._refresh_btn.configure(
                bg=theme.button_bg,
                fg=theme.button_fg,
                activebackground=theme.accent,
                activeforeground=theme.console_fg,
                highlightbackground=theme.panel_bg,
            )


class SidebarPane(tk.Frame):
    def __init__(self, master, *, config: dict) -> None:
        super().__init__(master)
        self.config_data = config
        self._theme: ThemePalette = LIGHT_THEME
        self._build_ui()

    def _build_ui(self) -> None:
        self._container = tk.Frame(self, bg=self._theme.panel_bg)
        self._container.pack(fill=tk.BOTH, expand=True)

        self._notebook = ttk.Notebook(self._container, style="Sidebar.TNotebook")
        self._notebook.pack(fill=tk.BOTH, expand=True)

        self._dead_panel = DeadPlayersPanel(
            self._notebook,
            userdata_path=self.config_data.get("userdata_db_path", "userdata_db.json"),
            wait_time_seconds=self.config_data.get("wait_time_new_life_seconds"),
        )
        self._notebook.add(self._dead_panel, text="Currently Dead")

        self._counter_panel = DeathCounterPanel(
            self._notebook,
            death_counter_path=self.config_data.get("death_counter_path", "death_counter.json"),
        )
        self._notebook.add(self._counter_panel, text="Death Counter")

        self._lists_notebook = ttk.Notebook(
            self._notebook, style="Sidebar.SubNotebook.TNotebook"
        )
        self._whitelist_panel = ListViewerPanel(
            self._lists_notebook,
            title="Whitelist",
            path=self.config_data.get("whitelist_path", "whitelist.txt"),
        )
        self._banlist_panel = ListViewerPanel(
            self._lists_notebook,
            title="Banlist",
            path=self.config_data.get("blacklist_path", "banlist.txt"),
        )
        self._lists_notebook.add(self._whitelist_panel, text="Whitelist")
        self._lists_notebook.add(self._banlist_panel, text="Banlist")
        self._notebook.add(self._lists_notebook, text="Lists")

        self._admin_panel = AdminManagerPanel(
            self._notebook,
            userdata_path=self.config_data.get("userdata_db_path", "userdata_db.json"),
        )
        self._notebook.add(self._admin_panel, text="Admins")

        self._danger_panel = DangerPanel(
            self._notebook,
            userdata_path=self.config_data.get("userdata_db_path", "userdata_db.json"),
        )
        self._notebook.add(self._danger_panel, text="Danger")

        self._leaderboard_panel = PlaytimeLeaderboardPanel(
            self._notebook,
            api_url=self.config_data.get("leaderboard_api_url")
            or self.config_data.get("bot_sync_api_url"),
        )
        self._notebook.add(self._leaderboard_panel, text="Leaderboards")

    def update_death_counter(self, count: int, last_reset: int) -> None:
        if hasattr(self, "_counter_panel"):
            self._counter_panel.apply_live_update(count, last_reset)

    def reload_paths(self, config: dict) -> None:
        self.config_data = config
        for child in self.winfo_children():
            child.destroy()
        self._build_ui()
        self.apply_theme(self._theme)

    def apply_theme(self, theme: ThemePalette) -> None:
        self._theme = theme
        self.configure(bg=theme.panel_bg)
        style = ttk.Style(self)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        style.configure(
            "Sidebar.TNotebook",
            background=theme.panel_bg,
            borderwidth=0,
            tabmargins=(0, 2, 0, 0),
            padding=0,
        )
        style.configure(
            "Sidebar.TNotebook.Tab",
            background=theme.panel_bg,
            foreground=theme.fg,
            padding=(12, 6),
            borderwidth=0,
        )
        style.map(
            "Sidebar.TNotebook.Tab",
            background=[("selected", theme.bg)],
            foreground=[("selected", theme.fg)],
        )
        style.configure(
            "Sidebar.SubNotebook.TNotebook",
            background=theme.panel_bg,
            borderwidth=0,
            tabmargins=(0, 2, 0, 0),
            padding=0,
        )
        style.configure(
            "Sidebar.SubNotebook.Tab",
            background=theme.panel_bg,
            foreground=theme.fg,
            padding=(10, 4),
            borderwidth=0,
        )
        style.map(
            "Sidebar.SubNotebook.Tab",
            background=[("selected", theme.bg)],
            foreground=[("selected", theme.fg)],
        )

        if hasattr(self, "_notebook"):
            self._notebook.configure(style="Sidebar.TNotebook")
        if hasattr(self, "_container"):
            self._container.configure(bg=theme.panel_bg)
        if hasattr(self, "_lists_notebook"):
            self._lists_notebook.configure(style="Sidebar.SubNotebook.TNotebook")
        if hasattr(self, "_dead_panel"):
            self._dead_panel.apply_theme(theme)
        if hasattr(self, "_counter_panel"):
            self._counter_panel.apply_theme(theme)
        if hasattr(self, "_whitelist_panel"):
            self._whitelist_panel.apply_theme(theme)
        if hasattr(self, "_banlist_panel"):
            self._banlist_panel.apply_theme(theme)
        if hasattr(self, "_admin_panel"):
            self._admin_panel.apply_theme(theme)
        if hasattr(self, "_danger_panel"):
            self._danger_panel.apply_theme(theme)
        if hasattr(self, "_leaderboard_panel"):
            self._leaderboard_panel.apply_theme(theme)
