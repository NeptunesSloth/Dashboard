"""Spirit veins & the sect treasury — a shared spirit-stone budget.

The sect holds a common pool of spirit stones. **Spirit veins** channel ambient
qi into it over time (passive income), and a small **tithe** flows in from each
disciple's productive work. The treasury **funds the daily stipend** — when it
runs dry, stipends stop until the veins (or an elder's endowment) refill it.
Persisted via store when MAYBOT_DB is set.
"""
from __future__ import annotations

import os
import threading
import time

from . import store

VEIN_RATE = int(os.getenv("MAYBOT_VEIN_RATE", "30"))                      # stones per period
VEIN_SECONDS = max(1, int(os.getenv("MAYBOT_VEIN_HOURS", "1"))) * 3600    # length of a vein period
START_BALANCE = int(os.getenv("MAYBOT_TREASURY_START", "500"))

_lock = threading.Lock()
_balance = START_BALANCE
_last = time.time()
_income = 0
_spent = 0


def _accrue_locked() -> None:
    global _balance, _last, _income
    now = time.time()
    if VEIN_RATE > 0 and now - _last >= VEIN_SECONDS:
        periods = int((now - _last) // VEIN_SECONDS)
        gain = periods * VEIN_RATE
        _balance += gain
        _income += gain
        _last += periods * VEIN_SECONDS


def _persist_locked() -> None:
    if store.enabled():
        store.set_treasury(_balance, _last, _income, _spent)


def balance() -> int:
    with _lock:
        _accrue_locked()
        _persist_locked()
        return _balance


def withdraw(amount: int) -> bool:
    global _balance, _spent
    with _lock:
        _accrue_locked()
        if _balance >= amount:
            _balance -= amount
            _spent += amount
            _persist_locked()
            return True
        return False


def deposit(amount: int) -> None:
    global _balance, _income
    with _lock:
        _accrue_locked()
        _balance += amount
        _income += amount
        _persist_locked()


def status() -> dict:
    with _lock:
        _accrue_locked()
        return {"balance": _balance, "income_per_hour": round(VEIN_RATE * 3600 / VEIN_SECONDS, 1),
                "total_income": _income, "total_spent": _spent, "vein_rate": VEIN_RATE}


def load_persisted() -> None:
    global _balance, _last, _income, _spent
    if not store.enabled():
        return
    row = store.get_treasury()
    if row:
        _balance, _last, _income, _spent = int(row[0]), float(row[1]), int(row[2]), int(row[3])


def clear() -> None:
    global _balance, _last, _income, _spent
    with _lock:
        _balance, _last, _income, _spent = START_BALANCE, time.time(), 0, 0
