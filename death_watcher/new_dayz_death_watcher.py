import glob
import json
import datetime
import os
import re
import threading
import time
import traceback
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, Iterable, List, Optional, Tuple
from urllib import error, request

DEFAULT_CACHE_CONTENT = {
    "prev_log_read": {"line": ""},
    "log_label": "2022-01-01 at 00:00:00",
}

DEFAULT_CONFIG = {
    "path_to_logs_directory": "../../profiles",
    "path_to_bans": "./deaths.txt",
    "path_to_cache": "./death_watcher_cache.json",
    "userdata_db_path": "../userdata_db.json",
    "death_cues": [
        "killed by",
        "committed suicide",
        "bled out",
        "died.",
        "(DEAD)",
        "was brutally murdered by that psycho Timmy",
    ],
    "ban_delay": 5,
    "search_logs_interval": 1,
    "verbose_logs": 1,
    "track_playtime": 0,
    "playtime_report_url": "",
    "playtime_bridge_token": "",
}


def death_event_player_id(line: str, cues: Iterable[str]) -> str:
    """Return the player id for a valid death line, otherwise an empty string.

    The helper enforces the following rules to avoid noisy matches:

    * A configured death cue must appear outside of quotes.
    * The line must include a parenthesised ``id=`` segment that is long enough
      to contain a DayZ GUID.
    * Unknown player ids are ignored.
    """

    if not line or "(id=" not in line:
        return ""

    normalized = line.casefold()
    if not any(cue.casefold() in normalized for cue in cues):
        return ""

    for cue in cues:
        lowered = cue.casefold()
        if lowered in normalized:
            quoted_double = f'"{cue}' in line
            quoted_single = f"'{cue}" in line
            if quoted_double or quoted_single:
                continue
            break
    else:
        return ""

    index = line.find("(id=")
    start_index = index + 4
    if index == -1 or len(line) < (start_index + 44):
        return ""
    player_id = line[start_index : start_index + 44]
    if "Unknown" in player_id or len(player_id.strip()) < 10:
        return ""
    return player_id


@dataclass
class _LogFileState:
    path: Path
    inode: int
    position: int


