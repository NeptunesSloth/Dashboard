# Starter shelf

Short public-domain stories and famous poems in Spanish, French, Mandarin Chinese, Japanese and
Korean, shipped with Sect Academy so the Read tab has something to open on day one. They appear on
the Books tab under "Starter shelf", open in the same reader (tap a word to look it up), and keep a
reading position under the id `shelf:<lang>:<slug>`. They are read-only, are never copied into the
user's `<state file>.books/` folder and do not count against the user's shelf caps.

## Files

- `manifest.yaml`: every story (`texts:`) with its evidence, and the poem file of each language.
- `<lang>/<slug>.txt`: one story, UTF-8, the work only.
- `<lang>/poems.yaml`: that language's poems; each line is `[original, English]`, or
  `[original, reading, English]` for Chinese (pinyin), Japanese (`kana | rōmaji`) and Korean
  (Revised Romanization). `[]` is a stanza break.

## The rules (checked by `tests/test_shelf.py`)

- **Public domain everywhere we can tell**: the author died before 1955 and the work was first
  published before 1931 (so it is public domain in the US, and in every country with a term of
  life + 70 or life + 80). A work outside that rule needs a `pd_exception` that argues its case;
  two poems have one (宮沢賢治「雨ニモマケズ」, printed 1934, and 윤동주「서시」, printed 1948:
  both were already out of copyright at home on 1 January 1996, so the URAA restored no US
  copyright). Countries with longer terms (Mexico, life + 100) may differ for authors who died
  after 1925; every entry names its dates so this can be checked.
- **Sources**: only Wikisource (es, fr, zh, ja, ko) and Aozora Bunko (works it lists as out of
  copyright). Each entry names the page its text came from. No Project Gutenberg text is used, so
  no Gutenberg licence or trademark applies; no archive header, licence block, colophon or ruby
  markup is left in any file.
- **Credit**: the reader shows each entry's author, dates and the source's host name under the
  text (as plain text: the page loads nothing from outside).
- **Our additions**: the English lines of the poems and the readings are our own, written for
  this shelf (plain and literal, for learners); no published translation was used. Where an old
  edition's spelling was brought up to date, or a variant reading chosen, the entry's `note` or
  the file's header says so.
- **Size**: the whole shelf stays under 3 MB (it is about 0.3 MB).

## Adding an entry

Put the text in `<lang>/<slug>.txt` (or the poem in `<lang>/poems.yaml`), add its record with
every field (`title, author, died, published, first_published_in, level, source, public_domain`),
and run `python -m pytest -q tests/test_shelf.py`. Slugs are lower-case ASCII words joined by `-`
and never change once shipped: a reading position is kept under the id.
