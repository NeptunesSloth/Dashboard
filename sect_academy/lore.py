"""Names and tables for the cultivation world. Data only; the rules are in colony.py."""
from __future__ import annotations

RANKS = ["Outer Disciple", "Inner Disciple", "Core Disciple", "Elder"]
GRADES = ["Yellow", "Mystic", "Earth", "Heaven"]

# kind: what it improves. bonus is per grade (Yellow .. Heaven).
MANUAL_BONUS = {
    "qi":      (0.10, 0.20, 0.35, 0.55),     # qi from meditation
    "sword":   (0.10, 0.20, 0.35, 0.55),     # combat strength
    "body":    (0.10, 0.18, 0.26, 0.35),     # damage taken, reduced
    "alchemy": (0.15, 0.30, 0.45, 0.60),     # pill brewing
}
MANUAL_KIND = {"qi": "Cultivation method", "sword": "Combat art", "body": "Body tempering", "alchemy": "Alchemy canon"}
MANUALS = {
    "breathing":    {"name": "Basic Breathing Method", "grade": 0, "kind": "qi"},
    "iron_skin":    {"name": "Iron Skin Exercises", "grade": 0, "kind": "body"},
    "falling_leaf": {"name": "Falling Leaf Sword", "grade": 0, "kind": "sword"},
    "herb_primer":  {"name": "Hundred Herbs Primer", "grade": 0, "kind": "alchemy"},
    "azure_tide":   {"name": "Azure Tide Scripture", "grade": 1, "kind": "qi"},
    "nine_cuts":    {"name": "Nine Cuts of the Autumn Wind", "grade": 1, "kind": "sword"},
    "bronze_body":  {"name": "Bronze Bell Body", "grade": 1, "kind": "body"},
    "cauldron":     {"name": "Three Flames Cauldron Canon", "grade": 1, "kind": "alchemy"},
    "star_river":   {"name": "Star River Meridian Art", "grade": 2, "kind": "qi"},
    "thunder_palm": {"name": "Heaven-Splitting Thunder Palm", "grade": 2, "kind": "sword"},
    "vajra":        {"name": "Indestructible Vajra Sutra", "grade": 2, "kind": "body"},
    "pill_sage":    {"name": "Notes of the Pill Sage", "grade": 2, "kind": "alchemy"},
    "primordial":   {"name": "Primordial Chaos Scripture", "grade": 3, "kind": "qi"},
    "sword_dao":    {"name": "One Sword Severs the Heavens", "grade": 3, "kind": "sword"},
    # forbidden: strong, open to any rank, and it costs the heart
    "blood_sutra":  {"name": "Blood Sutra of Ten Thousand Souls", "grade": 3, "kind": "qi", "demonic": True},
}

TREASURES = {
    "spirit_sword":  {"name": "Frostlight Spirit Sword", "text": "+15% to the sect's fighting strength."},
    "pill_furnace":  {"name": "Purple Cloud Pill Furnace", "text": "+30% pill brewing."},
    "jade_slip":     {"name": "Ancient Jade Slip", "text": "+25% research."},
    "array_flag":    {"name": "Nine Dragons Array Flag", "text": "+40% Ward Formation strength."},
    "spirit_spring": {"name": "Spirit Spring Stone", "text": "+10% qi from meditation for everyone."},
    "beast_bell":    {"name": "Beast-Taming Bell", "text": "Beast tides are a third weaker."},
    "pouch":         {"name": "Mustard-Seed Storage Pouch", "text": "The stores hold 30% more."},
    "lightning_rod": {"name": "Tribulation Lightning Pearl", "text": "+10% to every tribulation."},
}

BEASTS = ["Snow Spirit Fox", "Azure-Eyed Tiger Cub", "Three-Tailed Flame Cat", "Iron-Feather Crane", "Jade Qilin Foal"]

# (name, kind, young master's surname)
SECTS = [
    ("Azure Cloud Sect", "righteous", "Murong"), ("Heavenly Sword Pavilion", "righteous", "Dugu"),
    ("Jade Lotus Palace", "righteous", "Shangguan"), ("Nine Suns Sect", "righteous", "Ouyang"),
    ("Blood Fiend Sect", "demonic", "Xue"), ("Thousand Poison Valley", "demonic", "Wan"),
    ("Soul-Devouring Hall", "demonic", "Yin"), ("Black Wind Stronghold", "demonic", "Hei"),
    ("Golden Abacus Guild", "neutral", "Qian"), ("Hundred Beasts Mountain", "neutral", "Shi"),
    ("Misty Rain Tower", "neutral", "Liu"), ("Iron Fist Clan", "neutral", "Tie"),
]
KIND_START_REL = {"righteous": 10, "neutral": 0, "demonic": -25}
YOUNG_GIVEN = ["Tianba", "Aotian", "Wushuang", "Shaoyu", "Baichuan", "Kuang", "Yunfei", "Longxiao"]
EPITHETS = ["the Face-Slapper", "Young-Master's Bane", "the Unbowed"]

RING_LINES = [
    "Thirty years east of the river, thirty years west of the river. Do not bully the young for being poor.",
]
