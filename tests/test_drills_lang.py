"""Language drills: verb forms (es, fr from the dictionary data; ja, ko conjugated here), numbers, times, dates,
prices and counters in all five languages, and how answers are graded.

The expected forms below are written by hand, not read from the data, so they check it."""
import random

import pytest

from sect_academy import drills, drills_lang as L, drills_num as N

# ---------------------------------------------------------------------------
# Spanish: verb · tense · person · form
# ---------------------------------------------------------------------------
ES = """
ser pres 1s soy|ser pres 2s eres|ser pres 3s es|ser pres 1p somos|ser pres 2p sois|ser pres 3p son|ser pret 1s fui|ser pret 3s fue
ser pret 1p fuimos|ser pret 3p fueron|ser impf 1s era|ser impf 1p éramos|ser impf 3p eran|ser fut 1s seré|ser cond 3s sería
ser subj 1s sea|ser subj 1p seamos|ser subjimpf 3s fuera|ser imp 2s sé|ser imp 2p sed
estar pres 1s estoy|estar pres 2s estás|estar pres 3p están|estar pret 1s estuve|estar pret 3s estuvo|estar pret 1p estuvimos
estar pret 3p estuvieron|estar subj 1s esté|estar subj 3p estén|estar subjimpf 1s estuviera|estar imp 2s está
tener pres 1s tengo|tener pres 2s tienes|tener pres 3s tiene|tener pres 1p tenemos|tener pret 1s tuve|tener pret 3s tuvo
tener pret 3p tuvieron|tener fut 1s tendré|tener fut 3p tendrán|tener cond 1s tendría|tener subj 1s tenga|tener imp 2s ten
tener subjimpf 3s tuviera
hacer pres 1s hago|hacer pres 3s hace|hacer pret 1s hice|hacer pret 3s hizo|hacer pret 1p hicimos|hacer fut 1s haré|hacer fut 2s harás
hacer cond 3s haría|hacer subj 1s haga|hacer imp 2s haz|hacer subjimpf 1s hiciera
poder pres 1s puedo|poder pres 1p podemos|poder pres 3p pueden|poder pret 1s pude|poder pret 3s pudo|poder fut 1s podré
poder cond 3s podría|poder subj 2s puedas|poder subjimpf 3s pudiera
decir pres 1s digo|decir pres 2s dices|decir pres 1p decimos|decir pret 1s dije|decir pret 3s dijo|decir pret 3p dijeron
decir fut 1s diré|decir cond 1p diríamos|decir subj 1s diga|decir imp 2s di|decir subjimpf 3s dijera
ir pres 1s voy|ir pres 2s vas|ir pres 3s va|ir pres 1p vamos|ir pres 2p vais|ir pres 3p van|ir pret 1s fui|ir pret 2s fuiste
ir pret 1p fuimos|ir pret 2p fuisteis|ir impf 1s iba|ir impf 1p íbamos|ir fut 1s iré|ir cond 3s iría|ir subj 1s vaya
ir subj 1p vayamos|ir subjimpf 3p fueran|ir imp 2s ve|ir imp 2p id|ir imp 3s vaya
ver pres 1s veo|ver pres 2s ves|ver pret 1s vi|ver pret 3s vio|ver impf 1s veía|ver impf 1p veíamos|ver fut 1s veré|ver subj 1s vea
ver imp 2s ve
dar pres 1s doy|dar pres 2s das|dar pret 1s di|dar pret 3s dio|dar pret 3p dieron|dar subj 1s dé|dar subj 3s dé|dar subjimpf 1s diera
saber pres 1s sé|saber pres 2s sabes|saber pret 1s supe|saber pret 3s supo|saber fut 1s sabré|saber cond 1s sabría|saber subj 1s sepa
saber subj 1p sepamos
querer pres 1s quiero|querer pres 1p queremos|querer pret 1s quise|querer pret 3s quiso|querer fut 1s querré|querer cond 3s querría
querer subj 3s quiera
poner pres 1s pongo|poner pret 1s puse|poner pret 3s puso|poner fut 1s pondré|poner imp 2s pon|poner subj 1s ponga
venir pres 1s vengo|venir pres 2s vienes|venir pres 1p venimos|venir pret 1s vine|venir pret 3s vino|venir pret 1p vinimos
venir fut 1s vendré|venir imp 2s ven|venir subj 1s venga
salir pres 1s salgo|salir fut 1s saldré|salir imp 2s sal|salir subj 1s salga|salir pret 1s salí
hablar pres 1s hablo|hablar pres 2s hablas|hablar pres 3s habla|hablar pres 1p hablamos|hablar pres 2p habláis|hablar pres 3p hablan
hablar pret 1s hablé|hablar pret 2s hablaste|hablar pret 3s habló|hablar pret 3p hablaron|hablar impf 1s hablaba
hablar impf 1p hablábamos|hablar fut 1s hablaré|hablar fut 3s hablará|hablar cond 2s hablarías|hablar subj 1s hable
hablar subj 2p habléis|hablar subjimpf 1s hablara|hablar imp 2s habla|hablar imp 2p hablad|hablar imp 3s hable|hablar imp 3p hablen
comer pres 1s como|comer pres 2p coméis|comer pret 1s comí|comer pret 3s comió|comer pret 3p comieron|comer impf 1s comía
comer subj 1s coma|comer imp 2s come|comer imp 2p comed
vivir pres 1s vivo|vivir pres 1p vivimos|vivir pres 2p vivís|vivir pret 1s viví|vivir pret 3s vivió|vivir impf 1p vivíamos
vivir subj 3p vivan|vivir imp 2p vivid
pensar pres 1s pienso|pensar pres 1p pensamos|pensar pres 3p piensan|pensar subj 1s piense
volver pres 1s vuelvo|volver pres 1p volvemos|volver subj 3s vuelva|volver imp 2s vuelve
dormir pres 1s duermo|dormir pres 1p dormimos|dormir pret 3s durmió|dormir pret 3p durmieron|dormir subj 1p durmamos
pedir pres 1s pido|pedir pres 1p pedimos|pedir pret 3s pidió|pedir pret 3p pidieron|pedir subj 1s pida|pedir imp 2s pide
sentir pres 1s siento|sentir pret 3s sintió|sentir subj 1p sintamos
seguir pres 1s sigo|seguir pres 2s sigues|seguir pret 3s siguió|seguir subj 1s siga
conocer pres 1s conozco|conocer subj 1s conozca|conducir pres 1s conduzco|conducir pret 1s conduje|conducir pret 3p condujeron
traer pres 1s traigo|traer pret 1s traje|traer pret 3p trajeron|caer pres 1s caigo|caer pret 3s cayó|caer pret 3p cayeron
leer pret 3s leyó|leer pret 3p leyeron|leer impf 1s leía|oír pres 1s oigo|oír pres 2s oyes|oír pres 1p oímos|oír pret 3s oyó
jugar pres 1s juego|jugar pres 1p jugamos|jugar pret 1s jugué|jugar subj 1s juegue|buscar pret 1s busqué|buscar subj 1s busque
pagar pret 1s pagué|pagar subj 3s pague|empezar pres 1s empiezo|empezar pret 1s empecé|empezar subj 1s empiece
construir pres 1s construyo|construir pret 3s construyó|morir pret 3s murió|morir pres 1s muero|andar pret 1s anduve
andar pret 3p anduvieron|caber pres 1s quepo|caber pret 1s cupe|caber fut 1s cabré|valer pres 1s valgo|valer fut 1s valdré
reír pres 1s río|reír pres 1p reímos|elegir pres 1s elijo|elegir subj 1s elija|coger pres 1s cojo|huir pres 1s huyo
huir pret 3s huyó|oler pres 1s huelo|contar pres 1s cuento|costar pres 3s cuesta|mover pres 3s mueve|traducir pret 1s traduje
producir pres 1s produzco|obtener pres 1s obtengo|obtener pret 1s obtuve|proponer pret 1s propuse|mantener imp 2s mantén
despertar pres 1s despierto|negar pret 1s negué|dirigir pres 1s dirijo
"""

