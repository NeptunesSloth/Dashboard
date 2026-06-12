"""In-app settings — manage select environment-backed config from the dashboard.

Values are persisted in the store (needs ``MAYBOT_DB``), masked in the UI when
secret, and applied at runtime: pushed into ``os.environ`` (for settings read
fresh at call time) and into the relevant module globals (for settings cached at
import), so an operator can change them without editing ``.env`` or restarting.
An in-app value takes precedence over the environment default.
"""
from __future__ import annotations

import os
import threading

# (key, group, label, type, help). type ∈ {text, secret, bool, int, float}
SPECS = [
    # --- AI backend & keys ---
    ("ANTHROPIC_API_KEY", "ai", "Anthropic API key", "secret", "Powers `claude` members."),
    ("OPENAI_API_KEY", "ai", "OpenAI API key", "secret", "For OpenAI-compatible members."),
    ("OLLAMA_BASE_URL", "ai", "Ollama base URL", "text", "Default local AI host, e.g. http://127.0.0.1:11434"),
    # --- Notifications ---
    ("MAYBOT_DISCORD_WEBHOOK_URL", "notify", "Discord webhook", "secret", ""),
    ("MAYBOT_SLACK_WEBHOOK_URL", "notify", "Slack webhook", "secret", ""),
    ("MAYBOT_ALERT_WEBHOOK_URL", "notify", "Generic JSON webhook", "secret", ""),
    ("MAYBOT_TELEGRAM_TOKEN", "notify", "Telegram bot token", "secret", ""),
    ("MAYBOT_TELEGRAM_CHAT_ID", "notify", "Telegram chat ID", "text", ""),
    ("MAYBOT_SMTP_HOST", "notify", "SMTP host", "text", "Email alerts need host + from + to."),
    ("MAYBOT_SMTP_FROM", "notify", "SMTP from", "text", ""),
    ("MAYBOT_SMTP_TO", "notify", "SMTP to (comma-separated)", "text", ""),
    ("MAYBOT_SMTP_USER", "notify", "SMTP user", "text", ""),
    ("MAYBOT_SMTP_PASSWORD", "notify", "SMTP password", "secret", ""),
    # --- Automation & security gates ---
    ("MAYBOT_AUTOPILOT", "automation", "Autopilot", "bool", "Autonomous detect → fix → verify."),
    ("MAYBOT_AUTONOMY", "automation", "Tool autonomy", "bool", "Let agents auto-run auto_approve tools."),
    ("MAYBOT_AUTONOMY_MAX_CALLS", "automation", "Autonomy budget / task", "int", ""),
    ("MAYBOT_PR_ENABLED", "automation", "Open real PRs", "bool", "Needs gh auth + a resolvable repo."),
    ("MAYBOT_DELEGATION", "automation", "Agent delegation", "bool", "Agents may delegate downward."),
    ("MAYBOT_REQUIRE_AUTH", "automation", "Require sign-in", "bool", "Force a valid session on all pages/APIs."),
    # --- Sect simulation ---
    ("MAYBOT_SECT_TICK_SECONDS", "sim", "Sim tick seconds", "float", "Passive evolution cadence (0 = off)."),
    ("MAYBOT_SECT_XP_RATE", "sim", "Sim XP rate", "float", "Base cultivation XP per minute."),
    # --- Learning labs (advanced) ---
    ("MAYBOT_REAL_LABS", "labs", "Real-command pentest labs", "bool",
     "Let labs run REAL tools against an ISOLATED sandbox (off = simulated). The "
     "toggle alone does nothing until you also stand up the sandbox — see the "
     "requirements panel and docs/REAL_LABS.md. Commands always route through the "
     "guarded tools allow-list; the model never runs free-text shell."),
]
GROUPS = [("ai", "AI backend & keys"), ("notify", "Notifications"),
          ("automation", "Automation & security"), ("sim", "Sect simulation"),
          ("labs", "Learning labs (advanced)")]
_SPEC = {k: (g, lbl, typ, hlp) for (k, g, lbl, typ, hlp) in SPECS}

_lock = threading.RLock()
_overrides: dict[str, str] = {}


def _truthy(v) -> bool:
    return str(v).strip().lower() in ("1", "true", "yes", "on")


def effective(key: str) -> str:
    """Current effective value: an in-app override wins over the env default."""
    with _lock:
        if key in _overrides:
            return _overrides[key]
    return os.getenv(key, "")


