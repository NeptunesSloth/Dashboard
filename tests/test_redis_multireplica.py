"""Opt-in Redis-backed shared state for sessions + rate limiting.

These tests verify three things:

1. Default-off: with no MAYBOT_REDIS_URL the in-memory path is used and behaves
   exactly as before (sessions + rate limiting).
2. The Redis path is selected when MAYBOT_REDIS_URL is set (and reachable).
3. If the ``redis`` import/connection fails, authz logs one warning and falls
   back to in-memory — never crashes, never blocks auth.

When ``fakeredis`` is importable we exercise the real Redis round-trip (session
storage + TTL, rate-limit INCR/EXPIRE). Otherwise we mock the client and assert
the right calls are made.
"""
from __future__ import annotations

import time
import types

import pytest

from maybot_control_center import authz


try:
    import fakeredis  # noqa: F401
    HAVE_FAKEREDIS = True
except Exception:  # pragma: no cover - depends on env
    HAVE_FAKEREDIS = False


def setup_function():
    # Default to the in-memory backend for every test, then let each test
    # opt in to Redis explicitly.
    authz.clear()
    authz._reset_backends()


def teardown_function():
    authz._reset_backends()


# --------------------------------------------------------------------------- #
# 1. Default-off: in-memory path unchanged                                    #
# --------------------------------------------------------------------------- #
def test_default_off_uses_in_memory_backend(monkeypatch):
    monkeypatch.setattr(authz, "REDIS_URL", "")
    authz._reset_backends()
    assert authz.redis_enabled() is False
    assert isinstance(authz._sessions_backend(), authz._InMemorySessionStore)
    assert isinstance(authz._rate_backend(), authz._InMemoryRateStore)


def test_in_memory_session_roundtrip_unchanged(monkeypatch, tmp_path):
    monkeypatch.setattr(authz, "REDIS_URL", "")
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "none.yaml")
    monkeypatch.setattr(authz, "CONTROL_CENTER_TOKEN", "sekret")
    authz._reset_backends()

    issued = authz.issue_session("sekret")
    assert issued and issued["role"] == "operator"
    sid = issued["session"]
    # Session stored in the process-local dict (old behavior).
    assert sid in authz._sessions
    assert authz.role_for(sid) == "operator"
    assert authz.revoke_session(sid) is True
    assert authz.role_for(sid) is None


def test_in_memory_session_expiry_unchanged(monkeypatch):
    monkeypatch.setattr(authz, "REDIS_URL", "")
    authz._reset_backends()
    # Inject an already-expired session directly via the backend.
    authz._sessions_backend().put(
        "expired", {"role": "viewer", "name": "x", "projects": None,
                    "expires": time.time() - 1})
    assert authz._session_lookup("expired") is None
    assert "expired" not in authz._sessions  # reaped on lookup


def test_in_memory_rate_limit_unchanged(monkeypatch):
    monkeypatch.setattr(authz, "REDIS_URL", "")
    monkeypatch.setattr(authz, "RATE", 3)
    monkeypatch.setattr(authz, "WINDOW", 60)
    authz._reset_backends()
    assert [authz.allow_request("k") for _ in range(4)] == [True, True, True, False]
    assert authz.allow_request("other") is True


# --------------------------------------------------------------------------- #
# 2. Redis path is selected when MAYBOT_REDIS_URL is set                       #
# --------------------------------------------------------------------------- #
@pytest.mark.skipif(not HAVE_FAKEREDIS, reason="fakeredis not installed")
def test_redis_backend_selected_with_fakeredis(monkeypatch):
    import fakeredis

    monkeypatch.setattr(authz, "REDIS_URL", "redis://localhost:6379/0")
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    fake_redis_mod = types.SimpleNamespace(
        Redis=types.SimpleNamespace(from_url=lambda *a, **k: fake))
    monkeypatch.setitem(__import__("sys").modules, "redis", fake_redis_mod)
    authz._reset_backends()

    assert authz.redis_enabled() is True
    assert isinstance(authz._sessions_backend(), authz._RedisSessionStore)
    assert isinstance(authz._rate_backend(), authz._RedisRateStore)