FR = """
être pres 1s suis|être pres 2s es|être pres 3s est|être pres 1p sommes|être pres 2p êtes|être pres 3p sont|être impf 1s étais
être impf 1p étions|être fut 1s serai|être fut 3p seront|être cond 1s serais|être subj 1s sois|être subj 3s soit
être subj 1p soyons|être imp 2s sois|être imp 2p soyez
avoir pres 1s ai|avoir pres 2s as|avoir pres 3s a|avoir pres 1p avons|avoir pres 2p avez|avoir pres 3p ont|avoir impf 3s avait
avoir fut 1s aurai|avoir fut 2p aurez|avoir cond 3s aurait|avoir subj 1s aie|avoir subj 3s ait|avoir subj 1p ayons|avoir imp 2s aie
avoir imp 2p ayez
aller pres 1s vais|aller pres 2s vas|aller pres 3s va|aller pres 1p allons|aller pres 2p allez|aller pres 3p vont|aller impf 1s allais
aller fut 1s irai|aller fut 1p irons|aller cond 3s irait|aller subj 1s aille|aller subj 1p allions|aller subj 3p aillent|aller imp 2s va
faire pres 1s fais|faire pres 3s fait|faire pres 1p faisons|faire pres 2p faites|faire pres 3p font|faire impf 1p faisions
faire fut 1s ferai|faire fut 3p feront|faire cond 1s ferais|faire subj 1s fasse|faire subj 1p fassions|faire imp 2p faites
dire pres 1s dis|dire pres 1p disons|dire pres 2p dites|dire pres 3p disent|dire fut 1s dirai|dire subj 3s dise
pouvoir pres 1s peux|pouvoir pres 3s peut|pouvoir pres 1p pouvons|pouvoir pres 3p peuvent|pouvoir fut 1s pourrai
pouvoir cond 3s pourrait|pouvoir subj 1s puisse
vouloir pres 1s veux|vouloir pres 3s veut|vouloir pres 1p voulons|vouloir pres 3p veulent|vouloir fut 1s voudrai
vouloir cond 1s voudrais|vouloir subj 1s veuille|vouloir imp 2p veuillez
savoir pres 1s sais|savoir pres 3s sait|savoir pres 1p savons|savoir fut 1s saurai|savoir subj 1s sache|savoir subj 1p sachions
savoir imp 2s sache|savoir imp 2p sachez
venir pres 1s viens|venir pres 3s vient|venir pres 1p venons|venir pres 3p viennent|venir fut 1s viendrai|venir subj 1s vienne
venir subj 1p venions
voir pres 1s vois|voir pres 1p voyons|voir pres 3p voient|voir impf 1p voyions|voir fut 1s verrai|voir subj 1s voie
devoir pres 1s dois|devoir pres 1p devons|devoir pres 3p doivent|devoir fut 1s devrai|devoir subj 1s doive
prendre pres 1s prends|prendre pres 3s prend|prendre pres 1p prenons|prendre pres 3p prennent|prendre subj 1s prenne
mettre pres 1s mets|mettre pres 3s met|mettre pres 1p mettons
parler pres 1s parle|parler pres 2s parles|parler pres 1p parlons|parler pres 2p parlez|parler pres 3p parlent
parler impf 1s parlais|parler impf 3p parlaient|parler fut 1s parlerai|parler fut 1p parlerons|parler cond 3s parlerait
parler cond 1p parlerions|parler subj 1p parlions|parler subj 2p parliez|parler imp 2s parle|parler imp 1p parlons
finir pres 1s finis|finir pres 3s finit|finir pres 1p finissons|finir pres 3p finissent|finir impf 1s finissais|finir fut 1s finirai
finir subj 1s finisse|finir imp 2s finis
vendre pres 1s vends|vendre pres 3s vend|vendre pres 1p vendons|vendre pres 3p vendent|vendre fut 1s vendrai|vendre subj 1s vende
manger pres 1p mangeons|manger impf 1s mangeais|manger impf 3p mangeaient|manger pres 3p mangent
commencer pres 1p commençons|commencer impf 3s commençait
appeler pres 1s appelle|appeler pres 1p appelons|appeler pres 3p appellent|appeler fut 1s appellerai
jeter pres 1s jette|jeter pres 1p jetons|acheter pres 1s achète|acheter pres 1p achetons|acheter fut 1s achèterai
préférer pres 1s préfère|préférer pres 1p préférons|envoyer pres 1s envoie|envoyer fut 1s enverrai|payer pres 1p payons
boire pres 1s bois|boire pres 1p buvons|boire pres 3p boivent|croire pres 1p croyons|croire pres 3p croient
écrire pres 1s écris|écrire pres 1p écrivons|lire pres 1s lis|lire pres 1p lisons|dormir pres 1s dors|dormir pres 1p dormons
partir pres 1s pars|partir pres 3s part|partir pres 1p partons|sortir pres 1s sors|ouvrir pres 1s ouvre|ouvrir pres 1p ouvrons
recevoir pres 1s reçois|recevoir pres 1p recevons|recevoir pres 3p reçoivent|recevoir fut 1s recevrai
connaître pres 1s connais|connaître pres 3s connaît|connaître pres 1p connaissons|vivre pres 1s vis|vivre pres 1p vivons
suivre pres 1s suis|suivre pres 1p suivons|courir pres 1s cours|courir fut 1s courrai|mourir pres 3s meurt|mourir fut 1s mourrai
tenir pres 1s tiens|tenir fut 1s tiendrai|craindre pres 1s crains|craindre pres 1p craignons|peindre pres 1p peignons
rire pres 1s ris|rire pres 1p rions|conduire pres 1p conduisons|naître pres 3s naît|valoir pres 3s vaut|plaire pres 3s plaît
battre pres 3s bat|mourir imp 2s meurs
"""
FR_PC = """
aller elle|elle est allée;aller je|je suis allé;aller nous|nous sommes allés;aller ils|ils sont allés;aller elles|elles sont allées
venir il|il est venu;venir elle|elle est venue;arriver elles|elles sont arrivées;partir tu|tu es parti;naître elle|elle est née
mourir il|il est mort;mourir elle|elle est morte;tomber nous|nous sommes tombés;rester vous|vous êtes restés
devenir elle|elle est devenue;descendre il|il est descendu;sortir elles|elles sont sorties;entrer je|je suis entré
parler je|j'ai parlé;parler nous|nous avons parlé;faire il|il a fait;prendre elle|elle a pris;mettre ils|ils ont mis;voir tu|tu as vu
avoir je|j'ai eu;être nous|nous avons été;boire vous|vous avez bu;écrire elle|elle a écrit;ouvrir il|il a ouvert;finir ils|ils ont fini
lire je|j'ai lu;dire elles|elles ont dit;vivre il|il a vécu;recevoir elle|elle a reçu;offrir je|j'ai offert;courir il|il a couru
craindre nous|nous avons craint;naître ils|ils sont nés;revenir elles|elles sont revenues;connaître je|j'ai connu
"""
CODE = {lang: {k: c for k, c, *_ in L.TENSES[lang]} for lang in ("es", "fr")}


