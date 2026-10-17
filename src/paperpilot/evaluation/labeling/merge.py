"""Adjudication, label resolution, validation, and the JSONL writers (`queries`, `qrels`, `qa_pairs`).

Story 1.6 · CAP-6 · AD-1 · AD-2 (chunk ids are only read, checked against `chunks.jsonl`) · AD-5 (merged outputs
are class 1: never overwritten without `--replace`, written atomically). Covers I-8, E-1, E-4, E-6, E-7, E-8.

Label resolution, per (query_id, chunk_id) across every annotator's label (single source of the rule, also used
by `gold-sheets`): an adjudication row decides when one exists (`adjudicated=true`); otherwise one label -> that
label; all labels equal -> that label; a strict majority (> 50%) -> the majority label; otherwise an adjudication
row is still required (E-4).
"""

from __future__ import annotations

import json
import logging
import os
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from paperpilot.core.errors import LabelingStageError
from paperpilot.evaluation.labeling import (
    ANNOTATORS,
    DEV_SHARE,
    JUDGMENT_STAGES,
    LABEL_FLOOR,
    N_UNANSWERABLE,
    NO_EVIDENCE,
    REQUIRED_STAGES,
    SLICE_SIZE,
    UNANSWERABLE_CHUNK_ID,
    seeded,
)
from paperpilot.evaluation.labeling.sheets import (
    ADJUDICATION_COLUMNS,
    AnswerCheck,
    Findings,
    Judgment,
    Question,
    adjudication_path,
    check_questions,
    load_answer_checks,
    load_gold_rows,
    load_judgments,
    load_questions,
    load_review_rows,
    parse_query_id,
    raw_dir,
    read_checked,
)

logger = logging.getLogger(__name__)

PairKey = tuple[str, str]
GOLD_WORDS_WARN = 40


@dataclass(frozen=True)
class Adjudication:
    query_id: str
    chunk_id: str
    final: str
    adjudicator: str
    reason: str
    where: str


@dataclass(frozen=True)
class Resolved:
    query_id: str
    chunk_id: str
    label: int
    annotators: tuple[str, ...]
    adjudicated: bool


@dataclass(frozen=True)
class Resolution:
    judgments: tuple[Judgment, ...]
    adjudications: dict[PairKey, Adjudication]
    resolved: dict[PairKey, Resolved]
    missing: tuple[PairKey, ...]


@dataclass(frozen=True)
class SliceResult:
    included: tuple[str, ...]
    excluded_yes: tuple[str, ...]
    pending: tuple[str, ...]
    need_adjudication: tuple[str, ...]
    missing_author: tuple[str, ...]
    replacements: dict[str, str]


@dataclass(frozen=True)
class Outputs:
    queries: tuple[dict, ...]
    qrels: tuple[dict, ...]
    qa_pairs: tuple[dict, ...]
    no_evidence: tuple[str, ...]
    slice_result: SliceResult

    @property
    def labeled_rows(self) -> int:
        return len(self.qrels) + len(self.qa_pairs)


# --- adjudication + resolution ---------------------------------------------------------------


def load_adjudications(eval_dir: str | Path) -> tuple[dict[PairKey, Adjudication], Findings]:
    """Read `adjudication.csv` (absent = none yet); values and adjudicator ids are checked."""
    findings = Findings()
    path = adjudication_path(eval_dir)
    out: dict[PairKey, Adjudication] = {}
    if not path.is_file():
        findings.info.append(f"no adjudication file at {path} (nothing adjudicated yet)")
        return out, findings
    sheet, issues = read_checked(path, ADJUDICATION_COLUMNS)
    findings.errors.extend(issues)
    if sheet is None:
        return out, findings
    for row in sheet.rows:
        v = row.values
        where = sheet.where(row)
        key = (v["query_id"], v["chunk_id"])
        allowed = ("yes", "no") if v["chunk_id"] == UNANSWERABLE_CHUNK_ID else ("0", "1", "2")
        final = v["final_relevance"].lower() if v["chunk_id"] == UNANSWERABLE_CHUNK_ID else v["final_relevance"]
        if final not in allowed:
            findings.error(where, f"final_relevance {v['final_relevance']!r} is not one of {list(allowed)} (pair {list(key)})")
            continue
        if v["adjudicator"] not in ANNOTATORS:
            findings.error(where, f"adjudicator {v['adjudicator']!r} is not one of {list(ANNOTATORS)}")
            continue
        if key in out:
            findings.error(where, f"duplicate adjudication for {list(key)} (first at {out[key].where})")
            continue
        out[key] = Adjudication(v["query_id"], v["chunk_id"], final, v["adjudicator"], v["reason"], where)
    return out, findings


