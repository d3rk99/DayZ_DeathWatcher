from __future__ import annotations

import json
from pathlib import Path
from typing import Dict


def load_log_status(cache_path: str) -> Dict[str, Dict]:
    if not cache_path:
        return {}
    path = Path(cache_path)
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return {}
    servers = payload.get("servers", {})
    if not isinstance(servers, dict):
        return {}
    return servers