def _rows(text: str, sep: str = "|") -> list[list[str]]:
    return [r.split() for line in text.strip().splitlines() for r in line.split(sep) if r.strip()]


@pytest.mark.parametrize("lang,text", [("es", ES), ("fr", FR)])
def test_spanish_and_french_forms_from_the_dictionary_match_hand_known_ones(lang, text):
    rows = _rows(text)
    assert len(rows) >= (200 if lang == "es" else 160)
    wrong = []
    for verb, tense, person, form in rows:
        cells = L.paradigm(lang, verb)
        got = cells.get((CODE[lang][tense], person), [])
        if not got or got[0] != form:
            wrong.append((verb, tense, person, form, got))
    assert not wrong, wrong


def test_french_passe_compose_uses_the_right_auxiliary_and_agrees_after_etre():
    rows = [line.split("|") for chunk in FR_PC.strip().splitlines() for line in chunk.split(";")]
    assert len(rows) >= 40
    for head, want in rows:
        verb, pron = head.split()
        got = L.fr_passe_compose(verb, pron)
        assert got and got[0] == want, (verb, pron, got)
    assert "je suis allée" in L.fr_passe_compose("aller", "je")           # a woman speaking
    assert set(L.fr_passe_compose("aller", "vous")) >= {"vous êtes allés", "vous êtes allée"}
    assert L.fr_passe_compose("parler", "elle") == ["elle a parlé"]      # no agreement with avoir
    assert len(_rows(FR)) + len(rows) >= 200


