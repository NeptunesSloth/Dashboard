"""Drills made on the spot: subnetting and well-known ports.

These are skills, not facts to space out: the only way to get fast at subnetting is to do
a great many fresh problems. Each drill is ten generated questions, graded here, with the
working shown. Nothing is scheduled and nothing is paid; the best score is remembered.

Language drills work the same way: verb forms (``drills_lang``: Spanish and French from the
dictionary's conjugation tables, Japanese and Korean conjugated by rule) and numbers, times,
dates, prices and counters (``drills_num``). Their kinds are ``conj-<lang>`` and ``num-<lang>``;
the learner picks the tenses or question types and the length (``opts``). A typed answer is
graded by the course's own rules (``engine.check_typed``, with no typo forgiveness: one letter
is often the grammar), so a missing accent is accepted and flagged, and Chinese, Japanese and
Korean may be answered in the script or its romanisation.
"""
from __future__ import annotations

import ipaddress
import random
import re
import unicodedata
import uuid

from . import drills_lang, drills_num, engine

SIZE = 10
# (service, port, transport) as the Network+ and Security+ objectives list them
PORTS = [
    ("FTP data", 20, "TCP"), ("FTP control", 21, "TCP"), ("SSH / SFTP", 22, "TCP"), ("Telnet", 23, "TCP"), ("SMTP", 25, "TCP"),
    ("TACACS+", 49, "TCP"), ("DNS", 53, "TCP and UDP"), ("DHCP server", 67, "UDP"), ("DHCP client", 68, "UDP"), ("TFTP", 69, "UDP"),
    ("HTTP", 80, "TCP"), ("Kerberos", 88, "TCP and UDP"), ("POP3", 110, "TCP"), ("NTP", 123, "UDP"), ("IMAP", 143, "TCP"),
    ("SNMP", 161, "UDP"), ("SNMP traps", 162, "UDP"), ("LDAP", 389, "TCP"), ("HTTPS", 443, "TCP"), ("SMB", 445, "TCP"),
    ("Syslog", 514, "UDP"), ("SMTP submission (STARTTLS)", 587, "TCP"), ("LDAPS", 636, "TCP"), ("IMAPS", 993, "TCP"), ("POP3S", 995, "TCP"),
    ("Microsoft SQL Server", 1433, "TCP"), ("RADIUS authentication", 1812, "UDP"), ("RADIUS accounting", 1813, "UDP"),
    ("MySQL", 3306, "TCP"), ("RDP", 3389, "TCP"), ("SIP", 5060, "TCP and UDP"), ("SIP over TLS", 5061, "TCP"),
]
KINDS = {"subnet": "Subnetting", "ports": "Ports and protocols"}
LANGS = {"es": "Spanish", "fr": "French", "zh": "Chinese", "ja": "Japanese", "ko": "Korean"}
CONJ_LANGS = ("es", "fr", "ja", "ko")
for _l, _n in LANGS.items():
    if _l in CONJ_LANGS:
        KINDS[f"conj-{_l}"] = f"{_n} verbs"
    KINDS[f"num-{_l}"] = f"{_n} numbers"
MIN_SIZE, MAX_SIZE = 5, 30
HINT = {"ja": "Type kana or rōmaji", "ko": "Type Hangul or romanisation", "zh": "Type characters or pinyin (tone marks or numbers)"}
_open: dict[str, dict] = {}          # in-flight drills (answers stay on the server)