class DayZDeathWatcher:
    """Utility that tails DayZ server logs for death events."""

    def __init__(
        self,
        config_path: Optional[str] = None,
        *,
        set_console_title: bool = False,
        logger: Optional[Callable[[str], None]] = None,
    ) -> None:
        self._script_dir = Path(__file__).resolve().parent
        self.config_path = Path(config_path) if config_path else self._script_dir / "config.json"
        self.set_console_title = set_console_title
        self.players_to_ban: List[Tuple[str, float]] = []
        self.current_cache: dict = {}
        self._stop_event = threading.Event()
        self._log = logger or (lambda message: print(message, flush=True))
        self._log_state: Optional[_LogFileState] = None

        # populated during configuration loading
        self.config: dict = {}
        self.logs_directory: Optional[Path] = None
        self.path_to_bans: Optional[Path] = None
        self.path_to_cache: Optional[Path] = None
        self.death_cues: List[str] = []
        self.search_logs_interval: float = 1.0
        self.verbose_logs: bool = False
        self.ban_delay: float = 5.0
        self.track_playtime: bool = False
        self.playtime_report_url: Optional[str] = None
        self.playtime_bridge_token: Optional[str] = None
        self.userdata_db_path: Optional[Path] = None
        self._active_sessions: Dict[str, Dict[str, object]] = {}
        self._userdata_cache: Dict[str, Dict[str, object]] = {}
        self._userdata_loaded_at: float = 0.0

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

        log_number = 0
        while not self._stop_event.is_set():
            try:
                latest_file = self._get_latest_file()
            except Exception as exc:
                self._log(f"Unable to locate .adm logs: {exc}")
                self._sleep(10)
                continue

            if not latest_file:
                self._sleep(10)
                continue

            try:
                new_lines = self._collect_new_lines(latest_file)
            except Exception as exc:
                self._log(f"Failed to read log file {latest_file}: {exc}")
                self._sleep(10)
                continue

            if self.verbose_logs and new_lines:
                self._log(f"Found {len(new_lines)} new logs")

            for line in new_lines:
                if self.verbose_logs:
                    self._log(f"[{log_number}] {line}")

                player_id = death_event_player_id(line, self.death_cues)
                if player_id:
                    if self.verbose_logs:
                        self._log(f"Found death log:\n    {line} Victim id: {player_id}")

                    if not self._player_is_queued_for_ban(player_id):
                        self._queue_player_for_ban(player_id)

                self._handle_session_tracking(line)

                self.current_cache["prev_log_read"]["line"] = line
                self._update_cache()
                log_number += 1

            if self.verbose_logs and new_lines:
                self._log("")

            self._try_to_ban_players()
            self._sleep(self.search_logs_interval)

        self._log("Death watcher stopped.")

    def stop(self) -> None:
        self._stop_event.set()

    # ------------------------------------------------------------------
    # configuration helpers
    # ------------------------------------------------------------------
    def _prepare_files(self) -> None:
        self._ensure_config_exists()
        self._load_config()
        self._ensure_cache_exists()
        self.current_cache = self._load_cache()

        if not self.path_to_bans or not self.path_to_bans.exists():
            raise FileNotFoundError(
                f"Failed to find ban file: \"{self.path_to_bans}\""
            )

    def _ensure_config_exists(self) -> None:
        if self.config_path.exists():
            return

        self._log(f"Generating default config file: ({self.config_path})")
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with self.config_path.open("w", encoding="utf-8") as config_file:
            json.dump(DEFAULT_CONFIG, config_file, indent=4)

    def _load_config(self) -> None:
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
            userdata_path = self.config.get("userdata_db_path")
            self.userdata_db_path = resolve_path(userdata_path) if userdata_path else None
            self.death_cues = list(self.config["death_cues"])
            self.search_logs_interval = float(self.config["search_logs_interval"])
            self.verbose_logs = bool(int(self.config["verbose_logs"]))
            self.ban_delay = float(self.config["ban_delay"])
            self.track_playtime = bool(int(self.config.get("track_playtime", 0)))
            self.playtime_report_url = self.config.get("playtime_report_url") or None
            self.playtime_bridge_token = self.config.get("playtime_bridge_token") or None
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
        with self.path_to_cache.open("w", encoding="utf-8") as file:
            json.dump(DEFAULT_CACHE_CONTENT, file, indent=4)

    def _load_cache(self) -> dict:
        assert self.path_to_cache is not None
        with self.path_to_cache.open("r", encoding="utf-8") as json_file:
            cache = json.load(json_file)

        cache.setdefault("prev_log_read", {}).setdefault("line", "")
        if cache["prev_log_read"]["line"] == "\n":
            cache["prev_log_read"]["line"] = ""
        cache.setdefault("log_label", "")
        return cache

    # ------------------------------------------------------------------
    # playtime tracking
    # ------------------------------------------------------------------
    def _extract_timestamp(self, line: str) -> float:
        match = re.search(r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})", line)
        if match:
            try:
                return datetime.datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S").timestamp()
            except ValueError:
                pass

        match = re.search(r"(\d{2}:\d{2}:\d{2})", line)
        if match:
            try:
                today = datetime.datetime.utcnow().date()
                dt = datetime.datetime.strptime(match.group(1), "%H:%M:%S")
                combined = datetime.datetime.combine(today, dt.time())
                return combined.timestamp()
            except ValueError:
                pass

        return time.time()

    def _reload_userdata_cache(self) -> None:
        if not self.userdata_db_path or not self.userdata_db_path.exists():
            return
        if time.time() - self._userdata_loaded_at < 60:
            return
        try:
            content = self.userdata_db_path.read_text(encoding="utf-8")
            data = json.loads(content)
            self._userdata_cache = data.get("userdata", {}) if isinstance(data, dict) else {}
            self._userdata_loaded_at = time.time()
        except Exception as exc:  # pragma: no cover - best effort helper
            self._log(f"[playtime] Failed to load userdata cache: {exc}")

    def _lookup_steam_id(self, guid: str) -> Optional[str]:
        self._reload_userdata_cache()
        for entry in self._userdata_cache.values():
            if not isinstance(entry, dict):
                continue
            if entry.get("guid") == guid:
                steam_id = entry.get("steam_id")
                if isinstance(steam_id, str) and steam_id.strip():
                    return steam_id.strip()
        return None

    def _handle_session_tracking(self, line: str) -> None:
        match = re.search(r'Player "(?P<name>[^"]+)".*\(id=(?P<guid>[^\)]+)\)', line)
        if not match:
            return

        normalized = line.casefold()
        event: Optional[str] = None
        if any(
            token in normalized
            for token in ("disconnected", "has been disconnected", "logged off", "has left")
        ):
            event = "logout"
        elif any(token in normalized for token in ("connected", "has joined", "logged in")):
            event = "login"

        if not event:
            return

        timestamp = self._extract_timestamp(line)
        guid = match.group("guid").strip()
        name = match.group("name").strip()
        self._log(self._format_session_event(event, name, guid, timestamp))

        if not self.track_playtime or not self.playtime_report_url:
            return

        if event == "login":
            self._active_sessions[guid] = {
                "name": name,
                "login": timestamp,
                "steam_id": self._lookup_steam_id(guid),
            }
            return

        session = self._active_sessions.pop(guid, None)
        if not session:
            return

        login_ts = float(session.get("login", timestamp))
        duration = max(0, int(timestamp - login_ts))
        steam_id = session.get("steam_id") if isinstance(session, dict) else None
        self._report_play_session(
            guid,
            name or session.get("name", ""),
            login_ts,
            timestamp,
            duration,
            steam_id,
        )

    def _format_session_event(self, event: str, name: str, guid: str, timestamp: float) -> str:
        verb = "connected" if event == "login" else "disconnected"
        at = datetime.datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        return f"[session] {name} ({guid}) {verb} at {at}"

    def _report_play_session(
        self,
        guid: str,
        name: str,
        login_ts: float,
        logout_ts: float,
        duration: int,
        steam_id: Optional[str] = None,
    ) -> None:
        payload = {
            "playerGuid": guid,
            "playerName": name,
            "steam64Id": steam_id,
            "loginAt": datetime.datetime.utcfromtimestamp(login_ts).isoformat(),
            "logoutAt": datetime.datetime.utcfromtimestamp(logout_ts).isoformat(),
            "durationSeconds": int(duration),
        }

        headers = {"Content-Type": "application/json"}
        if self.playtime_bridge_token:
            headers["x-bot-bridge-token"] = self.playtime_bridge_token

        request_obj = request.Request(
            self.playtime_report_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            request.urlopen(request_obj, timeout=10)
        except error.HTTPError as exc:  # pragma: no cover - network operation
            self._log(f"[playtime] Failed to report session ({exc.code}): {exc.reason}")
        except Exception as exc:  # pragma: no cover - network operation
            self._log(f"[playtime] Failed to report session: {exc}")

    def _update_cache(self) -> None:
        assert self.path_to_cache is not None
        with self.path_to_cache.open("w", encoding="utf-8") as json_file:
            json.dump(self.current_cache, json_file, indent=4)
        if self.verbose_logs:
            self._log(f"Updated cache file:\n    {self.current_cache}")

    # ------------------------------------------------------------------
    # log helpers
    # ------------------------------------------------------------------
    def _get_latest_file(self) -> Optional[Path]:
        assert self.logs_directory is not None
        adm_files = glob.glob(str(self.logs_directory / "*.adm"))
        if not adm_files:
            return None
        latest_file = max(adm_files, key=os.path.getmtime)
        return Path(latest_file)

    def _get_cached_last_line(self) -> str:
        return self.current_cache.get("prev_log_read", {}).get("line", "")

    def _collect_new_lines(self, latest_file: Path) -> List[str]:
        if self._log_state is None or not self._log_state.path.exists():
            self._log_state, new_lines = self._prime_log_state(latest_file)
            return new_lines

        state_stat = self._log_state.path.stat()
        if state_stat.st_ino != self._log_state.inode or state_stat.st_size < self._log_state.position:
            self._log_state, new_lines = self._prime_log_state(latest_file)
            return new_lines

        if latest_file != self._log_state.path:
            new_lines = self._read_from_position(self._log_state)
            self._log_state, primed_lines = self._prime_log_state(latest_file)
            return new_lines + primed_lines

        return self._read_from_position(self._log_state)

    def _prime_log_state(self, log_file: Path) -> Tuple[_LogFileState, List[str]]:
        lines = self._read_lines_from_file(log_file)
        if len(lines) > 1:
            log_label = " ".join(lines[1].split(" ")[3:])
            if log_label:
                self.current_cache["log_label"] = log_label

        new_lines = self._filter_cached_lines(lines)
        inode = log_file.stat().st_ino
        position = log_file.stat().st_size
        return _LogFileState(path=log_file, inode=inode, position=position), new_lines

    def _read_from_position(self, state: _LogFileState) -> List[str]:
        with state.path.open("r", encoding="utf-8", errors="ignore") as log_file:
            log_file.seek(state.position)
            content = log_file.read()
            state.position = log_file.tell()
        return [line for line in content.split("\n") if line]

    @staticmethod
    def _read_lines_from_file(log_file: Path) -> List[str]:
        with log_file.open("r", encoding="utf-8", errors="ignore") as file:
            return [line for line in file.read().split("\n") if line]

    def _filter_cached_lines(self, lines: List[str]) -> List[str]:
        last_line = self._get_cached_last_line()
        if not lines:
            return []

        reversed_lines = list(lines)
        reversed_lines.reverse()
        new_lines: List[str] = []
        for line in reversed_lines:
            if line == last_line:
                break
            new_lines.insert(0, line)
        return new_lines

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
                with self.path_to_bans.open("a+", encoding="utf-8") as file:
                    file.seek(0)
                    ids = [name.strip() for name in file]
                    if player_id not in ids:
                        file.write(f"{player_id}\n")
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
        watcher._log("Closing program...")
        time.sleep(1.0)
    except Exception:
        watcher._log("Ran into an unexpected exception. Printing traceback below:\n")
        watcher._log(traceback.format_exc())
        input("Press enter to close this window.")


if __name__ == "__main__":
    main()
