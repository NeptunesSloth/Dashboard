# French → English dictionary

`fr_en.tsv.gz` is the offline dictionary the reader looks French words up in
(gzip of a UTF-8 text file, one entry per line, tab-separated, sorted):

    L <tab> lemma <tab> gloss <tab> <tab> flags <tab> frequency   (85,167 lines)
    F <tab> form  <tab> lemma[|lemma]     (335,982 lines: conjugations, plurals, feminines,
                                           elided and contracted forms; up to 3 lemmas)
    C <tab> verb  <tab> form=code,...     (7,147 lines: each form's tense and person)

The gloss is one section per Wiktionary entry (`verb: to read; to play | noun:
lira (unit of currency)`), common words first, proper nouns, abbreviations and
dialect entries last; flags `p` (only a proper noun) and `a` (only an
abbreviation); frequency is log10 of the word's count in the FrequencyWords
French list (absent: rare). A code is `mood.tense.person` (`ind.pres.1p`,
`ind.ph.3s` passé simple, `subj.pres.13s`, `cond.pres.1s`, `imp.2p`, `pp`);
the reader says "aller, present, 1st person plural (nous)" and, for a verb
form, shows only the verb's senses. About 3.4 MB gzipped, ~90 MB in memory
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

**Frequencies** (build time only): FrequencyWords by Hermit Dave,
https://github.com/hermitdave/FrequencyWords, `content/2018/fr/fr_50k.txt`
(OpenSubtitles 2018), content CC BY-SA 4.0. They decide which other readings
are worth listing under "Also" ("étaient" is être; étayer, ten times rarer, is
left out).

`function_fr_en.tsv` (our own, under this repository's terms) gives the
function words a short learner's gloss shown first (le, la, les, l', de, du,
des, au, aux, y, en, ne, que, qui, se, lui, leur, the possessives ...).

**How it was built:** `python scripts/build_dict_kaikki.py fr` streams the
JSONL (about 590 MB) line by line from kaikki.org, never storing it, keeps only
headword, part of speech, forms and glosses, and writes this file:

- a lemma's gloss is one section per Wiktionary entry of up to 4 senses (2
  after the first), the last-level glosses trimmed to 90 characters each (long
  parentheticals dropped), 320 in all; colloquial, slang and vulgar senses go
  after the plain ones;
- senses tagged obsolete, archaic or historical are dropped; dated or rare ones
  are kept only when the word has nothing else;
- inflected-form entries ("allons: first-person plural present of aller") become
  `F` lines, as do the conjugation tables and plural/feminine forms of nouns,
  adjectives and verbs; function words (articles, contractions, pronouns) keep
  their "form of" gloss as their meaning ("des: plural of un");
- people's names are dropped; place names (Londres, Espagne) are kept and
  flagged; a capitalised headword only fills a gap ("CE" never replaces "ce",
  "NE" is not a form of "ne"); misspellings are not forms;
- prefixes, suffixes, proverbs and headwords of more than four words are left out.

**Known gaps:** frequencies are per word, not per sense, so for homographs the
reader still guesses: a form of one of the ~40 commonest verbs is read as that
verb first (est → être, fut → être, été → être, "l'été" → summer, but "bus" →
bus), otherwise the headword as written ("joue" → cheek, with jouer under
"Also"). Glosses are Wiktionary's, terse and sometimes technical.

Your own entries (word + meaning, added in the app) live in the state file,
not here.
