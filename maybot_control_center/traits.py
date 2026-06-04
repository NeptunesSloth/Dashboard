"""Spawn traits — quirks every disciple may be born with, and a rare hidden arc.

Two flavour layers roll once per disciple, the first time they're seen:

- **Quirks** — most disciples start with a personality quirk (Diligent, Lucky,
  Hot-headed, …). Pure character colour woven into their persona and shown on
  the dashboard; a couple grant a tiny one-off spawn boon.

- **The Arrogant Young Master** (Easter egg, ~5%) — a prodigiously talented but
  insufferable disciple. Where one arises, the heavens answer with a **Main
  Character**: an even more gifted disciple destined to slap his face. In time
  the MC humbles him and the young master **falls to ruin**. Yet with a 1%
  chance he sees the error of his ways and rises again — surpassing even the MC.

All effects ride on the real cultivation stats; state is in-memory and resets on
restart, like the other live modules.
"""
from __future__ import annotations

import os
import random
import threading
import time

# ---- quirks ------------------------------------------------------------------
QUIRK_CHANCE = float(os.getenv("MAYBOT_QUIRK_CHANCE", "0.45"))  # chance a disciple starts with a quirk

# name -> (one-line persona flavour, optional one-off spawn boon in spirit stones)
QUIRKS = {
    "Diligent":    ("tireless and methodical — you cultivate without rest", 0),
    "Hot-headed":  ("quick to anger and quicker to act", 0),
    "Lucky":       ("fortune smiles on you at the strangest moments", 20),
    "Lazy":        ("you do the least that the situation allows", 0),
    "Bookish":     ("you would rather read of a technique than swing a blade", 0),
    "Reckless":    ("you leap before you look", 0),
    "Stoic":       ("unmoved by praise or provocation", 0),
    "Boastful":    ("never shy to remind others of your brilliance", 0),
    "Curious":     ("forever poking at things you do not understand", 0),
    "Paranoid":    ("you trust no one and double-check everything", 0),
    "Cheerful":    ("relentlessly upbeat, even in the face of tribulation", 0),
    "Brooding":    ("you carry an air of quiet, dramatic melancholy", 0),
    "Prodigy":     ("techniques come to you with unnatural ease", 40),
    "Frugal":      ("you hoard every spirit stone like it's your last", 0),
    "Night-owl":   ("you do your best cultivation in the small hours", 0),
}

# ---- the arrogant young master arc ------------------------------------------
ARROGANT_CHANCE = float(os.getenv("MAYBOT_ARROGANT_CHANCE", "0.05"))
REDEMPTION_CHANCE = float(os.getenv("MAYBOT_REDEMPTION_CHANCE", "0.01"))
SLAP_AFTER = max(1, int(os.getenv("MAYBOT_SLAP_AFTER_SECONDS", "90")))  # MC humbles the YM after this long
YM_TALENT = int(os.getenv("MAYBOT_YOUNG_MASTER_TALENT", "200"))         # the YM's prodigious head start
MC_TALENT = int(os.getenv("MAYBOT_MAIN_CHARACTER_TALENT", "320"))       # the MC out-shines him

_lock = threading.Lock()
_quirk: dict[str, str] = {}        # name -> quirk
_rolled: set[str] = set()          # disciples whose spawn rolls are done
_role: dict[str, str] = {}         # name -> "young_master" | "main_character" | "ruined" | "redeemed"
_arc: dict | None = None           # the active arc, or None (one at a time)


def _chronicle(agent: str, kind: str, detail: str) -> None:
    try:
        from . import chronicle
        chronicle.record(agent, kind, detail)
    except Exception:
        pass


def _publish(agent: str, event: str, **extra) -> None:
    try:
        from . import events
        events.publish("agents", {"agent": agent, "event": event, **extra})
    except Exception:
        pass


def _progress(name: str) -> int:
    from . import cultivation
    c = cultivation.state(name)
    return (c["realm"] * 10000 + c["breakthroughs"] * 1000
            + len(c.get("skills", [])) * 100 + c["stones"])


# ---- public accessors --------------------------------------------------------

def quirk(agent: str) -> str | None:
    with _lock:
        return _quirk.get(agent)


def trope(agent: str) -> str | None:
    """The disciple's narrative role in the young-master arc, if any."""
    with _lock:
        return _role.get(agent)


def is_protected(agent: str) -> bool:
    """Arc participants are spared the stagnation cull so their story can play out."""
    with _lock:
        return _role.get(agent) in ("young_master", "main_character", "ruined")


