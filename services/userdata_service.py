import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _read_json(path: Path) -> Dict:
    if not path.exists():
        return {"userdata": {}, "season_deaths": []}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError:
        return {"userdata": {}, "season_deaths": []}


def load_userdata(path: str) -> Dict:
    return _read_json(Path(path))


def list_dead_players(
    path: str, *, default_wait_seconds: Optional[int] = None
) -> List[Dict[str, str]]:
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
                    "revival_eta": _calculate_revive_eta(
                        info, default_wait_seconds=default_wait_seconds
                    ),
                }
            )
    return result


def _calculate_revive_eta(
    info: Dict, *, default_wait_seconds: Optional[int] = None
) -> str:
    wait_seconds_raw = info.get("revive_wait")
    if wait_seconds_raw in (None, "", 0):
        wait_seconds_raw = default_wait_seconds
    try:
        wait_seconds = int(wait_seconds_raw)
    except (TypeError, ValueError):
        return "Unknown"
    if wait_seconds <= 0:
        return "Unknown"
    time_of_death = int(info.get("time_of_death", 0))
    if not time_of_death:
        return "Unknown"
    eta = time_of_death + wait_seconds
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(eta))
    except (ValueError, OSError):
        return "Unknown"


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


def force_revive_all(path: str) -> int:
    data = _read_json(Path(path))
    season_deaths = data.get("season_deaths")
    if not isinstance(season_deaths, list):
        season_deaths = []
        data["season_deaths"] = season_deaths

    revived = 0
    for discord_id, user in data.get("userdata", {}).items():
        changed = False
        if int(user.get("is_alive", 1)) != 1:
            user["is_alive"] = 1
            changed = True
        if user.get("time_of_death"):
            user["time_of_death"] = 0
            changed = True
        if int(user.get("revive_wait", 0)) != 0:
            user["revive_wait"] = 0
            changed = True
        if changed:
            revived += 1
            if discord_id in season_deaths:
                season_deaths.remove(discord_id)

    if revived:
        _save_userdata(Path(path), data)
    return revived


def force_mark_dead(path: str, discord_id: str) -> bool:
    def updater(user: Dict) -> bool:
        user["is_alive"] = 0
        user["time_of_death"] = int(time.time())
        return True

    return _modify_user(Path(path), discord_id, updater)[0]


def remove_user(path: str, discord_id: str) -> bool:
    data = _read_json(Path(path))
    if discord_id not in data.get("userdata", {}):
        return False
    data["userdata"].pop(discord_id, None)
    season_deaths = data.get("season_deaths")
    if isinstance(season_deaths, list) and discord_id in season_deaths:
        season_deaths.remove(discord_id)
    _save_userdata(Path(path), data)
    return True


def _match_user_by_identifier(data: Dict, steam_id: Optional[str], guid: Optional[str]):
    userdata = data.get("userdata", {})
    for discord_id, user in userdata.items():
        if steam_id and str(user.get("steam_id")) == str(steam_id):
            return discord_id, user
        if guid and user.get("guid") == guid:
            return discord_id, user
    return None, None


def set_alive_time_seconds(
    path: str,
    *,
    steam_id: Optional[str] = None,
    guid: Optional[str] = None,
    alive_seconds: Optional[int] = None,
) -> bool:
    """Persist the latest recorded alive time for a player."""

    if alive_seconds is None:
        return False

    data = _read_json(Path(path))
    _, user = _match_user_by_identifier(data, steam_id, guid)
    if not user:
        return False

    try:
        user["alive_time_seconds"] = max(0, int(alive_seconds))
    except (TypeError, ValueError):
        return False

    _save_userdata(Path(path), data)
    return True


def get_alive_time_leaderboard(path: str, top_n: int = 10) -> List[Dict[str, str]]:
    """Return the top players by recorded alive time."""

    data = _read_json(Path(path))
    entries: List[Dict[str, str]] = []
    for discord_id, user in data.get("userdata", {}).items():
        alive_seconds = user.get("alive_time_seconds")
        if alive_seconds in (None, ""):
            continue
        try:
            duration = int(alive_seconds)
        except (TypeError, ValueError):
            continue
        entries.append(
            {
                "discord_id": discord_id,
                "username": user.get("username", "Unknown"),
                "steam_id": user.get("steam_id", ""),
                "alive_time_seconds": duration,
                "is_alive": int(user.get("is_alive", 1)),
            }
        )

    entries.sort(key=lambda entry: entry["alive_time_seconds"], reverse=True)
    return entries[:top_n]


def wipe_database(path: str) -> bool:
    """Completely reset the userdata database file."""
    try:
        payload = {"userdata": {}, "season_deaths": []}
        _save_userdata(Path(path), payload)
        return True
    except OSError:
        return False


def list_admins(path: str) -> List[Dict[str, str]]:
    """Return metadata for every user currently flagged as an admin."""
    data = load_userdata(path)
    admins: List[Dict[str, str]] = []
    for discord_id, info in data.get("userdata", {}).items():
        if int(info.get("is_admin", 0)) != 1:
            continue
        admins.append(
            {
                "discord_id": discord_id,
                "username": info.get("username", "Unknown"),
                "steam_id": info.get("steam_id", ""),
            }
        )
    admins.sort(key=lambda entry: entry.get("username", "").lower())
    return admins


def list_all_users(path: str) -> List[Dict[str, str]]:
    """Return lightweight metadata for every user in the database."""

    data = load_userdata(path)
    entries: List[Dict[str, str]] = []
    for discord_id, info in data.get("userdata", {}).items():
        entries.append(
            {
                "discord_id": discord_id,
                "username": info.get("username", "Unknown"),
                "steam_id": info.get("steam_id", ""),
                "is_admin": info.get("is_admin", 0),
            }
        )
    entries.sort(key=lambda entry: entry.get("username", "").lower())
    return entries


def set_admin_status(path: str, discord_id: str, is_admin: bool) -> Tuple[bool, str]:
    """Toggle the admin flag for a specific Discord ID."""

    data = _read_json(Path(path))
    user = data.get("userdata", {}).get(discord_id)
    if user is None:
        return False, "User not found in the database."

    desired_value = 1 if is_admin else 0
    current_value = int(user.get("is_admin", 0))
    if current_value == desired_value:
        if is_admin:
            return False, f"{user.get('username', discord_id)} is already marked as an admin."
        return False, f"{user.get('username', discord_id)} is not currently marked as an admin."

    user["is_admin"] = desired_value
    _save_userdata(Path(path), data)
    action = "now an admin" if is_admin else "no longer an admin"
    return True, f"{user.get('username', discord_id)} is {action}."