def resolve_label(labels: Sequence[int]) -> int | None:
    """One label, all equal, or a strict (> 50%) majority -> that label; else None (needs adjudication)."""
    counts = Counter(labels)
    label, top = counts.most_common(1)[0]
    if len(counts) == 1 or top * 2 > len(labels):
        return label
    return None


def resolve_judgments(
    judgments: Sequence[Judgment], adjudications: dict[PairKey, Adjudication]
) -> tuple[dict[PairKey, Resolved], list[PairKey]]:
    """Resolve every (query_id, chunk_id); returns the resolved map and the pairs still needing adjudication."""
    grouped: dict[PairKey, list[Judgment]] = {}
    for j in judgments:
        grouped.setdefault((j.query_id, j.chunk_id), []).append(j)
    resolved: dict[PairKey, Resolved] = {}
    missing: list[PairKey] = []
    for key in sorted(grouped):
        annotators = tuple(sorted({j.annotator for j in grouped[key]}))
        adjudication = adjudications.get(key)
        if adjudication is not None:
            resolved[key] = Resolved(key[0], key[1], int(adjudication.final), annotators, True)
            continue
        label = resolve_label([j.label for j in grouped[key]])
        if label is None:
            missing.append(key)
        else:
            resolved[key] = Resolved(key[0], key[1], label, annotators, False)
    return resolved, missing


def _stage_present(eval_dir: str | Path, stage: str) -> bool:
    directory = raw_dir(eval_dir, stage)
    return directory.is_dir() and any(directory.glob("*.csv"))


def resolve_stages(
    eval_dir: str | Path, reports_dir: str | Path, *, final: bool = False
) -> tuple[Resolution, Findings]:
    """Load pilot/round1/round2 labels + adjudication and resolve them (shared by `merge` and `gold-sheets`)."""
    findings = Findings()
    judgments: list[Judgment] = []
    for stage in JUDGMENT_STAGES:
        need_all = final and (stage in REQUIRED_STAGES or _stage_present(eval_dir, stage))
        stage_judgments, stage_findings = load_judgments(eval_dir, reports_dir, stage, require_all=need_all)
        judgments.extend(stage_judgments)
        findings.extend(stage_findings)
    seen: dict[tuple[str, str, str], Judgment] = {}
    for j in judgments:
        key = (j.annotator, j.query_id, j.chunk_id)
        if key in seen:
            findings.error(j.where, f"{j.annotator} already judged ({j.query_id}, {j.chunk_id}) at {seen[key].where}")
        seen.setdefault(key, j)
        parsed = parse_query_id(j.query_id)
        if j.stage != "pilot" and parsed is not None and parsed[0] == j.annotator:
            findings.error(j.where, f"{j.annotator} judged their own question {j.query_id}")
    adjudications, adj_findings = load_adjudications(eval_dir)
    findings.extend(adj_findings)
    resolved, missing = resolve_judgments(judgments, adjudications)
    known = {(j.query_id, j.chunk_id) for j in judgments}
    for key, adjudication in adjudications.items():
        if key[1] != UNANSWERABLE_CHUNK_ID and key not in known:
            findings.warnings.append(f"{adjudication.where}: adjudication for {list(key)} matches no judged pair")
    return Resolution(tuple(judgments), adjudications, resolved, tuple(missing)), findings


