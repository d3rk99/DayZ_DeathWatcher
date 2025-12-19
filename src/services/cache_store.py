from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.models.cache import CacheState
from src.services import file_service


class CacheStore:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.state = CacheState()
        self.load()

    def load(self) -> None:
        raw = file_service.read_json(self.path)
        if raw:
            self.state = CacheState.from_dict(raw)

    def save(self) -> None:
        file_service.write_json(self.path, self.state.to_dict())

    def update(self, **kwargs) -> None:
        for key, value in kwargs.items():
            setattr(self.state, key, value)
        self.save()

    @property
    def active_file(self) -> Optional[str]:
        return self.state.activeLogFile

    @property
    def offset(self) -> int:
        return self.state.byteOffset

