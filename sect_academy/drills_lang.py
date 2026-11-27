"""Verb drills made on the spot: Spanish, French, Japanese, Korean.

Spanish and French forms are read from the dictionary data (the ``C`` lines of ``dict/es`` and ``dict/fr``:
every form of a verb with its tense and person, from Wiktionary's conjugation tables). Nothing here writes a
Spanish or French form by rule; the small table of regular endings below is only used to say whether a form is
regular. Where the data has no form for a cell, the cell is never asked. The French passé composé is the one
compound tense: the auxiliary's present (from the data) + the past participle (from the data), agreeing with
the subject after être.

Japanese and Korean verbs are conjugated here: Japanese from the dictionary form and its JMdict part of speech
(ichidan, godan by ending, the irregular 行く, する and 来る), Korean by Hangul jamo arithmetic, with the
irregular classes (ㅂ, ㄷ, ㅡ, 르, ㅅ, ㅎ, ㄹ-stems, 하다) marked on each verb of the list.

A question is {q, a (accepted answers, best first), show (the answer as shown), why, grade, lang}.
"""
from __future__ import annotations

import random
import re
import threading


def _entries(text: str) -> list[list[str]]:
    """"食べる:たべる:eat 見る:みる:see" -> [["食べる", "たべる", "eat"], ...] (a meaning may hold spaces)."""
    return [t.split(":") for t in re.split(r"\s+(?=\S+:)", text.strip())]

# ---------------------------------------------------------------------------
# Spanish and French
# ---------------------------------------------------------------------------
ES_VERBS = """ser estar tener hacer poder decir ir ver dar saber querer llegar pasar deber poner parecer quedar creer
hablar llevar dejar seguir encontrar llamar venir pensar salir volver tomar conocer vivir sentir tratar mirar contar
empezar esperar buscar existir entrar trabajar escribir perder producir ocurrir entender pedir recibir recordar terminar
permitir aparecer conseguir comenzar servir sacar necesitar mantener resultar leer caer cambiar presentar crear abrir
considerar oír acabar convertir ganar formar traer partir morir aceptar realizar suponer comprender lograr explicar
preguntar tocar reconocer estudiar alcanzar nacer dirigir correr utilizar pagar ayudar gustar jugar escuchar cumplir
ofrecer descubrir levantar intentar usar decidir repetir olvidar valer comer mostrar ocupar mover continuar cerrar
dormir conducir elegir comprar enseñar viajar cocinar bailar cantar beber nadar limpiar lavar preparar vender subir
bajar andar caber construir huir incluir oler reír traducir costar soñar probar devolver resolver romper proponer
obtener detener contener atraer distinguir coger despertar sonreír freír negar""".split()
FR_VERBS = """être avoir faire dire pouvoir aller voir savoir vouloir venir devoir prendre trouver donner parler aimer
passer mettre croire demander rester répondre entendre penser arriver connaître devenir sentir sembler tenir comprendre
rendre attendre sortir vivre entrer porter chercher revenir appeler mourir partir jeter suivre écrire montrer tomber
ouvrir commencer finir manger oublier recevoir lire perdre servir dormir courir boire offrir payer acheter envoyer
essayer préférer espérer lever apprendre conduire construire produire découvrir souffrir mentir permettre promettre
battre craindre peindre plaire rire sourire valoir naître descendre monter retourner rentrer marcher jouer travailler
habiter étudier regarder écouter chanter danser fermer laisser pleurer gagner changer nager voyager placer lancer avancer
vendre défendre choisir réussir grandir remplir réfléchir obéir agir bâtir vieillir punir nourrir guérir accueillir
cueillir couvrir obtenir retenir appartenir traduire détruire joindre éteindre paraître disparaître apparaître
reconnaître prévoir admettre surprendre interdire mener amener élever répéter célébrer""".split()
# The forty commonest, for the "core" set (irregulars among them).
ES_CORE = ES_VERBS[:40]
FR_CORE = FR_VERBS[:40]
# French verbs whose passé composé takes être (used intransitively, as asked here)
FR_ETRE = {"aller", "venir", "arriver", "partir", "entrer", "sortir", "monter", "descendre", "naître", "mourir", "rester",
           "tomber", "retourner", "devenir", "revenir", "rentrer", "passer", "apparaître"}
# Forms the data lists that are wrong or not standard for the cell (checked by hand): never asked, never accepted.
_BAD = {"es": {("ser", "seigo"), ("ir", "idos")},
        "fr": {("aller", "vas", "ind.pres.1s"), ("mourir", "meure", "imp.2s"), ("manger", "mangeont"), ("valoir", "valent", "subj.pres.3p"),
               ("vouloir", "veux", "imp.2s"), ("vouloir", "voulons", "imp.1p"), ("vouloir", "voulez", "imp.2p")}}

