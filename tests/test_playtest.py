"""Regressions from a 60-day playtest: what the player is told must match what the sim does."""
import copy
import random

import pytest

from sect_academy import colony, dao, state

T0 = 1_800_000_000.0


@pytest.fixture()
def st(monkeypatch):
    monkeypatch.setenv("SECT_ACADEMY_FILE", ":memory:")
    s = state.reset_for_tests()
    colony._c(s, T0)["seed"] = 12345
    colony.setup(s, "Azure Lantern", "Jay", T0)
    return s


def _force(monkeypatch, c, kind, day=10):
    """Raise one particular daily event on a quiet day."""
    c["hour"] = 24 * day + 5
    c["flags"]["first_threat"] = 1
    c["festival"] = f"1-{colony._season(c)}"
    c["pending"] = None
    monkeypatch.setitem(colony.STORYTELLERS[c["storyteller"]], "event", 5.0)
    real = random.Random.choices
    monkeypatch.setattr(random.Random, "choices", lambda self, pop, weights=None, **kw: [kind] if kind in pop else real(self, pop, weights, **kw))
    colony._daily_event(c)
    monkeypatch.setattr(random.Random, "choices", real)
    return c["pending"]


def test_the_duel_pact_says_the_time_it_takes(st, monkeypatch):
    c = st["colony"]
    ev = _force(monkeypatch, c, "engagement")
    assert ev and ev["kind"] == "engagement"
    pact = next(o["label"] for o in ev["options"] if o["id"] == "pact")
    assert "year" not in pact.lower() and "Twelve days" in pact
    colony.resolve(st, "pact", T0)
    due = next(x for x in c["later"] if x["kind"] == "pact_duel")
    assert due["at"] - c["hour"] == 24 * 12
    assert "year" not in c["log"][-1]["title"]


def test_a_daily_event_does_not_come_back_within_its_cooldown(st):
    seen_at: dict[str, list[int]] = {}
    for seed in range(8):
        s = copy.deepcopy(st)
        c = s["colony"]
        c["seed"] = seed
        c["storyteller"] = "harsh"
        c["rooms"].update(main_hall=4, dormitory=4)
        for _ in range(24 * 70):
            before = dict(c["flags"].get("seen", {}))
            colony.advance(s, 1, T0)
            for k, d in c["flags"].get("seen", {}).items():
                if before.get(k) != d:
                    seen_at.setdefault(f"{seed}:{k}", []).append(d)
            if c["pending"]:
                colony.resolve(s, c["pending"]["options"][-1]["id"], T0)
            c["res"]["rice"] = max(c["res"]["rice"], 60.0)
    assert len(seen_at) > 20
    for key, days in seen_at.items():
        kind = key.split(":", 1)[1]
        if kind in colony.EVENT_REPEATS:
            continue
        assert all(b - a >= colony.EVENT_COOLDOWN for a, b in zip(days, days[1:])), (key, days)


def test_a_cave_seen_yesterday_is_not_offered_today(st, monkeypatch):
    c = st["colony"]
    c["flags"]["seen"] = {"cave": 9}
    ev = _force(monkeypatch, c, "cave", day=10)
    assert not ev or ev["kind"] != "cave"


def test_stocks_are_shown_rounded_down_so_enough_means_enough(st):
    c = st["colony"]
    v = colony.view(st, T0)
    room = next(r for r in v["rooms"] if r["cost"] and not r["locked"])
    for k, need in room["cost"].items():
        c["res"][k] = need - 0.4                        # 54.6 against 55
    v = colony.view(st, T0)
    room = next(r for r in v["rooms"] if r["id"] == room["id"])
    have = {r["id"]: r["n"] for r in v["res"]}
    assert not room["affordable"]
    assert all(have[k] < need for k, need in room["cost"].items())
    err = colony.queue_build(st, room["id"], T0)
    assert not err["ok"] and "1 more" in err["error"]
    for k, need in room["cost"].items():
        c["res"][k] = need + 0.0
    v = colony.view(st, T0)
    assert next(r for r in v["rooms"] if r["id"] == room["id"])["affordable"]


def test_a_disciple_keeps_the_backstory_the_event_told(st, monkeypatch):
    c = st["colony"]
    ev = _force(monkeypatch, c, "fallen_genius")
    assert ev and "great clan" in ev["text"]
    colony.resolve(st, "accept", T0)
    p = c["pawns"][-1]
    assert "great clan" in p["origin"]
    assert "great clan" in next(x for x in colony.view(st, T0)["pawns"] if x["id"] == p["id"])["origin"]


