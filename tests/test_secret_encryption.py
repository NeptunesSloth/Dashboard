"""Opt-in encryption-at-rest for secret config values (config + secrets).

These tests prove:
  * encrypt -> decrypt round-trips with a generated key;
  * load_devices() transparently decrypts `enc:` api_tokens when a key is set;
  * with no key, `enc:` values pass through untouched (no crash; warning);
  * a plaintext config loads identically whether or not a key is set (the
    default path is unchanged);
  * save_devices() writes `enc:` when a key is set, and a round-trip through
    save+load yields the original token.
"""
import pytest

cryptography = pytest.importorskip("cryptography")
from cryptography.fernet import Fernet  # noqa: E402

from maybot_control_center import config, secrets  # noqa: E402


@pytest.fixture(autouse=True)
def _reset(monkeypatch):
    # Clean slate: no key, no cached "already warned" state between tests.
    monkeypatch.delenv(secrets.KEY_ENV, raising=False)
    secrets._warned.clear()
    yield
    secrets._warned.clear()


def _set_key(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setenv(secrets.KEY_ENV, key)
    return key


def _point_at(monkeypatch, tmp_path):
    """Repoint config.DEVICES_FILE at a temp file for this test."""
    f = tmp_path / "devices.yaml"
    monkeypatch.setattr(config, "DEVICES_FILE", f)
    return f


# --------------------------------------------------------------------------- #
# secrets helper
# --------------------------------------------------------------------------- #
def test_round_trip_with_generated_key(monkeypatch):
    _set_key(monkeypatch)
    enc = secrets.encrypt("super-secret-token")
    assert enc.startswith(secrets.ENC_PREFIX)
    assert "super-secret-token" not in enc
    assert secrets.decrypt(enc) == "super-secret-token"


def test_keygen_produces_usable_key(monkeypatch):
    key = secrets.generate_key()
    monkeypatch.setenv(secrets.KEY_ENV, key)
    assert secrets.decrypt(secrets.encrypt("hello")) == "hello"


def test_no_key_passthrough_no_crash(caplog):
    # Without a key: encrypt is a no-op, decrypt leaves enc: untouched + warns.
    assert secrets.encrypt("tok") == "tok"
    enc_value = secrets.ENC_PREFIX + "gAAAAAfake"
    with caplog.at_level("WARNING"):
        out = secrets.decrypt(enc_value)
    assert out == enc_value
    assert any(secrets.KEY_ENV in r.message for r in caplog.records)


def test_empty_and_nonstring_passthrough(monkeypatch):
    _set_key(monkeypatch)
    assert secrets.encrypt("") == ""           # nothing to protect
    assert secrets.encrypt(None) is None
    assert secrets.decrypt("plain") == "plain"  # not enc: -> unchanged


def test_encrypt_is_idempotent(monkeypatch):
    _set_key(monkeypatch)
    once = secrets.encrypt("tok")
    assert secrets.encrypt(once) == once


def test_bad_key_falls_back_to_plaintext(monkeypatch, caplog):
    monkeypatch.setenv(secrets.KEY_ENV, "not-a-valid-fernet-key")
    with caplog.at_level("WARNING"):
        assert secrets.encrypt("tok") == "tok"
    assert not secrets.encryption_enabled()


# --------------------------------------------------------------------------- #
# config integration
# --------------------------------------------------------------------------- #
def test_load_decrypts_enc_token(monkeypatch, tmp_path):
    key = _set_key(monkeypatch)
    f = _point_at(monkeypatch, tmp_path)
    enc = Fernet(key.encode()).encrypt(b"real-token").decode()
    f.write_text(
        "devices:\n  - name: h1\n    url: http://x:8100\n"
        f"    api_token: enc:{enc}\n",
        encoding="utf-8",
    )
    devices = config.load_devices()
    assert devices[0]["api_token"] == "real-token"
    assert devices[0]["url"] == "http://x:8100"  # non-secret untouched


def test_load_enc_without_key_passes_through(monkeypatch, tmp_path, caplog):
    f = _point_at(monkeypatch, tmp_path)  # no key set
    f.write_text(
        "devices:\n  - name: h1\n    url: http://x:8100\n"
        "    api_token: enc:gAAAAAfake\n",
        encoding="utf-8",
    )
    with caplog.at_level("WARNING"):
        devices = config.load_devices()
    assert devices[0]["api_token"] == "enc:gAAAAAfake"  # untouched, no crash


def test_plaintext_config_loads_identically_with_or_without_key(monkeypatch, tmp_path):
    f = _point_at(monkeypatch, tmp_path)
    f.write_text(
        "devices:\n  - name: h1\n    url: http://x:8100\n"
        "    api_token: plain-token\n",
        encoding="utf-8",
    )
    without = config.load_devices()
    assert without[0]["api_token"] == "plain-token"

    _set_key(monkeypatch)
    with_key = config.load_devices()
    assert with_key[0]["api_token"] == "plain-token"  # plaintext still works


def test_save_encrypts_then_load_round_trips(monkeypatch, tmp_path):
    _set_key(monkeypatch)
    f = _point_at(monkeypatch, tmp_path)
    config.save_devices([{"name": "h1", "url": "http://x:8100", "api_token": "secret-tok"}])

    raw = f.read_text(encoding="utf-8")
    assert "secret-tok" not in raw          # not stored as plaintext
    assert "api_token: enc:" in raw          # stored encrypted
    assert "name: h1" in raw                 # non-secret stays plaintext
    assert "url: http://x:8100" in raw

    assert config.load_devices()[0]["api_token"] == "secret-tok"  # decrypts back


def test_save_without_key_is_plaintext(monkeypatch, tmp_path):
    f = _point_at(monkeypatch, tmp_path)  # no key
    config.save_devices([{"name": "h1", "url": "http://x:8100", "api_token": "secret-tok"}])
    raw = f.read_text(encoding="utf-8")
    assert "api_token: secret-tok" in raw    # exactly as today
    assert "enc:" not in raw