TENSES = {
    "es": [("pres", "ind.pres", "presente", "present"), ("pret", "ind.pret", "pretérito indefinido", "preterite"),
           ("impf", "ind.impf", "pretérito imperfecto", "imperfect"), ("fut", "ind.fut", "futuro", "future"),
           ("cond", "cond.pres", "condicional", "conditional"), ("subj", "subj.pres", "presente de subjuntivo", "present subjunctive"),
           ("subjimpf", "subj.impf", "imperfecto de subjuntivo", "imperfect subjunctive"), ("imp", "imp", "imperativo", "imperative")],
    "fr": [("pres", "ind.pres", "présent", "present"), ("pc", "pc", "passé composé", "passé composé"),
           ("impf", "ind.impf", "imparfait", "imperfect"), ("fut", "ind.fut", "futur simple", "future"),
           ("cond", "cond.pres", "conditionnel présent", "conditional"), ("subj", "subj.pres", "subjonctif présent", "present subjunctive"),
           ("imp", "imp", "impératif", "imperative")],
}
PERSONS = {"es": ["1s", "2s", "3s", "1p", "2p", "3p"], "fr": ["1s", "2s", "3s", "1p", "2p", "3p"]}
IMP_PERSONS = {"es": ["2s", "3s", "1p", "2p", "3p"], "fr": ["2s", "1p", "2p"]}
ES_PRON = {"1s": ["yo"], "2s": ["tú"], "3s": ["él", "ella", "usted"], "1p": ["nosotros", "nosotras"], "2p": ["vosotros", "vosotras"],
           "3p": ["ellos", "ellas", "ustedes"]}
ES_IMP_PRON = {"2s": "tú", "3s": "usted", "1p": "nosotros", "2p": "vosotros", "3p": "ustedes"}
FR_PRON = {"1s": ["je"], "2s": ["tu"], "3s": ["il", "elle"], "1p": ["nous"], "2p": ["vous"], "3p": ["ils", "elles"]}
FR_IMP_PRON = {"2s": "tu", "1p": "nous", "2p": "vous"}

_tables: dict[str, dict] = {}
_lock = threading.Lock()


def _main_block(row: str) -> list[tuple[str, list[str]]]:
    """The verb's own forms, before the reflexive ones (written with a space, an apostrophe or a hyphen)."""
    out = []
    for tok in row.split(","):
        f, _, codes = tok.partition("=")
        if not f or any(ch in f for ch in " '-"):
            break
        out.append((f, codes.split("/")))
    return out


def paradigm(lang: str, verb: str) -> dict[tuple[str, str], list[str]]:
    """{(tense code, person): [forms, best first]} for a Spanish or French verb, from the dictionary's C line.
    Tense codes as in ``TENSES`` ("ind.pret"), "imp" for the imperative, ("pp", "") for the past participle."""
    with _lock:
        cache = _tables.setdefault(lang, {})
        if verb in cache:
            return cache[verb]
    from .lexicon import es, fr
    table = (es if lang == "es" else fr).TABLE.load()
    row = table.conj.get(verb, "")
    cells: dict[tuple[str, str], list[str]] = {}
    bad = _BAD.get(lang, set())
    for form, codes in _main_block(row):
        for code in codes:
            if (verb, form) in bad:
                continue
            p = code.split(".")
            if code == "pp":
                keys = [("pp", "")]
            elif p[0] == "imp":
                if len(p) != 2:
                    continue                                   # imp.3s.f repeats imp.3s
                keys = [("imp", p[1])]
            elif len(p) == 3 and len(p[2]) >= 2 and p[2][-1] in "sp":
                keys = [(f"{p[0]}.{p[1]}", ch + p[2][-1]) for ch in p[2][:-1]]
            else:
                continue
            for k in keys:
                if (verb, form, f"{k[0]}.{k[1]}") in bad:       # wrong for this cell only (aller: *je vas)
                    continue
                lst = cells.setdefault(k, [])
                if form not in lst:
                    lst.append(form)
    if lang == "es" and ("imp", "2p") in cells:                # vosotros: the affirmative imperative ends in -d
        cells[("imp", "2p")] = [f for f in cells[("imp", "2p")] if f.endswith("d")] or cells.pop(("imp", "2p"))
    if lang == "fr" and verb in ("cueillir", "accueillir"):    # the data also lists *cueillirai
        for k in list(cells):
            if k[0] in ("ind.fut", "cond.pres"):
                cells[k] = [f for f in cells[k] if "illir" not in f]
    if lang == "fr" and ("pp", "") in cells and len(cells[("pp", "")]) > 1:
        # aller lists été (j'ai été = I went) beside allé: the participle spelled like the verb comes first
        from .lexicon import fr
        stem = fr.fold(verb)[:2]
        cells[("pp", "")].sort(key=lambda f: not fr.fold(f).startswith(stem))
    cells = {k: v for k, v in cells.items() if v}
    with _lock:
        _tables[lang][verb] = cells
    return cells


