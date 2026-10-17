---
story: '1.6'
slug: labeling-sprint
status: in-progress
baseline_commit: f50e556
context:
  - _bmad-output/planning-artifacts/architecture/architecture-NLPProject-2026-10-12/ARCHITECTURE-SPINE.md
  - _bmad-output/specs/spec-paperpilot-rag/evaluation-plan.md
  - _bmad-output/specs/spec-paperpilot-rag/stories.yaml#story-6
  - _bmad-output/implementation-artifacts/spec-pattern-digest.md
  - data/eval/labeling/team-guide.md
  - data/eval/labeling/guidelines.md
---

# House Spec — Story 1.6: Labeling sprint (qrels pooling, QA pairs, guidelines, IAA report)

> **Spec checkpoint:** this story carries `spec_checkpoint: true`. The owner reviews the frozen block below before any tooling is built. The human process (team guide + guidelines) is drafted alongside it so the team can start question writing at kickoff.

<frozen-after-approval>

## Intent

The 5-person team produces the human eval set that every reported number depends on: ≥250 answerable research questions + a fixed 100-question unanswerable slice; round-1 pooled passage judgments (qrels); gold answers (QA pairs); ≥80% inter-annotator agreement, documented. Teammates only fill Google Sheets; the coordinator runs one CLI (`python -m paperpilot.evaluation.labeling`) that drafts every sheet, checks every returned sheet, measures agreement, and merges the human labels into `data/eval/*.jsonl`. Implements CAP-6. The story is **done** only after round-2 pooling (needs story 1.5) and a re-run of the eval harness (story 1.4) on the final labels; the tooling + guides land first as their own PR.

## Boundaries & Constraints

### Always

- **Process documents** (class 1, spine AD-5): `data/eval/labeling/team-guide.md` (who/when/how, newbie wording), `guidelines.md` (relevance scale, tricky cases, real worked examples, change log), `coordinator-commands.md`, `agreement-report.md`.
- **Team:** annotators `P1`–`P5`; P1 = coordinator. Query ids: answerable `P<n>-001…050`, unanswerable `P<n>-U01…U20`.
- **Question quotas per person** (50 answerable): type — `terminology-mismatch` 15, `exact-term` 15, `survey` 10, `comparison` 10; subfield — `Machine learning & AI` 10, `NLP & IR` 8, `Computer vision` 7, `Information theory & signals` 7, `Algorithms & theory` 7, `Networks & social` 6, `Systems, security & data` 5. Subfield groups are a fixed mapping of arXiv categories (priority order NLP & IR → CV → ML & AI → the rest), measured on the real KB (2026-10-17: 12,350 papers; IT 2,921, theory 2,857, ML 1,657, networks 1,536, systems 1,401, CV 922, NLP 654, other 402). Unanswerable: 20 per person, post-2017 topics.
- **Round-1 pool:** for each answerable question, the union of the top-10 of rows E1, E2, E3 (measured mean 19.2, range 16–24 on 40 queries), so every baseline row has judged@10 = 100%. Passage order shuffled per question with a fixed seed; source row and rank hidden from annotators.
- **Assignment:** nobody judges their own questions; 15% of answerable questions (whole question = all its passages) are double-labeled by a second annotator; loads balanced to ±5% across P1–P5; deterministic (fixed seed).
- **Pilot:** 5 questions × their full pools (~100 rows), labeled by all 5 annotators independently.
- **Agreement:** raw agreement on the 0/1/2 label, per annotator pair and mean over pairs, plus Cohen's κ per pair; binary agreement (relevant = label ≥ 1) also reported. **Gate: mean pairwise raw agreement ≥ 80%** (κ reported, not gated). Below the gate: guideline change-log entry, second pilot on 5 new questions.
- **Unanswerable check:** one `yes`/`no` per question against its top-10 E3 passages; `yes` rows need a replacement question; 15% double-checked by another person. The 100 surviving questions are split 40 dev / 60 held-out (fixed seed, stratified by author) and the split is committed.
- **Gold answers:** per answerable question, by its author, from passages labeled 2; ≤ ~30 words; `gold_chunk_ids` ⊆ that question's 2-labeled chunks; `NO_EVIDENCE` allowed and counted. 15% reviewed by another person (`agree`/`disagree`).
- **Adjudication:** every double-labeled disagreement is decided by a third annotator in the disagreement meeting and recorded in `data/eval/labeling/adjudication.csv` (`query_id, chunk_id, final_relevance, adjudicator, reason`).
- **Artifacts:** machine-drafted sheets are class 3 under `reports/pooling/<stage>/P<n>.csv` (AD-5); returned human sheets are class 1 under `data/eval/labeling/raw/<stage>/P<n>.csv`; merged outputs are class 1: `data/eval/queries.jsonl` `{query_id, text, type, subfield, answerable, author}`, `data/eval/qrels.jsonl` `{query_id, chunk_id, relevance, annotators[], adjudicated}`, `data/eval/qa_pairs.jsonl` `{query_id, question, gold_answer, gold_chunk_ids[], answerable, split}` (`split` ∈ `dev`/`heldout` for unanswerable rows, `null` otherwise).
- **Validation (before any merge is written):** schema + allowed values; every `chunk_id` exists in the current `chunks.jsonl` (AD-2); one row per `(query_id, chunk_id)`; no duplicate questions (normalized-text token Jaccard ≥ 0.8 flagged); quota counts reported; total labeled rows (qrels + QA) ≥ 1,250.
- **CLI:** argparse subcommands `catalog`, `check-questions`, `pilot`, `sheets`, `unanswerable-sheets`, `agreement`, `gold-sheets`, `merge`, `validate`; `run_<x>_command` → int, never raises, exit 0 ok / 1 validation failed / 3 stage error; human summary on stdout. Retrieval only through `paperpilot.retrieval.Retriever` (AD-1: `evaluation` is a driver).
- **Round 2 ready:** `sheets --round 2 --rows <ids>` drafts only passages not yet judged, from rows given on the command line, so story 1.5 needs no new code here.

