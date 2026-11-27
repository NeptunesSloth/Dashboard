"""Japanese deinflection: a suffix rule table in the style of Yomichan / 10ten Reader, and Hepburn rōmaji.

``deinflect("食べました")`` lists every dictionary form the word could come from —
("食べる", {"v1", "vk"}, ["polite past"]) among them — and the caller keeps those
whose part of speech in JMdict agrees (a v1 verb for a v1 rule). A rule says: a
word ending in ``suffix`` may be ``base`` with the ending changed, if the word
is of a type in ``makes`` (None: any word, only for the outermost ending); the
result is a word of the types ``gives``. Chaining the rules undoes several
endings: 行きたくない -> 行きたい (negative) -> 行く (want to).

Types: v1 (ichidan), v5 (any godan), v5k-s (行く), v5aru (いらっしゃる), vk (来る),
vs-i (する and verbs written with it), vs (a noun that takes する), adj-i,
adj-na, te (a te-form, which ている/てしまう… attach to).
"""
from __future__ import annotations

from functools import lru_cache

F = None                    # "only as the outermost ending"

# godan ending -> (i-stem, a-stem, e-stem, o-stem, te, ta)
GODAN = {"う": ("い", "わ", "え", "お", "って", "った"), "く": ("き", "か", "け", "こ", "いて", "いた"),
         "ぐ": ("ぎ", "が", "げ", "ご", "いで", "いだ"), "す": ("し", "さ", "せ", "そ", "して", "した"),
         "つ": ("ち", "た", "て", "と", "って", "った"), "ぬ": ("に", "な", "ね", "の", "んで", "んだ"),
         "ぶ": ("び", "ば", "べ", "ぼ", "んで", "んだ"), "む": ("み", "ま", "め", "も", "んで", "んだ"),
         "る": ("り", "ら", "れ", "ろ", "って", "った")}

# endings on the masu-stem (食べ, 書き, し, き): (suffix, reason, the type of the word it makes)
MASU = [("ます", "polite", F), ("ました", "polite past", F), ("ません", "polite negative", F),
        ("ませんでした", "polite past negative", F), ("ましょう", "polite volitional (let's)", F), ("まして", "polite te-form", F),
        ("たい", "want to", {"adj-i"}), ("ながら", "while", F), ("なさい", "polite command", F), ("すぎる", "too much", {"v1"}),
        ("やすい", "easy to", {"adj-i"}), ("にくい", "hard to", {"adj-i"}), ("たがる", "wants to (someone else)", {"v5"})]
NAI = [("ない", "negative", {"adj-i"}), ("ず", "negative (written)", F), ("ずに", "without", F), ("ないで", "without / don't", F),
       ("なきゃ", "must (casual)", F), ("なくちゃ", "must (casual)", F)]
TE_TA = [("て", "te-form", {"te"}), ("た", "past", F), ("たら", "if / when (-tara)", F), ("たり", "doing things like (-tari)", F),
         ("ても", "even if", F)]
# endings on a te-form: て + いる …, written with て or で
TE_CHAIN = [("いる", "ongoing (-te iru)", {"v1"}), ("る", "ongoing (-te ru, casual)", {"v1"}), ("しまう", "completely / regrettably", {"v5"}),
            ("おく", "in advance (-te oku)", {"v5"}), ("ある", "has been done (-te aru)", {"v5"}), ("みる", "try (-te miru)", {"v1"}),
            ("ください", "please", F), ("くれる", "for me (-te kureru)", {"v1"}), ("もらう", "have done (-te morau)", {"v5"}),
            ("あげる", "for someone (-te ageru)", {"v1"}), ("いく", "goes on (-te iku)", {"v5"}), ("くる", "comes to (-te kuru)", {"vk"}),
            ("いい", "may (-te ii)", F), ("もいい", "may (-te mo ii)", F)]
