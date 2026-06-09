"""Opt-in mutual-TLS configuration for the control center -> agent link.

All behaviour is OFF by default: with none of the env vars set, a freshly
configured ``requests.Session`` keeps its defaults (``cert is None`` /
``verify is True``). These tests drive ``_configure_tls`` directly with a fresh
session and monkeypatched env so nothing leaks into the module-level session.
"""
import requests

from maybot_control_center.agent_client import _configure_tls

_CA = "MAYBOT_AGENT_CA"
_CERT = "MAYBOT_AGENT_CLIENT_CERT"
_KEY = "MAYBOT_AGENT_CLIENT_KEY"


def _clear_env(monkeypatch):
    for var in (_CA, _CERT, _KEY):
        monkeypatch.delenv(var, raising=False)


def test_defaults_off_when_no_env(monkeypatch):
    _clear_env(monkeypatch)
    s = _configure_tls(requests.Session())
    # requests defaults: verify True, no client cert.
    assert s.verify is True
    assert s.cert is None


def test_ca_sets_verify(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(_CA, "/etc/maybot/ca.crt")
    s = _configure_tls(requests.Session())
    assert s.verify == "/etc/maybot/ca.crt"
    assert s.cert is None


def test_client_cert_and_key_set_cert_tuple(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(_CERT, "/etc/maybot/cc.crt")
    monkeypatch.setenv(_KEY, "/etc/maybot/cc.key")
    s = _configure_tls(requests.Session())
    assert s.cert == ("/etc/maybot/cc.crt", "/etc/maybot/cc.key")
    assert s.verify is True  # CA unset => default verification


def test_full_mtls(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(_CA, "/ca.pem")
    monkeypatch.setenv(_CERT, "/cc.crt")
    monkeypatch.setenv(_KEY, "/cc.key")
    s = _configure_tls(requests.Session())
    assert s.verify == "/ca.pem"
    assert s.cert == ("/cc.crt", "/cc.key")


def test_missing_key_means_no_client_cert_and_warns(monkeypatch, caplog):
    _clear_env(monkeypatch)
    monkeypatch.setenv(_CERT, "/cc.crt")  # key intentionally absent
    with caplog.at_level("WARNING"):
        s = _configure_tls(requests.Session())
    assert s.cert is None  # incomplete pair => no client cert, no crash
    assert any("mTLS" in r.message or "client cert" in r.message.lower() for r in caplog.records)


def test_missing_cert_means_no_client_cert(monkeypatch):
    _clear_env(monkeypatch)
    monkeypatch.setenv(_KEY, "/cc.key")  # cert intentionally absent
    s = _configure_tls(requests.Session())
    assert s.cert is None


def test_returns_same_session(monkeypatch):
    _clear_env(monkeypatch)
    sess = requests.Session()
    assert _configure_tls(sess) is sess
