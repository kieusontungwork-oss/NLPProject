"""Pooling and assignment: top-10 union of E1/E2/E3, seeded shuffle, balanced assignment, sheet drafting.

Story 1.6 · CAP-6 · AD-1 (retrieval only through `paperpilot.retrieval.Retriever`) · AD-5 (drafted sheets are
class 3). Covers I-3, I-4, I-6, I-7, E-9, E-10. Every random choice comes from `seeded(purpose, key)`, and every
unordered collection is sorted before it is written, so equal inputs give byte-identical sheets (E-9). Source
row and rank never reach a sheet (they stay hidden from annotators).
"""

from __future__ import annotations

import logging
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from itertools import zip_longest
from pathlib import Path

from paperpilot.core.config import RetrievalConfig, get_row
from paperpilot.core.errors import LabelingStageError
from paperpilot.core.schemas import Hit
from paperpilot.evaluation.labeling import (
    ANNOTATORS,
    CELL_CAP_CHARS,
    LOAD_TOLERANCE,
    N_UNANSWERABLE,
    NO_EVIDENCE,
    PASSAGE_CAP_CHARS,
    POOL_DEPTH,
    seeded,
    share_count,
)
from paperpilot.evaluation.labeling.merge import Resolution
from paperpilot.evaluation.labeling.sheets import (
    JUDGMENT_COLUMNS,
    REPLACEMENTS,
    UNANSWERABLE_COLUMNS,
    Findings,
    GoldRow,
    Judgment,
    Question,
    drafted_annotators,
    drafted_dir,
    parse_query_id,
    raw_dir,
    raw_path,
    read_checked,
    stage_files,
    strip_sentence_tags,
)
from paperpilot.retrieval.retriever import Retriever

logger = logging.getLogger(__name__)

PairKey = tuple[str, str]


@dataclass(frozen=True)
class Passage:
    """A passage as shown to annotators (display text only; the id is never derived from it)."""

    chunk_id: str
    paper_title: str
    section: str
    year: int
    text: str


@dataclass(frozen=True)
class Assignment:
    primary: dict[str, str]
    second: dict[str, str]
    loads: dict[str, int]  # rows added by this assignment
    base: dict[str, int] | None = None  # rows already assigned in earlier rounds (round 2 balances cumulatively)

    @property
    def cumulative(self) -> dict[str, int]:
        return {a: n + (self.base or {}).get(a, 0) for a, n in self.loads.items()}

    def questions_of(self, annotator: str) -> list[str]:
        ids = [q for q, a in self.primary.items() if a == annotator] + [q for q, a in self.second.items() if a == annotator]
        return sorted(ids)


# --- retrieval + pools -----------------------------------------------------------------------


def display_text(text: str, header_prefix: str) -> str:
    """Chunk text without its header prefix, `<S>`/`</S>` stripped, whitespace collapsed."""
    body = text[len(header_prefix) :] if header_prefix and text.startswith(header_prefix) else text
    return strip_sentence_tags(body)


def passage_from_hit(hit: Hit) -> Passage:
    return Passage(hit.chunk_id, hit.title, hit.section_name, hit.year, display_text(hit.text, hit.header_prefix))


def build_retrievers(
    row_ids: Sequence[str], config_path: str | Path, kb_dir: str | Path, index_dir: str | Path, encoder=None
) -> dict[str, Retriever]:
    """One Retriever per config row id (`Retriever.from_config`; an unknown row raises ConfigError)."""
    rows: dict[str, RetrievalConfig] = {row_id: get_row(row_id, config_path) for row_id in row_ids}
    return {row_id: Retriever.from_config(row, kb_dir, index_dir, encoder) for row_id, row in rows.items()}


def pool_question(retrievers: Mapping[str, Retriever], question: Question, k: int = POOL_DEPTH) -> tuple[Passage, ...]:
    """Union of each retriever's top-`k`; sorted by chunk id, then shuffled with the seed keyed by query_id."""
    union: dict[str, Passage] = {}
    for row_id in sorted(retrievers):
        for hit in retrievers[row_id].retrieve(question.text, k).hits:
            union.setdefault(hit.chunk_id, passage_from_hit(hit))
    ordered = [union[chunk_id] for chunk_id in sorted(union)]
    seeded("pool", question.query_id).shuffle(ordered)
    return tuple(ordered)