### Ask First

- Changing quotas, pool depth (top-10 union), double-label share (15%), the 80% gate or its definition.
- Overwriting an existing `data/eval/*.jsonl` (merge refuses unless `--replace` is passed).
- Any runtime dependency (target: none beyond the lock; κ is computed in stdlib).

### Never

- Teammates never run code; no Label Studio or other server.
- No AI-generated labels, questions or gold answers (assignment requires human labels).
- No machine edits to class-1 human files (`raw/`, `adjudication.csv`, guides) — tools read them only.
- No network in tests; tests use synthetic KB + index fixtures.

## I/O & Edge-Case Matrix

| # | Input / trigger | Expected behavior |
| --- | --- | --- |
| I-1 | `catalog` | `reports/labeling/kickoff/papers_catalog.csv` (`arxiv_id, year, subfield, categories, title, abstract_start, link`) + `questions_P1..P5.csv` pre-numbered (70 rows each) |
| I-2 | `check-questions` on `raw/questions/` | Per-person report: missing fields, bad type/subfield, quota deltas, duplicates (within and across people), questions mentioning 2018+ years on answerable rows; exit 1 if any blocking issue |
| I-3 | `pilot --questions <ids>` | Identical sheets for P1–P5 under `reports/pooling/pilot/` |
| I-4 | `sheets --round 1` | Per-person sheets; no own questions; 15% double; balanced loads; columns `row_id, query_id, question, passage_id, paper_title, section, year, passage, relevance, comment` |
| I-5 | `agreement --stage pilot|round1|round2` | Pairwise raw agreement, κ, binary agreement, per-annotator disagreement counts; `reports/labeling/agreement_<stage>.json`; gate verdict printed |
| I-6 | `unanswerable-sheets` | 20 own + 3 others' questions per person with top-10 E3 passages |
| I-7 | `gold-sheets` | 50 own questions per person with the 2-labeled passages + ~8 review rows |
| I-8 | `merge` | Writes the three JSONL files from raw + adjudication; refuses to overwrite without `--replace`; runs `validate` first |
| E-1 | Relevance cell not in {0,1,2} (blank, `1.5`, text) | `validate`/`agreement` exit 1 naming file:row; nothing merged |
| E-2 | A returned sheet has renamed/missing/extra columns | Exit 1 naming the file and the column diff |
| E-3 | A returned sheet's row set differs from the drafted sheet (rows deleted/added/`passage_id` edited) | Exit 1 naming the rows |
| E-4 | Double-labeled disagreement without an adjudication row | `merge` exit 1 listing the missing pairs |
| E-5 | Two annotators have zero overlap | Their pair is skipped with a warning, not a crash |
| E-6 | A chunk_id no longer exists in `chunks.jsonl` (KB rebuilt) | `validate` exit 1 listing the ids (AD-2) |
| E-7 | Unanswerable question marked `yes` | Excluded from the slice until its replacement passes; slice count < 100 reported |
| E-8 | `NO_EVIDENCE` gold answer | Kept out of `qa_pairs.jsonl` answerable rows; counted and listed for the coordinator |
| E-9 | Same inputs, same seed | Byte-identical sheets (determinism) |
| E-10 | Round 2 | Only `(query_id, chunk_id)` pairs without a round-1 judgment are drafted |

