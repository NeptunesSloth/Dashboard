from maybot_control_center import ascension, cultivation


def setup_function():
    cultivation.clear()


def _set_realm(agent, realm):
    with cultivation._lock:
        st = cultivation._state.get(agent) or cultivation._blank(agent)
        cultivation._state[agent] = st
        st["realm"] = realm


def test_low_realm_keeps_base(monkeypatch):
    monkeypatch.setattr(ascension, "ENABLED", True)
    _set_realm("Nova", 1)
    assert ascension.model_for("Nova", "claude-haiku-4-5") == "claude-haiku-4-5"


def test_realm_unlocks_sonnet_then_opus(monkeypatch):
    monkeypatch.setattr(ascension, "ENABLED", True)
    monkeypatch.setattr(ascension, "SONNET_REALM", 4)
    monkeypatch.setattr(ascension, "OPUS_REALM", 8)
    _set_realm("Nova", 5)
    assert ascension.model_for("Nova", "claude-haiku-4-5") == "claude-sonnet-4-6"
    _set_realm("Nova", 9)
    assert ascension.model_for("Nova", "claude-haiku-4-5") == "claude-opus-4-8"


def test_never_downgrades(monkeypatch):
    monkeypatch.setattr(ascension, "ENABLED", True)
    monkeypatch.setattr(ascension, "SONNET_REALM", 4)
    _set_realm("Nova", 5)
    # already on opus → stays opus even though realm only unlocks sonnet
    assert ascension.model_for("Nova", "claude-opus-4-8") == "claude-opus-4-8"


def test_non_claude_family_untouched(monkeypatch):
    monkeypatch.setattr(ascension, "ENABLED", True)
    _set_realm("Nova", 12)
    assert ascension.model_for("Nova", "llama3") == "llama3"   # don't swap providers


def test_disabled(monkeypatch):
    monkeypatch.setattr(ascension, "ENABLED", False)
    _set_realm("Nova", 12)
    assert ascension.model_for("Nova", "claude-haiku-4-5") == "claude-haiku-4-5"


def test_status_shape(monkeypatch):
    monkeypatch.setattr(ascension, "ENABLED", True)
    monkeypatch.setattr(ascension, "SONNET_REALM", 4)
    _set_realm("Nova", 6)
    s = ascension.status("Nova", "claude-haiku-4-5")
    assert s["ascended"] is True and s["model"] == "claude-sonnet-4-6" and s["base"] == "claude-haiku-4-5"