# regular endings, only to say whether a form is regular
_ES_REG = {
    "ar": {"ind.pres": "o as a amos áis an", "ind.pret": "é aste ó amos asteis aron", "ind.impf": "aba abas aba ábamos abais aban",
           "subj.pres": "e es e emos éis en", "subj.impf": "ara aras ara áramos arais aran", "imp": "- a e emos ad en"},
    "er": {"ind.pres": "o es e emos éis en", "ind.pret": "í iste ió imos isteis ieron", "ind.impf": "ía ías ía íamos íais ían",
           "subj.pres": "a as a amos áis an", "subj.impf": "iera ieras iera iéramos ierais ieran", "imp": "- e a amos ed an"},
    "ir": {"ind.pres": "o es e imos ís en", "ind.pret": "í iste ió imos isteis ieron", "ind.impf": "ía ías ía íamos íais ían",
           "subj.pres": "a as a amos áis an", "subj.impf": "iera ieras iera iéramos ierais ieran", "imp": "- e a amos id an"},
}
_ES_INF = {"ind.fut": "é ás á emos éis án", "cond.pres": "ía ías ía íamos íais ían"}
_FR_REG = {
    "er": {"ind.pres": "e es e ons ez ent", "ind.impf": "ais ais ait ions iez aient", "subj.pres": "e es e ions iez ent",
           "imp": "- e - ons ez -", "pp": "é"},
    "ir": {"ind.pres": "is is it issons issez issent", "ind.impf": "issais issais issait issions issiez issaient",
           "subj.pres": "isse isses isse issions issiez issent", "imp": "- is - issons issez -", "pp": "i"},
    "re": {"ind.pres": "s s  ons ez ent", "ind.impf": "ais ais ait ions iez aient", "subj.pres": "e es e ions iez ent",
           "imp": "- s - ons ez -", "pp": "u"},
}
_FR_INF = {"ind.fut": "ai as a ons ez ont", "cond.pres": "ais ais ait ions iez aient"}
_IDX = {"1s": 0, "2s": 1, "3s": 2, "1p": 3, "2p": 4, "3p": 5}


def regular_form(lang: str, verb: str, tense: str, person: str) -> str | None:
    """What a regular verb of this class would have here ("" if the class has no simple rule)."""
    i = _IDX[person]
    if lang == "es":
        cls = verb[-2:].replace("í", "i")
        if cls not in _ES_REG:
            return None
        if tense in _ES_INF:
            return verb + _ES_INF[tense].split(" ")[i]
        ends = _ES_REG[cls].get(tense)
        return verb[:-2] + ends.split(" ")[i] if ends else None
    cls = verb[-2:]
    if cls not in _FR_REG:
        return None
    if tense in _FR_INF:
        return (verb[:-1] if cls == "re" else verb) + _FR_INF[tense].split(" ")[i]
    ends = _FR_REG[cls].get(tense)
    if not ends:
        return None
    return verb[:-2] + ends.split(" ")[i]


def _elide(word: str) -> bool:
    return word[:1].lower() in "aeiouyàâäéèêëîïôöûùüœh" and not word.startswith(("haï", "hai"))


def _fr_subject(pron: str, verb_form: str) -> str:
    return ("j'" + verb_form) if pron == "je" and _elide(verb_form) else f"{pron} {verb_form}"


def _agree(pp: str, pron: str) -> list[str]:
    """Past participle after être, agreeing with the subject (je/tu/vous: either gender; vous: one or many)."""
    def f(p: str, fem: bool, plural: bool) -> str:
        out = p + ("e" if fem else "")
        return out + ("s" if plural and not out.endswith("s") else "")
    table = {"il": [f(pp, False, False)], "elle": [f(pp, True, False)], "ils": [f(pp, False, True)], "elles": [f(pp, True, True)],
             "je": [f(pp, False, False), f(pp, True, False)], "tu": [f(pp, False, False), f(pp, True, False)],
             "nous": [f(pp, False, True), f(pp, True, True)],
             "vous": [f(pp, False, True), f(pp, True, True), f(pp, False, False), f(pp, True, False)]}
    return list(dict.fromkeys(table[pron]))


def _person_of(pron: str) -> str:
    return next(p for p, names in FR_PRON.items() if pron in names)


def fr_passe_compose(verb: str, pron: str) -> list[str] | None:
    """Accepted answers for the passé composé, with the subject pronoun, best first; None if the data lacks a part."""
    pp = paradigm("fr", verb).get(("pp", ""))
    aux_verb = "être" if verb in FR_ETRE else "avoir"
    aux = paradigm("fr", aux_verb).get(("ind.pres", _person_of(pron)))
    if not pp or not aux:
        return None
    parts = _agree(pp[0], pron) if aux_verb == "être" else [pp[0]]
    return [_fr_subject(pron, f"{aux[0]} {p}") for p in parts]


