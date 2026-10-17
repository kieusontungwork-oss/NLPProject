# PaperPilot labeling — agreement report (Story 1.6)

The coordinator fills this in on Mon 26 Oct, after the final `merge`.
Every number is copied from the committed files below. No number is typed from memory.

- `reports/labeling/merge_summary.json` (written by `merge`)
- `reports/labeling/agreement_<stage>.json` (written by `agreement`)
- `data/eval/queries.jsonl`, `data/eval/qrels.jsonl`, `data/eval/qa_pairs.jsonl`

---

## 1. Summary

| Item                                     | Value | Source (`merge_summary.json`)           |
| ---------------------------------------- | ----- | --------------------------------------- |
| Unique questions (answerable)            |       | `unique_questions.answerable`           |
| Unique questions (unanswerable slice)    |       | `unique_questions.unanswerable_slice`   |
| Unique questions (total)                 |       | `unique_questions.total`                |
| Passage-judgment rows (`qrels.jsonl`)    |       | `qrels_rows`                            |
| QA-pair rows (`qa_pairs.jsonl`)          |       | `qa_pairs_rows`                         |
| **Total labeled rows** (target ≥ 1,250)  |       | `total_labeled_rows`                    |
| Pilot gate (mean pairwise raw agreement) |       | `agreement_pilot.json` — verdict + mean |

---

## 2. Agreement per artifact (evaluation plan §6)

One row per artifact, from `merge_summary.json` → `artifacts.<key>`.

| Artifact                             | Key                   | Labeled rows | Double-labeled % | Raw agreement (pooled) | Cohen's κ (mean)   |
| ------------------------------------ | --------------------- | ------------ | ---------------- | ---------------------- | ------------------ |
| Passage judgments — pilot + round 1  | `qrels_pilot_round1`  |              |                  |                        |                    |
| Passage judgments — round 2          | `qrels_round2`        |              |                  |                        |                    |
| QA pairs — answerable (gold answers) | `qa_pairs_answerable` |              |                  |                        | —                  |
| Unanswerable check                   | `unanswerable_check`  |              |                  |                        |                    |
| Gold-answer review                   | `gold_review`         |              |                  |                        | — (not meaningful) |

- Field names in each `artifacts.<key>` entry:
  - `labeled_rows`
  - `double_labeled_pct` (0–100)
  - `raw_agreement_pooled` (0–1; write it as a percentage)
  - `cohen_kappa_mean`
- How to read the QA-pairs row:
  - "double-labeled %" is the share of gold answers that got a review.
  - "raw agreement" is the share of reviews marked `agree`.
- Passage-judgment agreement is computed over every pair of annotators who labeled the same row.
  - In the pilot all five people labeled every row, so each pilot row counts once per pair.
- `null` in the JSON means "not applicable"; write `—`.

---

## 3. Pilot gate

| Pilot                            | Rows | Mean pairwise raw agreement | Pooled raw agreement | Mean κ | Verdict (≥ 80%) |
| -------------------------------- | ---- | --------------------------- | -------------------- | ------ | --------------- |
| Pilot 1                          |      |                             |                      |        |                 |
| Pilot 2 (only if pilot 1 failed) |      |                             |                      |        |                 |

- Source: `reports/labeling/agreement_pilot.json` (keep a copy of pilot 1's file before a second pilot overwrites it).
- If pilot 1 failed, write here what we changed in `guidelines.md` (same text as its change log).

---

## 4. Unanswerable slice

| Item                                         | Value | Source (`merge_summary.json`)     |
| -------------------------------------------- | ----- | --------------------------------- |
| Slice size (target 100)                      |       | `unanswerable_slice.size`         |
| Dev half (target 40)                         |       | `unanswerable_slice.dev`          |
| Held-out half (target 60)                    |       | `unanswerable_slice.heldout`      |
| Questions answered by the library (replaced) |       | `unanswerable_slice.excluded_yes` |
| Replacements still pending                   |       | `unanswerable_slice.pending`      |

---

## 5. Exceptions and decisions

- `NO_EVIDENCE` gold answers (from `no_evidence`): list the ids and what we decided.
- Gold-review disagreements (from `gold_review_disagreements`): list `query_id`, reviewer, reason, and the decision.
- Merge flags used, if any: `--allow-short-qa`, `--allow-short-slice` (write why).
- Notes from `notes`.

---

## 6. Guideline changes

Copy the change log from `guidelines.md` §7 here, so the report shows which rules each round used.
