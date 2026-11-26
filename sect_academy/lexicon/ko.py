"""Korean -> English lookup (data: ``sect_academy/dict/ko/``; English Wiktionary via kaikki.org, CC BY-SA 4.0).

Korean is written in eojeol: a word with its particles and endings attached, spaces between. ``lookup`` takes
one eojeol back to a dictionary entry the way a learner would:

* **particles** come off the end of a noun (학교에서 -> 학교 + 에서), longest first and up to three stacked
  (친구들에게는), each checked against the batchim it needs (은 after a consonant, 는 after a vowel);
  the copula (이에요, 예요, 입니다 ...) is treated the same way;
* **verb and adjective endings** come off a stem, which is then given its dictionary form in -다: polite,
  formal, past, honorific, future and connective endings (먹었어요 -> 먹다, "past polite"), 하다 verbs
  (공부했습니다 -> 공부하다), contracted vowels (가요, 봐요, 줘요, 해요, 돼요) and the common irregular
  verbs (ㅂ 더워요 -> 덥다, ㄷ 들어요 -> 듣다 or 들다, ㅡ 써요 -> 쓰다, 르 몰라요 -> 모르다, ㅅ 나아요 -> 낫다,
  ㅎ 그래요 -> 그렇다, ㄹ 삽니다 -> 살다);
* every analysis that reaches a real entry is ranked by how much it had to assume; the best is the answer,
  the next ones are listed under "also".

All of this is done on Hangul jamo by Unicode arithmetic (a syllable is 0xAC00 + (initial*21 + vowel)*28 +
final). ``romanise`` gives Revised Romanization with the usual sound changes (liaison, nasalisation,
aspiration, ㄹ assimilation), for headwords the data has no romanisation for and for the tapped word itself.
"""
from __future__ import annotations

import re

from . import generic_norm, kaikki, simple_segment

LANG, NAME, SPEECH = "ko", "Korean", "ko-KR"
CREDIT = "Source: English Wiktionary (CC BY-SA 4.0), Wiktionary contributors, via kaikki.org."

# ---------------------------------------------------------------------------
# jamo
# ---------------------------------------------------------------------------
L_J = "ㄱㄲㄴㄷㄸㄹㅁㅂㅃㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
V_J = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
T_J = ["", "ㄱ", "ㄲ", "ㄳ", "ㄴ", "ㄵ", "ㄶ", "ㄷ", "ㄹ", "ㄺ", "ㄻ", "ㄼ", "ㄽ", "ㄾ", "ㄿ", "ㅀ", "ㅁ", "ㅂ", "ㅄ",
       "ㅅ", "ㅆ", "ㅇ", "ㅈ", "ㅊ", "ㅋ", "ㅌ", "ㅍ", "ㅎ"]
_BASE = 0xAC00


def is_syl(ch: str) -> bool:
    return len(ch) == 1 and 0xAC00 <= ord(ch) <= 0xD7A3


