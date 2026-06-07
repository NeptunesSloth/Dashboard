"""Email (SMTP) and Telegram notification channels."""
import pytest

from maybot_control_center import notify


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in ("MAYBOT_SLACK_WEBHOOK", "MAYBOT_DISCORD_WEBHOOK", "MAYBOT_WEBHOOK_URL",
                "MAYBOT_SMTP_HOST", "MAYBOT_SMTP_FROM", "MAYBOT_SMTP_TO",
                "MAYBOT_TELEGRAM_TOKEN", "MAYBOT_TELEGRAM_CHAT_ID"):
        monkeypatch.delenv(var, raising=False)
    notify.clear()
    yield
    notify.clear()


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