# --- unanswerable slice (E-7) --------------------------------------------------------------------


def resolve_slice(
    questions: Sequence[Question], checks: Sequence[AnswerCheck], adjudications: dict[PairKey, Adjudication]
) -> SliceResult:
    """Questions whose author answered `no` and whose double-checker (if any) agrees; else excluded or pending."""
    by_query: dict[str, list[AnswerCheck]] = {}
    for check in checks:
        by_query.setdefault(check.query_id, []).append(check)
    included: list[str] = []
    excluded: list[str] = []
    pending: list[str] = []
    need_adj: list[str] = []
    missing_author: list[str] = []
    replacements: dict[str, str] = {}
    for q in sorted((q for q in questions if not q.answerable), key=lambda q: q.query_id):
        rows = by_query.get(q.query_id, [])
        author_rows = [r for r in rows if r.annotator == q.author]
        if not author_rows:
            (pending if parse_query_id(q.query_id)[2] > N_UNANSWERABLE else missing_author).append(q.query_id)  # type: ignore[index]
            continue
        author = author_rows[0]
        adjudication = adjudications.get((q.query_id, UNANSWERABLE_CHUNK_ID))
        if adjudication is not None:
            final = adjudication.final
        elif any(r.answer != author.answer for r in rows if r.annotator != q.author):
            need_adj.append(q.query_id)
            continue
        else:
            final = author.answer
        if final == "no":
            included.append(q.query_id)
        else:
            excluded.append(q.query_id)
            if author.new_question:
                replacements[q.query_id] = author.new_question
    return SliceResult(tuple(included), tuple(excluded), tuple(pending), tuple(need_adj), tuple(missing_author), replacements)


def split_slice(included: Sequence[str]) -> dict[str, str]:
    """Seeded 40/60 dev/heldout split, stratified by author via round-robin (E-7: still 40% if < 100 survive)."""
    by_author: dict[str, list[str]] = {}
    for qid in sorted(included):
        by_author.setdefault(qid.split("-")[0], []).append(qid)
    for author, ids in by_author.items():
        seeded("split", author).shuffle(ids)
    target = round(DEV_SHARE * len(included))
    dev: list[str] = []
    queues = [by_author[author] for author in sorted(by_author)]
    while len(dev) < target and any(queues):
        for queue in queues:
            if queue and len(dev) < target:
                dev.append(queue.pop(0))
    dev_set = set(dev)
    return {qid: ("dev" if qid in dev_set else "heldout") for qid in sorted(included)}


# --- chunk ids (E-6, AD-2) ---------------------------------------------------------------------


def read_chunk_ids(kb_dir: str | Path) -> set[str]:
    """`chunk_id` of every line of `chunks.jsonl`, streamed; nothing else is kept in memory."""
    path = Path(kb_dir) / "chunks.jsonl"
    if not path.is_file():
        raise LabelingStageError("merge", f"chunk store not found: {path}; run `make kb`")
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                ids.add(json.loads(line)["chunk_id"])
            except (ValueError, KeyError, TypeError) as exc:
                raise LabelingStageError("merge", f"{path}:{lineno}: bad chunk record: {exc!r}") from exc
    return ids


# --- validate + build -------------------------------------------------------------------------


