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
| `es/` | Wiktionary data, compiled by doozan/spanish_data (+ a 200-word core list from the owner's Aprende app) | CC BY-SA 4.0 |
