"""Index manifests and atomic component swaps (class-3 artifacts, AD-5).

Story 1.3 · CAP-2 · AD-5. Each component is built in a sibling temp directory and swapped
in only when complete; loaders refuse on hash / model / engine mismatch.
"""

from __future__ import annotations

import json
import logging
import os
import shutil
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError

from paperpilot.core.errors import IndexMismatchError, IndexMissingError, RetrievalStageError
from paperpilot.core.schemas import IndexManifest

logger = logging.getLogger(__name__)

MANIFEST_NAME = "manifest.json"


def utc_now() -> str:
    """ISO-8601 UTC timestamp, seconds resolution."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def write_manifest(directory: Path, manifest: IndexManifest) -> None:
    """Write `manifest.json` (indent 2, sorted keys, trailing newline) into `directory`."""
    payload = json.dumps(manifest.model_dump(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    (directory / MANIFEST_NAME).write_text(payload, encoding="utf-8")


def read_manifest(directory: Path) -> IndexManifest:
    """Read a component manifest; a missing component raises IndexMissingError naming the path."""
    path = directory / MANIFEST_NAME
    if not path.is_file():
        raise IndexMissingError(directory)
    try:
        return IndexManifest(**json.loads(path.read_text(encoding="utf-8")))
    except (ValueError, TypeError, ValidationError) as exc:
        raise RetrievalStageError("index", f"unreadable manifest {path}: {exc}; run `make index`") from exc


def check_manifest(
    manifest: IndexManifest,
    *,
    chunk_store_hash: str,
    embedding_model: str | None = None,
    engine: str | None = None,
) -> None:
    """Refuse a manifest that disagrees with the current chunk store, model, or engine."""
    if manifest.chunk_store_hash != chunk_store_hash:
        raise IndexMismatchError("chunk_store_hash", chunk_store_hash, manifest.chunk_store_hash)
    if embedding_model is not None and manifest.embedding_model != embedding_model:
        raise IndexMismatchError("embedding_model", embedding_model, manifest.embedding_model)
    if engine is not None and manifest.engine != engine:
        raise IndexMismatchError("engine", engine, manifest.engine)


@contextmanager
def atomic_component(final_dir: Path) -> Iterator[Path]:
    """Yield a temp sibling directory; swap it over `final_dir` only if the body completes.

    On any exception the temp directory is removed and the previous component is untouched.
    """
    final_dir = Path(final_dir)
    final_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp = final_dir.parent / f".{final_dir.name}.tmp-{os.getpid()}"
    old = final_dir.parent / f".{final_dir.name}.old-{os.getpid()}"
    shutil.rmtree(tmp, ignore_errors=True)
    shutil.rmtree(old, ignore_errors=True)
    tmp.mkdir()
    try:
        yield tmp
        if final_dir.exists():
            final_dir.rename(old)
        try:
            tmp.rename(final_dir)
        except Exception:
            if old.exists():
                old.rename(final_dir)
            raise
    except BaseException:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(old, ignore_errors=True)