def validate(
    eval_dir: str | Path, reports_dir: str | Path, kb_dir: str | Path, *, final: bool = False
) -> tuple[Findings, Outputs | None]:
    """Every check before a merge; `final` adds required stages, missing adjudications and the row floor."""
    findings = check_questions(eval_dir, kb_dir)
    questions: list[Question] = []
    try:
        questions = load_questions(eval_dir)
    except LabelingStageError:
        findings.warnings.append("questions unreadable; question-dependent checks skipped")

    resolution, res_findings = resolve_stages(eval_dir, reports_dir, final=final)
    findings.extend(res_findings)
    if resolution.missing:
        listing = ", ".join(f"({q}, {c})" for q, c in resolution.missing[:20]) + (
            f", ... and {len(resolution.missing) - 20} more" if len(resolution.missing) > 20 else ""
        )
        message = f"{len(resolution.missing)} pair(s) need an adjudication row in adjudication.csv: {listing}"
        if final:
            findings.error(adjudication_path(eval_dir), message)
        else:
            findings.warnings.append(message)

    checks, check_findings = load_answer_checks(eval_dir, reports_dir, require_all=final)
    findings.extend(check_findings)
    gold_rows, gold_findings = load_gold_rows(eval_dir, reports_dir, require_all=final)
    findings.extend(gold_findings)
    reviews, review_findings = load_review_rows(eval_dir, reports_dir, require_all=final and _stage_present(eval_dir, "gold-review"))
    findings.extend(review_findings)

    # E-6 — every chunk id must exist in the current chunks.jsonl.
    where_by_chunk: dict[str, list[str]] = {}
    for j in resolution.judgments:
        where_by_chunk.setdefault(j.chunk_id, []).append(j.where)
    for adjudication in resolution.adjudications.values():
        if adjudication.chunk_id != UNANSWERABLE_CHUNK_ID:
            where_by_chunk.setdefault(adjudication.chunk_id, []).append(adjudication.where)
    for gold in gold_rows:
        for chunk_id in gold.chunk_ids:
            where_by_chunk.setdefault(chunk_id, []).append(gold.where)
    known_chunks = read_chunk_ids(kb_dir)
    absent = sorted(c for c in where_by_chunk if c not in known_chunks)
    if absent:
        first = [f"{c} (first at {where_by_chunk[c][0]})" for c in absent[:20]]
        findings.error(
            Path(kb_dir) / "chunks.jsonl",
            f"{len(absent)} chunk_id(s) not in chunks.jsonl (KB rebuilt since labeling?): " + "; ".join(first),
        )

    slice_result = resolve_slice(questions, checks, resolution.adjudications) if checks else SliceResult((), (), (), (), (), {})
    if checks:
        if slice_result.missing_author:
            findings.error(
                raw_dir(eval_dir, "unanswerable"),
                f"no answered_by_library row from the author for: {', '.join(slice_result.missing_author)}",
            )
        if slice_result.need_adjudication:
            message = (
                "author and double-checker disagree; add an adjudication row (chunk_id "
                f"{UNANSWERABLE_CHUNK_ID}, final_relevance yes/no) for: {', '.join(slice_result.need_adjudication)}"
            )
            if final:
                findings.error(adjudication_path(eval_dir), message)
            else:
                findings.warnings.append(message)
        if slice_result.pending:
            findings.warnings.append(f"replacement question(s) not yet checked, excluded from the slice: {', '.join(slice_result.pending)}")
        for qid in slice_result.excluded_yes:
            proposed = slice_result.replacements.get(qid)
            findings.warnings.append(
                f"{qid} answered 'yes' (library can answer it): needs a replacement question"
                + (f" (author proposes: {proposed})" if proposed else "")
            )
        findings.info.append(
            f"unanswerable slice: {len(slice_result.included)} of {SLICE_SIZE} questions survive"
            + ("" if len(slice_result.included) >= SLICE_SIZE else " (below the target)")
        )

    no_evidence: list[str] = []
    qa_rows: list[dict] = []
    answerable = {q.query_id: q for q in questions if q.answerable}
    if gold_rows:
        gold_by_query = {g.query_id: g for g in gold_rows}
        two_labeled: dict[str, set[str]] = {}
        for (qid, cid), r in resolution.resolved.items():
            if r.label == 2:
                two_labeled.setdefault(qid, set()).add(cid)
        for qid in sorted(answerable):
            gold = gold_by_query.get(qid)
            if gold is None:
                findings.error(raw_dir(eval_dir, "gold"), f"no gold row for answerable question {qid}")
                continue
            if gold.gold_answer.upper() == NO_EVIDENCE:
                no_evidence.append(qid)
                continue
            if not gold.chunk_ids:
                findings.error(gold.where, f"{qid}: gold_passages is empty for a real answer (write NO_EVIDENCE if none)")
                continue
            outside = [c for c in gold.chunk_ids if c not in two_labeled.get(qid, set())]
            if outside:
                findings.error(gold.where, f"{qid}: gold_passages not labeled 2 for this question: {outside}")
                continue
            if len(gold.gold_answer.split()) > GOLD_WORDS_WARN:
                findings.warnings.append(f"{gold.where}: {qid} gold answer has {len(gold.gold_answer.split())} words (about 30 expected)")
            qa_rows.append(
                {
                    "query_id": qid,
                    "question": answerable[qid].text,
                    "gold_answer": gold.gold_answer,
                    "gold_chunk_ids": list(dict.fromkeys(gold.chunk_ids)),
                    "answerable": True,
                    "split": None,
                }
            )
        if no_evidence:
            findings.warnings.append(f"{len(no_evidence)} NO_EVIDENCE gold answer(s), kept out of qa_pairs: {', '.join(no_evidence)}")
    for review in reviews:
        if review.review == "disagree":
            findings.warnings.append(f"{review.where}: {review.annotator} disagrees with the gold answer of {review.query_id}: {review.reason or '(no reason)'}")

    outputs: Outputs | None = None
    if questions and not findings.errors:
        split = split_slice(slice_result.included)
        by_id = {q.query_id: q for q in questions}
        queries = [
            {"query_id": q.query_id, "text": q.text, "type": q.type, "subfield": q.subfield, "answerable": True, "author": q.author}
            for q in questions
            if q.answerable
        ] + [
            {"query_id": qid, "text": by_id[qid].text, "type": None, "subfield": None, "answerable": False, "author": by_id[qid].author}
            for qid in slice_result.included
        ]
        qa_rows += [
            {"query_id": qid, "question": by_id[qid].text, "gold_answer": "", "gold_chunk_ids": [], "answerable": False, "split": split[qid]}
            for qid in slice_result.included
        ]
        qrels = [
            {"query_id": r.query_id, "chunk_id": r.chunk_id, "relevance": r.label, "annotators": list(r.annotators), "adjudicated": r.adjudicated}
            for _, r in sorted(resolution.resolved.items())
        ]
        outputs = Outputs(
            tuple(sorted(queries, key=lambda row: row["query_id"])),
            tuple(qrels),
            tuple(sorted(qa_rows, key=lambda row: row["query_id"])),
            tuple(no_evidence),
            slice_result,
        )
        message = f"labeled rows: {len(outputs.qrels)} qrels + {len(outputs.qa_pairs)} QA = {outputs.labeled_rows} (floor {LABEL_FLOOR})"
        if outputs.labeled_rows < LABEL_FLOOR:
            if final:
                findings.error(eval_dir, message + ": below the floor")
            else:
                findings.info.append(message + ": below the floor (checked only at merge/--final)")
        else:
            findings.info.append(message)
    return findings, outputs


def output_paths(eval_dir: str | Path) -> dict[str, Path]:
    base = Path(eval_dir)
    return {name: base / f"{name}.jsonl" for name in ("queries", "qrels", "qa_pairs")}


def _jsonl(rows: Sequence[dict]) -> bytes:
    return "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows).encode("utf-8")


def write_outputs(eval_dir: str | Path, outputs: Outputs, *, replace: bool) -> list[Path]:
    """Write the three JSONL files atomically; refuses to overwrite existing ones without `replace`."""
    paths = output_paths(eval_dir)
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing and not replace:
        raise LabelingStageError("merge", f"refusing to overwrite existing {', '.join(existing)}; pass --replace to overwrite")
    payloads = {"queries": outputs.queries, "qrels": outputs.qrels, "qa_pairs": outputs.qa_pairs}
    tmps: dict[str, Path] = {}
    try:
        for name, path in paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(_jsonl(payloads[name]))
            tmps[name] = tmp
        for name, path in paths.items():
            os.replace(tmps[name], path)
    finally:
        for tmp in tmps.values():
            tmp.unlink(missing_ok=True)
    return list(paths.values())
