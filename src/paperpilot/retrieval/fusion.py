"""Reciprocal Rank Fusion over 1 or 2 legs (one code path).

Story 1.3 · CAP-2 · AD-4 (rrf_k from the config row).
rrf_score(d) = sum over legs of 1 / (rrf_k + rank_leg(d)); ranks are 1-based.
Ties: (-rrf_score, min leg rank, chunk_id).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from paperpilot.core.ports import LegHit

logger = logging.getLogger(__name__)

LEG_ORDER = ("bm25", "dense")


@dataclass(frozen=True)
class FusedHit:
    """A fused candidate: its RRF score and the raw score each contributing leg gave it."""

    chunk_id: str
    rrf_score: float
    leg_scores: dict[str, float] = field(default_factory=dict)


def rrf(leg_results: dict[str, list[LegHit]], rrf_k: int) -> list[FusedHit]:
    """Fuse per-leg hit lists (keyed by leg name) into one ranked list, best first."""
    if rrf_k <= 0:
        raise ValueError(f"rrf_k={rrf_k} must be > 0")
    order = [leg for leg in LEG_ORDER if leg in leg_results] + sorted(
        leg for leg in leg_results if leg not in LEG_ORDER
    )
    scores: dict[str, float] = {}
    best_rank: dict[str, int] = {}
    leg_scores: dict[str, dict[str, float]] = {}
    for leg in order:  # fixed leg order keeps the float summation order deterministic
        for hit in leg_results[leg]:
            scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (rrf_k + hit.rank)
            best_rank[hit.chunk_id] = min(best_rank.get(hit.chunk_id, hit.rank), hit.rank)
            leg_scores.setdefault(hit.chunk_id, {})[leg] = hit.score
    ordered = sorted(scores, key=lambda cid: (-scores[cid], best_rank[cid], cid))
    return [FusedHit(cid, scores[cid], leg_scores[cid]) for cid in ordered]
