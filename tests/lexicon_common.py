"""The commonest words of each reader language, with the answer a learner should see first.

    python tests/lexicon_common.py            # accuracy per language, and every miss
    python tests/lexicon_common.py es fr      # some languages

Each list is the most frequent words of the courses' own sentences (``scripts/lexicon_hit_rate.py`` tokenises
them the way the reader does) plus the function words and the words a playtest found wrong, each checked by
hand: the lemma the lookup should land on and words of which one must appear in the **first** sense shown
(for Chinese, also the reading that should come first). People's names are left out.
``tests/test_lexicon_common.py`` holds every list at 100%.

Row: ``word: (lemma, "kw1|kw2")`` — the lemma (or one of "a|b"), and case-insensitive substrings of which one
must be in the first sense; Chinese ``word: (pinyin, "kw")``.
"""
from __future__ import annotations

import os
import sys

ES = {
    "el": ("el", "the"), "la": ("la", "the"), "en": ("en", "in"), "de": ("de", "of"), "a": ("a", "to"),
    "es": ("ser", "be"), "no": ("no", "no|not"), "que": ("que", "that"), "y": ("y", "and"), "me": ("me", "me"),
    "un": ("un", "a, an|an, a"), "mi": ("mi", "my"), "qué": ("qué", "what"), "por": ("por", "for|by|through"),
    "te": ("te", "you"), "las": ("las", "the"), "está": ("estar", "be"), "una": ("una", "a, an"), "muy": ("muy", "very"),
    "tengo": ("tener", "have"), "lo": ("lo", "it, him"), "al": ("al", "to the"), "sí": ("sí", "yes"), "los": ("los", "the"),
    "yo": ("yo", "i"), "se": ("se", "himself|oneself|itself"), "casa": ("casa", "house|home"), "con": ("con", "with"),
    "bien": ("bien", "well"), "mañana": ("mañana", "morning|tomorrow"), "mucho": ("mucho", "much|a lot"),
    "pero": ("pero", "but"), "tiene": ("tener", "have"), "aquí": ("aquí", "here"), "más": ("más", "more"),
    "para": ("para", "for"), "dos": ("dos", "two"), "hay": ("hay|haber", "there is"), "gracias": ("gracias", "thank"),
    "trabajo": ("trabajo", "work|job"), "son": ("ser", "be"), "estoy": ("estar", "be"), "tú": ("tú", "you"),
    "favor": ("favor", "favo"), "voy": ("ir", "go"), "si": ("si", "if"), "hoy": ("hoy", "today"), "he": ("haber", "have"),
    "esta": ("esta|este", "this"), "ya": ("ya", "already"), "español": ("español", "spanish"), "mis": ("mis|mi", "my"),
    "todo": ("todo", "all|everything"), "nada": ("nada", "nothing"), "tienes": ("tener", "have"),
    "gusta": ("gustar", "like|please"), "dónde": ("dónde", "where"), "del": ("del", "of the"), "días": ("día", "day"),
    "tarde": ("tarde", "afternoon|late"), "quiero": ("querer", "want"), "bueno": ("bueno", "good"),
    "hasta": ("hasta", "until"), "tres": ("tres", "three"), "hace": ("hacer", "do|make"), "soy": ("ser", "be"),
    "coche": ("coche", "car"), "semana": ("semana", "week"), "tiempo": ("tiempo", "time|weather"), "eso": ("eso|ése|ese", "that"),
    "cómo": ("cómo", "how"), "tu": ("tu", "your"), "día": ("día", "day"), "diez": ("diez", "ten"), "le": ("le", "him|her"),
    "ahora": ("ahora", "now"), "ayer": ("ayer", "yesterday"), "algo": ("algo", "something"), "nosotros": ("nosotros", "we"),
    "año": ("año", "year"), "este": ("este", "this"), "pues": ("pues", "so|then|well"), "café": ("café", "coffee"),
    "libro": ("libro", "book"), "años": ("año", "year"), "verdad": ("verdad", "truth|true"), "cuando": ("cuando", "when"),
    "vale": ("vale", "ok"), "claro": ("claro", "clear|of course"), "hola": ("hola", "hello"), "ocho": ("ocho", "eight"),
    "hora": ("hora", "hour|time"), "tren": ("tren", "train"), "menos": ("menos", "less"), "hermano": ("hermano", "brother"),
    "hermana": ("hermana", "sister"), "como": ("como", "like|as"), "hotel": ("hotel", "hotel"),
    "puedo": ("poder", "can|able"), "amigos": ("amigo", "friend"), "madre": ("madre", "mother"),
    "banco": ("banco", "bank|bench"), "cerca": ("cerca", "near|close"), "calle": ("calle", "street"),
    "has": ("haber", "have"), "mejor": ("mejor", "better|best"), "o": ("o", "or"), "usted": ("usted", "you"),
    "padre": ("padre", "father"), "nueve": ("nueve", "nine"), "autobús": ("autobús", "bus"),
    "piso": ("piso", "floor|flat|apartment"), "pasa": ("pasar", "pass|happen"), "perdona": ("perdonar", "forgive|excuse|pardon"),
    "ciudad": ("ciudad", "city"), "padres": ("padre", "father|parent"), "noche": ("noche", "night"),
    "todos": ("todos|todo", "all|every"), "poco": ("poco", "little|few"), "cuánto": ("cuánto", "how much"),
    "quieres": ("querer", "want"), "ir": ("ir", "go"), "va": ("ir", "go"), "ha": ("haber", "have"),
    "luego": ("luego", "then|later"), "muchas": ("muchas|mucho", "many"), "inglés": ("inglés", "english"),
    "su": ("su", "his, her"), "euros": ("euro", "euro"), "cuenta": ("cuenta", "bill|account|count"), "ver": ("ver", "see"),
    "tal": ("tal", "such"), "vosotros": ("vosotros", "you"), "agua": ("agua", "water"), "seis": ("seis", "six"),
    "vivo": ("vivir", "live"), "playa": ("playa", "beach"), "centro": ("centro", "center|centre"), "vamos": ("ir", "go"),
    "nos": ("nos", "us"), "médico": ("médico", "doctor"), "pasado": ("pasado", "past|last"), "buenos": ("bueno", "good"),
    "sábado": ("sábado", "saturday"), "mal": ("mal", "bad"), "están": ("estar", "be"), "puede": ("poder", "can|able"),
    "cine": ("cine", "cinema"), "buen": ("bueno", "good"), "dinero": ("dinero", "money"), "viene": ("venir", "come"),
    "horas": ("hora", "hour"), "mismo": ("mismo", "same"), "hecho": ("hecho", "done|made|fact"),
    "antes": ("antes", "before"), "profesor": ("profesor", "teacher|professor"), "grande": ("grande", "big|large"),
    "clase": ("clase", "class"), "veinte": ("veinte", "twenty"), "plaza": ("plaza", "square|plaza"),
    "caro": ("caro", "expensive|dear"), "mí": ("mí", "me"), "vez": ("vez", "time"), "había": ("haber", "have|there"),
    "espero": ("esperar", "wait|hope"), "entiendo": ("entender", "understand"), "estás": ("estar", "be"),
    "mesa": ("mesa", "table"), "uno": ("uno", "one"), "lunes": ("lunes", "monday"), "pan": ("pan", "bread"),
    "porque": ("porque", "because"), "hacer": ("hacer", "do|make"), "venir": ("venir", "come"), "frío": ("frío", "cold"),
    "también": ("también", "also|too"), "fin": ("fin", "end"), "estaba": ("estar", "be"), "ti": ("ti|tú", "you"),
    "sin": ("sin", "without"), "señora": ("señora", "lady|mrs|madam|woman|ms"), "señor": ("señor", "mr|sir|gentleman|mister"),
    "llamo": ("llamar", "call"), "ella": ("ella", "she"), "familia": ("familia", "family"),
    "abuela": ("abuela", "grandmother"), "cinco": ("cinco", "five"), "hablo": ("hablar", "speak|talk"),
    # the playtest's misses and the other function words
    "les": ("les", "to them"), "ido": ("ir", "go"), "fue": ("ser", "be"), "era": ("ser", "be"), "sido": ("ser", "be"),
    "sus": ("sus", "his, her"), "os": ("os", "you"), "unos": ("unos", "some"), "unas": ("unas|uno|un", "some"),
    "ese": ("ese", "that"), "esa": ("esa|ese|ése", "that"), "esto": ("esto", "this"), "nuestro": ("nuestro", "our"),
    "dímelo": ("decir", "say"), "vino": ("vino", "wine"), "comer": ("comer", "eat"), "habla": ("hablar", "speak|talk"),
    "hablamos": ("hablar", "speak|talk"), "fui": ("ser", "be"), "tenemos": ("tener", "have"), "dijo": ("decir", "say"),
    "hizo": ("hacer", "do|make"), "puso": ("poner", "put"), "quiso": ("querer", "want"), "salgo": ("salir", "leave|go out|exit"),
}