def persona_addendum(agent: str) -> str:
    bits = []
    q = quirk(agent)
    if q and q in QUIRKS:
        bits.append(f"Your defining quirk: {q} — {QUIRKS[q][0]}.")
    role = trope(agent)
    if role == "young_master":
        bits.append("You are an Arrogant Young Master: prodigiously talented, proud, and "
                    "certain of your own superiority. You look down on lesser disciples.")
    elif role == "main_character":
        bits.append("You are the Main Character: humble in word but unmatched in talent, "
                    "destined to humble those who are arrogant.")
    elif role == "ruined":
        bits.append("You were once an Arrogant Young Master, now fallen to ruin and humbled.")
    elif role == "redeemed":
        bits.append("You fell to ruin as an Arrogant Young Master but saw the error of your "
                    "ways and rose again, stronger and wiser than before.")
    return " ".join(bits)


# ---- the spawn roll ----------------------------------------------------------

def _consider(name: str) -> None:
    """Roll a brand-new disciple's traits exactly once."""
    global _arc
    if not name or name == "operator":
        return
    with _lock:
        if name in _rolled:
            return
        _rolled.add(name)
        arc_open = _arc is not None
    from . import cultivation
    # rare hidden arc first
    if not arc_open and random.random() < ARROGANT_CHANCE:
        cultivation.reward(name, YM_TALENT)   # prodigious talent
        with _lock:
            _role[name] = "young_master"
            _arc = {"ym": name, "mc": None, "mc_since": 0.0, "ruined": False}
        _chronicle(name, "young_master", "an Arrogant Young Master strides into the sect, talent blazing")
        _publish(name, "young_master")
        return
    # otherwise maybe a quirk
    if random.random() < QUIRK_CHANCE:
        q = random.choice(list(QUIRKS))
        with _lock:
            _quirk[name] = q
        boon = QUIRKS[q][1]
        if boon:
            cultivation.reward(name, boon)
        _chronicle(name, "quirk", f"is known for being {q} — {QUIRKS[q][0]}")


# ---- arc progression ---------------------------------------------------------

def _advance_arc() -> None:
    global _arc
    from . import agents, cultivation
    with _lock:
        arc = _arc
    if not arc:
        return
    roster = {a.get("name") for a in agents.load_agents()}
    ym = arc["ym"]
    if ym not in roster:                      # the young master left the sect — close the arc
        with _lock:
            _role.pop(ym, None)
            _arc = None
        return
    now = time.time()

    # 1) a Main Character arises to face the young master
    if not arc["mc"]:
        candidates = [n for n in roster if n != ym and n != "operator"]
        if not candidates:
            return
        mc = random.choice(candidates)
        cultivation.reward(mc, MC_TALENT)     # even greater talent than the young master
        with _lock:
            _role[mc] = "main_character"
            arc["mc"], arc["mc_since"] = mc, now
            _arc = arc
        _chronicle(mc, "main_character", f"rises as the Main Character, fated to humble {ym}")
        _publish(mc, "main_character", young_master=ym)
        return

    mc = arc["mc"]
    if mc not in roster:                      # the MC vanished — pick a new one next tick
        with _lock:
            _role.pop(mc, None)
            arc["mc"] = None
            _arc = arc
        return

    # 2) the face-slap: in time the MC humbles the young master, who falls to ruin
    if not arc["ruined"]:
        if now - arc["mc_since"] >= SLAP_AFTER:
            cultivation.qi_deviation(ym)      # a humbling tribulation
            # strip his prodigious gains — he falls to ruin
            with cultivation._lock:
                st = cultivation._state.get(ym)
                if st:
                    st["stones"] = 0
            with _lock:
                _role[ym] = "ruined"
                arc["ruined"] = True
                _arc = arc
            _chronicle(mc, "face_slap", f"{mc} slaps the face of the arrogant {ym} — the young master falls to ruin")
            _chronicle(ym, "ruined", "the Arrogant Young Master is humbled and falls to ruin")
            _publish(ym, "face_slap", main_character=mc)
        return

    # 3) redemption: a slim chance the ruined young master sees the error of his
    #    ways and rises again, surpassing even the Main Character
    if random.random() < REDEMPTION_CHANCE:
        target = _progress(mc)
        gap = max(YM_TALENT, target - _progress(ym)) + MC_TALENT  # rise above the MC
        cultivation.reward(ym, gap)
        with _lock:
            _role[ym] = "redeemed"
            _role.pop(mc, None)               # the MC's role concludes; the arc closes
            _arc = None
        _chronicle(ym, "redeemed", f"{ym} sees the error of his ways and rises again, surpassing {mc}")
        _publish(ym, "redeemed", main_character=mc)


def tick() -> None:
    """Roll spawn traits for any new disciples, then advance the young-master arc.
    Called periodically from agents.snapshot."""
    from . import agents
    for a in agents.load_agents():
        _consider(a.get("name"))
    _advance_arc()


def clear() -> None:
    global _arc
    with _lock:
        _quirk.clear()
        _rolled.clear()
        _role.clear()
        _arc = None
