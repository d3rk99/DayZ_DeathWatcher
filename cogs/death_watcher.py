import threading
import traceback
from typing import Optional

from nextcord.ext import commands

from death_watcher.new_dayz_death_watcher import DayZDeathWatcher


class DeathWatcher(commands.Cog):
    """Runs the legacy DayZ death watcher inside the bot process."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.thread: Optional[threading.Thread] = None
        self.watcher: Optional[DayZDeathWatcher] = None

        config = getattr(bot, "config", {})
        config_path = config.get("death_watcher_config_path")
        self.watcher = DayZDeathWatcher(config_path=config_path)

        print("\nStarting embedded DayZ death watcher...\n")
        self.thread = threading.Thread(target=self._run_watcher, daemon=True)
        self.thread.start()

    def cog_unload(self) -> None:
        if self.watcher:
            self.watcher.stop()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def _run_watcher(self) -> None:
        assert self.watcher is not None
        try:
            self.watcher.run_blocking()
        except Exception:
            print("DayZ death watcher encountered an unexpected error:\n")
            traceback.print_exc()


def setup(bot: commands.Bot) -> None:
    bot.add_cog(DeathWatcher(bot))
