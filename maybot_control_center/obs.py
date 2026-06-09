"""Lightweight observability: a cheap Prometheus exposition + opt-in JSON logs.

This is the *minimal, never-fail* sibling of :mod:`metrics`. Where ``metrics``
renders a rich, fleet-wide scrape (cultivation, SLOs, autopilot, …), this module
exposes only a handful of always-cheap in-memory counters/gauges and is wrapped
so a scrape can *never* raise — handy as an internal liveness/throughput target.

Two pieces, both additive and default-safe:

* :func:`render_prometheus` — hand-formatted text exposition (no dependency on
  ``prometheus_client``), reusing existing in-memory stats (selfcheck, usage,
  configured hosts/agents) plus a ``process_up`` gauge.
* :func:`setup_logging` — when ``MAYBOT_JSON_LOGS`` is truthy, attaches a JSON
  formatter to the root logger (one object per line). Unset => no change.
* :func:`setup_sentry` — opt-in Sentry error tracking. Default OFF: with no
  ``MAYBOT_SENTRY_DSN`` set it is a complete no-op (no import, no behaviour
  change). Called automatically from :func:`setup_logging`, so no wiring change
  is needed in callers.

Optional Sentry error tracking
------------------------------
Sentry is **optional** and **default-off**. The ``sentry-sdk`` package is
intentionally NOT in ``requirements.txt``; install it only if you want it::

    pip install sentry-sdk

Then enable by setting these environment variables:

* ``MAYBOT_SENTRY_DSN`` — the Sentry DSN. Unset => Sentry is completely off
  (no import, no init). This is the master switch.
* ``MAYBOT_SENTRY_TRACES_SAMPLE_RATE`` — float in [0, 1] for performance
  tracing sample rate. Defaults to ``0`` (errors only, no tracing).
* ``MAYBOT_ENV`` — environment tag reported to Sentry. Defaults to
  ``"production"``.
* ``MAYBOT_RELEASE`` — optional release/version string reported to Sentry.

If ``MAYBOT_SENTRY_DSN`` is set but ``sentry-sdk`` is not installed, a single
warning is logged and Sentry is silently skipped (never raises).
"""
from __future__ import annotations

import json
import logging
import os
import time

_START = time.time()

# Prometheus content type (text exposition format v0.0.4).
CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"


def _truthy(val: str | None) -> bool:
    return (val or "").strip().lower() in ("1", "true", "yes", "on")


def metrics_public() -> bool:
    """Whether /metrics is served unauthenticated. Defaults to on (internal scrape)."""
    return _truthy(os.getenv("MAYBOT_METRICS_PUBLIC", "1"))


def metrics_token() -> str:
    """Optional bearer/control token gating /metrics when public scraping is off."""
    return (os.getenv("MAYBOT_METRICS_TOKEN") or "").strip()


def _line(out: list[str], emitted: set[str], name: str, value, help_text: str,
          mtype: str = "gauge") -> None:
    if name not in emitted:
        out.append(f"# HELP {name} {help_text}")
        out.append(f"# TYPE {name} {mtype}")
        emitted.add(name)
    out.append(f"{name} {value}")


def render_prometheus() -> str:
    """Render a small, cheap Prometheus exposition. Never raises.

    Reuses existing in-memory snapshots only (no agent polling, no device
    polls), so a scrape is fast and side-effect free. On any failure it falls
    back to a minimal but valid exposition so scrapers don't see a 500.
    """
    out: list[str] = []
    emitted: set[str] = set()
    try:
        # ---- process liveness / uptime ----
        _line(out, emitted, "maybot_obs_process_up", 1,
              "1 if the control center process is serving", "gauge")
        _line(out, emitted, "maybot_obs_uptime_seconds", round(time.time() - _START, 1),
              "Seconds since this process module was imported", "gauge")

        # ---- API throughput / errors (from selfcheck) ----
        try:
            from . import selfcheck
            sc = selfcheck.snapshot()
            _line(out, emitted, "maybot_obs_api_requests_total", sc.get("api_requests", 0),
                  "API requests served (from selfcheck)", "counter")
            _line(out, emitted, "maybot_obs_api_errors_total", sc.get("api_errors", 0),
                  "API 5xx responses served (from selfcheck)", "counter")
        except Exception:
            pass

        # ---- LLM usage (cheap snapshot totals) ----
        try:
            from . import usage
            tot = usage.snapshot().get("totals", {})
            _line(out, emitted, "maybot_obs_llm_calls_total", tot.get("calls", 0),
                  "LLM calls recorded", "counter")
            _line(out, emitted, "maybot_obs_llm_tokens_total",
                  (tot.get("tokens_in", 0) + tot.get("tokens_out", 0)),
                  "LLM tokens (in+out)", "counter")
        except Exception:
            pass

        # ---- fleet sizing (configured hosts / agents) ----
        try:
            from .config import all_devices
            _line(out, emitted, "maybot_obs_hosts_total", len(all_devices()),
                  "Configured hosts/devices", "gauge")
        except Exception:
            pass
        try:
            from . import agents
            _line(out, emitted, "maybot_obs_agents_total", len(agents.load_agents()),
                  "Configured agents/disciples", "gauge")
        except Exception:
            pass

        return "\n".join(out) + "\n"
    except Exception:
        # Absolute floor: a valid, parseable exposition even if everything broke.
        return (
            "# HELP maybot_obs_process_up 1 if the control center process is serving\n"
            "# TYPE maybot_obs_process_up gauge\n"
            "maybot_obs_process_up 1\n"
        )