def test_bad_data_cells_are_neither_asked_nor_accepted():
    assert L.paradigm("es", "ser")[("ind.pres", "1s")] == ["soy"]
    assert L.paradigm("es", "ir")[("imp", "2p")] == ["id"]               # not *idos
    assert L.paradigm("fr", "aller")[("ind.pres", "1s")] == ["vais"]     # not *je vas
    assert L.paradigm("fr", "aller")[("pp", "")][0] == "allé"
    assert L.paradigm("fr", "valoir")[("subj.pres", "3p")] == ["vaillent"]
    assert all("illir" not in f for f in L.paradigm("fr", "cueillir")[("ind.fut", "1s")])
    assert "mangeont" not in str(L.paradigm("fr", "manger"))
    assert "essaie" in L.paradigm("fr", "essayer")[("ind.pres", "1s")]   # real variants stay accepted


def test_every_listed_verb_has_its_main_cells():
    for lang, verbs in (("es", L.ES_VERBS), ("fr", L.FR_VERBS)):
        assert len(verbs) == len(set(verbs)) >= 140
        for v in verbs:
            cells = L.paradigm(lang, v)
            assert ("ind.pres", "1p") in cells and ("ind.impf", "3s") in cells, (lang, v)


# ---------------------------------------------------------------------------
# Japanese
# ---------------------------------------------------------------------------
JA = """
食べる 食べます 食べて 食べない 食べた 食べられる 食べよう 食べれば
見る 見ます 見て 見ない 見た 見られる 見よう 見れば
起きる 起きます 起きて 起きない 起きた 起きられる 起きよう 起きれば
寝る 寝ます 寝て 寝ない 寝た 寝られる 寝よう 寝れば
教える 教えます 教えて 教えない 教えた 教えられる 教えよう 教えれば
書く 書きます 書いて 書かない 書いた 書ける 書こう 書けば
聞く 聞きます 聞いて 聞かない 聞いた 聞ける 聞こう 聞けば
行く 行きます 行って 行かない 行った 行ける 行こう 行けば
泳ぐ 泳ぎます 泳いで 泳がない 泳いだ 泳げる 泳ごう 泳げば
急ぐ 急ぎます 急いで 急がない 急いだ 急げる 急ごう 急げば
話す 話します 話して 話さない 話した 話せる 話そう 話せば
出す 出します 出して 出さない 出した 出せる 出そう 出せば
待つ 待ちます 待って 待たない 待った 待てる 待とう 待てば
持つ 持ちます 持って 持たない 持った 持てる 持とう 持てば
死ぬ 死にます 死んで 死なない 死んだ 死ねる 死のう 死ねば
遊ぶ 遊びます 遊んで 遊ばない 遊んだ 遊べる 遊ぼう 遊べば
呼ぶ 呼びます 呼んで 呼ばない 呼んだ 呼べる 呼ぼう 呼べば
読む 読みます 読んで 読まない 読んだ 読める 読もう 読めば
飲む 飲みます 飲んで 飲まない 飲んだ 飲める 飲もう 飲めば
買う 買います 買って 買わない 買った 買える 買おう 買えば
会う 会います 会って 会わない 会った 会える 会おう 会えば
言う 言います 言って 言わない 言った 言える 言おう 言えば
帰る 帰ります 帰って 帰らない 帰った 帰れる 帰ろう 帰れば
入る 入ります 入って 入らない 入った 入れる 入ろう 入れば
走る 走ります 走って 走らない 走った 走れる 走ろう 走れば
切る 切ります 切って 切らない 切った 切れる 切ろう 切れば
作る 作ります 作って 作らない 作った 作れる 作ろう 作れば
来る 来ます 来て 来ない 来た 来られる 来よう 来れば
する します して しない した できる しよう すれば
勉強する 勉強します 勉強して 勉強しない 勉強した 勉強できる 勉強しよう 勉強すれば
"""
JA_ORDER = ("masu", "te", "nai", "ta", "pot", "vol", "ba")
JA_CLASS = {"食べる": "v1", "見る": "v1", "着る": "v1", "書く": "v5k", "行く": "v5k-s", "泳ぐ": "v5g", "話す": "v5s", "待つ": "v5t",
            "死ぬ": "v5n", "遊ぶ": "v5b", "読む": "v5m", "買う": "v5u", "帰る": "v5r", "入る": "v5r", "切る": "v5r", "走る": "v5r",
            "来る": "vk", "する": "vs", "勉強する": "vs"}


def test_japanese_classes_come_from_jmdict():
    for w, cls in JA_CLASS.items():
        assert L.ja_class(w) == cls, w
    assert all(L.ja_class(w) for w, _, _ in L.JA_VERBS)


