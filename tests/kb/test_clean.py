"""Story 1.2 — kb.clean: boilerplate stripping (E-8), English heuristic (E-6), normalization (E-12)."""

from __future__ import annotations

import pytest

from paperpilot.core.config import DEFAULTS
from paperpilot.kb.clean import (
    clean_paper_text_for_checks,
    clean_sections,
    english_letter_share,
    is_boilerplate,
    is_english,
)
from paperpilot.kb.stats import BuildCounters


def test_boilerplate_matches_normalized_lowercase_names():
    assert is_boilerplate("References")
    assert is_boilerplate("  Acknowledgments ")
    assert not is_boilerplate("Related Work")


def test_clean_sections_strips_boilerplate_and_counts():
    counters = BuildCounters()
    pairs = clean_sections(
        ["Introduction", "References", "Methods", "Appendix"],
        ["Intro text.", "Ref [1]", "Methods text.", "Extra tables"],
        counters,
        DEFAULTS,
    )
    assert [name for name, _ in pairs] == ["Introduction", "Methods"]
    assert counters.boilerplate_sections_stripped == 2


def test_clean_sections_drops_empty_sections_e8():
    counters = BuildCounters()
    pairs = clean_sections(["Intro", "Empty"], ["Text.", "   "], counters, DEFAULTS)
    assert pairs == [("Intro", "Text.")]


def test_clean_sections_normalizes_whitespace_and_unicode_e12():
    counters = BuildCounters()
    pairs = clean_sections(["M\xe9thods"], ["  spaced \u00a0 out  text "], counters, DEFAULTS)
    assert pairs == [("M\xe9thods", "spaced out text")]


def test_english_heuristic_threshold_e6():
    assert is_english("plain english text", DEFAULTS)
    cyrillic = "э" * 50 + " words"
    assert not is_english(cyrillic, DEFAULTS)


def test_english_letter_share_edges():
    assert english_letter_share("", 100) == 1.0
    assert english_letter_share("1234 !!!", 100) == 1.0  # no letters = no evidence against


def test_clean_paper_text_joins_abstract_and_body_for_checks():
    text = clean_paper_text_for_checks(["Abstract text."], [("Intro", "Body text.")])
    assert text == "Abstract text. Body text."
