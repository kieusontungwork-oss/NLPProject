"""Story 1.2 — kb.stats: O-3 aggregation (Q1.3 figures, bands, year histogram, composition)."""

from __future__ import annotations

from paperpilot.core.config import DEFAULTS
from paperpilot.kb.chunk import chunk_paper
from paperpilot.kb.stats import BuildCounters, build_stats, chunk_size_band
from tests.conftest import make_paper


def test_band_names_cover_all_counts():
    assert chunk_size_band(0) == "0-128"
    assert chunk_size_band(128) == "0-128"
    assert chunk_size_band(255) == "129-255"
    assert chunk_size_band(384) == "256-384"
    assert chunk_size_band(512) == "385-512"
    assert chunk_size_band(513) == "513+"


def test_build_stats_aggregates_corpus_figures():
    papers = [
        make_paper(categories=["cs.CL", "stat.ML"], year=2007),
        make_paper(arxiv_id="0704.0002", categories=["math.AG"], year=2001),
    ]
    counters = BuildCounters()
    counters.dropped_no_metadata = 3
    counters.duplicates = 2
    counters.non_english_dropped = 1
    counters.malformed_source_lines = 4
    counters.malformed_metadata_lines = 5

    chunks = []
    for paper in papers:
        chunks.extend(chunk_paper(paper, DEFAULTS, BuildCounters()))

    stats = build_stats(
        papers,
        chunks,
        counters,
        DEFAULTS,
        source_url="https://s3.example/src.zip",
        metadata_url="https://storage.googleapis.example/meta.json",
        filter_mode="cs",
        filter_widened=False,
        generated_at="2026-10-14T00:00:00+00:00",
    )

    assert stats.papers == 2
    assert stats.chunks == len(chunks)
    assert stats.words == sum(len(c.text.split()) for c in chunks)
    assert stats.types == len({w.lower() for c in chunks for w in c.text.split()})
    assert stats.year_min == 2001 and stats.year_max == 2007
    assert stats.year_histogram == {"2001": 1, "2007": 1}
    assert stats.category_composition.cs_papers == 1
    assert stats.category_composition.aiml_papers == 1
    assert stats.category_composition.total == 2
    assert stats.provenance.dropped_no_metadata == 3
    assert stats.provenance.duplicates == 2
    assert stats.provenance.non_english_dropped == 1
    assert stats.provenance.malformed_source_lines == 4
    assert stats.provenance.malformed_metadata_lines == 5
    assert stats.provenance.filter_mode == "cs"
    assert stats.provenance.filter_widened is False
    assert sum(stats.chunk_size_histogram.values()) == len(chunks)


def test_build_stats_empty_corpus_is_well_formed():
    stats = build_stats(
        [], [], BuildCounters(), DEFAULTS, "s", "m", "cs", False, "2026-10-14T00:00:00+00:00"
    )
    assert stats.papers == 0 and stats.chunks == 0
    assert stats.year_min is None and stats.year_max is None
