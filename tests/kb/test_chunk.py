"""Story 1.2 — kb.chunk: band windows (E-10/E-11), abstract chunk (E-9/E-18), unique ids (E-13)."""

from __future__ import annotations

import pytest

from paperpilot.core.config import DEFAULTS, estimate_tokens
from paperpilot.kb.chunk import chunk_paper, chunk_text_for, header_prefix_for
from paperpilot.kb.stats import BuildCounters
from tests.conftest import make_paper


@pytest.fixture
def counters():
    return BuildCounters()


def test_header_prefix_format_is_single_sourced(counters):
    assert header_prefix_for("A  Title", "abstract") == "A Title — abstract"


def test_chunk_text_prepends_prefix_with_blank_line(counters):
    text = chunk_text_for("T — abstract", "Body words.")
    assert text == "T — abstract\n\nBody words."


def test_abstract_chunk_rank_zero_and_body_ranks_from_one_e18(counters):
    paper = make_paper(sections={"Introduction": "Intro text.", "Methods": "Methods text."})
    chunks = chunk_paper(paper, DEFAULTS, counters)
    assert chunks[0].section_name == "abstract"
    assert chunks[0].section_rank == 0
    body = [c for c in chunks if c.section_name != "abstract"]
    assert [c.section_rank for c in body] == [1, 2]
    assert [c.section_name for c in body] == ["Introduction", "Methods"]


def test_empty_abstract_emits_no_abstract_chunk_e9(counters):
    chunks = chunk_paper(make_paper(abstract=""), DEFAULTS, counters)
    assert all(c.section_name != "abstract" for c in chunks)
    assert chunks[0].section_rank == 1


def test_short_section_emits_single_chunk_e11(counters):
    # ~10 words -> ~13 tokens: inside emission rules even though below the 256 floor.
    chunks = chunk_paper(make_paper(), DEFAULTS, counters)
    assert all(0 < c.n_tokens for c in chunks)
    assert len([c for c in chunks if c.section_name == "Introduction"]) == 1


def test_oversized_section_splits_with_overlap_and_folds_tail_e10(counters):
    words = [f"w{i}" for i in range(1000)]  # 1000 words -> ~1333 tokens > 512
    paper = make_paper(
        sections={"Long": " ".join(words)},
        abstract="",
    )
    chunks = chunk_paper(paper, DEFAULTS, counters)
    assert len(chunks) >= 3
    # Overlap: consecutive windows share words (step < window size).
    first_words = chunks[0].text.split("\n\n", 1)[1].split()
    second_words = chunks[1].text.split("\n\n", 1)[1].split()
    assert set(first_words[-50:]) & set(second_words[:50])
    # Every window respects the ceiling under the documented estimator.
    assert all(c.n_tokens <= DEFAULTS.token_ceiling for c in chunks[:-1])
    # Folded tail: the last chunk absorbs the small remainder instead of a tiny orphan.
    assert chunks[-1].n_tokens >= DEFAULTS.fold_floor_tokens


def test_chunk_ids_unique_within_paper_e13(counters):
    words = [f"w{i}" for i in range(1000)]
    paper = make_paper(sections={"Long": " ".join(words), "Long ": " ".join(words)}, abstract="")
    chunks = chunk_paper(paper, DEFAULTS, counters)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_chunk_ids_stable_across_calls(counters):
    a = chunk_paper(make_paper(), DEFAULTS, counters)
    b = chunk_paper(make_paper(), DEFAULTS, BuildCounters())
    assert [c.chunk_id for c in a] == [c.chunk_id for c in b]


def test_header_prefix_rides_inside_stored_text(counters):
    chunks = chunk_paper(make_paper(), DEFAULTS, counters)
    for chunk in chunks:
        assert chunk.text.startswith(chunk.header_prefix + "\n\n")
        assert chunk.n_tokens == estimate_tokens(len(chunk.text.split("\n\n", 1)[1].split()))
