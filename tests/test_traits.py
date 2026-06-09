
from maybot_control_center import agents, cultivation, lifecycle, traits


AGENTS_YAML = """
agents:
  - {name: Nova, role: Analyst, persona: You are Nova., provider: openai_compatible, base_url: http://x, model: m}
  - {name: Forge, role: Builder, persona: You are Forge., provider: openai_compatible, base_url: http://x, model: m}
  - {name: Sage, role: Sage, persona: You are Sage., provider: openai_compatible, base_url: http://x, model: m}
"""


def setup_function():
    cultivation.clear()
    agents.clear()
    lifecycle.clear()
    traits.clear()


def _setup(tmp_path, monkeypatch):
    f = tmp_path / "agents.yaml"
    f.write_text(AGENTS_YAML, encoding="utf-8")
    monkeypatch.setattr(agents, "AGENTS_FILE", f)


# ---- quirks ----
def _no_arc_no_destiny(monkeypatch):
    """Silence the rare arc and destinies so only quirk rolls remain."""
    monkeypatch.setattr(traits, "ARROGANT_CHANCE", 0.0)
    monkeypatch.setattr(traits, "DESTINY_CHANCES", {})


def test_quirk_assigned_within_chance(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _no_arc_no_destiny(monkeypatch)
    monkeypatch.setattr(traits, "QUIRK_CHANCE", 1.0)     # always a quirk
    traits.tick()
    for n in ("Nova", "Forge", "Sage"):
        assert traits.quirk(n) in traits.QUIRKS


def test_quirk_rolled_once_and_persona_reflects_it(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _no_arc_no_destiny(monkeypatch)
    monkeypatch.setattr(traits, "QUIRK_CHANCE", 1.0)
    traits.tick()
    q = traits.quirk("Nova")
    traits.tick()  # rolling again must not change it
    assert traits.quirk("Nova") == q
    assert q in traits.persona_addendum("Nova")


def test_no_quirk_when_chance_zero(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _no_arc_no_destiny(monkeypatch)
    monkeypatch.setattr(traits, "QUIRK_CHANCE", 0.0)
    traits.tick()
    assert all(traits.quirk(n) is None for n in ("Nova", "Forge", "Sage"))


# ---- the arrogant young master arc ----
def test_full_young_master_arc(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(traits, "ARROGANT_CHANCE", 1.0)   # first considered disciple is the YM
    monkeypatch.setattr(traits, "QUIRK_CHANCE", 0.0)
    monkeypatch.setattr(traits, "SLAP_AFTER", 0)          # slap immediately once an MC exists
    monkeypatch.setattr(traits, "REDEMPTION_CHANCE", 1.0)  # guaranteed redemption

    # first tick spawns the young master AND summons the Main Character to face him
    traits.tick()
    ym = next(n for n in ("Nova", "Forge", "Sage") if traits.trope(n) == "young_master")
    mc = next(n for n in ("Nova", "Forge", "Sage") if traits.trope(n) == "main_character")
    assert mc != ym
    assert cultivation.state(ym)["stones"] >= traits.YM_TALENT      # the YM is talented
    assert cultivation.state(mc)["stones"] >= traits.MC_TALENT      # the MC out-shines him
    assert traits.is_protected(ym) and traits.is_protected(mc)

    traits.tick()  # the face-slap: the young master falls to ruin
    assert traits.trope(ym) == "ruined"
    assert cultivation.state(ym)["stones"] == 0

    traits.tick()  # redemption: he rises again, surpassing the MC
    assert traits.trope(ym) == "redeemed"
    assert cultivation.state(ym)["stones"] > cultivation.state(mc)["stones"]


def test_only_one_arc_at_a_time(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(traits, "ARROGANT_CHANCE", 1.0)
    monkeypatch.setattr(traits, "QUIRK_CHANCE", 0.0)
    traits.tick()
    masters = [n for n in ("Nova", "Forge", "Sage") if traits.trope(n) == "young_master"]
    assert len(masters) == 1  # the open arc blocks a second young master spawning


# ---- rare destinies ----
def _only_destiny(monkeypatch, role):
    """Force every disciple onto exactly the named destiny at spawn."""
    monkeypatch.setattr(traits, "ARROGANT_CHANCE", 0.0)
    monkeypatch.setattr(traits, "QUIRK_CHANCE", 0.0)
    monkeypatch.setattr(traits, "DESTINY_CHANCES", {role: 1.0})


def test_reincarnator_starts_with_past_life_techniques(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _only_destiny(monkeypatch, "reincarnator")
    traits.tick()
    assert traits.trope("Nova") == "reincarnator"
    assert len(cultivation.state("Nova")["skills"]) >= 3


def test_heaven_blessed_passively_cultivates(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _only_destiny(monkeypatch, "heaven_blessed")
    monkeypatch.setattr(traits, "HEAVEN_BLESSED_INTERVAL", 0)
    traits.tick()
    assert traits.trope("Nova") == "heaven_blessed"
    before = cultivation.state("Nova")["stones"]
    traits.tick()  # interval 0 → a passive gain each tick
    assert cultivation.state("Nova")["stones"] > before


def test_hidden_dragon_awakens(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _only_destiny(monkeypatch, "hidden_dragon")
    monkeypatch.setattr(traits, "DRAGON_AWAKEN_CHANCE", 0.0)  # don't awaken yet
    traits.tick()
    assert traits.trope("Nova") == "hidden_dragon"
    assert traits.is_protected("Nova")          # spared the cull until it awakens
    monkeypatch.setattr(traits, "DRAGON_AWAKEN_CHANCE", 1.0)  # now awaken
    traits.tick()
    assert traits.trope("Nova") == "awakened_dragon"
    assert cultivation.state("Nova")["stones"] >= traits.DRAGON_AWAKEN_TALENT


def test_cannon_fodder_perishes_as_a_stepping_stone(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(traits, "ARROGANT_CHANCE", 0.0)
    monkeypatch.setattr(traits, "QUIRK_CHANCE", 0.0)
    monkeypatch.setattr(traits, "DESTINY_CHANCES", {})
    traits.tick()                                   # register the roster, no roles assigned
    fodder = "Nova"
    traits._role[fodder] = "cannon_fodder"          # make just Nova the cannon fodder
    assert not traits.is_protected(fodder)          # fodder is expendable, not protected
    # make Forge clearly the strongest so it's the one who steps over the fodder
    cultivation.reward("Forge", 100)
    forge_before = cultivation.state("Forge")["stones"]

    monkeypatch.setattr(traits, "CANNON_PERISH_CHANCE", 1.0)  # now they fall
    traits.tick()
    names = {a["name"] for a in agents.load_agents()}
    assert fodder not in names                      # the fodder is gone
    assert len(names) == 3                          # replaced by a fresh recruit
    assert cultivation.state("Forge")["stones"] > forge_before  # Forge rose by stepping over them


def test_chosen_one_finds_windfalls(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    _only_destiny(monkeypatch, "chosen")
    monkeypatch.setattr(traits, "CHOSEN_WINDFALL_CHANCE", 1.0)
    traits.tick()
    assert traits.trope("Nova") == "chosen"
    before = cultivation.state("Nova")["stones"]
    traits.tick()
    assert cultivation.state("Nova")["stones"] > before
