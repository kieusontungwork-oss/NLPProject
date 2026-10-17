"""Sheet schemas, CSV I/O, round-trip checks, question checks, and the kickoff catalog.

Story 1.6 · CAP-6 · AD-1 · AD-5. Covers I-1, I-2, E-1, E-2, E-3. Sheets are read and written as `utf-8-sig` CSV
(Excel-friendly). Row numbers in messages are spreadsheet rows (header = row 1). Returned human sheets (class 1,
`<eval-dir>/labeling/raw/<stage>/P<n>.csv`) are only ever read here; drafted sheets (class 3,
`<reports-dir>/pooling/<stage>/P<n>.csv`) are written atomically.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

from paperpilot.core.errors import LabelingStageError
from paperpilot.core.ids import normalize
from paperpilot.kb.metadata import bare_metadata_id
from paperpilot.evaluation.labeling import (
    ANNOTATORS,
    N_ANSWERABLE,
    N_UNANSWERABLE,
    STAGES,
)
from paperpilot.evaluation.labeling.subfields import (
    QUESTION_SUBFIELDS,
    QUESTION_TYPES,
    SUBFIELD_QUOTA,
    TYPE_QUOTA,
    subfield_of,
)
from paperpilot.retrieval.tokenize import tokenize

logger = logging.getLogger(__name__)

CSV_ENCODING = "utf-8-sig"
DUPLICATE_JACCARD = 0.8
ABSTRACT_START_CHARS = 300

QUESTION_COLUMNS: tuple[str, ...] = ("query_id", "question", "type", "subfield", "source_paper", "comment")
JUDGMENT_COLUMNS: tuple[str, ...] = (
    "row_id",
    "query_id",
    "question",
    "passage_id",
    "paper_title",
    "section",
    "year",
    "passage",
    "relevance",
    "comment",
)
UNANSWERABLE_COLUMNS: tuple[str, ...] = (
    "query_id",
    "question",
    "passages",
    "answered_by_library",
    "new_question",
    "comment",
)
GOLD_COLUMNS: tuple[str, ...] = ("query_id", "question", "passages", "gold_passages", "gold_answer", "comment")
REVIEW_COLUMNS: tuple[str, ...] = ("query_id", "question", "passages", "gold_answer", "review", "reason")
CATALOG_COLUMNS: tuple[str, ...] = ("arxiv_id", "year", "subfield", "categories", "title", "abstract_start", "link")
ADJUDICATION_COLUMNS: tuple[str, ...] = ("query_id", "chunk_id", "final_relevance", "adjudicator", "reason")

STAGE_COLUMNS: dict[str, tuple[str, ...]] = {
    "questions": QUESTION_COLUMNS,
    "pilot": JUDGMENT_COLUMNS,
    "round1": JUDGMENT_COLUMNS,
    "round2": JUDGMENT_COLUMNS,
    "unanswerable": UNANSWERABLE_COLUMNS,
    "gold": GOLD_COLUMNS,
    "gold-review": REVIEW_COLUMNS,
}
# Columns that identify a row of a returned sheet; compared against the drafted sheet (E-3).
STAGE_KEYS: dict[str, tuple[str, ...]] = {
    "questions": ("query_id",),
    "pilot": ("row_id", "query_id", "passage_id"),
    "round1": ("row_id", "query_id", "passage_id"),
    "round2": ("row_id", "query_id", "passage_id"),
    "unanswerable": ("query_id",),
    "gold": ("query_id",),
    "gold-review": ("query_id",),
}

# Columns a returned row must keep unchanged (compared after whitespace normalization with the drafted row).
STAGE_FIXED: dict[str, tuple[str, ...]] = {
    "questions": (),
    "pilot": ("question", "paper_title", "section", "year", "passage"),
    "round1": ("question", "paper_title", "section", "year", "passage"),
    "round2": ("question", "paper_title", "section", "year", "passage"),
    "unanswerable": ("question", "passages"),
    "gold": ("question", "passages"),
    "gold-review": ("question", "passages", "gold_answer"),
}

ALLOWED_RELEVANCE = ("0", "1", "2")
ALLOWED_YES_NO = ("yes", "no")
ALLOWED_REVIEW = ("agree", "disagree")

_QUERY_ID = re.compile(r"^(P[1-9])-(?:(\d{3})|U(\d{2,}))$")
_BAD_YEAR = re.compile(r"\b20(?:1[89]|2\d)\b")
_NUMERIC_LOOKING = re.compile(r"^[0-9.eE+-]+$")


# --- findings -------------------------------------------------------------------------------


@dataclass(frozen=True)
class Issue:
    """One blocking problem, located as `file:row` (or just `file`)."""

    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


@dataclass
class Findings:
    """Accumulator for a check: blocking `errors`, non-blocking `warnings`, and `info` lines."""

    errors: list[Issue] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def error(self, where: object, message: str) -> None:
        self.errors.append(Issue(str(where), message))

    @property
    def ok(self) -> bool:
        return not self.errors

    def extend(self, other: Findings) -> None:
        self.errors.extend(other.errors)
        self.warnings.extend(other.warnings)
        self.info.extend(other.info)


# --- paths ----------------------------------------------------------------------------------


REPLACEMENTS = "replacements"  # sub-folder of `unanswerable` holding replacement-question check sheets


def raw_dir(eval_dir: str | Path, stage: str, subdir: str = "") -> Path:
    return Path(eval_dir) / "labeling" / "raw" / stage / subdir


def raw_path(eval_dir: str | Path, stage: str, annotator: str, subdir: str = "") -> Path:
    return raw_dir(eval_dir, stage, subdir) / f"{annotator}.csv"


def drafted_dir(reports_dir: str | Path, stage: str, subdir: str = "") -> Path:
    return Path(reports_dir) / "pooling" / stage / subdir


def drafted_path(reports_dir: str | Path, stage: str, annotator: str, subdir: str = "") -> Path:
    return drafted_dir(reports_dir, stage, subdir) / f"{annotator}.csv"


def stage_files(directory: Path) -> tuple[dict[str, Path], list[str]]:
    """The one file-discovery helper: `P1.csv`..`P5.csv` in `directory`; any other `*.csv` is warned about and ignored."""
    files: dict[str, Path] = {}
    strays: list[str] = []
    if directory.is_dir():
        for path in sorted(directory.glob("*.csv")):
            if path.stem in ANNOTATORS and path.name == f"{path.stem}.csv":
                files[path.stem] = path
            else:
                strays.append(f"ignored {path}: stage folders only read {ANNOTATORS[0]}.csv .. {ANNOTATORS[-1]}.csv")
    return files, strays


def returned_annotators(eval_dir: str | Path, stage: str, subdir: str = "") -> tuple[str, ...]:
    return tuple(stage_files(raw_dir(eval_dir, stage, subdir))[0])


def drafted_annotators(reports_dir: str | Path, stage: str, subdir: str = "") -> tuple[str, ...]:
    return tuple(stage_files(drafted_dir(reports_dir, stage, subdir))[0])


def adjudication_path(eval_dir: str | Path) -> Path:
    return Path(eval_dir) / "labeling" / "adjudication.csv"


# --- CSV I/O --------------------------------------------------------------------------------


@dataclass(frozen=True)
class SheetRow:
    number: int
    values: dict[str, str]


@dataclass(frozen=True)
class Sheet:
    path: Path
    header: tuple[str, ...]
    rows: tuple[SheetRow, ...]

    def where(self, row: SheetRow) -> str:
        return f"{self.path}:{row.number}"


def atomic_write(path: str | Path, data: bytes) -> None:
    """Write `data` to a temp sibling then `os.replace` it in (no half-written files)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    os.replace(tmp, path)


