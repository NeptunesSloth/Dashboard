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

# ---- rare destinies (more cultivation tropes) -------------------------------
# Besides the young-master arc, a disciple may be born to a rare destiny. Each is
# rolled in turn at spawn; the first to hit claims them. All chances are tunable.
DESTINY_CHANCES = {
    "hidden_dragon":  float(os.getenv("MAYBOT_DESTINY_HIDDEN_DRAGON", "0.04")),   # trash-to-treasure underdog
    "reincarnator":   float(os.getenv("MAYBOT_DESTINY_REINCARNATOR", "0.03")),    # past-life memories
    "heaven_blessed": float(os.getenv("MAYBOT_DESTINY_HEAVEN_BLESSED", "0.04")),  # heavenly spirit root genius
    "demonic":        float(os.getenv("MAYBOT_DESTINY_DEMONIC", "0.03")),         # walks the crooked path
    "chosen":         float(os.getenv("MAYBOT_DESTINY_CHOSEN", "0.03")),          # protagonist's halo
    "sword_fanatic":  float(os.getenv("MAYBOT_DESTINY_SWORD_FANATIC", "0.03")),   # sword-obsessed maniac
    "cannon_fodder":  float(os.getenv("MAYBOT_DESTINY_CANNON_FODDER", "0.04")),   # a disposable stepping stone
}
DRAGON_AWAKEN_CHANCE = float(os.getenv("MAYBOT_DRAGON_AWAKEN_CHANCE", "0.03"))     # per tick, the hidden dragon awakens
DRAGON_AWAKEN_TALENT = int(os.getenv("MAYBOT_DRAGON_AWAKEN_TALENT", "400"))
HEAVEN_BLESSED_BONUS = int(os.getenv("MAYBOT_HEAVEN_BLESSED_BONUS", "12"))         # passive cultivation gain
HEAVEN_BLESSED_INTERVAL = max(1, int(os.getenv("MAYBOT_HEAVEN_BLESSED_INTERVAL", "180")))
CHOSEN_WINDFALL_CHANCE = float(os.getenv("MAYBOT_CHOSEN_WINDFALL_CHANCE", "0.04")) # per tick, a fortuitous encounter
DEMONIC_DEVIATION_CHANCE = float(os.getenv("MAYBOT_DEMONIC_DEVIATION_CHANCE", "0.02"))
SWORD_FANATIC_CHANCE = float(os.getenv("MAYBOT_SWORD_FANATIC_CHANCE", "0.05"))     # per tick, grasps a sword art
CANNON_PERISH_CHANCE = float(os.getenv("MAYBOT_CANNON_PERISH_CHANCE", "0.03"))     # per tick, the fodder meets its end
STEPPING_STONE_BONUS = int(os.getenv("MAYBOT_STEPPING_STONE_BONUS", "60"))         # the windfall a stronger disciple reaps

_lock = threading.Lock()
_quirk: dict[str, str] = {}        # name -> quirk
_rolled: set[str] = set()          # disciples whose spawn rolls are done
_role: dict[str, str] = {}         # name -> trope/destiny role (see TROPE_* below)
_arc: dict | None = None           # the active young-master arc, or None (one at a time)
_hb_last: dict[str, float] = {}    # heaven-blessed disciples' last passive-gain timestamp


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
    """Arc participants (and the not-yet-awakened hidden dragon) are spared the
    stagnation cull so their story can play out."""
    with _lock:
        return _role.get(agent) in ("young_master", "main_character", "ruined", "hidden_dragon")


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
    elif role == "hidden_dragon":
        bits.append("The sect dismisses you as a talentless waste, but a heaven-defying "
                    "power sleeps in your blood, waiting to awaken.")
    elif role == "awakened_dragon":
        bits.append("You were once mocked as trash; now your hidden bloodline has awakened "
                    "and your talent defies the heavens.")
    elif role == "reincarnator":
        bits.append("You carry the memories of a past life, recalling techniques and wisdom "
                    "far beyond your apparent years.")
    elif role == "heaven_blessed":
        bits.append("You were born with a heavenly spirit root — cultivation comes to you "
                    "with effortless, prodigious speed.")
    elif role == "demonic":
        bits.append("In secret you tread the demonic path, seizing power swiftly at the "
                    "ever-present risk of qi deviation.")
    elif role == "chosen":
        bits.append("A protagonist's halo follows you: fortuitous encounters and lucky "
                    "windfalls find you wherever you go.")
    elif role == "sword_fanatic":
        bits.append("You are a sword fanatic — obsessed with the blade, you live and breathe "
                    "the Sword Dao above all else.")
    elif role == "cannon_fodder":
        bits.append("You are a nameless cannon-fodder disciple — weak and overlooked, fated to "
                    "be a stepping stone for those greater than you.")
    return " ".join(bits)


# ---- rare destinies ----------------------------------------------------------