FR = {
    "est": ("être", "be"), "le": ("le", "the"), "je": ("je", "i"), "la": ("la", "the"), "il": ("il", "he"),
    "à": ("à", "to"), "de": ("de", "of"), "j'": ("je", "i"), "tu": ("tu", "you"), "un": ("un", "a, an"),
    "vous": ("vous", "you"), "c'": ("ce", "it|that|this"), "a": ("avoir", "have"), "ce": ("ce", "this|that"),
    "pas": ("pas", "not"), "ai": ("avoir", "have"), "en": ("en", "in"), "l'": ("le", "the"), "une": ("une", "a, an|an, a"),
    "et": ("et", "and"), "ça": ("ça", "that|it"), "que": ("que", "that"), "nous": ("nous", "we"), "les": ("les", "the"),
    "au": ("au|à", "to the|at the"), "dans": ("dans", "in"), "ne": ("ne", "not"), "n'": ("ne", "not"),
    "on": ("on", "one|we|people"), "y": ("y", "there"), "oui": ("oui", "yes"), "qu'": ("que", "that"),
    "d'": ("de", "of"), "bien": ("bien", "well"), "mon": ("mon", "my"), "elle": ("elle", "she"),
    "s'": ("se", "himself|oneself|herself"), "heures": ("heure", "hour"), "du": ("du", "of the|some"),
    "merci": ("merci", "thank"), "suis": ("être", "be"), "pour": ("pour", "for"), "me": ("me", "me"),
    "fait": ("faire", "do|make"), "plaît": ("plaire", "please"), "très": ("très", "very"), "soir": ("soir", "evening"),
    "plus": ("plus", "more"), "as": ("avoir", "have"), "moi": ("moi", "me"), "maison": ("maison", "house|home"),
    "sont": ("être", "be"), "ma": ("ma", "my"), "non": ("non", "no"), "avec": ("avec", "with"),
    "bonjour": ("bonjour", "hello|good day|greetings"), "beaucoup": ("beaucoup", "much|lot"), "quand": ("quand", "when"),
    "tout": ("tout", "all|every"), "se": ("se", "himself"), "te": ("te", "you"), "va": ("aller", "go"),
    "m'": ("me", "me"), "mais": ("mais", "but"), "ils": ("ils", "they"), "des": ("des", "some"), "si": ("si", "if"),
    "français": ("français", "french"), "ici": ("ici", "here"), "trop": ("trop", "too"), "deux": ("deux", "two"),
    "bon": ("bon", "good"), "peux": ("pouvoir", "can|able|possible|may"), "faut": ("falloir", "need|necessary|must|have to"),
    "alors": ("alors", "then|so"), "café": ("café", "coffee"), "sur": ("sur", "on"), "matin": ("matin", "morning"),
    "vais": ("aller", "go"), "où": ("où", "where"), "demain": ("demain", "tomorrow"), "bonne": ("bonne", "good"),
    "avez": ("avoir", "have"), "aime": ("aimer", "love|like"), "enfants": ("enfant", "child"),
    "samedi": ("samedi", "saturday"), "qui": ("qui", "who"), "dix": ("dix", "ten"), "euros": ("euro", "euro"),
    "cette": ("cette", "this"), "hier": ("hier", "yesterday"), "était": ("être", "be"), "toi": ("toi", "you"),
    "là": ("là", "there"), "mes": ("mes", "my"), "habite": ("habiter", "live"), "train": ("train", "train"),
    "temps": ("temps", "time|weather"), "sûr": ("sûr", "sure"), "sommes": ("être", "be"), "film": ("film", "film|movie"),
    "voudrais": ("vouloir", "want"), "votre": ("votre", "your"), "ton": ("ton", "your"), "ans": ("an", "year"),
    "veux": ("vouloir", "want"), "t'": ("te", "you"), "dit": ("dire", "say|tell"), "es": ("être", "be"),
    "voiture": ("voiture", "car"), "sept": ("sept", "seven"), "quoi": ("quoi", "what"), "parle": ("parler", "speak|talk"),
    "livre": ("livre", "book"), "avons": ("avoir", "have"), "trois": ("trois", "three"), "dimanche": ("dimanche", "sunday"),
    "combien": ("combien", "how much|how many"), "ville": ("ville", "town|city"), "chez": ("chez", "at"),
    "par": ("par", "by"), "rien": ("rien", "nothing"), "comment": ("comment", "how"), "quel": ("quel", "which|what"),
    "travaille": ("travailler", "work"), "table": ("table", "table"), "frère": ("frère", "brother"),
    "vingt": ("vingt", "twenty"), "aujourd'hui": ("aujourd'hui", "today"), "restaurant": ("restaurant", "restaurant"),
    "gare": ("gare", "station"), "son": ("son", "his|her"), "faire": ("faire", "do|make"), "cher": ("cher", "dear|expensive"),
    "déjà": ("déjà", "already"), "aussi": ("aussi", "also|too"), "chose": ("chose", "thing"), "école": ("école", "school"),
    "mère": ("mère", "mother"), "parents": ("parent", "parent|relative"), "sœur": ("sœur", "sister"),
    "beau": ("beau", "handsome|beautiful|fine|nice"), "fais": ("faire", "do|make"), "mal": ("mal", "pain|evil|harm|bad"),
    "depuis": ("depuis", "since|for"), "mieux": ("mieux", "better"), "madame": ("madame", "madam|mrs|woman"),
    "peu": ("peu", "little"), "chien": ("chien", "dog"), "semaine": ("semaine", "week"), "vendredi": ("vendredi", "friday"),
    "heure": ("heure", "hour"), "mange": ("manger", "eat"), "pain": ("pain", "bread"), "près": ("près", "near|close"),
    "hôtel": ("hôtel", "hotel|mansion"), "musée": ("musée", "museum"), "voir": ("voir", "see"),
    "acheté": ("acheter", "buy|purchase"), "appartement": ("appartement", "apartment|flat"), "avais": ("avoir", "have"),
    "vraiment": ("vraiment", "really|truly"), "salut": ("salut", "hi|hello"), "allez": ("aller", "go"),
    "huit": ("huit", "eight"), "banque": ("banque", "bank"), "quelle": ("quelle", "which|what"), "ta": ("ta", "your"),
    "ou": ("ou", "or"), "eau": ("eau", "water"), "petit": ("petit", "small|little"), "travail": ("travail", "work|job"),
    "venir": ("venir", "come"), "prends": ("prendre", "take"), "carte": ("carte", "card|map|menu"), "sa": ("sa", "his|her"),
    "tard": ("tard", "late"), "mer": ("mer", "sea"), "encore": ("encore", "still|again|more"), "journée": ("journée", "day"),
    "retard": ("retard", "delay|late"), "raison": ("raison", "reason"), "parfait": ("parfait", "perfect"),
    "professeur": ("professeur", "teacher|professor"), "porte": ("porte", "door"), "ont": ("avoir", "have"),
    "six": ("six", "six"), "sais": ("savoir", "know"), "rue": ("rue", "street"), "bus": ("bus", "bus"),
    "arrive": ("arriver", "arrive"), "tôt": ("tôt", "early"),
    # the playtest's misses and the other function words
    "l'hôpital": ("hôpital", "hospital"), "qu'elle": ("elle", "she"), "qu'il": ("il", "he"), "allons": ("aller", "go"),
    "lue": ("lire", "read"), "étaient": ("être", "be"), "lui": ("lui", "him|her"), "leur": ("leur", "them|their"),
    "aux": ("aux|à", "to the|at the"), "fut": ("être", "be"), "l'eau": ("eau", "water"), "d'accord": ("d'accord", "agree|okay|ok"),
    "j'aime": ("j'aime", "love|like"), "faisons": ("faire", "do|make"), "mangeait": ("manger", "eat"), "irons": ("aller", "go"),
}

