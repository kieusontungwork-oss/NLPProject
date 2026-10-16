"""Chunk docstore: row -> chunk_id, byte offsets into chunks.jsonl, paper metadata sidecar.

Story 1.3 · CAP-2 · AD-5. Hydration seeks into `chunks.jsonl` by byte offset (no chunk text in
RAM); title/year/source_link come from `papers_meta.json`, derived from `papers.jsonl`, the
single source of paper metadata. Row i here == BM25 doc i == FAISS vector i == line i.
"""

from __future__ import annotations

import hashlib
import json
import logging
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from paperpilot.core.errors import IndexMissingError, RetrievalStageError
from paperpilot.core.schemas import IndexManifest
from paperpilot.retrieval import manifest as manifests

logger = logging.getLogger(__name__)

CHUNKS_NAME = "chunks.jsonl"
PAPERS_NAME = "papers.jsonl"
CHUNK_IDS_NAME = "chunk_ids.json"
OFFSETS_NAME = "offsets.npy"
PAPERS_META_NAME = "papers_meta.json"
ENGINE = "docstore"


def chunks_path(kb_dir: Path) -> Path:
    return Path(kb_dir) / CHUNKS_NAME


def chunk_store_hash(kb_dir: Path) -> str:
    """SHA-256 hex of the `chunks.jsonl` bytes; a missing file raises (no silent degradation)."""
    path = chunks_path(kb_dir)
    if not path.is_file():
        raise RetrievalStageError("docstore", f"chunk store not found: {path}; run `make kb`")
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_chunks(kb_dir: Path) -> Iterator[tuple[int, dict]]:
    """Yield `(byte_offset, chunk_dict)` for each non-blank line of chunks.jsonl, in file order."""
    path = chunks_path(kb_dir)
    if not path.is_file():
        raise RetrievalStageError("docstore", f"chunk store not found: {path}; run `make kb`")
    with path.open("rb") as handle:
        offset = 0
        for lineno, line in enumerate(handle, start=1):
            start, offset = offset, offset + len(line)
            if not line.strip():
                raise RetrievalStageError("docstore", f"{path}:{lineno}: blank line breaks row alignment")
            try:
                yield start, json.loads(line)
            except ValueError as exc:
                raise RetrievalStageError("docstore", f"{path}:{lineno}: malformed JSON: {exc}") from exc


def _load_papers_meta(kb_dir: Path) -> dict[str, dict]:
    path = Path(kb_dir) / PAPERS_NAME
    if not path.is_file():
        raise RetrievalStageError("docstore", f"paper metadata not found: {path}; run `make kb`")
    meta: dict[str, dict] = {}
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                paper = json.loads(line)
                meta[paper["arxiv_id"]] = {
                    "title": paper["title"],
                    "year": paper["year"],
                    "source_link": paper["source_link"],
                }
            except (ValueError, KeyError) as exc:
                raise RetrievalStageError("docstore", f"{path}:{lineno}: bad paper record: {exc!r}") from exc
    return meta


def build_docstore(kb_dir: Path, out_dir: Path, *, store_hash: str, config_row: str) -> IndexManifest:
    """Write the docstore component into `out_dir` (a temp directory owned by the caller)."""
    papers_meta = _load_papers_meta(kb_dir)
    chunk_ids: list[str] = []
    offsets: list[int] = []
    used: dict[str, dict] = {}
    for offset, chunk in iter_chunks(kb_dir):
        arxiv_id = chunk.get("arxiv_id")
        if arxiv_id not in papers_meta:
            raise RetrievalStageError(
                "docstore",
                f"chunk {chunk.get('chunk_id')!r} references arxiv_id {arxiv_id!r} missing from "
                f"{PAPERS_NAME} (KB invariant violated)",
            )
        chunk_ids.append(chunk["chunk_id"])
        offsets.append(offset)
        used[arxiv_id] = papers_meta[arxiv_id]
    if not chunk_ids:
        raise RetrievalStageError("docstore", f"{chunks_path(kb_dir)} holds no chunks")
    if len(set(chunk_ids)) != len(chunk_ids):
        raise RetrievalStageError("docstore", "chunk_id values in chunks.jsonl are not unique")
    (out_dir / CHUNK_IDS_NAME).write_text(json.dumps(chunk_ids), encoding="utf-8")
    np.save(out_dir / OFFSETS_NAME, np.asarray(offsets, dtype=np.int64))
    (out_dir / PAPERS_META_NAME).write_text(
        json.dumps(used, ensure_ascii=False, sort_keys=True), encoding="utf-8"
    )
    manifest = IndexManifest(
        created=manifests.utc_now(),
        embedding_model=None,
        dim=None,
        chunk_store_hash=store_hash,
        config_row=config_row,
        engine=ENGINE,
        n_chunks=len(chunk_ids),
        params={},
    )
    manifests.write_manifest(out_dir, manifest)
    return manifest


class Docstore:
    """Loaded docstore: row/chunk_id maps plus byte-offset hydration from chunks.jsonl."""

    def __init__(self, kb_dir: Path, chunk_ids: list[str], offsets: np.ndarray, papers_meta: dict[str, dict]):
        self.kb_dir = Path(kb_dir)
        self.chunk_ids = chunk_ids
        self.offsets = offsets
        self.papers_meta = papers_meta
        self._rows = {cid: row for row, cid in enumerate(chunk_ids)}

    @classmethod
    def load(cls, directory: Path, kb_dir: Path, *, store_hash: str) -> Docstore:
        """Load the component, refusing on a missing directory or a chunk-store hash mismatch."""
        directory = Path(directory)
        manifest = manifests.read_manifest(directory)
        manifests.check_manifest(manifest, chunk_store_hash=store_hash)
        try:
            chunk_ids = json.loads((directory / CHUNK_IDS_NAME).read_text(encoding="utf-8"))
            offsets = np.load(directory / OFFSETS_NAME)
            papers_meta = json.loads((directory / PAPERS_META_NAME).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise IndexMissingError(exc.filename or directory) from exc
        return cls(kb_dir, chunk_ids, offsets, papers_meta)

    def __len__(self) -> int:
        return len(self.chunk_ids)

    def row_of(self, chunk_id: str) -> int:
        return self._rows[chunk_id]

    def hydrate(self, chunk_ids: list[str]) -> list[dict]:
        """Return, per chunk id, the chunk fields plus `title`/`year`/`source_link` (input order kept)."""
        out: list[dict] = []
        with chunks_path(self.kb_dir).open("rb") as handle:
            for chunk_id in chunk_ids:
                handle.seek(int(self.offsets[self._rows[chunk_id]]))
                chunk = json.loads(handle.readline())
                if chunk["chunk_id"] != chunk_id:
                    raise RetrievalStageError(
                        "docstore", f"offset for {chunk_id!r} points at {chunk['chunk_id']!r}; run `make index`"
                    )
                meta = self.papers_meta[chunk["arxiv_id"]]
                out.append({**chunk, **meta})
        return out