def test_great_works_and_the_rival_toast_agree(st):
    c = st["colony"]
    _, a, b = c["pawns"]
    colony._bond(c, a, b, -35)
    assert c["log"][-1]["title"] == f"{a['name']} and {b['name']} are now rivals"
    line = next(x for w in colony.view(st, T0)["works"] if w["id"] == "family" for x in w["lines"] if "rivals" in x["text"])
    assert not line["ok"] and a["name"] in line["text"]
    n = len(c["log"])
    colony._bond(c, a, b, 7)                            # -28: hovering near the line is not news, and they are still rivals
    assert len(c["log"]) == n and colony.is_rival(c, a, b)
    assert next(x for x in colony.view(st, T0)["pawns"] if x["id"] == a["id"])["bonds"][0]["kind"] == "rival"
    assert any("rival" in t["label"].lower() for t in next(x for x in colony.view(st, T0)["pawns"] if x["id"] == a["id"])["mood_why"])
    colony._bond(c, a, b, 10)                           # -18: they make it up, and the chronicle says so
    assert c["log"][-1]["title"] == f"{a['name']} and {b['name']} are no longer rivals"
    line = next(x for w in colony.view(st, T0)["works"] if w["id"] == "family" for x in w["lines"] if "rivals" in x["text"])
    assert line["ok"] and not colony.is_rival(c, a, b)
    colony._bond(c, a, b, -20)                          # and a second falling-out is news again
    assert c["log"][-1]["title"] == f"{a['name']} and {b['name']} are now rivals"


def test_the_chronicle_uses_the_header_calendar(st):
    c = st["colony"]
    c["hour"] = 24 * 28 + 6                             # day 29: Autumn 5 of year 1
    colony._letter(c, "info", "Something", "happened")
    colony._annal(c, "Something happened")
    v = colony.view(st, T0)
    assert v["when"] == "Autumn 5, year 1" and v["season"] == "Autumn" and v["season_day"] == 5
    assert v["log"][0]["when"] == v["when"] and v["annals"][0]["when"] == v["when"]
    assert colony.calendar_label(48) == "Spring 1, year 2"


def test_the_breakthrough_ledger_says_the_pill_is_yet_to_be_used(st):
    c = st["colony"]
    p = c["pawns"][1]
    p["step"], p["qi"] = 3, colony.step_need(3)
    c["res"]["pills"] = 2.0
    rows = [label for label, _ in colony.bt_odds(c, p)]
    assert "A pill to steady the meridians (will be used)" in rows and not any("used up" in x for x in rows)
    colony.attempt(st, p["id"], T0)
    assert c["res"]["pills"] == 1.0
    scene = c["scenes"][-1]
    assert any("pill" in ln["text"] and "was used" in ln["text"] for ln in scene["lines"])


def test_the_elder_does_not_repeat_himself(st):
    c = st["colony"]
    c["flags"]["prio"] = 1
    c["rooms"]["library"] = 1
    c["research"]["current"] = "irrigation" if "irrigation" in colony.RESEARCH else next(iter(colony.RESEARCH))
    stones = c["res"]["stones"]
    colony._guide(c)
    told = [e for e in c["log"] if "elder" in e["title"].lower()]
    assert len(told) == 1 and c["guide"]["i"] == 3 and c["res"]["stones"] == stones + 9
    assert "Scripture Pavilion" in told[0]["title"]
    assert "Farm at 1 keeps" not in colony.GUIDE[0][1]


def test_risky_trope_choices_show_their_odds(st, monkeypatch):
    c = st["colony"]
    ev = _force(monkeypatch, c, "young_master")
    assert ev and ev["kind"] == "young_master"
    slap = next(o["label"] for o in ev["options"] if o["id"] == "slap")
    p = colony._p(c, ev["pawn"])
    s = colony._sect(c, ev["src"])
    me, foe = colony.duel_power(c, p), colony.young_master_foe(c, s)
    assert f"{int(me)} against about {int(foe)}" in slap and f"{colony.win_odds(me, foe, 0.7, 1.3)}% to win" in slap
    # the odds are the resolver's own roll: over many rolls the stated chance holds
    wins = sum(colony.duel_power(c, p) >= foe * random.Random(i).uniform(0.7, 1.3) for i in range(2000))
    assert abs(wins / 20 - colony.win_odds(me, foe, 0.7, 1.3)) < 4
    # the tournament names each round's champion and the odds of each disciple
    c["pending"] = None
    c["hour"] = 24 * 31 + 5
    c["tournament_year"] = 0
    c["festival"] = f"1-{colony._season(c)}"
    colony._daily_event(c)
    ev = c["pending"]
    assert ev and ev["kind"] == "tournament"
    sends = [o["label"] for o in ev["options"] if o["id"] != "decline"]
    assert sends and all("% to win round one" in x and "% to win every round" in x for x in sends)
    assert all(f"{ch['name']} {int(fp)}" in ev["text"] for _, ch, fp in colony.tournament_field(c)) and len(ev["text"]) <= 300


def test_win_odds_matches_a_uniform_roll():
    assert colony.win_odds(100, 100, 0.7, 1.3) == 50
    assert colony.win_odds(200, 100, 0.7, 1.3) == 100 and colony.win_odds(50, 100, 0.7, 1.3) == 0
    assert dao is not None