def test_japanese_conjugations_match_hand_known_forms():
    kana = {w: k for w, k, _ in L.JA_VERBS}
    n = 0
    for line in JA.strip().splitlines():
        word, *forms = line.split()
        for form, want in zip(JA_ORDER, forms):
            assert L.ja_conjugate(word, kana[word], form)[0] == want, (word, form)
            n += 1
    assert n >= 200
    # readings, where the kanji hides the change
    assert [L.ja_conjugate("来る", "くる", f)[1] for f in JA_ORDER] == ["きます", "きて", "こない", "きた", "こられる", "こよう", "くれば"]
    assert L.ja_conjugate("食べる", "たべる", "masen")[0] == "食べません"
    assert L.ja_conjugate("行く", "いく", "mashita")[1] == "いきました"


def test_japanese_answers_accept_kana_and_romaji():
    q = L._ask_ja(random.Random(1), ["来る", "くる", "come"], ("nai", "ない form (negative)"))
    for ans in ("来ない", "こない", "konai", "ko nai"):
        assert drills.grade(q, ans)[0], ans
    assert not drills.grade(q, "kinai")[0]
    q = L._ask_ja(random.Random(1), ["食べる", "たべる", "eat"], ("vol", "volitional"))
    assert drills.grade(q, "tabeyou")[0] and drills.grade(q, "tabeyō")[0] and drills.grade(q, "たべよう")[0]
    assert not drills.grade(q, "tabero")[0]


# ---------------------------------------------------------------------------
# Korean
# ---------------------------------------------------------------------------
KO = """
가다 가요 갔어요 갈_거예요 갑니다 가고_싶어요|오다 와요 왔어요 올_거예요 옵니다 오고_싶어요
보다 봐요 봤어요 볼_거예요 봅니다 보고_싶어요|주다 줘요 줬어요 줄_거예요 줍니다 주고_싶어요
하다 해요 했어요 할_거예요 합니다 하고_싶어요|먹다 먹어요 먹었어요 먹을_거예요 먹습니다 먹고_싶어요
마시다 마셔요 마셨어요 마실_거예요 마십니다 마시고_싶어요|읽다 읽어요 읽었어요 읽을_거예요 읽습니다 읽고_싶어요
쓰다 써요 썼어요 쓸_거예요 씁니다 쓰고_싶어요|듣다 들어요 들었어요 들을_거예요 듣습니다 듣고_싶어요
걷다 걸어요 걸었어요 걸을_거예요 걷습니다 걷고_싶어요|묻다 물어요 물었어요 물을_거예요 묻습니다 묻고_싶어요
살다 살아요 살았어요 살_거예요 삽니다 살고_싶어요|알다 알아요 알았어요 알_거예요 압니다 알고_싶어요
만들다 만들어요 만들었어요 만들_거예요 만듭니다 만들고_싶어요|놀다 놀아요 놀았어요 놀_거예요 놉니다 놀고_싶어요
열다 열어요 열었어요 열_거예요 엽니다 열고_싶어요|웃다 웃어요 웃었어요 웃을_거예요 웃습니다 웃고_싶어요
씻다 씻어요 씻었어요 씻을_거예요 씻습니다 씻고_싶어요|입다 입어요 입었어요 입을_거예요 입습니다 입고_싶어요
돕다 도와요 도왔어요 도울_거예요 돕습니다 돕고_싶어요|받다 받아요 받았어요 받을_거예요 받습니다 받고_싶어요
배우다 배워요 배웠어요 배울_거예요 배웁니다 배우고_싶어요|가르치다 가르쳐요 가르쳤어요 가르칠_거예요 가르칩니다 가르치고_싶어요
보내다 보내요 보냈어요 보낼_거예요 보냅니다 보내고_싶어요|기다리다 기다려요 기다렸어요 기다릴_거예요 기다립니다 기다리고_싶어요
되다 돼요 됐어요 될_거예요 됩니다 되고_싶어요|쉬다 쉬어요 쉬었어요 쉴_거예요 쉽니다 쉬고_싶어요
앉다 앉아요 앉았어요 앉을_거예요 앉습니다 앉고_싶어요|공부하다 공부해요 공부했어요 공부할_거예요 공부합니다 공부하고_싶어요
부르다 불러요 불렀어요 부를_거예요 부릅니다 부르고_싶어요|고르다 골라요 골랐어요 고를_거예요 고릅니다 고르고_싶어요
짓다 지어요 지었어요 지을_거예요 짓습니다 짓고_싶어요|낫다 나아요 나았어요 나을_거예요 낫습니다 낫고_싶어요
끄다 꺼요 껐어요 끌_거예요 끕니다 끄고_싶어요
춥다 추워요 추웠어요 추울_거예요 춥습니다|덥다 더워요 더웠어요 더울_거예요 덥습니다|쉽다 쉬워요 쉬웠어요 쉬울_거예요 쉽습니다
어렵다 어려워요 어려웠어요 어려울_거예요 어렵습니다|가깝다 가까워요 가까웠어요 가까울_거예요 가깝습니다
빠르다 빨라요 빨랐어요 빠를_거예요 빠릅니다|다르다 달라요 달랐어요 다를_거예요 다릅니다|모르다 몰라요 몰랐어요 모를_거예요 모릅니다
바쁘다 바빠요 바빴어요 바쁠_거예요 바쁩니다|아프다 아파요 아팠어요 아플_거예요 아픕니다|예쁘다 예뻐요 예뻤어요 예쁠_거예요 예쁩니다
크다 커요 컸어요 클_거예요 큽니다|그렇다 그래요 그랬어요 그럴_거예요 그렇습니다|빨갛다 빨개요 빨갰어요 빨갈_거예요 빨갛습니다
하얗다 하얘요 하얬어요 하얄_거예요 하얗습니다|어떻다 어때요 어땠어요 어떨_거예요 어떻습니다|좋다 좋아요 좋았어요 좋을_거예요 좋습니다
길다 길어요 길었어요 길_거예요 깁니다|멀다 멀어요 멀었어요 멀_거예요 멉니다|있다 있어요 있었어요 있을_거예요 있습니다
"""


