"""Dense leg: injected Encoder + exact FAISS IndexFlatIP (IP on L2-normalized vectors = cosine).

Story 1.3 · CAP-2 · AD-1 (port) · AD-5 (exact flat index). The model is loaded only through
`paperpilot.core.clients.load_sentence_transformer`. Vector i == line i of chunks.jsonl.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Iterator
from pathlib import Path
from typing import Protocol

import faiss
import numpy as np

from paperpilot.core import clients
from paperpilot.core.config import EMBED_BATCH_SIZE
from paperpilot.core.errors import IndexMissingError, RetrievalStageError
from paperpilot.core.ports import LegHit
from paperpilot.core.schemas import IndexManifest
from paperpilot.retrieval import manifest as manifests

logger = logging.getLogger(__name__)

INDEX_NAME = "index.faiss"
ENGINE = "faiss-flat-ip"
PROGRESS_EVERY_BATCHES = 100
NORM_TOLERANCE = 1e-3


class Encoder(Protocol):
    """Text encoder: `encode(texts)` -> float32 `(n, dim)` array, L2-normalized."""

    def encode(self, texts: list[str]) -> np.ndarray: ...


class SentenceTransformerEncoder:
    """Real encoder over a sentence-transformers model loaded through core.clients."""

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self._model = clients.load_sentence_transformer(model_id)

    @property
    def max_seq_length(self) -> int | None:
        """The model's input window in word pieces (longer chunks are truncated by the model)."""
        value = getattr(self._model, "max_seq_length", None)
        return int(value) if value is not None else None

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


def _check_vectors(vectors: np.ndarray, expected_rows: int, start_row: int = 0) -> np.ndarray:
    """Validate encoder output: shape, finite values, unit L2 norm. `start_row` names the batch in errors."""
    if vectors.ndim != 2 or vectors.shape[0] != expected_rows:
        raise RetrievalStageError(
            "dense", f"encoder returned shape {vectors.shape} for the batch starting at row {start_row}, expected ({expected_rows}, dim)"
        )
    vectors = np.ascontiguousarray(vectors, dtype=np.float32)
    if not np.isfinite(vectors).all():
        raise RetrievalStageError("dense", f"encoder returned non-finite values in the batch starting at row {start_row}")
    norms = np.linalg.norm(vectors, axis=1)
    if not np.all(np.abs(norms - 1.0) <= NORM_TOLERANCE):
        raise RetrievalStageError(
            "dense", f"encoder output is not L2-normalized in the batch starting at row {start_row} (norms {norms.min():.4f}..{norms.max():.4f})"
        )
    return vectors


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
        total: int | None = None,
    ) -> IndexManifest:
        """Encode `texts` (row order) into an IndexFlatIP and save it into `out_dir`.

        `total` (the chunk count, known from the docstore) only feeds the progress log lines.
        """
        max_seq_length = getattr(encoder, "max_seq_length", None)
        logger.info(
            "dense: embedding with %s (model window max_seq_length=%s word pieces; longer chunks are truncated)",
            model_id,
            max_seq_length,
        )
        index: faiss.IndexFlatIP | None = None
        done = 0
        for batch_no, batch in enumerate(_batches(texts, EMBED_BATCH_SIZE), start=1):
            vectors = _check_vectors(encoder.encode(batch), len(batch), start_row=done)
            if index is None:
                index = faiss.IndexFlatIP(vectors.shape[1])
            elif vectors.shape[1] != index.d:
                raise RetrievalStageError("dense", f"encoder dim changed from {index.d} to {vectors.shape[1]}")
            index.add(vectors)
            done += len(batch)
            if batch_no % PROGRESS_EVERY_BATCHES == 0:
                logger.info("dense: embedded %d/%s chunks", done, total if total is not None else "?")
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
            params={"max_seq_length": int(max_seq_length) if max_seq_length is not None else None},
        )
        manifests.write_manifest(out_dir, manifest)
        return manifest

    @classmethod
    def load(
        cls,
        directory: Path,
        chunk_ids: list[str],
        encoder_factory: Callable[[], Encoder],
        *,
        store_hash: str,
        embedding_model: str,
    ) -> FaissDenseRetriever:
        """Load the component; refuses on a missing directory, hash/model/dim mismatch.

        `encoder_factory` is called only after the index and manifest passed every check, so a
        missing or stale index fails before any model is loaded.
        """
        directory = Path(directory)
        if not (directory / manifests.MANIFEST_NAME).is_file():
            present = sorted(p.name for p in directory.parent.glob("*") if (p / manifests.MANIFEST_NAME).is_file()) if directory.parent.is_dir() else []
            raise IndexMissingError(directory, f"dense models present under {directory.parent}: {present or 'none'}")
        manifest = manifests.read_manifest(directory)
        manifests.check_manifest(manifest, chunk_store_hash=store_hash, embedding_model=embedding_model, engine=ENGINE)
        index_path = directory / INDEX_NAME
        if not index_path.is_file():
            raise IndexMissingError(index_path)
        index = faiss.read_index(str(index_path))
        if index.d != manifest.dim:
            raise RetrievalStageError("dense", f"dense index dim {index.d} != manifest dim {manifest.dim} in {directory}; run `make index`")
        if index.ntotal != manifest.n_chunks or index.ntotal != len(chunk_ids):
            raise RetrievalStageError(
                "dense",
                f"dense index has {index.ntotal} vectors, manifest n_chunks={manifest.n_chunks}, docstore has {len(chunk_ids)} chunks; run `make index`",
            )
        return cls(index, chunk_ids, encoder_factory())

    def encode(self, query: str) -> np.ndarray:
        return _check_vectors(self._encoder.encode([query]), 1)

    def search(self, vector: np.ndarray, depth: int) -> list[LegHit]:
        if vector.ndim != 2 or vector.shape[1] != self._index.d:
            raise RetrievalStageError("dense", f"query vector has shape {vector.shape}, index dim is {self._index.d}")
        k = min(depth, self._index.ntotal)
        if k < 1:
            return []
        scores, ids = self._index.search(vector, k)
        pairs = [(float(s), int(i)) for s, i in zip(scores[0], ids[0]) if i >= 0]
        pairs.sort(key=lambda pair: (-pair[0], pair[1]))
        return [LegHit(self._chunk_ids[row], score, rank) for rank, (score, row) in enumerate(pairs, start=1)]