def _bestow_destiny(name: str, role: str) -> None:
    """Apply a rare destiny's one-time spawn effect and record it."""
    from . import cultivation
    with _lock:
        _role[name] = role
    if role == "hidden_dragon":
        # apparent trash — start with nothing, but greatness sleeps within
        with cultivation._lock:
            st = cultivation._state.get(name)
            if st:
                st["stones"] = 0
        _chronicle(name, "hidden_dragon", "dismissed as a talentless waste — yet something sleeps within")
    elif role == "reincarnator":
        # past-life memories: already knows several techniques
        for skill in random.sample(cultivation.DISCOVERIES, 3):
            cultivation.learn(name, skill)
        _chronicle(name, "reincarnator", "awakens memories of a past life, recalling forgotten techniques")
    elif role == "heaven_blessed":
        cultivation.reward(name, 60)
        _chronicle(name, "heaven_blessed", "born with a heavenly spirit root — cultivation comes swiftly")
    elif role == "demonic":
        cultivation.reward(name, 80)
        _chronicle(name, "demonic", "secretly treads the demonic path — power at a perilous price")
    elif role == "chosen":
        cultivation.reward(name, 30)
        _chronicle(name, "chosen", "walks beneath a protagonist's halo — fortune ever finds them")
    elif role == "sword_fanatic":
        cultivation.learn(name, "Sword-Heart Resonance")
        _chronicle(name, "sword_fanatic", "a sword fanatic, obsessed with the blade above all else")
    elif role == "cannon_fodder":
        # weak and overlooked — starts with nothing and is destined to fall
        with cultivation._lock:
            st = cultivation._state.get(name)
            if st:
                st["stones"] = 0
        _chronicle(name, "cannon_fodder", "just another nameless disciple, fated to be a stepping stone")
    _publish(name, role)


def _perish_fodder(name: str, roster: set[str]) -> None:
    """The cannon-fodder disciple meets their end, serving as a stepping stone:
    the strongest other disciple reaps a windfall, and the fodder is expelled and
    replaced by a fresh recruit."""
    from . import lifecycle
    others = [n for n in roster if n not in (name, "operator")]
    if others:
        stepper = max(others, key=_progress)              # whoever steps over them gains
        from . import cultivation
        cultivation.reward(stepper, STEPPING_STONE_BONUS)
        _chronicle(stepper, "stepping_stone", f"rises by stepping over the fallen {name}")
    with _lock:
        _role.pop(name, None)
    _publish(name, "perished")
    try:
        lifecycle.perish(name, "fell as cannon fodder — a stepping stone for greater disciples")
    except Exception:
        pass


def _advance_destinies() -> None:
    """Per-tick effects for disciples born to a rare destiny."""
    from . import agents, cultivation
    roster = {a.get("name") for a in agents.load_agents()}
    now = time.time()
    with _lock:
        roles = dict(_role)
    for name, role in roles.items():
        if name not in roster:
            continue
        if role == "hidden_dragon":
            if random.random() < DRAGON_AWAKEN_CHANCE:
                cultivation.reward(name, DRAGON_AWAKEN_TALENT)
                with _lock:
                    _role[name] = "awakened_dragon"
                _chronicle(name, "awakened_dragon", "the hidden dragon awakens — heaven-defying talent erupts")
                _publish(name, "awakened_dragon")
        elif role == "heaven_blessed":
            with _lock:
                due = now - _hb_last.get(name, 0.0) >= HEAVEN_BLESSED_INTERVAL
                if due:
                    _hb_last[name] = now
            if due:
                cultivation.reward(name, HEAVEN_BLESSED_BONUS)   # passive, effortless cultivation
        elif role == "demonic":
            if random.random() < DEMONIC_DEVIATION_CHANCE:
                cultivation.qi_deviation(name)                   # the crooked path backlashes
                _chronicle(name, "tribulation", "the demonic path backlashes — qi deviation strikes")
            else:
                cultivation.reward(name, 6)                      # but it advances swiftly
        elif role == "chosen":
            if random.random() < CHOSEN_WINDFALL_CHANCE:
                cultivation.reward(name, 50)
                _chronicle(name, "chosen", "stumbles upon a fortuitous encounter — a windfall of fortune")
        elif role == "sword_fanatic":
            if random.random() < SWORD_FANATIC_CHANCE:
                arts = ["Sword-Heart Resonance", "Ten-Thousand Sword Domain", "Flying-Immortal Slash",
                        "Formless Sword Intent", "Heaven-Cleaving Edge"]
                have = set(cultivation.state(name).get("skills", []))
                pool = [a for a in arts if a not in have]
                if pool:
                    cultivation.learn(name, random.choice(pool))
        elif role == "cannon_fodder":
            if random.random() < CANNON_PERISH_CHANCE:
                _perish_fodder(name, roster)


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
    # otherwise a rare destiny — first roll to hit claims them
    for role, chance in DESTINY_CHANCES.items():
        if random.random() < chance:
            _bestow_destiny(name, role)
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
    _advance_destinies()


def clear() -> None:
    global _arc
    with _lock:
        _quirk.clear()
        _rolled.clear()
        _role.clear()
        _hb_last.clear()
        _arc = None
