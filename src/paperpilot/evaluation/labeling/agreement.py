"""Inter-annotator agreement: raw agreement, Cohen's kappa (stdlib), binary agreement, gate verdict.

Story 1.6 · CAP-6 · AD-1 · AD-5 (the JSON report is class 3 under `reports/labeling/`). Covers I-5 and E-5.
Gate: mean pairwise raw agreement >= 0.80 (kappa is reported, never gated); the pooled (micro) raw agreement over
all double-labeled rows and each pair's n are reported next to it, pairs with n < 10 are marked small. Cohen's
kappa is None (shown "n/a") when chance agreement is 1 (a constant label). Pairs with no overlapping rows are
skipped with a warning (E-5). The `gold-review` stage compares each reviewer with the answer's author, whose
own label is implicitly `agree`.
"""

from __future__ import annotations

import itertools
import json
import logging
from collections import Counter
from collections.abc import Hashable, Sequence
from dataclasses import dataclass
from pathlib import Path

from paperpilot.core.errors import LabelingStageError
from paperpilot.evaluation.labeling import AGREEMENT_GATE, ANNOTATORS, JUDGMENT_STAGES, SMALL_PAIR_ROWS
from paperpilot.evaluation.labeling.sheets import (
    Findings,
    atomic_write,
    load_answer_checks,
    load_judgments,
    load_review_rows,
    parse_query_id,
)

logger = logging.getLogger(__name__)

AGREEMENT_STAGES: tuple[str, ...] = (*JUDGMENT_STAGES, "unanswerable", "gold-review")

LabelMap = dict[str, dict[Hashable, Hashable]]


@dataclass(frozen=True)
class PairStats:
    a: str
    b: str
    n: int
    agree: int
    raw: float
    kappa: float | None
    binary: float | None

    @property
    def small(self) -> bool:
        return self.n < SMALL_PAIR_ROWS


@dataclass(frozen=True)
class AgreementReport:
    stage: str
    pairs: tuple[PairStats, ...]
    skipped: tuple[tuple[str, str], ...]
    mean_raw: float | None
    mean_kappa: float | None
    mean_binary: float | None
    disagreements: dict[str, int]
    verdict: str
    pooled_raw: float | None = None
    note: str = ""
    gate: float = AGREEMENT_GATE


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float | None:
    """Cohen's kappa for two equal-length label sequences; None when chance agreement is 1 (a constant label)."""
    if len(a) != len(b) or not a:
        raise ValueError(f"kappa needs two equal-length non-empty sequences, got {len(a)} and {len(b)}")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b)) / n
    count_a, count_b = Counter(a), Counter(b)
    expected = sum(count_a[label] * count_b[label] for label in count_a) / (n * n)
    if expected == 1.0:
        return None
    return (observed - expected) / (1.0 - expected)


def compute_agreement(stage: str, labels: LabelMap, *, binary: bool) -> tuple[AgreementReport, list[str]]:
    """Pairwise stats over `labels[annotator][key] -> label`; returns the report and warnings (E-5)."""
    pairs: list[PairStats] = []
    skipped: list[tuple[str, str]] = []
    warnings: list[str] = []
    disagreements = dict.fromkeys(ANNOTATORS, 0)
    for a, b in itertools.combinations(ANNOTATORS, 2):
        shared = sorted(set(labels.get(a, {})) & set(labels.get(b, {})), key=repr)
        if not shared:
            skipped.append((a, b))
            warnings.append(f"pair {a}-{b} has no rows labeled by both; skipped")
            continue
        la = [labels[a][key] for key in shared]
        lb = [labels[b][key] for key in shared]
        agree = sum(x == y for x, y in zip(la, lb))
        for x, y in zip(la, lb):
            if x != y:
                disagreements[a] += 1
                disagreements[b] += 1
        binary_raw = None
        if binary:
            binary_raw = sum((x >= 1) == (y >= 1) for x, y in zip(la, lb)) / len(shared)  # type: ignore[operator]
        pairs.append(PairStats(a, b, len(shared), agree, agree / len(shared), cohen_kappa(la, lb), binary_raw))
    mean_raw = _mean([p.raw for p in pairs])
    total_n = sum(p.n for p in pairs)
    report = AgreementReport(
        stage=stage,
        pairs=tuple(pairs),
        skipped=tuple(skipped),
        mean_raw=mean_raw,
        mean_kappa=_mean([p.kappa for p in pairs if p.kappa is not None]),
        mean_binary=_mean([p.binary for p in pairs if p.binary is not None]) if binary else None,
        disagreements=disagreements,
        verdict="NO DATA" if mean_raw is None else ("PASS" if mean_raw >= AGREEMENT_GATE else "FAIL"),
        pooled_raw=sum(p.agree for p in pairs) / total_n if total_n else None,
        note="kappa not meaningful: the answer's author is always `agree`" if stage == "gold-review" else "",
    )
    return report, warnings