</frozen-after-approval>

## Code Map

```text
src/paperpilot/evaluation/__init__.py
src/paperpilot/evaluation/labeling/subfields.py   # category -> subfield group mapping (single source)
src/paperpilot/evaluation/labeling/sheets.py      # CSV schemas, read/write, round-trip checks (E-2, E-3)
src/paperpilot/evaluation/labeling/pooling.py     # top-10 union of E1/E2/E3, shuffle, assignment (I-3, I-4, I-6, E-9, E-10)
src/paperpilot/evaluation/labeling/agreement.py   # raw agreement, Cohen's kappa (stdlib), gate (I-5, E-5)
src/paperpilot/evaluation/labeling/merge.py       # adjudication, validation, JSONL writers (I-8, E-1, E-4, E-6..E-8)
src/paperpilot/evaluation/labeling/cli.py         # subcommands
data/eval/labeling/{team-guide,guidelines,coordinator-commands,agreement-report}.md
tests/evaluation/                                  # local only
```

## Tasks & Acceptance

1. Guides — `team-guide.md`, `guidelines.md` (drafted 2026-10-17 for the kickoff), `coordinator-commands.md`. AC: a teammate can do Step 1 with only the guide + catalog.
2. `catalog` + subfield mapping. AC: I-1; counts match the measured composition.
3. Sheets I/O + `check-questions`. AC: I-2, E-2, E-3.
4. Pooling + assignment (`pilot`, `sheets`, `unanswerable-sheets`, `gold-sheets`). AC: I-3, I-4, I-6, I-7, E-9, E-10.
5. Agreement. AC: I-5, E-5; κ matches a hand-computed fixture.
6. Merge + validate. AC: I-8, E-1, E-4, E-6, E-7, E-8.
7. Human sprint (team): questions → pilot → gate → round 1 → unanswerable check → adjudication → gold answers. AC: agreement ≥ 80%; ≥ 1,250 labeled rows; `agreement-report.md` filled.
8. Round 2 + re-run (with stories 1.4/1.5). AC: judged@10 ≥ 90% for every reported row; `reports/metrics.json` regenerated on the final labels.

## Review Findings

Fresh-context review of PR #4: edge-case hunter (H1–H20), test audit (T1–T15, 121 mutants), acceptance auditor (A1–A9, D1–D10, U1–U14). Three Sonnet subagents, run concurrently.