def jamo(ch: str) -> tuple[str, str, str]:
    """A syllable as (initial, vowel, final) compatibility jamo; final is "" when there is none."""
    n = ord(ch) - _BASE
    return L_J[n // 588], V_J[(n % 588) // 28], T_J[n % 28]


def syl(lead: str, vowel: str, final: str = "") -> str:
    return chr(_BASE + (L_J.index(lead) * 21 + V_J.index(vowel)) * 28 + T_J.index(final))


def final(ch: str) -> str:
    return jamo(ch)[2] if is_syl(ch) else ""


def with_final(ch: str, f: str) -> str:
    lead, v, _ = jamo(ch)
    return syl(lead, v, f)


def with_vowel(ch: str, v: str) -> str:
    lead, _, f = jamo(ch)
    return syl(lead, v, f)


def hangul(s: str) -> bool:
    return bool(s) and all(is_syl(c) for c in s)


# ---------------------------------------------------------------------------
# Revised Romanization
# ---------------------------------------------------------------------------
_INI = dict(zip(L_J, ["g", "kk", "n", "d", "tt", "r", "m", "b", "pp", "s", "ss", "", "j", "jj", "ch", "k", "t", "p", "h"]))
_VOW = dict(zip(V_J, ["a", "ae", "ya", "yae", "eo", "e", "yeo", "ye", "o", "wa", "wae", "oe", "yo", "u", "wo", "we", "wi",
                      "yu", "eu", "ui", "i"]))
# a final as it sounds before a pause or a consonant: its representative sound
_REP = {"": "", "ㄱ": "ㄱ", "ㄲ": "ㄱ", "ㄳ": "ㄱ", "ㄺ": "ㄱ", "ㅋ": "ㄱ", "ㄴ": "ㄴ", "ㄵ": "ㄴ", "ㄶ": "ㄴ",
        "ㄷ": "ㄷ", "ㅅ": "ㄷ", "ㅆ": "ㄷ", "ㅈ": "ㄷ", "ㅊ": "ㄷ", "ㅌ": "ㄷ", "ㅎ": "ㄷ", "ㄹ": "ㄹ", "ㄼ": "ㄹ",
        "ㄽ": "ㄹ", "ㄾ": "ㄹ", "ㅀ": "ㄹ", "ㅁ": "ㅁ", "ㄻ": "ㅁ", "ㅂ": "ㅂ", "ㅍ": "ㅂ", "ㅄ": "ㅂ", "ㄿ": "ㅂ", "ㅇ": "ㅇ"}
_FIN = {"": "", "ㄱ": "k", "ㄴ": "n", "ㄷ": "t", "ㄹ": "l", "ㅁ": "m", "ㅂ": "p", "ㅇ": "ng"}
# before a vowel a final moves over: (what stays, what moves)
_SPLIT = {"ㄳ": ("ㄱ", "ㅅ"), "ㄵ": ("ㄴ", "ㅈ"), "ㄶ": ("", "ㄴ"), "ㄺ": ("ㄹ", "ㄱ"), "ㄻ": ("ㄹ", "ㅁ"), "ㄼ": ("ㄹ", "ㅂ"),
          "ㄽ": ("ㄹ", "ㅅ"), "ㄾ": ("ㄹ", "ㅌ"), "ㄿ": ("ㄹ", "ㅍ"), "ㅀ": ("", "ㄹ"), "ㅄ": ("ㅂ", "ㅅ"), "ㅎ": ("", ""),
          "ㅇ": ("ㅇ", "ㅇ")}
_ASP = {"ㄱ": "ㅋ", "ㄷ": "ㅌ", "ㅂ": "ㅍ", "ㅈ": "ㅊ"}


def _romanise_word(w: str) -> str:
    sy = [list(jamo(c)) for c in w]
    out = []
    for i, (lead, v, f) in enumerate(sy):
        nxt = sy[i + 1] if i + 1 < len(sy) else None
        if nxt is not None and f:
            n = nxt[0]
            if n == "ㅇ":                                    # liaison: the final moves to the next syllable
                if f in _SPLIT:
                    stay, move = _SPLIT[f]
                    f = stay
                    if move and move != "ㅇ":
                        nxt[0] = move
                else:
                    if f in ("ㄷ", "ㅌ") and nxt[1] == "ㅣ":    # palatalisation: 같이 gachi, 굳이 guji
                        nxt[0] = "ㅈ" if f == "ㄷ" else "ㅊ"
                    else:
                        nxt[0] = f
                    f = ""
            elif n == "ㅎ" and _REP[f] in ("ㄱ", "ㄷ", "ㅂ") and f not in ("ㅎ", "ㄶ", "ㅀ"):
                nxt[0] = "ㅊ" if f == "ㅈ" else _ASP[_REP[f]]
                f = ""                                        # aspiration: 축하 chuka
            elif f in ("ㅎ", "ㄶ", "ㅀ") and n in ("ㄱ", "ㄷ", "ㅈ"):
                nxt[0] = _ASP[n]                              # 좋다 jota, 않다 anta
                f = {"ㅎ": "", "ㄶ": "ㄴ", "ㅀ": "ㄹ"}[f]
            elif f in ("ㅎ", "ㄶ", "ㅀ") and n == "ㅅ":
                nxt[0] = "ㅆ"
                f = {"ㅎ": "", "ㄶ": "ㄴ", "ㅀ": "ㄹ"}[f]
            elif f in ("ㅅ", "ㅆ") and n in ("ㅅ", "ㅆ"):
                nxt[0], f = "ㅆ", ""                          # 겠습니다 gesseumnida
            elif f == "ㅎ" and n == "ㄴ":
                f = "ㄴ"
            r = _REP[f]
            if n in ("ㄴ", "ㅁ") and nxt[0] == n:            # nasalisation: 합니다 hamnida, 국물 gungmul
                r = {"ㄱ": "ㅇ", "ㄷ": "ㄴ", "ㅂ": "ㅁ"}.get(r, r)
                if r == "ㄹ" and n == "ㄴ":
                    nxt[0] = "ㄹ"                            # 설날 seollal
            elif n == "ㄹ" and nxt[0] == "ㄹ":
                if r == "ㄴ":
                    r = "ㄹ"                                  # 신라 silla
                elif r in ("ㅁ", "ㅇ"):
                    nxt[0] = "ㄴ"                             # 심리 simni, 종로 jongno
                elif r in ("ㄱ", "ㄷ", "ㅂ"):
                    r = {"ㄱ": "ㅇ", "ㄷ": "ㄴ", "ㅂ": "ㅁ"}[r]
                    nxt[0] = "ㄴ"                             # 국립 gungnip
            f = r
        ini = "l" if (lead == "ㄹ" and out and out[-1].endswith("l")) else _INI[lead]
        out.append(ini + _VOW[v] + _FIN[_REP[f]])
    return "".join(out)


def romanise(s: str) -> str:
    """Revised Romanization of Hangul text; anything else is kept as it is."""
    if not isinstance(s, str):
        return ""
    return re.sub(r"[가-힣]+", lambda m: _romanise_word(m.group(0)), s[:400])


# ---------------------------------------------------------------------------
# particles (and the copula), with the batchim they follow: C after a consonant, V after a vowel, A either
# ---------------------------------------------------------------------------
PARTICLES: dict[str, tuple[str, str]] = {
    "은": ("C", "topic"), "는": ("V", "topic"), "이": ("C", "subject"), "가": ("V", "subject"),
    "을": ("C", "object"), "를": ("V", "object"), "ㄹ": ("V", "object (spoken)"),
    "과": ("C", "and / with"), "와": ("V", "and / with"), "하고": ("A", "and / with"),
    "이랑": ("C", "and / with (casual)"), "랑": ("V", "and / with (casual)"),
    "으로": ("C", "to / toward / by means of"), "로": ("VL", "to / toward / by means of"),
    "으로서": ("C", "as (a role)"), "로서": ("VL", "as (a role)"), "으로써": ("C", "by means of"), "로써": ("VL", "by means of"),
    "에": ("A", "at / in / to (place, time)"), "에서": ("A", "at / in / from (where it happens)"),
    "에게": ("A", "to (a person)"), "한테": ("A", "to (a person, casual)"), "께": ("A", "to (a person, honorific)"),
    "에게서": ("A", "from (a person)"), "한테서": ("A", "from (a person)"), "께서": ("A", "subject (honorific)"),
    "도": ("A", "also / too / even"), "만": ("A", "only"), "의": ("A", "of / 's"), "까지": ("A", "until / as far as"),
    "부터": ("A", "from / starting at"), "보다": ("A", "than"), "처럼": ("A", "like"), "같이": ("A", "like / together"),
    "마다": ("A", "every"), "밖에": ("A", "nothing but (with a negative)"), "쯤": ("A", "about / around"),
    "씩": ("A", "each / apiece"), "들": ("A", "plural"), "요": ("A", "polite"), "이요": ("C", "polite"),
    "이나": ("C", "or / as many as"), "나": ("V", "or / as many as"), "조차": ("A", "even"), "마저": ("A", "even"),
    "뿐": ("A", "only"), "대로": ("A", "according to"), "엔": ("A", "at / in (topic)"), "에선": ("A", "at / in (topic)"),
    "에다": ("A", "onto / into"), "에다가": ("A", "onto / into"), "한테는": ("A", "to (a person, topic)"),
    "께서는": ("A", "subject (honorific topic)"), "이든지": ("C", "whichever"), "든지": ("V", "whichever"),
    # the copula: "is"
    "이에요": ("C", "is (copula, polite)"), "예요": ("V", "is (copula, polite)"), "입니다": ("A", "is (copula, formal)"),
    "입니까": ("A", "is it? (copula, formal)"), "이었어요": ("C", "was (copula, past polite)"),
    "였어요": ("V", "was (copula, past polite)"), "이었습니다": ("C", "was (copula, past formal)"),
    "였습니다": ("V", "was (copula, past formal)"), "이야": ("C", "is (copula, casual)"), "야": ("V", "is (copula, casual)"),
    "이다": ("C", "is (copula, plain)"), "이고": ("C", "is, and (copula)"), "이지만": ("C", "is, but (copula)"),
    "인데": ("C", "is, and/but (copula)"), "인데요": ("C", "is (copula, soft)"), "이라서": ("C", "because it is"),
    "라서": ("V", "because it is"), "이라고": ("C", "called / that it is"), "라고": ("V", "called / that it is"),
    "이세요": ("C", "is (copula, honorific)"), "세요": ("V", "is (copula, honorific)"), "인가요": ("C", "is it? (copula)"),
    "인가": ("C", "is it? (copula)"), "가요": ("V", "is it? (copula)"), "이죠": ("C", "is, right? (copula)"),
    "죠": ("V", "is, right? (copula)"), "이지요": ("C", "is, right? (copula)"), "지요": ("V", "is, right? (copula)"),
    "일까요": ("C", "could it be? (copula)"), "일": ("C", "to be (copula, future)"), "인": ("C", "being (copula)"),
    "이면": ("C", "if it is (copula)"), "이라면": ("C", "if it is (copula)"), "라면": ("V", "if it is (copula)"),
    "이네요": ("C", "is! (copula)"), "네요": ("V", "is! (copula)"),
}
_PARTS = sorted(PARTICLES, key=len, reverse=True)
_PART_FIRST = {"ㄹ"}             # a particle written as a final on the noun (날 = 나 + ㄹ)


def _fits(noun: str, need: str) -> bool:
    if need == "A":
        return True
    f = final(noun[-1])
    if need == "C":
        return bool(f)
    if need == "VL":
        return not f or f == "ㄹ"
    return not f


def _strip_particles(w: str, depth: int = 0) -> list[tuple[str, list[str]]]:
    """(noun, [particle, ...]) for every way the end of ``w`` is particles; the noun is left of them."""
    out: list[tuple[str, list[str]]] = []
    if depth >= 3 or len(w) < 2:
        return out
    for p in _PARTS:
        if p in _PART_FIRST:
            f = final(w[-1])
            if f == p and len(w) >= 2:
                noun = w[:-1] + with_final(w[-1], "")
                out.append((noun, [p]))
            continue
        if w.endswith(p) and len(w) > len(p):
            noun = w[: -len(p)]
            if not _fits(noun, PARTICLES[p][0]):
                continue
            out.append((noun, [p]))
            for n2, ps in _strip_particles(noun, depth + 1):
                out.append((n2, ps + [p]))
    return out


# ---------------------------------------------------------------------------
# verb and adjective endings
# ---------------------------------------------------------------------------
# endings after the bare stem: suffix -> label. A suffix may start with a final jamo (ㄴ, ㄹ, ㅂ) written on the
# stem's last syllable, or with 으 after a consonant stem.
STEM_TAILS: dict[str, str] = {
    "습니다": "formal polite", "습니까": "formal polite question", "ㅂ니다": "formal polite",
    "ㅂ니까": "formal polite question", "읍시다": "let's (formal)", "ㅂ시다": "let's (formal)",
    "고": "and (-고)", "고요": "and (-고요)", "지만": "but (-지만)", "지요": "…, right? (-지요)", "죠": "…, right? (-죠)",
    "지": "(-지)", "지마": "don't (-지 마)", "는": "that … (present, -는)", "는데": "and / but (-는데)",
    "는데요": "softened statement (-는데요)", "은데": "and / but (-은데)", "ㄴ데": "and / but (-ㄴ데)",
    "은데요": "softened statement (-은데요)", "ㄴ데요": "softened statement (-ㄴ데요)", "네요": "oh, … (-네요)",
    "네": "oh, … (-네)", "는군요": "I see, … (-군요)", "군요": "I see, … (-군요)", "게": "so that / -ly (-게)",
    "기": "-ing (-기)", "기로": "decide to (-기로)", "기에": "because (-기에)", "기는": "-ing (-기는)",
    "다": "plain form", "는다": "plain form (present)", "ㄴ다": "plain form (present)", "자": "let's (-자)",
    "면": "if / when (-면)", "으면": "if / when (-으면)", "니까": "because (-니까)", "으니까": "because (-으니까)",
    "러": "in order to (-러)", "으러": "in order to (-으러)", "려고": "intending to (-려고)", "으려고": "intending to (-으려고)",
    "려면": "in order to (-려면)", "으려면": "in order to (-으려면)",
    "은": "that … (past / description, -은)", "ㄴ": "that … (past / description, -ㄴ)",
    "을": "that will … (-을)", "ㄹ": "that will … (-ㄹ)", "을까요": "shall we …? (-을까요)", "ㄹ까요": "shall we …? (-ㄹ까요)",
    "을까": "shall I …? (-을까)", "ㄹ까": "shall I …? (-ㄹ까)", "을게요": "I will (-을게요)", "ㄹ게요": "I will (-ㄹ게요)",
    "을래요": "I want to (-을래요)", "ㄹ래요": "I want to (-ㄹ래요)", "을까봐": "in case (-을까 봐)",
    "거나": "or (-거나)", "도록": "so that (-도록)", "던": "that used to (-던)", "나요": "question (-나요)",
    "니": "question (-니)", "냐": "question (-냐)", "는지": "whether (-는지)", "은지": "whether (-은지)", "ㄴ지": "whether (-ㄴ지)",
    "세요": "polite request / honorific (-세요)", "으세요": "polite request / honorific (-으세요)",
    "셨어요": "honorific past polite", "으셨어요": "honorific past polite", "십니다": "honorific formal",
    "으십니다": "honorific formal", "십니까": "honorific formal question", "으십니까": "honorific formal question",
    "시고": "honorific, and", "으시고": "honorific, and", "셔서": "honorific, so", "으셔서": "honorific, so",
    "셨습니다": "honorific past formal", "으셨습니다": "honorific past formal", "실": "honorific (-실)", "으실": "honorific (-으실)",
    "신": "honorific (-신)", "으신": "honorific (-으신)", "시는": "honorific (-시는)", "으시는": "honorific (-으시는)",
    "시면": "honorific, if", "으시면": "honorific, if", "시죠": "honorific, …right? / please",
    "겠어요": "will / must (-겠-), polite", "겠습니다": "will (-겠-), formal", "겠다": "will (-겠-)", "겠어": "will (-겠-)",
    "겠네요": "must be (-겠네요)", "겠죠": "will …, right? (-겠죠)", "겠지요": "will …, right? (-겠지요)",
    "고있어요": "is …-ing", "잖아요": "you know (-잖아요)",
}
# endings after the infinitive (the -아/-어 form: 먹어, 가, 해, 봐)
INF_TAILS: dict[str, str] = {
    "요": "polite (-아요/-어요)", "": "informal (-아/-어)", "서": "so / and then (-아서)", "서요": "so (-아서요)",
    "도": "even if (-아도)", "도요": "even if (-아도요)", "야": "must / only if (-아야)", "야지": "should (-아야지)",
    "야지요": "should (-아야지요)", "야겠어요": "will have to (-아야겠어요)", "라": "command (-아라)", "주세요": "please (-아 주세요)",
}
# endings after the past marker ㅆ (먹었 = 먹어 + ㅆ)
PAST_TAILS: dict[str, str] = {
    "어요": "past polite", "어": "past informal", "습니다": "past formal polite", "습니까": "past formal question",
    "다": "past plain", "고": "past, and", "지만": "past, but", "는데": "past, and / but", "는데요": "past, softened",
    "을": "past (-었을)", "던": "past (-었던)", "네요": "past, oh … (-었네요)", "죠": "past, … right?", "지요": "past, … right?",
    "으면": "past, if", "을까요": "past, do you think …?", "겠어요": "past, must have", "겠네요": "past, must have",
    "나요": "past question", "니": "past question", "으니까": "past, because", "기": "past (-었기)", "어서": "past, so",
    "는지": "past, whether",
}
_STEM_ORDER = sorted(STEM_TAILS, key=len, reverse=True)
_INF_ORDER = sorted(INF_TAILS, key=len, reverse=True)
_PAST_ORDER = sorted(PAST_TAILS, key=len, reverse=True)
_JAMO_FINALS = set(T_J[1:])
# ㄷ-irregular verbs where the ㄷ reading is the usual one (들어요 is "listen" far more often than "lift")
PREFER = {"듣다", "걷다", "묻다", "깨닫다", "싣다", "모르다", "덥다", "춥다", "쉽다", "어렵다", "고맙다", "반갑다", "돕다"}


def _cut(w: str, tail: str) -> list[str]:
    """What is left of ``w`` before ``tail`` (a tail may begin with a final written on the previous syllable)."""
    if not tail:
        return [w]
    if tail[0] in _JAMO_FINALS:
        rest = tail[1:]
        if len(w) <= len(rest) or (rest and not w.endswith(rest)):
            return []
        head = w[: len(w) - len(rest)]
        if not is_syl(head[-1]) or final(head[-1]) != tail[0]:
            return []
        return [head[:-1] + with_final(head[-1], "")]
    if w.endswith(tail) and len(w) > len(tail):
        return [w[: -len(tail)]]
    return []


def _stem_variants(stem: str, tail: str) -> list[tuple[str, float, str]]:
    """Stems a bare-stem ending may have left: the stem itself, an ㄹ or ㅎ dropped before ㄴ/ㅂ/ㅅ, an ㄷ/ㅂ/ㅅ
    changed before 으."""
    out = [(stem, 0.0, "")]
    if not stem or not hangul(stem):
        return out
    last = stem[-1]
    f = final(last)
    if not f and (tail[:1] in ("ㄴ", "ㅂ", "ㄹ") or tail.startswith(("세", "셨", "십", "시", "신", "실", "니", "네", "는"))):
        out.append((stem[:-1] + with_final(last, "ㄹ"), 0.2, "ㄹ dropped"))        # 삽니다 살다, 만드세요 만들다, 아는 알다
    if not f and tail[:1] in ("ㄴ", "ㄹ", "면", "니") or (not f and tail.startswith(("네", "은"))):
        out.append((stem[:-1] + with_final(last, "ㅎ"), 0.4, "ㅎ irregular"))      # 그런 그렇다, 빨간 빨갛다
    if tail.startswith("으"):
        if f == "ㄹ":
            out.append((stem[:-1] + with_final(last, "ㄷ"), 0.3, "ㄷ irregular"))  # 들으면 듣다
        if not f:
            out.append((stem[:-1] + with_final(last, "ㅅ"), 0.4, "ㅅ irregular"))  # 나으면 낫다
    if not f and last == "우" and len(stem) >= 2 and not final(stem[-2]) and not tail.startswith("으"):
        out.append((stem[:-2] + with_final(stem[-2], "ㅂ"), 0.3, "ㅂ irregular"))   # 더우면 덥다, 추운 춥다
    return out


def _inf_stems(inf: str) -> list[tuple[str, float, str]]:
    """Stems an infinitive (-아/-어 form) may come from, with what each assumes."""
    if not hangul(inf):
        return []
    last = inf[-1]
    lead, v, f = jamo(last)
    if f:
        return []
    prev = inf[-2] if len(inf) >= 2 else ""
    base = inf[:-1]
    out: list[tuple[str, float, str]] = []
    if last == "해":
        out.append((base + "하", 0.0, "하다 verb"))
    if last == "돼":
        out.append((base + "되", 0.0, ""))
    if lead == "ㅇ" and v in ("ㅏ", "ㅓ") and prev:
        if final(prev):
            out.append((base, 0.0, ""))                                          # 먹어 먹, 앉아 앉, 있어 있
            if final(prev) == "ㄹ":
                out.append((base[:-1] + with_final(prev, "ㄷ"), 0.3, "ㄷ irregular"))   # 들어 듣
        else:
            out.append((base, 0.1, ""))                                          # 주어 주, 되어 되
            out.append((base[:-1] + with_final(prev, "ㅅ"), 0.4, "ㅅ irregular"))   # 나아 낫, 지어 짓
    if lead == "ㅇ" and v == "ㅕ" and prev == "하":
        out.append((base, 0.0, "하다 verb"))                                       # 하여
    if v == "ㅏ" or v == "ㅓ":
        if not (lead == "ㅇ" and prev):
            out.append((inf, 0.0, ""))                                           # 가 가, 서 서, 만나 만나
        if lead == "ㄹ" and prev and final(prev) == "ㄹ":
            out.append((base[:-1] + with_final(prev, "") + syl("ㄹ", "ㅡ"), 0.2, "르 irregular"))   # 몰라 모르, 불러 부르
        if lead != "ㅇ":
            out.append((base + with_vowel(last, "ㅡ"), 0.3, "ㅡ dropped"))          # 써 쓰, 바빠 바쁘, 예뻐 예쁘
    if v == "ㅘ":
        out.append((base + with_vowel(last, "ㅗ"), 0.0, ""))                       # 봐 보, 와 오
        if lead == "ㅇ" and prev and not final(prev):
            out.append((base[:-1] + with_final(prev, "ㅂ"), 0.3, "ㅂ irregular"))   # 도와 돕
    if v == "ㅝ":
        out.append((base + with_vowel(last, "ㅜ"), 0.0, ""))                       # 줘 주, 배워 배우
        if lead == "ㅇ" and prev and not final(prev):
            out.append((base[:-1] + with_final(prev, "ㅂ"), 0.2, "ㅂ irregular"))   # 더워 덥, 고마워 고맙
    if v == "ㅕ":
        out.append((base + with_vowel(last, "ㅣ"), 0.0, ""))                       # 마셔 마시, 기다려 기다리
        out.append((inf, 0.2, ""))                                               # 켜 켜
    if v == "ㅐ" and last != "해":
        out.append((inf, 0.0, ""))                                               # 보내 보내
        for vv in ("ㅓ", "ㅏ"):
            out.append((base + syl(lead, vv, "ㅎ"), 0.4, "ㅎ irregular"))          # 그래 그렇, 빨개 빨갛
    if v == "ㅙ":
        out.append((base + with_vowel(last, "ㅚ"), 0.0, ""))                       # 봬 뵈
    if v in ("ㅔ", "ㅖ", "ㅟ", "ㅚ", "ㅢ"):
        out.append((inf, 0.1, ""))
    return out


def _honorific(stems: list[tuple[str, float, str]]) -> list[tuple[str, float, str]]:
    """가시 -> 가, 읽으시 -> 읽: the honorific -시- taken off a stem."""
    out = list(stems)
    for s, c, n in stems:
        if len(s) >= 2 and s.endswith("시"):
            b = s[:-1]
            if b.endswith("으") and len(b) >= 2:
                out.append((b[:-1], c + 0.3, "honorific"))
            out.append((b, c + 0.3, "honorific"))
    return out


def verb_analyses(w: str) -> list[tuple[str, float, str]]:
    """(dictionary form in -다, cost, what was taken off) for every way ``w`` is a stem and an ending."""
    out: list[tuple[str, float, str]] = []
    if not hangul(w):
        return out

    def add(stems, cost, label):
        for s, c, note in stems:
            if s and hangul(s) and s + "다" != w:
                out.append((s + "다", cost + c, f"{label}; {note}" if note else label))

    # past: a syllable with the final ㅆ, then a past ending
    for i in range(len(w) - 1, -1, -1):
        if final(w[i]) == "ㅆ":
            rest = w[i + 1:]
            if rest in PAST_TAILS:
                inf = w[:i] + with_final(w[i], "")
                add(_honorific(_inf_stems(inf)), 1.0, PAST_TAILS[rest])
            break
    for tail in _INF_ORDER:
        for inf in _cut(w, tail) if tail else [w]:
            add(_honorific(_inf_stems(inf)), 1.0 if tail else 1.4, INF_TAILS[tail])
    for tail in _STEM_ORDER:
        for stem in _cut(w, tail):
            add(_honorific(_stem_variants(stem, tail)), 1.0, STEM_TAILS[tail])
    return out


# pronouns and the commonest nouns: with a particle on, they beat a verb form spelled the same (나는 "I + topic",
# not 날다 "to fly"; 저는, 제가, 이건, 거기에)
COMMON_NOUNS = {"나", "저", "너", "우리", "저희", "그", "그녀", "이", "거", "것", "이것", "그것", "저것", "뭐", "무엇", "누구",
                "여기", "거기", "저기", "어디", "언제", "지금", "오늘", "내일", "어제", "제", "내", "네", "때", "집", "물", "말",
                "돈", "일", "날", "씨", "분", "사람", "친구", "학교", "회사", "시간", "이름", "한국", "한국어", "영어", "밥", "책", "차"}

# endings that mark a word as a verb (so a verb reading beats a noun spelled the same: 가요 "go", not "song")
_VERBAL = re.compile(r"(?:요|니다|니까|ㅆ어|습니다)$")


def norm_word(w) -> str:
    return generic_norm(w)


def segment(text: str) -> list[dict]:
    """Korean is written with spaces between eojeol: split on them and on punctuation."""
    return simple_segment(text)


TABLE = kaikki.Table(LANG)
# a gloss that is only a name, or only says which word this is a form of ("topic-marked form of 나"), is weak
_WEAK = re.compile(r"^(?:(?:(?:a |an )?(?:korean )?(?:male |female )?(?:given name|surname|family name)[^;]*|"
                   r"[^;]*\b(?:marked|tense|honorific|polite|informal|formal|plain|indicative|assertive|interrogative|"
                   r"imperative|propositive|connective|adnominal|past|future|present) form of\b[^;]*)(?:; |$))+$", re.I)


def dictionary() -> kaikki.Table:
    return TABLE.load()


_DIGIT = dict(zip("일이삼사오육칠팔구", range(1, 10)))
_UNIT = {"십": 10, "백": 100, "천": 1000}


def sino_number(w: str) -> int | None:
    """오천 -> 5000, 이십오 -> 25, 삼백 -> 300, 만 -> 10000: Sino-Korean numbers written in Hangul (two syllables or more)."""
    if len(w) < 2 or len(w) > 12 or any(c not in _DIGIT and c not in _UNIT and c != "만" for c in w):
        return None
    total = section = 0
    digit = None
    last_unit = 10 ** 9
    for c in w:
        if c in _DIGIT:
            if digit is not None:
                return None
            digit = _DIGIT[c]
        elif c in _UNIT:
            u = _UNIT[c]
            if u >= last_unit:
                return None
            section += (digit or 1) * u
            digit, last_unit = None, u
        else:                                       # 만
            section += digit or 0
            total += (section or 1) * 10000
            section, digit, last_unit = 0, None, 10 ** 9
    return total + section + (digit or 0)


def candidates(word: str) -> list[tuple[str, str, str, float]]:
    """(key, how, grammar note, cost) to try for a normalised word, cheapest first."""
    out: list[tuple[str, str, str, float]] = []
    verbal = bool(_VERBAL.search(word)) or any(final(c) == "ㅆ" for c in word[-3:-1])
    out.append((word, "exact", "", 0.0))
    for key, cost, label in verb_analyses(word):
        out.append((key, "ending", label, cost - (0.6 if key in PREFER else 0.0)))
        if key.endswith("하다") and len(key) > 3:                     # a 하다 verb the data lacks: its noun
            out.append((key[:-2], "ending", f"{label}; noun + 하다 (do …)", cost + 1.2))
    for noun, ps in _strip_particles(word):
        cost = 0.1 * len(ps) if noun in COMMON_NOUNS else 0.9 * len(ps) + (0.6 if len(noun) == 1 else 0.0)
        label = " + ".join(f"{p}: {PARTICLES[p][1]}" for p in ps)
        out.append((noun, "particle", label, cost))
    if verbal and word not in dictionary().phrases:
        out[0] = (word, "exact", "", 1.6)             # 가요 is "song", but far more often "goes"
    seen: dict[str, int] = {}
    uniq: list[tuple[str, str, str, float]] = []
    for c in out:
        if c[0] in seen:
            i = seen[c[0]]
            if c[3] < uniq[i][3]:
                uniq[i] = c
            continue
        seen[c[0]] = len(uniq)
        uniq.append(c)
    return sorted(uniq, key=lambda c: c[3])


def _senses(key: str, mine: dict) -> list[dict]:
    d = dictionary()
    out = []
    if key in mine:
        out.append({"src": "mine", "text": mine[key]})
    if key in d.lem:
        out.append({"src": "wiktionary", "text": d.lem[key]})
    return out


def _strong(senses: list[dict]) -> bool:
    return any(s["src"] != "wiktionary" or not _WEAK.match(s["text"]) for s in senses)


def lookup(raw, mine: dict | None = None) -> dict:
    """Look an eojeol up. -> {found, word, lemma, path, how, gram, rom, lemma_rom, senses, also, weak}."""
    word = norm_word(raw)
    if not word:
        return {"ok": True, "found": False, "word": "", "senses": [], "also": [], "credit": CREDIT}
    mine = mine or {}
    d = dictionary()
    hits: list[tuple[float, int, dict]] = []
    n = 0
    cands = candidates(word)
    labels = {k: g for k, h, g, _ in sorted(cands, key=lambda c: c[3]) if h == "ending" and "noun + 하다" not in g}
    for key, how, gram, cost in cands:
        tries = [(key, how, gram, cost)]
        if how != "particle" or key not in d.lem or not _strong(_senses(key, {})):
            for i, lem in enumerate(d.lemmas_of(key)):
                if lem == key:
                    continue
                if how == "exact":             # a conjugation Wiktionary lists: the surest reading of all
                    c = 0.3 + 0.05 * i - (0.1 if lem in PREFER else 0.0)
                    tries.append((lem, "form", labels.get(lem, ""), c))
                elif key not in d.lem or not _strong(_senses(key, {})):
                    # 거 (a contraction of 것) or, after a particle came off, the verb a form belongs to: less sure
                    tries.append((lem, how, gram, cost + (0.5 if how == "particle" else 0.1)))
        for lem, h, g, c in tries:
            senses = _senses(lem, mine)
            if not senses:
                continue
            path = [word] if lem == word else ([word, key, lem] if key not in (word, lem) else [word, lem])
            if not _strong(senses):
                c += 5
            hits.append((c, n, {"lemma": lem, "path": path, "how": h, "gram": g, "senses": senses,
                                "lemma_rom": d.rom.get(lem) or romanise(lem)}))
            n += 1
    hits.sort(key=lambda x: (x[0], x[1]))
    out = {"ok": True, "word": word, "rom": romanise(word), "credit": CREDIT}
    num = sino_number(word)
    if num is not None and not hits:
        hits.append((0.0, 0, {"lemma": word, "path": [word], "how": "number", "gram": "Sino-Korean number",
                              "senses": [{"src": "rule", "text": f"{num:,}"}], "lemma_rom": romanise(word)}))
    seen: set[str] = set()
    ranked = []
    for _, _, h in hits:
        if h["lemma"] not in seen:
            seen.add(h["lemma"])
            ranked.append(h)
    if ranked:
        out.update(ranked[0])
        out["found"] = True
        out["weak"] = not _strong(ranked[0]["senses"])
        out["also"] = ranked[1:4]
    else:
        out.update(found=False, lemma="", path=[word], how="", gram="", senses=[], also=[], weak=False, lemma_rom="")
    return out


def search(q, direction: str = "from", mine: dict | None = None, limit: int = 40) -> list[dict]:
    """Korean -> English by headword (Hangul, or its romanisation), or English -> Korean by gloss."""
    return kaikki.search(dictionary(), q, direction, mine or {}, limit, norm_word, lookup, _WEAK, ascii_rom=True)