def _subnet_q(r: random.Random) -> dict:
    prefix = r.choice([24, 25, 26, 27, 28, 29, 30, 26, 27, 28, 22, 23, 20, 21, 19, 18])
    first = r.choice([10, 172, 192])
    host = ipaddress.IPv4Address(f"{first}.{r.randint(16, 31) if first == 172 else 168 if first == 192 else r.randint(0, 255)}.{r.randint(0, 255)}.{r.randint(1, 254)}")
    net = ipaddress.IPv4Network(f"{host}/{prefix}", strict=False)
    if host in (net.network_address, net.broadcast_address):
        host = net.network_address + 1
    hosts = net.num_addresses - 2
    octet = 3 if prefix > 24 else 2 if prefix > 16 else 1
    block = 2 ** (8 - (prefix - 8 * octet)) if prefix % 8 else 256
    work = (f"/{prefix} is mask {net.netmask}: the block size in octet {octet + 1} is {block}, so networks start at multiples of {block} there. "
            f"{host} falls in {net.network_address} to {net.broadcast_address}; usable hosts are {net.network_address + 1} to {net.broadcast_address - 1} ({hosts}).")
    kind = r.choice(["network", "broadcast", "hosts", "mask", "first", "last", "prefix_for", "same"])
    if kind == "network":
        return {"q": f"What is the network address of {host}/{prefix}?", "a": [str(net.network_address)], "why": work}
    if kind == "broadcast":
        return {"q": f"What is the broadcast address of {host}/{prefix}?", "a": [str(net.broadcast_address)], "why": work}
    if kind == "hosts":
        return {"q": f"How many usable host addresses are in a /{prefix} network?", "a": [str(hosts)],
                "why": f"2^{32 - prefix} = {net.num_addresses} addresses, minus the network and broadcast addresses = {hosts}."}
    if kind == "mask":
        return {"q": f"Write /{prefix} as a dotted-decimal subnet mask.", "a": [str(net.netmask)], "why": f"{prefix} one-bits: {net.netmask}."}
    if kind == "first":
        return {"q": f"What is the first usable host address in the subnet of {host}/{prefix}?", "a": [str(net.network_address + 1)], "why": work}
    if kind == "last":
        return {"q": f"What is the last usable host address in the subnet of {host}/{prefix}?", "a": [str(net.broadcast_address - 1)], "why": work}
    if kind == "prefix_for":
        need = r.choice([2, 5, 6, 10, 14, 25, 30, 50, 62, 100, 126, 200, 254, 500, 1000])
        p = next(x for x in range(30, 15, -1) if 2 ** (32 - x) - 2 >= need)
        return {"q": f"What is the longest prefix (smallest subnet) that fits {need} hosts? Answer like /26.", "a": [f"/{p}", str(p)],
                "why": f"/{p} gives {2 ** (32 - p) - 2} usable addresses; /{p + 1} gives only {2 ** (32 - p - 1) - 2}."}
    other = (net.broadcast_address + r.randint(1, 6)) if r.random() < 0.5 and int(net.broadcast_address) < 2 ** 32 - 10 else net.network_address + r.randint(1, max(1, hosts))
    if other == host:
        other = net.network_address + 1 if host != net.network_address + 1 else net.broadcast_address - 1
    same = other in net
    return {"q": f"Are {host} and {other} in the same /{prefix} subnet? (yes or no)", "a": ["yes", "y"] if same else ["no", "n"],
            "why": work + (" Both are inside it." if same else f" {other} is outside it.")}


def _port_q(r: random.Random) -> dict:
    name, port, proto = r.choice(PORTS)
    if r.random() < 0.55:
        return {"q": f"Which port does {name} use?", "a": [str(port)], "why": f"{name}: port {port} ({proto})."}
    wrong = r.sample([n for n, p, _ in PORTS if p != port], 3)
    choices = wrong + [name]
    r.shuffle(choices)
    return {"q": f"What runs on port {port}?", "a": [name], "choices": choices, "why": f"Port {port} ({proto}) is {name}."}


def options(lang: str) -> dict:
    """What a learner can choose for this language's drills."""
    if lang not in LANGS:
        return {"ok": False, "error": "unknown language"}
    out = {"ok": True, "lang": lang, "name": LANGS[lang], "num": drills_num.options(lang), "sizes": [10, 20, 30]}
    if lang in CONJ_LANGS:
        out["conj"] = drills_lang.options(lang)
    return out