def test_korean_conjugations_match_hand_known_forms():
    cls = {w: c for w, c, _, _ in L.KO_VERBS}
    n = 0
    for word, *forms in _rows(KO):
        for form, want in zip(("pres", "past", "fut", "formal", "want"), forms):
            assert L.ko_conjugate(word, cls[word], form)[0] == want.replace("_", " "), (word, form)
            n += 1
    assert n >= 200


def test_korean_answers_accept_hangul_and_romanisation():
    q = L._ask_ko(random.Random(1), ["듣다", "d", "v", "listen"], ("past", "polite past"))
    for ans in ("들었어요", "들 었 어 요", "deureosseoyo"):
        assert drills.grade(q, ans)[0], ans
    assert not drills.grade(q, "듣었어요")[0]
    q = L._ask_ko(random.Random(1), ["먹다", "r", "v", "eat"], ("formal", "formal"))
    assert drills.grade(q, "meokseumnida")[0] and drills.grade(q, "meogseubnida")[0]
    assert L._ask_ko(random.Random(1), ["춥다", "b", "a", "be cold"], ("want", "want to")) is None   # adjectives have no -고 싶어요
    assert L.ko_conjugate("보다", "r", "pres") == ["봐요", "보아요"] and L.ko_conjugate("오다", "r", "pres") == ["와요"]


# ---------------------------------------------------------------------------
# numbers
# ---------------------------------------------------------------------------
def test_spanish_numbers():
    assert [N.es_words(n) for n in (1, 21, 100, 101, 1000)] == ["uno", "veintiuno", "cien", "ciento uno", "mil"]
    assert N.es_words(1984) == "mil novecientos ochenta y cuatro"
    assert N.es_words(16) == "dieciséis" and N.es_words(22) == "veintidós" and N.es_words(26) == "veintiséis"
    assert N.es_words(500) == "quinientos" and N.es_words(700) == "setecientos" and N.es_words(900) == "novecientos"
    assert N.es_words(21000) == "veintiún mil" and N.es_words(100000) == "cien mil" and N.es_words(1000000) == "un millón"
    assert N.es_words(2000000) == "dos millones" and N.es_words(31) == "treinta y uno"
    assert N.es_words(1, "m") == "un" and N.es_words(1, "f") == "una"
    assert N.es_words(21, "m") == "veintiún" and N.es_words(21, "f") == "veintiuna" and N.es_words(31, "f") == "treinta y una"
    assert N.es_words(200, "f") == "doscientas" and N.es_words(501, "f") == "quinientas una"
    assert N.es_time(1, 0)[0][0] == "es la una" and N.es_time(3, 15)[0][0] == "son las tres y cuarto"
    assert N.es_time(3, 30)[0][0] == "son las tres y media" and N.es_time(3, 45)[0][0] == "son las cuatro menos cuarto"
    assert N.es_time(12, 45)[0][0] == "es la una menos cuarto" and N.es_time(7, 40)[0][0] == "son las ocho menos veinte"
    assert N.es_date(1, 5)[0] == ["el uno de mayo", "el primero de mayo"] and N.es_date(3, 5)[0] == ["el tres de mayo"]


def test_french_numbers():
    w = N.fr_words
    assert [w(n) for n in (70, 71, 72, 77, 79)] == ["soixante-dix", "soixante et onze", "soixante-douze", "soixante-dix-sept", "soixante-dix-neuf"]
    assert [w(n) for n in (80, 81, 89, 90, 91, 97, 99)] == ["quatre-vingts", "quatre-vingt-un", "quatre-vingt-neuf", "quatre-vingt-dix",
                                                         "quatre-vingt-onze", "quatre-vingt-dix-sept", "quatre-vingt-dix-neuf"]
    assert [w(n) for n in (21, 31, 41, 51, 61)] == ["vingt et un", "trente et un", "quarante et un", "cinquante et un", "soixante et un"]
    assert w(200) == "deux cents" and w(201) == "deux cent un" and w(280) == "deux cent quatre-vingts" and w(100) == "cent"
    assert w(1000) == "mille" and w(2000) == "deux mille" and w(80000) == "quatre-vingt mille" and w(200000) == "deux cent mille"
    assert w(1984) == "mille neuf cent quatre-vingt-quatre" and w(21, True) == "vingt et une" and w(81, True) == "quatre-vingt-une"
    assert N.fr_reform(w(1984)) == "mille-neuf-cent-quatre-vingt-quatre" and N.fr_reform(w(21)) == "vingt-et-un"
    assert N.fr_time(3, 15)[0][0] == "il est trois heures et quart" and N.fr_time(3, 30)[0][0] == "il est trois heures et demie"
    assert N.fr_time(3, 45)[0][0] == "il est quatre heures moins le quart" and N.fr_time(1, 0)[0][0] == "il est une heure"
    assert "il est midi" in N.fr_time(12, 0)[0] and N.fr_date(1, 5)[0] == ["le premier mai"]
    assert N.fr_date(21, 8)[0] == ["le vingt et un août"]