ZH = {
    "我": ("wǒ", "i; me"), "你": ("nǐ", "you"), "是": ("shì", "to be"), "吗": ("ma", "question"), "很": ("hěn", "very"),
    "在": ("zài", "to be (located)|at"), "点": ("diǎn", "o'clock|dot|point"), "吃": ("chī", "eat"),
    "了": ("le", "completed action"), "有": ("yǒu", "to have"), "好": ("hǎo", "good"), "的": ("de", "of|possessive"),
    "今天": ("jīntiān", "today"), "他": ("tā", "he"), "不": ("bù", "no; not|not"), "老师": ("lǎoshī", "teacher"),
    "什么": ("shénme", "what"), "中国": ("Zhōngguó", "china"), "去": ("qù", "to go"), "一": ("yī", "one"),
    "两": ("liǎng", "two"), "您": ("nín", "you"), "学校": ("xuéxiào", "school"), "喝": ("hē", "drink"),
    "喜欢": ("xǐhuan", "to like"), "我们": ("wǒmen", "we"), "没有": ("méiyǒu", "not have|haven't"), "想": ("xiǎng", "think|want"),
    "人": ("rén", "person|people"), "明天": ("míngtiān", "tomorrow"), "哪儿": ("nǎr", "where"), "买": ("mǎi", "buy"),
    "书": ("shū", "book"), "学生": ("xuésheng", "student"), "也": ("yě", "also"), "呢": ("ne", "particle"),
    "晚上": ("wǎnshang", "evening"), "医院": ("yīyuàn", "hospital"), "咖啡": ("kāfēi", "coffee"), "汉语": ("Hànyǔ", "chinese"),
    "说": ("shuō", "speak|say"), "没": ("méi", "not"), "妈妈": ("māma", "mother|mama"), "她": ("tā", "she"),
    "这": ("zhè", "this"), "现在": ("xiànzài", "now"), "北京": ("Běijīng", "beijing"), "要": ("yào", "want"),
    "这个": ("zhège", "this"), "会": ("huì", "can|know how"), "谢谢": ("xièxie", "thank"), "茶": ("chá", "tea"),
    "水": ("shuǐ", "water"), "一个": ("yīge", "a; an|one"), "个": ("gè", "classifier"), "叫": ("jiào", "to call|called"),
    "哥哥": ("gēge", "older brother"), "家": ("jiā", "home|family"), "八": ("bā", "eight"), "几点": ("jǐdiǎn", "what time"),
    "这儿": ("zhèr", "here"), "米饭": ("mǐfàn", "rice"), "饺子": ("jiǎozi", "dumpling"), "请": ("qǐng", "please|invite|ask"),
    "还": ("hái", "still|also"), "可以": ("kěyǐ", "can|may"), "块": ("kuài", "piece|lump|yuan|money"),
    "起床": ("qǐchuáng", "get up"), "每天": ("měitiān", "every day"), "昨天": ("zuótiān", "yesterday"),
    "天气": ("tiānqì", "weather"), "朋友": ("péngyou", "friend"), "三": ("sān", "three"), "请问": ("qǐngwèn", "excuse me|may i ask"),
    "名字": ("míngzi", "name"), "高兴": ("gāoxìng", "happy|glad"), "妹妹": ("mèimei", "younger sister"), "孩子": ("háizi", "child"),
    "四": ("sì", "four"), "下午": ("xiàwǔ", "afternoon"), "半": ("bàn", "half"), "商店": ("shāngdiàn", "store|shop"),
    "来": ("lái", "come"), "衣服": ("yīfu", "clothes"), "件": ("jiàn", "item|classifier"), "太": ("tài", "too"),
    "上班": ("shàngbān", "go to work"), "回家": ("huíjiā", "return home"), "忙": ("máng", "busy"), "你好": ("nǐhǎo", "hello"),
    "他们": ("tāmen", "they"), "认识": ("rènshi", "know|recognize"), "姐姐": ("jiějie", "older sister"), "和": ("hé", "and"),
    "几": ("jǐ", "how many"), "生日": ("shēngrì", "birthday"), "中午": ("zhōngwǔ", "noon"), "洗手间": ("xǐshǒujiān", "toilet"),
    "火车站": ("huǒchēzhàn", "train station"), "坐": ("zuò", "sit"), "怎么": ("zěnme", "how"), "早上": ("zǎoshang", "morning"),
    "杯": ("bēi", "cup"), "碗": ("wǎn", "bowl"), "给": ("gěi", "to give|for"), "多少": ("duōshǎo", "number|amount|how many"),
    "贵": ("guì", "expensive"), "便宜": ("piányi", "cheap"), "钱": ("qián", "money"), "电影": ("diànyǐng", "movie|film"),
    "工作": ("gōngzuò", "work|job"), "下雨": ("xiàyǔ", "rain"), "怎么样": ("zěnmeyàng", "how"), "知道": ("zhīdào", "know"),
    "爸爸": ("bàba", "father|dad"), "再见": ("zàijiàn", "goodbye"), "你们": ("nǐmen", "you"), "对不起": ("duìbuqǐ", "sorry"),
    "姓": ("xìng", "surname|family name"), "美国": ("Měiguó", "united states"), "哪": ("nǎ", "which|how"),
    "弟弟": ("dìdi", "younger brother"), "女儿": ("nǚ'ér", "daughter"), "口": ("kǒu", "mouth"), "七": ("qī", "seven"),
    "今年": ("jīnnián", "this year"), "二十": ("èrshí", "twenty"), "什么时候": ("shénmeshíhou", "when"),
    "前面": ("qiánmiàn", "ahead|in front"), "左边": ("zuǒbian", "left"), "右边": ("yòubian", "right"),
    "旁边": ("pángbiān", "side|adjacent"), "出租车": ("chūzūchē", "taxi"), "地铁": ("dìtiě", "subway|underground"),
    "走": ("zǒu", "walk"), "面条": ("miàntiáo", "noodles"), "水果": ("shuǐguǒ", "fruit"), "牛奶": ("niúnǎi", "milk"),
    "好吃": ("hǎochī", "tasty|delicious"), "菜": ("cài", "vegetable|dish"), "服务员": ("fúwùyuán", "waiter"),
    "菜单": ("càidān", "menu"), "瓶": ("píng", "bottle"), "英语": ("Yīngyǔ", "english"), "汉字": ("hànzì", "chinese character"),
    "写": ("xiě", "write"), "音乐": ("yīnyuè", "music"), "六": ("liù", "six"), "睡觉": ("shuìjiào", "sleep"),
    "下班": ("xiàbān", "finish work|get off work"), "晚饭": ("wǎnfàn", "dinner|evening meal"), "已经": ("yǐjīng", "already"),
    "非常": ("fēicháng", "very"), "热": ("rè", "hot|heat|warm"), "明白": ("míngbai", "understand|clear"),
    "意思": ("yìsi", "meaning|idea"), "为什么": ("wèishénme", "why"), "谁": ("shéi", "who"), "不是": ("bùshì", "not"),
    "十二": ("shí'èr", "twelve"), "不客气": ("bùkèqi", "you're welcome"), "儿子": ("érzi", "son"), "星期": ("xīngqī", "week"),
    "月": ("yuè", "moon|month"), "岁": ("suì", "year"), "大": ("dà", "big"), "时间": ("shíjiān", "time"),
    "上午": ("shàngwǔ", "morning"), "十": ("shí", "ten"), "住": ("zhù", "live|reside"), "后面": ("hòumian", "back|rear|behind"),
    "一直": ("yīzhí", "straight|continuously|always"), "远": ("yuǎn", "far"), "鸡蛋": ("jīdàn", "egg"), "肉": ("ròu", "meat"),
    "买单": ("mǎidān", "pay the bill"), "别的": ("biéde", "else|other"), "吧": ("ba", "suggestion|particle"),
    "学": ("xué", "learn|study"), "看": ("kàn", "see|look"), "听": ("tīng", "listen|hear"), "去年": ("qùnián", "last year"),
    "上个星期": ("shànggèxīngqī", "last week"), "打电话": ("dǎdiànhuà", "telephone call"), "票": ("piào", "ticket"),
    "漂亮": ("piàoliang", "pretty|beautiful"),
    # the playtest's misses
    "带": ("dài", "to carry"), "不过": ("bùguò", "however|but"), "雨": ("yǔ", "rain"), "星期六": ("xīngqīliù", "saturday"),
    "上个": ("shàngge", "last|previous|first"), "号": ("hào", "number|date|day of a month"),
}