- [x] [Review][Patch] P1 (H3) — sorting one column in Google Sheets detaches labels from passages and passes the round-trip; compare each row's displayed content with the drafted sheet
- [x] [Review][Patch] P2 (H1, A8) — round 2 treats missing returned sheets as "nothing judged" and ignores earlier round-2 sheets; require complete pilot/round-1 returns and include round 2
- [x] [Review][Patch] P3 (H2, D5) — `gold-sheets` drafts from incomplete round-1 returns without a visible warning; require complete judgment stages
- [x] [Review][Patch] P4 (H4, A8) — the ±5% load guard blocks small round-2 drafts; gate round 1 only, report round-2 balance against cumulative loads
- [x] [Review][Patch] P5 (H5, H15, A2) — answerable questions can end with zero qrels; `validate` checks coverage; `sheets --round 1` requires a returned pilot; `pilot --questions` rejects ids already drafted in round 1
- [x] [Review][Patch] P6 (H6) — the dev/heldout split reshuffles when slice membership changes; keep committed splits, place only new ids
- [x] [Review][Patch] P7 (H7) — `validate --final` demands sheets from annotators who were drafted none; expected annotators come from the drafted folder
- [x] [Review][Patch] P8 (H8) — returned sheets are checked against regenerable class-3 drafts; drafting refuses to overwrite a stage that already has returned sheets (unless `--force`)
- [x] [Review][Patch] P9 (H9) — an adjudicator may be one of the pair's own labelers; refuse
- [x] [Review][Patch] P10 (H10, A3) — `--final` accepts a short or long unanswerable slice and a non-40/60 split; require exactly 100 (40/60) unless `--allow-short-slice`
- [x] [Review][Patch] P11 (H11) — question text edited after pooling is not detected; warn on drift
- [x] [Review][Patch] P12 (H12) — a trailing empty header column (typing in column K) blocks a sheet; drop blank trailing columns
- [x] [Review][Patch] P13 (H13) — `pilot --auto 0` / empty `--questions` crash with IndexError/TypeError; validate inputs
- [x] [Review][Patch] P14 (H14) — the three JSONL files are not replaced as a set; back up and restore on failure
- [x] [Review][Patch] P15 (H15) — error floods; cap per file (first 10 + count)
- [x] [Review][Patch] P16 (H16, H17) — report pooled (micro) agreement and per-pair n alongside the approved mean-pairwise gate; κ = n/a when a pair uses one constant label
- [x] [Review][Patch] P17 (H18, H19) — reuse `kb.metadata.bare_metadata_id`; read only P1–P5 files and warn on stray CSVs
- [x] [Review][Patch] P18 (H20) — merge exit code masking; hint "likely numeric coercion" for numeric-looking unmatched ids
- [x] [Review][Patch] P19 (A1) — `python -m paperpilot.evaluation.labeling` must run (`__main__.py`)
- [x] [Review][Patch] P20 (A4) — `--final` requires ≥ 250 answerable QA rows unless `--allow-short-qa`
- [x] [Review][Patch] P21 (A5) — `agreement-report.md` template + a merge summary with the evaluation-plan §6 table (rows, double-labeled %, agreement, κ, unique questions)
- [x] [Review][Patch] P22 (A6) — gold review required under `--final`; `disagree` rows listed in the merge summary for the coordinator
- [x] [Review][Patch] P23 (A7, D3, D4, D6, D7, D10) — guides: unanswerable construction rules + 10 numbered worked examples in `guidelines.md`; stale names and `<S>` notes; `(fill)`/`comment` wording; `source_paper` format; columns for Steps 4–5; year rule and "Other CS" stated up front; catalog filtering
- [x] [Review][Patch] P24 (D1, D2, D8, D10) — coordinator doc: one consistent rule for the few allowed manual edits in `raw/`, catalog output line, dropdown entry for the subfield containing a comma; cap multi-passage cells below the 50k-character Sheets limit
- [x] [Review][Patch] P25 (T1–T14) — test gaps: hash-seed-independent determinism (subprocess), golden seed pins, E1/E2/E3 union, gold subset by label 0 and 1, NO_EVIDENCE case, share rounding, tolerance boundaries, Jaccard = 0.8, year rule scope, pilot diversity, weak asserts, floor boundary, set-atomic merge, partial optional stage, `SystemExit` codes (tests stay local)
- [x] [Review][Defer] H20 (part) — escaping formula-like passage text; mitigated by the documented "untick convert" import step. Target: only if a returned sheet shows it
- [x] [Review][Defer] Replacement path for `NO_EVIDENCE` answerable questions (A4 part): the coordinator decides at merge time via `--allow-short-qa`. Target: Mon 26 Oct merge, if needed

- [x] [Review][Defer] P1 limit — sorting only the `relevance` column cannot be detected by comparing content (relevance is the filled cell); the guide's golden rule ("never sort or filter a single column") is the protection. Target: a monotonic-column heuristic warning, only if a returned sheet shows it

Dismissed: `Findings` being a mutable dataclass (A9; it is an accumulator, not a value); test hygiene nits T15 (no behavior at stake).

## Spec Change Log

