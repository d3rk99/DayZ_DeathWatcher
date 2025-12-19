from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Optional

import discord
from discord.ext import commands

from src.models.config import AppConfig
from src.services.banlist import BanAndWhitelistService
from src.services.cache_store import CacheStore
from src.services.user_db import UserDatabase
from src.watchers.log_watcher import LogWatcher, LogLine


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def parse_ts(value: str) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(value)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        else:
            dt = dt.astimezone(timezone.utc)
        return dt
    except Exception:
        return None


class DeathWatcherBot(commands.Bot):
    def __init__(self, config: AppConfig):
        intents = discord.Intents.default()
        intents.members = True
        intents.guilds = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        self.config = config
        self.user_db = UserDatabase(config.paths.userdata_db_path)
        self.cache = CacheStore(config.paths.path_to_cache)
        self.bans = BanAndWhitelistService(
            config.paths.banlist_path, config.paths.whitelist_path
        )
        self.log_watcher = LogWatcher(config.paths.path_to_logs_directory, self.cache)
        self.log_task: Optional[asyncio.Task] = None
        self.reviver_task: Optional[asyncio.Task] = None
        self.logger = logging.getLogger("deathwatcher")
        self.add_command(self.validate_user_command)

    async def setup_hook(self) -> None:
        self.log_task = asyncio.create_task(self.consume_logs())
        self.reviver_task = asyncio.create_task(self.revive_loop())

    async def on_ready(self) -> None:
        self.logger.info("Logged in as %s", self.user)

    async def consume_logs(self) -> None:
        async for line in self.log_watcher.watch():
            await self.handle_log_line(line)

    async def handle_log_line(self, line: LogLine) -> None:
        if line.event != "PLAYER_DEATH":
            return

        steam64 = line.steam64
        if not steam64:
            return
        user = self.user_db.get_by_steam(steam64)
        if not user:
            self.logger.info("Unknown steamId %s died", steam64)
            return

        dead_until = utcnow() + self.config.ban_duration
        user.mark_death(line.timestamp, dead_until, line.alive_sec)
        self.user_db.save()
        self.bans.add_to_ban(steam64)
        guild = self.get_guild(self.config.discord.guild_id)
        if not guild:
            return

        member = guild.get_member(user.discordId)
        if member:
            await self._apply_death_roles(member)
            if member.voice and member.voice.channel:
                await member.move_to(None)
        await self._send_to_bot_spam(
            f"💀 Detected death for <@{user.discordId}> (steam64: {steam64})."
        )

    async def _apply_death_roles(self, member: discord.Member) -> None:
        alive_role = member.guild.get_role(self.config.discord.role_alive_id)
        dead_role = member.guild.get_role(self.config.discord.role_dead_id)
        updates = []
        if alive_role and alive_role in member.roles:
            updates.append(member.remove_roles(alive_role))
        if dead_role and dead_role not in member.roles:
            updates.append(member.add_roles(dead_role))
        if updates:
            await asyncio.gather(*updates)

    async def _apply_alive_roles(self, member: discord.Member) -> None:
        alive_role = member.guild.get_role(self.config.discord.role_alive_id)
        dead_role = member.guild.get_role(self.config.discord.role_dead_id)
        updates = []
        if dead_role and dead_role in member.roles:
            updates.append(member.remove_roles(dead_role))
        if alive_role and alive_role not in member.roles:
            updates.append(member.add_roles(alive_role))
        if updates:
            await asyncio.gather(*updates)

    async def revive_loop(self) -> None:
        while not self.is_closed():
            now = utcnow()
            for user in list(self.user_db.users.values()):
                if user.isDead and user.deadUntil:
                    dead_until = parse_ts(user.deadUntil)
                    if dead_until and dead_until <= now:
                        await self.revive_user(user)
            await asyncio.sleep(60)

    async def revive_user(self, user) -> None:
        guild = self.get_guild(self.config.discord.guild_id)
        member = guild.get_member(user.discordId) if guild else None
        user.revive()
        self.user_db.save()
        self.bans.remove_from_ban(user.steam64)
        if member:
            await self._apply_alive_roles(member)
        await self._send_to_bot_spam(
            f"✨ Revived <@{user.discordId}> (steam64: {user.steam64})."
        )

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        user = self.user_db.get_by_discord(after.id)
        if not user or not user.isDead:
            return
        alive_role = after.guild.get_role(self.config.discord.role_alive_id)
        if alive_role and alive_role in after.roles and alive_role not in before.roles:
            await self.revive_user(user)

    async def on_voice_state_update(
        self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState
    ) -> None:
        user = self.user_db.get_by_discord(member.id)
        if not user:
            return

        if after.channel and after.channel.id == self.config.discord.join_vc_id:
            await self._handle_join_channel(member, user)
            return

        if before.channel and before.channel.id == user.privateVcId:
            # user left their private VC
            if not after.channel or after.channel.id != self.config.discord.join_vc_id:
                self.bans.add_to_ban(user.steam64)
            await self._cleanup_private_channel(before.channel, user)

    async def _handle_join_channel(self, member: discord.Member, user) -> None:
        guild = member.guild
        if user.isDead and user.deadUntil:
            dead_until = parse_ts(user.deadUntil)
            if dead_until and dead_until > utcnow():
                await self._send_to_bot_spam(
                    f"⏳ <@{member.id}> is dead until {dead_until.isoformat()}. Access denied."
                )
                return

        channel = await self._get_or_create_private_channel(guild, user)
        if channel:
            await member.move_to(channel)
            self.bans.remove_from_ban(user.steam64)

    async def _get_or_create_private_channel(
        self, guild: discord.Guild, user
    ) -> Optional[discord.VoiceChannel]:
        channel = None
        if user.privateVcId:
            channel = guild.get_channel(user.privateVcId)
        if not channel:
            category = guild.get_channel(self.config.discord.online_category_id)
            channel = await guild.create_voice_channel(
                name=str(user.discordId), category=category
            )
            user.privateVcId = channel.id
            self.user_db.save()
        return channel

    async def _cleanup_private_channel(self, channel: discord.VoiceChannel, user) -> None:
        if channel.members:
            return
        try:
            await channel.delete()
            user.privateVcId = None
            self.user_db.save()
        except discord.HTTPException:
            self.logger.exception("Failed to delete private VC %s", channel.id)

    async def _send_to_bot_spam(self, message: str) -> None:
        guild = self.get_guild(self.config.discord.guild_id)
        if not guild:
            return
        channel = guild.get_channel(self.config.discord.bot_spam_channel_id)
        if channel and isinstance(channel, discord.TextChannel):
            await channel.send(message)

    def _is_admin(self, member: discord.Member) -> bool:
        return any(role.id in self.config.discord.role_admin_ids for role in member.roles)

    @commands.command(name="validate")
    async def validate_user_command(self, ctx: commands.Context, steam64: str) -> None:
        if not isinstance(ctx.author, discord.Member) or not self._is_admin(ctx.author):
            await ctx.send("You do not have permission to validate users.")
            return
        user = self.user_db.mark_validated(steam64, ctx.author.id)
        self.bans.add_to_whitelist(steam64)
        self.bans.add_to_ban(steam64)
        await ctx.send(
            f"Validated Steam64 `{steam64}` for <@{ctx.author.id}> and updated DayZ lists."
        )

    async def close(self) -> None:
        if self.log_watcher:
            self.log_watcher.stop()
        if self.log_task:
            self.log_task.cancel()
        if self.reviver_task:
            self.reviver_task.cancel()
        await super().close()


async def start_bot(config: AppConfig) -> None:
    logging.basicConfig(
        level=logging.DEBUG if config.verbose_logs else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    bot = DeathWatcherBot(config)
    await bot.start(config.discord.token)

