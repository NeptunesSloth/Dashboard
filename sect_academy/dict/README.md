# Dictionaries for the reader

One folder per language, named by its code (`es/`, later `fr/`, `zh/`, `ja/`,
`ko/`). Each folder holds the data files and a `README.md` that names the
source and its licence; a data file is distributed under the licence its
README states, not under the rest of this repository's terms.

The code that reads a folder is a lookup module in `sect_academy/lexicon/`
(`es.py` for `es/`), registered in `lexicon/__init__.py`. Adding a language is
that pair: a data folder here and a module there (see the module contract in
`lexicon/__init__.py`).

| Folder | Source | Licence |
| --- | --- | --- |
| `es/` | English Wiktionary via kaikki.org (wiktextract), built by `scripts/build_dict_kaikki.py` (+ a 200-word core list from the owner's Aprende app and our function-word glosses) | CC BY-SA 4.0 |
| `fr/` | English Wiktionary via kaikki.org (wiktextract), built by `scripts/build_dict_kaikki.py` (+ our function-word glosses) | CC BY-SA 4.0 |
| `zh/` | CC-CEDICT (MDBG), with word counts from jieba's dict.txt (MIT), built by `scripts/build_dict_zh_ja.py` | CC BY-SA 4.0 |
| `ja/` | JMdict, Electronic Dictionary Research and Development Group (https://www.edrdg.org/edrdg/licence.html), built by `scripts/build_dict_zh_ja.py` | CC BY-SA 4.0 |
| `ko/` | English Wiktionary via kaikki.org (wiktextract), built by `scripts/build_dict_kaikki.py` | CC BY-SA 4.0 |

The build scripts download, stream and keep only the compact result. Spanish
and French are ranked at build time with the FrequencyWords lists
(https://github.com/hermitdave/FrequencyWords, OpenSubtitles 2018 counts,
content CC BY-SA 4.0); only a one-digit frequency per lemma is kept.
