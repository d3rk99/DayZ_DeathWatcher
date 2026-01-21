from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from services.file_utils import atomic_write_lines, atomic_write_text, read_lines
from services.server_config import get_enabled_servers


SYNC_STATUS_FILENAME = ".sync_status.json"


def _normalize_steam64(value: str) -> str:
    value = str(value or "").strip()
    return value if value.isdigit() and len(value) == 17 else ""


def _unique_sorted(values: Iterable[str]) -> List[str]:
    cleaned = [value for value in values if value]
    return sorted(set(cleaned))


def compute_global_lists(userdata: Dict) -> Tuple[List[str], List[str]]:
    whitelist: List[str] = []
    banlist: List[str] = []
    users = userdata.get("userdata", {}) if isinstance(userdata, dict) else {}
    for entry in users.values():
        steam64 = _normalize_steam64(entry.get("steam64"))
        if not steam64:
            continue
        whitelist.append(steam64)
        is_dead = int(entry.get("is_alive", 1)) == 0
        in_correct_vc = bool(entry.get("inCorrectVC", False))
        if is_dead or not in_correct_vc:
            banlist.append(steam64)
    return _unique_sorted(whitelist), _unique_sorted(banlist)


def _merge_preserve_order(existing: List[str], new_items: List[str]) -> List[str]:
    seen = set(existing)
    merged = list(existing)
    for item in new_items:
        if item in seen:
            continue
        merged.append(item)
        seen.add(item)
    return merged


def _write_sync_outputs(sync_dir: Path, whitelist: List[str], banlist: List[str]) -> None:
    sync_dir.mkdir(parents=True, exist_ok=True)
    whitelist_path = sync_dir / "whitelist.txt"
    ban_path = sync_dir / "ban.txt"
    existing_whitelist = read_lines(whitelist_path)
    existing_banlist = read_lines(ban_path)
    atomic_write_lines(whitelist_path, _merge_preserve_order(existing_whitelist, whitelist))
    atomic_write_lines(ban_path, _merge_preserve_order(existing_banlist, banlist))


def _copy_to_servers(
    servers: Iterable[Dict],
    whitelist: List[str],
    banlist: List[str],
) -> None:
    for server in get_enabled_servers(list(servers)):
        whitelist_path = server.get("path_to_whitelist", "")
        ban_path = server.get("path_to_bans", "")
        if whitelist_path:
            atomic_write_lines(whitelist_path, whitelist)
        if ban_path:
            atomic_write_lines(ban_path, banlist)


def _write_status(sync_dir: Path, payload: Dict) -> None:
    path = sync_dir / SYNC_STATUS_FILENAME
    atomic_write_text(path, json.dumps(payload, indent=4))


def sync_global_lists(config: Dict, *, userdata: Dict) -> Dict:
    sync_dir_value = str(config.get("path_to_sync_dir") or "").strip()
    if not sync_dir_value:
        raise ValueError("path_to_sync_dir is not configured.")
    sync_dir = Path(sync_dir_value)

    whitelist, banlist = compute_global_lists(userdata)
    payload: Dict[str, object] = {
        "last_sync_time": int(time.time()),
        "whitelist_count": len(whitelist),
        "ban_count": len(banlist),
        "last_sync_result": "success",
        "last_error": "",
    }

    try:
        _write_sync_outputs(sync_dir, whitelist, banlist)
        _copy_to_servers(config.get("servers", []), whitelist, banlist)
    except Exception as exc:  # pragma: no cover - runtime safety
        payload["last_sync_result"] = "failed"
        payload["last_error"] = str(exc)
        _write_status(sync_dir, payload)
        raise

    _write_status(sync_dir, payload)
    return payload


def load_sync_status(sync_dir: str) -> Dict:
    if not sync_dir:
        return {}
    path = Path(sync_dir) / SYNC_STATUS_FILENAME
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}
