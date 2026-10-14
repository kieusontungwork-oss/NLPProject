"""Acquire stage: download the source zip and stream-parse train.txt (I-1, E-14, E-15).

Story 1.2 · CAP-1 · stack.md: direct S3 zip + streamed parse; the HF script
loader is broken (spike) and is never used. Transport is injectable for offline
tests; production defaults to urllib streaming.
"""

from __future__ import annotations

import io
import json
import logging
import os
import zipfile
from collections.abc import Callable, Iterator
from pathlib import Path
from urllib.request import urlopen

from paperpilot.core.config import SOURCE_MEMBER, S3_SOURCE_URL
from paperpilot.core.errors import KBStageError
from paperpilot.kb.stats import BuildCounters

logger = logging.getLogger(__name__)

_CHUNK = 1 << 20


def download_file(
    dest: Path,
    url: str,
    transport: Callable[[str], io.BufferedReader] | None = None,
) -> Path:
    """Stream `url` to `dest` atomically (tmp + os.replace); any failure leaves no partial file (E-14/E-15).

    If `dest` already exists it is reused (idempotent re-runs; E-14 wholesale
    rebuild semantics: raw inputs are not derived artifacts).
    """
    if dest.exists():
        logger.info("raw input already present, reusing %s", dest)
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".partial")
    opener = transport if transport is not None else _default_transport
    try:
        with opener(url) as response, tmp.open("wb") as out:
            while True:
                block = response.read(_CHUNK)
                if not block:
                    break
                out.write(block)
        os.replace(tmp, dest)
    except KBStageError:
        tmp.unlink(missing_ok=True)
        raise
    except Exception as exc:
        tmp.unlink(missing_ok=True)
        raise KBStageError("acquire", f"download failed from {url}: {exc}") from exc
    logger.info("downloaded %s -> %s", url, dest)
    return dest


def _default_transport(url: str) -> io.BufferedReader:
    try:
        return urlopen(url, timeout=120)  # noqa: S310 - fixed https url from config
    except Exception as exc:
        raise KBStageError("acquire", f"cannot open {url}: {exc}") from exc


def iter_source_records(
    zip_path: Path,
    counters: BuildCounters,
    limit: int | None = None,
    member: str = SOURCE_MEMBER,
) -> Iterator[dict]:
    """Stream-parse the JSONL member line-by-line (bounded RAM); malformed lines skip + count.

    `limit` stops after N *valid* records (E-16 smoke slices), not N lines.
    """
    try:
        with zipfile.ZipFile(zip_path) as archive:
            with archive.open(member) as raw:
                handle = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
                emitted = 0
                for line in handle:
                    if limit is not None and emitted >= limit:
                        return
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        record = json_record(line)
                    except (ValueError, KeyError, TypeError) as exc:
                        counters.malformed_source_lines += 1
                        logger.warning("malformed source line skipped: %s", exc)
                        continue
                    emitted += 1
                    yield record
    except KBStageError:
        raise
    except (zipfile.BadZipFile, KeyError) as exc:
        raise KBStageError("acquire", f"cannot read {member} from {zip_path}: {exc}") from exc


def json_record(line: str) -> dict:
    """Parse + validate one source record; raises ValueError/KeyError on malformed input."""
    record = json.loads(line)
    if not isinstance(record, dict):
        raise ValueError("record is not an object")
    if not str(record.get("article_id", "")).strip():
        raise ValueError("missing article_id")
    return record
