"""Email (SMTP), Telegram, PagerDuty and Opsgenie notification channels."""
import pytest

from maybot_control_center import notify


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in ("MAYBOT_SLACK_WEBHOOK", "MAYBOT_DISCORD_WEBHOOK", "MAYBOT_WEBHOOK_URL",
                "MAYBOT_SMTP_HOST", "MAYBOT_SMTP_FROM", "MAYBOT_SMTP_TO",
                "MAYBOT_TELEGRAM_TOKEN", "MAYBOT_TELEGRAM_CHAT_ID",
                "MAYBOT_PAGERDUTY_ROUTING_KEY", "MAYBOT_OPSGENIE_API_KEY",
                "MAYBOT_OPSGENIE_REGION"):
        monkeypatch.delenv(var, raising=False)
    notify.clear()
    yield
    notify.clear()


def test_no_channels_when_unset():
    assert notify.channels() == []


def test_email_channel_requires_full_config(monkeypatch):
    monkeypatch.setenv("MAYBOT_SMTP_HOST", "smtp.example")
    assert "email" not in notify.channels()           # missing FROM/TO
    monkeypatch.setenv("MAYBOT_SMTP_FROM", "a@example")
    monkeypatch.setenv("MAYBOT_SMTP_TO", "ops@example, oncall@example")
    assert "email" in notify.channels()


def test_telegram_channel_requires_token_and_chat(monkeypatch):
    monkeypatch.setenv("MAYBOT_TELEGRAM_TOKEN", "t")
    assert "telegram" not in notify.channels()
    monkeypatch.setenv("MAYBOT_TELEGRAM_CHAT_ID", "123")
    assert "telegram" in notify.channels()


def test_send_delivers_to_email_and_telegram(monkeypatch):
    monkeypatch.setenv("MAYBOT_SMTP_HOST", "smtp.example")
    monkeypatch.setenv("MAYBOT_SMTP_FROM", "a@example")
    monkeypatch.setenv("MAYBOT_SMTP_TO", "ops@example")
    monkeypatch.setenv("MAYBOT_TELEGRAM_TOKEN", "t")
    monkeypatch.setenv("MAYBOT_TELEGRAM_CHAT_ID", "123")

    sent = {}
    monkeypatch.setattr(notify, "_send_email", lambda title, body: sent.setdefault("email", (title, body)) or True)
    monkeypatch.setattr(notify, "_post", lambda url, payload: sent.setdefault("tg", (url, payload)) or True)

    res = notify.send("Tribulation", "lightning", level="warning")
    assert set(res["delivered"]) == {"email", "telegram"}
    assert sent["email"][0] == "Tribulation"
    assert "api.telegram.org/bott/sendMessage" in sent["tg"][0]
    assert sent["tg"][1]["chat_id"] == "123"


def test_send_email_uses_smtp(monkeypatch):
    monkeypatch.setenv("MAYBOT_SMTP_HOST", "smtp.example")
    monkeypatch.setenv("MAYBOT_SMTP_FROM", "a@example")
    monkeypatch.setenv("MAYBOT_SMTP_TO", "ops@example")
    monkeypatch.setenv("MAYBOT_SMTP_TLS", "1")

    class _FakeSMTP:
        instances = []

        def __init__(self, host, port, timeout=10):
            self.host, self.port = host, port
            self.started_tls = False
            self.sent = None
            _FakeSMTP.instances.append(self)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def starttls(self):
            self.started_tls = True

        def login(self, u, p):
            pass

        def send_message(self, msg):
            self.sent = msg

    monkeypatch.setattr(notify.smtplib, "SMTP", _FakeSMTP)
    assert notify._send_email("Subject", "Body") is True
    smtp = _FakeSMTP.instances[-1]
    assert smtp.host == "smtp.example" and smtp.port == 587
    assert smtp.started_tls is True
    assert smtp.sent["Subject"] == "Subject"


