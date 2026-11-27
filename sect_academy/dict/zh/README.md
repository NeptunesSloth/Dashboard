# Mandarin Chinese → English dictionary

`cedict_zh_en.tsv.gz` is the offline dictionary the reader looks Chinese words
up in (gzip of a UTF-8 text file, one entry per line, tab-separated, lines
starting with `#` are comments):

    simplified  traditional ("" if the same)  pinyin with tone numbers  gloss  flags  frequency

125,474 entries (4.0 MB). The gloss keeps every sense, in CC-CEDICT's order
(classifier "CL:" notes dropped, very long senses shortened, at most 500
characters), joined by "; ": 带 is "band; belt; … to wear; to carry; to take
along; … to bring". Flags: `w`
weak (the entry only says "variant of X", "surname X", "see X" or "used in X"),
`p` proper noun. The reader shows pinyin with tone marks (*xuéxí*) and also
finds a word typed with tone numbers (*xue2xi2*) or with no tones (*xuexi*).

**Source:** CC-CEDICT, published by MDBG,
https://www.mdbg.net/chinese/export/cedict/cedict_1_0_ts_utf-8_mdbg.txt.gz,
fetched 26 November 2026 (the file is dated 2026-11-24).

**Licence:** Creative Commons Attribution-ShareAlike 4.0 International
(CC BY-SA 4.0), https://creativecommons.org/licenses/by-sa/4.0/ — the text is
by the CC-CEDICT contributors (https://cc-cedict.org/). `cedict_zh_en.tsv.gz`
is a trimmed adaptation and is distributed under that licence, not under the
rest of this repository's terms: you may share and adapt it with attribution,
and what you build from it must carry the same licence.

**Frequencies:** CC-CEDICT has none, so the last column is the word count from
jieba's dictionary (`dict.txt` of jieba 0.42.1,
https://github.com/fxsjy/jieba), MIT licence:

    Copyright (c) 2013 Sun Junyi
    Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
    associated documentation files (the "Software"), to deal in the Software without restriction,
    including without limitation the rights to use, copy, modify, merge, publish, distribute,
    sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
    furnished to do so, subject to the following conditions: The above copyright notice and this
    permission notice shall be included in all copies or substantial portions of the Software.
    THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.

Only the counts are kept (one number per CEDICT headword); jieba's word list
itself is not shipped. The counts price words for the segmenter (common words
are cheap) and rank search results.

**How it was built:** `python scripts/build_dict_zh_ja.py --only zh` downloads
CC-CEDICT and jieba's dict.txt to a temporary folder, reads them as streams,
writes this file and deletes the downloads.

**Known gaps:**
- Pinyin is CC-CEDICT's citation tone: 一 is *yī* and 不 *bù* everywhere, without
  the tone changes of speech (*yí ge*, *bú shì*) that the course writes.
- A frequency belongs to a written word, not to a reading, so for a character
  with several readings (的 *de/dí/dì*, 了 *le/liǎo*) a short table in
  `lexicon/zh.py` names the usual one; the others are still listed.
- The segmenter joins what the dictionary lists as one word: 你好, 中国人,
  早上好 are one word here where the course's pinyin writes two. Personal and
  place names that are not in CC-CEDICT come out as single characters.
- Erhua (一点儿) and Taiwan-only words have thinner coverage.