def _irregular(verb: str, name: str, show: str, reg: str, stem_len: int, form: str = "") -> str:
    """Why a form is not the regular one: the regular ending on a changed stem, or irregular outright."""
    form = form or show
    if reg.startswith(verb):
        stem_len = len(verb)
    ending = reg[stem_len:]
    if ending and form.endswith(ending) and form[:len(form) - len(ending)] != verb[:stem_len]:
        return f"{verb} changes its stem (or its spelling) in the {name}: {show}; the ending is the regular -{ending}."
    return f"{verb} is irregular in the {name}: {show}."


def _ask_es(r: random.Random, verb: str, tense: tuple, cells: dict) -> dict | None:
    key, code, name, _en = tense
    persons = IMP_PERSONS["es"] if code == "imp" else PERSONS["es"]
    person = r.choice(persons)
    forms = cells.get((code, person))
    if not forms:
        return None
    pron = ES_IMP_PRON[person] if code == "imp" else r.choice(ES_PRON[person])
    accepted = list(forms)
    if code != "imp":
        accepted += [f"{p} {f}" for p in ES_PRON[person] for f in forms]
    reg = regular_form("es", verb, code, person)
    note = "" if code != "subj.impf" or len(forms) < 2 else f" The -se form ({forms[1]}) is right too."
    if reg is None:
        why = f"{verb}, {name}, {pron}: {forms[0]}."
    elif reg == forms[0]:
        cls = verb[-2:].replace("í", "i")
        why = (f"The regular -{cls} pattern: {forms[0]}." if code in _ES_INF
               else f"The regular -{cls} pattern: {verb[:-2]}- + -{forms[0][len(verb) - 2:]}.")
    else:
        why = _irregular(verb, name, forms[0], reg, len(verb) - 2)
    return {"q": f"{verb} · {name} · {pron}", "a": accepted, "show": forms[0], "why": why + note, "grade": "typed", "lang": "es"}


def _ask_fr(r: random.Random, verb: str, tense: tuple, cells: dict) -> dict | None:
    key, code, name, _en = tense
    if code == "imp":
        person = r.choice(IMP_PERSONS["fr"])
        forms = cells.get(("imp", person))
        if not forms:
            return None
        pron = FR_IMP_PRON[person]
        accepted, show = list(forms), forms[0]
    else:
        person = r.choice(PERSONS["fr"])
        pron = r.choice(FR_PRON[person])
        if code == "pc":
            accepted = fr_passe_compose(verb, pron)
            if not accepted:
                return None
            bare = [a.split(" ", 1)[1] if not a.startswith("j'") else a[2:] for a in accepted]
            show = accepted[0]
            aux = "être" if verb in FR_ETRE else "avoir"
            pp = paradigm("fr", verb)[("pp", "")][0]
            why = (f"Passé composé = {aux} in the present + the past participle ({pp}). "
                   + (f"{verb} takes être, so the participle agrees with the subject: {bare[0].split(' ')[-1]}."
                      if aux == "être" else "With avoir the participle does not change."))
            return {"q": f"{verb} · {name} · {pron}", "a": accepted + bare, "show": show, "why": why, "grade": "typed", "lang": "fr"}
        forms = cells.get((code, person))
        if not forms:
            return None
        lead = "que " if code == "subj.pres" else ""
        with_pron = [_fr_subject(pron, f) for f in forms]
        que = [("qu'" + w) if w.startswith(("il ", "elle ")) else "que " + w for w in with_pron] if lead else []
        accepted = list(dict.fromkeys(list(forms) + with_pron + que))
        show = que[0] if que else with_pron[0]
    reg = regular_form("fr", verb, code, person)
    if reg is None:
        why = f"{verb}, {name}: {show}."
    elif reg == forms[0]:
        why = f"The regular -{verb[-2:]} pattern: {show}."
    else:
        why = _irregular(verb, name, show, reg, len(verb) - 2, forms[0])
    return {"q": f"{verb} · {name} · {pron}", "a": accepted, "show": show, "why": why, "grade": "typed", "lang": "fr"}


