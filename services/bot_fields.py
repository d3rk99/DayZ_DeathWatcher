"""Metadata about the Discord bot configuration fields surfaced in setup."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Sequence


@dataclass(frozen=True)
class BotField:
    key: str
    label: str
    field_type: type = str
    required: bool = False
    description: str | None = None


BOT_FIELDS: Sequence[BotField] = (
    BotField(
        key="token",
        label="Bot Token",
        field_type=str,
        required=True,
        description="Paste the Discord bot token from the developer portal.",
    ),
    BotField(
        key="guild_id",
        label="Guild / Server ID",
        field_type=int,
        required=True,
        description="Right-click your Discord server with Developer Mode enabled to copy the ID.",
    ),
    BotField(
        key="admin_role_id",
        label="Admin Role ID",
        field_type=int,
        required=True,
        description="Role applied to Discord admins who can run bot commands.",
    ),
    BotField(
        key="validate_steam_id_channel",
        label="Validate Steam Channel ID",
        field_type=str,
        required=True,
        description="Channel that receives /validatesteamid requests.",
    ),
    BotField(
        key="join_vc_id",
        label="Join Voice Channel ID",
        field_type=int,
        description="Voice channel users join before the bot moves them.",
    ),
    BotField(
        key="join_vc_category_id",
        label="Voice Channel Category ID",
        field_type=int,
        description="Category that hosts the temporary player voice channels.",
    ),
    BotField(
        key="alive_role",
        label="Alive Role ID",
        field_type=int,
        required=True,
        description="Role assigned to members who have not died.",
    ),
    BotField(
        key="dead_role",
        label="Dead Role ID",
        field_type=int,
        required=True,
        description="Role assigned to members currently dead on the server.",
    ),
    BotField(
        key="can_revive_role",
        label="Can Revive Role ID",
        field_type=int,
        required=True,
        description="Role given to staff allowed to revive players.",
    ),
    BotField(
        key="season_pass_role",
        label="Season Pass Role ID",
        field_type=int,
        description="Optional role that shortens revive timers.",
    ),
    BotField(
        key="error_dump_channel_id",
        label="Error Dump Channel ID",
        field_type=str,
        description="Channel that receives unexpected errors from the bot.",
    ),
    BotField(
        key="error_dump_allow_mention",
        label="Allow Error Mentions",
        field_type=bool,
        description="Enable to ping a user or @everyone when errors occur.",
    ),
    BotField(
        key="error_dump_mention_tag",
        label="Error Mention Tag",
        field_type=str,
        description="Username, user ID, or @everyone/@here to notify on errors.",
    ),
    BotField(
        key="error_dump_rate_limit_seconds",
        label="Error Dump Rate Limit (seconds)",
        field_type=int,
        description="Minimum delay between Discord error reports.",
    ),
    BotField(
        key="error_dump_include_traceback",
        label="Include Tracebacks",
        field_type=bool,
        description="Include full traceback text in error reports.",
    ),
)


REQUIRED_BOT_KEYS: List[str] = [field.key for field in BOT_FIELDS if field.required]
