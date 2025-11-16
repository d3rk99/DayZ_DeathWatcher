"""Death Watcher module.

Originally this script was a stand-alone utility. It now exposes a
``DeathWatcher`` class that can be embedded in the Discord bot so both pieces
can run from the same process. The watcher tails the newest DayZ ``.adm`` log
inside the configured directory, looks for death cues and appends the matching
GUID to the ``deaths.txt`` file that the bot consumes.
"""
from __future__ import annotations

import glob
import json
import os
import threading
import time
from typing import Dict, List, Tuple

DEFAULT_CONFIG: Dict[str, object] = {
    "path_to_logs_directory": "../../profiles",
    "path_to_bans": "./deaths.txt",
    "path_to_cache": "./death_watcher_cache.json",
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
}

DEFAULT_CACHE = {
    "prev_log_read": {"line": ""},
    "log_label": "2022-01-01 at 00:00:00",
}


class DeathWatcher:
    """Tail DayZ server logs and write deaths to a ban file."""

    def __init__(self, config_path: str | None = None) -> None:
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.config_path = config_path or os.path.join(base_dir, "config.json")
        self.base_dir = os.path.dirname(os.path.abspath(self.config_path))
        self.players_to_ban: List[Tuple[str, float]] = []
        self.stop_event = threading.Event()
        self.current_cache: Dict[str, Dict[str, str]] = DEFAULT_CACHE.copy()

        self._ensure_config_file()
        self.config = self._load_json(self.config_path)
        self._hydrate_paths_from_config()
        self._ensure_cache_file()
        self.current_cache = self._load_json(self.path_to_cache)
        self.verbose_logs = int(self.config.get("verbose_logs", 0))
        self.search_logs_interval = float(self.config.get("search_logs_interval", 1))
        self.ban_delay = float(self.config.get("ban_delay", 5))

    def start_in_background(self) -> threading.Thread:
        """Start the watcher on a daemon thread and return it."""
        thread = threading.Thread(target=self.run, daemon=True)
        thread.start()
        return thread

    def stop(self) -> None:
        """Signal the watcher to stop."""
        self.stop_event.set()

    # ------------------------------------------------------------------
    # File helpers
    def _ensure_config_file(self) -> None:
        os.makedirs(self.base_dir, exist_ok=True)
        if not os.path.isfile(self.config_path):
            with open(self.config_path, "w", encoding="utf-8") as file:
                json.dump(DEFAULT_CONFIG, file, indent=2)

    def _ensure_cache_file(self) -> None:
        cache_dir = os.path.dirname(self.path_to_cache)
        os.makedirs(cache_dir, exist_ok=True)
        if not os.path.isfile(self.path_to_cache):
            with open(self.path_to_cache, "w", encoding="utf-8") as file:
                json.dump(DEFAULT_CACHE, file, indent=2)

    def _load_json(self, path: str) -> Dict:
        with open(path, "r", encoding="utf-8") as json_file:
            return json.load(json_file)

    def _resolve_path(self, configured_path: str) -> str:
        if os.path.isabs(configured_path):
            return configured_path
        return os.path.abspath(os.path.join(self.base_dir, configured_path))

    def _hydrate_paths_from_config(self) -> None:
        self.path_to_logs_directory = self._resolve_path(
            self.config["path_to_logs_directory"]
        )
        self.path_to_bans = self._resolve_path(self.config["path_to_bans"])
        self.path_to_cache = self._resolve_path(self.config["path_to_cache"])
        self.death_cues = self.config.get("death_cues", [])

    # ------------------------------------------------------------------
    # Core functionality
    def run(self) -> None:
        """Continuously monitor logs for deaths."""
        print("Starting embedded DayZ death watcher...")
        if not os.path.isfile(self.path_to_bans):
            raise FileNotFoundError(
                f"Failed to find ban file: '{self.path_to_bans}'."
            )

        self.current_cache = self._load_json(self.path_to_cache)
        if self.current_cache.get("prev_log_read", {}).get("line") == "\n":
            self.current_cache["prev_log_read"]["line"] = ""

        try:
            latest_file = self.get_latest_file()
        except FileNotFoundError as exc:
            print(exc)
            latest_file = None
        if latest_file:
            print(f"Started searching for new logs. ({latest_file})")

        while not self.stop_event.is_set():
            try:
                latest_file = self.get_latest_file()
                logs = self._read_log_file(latest_file)
            except FileNotFoundError as exc:
                print(exc)
                self._sleep_with_stop(10)
                continue

            log_label = " ".join(logs[1].split(" ")[3:]) if len(logs) > 1 else ""
            if log_label != self.current_cache.get("log_label"):
                self.current_cache["log_label"] = log_label

            new_lines = self.read_new_lines(logs)
            if self.verbose_logs and new_lines:
                print(f"Found {len(new_lines)} new logs")

            for line in new_lines:
                self._process_line(line)
                self.current_cache["prev_log_read"]["line"] = line
                self.update_cache()

            if self.verbose_logs and new_lines:
                print()
            self.try_to_ban_players()
            self._sleep_with_stop(self.search_logs_interval)

    def _process_line(self, line: str) -> None:
        if self.verbose_logs:
            print(line)
        if self.is_death_log(line):
            player_id = self.get_id_from_line(line)
            if self.verbose_logs:
                print(f"Found death log: {line} Victim id: {player_id}")
            if player_id and not self.player_is_queued_for_ban(player_id):
                time_to_ban_player = time.time() + self.ban_delay
                if (
                    self.players_to_ban
                    and time_to_ban_player < self.players_to_ban[-1][1] + 2
                ):
                    time_to_ban_player = self.players_to_ban[-1][1] + 2
                self.players_to_ban.append((player_id, time_to_ban_player))
                print(f"    Queued ban for player id: {player_id}.")
                if self.verbose_logs:
                    print(
                        f"    This player will be banned in {time_to_ban_player - time.time()} seconds."
                    )

    def try_to_ban_players(self) -> None:
        current_seconds = time.time()
        for player in list(self.players_to_ban):
            if current_seconds >= player[1]:
                self.ban_player(player[0])
                self.players_to_ban.remove(player)
            else:
                break

    def ban_player(self, player_id: str) -> None:
        tries = 0
        while tries < 10:
            try:
                os.makedirs(os.path.dirname(self.path_to_bans), exist_ok=True)
                with open(self.path_to_bans, "a+", encoding="utf-8") as file:
                    file.seek(0)
                    ids = [name.strip() for name in file]
                    if player_id not in ids:
                        file.write(f"{player_id}\n")
                if self.verbose_logs:
                    print(
                        f"Added player with id: {player_id} to ban file: {self.path_to_bans}"
                    )
                return
            except Exception as exc:  # pragma: no cover - best effort logging
                print(f"Failed to ban player: '{exc}' Try: {tries + 1}")
                tries += 1
                time.sleep(0.25)
        print(
            f"Player: {player_id} could not be added to the ban file: {self.path_to_bans}"
        )

    def get_latest_file(self) -> str:
        adm_files = glob.glob(os.path.join(self.path_to_logs_directory, "*.adm"))
        if not adm_files:
            raise FileNotFoundError(
                f"No .adm files found in {self.path_to_logs_directory}."
            )
        return max(adm_files, key=os.path.getmtime)

    def _read_log_file(self, latest_file: str) -> List[str]:
        with open(latest_file, "r", encoding="utf-8") as file:
            lines = file.read().split("\n")
        return [line for line in lines if line]

    def read_new_lines(self, lines: List[str]) -> List[str]:
        reversed_lines = list(reversed(lines))
        new_lines: List[str] = []
        for line in reversed_lines:
            if line == self.current_cache["prev_log_read"].get("line"):
                break
            new_lines.insert(0, line)
        return new_lines

    def is_death_log(self, line: str) -> bool:
        for death in self.death_cues:
            if death in line and f'"{death}' not in line and f"'{death}" not in line:
                return True
        return False

    def get_id_from_line(self, line: str) -> str:
        index = line.find("(id=")
        start_index = index + 4
        if index == -1 or len(line) < (start_index + 44):
            return ""
        player_id = line[start_index : start_index + 44]
        if "Unknown" in player_id:
            return ""
        return player_id

    def update_cache(self) -> None:
        with open(self.path_to_cache, "w", encoding="utf-8") as json_file:
            json.dump(self.current_cache, json_file, indent=4)
        if self.verbose_logs:
            print(f"Updated cache file: {self.current_cache}")

    def player_is_queued_for_ban(self, player_id: str) -> bool:
        return any(player[0] == player_id for player in self.players_to_ban)

    def _sleep_with_stop(self, seconds: float) -> None:
        remaining = seconds
        while remaining > 0 and not self.stop_event.is_set():
            sleep_inc = min(0.25, remaining)
            time.sleep(sleep_inc)
            remaining -= sleep_inc


def main() -> None:
    watcher = DeathWatcher()
    try:
        watcher.run()
    except KeyboardInterrupt:
        watcher.stop()
        print("Closing program...")
    except Exception as exc:  # pragma: no cover - CLI helper
        print(f"Ran into an unexpected exception. Error: {exc}")


if __name__ == "__main__":
    main()
