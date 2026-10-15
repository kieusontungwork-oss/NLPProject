"""Build counters and kb_stats.json aggregation (O-3).

Story 1.2 · CAP-1 · spine AD-5 (class-2 writer). Every drop/duplicate/malformed
path increments a counter here — silent degradation is forbidden (house rule).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from paperpilot.core.config import KBDefaults, estimate_tokens
from paperpilot.core.schemas import (
    CategoryComposition,
    Chunk,
    KBStats,
    Paper,
    Provenance,
)

logger = logging.getLogger(__name__)

CHUNK_SIZE_BANDS: tuple[tuple[str, int], ...] = (
    ("0-128", 128),
    ("129-255", 255),
    ("256-384", 384),
    ("385-512", 512),
)
OVERFLOW_BAND = "513+"


@dataclass
class BuildCounters:
    """Mutable counters threaded through the build; rendered into Provenance at the end."""

    dropped_no_metadata: int = 0
    duplicates: int = 0
    duplicate_chunks: int = 0
    malformed_source_lines: int = 0
    malformed_metadata_lines: int = 0
    non_english_dropped: int = 0
    boilerplate_sections_stripped: int = 0
    nameless_sections_dropped: int = 0
    sections_merged_name_collision: int = 0


@dataclass
class CorpusAggregate:
    """Running corpus aggregates for streaming emission (bounded RAM: no paper/chunk lists)."""

    words: int = 0
    vocab: set[str] = field(default_factory=set)
    size_hist: dict[str, int] = field(default_factory=lambda: {name: 0 for name, _ in CHUNK_SIZE_BANDS} | {OVERFLOW_BAND: 0})
    year_hist: dict[str, int] = field(default_factory=dict)
    cs_papers: int = 0
    aiml_papers: int = 0

    def add_paper(self, paper: Paper, defaults: KBDefaults) -> None:
        self.year_hist[str(paper.year)] = self.year_hist.get(str(paper.year), 0) + 1
        if any(c.startswith(defaults.category_prefix) for c in paper.categories):
            self.cs_papers += 1
        if any(c in defaults.aiml_categories for c in paper.categories):
            self.aiml_papers += 1

    def add_chunk(self, chunk: Chunk) -> None:
        self.size_hist[chunk_size_band(chunk.n_tokens)] += 1
        chunk_words = chunk.text.split()
        self.words += len(chunk_words)
        self.vocab.update(w.lower() for w in chunk_words)


def chunk_size_band(n_tokens: int) -> str:
    """Histogram band name for a chunk token count (O-3)."""
    for name, upper in CHUNK_SIZE_BANDS:
        if n_tokens <= upper:
            return name
    return OVERFLOW_BAND


def build_stats(
    papers: list[Paper],
    chunks: list[Chunk],
    counters: BuildCounters,
    defaults: KBDefaults,
    source_url: str,
    metadata_url: str,
    filter_mode: str,
    filter_widened: bool,
    generated_at: str,
) -> KBStats:
    """Aggregate the corpus figures (assignment Q1.3: documents, passages, words, types).

    Thin wrapper over CorpusAggregate for list-shaped inputs. The CLI currently
    uses build_stats; CorpusAggregate is there for switching to streaming
    emission if memory requires it.
    """
    agg = CorpusAggregate()
    for paper in papers:
        agg.add_paper(paper, defaults)
    for chunk in chunks:
        agg.add_chunk(chunk)
    return render_stats(
        agg,
        len(papers),
        len(chunks),
        counters,
        source_url,
        metadata_url,
        filter_mode,
        filter_widened,
        generated_at,
    )


def render_stats(
    agg: CorpusAggregate,
    papers: int,
    chunks: int,
    counters: BuildCounters,
    source_url: str,
    metadata_url: str,
    filter_mode: str,
    filter_widened: bool,
    generated_at: str,
) -> KBStats:
    """Assemble KBStats from the aggregate + counters (O-3)."""
    years = [int(y) for y in agg.year_hist]
    stats = KBStats(
        papers=papers,
        chunks=chunks,
        words=agg.words,
        types=len(agg.vocab),
        chunk_size_histogram=agg.size_hist,
        year_min=min(years) if years else None,
        year_max=max(years) if years else None,
        year_histogram=dict(sorted(agg.year_hist.items())),
        category_composition=CategoryComposition(
            cs_papers=agg.cs_papers, aiml_papers=agg.aiml_papers, total=papers
        ),
        provenance=Provenance(
            source_url=source_url,
            metadata_url=metadata_url,
            filter_mode=filter_mode,
            filter_widened=filter_widened,
            dropped_no_metadata=counters.dropped_no_metadata,
            duplicates=counters.duplicates,
            duplicate_chunks=counters.duplicate_chunks,
            malformed_source_lines=counters.malformed_source_lines,
            malformed_metadata_lines=counters.malformed_metadata_lines,
            non_english_dropped=counters.non_english_dropped,
            boilerplate_sections_stripped=counters.boilerplate_sections_stripped,
            nameless_sections_dropped=counters.nameless_sections_dropped,
            sections_merged_name_collision=counters.sections_merged_name_collision,
            generated_at=generated_at,
        ),
    )
    logger.info(
        "kb_stats: papers=%d chunks=%d words=%d types=%d years=%s-%s cs=%.1f%% aiml=%.1f%%",
        stats.papers,
        stats.chunks,
        stats.words,
        stats.types,
        stats.year_min,
        stats.year_max,
        100.0 * agg.cs_papers / papers if papers else 0.0,
        100.0 * agg.aiml_papers / papers if papers else 0.0,
    )
    return stats


__all__ = [
    "BuildCounters",
    "CHUNK_SIZE_BANDS",
    "CorpusAggregate",
    "OVERFLOW_BAND",
    "build_stats",
    "chunk_size_band",
    "estimate_tokens",
    "render_stats",
]