# ---------------------------------------------------------------------------
# Japanese
# ---------------------------------------------------------------------------
# dictionary form : reading : meaning. The class comes from JMdict (checked in the tests).
JA_VERBS = _entries("""食べる:たべる:eat 見る:みる:see 起きる:おきる:get up 寝る:ねる:sleep 着る:きる:wear
出る:でる:leave 出かける:でかける:go out 教える:おしえる:teach 覚える:おぼえる:remember 忘れる:わすれる:forget
借りる:かりる:borrow 浴びる:あびる:take (a shower) 始める:はじめる:begin 開ける:あける:open 閉める:しめる:close
答える:こたえる:answer 降りる:おりる:get off 入れる:いれる:put in 決める:きめる:decide 住む:すむ:live 読む:よむ:read
飲む:のむ:drink 休む:やすむ:rest 書く:かく:write 聞く:きく:listen 歩く:あるく:walk 働く:はたらく:work 置く:おく:put
行く:いく:go 泳ぐ:およぐ:swim 急ぐ:いそぐ:hurry 脱ぐ:ぬぐ:take off 話す:はなす:speak 貸す:かす:lend 出す:だす:take out
消す:けす:turn off 押す:おす:push 待つ:まつ:wait 持つ:もつ:hold 立つ:たつ:stand 死ぬ:しぬ:die 遊ぶ:あそぶ:play
呼ぶ:よぶ:call 飛ぶ:とぶ:fly 買う:かう:buy 会う:あう:meet 言う:いう:say 使う:つかう:use 洗う:あらう:wash
歌う:うたう:sing 習う:ならう:learn 思う:おもう:think 手伝う:てつだう:help 帰る:かえる:go home 入る:はいる:enter
走る:はしる:run 切る:きる:cut 取る:とる:take 作る:つくる:make 乗る:のる:ride 終わる:おわる:end 座る:すわる:sit
送る:おくる:send 撮る:とる:take (a photo) 来る:くる:come する:する:do 勉強する:べんきょうする:study
電話する:でんわする:phone 散歩する:さんぽする:take a walk 運転する:うんてんする:drive""")
JA_FORMS = [("masu", "ます form (polite)"), ("masen", "ません (polite negative)"), ("mashita", "ました (polite past)"),
            ("te", "て form"), ("nai", "ない form (negative)"), ("ta", "た form (past)"), ("pot", "potential (can …)"),
            ("vol", "volitional (let's …)"), ("ba", "ば conditional (if …)")]
_GODAN = {"う": ("い", "わ", "え", "お", "って", "った"), "く": ("き", "か", "け", "こ", "いて", "いた"),
          "ぐ": ("ぎ", "が", "げ", "ご", "いで", "いだ"), "す": ("し", "さ", "せ", "そ", "して", "した"),
          "つ": ("ち", "た", "て", "と", "って", "った"), "ぬ": ("に", "な", "ね", "の", "んで", "んだ"),
          "ぶ": ("び", "ば", "べ", "ぼ", "んで", "んだ"), "む": ("み", "ま", "め", "も", "んで", "んだ"),
          "る": ("り", "ら", "れ", "ろ", "って", "った")}
_SURU = {"masu": "します", "masen": "しません", "mashita": "しました", "te": "して", "nai": "しない", "ta": "した",
         "pot": "できる", "vol": "しよう", "ba": "すれば"}
_KURU = {"masu": "きます", "masen": "きません", "mashita": "きました", "te": "きて", "nai": "こない", "ta": "きた",
         "pot": "こられる", "vol": "こよう", "ba": "くれば"}


def ja_class(word: str) -> str:
    """"v1", "v5" + ending, "v5k-s" (行く), "vk" (来る) or "vs" (する and noun + する), from JMdict's part of speech."""
    if word.endswith("する"):
        return "vs"
    from .lexicon import ja
    d = ja.dictionary()
    for _, i, term, _ in ja.find(word):
        if term != word:
            continue
        tags = d.tags[i]
        for t in tags:
            if t in ("v1", "vk", "v5k-s") or (t.startswith("v5") and len(t) == 3):
                return t
    return ""


def ja_conjugate(word: str, kana: str, form: str, cls: str | None = None) -> tuple[str, str]:
    """(written form, kana) of a Japanese verb in one of ``JA_FORMS``."""
    cls = cls or ja_class(word)
    if cls == "vs":
        pre_w, pre_k = word[:-2], kana[:-2]
        return pre_w + _SURU[form], pre_k + _SURU[form]
    if cls == "vk":
        k = _KURU[form]
        return (("来" + k[1:]) if word.startswith("来") else k), k
    if cls == "v1":
        end = {"masu": "ます", "masen": "ません", "mashita": "ました", "te": "て", "nai": "ない", "ta": "た", "pot": "られる",
               "vol": "よう", "ba": "れば"}[form]
        return word[:-1] + end, kana[:-1] + end
    i_, a_, e_, o_, te, ta = _GODAN[word[-1]]
    if cls == "v5k-s":
        te, ta = "って", "った"
    end = {"masu": i_ + "ます", "masen": i_ + "ません", "mashita": i_ + "ました", "te": te, "nai": a_ + "ない", "ta": ta,
           "pot": e_ + "る", "vol": o_ + "う", "ba": e_ + "ば"}[form]
    return word[:-1] + end, kana[:-1] + end


