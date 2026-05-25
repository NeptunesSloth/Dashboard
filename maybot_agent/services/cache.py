from __future__ import annotations
import time
from typing import Any, Callable

_store: dict[tuple, tuple[Any, float]] = {}


def cached(key: tuple, ttl: float, fn: Callable, *args, **kwargs) -> Any:
    now = time.monotonic()
    entry = _store.get(key)
    if entry is not None:
        val, ts = entry
        if now - ts < ttl:
            return val
    val = fn(*args, **kwargs)
    _store[key] = (val, now)
    return val
