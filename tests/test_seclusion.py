from maybot_control_center import cultivation as c


def setup_function():
    c.clear()


def test_enter_and_exit_seclusion():
    st = c.enter_seclusion("Nova")
    assert st["in_seclusion"] is True
    assert st["seclusion_remaining"] > 0
    st2 = c.exit_seclusion("Nova")
    assert st2["in_seclusion"] is False


def test_seclusion_matures_into_a_breakthrough_and_technique(monkeypatch):
    monkeypatch.setattr(c, "SECLUSION_SECONDS", 1800)
    c.enter_seclusion("Nova")
    assert c.tick_seclusion("Nova") is False         # not matured yet
    # fast-forward past the seclusion period
    with c._lock:
        c._state["Nova"]["seclusion_since"] -= 2000
    assert c.tick_seclusion("Nova") is True
    st = c.state("Nova")
    assert st["realm_name"] == "Qi Condensation"      # guaranteed breakthrough (was Mortal)
    assert any(s.startswith("Dao Insight") for s in st["skills"])  # researched a technique
    assert st["event"] == "breakthrough"
    assert st["in_seclusion"] is True                 # keeps cultivating toward the next


def test_seclusion_consolidates_the_realm(monkeypatch):
    monkeypatch.setattr(c, "SECLUSION_SECONDS", 1)
    c.enter_seclusion("Nova")
    with c._lock:
        c._state["Nova"]["seclusion_since"] -= 5
    c.tick_seclusion("Nova")
    st = c.state("Nova")
    # stones brought up to at least the new realm's requirement (no instant deviation)
    assert st["stones"] >= 60  # Qi Condensation threshold