def write_csv(path: str | Path, columns: tuple[str, ...], rows: list[dict[str, str]]) -> None:
    """Write a `utf-8-sig` CSV, byte-deterministic for equal input (E-9)."""
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\n")
    writer.writerow(columns)
    for row in rows:
        writer.writerow([row.get(column, "") for column in columns])
    atomic_write(path, buffer.getvalue().encode(CSV_ENCODING))


def read_sheet(path: str | Path) -> Sheet:
    """Read a CSV into a Sheet; wholly blank rows are skipped, cells are stripped. Raises LabelingStageError."""
    path = Path(path)
    try:
        with path.open("r", encoding=CSV_ENCODING, newline="") as handle:
            table = list(csv.reader(handle))
    except FileNotFoundError as exc:
        raise LabelingStageError("sheets", f"sheet not found: {path}") from exc
    except (OSError, UnicodeDecodeError, csv.Error) as exc:
        raise LabelingStageError("sheets", f"cannot read {path} as UTF-8 CSV: {exc}") from exc
    if not table:
        raise LabelingStageError("sheets", f"{path} is empty (no header row)")
    # Drop trailing columns whose header and every cell are blank (spreadsheet exports add them).
    last = max((k for line in table for k, cell in enumerate(line) if cell.strip()), default=-1)
    width = max(last + 1, 0)
    header = tuple(cell.strip() for cell in table[0][:width])
    rows: list[SheetRow] = []
    for number, cells in enumerate(table[1:], start=2):
        if not any(cell.strip() for cell in cells):
            continue
        padded = [cell.strip() for cell in cells[:width]] + [""] * max(0, width - len(cells))
        rows.append(SheetRow(number, dict(zip(header, padded))))
    return Sheet(path, header, tuple(rows))


