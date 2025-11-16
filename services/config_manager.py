import json
import threading
from pathlib import Path
from typing import Any, Callable, Dict, List


class ConfigManager:
    """Thread-safe helper that loads and saves the shared config.json file."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._listeners: List[Callable[[Dict[str, Any]], None]] = []
        self._data: Dict[str, Any] = {}
        self.reload()

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
                raise FileNotFoundError(f"Config file not found: {self.path}")
            self._data = json.loads(self.path.read_text())
        self._notify_listeners()
        return self.data

    def update(self, new_data: Dict[str, Any]) -> None:
        with self._lock:
            self._data.update(new_data)
            self.path.write_text(json.dumps(self._data, indent=4))
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