ADJ_I = [("く", "adverb (-ku)", F), ("かった", "past", F), ("くない", "negative", {"adj-i"}), ("くて", "te-form", F),
         ("ければ", "if (-kereba)", F), ("さ", "noun (-sa)", F), ("そう", "looks (-sou)", F), ("すぎる", "too", {"v1"}),
         ("かったら", "if / when (-kattara)", F), ("くありません", "polite negative", F), ("くなる", "becomes", {"v5"}),
         ("くありませんでした", "polite past negative", F), ("かろう", "probably", F), ("げ", "seeming (-ge)", F)]

V1 = {"v1", "vk"}            # a kanji 来る inflects like an ichidan verb on paper: 来ます, 来た, 来ない


def _rules() -> list[tuple[str, str, set | None, set, str]]:
    r: list[tuple[str, str, set | None, set, str]] = []
    add = lambda suf, base, makes, gives, why: r.append((suf, base, makes, set(gives), why))   # noqa: E731
    # --- ichidan (食べる) and kanji 来る
    for suf, why, mk in MASU + NAI + TE_TA:
        add(suf, "る", mk, V1, why)
    for suf, why, mk in [("られる", "passive or potential", {"v1"}), ("させる", "causative", {"v1"}), ("れる", "potential (casual)", {"v1"}),
                         ("れば", "if (-ba)", F), ("よう", "volitional (let's)", F), ("ろ", "command", F), ("よ", "command", F),
                         ("させられる", "made to (causative passive)", {"v1"})]:
        add(suf, "る", mk, {"v1"} if suf not in ("られる", "させる", "れば", "よう") else V1, why)
    add("い", "る", F, {"vk"}, "command")                                  # 来い
    # --- godan
    for end, (i, a, e, o, te, ta) in GODAN.items():
        for suf, why, mk in MASU:
            add(i + suf, end, mk, {"v5"}, why)
        for suf, why, mk in NAI:
            add(("わ" if end == "う" else a) + suf, end, mk, {"v5"}, why)
        add(a + "れる", end, {"v1"}, {"v5"}, "passive")
        add(a + "せる", end, {"v1"}, {"v5"}, "causative")
        add(a + "される", end, {"v1"}, {"v5"}, "made to (causative passive)")
        add(e + "る", end, {"v1"}, {"v5"}, "potential (can)")
        add(e + "ば", end, F, {"v5"}, "if (-ba)")
        add(e, end, F, {"v5"}, "command")
        add(o + "う", end, F, {"v5"}, "volitional (let's)")
        for suf, why, mk in TE_TA:
            t = te if suf.startswith("て") else ta
            add(t + suf[1:], end, mk, {"v5"}, why)
    for suf, why, mk in TE_TA:                                              # 行く: 行って, 行った
        add(("って" if suf.startswith("て") else "った") + suf[1:], "く", mk, {"v5k-s"}, why)
    for suf, why, mk in MASU:                                               # いらっしゃる: いらっしゃいます
        add("い" + suf, "る", mk, {"v5aru"}, why)
    add("い", "る", F, {"v5aru"}, "command")
    # --- する (and nouns that take it), くる written in kana
    for stem, verb, kind in (("し", "する", "vs-i"), ("き", "くる", "vk")):
        for suf, why, mk in MASU:
            add(stem + suf, verb, mk, {kind}, why)
        for suf, why, mk in TE_TA:
            add(stem + suf, verb, mk, {kind}, why)
    for suf, why, mk in NAI:
        add("し" + suf, "する", mk, {"vs-i"}, why)
        add("こ" + suf, "くる", mk, {"vk"}, why)
    for suf, base, mk, why in [("すれば", "する", F, "if (-ba)"), ("しろ", "する", F, "command"), ("せよ", "する", F, "command"),
                               ("しよう", "する", F, "volitional (let's)"), ("される", "する", {"v1"}, "passive"),
                               ("させる", "する", {"v1"}, "causative"), ("できる", "する", {"v1"}, "potential (can)"),
                               ("せず", "する", F, "negative (written)"), ("せずに", "する", F, "without")]:
        add(suf, base, mk, {"vs-i"}, why)
    for suf, base, mk, why in [("くれば", "くる", F, "if (-ba)"), ("こい", "くる", F, "command"), ("こよう", "くる", F, "volitional (let's)"),
                               ("こられる", "くる", {"v1"}, "passive or potential"), ("こさせる", "くる", {"v1"}, "causative")]:
        add(suf, base, mk, {"vk"}, why)
    add("する", "", {"vs-i"}, {"vs"}, "suru verb")
    # --- te-form chains (食べている -> 食べて), with で for the voiced te-forms (読んでいる -> 読んで)
    for suf, why, mk in TE_CHAIN:
        add("て" + suf, "て", mk, {"te"}, why)
        add("で" + suf, "で", mk, {"te"}, why)
    for suf, why, mk in [("ちゃう", "completely (casual -chau)", {"v5"}), ("とく", "in advance (casual -toku)", {"v5"})]:
        add(suf, "て", mk, {"te"}, why)
    add("じゃう", "で", {"v5"}, {"te"}, "completely (casual -jau)")
    add("どく", "で", {"v5"}, {"te"}, "in advance (casual -doku)")
    # --- adjectives
    for suf, why, mk in ADJ_I:
        add(suf, "い", mk, {"adj-i"}, why)
    add("な", "", F, {"adj-na"}, "na-adjective + na")
    add("に", "", F, {"adj-na"}, "adverb (-ni)")
    return r


