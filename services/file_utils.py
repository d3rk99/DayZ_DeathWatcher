from __future__ import annotations

import os
import threading
import time
import uuid
from pathlib import Path
from typing import Iterable, List

_LOCKS: dict[str, threading.Lock] = {}
_LOCKS_GUARD = threading.Lock()


def _get_lock_key(path: str | Path) -> str:
    return str(Path(path).resolve())


def get_file_lock(path: str | Path) -> threading.Lock:
    key = _get_lock_key(path)
    with _LOCKS_GUARD:
        if key not in _LOCKS:
            _LOCKS[key] = threading.Lock()
        return _LOCKS[key]


def read_lines(path: str | Path) -> List[str]:
    file_path = Path(path)
    if not file_path.exists():
        return []
    with get_file_lock(file_path):
        return [line.strip() for line in file_path.read_text().splitlines()]


def atomic_write_text(path: str | Path, text: str, *, retries: int = 5, retry_delay: float = 0.2) -> None:
    file_path = Path(path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = file_path.with_name(f".{file_path.name}.{uuid.uuid4().hex}.tmp")
    with get_file_lock(file_path):
        temp_path.write_text(text)
        attempt = 0
        while True:
            try:
                os.replace(temp_path, file_path)
                break
            except PermissionError:
                attempt += 1
                if attempt > retries:
                    raise
                time.sleep(retry_delay)


def atomic_write_lines(path: str | Path, lines: Iterable[str]) -> None:
    atomic_write_text(path, "\n".join(lines))
