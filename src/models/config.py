from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional


def _as_path(value: str | Path) -> Path:
    return value if isinstance(value, Path) else Path(value)


@dataclass
class DiscordConfig:
    token: str
    guild_id: int
    role_alive_id: int
    role_dead_id: int
    role_admin_ids: List[int]
    join_vc_id: int
    online_category_id: int
    bot_spam_channel_id: int


@dataclass
class PathsConfig:
    path_to_logs_directory: Path
    userdata_db_path: Path
    path_to_cache: Path
    banlist_path: Path
    whitelist_path: Path


@dataclass
class AppConfig:
    discord: DiscordConfig
    paths: PathsConfig
    ban_duration_days: int
    verbose_logs: bool = False

    @property
    def ban_duration(self) -> timedelta:
        return timedelta(days=self.ban_duration_days)


def load_config(raw: Dict[str, Any]) -> AppConfig:
    discord_cfg = raw.get("discord", {})
    paths_cfg = raw.get("paths", {})

    discord = DiscordConfig(
        token=discord_cfg["token"],
        guild_id=int(discord_cfg["guild_id"]),
        role_alive_id=int(discord_cfg["role_alive_id"]),
        role_dead_id=int(discord_cfg["role_dead_id"]),
        role_admin_ids=[int(r) for r in discord_cfg.get("role_admin_ids", [])],
        join_vc_id=int(discord_cfg["join_vc_id"]),
        online_category_id=int(discord_cfg["online_category_id"]),
        bot_spam_channel_id=int(discord_cfg["bot_spam_channel_id"]),
    )

    paths = PathsConfig(
        path_to_logs_directory=_as_path(paths_cfg["path_to_logs_directory"]),
        userdata_db_path=_as_path(paths_cfg["userdata_db_path"]),
        path_to_cache=_as_path(paths_cfg["path_to_cache"]),
        banlist_path=_as_path(paths_cfg["banlist_path"]),
        whitelist_path=_as_path(paths_cfg["whitelist_path"]),
    )

    return AppConfig(
        discord=discord,
        paths=paths,
        ban_duration_days=int(raw.get("ban_duration_days", 1)),
        verbose_logs=bool(raw.get("verbose_logs", False)),
    )
