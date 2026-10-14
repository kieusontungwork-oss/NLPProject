"""KB build CLI: `python -m paperpilot.kb.cli build` (exit 0 / 1 verify / 3 stage).

Story 1.2 · CAP-1 · spine AD-5: this module is the ONLY writer of class-2
artifacts (data/raw/, data/kb/). Writes are atomic (tmp + os.replace); reruns
are wholesale rebuilds. Local file overrides (--source-zip, --metadata-file)
exist for offline tests and re-runs; production defaults download from the
pinned URLs in core.config.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

from paperpilot.core.config import DEFAULTS, GCS_METADATA_URL, S3_SOURCE_URL
from paperpilot.core.errors import KBStageError, PaperPilotError
from paperpilot.core.schemas import Chunk, KBStats, Paper
from paperpilot.kb import acquire, metadata
from paperpilot.kb.chunk import chunk_paper
from paperpilot.kb.clean import clean_paper_text_for_checks, clean_sections, is_english
from paperpilot.kb.dedup import dedup_papers
from paperpilot.kb.stats import BuildCounters, build_stats

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_VERIFY = 1
EXIT_STAGE = 3


def build(
    data_dir: Path,
    limit: int | None,
    defaults=DEFAULTS,
    source_zip: Path | None = None,
    metadata_file: Path | None = None,
) -> KBStats:
    """Run the full pipeline; returns the stats object the CLI persists. Raises KBStageError."""
    counters = BuildCounters()
    raw_dir = data_dir / "data" / "raw"
    kb_dir = data_dir / "data" / "kb"
    kb_dir.mkdir(parents=True, exist_ok=True)

    zip_path = source_zip if source_zip is not None else raw_dir / "arxiv-dataset.zip"
    if source_zip is None:
        acquire.download_file(zip_path, S3_SOURCE_URL)
    if not zip_path.exists():
        raise KBStageError("acquire", f"source zip not found: {zip_path}")

    meta_path = metadata_file if metadata_file is not None else raw_dir / "arxiv-metadata-oai.json"
    if metadata_file is None:
        acquire.download_file(meta_path, GCS_METADATA_URL)
    if not meta_path.exists():
        raise KBStageError("join", f"metadata snapshot not found: {meta_path}")

    db_path = kb_dir / "metadata-index.tmp.sqlite3"
    metadata.build_metadata_index(meta_path, db_path, counters)
    metadata.check_index_usable(db_path)

    try:
        # Pass A: decide widening (E-4) from the cs.* yield before emitting anything.
        # Malformed lines are counted only in pass B, so pass A uses throwaway counters.
        pass_a_counters = BuildCounters()
        cs_yield = metadata.count_in_scope(
            acquire.iter_source_records(zip_path, pass_a_counters, limit), db_path, defaults, pass_a_counters
        )
        filter_mode, widened = metadata.resolve_filter_mode(cs_yield, defaults)

        # Pass B: join -> scope -> english -> dedup -> chunk, in source order.
        papers: list[Paper] = []
        chunks: list[Chunk] = []
        joined = metadata.iter_scope(
            acquire.iter_source_records(zip_path, counters, limit), db_path, defaults, counters, filter_mode
        )
        for paper in joined:
            section_pairs = clean_sections(list(paper.sections), list(paper.sections.values()), counters, defaults)
            check_text = clean_paper_text_for_checks([paper.abstract] if paper.abstract else [], section_pairs)
            if not is_english(check_text, defaults):
                counters.non_english_dropped += 1
                continue
            paper = paper.model_copy(
                update={"sections": {name: text for name, text in section_pairs}}
            )
            papers.append(paper)

        papers = list(dedup_papers(iter(papers), counters))
        for paper in papers:
            chunks.extend(chunk_paper(paper, defaults, counters))

        verify(papers, chunks)

        stats = build_stats(
            papers,
            chunks,
            counters,
            defaults,
            source_url=S3_SOURCE_URL,
            metadata_url=GCS_METADATA_URL,
            filter_mode=filter_mode,
            filter_widened=widened,
            generated_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    finally:
        db_path.unlink(missing_ok=True)

    write_jsonl(kb_dir / "papers.jsonl", [p.model_dump() for p in papers])
    write_jsonl(kb_dir / "chunks.jsonl", [c.model_dump() for c in chunks])
    write_json(kb_dir / "kb_stats.json", stats.model_dump())
    return stats


def verify(papers: list[Paper], chunks: list[Chunk]) -> None:
    """Post-build invariants; failure = exit 1 (verification), never a silent bad artifact."""
    ids = [c.chunk_id for c in chunks]
    if len(ids) != len(set(ids)):
        dupes = sorted({cid for cid in ids if ids.count(cid) > 1})
        raise PaperPilotError(f"chunk_id uniqueness violated: {dupes[:5]}")
    paper_ids = {p.arxiv_id for p in papers}
    orphans = [c for c in chunks if c.arxiv_id not in paper_ids]
    if orphans:
        raise PaperPilotError(f"chunks reference unknown papers: {orphans[0].arxiv_id}")
    if any(not p.title or not p.categories for p in papers):
        raise PaperPilotError("null metadata detected in emitted papers")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    """Atomic JSONL write (house convention: one compact json per line, tmp + os.replace)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as out:
            for row in rows:
                out.write(json.dumps(row, ensure_ascii=False, sort_keys=False) + "\n")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def write_json(path: Path, payload: dict) -> None:
    """Atomic JSON write (house convention: indent=2, sorted keys, trailing newline)."""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        with tmp.open("w", encoding="utf-8") as out:
            out.write(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.replace(path)
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


def run_build_command(argv: list[str] | None = None) -> int:
    """CLI entry: never raises; human summary on stdout, errors on stderr."""
    parser = argparse.ArgumentParser(prog="paperpilot.kb", description="Build the PaperPilot knowledge base")
    sub = parser.add_subparsers(dest="command", required=True)
    build_parser = sub.add_parser("build", help="acquire, join, clean, dedup, chunk, stats")
    build_parser.add_argument("--limit", type=int, default=None, help="smoke slice: first N valid records")
    build_parser.add_argument("--data-dir", type=Path, default=Path("."), help="repo root for data/")
    build_parser.add_argument("--source-zip", type=Path, default=None, help="local zip override (offline/tests)")
    build_parser.add_argument("--metadata-file", type=Path, default=None, help="local metadata JSONL override (offline/tests)")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    try:
        stats = build(
            data_dir=args.data_dir,
            limit=args.limit,
            source_zip=args.source_zip,
            metadata_file=args.metadata_file,
        )
    except KBStageError as exc:
        print(f"kb build failed: {exc}", file=sys.stderr)
        return EXIT_STAGE
    except PaperPilotError as exc:
        print(f"kb build failed verification: {exc}", file=sys.stderr)
        return EXIT_VERIFY

    print(
        f"kb build ok: papers={stats.papers} chunks={stats.chunks} words={stats.words} "
        f"types={stats.types} years={stats.year_min}-{stats.year_max} filter={stats.provenance.filter_mode}"
    )
    return EXIT_OK


if __name__ == "__main__":
    sys.exit(run_build_command())
