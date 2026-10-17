"""Labeling sprint tooling: drafts the human sheets, checks returned sheets, measures agreement, merges labels.

Story 1.6 · CAP-6 · AD-1 (driver; retrieval only through `paperpilot.retrieval.Retriever`) · AD-2 (chunk ids are
only read, never minted) · AD-5 (drafted sheets are class 3 under `reports/`, returned sheets and merged JSONL are
class 1 under `data/eval/` and are never machine-edited except by an explicit `merge`).

This module holds the shared constants and the one seed helper; it imports no sibling module (no cycles).
"""

from __future__ import annotations

import random

LABELING_SEED = 1006

ANNOTATORS: tuple[str, ...] = ("P1", "P2", "P3", "P4", "P5")
COORDINATOR = "P1"

STAGES: tuple[str, ...] = ("questions", "pilot", "round1", "round2", "unanswerable", "gold", "gold-review")
JUDGMENT_STAGES: tuple[str, ...] = ("pilot", "round1", "round2")
# Stages `merge`/`validate --final` cannot run without; round2 is optional (but must be complete if it exists).
REQUIRED_STAGES: tuple[str, ...] = ("questions", "pilot", "round1", "unanswerable", "gold", "gold-review")

N_ANSWERABLE = 50
N_UNANSWERABLE = 20
POOL_DEPTH = 10
ROUND1_ROWS: tuple[str, ...] = ("E1", "E2", "E3")
UNANSWERABLE_ROW = "E3"
DOUBLE_SHARE = 0.15
DEV_SHARE = 0.40
AGREEMENT_GATE = 0.80
LOAD_TOLERANCE = 0.05
LABEL_FLOOR = 1250
UNANSWERABLE_CHUNK_ID = "UNANSWERABLE"
NO_EVIDENCE = "NO_EVIDENCE"
SLICE_SIZE = 100
ANSWERABLE_QA_FLOOR = 250
SMALL_PAIR_ROWS = 10
PASSAGE_CAP_CHARS = 2000  # display cap per passage on unanswerable/gold/review sheets
CELL_CAP_CHARS = 45000  # display cap per multi-passage cell (Google Sheets allows 50,000 characters per cell)


def seeded(purpose: str, key: str) -> random.Random:
    """The only source of randomness: `random.Random(f"{LABELING_SEED}:{purpose}:{key}")` (E-9)."""
    return random.Random(f"{LABELING_SEED}:{purpose}:{key}")


def share_count(n: int) -> int:
    """Items in the 15% double-check share of `n`: Python `round(0.15 * n)` (banker's rounding on exact .5, e.g.
    round(7.5) = 8 and round(2.5) = 2). Deliberate and pinned by tests; do not replace with floor/ceil."""
    return round(DOUBLE_SHARE * n)
