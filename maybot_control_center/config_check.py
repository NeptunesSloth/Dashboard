"""Non-fatal startup configuration validation.

:func:`check` inspects the environment for common misconfigurations and returns
a list of human-readable warning strings. It is *advisory only*: it never
raises and never changes behaviour — startup proceeds regardless. ``app.py``
calls it once at import time and logs/prints each warning.

Every check is wrapped so a probe that itself fails (e.g. a permission error
while stat-ing a directory) is swallowed rather than surfaced as a crash.
"""
from __future__ import annotations

import os


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def _is_dev() -> bool:
    """Treat the environment as development when explicitly flagged.

    ``MAYBOT_DEV``/``MAYBOT_ENV=dev`` suppress the "auth not configured" warning
    so local runs stay quiet. Production deployments leave these unset.
    """
    if _truthy(os.getenv("MAYBOT_DEV")):
        return True
    return os.getenv("MAYBOT_ENV", "").strip().lower() in ("dev", "development", "local", "test")


def _auth_configured() -> bool:
    if os.getenv("MAYBOT_CONTROL_CENTER_TOKEN", "").strip():
        return True
    try:
        from . import authz
        return bool(authz.load_users())
    except Exception:
        # If we can't even tell, don't claim auth is missing.
        return True


def check() -> list[str]:
    """Return a list of advisory configuration warnings. Never raises."""
    warnings: list[str] = []

    # ---- Auth not configured (outside dev) ----
    try:
        if not _is_dev() and not _auth_configured():
            warnings.append(
                "Auth is not configured: set MAYBOT_CONTROL_CENTER_TOKEN or create a "
                "user account — the dashboard API is otherwise publicly accessible."
            )
    except Exception:
        pass

    # ---- MAYBOT_DB set but its directory isn't writable ----
    try:
        db = os.getenv("MAYBOT_DB", "").strip()
        if db and db != ":memory:":
            target = os.path.dirname(os.path.abspath(db)) or "."
            if os.path.isdir(target):
                if not os.access(target, os.W_OK):
                    warnings.append(
                        f"MAYBOT_DB is set to '{db}' but its directory '{target}' is not "
                        "writable — persistence will silently fail."
                    )
            else:
                warnings.append(
                    f"MAYBOT_DB is set to '{db}' but its directory '{target}' does not "
                    "exist — persistence will silently fail."
                )
    except Exception:
        pass

    # ---- Partial SMTP (email) config ----
    try:
        host = os.getenv("MAYBOT_SMTP_HOST", "").strip()
        sender = os.getenv("MAYBOT_SMTP_FROM", "").strip()
        recipients = [a for a in os.getenv("MAYBOT_SMTP_TO", "").split(",") if a.strip()]
        if (host or sender or recipients) and not (host and sender and recipients):
            missing = [name for name, present in (
                ("MAYBOT_SMTP_HOST", host),
                ("MAYBOT_SMTP_FROM", sender),
                ("MAYBOT_SMTP_TO", recipients),
            ) if not present]
            warnings.append(
                "Email notifications are partially configured; missing "
                f"{', '.join(missing)} — the email channel will stay disabled."
            )
    except Exception:
        pass

    # ---- Partial Telegram config ----
    try:
        tok = os.getenv("MAYBOT_TELEGRAM_TOKEN", "").strip()
        chat = os.getenv("MAYBOT_TELEGRAM_CHAT_ID", "").strip()
        if bool(tok) != bool(chat):
            missing = "MAYBOT_TELEGRAM_CHAT_ID" if tok else "MAYBOT_TELEGRAM_TOKEN"
            warnings.append(
                f"Telegram notifications are partially configured; missing {missing} "
                "— the telegram channel will stay disabled."
            )
    except Exception:
        pass

    # ---- Non-numeric MAYBOT_BUDGET_* ----
    try:
        for name, val in os.environ.items():
            if not name.startswith("MAYBOT_BUDGET_"):
                continue
            raw = (val or "").strip()
            if not raw:
                continue
            try:
                float(raw)
            except ValueError:
                warnings.append(
                    f"{name} is set to a non-numeric value '{raw}' — it will be ignored "
                    "or fall back to a default."
                )
    except Exception:
        pass

    return warnings
