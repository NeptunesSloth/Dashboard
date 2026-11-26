"""The commonest words of every reader language get the right first meaning (lists in tests/lexicon_common.py),
and what a playtest of 107 taps found wrong stays fixed."""
import sys
from pathlib import Path

import pytest

from sect_academy.lexicon import es, fr, ja, ko, zh

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lexicon_common  # noqa: E402


@pytest.mark.parametrize("lang", list(lexicon_common.LISTS))
def test_common_words_have_the_right_first_meaning(lang):
    ok, n, bad = lexicon_common.accuracy(lang)
    assert n >= 150
    assert not bad, f"{lang}: {ok}/{n}\n" + "\n".join(bad)


# ---------------------------------------------------------------- Spanish
def test_spanish_function_words_have_learner_glosses():
    assert "direct object" in es.lookup("lo")["senses"][0]["text"] and "lo bueno" in es.lookup("lo")["senses"][0]["text"]
    assert es.lookup("le")["senses"][0]["src"] == "core" and "to him" in es.lookup("le")["senses"][0]["text"]
    assert "his, her" in es.lookup("su")["senses"][0]["text"] and not es.lookup("su")["weak"]
    assert "a + el" in es.lookup("al")["senses"][0]["text"]
    assert "us" in es.lookup("nos")["senses"][0]["text"].split(", ")[0]
    for w in ("me", "lo", "os"):
        assert es.lookup(w)["found"], w


def test_spanish_keeps_every_part_of_speech_and_reads_verb_forms_as_the_verb():
    ido = es.lookup("ido")
    assert ido["lemma"] == "ir" and ido["gram"] == "ir, past participle"
    assert "ido" in [a["lemma"] for a in ido["also"]]                 # the adjective is still offered
    fue = es.lookup("fue")
    assert fue["lemma"] == "ser" and fue["gram"].startswith("ser / ir, preterite, 3rd person singular")
    assert "ir" in [a["lemma"] for a in fue["also"]]
    assert {s.get("pos") for s in es.lookup("como")["senses"] if s["src"] == "wiktionary"} >= {"adv", "conj"}
    assert es.lookup("vino")["senses"][0]["text"] == "wine" and "venir" in [a["lemma"] for a in es.lookup("vino")["also"]]


@pytest.mark.parametrize("word,gram", [
    ("hablábamos", "hablar, imperfect, 1st person plural (nosotros)"),
    ("tengo", "tener, present, 1st person singular (yo)"),
    ("era", "ser, imperfect, 1st/3rd person singular"),
    ("dímelo", "decir, imperative, 2nd person singular (tú) + me + lo"),
    ("hay", "haber, present, 3rd person singular"),
])
def test_spanish_conjugated_forms_say_tense_and_person(word, gram):
    assert es.lookup(word)["gram"].startswith(gram)


def test_spanish_names_and_initialisms_are_weak():
    assert "initialism" not in es.lookup("al")["senses"][0]["text"]
    assert es.lookup("casas")["lemma"] == "casa" and not es.lookup("casas")["gram"]     # a noun's plural: no verb grammar


# ---------------------------------------------------------------- French
def test_french_common_noun_before_the_place_name():
    r = fr.lookup("l'hôpital")
    assert r["lemma"] == "hôpital" and r["senses"][0]["text"] == "hospital" and r["how"] == "elision"
    toks = [t["t"] for t in fr.segment("Il va à l'hôpital.")]
    assert "l'" in toks and "hôpital" in toks


def test_french_elided_pronoun_pairs_are_both_words():
    r = fr.lookup("qu'elle")
    assert r["lemma"] == "elle" and r["gram"] == "qu' = que + elle"
    assert any(s["text"].startswith("que — ") for s in r["senses"])
    assert fr.lookup("s'il")["gram"] == "s' = si + il"
    assert [t["k"] for t in fr.segment("Je sais qu'elle vient.") if t["k"]] == ["je", "sais", "qu'", "elle", "vient"]


def test_french_also_leaves_out_rare_words_names_and_abbreviations():
    assert "étayer" not in [a["lemma"] for a in fr.lookup("étaient")["also"]]
    assert "nord-est" not in [a["lemma"] for a in fr.lookup("ne")["also"]]
    assert not any("lira" in s["text"] for s in fr.lookup("lue")["senses"])     # a verb form: the verb's senses only
    assert "est" in [a["lemma"] for a in fr.lookup("est")["also"]]              # east is common: still offered


@pytest.mark.parametrize("word,gram", [
    ("allons", "aller, present, 1st person plural (nous)"),
    ("fut", "être, simple past (passé simple), 3rd person singular"),
    ("mangeait", "manger, imperfect, 3rd person singular"),
    ("parlé", "parler, past participle"),
    ("irons", "aller, future, 1st person plural"),
    ("j'", "j' = je (I)"),
])
def test_french_conjugated_forms_say_tense_and_person(word, gram):
    assert fr.lookup(word)["gram"].startswith(gram)


def test_french_function_words_lead_with_a_learner_gloss():
    for w in ("le", "la", "les", "de", "du", "des", "au", "aux", "y", "en", "ne", "que", "qui", "se", "lui", "leur"):
        assert fr.lookup(w)["senses"][0]["src"] == "core", w


# ---------------------------------------------------------------- Chinese
def test_chinese_keeps_every_sense_in_cedict_order():
    dai = zh.lookup("带")["senses"][0]["text"]
    assert dai.startswith("band; belt") and "to carry" in dai and "to bring" in dai
    assert "however" in zh.lookup("不过")["senses"][0]["text"]


def test_chinese_common_reading_first_and_day_names_whole():
    assert zh.lookup("雨")["reading"] == "yǔ" and zh.lookup("雨")["senses"][1]["read"] == "yù"
    assert [t["t"] for t in zh.segment("上个星期六我去了。")][:2] == ["上个", "星期六"]
    assert [t["t"] for t in zh.segment("上个星期他很忙。")][0] == "上个星期"


# ---------------------------------------------------------------- Japanese
def test_japanese_particles_split_off_an_uncommon_expression():
    assert [t["t"] for t in ja.segment("写真を撮りました。")] == ["写真", "を", "撮りました", "。"]
    assert [t["t"] for t in ja.segment("気に入りました")] == ["気に入りました"]    # a common entry stays whole
    assert ja.lookup("写真を撮りました")["rom"] == "shashin o toru"


def test_japanese_also_has_no_single_kanji_for_a_word_of_several():
    assert not [a for a in ja.lookup("銀行")["also"] if a["how"] == "character"]
    assert [a["lemma"] for a in ja.lookup("食べました")["also"] if a["how"] == "character"] == ["食"]


def test_japanese_kana_homographs_read_as_the_everyday_word():
    assert ja.lookup("きのう")["senses"][0]["text"].startswith("yesterday")
    assert ja.lookup("みず")["lemma"] == "みず"                       # water, not 見る + -ず


# ---------------------------------------------------------------- Korean
def test_korean_homographs_usual_word_first():
    r = ko.lookup("시장")
    assert [s["text"] for s in r["senses"]][:2] == ["market", "mayor"]
    assert ko.lookup("시장에서")["senses"][0]["text"] == "market"
    assert [s["text"] for s in ko.lookup("눈")["senses"]][1] == "snow"
    assert ko.lookup("삼만")["senses"][0]["text"] == "30,000"