def build_pools(
    retrievers: Mapping[str, Retriever], questions: Sequence[Question], k: int = POOL_DEPTH
) -> dict[str, tuple[Passage, ...]]:
    return {q.query_id: pool_question(retrievers, q, k) for q in sorted(questions, key=lambda q: q.query_id)}


def build_ranked(
    retriever: Retriever, questions: Sequence[Question], k: int = POOL_DEPTH
) -> dict[str, tuple[Passage, ...]]:
    """One retriever's top-`k` in rank order per question (unanswerable check sheets: no shuffling)."""
    return {q.query_id: tuple(passage_from_hit(h) for h in retriever.retrieve(q.text, k).hits) for q in questions}


def cap_text(text: str, limit: int) -> str:
    """`text` cut to at most `limit` characters, ending in " …" when it was cut (display only)."""
    return text if len(text) <= limit else text[: limit - 2] + " …"


def format_passages(passages: Sequence[Passage], labels: Sequence[str]) -> str:
    """`[label] <title> — <section> (<year>): <text>` blocks separated by blank lines.

    Display only: each passage's text is capped at 2,000 characters and the whole cell at 45,000, to stay under
    Google Sheets' 50,000-character cell limit; the round-trip compares against the drafted (capped) text.
    """
    blocks = (
        f"[{label}] {p.paper_title} — {p.section} ({p.year}): {cap_text(p.text, PASSAGE_CAP_CHARS)}"
        for label, p in zip(labels, passages)
    )
    return cap_text("\n\n".join(blocks), CELL_CAP_CHARS)


# --- assignment ------------------------------------------------------------------------------


def interleaved_order(ids: Sequence[str], authors: Mapping[str, str]) -> list[str]:
    """Sorted query ids taken round-robin across authors (P1-001, P2-001, ..., P5-001, P1-002, ...).

    A strictly lexicographic pass leaves the last author's questions for the end, when that author cannot take
    any of them, which starves them by ~15% (measured on the synthetic KB); interleaving keeps loads within +-5%.
    """
    by_author: dict[str, list[str]] = {}
    for qid in sorted(ids):
        by_author.setdefault(authors[qid], []).append(qid)
    return [qid for group in zip_longest(*(by_author[a] for a in sorted(by_author))) for qid in group if qid is not None]


def assign(
    weights: Mapping[str, int], authors: Mapping[str, str], purpose: str, base_loads: Mapping[str, int] | None = None
) -> Assignment:
    """Least-loaded assignment (ties -> lowest id); nobody judges their own question; 15% double-labeled.

    `base_loads` (rows already assigned in earlier rounds) start the load counters, so round 2 balances the
    cumulative load; `Assignment.loads` still reports only the rows this call added.
    """
    ids = sorted(weights)
    doubled = set(seeded("double", purpose).sample(ids, share_count(len(ids)))) if ids else set()
    base = {a: (base_loads or {}).get(a, 0) for a in ANNOTATORS}
    loads = dict(base)
    primary: dict[str, str] = {}
    second: dict[str, str] = {}
    for qid in interleaved_order(ids, authors):
        eligible = [a for a in ANNOTATORS if a != authors[qid]]
        chosen = min(eligible, key=lambda a: (loads[a], a))
        primary[qid] = chosen
        loads[chosen] += weights[qid]
        if qid in doubled:
            other = min((a for a in eligible if a != chosen), key=lambda a: (loads[a], a))
            second[qid] = other
            loads[other] += weights[qid]
    return Assignment(primary, second, {a: loads[a] - base[a] for a in ANNOTATORS}, base if base_loads else None)


def balance_offenders(loads: Mapping[str, int], tolerance: float = LOAD_TOLERANCE) -> list[str]:
    """Annotators whose load deviates from the mean by more than `tolerance` (relative)."""
    mean = sum(loads.values()) / len(loads)
    if mean == 0:
        return []
    return [f"{a} has {n} rows ({(n - mean) / mean:+.1%} vs mean {mean:.1f})" for a, n in sorted(loads.items()) if abs(n - mean) > tolerance * mean]


