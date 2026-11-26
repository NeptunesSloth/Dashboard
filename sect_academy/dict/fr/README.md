# French → English dictionary

`fr_en.tsv.gz` is the offline dictionary the reader looks French words up in
(gzip of a UTF-8 text file, one entry per line, tab-separated, sorted):

    L <tab> lemma <tab> English gloss     (85,167 lines; up to 3-4 senses separated by "; ")
    F <tab> form  <tab> lemma[|lemma]     (337,095 lines: conjugations, plurals, feminines,
                                           elided and contracted forms; up to 3 lemmas)

About 2.4 MB gzipped, ~280 MB in memory together with Spanish and Korean once all three have been used
(each language loads on its first lookup).

**Source:** English Wiktionary, by the Wiktionary contributors, as extracted by
wiktextract and published by kaikki.org:
https://kaikki.org/dictionary/French/kaikki.org-dictionary-French.jsonl
(file dated 30 October 2026, fetched 26 November 2026).

**Licence:** Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/ (Wiktionary
text is also available under the GFDL). `fr_en.tsv.gz` is distributed under
that licence, not under the rest of this repository's terms: you may share and
adapt it with attribution, and anything you build from it must carry the same
licence. The reader shows the credit line with every result.

**How it was built:** `python scripts/build_dict_fr_ko.py fr` streams the
JSONL (about 590 MB) line by line from kaikki.org, never storing it, keeps only
headword, part of speech, forms and glosses, and writes this file:

- a lemma's gloss is the last-level gloss of its first senses, trimmed to 90
  characters each (long parentheticals dropped), 240 in all;
- senses tagged obsolete, archaic or historical are dropped; dated or rare ones
  are kept only when the word has nothing else;
- inflected-form entries ("allons: first-person plural present of aller") become
  `F` lines, as do the conjugation tables and plural/feminine forms of nouns,
  adjectives and verbs; function words (articles, contractions, pronouns) keep
  their "form of" gloss as their meaning ("des: plural of un");
- people's names are dropped; place names (Londres, Espagne) are kept; a
  capitalised headword only fills a gap ("CE" never replaces "ce");
- prefixes, suffixes, proverbs and headwords of more than four words are left out.

**Known gaps:** no frequency information, so for homographs the reader
guesses: a form of one of the ~40 commonest verbs is read as that verb first
(est → être, fut → être, été → être, "l'été" → summer), otherwise the headword
as written ("joue" → cheek, with jouer under "Also"). Slang and regional senses
can appear among the first three. Glosses are Wiktionary's, terse and sometimes
technical.

Your own entries (word + meaning, added in the app) live in the state file,
not here.
