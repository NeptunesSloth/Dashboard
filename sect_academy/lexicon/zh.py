"""Mandarin Chinese -> English lookup (data: ``sect_academy/dict/zh/``; CC-CEDICT, CC BY-SA 4.0).

* **Words**: simplified and traditional headwords both lead to an entry; every
  entry has its pinyin (numbered in the data, shown with tone marks).
* **Segmenting**: Chinese has no spaces, so a page is cut into words against the
  headword list (``cjk.lattice``: fewest, most common words win; numbers and
  Latin runs stay whole; punctuation is its own piece).
* **Weak entries**: an entry that is only "variant of X", "surname X" or "see X"
  is a weak answer, like a name-only sense in Spanish: lookup prefers a real
  meaning and follows a variant to the entry it points at.
* **Frequencies**: CEDICT has none, so each headword carries jieba's word count
  (MIT; see the data README): it prices words for the segmenter and ranks search.
* **Which reading first**: a frequency is per word, not per reading. For a character with
  several readings (的 de/dí/dì, 了 le/liǎo) a short table below names the usual
  one; otherwise the entry with more senses comes first. All of them are shown.
"""
from __future__ import annotations

import gzip
import math
import re
import threading
from array import array
import unicodedata
from bisect import bisect_left
from pathlib import Path

from . import cjk

LANG, NAME, SPEECH = "zh", "Mandarin Chinese", "zh-CN"
DICT_DIR = Path(__file__).parent.parent / "dict" / "zh"
CREDIT = "Source: CC-CEDICT (MDBG), CC BY-SA 4.0."
USES_CONTEXT = True
MAX_LEN = 8                     # longest headword the segmenter tries (idioms are 4; a few names are longer)

# The usual reading of characters that have several (the first shown). Everything else: most senses first.
USUAL = {"了": "le5", "的": "de5", "着": "zhe5", "得": "de5", "地": "di4", "还": "hai2", "行": "xing2", "长": "chang2",
         "都": "dou1", "只": "zhi3", "要": "yao4", "会": "hui4", "和": "he2", "为": "wei4", "觉": "jue2", "种": "zhong3",
         "重": "zhong4", "好": "hao3", "少": "shao3", "发": "fa1", "中": "zhong1", "乐": "le4", "看": "kan4", "子": "zi3",
         "上": "shang4", "大": "da4", "干": "gan4", "当": "dang1", "难": "nan2", "空": "kong1", "调": "diao4", "解": "jie3",
         "结": "jie2", "朝": "chao2", "传": "chuan2", "卷": "juan3", "落": "luo4", "模": "mo2", "色": "se4", "似": "si4",
         "压": "ya1", "血": "xue4", "便": "bian4", "教": "jiao1", "应": "ying1", "相": "xiang1", "正": "zheng4", "曾": "ceng2",
         "几": "ji3", "期": "qi1", "车": "che1", "场": "chang3", "倒": "dao3", "给": "gei3", "更": "geng4", "过": "guo4",
         "号": "hao4", "假": "jia3", "间": "jian1", "将": "jiang1", "累": "lei4", "片": "pian4", "强": "qiang2", "省": "sheng3",
         "体": "ti3", "约": "yue1", "作": "zuo4", "差": "cha4", "数": "shu4", "分": "fen1", "处": "chu4", "没": "mei2",
         "说": "shuo1", "么": "me5", "那": "na4", "哪": "na3", "呢": "ne5", "吗": "ma5", "吧": "ba5", "啊": "a5", "一": "yi1",
         "不": "bu4", "个": "ge4", "们": "men5", "什": "shen2", "系": "xi4", "转": "zhuan3", "参": "can1", "降": "jiang4",
         "角": "jiao3", "背": "bei4", "头": "tou2", "量": "liang4", "乘": "cheng2", "载": "zai4", "这": "zhe4", "谁": "shei2",
         "在": "zai4", "是": "shi4", "人": "ren2", "我": "wo3", "你": "ni3", "他": "ta1", "她": "ta1", "有": "you3",
         "雨": "yu3", "雪": "xue3", "衣": "yi1", "王": "wang2", "饮": "yin3", "思": "si1"}

