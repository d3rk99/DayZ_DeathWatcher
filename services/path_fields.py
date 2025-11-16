"""Shared metadata for the configurable file paths the bot depends on."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List


def _expand(path: str) -> str:
    import os

    return os.path.abspath(os.path.expanduser(path or ""))


@dataclass(frozen=True)
class PathField:
    key: str
    label: str
    must_exist: bool = True
    description: str | None = None


PATH_FIELDS: Dict[str, PathField] = {
    "whitelist_path": PathField(
        key="whitelist_path",
        label="Whitelist File",
        must_exist=True,
        description="Text file that tracks members allowed on the server.",
    ),
    "blacklist_path": PathField(
        key="blacklist_path",
        label="Banlist File",
        must_exist=True,
        description="DayZ ban file that the bot appends to when players die.",
    ),
    "death_watcher_death_path": PathField(
        key="death_watcher_death_path",
        label="DayZ Death Log",
        must_exist=False,
        description="Watcher log that powers the death analytics tab.",
    ),
    "userdata_db_path": PathField(
        key="userdata_db_path",
        label="Userdata Database",
        must_exist=False,
        description="JSON file that stores revive timers and admin flags.",
    ),
    "steam_ids_to_unban_path": PathField(
        key="steam_ids_to_unban_path",
        label="Steam IDs To Unban",
        must_exist=False,
        description="Helper list of accounts that should be removed from the banlist soon.",
    ),
    "death_counter_path": PathField(
        key="death_counter_path",
        label="Death Counter Data",
        must_exist=False,
        description="JSON storage for the GUI death counter widget.",
    ),
}


REQUIRED_PATH_KEYS: List[str] = ["whitelist_path", "blacklist_path"]


def find_missing_required_paths(config: Dict[str, str]) -> List[str]:
    """Return config keys whose files must exist but do not."""

    import os

    missing: List[str] = []
    for key in REQUIRED_PATH_KEYS:
        value = str(config.get(key, "")).strip()
        if not value:
            missing.append(key)
            continue
        if not os.path.isfile(_expand(value)):
            missing.append(key)
    return missing