# --- judgment sheets (pilot / round 1 / round 2) --------------------------------------------------


def _judgment_rows(question: Question, passages: Sequence[Passage], first_row_id: int) -> list[dict[str, str]]:
    return [
        {
            "row_id": str(first_row_id + i),
            "query_id": question.query_id,
            "question": question.text,
            "passage_id": p.chunk_id,
            "paper_title": p.paper_title,
            "section": p.section,
            "year": str(p.year),
            "passage": p.text,
        }
        for i, p in enumerate(passages)
    ]


def draft_judgment_sheet(
    query_ids: Sequence[str], questions: Mapping[str, Question], pools: Mapping[str, Sequence[Passage]]
) -> list[dict[str, str]]:
    """Rows for one annotator: questions in sorted order, each with its (already shuffled) pool."""
    rows: list[dict[str, str]] = []
    for qid in sorted(query_ids):
        rows.extend(_judgment_rows(questions[qid], pools[qid], len(rows) + 1))
    return rows


def draft_pilot(
    pilot_ids: Sequence[str], questions: Mapping[str, Question], pools: Mapping[str, Sequence[Passage]]
) -> dict[str, list[dict[str, str]]]:
    """I-3: identical sheets for every annotator."""
    rows = draft_judgment_sheet(pilot_ids, questions, pools)
    return {annotator: [dict(row) for row in rows] for annotator in ANNOTATORS}


def pick_pilot_questions(questions: Sequence[Question], n: int, exclude: Collection[str] = ()) -> list[str]:
    """`--auto n` (1 <= n <= 5): n answerable questions, each from a different author, covering different
    subfields (seeded); ids in `exclude` (already drafted for round 1) are never picked."""
    if not 1 <= n <= len(ANNOTATORS):
        raise LabelingStageError("pilot", f"--auto needs 1 <= N <= {len(ANNOTATORS)}, got {n}")
    by_author: dict[str, list[Question]] = {}
    for q in sorted(questions, key=lambda q: q.query_id):
        if q.answerable and q.query_id not in exclude:
            by_author.setdefault(q.author, []).append(q)
    if len(by_author) < n:
        raise LabelingStageError("pilot", f"--auto {n} needs answerable questions from {n} different authors; found {len(by_author)}")
    authors = sorted(by_author)
    rng = seeded("pilot", "auto")
    rng.shuffle(authors)
    chosen: list[str] = []
    used_subfields: set[str] = set()
    for author in authors[:n]:
        candidates = by_author[author]
        fresh = [q for q in candidates if q.subfield not in used_subfields]
        pick = rng.choice(fresh or candidates)
        used_subfields.add(pick.subfield)
        chosen.append(pick.query_id)
    return sorted(chosen)


def _pairs_of(path, findings: Findings) -> list[tuple[str, str]]:
    sheet, issues = read_checked(path, JUDGMENT_COLUMNS)
    if sheet is None:
        findings.errors.extend(issues)
        return []
    return [(row.values["query_id"], row.values["passage_id"]) for row in sheet.rows]


def judged_pairs(eval_dir: str | Path, reports_dir: str | Path) -> tuple[set[PairKey], dict[str, int], Findings]:
    """(query_id, chunk_id) pairs with a returned judgment row in pilot, round 1 and round 2 (E-10), the rows each
    annotator already carries (round 1 + round 2, for cumulative balancing), and blocking findings.

    A returned sheet is required for every annotator with a drafted pilot/round-1 sheet: a missing one would
    silently look like "nothing judged". Returned round-2 sheets are included so repeated calls never re-draft.
    Raises LabelingStageError when there are no returned pilot/round-1 sheets at all.
    """
    findings = Findings()
    pairs: set[PairKey] = set()
    loads = dict.fromkeys(ANNOTATORS, 0)
    found = False
    for stage in ("pilot", "round1", "round2"):
        returned, strays = stage_files(raw_dir(eval_dir, stage))
        findings.warnings.extend(strays)
        if stage != "round2":
            for annotator in drafted_annotators(reports_dir, stage):
                if annotator not in returned:
                    findings.error(raw_path(eval_dir, stage, annotator), "returned sheet missing: needed to know which passages are judged")
            found = found or bool(returned)
        for annotator, path in returned.items():
            rows = _pairs_of(path, findings)
            pairs.update(rows)
            if stage != "pilot":
                loads[annotator] += len(rows)
    if not found:
        raise LabelingStageError("pooling", f"no returned pilot/round1 sheets under {Path(eval_dir) / 'labeling' / 'raw'}; save them first")
    return pairs, loads, findings


