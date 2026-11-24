# Spaced-repetition scheduler choice: FSRS vs SM-2 (Leitner as baseline)

Research date: 2026-11-24. Primary sources were fetched as raw files from GitHub on that date
(py-fsrs `main` = v6.3.3; srs-benchmark `main` @ 57c0b07, 2026-11-19; Anki `main` = 26.09.4; fsrs-rs `main` = 7.0.0).

Version labelling used throughout: **[FSRS-6]** = 21-parameter version (what py-fsrs 6.3.3 and Anki 26.09 ship);
**[FSRS-5]** = 19-parameter predecessor; **[FSRS-7]** = 34-parameter successor (released in fsrs-rs 7.0.0, not in Anki or py-fsrs).

**Bottom line for the report writer:** implement **FSRS-6 with the published default parameters**, desired retention 0.9,
no optimizer. It is the version in the stable Python reference library and in Anki; it has closed-form interval maths
(FSRS-7 does not); and a ~55-line pure-Python port was checked by me against py-fsrs 6.3.3 with zero mismatches over
75,000 simulated reviews (code at the end of the first section).

## What are the exact FSRS formulas and the published default weight vector?

### Takeaway
The current stable, widely deployed version is FSRS-6 (21 weights, DSR model, power forgetting curve with a trainable decay `w20`). All formulas below are FSRS-6 exactly as implemented in py-fsrs 6.3.3; FSRS-7 exists but needs two stabilities, 34 parameters and an iterative interval solver, so it is a poor fit for a ~150-line implementation.

### Cited Findings

**Which version is current**
- py-fsrs `main` is package version `6.3.3` and its `DEFAULT_PARAMETERS` tuple has 21 values (FSRS-6). — [py-fsrs pyproject.toml](https://github.com/open-spaced-repetition/py-fsrs/blob/main/pyproject.toml), [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Anki `main` (version file `26.09.4`) pins the `fsrs` crate at `6.6.2`, i.e. Anki still ships FSRS-6. — [anki Cargo.toml](https://github.com/ankitects/anki/blob/main/Cargo.toml), [anki .version](https://github.com/ankitects/anki/blob/main/.version)
- fsrs-rs `main` is crate version `7.0.0` and states "FSRS-6 and FSRS-7 are selected from the parameter count". — [fsrs-rs Cargo.toml](https://github.com/open-spaced-repetition/fsrs-rs/blob/main/Cargo.toml), [fsrs-rs README](https://github.com/open-spaced-repetition/fsrs-rs/blob/main/README.md)
- The algorithm wiki now leads with FSRS-7: stored state is `(S_long, S_short, D)`, 34 parameters, 11 of them for the forgetting curve; "Unlike previous versions, where the interval at a given level of desired retention could be calculated analytically, this is no longer possible in FSRS-7, so intervals are calculated iteratively." — [awesome-fsrs wiki, The Algorithm](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)
- srs-benchmark README calls FSRS-7 "the newest version" and says "In Anki, FSRS-7 should be shipped with both recency weighting and scheduling penalties enabled" (future tense: not shipped). — [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md)
- An Anki forum thread dated 2026-06-05 had a moderator stating FSRS-7 "hasn't been merged into or released by open-spaced-repetition" and there was "no PR for it in the Anki repo". This is now partly stale (fsrs-rs 7.0.0 exists) but consistent with Anki 26.09.4 still pinning 6.6.2. — [Anki forum](https://forums.ankiweb.net/t/when-will-anki-integrate-fsrs-7/69997)
- Expertium's benchmark write-up states "FSRS-7 is the final version, there will be no major releases in the foreseeable future." — [Expertium, Benchmark](https://expertium.github.io/Benchmark.html)
- The old wiki location (`fsrs4anki/wiki/The-Algorithm`) is now a "Page moved" stub pointing to the awesome-fsrs wiki. — [fsrs4anki wiki](https://github.com/open-spaced-repetition/fsrs4anki/wiki/The-Algorithm)

**[FSRS-6] default weight vector (21 values, index 0..20, identical in the wiki and py-fsrs)**
- `[0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666, 0.796, 1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542]` — [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm); [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py) (where `w20` is the named constant `FSRS_DEFAULT_DECAY = 0.1542`)
- Role of each weight, as used in py-fsrs: w0..w3 initial stability for Again/Hard/Good/Easy; w4, w5 initial difficulty; w6 difficulty delta; w7 mean-reversion weight; w8, w9, w10 stability-after-recall; w11..w14 stability-after-lapse; w15 Hard penalty; w16 Easy bonus; w17, w18, w19 same-day (short-term) stability; w20 forgetting-curve decay. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)

**[FSRS-5] default weight vector (19 values), for reference only**
- `[0.40255, 1.18385, 3.173, 15.69105, 7.1949, 0.5345, 1.4604, 0.0046, 1.54575, 0.1192, 1.01925, 1.9395, 0.11, 0.29605, 2.2698, 0.2315, 2.9898, 0.51655, 0.6621]` — [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)
- FSRS-5 uses fixed curve constants `DECAY = -0.5`, `FACTOR = 19/81` (inherited from FSRS-4.5), and same-day stability `S' = S * e^(w17*(G-3+w18))` with no `S^-w19` term. — [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)

**[FSRS-6] formulas** (G = grade: 1 Again, 2 Hard, 3 Good, 4 Easy; t = whole days since last review)
- Constants: `DECAY = -w20`; `FACTOR = 0.9^(1/DECAY) - 1` (equivalently `0.9^(-1/w20) - 1`), chosen so that R(S,S) = 90%. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py), [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)
- Retrievability: `R(t,S) = (1 + FACTOR * t / S) ^ DECAY`; py-fsrs uses `elapsed_days = max(0, (now - last_review).days)` (integer days). — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Initial stability: `S0(G) = w[G-1]`, clamped to `>= 0.001` (`STABILITY_MIN`). — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Initial difficulty: `D0(G) = w4 - e^(w5*(G-1)) + 1`, clamped to [1, 10] (`MIN_DIFFICULTY = 1.0`, `MAX_DIFFICULTY = 10.0`). — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Difficulty update (linear damping then mean reversion to the *unclamped* D0(4)): `dD = -w6*(G-3)`; `D' = D + dD*(10-D)/9`; `D'' = w7*D0(4) + (1-w7)*D'`; clamp to [1, 10]. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py); wiki: "In FSRS 5, D0(4) is the target of mean reversion. Earlier versions had D0(3)" — [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)
- Stability after successful recall (G in 2,3,4): `S' = S * (1 + e^w8 * (11-D) * S^(-w9) * (e^((1-R)*w10) - 1) * hard_penalty * easy_bonus)`, with `hard_penalty = w15` if G=2 else 1, `easy_bonus = w16` if G=4 else 1. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Stability after lapse (G=1): `S_f = w11 * D^(-w12) * ((S+1)^w13 - 1) * e^((1-R)*w14)`; py-fsrs then returns `min(S_f, S / e^(w17*w18))`, so post-lapse stability never exceeds the pre-lapse value. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Same-day ("short-term") review, used whenever the card already has S/D and `days_since_last_review < 1`: `SInc = e^(w17*(G-3+w18)) * S^(-w19)`; if G >= 2 then `SInc = max(SInc, 1.0)`; `S' = S * SInc`. Wiki: "In practice, we should ensure that SInc >= 1 when G >= 2." — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py), [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)
- Order of operations in py-fsrs `review_card`: R is computed from the *old* S; new S uses the *old* D; D is updated on every review after the first (including same-day ones). All results are clamped (`S >= 0.001`, `D` in [1,10]). — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Wiki guidance on semantics: stability cannot decrease after a successful review; "Easy, Good, and Hard all count as 'success'; Again counts as a memory 'lapse'. That's why you shouldn't use Hard as a failing grade". — [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)

