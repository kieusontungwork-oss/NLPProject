"""Core-defined ports for the retrieval legs (AD-1): the retriever talks to legs only through these.

Story 1.3 · CAP-2 · spine AD-1. `LegHit` is the only thing that crosses a port; ranks are 1-based.
The dense port is split into `encode` + `search` so the caller can time `dense_encode` and
`dense_search` separately (AD-3 stage timings).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

import numpy as np


@dataclass(frozen=True)
class LegHit:
    """One candidate from one leg: its chunk id, the leg's raw score, and its 1-based rank."""

    chunk_id: str
    score: float
    rank: int


@runtime_checkable
class SparseRetriever(Protocol):
    """Lexical leg: query text -> up to `depth` hits, best first, scores > 0 only."""

    def search(self, query: str, depth: int) -> list[LegHit]: ...


@runtime_checkable
class DenseRetriever(Protocol):
    """Dense leg: `encode` a query to a (1, dim) float32 L2-normalized array, then `search` it."""

    def encode(self, query: str) -> np.ndarray: ...

    def search(self, vector: np.ndarray, depth: int) -> list[LegHit]: ...