# ---------------------------------------------------------------------------
# PagerDuty
# ---------------------------------------------------------------------------
def test_pagerduty_channel_requires_routing_key(monkeypatch):
    assert "pagerduty" not in notify.channels()
    monkeypatch.setenv("MAYBOT_PAGERDUTY_ROUTING_KEY", "rk-123")
    assert "pagerduty" in notify.channels()


def test_send_delivers_to_pagerduty(monkeypatch):
    monkeypatch.setenv("MAYBOT_PAGERDUTY_ROUTING_KEY", "rk-123")
    posted = {}

    def _fake_post(url, payload):
        posted["url"] = url
        posted["payload"] = payload
        return True

    monkeypatch.setattr(notify, "_post", _fake_post)
    res = notify.send("Tribulation", "lightning", level="error")
    assert res["delivered"] == ["pagerduty"]
    assert posted["url"] == "https://events.pagerduty.com/v2/enqueue"
    p = posted["payload"]
    assert p["routing_key"] == "rk-123"
    assert p["event_action"] == "trigger"
    assert p["payload"]["severity"] == "error"
    assert p["payload"]["source"] == "maybot"
    assert "Tribulation" in p["payload"]["summary"] and "lightning" in p["payload"]["summary"]


def test_pagerduty_severity_mapping(monkeypatch):
    monkeypatch.setenv("MAYBOT_PAGERDUTY_ROUTING_KEY", "rk")
    seen = {}
    monkeypatch.setattr(notify, "_post", lambda url, payload: seen.update(payload) or True)
    notify.send("warn-title", "b", level="warning")
    assert seen["payload"]["severity"] == "warning"


# ---------------------------------------------------------------------------
# Opsgenie
# ---------------------------------------------------------------------------
def test_opsgenie_channel_requires_key(monkeypatch):
    assert "opsgenie" not in notify.channels()
    monkeypatch.setenv("MAYBOT_OPSGENIE_API_KEY", "gk-1")
    assert "opsgenie" in notify.channels()


def test_send_delivers_to_opsgenie_us(monkeypatch):
    monkeypatch.setenv("MAYBOT_OPSGENIE_API_KEY", "gk-1")
    captured = {}

    def _fake_post_headers(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        captured["headers"] = headers
        return True

    monkeypatch.setattr(notify, "_post_headers", _fake_post_headers)
    res = notify.send("Alert title", "body text", level="error")
    assert res["delivered"] == ["opsgenie"]
    assert captured["url"] == "https://api.opsgenie.com/v2/alerts"
    assert captured["headers"]["Authorization"] == "GenieKey gk-1"
    assert captured["payload"]["message"] == "Alert title"
    assert captured["payload"]["description"] == "body text"
    assert captured["payload"]["priority"] == "P1"


def test_opsgenie_eu_region_url(monkeypatch):
    monkeypatch.setenv("MAYBOT_OPSGENIE_API_KEY", "gk-eu")
    monkeypatch.setenv("MAYBOT_OPSGENIE_REGION", "eu")
    captured = {}
    monkeypatch.setattr(notify, "_post_headers",
                        lambda url, payload, headers: captured.update(url=url, headers=headers) or True)
    notify.send("t", "b", level="info")
    assert captured["url"] == "https://api.eu.opsgenie.com/v2/alerts"
    assert captured["headers"]["Authorization"] == "GenieKey gk-eu"


def test_post_headers_attaches_auth(monkeypatch):
    captured = {}

    class _Resp:
        ok = True

    class _FakeRequests:
        @staticmethod
        def post(url, json=None, headers=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["headers"] = headers
            return _Resp()

    import sys
    monkeypatch.setitem(sys.modules, "requests", _FakeRequests)
    ok = notify._post_headers("https://x/y", {"a": 1}, {"Authorization": "GenieKey k"})
    assert ok is True
    assert captured["headers"]["Authorization"] == "GenieKey k"
    assert captured["headers"]["Content-Type"] == "application/json"
