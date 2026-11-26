# Spanish → English dictionary

`es_en.tsv.gz` is the offline dictionary the reader looks words up in
(gzip of a UTF-8 text file, one entry per line, tab-separated):

    L <tab> lemma <tab> English gloss     (84,893 lines; senses separated by "; ")
    F <tab> form  <tab> lemma             (133,319 lines: plurals, conjugations,
                                           verb forms with pronouns attached, ...)

**Source:** Wiktionary data (CC BY-SA), compiled by doozan/spanish_data
(https://github.com/doozan/spanish_data). It was taken unchanged from the
owner's offline "Aprende" app, which shipped the same file.

**Licence:** Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/ — the text is
by the Wiktionary contributors, via doozan/spanish_data. `es_en.tsv.gz` is
distributed under that licence (it is not covered by the rest of this
repository's terms): you may share and adapt it with attribution, and anything
you build from it must carry the same licence.

Known limits of the data: where a common word and a proper noun share a
spelling, the compiled list sometimes kept only the name ("año" → "surname",
"casas" → "surname"). The reader treats a gloss that is only "surname" or
"given name" as weak, keeps looking (so "casas" finds "casa"), and also
consults the short list below.

`core_es_en.tsv` (same `L` format, about 200 lines) is the owner's own core
word list from the Aprende app (everyday words such as año = year). It is
shown as a second sense next to the Wiktionary gloss.

Your own entries (word + meaning, added in the app) live in the state file,
not here.