class _JsonFormatter(logging.Formatter):
    """Render each log record as a single-line JSON object."""

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            payload["exc"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str)


_JSON_LOGGING_ENABLED = False
_SENTRY_INITIALIZED = False


def setup_sentry() -> bool:
    """Opt-in Sentry error tracking. Default OFF, idempotent, never raises.

    When ``MAYBOT_SENTRY_DSN`` is set, lazily import ``sentry_sdk`` and
    initialize it. When the DSN is unset/empty this is a complete no-op: no
    import is attempted and behaviour is unchanged. If ``sentry-sdk`` is not
    installed, log a single warning and no-op (no raise).

    Reads ``MAYBOT_SENTRY_TRACES_SAMPLE_RATE`` (default ``0``), ``MAYBOT_ENV``
    (default ``"production"``) and ``MAYBOT_RELEASE`` (optional). Guarded so a
    second call after a successful init does nothing.

    Returns True if Sentry is (now or already) initialized, else False.
    """
    global _SENTRY_INITIALIZED
    if _SENTRY_INITIALIZED:
        return True

    dsn = (os.getenv("MAYBOT_SENTRY_DSN") or "").strip()
    if not dsn:
        # Master switch off: no import, no behaviour change.
        return False

    try:
        import sentry_sdk
    except Exception:
        logging.getLogger(__name__).warning(
            "MAYBOT_SENTRY_DSN is set but sentry-sdk is not installed; "
            "Sentry error tracking is disabled. Run 'pip install sentry-sdk' "
            "to enable it."
        )
        return False

    try:
        traces_raw = (os.getenv("MAYBOT_SENTRY_TRACES_SAMPLE_RATE") or "").strip()
        try:
            traces = float(traces_raw or 0)
        except (TypeError, ValueError):
            traces = 0.0
        sentry_sdk.init(
            dsn=dsn,
            traces_sample_rate=traces,
            environment=(os.getenv("MAYBOT_ENV") or "production"),
            release=(os.getenv("MAYBOT_RELEASE") or None),
        )
    except Exception:
        logging.getLogger(__name__).warning(
            "sentry_sdk.init failed; continuing without Sentry", exc_info=True
        )
        return False

    _SENTRY_INITIALIZED = True
    return True


def setup_logging() -> bool:
    """Opt-in structured JSON logging.

    When ``MAYBOT_JSON_LOGS`` is truthy, attach a JSON formatter to the root
    logger so every record serializes as one JSON object per line. When the env
    is unset/falsey this is a no-op (no behaviour change). Idempotent.

    Also calls :func:`setup_sentry` (opt-in, default-off) so Sentry can be
    enabled without any caller change.

    Returns True if JSON logging is (now) active, else False.
    """
    global _JSON_LOGGING_ENABLED
    # Opt-in Sentry initialization is wired here so app.py needs no change. It is
    # a complete no-op unless MAYBOT_SENTRY_DSN is set, and never raises.
    setup_sentry()
    if not _truthy(os.getenv("MAYBOT_JSON_LOGS")):
        return False
    root = logging.getLogger()
    formatter = _JsonFormatter()
    if not root.handlers:
        root.addHandler(logging.StreamHandler())
    for handler in root.handlers:
        handler.setFormatter(formatter)
    if root.level == logging.NOTSET:
        root.setLevel(logging.INFO)
    _JSON_LOGGING_ENABLED = True
    return True
