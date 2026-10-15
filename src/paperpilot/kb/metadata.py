"""Metadata stage: arXiv snapshot index, id repair, join, cs.* filter with widening (E-1..E-4, E-17, E-19).

Story 1.2 · CAP-1. The 4.5GB snapshot streams into a temp sqlite table (stdlib)
keyed by bare arxiv_id so the join needs bounded RAM (Design Notes). The sqlite
file is a build-time index only — never an emitted artifact, never queried with
LIKE (assignment rule bans string-matching retrieval, not build tooling).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
from collections.abc import Iterator
from pathlib import Path

from paperpilot.core.config import KBDefaults
from paperpilot.core.errors import KBStageError
from paperpilot.core.ids import normalize
from paperpilot.core.schemas import Paper
from paperpilot.kb.stats import BuildCounters

logger = logging.getLogger(__name__)

_NEW_STYLE_ID = re.compile(r"^\d{4}\.\d{4,5}(v\d+)?$")
_PRE_2007_ID = re.compile(r"^([a-z\-]+)(\d{7})$")
_YEAR_NEW_ID = re.compile(r"^(\d{2})(\d{2})\.\d{4,5}$")
_YEAR_OLD_ID = re.compile(r"^[a-z\-]+(?:\.[A-Za-z]{2})?/(\d{2})(\d{2})\d{3}$")
_VERSION_SUFFIX = re.compile(r"v\d+$")

BODY_FALLBACK_SECTION = "body"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS metadata (
    arxiv_id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    authors_json TEXT NOT NULL,
    year INTEGER,
    abstract TEXT NOT NULL,
    license TEXT NOT NULL,
    categories_json TEXT NOT NULL
)
"""


def bare_dataset_id(arxiv_id: str) -> str:
    """Re-insert the slash in pre-2007 slash-less dataset ids (E-2): nlin0608019 -> nlin/0608019."""
    if "." in arxiv_id or "/" in arxiv_id:
        return arxiv_id
    match = _PRE_2007_ID.match(arxiv_id)
    if match:
        return f"{match.group(1)}/{match.group(2)}"
    return arxiv_id


def bare_metadata_id(raw_id: str) -> str:
    """Strip the version suffix from snapshot ids (E-3): 0704.0001v2 -> 0704.0001."""
    return _VERSION_SUFFIX.sub("", raw_id)


def split_categories(categories: str | list) -> list[str]:
    """Snapshot categories: a one-element list of a space-separated string, or a plain string (E-17)."""
    if isinstance(categories, str):
        return categories.split()
    if isinstance(categories, list):
        return " ".join(str(c) for c in categories).split()
    raise ValueError(f"categories must be str or list, got {type(categories).__name__}")


def year_from_arxiv_id(arxiv_id: str) -> int | None:
    """First-submission year derived from a bare arxiv id (E-19); None if the id is unparseable.

    New-style YYMM.NNNN(N) -> 2000+YY; old-style archive[.SUB]/YYMMNNN -> 19YY if YY >= 91 else 20YY.
    MM outside 01-12 -> None.
    """
    match = _YEAR_NEW_ID.match(arxiv_id)
    if match:
        yy, mm = int(match.group(1)), int(match.group(2))
        return 2000 + yy if 1 <= mm <= 12 else None
    match = _YEAR_OLD_ID.match(arxiv_id)
    if match:
        yy, mm = int(match.group(1)), int(match.group(2))
        if not 1 <= mm <= 12:
            return None
        return 1900 + yy if yy >= 91 else 2000 + yy
    return None


def _parse_authors(raw: str) -> list[str]:
    """Snapshot authors are free text with ', ' / ' and ' separators; split deterministically."""
    return [a.strip() for a in raw.replace(" and ", ", ").split(", ") if a.strip()]


