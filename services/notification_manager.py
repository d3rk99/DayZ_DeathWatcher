from __future__ import annotations

import threading
import time
from pathlib import Path
from typing import Callable, Iterable

try:
    from playsound import playsound
except Exception:  # pragma: no cover - playsound may be missing during tests
    playsound = None


class NotificationManager:
    """Play alert sounds whenever watched log lines include trigger phrases."""

    def __init__(
        self,
        config: dict,
        *,
        on_status: Callable[[str], None] | None = None,
        cooldown_seconds: float = 5.0,
    ) -> None:
        self._status_callback = on_status or (lambda _msg: None)
        self._cooldown = cooldown_seconds
        self._lock = threading.Lock()
        self._triggers: list[str] = []
        self._sound_path = ""
        self._last_play = 0.0
        self.update_config(config)

    def update_config(self, data: dict) -> None:
        """Refresh notification settings from the latest config snapshot."""

        triggers = data.get("restart_notification_triggers", [])
        if isinstance(triggers, str):
            triggers_list: Iterable[str] = [part.strip() for part in triggers.split(",")]
        else:
            triggers_list = (str(item).strip() for item in triggers)

        cleaned_triggers = [trigger.lower() for trigger in triggers_list if trigger]
        sound_path = str(data.get("restart_notification_sound_path", "") or "")

        with self._lock:
            self._triggers = cleaned_triggers
            self._sound_path = sound_path

    def handle_log_line(self, line: str) -> None:
        """Inspect a log line and play the alert sound when triggers match."""

        if not line:
            return

        with self._lock:
            triggers = tuple(self._triggers)
            sound_path = self._sound_path

        if not triggers or not sound_path:
            return

        lowered = line.lower()
        if not any(trigger in lowered for trigger in triggers):
            return

        self._play_sound(sound_path)

    def _play_sound(self, path: str) -> None:
        if not playsound:
            self._status_callback(
                "Cannot play notification sound because the 'playsound' package is missing.\n"
            )
            return

        resolved = Path(path)
        if not resolved.is_file():
            self._status_callback(f"Notification sound not found at: {resolved}\n")
            return

        now = time.monotonic()
        if now - self._last_play < self._cooldown:
            return

        self._last_play = now
        threading.Thread(
            target=self._play_sound_blocking, args=(str(resolved),), daemon=True
        ).start()

    def _play_sound_blocking(self, path: str) -> None:
        try:
            playsound(path)
        except Exception as exc:  # pragma: no cover - best-effort feedback
            self._status_callback(f"Failed to play notification sound: {exc}\n")