@pytest.mark.skipif(not HAVE_FAKEREDIS, reason="fakeredis not installed")
def test_redis_session_roundtrip_with_fakeredis(monkeypatch, tmp_path):
    import fakeredis

    monkeypatch.setattr(authz, "REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "none.yaml")
    monkeypatch.setattr(authz, "CONTROL_CENTER_TOKEN", "sekret")
    monkeypatch.setattr(authz, "SESSION_TTL_MINUTES", 60.0)
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setitem(
        __import__("sys").modules, "redis",
        types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *a, **k: fake)))
    authz._reset_backends()

    issued = authz.issue_session("sekret")
    sid = issued["session"]
    # Stored in Redis (not the in-memory dict), with a TTL matching expiry.
    assert sid not in authz._sessions
    key = f"{authz.REDIS_PREFIX}:sess:{sid}"
    assert fake.exists(key)
    ttl = fake.ttl(key)
    assert 0 < ttl <= 60 * 60
    # Lookup resolves through Redis.
    assert authz.role_for(sid) == "operator"
    assert authz.name_for(sid) in ("operator", "user")
    # Revoke deletes the Redis key.
    assert authz.revoke_session(sid) is True
    assert not fake.exists(key)
    assert authz.role_for(sid) is None


@pytest.mark.skipif(not HAVE_FAKEREDIS, reason="fakeredis not installed")
def test_redis_rate_limit_incr_expire_with_fakeredis(monkeypatch):
    import fakeredis

    monkeypatch.setattr(authz, "REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(authz, "RATE", 3)
    monkeypatch.setattr(authz, "WINDOW", 60)
    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    monkeypatch.setitem(
        __import__("sys").modules, "redis",
        types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=lambda *a, **k: fake)))
    authz._reset_backends()

    assert [authz.allow_request("k") for _ in range(4)] == [True, True, True, False]
    # A different key has its own shared budget.
    assert authz.allow_request("other") is True
    # The counter key carries a TTL (EXPIRE was applied on first INCR).
    bucket = int(time.time() // 60)
    rkey = f"{authz.REDIS_PREFIX}:rl:k:{bucket}"
    assert fake.get(rkey) == "4"
    assert 0 < fake.ttl(rkey) <= 60


@pytest.mark.skipif(not HAVE_FAKEREDIS, reason="fakeredis not installed")
def test_redis_rate_limit_shared_across_replicas(monkeypatch):
    """Two authz "replicas" sharing one Redis enforce a single budget."""
    import fakeredis

    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    store_a = authz._RedisRateStore(fake, "maybot")
    store_b = authz._RedisRateStore(fake, "maybot")
    # 3 from replica A, then replica B sees the shared count and rejects the 4th.
    assert [store_a.allow("u", 3, 60) for _ in range(3)] == [True, True, True]
    assert store_b.allow("u", 3, 60) is False


@pytest.mark.skipif(not HAVE_FAKEREDIS, reason="fakeredis not installed")
def test_redis_session_shared_across_replicas(monkeypatch):
    """A session written by one replica is visible to another via Redis."""
    import fakeredis

    fake = fakeredis.FakeStrictRedis(decode_responses=True)
    store_a = authz._RedisSessionStore(fake, "maybot")
    store_b = authz._RedisSessionStore(fake, "maybot")
    rec = {"role": "operator", "name": "a", "projects": None,
           "expires": time.time() + 3600}
    store_a.put("sid1", rec)
    got = store_b.get("sid1")
    assert got and got["role"] == "operator" and got["name"] == "a"


# --------------------------------------------------------------------------- #
# 3. Graceful fallback when redis import/connection fails                      #
# --------------------------------------------------------------------------- #
def test_fallback_when_redis_import_fails(monkeypatch, caplog):
    monkeypatch.setattr(authz, "REDIS_URL", "redis://localhost:6379/0")
    # Make ``import redis`` raise inside _redis_client.
    real_import = __builtins__["__import__"] if isinstance(__builtins__, dict) else __builtins__.__import__

    def boom(name, *args, **kwargs):
        if name == "redis":
            raise ImportError("no module named redis")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", boom)
    authz._reset_backends()

    with caplog.at_level("WARNING"):
        # Must not crash and must not block auth.
        assert isinstance(authz._sessions_backend(), authz._InMemorySessionStore)
        assert isinstance(authz._rate_backend(), authz._InMemoryRateStore)
    assert authz.redis_enabled() is False
    # Exactly one warning mentioning redis fallback.
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert warnings, "expected a fallback warning"
    assert any("redis" in r.getMessage().lower() for r in warnings)


def test_fallback_when_redis_connection_fails(monkeypatch, caplog):
    monkeypatch.setattr(authz, "REDIS_URL", "redis://localhost:6379/0")

    def from_url(*a, **k):
        raise ConnectionError("refused")

    monkeypatch.setitem(
        __import__("sys").modules, "redis",
        types.SimpleNamespace(Redis=types.SimpleNamespace(from_url=from_url)))
    authz._reset_backends()

    with caplog.at_level("WARNING"):
        assert isinstance(authz._sessions_backend(), authz._InMemorySessionStore)
    assert authz.redis_enabled() is False
    assert any("redis" in r.getMessage().lower()
               for r in caplog.records if r.levelname == "WARNING")


def test_fallback_still_serves_auth(monkeypatch, tmp_path):
    """After a Redis failure, sessions + rate limiting still work in-memory."""
    monkeypatch.setattr(authz, "REDIS_URL", "redis://localhost:6379/0")
    monkeypatch.setattr(authz, "USERS_FILE", tmp_path / "none.yaml")
    monkeypatch.setattr(authz, "CONTROL_CENTER_TOKEN", "sekret")
    monkeypatch.setattr(authz, "RATE", 2)
    monkeypatch.setattr(authz, "WINDOW", 60)
    monkeypatch.setitem(
        __import__("sys").modules, "redis",
        types.SimpleNamespace(
            Redis=types.SimpleNamespace(
                from_url=lambda *a, **k: (_ for _ in ()).throw(ConnectionError("x")))))
    authz._reset_backends()

    issued = authz.issue_session("sekret")
    assert issued and authz.role_for(issued["session"]) == "operator"
    assert [authz.allow_request("z") for _ in range(3)] == [True, True, False]


# --------------------------------------------------------------------------- #
# Mock-only path (runs even without fakeredis): verify the right Redis calls   #
# --------------------------------------------------------------------------- #
def test_rate_store_calls_incr_and_expire_mocked():
    calls = []

    class FakeClient:
        def incr(self, key):
            calls.append(("incr", key))
            return len([c for c in calls if c[0] == "incr"])

        def expire(self, key, ttl):
            calls.append(("expire", key, ttl))
            return True

    store = authz._RedisRateStore(FakeClient(), "maybot")
    assert store.allow("k", 2, 30) is True   # count 1 -> incr + expire
    assert store.allow("k", 2, 30) is True   # count 2 -> incr only
    assert store.allow("k", 2, 30) is False  # count 3 -> over limit
    assert calls[0][0] == "incr"
    assert calls[1] == ("expire", calls[1][1], 30)  # expire only on first hit
    assert sum(1 for c in calls if c[0] == "expire") == 1


def test_session_store_set_get_delete_mocked():
    storage = {}

    class FakeClient:
        def set(self, key, val, ex=None):
            storage[key] = (val, ex)

        def get(self, key):
            v = storage.get(key)
            return v[0] if v else None

        def delete(self, *keys):
            n = 0
            for k in keys:
                if storage.pop(k, None) is not None:
                    n += 1
            return n

    store = authz._RedisSessionStore(FakeClient(), "maybot")
    store.put("sid", {"role": "viewer", "expires": time.time() + 100})
    key = "maybot:sess:sid"
    assert key in storage
    assert storage[key][1] is not None and storage[key][1] <= 100  # TTL set
    got = store.get("sid")
    assert got and got["role"] == "viewer"
    assert store.delete("sid") is True
    assert store.get("sid") is None
