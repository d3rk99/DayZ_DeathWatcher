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
    scope: str = "global"
    kind: str = "file"


PATH_FIELDS: Dict[str, PathField] = {
    "path_to_whitelist": PathField(
        key="path_to_whitelist",
        label="Whitelist File",
        must_exist=True,
        description="Text file that tracks members allowed on the server.",
        scope="server",
    ),
    "path_to_bans": PathField(
        key="path_to_bans",
        label="Banlist File",
        must_exist=True,
        description="DayZ ban file that the bot appends to when players die.",
        scope="server",
    ),
    "path_to_logs_directory": PathField(
        key="path_to_logs_directory",
        label="Logs Directory",
        must_exist=False,
        description="DetailedLogs folder containing .ljson files for this server.",
        scope="server",
        kind="dir",
    ),
    "death_watcher_death_path": PathField(
        key="death_watcher_death_path",
        label="Death Watcher Output",
        must_exist=False,
        description="Watcher output file used to track DayZ death events.",
        scope="server",
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


REQUIRED_PATH_KEYS: List[str] = ["path_to_whitelist", "path_to_bans"]


def find_missing_required_paths(config: Dict[str, str]) -> List[str]:
    """Return config keys whose files must exist but do not."""

    import os

    missing: List[str] = []
    servers = config.get("servers") or []
    for key in REQUIRED_PATH_KEYS:
        field = PATH_FIELDS.get(key)
        if not field:
            continue
        if field.scope == "server":
            for server in servers:
                value = str(server.get(key, "")).strip()
                if not value:
                    missing.append(f"{key}:{server.get('server_id')}")
                    continue
                expanded = _expand(value)
                if field.kind == "dir":
                    exists = os.path.isdir(expanded)
                else:
                    exists = os.path.isfile(expanded)
                if not exists:
                    missing.append(f"{key}:{server.get('server_id')}")
        else:
            value = str(config.get(key, "")).strip()
            if not value:
                missing.append(key)
                continue
            expanded = _expand(value)
            exists = os.path.isdir(expanded) if field.kind == "dir" else os.path.isfile(expanded)
            if not exists:
                missing.append(key)
    return missing