# ---------------------------------------------------------------------------
# pinyin
# ---------------------------------------------------------------------------
_MARKS = {"1": "̄", "2": "́", "3": "̌", "4": "̀"}
_SYL = re.compile(r"^([A-Za-züÜv:]+)([1-5])$")


def mark_syllable(syl: str) -> str:
    """'xue2' -> 'xué', 'lv4' -> 'lǜ', 'r5' -> 'r'; anything that is not a numbered syllable is left as it is."""
    m = _SYL.match(syl)
    if not m:
        return syl
    base = m.group(1).replace("u:", "ü").replace("v", "ü").replace("U:", "Ü").replace("V", "Ü")
    mark = _MARKS.get(m.group(2))
    if not mark:
        return base
    low = base.lower()
    if "a" in low:
        i = low.index("a")
    elif "e" in low:
        i = low.index("e")
    elif "ou" in low:
        i = low.index("o")
    else:
        i = max((k for k, ch in enumerate(low) if ch in "aeiouü"), default=-1)
        if i < 0:
            return base
    return unicodedata.normalize("NFC", base[: i + 1] + mark + base[i + 1:])


def pinyin_marks(numbered: str) -> str:
    """'xue2 xi2' -> 'xuéxí', 'Xi1 an1' -> "Xī'ān", 'san1 D da3 yin4' -> 'sān D dǎyìn'."""
    out = ""
    prev_syl = False
    for part in numbered.split():
        syl = bool(_SYL.match(part))
        m = mark_syllable(part)
        if not out:
            out = m
        elif syl and prev_syl:
            out += ("'" if m[:1].lower() in "aeoāáǎàēéěèōóǒò" else "") + m
        else:
            out += " " + m
        prev_syl = syl
    return out


def _plain(s: str) -> str:
    """Pinyin without tones, spaces or apostrophes, ü as u: the loosest search key."""
    s = unicodedata.normalize("NFD", s.lower().replace("u:", "u").replace("v", "u"))
    return re.sub(r"[^a-z]", "", "".join(ch for ch in s if unicodedata.category(ch) != "Mn"))


def _numbered_key(numbered: str) -> str:
    """'xue2 sheng5' -> 'xue2sheng' (neutral tone left bare), ü as v."""
    return re.sub(r"[\s'·,-]", "", re.sub(r"5\b", "", numbered.lower().replace("u:", "v").replace("ü", "v")))


def _marked_key(s: str) -> str:
    return re.sub(r"[\s'·,-]", "", unicodedata.normalize("NFC", s.lower()))


def romanise(word: str) -> str:
    """The pinyin (tone marks) of a word's usual reading, "" if it is not in the dictionary."""
    ids = _ranked(word)
    return pinyin_marks(dictionary().pin[ids[0]]) if ids else ""


# ---------------------------------------------------------------------------
# the dictionary
# ---------------------------------------------------------------------------
class _Dict:
    def __init__(self) -> None:
        self.simp: list[str] = []
        self.trad: list[str] = []
        self.pin: list[str] = []
        self.gloss: list[str] = []
        self.flags: list[str] = []
        self.freq = array("q")                  # jieba's count for the simplified form (0: none)
        self.head = cjk.IdMap()                  # simplified or traditional -> entry ids
        self.keys: list[str] = []                  # every headword, sorted (prefix search)
        self._pinyin: cjk.IdMap | None = None
        self.pinyin_keys: list[str] = []

    def load(self) -> _Dict:
        head = cjk.IdMap()
        with gzip.open(DICT_DIR / "cedict_zh_en.tsv.gz", "rt", encoding="utf-8") as f:
            for line in f:
                if line.startswith("#"):
                    continue
                p = line.rstrip("\n").split("\t")
                if len(p) != 6:
                    continue
                i = len(self.simp)
                self.simp.append(p[0])
                self.trad.append(p[1] or p[0])
                self.pin.append(p[2])
                self.gloss.append(p[3])
                self.flags.append(p[4])
                self.freq.append(int(p[5]) if p[5].isdigit() else 0)
                head.add(p[0], i)
                if p[1] and p[1] != p[0]:
                    head.add(p[1], i)
        self.head = head.freeze()
        self.keys = sorted(self.head)
        return self

    def pinyin_index(self) -> cjk.IdMap:
        """Toneless pinyin -> entry ids (built on the first pinyin search)."""
        if self._pinyin is None:
            idx = cjk.IdMap()
            for i, p in enumerate(self.pin):
                idx.add(_plain(p), i)
            self._pinyin = idx.freeze()
            self.pinyin_keys = sorted(idx)
        return self._pinyin


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


