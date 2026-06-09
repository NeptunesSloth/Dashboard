"""Non-fatal startup configuration validation (config_check.check)."""
import pytest

from maybot_control_center import config_check

# Every env var the checks look at — cleared before each test for a known baseline.
_RELEVANT = (
    "MAYBOT_DEV", "MAYBOT_ENV",
    "MAYBOT_CONTROL_CENTER_TOKEN",
    "MAYBOT_DB",
    "MAYBOT_SMTP_HOST", "MAYBOT_SMTP_FROM", "MAYBOT_SMTP_TO",
    "MAYBOT_TELEGRAM_TOKEN", "MAYBOT_TELEGRAM_CHAT_ID",
    "MAYBOT_BUDGET_USD", "MAYBOT_BUDGET_DAILY_USD", "MAYBOT_BUDGET_MONTHLY_USD",
    "MAYBOT_BUDGET_AGENT_USD", "MAYBOT_BUDGET_LOW_PCT",
)


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    for var in _RELEVANT:
        monkeypatch.delenv(var, raising=False)
    yield


def _has(warnings, needle):
    return any(needle in w for w in warnings)


def test_returns_list_and_never_raises(monkeypatch):
    # Dev mode + no config: should be quiet and definitely not raise.
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    warnings = config_check.check()
    assert isinstance(warnings, list)


def test_no_false_positives_on_clean_dev_env(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    # Pretend auth is fine so we don't depend on a real users.yaml on disk.
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    assert config_check.check() == []


def test_partial_smtp_config_warns(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_SMTP_HOST", "smtp.example")
    # FROM and TO missing -> partial.
    warnings = config_check.check()
    assert _has(warnings, "Email notifications are partially configured")
    assert _has(warnings, "MAYBOT_SMTP_FROM")
    assert _has(warnings, "MAYBOT_SMTP_TO")


def test_complete_smtp_config_no_warning(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_SMTP_HOST", "smtp.example")
    monkeypatch.setenv("MAYBOT_SMTP_FROM", "a@example")
    monkeypatch.setenv("MAYBOT_SMTP_TO", "ops@example")
    assert not _has(config_check.check(), "Email notifications are partially configured")


def test_partial_telegram_config_warns(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_TELEGRAM_TOKEN", "t")
    warnings = config_check.check()
    assert _has(warnings, "Telegram notifications are partially configured")
    assert _has(warnings, "MAYBOT_TELEGRAM_CHAT_ID")


def test_auth_warning_when_not_dev_and_no_auth(monkeypatch):
    monkeypatch.setattr(config_check, "_auth_configured", lambda: False)
    warnings = config_check.check()
    assert _has(warnings, "Auth is not configured")


def test_no_auth_warning_in_dev(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: False)
    assert not _has(config_check.check(), "Auth is not configured")


def test_db_dir_missing_warns(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_DB", "/no/such/dir/maybot.db")
    assert _has(config_check.check(), "does not")


def test_db_in_writable_dir_no_warning(monkeypatch, tmp_path):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_DB", str(tmp_path / "maybot.db"))
    assert not _has(config_check.check(), "MAYBOT_DB")


def test_db_unwritable_dir_warns(monkeypatch, tmp_path):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setattr("os.access", lambda path, mode: False)
    monkeypatch.setenv("MAYBOT_DB", str(tmp_path / "maybot.db"))
    assert _has(config_check.check(), "not writable")


def test_db_memory_no_warning(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_DB", ":memory:")
    assert not _has(config_check.check(), "MAYBOT_DB")


def test_non_numeric_budget_warns(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_BUDGET_USD", "lots")
    warnings = config_check.check()
    assert _has(warnings, "MAYBOT_BUDGET_USD")
    assert _has(warnings, "non-numeric")


def test_numeric_budget_no_warning(monkeypatch):
    monkeypatch.setenv("MAYBOT_DEV", "1")
    monkeypatch.setattr(config_check, "_auth_configured", lambda: True)
    monkeypatch.setenv("MAYBOT_BUDGET_USD", "50")
    assert not _has(config_check.check(), "non-numeric")
