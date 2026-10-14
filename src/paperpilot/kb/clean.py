"""Clean stage: boilerplate stripping, English filter, normalization (E-6, E-8, E-12).

Story 1.2 · CAP-1. Boilerplate = sections whose normalized name matches the
documented set (spike: ~4.5% of text is references/appendix/acknowledgments,
strippable by name). English heuristic: ASCII-letter share over a text sample;
dep-free and deterministic (Design Notes).
"""

from __future__ import annotations

import logging

from paperpilot.core.config import KBDefaults
from paperpilot.core.ids import normalize
from paperpilot.kb.stats import BuildCounters

logger = logging.getLogger(__name__)

BOILERPLATE_SECTION_NAMES: frozenset[str] = frozenset(
    {
        "references",
        "reference",
        "bibliography",
        "appendix",
        "acknowledgments",
        "acknowledgements",
        "acknowledgment",
        "acknowledgement",
    }
)


def is_boilerplate(section_name: str) -> bool:
    """True when the section is strippable boilerplate (exact match after normalize+lower)."""
    return normalize(section_name).lower() in BOILERPLATE_SECTION_NAMES


def english_letter_share(text: str, sample_chars: int) -> float:
    """Share of alphabetic characters in the sample that are ASCII (1.0 for empty input)."""
    sample = normalize(text)[:sample_chars]
    letters = [c for c in sample if c.isalpha()]
    if not letters:
        return 1.0
    return sum(1 for c in letters if c.isascii()) / len(letters)


def is_english(text: str, defaults: KBDefaults) -> bool:
    """Documented heuristic: drop when the ASCII-letter share falls below the threshold."""
    return english_letter_share(text, defaults.english_sample_chars) >= defaults.ascii_letter_share


def clean_sections(
    section_names: list[str],
    sections: list[str],
    counters: BuildCounters,
    defaults: KBDefaults,
) -> list[tuple[str, str]]:
    """Strip boilerplate sections and normalize the rest, preserving dataset order.

    Returns (name, normalized_text) pairs; empty/whitespace sections are dropped
    (E-8). Order is the dataset's own — section_rank derives from it downstream.
    """
    cleaned: list[tuple[str, str]] = []
    for raw_name, raw_text in zip(section_names, sections, strict=False):
        if is_boilerplate(raw_name):
            counters.boilerplate_sections_stripped += 1
            logger.debug("stripped boilerplate section %r", raw_name)
            continue
        text = normalize(raw_text)
        if not text:
            continue
        cleaned.append((normalize(raw_name), text))
    return cleaned


def clean_paper_text_for_checks(abstract_text: list[str], body_sections: list[tuple[str, str]]) -> str:
    """Concatenation used for the English check and the dedup hash (abstract + body, in order)."""
    parts = [normalize(part) for part in abstract_text]
    parts.extend(text for _, text in body_sections)
    return " ".join(part for part in parts if part)
