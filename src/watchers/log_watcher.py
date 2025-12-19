from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Optional

from src.services.cache_store import CacheStore

logger = logging.getLogger(__name__)


@dataclass
class LogLine:
    timestamp: str
    payload: dict

    @property
    def event(self) -> str:
        return self.payload.get("event", "")

    @property
    def steam64(self) -> Optional[str]:
        player = self.payload.get("player") or {}
        return player.get("steamId")

    @property
    def alive_sec(self) -> Optional[int]:
        player = self.payload.get("player") or {}
        return player.get("aliveSec")


class LogWatcher:
    def __init__(self, logs_dir: Path, cache: CacheStore):
        self.logs_dir = logs_dir
        self.cache = cache
        self.partial_line = ""
        self._stop = False

    def stop(self) -> None:
        self._stop = True

    async def watch(self) -> AsyncGenerator[LogLine, None]:
        while not self._stop:
            latest = self._latest_log_file()
            if not latest:
                await asyncio.sleep(2)
                continue

            if latest.name != self.cache.active_file:
                logger.info("Switching to new log file %s", latest.name)
                self.cache.update(activeLogFile=latest.name, byteOffset=0)
                self.partial_line = ""

            async for line in self._tail_file(latest):
                yield line
            await asyncio.sleep(1)

    def _latest_log_file(self) -> Optional[Path]:
        if not self.logs_dir.exists():
            return None
        candidates = sorted(self.logs_dir.glob("dl_*.ljson"))
        return candidates[-1] if candidates else None

    async def _tail_file(self, path: Path) -> AsyncGenerator[LogLine, None]:
        try:
            with path.open("r", encoding="utf-8") as f:
                f.seek(self.cache.offset if path.name == self.cache.active_file else 0)
                while not self._stop:
                    chunk = f.read(4096)
                    if not chunk:
                        self.cache.update(byteOffset=f.tell(), activeLogFile=path.name)
                        break
                    buffer = self.partial_line + chunk
                    lines = buffer.split("\n")
                    self.partial_line = lines.pop()  # save partial
                    for raw in lines:
                        if not raw.strip():
                            continue
                        try:
                            payload = json.loads(raw)
                            ts = payload.get("ts") or datetime.utcnow().isoformat()
                            self.cache.update(byteOffset=f.tell(), lastSeenTs=ts, activeLogFile=path.name)
                            yield LogLine(timestamp=ts, payload=payload)
                        except json.JSONDecodeError:
                            logger.exception("Failed to parse log line")
        except FileNotFoundError:
            logger.warning("Log file disappeared: %s", path)

