"""Retriever: leg orchestration, RRF fusion, hydration, EvidencePack assembly.

Story 1.3 · CAP-2 · AD-1 (talks to legs only through core ports) · AD-3 (EvidencePack) ·
AD-4 (leg switches are a validated config row).
"""

from __future__ import annotations

import logging
from pathlib import Path

from paperpilot.core.config import DEFAULT_INDEX_DIR, DEFAULT_KB_DIR, RetrievalConfig
from paperpilot.core.errors import RetrievalInputError
from paperpilot.core.ids import adhoc_query_id
from paperpilot.core.ports import DenseRetriever, LegHit, SparseRetriever
from paperpilot.core.schemas import EffectiveQuery, EvidencePack, Hit, LegScores
from paperpilot.core.timing import stage_timer
from paperpilot.retrieval import dense as dense_mod
from paperpilot.retrieval import docstore as docstore_mod
from paperpilot.retrieval import sparse as sparse_mod
from paperpilot.retrieval.fusion import rrf

logger = logging.getLogger(__name__)


class Retriever:
    """Run the enabled legs, fuse with RRF, hydrate hits, return an EvidencePack."""

    def __init__(
        self,
        row: RetrievalConfig,
        docstore: docstore_mod.Docstore,
        sparse: SparseRetriever | None,
        dense: DenseRetriever | None,
    ) -> None:
        if row.use_sparse and sparse is None:
            raise ValueError(f"row {row.id} enables the sparse leg but no sparse retriever was given")
        if row.use_dense and dense is None:
            raise ValueError(f"row {row.id} enables the dense leg but no dense retriever was given")
        self.row = row
        self._docstore = docstore
        self._sparse = sparse if row.use_sparse else None
        self._dense = dense if row.use_dense else None

    @classmethod
    def from_config(
        cls,
        row: RetrievalConfig,
        kb_dir: str | Path = DEFAULT_KB_DIR,
        index_dir: str | Path = DEFAULT_INDEX_DIR,
        encoder: dense_mod.Encoder | None = None,
    ) -> Retriever:
        """Load the components the row enables; refuses on missing or mismatched indexes."""
        kb_dir, index_dir = Path(kb_dir), Path(index_dir)
        store_hash = docstore_mod.chunk_store_hash(kb_dir)
        store = docstore_mod.Docstore.load(index_dir / "docstore", kb_dir, store_hash=store_hash)
        sparse = dense = None
        if row.use_sparse:
            sparse = sparse_mod.Bm25sRetriever.load(
                sparse_mod.sparse_dir(index_dir),
                store.chunk_ids,
                store_hash=store_hash,
                engine=row.sparse_engine,
            )
        if row.use_dense:
            dense = dense_mod.FaissDenseRetriever.load(
                dense_mod.dense_dir(index_dir, row.embedding_model),
                store.chunk_ids,
                (lambda: encoder) if encoder is not None else (lambda: dense_mod.SentenceTransformerEncoder(row.embedding_model)),
                store_hash=store_hash,
                embedding_model=row.embedding_model,
            )
        return cls(row, store, sparse, dense)

    def retrieve(self, query: str, k: int = 10, *, query_id: str | None = None) -> EvidencePack:
        """Return the RRF-fused top-`k` as an EvidencePack."""
        if not query or not query.strip():
            raise RetrievalInputError("query is empty or whitespace-only")
        depth = self.row.candidate_depth
        if k < 1 or k > depth:
            raise RetrievalInputError(f"k={k} must satisfy 1 <= k <= candidate_depth={depth}")
        timings: dict[str, float] = {}
        with stage_timer(timings, "total"):
            leg_results: dict[str, list[LegHit]] = {}
            if self._sparse is not None:
                with stage_timer(timings, "sparse"):
                    leg_results["bm25"] = self._sparse.search(query, depth)
            if self._dense is not None:
                with stage_timer(timings, "dense_encode"):
                    vector = self._dense.encode(query)
                with stage_timer(timings, "dense_search"):
                    leg_results["dense"] = self._dense.search(vector, depth)
            with stage_timer(timings, "fusion"):
                fused = rrf(leg_results, self.row.rrf_k)[:k]
            with stage_timer(timings, "hydrate"):
                chunks = self._docstore.hydrate([f.chunk_id for f in fused])
                hits = [
                    Hit(
                        rank=rank,
                        chunk_id=f.chunk_id,
                        text=chunk["text"],
                        header_prefix=chunk["header_prefix"],
                        arxiv_id=chunk["arxiv_id"],
                        title=chunk["title"],
                        section_name=chunk["section_name"],
                        year=chunk["year"],
                        source_link=chunk["source_link"],
                        leg_scores=LegScores(bm25=f.leg_scores.get("bm25"), dense=f.leg_scores.get("dense")),
                        rrf_score=f.rrf_score,
                    )
                    for rank, (f, chunk) in enumerate(zip(fused, chunks), start=1)
                ]
        qid = query_id if query_id is not None else adhoc_query_id(query)
        pack = EvidencePack(
            query_id=qid,
            query=query,
            effective_queries=[EffectiveQuery(type="raw", text=query, legs=list(leg_results))],
            hits=hits,
            stage_timings_ms=timings,
        )
        logger.info(
            "retrieve query_id=%s row=%s k=%d timings_ms=%s",
            qid,
            self.row.id,
            k,
            {key: round(value, 3) for key, value in timings.items()},
        )
        return pack