def pilot_ready(eval_dir: str | Path, reports_dir: str | Path) -> Findings:
    """Round 1 may only be drafted once the pilot is drafted and every returned pilot sheet is in."""
    findings = Findings()
    drafted = drafted_annotators(reports_dir, "pilot")
    if not drafted:
        findings.error(drafted_dir(reports_dir, "pilot"), "no pilot has been drafted: run `pilot` and pass the gate before round 1")
    returned, _ = stage_files(raw_dir(eval_dir, "pilot"))
    for annotator in drafted:
        if annotator not in returned:
            findings.error(raw_path(eval_dir, "pilot", annotator), "returned pilot sheet missing: round 1 is drafted only after the pilot is back and passed")
    return findings


def pilot_query_ids(eval_dir: str | Path, reports_dir: str | Path) -> set[str]:
    """Questions used in the pilot: query ids in the pilot drafts and returned pilot sheets (excluded from round 1)."""
    ids: set[str] = set()
    for directory in (drafted_dir(reports_dir, "pilot"), raw_dir(eval_dir, "pilot")):
        for path in stage_files(directory)[0].values():
            sheet, _ = read_checked(path, JUDGMENT_COLUMNS)
            if sheet is not None:
                ids.update(row.values["query_id"] for row in sheet.rows)
    return ids


def round1_query_ids(reports_dir: str | Path) -> set[str]:
    """Question ids already drafted into round-1 sheets (they can no longer become pilot questions)."""
    ids: set[str] = set()
    for path in stage_files(drafted_dir(reports_dir, "round1"))[0].values():
        sheet, _ = read_checked(path, JUDGMENT_COLUMNS)
        if sheet is not None:
            ids.update(row.values["query_id"] for row in sheet.rows)
    return ids


def draft_round(
    candidates: Sequence[Question],
    pools: Mapping[str, Sequence[Passage]],
    purpose: str,
    base_loads: Mapping[str, int] | None = None,
) -> tuple[dict[str, list[dict[str, str]]], Assignment]:
    """Assign `candidates` (with non-empty pools) and draft one sheet per annotator (I-4)."""
    questions = {q.query_id: q for q in candidates if pools.get(q.query_id)}
    assignment = assign(
        {qid: len(pools[qid]) for qid in questions}, {qid: q.author for qid, q in questions.items()}, purpose, base_loads
    )
    sheets = {a: draft_judgment_sheet(assignment.questions_of(a), questions, pools) for a in ANNOTATORS}
    return sheets, assignment


# --- unanswerable check sheets (I-6) -----------------------------------------------------------------


def previous_replacement_ids(reports_dir: str | Path) -> dict[str, list[str]]:
    """Question ids already drafted into each author's `replacements` sheet."""
    out: dict[str, list[str]] = {}
    for annotator, path in stage_files(drafted_dir(reports_dir, "unanswerable", REPLACEMENTS))[0].items():
        sheet, _ = read_checked(path, UNANSWERABLE_COLUMNS)
        if sheet is not None:
            out[annotator] = [row.values["query_id"] for row in sheet.rows]
    return out


