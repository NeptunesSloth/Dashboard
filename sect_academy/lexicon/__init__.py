"""Per-language dictionaries for the reader: a registry of lookup modules.

Each language with lookup is one module here (``es.py``) reading its data from
``sect_academy/dict/<lang>/`` (whose README names the source and licence).
A module provides:

    LANG, NAME, SPEECH                  code ("es"), English name ("Spanish"), speech tag ("es-ES")
    CREDIT                              one line naming the source and licence, shown with every result
    norm_word(raw) -> str               a tapped/typed word as a dictionary key ("" if it is not a word)
    lookup(word, mine) -> dict          {found, word, lemma, path, how, senses[{src, text}], also, weak}
    search(q, direction, mine, limit)   -> [{w, en, src}] rows: w the word in the language, en its gloss;
                                        direction "from" (by headword) or "en" (English -> the language, by gloss)
    segment(text) -> [{t, k}]           the text cut into tokens whose ``t`` joined give the text back;
                                        ``k`` is the lookup key of a word token, None for space/punctuation

``mine`` is the learner's own entries for that language ({word: meaning}). Data
is loaded lazily, once. Spanish segments on spaces and punctuation; Chinese and
Japanese will need longest-match against their dictionary — that is why the
reader asks the server to segment a page rather than splitting it itself.
"""
from __future__ import annotations

import importlib
import re
import unicodedata

# Book languages the reader offers. Those without a module here are read and spoken,
# and the UI says lookup is coming.
LANGS = {"es": "Spanish", "fr": "French", "zh": "Mandarin Chinese", "ja": "Japanese", "ko": "Korean",
         "en": "English", "pt": "Portuguese", "it": "Italian", "de": "German", "other": "Another language"}
SPEECH = {"es": "es-ES", "fr": "fr-FR", "zh": "zh-CN", "ja": "ja-JP", "ko": "ko-KR", "en": "en-GB",
          "pt": "pt-PT", "it": "it-IT", "de": "de-DE"}
MODULES = {"es": "sect_academy.lexicon.es"}      # lang -> lookup module (import path)
MAX_WORD = 40
_LANG_RE = re.compile(r"^[a-z]{2,5}$")


def available() -> list[str]:
    return list(MODULES)


def get(lang: str):
    """The lookup module for a language, or None."""
    name = MODULES.get(lang) if isinstance(lang, str) else None
    return importlib.import_module(name) if name else None


def valid_lang(lang) -> bool:
    return isinstance(lang, str) and bool(_LANG_RE.match(lang)) and lang in LANGS


def generic_norm(w) -> str:
    """Any language: one word, NFC, lower case, no punctuation around it."""
    if not isinstance(w, str):
        return ""
    w = unicodedata.normalize("NFC", w[:200]).replace("’", "'").replace("‘", "'").lower().strip()
    w = re.sub(r"^[^\w]+|[^\w]+$", "", w)
    if not w or any(ch.isspace() for ch in w) or not any(ch.isalpha() for ch in w) or len(w) > MAX_WORD:
        return ""
    return w


def norm_word(lang: str, w) -> str:
    mod = get(lang)
    return mod.norm_word(w) if mod else generic_norm(w)


_WORD = re.compile(r"[^\W\d_](?:[\w'’-]*[^\W_])?")


def simple_segment(text: str) -> list[dict]:
    """Split on spaces and punctuation (alphabetic scripts). Lookup keys are normalised words."""
    out, last = [], 0
    for m in _WORD.finditer(text):
        if m.start() > last:
            out.append({"t": text[last:m.start()], "k": None})
        out.append({"t": m.group(0), "k": generic_norm(m.group(0)) or None})
        last = m.end()
    if last < len(text):
        out.append({"t": text[last:], "k": None})
    return out