**[FSRS-7] (for awareness only)**
- Default parameters per the wiki (34 values, attributed to `init_w` in `fsrs_v7.py`): `[0.1104, 2.2395, 3.9221, 11.7841, 6.1686, 0.6457, 3.6807, 1.9795, 0.0, 1.3826, 0.7024, 0.5999, 0.8146, 0.6398, 1.0, 1.3207, 0.6707, 3.8668, 0.4416, 0.0934, 1.8631, 0.6162, 1.0869, 0.1567, 0.0801, 0.2421, 0.9464, 0.1433, 0.7145, 0.0, 0.5667, 0.3734, 0.5333, 0.3048]` — [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm); **contradicted by** the srs-benchmark README's "Default Parameters / FSRS-7" block, which lists a different set of **35** numbers starting `0.041, 2.4175, 4.1283, 11.9709, ...` — [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md)
- FSRS-7 "is designed to work with fractional interval lengths" and is "the only version that can give realistic predictions of probability of recall for same-day reviews". — [awesome-fsrs wiki](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm), [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md)

### Inferences
- Derived values from the FSRS-6 defaults (computed by me, not quoted): `DECAY = -0.1542`, `FACTOR = 0.98034649...`; `D0 = [6.4133, 5.1122, 2.1181, 1.0]` for Again/Hard/Good/Easy (Easy's raw value is negative and clamps to 1); first review intervals at 0.9 retention = `[1, 1, 2, 8]` days; a Good-only card reviewed exactly on its due date gets intervals `2, 11, 46, 163, 497, 1346, ...` days (no fuzz).
- With `w7 = 0.001` in the FSRS-6 defaults, mean reversion is almost switched off (it was 0.0046 in FSRS-5 defaults and is hard-coded to 0.01/0.99 in FSRS-7); it must still be implemented to match reference behaviour.
- FSRS-6 is the right target for a dependency-free implementation: FSRS-7's two published default vectors disagree with each other (34 vs 35 values), it has no pure-Python reference release, and it needs a root-finder for intervals. The data model should store the weight vector per scheduler so a later move to FSRS-7 is a function swap, not a schema change.
- Per-card state needed: `state` (learning/review/relearning), `step`, `stability`, `difficulty`, `last_review`, `due`. A review log (card id, grade, timestamp) should be kept from day one because it is what any future parameter optimizer consumes.

**Verified reference port (mine; FSRS-6; not from a source).** Checked against `fsrs==6.3.3` with fuzz disabled: 3,000 random cards x 25 reviews with random grades and delays (0 s to 40 days) gave 0 mismatches in stability, difficulty, state and due date.

```python
import math
from datetime import timedelta
W = (0.212, 1.2931, 2.3065, 8.2956, 6.4133, 0.8334, 3.0194, 0.001, 1.8722, 0.1666, 0.796,
     1.4835, 0.0614, 0.2629, 1.6483, 0.6014, 1.8729, 0.5425, 0.0912, 0.0658, 0.1542)
DECAY = -W[20]; FACTOR = 0.9 ** (1 / DECAY) - 1
S_MIN, RET, MAX_IVL = 0.001, 0.9, 36500
LEARN, RELEARN = (1, 10), (10,)          # minutes
def clampD(d): return min(max(d, 1.0), 10.0)
def R(t_days, s): return (1 + FACTOR * t_days / s) ** DECAY
def interval(s, r=RET): return min(max(round(s / FACTOR * (r ** (1 / DECAY) - 1)), 1), MAX_IVL)
def s0(g): return max(W[g - 1], S_MIN)
def d0(g, clamp=True):
    d = W[4] - math.exp(W[5] * (g - 1)) + 1
    return clampD(d) if clamp else d
def next_d(d, g):
    d2 = d + (-W[6] * (g - 3)) * (10 - d) / 9
    return clampD(W[7] * d0(4, False) + (1 - W[7]) * d2)
def s_recall(d, s, r, g):
    return s * (1 + math.exp(W[8]) * (11 - d) * s ** -W[9] * (math.exp((1 - r) * W[10]) - 1)
                * (W[15] if g == 2 else 1) * (W[16] if g == 4 else 1))
def s_forget(d, s, r):
    long = W[11] * d ** -W[12] * ((s + 1) ** W[13] - 1) * math.exp((1 - r) * W[14])
    return min(long, s / math.exp(W[17] * W[18]))
def s_short(s, g):
    inc = math.exp(W[17] * (g - 3 + W[18])) * s ** -W[19]
    if g >= 2: inc = max(inc, 1.0)
    return s * inc
def review(card, g, now):
    """card: dict(state 'learning'|'review'|'relearning', step, s, d, last, due); new card =
    dict(state='learning', step=0, s=None, d=None, last=None, due=now). g in 1..4; now is tz-aware UTC."""
    c = dict(card); days = (now - c["last"]).days if c.get("last") else None
    if c.get("s") is None:                                  # first ever review
        c["s"], c["d"] = s0(g), d0(g)
    elif days is not None and days < 1:                     # same-day review
        c["s"] = max(s_short(c["s"], g), S_MIN); c["d"] = next_d(c["d"], g)
    else:                                                   # normal (>= 1 day) review
        r = R(max(days, 0), c["s"])
        ns = s_forget(c["d"], c["s"], r) if g == 1 else s_recall(c["d"], c["s"], r, g)
        c["d"] = next_d(c["d"], g); c["s"] = max(ns, S_MIN)
    if c["state"] == "review":
        if g == 1 and RELEARN: c["state"], c["step"] = "relearning", 0; ivl = timedelta(minutes=RELEARN[0])
        else: ivl = timedelta(days=interval(c["s"]))
    else:
        steps = LEARN if c["state"] == "learning" else RELEARN
        st = c["step"]
        if not steps or (st >= len(steps) and g >= 2) or g == 4 or (g == 3 and st + 1 >= len(steps)):
            c["state"], c["step"] = "review", None; ivl = timedelta(days=interval(c["s"]))
        elif g == 1: c["step"] = 0; ivl = timedelta(minutes=steps[0])
        elif g == 2:
            m = steps[0] * 1.5 if (st == 0 and len(steps) == 1) else (steps[0] + steps[1]) / 2 if st == 0 else steps[st]
            ivl = timedelta(minutes=m)
        else: c["step"] = st + 1; ivl = timedelta(minutes=steps[c["step"]])
    c["due"], c["last"] = now + ivl, now
    return c
```

### Gaps
- FSRS-7's authoritative default vector could not be pinned down: the wiki (34 values) and the benchmark README (35 values) disagree, and I did not open `fsrs_v7.py` or fsrs-rs source to resolve it. Do not copy either FSRS-7 vector into code without checking the source file.
- I did not diff py-fsrs against fsrs-rs 6.6.2 (Anki's implementation). py-fsrs's own README warns results "may be slightly different than the numbers computed by Anki... the two implementations are slightly different and updated at different times" ([py-fsrs README](https://github.com/open-spaced-repetition/py-fsrs/blob/main/README.md)); the port above matches py-fsrs, not necessarily Anki, bit for bit.
- The exact release dates of py-fsrs 6.3.3 and fsrs-rs 7.0.0 were not retrieved (GitHub API was not accessible in this session).

## What desired-retention default is recommended, how is the next interval computed, and what about max interval and fuzz?

### Takeaway
Use desired retention 0.9 (the default in both py-fsrs and Anki); the interval is a closed-form function of stability that equals S exactly at 0.9. Reference defaults are a 36,500-day (100-year) cap and a small banded fuzz on intervals of 3+ days.

### Cited Findings
- [FSRS-6] Next interval: `I = (S / FACTOR) * (r^(1/DECAY) - 1)`, then `round()`, then `max(I, 1)`, then `min(I, maximum_interval)`; intervals are whole days. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- py-fsrs `Scheduler` defaults: `desired_retention = 0.9`, `learning_steps = (1 min, 10 min)`, `relearning_steps = (10 min,)`, `maximum_interval = 36500`, `enable_fuzzing = True`. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Anki's built-in defaults match: `desired_retention: 0.9`, `maximum_review_interval: 36_500`, learn steps `[1.0, 10.0]` minutes, relearn steps `[10.0]`. — [anki rslib/src/deckconfig/mod.rs](https://github.com/ankitects/anki/blob/main/rslib/src/deckconfig/mod.rs)
- Anki manual: desired retention "default is 90%, which offers a good balance of retention and workload"; "Above 90% the workload increases very quickly, and above 97% the workload can be overwhelming"; "recommend you keep it lower than 97%". Maximum interval "default is 100 years". — [Anki manual, Deck Options](https://docs.ankiweb.net/deck-options.html)
- Anki UI strings: "A maximum interval less than 6 months is not recommended"; warnings exist for desired retention that is "very low, which can lead to very long intervals" or "very high, which can lead to very short intervals". — [anki ftl/core/deck-config.ftl](https://github.com/ankitects/anki/blob/main/ftl/core/deck-config.ftl)
- Fuzz in py-fsrs: applied only to cards in the Review state and only if the interval is >= 2.5 days. `delta = 1.0 + 0.15*overlap(ivl, 2.5..7) + 0.10*overlap(ivl, 7..20) + 0.05*overlap(ivl, 20..inf)`; `min_ivl = max(2, round(ivl - delta))`; `max_ivl = min(round(ivl + delta), maximum_interval)`; `min_ivl = min(min_ivl, max_ivl)`; result = `floor(random() * (max_ivl - min_ivl + 1)) + min_ivl`, capped at maximum_interval. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Parameters and desired retention are independent: "you do not need to re-optimize parameters if you have changed desired retention." — [fsrs4anki tutorial](https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md)

### Inferences
- Interval multipliers relative to S under FSRS-6 defaults (computed by me): retention 0.80 -> 3.32 x S; 0.85 -> 1.91 x S; 0.90 -> 1.00 x S; 0.95 -> 0.40 x S. Lowering retention from 0.90 to 0.85 nearly doubles intervals; raising it to 0.95 more than halves them. A single config knob (suggest allowing 0.80-0.95) is enough.
- For a small app with short-lived content, a lower cap than 36,500 days (e.g. 365) is a reasonable product choice and is above Anki's "not less than 6 months" warning threshold.
- Fuzz exists to stop cards introduced together from clumping on the same future day; with small decks it is optional, and disabling it makes tests deterministic.

### Gaps
- No primary source gives a quantified workload-vs-retention curve for default parameters; Anki computes an "Approximate workload: Nx" figure in-app and points users to its simulator.
- Anki's own fuzz implementation was not compared line by line with py-fsrs's; the constants above are py-fsrs's.

## How should learning steps and same-day re-shows of new or failed cards be handled in a simple implementation?

### Takeaway
Keep short, same-day steps (reference default: 1 min and 10 min for new cards, 10 min after a lapse) as a thin state machine around FSRS; FSRS-6 updates stability with its same-day formula during those steps and takes over scheduling once the card graduates to Review. FSRS guidance is that every step must be completable on the same day and that many steps are discouraged.

### Cited Findings
- py-fsrs state machine [FSRS-6 library behaviour]. States: Learning, Review, Relearning; a new card starts in Learning at step 0. In Learning/Relearning: **Again** -> step 0, due in `steps[0]`; **Hard** -> step unchanged, due in `steps[0]*1.5` if there is exactly one step, the mean of `steps[0]` and `steps[1]` if on step 0 with two or more steps, otherwise `steps[step]`; **Good** -> if on the last step, graduate to Review with the FSRS interval, else advance one step; **Easy** -> graduate immediately to Review with the FSRS interval. Empty step list -> go straight to Review. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- In Review: Again -> Relearning at step 0 (due in `relearning_steps[0]`), or, if there are no relearning steps, stays in Review with the FSRS interval; Hard/Good/Easy -> stays in Review with the FSRS interval. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Memory state is updated on every rating in every state: first rating sets S0/D0; a rating less than one day after the previous one uses the short-term stability formula; otherwise the normal recall/lapse formulas. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)
- Anki defaults: learning steps 1m 10m; relearning step 10m; graduating interval 1 day (Good) / 4 days (Easy) for the non-FSRS scheduler; leech threshold 8 lapses. — [anki rslib/src/deckconfig/mod.rs](https://github.com/ankitects/anki/blob/main/rslib/src/deckconfig/mod.rs), [anki ftl/core/deck-config.ftl](https://github.com/ankitects/anki/blob/main/ftl/core/deck-config.ftl)
- Anki manual with FSRS: "Ensure that all your learning and re-learning steps are shorter than 1d and can be completed on the same day"; "Steps such as 10m or 30m are good"; "(Re)learning steps of 1 day or greater are not recommended when using FSRS." — [Anki manual, Deck Options](https://docs.ankiweb.net/deck-options.html)
- FSRS tutorial: "A *single* reasonable learning step can be 10m, 15m, 20m or 30m"; steps longer than 12-14 hours are not recommended; "The use of *multiple* short (re)learning steps, such as '5m 10m 15m 30m', is also discouraged. However, if you notice that your retention for young cards is much lower than desired, adding more intraday learning steps (such as 2h or 4h) may be helpful"; with longer steps "there can be cases where the 'Hard' interval exceeds the 'Good' interval". — [fsrs4anki tutorial](https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md)
- FSRS versions before 7 were "designed to work with integer interval lengths"; FSRS-5/6 use same-day reviews "to refine its prediction for the next review" but cannot realistically predict recall within a day. — [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md)

### Inferences
- Simplest faithful design for a session-based web app: treat a step as "re-show later in this session". On a wrong answer put the card back in the session queue (due in about a minute); require one correct same-day answer to graduate. That is the py-fsrs machine with `LEARN = (1,)` or `(10,)`; if the session ends first, the stored `due` time still brings the card back next visit.
- An even simpler variant is supported by the reference code: empty step lists, so every rating yields an FSRS day-interval (Again on a new card gives 1 day, since S0(Again) = 0.212 rounds up to the 1-day floor). This loses the immediate re-show that learners expect after a miss, so in-session re-queueing is the better default.
- Because FSRS-6 cannot schedule sub-day intervals itself, step lengths are a product decision, not an algorithm output.

### Gaps
- No benchmark evidence was found comparing learning outcomes for one step versus two steps versus none; the tutorial's advice is stated without numbers.

## What benchmark evidence shows FSRS vs SM-2 in review-load and log-loss terms?

### Takeaway
On prediction accuracy the evidence is strong: in the last srs-benchmark release that included SM-2, FSRS-5 had roughly half the log loss and about a third of the calibration error, and FSRS-6 beats Anki's SM-2 variant for 99.6% of users. On review load the evidence is weak: the often-quoted "20-30% fewer reviews" comes from old simulations that the FSRS wiki itself now flags as unreliable.

### Cited Findings
- srs-benchmark README as of 2024-09-01 (commit 8a75a35; 19,990 users; 702,721,850 reviews evaluated), **unweighted** means with 99% CIs: FSRS-5 (19 params) log loss 0.346±0.0031, RMSE(bins) 0.0712±0.00084, AUC 0.697±0.0017; FSRS-5 with default parameters (0 trained) 0.373±0.0032 / 0.101±0.0011 / 0.691±0.0016; AVG baseline 0.385±0.0036 / 0.101±0.0011 / 0.500±0.0018; **SM-2 0.71±0.013 / 0.199±0.0021 / 0.604±0.0018**. — [srs-benchmark README @ 8a75a35](https://github.com/open-spaced-repetition/srs-benchmark/blob/8a75a35/README.md)
- Same commit, **weighted by number of reviews**: FSRS-5 0.320±0.0052 / 0.050±0.0010 / 0.700±0.0028; FSRS-5 default params 0.346±0.0060 / 0.081±0.0017 / 0.681±0.0028; AVG 0.354±0.0059 / 0.085±0.0019 / 0.508±0.0029; **SM-2 0.54±0.012 / 0.147±0.0029 / 0.599±0.0031**. — [srs-benchmark README @ 8a75a35](https://github.com/open-spaced-repetition/srs-benchmark/blob/8a75a35/README.md)
- Same commit: "FSRS-5 has a 99.0% superiority over SM-2, meaning that for 99.0% of users, RMSE will be lower with FSRS-5 than with SM-2. But please remember that SM-2 wasn't designed to predict probabilities". — [srs-benchmark README @ 8a75a35](https://github.com/open-spaced-repetition/srs-benchmark/blob/8a75a35/README.md)
- Expertium: FSRS-6 (with recency weighting) has "a 99.6% superiority over Anki SM-2" on log loss; caveat: "There is no way to have a truly fair, no caveats, comparison between FSRS and SM-2." — [Expertium, Benchmark](https://expertium.github.io/Benchmark.html)
- Current srs-benchmark README (2026-11-19; 9,999 collections; 349,923,850 reviews evaluated; without same-day reviews), log loss / RMSE(bins) / AUC: FSRS-7 0.3401±0.0043 / 0.0634±0.0011 / 0.7167±0.0022; FSRS-rs (FSRS-6 + recency weighting) 0.3443±0.0042 / 0.0635±0.0010 / 0.7074±0.0022; **FSRS-6 0.3460±0.0042 / 0.0653±0.0011 / 0.7034±0.0023**; FSRS-5 0.3561±0.0044 / 0.0742±0.0012 / 0.7010±0.0023; FSRS-7 default parameters 0.3620±0.0045 / 0.0910±0.0014 / 0.7029±0.0022; FSRS-4.5 0.3625±0.0045 / 0.0764±0.0013 / 0.6891±0.0023; AVG 0.3945±0.0051 / 0.1034±0.0016 / 0.4997±0.0025; HLR (Duolingo) 0.4694±0.0074 / 0.1275±0.0019 / 0.6369±0.0026; Ebisu v2 0.4989±0.0078 / 0.1627±0.0022 / 0.6051±0.0025. SM-2 no longer appears in the current tables. — [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md)
- With same-day reviews included in evaluation (10,000 collections; 519,296,315 reviews): FSRS-7 0.3206±0.0040 log loss versus FSRS-6 0.3842±0.0051 and AVG 0.3816±0.0048, i.e. FSRS-6 is no better than a constant at predicting same-day recall. — [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md)
- Review load: "With FSRS, users have to do 20–30% fewer reviews than with the SM-2 algorithm to achieve the same retention level (2026-02-12 update: this figure is based on very old simulation results, take it with a grain of salt)." — [awesome-fsrs wiki, ABC of FSRS](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/ABC-of-FSRS)
- Qualitative mechanism: "For many users, the default algorithm (SM-2) tends to show new cards at unnecessarily short intervals... for mature cards, the opposite is true: FSRS is more conservative than SM-2." FSRS is also "much better at scheduling cards that have been reviewed late". — [fsrs4anki tutorial](https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md), [awesome-fsrs wiki, ABC of FSRS](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/ABC-of-FSRS)
- Overdue handling: under SM-2/Anki a late successful review increases the next interval linearly with the delay, whereas in FSRS "the subsequent stability converges to an upper limit". — [awesome-fsrs wiki, The Algorithm](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)
- SM-2 as originally specified: `I(1)=1`, `I(2)=6`, `I(n)=I(n-1)*EF` for n>2; EF starts at 2.5; `EF' = EF + (0.1 - (5-q)*(0.08 + (5-q)*0.02))` with a floor of 1.3; quality q is 0-5; if q < 3 repetitions restart from I(1) "without changing the E-Factor"; items scoring below 4 are repeated in the same session until they score at least 4. — [SuperMemo, SM-2](https://super-memory.com/english/ol/sm2.htm)
- Anki adoption: FSRS is built into Anki (first integrated as FSRS v4) and Anki 26.09 pins the FSRS-6 crate; SM-2-style settings remain alongside (`initial_ease: 2.5`, `easy_multiplier: 1.3`, `hard_multiplier: 1.2`). — [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md), [anki Cargo.toml](https://github.com/ankitects/anki/blob/main/Cargo.toml), [anki rslib/src/deckconfig/mod.rs](https://github.com/ankitects/anki/blob/main/rslib/src/deckconfig/mod.rs)
- Anecdotal simulator results on the Anki forum vary widely (one run reported about 8% fewer daily repetitions; other users reported FSRS needing more reviews at a nominal 90% target until settings were adjusted). Reported via search summary only, not read in full. — [Anki forum thread 1](https://forums.ankiweb.net/t/update-simulator-for-fsrs-to-compare-with-ankis-built-in-scheduler/23793), [Anki forum thread 2](https://forums.ankiweb.net/t/anki-sm2-beating-fsrs-in-fsrs-simulator/34866)

### Inferences
- The most relevant number for this app (which will run default parameters with no optimizer) is the *default-parameter* row: FSRS-5 defaults at 0.373 log loss still beat SM-2 at 0.71 and the AVG baseline at 0.385 in the 2024 tables. No FSRS-6 default-parameter row exists in the current README (only FSRS-7 defaults: 0.3620 vs AVG 0.3945), so "FSRS-6 defaults beat SM-2" is an extrapolation from FSRS-5 and FSRS-7 rows, not a directly published figure.
- The benchmark measures prediction of recall, not learning efficiency. Better prediction is what lets a scheduler hit a chosen retention target; SM-2 has no retention target at all, which is the practical advantage for a product (one "desired retention" knob instead of ease factors and interval multipliers).
- Honest framing for the report: "FSRS is far better calibrated than SM-2 (about 2x lower log loss, about 99% of users); the review-load saving is plausible but the 20-30% figure is unverified."
- SM-2's known failure mode ("ease hell": EF ratcheting down to 1.3 after repeated low grades) is addressed in FSRS by difficulty mean reversion, per the tutorial; with the FSRS-6 default `w7 = 0.001` that reversion is slow.
- The 2024 and 2026 benchmark tables use different datasets (20k vs 10k users) and filters, so SM-2's 2024 numbers must not be placed in the same table as FSRS-6's 2026 numbers without that caveat.

### Gaps
- No current (2026) srs-benchmark row for SM-2 or Anki-SM-2 in the README text; Expertium's page has them only as images that I could not read. The 99.6% figure is the only FSRS-6-vs-SM-2 number I could verify in text.
- No controlled study (randomised users, measured retention and review counts) comparing FSRS with SM-2 was found; all review-load claims are simulations or anecdotes.
- **Leitner baseline: no source was retrieved in this session.** Leitner is not in srs-benchmark. Anything said about Leitner in the report (fixed boxes, promote on correct, demote to box 1 on wrong, fixed per-box intervals) would be from general knowledge and needs a citation before being presented as sourced.

## How should a 2-button or auto-graded typed answer map onto FSRS's four grades?

### Takeaway
Map wrong to Again (1) and right to Good (3); FSRS's maintainers say Again/Good-only usage works fine and may even be slightly more accurate. The one hard rule is that a failed recall must never be recorded as Hard, because Hard is a passing grade.

### Cited Findings
- "Q8: I only use 'Again' and 'Good', will FSRS work fine? A8: Yes. According to our research, FSRS is a little more accurate for people who mostly use 'Again' and 'Good' than for people who use all 4 buttons a lot. However, this conclusion may change as we investigate this further." — [fsrs4anki tutorial](https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md)
- "Internally, FSRS treats Again as 'fail' and Hard/Good/Easy as 'pass'." — [fsrs4anki tutorial](https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md)
- "FSRS can adapt to almost any habit, except for one: pressing 'Hard' instead of 'Again' when you forget the information... If you press 'Hard' when you have failed to recall the information, all intervals will be unreasonably high." — [Anki manual, Deck Options](https://docs.ankiweb.net/deck-options.html)
- "The grade should be chosen based only on how easy it was to answer the card, not how long you want to wait until you see it again"; and "you should not change your rating habits" because FSRS uses past rating history. — [fsrs4anki tutorial](https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md)
- The benchmark has a `--two_buttons` option described as "Treat Hard and Easy as Good", i.e. the maintainers' own two-grade collapse is Again -> 1 and everything else -> 3. — [srs-benchmark README](https://github.com/open-spaced-repetition/srs-benchmark/blob/main/README.md)
- Effect of grades in the formulas: Hard multiplies the stability gain by `w15 = 0.6014`, Easy by `w16 = 1.8729`; difficulty moves by `-w6*(G-3)` with `w6 = 3.0194`, so Good leaves difficulty unchanged apart from mean reversion, Again raises it and Easy lowers it. — [py-fsrs scheduler.py](https://github.com/open-spaced-repetition/py-fsrs/blob/main/fsrs/scheduler.py)

### Inferences
- Recommended mapping for this app: wrong / "didn't know" -> Again (1); right -> Good (3). Store the grade as 1-4 anyway so richer grading can be added later without a migration.
- For auto-graded typed answers, a defensible optional refinement (my suggestion, not sourced): exact match -> Good; correct only after a hint, or a near-miss the app accepts as correct (typo, accent) -> Hard; anything the app counts as incorrect -> Again. Never auto-assign Easy from answer speed without data: with defaults, a first-review Easy gives an 8-day first interval versus 2 days for Good, so false positives are costly.
- Because only Again raises difficulty in a two-grade scheme and Good never lowers it (beyond the tiny `w7` reversion), difficulty in a 2-button app drifts upward only. That is the same behaviour Anki users who press only Again/Good get, and the maintainers report it works.
- LLM-graded free-text answers should be collapsed to pass/fail before reaching the scheduler; a "partially correct" verdict is a product decision between Again (safe: shorter interval) and Hard (passing).

### Gaps
- The "little more accurate for Again/Good users" claim is stated without figures in the tutorial; I did not find the underlying analysis.
- No source addresses auto-graded or typed-answer mapping specifically; the refinement above is inference.

## Recommended daily new-card limits for beginners and the "review debt" problem

### Takeaway
Anki's defaults are 20 new cards/day and a 200 reviews/day cap, tied together by an explicit 10x rule: each daily new card costs roughly ten daily reviews at steady state. A beginner-friendly app should default lower than 20 and throttle new cards when reviews pile up.

### Cited Findings
- Anki defaults in source: `new_per_day: 20`, `reviews_per_day: 200`. — [anki rslib/src/deckconfig/mod.rs](https://github.com/ankitects/anki/blob/main/rslib/src/deckconfig/mod.rs)
- Anki manual: "If you are consistently learning 20 new cards a day, you can expect your daily reviews to be roughly about 200 cards/day"; "You can decrease the reviews required by introducing fewer new cards each day until your review burden decreases"; the manual warns of users who "excitedly studied hundreds of new cards over their first few days" and were then overwhelmed. — [Anki manual, Deck Options](https://docs.ankiweb.net/deck-options.html)
- Anki UI tooltip: new cards/day "should typically be at least 10x smaller than your review limit", "Because new material will increase your short-term review workload". The options screen warns when `min(9999, new * 10) > review limit`. — [anki ftl/core/deck-config.ftl](https://github.com/ankitects/anki/blob/main/ftl/core/deck-config.ftl), [anki DailyLimits.svelte](https://github.com/ankitects/anki/blob/main/ts/routes/deck-options/DailyLimits.svelte)
- Anki default behaviour: "the review limit also applies to new cards, and no new cards will be shown when the review limit has been reached" (unless the user opts out). — [anki ftl/core/deck-config.ftl](https://github.com/ankitects/anki/blob/main/ftl/core/deck-config.ftl)
- Maximum reviews/day "can help to smooth out occasional peaks in due card counts" for consistent studiers. — [Anki manual, Deck Options](https://docs.ankiweb.net/deck-options.html)
- Returning after a break: "If you took a long break from Anki and then reviewed cards that are long overdue, don't worry, it won't skew your parameters, as long as you answer honestly"; FSRS's post-delay stability "converges to an upper limit" instead of growing linearly with the delay. — [fsrs4anki tutorial](https://github.com/open-spaced-repetition/fsrs4anki/blob/main/docs/tutorial.md), [awesome-fsrs wiki, The Algorithm](https://github.com/open-spaced-repetition/awesome-fsrs/wiki/The-Algorithm)
- Desired retention is the other workload lever: above 90% "the workload increases very quickly". — [Anki manual, Deck Options](https://docs.ankiweb.net/deck-options.html)

### Inferences
- Suggested defaults for a small self-hosted learning app aimed at beginners: 10 new items/day (about 100 reviews/day at steady state by Anki's 10x rule), a review cap of 10x the new limit, and Anki's rule that reviews are served before new items and count against the cap. This is my recommendation derived from the 10x rule; Anki's own default is 20/200.
- Review debt mechanics: new cards are a commitment to future reviews, so missed days add to a due pile that does not shrink on its own. Mitigations that follow from the sources: (1) stop or reduce new cards automatically while due reviews exceed the daily cap; (2) cap daily reviews so a backlog is paid down over several days; (3) when capping, serve the backlog in a deliberate order; (4) let the user lower desired retention (0.85 nearly doubles intervals under FSRS-6 defaults).
- FSRS makes backlog recovery cheaper than SM-2 in one specific way: R is computed from the real elapsed time, so an overdue card answered correctly earns a larger, but bounded, stability increase, and one answered wrong is handled by the lapse formula. No special "overdue" code path is needed.
- FSRS provides `R(t,S)` for every card, so the app can show a live "predicted recall" figure and sort a backlog by it without extra modelling.

### Gaps
- No primary source was found giving a specific recommended new-card number for beginners below Anki's default of 20; community figures (5-10/day for language learners and similar) were not verified in this session and are omitted.
- No sourced guidance was retrieved on the best backlog review order (e.g. ascending retrievability versus due date); Anki exposes several sort orders, but I did not fetch that documentation.
- Anki's "Easy Days" and load-balancing features (which smooth daily load) were only seen in passing in the manual; their mechanics were not researched.
