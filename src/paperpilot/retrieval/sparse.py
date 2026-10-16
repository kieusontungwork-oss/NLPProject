"""Sparse leg: bm25s (method lucene, k1 1.5, b 0.75) behind the SparseRetriever port.

Story 1.3 · CAP-2 · AD-1 (port) · AD-5 (class-3 index). Doc i == line i of chunks.jsonl.
Results sort by (-score, row); scores <= 0 are dropped (no lexical match is not a hit).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from pathlib import Path

import bm25s
import numpy as np

from paperpilot.core.config import BM25_B, BM25_K1, BM25_METHOD
from paperpilot.core.errors import RetrievalStageError
from paperpilot.core.ports import LegHit
from paperpilot.core.schemas import IndexManifest
from paperpilot.retrieval import manifest as manifests
from paperpilot.retrieval.tokenize import tokenize

logger = logging.getLogger(__name__)

ENGINE = "bm25s"


def sparse_dir(index_dir: Path) -> Path:
    return Path(index_dir) / "sparse" / ENGINE


class Bm25sRetriever:
    """bm25s-backed lexical retriever; build/save/load/search."""

    def __init__(self, index: bm25s.BM25, chunk_ids: list[str]) -> None:
        self._index = index
        self._chunk_ids = chunk_ids

    @staticmethod
    def build(texts: Iterable[str], out_dir: Path, *, store_hash: str, config_row: str) -> IndexManifest:
        """Index `texts` (row order) and save into `out_dir` (a temp directory owned by the caller)."""
        corpus = [tokenize(text) for text in texts]
        if not corpus:
            raise RetrievalStageError("sparse", "no chunks to index")
        index = bm25s.BM25(method=BM25_METHOD, k1=BM25_K1, b=BM25_B)
        index.index(corpus, show_progress=False)
        index.save(out_dir)
        manifest = IndexManifest(
            created=manifests.utc_now(),
            embedding_model=None,
            dim=None,
            chunk_store_hash=store_hash,
            config_row=config_row,
            engine=ENGINE,
            n_chunks=len(corpus),
            params={"method": BM25_METHOD, "k1": BM25_K1, "b": BM25_B},
        )
        manifests.write_manifest(out_dir, manifest)
        return manifest

    @classmethod
    def load(
        cls, directory: Path, chunk_ids: list[str], *, store_hash: str, engine: str = ENGINE
    ) -> Bm25sRetriever:
        """Load the component; refuses on a missing directory, hash mismatch, or engine mismatch."""
        directory = Path(directory)
        manifest = manifests.read_manifest(directory)
        manifests.check_manifest(manifest, chunk_store_hash=store_hash, engine=engine)
        if manifest.n_chunks != len(chunk_ids):
            raise RetrievalStageError(
                "sparse", f"sparse index has {manifest.n_chunks} docs but docstore has {len(chunk_ids)} chunks"
            )
        index = bm25s.BM25.load(directory, load_corpus=False)
        return cls(index, chunk_ids)

    def search(self, query: str, depth: int) -> list[LegHit]:
        tokens = tokenize(query)
        if not tokens or depth < 1:
            return []
        scores = self._index.get_scores(tokens)
        candidates = np.flatnonzero(scores > 0)
        if candidates.size == 0:
            return []
        cand_scores = scores[candidates]
        if candidates.size > depth:
            # keep every candidate tying the depth-th score so the (-score, row) cut is exact
            cutoff = np.partition(cand_scores, -depth)[-depth]
            keep = cand_scores >= cutoff
            candidates, cand_scores = candidates[keep], cand_scores[keep]
        order = np.lexsort((candidates, -cand_scores))[:depth]
        return [
            LegHit(self._chunk_ids[int(candidates[i])], float(cand_scores[i]), rank)
            for rank, i in enumerate(order, start=1)
        ]
