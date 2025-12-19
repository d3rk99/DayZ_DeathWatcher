from __future__ import annotations

from pathlib import Path
from typing import Set

from src.services import file_service


class BanAndWhitelistService:
    def __init__(self, banlist_path: Path, whitelist_path: Path) -> None:
        self.banlist_path = banlist_path
        self.whitelist_path = whitelist_path

    def _read_set(self, path: Path) -> Set[str]:
        return set(file_service.read_lines(path))

    def _write_set(self, path: Path, entries: Set[str]) -> None:
        file_service.write_lines(path, sorted(entries))

    def add_to_whitelist(self, steam64: str) -> None:
        entries = self._read_set(self.whitelist_path)
        entries.add(steam64)
        self._write_set(self.whitelist_path, entries)

    def add_to_ban(self, steam64: str) -> None:
        entries = self._read_set(self.banlist_path)
        entries.add(steam64)
        self._write_set(self.banlist_path, entries)

    def remove_from_ban(self, steam64: str) -> None:
        entries = self._read_set(self.banlist_path)
        if steam64 in entries:
            entries.remove(steam64)
            self._write_set(self.banlist_path, entries)

