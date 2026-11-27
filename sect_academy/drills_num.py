"""Number drills made on the spot, in all five languages: numbers both ways, clock times, dates, prices, and
counters (Chinese measure words, Japanese counters, Korean native numbers with their counters).

Every spelling is built here from the language's rules, each one written out below with its exceptions:
Spanish un/una/uno and cien/ciento, French 70–99, et un and the plural s of vingts/cents, Chinese 零 and 两,
Japanese sound changes (さんびゃく, ろっぴゃく, はっぴゃく, いっぽん), Korean Sino and native numbers and the
native contractions before a counter (한, 두, 세, 네, 스무). A question is {q, a (accepted, best first), show, why,
grade ("typed": the course's typed-answer rules; "digits": the number, any grouping), lang}.
"""
from __future__ import annotations

import itertools
import random

# ---------------------------------------------------------------------------
# Spanish
# ---------------------------------------------------------------------------
ES_UNITS = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis diecisiete "
            "dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro veinticinco veintiséis veintisiete "
            "veintiocho veintinueve").split()
ES_TENS = {30: "treinta", 40: "cuarenta", 50: "cincuenta", 60: "sesenta", 70: "setenta", 80: "ochenta", 90: "noventa"}
ES_HUND = {2: "doscientos", 3: "trescientos", 4: "cuatrocientos", 5: "quinientos", 6: "seiscientos", 7: "setecientos",
           8: "ochocientos", 9: "novecientos"}
ES_MONTHS = "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split()


def _es_one(word: str, g: str) -> str:
    """uno as a number, un before a masculine noun (veintiún), una before a feminine one (veintiuna)."""
    if g == "m":
        return {"uno": "un", "veintiuno": "veintiún"}[word]
    if g == "f":
        return word[:-1] + "a"
    return word


def es_words(n: int, g: str = "n") -> str:
    """Spanish for 0 <= n < 10**9. ``g``: "n" counting (uno, veintiuno), "m" before a masculine noun (un,
    veintiún, doscientos), "f" before a feminine noun (una, veintiuna, doscientas)."""
    if n < 0 or n >= 10 ** 9:
        raise ValueError(n)
    if n >= 10 ** 6:
        m, rest = divmod(n, 10 ** 6)
        head = "un millón" if m == 1 else es_words(m, "m") + " millones"
        return head + (" " + es_words(rest, g) if rest else "")
    if n >= 1000:
        t, rest = divmod(n, 1000)
        head = "mil" if t == 1 else es_words(t, "m" if g != "f" else "f") + " mil"
        return head + (" " + es_words(rest, g) if rest else "")
    if n >= 100:
        h, rest = divmod(n, 100)
        if n == 100:
            return "cien"
        head = "ciento" if h == 1 else ES_HUND[h]
        if g == "f" and h > 1:
            head = head[:-2] + "as"
        return head + (" " + es_words(rest, g) if rest else "")
    if n < 30:
        w = ES_UNITS[n]
        return _es_one(w, g) if n % 10 == 1 and n != 11 else w
    t, u = divmod(n, 10)
    return ES_TENS[t * 10] + (" y " + (_es_one("uno", g) if u == 1 else ES_UNITS[u]) if u else "")


