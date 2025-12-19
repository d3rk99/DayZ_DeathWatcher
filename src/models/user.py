from __future__ import annotations

from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, Optional


@dataclass
class UserRecord:
    steam64: str
    discordId: int
    validatedAt: str
    isDead: bool = False
    deadUntil: Optional[str] = None
    lastAliveSec: Optional[int] = None
    lastDeathAt: Optional[str] = None
    privateVcId: Optional[int] = None
    lastVoiceState: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UserRecord":
        return cls(**data)

    def mark_death(self, ts: str, dead_until: datetime, alive_sec: int | None) -> None:
        self.isDead = True
        self.deadUntil = dead_until.isoformat()
        self.lastDeathAt = ts
        self.lastAliveSec = alive_sec

    def revive(self) -> None:
        self.isDead = False
        self.deadUntil = None
        self.lastVoiceState = None