def test_chinese_numbers():
    assert N.zh_words(105) == "一百零五" and N.zh_words(1005) == "一千零五" and N.zh_words(1050) == "一千零五十"
    assert N.zh_words(110) == "一百一十" and N.zh_words(15) == "十五" and N.zh_words(10500) == "一万零五百"
    assert N.zh_words(100010) == "十万零一十" and N.zh_words(542) == "五百四十二" and N.zh_words(0) == "零"
    assert N.zh_variants(N.zh_words(2000)) == ["两千", "二千"] and N.zh_variants(N.zh_words(200)) == ["二百", "两百"]
    assert N.zh_variants(N.zh_words(22)) == ["二十二"] and N.zh_variants(N.zh_words(2)) == ["二"]       # never *两十
    assert N.zh_pinyin("五百四十二") == "wǔ bǎi sì shí èr"
    assert N.zh_pinyin("一百", True) == "yì bǎi" and N.zh_pinyin("一万", True) == "yí wàn" and N.zh_pinyin("十一", True) == "shí yī"
    assert N.zh_time(3, 15)[0][0] == "三点一刻" and N.zh_time(2, 0)[0][0] == "两点" and N.zh_time(3, 30)[0][0] == "三点半"
    assert N.zh_date(3, 5)[0][0] == "五月三号" and N.zh_date(2, 2)[0][0] == "二月二号"
    assert N.zh_price(2)[0][0] == "两块" and "二块" not in N.zh_price(2)[0]


def test_japanese_numbers():
    k = N.ja_kana
    assert [k(n) for n in (300, 600, 800, 1000, 3000, 8000)] == ["さんびゃく", "ろっぴゃく", "はっぴゃく", "せん", "さんぜん", "はっせん"]
    assert k(542) == "ごひゃくよんじゅうに" and k(10000) == "いちまん" and k(10000000) == "いっせんまん" and k(1600) == "せんろっぴゃく"
    assert N.ja_kanji(542) == "五百四十二" and N.ja_kanji(1000) == "千" and N.ja_kanji(11000) == "一万一千"
    assert "し" in N.ja_kana_variants(4) and "しち" in N.ja_kana_variants(7) and "く" in N.ja_kana_variants(9)
    assert N.ja_price(3000)[0] == ["さんぜんえん"] and N.ja_price(4)[0] == ["よえん"] and N.ja_price(14)[0] == ["じゅうよえん"]
    assert N.ja_price(100)[0] == ["ひゃくえん"]
    assert N.ja_time(3, 15)[1][0] == "三時十五分" and N.ja_time(3, 15)[0] == ["さんじじゅうごふん"]
    assert N.ja_time(4, 0)[0] == ["よじ"] and N.ja_time(9, 0)[0] == ["くじ"] and "さんじはん" in N.ja_time(3, 30)[0]
    assert N.ja_minutes(1) == ["いっぷん"] and N.ja_minutes(10)[0] == "じゅっぷん" and N.ja_minutes(6) == ["ろっぷん"]
    assert [N.ja_day(d) for d in (1, 2, 3, 4, 8, 10, 14, 20, 24)] == ["ついたち", "ふつか", "みっか", "よっか", "ようか", "とおか",
                                                                    "じゅうよっか", "はつか", "にじゅうよっか"]
    assert N.ja_date(3, 5)[0] == ["ごがつみっか"] and N.ja_date(1, 4)[0] == ["しがつついたち"]
    hon = N.JA_COUNTERS["本"][0]
    assert hon[:3] == ["いっぽん", "にほん", "さんぼん"] and hon[5] == "ろっぽん" and hon[7] == "はっぽん" and hon[9] == "じゅっぽん"
    assert N.JA_COUNTERS["人"][0][:4] == ["ひとり", "ふたり", "さんにん", "よにん"] and N.JA_COUNTERS["匹"][0][2] == "さんびき"


def test_korean_numbers():
    assert [N.ko_native(n) for n in (1, 2, 3, 4, 5, 10, 20, 21, 30, 40, 50, 60, 70, 80, 90, 99)] == [
        "하나", "둘", "셋", "넷", "다섯", "열", "스물", "스물하나", "서른", "마흔", "쉰", "예순", "일흔", "여든", "아흔", "아흔아홉"]
    assert [N.ko_native(n, True) for n in (1, 2, 3, 4, 11, 20, 21, 22, 23, 24)] == ["한", "두", "세", "네", "열한", "스무", "스물한",
                                                                                 "스물두", "스물세", "스물네"]
    assert all(N.ko_native(n) for n in range(1, 100))
    assert N.ko_sino(100) == "백" and N.ko_sino(1000) == "천" and N.ko_sino(10000) == "만" and N.ko_sino(15000) == "만 오천"
    assert N.ko_sino(16) == "십육" and N.ko_sino(542) == "오백사십이" and N.ko_sino(25000) == "이만 오천"
    assert N.ko_time(3, 30)[0] == ["세 시 삼십 분", "세 시 반"] and N.ko_time(12, 0)[0] == ["열두 시"]
    assert N.ko_date(3, 6)[0][0] == "유월 삼 일" and N.ko_date(9, 10)[0][0] == "시월 구 일"


def test_every_question_kind_generates_answerable_questions():
    for lang, kinds in N.KINDS.items():
        r = random.Random(7)
        for kind, _ in kinds:
            mk = N.make(lang, r, [kind])
            for _ in range(60):
                q = mk()
                assert q["a"] and q["show"] and q["why"] and q["lang"] == lang
                assert all(drills.grade(q, a)[0] for a in q["a"]), q
    for lang in ("es", "fr", "ja", "ko"):
        r = random.Random(3)
        mk = L.make(lang, r, [t["id"] for t in L.options(lang)["tenses"]], "all")
        for _ in range(150):
            q = mk()
            if q:
                assert all(drills.grade(q, a)[0] for a in q["a"]), q


