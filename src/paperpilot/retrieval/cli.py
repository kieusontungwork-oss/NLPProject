"""Retrieval CLI: `python -m paperpilot.retrieval.cli {index,search}` (exit 0 ok / 3 stage).

Story 1.3 · CAP-2 · AD-5: `index` is the only writer of class-3 index artifacts under `indexes/`
(each component built in a temp sibling dir and swapped in only when complete). Human output on
stdout, errors on stderr; `run_*_command` never raise.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import time
from pathlib import Path

from paperpilot.core.config import (
    DEFAULT_ABLATIONS_PATH,
    DEFAULT_INDEX_DIR,
    DEFAULT_KB_DIR,
    RetrievalConfig,
    get_row,
)
from paperpilot.core.errors import PaperPilotError
from paperpilot.core.schemas import EvidencePack
from paperpilot.retrieval import dense as dense_mod
from paperpilot.retrieval import docstore as docstore_mod
from paperpilot.retrieval import sparse as sparse_mod
from paperpilot.retrieval.manifest import atomic_component
from paperpilot.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_STAGE = 3


def build_indexes(
    row: RetrievalConfig,
    kb_dir: Path,
    index_dir: Path,
    encoder: dense_mod.Encoder | None = None,
) -> dict[str, float]:
    """Build the docstore plus every leg the row enables; returns seconds per component."""
    store_hash = docstore_mod.chunk_store_hash(kb_dir)
    durations: dict[str, float] = {}
    if row.use_dense and encoder is None:
        encoder = dense_mod.SentenceTransformerEncoder(row.embedding_model)  # fail fast, before any component

    start = time.perf_counter()
    with atomic_component(index_dir / "docstore") as tmp:
        store_manifest = docstore_mod.build_docstore(kb_dir, tmp, store_hash=store_hash, config_row=row.id)
    durations["docstore"] = time.perf_counter() - start

    if row.use_sparse:
        start = time.perf_counter()
        with atomic_component(sparse_mod.sparse_dir(index_dir)) as tmp:
            sparse_mod.Bm25sRetriever.build(
                (chunk["text"] for _, chunk in docstore_mod.iter_chunks(kb_dir)),
                tmp,
                store_hash=store_hash,
                config_row=row.id,
            )
        durations["sparse"] = time.perf_counter() - start

    if row.use_dense:
        start = time.perf_counter()
        with atomic_component(dense_mod.dense_dir(index_dir, row.embedding_model)) as tmp:
            dense_mod.FaissDenseRetriever.build(
                (chunk["text"] for _, chunk in docstore_mod.iter_chunks(kb_dir)),
                encoder,
                tmp,
                model_id=row.embedding_model,
                store_hash=store_hash,
                config_row=row.id,
                total=store_manifest.n_chunks,
            )
        durations["dense"] = time.perf_counter() - start
    return durations


def format_pack(pack: EvidencePack) -> str:
    """Human-readable search output: one block per hit, then stage timings."""

    def fmt(value: float | None) -> str:
        return "-" if value is None else f"{value:.4f}"

    lines = [f"query_id={pack.query_id} legs={pack.effective_queries[0].legs} hits={len(pack.hits)}"]
    for hit in pack.hits:
        lines.append(
            f"{hit.rank:>3}. rrf={hit.rrf_score:.5f} bm25={fmt(hit.leg_scores.bm25)} "
            f"dense={fmt(hit.leg_scores.dense)}  {hit.title} — {hit.section_name} ({hit.year})"
        )
    timings = " ".join(f"{key}={value:.2f}" for key, value in pack.stage_timings_ms.items())
    lines.append(f"timings_ms: {timings}")
    return "\n".join(lines)


def _emit(text: str) -> int:
    """Write `text` + newline to stdout inside the never-raises guard; any I/O failure -> EXIT_STAGE."""
    try:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except (UnicodeEncodeError, BrokenPipeError, OSError) as exc:
        try:
            print(f"cannot write output to stdout: {type(exc).__name__}: {exc}", file=sys.stderr)
        except Exception:
            pass
        return EXIT_STAGE
    return EXIT_OK


def _add_common(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--row", required=True, help="config row id from configs/ablations.yaml (E1/E2/E3)")
    parser.add_argument("--config", type=Path, default=DEFAULT_ABLATIONS_PATH, help="ablations YAML")
    parser.add_argument("--kb-dir", type=Path, default=DEFAULT_KB_DIR, help="directory holding chunks.jsonl/papers.jsonl")
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR, help="directory for index artifacts")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paperpilot.retrieval", description="PaperPilot baseline retrieval")
    sub = parser.add_subparsers(dest="command", required=True)
    index_parser = sub.add_parser("index", help="build docstore + the indexes the row enables")
    _add_common(index_parser)
    search_parser = sub.add_parser("search", help="retrieve the top-k for a query")
    _add_common(search_parser)
    search_parser.add_argument("query", help="query text")
    search_parser.add_argument("--k", type=int, default=10, help="hits to return (default 10)")
    search_parser.add_argument("--json", action="store_true", help="print the EvidencePack as JSON")
    return parser


def run_index_command(args: argparse.Namespace, encoder: dense_mod.Encoder | None = None) -> int:
    """Build indexes for `args.row`; never raises."""
    try:
        row = get_row(args.row, args.config)
        durations = build_indexes(row, args.kb_dir, args.index_dir, encoder)
    except PaperPilotError as exc:
        print(f"index failed: {exc}", file=sys.stderr)
        return EXIT_STAGE
    except Exception as exc:
        print(f"index failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_STAGE
    summary = " ".join(f"{name}={secs:.2f}s" for name, secs in durations.items())
    return _emit(f"index ok: row={row.id} {summary}")


def run_search_command(args: argparse.Namespace, encoder: dense_mod.Encoder | None = None) -> int:
    """Retrieve for `args.query`; never raises."""
    try:
        row = get_row(args.row, args.config)
        retriever = Retriever.from_config(row, args.kb_dir, args.index_dir, encoder)
        pack = retriever.retrieve(args.query, args.k)
        text = json.dumps(pack.model_dump(), ensure_ascii=True, indent=2) if args.json else format_pack(pack)
    except PaperPilotError as exc:
        print(f"search failed: {exc}", file=sys.stderr)
        return EXIT_STAGE
    except Exception as exc:
        print(f"search failed: {type(exc).__name__}: {exc}", file=sys.stderr)
        return EXIT_STAGE
    return _emit(text)


def main(argv: list[str] | None = None) -> int:
    """CLI entry; argparse usage errors still exit 2 via SystemExit (argparse convention)."""
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    return run_index_command(args) if args.command == "index" else run_search_command(args)


if __name__ == "__main__":
    sys.exit(main())
