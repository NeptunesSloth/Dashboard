# Korean → English dictionary

`ko_en.tsv.gz` is the offline dictionary the reader looks Korean words up in
(gzip of a UTF-8 text file, one entry per line, tab-separated, sorted):

    L <tab> lemma <tab> gloss <tab> romanisation           (32,750 lines)
    F <tab> form  <tab> lemma[|lemma]                       (321,173 lines: conjugated verb and
                                                             adjective forms, contractions)
    P <tab> headword                                        set phrases and interjections
                                                             (감사합니다): read whole, not as a verb form

About 1.8 MB gzipped.

**Source:** English Wiktionary, by the Wiktionary contributors, as extracted by
wiktextract and published by kaikki.org:
https://kaikki.org/dictionary/Korean/kaikki.org-dictionary-Korean.jsonl
(file dated 30 October 2026, fetched 26 November 2026).

**Licence:** Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/ (Wiktionary
text is also available under the GFDL). `ko_en.tsv.gz` is distributed under
that licence, not under the rest of this repository's terms: you may share and
adapt it with attribution, and anything you build from it must carry the same
licence. The reader shows the credit line with every result.

The gloss is one section per Wiktionary entry, so each homograph shows: 눈 is
`noun: eye … | noun: snow | noun: bud`. Kaikki has no frequencies, so a short
curated list (`KO_FIRST` in the build script, ~80 words) puts the everyday
homograph first (시장: market, mayor, hunger; 네: yes before four; 저: I before
that); dialect-only homographs (시장 "now", Hamgyong) are dropped beside a
standard one.

**How it was built:** `python scripts/build_dict_kaikki.py ko` streams the
JSONL (about 210 MB) line by line, never storing it, and keeps:

- Hangul headwords only (hanja-only entries are dropped; the reader looks up
  Hangul), up to 4 senses for the first entry and 2 for each other, trimmed as
  for French;
- the romanisation from the entry's `romanization` form (Wiktionary's Revised
  Romanization); where an entry has none, `lexicon/ko.py`'s rule-based
  romaniser fills it in (it agrees with every `rom` and `ex_rom` in the Korean
  course);
- the conjugation tables Wiktionary gives for verbs and adjectives (먹었어요 →
  먹다, 들어요 → 듣다|들다) as `F` lines;
- place names (서울, 한국, 미국); people's names are dropped.

**Known gaps:** the form table only covers verbs that have a conjugation table
on Wiktionary, and only the forms in it; everything else is reached by the
particle and ending rules in `lexicon/ko.py`, which can be wrong on
homographs (삽니다 is 사다 "buy" first, 살다 "live" under "Also"; 할, 갈, 볼
are read as verbs, not the nouns "tenth", "reed", "cheek"). No frequency data
beyond the curated homograph list. Personal names (민수)
are not in it. Glosses are Wiktionary's.

Your own entries live in the state file, not here.
