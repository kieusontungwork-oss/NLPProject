"""Story 1.2 — core.config: the single-sourced defaults and window derivations (I-3)."""

from __future__ import annotations

from paperpilot.core.config import DEFAULTS, KBDefaults, estimate_tokens


def test_estimate_tokens_is_words_times_four_thirds():
    assert estimate_tokens(0) == 0
    assert estimate_tokens(384) == 512
    assert estimate_tokens(3) == 4


def test_default_window_derivation_matches_the_frozen_matrix():
    # E-10: max window = ceiling*3/4 words; step = ~15% overlap; fold floor from 128 tokens.
    assert DEFAULTS.token_ceiling == 512
    assert DEFAULTS.token_floor == 256
    assert DEFAULTS.max_window_words == 384
    assert DEFAULTS.step_words == 326
    assert DEFAULTS.fold_floor_words == 96


def test_defaults_are_single_sourced():
    assert DEFAULTS.widen_threshold == 12_000
    assert DEFAULTS.category_prefix == "cs."
    assert "cs.CL" in DEFAULTS.aiml_categories
