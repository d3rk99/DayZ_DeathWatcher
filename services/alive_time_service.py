import json
import os
from pathlib import Path
from typing import Callable, Dict, List, Optional

from services.file_utils import atomic_write_text


DEFAULT_CACHE_CONTENT = {"prev_log_read": {"line": ""}, "log_label": ""}


class AliveTimeLogWatcher:
    """Lightweight watcher that scans DayZ logs for disconnect events."""

    def __init__(
        self,
        logs_directory: Path,
        cache_path: Path,
        *,
        logger: Optional[Callable[[str], None]] = None,
        event_name: str = "PLAYER_MANAGEMENT",
        sub_event: str = "disconnect",
        server_id: Optional[str] = None,
    ) -> None:
        self.logs_directory = logs_directory
        self.cache_path = cache_path
        self.event_name = event_name
        self.sub_event = sub_event
        self.server_id = str(server_id) if server_id is not None else None
        self._log = logger or (lambda message: print(message, flush=True))

        self.current_cache: Dict = {}
        self._cache_container: Dict = {}
        self._prepare_files()

    def poll_disconnects(self) -> List[Dict[str, Optional[str]]]:
        """Return any new disconnect events discovered since the last poll."""

        latest_file = self._get_latest_file()
        if not latest_file:
            return []

        try:
            with latest_file.open("r", encoding="utf-8", errors="ignore") as log_file:
                logs = [line for line in log_file.read().split("\n") if line]
        except Exception as exc:
            self._log(f"Failed to read log file {latest_file}: {exc}")
            return []

        if len(logs) > 1:
            log_label = " ".join(logs[1].split(" ")[3:])
            if log_label:
                self.current_cache["log_label"] = log_label

        new_lines = self._read_new_lines(logs)
        events: List[Dict[str, Optional[str]]] = []
        for line in new_lines:
            parsed = self._parse_log_line(line)
            if not parsed:
                continue
            if parsed.get("event") != self.event_name:
                continue
            if parsed.get("sub_event") != self.sub_event:
                continue

            player = parsed.get("player", parsed)
            steam_id = str(player.get("steamId", "") or parsed.get("steamId", ""))
            guid = player.get("dzid") or parsed.get("dzid") or player.get("guid")
            alive_seconds = self._coerce_int(player.get("aliveSec") or parsed.get("aliveSec"))
            name = player.get("name") or parsed.get("name")

            if alive_seconds is None:
                continue

            events.append(
                {
                    "steam_id": steam_id or None,
                    "guid": guid,
                    "alive_seconds": alive_seconds,
                    "name": name,
                }
            )

            self.current_cache["prev_log_read"]["line"] = line

        self._update_cache()
        return events

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------
    def _prepare_files(self) -> None:
        if not self.logs_directory.exists():
            self._log(
                f"Logs directory does not exist ({self.logs_directory}). Waiting for files to appear."
            )

        if not self.cache_path.exists():
            atomic_write_text(self.cache_path, json.dumps(DEFAULT_CACHE_CONTENT))
        try:
            cache_data = json.loads(self.cache_path.read_text())
        except json.JSONDecodeError:
            cache_data = dict(DEFAULT_CACHE_CONTENT)
            self.current_cache = cache_data
            self._update_cache()
            return

        if self.server_id:
            if "servers" not in cache_data:
                cache_data = {"servers": {self.server_id: cache_data}}
            self._cache_container = cache_data
            self.current_cache = cache_data.get("servers", {}).get(
                self.server_id, dict(DEFAULT_CACHE_CONTENT)
            )
            self.current_cache.setdefault("prev_log_read", {}).setdefault("line", "")
        else:
            self.current_cache = cache_data
            if "prev_log_read" not in self.current_cache:
                self.current_cache["prev_log_read"] = {"line": ""}

    def _update_cache(self) -> None:
        try:
            if self.server_id:
                if "servers" not in self._cache_container:
                    self._cache_container = {"servers": {}}
                self._cache_container["servers"][self.server_id] = self.current_cache
                atomic_write_text(self.cache_path, json.dumps(self._cache_container, indent=4))
            else:
                atomic_write_text(self.cache_path, json.dumps(self.current_cache, indent=4))
        except Exception:
            self._log(f"Failed to update alive time cache at {self.cache_path}")

    def _get_latest_file(self) -> Optional[Path]:
        if not self.logs_directory.exists():
            return None
        ljson_files = [
            entry
            for entry in self.logs_directory.glob("*")
            if entry.is_file() and entry.suffix.lower() == ".ljson"
        ]
        if not ljson_files:
            return None
        latest_file = max(ljson_files, key=os.path.getmtime)
        return Path(latest_file)

    def _read_new_lines(self, cached_lines: List[str]) -> List[str]:
        last_line = self.current_cache.get("prev_log_read", {}).get("line", "")
        if not cached_lines:
            return []

        lines = list(cached_lines)
        lines.reverse()
        new_lines: List[str] = []
        for line in lines:
            if line == last_line:
                break
            new_lines.insert(0, line)
        return new_lines

    @staticmethod
    def _parse_log_line(line: str) -> Optional[dict]:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _coerce_int(value) -> Optional[int]:
        if value is None:
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None