def _weak(i: int) -> bool:
    return "w" in dictionary().flags[i]


def _order(word: str, i: int) -> tuple:
    d = dictionary()
    usual = USUAL.get(word)
    # a reading whose first sense is literary, archaic or dialect (雨 yù "(literary) to rain") after the everyday one
    marked = bool(_REGISTER.match(d.gloss[i]))
    return (_weak(i), "p" in d.flags[i] and not word[:1].isupper(), usual is not None and d.pin[i] != usual,
            marked, -d.gloss[i].count("; "), i)


def _ranked(word: str) -> list[int]:
    d = dictionary()
    return sorted(d.head.get(word, []), key=lambda i: _order(word, i))


# ---------------------------------------------------------------------------
# segmenting
# ---------------------------------------------------------------------------
def _cost(ids: list[int], n: int) -> float:
    d = dictionary()
    strong = [i for i in ids if not _weak(i)]
    if not strong:
        return 1.5
    best = max(d.freq[i] for i in strong)
    proper = all("p" in d.flags[i] for i in strong)
    # a unigram cost: a common word is cheap (的 0.75, 已经 0.85), one with no count costs about as much as two
    return max(0.75, 1.6 - 0.07 * math.log(1 + best)) + (0.2 if proper and n >= 3 else 0.0)


def _edges(s: str, i: int):
    d = dictionary()
    out = []
    for j in range(i + 1, min(len(s), i + MAX_LEN) + 1):
        ids = d.head.get(s[i:j])
        if ids and not (j < len(s) and s[j] in _DAY and s[j - 2:j] in ("星期", "礼拜")):
            out.append((j, _cost(ids, j - i)))     # a word never ends inside a day name (上个|星期六, not 上个星期|六)
    j = i
    while j < len(s) and s[j] in _NUMERALS:
        j += 1
    if j - i >= 2 and any(ch in "十百千万亿" for ch in s[i:j]):
        out.append((j, 0.7))                  # a number written out (四十五, 一百二十) is one word
    return out


_NUMERALS = set("零〇一二三四五六七八九十百千万亿两")
_DAY = set("一二三四五六日天")
_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "两": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_UNIT = {"十": 10, "百": 100, "千": 1000, "万": 10_000, "亿": 100_000_000}


def number_value(w: str) -> int | None:
    """四十五 -> 45, 一百零二 -> 102, 两千 -> 2000; None if ``w`` is not a written-out number."""
    if len(w) < 2 or any(ch not in _NUMERALS for ch in w) or not any(ch in _UNIT for ch in w):
        return None
    total, section, digit = 0, 0, 0
    for ch in w:
        if ch in _DIGIT:
            digit = _DIGIT[ch]
        elif _UNIT[ch] >= 10_000:
            section = (section + digit) * _UNIT[ch]
            total, section, digit = total + section, 0, 0
        else:
            section += (digit or 1) * _UNIT[ch]
            digit = 0
    return total + section + digit


def _unknown(s: str, i: int):
    return cjk.fallback_piece(s, i), 2.0


def segment(text: str) -> list[dict]:
    return cjk.segment(text, _edges, _unknown, norm_word)


