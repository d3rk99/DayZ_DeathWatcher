from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from src.models.user import UserRecord
from src.services import file_service


class UserDatabase:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.users: Dict[str, UserRecord] = {}
        self.load()

    def load(self) -> None:
        raw = file_service.read_json(self.path)
        self.users = {k: UserRecord.from_dict(v) for k, v in raw.items()}

    def save(self) -> None:
        data = {steam: user.to_dict() for steam, user in self.users.items()}
        file_service.write_json(self.path, data)

    def upsert(self, user: UserRecord) -> None:
        self.users[user.steam64] = user
        self.save()

    def get_by_steam(self, steam64: str) -> Optional[UserRecord]:
        return self.users.get(steam64)

    def get_by_discord(self, discord_id: int) -> Optional[UserRecord]:
        return next((u for u in self.users.values() if u.discordId == discord_id), None)

    def mark_validated(self, steam64: str, discord_id: int) -> UserRecord:
        now = datetime.utcnow().isoformat()
        user = self.users.get(steam64)
        if user:
            user.discordId = discord_id
            user.validatedAt = now
        else:
            user = UserRecord(
                steam64=steam64,
                discordId=discord_id,
                validatedAt=now,
            )
        self.upsert(user)
        return user

    def mark_death(self, steam64: str, ts: str, dead_until: datetime, alive_sec: int | None) -> Optional[UserRecord]:
        user = self.users.get(steam64)
        if not user:
            return None
        user.mark_death(ts, dead_until, alive_sec)
        self.save()
        return user

    def revive(self, user: UserRecord) -> None:
        user.revive()
        self.save()

