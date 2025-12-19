import datetime
import os
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[1]))

import pytest

from death_watcher.new_dayz_death_watcher import (
    DEFAULT_CONFIG,
    DayZDeathWatcher,
    death_event_player_id,
    death_event_player_name,
)


@pytest.fixture
def sample_cues():
    return list(DEFAULT_CONFIG["death_cues"])


def test_death_event_player_id_accepts_valid_line(sample_cues):
    player_id = "12345678901234567890123456789012345678901234"
    line = (
        f"2024-01-01 12:00:00 PlayerOne (id={player_id}) was killed by a zombie"
    )

    assert death_event_player_id(line, sample_cues) == player_id


def test_death_event_player_id_ignores_quoted_cue(sample_cues):
    player_id = "12345678901234567890123456789012345678901234"
    line = f'2024-01-01 12:00:00 PlayerOne (id={player_id}) said "killed by a friend"'

    assert death_event_player_id(line, sample_cues) == ""


def test_death_event_player_id_rejects_unknown_and_short_ids(sample_cues):
    unknown_line = "2024-01-01 12:00:00 PlayerOne (id=Unknown) was killed by a zombie"
    short_id_line = "2024-01-01 12:00:00 PlayerOne (id=1234) was killed by a zombie"

    assert death_event_player_id(unknown_line, sample_cues) == ""
    assert death_event_player_id(short_id_line, sample_cues) == ""


def test_death_event_player_name_extracts_when_id_missing(sample_cues):
    line = '2024-01-01 12:00:00 Player "Test User" bled out in a bunker'

    assert death_event_player_name(line, sample_cues) == "Test User"


def test_log_rotation_reads_tail_and_new_file(tmp_path, sample_cues):
    watcher = DayZDeathWatcher()
    watcher.logs_directory = tmp_path
    watcher.path_to_bans = tmp_path / "bans.txt"
    watcher.path_to_cache = tmp_path / "cache.json"
    watcher.death_cues = sample_cues
    watcher.current_cache = {"prev_log_read": {"line": ""}, "log_label": ""}

    first_log = tmp_path / "server_1.adm"
    first_log.write_text("header\nfirst line\n", encoding="utf-8")

    latest = watcher._get_latest_file()
    first_lines = watcher._collect_new_lines(latest)
    assert first_lines == ["header", "first line"]

    # Append a line that has not been read yet, then rotate to a new log file.
    with first_log.open("a", encoding="utf-8") as file:
        file.write("tail line\n")

    second_log = tmp_path / "server_2.adm"
    second_log.write_text("new header\nsecond line\n", encoding="utf-8")
    future_mtime = datetime.datetime.now().timestamp() + 5
    os.utime(second_log, (future_mtime, future_mtime))

    latest = watcher._get_latest_file()
    rotation_lines = watcher._collect_new_lines(latest)

    assert rotation_lines == ["tail line", "new header", "second line"]
    assert watcher._log_state.path == second_log


def test_process_death_line_falls_back_to_session_name(tmp_path, sample_cues):
    watcher = DayZDeathWatcher()
    watcher.death_cues = sample_cues
    watcher.current_cache = {"prev_log_read": {"line": ""}, "log_label": ""}
    watcher.path_to_cache = tmp_path / "cache.json"
    watcher.path_to_bans = tmp_path / "bans.txt"

    guid = "12345678901234567890123456789012345678901234"
    watcher._guid_by_name["test user"] = guid

    line = '2024-01-01 12:00:00 Player "Test User" (DEAD) died.'
    watcher._process_death_line(line)

    assert watcher._player_is_queued_for_ban(guid)
