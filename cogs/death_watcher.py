import json
import threading
import traceback
from pathlib import Path
from typing import Optional

from nextcord.ext import commands

from death_watcher.new_dayz_death_watcher import DEFAULT_CONFIG, DayZDeathWatcher
from services.server_config import ensure_server_defaults, get_enabled_servers, normalize_servers


class DeathWatcher(commands.Cog):
    """Runs the legacy DayZ death watcher inside the bot process."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.threads: list[threading.Thread] = []
        self.watchers: list[DayZDeathWatcher] = []

        config = getattr(bot, "config", {})
        self.logger = getattr(bot, "death_watcher_logger", None)

        base_config = dict(DEFAULT_CONFIG)
        config_path = config.get("death_watcher_config_path")
        if config_path and Path(config_path).exists():
            try:
                base_config.update(json.loads(Path(config_path).read_text()))
            except Exception:
                pass
        cache_path = config.get("death_watcher_cache_path") or base_config.get(
            "path_to_cache", "./death_watcher/death_watcher_cache.json"
        )

        servers = ensure_server_defaults(normalize_servers(config))
        enabled_servers = get_enabled_servers(servers)

        message = "\nStarting embedded DayZ death watcher...\n"
        if self.logger:
            self.logger(message)
        else:
            print(message)

        for server in enabled_servers:
            server_id = str(server["server_id"])
            config_data = dict(base_config)
            config_data["path_to_logs_directory"] = server.get("path_to_logs_directory") or config_data.get(
                "path_to_logs_directory", ""
            )
            config_data["path_to_bans"] = server.get("death_watcher_death_path")
            config_data["path_to_cache"] = cache_path
            config_data.setdefault("death_event_name", base_config.get("death_event_name", "PLAYER_DEATH"))

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

            watcher = DayZDeathWatcher(
                config_data=config_data,
                server_id=server_id,
                logger=_make_logger(server_id),
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
