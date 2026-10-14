"""Build counters and kb_stats.json aggregation (O-3).

Story 1.2 · CAP-1 · spine AD-5 (class-2 writer). Every drop/duplicate/malformed
path increments a counter here — silent degradation is forbidden (house rule).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
    """Aggregate the corpus figures (assignment Q1.3: documents, passages, words, types)."""
    size_hist: dict[str, int] = {name: 0 for name, _ in CHUNK_SIZE_BANDS}
    size_hist[OVERFLOW_BAND] = 0
    year_hist: dict[str, int] = {}
    words = 0
    vocab: set[str] = set()
    cs_papers = 0
    aiml_papers = 0

    for chunk in chunks:
        size_hist[chunk_size_band(chunk.n_tokens)] += 1
        chunk_words = chunk.text.split()
        words += len(chunk_words)
        vocab.update(w.lower() for w in chunk_words)

    for paper in papers:
        year_hist[str(paper.year)] = year_hist.get(str(paper.year), 0) + 1
        if any(c.startswith(defaults.category_prefix) for c in paper.categories):
            cs_papers += 1
        if any(c in defaults.aiml_categories for c in paper.categories):
            aiml_papers += 1

    years = [p.year for p in papers]
    stats = KBStats(
        papers=len(papers),
        chunks=len(chunks),
        words=words,
        types=len(vocab),
        chunk_size_histogram=size_hist,
        year_min=min(years) if years else None,
        year_max=max(years) if years else None,
        year_histogram=dict(sorted(year_hist.items())),
        category_composition=CategoryComposition(
            cs_papers=cs_papers, aiml_papers=aiml_papers, total=len(papers)
        ),
        provenance=Provenance(
            source_url=source_url,
            metadata_url=metadata_url,
            filter_mode=filter_mode,
            filter_widened=filter_widened,
            dropped_no_metadata=counters.dropped_no_metadata,
            duplicates=counters.duplicates,
            malformed_source_lines=counters.malformed_source_lines,
            malformed_metadata_lines=counters.malformed_metadata_lines,
            non_english_dropped=counters.non_english_dropped,
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
        100.0 * cs_papers / stats.papers if stats.papers else 0.0,
        100.0 * aiml_papers / stats.papers if stats.papers else 0.0,
    )
    return stats


__all__ = [
    "BuildCounters",
    "CHUNK_SIZE_BANDS",
    "OVERFLOW_BAND",
    "build_stats",
    "chunk_size_band",
    "estimate_tokens",
]
