"""Story 1.2 — core.schemas: null-hostile O-1/O-2 contracts (citation resolvability depends on it)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from paperpilot.core.schemas import Chunk, KBStats, Paper
from tests.conftest import make_chunk, make_paper


@pytest.mark.parametrize(
    "overrides",
    [
        {"title": ""},
        {"year": None},
        {"categories": []},
        {"arxiv_id": ""},
        {"source_link": ""},
    ],
)
def test_paper_rejects_null_or_empty_critical_metadata(overrides):
    with pytest.raises(ValidationError):
        make_paper(**overrides)


def test_paper_allows_empty_abstract_and_license_but_not_null():
    assert make_paper(abstract="", license="").abstract == ""
    with pytest.raises(ValidationError):
        make_paper(abstract=None)


def test_chunk_requires_16_hex_id_and_positive_tokens():
    with pytest.raises(ValidationError):
        make_chunk(chunk_id="nothex")
    with pytest.raises(ValidationError):
        make_chunk(n_tokens=0)


def test_kbstats_defaults_allow_empty_corpus():
    stats = KBStats(
        papers=0,
        chunks=0,
        words=0,
        types=0,
        chunk_size_histogram={},
        year_histogram={},
        category_composition={"cs_papers": 0, "aiml_papers": 0, "total": 0},
        provenance={
            "source_url": "https://example.invalid/x.zip",
            "metadata_url": "https://example.invalid/y.json",
            "filter_mode": "cs",
            "filter_widened": False,
            "dropped_no_metadata": 0,
            "duplicates": 0,
            "malformed_source_lines": 0,
            "malformed_metadata_lines": 0,
            "non_english_dropped": 0,
            "generated_at": "2026-10-14T00:00:00+00:00",
        },
    )
    assert stats.year_min is None and stats.year_max is None
