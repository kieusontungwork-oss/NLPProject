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

from paperpilot.core.config import SOURCE_MEMBERS, S3_SOURCE_URL
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
            expected = _content_length(response)
            written = 0
            while True:
                block = response.read(_CHUNK)
                if not block:
                    break
                written += len(block)
                out.write(block)
        if expected is not None and written != expected:
            raise KBStageError(
                "acquire",
                f"download truncated: wrote {written} bytes, server declared {expected} for {url}",
            )
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


def _content_length(response: object) -> int | None:
    """Server-declared byte count when the transport exposes headers; None otherwise."""
    headers = getattr(response, "headers", None)
    if headers is None:
        return None
    raw = headers.get("Content-Length")
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def iter_source_records(
    zip_path: Path,
    counters: BuildCounters,
    limit: int | None = None,
    members: tuple[str, ...] = SOURCE_MEMBERS,
) -> Iterator[dict]:
    """Stream-parse the JSONL members (I-1: train, val, test) as ONE record stream, in order.

    Line-by-line (bounded RAM); malformed lines skip + count. `limit` stops after N
    *valid* records across the whole stream (E-16 smoke slices), not N lines.
    """
    emitted = 0
    try:
        with zipfile.ZipFile(zip_path) as archive:
            for member in members:
                try:
                    raw = archive.open(member)
                except KeyError as exc:
                    raise KBStageError("acquire", f"cannot read {member} from {zip_path}: {exc}") from exc
                with raw:
                    handle = io.TextIOWrapper(raw, encoding="utf-8", errors="replace")
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
    except zipfile.BadZipFile as exc:
        raise KBStageError("acquire", f"cannot read {zip_path}: {exc}") from exc


def json_record(line: str) -> dict:
    """Parse + validate one source record; raises ValueError/KeyError on malformed input."""
    record = json.loads(line)
    if not isinstance(record, dict):
        raise ValueError("record is not an object")
    if not str(record.get("article_id", "")).strip():
        raise ValueError("missing article_id")
    return record
