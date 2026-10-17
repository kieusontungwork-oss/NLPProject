"""Subfield mapping (single source): arXiv categories -> the seven question subfields (+ "Other CS").

Story 1.6 · CAP-6 · AD-1. The first group, in priority order, whose category set intersects a paper's
categories wins; no match -> "Other CS". The quotas below follow the real KB composition (2026-10-17).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable

logger = logging.getLogger(__name__)

OTHER_SUBFIELD = "Other CS"

SUBFIELD_GROUPS: tuple[tuple[str, frozenset[str]], ...] = (
    ("NLP & IR", frozenset({"cs.CL", "cs.IR"})),
    ("Computer vision", frozenset({"cs.CV", "cs.GR", "cs.MM"})),
    ("Machine learning & AI", frozenset({"cs.LG", "cs.AI", "cs.NE", "stat.ML", "cs.RO", "cs.MA"})),
    ("Information theory & signals", frozenset({"cs.IT"})),
    ("Networks & social", frozenset({"cs.NI", "cs.SI"})),
    (
        "Algorithms & theory",
        frozenset({"cs.DS", "cs.DM", "cs.CC", "cs.CG", "cs.GT", "cs.LO", "cs.FL", "cs.SC", "cs.NA"}),
    ),
    (
        "Systems, security & data",
        frozenset({"cs.DC", "cs.CR", "cs.SY", "cs.DB", "cs.SE", "cs.PL", "cs.AR", "cs.OS", "cs.PF", "cs.ET", "cs.MS"}),
    ),
)

QUESTION_SUBFIELDS: tuple[str, ...] = tuple(name for name, _ in SUBFIELD_GROUPS)
QUESTION_TYPES: tuple[str, ...] = ("terminology-mismatch", "exact-term", "survey", "comparison")

TYPE_QUOTA: dict[str, int] = {"terminology-mismatch": 15, "exact-term": 15, "survey": 10, "comparison": 10}
SUBFIELD_QUOTA: dict[str, int] = {
    "Machine learning & AI": 10,
    "NLP & IR": 8,
    "Computer vision": 7,
    "Information theory & signals": 7,
    "Algorithms & theory": 7,
    "Networks & social": 6,
    "Systems, security & data": 5,
}


def subfield_of(categories: Iterable[str]) -> str:
    """Map a paper's arXiv categories to its subfield group (priority order), else "Other CS"."""
    cats = set(categories)
    for name, group in SUBFIELD_GROUPS:
        if cats & group:
            return name
    return OTHER_SUBFIELD