# ---------------------------------------------------------------------------
# lookup and search
# ---------------------------------------------------------------------------
_REGISTER = re.compile(r"\((?:literary|classical|archaic|old|dialect|slang|internet slang|onom\.|honorific|polite|formal|"
                       r"[\w ]*dialect)\)|dialect\)|slang\)", re.I)
_VARIANT = re.compile(r"variant of ([^\[|;,]+)(?:\|([^\[;,]+))?(?:\[([^\]]+)\])?")


def _sense(i: int) -> dict:
    d = dictionary()
    return {"src": "cedict", "text": d.gloss[i], "read": pinyin_marks(d.pin[i])}


def _follow(i: int) -> list[int]:
    """A 'variant of X[pin]' entry -> X's own entries with that reading (strong ones only)."""
    d = dictionary()
    m = _VARIANT.search(d.gloss[i])
    if not m:
        return []
    pin = (m.group(3) or "").lower()
    out = []
    for head in filter(None, (m.group(1), m.group(2))):
        for j in d.head.get(head.strip(), []):
            if not _weak(j) and (not pin or d.pin[j].lower() == pin) and j not in out:
                out.append(j)
    return out


def _brief(word: str, ids: list[int], how: str = "") -> dict:
    d = dictionary()
    return {"lemma": word, "path": [word], "how": how, "reading": pinyin_marks(d.pin[ids[0]]),
            "senses": [_sense(i) for i in ids[:4]]}


def has_word(w: str) -> bool:
    return w in dictionary().head


def lookup(raw, mine: dict | None = None, around: tuple[str, str] | None = None) -> dict:
    """Look a word up. -> {found, word, lemma, path, how, reading, rom, senses[{src, text, read}], also, weak}."""
    word = norm_word(raw)
    if not word:
        return {"ok": True, "found": False, "word": "", "senses": [], "also": [], "credit": CREDIT}
    mine = mine or {}
    d = dictionary()
    ids = _ranked(word)
    strong = [i for i in ids if not _weak(i)]
    how = ""
    path = [word]
    if ids and not strong:                                   # only variants: follow them to the real entry
        for i in ids:
            for j in _follow(i):
                if j not in strong:
                    strong.append(j)
        if strong:
            how = "variant"
            target = d.simp[strong[0]] if d.simp[strong[0]] != word else d.trad[strong[0]]
            path = [word, target]
    senses = []
    if word in mine:
        senses.append({"src": "mine", "text": mine[word]})
    shown = strong or ids
    senses += [_sense(i) for i in shown[:4]]
    also: list[dict] = []
    if around and (around[0] or around[1]):
        big = cjk.around(word, around[0], around[1], has_word)
        if big:
            also.append(_brief(big, _ranked(big), "compound"))
    for i in shown[4:6]:
        also.append(_brief(word, [i], "reading"))
    if len(word) > 1:
        for ch in dict.fromkeys(word):
            r = _ranked(ch)
            if r:
                also.append(_brief(ch, r, "character"))
    if not ids and number_value(word) is not None:
        senses.append({"src": "number", "text": f"{number_value(word):,} (number)", "read": _number_pinyin(word)})
        shown = []
    out = {"ok": True, "word": word, "found": bool(senses), "also": also[:6], "credit": CREDIT}
    if senses:
        first = shown[0] if shown else None
        other = ""
        if first is not None:
            other = d.trad[first] if d.simp[first] == path[-1] else d.simp[first]
        reading = pinyin_marks(d.pin[first]) if first is not None else senses[-1].get("read", "")
        out.update(lemma=path[-1], path=path, how=how, senses=senses, reading=reading, rom=reading,
                   forms=[other] if other and other != path[-1] else [],
                   weak=bool(ids) and not [i for i in ids if not _weak(i)] and not how and word not in mine)
    else:
        out.update(lemma="", path=[word], how="", senses=[], weak=False, reading="", rom="", forms=[])
    return out