def _ja_why(word: str, cls: str, form: str) -> str:
    if cls == "vs":
        return "する is irregular: " + {"pot": "its potential is できる.", "nai": "しない.", "ba": "すれば."}.get(form, "し- before most endings.")
    if cls == "vk":
        return "来る is irregular: き- before ます, て and た; こ- before ない, られる and よう; くれば."
    if cls == "v1":
        return "Ichidan (ru-verb): drop る and add the ending."
    if cls == "v5k-s" and form in ("te", "ta"):
        return "行く is the one exception among く verbs: 行って, 行った (not *行いて)."
    names = {"masu": "i-row + ます", "masen": "i-row + ません", "mashita": "i-row + ました", "nai": "a-row + ない (う becomes わ)",
             "pot": "e-row + る", "vol": "o-row + う", "ba": "e-row + ば",
             "te": "the て form follows the ending: う/つ/る → って, ぶ/む/ぬ → んで, く → いて, ぐ → いで, す → して",
             "ta": "the た form follows the ending: う/つ/る → った, ぶ/む/ぬ → んだ, く → いた, ぐ → いだ, す → した"}
    return f"Godan (u-verb) ending in {word[-1]}: {names[form]}."


def _ask_ja(r: random.Random, entry: list[str], form: tuple) -> dict | None:
    from .lexicon.ja_rules import romaji
    word, kana, en = entry
    cls = ja_class(word)
    if not cls:
        return None
    w, k = ja_conjugate(word, kana, form[0], cls)
    roms = list(dict.fromkeys([romaji(k, macrons=False), romaji(k)]))
    accepted = list(dict.fromkeys([w, k])) + roms
    show = w + (f" ({k}, {roms[0]})" if w != k else f" ({roms[0]})")
    return {"q": f"{word} ({kana}, {en}) · {form[1]}", "a": accepted, "show": show, "why": _ja_why(word, cls, form[0]),
            "grade": "typed", "lang": "ja"}


# ---------------------------------------------------------------------------
# Korean
# ---------------------------------------------------------------------------
# dictionary form : class : verb (v), adjective (a) or a verb with no "want to" (x) : meaning. Classes: r regular (ㄹ-stems and 하다 are found
# from the spelling), b ㅂ (b2: 돕다 and 곱다, which take 와), d ㄷ, s ㅅ, h ㅎ, reu 르. A stem in ㅡ is always
# ㅡ-irregular, so it needs no mark.
KO_VERBS = _entries("""가다:r:v:go 오다:r:v:come 보다:r:v:see 주다:r:v:give 하다:r:v:do 먹다:r:v:eat
마시다:r:v:drink 자다:r:v:sleep 읽다:r:v:read 쓰다:r:v:write 듣다:d:v:listen 걷다:d:v:walk 묻다:d:v:ask 살다:r:v:live
알다:r:v:know 만들다:r:v:make 놀다:r:v:play 팔다:r:v:sell 열다:r:v:open 울다:r:v:cry 웃다:r:v:laugh 씻다:r:v:wash
입다:r:v:wear 잡다:r:v:catch 돕다:b2:v:help 받다:r:v:receive 닫다:r:v:close 믿다:r:v:believe 배우다:r:v:learn
가르치다:r:v:teach 보내다:r:v:send 기다리다:r:v:wait 되다:r:v:become 쉬다:r:v:rest 타다:r:v:ride 서다:r:v:stand
켜다:r:v:turn on 앉다:r:v:sit 찾다:r:v:look for 일하다:r:v:work 공부하다:r:v:study 좋아하다:r:v:like 만나다:r:v:meet
사다:r:v:buy 일어나다:r:v:get up 내리다:r:v:get off 바꾸다:r:v:change 춤추다:r:v:dance 끝나다:r:x:end 시작하다:r:v:begin
치다:r:v:hit 뛰다:r:v:run 모르다:reu:x:not know 부르다:reu:v:sing 고르다:reu:v:choose 끄다:r:v:turn off 짓다:s:v:build
붓다:s:v:pour 낫다:s:v:get better 놓다:r:v:put 넣다:r:v:put in 있다:r:x:be (there) 없다:r:a:not be there
춥다:b:a:be cold 덥다:b:a:be hot 쉽다:b:a:be easy 어렵다:b:a:be difficult 맵다:b:a:be spicy 가깝다:b:a:be near
고맙다:b:a:be thankful 빠르다:reu:a:be fast 다르다:reu:a:be different 바쁘다:r:a:be busy 아프다:r:a:be sick
예쁘다:r:a:be pretty 크다:r:a:be big 기쁘다:r:a:be glad 슬프다:r:a:be sad 그렇다:h:a:be so 빨갛다:h:a:be red
하얗다:h:a:be white 어떻다:h:a:be how 좋다:r:a:be good 싫다:r:a:be disliked 많다:r:a:be many 작다:r:a:be small
길다:r:a:be long 멀다:r:a:be far 싸다:r:a:be cheap 비싸다:r:a:be expensive""")
KO_FORMS = [("pres", "polite present -아요/어요"), ("past", "polite past -았어요/었어요"), ("fut", "future -(으)ㄹ 거예요"),
            ("formal", "formal -(스)ㅂ니다"), ("want", "want to -고 싶어요")]
_BRIGHT = set("ㅏㅗㅑ")


def _ko():
    from .lexicon import ko
    return ko


