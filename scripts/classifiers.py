# scripts/classifiers.py
"""Regex classifiers for the SentiScope feasibility study (Electronics reviews)."""

import re

ASPECT_LEXICON = {
    "battery": [r"\bbatt(?:ery|eries)\b", r"\bcharging\b", r"\bcharge life\b"],
    "sound_quality": [r"\bsounds?\b", r"\bsound\b", r"\baudio\b", r"\bbass\b", r"\btreble\b", r"\bsoundstage\b"],
    "noise_cancelling": [r"\bnoise[ -]cancell?(?:ing|ation)\b", r"\bANC\b", r"\bambient (?:mode|sound)\b", r"\btransparency mode\b"],
    "comfort": [r"\bcomfort(?:able|ably)?\b", r"\bear ?(?:fatigue|pain|sore|hurts?)\b", r"\bclamping?\b", r"\bwore (?:them|it) all day\b"],
    "microphone": [r"\bmics?\b", r"\bmicrophone\b", r"\bvoice ?(?:quality|pick ??up)\b"],
    "build_quality": [r"\bbuild\b", r"\bsturdy\b", r"\bwell[ -]made\b", r"\bcheap(?:ly)?[ -](?:made|feeling)\b", r"\bflimsy\b", r"\bplasticky\b"],
    "price_value": [r"\bprice[ds]?\b", r"\bworth\b", r"\bvalue\b", r"\bexpensive\b", r"\boverpriced\b", r"\bsteep\b"],
    "connectivity": [r"\bbluetooth\b", r"\bpairs? with\b", r"\bconnect(?:s|ion|ivity)?\b", r"\bdrop ?outs?\b", r"\bmultipoint\b"],
    "fit": [r"\bfit(?:s|ting|ted)?\b", r"\bsize\b", r"\btoo (?:big|small|tight|loose)\b"],
    "app_software": [r"\bapp\b", r"\bfirmware\b", r"\bsoftware\b"],
    "screen_display": [r"\bscreen\b", r"\bdisplay\b", r"\btouch ?screen\b"],
    "setup_ease": [r"\bset[ -]?up\b", r"\bsetup\b", r"\binstall(?:ation|ed|ing)?\b"],
    "durability": [r"\bdurab\w*\b", r"\blongevity\b", r"\bstands? up to\b"],
    "warranty_support": [r"\bwarranty\b", r"\bcustomer (?:service|support)\b", r"\brefund\b"],
}

_NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "eighteen": 18, "twenty": 20,
}
_UNIT_TO_MONTHS = {"day": 1 / 30.4, "week": 1 / 4.345, "month": 1.0, "year": 12.0}
_NUM_ALT = "|".join(list(_NUM_WORDS) + [r"\d{1,3}(?:\.\d+)?"])

_DURATION_RE = re.compile(r"\b(" + _NUM_ALT + r")\s*\+?\s*(day|week|month|year)s?\b", re.IGNORECASE)
_DURATION_IN_RE = re.compile(r"\b(" + _NUM_ALT + r")\s+(day|week|month|year)s?\s+in\b", re.IGNORECASE)
_OWNERSHIP_CTX_RE = re.compile(
    r"(after|own(?:ed|er|ing)|have had|has had|i.?ve had|had (?:it|them|this|these|mine)|"
    r"of (?:use|ownership|daily|light|heavy)|daily use|update|later|since|purchase|bought|"
    r"got (?:it|them|this|these)|used|still (?:going|working|using))",
    re.IGNORECASE,
)

DURABILITY_LEXICON = {
    "hinge": [r"\bhinges?\b"],
    "battery_degradation": [
        r"\bbattery\b[^.!?]{0,80}\b(degrad\w*|drains?\b|draining|doesn.?t hold|no longer holds|"
        r"life (?:has )?(?:dropped|decreased|shortened|gone down|deteriorat\w*))",
        r"\bdegraded\b[^.!?]{0,60}\bbattery\b",
    ],
    "stopped_working": [
        r"stopped working", r"quit working", r"ceased (?:to )?(?:work|function)",
        r"won.?t (?:turn on|power on|charge)", r"dead (?:on arrival|after)", r"stopped charging",
    ],
    "broke_cracked": [r"\bbroke\b", r"\bbroken\b", r"\bcracked\b", r"\bsnapped\b", r"\bshattered\b", r"\b(?:fell|falls?|falling|came|coming) apart\b"],
    "worn_out": [r"\bworn (?:out|down)\b", r"\bfrayed\b", r"\bpeeling\b", r"\bflaking\b", r"\bfoam (?:crumbled|flattened|deteriorated)\b"],
    "intermittent_fault": [
        r"\bintermittent\w*\b", r"cuts? (?:in )?and out",
        r"one (?:side|ear ?cup|channel|bud) (?:stopped|died|went (?:out|dead))",
    ],
    "connection_failure": [r"\bconnection (?:drops?|issues?|problems?)\b", r"\bkeeps? disconnect\w*\b", r"\bwon.?t pair\b", r"\bcan.?t connect\b"],
}

_aspects_c = {a: [re.compile(p, re.IGNORECASE) for p in ps] for a, ps in ASPECT_LEXICON.items()}
_durab_c = {a: [re.compile(p, re.IGNORECASE) for p in ps] for a, ps in DURABILITY_LEXICON.items()}


def _scan(text, compiled):
    if not text:
        return set()
    return {name for name, pats in compiled.items() if any(p.search(text) for p in pats)}


def detect_aspects(text):
    """Return set of aspect names discussed in `text`."""
    return _scan(text, _aspects_c)


def detect_durability_issues(text):
    """Return set of durability/failure categories present in `text`."""
    return _scan(text, _durab_c)


def detect_duration_cue(text):
    """Return {'months': float, 'snippet': str} for the first explicit
    ownership-duration mention, else None. 'N units in' phrasing
    (e.g. 'three months in') is accepted without extra context."""
    if not text:
        return None
    m = _DURATION_IN_RE.search(text)
    if m:
        num = _to_number(m.group(1))
        if num is not None:
            months = num * _UNIT_TO_MONTHS[m.group(2).lower()]
            return {"months": round(months, 1), "snippet": _window(text, m)}
    for m in _DURATION_RE.finditer(text):
        window = _window(text, m)
        if _OWNERSHIP_CTX_RE.search(window):
            num = _to_number(m.group(1))
            if num is None:
                continue
            months = num * _UNIT_TO_MONTHS[m.group(2).lower()]
            return {"months": round(months, 1), "snippet": window}
    return None


def _to_number(group):
    if group.isdigit():
        return int(group)
    try:
        return float(group)
    except ValueError:
        return _NUM_WORDS.get(group.lower())


def _window(text, m, pad=60):
    return text[max(0, m.start() - pad):min(len(text), m.end() + pad)].strip()
