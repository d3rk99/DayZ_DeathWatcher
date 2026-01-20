import json
from pathlib import Path
from typing import Optional

from nextcord import Embed, Message, TextChannel
from nextcord.ext import commands, tasks

from services.alive_time_service import AliveTimeLogWatcher
from services.server_config import get_active_servers, get_default_server_id
from services import userdata_service


def _format_duration(seconds: int) -> str:
    minutes, secs = divmod(max(0, seconds), 60)
    hours, minutes = divmod(minutes, 60)
    days, hours = divmod(hours, 24)

    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    return " ".join(parts)


class AliveTimeTracker(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.config = getattr(bot, "config", {})
        self.userdata_path = self.config.get("userdata_db_path", "./userdata_db.json")
        self.leaderboard_channel_id = int(
            self.config.get("alive_leaderboard_channel_id", 0)
        )
        self.leaderboard_update_seconds = int(
            self.config.get("alive_leaderboard_update_seconds", 300)
        )
        self.cache_path = Path(self.config.get("alive_log_cache_path", "./alive_cache.json"))

        self.log_watcher: Optional[AliveTimeLogWatcher] = None
        self.leaderboard_message_id: Optional[int] = None
        self._configure_watcher()

        # default intervals are replaced during initialization
        self.poll_logs.change_interval(seconds=self.search_logs_interval)
        self.update_leaderboard.change_interval(seconds=self.leaderboard_update_seconds)

    def cog_unload(self) -> None:
        if self.poll_logs.is_running():
            self.poll_logs.cancel()
        if self.update_leaderboard.is_running():
            self.update_leaderboard.cancel()

    def _configure_watcher(self) -> None:
        death_watcher_config_path = self.config.get("death_watcher_config_path")
        logs_directory: Optional[Path] = None
        self.search_logs_interval = 5

        servers = get_active_servers(self.config)
        default_id = get_default_server_id(self.config, servers)
        for server in servers:
            if server.get("server_id") == default_id and server.get("path_to_logs_directory"):
                logs_directory = Path(str(server["path_to_logs_directory"]))
                break

        if death_watcher_config_path and Path(death_watcher_config_path).exists():
            try:
                with open(death_watcher_config_path, "r", encoding="utf-8") as file:
                    death_config = json.load(file)
                if not logs_directory:
                    logs_directory = Path(death_config.get("path_to_logs_directory", ""))
                self.search_logs_interval = float(death_config.get("search_logs_interval", 5))
            except Exception:
                logs_directory = None

        if logs_directory and logs_directory.exists():
            self.log_watcher = AliveTimeLogWatcher(
                logs_directory=logs_directory,
                cache_path=self.cache_path,
                server_id=default_id,
                logger=lambda message: print(f"[AliveTimeWatcher] {message}")
            )
        else:
            print("[AliveTimeWatcher] Logs directory not configured; disconnect tracking disabled.")

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        if not self.poll_logs.is_running():
            self.poll_logs.start()
        if not self.update_leaderboard.is_running():
            self.update_leaderboard.start()

    @tasks.loop(seconds=10)
    async def poll_logs(self) -> None:
        if not self.log_watcher:
            return

        events = await self.bot.loop.run_in_executor(None, self.log_watcher.poll_disconnects)
        for event in events:
            success = userdata_service.set_alive_time_seconds(
                self.userdata_path,
                steam_id=event.get("steam_id"),
                guid=event.get("guid"),
                alive_seconds=event.get("alive_seconds"),
            )

    @tasks.loop(seconds=300)
    async def update_leaderboard(self) -> None:
        await self.bot.wait_until_ready()

        if not self.leaderboard_channel_id:
            return

        channel = await self._get_channel()
        if not channel:
            return

        leaderboard = userdata_service.get_alive_time_leaderboard(
            self.userdata_path, top_n=10
        )
        content = self._build_message(leaderboard)

        message = await self._get_leaderboard_message(channel)
        if message:
            await message.edit(content=None, embed=content)
        else:
            sent = await channel.send(embed=content)
            self.leaderboard_message_id = sent.id

    def _build_message(self, leaderboard: list[dict]) -> Embed:
        embed = Embed(title="Alive Time Leaderboard", colour=0x5865F2)

        if not leaderboard:
            embed.description = "No disconnects have been recorded yet."
            return embed

        lines = ["**Top 10 longest runs:**", ""]
        for idx, entry in enumerate(leaderboard, start=1):
            name = entry.get("username") or entry.get("discord_id")
            duration = _format_duration(int(entry.get("alive_time_seconds", 0)))
            is_alive = int(entry.get("is_alive", 1)) == 1
            status_label = "🟢 Alive" if is_alive else "🔴 Dead"
            lines.append(f"**{idx}. {status_label} — {name} — {duration}**")

        embed.description = "\n".join(lines)
        return embed

    async def _get_channel(self) -> Optional[TextChannel]:
        channel = self.bot.get_channel(self.leaderboard_channel_id)
        if channel:
            return channel  # type: ignore[return-value]
        try:
            fetched = await self.bot.fetch_channel(self.leaderboard_channel_id)
            if isinstance(fetched, TextChannel):
                return fetched
        except Exception:
            return None
        return None

    async def _get_leaderboard_message(
        self, channel: TextChannel
    ) -> Optional[Message]:
        if self.leaderboard_message_id:
            try:
                return await channel.fetch_message(self.leaderboard_message_id)
            except Exception:
                self.leaderboard_message_id = None

        async for message in channel.history(limit=50):
            if (
                message.author.id == self.bot.user.id
                and (
                    (message.content and "Alive Time Leaderboard" in message.content)
                    or any(embed.title == "Alive Time Leaderboard" for embed in message.embeds)
                )
            ):
                self.leaderboard_message_id = message.id
                return message
        return None


def setup(bot: commands.Bot) -> None:
    bot.add_cog(AliveTimeTracker(bot))