def ko_infinitive(dict_form: str, cls: str) -> list[str]:
    """The -아/어 form ("infinitive"), best first: 가, 먹어, 해, 들어, 몰라, 도와, 더워, 나아, 그래."""
    ko = _ko()
    stem = dict_form[:-1]
    head, last = stem[:-1], stem[-1]
    L, V, F = ko.jamo(last)
    prev_bright = bool(head) and ko.jamo(head[-1])[1] in _BRIGHT
    if last == "하" and not F:
        return [head + "해"]
    if cls == "h" and F == "ㅎ":
        return [head + ko.syl(L, "ㅒ" if V == "ㅑ" else "ㅐ")]
    if cls == "reu" and last == "르":
        return [head[:-1] + ko.with_final(head[-1], "ㄹ") + ("라" if prev_bright else "러")]
    if V == "ㅡ" and not F:
        return [head + ko.syl(L, "ㅏ" if prev_bright else "ㅓ")]
    if cls in ("b", "b2") and F == "ㅂ":
        return [head + ko.syl(L, V) + ("와" if cls == "b2" else "워")]
    if cls == "d" and F == "ㄷ":
        return [head + ko.syl(L, V, "ㄹ") + ("아" if V in _BRIGHT else "어")]
    if cls == "s" and F == "ㅅ":
        return [head + ko.syl(L, V) + ("아" if V in _BRIGHT else "어")]
    if F:
        return [stem + ("아" if V in _BRIGHT else "어")]
    if V in ("ㅏ", "ㅓ", "ㅕ", "ㅐ", "ㅔ"):
        return [stem]
    if V == "ㅗ":
        return [head + ko.syl(L, "ㅘ")] + ([stem + "아"] if last != "오" else [])
    if V == "ㅜ":
        return [head + ko.syl(L, "ㅝ"), stem + "어"]
    if V == "ㅚ":
        return [head + ko.syl(L, "ㅙ"), stem + "어"]
    if V == "ㅣ":
        return [head + ko.syl(L, "ㅕ")]
    return [stem + "어"]


def ko_conjugate(dict_form: str, cls: str, form: str) -> list[str]:
    """Accepted forms (best first) of a Korean verb or adjective in one of ``KO_FORMS``."""
    ko = _ko()
    stem = dict_form[:-1]
    head, last = stem[:-1], stem[-1]
    L, V, F = ko.jamo(last)
    if form == "pres":
        return [i + "요" for i in ko_infinitive(dict_form, cls)]
    if form == "past":
        return [i[:-1] + ko.with_final(i[-1], "ㅆ") + "어요" for i in ko_infinitive(dict_form, cls)]
    if form == "want":
        return [stem + "고 싶어요"]
    if form == "fut":
        if F == "ㄹ":
            base = stem
        elif cls in ("b", "b2") and F == "ㅂ":
            base = head + ko.syl(L, V) + "울"
        elif cls == "d" and F == "ㄷ":
            base = head + ko.syl(L, V, "ㄹ") + "을"
        elif cls == "s" and F == "ㅅ":
            base = head + ko.syl(L, V) + "을"
        elif cls == "h" and F == "ㅎ":
            base = head + ko.syl(L, V, "ㄹ")
        elif not F:
            base = head + ko.syl(L, V, "ㄹ")
        else:
            base = stem + "을"
        return [base + " 거예요"]
    # formal
    if F == "ㄹ":
        return [head + ko.syl(L, V, "ㅂ") + "니다"]
    if not F:
        return [head + ko.syl(L, V, "ㅂ") + "니다"]
    return [stem + "습니다"]


def ko_roms(form: str) -> list[str]:
    """Romanisations accepted for a Korean answer: Revised Romanization of the whole, and syllable by syllable."""
    ko = _ko()
    whole = ko.romanise(form)
    return list(dict.fromkeys([whole, ko_letters(form)]))


_T_LETTERS = {"": "", "ㄱ": "g", "ㄲ": "kk", "ㄳ": "gs", "ㄴ": "n", "ㄵ": "nj", "ㄶ": "nh", "ㄷ": "d", "ㄹ": "l", "ㄺ": "lg",
              "ㄻ": "lm", "ㄼ": "lb", "ㄽ": "ls", "ㄾ": "lt", "ㄿ": "lp", "ㅀ": "lh", "ㅁ": "m", "ㅂ": "b", "ㅄ": "bs", "ㅅ": "s",
              "ㅆ": "ss", "ㅇ": "ng", "ㅈ": "j", "ㅊ": "ch", "ㅋ": "k", "ㅌ": "t", "ㅍ": "p", "ㅎ": "h"}


def ko_letters(s: str) -> str:
    """Letter-by-letter transliteration (먹었어요 meogeosseoyo, 먹습니다 meogseubnida): what a learner who has not
    yet met the sound changes types."""
    ko = _ko()
    out = []
    for ch in s:
        if ko.is_syl(ch):
            L, V, F = ko.jamo(ch)
            out.append(("r" if L == "ㄹ" else ko._INI[L]) + ko._VOW[V] + _T_LETTERS[F])
        else:
            out.append(ch)
    return "".join(out)


