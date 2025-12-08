import json
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List


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
        "bot_sync_api_url": "",
        "bot_sync_token": "",
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