# ---------------------------------------------------------------------------
# grading and the drill itself
# ---------------------------------------------------------------------------
def test_grading_follows_the_course_rules():
    q = {"a": ["hablábamos", "nosotros hablábamos"], "grade": "typed"}
    assert drills.grade(q, "hablábamos") == (True, None)
    assert drills.grade(q, "hablabamos") == (True, "accent")               # a missing accent: right, flagged
    assert drills.grade(q, "Nosotros hablábamos")[0]
    pret = {"a": ["habló"], "grade": "typed"}
    assert not drills.grade(pret, "hablo")[0]                                # the final accent is the tense
    assert not drills.grade({"a": ["fuimos"], "grade": "typed"}, "fuimo")[0]   # no typo forgiveness
    fr = {"a": ["mille neuf cent quatre-vingt-quatre", "mille-neuf-cent-quatre-vingt-quatre"], "grade": "typed"}
    assert drills.grade(fr, "mille neuf cent quatre vingt quatre")[0] and drills.grade(fr, "mille-neuf-cent-quatre-vingt-quatre")[0]
    zh = {"a": N.zh_accept(["五百四十二"]), "grade": "typed"}
    for ans in ("五百四十二", "wǔ bǎi sì shí èr", "wu3 bai3 si4 shi2 er4", "wu3bai3si4shi2er4"):
        assert drills.grade(zh, ans)[0], ans
    assert drills.grade(zh, "wubaisishier") == (True, "tone")
    assert not drills.grade(zh, "wu2 bai3 si4 shi2 er4")[0]                  # a wrong tone is a wrong word
    ja = {"a": ["三千円", "さんぜんえん", "sanzen'en", "sanzenen"], "grade": "typed"}
    assert drills.grade(ja, "さんぜんえん")[0] and drills.grade(ja, "sanzenen")[0] and not drills.grade(ja, "さんせんえん")[0]
    dig = {"a": ["1984"], "grade": "digits"}
    for ans in ("1984", "1 984", "1,984", "1.984", "１９８４"):
        assert drills.grade(dig, ans)[0], ans
    for ans in ("", "19 84 x", "²", "1985", "1e3", "-1984", "9" * 40):
        assert not drills.grade(dig, ans)[0], ans


def test_hostile_input_is_refused_or_harmless():
    for bad in (None, 5, ["x"], "<script>alert(1)</script>", "x" * 10000, "\x00‮"):
        for q in ({"a": ["1"], "grade": "digits"}, {"a": ["fuimos"], "grade": "typed"}, {"a": ["五", "wǔ"], "grade": "typed"}):
            assert drills.grade(q, bad)[0] is False
    for opts in (None, [], {"size": "x"}, {"size": 10 ** 9}, {"size": True}, {"tenses": "pres"}, {"tenses": ["x" * 1000] * 1000},
                 {"kinds": [None, 3, {}]}, {"set": ["all"]}):
        d = drills.start("conj-es", seed=1, opts=opts)
        assert d["ok"] and 5 <= len(d["questions"]) <= drills.MAX_SIZE
        d = drills.start("num-ko", seed=1, opts=opts)
        assert d["ok"] and 5 <= len(d["questions"]) <= drills.MAX_SIZE
    assert not drills.start("conj-zh")["ok"] and not drills.start("num-xx")["ok"] and not drills.start("conj-es-x")["ok"]
    assert not drills.options("../etc")["ok"]
    d = drills.start("num-fr", seed=1)
    assert not drills.answer(d["drill"], 99, "1")["ok"] and not drills.answer(d["drill"], -1, "1")["ok"]


def test_language_drills_through_the_api_are_graded_and_remembered():
    from fastapi.testclient import TestClient

    from sect_academy.app import app
    client = TestClient(app)
    o = client.get("/api/drill/options?lang=fr").json()
    assert o["ok"] and {t["id"] for t in o["conj"]["tenses"]} >= {"pres", "pc", "imp"}
    d = client.post("/api/drill", json={"kind": "conj-fr", "opts": {"tenses": ["pc"], "size": 12, "set": "core"}}).json()
    assert d["ok"] and len(d["questions"]) == 12 and all("passé composé" in q["q"] for q in d["questions"])
    key = drills._open[d["drill"]]["qs"]
    assert all(not set(q) - {"n", "q", "choices", "lang", "hint"} for q in d["questions"])      # answers stay on the server
    for q in d["questions"]:
        r = client.post("/api/drill/answer", json={"drill": d["drill"], "n": q["n"], "answer": key[q["n"]]["a"][0]}).json()
        assert r["correct"] and r["expected"] and r["why"]
    assert r["finished"] and client.get("/api/overview").json()["drills"]["conj-fr"] == {"best": 100, "runs": 1}
    d = client.post("/api/drill", json={"kind": "num-ja", "opts": {"kinds": ["count"], "size": 5}}).json()
    q = d["questions"][0]
    assert q["lang"] == "ja" and q["hint"]
    r = client.post("/api/drill/answer", json={"drill": d["drill"], "n": 0, "answer": "x" * 500}).json()
    assert r["ok"] and not r["correct"]
