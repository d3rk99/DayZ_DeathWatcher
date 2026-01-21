import asyncio
import json
import threading
import traceback
from pathlib import Path
from typing import Optional

from nextcord.ext import commands

from death_watcher.new_dayz_death_watcher import DEFAULT_CONFIG, DayZDeathWatcher
from main import handle_death_event
from services.server_config import ensure_server_defaults, get_active_servers, get_enabled_servers


class DeathWatcher(commands.Cog):
    """Runs the legacy DayZ death watcher inside the bot process."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.threads: list[threading.Thread] = []
        self.watchers: list[DayZDeathWatcher] = []

        config = getattr(bot, "config", {})
        self.logger = getattr(bot, "death_watcher_logger", None)

        base_config = dict(DEFAULT_CONFIG)
        config_path = config.get("death_watcher_config_path") or "./death_watcher/config.json"
        if config_path and Path(config_path).exists():
            try:
                base_config.update(json.loads(Path(config_path).read_text()))
            except Exception:
                pass
        cache_path = config.get("death_watcher_cache_path") or base_config.get(
            "path_to_cache", "./death_watcher/death_watcher_cache.json"
        )

        servers = ensure_server_defaults(get_active_servers(config))
        enabled_servers = get_enabled_servers(servers)
        enable_death_scanning = bool(config.get("enable_death_scanning", True))

        message = "\nStarting embedded DayZ death watcher...\n"
        if self.logger:
            self.logger(message)
        else:
            print(message)

        if not enable_death_scanning:
            return

        for server in enabled_servers:
            server_id = str(server["server_id"])
            if server.get("enable_death_scanning") is False:
                continue
            config_data = dict(base_config)
            config_data["path_to_logs_directory"] = server.get("path_to_logs_directory") or config_data.get(
                "path_to_logs_directory", ""
            )
            config_data["path_to_cache"] = cache_path
            config_data.setdefault("death_event_name", base_config.get("death_event_name", "PLAYER_DEATH"))
            config_data["search_logs_interval"] = config.get(
                "search_logs_interval", config_data.get("search_logs_interval", 1)
            )
            config_data["archive_old_ljson"] = int(config.get("archive_old_ljson", 0))
            config_data["death_exceptions"] = config.get("death_exceptions", {})

            def _make_logger(sid: str):
                def _log(message: str) -> None:
                    formatted = f"[Server {sid}] {message}"
                    if self.logger:
                        try:
                            self.logger(formatted, server_id=sid)
                        except TypeError:
                            self.logger(formatted)
                    else:
                        print(formatted)
                return _log

            def _on_death(steam64: str, alive_sec: Optional[int], log_ts: Optional[str]) -> None:
                if not steam64:
                    return
                coro = handle_death_event(
                    steam64,
                    server_id=server_id,
                    alive_sec=alive_sec,
                    log_ts=log_ts,
                )
                asyncio.run_coroutine_threadsafe(coro, self.bot.loop)

            watcher = DayZDeathWatcher(
                config_data=config_data,
                server_id=server_id,
                logger=_make_logger(server_id),
                on_death=_on_death,
            )
            self.watchers.append(watcher)
            thread = threading.Thread(target=lambda w=watcher: self._run_watcher(w), daemon=True)
            self.threads.append(thread)
            thread.start()

    def cog_unload(self) -> None:
        for watcher in self.watchers:
            watcher.stop()
        for thread in self.threads:
            if thread.is_alive():
                thread.join(timeout=5)

    def _run_watcher(self, watcher: DayZDeathWatcher) -> None:
        try:
            watcher.run_blocking()
        except Exception:
            details = traceback.format_exc()
            if self.logger:
                try:
                    self.logger("DayZ death watcher encountered an unexpected error:\n")
                    self.logger(details)
                except TypeError:
                    self.logger("DayZ death watcher encountered an unexpected error:\n")
                    self.logger(details)
            else:
                print("DayZ death watcher encountered an unexpected error:\n")
                print(details)


def setup(bot: commands.Bot) -> None:
    bot.add_cog(DeathWatcher(bot))
