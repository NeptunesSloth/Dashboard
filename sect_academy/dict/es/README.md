# Spanish → English dictionary

`es_en.tsv.gz` is the offline dictionary the reader looks Spanish words up in
(gzip of a UTF-8 text file, one entry per line, tab-separated, sorted; the
format is shared with `fr/` and `ko/` and read by `lexicon/kaikki.py`):

    L <tab> lemma <tab> gloss <tab> <tab> flags <tab> frequency   (101,941 lines)
    F <tab> form  <tab> lemma[|lemma]          (140,311 lines: conjugations, plurals, feminines)
    C <tab> verb  <tab> form=code,...          (1,936 lines: each form's tense and person)

The gloss keeps every part of speech Wiktionary has for the word, one section
per entry (`adj: away with the fairies … | noun: Ido (language)`), the usual
ones first: proper nouns, abbreviations and dialect-only entries go last, and
within an entry colloquial, slang and vulgar senses go after the plain ones.
Flags: `p` only a proper noun, `a` only an abbreviation. Frequency: log10 of
the word's count in the subtitle frequency list below (absent: a rare word).
A conjugation code is `mood.tense.person` (`ind.pret.3s`, `subj.impf.13s`,
`imp.2s.f`, `pp.fs`, `ger`); the reader says it in words ("ser / ir,
preterite, 3rd person singular (él, ella, usted)"). About 2.4 MB gzipped.

**Source:** English Wiktionary, by the Wiktionary contributors, as extracted by
wiktextract and published by kaikki.org:
https://kaikki.org/dictionary/Spanish/kaikki.org-dictionary-Spanish.jsonl
(file dated 30 October 2026, fetched 26 November 2026). It replaces the
earlier doozan/spanish_data compilation, which kept one part of speech per
word ("ido" was only "absent-minded", "su" only "given name").

**Licence:** Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/ (Wiktionary
text is also available under the GFDL). `es_en.tsv.gz` is distributed under
that licence, not under the rest of this repository's terms: you may share and
adapt it with attribution, and anything you build from it must carry the same
licence. The reader shows the credit line with every result.

**Frequencies** (build time only): FrequencyWords by Hermit Dave,
https://github.com/hermitdave/FrequencyWords, `content/2018/es/es_50k.txt`
(word counts from the OpenSubtitles 2018 corpus), content licensed CC BY-SA
4.0. Only a one-digit frequency per lemma is kept; the list itself is not
shipped. It marks rare lemmas, which the reader leaves out of "Also"
("étaient" is être; étayer is not offered) and whose forms Spanish does not
store (below).

**How it was built:** `python scripts/build_dict_kaikki.py es` streams the
JSONL (about 1.1 GB) line by line, never storing it, keeps headword, part of
speech, forms and glosses, and writes this file:

- each Wiktionary entry is a section of up to 4 senses (2 after the first),
  90 characters each, 320 in all; obsolete, archaic and historical senses are
  dropped, dated, rare and neologism senses kept only when nothing else is;
- people's names are dropped; place names are kept, flagged `p`; a
  capitalised headword only fills a gap ("AL" never adds to "al");
- forms: the conjugation tables of verbs and the plurals and feminines of
  nouns and adjectives, plus Wiktionary's "form of" entries, except
  misspellings, Internet spellings, voseo, negative imperatives, the future
  subjunctive and forms with pronouns attached (`lexicon/es.py` takes
  "dímelo" apart by rule);
- to keep memory down (≈ 70 MB in the app), the forms of rare verbs (not in the
  frequency list) and the plurals and feminines the reader's ending rules
  already find (casas → casa, buena → bueno) are not stored as `F` lines.

`function_es_en.tsv` (same `L` format, ~100 lines, our own, under this
repository's terms) gives the function words a short learner's gloss shown
first: lo, le, les, me, te, se, nos, os, su, mi, tu, al, del, que, the
articles, demonstratives, prepositions, haber, hay ("lo — it, him, you
(usted) (direct object); the (neuter, with adjectives: lo bueno = the good
thing)").

`core_es_en.tsv` (same `L` format, about 200 lines) is the owner's own core
word list from the Aprende app (everyday words such as año = year). It is
shown as a sense next to the Wiktionary gloss.

**Known gaps:** no frequency per sense, so the order inside a word is
Wiktionary's; a homograph of a common verb form keeps its own meaning first
("vino" is wine, venir under "Also") except for the forms of the commonest
verbs (`VERB_FIRST` in `lexicon/es.py`: "ido" is ir, "son" ser). Rare verbs
have no tense/person note.

Your own entries (word + meaning, added in the app) live in the state file,
not here.