JA = {
    "です": ("です", "be, is"), "は": ("は", "topic"), "か": ("か", "question"), "を": ("を", "direct object"),
    "に": ("に", "at, in|to"), "の": ("の", "possessive"), "で": ("で", "at, in|by"), "へ": ("へ", "to"),
    "が": ("が", "subject"), "さん": ("さん", "mr"), "わたし": ("わたし", "i, me"), "ください": ("ください", "please"),
    "これ": ("これ", "this"), "この": ("この", "this"), "いきます": ("いく", "go"), "します": ("する", "do"),
    "から": ("から", "from"), "います": ("いる", "be|exist"), "それ": ("それ", "that"), "たべます": ("たべる", "eat"),
    "あります": ("ある", "be|exist|have"), "ともだち": ("ともだち", "friend"), "うち": ("うち", "house|home"),
    "なに": ("なに", "what"), "がっこう": ("がっこう", "school"), "なん": ("なん", "what"), "いま": ("いま", "now"),
    "まで": ("まで", "until|to"), "ね": ("ね", "right?|isn't it"), "いいえ": ("いいえ", "no"), "ほん": ("ほん", "book"),
    "すみません": ("すみません", "excuse me|sorry"), "かいしゃ": ("かいしゃ", "company"), "にほんご": ("にほんご", "japanese"),
    "なんじ": ("なんじ", "what time"), "どこ": ("どこ", "where"), "かばん": ("かばん", "bag"), "まいにち": ("まいにち", "every day"),
    "かえります": ("かえる", "return|go home"), "いい": ("いい", "good"), "きのう": ("きのう", "yesterday"),
    "はい": ("はい", "yes"), "せんせい": ("せんせい", "teacher"), "がくせい": ("がくせい", "student"),
    "としょかん": ("としょかん", "library"), "ケーキ": ("ケーキ", "cake"), "テスト": ("テスト", "test"),
    "コンビニ": ("コンビニ", "convenience store"), "おねがい": ("おねがい", "request|please"), "いくら": ("いくら", "how much"),
    "みせ": ("みせ", "store|shop"), "どようび": ("どようび", "saturday"), "きょう": ("きょう", "today"),
    "あした": ("あした", "tomorrow"), "いっしょ": ("いっしょ", "together"), "へや": ("へや", "room"),
    "かさ": ("かさ", "umbrella"), "にほん": ("にほん", "japan"), "くるま": ("くるま", "car"), "ありがとう": ("ありがとう", "thank"),
    "コーヒー": ("コーヒー", "coffee"), "そう": ("そう", "so|in that way"), "だれ": ("だれ", "who"),
    "なんばん": ("なんばん", "what number"), "と": ("と", "and|with"), "くじ": ("くじ", "nine o'clock"),
    "さんじ": ("さんじ", "3 o'clock"), "ぎんこう": ("ぎんこう", "bank"), "すき": ("すき", "liking|fond"), "ねこ": ("ねこ", "cat"),
    "みず": ("みず", "water"), "どうぞ": ("どうぞ", "please"), "トイレ": ("トイレ", "toilet"), "きました": ("くる", "come"),
    "かいしゃいん": ("かいしゃいん", "company employee|office worker"), "も": ("も", "too|also"), "あれ": ("あれ", "that"),
    "でんわばんごう": ("でんわばんごう", "telephone number"), "りんご": ("りんご", "apple"), "おきます": ("おきる", "get up|rise"),
    "はん": ("はん", "half"), "ろくじ": ("ろくじ", "six o'clock"), "ごご": ("ごご", "afternoon"), "よる": ("よる", "night|evening"),
    "ねます": ("ねる", "sleep"), "にちようび": ("にちようび", "sunday"), "しゅうまつ": ("しゅうまつ", "weekend"),
    "のみます": ("のむ", "drink"), "みます": ("みる", "see|look|watch"), "べんきょう": ("べんきょう", "study"),
    "ひるごはん": ("ひるごはん", "lunch"), "えいが": ("えいが", "movie|film"), "した": ("する", "do"), "こうえん": ("こうえん", "park"),
    "テニス": ("テニス", "tennis"), "おいしい": ("おいしい", "delicious|tasting"), "あそこ": ("あそこ", "there"),
    "えき": ("えき", "station"), "じしょ": ("じしょ", "dictionary"), "でんしゃ": ("でんしゃ", "train"),
    "レストラン": ("レストラン", "restaurant"), "テレビ": ("テレビ", "television|tv"), "バス": ("バス", "bus"),
    "アメリカ": ("アメリカ", "america"), "いしゃ": ("いしゃ", "doctor"), "ありません": ("ある", "be|exist|have"),
    "とけい": ("とけい", "clock|watch"), "かぎ": ("かぎ", "key"), "えいご": ("えいご", "english"), "あの": ("あの", "that"),
    "いち": ("いち", "one"), "はは": ("はは", "mother"), "ふたつ": ("ふたつ", "two"), "きって": ("きって", "stamp"),
    "しちじ": ("しちじ", "seven o'clock"), "はちじ": ("はちじ", "eight o'clock"), "げつようび": ("げつようび", "monday"),
    "きます": ("くる", "come"), "やすみ": ("やすみ", "rest|holiday|vacation"), "ききます": ("きく", "hear|listen"),
    "おんがく": ("おんがく", "music"), "ごはん": ("ごはん", "rice|meal"), "けさ": ("けさ", "this morning"),
    "しました": ("する", "do"), "たかい": ("たかい", "high|tall|expensive"), "とても": ("とても", "very"),
    "まち": ("まち", "town"), "すし": ("すし", "sushi"), "あさ": ("あさ", "morning"), "つくえ": ("つくえ", "desk"),
    "おちゃ": ("おちゃ", "tea"), "ちょっと": ("ちょっと", "a little|a bit"), "ホテル": ("ホテル", "hotel"), "パン": ("パン", "bread"),
    "ペン": ("ペン", "pen"), "にほんじん": ("にほんじん", "japanese person"), "はじめまして": ("はじめまして", "nice to meet you"),
    "よろしく": ("よろしく", "well|regards"), "だいがく": ("だいがく", "university"), "しんぶん": ("しんぶん", "newspaper"),
    "もう": ("もう", "already"), "いちど": ("いちど", "once"), "ゆっくり": ("ゆっくり", "slowly"), "よん": ("よん", "four"),
    "その": ("その", "that"), "みっつ": ("みっつ", "three"), "えん": ("えん", "yen"), "たまご": ("たまご", "egg"),
    "いちじ": ("いちじ", "one o'clock"), "よじ": ("よじ", "four o'clock"), "いつ": ("いつ", "when"),
    "しんかんせん": ("しんかんせん", "shinkansen|bullet train"), "かいます": ("かう", "buy"), "あさごはん": ("あさごはん", "breakfast"),
    "いつも": ("いつも", "always"), "せんしゅう": ("せんしゅう", "last week"), "らいしゅう": ("らいしゅう", "next week"),
    "どう": ("どう", "how"), "おおきい": ("おおきい", "big|large"), "やすい": ("やすい", "cheap"), "ふるい": ("ふるい", "old"),
    "あつい": ("あつい", "hot"), "むずかしい": ("むずかしい", "difficult"), "きれい": ("きれい", "pretty|beautiful|clean"),
    "しずか": ("しずか", "quiet"), "げんき": ("げんき", "lively|healthy|energetic"), "でも": ("でも", "but"),
    "ここ": ("ここ", "here"), "となり": ("となり", "next|neighbo"), "ちかく": ("ちかく", "near"), "みぎ": ("みぎ", "right"),
    "ふたり": ("ふたり", "two persons|two people"), "こども": ("こども", "child"), "ひと": ("ひと", "person"),
    "なまえ": ("なまえ", "name"), "おはよう": ("おはよう", "good morning"), "でんわ": ("でんわ", "telephone|phone"),
    "どういたしまして": ("どういたしまして", "you're welcome"), "ノート": ("ノート", "notebook"), "トマト": ("トマト", "tomato"),
    "ジュース": ("ジュース", "juice"), "ビール": ("ビール", "beer"), "あなた": ("あなた", "you"), "どちら": ("どちら", "which|where"),
    "どれ": ("どれ", "which"), "えんぴつ": ("えんぴつ", "pencil"), "ざっし": ("ざっし", "magazine"),
    "わかりません": ("わかる", "understand"), "わかりました": ("わかる", "understand"), "にじゅう": ("にじゅう", "twenty"),
    "ばんごう": ("ばんごう", "number"), "ちち": ("ちち", "father"), "いくつ": ("いくつ", "how many|how old"),
    "ひとつ": ("ひとつ", "one"), "いらっしゃいませ": ("いらっしゃいませ", "welcome"), "ごぜん": ("ごぜん", "morning|a.m"),
    "じゅうじ": ("じゅうじ", "ten o'clock"), "ひる": ("ひる", "noon|daytime"), "どうも": ("どうも", "thank"),
    "かようび": ("かようび", "tuesday"), "すいようび": ("すいようび", "wednesday"),
    # the playtest's misses
    "写真": ("写真", "photograph|photo"), "撮りました": ("撮る", "take"), "銀行": ("銀行", "bank"),
}