def _number_pinyin(w: str) -> str:
    out = []
    for ch in w:
        r = _ranked(ch)
        out.append(dictionary().pin[r[0]] if r else ch)
    return pinyin_marks(" ".join(out))


def _row(i: int, w: str | None = None) -> dict:
    d = dictionary()
    return {"w": w or d.simp[i], "en": d.gloss[i][:300], "src": "cedict", "read": pinyin_marks(d.pin[i])}


def search(q, direction: str = "from", mine: dict | None = None, limit: int = 40) -> list[dict]:
    """Chinese -> English by characters or pinyin (tone marks, tone numbers or none), English -> Chinese by gloss."""
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
                rows.append({"w": k, "en": v, "src": "mine", "read": romanise(k)})
        scored = []
        for i, gl in enumerate(d.gloss):
            low = gl.lower()
            if ql not in low or _weak(i):
                continue
            senses = [x.strip() for x in re.split(r"[;,] ", re.sub(r"\([^)]*\)", "", low))]
            if ql in senses or f"to {ql}" in senses:
                score = 0 if senses[0] in (ql, f"to {ql}") else 1
            else:
                score = 2 if pat.search(low) else 3
            pr = d.freq[i]
            rare = 0 if pr >= 2000 else 1 if pr >= 200 else 2 if pr >= 20 else 3   # by how common the word is
            if _REGISTER.search(low.split("; ")[0]):
                rare += 2                                                     # literary, dialect, slang: not the everyday word
            scored.append((2 * score + rare, "p" in d.flags[i], len(d.simp[i]) > 2, -pr, len(low), i))
        scored.sort()
        rows += [_row(t[-1]) for t in scored[: limit * 2]]
    elif cjk.kind(q[0]) in ("h", "H", "K"):
        w = norm_word(q)
        for k, v in mine.items():
            if w and k.startswith(w):
                rows.append({"w": k, "en": v, "src": "mine", "read": romanise(k)})
        rows += [_row(i, w) for i in _ranked(w)]
        i = bisect_left(d.keys, w)
        pref = []
        while i < len(d.keys) and d.keys[i].startswith(w) and len(pref) < limit * 4:
            if d.keys[i] != w:
                pref.append(d.keys[i])
            i += 1
        pref.sort(key=lambda k: (len(k), -max(d.freq[j] for j in d.head[k])))
        for k in pref:
            r = _ranked(k)
            rows.append(_row(r[0], k))
    else:
        qn = q.lower()
        plain = _plain(qn)
        if not plain:
            return []
        has_num = bool(re.search(r"[1-5]", qn))
        has_mark = any(unicodedata.category(ch) == "Mn" for ch in unicodedata.normalize("NFD", qn) if ch != "̈")
        want = _numbered_key(qn) if has_num else _marked_key(qn) if has_mark else ""
        idx = d.pinyin_index()

        def tone_ok(i: int) -> bool:
            if has_num:
                return _numbered_key(d.pin[i]) == want
            return not has_mark or _marked_key(pinyin_marks(d.pin[i])) == want
        exact = sorted(idx.get(plain, []), key=lambda i: (_weak(i), "p" in d.flags[i], -d.freq[i], len(d.simp[i]), i))
        rows += [_row(i) for i in exact if tone_ok(i)][: limit]
        if len(rows) < limit:                                 # longer words that start with this pinyin
            keys = d.pinyin_keys
            j = bisect_left(keys, plain)
            more = []
            while j < len(keys) and keys[j].startswith(plain) and len(more) < limit * 6:
                if keys[j] != plain:
                    more += idx[keys[j]]
                j += 1
            more.sort(key=lambda i: (_weak(i), "p" in d.flags[i], len(d.pin[i].split()), -d.freq[i], i))
            rows += [_row(i) for i in more]
    seen: set[tuple[str, str]] = set()
    out = []
    for r in rows:
        key = (r["w"], r.get("read", ""))
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
        if len(out) >= limit:
            break
    return out
