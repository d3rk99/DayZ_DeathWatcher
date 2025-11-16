import json
import time
from pathlib import Path
from typing import Dict, List, Tuple


def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {"userdata": {}, "season_deaths": []}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"userdata": {}, "season_deaths": []}


def load_userdata(path: str) -> Dict:
    return _read_json(Path(path))


def list_dead_players(path: str) -> List[Dict[str, str]]:
    data = load_userdata(path)
    result: List[Dict[str, str]] = []
    for discord_id, info in data.get("userdata", {}).items():
        if int(info.get("is_alive", 1)) == 0:
            result.append(
                {
                    "discord_id": discord_id,
                    "discord_name": info.get("username", "Unknown"),
                    "steam64": info.get("steam_id", ""),
                    "time_of_death": info.get("time_of_death", 0),
                    "alive_status": "Dead" if int(info.get("is_alive", 0)) == 0 else "Alive",
                    "revival_eta": _calculate_revive_eta(info),
                }
            )
    return result


def _calculate_revive_eta(info: Dict) -> str:
    wait_seconds = info.get("revive_wait", 0)
    if not wait_seconds:
        return "Unknown"
    time_of_death = int(info.get("time_of_death", 0))
    if not time_of_death:
        return "Unknown"
    eta = time_of_death + int(wait_seconds)
    now = int(time.time())
    remaining = max(0, eta - now)
    minutes, seconds = divmod(remaining, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m"
    return f"{seconds}s"


def _save_userdata(path: Path, data: Dict) -> None:
    path.write_text(json.dumps(data, indent=4))


def _modify_user(path: Path, discord_id: str, updater) -> Tuple[bool, Dict]:
    data = _read_json(path)
    user = data.get("userdata", {}).get(discord_id)
    if user is None:
        return False, data
    updated = updater(user)
    if updated:
        _save_userdata(path, data)
    return updated, data


def force_revive(path: str, discord_id: str) -> bool:
    def updater(user: Dict) -> bool:
        changed = False
        if int(user.get("is_alive", 1)) != 1:
            user["is_alive"] = 1
            changed = True
        if user.get("time_of_death"):
            user["time_of_death"] = 0
            changed = True
        user["revive_wait"] = 0
        return changed

    return _modify_user(Path(path), discord_id, updater)[0]


def force_mark_dead(path: str, discord_id: str) -> bool:
    def updater(user: Dict) -> bool:
        user["is_alive"] = 0
        user["time_of_death"] = int(time.time())
        return True

    return _modify_user(Path(path), discord_id, updater)[0]


def remove_user(path: str, discord_id: str) -> bool:
    data = _read_json(Path(path))
    if discord_id in data.get("userdata", {}):
        data["userdata"].pop(discord_id)
        _save_userdata(Path(path), data)
        return True
    return False


def wipe_database(path: str) -> bool:
    """Completely reset the userdata database file."""
    try:
        payload = {"userdata": {}, "season_deaths": []}
        _save_userdata(Path(path), payload)
        return True
    except OSError:
        return False
