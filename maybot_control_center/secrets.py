"""Opt-in encryption-at-rest for secret config values (default OFF).

By default this module is a no-op and config files are stored as today
(plaintext). When you set the ``MAYBOT_SECRET_KEY`` environment variable to a
base64 Fernet key, the control center transparently:

  * DECRYPTS any value prefixed ``enc:`` when it loads config (e.g. devices.yaml),
    so already-encrypted tokens come back as plaintext in memory; and
  * ENCRYPTS the known secret field(s) — currently only a device's ``api_token`` —
    when it saves config, storing them as ``enc:<fernet-token>``.

Backward compatibility is guaranteed both ways:
  * With ``MAYBOT_SECRET_KEY`` unset, load/save behave byte-for-byte as before.
  * Plaintext values always load, whether or not a key is set; the next save
    with a key set quietly migrates them to ``enc:`` form.
  * If an ``enc:`` value is found but no key is set (or ``cryptography`` is not
    installed), it is left untouched and a warning is logged — never a crash.

Setup (operator):

    pip install cryptography                 # NOT in requirements.txt; opt-in
    export MAYBOT_SECRET_KEY="$(python -m maybot_control_center.secrets keygen)"

``keygen`` simply prints a fresh ``cryptography.fernet.Fernet.generate_key()``.
Store the key securely (a secrets manager / env file with tight perms); losing
it means encrypted values can no longer be decrypted.
"""
from __future__ import annotations

import logging
import os

_log = logging.getLogger("maybot_control_center")

# Marker prefix for an encrypted value. Plaintext values never start with this.
ENC_PREFIX = "enc:"

# Env var holding the base64 Fernet key. Unset => encryption disabled (default).
KEY_ENV = "MAYBOT_SECRET_KEY"

# Logged at most once so a missing key / missing library doesn't spam logs.
_warned: set[str] = set()


def _warn_once(tag: str, msg: str) -> None:
    if tag not in _warned:
        _warned.add(tag)
        _log.warning(msg)


def _fernet():
    """Return a Fernet instance, or None if encryption is unavailable.

    None means "act as plaintext": either no key is configured (the default,
    silent) or the key/library is unusable (warned once).
    """
    key = os.getenv(KEY_ENV)
    if not key:
        return None  # default-off: silent, no dependency required
    try:
        from cryptography.fernet import Fernet  # lazy: only when a key is set
    except Exception:
        _warn_once(
            "no-cryptography",
            f"{KEY_ENV} is set but the 'cryptography' package is not installed — "
            "falling back to plaintext config. Run 'pip install cryptography' to "
            "enable encryption-at-rest for secret config values.",
        )
        return None
    try:
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception:
        _warn_once(
            "bad-key",
            f"{KEY_ENV} is set but is not a valid Fernet key — falling back to "
            "plaintext config. Generate one with "
            "'python -m maybot_control_center.secrets keygen'.",
        )
        return None


def encryption_enabled() -> bool:
    """True when a usable key + library are available (encryption is active)."""
    return _fernet() is not None


def is_encrypted(value) -> bool:
    return isinstance(value, str) and value.startswith(ENC_PREFIX)


def encrypt(value):
    """Return ``enc:<token>`` for a secret, or the value unchanged if disabled.

    Empty strings and non-strings are passed through untouched (nothing to
    protect). Already-encrypted values are returned as-is (idempotent).
    """
    if not isinstance(value, str) or value == "" or is_encrypted(value):
        return value
    f = _fernet()
    if f is None:
        return value  # disabled / unavailable => plaintext, as today
    token = f.encrypt(value.encode("utf-8")).decode("ascii")
    return ENC_PREFIX + token


def decrypt(value):
    """Decrypt an ``enc:`` value; pass anything else through unchanged.

    If the value is encrypted but no key/library is available, it is returned
    untouched with a one-time warning (so existing configs never crash).
    """
    if not is_encrypted(value):
        return value
    f = _fernet()
    if f is None:
        _warn_once(
            "enc-no-key",
            f"Found an 'enc:' encrypted config value but {KEY_ENV} is not "
            "available — leaving it as-is. Set the key to decrypt it.",
        )
        return value
    token = value[len(ENC_PREFIX):]
    try:
        from cryptography.fernet import InvalidToken
    except Exception:
        InvalidToken = Exception  # type: ignore[assignment]
    try:
        return f.decrypt(token.encode("ascii")).decode("utf-8")
    except InvalidToken:
        _warn_once(
            "bad-token",
            "An 'enc:' config value could not be decrypted with the current "
            f"{KEY_ENV} (wrong key or corrupted) — leaving it as-is.",
        )
        return value
    except Exception:
        _warn_once("decrypt-error", "Failed to decrypt an 'enc:' config value — leaving it as-is.")
        return value


def generate_key() -> str:
    """Return a fresh base64 Fernet key (requires 'cryptography' installed)."""
    from cryptography.fernet import Fernet
    return Fernet.generate_key().decode("ascii")


def _main(argv: list[str]) -> int:
    if len(argv) == 1 and argv[0] == "keygen":
        try:
            print(generate_key())
        except Exception as e:  # pragma: no cover - depends on optional dep
            print(
                "error: could not generate a key — is 'cryptography' installed? "
                "Run 'pip install cryptography'. (%s)" % e
            )
            return 1
        return 0
    print("usage: python -m maybot_control_center.secrets keygen")
    return 2


if __name__ == "__main__":  # pragma: no cover
    import sys
    raise SystemExit(_main(sys.argv[1:]))