KO = {
    "있어요": ("있다", "exist|have|be"), "네": ("네", "yes"), "주세요": ("주다", "give"), "저는": ("저", "i, me"),
    "뭐": ("뭐", "what"), "없어요": ("없다", "none|not|lack"), "이": ("이", "this"), "한": ("한", "one"),
    "가세요": ("가다", "go"), "가요": ("가다", "go"), "감사합니다": ("감사합니다", "thank"), "명": ("명", "counter for people"),
    "잘": ("잘", "well"), "한국": ("한국", "korea"), "사람이에요": ("사람", "person"), "이거": ("이거", "this"),
    "두": ("두", "two"), "세": ("세", "three"), "몇": ("몇", "how many"), "해요": ("하다", "do"),
    "한국어를": ("한국어", "korean"), "싶어요": ("싶다", "want"), "안녕하세요": ("안녕하세요", "hello|how are you"),
    "만나요": ("만나다", "meet"), "시간이": ("시간", "time|hour"), "시": ("시", "hour|o'clock"), "주말에": ("주말", "weekend"),
    "내일": ("내일", "tomorrow"), "먹어요": ("먹다", "eat"), "공부해요": ("공부하다", "study"), "맛있어요": ("맛있다", "delicious"),
    "사요": ("사다", "buy"), "너무": ("너무", "too|very"), "아니요": ("아니요", "no"), "물": ("물", "water"),
    "아니에요": ("아니다", "not"), "회사원이에요": ("회사원", "office worker|employee"), "오늘": ("오늘", "today"),
    "얼마예요": ("얼마", "how much"), "오세요": ("오다", "come"), "병": ("병", "bottle"), "지금": ("지금", "now"),
    "마셔요": ("마시다", "drink"), "우리": ("우리", "we"), "매워요": ("맵다", "spicy"), "좋아해요": ("좋아하다", "like"),
    "어제": ("어제", "yesterday"), "왔어요": ("오다", "come"), "했어요": ("하다", "do"), "할": ("하다", "do"),
    "괜찮아요": ("괜찮다", "ok|all right|good|fine"), "반갑습니다": ("반갑다", "glad"), "씨": ("씨", "mr"),
    "대학생이에요": ("대학생", "student"), "친구가": ("친구", "friend"), "원": ("원", "won"), "개": ("개", "counter|item"),
    "잔": ("잔", "cup"), "좋아요": ("좋다", "good"), "학교에": ("학교", "school"), "봐요": ("보다", "see|look"),
    "영화를": ("영화", "movie|film"), "읽어요": ("읽다", "read"), "책을": ("책", "book"), "저녁에": ("저녁", "evening"),
    "비싸요": ("비싸다", "expensive"), "멀어요": ("멀다", "far"), "먹었어요": ("먹다", "eat"),
    "재미있었어요": ("재미있다", "interesting|fun|amusing"), "다시": ("다시", "again"), "여기": ("여기", "here"),
    "나라": ("나라", "country"), "커피": ("커피", "coffee"), "사과": ("사과", "apple"), "계세요": ("계시다", "stay|be"),
    "죄송합니다": ("죄송하다", "sorry"), "만나서": ("만나다", "meet"), "또": ("또", "again|also"), "그럼": ("그럼", "then"),
    "미국": ("미국", "america|united states"), "학생이에요": ("학생", "student"), "의사예요": ("의사", "doctor"),
    "돈이": ("돈", "money"), "가방에": ("가방", "bag"), "번": ("번", "time|number"), "십": ("십", "ten|10"),
    "오천": ("오천", "5,000"), "하나": ("하나", "one"), "드릴까요": ("주다", "give"), "오후": ("오후", "afternoon|p.m"),
    "친구를": ("친구", "friend"), "와요": ("오다", "come"), "집에": ("집", "house|home"), "학교에서": ("학교", "school"),
    "아침에": ("아침", "morning|breakfast"), "가족은": ("가족", "family"), "불고기를": ("불고기", "bulgogi"),
    "비빔밥": ("비빔밥", "bibimbap"), "안": ("안", "not"), "좀": ("좀", "little|please"), "조금": ("조금", "little|bit"),
    "싸요": ("싸다", "cheap"), "커요": ("크다", "big"), "작아요": ("작다", "small"), "못": ("못", "cannot"),
    "가까워요": ("가깝다", "close|near"), "갔어요": ("가다", "go"), "보냈어요": ("보내다", "send|spend"), "가고": ("가다", "go"),
    "천천히": ("천천히", "slowly"), "말해": ("말하다", "speak|talk|say"), "차": ("차", "vehicle|car"), "사람": ("사람", "person"),
    "선생님은": ("선생님", "teacher"), "이름이": ("이름", "name"), "어느": ("어느", "which"), "그래요": ("그렇다", "so|thus"),
    "휴대폰이": ("휴대폰", "phone"), "화장실이": ("화장실", "bathroom|toilet|restroom"), "어디에": ("어디", "where"),
    "삼월": ("삼월", "march"), "오월": ("오월", "may"), "육": ("육", "6|six"), "칠월": ("칠월", "july"), "천": ("천", "thousand"),
    "만": ("만", "ten thousand"), "삼만": ("삼만", "30,000"), "저거는": ("저거", "that"), "다섯": ("다섯", "five"),
    "일곱": ("일곱", "seven"), "열": ("열", "ten"), "살이에요": ("살", "years|age"), "분": ("분", "minute"), "반": ("반", "half"),
    "오전": ("오전", "a.m|morning|forenoon"), "자요": ("자다", "sleep"), "우유를": ("우유", "milk"),
    "언니가": ("언니", "older sister"), "동생이": ("동생", "younger sibling"), "밥을": ("밥", "rice|meal"), "맥주": ("맥주", "beer"),
    "음식을": ("음식", "food"), "싫어해요": ("싫어하다", "dislike|hate|detest|loathe"), "먹겠습니다": ("먹다", "eat"),
    "김치를": ("김치", "kimchi"), "옷을": ("옷", "clothes|clothing"), "신발": ("신발", "shoes"), "카드": ("카드", "card"),
    "병원": ("병원", "hospital"), "편의점": ("편의점", "convenience store"), "은행은": ("은행", "bank"), "옆에": ("옆", "side"),
    "근처에": ("근처", "vicinity|near|neighborhood"), "역이": ("역", "station"), "실례합니다": ("실례하다", "rude|excuse"),
    "왼쪽으로": ("왼쪽", "left"), "지난주에": ("지난주", "last week"), "언제": ("언제", "when"), "어떻게": ("어떻게", "how"),
    "봤어요": ("보다", "see"),
    # the playtest's misses and other homographs
    "시장": ("시장", "market"), "시장에서": ("시장", "market"), "눈": ("눈", "eye"), "밤": ("밤", "night"),
    "다리": ("다리", "leg"), "팔": ("팔", "arm"), "배": ("배", "belly|abdomen"), "말": ("말", "speech|language"),
}