def _mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def stage_labels(eval_dir: str | Path, reports_dir: str | Path, stage: str) -> tuple[LabelMap, bool, Findings]:
    """Validated per-annotator labels of `stage`; `binary` says whether label >= 1 agreement applies."""
    if stage not in AGREEMENT_STAGES:
        raise LabelingStageError("agreement", f"unknown stage {stage!r}; choose one of {list(AGREEMENT_STAGES)}")
    labels: LabelMap = {annotator: {} for annotator in ANNOTATORS}
    if stage in JUDGMENT_STAGES:
        judgments, findings = load_judgments(eval_dir, reports_dir, stage)
        for j in judgments:
            labels[j.annotator][(j.query_id, j.chunk_id)] = j.label
        return labels, True, findings
    if stage == "unanswerable":
        checks, findings = load_answer_checks(eval_dir, reports_dir)
        for c in checks:
            labels[c.annotator][c.query_id] = c.answer
        return labels, False, findings
    reviews, findings = load_review_rows(eval_dir, reports_dir)
    for r in reviews:
        labels[r.annotator][r.query_id] = r.review
        parsed = parse_query_id(r.query_id)
        if parsed is not None and parsed[0] != r.annotator:
            labels[parsed[0]][r.query_id] = "agree"  # the author stands behind their own answer
    return labels, False, findings


def report_path(reports_dir: str | Path, stage: str) -> Path:
    return Path(reports_dir) / "labeling" / f"agreement_{stage}.json"


def write_report(reports_dir: str | Path, report: AgreementReport) -> Path:
    payload = {
        "stage": report.stage,
        "gate": report.gate,
        "verdict": report.verdict,
        "mean_raw_agreement": report.mean_raw,
        "pooled_raw_agreement": report.pooled_raw,
        "mean_kappa": report.mean_kappa,
        "mean_binary_agreement": report.mean_binary,
        "pairs": [
            {"a": p.a, "b": p.b, "n": p.n, "small": p.small, "agree": p.agree, "raw_agreement": p.raw, "kappa": p.kappa, "binary_agreement": p.binary}
            for p in report.pairs
        ],
        "skipped_pairs": [list(pair) for pair in report.skipped],
        "disagreements_by_annotator": report.disagreements,
        "note": report.note,
    }
    path = report_path(reports_dir, report.stage)
    atomic_write(path, (json.dumps(payload, indent=2) + "\n").encode("utf-8"))
    return path


def format_report(report: AgreementReport) -> str:
    """Human table + gate verdict (the gate is the mean pairwise raw agreement; pooled is printed next to it)."""

    def num(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.3f}"

    lines = [f"agreement stage={report.stage} (gate: mean pairwise raw agreement >= {report.gate:.2f})"]
    lines.append(f"{'pair':<7}{'rows':>6}{'raw':>8}{'kappa':>8}{'binary':>8}")
    for p in report.pairs:
        flag = "  small (n < 10)" if p.small else ""
        lines.append(f"{p.a + '-' + p.b:<7}{p.n:>6}{num(p.raw):>8}{num(p.kappa):>8}{num(p.binary) if p.binary is not None else '-':>8}{flag}")
    binary = "-" if report.mean_binary is None else num(report.mean_binary)
    lines.append(f"{'mean':<7}{'':>6}{num(report.mean_raw):>8}{num(report.mean_kappa):>8}{binary:>8}")
    lines.append(f"pooled raw agreement over all double-labeled rows: {num(report.pooled_raw)}")
    if report.note:
        lines.append(f"note: {report.note}")
    lines.append("disagreements per annotator: " + " ".join(f"{a}={n}" for a, n in report.disagreements.items()))
    lines.append(f"gate verdict: {report.verdict} (mean pairwise raw {num(report.mean_raw)}; pooled {num(report.pooled_raw)})")
    return "\n".join(lines)
