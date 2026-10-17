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
import shutil
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

from paperpilot.core.errors import LabelingStageError
from paperpilot.core.ids import normalize
from paperpilot.evaluation.labeling import (
    ANNOTATORS,
    ANSWERABLE_QA_FLOOR,
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
from paperpilot.evaluation.labeling.agreement import LabelMap, compute_agreement
from paperpilot.evaluation.labeling.sheets import (
    ADJUDICATION_COLUMNS,
    AnswerCheck,
    Findings,
    Judgment,
    Question,
    adjudication_path,
    atomic_write,
    check_questions,
    drafted_annotators,
    load_answer_checks,
    load_gold_rows,
    load_judgments,
    load_questions,
    load_review_rows,
    parse_query_id,
    raw_dir,
    read_checked,
    returned_annotators,
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
    summary: dict
    review_disagreements: tuple[dict, ...] = ()

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
    return bool(returned_annotators(eval_dir, stage))


def _stage_active(eval_dir: str | Path, reports_dir: str | Path, stage: str) -> bool:
    """A stage is active once it has returned sheets or drafted sheets."""
    return _stage_present(eval_dir, stage) or bool(drafted_annotators(reports_dir, stage))


def resolve_stages(
    eval_dir: str | Path, reports_dir: str | Path, *, final: bool = False, complete: bool = False
) -> tuple[Resolution, Findings]:
    """Load pilot/round1/round2 labels + adjudication and resolve them (shared by `merge` and `gold-sheets`).

    With `final` or `complete`, every drafted sheet of an active stage (pilot and round 1 always) must be back.
    """
    findings = Findings()
    judgments: list[Judgment] = []
    for stage in JUDGMENT_STAGES:
        need_all = (final or complete) and (stage in REQUIRED_STAGES or _stage_active(eval_dir, reports_dir, stage))
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
    labelers: dict[PairKey, set[str]] = {}
    for j in judgments:
        labelers.setdefault((j.query_id, j.chunk_id), set()).add(j.annotator)
    for key, adjudication in adjudications.items():
        if key[1] == UNANSWERABLE_CHUNK_ID:
            continue
        if key not in labelers:
            findings.warnings.append(f"{adjudication.where}: adjudication for {list(key)} matches no judged pair")
        elif adjudication.adjudicator in labelers[key] and set(ANNOTATORS) - labelers[key]:
            findings.error(
                adjudication.where,
                f"adjudicator {adjudication.adjudicator} labeled this pair; a third annotator must decide ({sorted(set(ANNOTATORS) - labelers[key])} did not)",
            )
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


def split_slice(included: Sequence[str], existing: dict[str, str] | None = None) -> dict[str, str]:
    """Seeded 40/60 dev/heldout split, stratified by author (E-7: still `round(0.4 n)` dev if fewer survive).

    Ids that already have a split in `existing` (the committed `qa_pairs.jsonl`) keep it. Only new ids are placed:
    dev until the dev count reaches `round(0.4 n)`, each time taking the next id of the author with the fewest dev
    rows (ties: lowest author id); the rest go to heldout. Within an author the order is a seeded shuffle.
    """
    members = set(included)
    split = {qid: s for qid, s in (existing or {}).items() if qid in members and s in ("dev", "heldout")}
    dev_by_author: Counter[str] = Counter(qid.split("-")[0] for qid, s in split.items() if s == "dev")
    queues: dict[str, list[str]] = {}
    for qid in sorted(members - set(split)):
        queues.setdefault(qid.split("-")[0], []).append(qid)
    for author, ids in queues.items():
        seeded("split", author).shuffle(ids)
    need = round(DEV_SHARE * len(members)) - sum(dev_by_author.values())
    while need > 0 and any(queues.values()):
        author = min((a for a, ids in queues.items() if ids), key=lambda a: (dev_by_author[a], a))
        split[queues[author].pop(0)] = "dev"
        dev_by_author[author] += 1
        need -= 1
    for ids in queues.values():
        for qid in ids:
            split[qid] = "heldout"
    return {qid: split[qid] for qid in sorted(members)}


def load_existing_splits(eval_dir: str | Path, findings: Findings) -> dict[str, str]:
    """`split` of every unanswerable row of an existing `qa_pairs.jsonl` (kept stable across merges)."""
    path = output_paths(eval_dir)["qa_pairs"]
    if not path.is_file():
        return {}
    splits: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            if row.get("answerable") is False and row.get("split") in ("dev", "heldout"):
                splits[row["query_id"]] = row["split"]
    except (ValueError, KeyError, OSError, AttributeError) as exc:
        findings.warnings.append(f"cannot read existing splits from {path} ({exc!r}); the split is recomputed")
        return {}
    return splits


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


def _listing(items: Sequence[str], limit: int = 20) -> str:
    return ", ".join(items[:limit]) + (f", ... and {len(items) - limit} more" if len(items) > limit else "")


def _judgment_stats(judgments: Sequence[Judgment], stages: Sequence[str]) -> dict:
    """Labeled (query, passage) pairs, share labeled by 2+ people, pooled raw agreement and mean kappa."""
    labels: LabelMap = {a: {} for a in ANNOTATORS}
    people: dict[PairKey, set[str]] = {}
    for j in judgments:
        if j.stage in stages:
            labels[j.annotator][(j.query_id, j.chunk_id)] = j.label
            people.setdefault((j.query_id, j.chunk_id), set()).add(j.annotator)
    report, _ = compute_agreement("summary", labels, binary=True)
    doubled = sum(1 for who in people.values() if len(who) >= 2)
    return {
        "labeled_rows": len(people),
        "double_labeled_pct": 100 * doubled / len(people) if people else None,
        "raw_agreement_pooled": report.pooled_raw,
        "cohen_kappa_mean": report.mean_kappa,
    }


def _label_stats(labels: LabelMap, labeled_rows: int, double_pct: float | None) -> dict:
    report, _ = compute_agreement("summary", labels, binary=False)
    return {
        "labeled_rows": labeled_rows,
        "double_labeled_pct": double_pct,
        "raw_agreement_pooled": report.pooled_raw,
        "cohen_kappa_mean": report.mean_kappa,
    }


def format_summary(summary: dict) -> str:
    """The evaluation-plan table: labeled rows, double-labeled %, pooled raw agreement, mean kappa per artifact."""

    def num(value: float | None, digits: int = 3) -> str:
        return "n/a" if value is None else f"{value:.{digits}f}"

    lines = [f"{'artifact':<24}{'rows':>8}{'double %':>10}{'raw (pooled)':>14}{'kappa':>8}"]
    for name, stats in summary["artifacts"].items():
        lines.append(
            f"{name:<24}{stats['labeled_rows']:>8}{num(stats['double_labeled_pct'], 1):>10}"
            f"{num(stats['raw_agreement_pooled']):>14}{num(stats['cohen_kappa_mean']):>8}"
        )
    unique = summary["unique_questions"]
    lines.append(
        f"unique questions: {unique['total']} ({unique['answerable']} answerable + {unique['unanswerable_slice']} unanswerable slice)"
    )
    lines.append(
        f"total labeled rows: {summary['total_labeled_rows']} ({summary['qrels_rows']} qrels + {summary['qa_pairs_rows']} QA)"
    )
    return "\n".join(lines)


def validate(
    eval_dir: str | Path,
    reports_dir: str | Path,
    kb_dir: str | Path,
    *,
    final: bool = False,
    allow_short_slice: bool = False,
    allow_short_qa: bool = False,
) -> tuple[Findings, Outputs | None]:
    """Every check before a merge; `final` adds required stages, missing adjudications, coverage, the row floor,
    the 100-question 40/60 slice and the 250 answerable QA rows (relaxed by the two `allow_short_*` flags)."""
    findings = check_questions(eval_dir, kb_dir)
    questions: list[Question] = []
    try:
        questions = load_questions(eval_dir)
    except LabelingStageError:
        findings.warnings.append("questions unreadable; question-dependent checks skipped")

    resolution, res_findings = resolve_stages(eval_dir, reports_dir, final=final)
    findings.extend(res_findings)
    if resolution.missing:
        pairs = [f"({q}, {c})" for q, c in resolution.missing]
        message = f"{len(resolution.missing)} pair(s) need an adjudication row in adjudication.csv: {_listing(pairs)}"
        if final:
            findings.error(adjudication_path(eval_dir), message)
        else:
            findings.warnings.append(message)

    checks, check_findings = load_answer_checks(eval_dir, reports_dir, require_all=final)
    findings.extend(check_findings)
    gold_rows, gold_findings = load_gold_rows(eval_dir, reports_dir, require_all=final)
    findings.extend(gold_findings)
    reviews, review_findings = load_review_rows(eval_dir, reports_dir, require_all=final)
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

    answerable = {q.query_id: q for q in questions if q.answerable}
    current_text = {q.query_id: normalize(q.text) for q in questions}

    # H11 — a question edited after pooling no longer matches what annotators saw.
    drifted = sorted({j.query_id for j in resolution.judgments if j.query_id in current_text and normalize(j.question) != current_text[j.query_id]})
    if drifted:
        findings.warnings.append(f"question text on returned sheets differs from the current question for: {_listing(drifted)}")

    # Coverage — every answerable question needs at least one resolved judgment.
    if resolution.resolved and _stage_present(eval_dir, "round1"):
        covered = {qid for qid, _ in resolution.resolved}
        uncovered = sorted(set(answerable) - covered)
        if uncovered:
            message = f"{len(uncovered)} answerable question(s) have no resolved judgment: {_listing(uncovered)}"
            if final:
                findings.error(raw_dir(eval_dir, "round1"), message)
            else:
                findings.warnings.append(message)
        relevant = {qid for (qid, _), r in resolution.resolved.items() if r.label >= 1}
        no_relevant = sorted((covered & set(answerable)) - relevant)
        if no_relevant:
            findings.warnings.append(f"{len(no_relevant)} question(s) have no passage labeled 1 or 2: {_listing(no_relevant)}")

    # Unanswerable slice (E-7, H9, H10).
    slice_result = resolve_slice(questions, checks, resolution.adjudications) if checks else SliceResult((), (), (), (), (), {})
    if checks:
        labelers_of: dict[str, set[str]] = {}
        for c in checks:
            labelers_of.setdefault(c.query_id, set()).add(c.annotator)
        for (qid, cid), adjudication in resolution.adjudications.items():
            if cid != UNANSWERABLE_CHUNK_ID:
                continue
            people = labelers_of.get(qid, set()) | ({parse_query_id(qid)[0]} if parse_query_id(qid) else set())
            if adjudication.adjudicator in people and set(ANNOTATORS) - people:
                findings.error(adjudication.where, f"adjudicator {adjudication.adjudicator} is the author or a double-checker of {qid}; a third annotator must decide")
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
        n_slice = len(slice_result.included)
        findings.info.append(
            f"unanswerable slice: {n_slice} of {SLICE_SIZE} questions survive" + ("" if n_slice >= SLICE_SIZE else " (below the target)")
        )
        if n_slice > SLICE_SIZE:
            replacements = [q for q in slice_result.included if parse_query_id(q)[2] > N_UNANSWERABLE]  # type: ignore[index]
            extras = replacements if len(replacements) >= n_slice - SLICE_SIZE else list(slice_result.included[SLICE_SIZE:])
            findings.error(
                raw_dir(eval_dir, "unanswerable"),
                f"the slice has {n_slice} questions (more than {SLICE_SIZE}); extras to drop: {_listing(list(extras))}",
            )
        elif final and n_slice < SLICE_SIZE and not allow_short_slice:
            findings.error(
                raw_dir(eval_dir, "unanswerable"),
                f"the slice has {n_slice} of {SLICE_SIZE} questions; finish the replacements or pass --allow-short-slice",
            )

    # Gold answers (E-8).
    no_evidence: list[str] = []
    qa_rows: list[dict] = []
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
        message = f"answerable QA rows: {len(qa_rows)} (floor {ANSWERABLE_QA_FLOOR}); NO_EVIDENCE: {', '.join(no_evidence) or 'none'}"
        if len(qa_rows) < ANSWERABLE_QA_FLOOR:
            if final and not allow_short_qa:
                findings.error(raw_dir(eval_dir, "gold"), message + "; pass --allow-short-qa to accept")
            else:
                findings.info.append(message + " (below the floor)")
        else:
            findings.info.append(message)
    review_disagreements = tuple(
        {"query_id": r.query_id, "reviewer": r.annotator, "reason": r.reason}
        for r in sorted(reviews, key=lambda r: (r.query_id, r.annotator))
        if r.review == "disagree"
    )
    for item in review_disagreements:
        findings.warnings.append(f"gold review: {item['reviewer']} disagrees with the gold answer of {item['query_id']}: {item['reason'] or '(no reason)'}")

    outputs: Outputs | None = None
    if questions and not findings.errors:
        existing = load_existing_splits(eval_dir, findings)
        split = split_slice(slice_result.included, existing)
        n_dev = sum(1 for s in split.values() if s == "dev")
        if final and not allow_short_slice and split and (n_dev, len(split) - n_dev) != (40, 60):
            findings.error(output_paths(eval_dir)["qa_pairs"], f"split is {n_dev} dev / {len(split) - n_dev} heldout, expected 40 / 60")
            return findings, None
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
        n_answerable_qa = sum(1 for row in qa_rows if row["answerable"])
        # --- summary (what agreement-report.md is filled from)
        review_labels: LabelMap = {a: {} for a in ANNOTATORS}
        for r in reviews:
            review_labels[r.annotator][r.query_id] = r.review
            parsed = parse_query_id(r.query_id)
            if parsed is not None and parsed[0] != r.annotator:
                review_labels[parsed[0]][r.query_id] = "agree"
        qa_ids = {row["query_id"] for row in qa_rows if row["answerable"]}
        reviewed_qa = [r for r in reviews if r.query_id in qa_ids]
        unans_labels: LabelMap = {a: {} for a in ANNOTATORS}
        unans_people: dict[str, set[str]] = {}
        for c in checks:
            unans_labels[c.annotator][c.query_id] = c.answer
            unans_people.setdefault(c.query_id, set()).add(c.annotator)
        n_unans = len(unans_people)
        gold_review_stats = _label_stats(review_labels, len(reviews), 100.0 if reviews else None)
        summary = {
            "artifacts": {
                "qrels_pilot_round1": _judgment_stats(resolution.judgments, ("pilot", "round1")),
                "qrels_round2": _judgment_stats(resolution.judgments, ("round2",)),
                "qa_pairs_answerable": {
                    "labeled_rows": n_answerable_qa,
                    "double_labeled_pct": 100 * len({r.query_id for r in reviewed_qa}) / n_answerable_qa if n_answerable_qa else None,
                    "raw_agreement_pooled": sum(r.review == "agree" for r in reviewed_qa) / len(reviewed_qa) if reviewed_qa else None,
                    "cohen_kappa_mean": None,
                },
                "unanswerable_check": _label_stats(
                    unans_labels, n_unans, 100 * sum(1 for who in unans_people.values() if len(who) >= 2) / n_unans if n_unans else None
                ),
                "gold_review": gold_review_stats,
            },
            "unique_questions": {
                "answerable": len(answerable),
                "unanswerable_slice": len(slice_result.included),
                "total": len(answerable) + len(slice_result.included),
            },
            "qrels_rows": len(qrels),
            "qa_pairs_rows": len(qa_rows),
            "total_labeled_rows": len(qrels) + len(qa_rows),
            "unanswerable_slice": {
                "size": len(slice_result.included),
                "dev": n_dev,
                "heldout": len(split) - n_dev,
                "excluded_yes": list(slice_result.excluded_yes),
                "pending": list(slice_result.pending),
            },
            "no_evidence": list(no_evidence),
            "gold_review_disagreements": list(review_disagreements),
            "notes": {"cohen_kappa_mean": "mean over annotator pairs where kappa is defined; gold_review kappa is not meaningful (the author is always `agree`)"},
        }
        outputs = Outputs(
            tuple(sorted(queries, key=lambda row: row["query_id"])),
            tuple(qrels),
            tuple(sorted(qa_rows, key=lambda row: row["query_id"])),
            tuple(no_evidence),
            slice_result,
            summary,
            review_disagreements,
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
    """Write the three JSONL files as a set; refuses to overwrite existing ones without `replace`.

    Existing files are copied to `<name>.bak` first; all three temp files are written, then replaced one by one.
    On any failure the originals are restored from the `.bak` copies (new files are removed) and the temp files
    are deleted; the `.bak` copies are deleted only after all three replacements succeeded.
    """
    paths = output_paths(eval_dir)
    existing = [str(p) for p in paths.values() if p.exists()]
    if existing and not replace:
        raise LabelingStageError("merge", f"refusing to overwrite existing {', '.join(existing)}; pass --replace to overwrite")
    payloads = {"queries": outputs.queries, "qrels": outputs.qrels, "qa_pairs": outputs.qa_pairs}
    backups: dict[str, Path] = {}
    tmps: dict[str, Path] = {}
    replaced: list[str] = []
    try:
        for name, path in paths.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                backups[name] = path.with_name(path.name + ".bak")
                shutil.copy2(path, backups[name])
        for name, path in paths.items():
            tmp = path.with_name(path.name + ".tmp")
            tmp.write_bytes(_jsonl(payloads[name]))
            tmps[name] = tmp
        for name, path in paths.items():
            os.replace(tmps[name], path)
            replaced.append(name)
    except BaseException:
        for name in replaced:
            if name in backups:
                shutil.copyfile(backups[name], paths[name])
            else:
                paths[name].unlink(missing_ok=True)
        for tmp in tmps.values():
            tmp.unlink(missing_ok=True)
        for backup in backups.values():
            backup.unlink(missing_ok=True)
        raise
    for backup in backups.values():
        backup.unlink(missing_ok=True)
    return list(paths.values())


def write_summary(reports_dir: str | Path, outputs: Outputs) -> Path:
    """`<reports-dir>/labeling/merge_summary.json` (class 3)."""
    path = Path(reports_dir) / "labeling" / "merge_summary.json"
    atomic_write(path, (json.dumps(outputs.summary, indent=2, ensure_ascii=False) + "\n").encode("utf-8"))
    return path