def read_checked(path: Path, expected: tuple[str, ...]) -> tuple[Sheet | None, list[Issue]]:
    """Read a sheet and check its header against `expected` (E-2); returns (None, issues) if unusable."""
    try:
        sheet = read_sheet(path)
    except LabelingStageError as exc:
        return None, [Issue(str(path), str(exc))]
    issues = check_columns(sheet, expected)
    if issues:
        return None, issues
    return sheet, []


def check_columns(sheet: Sheet, expected: tuple[str, ...]) -> list[Issue]:
    """E-2: renamed/missing/extra/reordered columns, named by file and the column diff."""
    if sheet.header == expected:
        return []
    missing = [c for c in expected if c not in sheet.header]
    extra = [c for c in sheet.header if c not in expected]
    if missing or extra:
        return [Issue(str(sheet.path), f"column mismatch: missing {missing}, unexpected {extra}; expected {list(expected)}")]
    return [Issue(str(sheet.path), f"columns are reordered; expected {list(expected)}, found {list(sheet.header)}")]


def _key(row: SheetRow, key_columns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(row.values.get(column, "") for column in key_columns)


def _preview(items: list[str], limit: int = 10) -> str:
    shown = ", ".join(items[:limit])
    return shown + (f", ... and {len(items) - limit} more" if len(items) > limit else "")


def _numeric_hint(row: SheetRow, key_columns: tuple[str, ...]) -> str:
    for column in ("passage_id", "query_id"):
        if column in key_columns and _NUMERIC_LOOKING.match(row.values.get(column, "")):
            return (
                f" (the {column} looks like a number: Google Sheets probably converted this id to a number "
                "— re-import with 'Convert text to numbers' unticked)"
            )
    return ""


def check_roundtrip(
    returned: Sheet, drafted: Sheet, key_columns: tuple[str, ...], fixed_columns: tuple[str, ...] = ()
) -> list[Issue]:
    """E-3: the returned row set must equal the drafted one (rows deleted, added, `passage_id` edited), and each
    row's fixed (non-fill) columns must be unchanged after whitespace normalization (a sorted single column)."""
    issues: list[Issue] = []
    drafted_by_key = {_key(row, key_columns): row for row in drafted.rows}
    seen: dict[tuple[str, ...], int] = {}
    for row in returned.rows:
        key = _key(row, key_columns)
        if key in seen:
            issues.append(Issue(returned.where(row), f"duplicate row {list(key)} (first at row {seen[key]})"))
            continue
        seen[key] = row.number
        original = drafted_by_key.get(key)
        if original is None:
            issues.append(
                Issue(returned.where(row), f"row {list(key)} is not in the drafted sheet (added or id edited){_numeric_hint(row, key_columns)}")
            )
            continue
        changed = [c for c in fixed_columns if normalize(row.values.get(c, "")) != normalize(original.values.get(c, ""))]
        if changed:
            issues.append(
                Issue(returned.where(row), f"the row content changed ({', '.join(changed)} differs from the drafted sheet) — was a single column sorted?")
            )
    missing = [str(list(_key(row, key_columns))) for row in drafted.rows if _key(row, key_columns) not in seen]
    if missing:
        issues.append(Issue(str(returned.path), f"{len(missing)} drafted row(s) missing: {_preview(missing)}"))
    return issues


def parse_relevance(value: str) -> int | None:
    """`0`/`1`/`2` -> int; anything else (blank, `1.5`, text) -> None (E-1)."""
    return int(value) if value in ALLOWED_RELEVANCE else None


# --- stage loading ----------------------------------------------------------------------------


def load_stage_sheets(
    eval_dir: str | Path,
    reports_dir: str | Path | None,
    stage: str,
    *,
    require_all: bool = False,
    subdir: str = "",
) -> tuple[dict[str, Sheet], Findings]:
    """Read every returned sheet of `stage`, checking columns (E-2) and rows + fixed content against the drafted sheet (E-3).

    Expected annotators are those with a drafted sheet (all of P1-P5 for `questions`). A missing returned sheet is
    an error with `require_all`, else a warning (info only when the stage has no returned sheets at all).
    `subdir` selects a sub-folder of the stage (the unanswerable `replacements`).
    """
    if stage not in STAGES:
        raise LabelingStageError("sheets", f"unknown stage {stage!r}; stages: {list(STAGES)}")
    findings = Findings()
    sheets: dict[str, Sheet] = {}
    expected_columns = STAGE_COLUMNS[stage]
    returned, strays = stage_files(raw_dir(eval_dir, stage, subdir))
    findings.warnings.extend(strays)
    if stage == "questions" or reports_dir is None:
        expected = ANNOTATORS
    else:
        expected = drafted_annotators(reports_dir, stage, subdir)
    for annotator, path in returned.items():
        sheet, issues = read_checked(path, expected_columns)
        findings.errors.extend(issues)
        if sheet is None:
            continue
        sheets[annotator] = sheet
        if stage == "questions":
            findings.errors.extend(check_question_ids(sheet, annotator))
            continue
        drafted = drafted_path(reports_dir, stage, annotator, subdir) if reports_dir is not None else None
        if drafted is None or not drafted.is_file():
            findings.error(
                path,
                f"no drafted sheet at {drafted} to compare against; regenerate it (drafting is deterministic) and re-run",
            )
            continue
        drafted_sheet, drafted_issues = read_checked(drafted, expected_columns)
        if drafted_sheet is None:
            findings.errors.extend(drafted_issues)
            continue
        findings.errors.extend(check_roundtrip(sheet, drafted_sheet, STAGE_KEYS[stage], STAGE_FIXED[stage]))
    missing = [a for a in expected if a not in returned]
    where = raw_dir(eval_dir, stage, subdir)
    if not returned:
        findings.info.append(f"stage {stage!r}: no returned sheets in {where} (skipped)")
        if require_all:
            findings.error(where, f"no returned sheets for required stage {stage!r}")
    else:
        for annotator in missing:
            path = raw_path(eval_dir, stage, annotator, subdir)
            if require_all:
                findings.error(path, "returned sheet missing")
            else:
                findings.warnings.append(f"returned sheet missing: {path}")
    return sheets, findings


# --- questions --------------------------------------------------------------------------------


@dataclass(frozen=True)
class Question:
    query_id: str
    text: str
    type: str
    subfield: str
    source_paper: str
    author: str
    answerable: bool


def parse_query_id(query_id: str) -> tuple[str, bool, int] | None:
    """`P3-007` -> ("P3", True, 7); `P3-U12` -> ("P3", False, 12); anything else -> None."""
    match = _QUERY_ID.match(query_id)
    if match is None:
        return None
    author, answerable, unanswerable = match.groups()
    return (author, True, int(answerable)) if answerable else (author, False, int(unanswerable))


def expected_question_ids(annotator: str) -> list[str]:
    return [f"{annotator}-{i:03d}" for i in range(1, N_ANSWERABLE + 1)] + [
        f"{annotator}-U{i:02d}" for i in range(1, N_UNANSWERABLE + 1)
    ]


def check_question_ids(sheet: Sheet, annotator: str) -> list[Issue]:
    """All 70 ids present; unknown ids rejected; replacement ids `P<n>-U21+` are allowed extras."""
    issues: list[Issue] = []
    expected = set(expected_question_ids(annotator))
    seen: dict[str, int] = {}
    for row in sheet.rows:
        qid = row.values.get("query_id", "")
        parsed = parse_query_id(qid)
        is_replacement = parsed is not None and parsed[0] == annotator and not parsed[1] and parsed[2] > N_UNANSWERABLE
        if qid not in expected and not is_replacement:
            issues.append(Issue(sheet.where(row), f"unexpected query_id {qid!r} (sheet {annotator} holds {annotator}-001..050 and {annotator}-U01..U20)"))
        elif qid in seen:
            issues.append(Issue(sheet.where(row), f"duplicate query_id {qid!r} (first at row {seen[qid]})"))
        seen.setdefault(qid, row.number)
    missing = sorted(expected - set(seen))
    if missing:
        issues.append(Issue(str(sheet.path), f"{len(missing)} query id(s) missing: {_preview(missing)}"))
    return issues


def read_paper_ids(kb_dir: str | Path) -> set[str]:
    """arXiv ids in `papers.jsonl`, streamed one line at a time."""
    path = Path(kb_dir) / "papers.jsonl"
    if not path.is_file():
        raise LabelingStageError("sheets", f"paper metadata not found: {path}; run `make kb`")
    ids: set[str] = set()
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                ids.add(json.loads(line)["arxiv_id"])
            except (ValueError, KeyError, TypeError) as exc:
                raise LabelingStageError("sheets", f"{path}:{lineno}: bad paper record: {exc!r}") from exc
    return ids


def normalize_arxiv_id(value: str) -> str:
    """Trim, drop a leading `arXiv:` (local) and a trailing version (`kb.metadata.bare_metadata_id`) from a typed id."""
    value = value.strip()
    if value.lower().startswith("arxiv:"):
        value = value[len("arxiv:") :]
    return bare_metadata_id(value.strip())


def load_questions(eval_dir: str | Path) -> list[Question]:
    """Every non-empty question of `raw/questions/P*.csv`, sorted by query_id. Raises on a missing/bad sheet."""
    questions: list[Question] = []
    for annotator in ANNOTATORS:
        path = raw_path(eval_dir, "questions", annotator)
        sheet, issues = read_checked(path, QUESTION_COLUMNS)
        if sheet is None:
            detail = "; ".join(str(issue) for issue in issues) or f"cannot read {path}"
            raise LabelingStageError("sheets", f"{detail}; run `check-questions` first")
        for row in sheet.rows:
            parsed = parse_query_id(row.values["query_id"])
            text = row.values["question"]
            if parsed is None or not text:
                continue
            questions.append(
                Question(
                    query_id=row.values["query_id"],
                    text=text,
                    type=row.values["type"],
                    subfield=row.values["subfield"],
                    source_paper=normalize_arxiv_id(row.values["source_paper"]),
                    author=parsed[0],
                    answerable=parsed[1],
                )
            )
    return sorted(questions, key=lambda q: q.query_id)


def check_questions(eval_dir: str | Path, kb_dir: str | Path) -> Findings:
    """I-2: per-person report of missing/invalid fields, quota deltas, duplicates, and 2018+ years."""
    sheets, findings = load_stage_sheets(eval_dir, None, "questions", require_all=True)
    paper_ids = read_paper_ids(kb_dir)
    seen_questions: list[tuple[str, str, frozenset[str]]] = []
    for annotator, sheet in sheets.items():
        type_counts = dict.fromkeys(QUESTION_TYPES, 0)
        subfield_counts = dict.fromkeys(QUESTION_SUBFIELDS, 0)
        n_answerable = n_unanswerable = 0
        for row in sheet.rows:
            values = row.values
            parsed = parse_query_id(values["query_id"])
            if parsed is None or parsed[0] != annotator:
                continue
            where = sheet.where(row)
            text = values["question"]
            if not text:
                findings.error(where, f"{values['query_id']}: question is empty")
            else:
                seen_questions.append((values["query_id"], where, frozenset(tokenize(text))))
            if not parsed[1]:
                n_unanswerable += 1
                continue
            n_answerable += 1
            if text and not text.endswith("?"):
                findings.error(where, f"{values['query_id']}: question must end with '?'")
            if text and _BAD_YEAR.search(text):
                findings.error(where, f"{values['query_id']}: answerable question mentions a 2018+ year")
            if not values["type"]:
                findings.error(where, f"{values['query_id']}: type is missing")
            elif values["type"] not in QUESTION_TYPES:
                findings.error(where, f"{values['query_id']}: type {values['type']!r} not in {list(QUESTION_TYPES)}")
            else:
                type_counts[values["type"]] += 1
            if not values["subfield"]:
                findings.error(where, f"{values['query_id']}: subfield is missing")
            elif values["subfield"] not in QUESTION_SUBFIELDS:
                findings.error(where, f"{values['query_id']}: subfield {values['subfield']!r} not in {list(QUESTION_SUBFIELDS)}")
            else:
                subfield_counts[values["subfield"]] += 1
            source = normalize_arxiv_id(values["source_paper"])
            if not source:
                findings.error(where, f"{values['query_id']}: source_paper is missing")
            elif source not in paper_ids:
                findings.warnings.append(f"{where}: source_paper {source!r} not found in papers.jsonl")
        findings.info.append(f"{annotator}: {n_answerable} answerable, {n_unanswerable} unanswerable questions")
        for name, quota in TYPE_QUOTA.items():
            if type_counts[name] != quota:
                findings.warnings.append(f"{annotator} quota: type {name!r} has {type_counts[name]}, expected {quota} ({type_counts[name] - quota:+d})")
        for name, quota in SUBFIELD_QUOTA.items():
            if subfield_counts[name] != quota:
                findings.warnings.append(f"{annotator} quota: subfield {name!r} has {subfield_counts[name]}, expected {quota} ({subfield_counts[name] - quota:+d})")
    seen_questions.sort()
    for i, (id_a, where_a, tokens_a) in enumerate(seen_questions):
        if not tokens_a:
            continue
        for id_b, where_b, tokens_b in seen_questions[i + 1 :]:
            if not tokens_b:
                continue
            jaccard = len(tokens_a & tokens_b) / len(tokens_a | tokens_b)
            if jaccard >= DUPLICATE_JACCARD:
                findings.error(where_b, f"duplicate of {id_a} ({where_a}): token Jaccard {jaccard:.2f} >= {DUPLICATE_JACCARD}")
    return findings


# --- catalog (I-1) ----------------------------------------------------------------------------


def strip_sentence_tags(text: str) -> str:
    """Remove the `<S>` / `</S>` conversion leftovers and collapse whitespace."""
    return normalize(text.replace("</S>", " ").replace("<S>", " "))


def write_catalog(kb_dir: str | Path, out_dir: str | Path) -> dict[str, int]:
    """Write papers_catalog.csv + questions_P1..P5.csv into `out_dir`; returns papers per subfield."""
    path = Path(kb_dir) / "papers.jsonl"
    if not path.is_file():
        raise LabelingStageError("catalog", f"paper metadata not found: {path}; run `make kb`")
    entries: list[tuple[str, int, str, str, str, str, str]] = []
    with path.open("r", encoding="utf-8") as handle:
        for lineno, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                paper = json.loads(line)
                categories = list(paper["categories"])
                entries.append(
                    (
                        subfield_of(categories),
                        int(paper["year"]),
                        paper["arxiv_id"],
                        " ".join(categories),
                        " ".join(str(paper["title"]).split()),
                        strip_sentence_tags(str(paper["abstract"]))[:ABSTRACT_START_CHARS],
                        paper["source_link"],
                    )
                )
            except (ValueError, KeyError, TypeError) as exc:
                raise LabelingStageError("catalog", f"{path}:{lineno}: bad paper record: {exc!r}") from exc
    entries.sort(key=lambda e: (e[0], -e[1], e[4].lower(), e[2]))
    counts: dict[str, int] = {}
    rows = []
    for subfield, year, arxiv_id, categories, title, abstract_start, link in entries:
        counts[subfield] = counts.get(subfield, 0) + 1
        rows.append(
            {
                "arxiv_id": arxiv_id,
                "year": str(year),
                "subfield": subfield,
                "categories": categories,
                "title": title,
                "abstract_start": abstract_start,
                "link": link,
            }
        )
    out_dir = Path(out_dir)
    write_csv(out_dir / "papers_catalog.csv", CATALOG_COLUMNS, rows)
    for annotator in ANNOTATORS:
        write_csv(
            out_dir / f"questions_{annotator}.csv",
            QUESTION_COLUMNS,
            [{"query_id": qid} for qid in expected_question_ids(annotator)],
        )
    return counts


# --- typed rows of the returned sheets ----------------------------------------------------------


@dataclass(frozen=True)
class Judgment:
    """One relevance label of one annotator for one (query, passage) pair."""

    stage: str
    annotator: str
    query_id: str
    chunk_id: str
    label: int
    paper_title: str
    section: str
    year: str
    passage: str
    where: str
    question: str = ""  # the question text shown on the returned sheet (drift check)


@dataclass(frozen=True)
class AnswerCheck:
    """One `answered_by_library` answer (E-7) for an unanswerable question."""

    annotator: str
    query_id: str
    answer: str
    new_question: str
    where: str


@dataclass(frozen=True)
class GoldRow:
    annotator: str
    query_id: str
    gold_answer: str
    chunk_ids: tuple[str, ...]
    where: str


@dataclass(frozen=True)
class ReviewRow:
    annotator: str
    query_id: str
    review: str
    reason: str
    where: str


def split_ids(value: str) -> tuple[str, ...]:
    """Chunk ids separated by spaces, commas or newlines."""
    return tuple(part for part in re.split(r"[\s,;]+", value) if part)


def load_judgments(
    eval_dir: str | Path, reports_dir: str | Path, stage: str, *, require_all: bool = False
) -> tuple[list[Judgment], Findings]:
    """Typed labels of a judgment stage (`pilot`/`round1`/`round2`); a bad relevance cell is an error (E-1)."""
    sheets, findings = load_stage_sheets(eval_dir, reports_dir, stage, require_all=require_all)
    judgments: list[Judgment] = []
    for annotator, sheet in sheets.items():
        for row in sheet.rows:
            values = row.values
            label = parse_relevance(values["relevance"])
            if label is None:
                findings.error(
                    sheet.where(row), f"relevance {values['relevance']!r} is not one of 0, 1, 2 (query {values['query_id']})"
                )
                continue
            judgments.append(
                Judgment(
                    stage=stage,
                    annotator=annotator,
                    query_id=values["query_id"],
                    chunk_id=values["passage_id"],
                    label=label,
                    paper_title=values["paper_title"],
                    section=values["section"],
                    year=values["year"],
                    passage=values["passage"],
                    where=sheet.where(row),
                    question=values["question"],
                )
            )
    return judgments, findings


def load_answer_checks(
    eval_dir: str | Path, reports_dir: str | Path, *, require_all: bool = False
) -> tuple[list[AnswerCheck], Findings]:
    """Answers from the main unanswerable sheets plus the `replacements/` sheets (never required)."""
    findings = Findings()
    checks: list[AnswerCheck] = []
    for subdir, needed in (("", require_all), (REPLACEMENTS, False)):
        sheets, sheet_findings = load_stage_sheets(eval_dir, reports_dir, "unanswerable", require_all=needed, subdir=subdir)
        if subdir and not sheets:
            sheet_findings.info.clear()  # replacements are optional: no noise when there are none
            for annotator in drafted_annotators(reports_dir, "unanswerable", subdir):
                sheet_findings.warnings.append(f"returned sheet missing: {raw_path(eval_dir, 'unanswerable', annotator, subdir)}")
        findings.extend(sheet_findings)
        for annotator, sheet in sheets.items():
            for row in sheet.rows:
                values = row.values
                answer = values["answered_by_library"].lower()
                if answer not in ALLOWED_YES_NO:
                    findings.error(sheet.where(row), f"answered_by_library {values['answered_by_library']!r} is not yes/no (query {values['query_id']})")
                    continue
                checks.append(AnswerCheck(annotator, values["query_id"], answer, values["new_question"], sheet.where(row)))
    return checks, findings


def load_gold_rows(
    eval_dir: str | Path, reports_dir: str | Path, *, require_all: bool = False
) -> tuple[list[GoldRow], Findings]:
    sheets, findings = load_stage_sheets(eval_dir, reports_dir, "gold", require_all=require_all)
    rows: list[GoldRow] = []
    for annotator, sheet in sheets.items():
        for row in sheet.rows:
            values = row.values
            if not values["gold_answer"]:
                findings.error(sheet.where(row), f"gold_answer is empty (query {values['query_id']}; write NO_EVIDENCE if none)")
                continue
            rows.append(GoldRow(annotator, values["query_id"], values["gold_answer"], split_ids(values["gold_passages"]), sheet.where(row)))
    return rows, findings


def load_review_rows(
    eval_dir: str | Path, reports_dir: str | Path, *, require_all: bool = False
) -> tuple[list[ReviewRow], Findings]:
    sheets, findings = load_stage_sheets(eval_dir, reports_dir, "gold-review", require_all=require_all)
    rows: list[ReviewRow] = []
    for annotator, sheet in sheets.items():
        for row in sheet.rows:
            values = row.values
            review = values["review"].lower()
            if review not in ALLOWED_REVIEW:
                findings.error(sheet.where(row), f"review {values['review']!r} is not agree/disagree (query {values['query_id']})")
                continue
            rows.append(ReviewRow(annotator, values["query_id"], review, values["reason"], sheet.where(row)))
    return rows, findings
