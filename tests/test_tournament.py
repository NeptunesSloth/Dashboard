import pytest

from maybot_control_center import agents, cultivation, governance, tournament


AGENTS_YAML = """
agents:
  - {name: Nova, role: Analyst, persona: p, provider: openai_compatible, base_url: http://x, model: m}
  - {name: Forge, role: Builder, persona: p, provider: openai_compatible, base_url: http://x, model: m}
  - {name: Sage, role: Sage, persona: p, provider: openai_compatible, base_url: http://x, model: m}
  - {name: Ember, role: Smith, persona: p, provider: openai_compatible, base_url: http://x, model: m}
"""


def setup_function():
    cultivation.clear()
    governance.clear()
    agents.clear()
    tournament.clear()


def _setup(tmp_path, monkeypatch, yaml_txt=AGENTS_YAML):
    f = tmp_path / "agents.yaml"
    f.write_text(yaml_txt, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


def _set_realm(name, realm):
    cultivation._state[name] = {**cultivation._blank(name), "realm": realm}


def test_bracket_structure_and_single_champion(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    b = tournament.hold()
    # 4 disciples → 2 rounds (semis, final)
    assert len(b["rounds"]) == 2
    assert len(b["rounds"][0]) == 2 and len(b["rounds"][1]) == 1
    assert b["champion"] in {"Nova", "Forge", "Sage", "Ember"}
    assert b["finalist"] and b["finalist"] != b["champion"]


def _seed_by_realm(monkeypatch):
    """Standing pulls in reputation/usage/tools; isolate by seeding on realm alone."""
    monkeypatch.setattr(tournament, "_standing", lambda n: float(cultivation.realm_of(n)))


def test_top_seed_meets_bottom_first(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _seed_by_realm(monkeypatch)
    _set_realm("Nova", 8)   # strongest
    _set_realm("Forge", 6)
    _set_realm("Sage", 4)
    _set_realm("Ember", 1)  # weakest
    b = tournament.hold()
    assert b["seeds"][0] == "Nova" and b["seeds"][-1] == "Ember"
    # standard seeding: the #1 seed faces the #4 seed in the first round
    first_round_pairs = {frozenset([m["a"], m["b"]]) for m in b["rounds"][0]}
    assert frozenset(["Nova", "Ember"]) in first_round_pairs


def test_champion_is_rewarded(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(tournament, "REWARD", 120)
    _seed_by_realm(monkeypatch)
    # deterministic resolver: the higher-seeded disciple always wins (no upsets)
    monkeypatch.setattr(tournament, "_winner",
                        lambda a, b, s: a if b is None else (b if a is None else (a if s.get(a, 0) >= s.get(b, 0) else b)))
    _set_realm("Nova", 8)
    _set_realm("Forge", 7)
    _set_realm("Sage", 6)
    _set_realm("Ember", 5)
    before = cultivation.state("Nova")["stones"]
    b = tournament.hold()
    assert b["champion"] == "Nova"                       # the strongest wins when upsets are off
    assert cultivation.state("Nova")["stones"] == before + 120


def test_byes_for_non_power_of_two(tmp_path, monkeypatch):
    yaml_txt = AGENTS_YAML + "  - {name: Quill, role: Scribe, persona: p, provider: openai_compatible, base_url: http://x, model: m}\n"
    _setup(tmp_path, monkeypatch, yaml_txt)
    b = tournament.hold()  # 5 disciples → padded to 8, 3 rounds with byes
    assert len(b["rounds"]) == 3
    byes = [m for m in b["rounds"][0] if m["a"] is None or m["b"] is None]
    assert byes  # at least one bye exists in the first round


def test_needs_two_disciples(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch,
           "agents:\n  - {name: Solo, role: r, persona: p, provider: openai_compatible, base_url: http://x, model: m}\n")
    with pytest.raises(ValueError):
        tournament.hold()


def test_auto_tick_respects_interval(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(tournament, "AUTO_INTERVAL", 0)
    assert tournament.auto_tick() is None              # disabled → no-op
    monkeypatch.setattr(tournament, "AUTO_INTERVAL", 1000)
    tournament._auto_ts = 0.0
    assert tournament.auto_tick() is not None           # first call is due
    assert tournament.auto_tick() is None               # within interval → no-op
