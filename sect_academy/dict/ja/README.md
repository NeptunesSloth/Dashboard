# Japanese → English dictionary

`jmdict_ja_en.tsv.gz` is the offline dictionary the reader looks Japanese words
up in (gzip of a UTF-8 text file, one entry per line, tab-separated, lines
starting with `#` are comments):

    kanji forms  kana readings  tags  rank  gloss

213,620 entries (6.8 MB). Forms and readings are comma-separated; `!` after one
marks it as common (JMdict's news1/ichi1/spec/gai1 or nf01–nf48 marks); a
reading that belongs to only some kanji forms is written `reading@form1/form2`
(`@-`: never written in kanji). Tags are JMdict part-of-speech codes (v1, v5k,
vk, vs, adj-i, adj-na, n, prt, exp …) — the reader's conjugation rules check
them — plus `uk` when the word is usually written in kana. Rank orders
homographs: 1–48 the newspaper-frequency band, 12 basic words without a band,
30 other common words, 60 lesser marks, 99 none. The gloss keeps the first
three senses with up to three English glosses each (senses joined "; ",
glosses ", ").

**Source:** JMdict (the English-only file `JMdict_e`), from the Electronic
Dictionary Research and Development Group, http://ftp.edrdg.org/pub/Nihongo/JMdict_e.gz,
fetched 26 November 2026.

**Licence:** This publication has included material from the JMdict
(EDICT, etc.) dictionary files in accordance with the licence provisions of
the Electronic Dictionary Research and Development Group. JMdict, Electronic
Dictionary Research and Development Group — the files are the property of the
Group and are made available under the Creative Commons Attribution-ShareAlike
Licence (V4.0), https://creativecommons.org/licenses/by-sa/4.0/. Licence
statement: https://www.edrdg.org/edrdg/licence.html. `jmdict_ja_en.tsv.gz` is
a trimmed adaptation, distributed under that licence and not under the rest
of this repository's terms. The reader shows the credit line with every result
(`CREDIT` in `lexicon/ja.py`).

**How it was built:** `python scripts/build_dict_zh_ja.py --only ja` downloads
JMdict_e to a temporary folder, parses the XML as a stream (each `&v1;`-style
entity read as its code), writes this file and deletes the download. Entries
with no frequency mark whose every kept sense is archaic, obsolete or rare were
left out (5,613 of 219,233).

**Known gaps:**
- JMdict is a dictionary of words, not of names: a family or given name
  (田中, たなか) is not in it. Before さん/くん/さま the reader treats the piece as a
  name; elsewhere a name comes out in pieces.
- Only the first three senses are kept; rare senses of common words are gone.
- Conjugations are undone by rule (`lexicon/ja_rules.py`), checked against the
  part of speech, so a form the rules do not cover (classical grammar, some
  dialect and slang) is found only if JMdict lists it.
- Words in kana that JMdict normally writes in kanji are a weaker guess for the
  segmenter (はいしゃ can be 歯医者 or は + いしゃ); a long hiragana-only run can
  be cut differently from how a teacher would space it.
- Counters are recognised for common ones after a number (さんじゅうにさい,
  八時, 3つ); others come out as number + word.