RULES = _rules()
_BY_LAST: dict[str, list] = {}
for _rule in RULES:
    _BY_LAST.setdefault(_rule[0][-1], []).append(_rule)
for _v in _BY_LAST.values():
    _v.sort(key=lambda x: -len(x[0]))

_TE_REASONS = {why for _, why, _ in TE_CHAIN} | {"completely (casual -chau)", "in advance (casual -toku)",
                                                    "completely (casual -jau)", "in advance (casual -doku)"}


@lru_cache(maxsize=65536)
def deinflect(word: str) -> tuple[tuple[str, frozenset | None, tuple[str, ...]], ...]:
    """Every (term, types, reasons) the word may come from; the word itself first (types None: any).
    ``reasons`` are listed from the dictionary form outwards (食べました: ("polite past",))."""
    out: list[tuple[str, frozenset | None, tuple[str, ...]]] = [(word, None, ())]
    seen = {(word, None)}
    i = 0
    while i < len(out) and len(out) < 400:
        term, cur, why = out[i]
        i += 1
        if not term or len(why) >= 6:
            continue
        for suf, base, makes, gives, reason in _BY_LAST.get(term[-1], ()):
            if not term.endswith(suf):
                continue
            if cur is None:
                if makes is not None and why:          # never happens for the raw word; kept for clarity
                    continue
            elif makes is None or not (cur & makes):
                continue
            new = term[: len(term) - len(suf)] + base
            if not new or (new == term):
                continue
            g = frozenset(gives)
            if (new, g) in seen:
                continue
            seen.add((new, g))
            out.append((new, g, (reason, *why)))
    return tuple(out)


def describe(reasons: tuple[str, ...] | list[str]) -> str:
    """Reasons as one phrase: "te-form" is dropped where -te iru and friends say it already."""
    rs = list(reasons)
    keep = [r for k, r in enumerate(rs) if not (r == "te-form" and k + 1 < len(rs) and rs[k + 1] in _TE_REASONS)]
    return ", ".join(keep)


def _fits(t: str, p: str) -> bool:
    return (p == t or (t == "v5" and p.startswith("v5")) or (t == "v1" and p.startswith("v1")) or (t == "vs-i" and p == "vs-s")
            or (t == "vs" and p == "vs-c") or (t == "adj-i" and p == "adj-ix"))


def pos_ok(types: frozenset | None, pos: tuple[str, ...]) -> bool:
    """Does an entry with these JMdict part-of-speech codes fit a rule's result types? (None: any entry.)"""
    return types is None or any(_fits(t, p) for t in types for p in pos)


