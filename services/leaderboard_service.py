"""Helpers for fetching leaderboard data from the web backend."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Dict, List, Tuple


def fetch_playtime_leaderboard(api_base: str, *, timeout: float = 8.0) -> Tuple[List[Dict[str, Any]], Dict[str, Any] | None]:
    """Retrieve the top playtime leaderboard and the current user's row.

    Args:
        api_base: Base URL of the backend (e.g. "http://localhost:3001").
        timeout: Number of seconds to wait before giving up on the request.

    Returns:
        A tuple of (leaderboard_rows, me_row). Each row is a dict as returned
        by the backend. "me_row" may be None if the backend does not provide
        a personal entry.
    """

    api_base = (api_base or "").rstrip("/")
    if not api_base:
        raise ValueError("Leaderboard API URL is not configured.")

    url = f"{api_base}/leaderboards/playtime"
    request = urllib.request.Request(url, headers={"Accept": "application/json"})

    try:
        with urllib.request.urlopen(request, timeout=timeout) as resp:  # noqa: S310
            payload = resp.read().decode("utf-8")
            data = json.loads(payload)
            leaderboard = data.get("leaderboard") or []
            me = data.get("me") or None
            return leaderboard, me
    except urllib.error.HTTPError as exc:  # pragma: no cover - network
        raise RuntimeError(f"Leaderboard request failed ({exc.code})") from exc
    except urllib.error.URLError as exc:  # pragma: no cover - network
        raise RuntimeError(f"Unable to reach leaderboard API: {exc.reason}") from exc
    except (json.JSONDecodeError, OSError) as exc:
        raise RuntimeError("Received an invalid response from the leaderboard API.") from exc


__all__ = ["fetch_playtime_leaderboard"]
