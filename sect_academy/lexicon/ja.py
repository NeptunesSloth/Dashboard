"""Japanese -> English lookup (data: ``sect_academy/dict/ja/``; JMdict, EDRDG, CC BY-SA 4.0).

* **Words**: kanji and kana headwords both lead to an entry; every entry has its
  kana readings, part-of-speech codes and a frequency rank (JMdict's priority
  marks), which orders homographs (はし: bridge, chopsticks, edge).
* **Conjugations**: a tapped 食べました is undone by the suffix rules in
  ``ja_rules`` (the Yomichan/10ten approach) and only kept where the entry's
  part of speech agrees; the path is shown ("polite past").
* **Segmenting**: Japanese has no spaces, so a page is cut with ``cjk.lattice``
  over dictionary words *and* their conjugated forms; particles (は が を に で と
  も の へ から まで より や ね よ か) come out as their own words.
* **Rōmaji**: Hepburn from the kana reading — long vowels with macrons for
  display (gakkō), and as the kana are written (gakkou) for typing, which is the
  convention of this app's Japanese course.
"""
from __future__ import annotations

import gzip
import re
import threading
from bisect import bisect_left
from functools import lru_cache
from pathlib import Path

from . import cjk
from .ja_rules import deinflect, describe, kana_from_romaji, pos_ok, romaji, to_hiragana

LANG, NAME, SPEECH = "ja", "Japanese", "ja-JP"
DICT_DIR = Path(__file__).parent.parent / "dict" / "ja"
CREDIT = ("Source: JMdict, Electronic Dictionary Research and Development Group (EDRDG), CC BY-SA 4.0 — "
          "https://www.edrdg.org/edrdg/licence.html")
USES_CONTEXT = True
MAX_LEN = 12
PARTICLES = {"は": "wa", "へ": "e", "を": "o"}            # read differently as particles
# Particle pairs JMdict lists as one expression; read as two words they teach more (に + は).
SPLIT = {"には", "とは", "へは", "からは", "までは", "にも", "とも", "での", "との", "への", "からの", "までの", "をも",
         "にの", "がは", "はが", "もの", "のは", "のが", "のを", "のに", "のも", "ので", "かね", "かな", "よね",
         "なんです", "ですか", "ですね", "ですよ", "わたしは", "さんは", "ははは", "ますか", "ますね", "ますよ", "がい", "はい", "がる", "はし"}
SPLIT_OK = {"ので", "のに", "はい", "もの", "かな"}      # real words: kept whole unless the text reads better split
_PARTICLE_SET = {"は", "が", "を", "に", "で", "と", "も", "の", "へ", "から", "まで", "より", "や", "ね", "よ", "か", "な", "わ", "ぞ"}
_READ_FIX = {"こんにちは": "konnichiwa", "こんばんは": "konbanwa"}