def _ids(v, cap: int = 12) -> list[str]:
    return [x for x in v if isinstance(x, str) and len(x) <= 16][:cap] if isinstance(v, list) else []


def _maker(kind: str, r: random.Random, opts: dict):
    if kind == "subnet":
        return lambda: _subnet_q(r)
    if kind == "ports":
        return lambda: _port_q(r)
    what, _, lang = kind.partition("-")
    if what == "conj":
        vset = opts.get("set") if isinstance(opts.get("set"), str) and opts["set"] in drills_lang.SETS else "all"
        return drills_lang.make(lang, r, _ids(opts.get("tenses")), vset)
    return drills_num.make(lang, r, _ids(opts.get("kinds")))


def start(kind: str, seed: int | None = None, opts: dict | None = None) -> dict:
    if kind not in KINDS:
        return {"ok": False, "error": "unknown drill"}
    opts = opts if isinstance(opts, dict) else {}
    r = random.Random(seed)
    make = _maker(kind, r, opts)
    size = SIZE
    if kind not in ("subnet", "ports") and isinstance(opts.get("size"), int) and not isinstance(opts.get("size"), bool):
        size = max(MIN_SIZE, min(MAX_SIZE, opts["size"]))
    qs, seen = [], set()
    for _ in range(size * 40):                 # a narrow choice (one tense, one kind) may run out of fresh questions
        if len(qs) >= size:
            break
        q = make()
        if q and q["q"] not in seen:
            seen.add(q["q"])
            qs.append(q)
    if not qs:
        return {"ok": False, "error": "Nothing to ask with those choices."}
    did = uuid.uuid4().hex[:12]
    for old in list(_open)[:-8]:
        _open.pop(old, None)
    _open[did] = {"kind": kind, "qs": qs, "done": {}}
    return {"ok": True, "drill": did, "kind": kind, "name": KINDS[kind],
            "questions": [{"n": i, "q": q["q"], "choices": q.get("choices"), "lang": q.get("lang", ""),
                           "hint": HINT.get(q.get("lang", ""), "")} for i, q in enumerate(qs)]}


def _norm(s: str) -> str:
    return " ".join(str(s or "").strip().lower().split())


def answer(drill: str, n: int, given: str) -> dict:
    d = _open.get(drill)
    if not d or not 0 <= n < len(d["qs"]):
        return {"ok": False, "error": "This drill has expired. Start a new one."}
    q = d["qs"][n]
    ok, flag = grade(q, given)
    first = n not in d["done"]
    d["done"].setdefault(n, ok)                      # only the first answer counts
    finished = len(d["done"]) == len(d["qs"])
    counted = finished and (d.get("counted") or not first)
    if finished:
        d["counted"] = True
    return {"ok": True, "counted": bool(counted), "correct": ok, "flag": flag, "expected": q.get("show") or q["a"][0], "why": q["why"],
            "score": sum(1 for v in d["done"].values() if v), "answered": len(d["done"]), "total": len(d["qs"]), "kind": d["kind"],
            "finished": finished}


_GROUPING = re.compile(r"[\s,.'’_\u00a0\u202f]")


def grade(q: dict, given) -> tuple[bool, str | None]:
    """(correct, flag) for an answer to a generated question; flag is "accent" or "tone" for a forgiven slip."""
    given = given if isinstance(given, str) else ""
    how = q.get("grade", "plain")
    if how == "digits":
        got = _GROUPING.sub("", unicodedata.normalize("NFKC", given))
        return got.isascii() and got.isdigit() and len(got) <= 12 and int(got) == int(q["a"][0]), None
    if how == "typed":
        res = engine.check_typed(given, q["a"], slips=False)
        return bool(res["correct"]), res.get("flag")
    return _norm(given) in {_norm(a) for a in q["a"]}, None
