"""Dedup stage: content-hash duplicate removal before chunking (E-5).

Story 1.2 · CAP-1 · pipeline-stages.md: "Deduplicate by content hash before
chunking." Keep-first in source file order keeps the build deterministic.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Iterator

from paperpilot.core.schemas import Paper
from paperpilot.kb.stats import BuildCounters

logger = logging.getLogger(__name__)


def content_hash(paper: Paper) -> str:
    """SHA-256 over the paper's normalized content: abstract + body sections in rank order.

    Paper.sections preserves dataset order (dict insertion order), so iteration is
    deterministic without re-sorting.
    """
    parts = [paper.abstract, *paper.sections.values()]
    return hashlib.sha256("\n".join(parts).encode("utf-8")).hexdigest()


def dedup_papers(papers: Iterator[Paper], counters: BuildCounters) -> Iterator[Paper]:
    """Yield papers with duplicate content hashes dropped (first occurrence wins)."""
    seen: set[str] = set()
    for paper in papers:
        digest = content_hash(paper)
        if digest in seen:
            counters.duplicates += 1
            logger.warning("duplicate content dropped: arxiv_id=%s", paper.arxiv_id)
            continue
        seen.add(digest)
        yield paper
