import json
import os
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Callable, List, Optional, Tuple

from dayz_dev_tools import guid as GUID

DEFAULT_CACHE_CONTENT = {
    "prev_log_read": {"line": ""},
    "log_label": "2022-01-01 at 00:00:00",
}

DEFAULT_CONFIG = {
    "path_to_logs_directory": "E:/DayZ MM/servers/MementoMori/profiles/DetailedLogs",
    "path_to_bans": "./deaths.txt",
    "path_to_cache": "./death_watcher_cache.json",
    "ban_delay": 5,
    "search_logs_interval": 1,
    "verbose_logs": 1,
    "death_event_name": "PLAYER_DEATH",
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
    ) -> None:
        self._script_dir = Path(__file__).resolve().parent
        self.config_path = Path(config_path) if config_path else self._script_dir / "config.json"
        self.set_console_title = set_console_title
        self.config_data = config_data
        self.server_id = str(server_id) if server_id is not None else None
        self.players_to_ban: List[Tuple[str, float]] = []
        self.current_cache: dict = {}
        self._cache_container: dict = {}
        self._stop_event = threading.Event()
        self._log = logger or (lambda message: print(message, flush=True))

        # populated during configuration loading
        self.config: dict = {}
        self.logs_directory: Optional[Path] = None
        self.path_to_bans: Optional[Path] = None
        self.path_to_cache: Optional[Path] = None
        self.death_event_name: str = "PLAYER_DEATH"
        self.search_logs_interval: float = 1.0
        self.verbose_logs: bool = False
        self.ban_delay: float = 5.0

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

        last_log_line = self.current_cache.get("prev_log_read", {}).get("line", "")
        if last_log_line:
            self._log(f"Last log read: {last_log_line}")

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
                self._sleep(10)
                continue

            if not latest_file:
                self._sleep(10)
                continue

            try:
                with latest_file.open("r", encoding="utf-8", errors="ignore") as log_file:
                    logs = [line for line in log_file.read().split("\n") if line]
            except Exception as exc:
                self._log(f"Failed to read log file {latest_file}: {exc}")
                self._sleep(10)
                continue

            if len(logs) > 1:
                log_label = " ".join(logs[1].split(" ")[3:])
                if log_label:
                    self.current_cache["log_label"] = log_label

            new_lines = self._read_new_lines(latest_file, logs)
            for line in new_lines:
                parsed_log = self._parse_log_line(line)
                is_death_log = parsed_log and self._is_death_log(parsed_log)
                if is_death_log:
                    player_id = self._get_id_from_log(parsed_log)
                    lifetime_seconds = self._get_lifetime_seconds(parsed_log)
                    if self.verbose_logs:
                        lifetime_text = (
                            f" Lived for {lifetime_seconds} seconds"
                            if lifetime_seconds is not None
                            else ""
                        )
                        self._log(
                            f"Found death log:\n    {line} Victim id: {player_id}{lifetime_text}"
                        )

                    if player_id and not self._player_is_queued_for_ban(player_id):
                        self._queue_player_for_ban(player_id)

                self.current_cache["prev_log_read"]["line"] = line
                self._update_cache()

            self._try_to_ban_players()
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

        if not self.path_to_bans or not self.path_to_bans.exists():
            raise FileNotFoundError(
                f"Failed to find ban file: \"{self.path_to_bans}\""
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
            self.path_to_bans = resolve_path(self.config["path_to_bans"])
            self.path_to_cache = resolve_path(self.config["path_to_cache"])
            self.search_logs_interval = float(self.config["search_logs_interval"])
            self.verbose_logs = bool(int(self.config["verbose_logs"]))
            self.ban_delay = float(self.config["ban_delay"])
            self.death_event_name = str(
                self.config.get("death_event_name", "PLAYER_DEATH")
            )
        except KeyError as exc:
            raise RuntimeError(f"Missing config entry: {exc}")

        if not self.logs_directory.exists():
            raise FileNotFoundError(
                f"Failed to find log directory: \"{self.logs_directory}\""
            )

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
        if self.server_id:
            if "servers" not in cache:
                cache = {"servers": {self.server_id: cache}}
            self._cache_container = cache
            scoped_cache = cache.get("servers", {}).get(self.server_id, {})
            scoped_cache.setdefault("prev_log_read", {}).setdefault("line", "")
            if scoped_cache["prev_log_read"]["line"] == "\n":
                scoped_cache["prev_log_read"]["line"] = ""
            scoped_cache.setdefault("log_label", "")
            return scoped_cache

        cache.setdefault("prev_log_read", {}).setdefault("line", "")
        if cache["prev_log_read"]["line"] == "\n":
            cache["prev_log_read"]["line"] = ""
        cache.setdefault("log_label", "")
        return cache

    def _update_cache(self) -> None:
        assert self.path_to_cache is not None
        if self.server_id:
            if "servers" not in self._cache_container:
                self._cache_container = {"servers": {}}
            self._cache_container["servers"][self.server_id] = self.current_cache
            _atomic_write_text(self.path_to_cache, json.dumps(self._cache_container, indent=4))
            return
        _atomic_write_text(self.path_to_cache, json.dumps(self.current_cache, indent=4))

    # ------------------------------------------------------------------
    # log helpers
    # ------------------------------------------------------------------
    def _get_latest_file(self) -> Optional[Path]:
        assert self.logs_directory is not None
        ljson_files = [
            entry
            for entry in self.logs_directory.glob("*")
            if entry.is_file() and entry.suffix.lower() == ".ljson"
        ]
        if not ljson_files:
            return None
        latest_file = max(ljson_files, key=os.path.getmtime)
        return Path(latest_file)

    def _read_new_lines(self, log_file: Path, cached_lines: List[str]) -> List[str]:
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

    def _is_death_log(self, log_entry: dict) -> bool:
        return log_entry.get("event") == self.death_event_name

    @staticmethod
    def _parse_log_line(line: str) -> Optional[dict]:
        try:
            return json.loads(line)
        except json.JSONDecodeError:
            return None

    def _get_id_from_log(self, log_entry: dict) -> str:
        steam_id = log_entry.get("player", {}).get("steamId")
        if not steam_id:
            return ""

        try:
            return str(GUID.guid_for_steamid64(str(steam_id)))
        except Exception as exc:
            self._log(
                f"Failed to convert steam ID {steam_id} to GUID; skipping ban entry. ({exc})"
            )
            return ""

    @staticmethod
    def _get_lifetime_seconds(log_entry: dict) -> Optional[float]:
        lifetime = log_entry.get("player", {}).get("aliveSec")
        if lifetime is None:
            return None
        try:
            return float(lifetime)
        except (TypeError, ValueError):
            return None

    # ------------------------------------------------------------------
    # ban helpers
    # ------------------------------------------------------------------
    def _player_is_queued_for_ban(self, player_id: str) -> bool:
        return any(player_id == player[0] for player in self.players_to_ban)

    def _queue_player_for_ban(self, player_id: str) -> None:
        time_to_ban_player = time.time() + self.ban_delay
        if self.players_to_ban and time_to_ban_player < self.players_to_ban[-1][1] + 2:
            time_to_ban_player = self.players_to_ban[-1][1] + 2
        self.players_to_ban.append((player_id, time_to_ban_player))
        self._log(f"    Banning player with id: {player_id}.")
        if self.verbose_logs:
            eta = max(0.0, time_to_ban_player - time.time())
            self._log(f"    This player will be banned in {eta} seconds.")

    def _try_to_ban_players(self) -> None:
        current_seconds = time.time()
        while self.players_to_ban and current_seconds >= self.players_to_ban[0][1]:
            player_id, _ = self.players_to_ban.pop(0)
            self._ban_player(player_id)
            current_seconds = time.time()

    def _ban_player(self, player_id: str) -> None:
        assert self.path_to_bans is not None
        success = False
        tries = 0
        while not success and tries < 10:
            try:
                ids = []
                if self.path_to_bans.exists():
                    ids = [
                        name.strip()
                        for name in self.path_to_bans.read_text(encoding="utf-8").splitlines()
                        if name.strip()
                    ]
                if player_id not in ids:
                    ids.append(player_id)
                    _atomic_write_text(self.path_to_bans, "\n".join(ids))
                success = True
            except Exception as exc:
                self._log(f"Failed to ban player: '{exc}' Try: {tries + 1}")
                tries += 1
                self._sleep(0.25)

        if success:
            if self.verbose_logs:
                self._log(f"Added player with id: {player_id} to ban file: {self.path_to_bans}")
        else:
            self._log(f"Player: {player_id} could not be added to the ban file: {self.path_to_bans}")

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
