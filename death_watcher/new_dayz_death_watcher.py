import json
import os
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Callable, List, Optional

DEFAULT_CACHE_CONTENT = {
    "servers": {}
}

DEFAULT_CONFIG = {
    "path_to_logs_directory": "E:/DayZ MM/servers/MementoMori/profiles/DetailedLogs",
    "path_to_cache": "./death_watcher_cache.json",
    "search_logs_interval": 1,
    "verbose_logs": 1,
    "death_event_name": "PLAYER_DEATH",
    "archive_old_ljson": 0,
    "death_exceptions": {
        "ignore_suicide_at_origin": True,
        "origin_coords": {"x": 0, "y": 0, "z": 0},
        "origin_tolerance": 0,
    },
}


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    temp_path.write_text(text, encoding="utf-8")
    os.replace(temp_path, path)


class DayZDeathWatcher:
    """Utility that tails DayZ server logs for death events."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        *,
        set_console_title: bool = False,
        config_data: Optional[dict] = None,
        server_id: Optional[str] = None,
        logger: Optional[Callable[[str], None]] = None,
        on_death: Optional[Callable[[str, Optional[int], Optional[str]], None]] = None,
    ) -> None:
        self._script_dir = Path(__file__).resolve().parent
        self.config_path = Path(config_path) if config_path else self._script_dir / "config.json"
        self.set_console_title = set_console_title
        self.config_data = config_data
        self.server_id = str(server_id) if server_id is not None else None
        self.current_cache: dict = {}
        self._cache_container: dict = {}
        self._stop_event = threading.Event()
        self._log = logger or (lambda message: print(message, flush=True))
        self._on_death = on_death
        self._partial_line = ""

        # populated during configuration loading
        self.config: dict = {}
        self.logs_directory: Optional[Path] = None
        self.path_to_cache: Optional[Path] = None
        self.death_event_name: str = "PLAYER_DEATH"
        self.search_logs_interval: float = 1.0
        self.verbose_logs: bool = False
        self.archive_old_ljson: bool = False
        self.death_exceptions: dict = {}

    # ------------------------------------------------------------------
    # public api
    # ------------------------------------------------------------------
    def run_blocking(self) -> None:
        """Run the watcher until `stop` is called."""
        if self.set_console_title and os.name == "nt":
            os.system("title DayZ Death Watcher")

        self._stop_event.clear()

        try:
            self._prepare_files()
        except Exception as exc:  # pragma: no cover - interactive convenience
            self._log(f"Failed to prepare death watcher files: {exc}")
            raise

        current_file = self.current_cache.get("current_file", "")
        if current_file:
            self._log(f"Last log file: {current_file} @ offset {self.current_cache.get('offset', 0)}")

        self._sleep(1)
        latest_file = self._get_latest_file()
        if latest_file:
            self._log(f"Started searching for new logs. ({latest_file})\n")
        else:
            self._log("Waiting for DayZ log files to appear...\n")
        self._sleep(1)

        while not self._stop_event.is_set():
            try:
                latest_file = self._get_latest_file()
            except Exception as exc:
                self._log(f"Unable to locate .ljson logs: {exc}")
                self._update_error(str(exc))
                self._sleep(10)
                continue

            if not latest_file:
                self._sleep(10)
                continue

            self._handle_file_rotation(latest_file)

            try:
                new_lines = self._read_new_lines(latest_file)
            except Exception as exc:
                self._log(f"Failed to read log file {latest_file}: {exc}")
                self._update_error(str(exc))
                self._sleep(10)
                continue

            for line in new_lines:
                parsed_log = self._parse_log_line(line)
                if not parsed_log:
                    continue
                if not self._is_death_log(parsed_log):
                    continue
                if self._should_ignore_death(parsed_log):
                    continue

                steam_id = self._get_steam_id(parsed_log)
                lifetime_seconds = self._get_lifetime_seconds(parsed_log)
                log_ts = str(parsed_log.get("ts", "")) if parsed_log.get("ts") else None
                if self.verbose_logs:
                    lifetime_text = (
                        f" Lived for {lifetime_seconds} seconds"
                        if lifetime_seconds is not None
                        else ""
                    )
                    self._log(
                        f"Found death log:\n    {line} Victim steam64: {steam_id}{lifetime_text}"
                    )

                if steam_id and self._on_death:
                    self._on_death(steam_id, lifetime_seconds, log_ts)

                if log_ts:
                    self.current_cache["last_ts"] = log_ts
                    self._update_cache()

            self._sleep(self.search_logs_interval)

        self._log("Death watcher stopped.")

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # configuration helpers
    # ------------------------------------------------------------------
    def _prepare_files(self) -> None:
        if self.config_data is None:
            self._ensure_config_exists()
        self._load_config()
        self._ensure_cache_exists()
        self.current_cache = self._load_cache()

        if not self.logs_directory or not self.logs_directory.exists():
            raise FileNotFoundError(
                f"Failed to find log directory: \"{self.logs_directory}\""
            )

    def _ensure_config_exists(self) -> None:
        if self.config_data is not None:
            return
        if self.config_path.exists():
            return

        self._log(f"Generating default config file: ({self.config_path})")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(self.config_path, json.dumps(DEFAULT_CONFIG, indent=4))

    def _load_config(self) -> None:
        if self.config_data is not None:
            self.config = dict(self.config_data)
        else:
            with self.config_path.open("r", encoding="utf-8") as json_file:
                self.config = json.load(json_file)

        def resolve_path(value: str) -> Path:
            candidate = Path(value)
            if not candidate.is_absolute():
                candidate = (self.config_path.parent / candidate).resolve()
            return candidate

        try:
            self.logs_directory = resolve_path(self.config["path_to_logs_directory"])
            self.path_to_cache = resolve_path(self.config["path_to_cache"])
            self.search_logs_interval = float(self.config["search_logs_interval"])
            self.verbose_logs = bool(int(self.config.get("verbose_logs", 0)))
            self.death_event_name = str(
                self.config.get("death_event_name", "PLAYER_DEATH")
            )
            self.archive_old_ljson = bool(int(self.config.get("archive_old_ljson", 0)))
            self.death_exceptions = dict(self.config.get("death_exceptions", {}))
        except KeyError as exc:
            raise RuntimeError(f"Missing config entry: {exc}")

    def _ensure_cache_exists(self) -> None:
        if self.path_to_cache and self.path_to_cache.exists():
            return

        assert self.path_to_cache is not None
        self._log(f"Failed to find cache file: {self.path_to_cache}\nCreating it now.")
        self.path_to_cache.parent.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(self.path_to_cache, json.dumps(DEFAULT_CACHE_CONTENT, indent=4))

    def _load_cache(self) -> dict:
        assert self.path_to_cache is not None
        with self.path_to_cache.open("r", encoding="utf-8") as json_file:
            cache = json.load(json_file)
        if "servers" not in cache:
            cache = {"servers": {self.server_id or "default": cache}}
        self._cache_container = cache
        server_key = self.server_id or "default"
        scoped_cache = cache.get("servers", {}).get(server_key, {})
        scoped_cache.setdefault("current_file", "")
        scoped_cache.setdefault("offset", 0)
        scoped_cache.setdefault("last_ts", "")
        scoped_cache.setdefault("last_error", "")
        return scoped_cache

    def _update_cache(self) -> None:
        assert self.path_to_cache is not None
        server_key = self.server_id or "default"
        self._cache_container.setdefault("servers", {})[server_key] = self.current_cache
        _atomic_write_text(self.path_to_cache, json.dumps(self._cache_container, indent=4))

    def _update_error(self, message: str) -> None:
        self.current_cache["last_error"] = message
        self._update_cache()

    # ------------------------------------------------------------------
    # log helpers
    # ------------------------------------------------------------------
    def _get_latest_file(self) -> Optional[Path]:
        assert self.logs_directory is not None
        ljson_files = [
            entry
            for entry in self.logs_directory.glob("*.ljson")
            if entry.is_file() and entry.name.startswith("dl_")
        ]
        if not ljson_files:
            return None
        latest_file = max(ljson_files, key=os.path.getmtime)
        return Path(latest_file)

    def _handle_file_rotation(self, latest_file: Path) -> None:
        current_file = self.current_cache.get("current_file", "")
        if current_file == str(latest_file):
            return
        if current_file and self.archive_old_ljson:
            self._archive_old_logs(current_file, latest_file)
        self.current_cache["current_file"] = str(latest_file)
        self.current_cache["offset"] = 0
        self._partial_line = ""
        self._update_cache()

    def _archive_old_logs(self, current_file: str, latest_file: Path) -> None:
        try:
            archive_dir = (latest_file.parent / "archive").resolve()
            archive_dir.mkdir(parents=True, exist_ok=True)
            for entry in latest_file.parent.glob("*.ljson"):
                if entry == latest_file:
                    continue
                target = archive_dir / entry.name
                if entry.exists() and not target.exists():
                    entry.rename(target)
        except Exception as exc:
            self._log(f"Failed to archive old logs: {exc}")

    def _read_new_lines(self, log_file: Path) -> List[str]:
        offset = int(self.current_cache.get("offset", 0))
        file_size = log_file.stat().st_size
        if offset > file_size:
            offset = 0
        with log_file.open("r", encoding="utf-8", errors="ignore") as handle:
            handle.seek(offset)
            data = handle.read()
            new_offset = handle.tell()

        if not data:
            self.current_cache["offset"] = new_offset
            self._update_cache()
            return []

        combined = f"{self._partial_line}{data}"
        lines = combined.splitlines(keepends=True)
        self._partial_line = ""
        new_lines: List[str] = []
        for line in lines:
            if line.endswith("\n") or line.endswith("\r"):
                stripped = line.strip()
                if stripped:
                    new_lines.append(stripped)
            else:
                self._partial_line = line

        self.current_cache["offset"] = new_offset
        self._update_cache()
        return new_lines

    def _is_death_log(self, log_entry: dict) -> bool:
        return log_entry.get("event") == self.death_event_name

    @staticmethod
    def _parse_log_line(line: str) -> Optional[dict]:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _get_steam_id(self, log_entry: dict) -> str:
        steam_id = log_entry.get("player", {}).get("steamId")
        if not steam_id:
            return ""
        steam_id = str(steam_id).strip()
        if steam_id.isdigit() and len(steam_id) == 17:
            return steam_id
        return ""

    def _should_ignore_death(self, log_entry: dict) -> bool:
        if not self.death_exceptions:
            return False
        if not bool(self.death_exceptions.get("ignore_suicide_at_origin", False)):
            return False
        if log_entry.get("sub_event") != "suicide":
            return False
        data = log_entry.get("data", {})
        if data.get("source") != "self" or data.get("killer") != "self":
            return False
        player = log_entry.get("player", {})
        position = player.get("position", {})
        if not isinstance(position, dict):
            return False
        origin = self.death_exceptions.get("origin_coords", {"x": 0, "y": 0, "z": 0})
        tolerance = float(self.death_exceptions.get("origin_tolerance", 0) or 0)
        try:
            dx = float(position.get("x", 0)) - float(origin.get("x", 0))
            dy = float(position.get("y", 0)) - float(origin.get("y", 0))
            dz = float(position.get("z", 0)) - float(origin.get("z", 0))
        except (TypeError, ValueError):
            return False
        at_origin = False
        if tolerance > 0:
            at_origin = (dx * dx + dy * dy + dz * dz) ** 0.5 <= tolerance
        else:
            at_origin = dx == 0 and dy == 0 and dz == 0
        if not at_origin:
            return False
        if self.verbose_logs:
            steam_id = self._get_steam_id(log_entry)
            self._log(
                "Ignored transfer death at origin for steam64="
                f"{steam_id} coords=({position.get('x')}, {position.get('y')}, {position.get('z')})"
            )
        return True

    @staticmethod
    def _get_lifetime_seconds(log_entry: dict) -> Optional[int]:
        lifetime = log_entry.get("player", {}).get("aliveSec")
        if lifetime is None:
            return None
        try:
            return int(lifetime)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # misc helpers
    # ------------------------------------------------------------------
    def _sleep(self, seconds: float) -> None:
        remaining = max(0.0, seconds)
        while remaining > 0 and not self._stop_event.is_set():
            step = min(0.25, remaining)
            time.sleep(step)
            remaining -= step


def main() -> None:
    watcher = DayZDeathWatcher(set_console_title=True)
    try:
        watcher.run_blocking()
    except KeyboardInterrupt:
        print("Closing program...")
        time.sleep(1.0)
    except Exception:
        print("Ran into an unexpected exception. Printing traceback below:\n")
        print(traceback.format_exc())
        input("Press enter to close this window.")


if __name__ == "__main__":
    main()
