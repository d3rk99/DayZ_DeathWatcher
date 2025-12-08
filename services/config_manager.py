import json
import os
import sys
import threading
from argparse import ArgumentParser
from pathlib import Path
from typing import Any, Callable, Dict, List, Sequence

from services.path_fields import PATH_FIELDS, REQUIRED_PATH_KEYS


def _default_config() -> Dict[str, Any]:
    """Return a baseline config structure used for first-time setups."""

    return {
        "prefix": "*",
        "token": "",
        "whitelist_path": "",
        "blacklist_path": "",
        "userdata_db_path": "./userdata_db.json",
        "admin_role_id": 0,
        "guild_id": 0,
        "join_vc_id": 0,
        "join_vc_category_id": 0,
        "validate_steam_id_channel": "",
        "alive_role": 0,
        "dead_role": 0,
        "can_revive_role": 0,
        "season_pass_role": 0,
        "watch_death_watcher": 1,
        "death_watcher_death_path": "",
        "death_counter_path": "./death_counter.json",
        "run_death_watcher_cog": 1,
        "death_watcher_config_path": "",
        "steam_ids_to_unban_path": "./steam_ids_to_unban.txt",
        "error_dump_channel": "",
        "error_dump_allow_mention": 0,
        "error_dump_mention_tag": "",
        "wait_time_new_life_seconds": 1209600,
        "wait_time_new_life_seconds_season_pass": 300,
        "restart_notification_sound_path": "",
        "restart_notification_triggers": [],
    }


class ConfigManager:
    """Thread-safe helper that loads and saves the shared config.json file."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._data: Dict[str, Any] = {}
        self._is_new_file = False
        self.reload()

    @property
    def needs_initial_setup(self) -> bool:
        return self._is_new_file

    @property
    def data(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self._data)

    def add_listener(self, callback: Callable[[Dict[str, Any]], None]) -> None:
        if callback not in self._listeners:
            self._listeners.append(callback)

    def reload(self) -> Dict[str, Any]:
        with self._lock:
            if not self.path.exists():
                self._data = _default_config()
                self._is_new_file = True
            else:
                merged = _default_config()
                merged.update(json.loads(self.path.read_text()))
                self._data = merged
                self._is_new_file = False
        self._notify_listeners()
        return self.data

    def update(self, new_data: Dict[str, Any]) -> None:
        with self._lock:
            self._data.update(new_data)
            self.path.write_text(json.dumps(self._data, indent=4))
            self._is_new_file = False
        self._notify_listeners()

    def _notify_listeners(self) -> None:
        snapshot = self.data
        for callback in list(self._listeners):
            try:
                callback(snapshot)
            except Exception:
                # GUI should surface errors elsewhere; suppress here to
                # guarantee subsequent listeners still run.
                pass


class ConfigValidationError(Exception):
    """Raised when config.json is missing required fields or paths."""

    def __init__(self, issues: Sequence[str], *, missing_path_keys: Sequence[str] | None = None):
        self.issues = list(issues)
        self.missing_path_keys = list(missing_path_keys or [])
        prefix = "Configuration validation failed:\n - " if self.issues else "Configuration validation failed."
        message = prefix + "\n - ".join(self.issues)
        super().__init__(message)


_REQUIRED_ID_FIELDS: Dict[str, str] = {
    "admin_role_id": "Admin Role ID",
    "guild_id": "Guild ID",
    "join_vc_id": "Join Voice Channel ID",
    "join_vc_category_id": "Join Voice Category ID",
    "alive_role": "Alive Role ID",
    "dead_role": "Dead Role ID",
    "can_revive_role": "Can Revive Role ID",
    "validate_steam_id_channel": "Validate Steam ID Channel",
}


def _is_positive_int(value: Any) -> bool:
    try:
        return int(value) > 0
    except (TypeError, ValueError):
        return False


def _expand(path: str) -> Path:
    return Path(os.path.expanduser(str(path))).resolve()


def validate_config(config: Dict[str, Any], *, config_path: str | Path | None = None) -> None:
    """Validate required IDs and file paths.

    Raises:
        ConfigValidationError: if any required field is missing or unreadable.
    """

    issues: List[str] = []
    missing_path_keys: List[str] = []

    def add_issue(message: str, *, missing_key: str | None = None) -> None:
        issues.append(message)
        if missing_key:
            missing_path_keys.append(missing_key)

    token = str(config.get("token", "")).strip()
    if not token:
        add_issue("Discord bot token is missing (set DISCORD_TOKEN or update config.json).")

    for key, label in _REQUIRED_ID_FIELDS.items():
        if not _is_positive_int(config.get(key)):
            add_issue(f"{label} must be a positive integer.")

    for key in REQUIRED_PATH_KEYS:
        value = str(config.get(key, "")).strip()
        field = PATH_FIELDS.get(key)
        label = field.label if field else key
        if not value:
            add_issue(f"{label} is missing in config.json.", missing_key=key)
            continue

        expanded = _expand(value)
        if not expanded.is_file():
            add_issue(f"{label} does not exist at {expanded}.", missing_key=key)
            continue

        if not os.access(expanded, os.R_OK):
            add_issue(f"{label} is not readable at {expanded}.", missing_key=key)

    if issues:
        raise ConfigValidationError(issues, missing_path_keys=missing_path_keys)


def _parse_args(argv: Sequence[str]) -> ArgumentParser:
    parser = ArgumentParser(description="Validate the DayZ Death Watcher configuration.")
    parser.add_argument(
        "--config",
        default="config.json",
        help="Path to the config file to validate (default: config.json).",
    )
    return parser


def _load_config(config_path: Path) -> Dict[str, Any]:
    if not config_path.is_file():
        raise ConfigValidationError([f"Config file not found at {config_path}."])
    try:
        return json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ConfigValidationError([f"Config file contains invalid JSON: {exc}"]) from exc


def _run_cli(argv: Sequence[str]) -> int:
    parser = _parse_args(argv)
    args = parser.parse_args(argv)
    config_path = Path(args.config).expanduser().resolve()

    try:
        config = _load_config(config_path)
        validate_config(config, config_path=config_path)
    except ConfigValidationError as exc:
        print(exc)
        return 1

    print(f"Validation succeeded for {config_path}.")
    return 0


if __name__ == "__main__":
    sys.exit(_run_cli(sys.argv[1:]))