class _Dict:
    def __init__(self) -> None:
        self.kanji: list[str] = []
        self.kana: list[str] = []
        self.tags: list[tuple[str, ...]] = []
        self.rank: list[int] = []
        self.gloss: list[str] = []
        self.index: dict[str, list[int]] = {}      # any written form or reading (katakana as written) -> entry ids
        self.keys: list[str] = []
        self._loose: dict[str, list[str]] | None = None
        self.loose_keys: list[str] = []

    def load(self) -> _Dict:
        tag_cache: dict[str, tuple[str, ...]] = {}
        with gzip.open(DICT_DIR / "jmdict_ja_en.tsv.gz", "rt", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                p = line.rstrip("\n").split("\t")
                if len(p) != 5:
                    continue
                i = len(self.kanji)
                self.kanji.append(p[0])
                self.kana.append(p[1])
                self.tags.append(tag_cache.setdefault(p[2], tuple(p[2].split())))
                self.rank.append(int(p[3]) if p[3].isdigit() else 99)
                self.gloss.append(p[4])
                for form in p[0].split(",") if p[0] else ():
                    self.index.setdefault(form.rstrip("!"), []).append(i)
                for r in p[1].split(","):
                    self.index.setdefault(r.split("@")[0].rstrip("!"), []).append(i)
        for ids in self.index.values():
            ids.sort(key=lambda i: self.rank[i])
        self.keys = sorted(self.index)
        return self

    def loose(self) -> dict[str, list[str]]:
        """Readings with long vowels and ー taken out (とうきょう, ときょう -> ときょ): for rōmaji typed without them."""
        if self._loose is None:
            idx: dict[str, list[str]] = {}
            for k in self.index:
                if all(cjk.is_hira(ch) or cjk.is_kata(ch) for ch in k):
                    idx.setdefault(_loosen(k), []).append(k)
            self._loose = idx
            self.loose_keys = sorted(idx)
        return self._loose


_O_ROW = set("おこそとのほもよろごぞどぼぽょ")
_U_ROW = set("うくすつぬふむゆるぐずづぶぷゅ")
_A_ROW = set("あかさたなはまやらわがざだばぱゃ")
_I_ROW = set("いきしちにひみりぎじぢびぴ")
_E_ROW = set("えけせてねへめれげぜでべぺ")


def _loosen(k: str) -> str:
    h = to_hiragana(k).replace("ー", "")
    out = []
    for ch in h:
        prev = out[-1] if out else ""
        if (ch == "う" and (prev in _O_ROW or prev in _U_ROW)) or (ch == "お" and prev in _O_ROW) or (ch == "あ" and prev in _A_ROW) \
                or (ch == "い" and prev in _I_ROW) or (ch == "え" and prev in _E_ROW):
            continue
        out.append(ch)
    return "".join(out)


_dict: _Dict | None = None
_dict_lock = threading.Lock()


def dictionary() -> _Dict:
    global _dict
    if _dict is None:
        with _dict_lock:
            if _dict is None:
                _dict = _Dict().load()
    return _dict


def norm_word(w) -> str:
    return cjk.norm_word(w)


# ---------------------------------------------------------------------------
# one entry
# ---------------------------------------------------------------------------
def _forms(i: int) -> list[tuple[str, bool]]:
    k = dictionary().kanji[i]
    return [(f.rstrip("!"), f.endswith("!")) for f in k.split(",")] if k else []


def _readings(i: int) -> list[tuple[str, bool, list[str]]]:
    out = []
    for r in dictionary().kana[i].split(","):
        base, _, restr = r.partition("@")
        out.append((base.rstrip("!"), base.endswith("!"), restr.split("/") if restr else []))
    return out


def reading_for(i: int, surface: str) -> str:
    """The kana reading of entry i as written ``surface``."""
    rs = _readings(i)
    for r, _, _ in rs:
        if r == surface:
            return r
    for r, _, restr in rs:
        if not restr or surface in restr:
            if restr != ["-"]:
                return r
    return rs[0][0]


def _is_kana(s: str) -> bool:
    return all(cjk.is_hira(ch) or cjk.is_kata(ch) for ch in s)


def _uk(i: int) -> bool:
    return "uk" in dictionary().tags[i] or not dictionary().kanji[i]


def rom_of(i: int, reading: str, macrons: bool = True) -> str:
    if reading in _READ_FIX:
        return _READ_FIX[reading]
    tags = dictionary().tags[i]
    if reading in PARTICLES and "prt" in tags:
        return PARTICLES[reading]
    verb = any(t.startswith("v5u") for t in tags)
    return romaji(reading, macrons=macrons, keep_final_ou=verb)


def _score(i: int, surface: str) -> float:
    """Lower is better: the entry's frequency rank, and on kana a word normally written in kanji counts as rarer."""
    d = dictionary()
    s = float(d.rank[i])
    if surface in _PARTICLE_SET and "prt" in d.tags[i]:
        s -= 20
    elif _is_kana(surface) and not _uk(i):
        common_kana = any(r == surface and c for r, c, _ in _readings(i))
        s += 6 if common_kana else 14
    return s


# ---------------------------------------------------------------------------
# finding a word (with its conjugation undone)
# ---------------------------------------------------------------------------
@lru_cache(maxsize=65536)
def find(surface: str) -> tuple:
    """All readings of a written piece as (score, entry, term, reasons), best first."""
    d = dictionary()
    out = []
    for term, types, reasons in deinflect(surface):
        ids = d.index.get(term)
        if not ids:
            continue
        for i in ids:
            if pos_ok(types, d.tags[i]):
                # 行った is more often 行く (went) than 行う (did), きます 来る than 着る: the irregular verbs win close calls
                bonus = -12 if reasons and ("v5k-s" in d.tags[i] or "vk" in d.tags[i]) else 0
                out.append((_score(i, term) + 5 * len(reasons) + bonus, i, term, reasons))
    if not out and len(surface) >= 3 and surface[0] in "おご" and cjk.is_hira(surface[1]):
        # the polite prefix お/ご on a word JMdict lists without it (おいくつ -> いくつ)
        out = [(sc + 8, i, t, (*rs, "polite prefix o-/go-")) for sc, i, t, rs in find(surface[1:])
               if any(p in _CONTENT or p == "adv" for p in d.tags[i])]
    out.sort(key=lambda x: (x[0], x[1]))
    seen, best = set(), []
    for x in out:
        if x[1] not in seen:
            seen.add(x[1])
            best.append(x)
    return tuple(best)


def has_word(w: str) -> bool:
    return w in dictionary().index


def _prefix(s: str) -> bool:
    keys = dictionary().keys
    i = bisect_left(keys, s)
    return i < len(keys) and keys[i].startswith(s)


# ---------------------------------------------------------------------------
# segmenting
# ---------------------------------------------------------------------------
def _edges(s: str, i: int):
    out = []
    for j in range(i + 1, min(len(s), i + MAX_LEN) + 1):
        sub = s[i:j]
        last = sub[-1]
        if not (cjk.is_hira(last) or cjk.is_kata(last)) and j - i > 1 and not _prefix(sub):
            break
        if cjk.kind(last) not in ("h", "H", "K"):
            break
        if j - i > 1 and sub in SPLIT and sub not in SPLIT_OK:
            continue
        hits = find(sub)
        if not hits:
            continue
        sc, i0, term, reasons = hits[0]
        cost = 1.0 + min(sc, 99) / 220 + (0.25 if sub in SPLIT_OK else 0.0)
        tags = dictionary().tags[i0]
        if _is_kana(term) and not _uk(i0) and not (sub in _PARTICLE_SET and "prt" in tags) and sub not in _HONORIFIC:
            # kana for a word normally written in kanji: likely in beginner text, but a weaker guess
            cost += 0.45 if any(r == term and c for r, c, _ in _readings(i0)) else 0.9
        if dictionary().rank[i0] >= 99 and _is_kana(sub):
            cost += 1.2                       # no frequency data at all: a rare word, seldom the right cut in kana
        if sub[0] in "んっゃゅょぁぃぅぇぉー":
            cost += 1.0                       # (んで, っす) colloquial pieces that rarely start a word in writing
        if _is_kana(sub) and j - i > 1 and sub[0] in "はがをでにもとへ" and not _uk(i0):
            cost += 0.15                      # likelier a particle and the next word (は|なに, not はな|に)
        if "exp" in tags and ("を" in sub[1:] or "が" in sub[1:-1]):
            cost += 1.15                      # a phrase with its own particle (絵を描く): read as its words
        elif "exp" in tags and not any(t in _CONTENT for t in tags) and j - i > 1:
            cost += 1.15                      # a set phrase (これは, どうぞよろしく): read as its words when they are words
        elif (_is_kana(sub) and sub[-1] in _ENDS and dictionary().rank[i0] >= 30 and has_word(sub[:-1])
              and not any(t in _CONTENT for t in tags)):
            cost += 1.15
        if j - i == 1 and cjk.is_hira(sub) and sub not in _ONE_KANA:
            cost += 0.6                       # a lone hiragana is rarely a word unless it is a particle
        out.append((j, cost))
    n = number_at(s, i)
    if n and n[0] > i + 1:
        out.append((n[0], 0.9))
    if (i == 0 or s[i - 1] in _ENDS or cjk.kind(s[i - 1]) != cjk.kind(s[i])) and not s.startswith(_HONORIFIC, i):
        for j in range(i + 2, min(len(s), i + 4) + 1):      # a name before さん/くん/さま (たなかさん, スミスさん)
            if s.startswith(_HONORIFIC, j) and s[j - 1] not in "はがをにでもと" and all(cjk.kind(ch) in ("H", "K") for ch in s[i:j]):
                out.append((j, 1.3 + 0.1 * (j - i)))
                break
    return out


_HONORIFIC = ("さん", "くん", "ちゃん", "さま", "せんせい", "様", "君", "先生")


_CONTENT = {"n", "v1", "vk", "vs", "vs-i", "vs-s", "adj-i", "adj-na", "adj-no", "pn", "n-adv", "n-t", "ctr", "num",
            "v5k", "v5u", "v5s", "v5t", "v5n", "v5b", "v5m", "v5r", "v5g", "v5k-s", "v5aru", "v5r-i", "adj-ix", "conj"}
_ENDS = set("はがをにでもとかねよの")
_ONE_KANA = set("はがをにでとものへやねよかなわさぞぜしてだ")


# numbers written out (さんじゅうに, 三十二, 32) and the counter after them (さい, じ, ふん, えん …)
_NUM = {"いち": 1, "いっ": 1, "に": 2, "さん": 3, "よん": 4, "よ": 4, "し": 4, "ご": 5, "ろく": 6, "ろっ": 6, "なな": 7, "しち": 7,
        "はち": 8, "はっ": 8, "きゅう": 9, "く": 9, "じゅう": 10, "じゅっ": 10, "じっ": 10, "ひゃく": 100, "びゃく": 100,
        "ぴゃく": 100, "せん": 1000, "ぜん": 1000, "まん": 10000, "一": 1, "二": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7,
        "八": 8, "九": 9, "十": 10, "百": 100, "千": 1000, "万": 10000, "〇": 0, "零": 0}
_BIG = {10, 100, 1000, 10000}
COUNTERS = {"じ": "o'clock", "時": "o'clock", "じかん": "hours", "時間": "hours", "ふん": "minutes", "ぷん": "minutes", "分": "minutes",
            "はん": "and a half", "半": "and a half", "さい": "years old", "歳": "years old", "才": "years old", "えん": "yen", "円": "yen",
            "にち": "day(s)", "日": "day(s)", "か": "day(s)", "がつ": "month (of the year)", "月": "month (of the year)",
            "かげつ": "months", "ヶ月": "months", "か月": "months", "ねん": "year(s)", "年": "year(s)", "にん": "people", "人": "people",
            "ほん": "long things", "ぼん": "long things", "ぽん": "long things", "本": "long things", "まい": "flat things",
            "枚": "flat things", "かい": "times / floor", "回": "times", "階": "floor", "つ": "things", "こ": "small things",
            "個": "small things", "さつ": "books", "冊": "books", "ひき": "animals", "びき": "animals", "ぴき": "animals",
            "匹": "animals", "ばん": "number", "番": "number", "ど": "times / degrees", "度": "times / degrees"}
_NUM_KEYS = sorted(_NUM, key=len, reverse=True)
_CTR_KEYS = sorted(COUNTERS, key=len, reverse=True)


def number_at(s: str, i: int) -> tuple[int, int, str] | None:
    """(end, value, counter) for a number written at s[i:] with a counter after it (or a compound like にじゅうご)."""
    j, pieces, digits = i, [], ""
    while j < len(s) and s[j].isdigit():
        digits += s[j]
        j += 1
    if not digits:
        while j < len(s):
            for k in _NUM_KEYS:
                if s.startswith(k, j):
                    pieces.append(_NUM[k])
                    j += len(k)
                    break
            else:
                break
    if j == i:
        return None
    ctr = next((c for c in _CTR_KEYS if s.startswith(c, j)), "")
    if not digits and not ctr and not (len(pieces) >= 2 and any(p in _BIG for p in pieces)):
        return None
    if not digits and len(pieces) == 1 and pieces[0] in (2, 5, 9, 4) and ctr in ("", "か", "こ", "ど") and s[i] not in _NUM_KANJI:
        return None                                                       # に, ご, く, し: far likelier a particle or a word
    if digits:
        value = int(digits[:12])
    else:
        value, cur = 0, 0
        for p in pieces:
            if p in _BIG:
                if p == 10000:
                    value, cur = (value + (cur or 1)) * p, 0
                else:
                    value += (cur or 1) * p
                    cur = 0
            else:
                cur = p
        value += cur
    return j + len(ctr), value, ctr


_NUM_KANJI = set("一二三四五六七八九十百千万〇零")


def _unknown(s: str, i: int):
    return cjk.fallback_piece(s, i), 2.0 if not cjk.is_kata(s[i]) else 1.6


def segment(text: str) -> list[dict]:
    return cjk.segment(text, _edges, _unknown, norm_word)


# ---------------------------------------------------------------------------
# lookup and search
# ---------------------------------------------------------------------------
def _sense(i: int, surface: str) -> dict:
    r = reading_for(i, surface) if not _is_kana(surface) else surface
    return {"src": "jmdict", "text": dictionary().gloss[i], "read": r, "rom": rom_of(i, r)}


def _head(i: int) -> str:
    """How an entry is usually written: kana if JMdict says so, else its first kanji form."""
    f = _forms(i)
    return _readings(i)[0][0] if _uk(i) or not f else f[0][0]


def romanise(word: str) -> str:
    """Rōmaji as this app's course types it (gakkou), "" if the word is not in the dictionary."""
    hits = find(word)
    if not hits:
        return ""
    _, i, term, _ = hits[0]
    return rom_of(i, reading_for(i, term) if not _is_kana(term) else term, macrons=False)


def romanise_alt(word: str) -> list[str]:
    """Other accepted spellings of the rōmaji (with macrons: gakkō)."""
    hits = find(word)
    if not hits:
        return []
    _, i, term, _ = hits[0]
    r = reading_for(i, term) if not _is_kana(term) else term
    a, b = rom_of(i, r), rom_of(i, r, macrons=False)
    return [a] if a != b else []


def lookup(raw, mine: dict | None = None, around: tuple[str, str] | None = None) -> dict:
    """Look a word up. -> {found, word, lemma, path, how, how_text, reading, rom, senses[{src, text, read, rom}], also, weak}."""
    word = norm_word(raw)
    if not word:
        return {"ok": True, "found": False, "word": "", "senses": [], "also": [], "credit": CREDIT}
    mine = mine or {}
    hits = find(word)
    out = {"ok": True, "word": word, "credit": CREDIT, "weak": False}
    senses: list[dict] = []
    if word in mine:
        senses.append({"src": "mine", "text": mine[word]})
    also: list[dict] = []
    if hits:
        _, i0, term, reasons = hits[0]
        same = [h for h in hits if h[2] == term and h[3] == reasons]
        senses += [_sense(h[1], term) for h in same[:4]]
        path = [word]
        if reasons:
            if reasons[0] == "suru verb" and term + "する" != word:
                path.append(term + "する")
            path.append(term)
        first = _sense(i0, term)
        head = _head(i0)
        forms = [f for f, _ in _forms(i0) if f != term][:2]
        if head != term and head not in forms:
            forms.insert(0, head)
        out.update(found=True, lemma=term, path=path, how="inflected" if reasons else "", how_text=describe(reasons),
                   reading=first["read"], rom=first["rom"], rom_typed=rom_of(i0, first["read"], macrons=False),
                   senses=senses, forms=forms[:3])
        for _, i, t, rs in [h for h in hits if h not in same][:3]:
            s = _sense(i, t)
            also.append({"lemma": t, "path": [word, t] if t != word else [word], "how": "inflected" if rs else "",
                         "how_text": describe(rs), "reading": s["read"], "senses": [s]})
    elif number_at(word, 0) and number_at(word, 0)[0] == len(word):
        _, value, ctr = number_at(word, 0)
        text = f"{value:,}" + (f" {COUNTERS[ctr]}" if ctr else "")
        kana = _is_kana(word)
        senses.append({"src": "number", "text": text + (f" (number + counter {ctr})" if ctr else " (number)"), "read": word if kana else "",
                       "rom": romaji(word) if kana else ""})
        out.update(found=True, lemma=word, path=[word], how="", how_text="", reading=word if kana else "",
                   rom=romaji(word) if kana else "", senses=senses, forms=[])
    elif around and (around[1] or "").startswith(_HONORIFIC) and all(cjk.kind(ch) in ("H", "K") for ch in word):
        senses.append({"src": "name", "text": f"a name (followed by {around[1][:2]})", "read": word, "rom": romaji(word)})
        out.update(found=True, lemma=word, path=[word], how="", how_text="", reading=word, rom=romaji(word), senses=senses, forms=[])
    elif senses:
        out.update(found=True, lemma=word, path=[word], how="", how_text="", reading="", rom="", senses=senses, forms=[])
    else:
        out.update(found=False, lemma="", path=[word], how="", how_text="", reading="", rom="", senses=[], forms=[])
    if around and (around[0] or around[1]):
        big = cjk.around(word, around[0], around[1], has_word)
        if big:
            h = find(big)
            if h:
                s = _sense(h[0][1], big)
                also.insert(0, {"lemma": big, "path": [big], "how": "compound", "reading": s["read"], "senses": [s]})
    if len(word) > 1 and any(cjk.is_han(ch) for ch in word):
        for ch in dict.fromkeys(c for c in word if cjk.is_han(c)):
            h = find(ch)
            if h:
                s = _sense(h[0][1], ch)
                also.append({"lemma": ch, "path": [ch], "how": "character", "reading": s["read"], "senses": [s]})
    out["also"] = also[:6]
    return out


def _row(i: int, w: str) -> dict:
    r = reading_for(i, w) if not _is_kana(w) else w
    return {"w": w, "en": dictionary().gloss[i][:300], "src": "jmdict", "read": r if r != w else "", "rom": rom_of(i, r)}


def search(q, direction: str = "from", mine: dict | None = None, limit: int = 40) -> list[dict]:
    """Japanese -> English by kanji, kana or rōmaji (Hepburn, with or without long vowels), English -> Japanese by gloss."""
    q = re.sub(r"\s+", " ", q if isinstance(q, str) else "")[:60].strip()
    if not q:
        return []
    mine = mine or {}
    d = dictionary()
    rows: list[dict] = []
    if direction == "en":
        ql = q.lower()
        pat = re.compile(r"(?:^|[^a-z])" + re.escape(ql) + r"(?:$|[^a-z])")
        for k, v in mine.items():
            if ql in v.lower():
                rows.append({"w": k, "en": v, "src": "mine", "read": "", "rom": romanise(k)})
        scored = []
        for i, gl in enumerate(d.gloss):
            low = gl.lower()
            if ql not in low:
                continue
            senses = [x.strip() for x in re.split(r"[;,] ", re.sub(r"\([^)]*\)", "", low))]
            if ql in senses or f"to {ql}" in senses:
                score = 0 if senses[0] in (ql, f"to {ql}") else 1
            else:
                score = 2 if pat.search(low) else 3
            scored.append((score * 30 + d.rank[i], len(low), i))
        scored.sort()
        rows += [_row(i, _head(i)) for _, _, i in scored[: limit * 2]]
    else:
        w = norm_word(q)
        if w and any(cjk.kind(ch) in ("h", "H", "K") for ch in w):
            cands = [w]
        else:
            cands = kana_from_romaji(q)
            if not cands:
                return []
        for k, v in mine.items():
            if any(k.startswith(c) for c in cands):
                rows.append({"w": k, "en": v, "src": "mine", "read": "", "rom": romanise(k)})
        found: list[tuple[float, int, str]] = []
        for c in cands:
            for sc, i, term, _ in find(c):
                found.append((sc, i, term))
            for kk in (c, c and _kata(c)):
                for i in d.index.get(kk, []):
                    found.append((_score(i, kk), i, kk))
        pref: list[tuple[float, int, str]] = []
        for c in cands:
            for kk in dict.fromkeys((c, _kata(c))):
                j = bisect_left(d.keys, kk)
                while j < len(d.keys) and d.keys[j].startswith(kk) and len(pref) < limit * 8:
                    if d.keys[j] != kk:
                        pref += [(_score(i, d.keys[j]) + len(d.keys[j]), i, d.keys[j]) for i in d.index[d.keys[j]][:2]]
                    j += 1
        if not found and not _has_script(q):                      # rōmaji typed without long vowels: tokyo -> とうきょう
            loose = d.loose()
            for c in cands:
                for kk in loose.get(_loosen(c), []):
                    found += [(_score(i, kk), i, kk) for i in d.index[kk]]
        found.sort()
        pref.sort()
        for sc, i, term in found + pref:
            head = term if not _is_kana(term) or _uk(i) else _head(i)
            rows.append(_row(i, head))
    seen: set[tuple[str, str]] = set()
    out = []
    for r in rows:
        key = (r["w"], r["en"][:40])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out


def _kata(s: str) -> str:
    from .ja_rules import to_katakana
    return to_katakana(s)


def _has_script(q: str) -> bool:
    return any(cjk.kind(ch) in ("h", "H", "K") for ch in q)