# ---------------------------------------------------------------------------
# rōmaji
# ---------------------------------------------------------------------------
_KANA = dict(zip(
    "あいうえおかきくけこさしすせそたちつてとなにぬねのはひふへほまみむめもやゆよらりるれろわゐゑをんがぎぐげござじずぜぞだぢづでどばびぶべぼぱぴぷぺぽゔぁぃぅぇぉゎ",
    "a i u e o ka ki ku ke ko sa shi su se so ta chi tsu te to na ni nu ne no ha hi fu he ho ma mi mu me mo ya yu yo ra ri ru re ro "
    "wa i e o n ga gi gu ge go za ji zu ze zo da ji zu de do ba bi bu be bo pa pi pu pe po vu a i u e o wa".split()))
_SMALL_Y = {"ゃ": "a", "ゅ": "u", "ょ": "o"}
_PAIRS = {"ふぁ": "fa", "ふぃ": "fi", "ふぇ": "fe", "ふぉ": "fo", "てぃ": "ti", "でぃ": "di", "とぅ": "tu", "どぅ": "du", "でゅ": "dyu",
          "うぃ": "wi", "うぇ": "we", "うぉ": "wo", "ゔぁ": "va", "ゔぃ": "vi", "ゔぇ": "ve", "ゔぉ": "vo", "しぇ": "she", "じぇ": "je",
          "ちぇ": "che", "つぁ": "tsa", "つぃ": "tsi", "つぇ": "tse", "つぉ": "tso", "いぇ": "ye", "くぁ": "kwa", "ぐぁ": "gwa",
          "ふゅ": "fyu", "てゅ": "tyu"}
_MACRON = {"a": "ā", "i": "ī", "u": "ū", "e": "ē", "o": "ō"}


def to_hiragana(s: str) -> str:
    return "".join(chr(ord(ch) - 0x60) if 0x30A1 <= ord(ch) <= 0x30F6 else ch for ch in s)


def to_katakana(s: str) -> str:
    return "".join(chr(ord(ch) + 0x60) if 0x3041 <= ord(ch) <= 0x3096 else ch for ch in s)


def _syllables(kana: str) -> list[str]:
    """Kana as rōmaji syllables; っ as "Q", ー as "-" (resolved by the caller); unknown characters kept."""
    h = to_hiragana(kana)
    out, i = [], 0
    while i < len(h):
        two = h[i:i + 2]
        if two in _PAIRS:
            out.append(_PAIRS[two])
            i += 2
            continue
        if len(two) == 2 and two[1] in _SMALL_Y and two[0] in _KANA and _KANA[two[0]].endswith("i") and two[0] != "い":
            base = _KANA[two[0]]
            out.append((base[:-1] if base[:-1] in ("sh", "ch", "j") else base[:-1] + "y") + _SMALL_Y[two[1]])
            i += 2
            continue
        ch = h[i]
        out.append("Q" if ch == "っ" else "-" if ch == "ー" else _KANA.get(ch) or {"ゃ": "ya", "ゅ": "yu", "ょ": "yo"}.get(ch, ch))
        i += 1
    return out


def romaji(kana: str, macrons: bool = True, keep_final_ou: bool = False) -> str:
    """Hepburn rōmaji for a kana reading. ``macrons``: long vowels as ō ū ā ē (がっこう gakkō, コーヒー kōhī);
    without: as the kana are written, the way this app's Japanese course types them (gakkou, koohii).
    ``keep_final_ou``: a verb's last う stays (思う omou, not omō)."""
    syl = _syllables(kana)
    out: list[str] = []
    for k, s in enumerate(syl):
        nxt = syl[k + 1] if k + 1 < len(syl) else ""
        if s == "Q":
            if nxt and nxt[0] not in "aeiouQ-n'":
                out.append("t" if nxt.startswith("ch") else nxt[0])
            continue
        if s == "-":
            prev = "".join(out)
            v = next((ch for ch in reversed(prev) if ch in "aeiou"), "")
            if v and macrons and prev.endswith(v):
                out[-1] = out[-1][:-1] + _MACRON[v]
            elif v:
                out.append(v)
            continue
        if s == "n" and nxt and (nxt[0] in "aeiouy"):
            out.append("n'")
            continue
        out.append(s)
    text = "".join(out)
    if not macrons:
        return text
    tail = ""
    if keep_final_ou and text.endswith(("ou", "uu")):
        text, tail = text[:-2], text[-2:]
    for a, b in (("ou", "ō"), ("oo", "ō"), ("uu", "ū"), ("aa", "ā"), ("ee", "ē")):
        text = text.replace(a, b)
    return text + tail