def _ko_why(dict_form: str, cls: str, form: str) -> str:
    stem = dict_form[:-1]
    F = _ko().final(stem[-1])
    if stem.endswith("하"):
        return "하다 verbs: 하 + 여 → 해 (해요, 했어요)." if form in ("pres", "past") else "하다 verbs are regular before other endings."
    if F == "ㄹ" and form in ("fut", "formal"):
        return "ㄹ-stem: the ㄹ drops before ㅂ, ㄴ and ㅅ (삽니다), and -(으)ㄹ merges into it (살 거예요)."
    expl = {"b": "ㅂ irregular: ㅂ becomes 우 before a vowel (추워요, 추울 거예요).",
            "b2": "ㅂ irregular (돕다, 곱다): ㅂ becomes 오 before 아 (도와요).",
            "d": "ㄷ irregular: ㄷ becomes ㄹ before a vowel (들어요, 들을 거예요).",
            "s": "ㅅ irregular: ㅅ drops before a vowel, and the vowels do not merge (나아요).",
            "h": "ㅎ irregular: ㅎ drops; before 아/어 the vowel becomes ㅐ (그래요, 빨개요).",
            "reu": "르 irregular: 르 becomes ㄹ라 / ㄹ러 before 아/어 (몰라요, 불러요)."}
    if cls in expl and (form in ("pres", "past", "fut")):
        return expl[cls]
    if form in ("pres", "past") and _ko().jamo(stem[-1])[1] == "ㅡ" and not F:
        return "ㅡ drops before 아/어; the vowel before it picks 아 or 어 (바빠요, 써요)."
    return {"pres": "아요 after ㅏ/ㅗ, 어요 otherwise; vowels merge where they can (가요, 봐요, 마셔요).",
            "past": "았어요 after ㅏ/ㅗ, 었어요 otherwise (먹었어요, 갔어요).",
            "fut": "ㄹ 거예요 after a vowel, 을 거예요 after a consonant.",
            "formal": "ㅂ니다 after a vowel, 습니다 after a consonant.",
            "want": "Stem + 고 싶어요."}[form]


def _ask_ko(r: random.Random, entry: list[str], form: tuple) -> dict | None:
    word, cls, kind, en = entry
    if form[0] == "want" and kind != "v":
        return None
    forms = ko_conjugate(word, cls, form[0])
    accepted = forms + [x for f in forms for x in ko_roms(f)]
    return {"q": f"{word} ({en}) · {form[1]}", "a": list(dict.fromkeys(accepted)),
            "show": f"{forms[0]} ({ko_roms(forms[0])[0]})", "why": _ko_why(word, cls, form[0]), "grade": "typed", "lang": "ko"}


# ---------------------------------------------------------------------------
# options and the drill
# ---------------------------------------------------------------------------
SETS = {"core": "the 40 commonest", "all": "all"}


def options(lang: str) -> dict:
    """What the learner can choose for a verb drill in this language."""
    if lang in TENSES:
        return {"tenses": [{"id": k, "name": n, "en": e} for k, _, n, e in TENSES[lang]],
                "sets": [{"id": "core", "name": f"{len(ES_CORE if lang == 'es' else FR_CORE)} commonest"},
                         {"id": "all", "name": f"all {len(ES_VERBS if lang == 'es' else FR_VERBS)}"}]}
    if lang == "ja":
        return {"tenses": [{"id": k, "name": n} for k, n in JA_FORMS], "sets": [{"id": "all", "name": f"{len(JA_VERBS)} verbs"}]}
    if lang == "ko":
        return {"tenses": [{"id": k, "name": n} for k, n in KO_FORMS], "sets": [{"id": "all", "name": f"{len(KO_VERBS)} verbs and adjectives"}]}
    return {}


def make(lang: str, r: random.Random, tenses: list[str], vset: str = "all"):
    """A question maker for this language and these tenses (ids from ``options``); None if nothing fits."""
    if lang in TENSES:
        chosen = [t for t in TENSES[lang] if t[0] in tenses] or TENSES[lang][:1]
        pool = (ES_CORE if lang == "es" else FR_CORE) if vset == "core" else (ES_VERBS if lang == "es" else FR_VERBS)
        ask = _ask_es if lang == "es" else _ask_fr

        def one() -> dict | None:
            verb = r.choice(pool)
            return ask(r, verb, r.choice(chosen), paradigm(lang, verb))
        return one
    if lang == "ja":
        chosen = [f for f in JA_FORMS if f[0] in tenses] or JA_FORMS[:1]
        return lambda: _ask_ja(r, r.choice(JA_VERBS), r.choice(chosen))
    if lang == "ko":
        chosen = [f for f in KO_FORMS if f[0] in tenses] or KO_FORMS[:1]
        return lambda: _ask_ko(r, r.choice(KO_VERBS), r.choice(chosen))
    return None