def _es_why(n: int, g: str = "n") -> str:
    notes = []
    if n % 100 in range(16, 30) or n in range(16, 30):
        notes.append("16 to 29 are one word (dieciséis, veintidós, veintitrés, veintiséis carry an accent).")
    if n % 100 > 30 and n % 10:
        notes.append("From 31 the tens and units are joined by y (treinta y uno).")
    if n == 100 or n % 100000 == 100 or (n % 1000 == 100):
        notes.append("100 on its own is cien; 101 to 199 use ciento.")
    elif (n // 100) % 10 in (5, 7, 9):
        notes.append("quinientos, setecientos and novecientos are irregular.")
    if 1000 <= n < 2000:
        notes.append("1000 is mil, never *un mil.")
    if n % 10 == 1 and n % 100 != 11 and g != "n":
        notes.append("Before a noun, uno becomes un (masculine) or una (feminine): veintiún euros, veintiuna personas.")
    elif g == "f" and n >= 200:
        notes.append("The hundreds agree with a feminine noun: doscientas.")
    return " ".join(notes) or "Say it as it is read: thousands, hundreds, then tens and units."


def es_time(h: int, m: int) -> tuple[list[str], str]:
    """'son las tres y cuarto' and the other ways to say it, for a 12-hour clock time (m a multiple of 5)."""
    def hour(x: int) -> tuple[str, str]:
        x = (x - 1) % 12 + 1
        return ("es la", "una") if x == 1 else ("son las", es_words(x))
    out = []
    if m == 0:
        v, w = hour(h)
        out = [f"{v} {w}", f"{v} {w} en punto"]
        why = "Es la una, son las dos …: the hour is feminine (la hora)."
    elif m <= 30:
        v, w = hour(h)
        named = {15: "cuarto", 30: "media"}.get(m)
        out = ([f"{v} {w} y {named}"] if named else []) + [f"{v} {w} y {es_words(m)}"]
        why = "Up to the half hour: the hour + y + the minutes (y cuarto, y media)."
    else:
        v, w = hour(h + 1)
        v0, w0 = hour(h)
        named = "cuarto" if m == 45 else es_words(60 - m)
        out = [f"{v} {w} menos {named}", f"{v0} {w0} y {es_words(m)}"]
        why = "After the half hour Spanish counts back from the next hour: menos cuarto, menos veinte."
    return out, why


def es_date(d: int, mo: int) -> tuple[list[str], str]:
    month = ES_MONTHS[mo - 1]
    days = ["uno", "primero"] if d == 1 else [es_words(d)]
    if mo == 9:
        alts = [f"el {x} de {mm}" for x in days for mm in ("septiembre", "setiembre")]
    else:
        alts = [f"el {x} de {month}" for x in days]
    return alts, "el + the number + de + the month (no capital letter). The 1st: el uno or el primero."


# ---------------------------------------------------------------------------
# French
# ---------------------------------------------------------------------------
FR_UNITS = "zéro un deux trois quatre cinq six sept huit neuf dix onze douze treize quatorze quinze seize".split()
FR_TENS = {2: "vingt", 3: "trente", 4: "quarante", 5: "cinquante", 6: "soixante"}
FR_MONTHS = "janvier février mars avril mai juin juillet août septembre octobre novembre décembre".split()


def _fr_below100(n: int, fem: bool, last: bool) -> str:
    un = "une" if fem else "un"
    if n < 17:
        return un if n == 1 else FR_UNITS[n]
    if n < 20:
        return "dix-" + FR_UNITS[n - 10]
    if n < 70:
        t, u = divmod(n, 10)
        return FR_TENS[t] + ("" if u == 0 else f" et {un}" if u == 1 else "-" + FR_UNITS[u])
    if n < 80:
        return "soixante et onze" if n == 71 else "soixante-" + _fr_below100(n - 60, fem, last)
    if n == 80:
        return "quatre-vingts" if last else "quatre-vingt"
    return "quatre-vingt-" + _fr_below100(n - 80, fem, last)


def _fr_below1000(n: int, fem: bool, last: bool) -> str:
    h, r = divmod(n, 100)
    if not h:
        return _fr_below100(r, fem, last)
    head = "cent" if h == 1 else FR_UNITS[h] + " cent" + ("s" if not r and last else "")
    return head + (" " + _fr_below100(r, fem, last) if r else "")


def fr_words(n: int, fem: bool = False) -> str:
    """French for 0 <= n < 10**6, traditional spelling (the 1990 spelling, all hyphens, grades the same)."""
    if n < 0 or n >= 10 ** 6:
        raise ValueError(n)
    t, r = divmod(n, 1000)
    if not t:
        return _fr_below1000(r, fem, True)
    head = "mille" if t == 1 else _fr_below1000(t, False, False) + " mille"
    return head + (" " + _fr_below1000(r, fem, True) if r else "")


def fr_reform(words: str) -> str:
    """The 1990 spelling: every part joined by hyphens (vingt-et-un, deux-cents, mille-neuf-cent-quatre-vingt-quatre)."""
    return words.replace(" ", "-")


def _fr_why(n: int, fem: bool = False) -> str:
    notes = []
    r = n % 100
    if 70 <= r < 80:
        notes.append("70 to 79 are soixante + 10 to 19 (soixante-dix, soixante et onze, soixante-douze).")
    elif 80 <= r < 100:
        notes.append("80 is quatre-vingts (four twenties); 81 to 99 drop the s and add 1 to 19 (quatre-vingt-un, quatre-vingt-dix-sept).")
    if r in (21, 31, 41, 51, 61, 71):
        notes.append(f"21 to 71 join the one with et ({'vingt et une' if fem else 'vingt et un'}); 81 and 91 do not.")
    if n % 100 == 0 and (n // 100) % 10 > 1 and n < 1000:
        notes.append("cent takes an s when multiplied and last (deux cents), not when a number follows (deux cent un).")
    if n >= 1000:
        notes.append("mille never takes an s.")
    if fem and n % 10 == 1 and r != 11:
        notes.append("un agrees with a feminine noun: une.")
    notes.append("The 1990 spelling, with hyphens everywhere, is right too.")
    return " ".join(notes)


def fr_time(h: int, m: int) -> tuple[list[str], str]:
    def hour(x: int) -> list[str]:
        x = (x - 1) % 12 + 1
        if x == 12:
            return ["douze heures", "midi", "minuit"]
        return ["une heure" if x == 1 else f"{fr_words(x)} heures"]
    if m == 0:
        out = [f"il est {w}" for w in hour(h)]
        why = "il est + the hour + heure(s)."
    elif m <= 30:
        named = {15: ["et quart", "quinze"], 30: ["et demie", "trente"]}.get(m, [fr_words(m)])
        out = [f"il est {w} {x}" for w in hour(h) for x in named]
        out += [f"il est {w} et demi" for w in hour(h)[1:] if m == 30]      # midi et demi
        why = "il est trois heures dix; a quarter past is et quart, half past et demie."
    else:
        nxt = hour(h + 1)
        named = ["moins le quart", "moins quart"] if m == 45 else [f"moins {fr_words(60 - m)}"]
        out = [f"il est {w} {x}" for w in nxt for x in named] + [f"il est {w} {fr_words(m)}" for w in hour(h)]
        why = "After the half hour, French counts back from the next hour: moins le quart, moins vingt."
    return out, why


def fr_date(d: int, mo: int) -> tuple[list[str], str]:
    day = "premier" if d == 1 else fr_words(d)
    return [f"le {day} {FR_MONTHS[mo - 1]}"], "le + the number + the month (no capital, no de). The 1st is le premier."


# ---------------------------------------------------------------------------
# Chinese
# ---------------------------------------------------------------------------
ZH_DIG = "零一二三四五六七八九"
ZH_PY = {"零": "líng", "一": "yī", "二": "èr", "两": "liǎng", "三": "sān", "四": "sì", "五": "wǔ", "六": "liù", "七": "qī",
         "八": "bā", "九": "jiǔ", "十": "shí", "百": "bǎi", "千": "qiān", "万": "wàn", "点": "diǎn", "刻": "kè", "半": "bàn",
         "分": "fēn", "钟": "zhōng", "差": "chà", "月": "yuè", "号": "hào", "日": "rì", "块": "kuài", "钱": "qián", "元": "yuán",
         "毛": "máo", "角": "jiǎo", "个": "gè", "本": "běn", "张": "zhāng", "只": "zhī", "杯": "bēi"}
ZH_TONE = {"yī": 1, "èr": 4, "liǎng": 3, "sān": 1, "sì": 4, "wǔ": 3, "liù": 4, "qī": 1, "bā": 1, "jiǔ": 3, "shí": 2, "bǎi": 3,
           "qiān": 1, "wàn": 4, "gè": 4, "ge": 5, "běn": 3, "zhāng": 1, "zhī": 1, "bēi": 1, "kè": 4, "diǎn": 3, "kuài": 4,
           "yuán": 2}


def _zh_section(s: int, lead: bool) -> str:
    out, zero, started = "", False, False
    for d, unit in zip((s // 1000, s // 100 % 10, s // 10 % 10, s % 10), ("千", "百", "十", "")):
        if not d:
            zero = zero or started
            continue
        if zero:
            out += "零"
            zero = False
        out += unit if (unit == "十" and d == 1 and not started and lead) else ZH_DIG[d] + unit
        started = True
    return out


def zh_words(n: int) -> str:
    """Chinese for 0 <= n < 10**8, written with 二 throughout (see ``zh_variants`` for 两)."""
    if n < 0 or n >= 10 ** 8:
        raise ValueError(n)
    if n == 0:
        return "零"
    hi, lo = divmod(n, 10000)
    if not hi:
        return _zh_section(lo, True)
    out = _zh_section(hi, True) + "万"
    if lo:
        out += ("零" if lo < 1000 else "") + _zh_section(lo, False)
    return out


def zh_variants(hz: str) -> list[str]:
    """两 or 二 before 百, 千, 万: 两千 first (the usual), then 二千; 二百 first, then 两百. 二 before 十, alone or last stays."""
    spots = [i for i, ch in enumerate(hz) if ch == "二" and hz[i + 1:i + 2] in ("百", "千", "万")]
    out = []
    for combo in itertools.product((False, True), repeat=len(spots)):
        s = list(hz)
        for i, two in zip(spots, combo):
            if two:
                s[i] = "两"
        out.append("".join(s))
    lead_liang = hz[:2] in ("二千", "二万")
    out.sort(key=lambda v: (v[:1] != "两") if lead_liang else (v.count("两")))
    return list(dict.fromkeys(out))


def zh_pinyin(hz: str, sandhi: bool = False, py: dict | None = None) -> str:
    """Pinyin, syllable by syllable. ``sandhi``: 一 before a unit or a measure word as it is said (yì bǎi, yí gè)."""
    py = {**ZH_PY, **(py or {})}
    sylls: list[str] = []
    chars = list(hz)
    i = 0
    while i < len(chars):
        ch = chars[i]
        for k in sorted(py, key=len, reverse=True):          # nouns of several characters (苹果)
            if hz.startswith(k, i):
                sylls.append(py[k])
                i += len(k)
                break
        else:
            sylls.append(ch)
            i += 1
    if sandhi:
        for j, s in enumerate(sylls):
            nxt = sylls[j + 1] if j + 1 < len(sylls) else ""
            prev = sylls[j - 1] if j else ""
            if s == "yī" and nxt in ZH_TONE and nxt not in ("shí", "yī", "èr", "sān", "sì", "wǔ", "liù", "qī", "bā", "jiǔ", "líng") \
                    and prev != "shí":
                sylls[j] = "yí" if ZH_TONE[nxt] in (4, 5) else "yì"
    return " ".join(sylls)


def zh_accept(hanzi: list[str], py: dict | None = None) -> list[str]:
    """Every written form, then their pinyin (as in the dictionary, and with 一's tone change; gè or ge)."""
    out = list(hanzi)
    for hz in hanzi:
        for sandhi in (False, True):
            p = zh_pinyin(hz, sandhi, py)
            out.append(p)
            if "gè" in p:
                out.append(p.replace("gè", "ge"))
    return list(dict.fromkeys(out))


def _zh_why(n: int) -> str:
    notes = []
    s = str(n)
    if "0" in s.strip("0") or (n >= 10000 and n % 10000 and n % 10000 < 1000):
        notes.append("A gap inside the number is read 零 once (一百零五, 一千零五十); zeros at the end are not read.")
    if 10 <= n < 20:
        notes.append("10 to 19 start with 十 (十五), not 一十.")
    elif n >= 100 and n % 100 // 10 == 1:
        notes.append("After 百 or 千 the ten is 一十 (一百一十).")
    if s[0] == "2" and n >= 100:
        notes.append("Before 百, 千 and 万 two can be 两 (两千 is usual); 二 before 十 and as the last digit.")
    return " ".join(notes) or "Read the digits with their places: 千, 百, 十."


def zh_time(h: int, m: int) -> tuple[list[str], str]:
    hz = "两" if h == 2 else zh_words(h)
    base = hz + "点"
    if m == 0:
        out, why = [base, base + "钟"], "点 is the hour (两点 for two o'clock, never 二点)."
    elif m == 15:
        out, why = [base + "一刻", base + "十五分", base + "十五"], "一刻 is a quarter hour; 十五分 is right too."
    elif m == 30:
        out, why = [base + "半", base + "三十分", base + "三十"], "半 is half past; 三十分 is right too."
    elif m == 45:
        nxt = "两" if h + 1 == 2 else zh_words(h % 12 + 1)
        out = [base + "四十五分", base + "四十五", base + "三刻", "差一刻" + nxt + "点", nxt + "点差一刻"]
        why = "四十五分; 三刻 (three quarters) or 差一刻 (a quarter to) the next hour also work."
    elif m < 10:
        out = [base + "零" + zh_words(m) + "分", base + zh_words(m) + "分", base + "零" + zh_words(m)]
        why = "Minutes under ten are often read with 零: 三点零五分."
    else:
        out, why = [base + zh_words(m) + "分", base + zh_words(m)], "The hour with 点, then the minutes with 分."
    return out, why


def zh_date(d: int, mo: int) -> tuple[list[str], str]:
    m = zh_words(mo) + "月"
    return [m + zh_words(d) + "号", m + zh_words(d) + "日"], "Month, then day: 五月三号 (号 in speech, 日 in writing). 二月 keeps 二."


def zh_price(yuan: int, jiao: int = 0) -> tuple[list[str], str]:
    def amount(n: int) -> list[str]:
        return ["两"] if n == 2 else zh_variants(zh_words(n))
    out = []
    for a in amount(yuan):
        if jiao:
            out += [a + "块" + zh_words(jiao), a + "块" + zh_words(jiao) + "毛", a + "元" + zh_words(jiao) + "角"]
        else:
            out += [a + "块", a + "块钱", a + "元"]
    why = "块 in speech, 元 in writing (毛 and 角 for tenths). Two is 两 before a measure word: 两块."
    return out, why


ZH_COUNTERS = {"个": [("人", "rén", "people"), ("苹果", "píngguǒ", "apples")], "本": [("书", "shū", "books")],
               "张": [("纸", "zhǐ", "sheets of paper"), ("票", "piào", "tickets"), ("桌子", "zhuōzi", "tables")],
               "只": [("猫", "māo", "cats"), ("狗", "gǒu", "dogs"), ("鸟", "niǎo", "birds")],
               "杯": [("水", "shuǐ", "glasses of water"), ("咖啡", "kāfēi", "cups of coffee"), ("茶", "chá", "cups of tea")]}
ZH_COUNTER_WHY = {"个": "个 is the general measure word (people, apples, most things).", "本": "本 counts books and bound volumes.",
                  "张": "张 counts flat things: paper, tickets, tables, beds.", "只": "只 counts most animals (and one of a pair).",
                  "杯": "杯 is a cup or glass of a drink."}


# ---------------------------------------------------------------------------
# Japanese
# ---------------------------------------------------------------------------
JA_ONES = {1: "いち", 2: "に", 3: "さん", 4: "よん", 5: "ご", 6: "ろく", 7: "なな", 8: "はち", 9: "きゅう"}
JA_TENS = {1: "じゅう", 2: "にじゅう", 3: "さんじゅう", 4: "よんじゅう", 5: "ごじゅう", 6: "ろくじゅう", 7: "ななじゅう",
           8: "はちじゅう", 9: "きゅうじゅう"}
JA_HUND = {1: "ひゃく", 2: "にひゃく", 3: "さんびゃく", 4: "よんひゃく", 5: "ごひゃく", 6: "ろっぴゃく", 7: "ななひゃく",
           8: "はっぴゃく", 9: "きゅうひゃく"}
JA_THOU = {1: "せん", 2: "にせん", 3: "さんぜん", 4: "よんせん", 5: "ごせん", 6: "ろくせん", 7: "ななせん", 8: "はっせん",
           9: "きゅうせん"}
JA_KANJI = "〇一二三四五六七八九"


def _ja_section(s: int) -> str:
    th, h, t, o = s // 1000, s // 100 % 10, s // 10 % 10, s % 10
    return "".join([JA_THOU.get(th, ""), JA_HUND.get(h, ""), JA_TENS.get(t, ""), JA_ONES.get(o, "")])


def ja_kana(n: int) -> str:
    """The usual reading of 0 <= n < 10**8 (よん, なな, きゅう; さんびゃく, ろっぴゃく, はっぴゃく, さんぜん, はっせん)."""
    if n < 0 or n >= 10 ** 8:
        raise ValueError(n)
    if n == 0:
        return "ゼロ"
    hi, lo = divmod(n, 10000)
    out = ""
    if hi:
        out = ("いっせん" if hi == 1000 else _ja_section(hi)) + "まん"
        if hi == 1:
            out = "いちまん"
    return out + _ja_section(lo)


def ja_kana_variants(n: int) -> list[str]:
    """The usual reading first, then the others heard: し / しち / く for a last 4 / 7 / 9, しちじゅう, せんまん, れい."""
    base = ja_kana(n)
    out = [base]
    if n == 0:
        return [base, "れい", "ぜろ"]
    if n % 10 in (4, 7, 9):
        alt = {4: ("よん", "し"), 7: ("なな", "しち"), 9: ("きゅう", "く")}[n % 10]
        out.append(base[: -len(alt[0])] + alt[1])
    if n % 100 // 10 == 7:
        out += [v.replace("ななじゅう", "しちじゅう") for v in list(out)]
    if n // 10000 == 1000:
        out += [v.replace("いっせんまん", "せんまん", 1) for v in list(out)]
    return list(dict.fromkeys(out))


def ja_kanji(n: int) -> str:
    """Kanji numerals as written in text: 五百四十二, 千, 一万 (no 一 before 十, 百, 千)."""
    if n == 0:
        return "〇"

    def sec(s: int) -> str:
        out = ""
        for d, u in zip((s // 1000, s // 100 % 10, s // 10 % 10, s % 10), ("千", "百", "十", "")):
            if d:
                out += (u if d == 1 and u else JA_KANJI[d] + u)
        return out
    hi, lo = divmod(n, 10000)
    low = sec(lo)
    if hi and low.startswith("千"):
        low = "一" + low                       # 一万一千: after 万 the thousand is written 一千
    return ((sec(hi) if hi != 1 else "一") + "万" if hi else "") + low


def ja_roms(kanas: list[str]) -> list[str]:
    from .lexicon.ja_rules import romaji
    return list(dict.fromkeys(r for k in kanas for r in (romaji(k, macrons=False), romaji(k))))


def _ja_why(n: int) -> str:
    notes = []
    s = f"{n:08d}"
    if s[-3] in "368" or s[-4] in "38" or (n >= 10000 and s[-7] in "38"):
        notes.append("Sound changes: さんびゃく, ろっぴゃく, はっぴゃく; さんぜん, はっせん.")
    if n % 10 in (4, 7, 9):
        notes.append("4, 7 and 9 are usually よん, なな, きゅう (し, しち, く are heard too).")
    if 1000 <= n % 10000 < 2000 or n == 1000:
        notes.append("1000 is せん, not いっせん; 10,000 is いちまん.")
    if n >= 10000:
        notes.append("Japanese groups by 万 (10,000): 30,000 is さんまん.")
    return " ".join(notes) or "Read it place by place: せん, ひゃく, じゅう."


JA_HOURS = {1: "いちじ", 2: "にじ", 3: "さんじ", 4: "よじ", 5: "ごじ", 6: "ろくじ", 7: "しちじ", 8: "はちじ", 9: "くじ",
            10: "じゅうじ", 11: "じゅういちじ", 12: "じゅうにじ"}
JA_MIN_ONES = {1: ["いっぷん"], 2: ["にふん"], 3: ["さんぷん"], 4: ["よんぷん"], 5: ["ごふん"], 6: ["ろっぷん"], 7: ["ななふん"],
               8: ["はっぷん", "はちふん"], 9: ["きゅうふん"]}
JA_MIN_TENS = {1: ["じゅっぷん", "じっぷん"], 2: ["にじゅっぷん", "にじっぷん"], 3: ["さんじゅっぷん", "さんじっぷん"],
               4: ["よんじゅっぷん", "よんじっぷん"], 5: ["ごじゅっぷん", "ごじっぷん"]}


def ja_minutes(m: int) -> list[str]:
    t, o = divmod(m, 10)
    if not o:
        return JA_MIN_TENS[t]
    return [JA_TENS.get(t, "") + x for x in JA_MIN_ONES[o]]


def ja_time(h: int, m: int) -> tuple[list[str], list[str], str]:
    """(kana readings, written forms, why) for h:mm."""
    hours = [JA_HOURS[h]] + (["ななじ"] if h == 7 else [])
    if m == 0:
        return hours, [ja_kanji(h) + "時"], "時 (じ): よじ, しちじ, くじ for 4, 7 and 9 o'clock."
    mins = (["はん"] if m == 30 else []) + ja_minutes(m)
    kana = [a + b for a in hours for b in mins]
    written = [ja_kanji(h) + "時" + ("半" if m == 30 else ja_kanji(m) + "分")] + ([ja_kanji(h) + "時" + ja_kanji(m) + "分"] if m == 30 else [])
    why = "分 is ふん or ぷん: いっぷん, さんぷん, ろっぷん, はっぷん, じゅっぷん; ごふん, きゅうふん." + (" Half past is 半 (はん)." if m == 30 else "")
    return kana, written, why


JA_MONTHS = {1: "いちがつ", 2: "にがつ", 3: "さんがつ", 4: "しがつ", 5: "ごがつ", 6: "ろくがつ", 7: "しちがつ", 8: "はちがつ",
             9: "くがつ", 10: "じゅうがつ", 11: "じゅういちがつ", 12: "じゅうにがつ"}
JA_DAYS = {1: "ついたち", 2: "ふつか", 3: "みっか", 4: "よっか", 5: "いつか", 6: "むいか", 7: "なのか", 8: "ようか", 9: "ここのか",
           10: "とおか", 14: "じゅうよっか", 20: "はつか", 24: "にじゅうよっか", 17: "じゅうしちにち", 19: "じゅうくにち",
           27: "にじゅうしちにち", 29: "にじゅうくにち"}


def ja_day(d: int) -> str:
    return JA_DAYS.get(d) or ja_kana(d) + "にち"


def ja_date(d: int, mo: int) -> tuple[list[str], list[str], str]:
    kana = [JA_MONTHS[mo] + ja_day(d)]
    why = "Months: しがつ, しちがつ, くがつ. Days 1 to 10, 14, 20 and 24 have their own words (ついたち, ふつか, みっか … はつか)."
    return kana, [ja_kanji(mo) + "月" + ja_kanji(d) + "日", f"{mo}月{d}日"], why


def ja_price(n: int) -> tuple[list[str], list[str], str]:
    def yen(k: str) -> str:
        return (k[:-2] + "よ" if k.endswith("よん") else k) + "えん"
    variants = ja_kana_variants(n)
    kana = [yen(variants[0])] + [yen(k) for k in variants[1:] if not k.endswith(("し", "く"))]
    if n % 10 == 7:
        kana.append(ja_kana(n)[:-2] + "しちえん")
    why = "円 is えん; a final 4 is よ (よえん, じゅうよえん)." if n % 10 == 4 else "円 is えん, after the number read as usual."
    return list(dict.fromkeys(kana)), [ja_kanji(n) + "円", f"{n:,}円", f"{n}円"], why


JA_COUNTERS = {
    "本": (["いっぽん", "にほん", "さんぼん", "よんほん", "ごほん", "ろっぽん", "ななほん", "はっぽん", "きゅうほん", "じゅっぽん"],
          {8: ["はちほん"], 10: ["じっぽん"]}, [("鉛筆", "pencils"), ("傘", "umbrellas"), ("ペン", "pens")],
          "本 counts long thin things: いっぽん, さんぼん, ろっぽん, はっぽん, じゅっぽん."),
    "枚": (["いちまい", "にまい", "さんまい", "よんまい", "ごまい", "ろくまい", "ななまい", "はちまい", "きゅうまい", "じゅうまい"],
          {}, [("紙", "sheets of paper"), ("切手", "stamps"), ("シャツ", "shirts")], "枚 counts flat things and has no sound changes."),
    "人": (["ひとり", "ふたり", "さんにん", "よにん", "ごにん", "ろくにん", "しちにん", "はちにん", "きゅうにん", "じゅうにん"],
          {7: ["ななにん"], 9: ["くにん"]}, [("学生", "students"), ("人", "people")], "人: ひとり, ふたり, then さんにん; 4 is よにん."),
    "匹": (["いっぴき", "にひき", "さんびき", "よんひき", "ごひき", "ろっぴき", "ななひき", "はっぴき", "きゅうひき", "じゅっぴき"],
          {8: ["はちひき"], 10: ["じっぴき"]}, [("猫", "cats"), ("犬", "dogs"), ("魚", "fish")],
          "匹 counts small animals: いっぴき, さんびき, ろっぴき, はっぴき, じゅっぴき."),
    "個": (["いっこ", "にこ", "さんこ", "よんこ", "ごこ", "ろっこ", "ななこ", "はっこ", "きゅうこ", "じゅっこ"],
          {8: ["はちこ"], 10: ["じっこ"]}, [("りんご", "apples"), ("卵", "eggs")], "個 counts small things: いっこ, ろっこ, はっこ, じゅっこ."),
}


# ---------------------------------------------------------------------------
# Korean
# ---------------------------------------------------------------------------
KO_SINO = "영일이삼사오육칠팔구"
KO_NATIVE_ONES = {1: "하나", 2: "둘", 3: "셋", 4: "넷", 5: "다섯", 6: "여섯", 7: "일곱", 8: "여덟", 9: "아홉"}
KO_NATIVE_TENS = {1: "열", 2: "스물", 3: "서른", 4: "마흔", 5: "쉰", 6: "예순", 7: "일흔", 8: "여든", 9: "아흔"}
KO_SHORT = {"하나": "한", "둘": "두", "셋": "세", "넷": "네"}
KO_MONTHS = {1: "일월", 2: "이월", 3: "삼월", 4: "사월", 5: "오월", 6: "유월", 7: "칠월", 8: "팔월", 9: "구월", 10: "시월",
             11: "십일월", 12: "십이월"}


def ko_sino(n: int) -> str:
    """Sino-Korean for 0 <= n < 10**8 (백, 천, 만 without 일; groups of 만 spaced: 만 오천)."""
    if n < 0 or n >= 10 ** 8:
        raise ValueError(n)
    if n == 0:
        return "영"

    def sec(s: int) -> str:
        out = ""
        for d, u in zip((s // 1000, s // 100 % 10, s // 10 % 10, s % 10), ("천", "백", "십", "")):
            if d:
                out += u if d == 1 and u else KO_SINO[d] + u
        return out
    hi, lo = divmod(n, 10000)
    parts = []
    if hi:
        parts.append(("" if hi == 1 else sec(hi)) + "만")
    if lo:
        parts.append(sec(lo))
    return " ".join(parts)


def ko_native(n: int, before_counter: bool = False) -> str:
    """Native Korean 1–99; before a counter 1–4 shorten (한, 두, 세, 네) and 20 is 스무."""
    if not 1 <= n <= 99:
        raise ValueError(n)
    t, o = divmod(n, 10)
    ones = KO_NATIVE_ONES.get(o, "")
    if before_counter:
        if n == 20:
            return "스무"
        ones = KO_SHORT.get(ones, ones)
    return KO_NATIVE_TENS.get(t, "") + ones


def ko_accept(forms: list[str]) -> list[str]:
    from .drills_lang import ko_roms
    return list(dict.fromkeys(forms + [r for f in forms for r in ko_roms(f)]))


def ko_time(h: int, m: int) -> tuple[list[str], str]:
    hour = ko_native(h, True) + " 시"
    if m == 0:
        return [hour], "Hours are native numbers (한 시, 두 시, 세 시, 네 시, 열두 시)."
    out = [f"{hour} {ko_sino(m)} 분"] + ([f"{hour} 반"] if m == 30 else [])
    return out, "Hours are native numbers (세 시), minutes Sino-Korean (삼십 분)." + (" 반 is half past." if m == 30 else "")


def ko_date(d: int, mo: int) -> tuple[list[str], str]:
    why = "Months and days are Sino-Korean; June is 유월 and October 시월 (the final consonant drops)."
    return [f"{KO_MONTHS[mo]} {ko_sino(d)} 일", f"{KO_MONTHS[mo]} {ko_sino(d)}일"], why


KO_COUNTERS = {"개": [("사과", "apples"), ("의자", "chairs")], "명": [("학생", "students"), ("사람", "people")],
               "마리": [("고양이", "cats"), ("개", "dogs")], "권": [("책", "books"), ("공책", "notebooks")],
               "잔": [("커피", "cups of coffee"), ("물", "glasses of water")]}
KO_COUNTER_WHY = {"개": "개 counts things.", "명": "명 counts people.", "마리": "마리 counts animals.", "권": "권 counts books.",
                  "잔": "잔 counts cups and glasses."}


# ---------------------------------------------------------------------------
# questions
# ---------------------------------------------------------------------------
KINDS = {
    "es": [("num", "Numbers to words"), ("read", "Words to numbers"), ("agree", "Numbers with nouns (un, una)"), ("time", "Clock times"),
           ("date", "Dates"), ("price", "Prices")],
    "fr": [("num", "Numbers to words"), ("read", "Words to numbers"), ("agree", "Numbers with nouns (un, une)"), ("time", "Clock times"),
           ("date", "Dates"), ("price", "Prices")],
    "zh": [("num", "Numbers to words"), ("read", "Words to numbers"), ("time", "Clock times"), ("date", "Dates"), ("price", "Prices"),
           ("count", "Measure words (个 本 张 只 杯)")],
    "ja": [("num", "Numbers to readings"), ("read", "Readings to numbers"), ("time", "Clock times"), ("date", "Dates"),
           ("price", "Prices"), ("count", "Counters (本 枚 人 匹 個)")],
    "ko": [("num", "Sino-Korean numbers"), ("native", "Native numbers (하나, 둘 …)"), ("read", "Words to numbers"), ("time", "Clock times"),
           ("date", "Dates"), ("price", "Prices"), ("count", "Counters (개 명 마리 권 잔)")],
}
EDGES = {"es": [1, 15, 16, 21, 22, 30, 31, 100, 101, 115, 200, 500, 555, 700, 900, 999, 1000, 1001, 1984, 2021, 21000, 100000, 1000000],
         "fr": [21, 70, 71, 72, 77, 79, 80, 81, 89, 90, 91, 97, 99, 100, 101, 180, 200, 201, 280, 1000, 1984, 2000, 21000, 80000, 200000],
         "zh": [2, 10, 12, 20, 22, 102, 105, 110, 200, 222, 1005, 1050, 2000, 10005, 10500, 20000, 12345],
         "ja": [4, 7, 9, 14, 300, 600, 800, 1000, 3000, 8000, 10000, 30000, 1600, 680, 1800],
         "ko": [10, 16, 100, 1000, 10000, 15000, 106, 61]}
ES_NOUNS = [("libro", "libros", "m"), ("euro", "euros", "m"), ("año", "años", "m"), ("casa", "casas", "f"),
            ("persona", "personas", "f"), ("mesa", "mesas", "f"), ("semana", "semanas", "f"), ("día", "días", "m")]
FR_NOUNS = [("livre", "livres", False), ("an", "ans", False), ("jour", "jours", False), ("maison", "maisons", True),
            ("personne", "personnes", True), ("page", "pages", True), ("semaine", "semaines", True)]
UI_LANGS = {"es": "Spanish", "fr": "French", "zh": "Chinese", "ja": "Japanese", "ko": "Korean"}


def _number(r: random.Random, lang: str) -> int:
    roll = r.random()
    if roll < 0.25:
        return r.choice(EDGES[lang])
    if roll < 0.45:
        return r.randint(0, 99)
    if roll < 0.7:
        return r.randint(100, 999)
    if roll < 0.9:
        return r.randint(1000, 9999)
    return r.randint(10000, 999999)


def _fmt(n: int, lang: str) -> str:
    """Digits grouped the way the language writes them (1 984 in French, 1.984 in Spanish, 1,984 elsewhere)."""
    if n < 10000 and lang == "es":
        return str(n)
    sep = {"fr": " ", "es": "."}.get(lang, ",")
    return f"{n:,}".replace(",", sep)


def _q(q: str, accepted: list[str], show: str, why: str, lang: str, grade: str = "typed") -> dict:
    return {"q": q, "a": [a for a in dict.fromkeys(accepted) if a], "show": show, "why": why, "grade": grade, "lang": lang}


def _clock(r: random.Random) -> tuple[int, int]:
    return r.randint(1, 12), r.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 15, 30, 45])


def _es(r: random.Random, kind: str) -> dict:
    if kind == "num":
        n = _number(r, "es")
        w = es_words(n)
        return _q(f"Write {_fmt(n, 'es')} in words.", [w], w, _es_why(n), "es")
    if kind == "read":
        n = _number(r, "es")
        return _q(f"Write as a number: {es_words(n)}", [str(n)], _fmt(n, "es"), _es_why(n), "es", "digits")
    if kind == "agree":
        n = r.choice([1, 21, 31, 41, 51, 61, 71, 81, 91, 101, 121, 200, 300, 500, 700, 900, 201, 221, 361, r.randint(2, 999)])
        sing, plur, g = r.choice(ES_NOUNS)
        w = es_words(n, g) + " " + (sing if n == 1 else plur)
        return _q(f"Write in words: {n} {sing if n == 1 else plur}", [w], w, _es_why(n, g), "es")
    if kind == "time":
        h, m = _clock(r)
        out, why = es_time(h, m)
        acc = out + [x.split(" ", 1)[1] for x in out]
        return _q(f"What time is it? {h}:{m:02d}", acc, out[0], why, "es")
    if kind == "date":
        mo = r.randint(1, 12)
        d = r.choice([1, r.randint(2, 28), r.randint(2, 31) if mo not in (2, 4, 6, 9, 11) else 30])
        out, why = es_date(d, mo)
        return _q(f"Say the date: {d}/{mo} (day/month)", out + [x[3:] for x in out], out[0], why, "es")
    e = r.choice([1, 2, 21, 31, 100, 101, 200, 500, r.randint(3, 99), r.randint(102, 999), r.randint(1000, 2000)])
    c = r.choice([0, 0, 0, 50, 25, 99])
    eu = es_words(e, "m") + (" euro" if e == 1 else " euros")
    acc = [eu]
    shown = f"{e},{c:02d} €" if c else f"{e} €"
    if c:
        cw = es_words(c)
        acc = [f"{eu} con {cw}", f"{eu} con {cw} céntimos", f"{eu} {cw}", f"{es_words(e)} con {cw}"]
    return _q(f"Say the price: {shown}", acc, acc[0], "Before euros, uno is un (un euro, veintiún euros); cents follow con."
              + (" " + _es_why(e, "m") if e % 10 == 1 or e >= 100 else ""), "es")


def _fr(r: random.Random, kind: str) -> dict:
    if kind == "num":
        n = _number(r, "fr")
        w = fr_words(n)
        return _q(f"Write {_fmt(n, 'fr')} in words.", [w, fr_reform(w)], w, _fr_why(n), "fr")
    if kind == "read":
        n = _number(r, "fr")
        return _q(f"Write as a number: {fr_words(n)}", [str(n)], _fmt(n, "fr"), _fr_why(n), "fr", "digits")
    if kind == "agree":
        n = r.choice([1, 21, 31, 41, 51, 61, 71, 81, 91, 101, 200, 201, 280, r.randint(2, 999)])
        sing, plur, fem = r.choice(FR_NOUNS)
        w = fr_words(n, fem) + " " + (sing if n == 1 else plur)
        return _q(f"Write in words: {n} {sing if n == 1 else plur}", [w, fr_reform(fr_words(n, fem)) + " " + (sing if n == 1 else plur)], w,
                  _fr_why(n, fem), "fr")
    if kind == "time":
        h, m = _clock(r)
        out, why = fr_time(h, m)
        return _q(f"Quelle heure est-il ? {h}:{m:02d}", out + [x[7:] for x in out], out[0], why, "fr")
    if kind == "date":
        mo = r.randint(1, 12)
        d = r.choice([1, r.randint(2, 28), 21, 31 if mo in (1, 3, 5, 7, 8, 10, 12) else 30])
        out, why = fr_date(d, mo)
        return _q(f"Say the date: {d}/{mo} (day/month)", out + [x[3:] for x in out], out[0], why, "fr")
    e = r.choice([1, 2, 21, 71, 80, 81, 100, 200, 201, r.randint(3, 99), r.randint(102, 999)])
    c = r.choice([0, 0, 0, 50, 20, 99])
    eu = fr_words(e) + (" euro" if e == 1 else " euros")
    shown = f"{e},{c:02d} €" if c else f"{e} €"
    acc = [eu]
    if c:
        cw = fr_words(c)
        acc = [f"{eu} {cw}", f"{eu} et {cw} centimes", f"{eu} {cw} centimes"]
    return _q(f"Say the price: {shown}", acc + [fr_reform(fr_words(e)) + a[len(fr_words(e)):] for a in acc], acc[0],
              "euro takes an s from two; cents follow the euros (trois euros cinquante). " + _fr_why(e), "fr")


def _zh(r: random.Random, kind: str) -> dict:
    if kind in ("num", "read"):
        n = _number(r, "zh")
        hz = zh_variants(zh_words(n))
        if kind == "read":
            return _q(f"Write as a number: {hz[0]} ({zh_pinyin(hz[0])})", [str(n)], f"{n:,}", _zh_why(n), "zh", "digits")
        return _q(f"Write {n:,} in Chinese (characters or pinyin).", zh_accept(hz), f"{hz[0]} ({zh_pinyin(hz[0])})", _zh_why(n), "zh")
    if kind == "time":
        h, m = _clock(r)
        out, why = zh_time(h, m)
        return _q(f"现在几点？ {h}:{m:02d}", zh_accept(out), f"{out[0]} ({zh_pinyin(out[0])})", why, "zh")
    if kind == "date":
        mo, d = r.randint(1, 12), r.randint(1, 31 if r.random() < 0.5 else 28)
        out, why = zh_date(d, mo)
        return _q(f"Say the date: {d}/{mo} (day/month)", zh_accept(out), f"{out[0]} ({zh_pinyin(out[0])})", why, "zh")
    if kind == "price":
        y = r.choice([2, 2, 12, 20, 25, 100, 200, 2000, r.randint(3, 99), r.randint(101, 999)])
        j = r.choice([0, 0, 0, 5])
        out, why = zh_price(y, j)
        shown = f"¥{y}.{j}0" if j else f"¥{y}"
        return _q(f"Say the price: {shown}", zh_accept(out), f"{out[0]} ({zh_pinyin(out[0])})", why, "zh")
    ctr = r.choice(list(ZH_COUNTERS))
    noun, npy, en = r.choice(ZH_COUNTERS[ctr])
    n = r.choice([1, 2, 2, 3, 4, 5, 6, 7, 8, 9, 10])
    num = "两" if n == 2 else zh_words(n)
    out = [num + ctr + noun, num + ctr]
    why = ZH_COUNTER_WHY[ctr] + (" Two before a measure word is 两, never 二." if n == 2 else "")
    return _q(f"In Chinese: {n} × {en} ({noun})", zh_accept(out, {noun: npy}), f"{out[0]} ({zh_pinyin(out[0], True, {noun: npy})})",
              why, "zh")


def _ja(r: random.Random, kind: str) -> dict:
    if kind in ("num", "read"):
        n = _number(r, "ja")
        if r.random() < 0.15:
            n = r.choice([1000, 10000, 100000, 1000000, 10000000, 30000, 80000])
        kana = ja_kana_variants(n)
        if kind == "read":
            return _q(f"Write as a number: {ja_kanji(n)} ({kana[0]})", [str(n)], f"{n:,}", _ja_why(n), "ja", "digits")
        roms = ja_roms(kana)
        return _q(f"Read {n:,} in Japanese (kana or rōmaji).", [ja_kanji(n)] + kana + roms, f"{kana[0]} ({roms[0]})", _ja_why(n), "ja")
    if kind == "time":
        h, m = _clock(r)
        kana, written, why = ja_time(h, m)
        roms = ja_roms(kana)
        return _q(f"今、何時ですか。 {h}:{m:02d} (kana or rōmaji)", written + kana + roms, f"{written[0]} ({kana[0]}, {roms[0]})", why, "ja")
    if kind == "date":
        mo, d = r.randint(1, 12), r.choice([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 14, 20, 24, r.randint(11, 31)])
        if mo == 2 and d > 28:
            d = 28
        kana, written, why = ja_date(d, mo)
        roms = ja_roms(kana)
        return _q(f"Read the date: {mo}月{d}日", written + kana + roms, f"{written[0]} ({kana[0]}, {roms[0]})", why, "ja")
    if kind == "price":
        n = r.choice([4, 14, 300, 600, 800, 3000, 8000, 10000, 1000, r.randint(1, 999) * 10, r.randint(100, 99999)])
        kana, written, why = ja_price(n)
        roms = ja_roms(kana)
        return _q(f"Read the price: {n:,}円", written + kana + roms, f"{kana[0]} ({roms[0]})", why, "ja")
    ctr = r.choice(list(JA_COUNTERS))
    forms, extra, nouns, why = JA_COUNTERS[ctr]
    n = r.randint(1, 10)
    noun, en = r.choice(nouns)
    kana = [forms[n - 1]] + extra.get(n, [])
    roms = ja_roms(kana)
    written = [ja_kanji(n) + ctr, f"{n}{ctr}"]
    return _q(f"Count them: {n} × {en} ({noun}, counter {ctr})", written + kana + roms, f"{n}{ctr} ({kana[0]}, {roms[0]})", why, "ja")


def _ko(r: random.Random, kind: str) -> dict:
    if kind in ("num", "read"):
        n = _number(r, "ko")
        w = ko_sino(n)
        if kind == "read":
            return _q(f"Write as a number: {w}", [str(n)], f"{n:,}", "Sino-Korean: 십, 백, 천, 만 (no 일 before them).", "ko", "digits")
        return _q(f"Write {n:,} in Sino-Korean numbers.", ko_accept([w]), f"{w} ({ko_accept([w])[1]})",
                  "Sino-Korean: 십, 백, 천, 만 with no 일 in front (백, not 일백); Korean groups by 만 (10,000).", "ko")
    if kind == "native":
        n = r.choice([1, 2, 3, 4, 10, 20, 21, 22, 30, 40, 50, 99, r.randint(1, 99), r.randint(1, 99)])
        w = ko_native(n)
        return _q(f"Write {n} in native Korean numbers.", ko_accept([w]), f"{w} ({ko_accept([w])[1]})",
                  "Native numbers: 하나 … 열, 스물, 서른, 마흔, 쉰, 예순, 일흔, 여든, 아흔 (only up to 99).", "ko")
    if kind == "time":
        h, m = _clock(r)
        out, why = ko_time(h, m)
        acc = ko_accept(out)
        return _q(f"지금 몇 시예요? {h}:{m:02d}", acc, f"{out[0]} ({acc[len(out)]})", why, "ko")
    if kind == "date":
        mo, d = r.choice([6, 10, r.randint(1, 12)]), r.randint(1, 30)
        out, why = ko_date(d, mo)
        acc = ko_accept(out)
        return _q(f"Say the date: {mo}월 {d}일", acc, f"{out[0]} ({acc[len(out)]})", why, "ko")
    if kind == "price":
        n = r.choice([1000, 3000, 10000, 15000, 25000, 100000, r.randint(1, 99) * 100, r.randint(1, 999) * 1000])
        w = ko_sino(n) + " 원"
        acc = ko_accept([w])
        return _q(f"Say the price: {n:,}원", acc, f"{w} ({acc[1]})", "Prices are Sino-Korean: 만 원 (not 일만 원), 삼천 원.", "ko")
    ctr = r.choice(list(KO_COUNTERS))
    noun, en = r.choice(KO_COUNTERS[ctr])
    n = r.choice([1, 2, 3, 4, 20, 21, 22, 23, 24, r.randint(5, 30)])
    w = f"{ko_native(n, True)} {ctr}"
    acc = ko_accept([f"{noun} {w}", w])
    why = KO_COUNTER_WHY[ctr] + " Counters take native numbers, shortened: 한, 두, 세, 네, and 스무 for 20."
    return _q(f"Count them: {n} × {en} ({noun}, counter {ctr})", acc, f"{noun} {w} ({acc[2]})", why, "ko")


_MAKERS = {"es": _es, "fr": _fr, "zh": _zh, "ja": _ja, "ko": _ko}


def options(lang: str) -> dict:
    return {"kinds": [{"id": k, "name": n} for k, n in KINDS.get(lang, [])]}


def make(lang: str, r: random.Random, kinds: list[str]):
    if lang not in _MAKERS:
        return None
    chosen = [k for k, _ in KINDS[lang] if k in kinds] or [KINDS[lang][0][0]]
    return lambda: _MAKERS[lang](r, r.choice(chosen))