def draft_unanswerable(
    unanswerable: Sequence[Question],
    pools: Mapping[str, Sequence[Passage]],
    only: Sequence[str] | None = None,
    previous: Mapping[str, Sequence[str]] | None = None,
) -> dict[str, list[dict[str, str]]]:
    """Per annotator: their own original unanswerable questions + 15% of others' (seeded), top-10 E3 passages.

    Replacement questions (`P<n>-U21+`) are never in the full sheet. With `only`, each author's sheet holds
    those ids plus the replacement ids already drafted for them (`previous`), and no double-check rows.
    """
    by_id = {q.query_id: q for q in unanswerable}
    originals = [q for q in sorted(unanswerable, key=lambda q: q.query_id) if parse_query_id(q.query_id)[2] <= N_UNANSWERABLE]  # type: ignore[index]

    def row(q: Question) -> dict[str, str]:
        passages = pools[q.query_id]
        return {
            "query_id": q.query_id,
            "question": q.text,
            "passages": format_passages(passages, [str(i) for i in range(1, len(passages) + 1)]),
        }

    sheets: dict[str, list[dict[str, str]]] = {}
    for annotator in ANNOTATORS:
        if only is None:
            chosen = [q for q in originals if q.author == annotator]
            others = [q for q in originals if q.author != annotator]
            chosen += seeded("unanswerable-double", annotator).sample(others, min(len(others), share_count(len(chosen))))
        else:
            wanted = set(only) | set((previous or {}).get(annotator, ()))
            chosen = [q for q in by_id.values() if q.author == annotator and q.query_id in wanted]
        sheets[annotator] = [row(q) for q in sorted(chosen, key=lambda q: q.query_id)]
    return sheets


# --- gold sheets (I-7) ---------------------------------------------------------------------------


def passage_index(judgments: Sequence[Judgment]) -> dict[str, Passage]:
    """Display info per chunk id, taken from the returned judgment rows."""
    out: dict[str, Passage] = {}
    for j in judgments:
        out.setdefault(j.chunk_id, Passage(j.chunk_id, j.paper_title, j.section, int(j.year) if j.year.isdigit() else 0, j.passage))
    return out


def two_labeled_by_query(resolution: Resolution) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for (qid, cid), resolved in sorted(resolution.resolved.items()):
        if resolved.label == 2:
            out.setdefault(qid, []).append(cid)
    return out


def draft_gold(
    questions: Sequence[Question], resolution: Resolution
) -> dict[str, list[dict[str, str]]]:
    """Per author: their answerable questions with the 2-labeled passages and a pre-filled `gold_passages`."""
    info = passage_index(resolution.judgments)
    twos = two_labeled_by_query(resolution)
    sheets: dict[str, list[dict[str, str]]] = {a: [] for a in ANNOTATORS}
    for q in sorted(questions, key=lambda q: q.query_id):
        if not q.answerable:
            continue
        chunk_ids = twos.get(q.query_id, [])
        sheets[q.author].append(
            {
                "query_id": q.query_id,
                "question": q.text,
                "passages": format_passages([info[c] for c in chunk_ids], chunk_ids),
                "gold_passages": " ".join(chunk_ids),
            }
        )
    return sheets


def draft_gold_review(
    questions: Sequence[Question], gold_rows: Sequence[GoldRow], resolution: Resolution
) -> dict[str, list[dict[str, str]]]:
    """Per annotator: `round(0.15 * own answerable)` seeded answers from other authors (NO_EVIDENCE excluded)."""
    info = passage_index(resolution.judgments)
    by_id = {q.query_id: q for q in questions if q.answerable}
    reviewable = [g for g in sorted(gold_rows, key=lambda g: g.query_id) if g.query_id in by_id and g.gold_answer.upper() != NO_EVIDENCE]
    sheets: dict[str, list[dict[str, str]]] = {}
    for annotator in ANNOTATORS:
        n_own = sum(1 for q in by_id.values() if q.author == annotator)
        pool = [g for g in reviewable if by_id[g.query_id].author != annotator]
        picked = seeded("gold-review", annotator).sample(pool, min(len(pool), share_count(n_own)))
        rows = []
        for g in sorted(picked, key=lambda g: g.query_id):
            cited = [c for c in g.chunk_ids if c in info]
            rows.append(
                {
                    "query_id": g.query_id,
                    "question": by_id[g.query_id].text,
                    "passages": format_passages([info[c] for c in cited], cited),
                    "gold_answer": g.gold_answer,
                }
            )
        sheets[annotator] = rows
    return sheets
