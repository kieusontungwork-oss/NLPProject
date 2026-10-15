"""Chunk stage: structure-aware split, 256-512 band, ~15% overlap, header prefixes (E-7..E-13, E-18).

Story 1.2 · CAP-1 · pipeline-stages.md "Chunking design" (graded design choice).
Windows are word-based: the estimator (words x 4/3, core.config) maps the token
band onto word windows, so no model tokenizer is needed at KB time. The band
governs regular windows; a folded tail (E-10) may exceed the ceiling by up to
fold_floor tokens — a small orphan chunk would serve retrieval worse (Design
Notes; embedders truncate at their model window regardless).
"""

from __future__ import annotations

import logging

from paperpilot.core.config import KBDefaults, estimate_tokens
from paperpilot.core.ids import chunk_id, normalize
from paperpilot.core.schemas import Chunk, Paper
from paperpilot.kb.stats import BuildCounters

logger = logging.getLogger(__name__)

ABSTRACT_SECTION = "abstract"


def header_prefix_for(title: str, section_name: str) -> str:
    """Single-sourced prefix format (Design Notes): '<title> — <section_name>'."""
    return f"{normalize(title)} — {section_name}"


def chunk_text_for(header_prefix: str, body: str) -> str:
    """Stored chunk text = prefix + single space + body (what BM25/embeddings see); already normalized (AD-2)."""
    return f"{header_prefix} {body}"


def _windows(words: list[str], defaults: KBDefaults) -> list[list[str]]:
    """Deterministic word windows: max size, fixed step (< 15% overlap), fold tiny tail (E-10)."""
    if len(words) <= defaults.max_window_words:
        return [words]
    windows: list[list[str]] = []
    start = 0
    prev_start = 0
    while start < len(words):
        window = words[start : start + defaults.max_window_words]
        if windows and len(window) < defaults.fold_floor_words:
            # Fold only the words past the previous window's end (no repeated overlap words).
            prev_end = prev_start + len(windows[-1])
            windows[-1].extend(words[prev_end:])
            break
        windows.append(window)
        prev_start = start
        if start + defaults.max_window_words >= len(words):
            break
        start += defaults.step_words
    return windows


def _chunks_for_section(
    paper: Paper,
    section_name: str,
    section_rank: int,
    body: str,
    defaults: KBDefaults,
    counters: BuildCounters,
) -> list[Chunk]:
    prefix = header_prefix_for(paper.title, section_name)
    chunks: list[Chunk] = []
    for index, window in enumerate(_windows(body.split(), defaults)):
        text = chunk_text_for(prefix, " ".join(window))
        n_tokens = estimate_tokens(len(window))
        cid = chunk_id(paper.arxiv_id, section_name, text)
        if any(existing.chunk_id == cid for existing in chunks):
            counters.duplicate_chunks += 1
            logger.warning(
                "duplicate chunk id %s within %s/%s [%d]; dropped", cid, paper.arxiv_id, section_name, index
            )
            continue
        chunks.append(
            Chunk(
                chunk_id=cid,
                arxiv_id=paper.arxiv_id,
                section_name=section_name,
                section_rank=section_rank,
                text=text,
                n_tokens=n_tokens,
                header_prefix=prefix,
            )
        )
    return chunks


def chunk_paper(paper: Paper, defaults: KBDefaults, counters: BuildCounters) -> list[Chunk]:
    """Chunk one cleaned paper: abstract chunk (rank 0), then body sections (rank 1..).

    Paper.sections preserves dataset order (dict insertion order), which is the
    section_rank order. Empty abstract emits no abstract chunk (E-9); a paper whose
    join fell back to a single `body` section ranks it like any body section (E-7).
    """
    chunks: list[Chunk] = []
    if paper.abstract:
        chunks.extend(
            _chunks_for_section(paper, ABSTRACT_SECTION, 0, paper.abstract, defaults, counters)
        )
    for offset, (name, text) in enumerate(paper.sections.items(), start=1):
        chunks.extend(_chunks_for_section(paper, name, offset, text, defaults, counters))
    return chunks