def _apply(key: str, val: str) -> None:
    """Make ``val`` take effect at runtime (env + any cached module global)."""
    if val == "":
        os.environ.pop(key, None)
    else:
        os.environ[key] = val
    try:
        if key == "ANTHROPIC_API_KEY":
            from . import agents
            agents._anthropic = None                      # rebuild the SDK client with the new key
        elif key == "MAYBOT_REQUIRE_AUTH":
            from . import authz
            authz.REQUIRE_AUTH = _truthy(val)
        elif key == "MAYBOT_DELEGATION":
            from . import agents
            agents.DELEGATION_GLOBAL = _truthy(val)
        elif key == "MAYBOT_AUTONOMY":
            from . import autonomy
            autonomy.ENABLED = _truthy(val)
        elif key == "MAYBOT_AUTONOMY_MAX_CALLS":
            from . import autonomy
            try:
                autonomy.MAX_CALLS = max(0, int(float(val or "0")))
            except ValueError:
                pass
        elif key == "MAYBOT_PR_ENABLED":
            from . import pullrequest
            pullrequest.ENABLED = _truthy(val)
        elif key == "MAYBOT_AUTOPILOT":
            from . import autopilot
            autopilot.ENABLED = _truthy(val)
            if autopilot.ENABLED:
                try:
                    autopilot.start()                     # idempotent; starts the loop if not already
                except Exception:
                    pass
        elif key in ("MAYBOT_DISCORD_WEBHOOK_URL", "MAYBOT_SLACK_WEBHOOK_URL", "MAYBOT_ALERT_WEBHOOK_URL"):
            from . import notifier
            notifier.DISCORD_WEBHOOK = os.getenv("MAYBOT_DISCORD_WEBHOOK_URL", "")
            notifier.SLACK_WEBHOOK = os.getenv("MAYBOT_SLACK_WEBHOOK_URL", "")
            notifier.GENERIC_WEBHOOK = os.getenv("MAYBOT_ALERT_WEBHOOK_URL", "")
        elif key == "MAYBOT_SECT_TICK_SECONDS":
            from . import sectsim
            try:
                sectsim.TICK_SECONDS = float(val or "0")
            except ValueError:
                pass
            if sectsim.TICK_SECONDS > 0:
                try:
                    sectsim.start()                       # idempotent
                except Exception:
                    pass
        elif key == "MAYBOT_SECT_XP_RATE":
            from . import sectsim
            try:
                sectsim.XP_RATE = float(val or "0")
            except ValueError:
                pass
        elif key == "MAYBOT_REAL_LABS":
            from . import learning
            learning.REAL_LABS = _truthy(val)             # flip the real-command gate live
    except Exception:
        pass


def set_value(key: str, val) -> None:
    if key not in _SPEC:
        return
    sval = "" if val is None else str(val).strip()
    with _lock:
        _overrides[key] = sval
    _apply(key, sval)


def set_many(values: dict) -> None:
    for k, v in (values or {}).items():
        set_value(k, v)
    _save()


def view(reveal: bool = False) -> dict:
    """UI shape: groups of fields with current values.

    Secrets are masked unless ``reveal`` is set — the API only reveals them after
    the operator re-enters their password (the password-protected settings panel).
    """
    groups = []
    for gid, glabel in GROUPS:
        items = []
        for (k, g, lbl, typ, hlp) in SPECS:
            if g != gid:
                continue
            cur = effective(k)
            it = {"key": k, "label": lbl, "type": typ, "help": hlp}
            if typ == "secret":
                it["set"] = bool(cur)
                it["value"] = cur if reveal else ""       # only sent after password unlock
            elif typ == "bool":
                it["value"] = "1" if _truthy(cur) else "0"
            else:
                it["value"] = cur
            items.append(it)
        groups.append({"id": gid, "label": glabel, "items": items})
    return {"groups": groups, "persisted": _persist_enabled(), "revealed": reveal}


def _persist_enabled() -> bool:
    from . import store
    return store.enabled()


def _save() -> None:
    from . import store
    if store.enabled():
        with _lock:
            store.save_state("settings", {"values": dict(_overrides)})


def load_persisted() -> None:
    from . import store
    data = store.load_state("settings")
    if not data:
        return
    vals = data.get("values") or {}
    with _lock:
        _overrides.update({k: str(v) for k, v in vals.items() if k in _SPEC})
        items = list(_overrides.items())
    for k, v in items:
        _apply(k, v)