_ROMA = {}
for _k, _v in _KANA.items():
    if _k not in "ぁぃぅぇぉゎゐゑ":
        _ROMA.setdefault(_v, _k)
_ROMA.update({"si": "し", "ti": "ち", "tu": "つ", "hu": "ふ", "zi": "じ", "di": "ぢ", "du": "づ", "wo": "を", "o": "お", "e": "え",
              "i": "い", "n'": "ん", "la": "ぁ", "li": "ぃ", "lu": "ぅ", "le": "ぇ", "lo": "ぉ", "xa": "ぁ", "xi": "ぃ",
              "xu": "ぅ", "xe": "ぇ", "xo": "ぉ", "ltu": "っ", "xtu": "っ", "-": "ー", "ji": "じ", "zu": "ず"})
_ROMA.update({v: k for k, v in _PAIRS.items()})
for _c, _base in (("k", "き"), ("g", "ぎ"), ("n", "に"), ("h", "ひ"), ("b", "び"), ("p", "ぴ"), ("m", "み"), ("r", "り")):
    for _vv, _sm in (("a", "ゃ"), ("u", "ゅ"), ("o", "ょ")):
        _ROMA[_c + "y" + _vv] = _base + _sm
for _pre, _base in (("sh", "し"), ("sy", "し"), ("ch", "ち"), ("ty", "ち"), ("cy", "ち"), ("j", "じ"), ("jy", "じ"), ("zy", "じ")):
    for _vv, _sm in (("a", "ゃ"), ("u", "ゅ"), ("o", "ょ")):
        _ROMA[_pre + _vv] = _base + _sm
    _ROMA.setdefault(_pre + "e", _base + "ぇ")
_ROMA_MAX = max(len(k) for k in _ROMA)
_UNMACRON = {"ā": "aa", "ī": "ii", "ū": "uu", "ē": "ee", "ô": "ou", "â": "aa", "û": "uu", "ê": "ee", "î": "ii"}


def kana_from_romaji(q: str) -> list[str]:
    """Typed rōmaji (Hepburn, with or without macrons; kunrei; the way a keyboard types it) as hiragana.
    Returns the readings it could stand for ("tōkyō" -> とうきょう and とおきょお), [] if it is not rōmaji."""
    q = q.lower().strip().replace(" ", "").replace("’", "'")
    variants = [q]
    if "ō" in q:
        variants = [q.replace("ō", "ou"), q.replace("ō", "oo")]
    out = []
    for v in variants:
        for a, b in _UNMACRON.items():
            v = v.replace(a, b)
        kana = _romaji_to_kana(v)
        if kana and kana not in out:
            out.append(kana)
    return out


def _romaji_to_kana(s: str) -> str:
    out, i = [], 0
    while i < len(s):
        ch = s[i]
        if ch == "n" and s[i + 1:i + 2] == "n":                    # "nn": ん, and the second n starts "ni" if a vowel follows
            out.append("ん")
            i += 1 if s[i + 2:i + 3] and s[i + 2] in "aeiouy" else 2
            continue
        if ch == "n" and (i + 1 == len(s) or s[i + 1] not in "aeiouy'"):
            out.append("ん")
            i += 1
            continue
        if ch.isalpha() and i + 1 < len(s) and s[i + 1] == ch and ch not in "aeioun":
            out.append("っ")
            i += 1
            continue
        if ch == "t" and s[i + 1:i + 3] == "ch":
            out.append("っ")
            i += 1
            continue
        for L in range(min(_ROMA_MAX, len(s) - i), 0, -1):
            piece = s[i:i + L]
            if piece in _ROMA:
                out.append(_ROMA[piece])
                i += L
                break
        else:
            return ""
    return "".join(out)
