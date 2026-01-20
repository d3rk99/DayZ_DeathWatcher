"""Utilities for inspecting and updating the persistent death counter file."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict

from services.file_utils import atomic_write_text


def _default_state() -> Dict[str, int | Dict[str, Dict[str, int]]]:
    return {"count": 0, "last_reset": int(time.time()), "per_server": {}}


def _load_state(path: Path) -> Dict[str, int | Dict[str, Dict[str, int]]]:
    if not path.exists():
        state = _default_state()
        path.parent.mkdir(parents=True, exist_ok=True)
        atomic_write_text(path, json.dumps(state, indent=4))
        return state
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return _default_state()
    per_server = data.get("per_server", {})
    if not isinstance(per_server, dict):
        per_server = {}
    return {
        "count": int(data.get("count", 0)),
        "last_reset": int(data.get("last_reset", _default_state()["last_reset"])),
        "per_server": per_server,
    }


def _write_state(path: Path, state: Dict[str, int | Dict[str, Dict[str, int]]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(state, indent=4))


def get_counter_summary(path_str: str) -> Dict[str, int | Dict[str, Dict[str, int]]]:
    """Return full counter summary stored on disk."""
    path = Path(path_str)
    return _load_state(path)


def set_counter(path_str: str, count: int) -> Dict[str, int | Dict[str, Dict[str, int]]]:
    path = Path(path_str)
    state = _load_state(path)
    previous = state["count"]
    state["count"] = max(0, int(count))
    if state["count"] == 0 and previous != 0:
        state["last_reset"] = int(time.time())
    _write_state(path, state)
    return state


def adjust_counter(path_str: str, delta: int) -> Dict[str, int | Dict[str, Dict[str, int]]]:
    path = Path(path_str)
    state = _load_state(path)
    previous = state["count"]
    state["count"] = max(0, state["count"] + int(delta))
    if state["count"] == 0 and previous != 0:
        state["last_reset"] = int(time.time())
    _write_state(path, state)
    return state


def wipe_counter(path_str: str) -> Dict[str, int | Dict[str, Dict[str, int]]]:
    """Force the counter back to zero and stamp a new last_reset timestamp."""
    path = Path(path_str)
    state = _load_state(path)
    state["count"] = 0
    state["last_reset"] = int(time.time())
    for entry in state.get("per_server", {}).values():
        entry["count"] = 0
        entry["last_reset"] = int(time.time())
    _write_state(path, state)
    return state
