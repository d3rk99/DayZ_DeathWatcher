from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def _coerce_server_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _expand(path: str) -> str:
    import os

    return os.path.abspath(os.path.expanduser(path or ""))


def derive_paths_from_root(root_path: str) -> Dict[str, str]:
    root = _expand(root_path)
    if not root:
        return {}
    return {
        "path_to_logs_directory": str(Path(root) / "profiles" / "DetailedLogs"),
        "path_to_bans": str(Path(root) / "ban.txt"),
        "path_to_whitelist": str(Path(root) / "whitelist.txt"),
    }


def apply_server_root(entry: Dict[str, Any]) -> Dict[str, Any]:
    root = entry.get("server_root_path")
    if not root:
        return entry
    derived = derive_paths_from_root(str(root))
    for key, value in derived.items():
        if not entry.get(key):
            entry[key] = value
    return entry

def _legacy_logs_path(config: Dict[str, Any]) -> str:
    config_path = config.get("death_watcher_config_path") or "./death_watcher/config.json"
    if not config_path:
        return ""
    try:
        data = json.loads(Path(config_path).read_text())
    except Exception:
        return ""
    return str(data.get("path_to_logs_directory", ""))


def normalize_servers(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    servers = config.get("servers")
    if isinstance(servers, list) and servers:
        normalized: List[Dict[str, Any]] = []
        for entry in servers:
            if not isinstance(entry, dict):
                continue
            server_id = _coerce_server_id(entry.get("server_id") or entry.get("id") or "")
            if not server_id:
                continue
            normalized.append(
                apply_server_root(
                    {
                        "server_id": server_id,
                        "display_name": entry.get("display_name") or f"Server {server_id}",
                        "server_root_path": entry.get("server_root_path", ""),
                        "path_to_logs_directory": entry.get("path_to_logs_directory", ""),
                        "path_to_bans": entry.get("path_to_bans", ""),
                        "path_to_whitelist": entry.get("path_to_whitelist", ""),
                        "death_watcher_death_path": entry.get("death_watcher_death_path", ""),
                        "enable_death_scanning": entry.get("enable_death_scanning"),
                        "enabled": bool(entry.get("enabled", True)),
                    }
                )
            )
        return normalized

    legacy_server_id = _coerce_server_id(config.get("default_server_id") or 1)
    death_path = config.get("death_watcher_death_path", "")
    legacy = {
        "server_id": legacy_server_id,
        "display_name": "Server 1",
        "server_root_path": "",
        "path_to_logs_directory": _legacy_logs_path(config),
        "path_to_bans": config.get("blacklist_path", ""),
        "path_to_whitelist": config.get("whitelist_path", ""),
        "death_watcher_death_path": death_path,
        "enable_death_scanning": config.get("enable_death_scanning"),
        "enabled": True,
    }
    return [apply_server_root(legacy)]


def ensure_server_defaults(
    servers: Iterable[Dict[str, Any]],
    *,
    default_logs_directory: str = "",
    default_death_path_template: str = "./death_watcher/deaths_{server_id}.txt",
) -> List[Dict[str, Any]]:
    normalized: List[Dict[str, Any]] = []
    for entry in servers:
        server_id = _coerce_server_id(entry.get("server_id"))
        if not server_id:
            continue
        entry = apply_server_root(dict(entry))
        death_path = entry.get("death_watcher_death_path") or default_death_path_template.format(
            server_id=server_id
        )
        normalized.append(
            {
                "server_id": server_id,
                "display_name": entry.get("display_name") or f"Server {server_id}",
                "server_root_path": entry.get("server_root_path", ""),
                "path_to_logs_directory": entry.get("path_to_logs_directory")
                or default_logs_directory,
                "path_to_bans": entry.get("path_to_bans", ""),
                "path_to_whitelist": entry.get("path_to_whitelist", ""),
                "death_watcher_death_path": death_path,
                "enable_death_scanning": entry.get("enable_death_scanning"),
                "enabled": bool(entry.get("enabled", True)),
            }
        )
    return normalized


def get_default_server_id(config: Dict[str, Any], servers: List[Dict[str, Any]]) -> str:
    fallback = servers[0]["server_id"] if servers else "1"
    return _coerce_server_id(config.get("default_server_id") or fallback)


def get_enabled_servers(servers: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [server for server in servers if bool(server.get("enabled", True))]


def get_active_servers(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    servers = normalize_servers(config)
    enabled = get_enabled_servers(servers)
    try:
        max_count = int(config.get("max_active_servers", len(enabled)))
    except (TypeError, ValueError):
        max_count = len(enabled)
    if max_count <= 0:
        return []
    return enabled[:max_count]


def server_map(servers: Iterable[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    return {str(server.get("server_id")): server for server in servers if server.get("server_id")}


def resolve_server_id(
    candidate: Optional[str], *, fallback: str, enabled_ids: Iterable[str]
) -> str:
    enabled = {str(server_id) for server_id in enabled_ids}
    if candidate and str(candidate) in enabled:
        return str(candidate)
    if fallback in enabled:
        return fallback
    return next(iter(enabled), fallback)


def get_unban_scope(config: Dict[str, Any]) -> str:
    return str(config.get("unban_scope") or "active_server_only")


def get_validate_scope(config: Dict[str, Any]) -> str:
    return str(config.get("validate_whitelist_scope") or "all_servers")


def resolve_user_server_ids(
    *,
    scope: str,
    userdata: Dict[str, Any],
    servers: Iterable[Dict[str, Any]],
    default_server_id: str,
) -> List[str]:
    enabled = get_enabled_servers(list(servers))
    enabled_ids = [str(server["server_id"]) for server in enabled]
    if not enabled_ids:
        return []
    scope_key = scope or "active_server_only"
    if scope_key == "all_servers":
        return enabled_ids
    if scope_key == "user_home_server":
        candidate = userdata.get("home_server_id") or userdata.get("active_server_id")
    else:
        candidate = userdata.get("active_server_id")
    selected = resolve_server_id(
        str(candidate) if candidate else None,
        fallback=default_server_id,
        enabled_ids=enabled_ids,
    )
    return [selected]
