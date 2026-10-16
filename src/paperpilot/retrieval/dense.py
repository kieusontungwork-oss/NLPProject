"""Dense leg: injected Encoder + exact FAISS IndexFlatIP (IP on L2-normalized vectors = cosine).

Story 1.3 · CAP-2 · AD-1 (port) · AD-5 (exact flat index). The model is loaded only through
`paperpilot.core.clients.load_sentence_transformer`. Vector i == line i of chunks.jsonl.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np

from paperpilot.core import clients
from paperpilot.core.config import EMBED_BATCH_SIZE
from paperpilot.core.errors import RetrievalStageError
from paperpilot.core.ports import LegHit
from paperpilot.core.schemas import IndexManifest
from paperpilot.retrieval import manifest as manifests

logger = logging.getLogger(__name__)

INDEX_NAME = "index.faiss"
ENGINE = "faiss-flat-ip"


class Encoder(Protocol):
    """Text encoder: `encode(texts)` -> float32 `(n, dim)` array, L2-normalized."""

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEncoder:
    """Real encoder over a sentence-transformers model loaded through core.clients."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self._model = clients.load_sentence_transformer(model_id)

    def encode(self, texts: list[str]) -> np.ndarray:
        vectors = self._model.encode(
            texts,
            batch_size=EMBED_BATCH_SIZE,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.ascontiguousarray(vectors, dtype=np.float32)


def model_slug(model_id: str) -> str:
    """Directory slug for a model id: `/` -> `__`."""
    return model_id.replace("/", "__")


def dense_dir(index_dir: Path, model_id: str) -> Path:
    return Path(index_dir) / "dense" / model_slug(model_id)


def _batches(texts: Iterable[str], size: int) -> Iterator[list[str]]:
    batch: list[str] = []
    for text in texts:
        batch.append(text)
        if len(batch) == size:
            yield batch
            batch = []
    if batch:
        yield batch


def _check_vectors(vectors: np.ndarray, expected_rows: int) -> np.ndarray:
    if vectors.ndim != 2 or vectors.shape[0] != expected_rows:
        raise RetrievalStageError(
            "dense", f"encoder returned shape {vectors.shape}, expected ({expected_rows}, dim)"
        )
    return np.ascontiguousarray(vectors, dtype=np.float32)


class FaissDenseRetriever:
    """Exact-cosine dense retriever; build/save/load/search."""

    def __init__(self, index: faiss.Index, chunk_ids: list[str], encoder: Encoder) -> None:
        self._index = index
        self._chunk_ids = chunk_ids
        self._encoder = encoder

    @staticmethod
    def build(
        texts: Iterable[str],
        encoder: Encoder,
        out_dir: Path,
        *,
        model_id: str,
        store_hash: str,
        config_row: str,
    ) -> IndexManifest:
        """Encode `texts` (row order) into an IndexFlatIP and save it into `out_dir`."""
        index: faiss.IndexFlatIP | None = None
        for batch in _batches(texts, EMBED_BATCH_SIZE):
            vectors = _check_vectors(encoder.encode(batch), len(batch))
            if index is None:
                index = faiss.IndexFlatIP(vectors.shape[1])
            elif vectors.shape[1] != index.d:
                raise RetrievalStageError("dense", f"encoder dim changed from {index.d} to {vectors.shape[1]}")
            index.add(vectors)
        if index is None:
            raise RetrievalStageError("dense", "no chunks to embed")
        faiss.write_index(index, str(out_dir / INDEX_NAME))
        manifest = IndexManifest(
            created=manifests.utc_now(),
            embedding_model=model_id,
            dim=int(index.d),
            chunk_store_hash=store_hash,
            config_row=config_row,
            engine=ENGINE,
            n_chunks=int(index.ntotal),
            params={},
        )
        manifests.write_manifest(out_dir, manifest)
        return manifest

    @classmethod
    def load(
        cls,
        directory: Path,
        chunk_ids: list[str],
        encoder: Encoder,
        *,
        store_hash: str,
        embedding_model: str,
    ) -> FaissDenseRetriever:
        """Load the component; refuses on a missing directory, hash mismatch, or model mismatch."""
        directory = Path(directory)
        manifest = manifests.read_manifest(directory)
        manifests.check_manifest(manifest, chunk_store_hash=store_hash, embedding_model=embedding_model)
        index = faiss.read_index(str(directory / INDEX_NAME))
        if index.ntotal != len(chunk_ids):
            raise RetrievalStageError(
                "dense", f"dense index has {index.ntotal} vectors but docstore has {len(chunk_ids)} chunks"
            )
        return cls(index, chunk_ids, encoder)

    def encode(self, query: str) -> np.ndarray:
        return _check_vectors(self._encoder.encode([query]), 1)

    def search(self, vector: np.ndarray, depth: int) -> list[LegHit]:
        k = min(depth, self._index.ntotal)
        if k < 1:
            return []
        scores, ids = self._index.search(vector, k)
        pairs = [(float(s), int(i)) for s, i in zip(scores[0], ids[0]) if i >= 0]
        pairs.sort(key=lambda pair: (-pair[0], pair[1]))
        return [LegHit(self._chunk_ids[row], score, rank) for rank, (score, row) in enumerate(pairs, start=1)]