def build_metadata_index(
    metadata_path: Path,
    db_path: Path,
    counters: BuildCounters,
) -> None:
    """Stream the snapshot JSONL into a sqlite index (I-2); malformed lines skip + count."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(_SCHEMA)
        with metadata_path.open("r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                    raw_id = str(record["id"])
                    title = str(record["title"])
                    categories = split_categories(record["categories"])
                    if not raw_id or not title:
                        raise ValueError("empty id or title")
                    bare_id = bare_metadata_id(raw_id)
                    conn.execute(
                        "INSERT OR REPLACE INTO metadata VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (
                            bare_id,
                            title,
                            json.dumps(_parse_authors(str(record.get("authors", "")))),
                            year_from_arxiv_id(bare_id),
                            str(record.get("abstract", "")),
                            str(record.get("license") or ""),
                            json.dumps(categories),
                        ),
                    )
                except (json.JSONDecodeError, KeyError, TypeError, ValueError, sqlite3.Error) as exc:
                    counters.malformed_metadata_lines += 1
                    logger.warning("malformed metadata line skipped: %s", exc)
                    continue
        conn.commit()
    finally:
        conn.close()


def lookup_metadata(db_path: Path, arxiv_id: str) -> tuple[str, list[str], int | None, str, str, list[str]] | None:
    """Point query by bare id; None = no usable row (missing, or year unparseable)."""
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute(
            "SELECT title, authors_json, year, abstract, license, categories_json FROM metadata WHERE arxiv_id = ?",
            (arxiv_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None or row[2] is None:
        return None
    return (
        str(row[0]),
        list(json.loads(row[1])),
        int(row[2]),
        str(row[3]),
        str(row[4]),
        list(json.loads(row[5])),
    )


def category_in_scope(categories: list[str], defaults: KBDefaults, mode: str) -> bool:
    """Filter test (E-17): mode 'cs' = any cs.* category; mode 'all' = everything."""
    if mode == "all":
        return True
    return any(c.startswith(defaults.category_prefix) for c in categories)


def join_paper(
    record: dict,
    db_path: Path,
    counters: BuildCounters,
) -> Paper | None:
    """Join one parsed source record against the index; None = drop (E-1 / unusable metadata).

    Abstract comes from the source's `abstract_text[]` (the join fills only
    title/authors/year/categories/license per stack.md). E-7 fallback lives here:
    empty section_names[] folds article_text[] into one `body` section. Emits
    Paper only when metadata is complete — empty title/authors/categories are
    unusable metadata and drop the paper (never nulls). Nameless sections are
    skipped and counted; section names colliding after normalization merge
    (last wins) and are counted.
    """
    arxiv_id = bare_dataset_id(str(record["article_id"]))
    row = lookup_metadata(db_path, arxiv_id)
    if row is None:
        return None
    title, authors, year, _abstract, license, categories = row
    if not categories or not authors or not normalize(title):
        return None  # no scoping, composition, or citation target possible

    section_names = [normalize(str(n)) for n in record.get("section_names") or []]
    section_bodies = [_join_pieces(s) for s in record.get("sections") or []]
    sections: dict[str, str] = {}
    for name, body in zip(section_names, section_bodies, strict=False):
        if not name:
            counters.nameless_sections_dropped += 1
            continue
        if name in sections:
            counters.sections_merged_name_collision += 1
        sections[name] = body
    if not section_names:
        body = _join_pieces(record.get("article_text") or "")
        sections = {BODY_FALLBACK_SECTION: body} if body else {}
    abstract = _join_pieces(record.get("abstract_text") or [])

    return Paper(
        arxiv_id=arxiv_id,
        title=normalize(title),
        authors=authors,
        year=year,
        abstract=normalize(abstract),
        sections={name: normalize(text) for name, text in sections.items() if normalize(text)},
        source_link=f"https://arxiv.org/abs/{arxiv_id}",
        license=normalize(license),
        categories=categories,
    )


def _join_pieces(value: object) -> str:
    """Dataset fields arrive as paragraph lists (sections[][]) or plain strings; join to text."""
    if isinstance(value, list):
        return " ".join(str(piece) for piece in value)
    return str(value)


def count_in_scope(
    records: Iterator[dict],
    db_path: Path,
    defaults: KBDefaults,
    counters: BuildCounters,
) -> int:
    """Pass A: count cs.*-scoped joins to decide widening (E-4) before emitting anything."""
    cs_yield = 0
    for record in records:
        paper = join_paper(record, db_path, counters)
        if paper is None:
            continue
        if category_in_scope(paper.categories, defaults, "cs"):
            cs_yield += 1
    return cs_yield


def resolve_filter_mode(cs_yield: int, defaults: KBDefaults) -> tuple[str, bool]:
    """E-4: cs.* unless the pre-clean yield is under the threshold; returns (mode, widened)."""
    if cs_yield < defaults.widen_threshold:
        logger.warning(
            "cs.* yield %d below threshold %d — widening filter to all categories",
            cs_yield,
            defaults.widen_threshold,
        )
        return "all", True
    return "cs", False


def iter_scope(
    records: Iterator[dict],
    db_path: Path,
    defaults: KBDefaults,
    counters: BuildCounters,
    mode: str,
) -> Iterator[Paper]:
    """Pass B: join + drop (counting E-1 and year failures) + scope filter, in source order."""
    for record in records:
        paper = join_paper(record, db_path, counters)
        if paper is None:
            counters.dropped_no_metadata += 1
            continue
        if not category_in_scope(paper.categories, defaults, mode):
            continue
        yield paper


def check_index_usable(db_path: Path) -> None:
    """Fail loudly (stage error) when the index file is missing or empty."""
    if not db_path.exists() or db_path.stat().st_size == 0:
        raise KBStageError("join", f"metadata index missing or empty: {db_path}")
