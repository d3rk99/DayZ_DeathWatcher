import csv
import io
import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Tuple

from services.file_utils import atomic_write_text

CAUSE_PATTERNS: Dict[str, List[str]] = {
    "Firearm": ["shot", "rifle", "gun", "m4"],
    "Melee": ["knife", "sword", "axe", "melee"],
    "Zombie": ["infected", "zombie"],
    "Fall": ["fall", "fell"],
    "Explosive": ["grenade", "explosion", "explosive"],
}


@dataclass
class DeathEvent:
    timestamp: float
    raw: str
    cause: str


class AnalyticsManager:
    def __init__(self, max_events: int = 200) -> None:
        self.max_events = max_events
        self._events: List[DeathEvent] = []

    def record_line(self, line: str) -> bool:
        """Attempt to extract a death event from the provided log line."""
        cause = self._detect_cause(line)
        if cause is None:
            return False
        event = DeathEvent(timestamp=time.time(), raw=line.strip(), cause=cause)
        self._events.append(event)
        if len(self._events) > self.max_events:
            self._events = self._events[-self.max_events :]
        return True

    def _detect_cause(self, line: str) -> str | None:
        lower = line.lower()
        if "death" not in lower and "killed" not in lower:
            return None
        for label, keywords in CAUSE_PATTERNS.items():
            if any(word in lower for word in keywords):
                return label
        return "Unknown"

    @property
    def events(self) -> List[DeathEvent]:
        return list(self._events)

    def export(self, path: str, fmt: str = "json") -> None:
        path_obj = Path(path)
        if fmt == "json":
            payload = [event.__dict__ for event in self._events]
            atomic_write_text(path_obj, json.dumps(payload, indent=2))
        elif fmt == "csv":
            buffer = io.StringIO()
            writer = csv.writer(buffer)
            writer.writerow(["timestamp", "cause", "raw"])
            for event in self._events:
                writer.writerow([event.timestamp, event.cause, event.raw])
            atomic_write_text(path_obj, buffer.getvalue())
        else:
            raise ValueError(f"Unsupported format: {fmt}")

    def timeline(self) -> Tuple[List[float], List[int]]:
        times = [event.timestamp for event in self._events]
        counts = list(range(1, len(times) + 1))
        return times, counts

    def cause_breakdown(self) -> Dict[str, int]:
        breakdown: Dict[str, int] = {label: 0 for label in list(CAUSE_PATTERNS) + ["Unknown"]}
        for event in self._events:
            breakdown[event.cause] = breakdown.get(event.cause, 0) + 1
        return breakdown
