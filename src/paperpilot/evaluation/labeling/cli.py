"""Labeling CLI: `python -m paperpilot.evaluation.labeling.cli <subcommand>` (exit 0 ok / 1 validation / 3 stage).

Story 1.6 · CAP-6 · AD-1 (driver) · AD-5. Subcommands: catalog, check-questions, pilot, sheets,
unanswerable-sheets, agreement, gold-sheets, merge, validate. Human summaries go to stdout, problems to stderr;
every `run_<x>_command` returns an int and never raises (argparse usage errors still exit 2 via SystemExit).
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from paperpilot.core.config import DEFAULT_ABLATIONS_PATH, DEFAULT_INDEX_DIR, DEFAULT_KB_DIR
from paperpilot.core.errors import LabelingStageError, PaperPilotError
from paperpilot.evaluation.labeling import (
    ANNOTATORS,
    POOL_DEPTH,
    ROUND1_ROWS,
    UNANSWERABLE_ROW,
)
from paperpilot.evaluation.labeling import agreement as agreement_mod
from paperpilot.evaluation.labeling import merge as merge_mod
from paperpilot.evaluation.labeling import pooling
from paperpilot.evaluation.labeling.sheets import (
    GOLD_COLUMNS,
    JUDGMENT_COLUMNS,
    REVIEW_COLUMNS,
    UNANSWERABLE_COLUMNS,
    Findings,
    check_questions,
    drafted_path,
    load_gold_rows,
    load_questions,
    write_catalog,
    write_csv,
)

logger = logging.getLogger(__name__)

EXIT_OK = 0
EXIT_VALIDATION = 1
EXIT_STAGE = 3

DEFAULT_EVAL_DIR = Path("data/eval")
DEFAULT_REPORTS_DIR = Path("reports")


# --- output helpers -----------------------------------------------------------------------------


def _emit(text: str) -> int:
    """Write `text` + newline to stdout inside the never-raises guard; any I/O failure -> EXIT_STAGE."""
    try:
        sys.stdout.write(text + "\n")
        sys.stdout.flush()
    except (UnicodeEncodeError, BrokenPipeError, OSError) as exc:
        _err(f"cannot write output to stdout: {type(exc).__name__}: {exc}")
        return EXIT_STAGE
    return EXIT_OK


def _err(text: str) -> None:
    try:
        print(text, file=sys.stderr)
    except Exception:  # noqa: BLE001 - stderr may be closed; nothing left to report to
        pass


def _print_findings(findings: Findings, *, show_warnings: bool = True) -> int:
    """Info + warnings to stdout, errors to stderr; returns EXIT_VALIDATION if there are errors."""
    lines = list(findings.info)
    if show_warnings:
        lines += [f"warning: {w}" for w in findings.warnings]
    if lines and _emit("\n".join(lines)) != EXIT_OK:
        return EXIT_STAGE
    for issue in findings.errors:
        _err(f"error: {issue}")
    if findings.errors:
        _err(f"{len(findings.errors)} blocking issue(s); nothing was written")
        return EXIT_VALIDATION
    return EXIT_OK


def _guard(name: str, work) -> int:
    """Run `work() -> int`; typed stage errors and anything unexpected become EXIT_STAGE."""
    try:
        return work()
    except PaperPilotError as exc:
        _err(f"{name} failed: {exc}")
        return EXIT_STAGE
    except Exception as exc:  # noqa: BLE001 - run_*_command never raises
        _err(f"{name} failed: {type(exc).__name__}: {exc}")
        return EXIT_STAGE


def _questions_ready(args: argparse.Namespace) -> bool:
    """Drafting needs valid returned question sheets; blocking issues are printed and stop the command."""
    findings = check_questions(args.eval_dir, args.kb_dir)
    if findings.errors:
        _print_findings(Findings(errors=findings.errors), show_warnings=False)
        _err("fix the question sheets first (run `check-questions`)")
        return False
    return True


def _write_sheets(reports_dir: Path, stage: str, columns: tuple[str, ...], sheets: dict[str, list[dict[str, str]]], *, subdir: str = "") -> list[Path]:
    paths = []
    for annotator in ANNOTATORS:
        rows = sheets.get(annotator, [])
        if not rows:
            continue
        path = drafted_path(reports_dir, stage, annotator)
        if subdir:
            path = path.parent / subdir / path.name
        write_csv(path, columns, rows)
        paths.append(path)
    return paths


def _retrievers(args: argparse.Namespace, row_ids, encoder):
    return pooling.build_retrievers(row_ids, args.config, args.kb_dir, args.index_dir, encoder)


# --- subcommands ----------------------------------------------------------------------------


def run_catalog_command(args: argparse.Namespace) -> int:
    def work() -> int:
        out_dir = Path(args.reports_dir) / "labeling" / "kickoff"
        counts = write_catalog(args.kb_dir, out_dir)
        lines = [f"catalog ok: {sum(counts.values())} papers -> {out_dir}"]
        lines += [f"  {name}: {n}" for name, n in sorted(counts.items())]
        lines.append(f"wrote questions_{ANNOTATORS[0]}.csv .. questions_{ANNOTATORS[-1]}.csv (70 rows each)")
        return _emit("\n".join(lines))

    return _guard("catalog", work)


def run_check_questions_command(args: argparse.Namespace) -> int:
    return _guard("check-questions", lambda: _print_findings(check_questions(args.eval_dir, args.kb_dir)))


def run_pilot_command(args: argparse.Namespace, encoder=None) -> int:
    def work() -> int:
        if not _questions_ready(args):
            return EXIT_VALIDATION
        questions = load_questions(args.eval_dir)
        by_id = {q.query_id: q for q in questions}
        if args.questions:
            ids = sorted({part.strip() for part in args.questions.split(",") if part.strip()})
            bad = [i for i in ids if i not in by_id or not by_id[i].answerable]
            if bad:
                raise LabelingStageError("pilot", f"not answerable questions of the returned sheets: {bad}")
        else:
            ids = pooling.pick_pilot_questions(questions, args.auto)
        retrievers = _retrievers(args, ROUND1_ROWS, encoder)
        pools = pooling.build_pools(retrievers, [by_id[i] for i in ids], POOL_DEPTH)
        sheets = pooling.draft_pilot(ids, by_id, pools)
        paths = _write_sheets(Path(args.reports_dir), "pilot", JUDGMENT_COLUMNS, sheets)
        rows = len(sheets[ANNOTATORS[0]])
        return _emit(f"pilot ok: {len(ids)} questions ({', '.join(ids)}), {rows} rows in each of {len(paths)} identical sheets -> {paths[0].parent}")

    return _guard("pilot", work)


def run_sheets_command(args: argparse.Namespace, encoder=None) -> int:
    def work() -> int:
        rows = [r.strip() for r in args.rows.split(",") if r.strip()] if args.rows else []
        if args.round == 1 and rows:
            raise LabelingStageError("sheets", "--rows is only for --round 2")
        if args.round == 2 and not rows:
            raise LabelingStageError("sheets", "--round 2 needs --rows <config row ids>, e.g. --rows E4,E5a")
        if not _questions_ready(args):
            return EXIT_VALIDATION
        answerable = [q for q in load_questions(args.eval_dir) if q.answerable]
        if args.round == 1:
            piloted = pooling.pilot_query_ids(args.eval_dir, args.reports_dir)
            candidates = [q for q in answerable if q.query_id not in piloted]
            pools = pooling.build_pools(_retrievers(args, ROUND1_ROWS, encoder), candidates, POOL_DEPTH)
            purpose, stage = "round1", "round1"
        else:
            judged = pooling.judged_pairs(args.eval_dir)
            candidates = answerable
            full = pooling.build_pools(_retrievers(args, rows, encoder), candidates, POOL_DEPTH)
            pools = {qid: tuple(p for p in pool if (qid, p.chunk_id) not in judged) for qid, pool in full.items()}
            purpose, stage = f"round2:{','.join(sorted(rows))}", "round2"
        sheets, assignment = pooling.draft_round(candidates, pools, purpose)
        total = sum(assignment.loads.values())
        if total == 0:
            return _emit(f"sheets round {args.round}: nothing to draft (no unjudged passages)")
        lines = [f"sheets round {args.round}: {len(assignment.primary)} questions ({len(assignment.second)} double-labeled), {total} rows"]
        lines += [f"  {a}: {len(assignment.questions_of(a))} questions, {assignment.loads[a]} rows" for a in ANNOTATORS]
        offenders = pooling.balance_offenders(assignment.loads)
        if offenders:
            _emit("\n".join(lines))
            for offender in offenders:
                _err(f"error: load imbalance (> 5% from the mean): {offender}")
            _err("nothing was written")
            return EXIT_VALIDATION
        paths = _write_sheets(Path(args.reports_dir), stage, JUDGMENT_COLUMNS, sheets)
        lines.append(f"wrote {len(paths)} sheets -> {paths[0].parent}")
        return _emit("\n".join(lines))

    return _guard("sheets", work)


def run_unanswerable_sheets_command(args: argparse.Namespace, encoder=None) -> int:
    def work() -> int:
        if not _questions_ready(args):
            return EXIT_VALIDATION
        unanswerable = [q for q in load_questions(args.eval_dir) if not q.answerable]
        only = [part.strip() for part in args.only.split(",") if part.strip()] if args.only else None
        if only is not None:
            known = {q.query_id for q in unanswerable}
            bad = [i for i in only if i not in known]
            if bad:
                raise LabelingStageError("unanswerable-sheets", f"--only ids are not unanswerable questions of the returned sheets: {bad}")
        needed = [q for q in unanswerable if only is None or q.query_id in only]
        pools = pooling.build_ranked(_retrievers(args, (UNANSWERABLE_ROW,), encoder)[UNANSWERABLE_ROW], needed, POOL_DEPTH)
        sheets = pooling.draft_unanswerable(unanswerable if only is None else needed, pools, only)
        subdir = "replacements" if only is not None else ""
        paths = _write_sheets(Path(args.reports_dir), "unanswerable", UNANSWERABLE_COLUMNS, sheets, subdir=subdir)
        counts = ", ".join(f"{a}={len(rows)}" for a, rows in sheets.items() if rows)
        return _emit(f"unanswerable-sheets ok: rows per sheet {counts} -> {paths[0].parent if paths else '(none)'}")

    return _guard("unanswerable-sheets", work)


def run_agreement_command(args: argparse.Namespace) -> int:
    def work() -> int:
        labels, binary, findings = agreement_mod.stage_labels(args.eval_dir, args.reports_dir, args.stage)
        if findings.errors:
            return _print_findings(Findings(errors=findings.errors))
        report, warnings = agreement_mod.compute_agreement(args.stage, labels, binary=binary)
        for warning in warnings + findings.warnings:
            _err(f"warning: {warning}")
        if report.verdict == "NO DATA":
            _err(f"no annotator pair has overlapping rows in stage {args.stage!r}; nothing to measure")
            return EXIT_VALIDATION
        path = agreement_mod.write_report(args.reports_dir, report)
        return _emit(agreement_mod.format_report(report) + f"\nwrote {path}")

    return _guard("agreement", work)


def run_gold_sheets_command(args: argparse.Namespace) -> int:
    def work() -> int:
        if not _questions_ready(args):
            return EXIT_VALIDATION
        questions = load_questions(args.eval_dir)
        resolution, findings = merge_mod.resolve_stages(args.eval_dir, args.reports_dir)
        if resolution.missing:
            listing = ", ".join(f"({q}, {c})" for q, c in resolution.missing[:20])
            findings.error(args.eval_dir, f"{len(resolution.missing)} pair(s) need an adjudication row first: {listing}")
        if findings.errors:
            return _print_findings(Findings(errors=findings.errors))
        if args.review:
            gold_rows, gold_findings = load_gold_rows(args.eval_dir, args.reports_dir, require_all=True)
            if gold_findings.errors:
                return _print_findings(Findings(errors=gold_findings.errors))
            sheets = pooling.draft_gold_review(questions, gold_rows, resolution)
            paths = _write_sheets(Path(args.reports_dir), "gold-review", REVIEW_COLUMNS, sheets)
            kind = "review"
        else:
            sheets = pooling.draft_gold(questions, resolution)
            paths = _write_sheets(Path(args.reports_dir), "gold", GOLD_COLUMNS, sheets)
            kind = "gold"
        counts = ", ".join(f"{a}={len(rows)}" for a, rows in sheets.items())
        return _emit(f"gold-sheets {kind} ok: rows per sheet {counts} -> {paths[0].parent if paths else '(none)'}")

    return _guard("gold-sheets", work)


def run_validate_command(args: argparse.Namespace) -> int:
    def work() -> int:
        findings, _ = merge_mod.validate(args.eval_dir, args.reports_dir, args.kb_dir, final=args.final)
        code = _print_findings(findings)
        if code == EXIT_OK:
            code = _emit("validate ok" + (" (final)" if args.final else ""))
        return code

    return _guard("validate", work)


def run_merge_command(args: argparse.Namespace) -> int:
    def work() -> int:
        findings, outputs = merge_mod.validate(args.eval_dir, args.reports_dir, args.kb_dir, final=True)
        code = _print_findings(findings)
        if code != EXIT_OK or outputs is None:
            return EXIT_VALIDATION
        paths = merge_mod.write_outputs(args.eval_dir, outputs, replace=args.replace)
        slice_result = outputs.slice_result
        lines = [
            f"merge ok: {len(outputs.queries)} queries, {len(outputs.qrels)} qrels, {len(outputs.qa_pairs)} QA pairs "
            f"({outputs.labeled_rows} labeled rows)",
            f"unanswerable slice: {len(slice_result.included)} questions",
        ]
        if outputs.no_evidence:
            lines.append(f"NO_EVIDENCE gold answers ({len(outputs.no_evidence)}): {', '.join(outputs.no_evidence)}")
        lines += [f"wrote {p}" for p in paths]
        return _emit("\n".join(lines))

    return _guard("merge", work)


# --- parser / entry -------------------------------------------------------------------------


def _add_common(parser: argparse.ArgumentParser, *, config: bool = False) -> None:
    parser.add_argument("--kb-dir", type=Path, default=DEFAULT_KB_DIR, help="directory holding chunks.jsonl/papers.jsonl")
    parser.add_argument("--index-dir", type=Path, default=DEFAULT_INDEX_DIR, help="directory with the built indexes")
    parser.add_argument("--eval-dir", type=Path, default=DEFAULT_EVAL_DIR, help="class-1 eval directory (returned sheets, JSONL)")
    parser.add_argument("--reports-dir", type=Path, default=DEFAULT_REPORTS_DIR, help="class-3 reports directory (drafted sheets)")
    if config:
        parser.add_argument("--config", type=Path, default=DEFAULT_ABLATIONS_PATH, help="ablations YAML")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="paperpilot.evaluation.labeling", description="PaperPilot labeling sprint tooling")
    sub = parser.add_subparsers(dest="command", required=True)

    _add_common(sub.add_parser("catalog", help="write the paper catalog + empty question sheets"))
    _add_common(sub.add_parser("check-questions", help="validate the returned question sheets"))

    pilot = sub.add_parser("pilot", help="draft the pilot sheets (identical for P1-P5)")
    _add_common(pilot, config=True)
    group = pilot.add_mutually_exclusive_group(required=True)
    group.add_argument("--questions", help="comma-separated answerable query ids")
    group.add_argument("--auto", type=int, metavar="N", help="pick N questions (different authors, different subfields)")

    sheets = sub.add_parser("sheets", help="draft the round-1 or round-2 sheets")
    _add_common(sheets, config=True)
    sheets.add_argument("--round", type=int, choices=(1, 2), required=True)
    sheets.add_argument("--rows", help="round 2: comma-separated config row ids whose top-10 are pooled")

    unanswerable = sub.add_parser("unanswerable-sheets", help="draft the unanswerable-check sheets")
    _add_common(unanswerable, config=True)
    unanswerable.add_argument("--only", help="comma-separated (replacement) query ids; draft only these")

    agreement = sub.add_parser("agreement", help="pairwise agreement + gate verdict")
    _add_common(agreement)
    agreement.add_argument("--stage", required=True, choices=agreement_mod.AGREEMENT_STAGES)

    gold = sub.add_parser("gold-sheets", help="draft the gold-answer sheets (or the reviews with --review)")
    _add_common(gold)
    gold.add_argument("--review", action="store_true", help="draft the gold-answer review sheets")

    merge = sub.add_parser("merge", help="validate, then write queries/qrels/qa_pairs JSONL")
    _add_common(merge)
    merge.add_argument("--replace", action="store_true", help="overwrite existing data/eval/*.jsonl")

    validate = sub.add_parser("validate", help="check every returned sheet and the merge inputs")
    _add_common(validate)
    validate.add_argument("--final", action="store_true", help="also require every stage, adjudications and the row floor")
    return parser


def main(argv: list[str] | None = None, encoder=None) -> int:
    """CLI entry; argparse usage errors still exit 2 via SystemExit (argparse convention)."""
    args = _parser().parse_args(argv)
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s", stream=sys.stderr)
    if args.command == "pilot":
        return run_pilot_command(args, encoder)
    if args.command == "sheets":
        return run_sheets_command(args, encoder)
    if args.command == "unanswerable-sheets":
        return run_unanswerable_sheets_command(args, encoder)
    handlers = {
        "catalog": run_catalog_command,
        "check-questions": run_check_questions_command,
        "agreement": run_agreement_command,
        "gold-sheets": run_gold_sheets_command,
        "merge": run_merge_command,
        "validate": run_validate_command,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