LISTS = {"es": ES, "fr": FR, "zh": ZH, "ja": JA, "ko": KO}


def check(lang: str, word: str, want: tuple[str, str], r: dict) -> str:
    """"" if the lookup ``r`` of ``word`` is right, else what is wrong."""
    if not r.get("found") or not r.get("senses"):
        return "not found"
    first = str(r["senses"][0].get("text", "")).lower()
    if lang == "zh":
        reading, kw = want
        if str(r.get("reading", "")).lower() != reading.lower():
            return f"reading {r.get('reading')!r}, want {reading!r}"
    else:
        lemma, kw = want
        if r.get("lemma") not in lemma.split("|"):
            return f"lemma {r.get('lemma')!r}, want {lemma!r}"
    if not any(k in first for k in kw.lower().split("|")):
        return f"first sense {first[:70]!r}, want {kw!r}"
    return ""


def accuracy(lang: str) -> tuple[int, int, list[str]]:
    from sect_academy import lexicon
    mod = lexicon.get(lang)
    bad = []
    for word, want in LISTS[lang].items():
        why = check(lang, word, want, mod.lookup(word, {}))
        if why:
            bad.append(f"{word}: {why}")
    return len(LISTS[lang]) - len(bad), len(LISTS[lang]), bad


if __name__ == "__main__":
    sys.path.insert(0, os.getcwd())             # the tree to measure is the one this is run from
    for lang in sys.argv[1:] or list(LISTS):
        ok, n, bad = accuracy(lang)
        print(f"{lang}: {ok}/{n} right ({ok / n:.0%})")
        for b in bad:
            print("   ", b)