- 2026-10-17: Initial frozen block (in-session). Deviations from `evaluation-plan.md`, all for the owner's review: (1) round-1 pool = top-**10** union of E1/E2/E3 (~19/question, ~4,750 judgments) instead of top-20 (~36/question, ~9,000) — keeps judged@10 = 100% for the baselines at half the effort; (2) question rows live in `queries.jsonl`, not inside `qrels.jsonl`; (3) the IAA gate is defined as mean pairwise raw agreement on 0/1/2, κ reported; (4) 5 annotators, so agreement is pairwise. `story6-labeling-pack-prompt.md` is superseded (it predates the 100-question slice and the 2017 corpus end).
- 2026-10-17: Spec checkpoint passed — owner approved the frozen block, including deviations (1)–(4). KEEP: top-10 union pool; 15% whole-question double-labeling; gate = mean pairwise raw agreement ≥ 80%; teammates never run code.
- 2026-10-17: Build amendments (tooling). (a) Label resolution for multi-labeled pairs: adjudication row if present, else unanimous, else strict majority, else an adjudication row is required (E-4); pilot rows (5 labels) usually resolve by majority. (b) Round-1 assignment processes questions round-robin across authors (`P1-001, P2-001, …`) instead of sorted query_id order: in sorted order the last author's questions starve one annotator (−16.5% load on a 245-question synthetic run, failing the ±5% guard); round-robin gives ±2%. (c) Display text in sheets strips the header prefix and `<S>`/`</S>` markers (display only). (d) Unanswerable adjudication rows use `chunk_id = UNANSWERABLE` with `final_relevance` yes/no; replacement questions take ids `P<n>-U21…` and are re-checked with `unanswerable-sheets --only`. (e) A second pilot archives the first pilot's folders and its questions return to round 1. (f) `agreement` exits 0 on a FAIL verdict (the verdict is printed); exit 1 is for malformed sheets. (g) The labeling timeline was compressed to one week (17–24 Oct) at the owner's request; round 2 waits for story 1.5. KEEP: round-robin assignment; teammates never run code; the resolution rule is identical in merge, gold-sheets and validate.
- 2026-10-17: Post-review amendment — P1–P25 applied (623 tests). Notable decisions: (1) gold-review is required at merge; `disagree` rows are listed, not blocking; (2) a failed first pilot is archived and its labels are not used (two pilots cannot share one stage without "already judged" conflicts); its questions go into round 1; (3) the adjudicator rule ("not one of the pair's labelers") is waived for pilot pairs, which all five people label; (4) Cohen's κ is `None` ("n/a") when a pair uses one constant label, excluded from the mean; the gate stays mean pairwise raw agreement ≥ 0.80, with the pooled value reported beside it; (5) because gold sheets need every drafted judgment stage returned, the coordinator drafts gold sheets before drafting round 2, and review sheets after round 2 is back; (6) `--final` requires exactly 100 unanswerable (40/60) and ≥ 250 answerable QA rows unless `--allow-short-slice` / `--allow-short-qa`; committed splits never move. `agreement-report.md` template added, filled from `merge_summary.json`. KEEP: drafting refuses to overwrite a stage with returned sheets (unless `--force`); round-trip compares row content; merge replaces the three files as a set.

## Design Notes

- **Load per person** (estimate): 70 questions; pilot ~100 rows; round 1 ≈ (250 × 19.2 × 1.15) / 5 ≈ 1,100 rows; 23 unanswerable checks; 50 gold answers + ~8 reviews; round 2 ~300–500 rows. About 20 hours each over two weeks.
- **Row count:** round 1 ≈ 5,500 judgment rows + 350 QA rows ≫ the 1,250 floor, so the floor holds even if round 1 is cut.
- **Seed qrels for story 1.4:** the pilot labels (adjudicated) are the seed qrels; matrices on them are development output only.

## Verification

1. `pytest tests/ -q` green offline.
2. Synthetic dry run of every subcommand on the test KB; sheets round-trip through `check`/`agreement`/`merge`.
3. Real run: `catalog` reproduces the kickoff files; pilot sheets for 5 real questions.

## Suggested Review Order

1. `src/paperpilot/evaluation/labeling/pooling.py` — pool union, shuffle, `interleaved_order`, assignment and load guard
2. `src/paperpilot/evaluation/labeling/merge.py` — label resolution, adjudication, unanswerable slice + split, gold checks, JSONL writers
3. `src/paperpilot/evaluation/labeling/agreement.py` — raw agreement, Cohen's κ, gate
4. `src/paperpilot/evaluation/labeling/sheets.py` — CSV schemas, round-trip checks, `check-questions`
5. `src/paperpilot/evaluation/labeling/cli.py`, `subfields.py`, `core/errors.py`
6. `data/eval/labeling/coordinator-commands.md`
