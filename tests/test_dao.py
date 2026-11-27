"""The deeper life of the sect: lineage, companions, heart demons, precepts, merit, discipline, the council,
alchemy, paths, seclusion, the kingdom, alliances and sieges, the demonic path, succession, rumours, graves."""
import copy
import random

import pytest

from sect_academy import colony, dao, state

T0 = 1_800_000_000.0


@pytest.fixture()
def st(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    s = state.reset_for_tests()
    colony._c(s, T0)["seed"] = 4242
    colony.setup(s, "Azure Lantern", "Jay", T0)
    c = s["colony"]
    c["guide"]["skip"] = True
    c["flags"]["first_threat"] = 1
    c["res"].update(rice=300.0, stones=100.0, wood=200.0, stone=200.0, herbs=60.0, pills=3.0)
    return s


def _answer(st, opt=None):
    c = st["colony"]
    ev = c["pending"]
    return colony.resolve(st, opt or ev["options"][-1]["id"], T0)


def test_master_and_disciple(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    m["step"] = 9
    assert not dao.apprentice(st, a["id"], b["id"], T0)["ok"]                      # b is no elder
    assert dao.apprentice(st, a["id"], m["id"], T0)["ok"] and a["mentor"] == m["id"]
    assert not dao.apprentice(st, b["id"], m["id"], T0)["ok"]                      # one personal disciple each
    assert any(lab.startswith("Taught by") for lab, _ in colony.qi_rate(c, a))
    a["step"], a["qi"] = 3, colony.step_need(3)
    assert any("watches over" in lab for lab, _ in colony.bt_odds(c, a))
    c["hour"] = 24 * 3 + 4
    colony.advance(st, 1, T0)
    assert a["xp_x"] == pytest.approx(1.3)
    v = next(x for x in colony.view(st, T0)["pawns"] if x["id"] == a["id"])
    assert v["mentor"] == "Jay" and v["mentors"] == []
    # the master of a disciple dies at an enemy's hands: grief, a last lesson, and a vendetta
    b["step"] = 12
    a["mentor"] = b["id"]
    foe = c["sects"][1]
    rel = foe["rel"]
    c["marks"]["last_foe"] = foe["id"]
    best = max(colony.SKILLS, key=lambda s: b["skills"][s]["lv"])
    lv = a["skills"][best]["lv"]
    colony._die(c, b)
    assert a["mentor"] == "" and a["skills"][best]["lv"] == min(20, lv + 2) and a["resolve_until"] > c["hour"] + 24 * 29
    assert foe["rel"] == rel - 20 and a["title"] == "the Avenger" and colony.view(st, T0)["tombs"][0]["name"] == b["name"]


def test_dao_companions_and_heart_demons(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    assert not dao.companion(st, a["id"], b["id"], T0)["ok"]
    colony._bond(c, a, b, 80)
    assert dao.companion(st, a["id"], b["id"], T0)["ok"] and a["companion"] == b["id"] and b["companion"] == a["id"]
    assert any("dao companion" in lab for lab, _ in colony.qi_rate(c, a)) and ("Has a dao companion", 4) in colony.mood_mods(c, a)
    # in a lost fight a companion takes the killing blow
    a["health"], b["health"] = 0.0, 90.0
    assert dao.saved_by_companion(c, a, [a, b]) and a["health"] == 8.0 and b["health"] == 65.0
    # a failed tribulation leaves a heart demon; it weighs on every later attempt until it is faced
    a["health"] = 100.0
    a["step"], a["qi"] = 11, colony.step_need(11)
    base = colony.bt_chance(c, a)
    dao.on_bt(c, a, False, False, True)
    assert a["demon"] == 1 and colony.bt_chance(c, a) == base - 8 and ("Heart demon", -3) in colony.mood_mods(c, a)
    assert dao.face_demon(st, a["id"], T0)["ok"] and [o["id"] for o in c["pending"]["options"]] == ["confront", "pill", "friend"]
    _answer(st, "pill")
    assert a["demon"] == 0 and c["res"]["pills"] == 2 and a["toxin"] == 1
    a["demon"] = 2
    outcomes = set()
    for seed in range(30):
        s2 = copy.deepcopy(st)
        s2["colony"]["seed"] = seed
        dao.face_demon(s2, a["id"], T0)
        _answer(s2, "confront")
        outcomes.add(s2["colony"]["pawns"][1]["demon"])
    assert outcomes == {0, 2}
    # losing a companion is the worst grief there is
    colony._die(c, b)
    assert a["companion"] == "" and a["demon"] == 3 and any(t["k"] == "companion_dead" and t["v"] == -25 for t in a["thoughts"])
    assert not dao.face_demon(st, m["id"], T0)["ok"]


def test_precepts_the_council_and_the_punishment_hall(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    for pid in ("strength", "compassion", "frugality"):
        assert dao.set_precept(st, pid, True, T0)["ok"]
    assert not dao.set_precept(st, "hospitality", True, T0)["ok"]                  # three at most
    power = colony.combat_power(c, a)
    dao.set_precept(st, "strength", False, T0)
    assert colony.combat_power(c, a) < power and any(t["k"] == "precept_drop" for t in a["thoughts"])
    dao.set_precept(st, "strength", True, T0)
    rival = colony._rival(c)
    colony._ask(c, "young_master", "t", "x", [("slap", "s"), ("endure", "e")], pawn=a["id"], src=rival["id"])
    opts = {o["id"]: o for o in colony.view(st, T0)["pending"]["options"]}
    assert opts["endure"]["warn"] == "Strength above all" and not opts["slap"]["warn"]
    _answer(st, "endure")
    assert all(any(t["k"] == "precept" for t in p["thoughts"]) for p in c["pawns"])
    # a refused choice leaves no trace: nobody reacts to something that did not happen
    for p in c["pawns"]:
        p["thoughts"] = []
    c["res"]["rice"] = 0.0
    colony._ask(c, "festival", "t", "x", [("hold", "h"), ("skip", "s")], name="F", flavour="f", cost=12)
    assert not _answer(st, "hold")["ok"] and c["pending"] and not any(p["thoughts"] for p in c["pawns"])
    _answer(st, "skip")
    # the council: two elders, and they have a view
    assert not colony.view(st, T0)["council"]
    a["step"] = b["step"] = 12
    c["res"]["rice"] = 300.0
    colony._ask(c, "festival", "t", "x", [("hold", "h"), ("skip", "s")], name="F", flavour="f", cost=12)
    opts = {o["id"]: o for o in colony.view(st, T0)["pending"]["options"]}
    assert colony.view(st, T0)["council"] and opts["hold"]["counsel"] and not opts["skip"]["counsel"]
    bond = colony.bond(c, m, a)
    _answer(st, "skip")
    assert colony.bond(c, m, a) == bond - 5 and any(t["k"] == "overruled" for t in a["thoughts"])
    # a brawl comes before the punishment hall
    a["step"] = b["step"] = 0
    dao.brawl(c, a, b)
    assert c["pending"]["kind"] == "discipline"
    _answer(st, "confine")
    assert a["away_until"] > c["hour"] and b["away_kind"].startswith("confined") and any(t["k"] == "order" for t in m["thoughts"])
    dao.brawl(c, a, b)
    a["merit"] = b["merit"] = 25.0
    _answer(st, "fine")
    assert a["merit"] == 15 and b["merit"] == 15


def test_merit_buys_artifacts_and_favouritism_is_noticed(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    art = colony._new_artifact(c, random.Random(1), "a test", quality=1, kind="sword")
    a["merit"], b["merit"] = 40.0, 10.0
    c["hour"] = 24 * 2 + 4
    colony.advance(st, 1, T0)
    assert art["owner"] == a["id"] and a["merit"] < 12
    art2 = colony._new_artifact(c, random.Random(2), "a test", quality=0, kind="charm")
    art["owner"] = ""
    a["merit"], b["merit"] = 60.0, 0.0
    colony.equip(st, b["id"], art2["id"], T0)                                      # b did nothing to earn it
    assert any(t["k"] == "merit_ignored" for t in a["thoughts"])
    doing = a["doing"]
    a["doing"], a["merit"] = "farm", 0.0
    dao.hourly(c, False)
    assert a["merit"] > 0
    a["doing"] = doing


def test_alchemy_paths_and_seclusion(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    # recipes: the hall brews what it is set to when the rare herbs allow, and a clumsy hand can ruin a batch
    assert dao.set_recipe(st, "marrow", T0)["ok"] and not dao.set_recipe(st, "gold", T0)["ok"]
    pills = c["res"]["pills"]
    dao.brew(c, a)                                                                 # no rare herbs: ordinary pill
    assert c["res"]["pills"] == pills + 1 and c["elixirs"]["marrow"] == 0
    made = ruined = 0
    for seed in range(40):
        s2 = copy.deepcopy(st)
        c2 = s2["colony"]
        c2["seed"], c2["rare"] = seed, 5.0
        c2["pawns"][1]["skills"]["craft"]["lv"] = 4
        dao.brew(c2, c2["pawns"][1])
        assert c2["rare"] == 3
        made += c2["elixirs"]["marrow"]
        ruined += 1 - c2["elixirs"]["marrow"]
    assert made > ruined > 0
    c["elixirs"]["marrow"] = 1
    root = a["root_mult"]
    assert dao.take_marrow(st, a["id"], T0)["ok"] and a["root_mult"] == pytest.approx(root + 0.08) and a["toxin"] == 2
    c["elixirs"]["marrow"] = 1
    assert not dao.take_marrow(st, a["id"], T0)["ok"]                              # once per disciple
    for _ in range(3):
        colony.use_pill(st, a["id"], T0)
    assert a["toxin"] == 5 and ("Pill toxin", -4) in colony.mood_mods(c, a)
    # berserk pills are an option at the gate
    c["elixirs"]["berserk"] = 1
    colony._omen(c, random.Random(1), "beasts")
    assert "berserk" in [o["id"] for o in c["pending"]["options"]]
    hp = a["health"]
    _answer(st, "berserk")
    assert c["elixirs"]["berserk"] == 0 and a["health"] < hp
    # paths: chosen once, at Foundation Establishment
    assert not dao.set_path(st, a["id"], "sword", T0)["ok"]
    a["step"] = 8
    a["health"] = 100.0
    assert any("choose a path" in x["text"] for x in colony.view(st, T0)["alerts"])
    assert dao.set_path(st, a["id"], "sword", T0)["ok"]
    with_path = colony.combat_power(c, a)
    a["path"] = ""
    assert with_path == pytest.approx(colony.combat_power(c, a) * 1.2)
    a["path"] = "sword"
    assert not dao.set_path(st, a["id"], "body", T0)["ok"]
    c["rooms"]["ward"] = 2
    b["step"] = 8
    d0 = colony.defense(c)
    dao.set_path(st, b["id"], "formation", T0)
    assert colony.defense(c) == pytest.approx(d0 + 0.12 * colony.ward_power(c))
    # closed-door seclusion: gone twelve days, back with a great deal of qi
    a["qi"] = 0.0
    assert dao.retreat(st, a["id"], T0)["ok"] and a["away_until"] == c["hour"] + 288 and not dao.retreat(st, m["id"], T0)["ok"]
    a["away_until"] = c["hour"]
    assert dao.later(c, {"kind": "retreat_return", "pawn": a["id"]}, random.Random(5)) and (a["qi"] > 0 or a["step"] > 8)


def test_the_kingdom_alliances_and_a_three_stage_siege(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    # the lord's favour
    c["kingdom"] = -40.0
    assert colony.view(st, T0)["kingdom"]["stance"] == "Resentful"
    assert dao.raise_event(c, random.Random(1), "taxes") and c["pending"]["kind"] == "taxes"
    _answer(st, "pay")
    assert c["kingdom"] == -30 and c["res"]["rice"] == 280
    dao.raise_event(c, random.Random(1), "taxes")
    _answer(st, "refuse")
    assert c["pending"]["kind"] == "omen" and "soldiers" in c["pending"]["text"]
    _answer(st, "fight")
    c["kingdom"] = 40.0
    c["hour"] = 24 * 27 + 5
    c["festival"] = "1-2"
    c["res"]["rice"] = 50.0
    rice = c["res"]["rice"]
    colony.advance(st, 1, T0)
    assert any(e["title"] == "The lord's harvest gift" for e in c["log"]) and c["res"]["rice"] >= rice + 30
    if c["pending"]:
        _answer(st)
    # alliances: sworn at +50, and allies come when called
    s = c["sects"][0]
    assert not dao.ally(st, s["id"], T0)["ok"]
    s["rel"] = 60.0
    stones = c["res"]["stones"]
    assert dao.ally(st, s["id"], T0)["ok"] and s["ally"] and c["res"]["stones"] == stones - 20
    assert dao.ally_aid(c, None) == pytest.approx(0.2 * colony.defense(c)) and dao.ally_aid(c, s) == 0
    assert next(x for x in colony.view(st, T0)["sects"] if x["id"] == s["id"])["ally"]
    s["rel"] = 10.0
    dao.daily(c, False)
    assert not s["ally"]
    # a blood feud becomes a siege: three battles, each harder, and victory breaks them
    foe = c["sects"][1]
    foe["rel"] = -70.0
    for p in c["pawns"]:
        p["skills"]["combat"]["lv"] = 20
        p["step"] = 12
        p["health"] = 100.0
    c["rooms"]["ward"] = 5
    c["hour"] = 24 * 40 + 5
    c["festival"] = "1-3"
    c["tournament_year"] = 1
    strengths = []
    for _ in range(24 * 16):
        colony.advance(st, 1, T0)
        ev = c["pending"]
        if ev:
            if ev["kind"] == "omen" and "siege" in ev["text"].lower():
                strengths.append(ev["strength"])
                assert colony.view(st, T0)["siege"]["sect"] == foe["name"]
                _answer(st, "fight")
            else:
                _answer(st)
        for p in c["pawns"]:
            p["health"] = 100.0
        if not c["siege"] and len(strengths) == 3:
            break
    assert len(strengths) == 3 and c["siege"] is None and foe["power"] <= 0.6 and foe["rel"] <= -10
    assert any("ended in victory" in x["text"] for x in c["annals"]) and any("carved on the cliff" in x["text"] for x in c["annals"])


def test_the_demonic_path_a_reincarnated_ancient_and_succession(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    # the sutra, kept too long, asks for more
    c["manuals"].append("blood_sutra")
    c["sutra_days"] = 20
    c["hour"] = 24 * 20 + 5
    c["festival"] = "1-1"
    colony.advance(st, 1, T0)
    assert c["pending"]["kind"] == "embrace"
    burned = copy.deepcopy(st)
    _answer(burned, "burn")
    assert "blood_sutra" not in burned["colony"]["manuals"] and not burned["colony"]["demonic"]
    righteous = next(s for s in c["sects"] if s["kind"] == "righteous")
    rel = righteous["rel"]
    _answer(st, "embrace")
    assert c["demonic"] and righteous["rel"] == rel - 40 and colony.view(st, T0)["demonic"]
    assert ("The demonic path", 1.25) in colony.qi_rate(c, a)
    righteous["rel"] = 80.0
    assert not dao.ally(st, righteous["id"], T0)["ok"]
    qi = a["qi"]
    dao.after_fight(c, [a], 1.5, "fight", None, "beasts")
    assert a["qi"] > qi or a["step"] > 0                                           # qi taken at the gate
    # a child who has walked the road before
    assert dao.raise_event(c, random.Random(2), "prodigy") and c["pending"]["cand"]["ancient"] == 1
    _answer(st, "accept")
    kid = c["pawns"][-1]
    assert ("Uncanny comprehension", 1.4) in colony.qi_rate(c, kid)
    dao.on_bt(c, kid, True, False, False)
    assert kid["ancient"] == 2 and ("Has walked this road before", 1.8) in colony.qi_rate(c, kid)
    nem = next(x for x in c["later"] if x["kind"] == "nemesis")
    assert dao.later(c, nem, random.Random(1)) and "Nine Nether Palace" in c["pending"]["text"]
    _answer(st, "fight")
    # the founder ascends, names an heir, and leaves a blessing shaped by how the sect was run
    a["step"] = 20
    dao.succession(c)
    assert c["pending"]["kind"] == "succession" and c["pending"]["options"][0]["id"] == a["id"]
    _answer(st, a["id"])
    assert a["master"] and m not in c["pawns"] and c["blessings"] == ["dread"] and colony._master(c) is a
    assert colony.combat_power(c, a) > 0 and any("became Sect Master" in x["text"] for x in c["annals"])
    assert colony.view(st, T0)["master"] == a["name"] and colony.view(st, T0)["blessings"]


def test_rumours_the_graveyard_and_a_long_fuzzed_life(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    c["later"].append({"at": c["hour"] + 30, "kind": "elder", "src": c["sects"][0]["id"]})
    assert any(c["sects"][0]["name"] in x for x in colony.view(st, T0)["rumours"])
    # tomb-sweeping: grief is set down
    c["later"] = []
    colony._die(c, b)
    a["demon"] = 1
    assert any(t["k"] == "death" for t in a["thoughts"])
    c["hour"] = 24 * 50 + 5                                                        # spring of year two
    c["festival"] = "2-0"
    c["recruit_year"] = 2
    colony.advance(st, 1, T0)
    assert c["pending"]["kind"] == "qingming"
    _answer(st, "visit")
    assert not any(t["k"] == "death" for t in a["thoughts"]) and a["demon"] == 0 and c["marks"]["qingming"] == 2
    # two years of random choices, random orders: nothing may break, and a save must round-trip
    for seed in range(6):
        s2 = copy.deepcopy(st)
        c2 = s2["colony"]
        c2["seed"] = seed
        c2["storyteller"] = "harsh"
        c2["rooms"].update(main_hall=5, dormitory=5, alchemy=2, ward=2, fields=5, library=1, training=1)
        r = random.Random(seed)
        for h in range(24 * 96):
            colony.advance(s2, 1, T0)
            if c2["pending"]:
                colony.resolve(s2, r.choice(c2["pending"]["options"])["id"], T0)
                if c2["pending"]:
                    colony.resolve(s2, c2["pending"]["options"][-1]["id"], T0)
            if h % 37 == 0 and c2["pawns"]:
                p = r.choice(c2["pawns"])
                o = r.choice(c2["pawns"])
                r.choice([lambda: dao.apprentice(s2, p["id"], o["id"], T0), lambda: dao.companion(s2, p["id"], o["id"], T0),
                          lambda: dao.face_demon(s2, p["id"], T0), lambda: dao.set_precept(s2, r.choice(list(dao.PRECEPTS)), r.random() < 0.7, T0),
                          lambda: dao.set_path(s2, p["id"], r.choice(list(dao.PATHS)), T0), lambda: dao.retreat(s2, p["id"], T0),
                          lambda: dao.set_recipe(s2, r.choice(list(dao.RECIPES)), T0), lambda: dao.take_marrow(s2, p["id"], T0),
                          lambda: dao.ally(s2, r.choice(c2["sects"])["id"], T0), lambda: colony.forge(s2, T0),
                          lambda: colony.expedition(s2, r.choice(list(colony.PLACES)), T0), lambda: colony.attempt(s2, p["id"], T0),
                          lambda: colony.set_direct(s2, p["id"], r.random() < 0.5, T0)])()
            c2["res"]["rice"] = max(c2["res"]["rice"], 60.0)
            c2["res"]["stones"] = max(c2["res"]["stones"], 30.0)
        v = colony.view(s2, T0)
        assert v["pawns"] and sum(1 for p in v["pawns"] if p["master"]) == 1
        back = colony.sanitize(copy.deepcopy(c2), T0)
        assert back and len(back["pawns"]) == len(c2["pawns"]) and back["precepts"] == c2["precepts"]


def test_a_breakthrough_is_graded_by_preparation_and_ends_in_a_chosen_fate(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    a["step"], a["qi"], a["health"], a["mood"] = 3, colony.step_need(3), 100.0, 50.0
    c["res"]["pills"] = 0.0
    a["element"] = "metal"                                                         # not spring's element
    grade, checks = dao.bt_grade(c, a)
    assert grade == 1 and sum(ok for _, ok in checks) == 2                        # healthy, and nothing weighing on them
    v = next(x for x in colony.view(st, T0)["pawns"] if x["id"] == a["id"])
    assert v["grade"]["name"] == "Common" and len(v["grade"]["checks"]) == 8
    # arrange things: a calm heart, a pill, a friend on watch, the right season, a good chamber
    a["mood"], a["element"] = 80.0, "wood"
    c["res"]["pills"] = 2.0
    colony._bond(c, a, b, 40)
    c["rooms"]["meditation"] = 2
    assert dao.bt_grade(c, a)[0] == 3
    root = a["root_mult"]
    for seed in range(40):
        s2 = copy.deepcopy(st)
        c2 = s2["colony"]
        c2["seed"] = seed
        res = colony.attempt(s2, a["id"], T0)
        if res["success"]:
            a2 = c2["pawns"][1]
            assert a2["root_mult"] == pytest.approx(root + 0.07) and "superior foundation" in res["event"]["text"]
            ev = c2["pending"]
            assert ev["kind"] == "fate" and len(ev["options"]) == 3
            again = copy.deepcopy(s2)                                              # the same three every time: no rerolling
            assert [o["id"] for o in again["colony"]["pending"]["options"]] == [o["id"] for o in ev["options"]]
            pick = ev["options"][0]["id"]
            colony.resolve(s2, pick, T0)
            assert a2["fates"] == [pick] and next(x for x in colony.view(s2, T0)["pawns"] if x["id"] == a2["id"])["fates"][0]["name"] == dao.FATES[pick]["name"]
            break
    else:
        raise AssertionError("no success in 40 seeds")
    # fates are trades, and they show in the ledgers
    a["fates"] = ["hungry_ghost", "sword_heart", "clear_mind"]
    assert ("Fate: Hungry Ghost Meridians", 1.12) in colony.qi_rate(c, a) and dao.hunger_x(c, a) == pytest.approx(1.2)
    assert ("Fate: Sword Heart", -2) in colony.mood_mods(c, a) and ("Fate: Clear Mind", 5) in colony.bt_odds(c, a)
    # a rare fate needs a well-prepared breakthrough
    assert not any(dao.FATES[o["id"]].get("rare") for s_ in range(30) for o in _fate_opts(st, a, 2, s_))
    assert any(dao.FATES[o["id"]].get("rare") for s_ in range(30) for o in _fate_opts(st, a, 4, s_))


def _fate_opts(st, a, grade, seed):
    s2 = copy.deepcopy(st)
    c2 = s2["colony"]
    c2["seed"] = seed
    p = c2["pawns"][1]
    p["fates"] = []
    c2["pending"] = None
    dao.offer_fate(c2, p, grade)
    return c2["pending"]["options"]


def test_beasts_branches_karma_banner_and_the_map(st):
    c = st["colony"]
    m, a, b = c["pawns"]
    # a spirit beast chooses a disciple
    power = colony.combat_power(c, a)
    assert dao.raise_event(c, random.Random(3), "beast_bond")
    owner = next(p for p in c["pawns"] if p.get("beast"))
    assert colony.combat_power(c, owner) > (power if owner is a else 0) and any("at their heel" in lab for lab, _ in colony.mood_mods(c, owner))
    # karma is kept quietly and felt at the tribulation
    colony._ask(c, "village", "t", "x", [("send", "s"), ("decline", "d")], pawn=a["id"])
    _answer(st, "decline")
    assert c["karma"] == -3
    c["karma"] = -25.0
    a["step"], a["qi"] = 3, colony.step_need(3)
    assert ("The sect's karmic debt", -6) in colony.bt_odds(c, a) and any("hush their children" in x for x in colony.view(st, T0)["rumours"])
    c["karma"] = 25.0
    assert ("Heaven remembers the sect's kindness", 4) in colony.bt_odds(c, a)
    # banner and motto: a known colour, and text that is only ever text
    assert dao.set_style(st, "jade", "  Ask the   mountain <b>first</b>  ", T0)["ok"] and not dao.set_style(st, "puce", "x", T0)["ok"]
    v = colony.view(st, T0)
    assert v["style"] == {"colour": "jade", "hex": "#3fae82", "motto": "Ask the mountain <b>first</b>"} and len(dao.set_style(st, "", "x" * 200, T0)) and len(c["style"]["motto"]) == 60
    # the map knows home, the places, and every sect
    kinds = [x["kind"] for x in v["map"]]
    assert kinds.count("home") == 1 and kinds.count("place") == 6 and len(v["map"]) == 10 and all(0 <= x["x"] <= 100 and 0 <= x["y"] <= 100 for x in v["map"])
    # a branch sect: an elder and two disciples leave for good, and tribute comes home
    a["step"] = 12
    assert not dao.found_branch(st, a["id"], T0)["ok"]                             # the sect is too small
    for i in range(6):
        c["pawns"].append(colony._make_pawn(c, 70 + i))
    c["rooms"]["main_hall"] = 4
    assert not dao.found_branch(st, m["id"], T0)["ok"] and dao.found_branch(st, a["id"], T0)["ok"]
    assert len(c["pawns"]) == 6 and a not in c["pawns"] and c["res"]["stones"] == 0 and c["branches"][0]["leader"] == a["name"]
    assert any(x["kind"] == "branch" for x in colony.view(st, T0)["map"])
    c["storyteller"] = "calm"
    c["festival"] = "9-9"
    rice = c["res"]["rice"] = 20.0
    for _ in range(24 * 13):
        colony.advance(st, 1, T0)
        if c["pending"]:
            _answer(st)
        c["res"]["rice"] = max(c["res"]["rice"], 20.0)
    assert any(e["title"].startswith("Tribute from") for e in c["log"]) or c["res"]["stones"] >= 5
    assert rice == 20.0
    back = colony.sanitize(copy.deepcopy(c), T0)
    assert back["branches"] == c["branches"] and back["style"]["colour"] == "jade" and back["karma"] == c["karma"]


def test_expeditions_you_staff_and_steer(st):
    from sect_academy import road
    c = st["colony"]
    m, a, b = c["pawns"]
    assert not colony.expedition(st, "ruins", T0, [m["id"]], "bold")["ok"]         # the Sect Master stays
    a["skills"]["scholar"]["lv"] = 12
    assert colony.expedition(st, "ruins", T0, [a["id"]], "bold")["ok"]
    assert a["away_until"] > c["hour"] and b["away_until"] <= c["hour"]            # only who you named
    ret = next(x for x in c["later"] if x["kind"] == "trip_return")
    assert ret["stance"] == "bold" and ret["risk_x"] == 1.4 and c["trip_plan"]["pawns"] == [a["id"]]
    # halfway there the party sends word, and what you can do depends on who went
    for _ in range(26):
        colony.advance(st, 1, T0)
        if c["pending"] and c["pending"]["kind"] != "trip_choice":
            _answer(st)
    ev = c["pending"]
    assert ev["kind"] == "trip_choice" and a["name"] in ev["options"][1]["label"] and "scholarship 12" in ev["options"][1]["label"]
    manuals = len(c["manuals"])
    _answer(st, "read")
    assert ret["bonus"] == "manual"
    for _ in range(30):
        colony.advance(st, 1, T0)
        if c["pending"]:
            _answer(st)
    assert len(c["manuals"]) >= manuals + 1 and not any(x["kind"] in ("trip_return", "trip_mid") for x in c["later"])
    # a standing order sends the same party again
    assert road.set_standing(st, 0, True, T0)["ok"]
    a["health"] = 100.0
    c["hour"] = (c["hour"] // 24 + 1) * 24 + 4
    colony.advance(st, 1, T0)
    assert any(x["kind"] == "trip_return" for x in c["later"]) and c["log"][-1]["title"].startswith("Standing order")
    assert colony.view(st, T0)["trip_plan"]["who"] == [a["name"]] and colony.view(st, T0)["standing"]["repeat"]


def test_trust_between_master_and_disciple_has_three_stations(st):
    from sect_academy import road
    c = st["colony"]
    m, a, b = c["pawns"]
    m["step"] = 9
    dao.apprentice(st, a["id"], m["id"], T0)
    best = max(colony.SKILLS, key=lambda s: m["skills"][s]["lv"])
    lv = a["skills"][best]["lv"]
    road._trust(c, a, 31)
    assert a["stations"] == 1 and a["skills"][best]["lv"] == min(20, lv + 2) and any("told the story" in e["title"] for e in c["log"])
    road._trust(c, a, 30)
    assert a["stations"] == 2 and ("Their master's private teaching", 1.08) in colony.qi_rate(c, a)
    road._trust(c, a, 30)
    a["step"], a["qi"] = 3, colony.step_need(3)
    assert a["stations"] == 3 and ("Heir to their master's line", 5) in colony.bt_odds(c, a) and a["title"].startswith("Heir of")
    v = next(x for x in colony.view(st, T0)["pawns"] if x["id"] == a["id"])
    assert v["trust"] == 91 and [s["done"] for s in v["station_marks"]] == [True, True, True]
    road._trust(c, b, 50)                                                           # no master, no track
    assert b["trust"] == 0
    t = a["trust"] = 10.0
    road.daily(c, False)
    assert a["trust"] > t                                                           # a day at home together


def test_named_rivals_advance_by_a_rule_you_can_read(st):
    from sect_academy import road
    c = st["colony"]
    v = colony.view(st, T0)
    s = c["sects"][0]
    info = v["champs"][s["id"]]
    assert len(info["list"]) == 2 and info["list"][0]["name"] == s["young"] and info["every"] == road.champ_days(s)
    before = [ch["step"] for ch in s["champs"]]
    for _ in range(road.champ_days(s)):
        road.daily(c, True)
    assert [ch["step"] for ch in s["champs"]] == [x + 1 for x in before]            # exactly as the rule says, no hidden growth
    champ = road.champion(c, s)
    assert champ["step"] == max(ch["step"] for ch in s["champs"])
    lo, hi = road.champ_power(champ) * 0.85, road.champ_power(champ) * 1.15
    assert all(lo <= road.tournament_foe(c, s, random.Random(i)) <= hi for i in range(20))
    # the tournament names who was beaten
    for p in c["pawns"]:
        p["skills"]["combat"]["lv"], p["step"] = 20, 20
    colony._ask(c, "tournament", "t", "x", [(c["pawns"][1]["id"], "go"), ("decline", "no")])
    res = _answer(st, c["pawns"][1]["id"])
    assert any(ch["name"] in res["event"]["text"] for sx in c["sects"] for ch in sx["champs"])


def test_meridians_realm_requirements_and_standing_orders(st):
    from sect_academy import road
    c = st["colony"]
    m, a, b = c["pawns"]
    # meridians: a point per stage, prerequisites, and conditions you can read
    assert road.points(a) == 0 and not road.open_node(st, a["id"], "sea", T0)["ok"]
    a["step"] = 4
    assert road.points(a) == 4 and not road.open_node(st, a["id"], "pillow", T0)["ok"]      # Sea of Qi first
    assert road.open_node(st, a["id"], "sea", T0)["ok"] and road.open_node(st, a["id"], "pillow", T0)["ok"] and road.points(a) == 2
    assert ("Meridian: Sea of Qi", 1.04) in colony.qi_rate(c, a) and not road.open_node(st, a["id"], "sea", T0)["ok"]
    assert "friend" in road.open_node(st, a["id"], "linked", T0)["error"]
    colony._bond(c, a, b, 40)
    assert road.open_node(st, a["id"], "linked", T0)["ok"] and ("Meridian: Linked Hearts", 1.06) in colony.qi_rate(c, a)
    power = colony.combat_power(c, a)
    assert road.open_node(st, a["id"], "wrist", T0)["ok"] and colony.combat_power(c, a) == pytest.approx(power * 1.05) and road.points(a) == 0
    nodes = {n["id"]: n for n in next(x for x in colony.view(st, T0)["pawns"] if x["id"] == a["id"])["meridians"]}
    assert nodes["sea"]["open"] and nodes["heaven"]["blocked"] and len(nodes) == 12
    # each great realm asks for one thing, with two ways to have it
    a["step"], a["qi"] = 7, colony.step_need(7)                                    # at the door of Foundation Establishment
    c["res"]["pills"] = 0.0
    gate = next(x for x in colony.view(st, T0)["pawns"] if x["id"] == a["id"])["gate"]
    assert not gate["ok"] and "pill" in gate["text"] and "Meditation Chamber" in gate["text"]
    assert colony.attempt(st, a["id"], T0)["error"] == gate["text"]
    c["rooms"]["meditation"] = 1                                                    # the second route
    assert road.realm_gate(c, a)[0]
    a["step"] = 3
    assert road.realm_gate(c, a) == (True, "")                                      # the first great realm asks nothing
    a["step"] = 15
    assert not road.realm_gate(c, a)[0]
    c["rooms"]["ward"] = 3
    assert road.realm_gate(c, a)[0]
    # standing orders: keep pills in stock, and saved priorities
    c["rooms"]["alchemy"] = 1
    c["res"].update(pills=0.0, herbs=30.0)
    a["step"] = 0
    a["skills"]["craft"]["lv"], b["skills"]["craft"]["lv"], m["skills"]["craft"]["lv"] = 15, 2, 1
    a["prio"]["craft"] = 0                                                          # even with brewing switched off for them
    assert colony._pick_job(c, a, {}) != "craft"
    road.set_standing(st, 3, False, T0)
    assert colony._pick_job(c, a, {}) == "craft" and colony._pick_job(c, b, {}) != "craft"
    assert any(e["title"] == "Standing order: brewing" for e in c["log"])
    c["res"]["pills"] = 3.0
    assert colony._pick_job(c, a, {}) != "craft"
    assert not road.preset_apply(st, "war", T0)["ok"] and not road.preset_save(st, "lunch", T0)["ok"]
    road.preset_save(st, "peace", T0)
    for p in c["pawns"]:
        p["prio"]["train"] = 1
    road.preset_save(st, "war", T0)
    road.preset_apply(st, "peace", T0)
    assert all(p["prio"]["train"] != 1 for p in c["pawns"]) and colony.view(st, T0)["presets"] == ["peace", "war"]
    road.preset_apply(st, "war", T0)
    assert all(p["prio"]["train"] == 1 for p in c["pawns"])
    back = colony.sanitize(copy.deepcopy(c), T0)
    assert back["standing"] == {"pills": 3, "repeat": False} and set(back["presets"]) == {"peace", "war"} and back["pawns"][1]["meridians"] == a["meridians"]
