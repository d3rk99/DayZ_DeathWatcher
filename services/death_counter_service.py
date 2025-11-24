"""Utilities for inspecting and updating the persistent death counter file."""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Tuple


def _default_state() -> Dict[str, int]:
    return {"count": 0, "last_reset": int(time.time())}


def _load_state(path: Path) -> Dict[str, int]:
    if not path.exists():
        state = _default_state()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state, indent=4))
        return state
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return _default_state()
    return {
        "count": int(data.get("count", 0)),
        "last_reset": int(data.get("last_reset", _default_state()["last_reset"])),
    }


def _write_state(path: Path, state: Dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(state, indent=4))


def get_counter(path_str: str) -> Tuple[int, int]:
    """Return (count, last_reset) stored on disk."""
    path = Path(path_str)
    state = _load_state(path)
    return state["count"], state["last_reset"]


def set_counter(path_str: str, count: int) -> Tuple[int, int]:
    path = Path(path_str)
    state = _load_state(path)
    previous = state["count"]
    state["count"] = max(0, int(count))
    if state["count"] == 0 and previous != 0:
        state["last_reset"] = int(time.time())
    _write_state(path, state)
    return state["count"], state["last_reset"]


def adjust_counter(path_str: str, delta: int) -> Tuple[int, int]:
    path = Path(path_str)
    state = _load_state(path)
    previous = state["count"]
    state["count"] = max(0, state["count"] + int(delta))
    if state["count"] == 0 and previous != 0:
        state["last_reset"] = int(time.time())
    _write_state(path, state)
    return state["count"], state["last_reset"]


def wipe_counter(path_str: str) -> Tuple[int, int]:
    """Force the counter back to zero and stamp a new last_reset timestamp."""
    path = Path(path_str)
    state = _load_state(path)
    state["count"] = 0
    state["last_reset"] = int(time.time())
    _write_state(path, state)
    return state["count"], state["last_reset"]


def set_last_reset(path_str: str, timestamp: int) -> Tuple[int, int]:
    """Persist a custom last_reset value without altering the counter."""
    path = Path(path_str)
    state = _load_state(path)
    state["last_reset"] = max(0, int(timestamp))
    _write_state(path, state)
    return state["count"], state["last_reset"]
