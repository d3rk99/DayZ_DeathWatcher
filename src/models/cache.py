from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, Optional


@dataclass
class CacheState:
    activeLogFile: Optional[str] = None
    byteOffset: int = 0
    lastSeenTs: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CacheState":
        return cls(**data)

