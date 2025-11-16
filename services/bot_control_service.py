"""Bridge helpers that let the GUI control the running Discord bot."""
from __future__ import annotations

import asyncio
import sys
from typing import Callable, Tuple

from services import death_counter_service, userdata_service

_DEFAULT_TIMEOUT = 10.0


def _get_main_module():
    module = sys.modules.get("__main__")
    if module is None:
        raise RuntimeError("Main module has not been initialized yet.")
    return module


def _get_bot_loop():
    module = _get_main_module()
    client = getattr(module, "client", None)
    loop = getattr(client, "loop", None) if client else None
    if loop and loop.is_running():
        return loop
    return None


def _run_in_loop(factory: Callable[[], "asyncio.Future"], timeout: float = _DEFAULT_TIMEOUT):
    loop = _get_bot_loop()
    if loop is None:
        raise RuntimeError("The Discord bot is not running.")
    future = asyncio.run_coroutine_threadsafe(factory(), loop)
    return future.result(timeout=timeout)


def is_bot_running() -> bool:
    return _get_bot_loop() is not None


def get_death_counter(path: str) -> Tuple[int, int, bool]:
    module = _get_main_module()
    coro = getattr(module, "get_death_counter_value", None)
    loop = _get_bot_loop()
    if coro and loop:
        count, last_reset = _run_in_loop(coro)
        return count, last_reset, True
    count, last_reset = death_counter_service.get_counter(path)
    return count, last_reset, False


def set_death_counter(path: str, count: int) -> Tuple[int, int, bool]:
    module = _get_main_module()
    coro = getattr(module, "set_death_counter_value", None)
    loop = _get_bot_loop()
    if coro and loop:
        new_count, last_reset = _run_in_loop(lambda: coro(count))
        return new_count, last_reset, True
    new_count, last_reset = death_counter_service.set_counter(path, count)
    return new_count, last_reset, False


def adjust_death_counter(path: str, delta: int) -> Tuple[int, int, bool]:
    module = _get_main_module()
    coro = getattr(module, "adjust_death_counter", None)
    loop = _get_bot_loop()
    if coro and loop:
        count, last_reset = _run_in_loop(lambda: coro(delta))
        return count, last_reset, True
    count, last_reset = death_counter_service.adjust_counter(path, delta)
    return count, last_reset, False


def wipe_death_counter(path: str) -> Tuple[int, int, bool]:
    module = _get_main_module()
    coro = getattr(module, "reset_death_counter", None)
    loop = _get_bot_loop()
    if coro and loop:
        count, last_reset = _run_in_loop(coro)
        return count, last_reset, True
    count, last_reset = death_counter_service.wipe_counter(path)
    return count, last_reset, False


def refresh_activity() -> None:
    module = _get_main_module()
    coro = getattr(module, "update_bot_activity", None)
    if coro is None:
        raise RuntimeError("Unable to find the activity updater.")
    _run_in_loop(coro)


def force_revive_user(path: str, discord_id: str) -> bool:
    module = _get_main_module()
    coro = getattr(module, "unban_user", None)
    loop = _get_bot_loop()
    if coro and loop:
        _run_in_loop(lambda: coro(discord_id))
        return True
    return userdata_service.force_revive(path, discord_id)


def force_revive_all_users(path: str) -> int:
    module = _get_main_module()
    coro = getattr(module, "bulk_revive_dead_users", None)
    loop = _get_bot_loop()
    if coro and loop:
        return _run_in_loop(coro)
    return userdata_service.force_revive_all(path)


def force_mark_dead(path: str, discord_id: str) -> bool:
    module = _get_main_module()
    coro = getattr(module, "set_user_as_dead", None)
    loop = _get_bot_loop()
    if coro and loop:
        _run_in_loop(lambda: coro(discord_id))
        return True
    return userdata_service.force_mark_dead(path, discord_id)


def remove_user_from_database(path: str, discord_id: str) -> bool:
    return userdata_service.remove_user(path, discord_id)
