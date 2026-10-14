# PROMPT — Generate the Story-6 Labeling Pack (guidelines + schemas + agreement tooling)

> Hand this prompt to a coding agent to produce the human-labeling work package for Story 6.
> 2–3 teammates will annotate with these docs; the procedure must be unambiguous and identical for everyone.

---

You are preparing the human-evaluation work package for PaperPilot (AI6127 RAG project). Story 6 of
`_bmad-output/specs/spec-paperpilot-rag/stories.yaml` requires a ≥1,000-record hand-labeled eval set with
IAA ≥80%. Your job is to write the DOCUMENTS AND TOOLING that let 2–3 annotators do this work in a
unified, reproducible way. Do NOT label any data yourself.

## Read first (in this order)

1. `_bmad-output/specs/spec-paperpilot-rag/SPEC.md` — CAP-6 (contract), CAP-4 success (unanswerable gate rates), Open Questions (1,000-records reading)
2. `_bmad-output/specs/spec-paperpilot-rag/evaluation-plan.md` — the annotation protocol, metric matrix, record counting (§6), the 25-question unanswerable slice
3. `_bmad-output/specs/spec-paperpilot-rag/stories.yaml` — Story 6 (`invoke_dev_with`)
4. `papers/AI6127_Assignment.md` — the brief's rules ("≥1,000 hand-labeled records", IAA ≥80%, JSONL documentation, dedup + balance)
5. `_bmad-output/specs/spec-paperpilot-rag/pipeline-stages.md` — chunk_id format (qrels must reference valid chunk ids)

## Deliverables (write all four)

### 1. `docs/labeling/labeling-guidelines.md`
The single source of truth annotators follow. Must contain:
- **Relevance scale** for qrels: 2 = supporting evidence / 1 = related but insufficient / 0 = irrelevant — for EACH level: definition, what it is NOT, and boundary rulings for the tricky cases (survey papers, partially-relevant passages, abstracts, duplicate content across papers, tables/numbers in text)
- **QA answer rules**: gold-answer length (one sentence max), evidence-span extraction rules (must be verbatim from one passage), what to do when multiple valid answers exist
- **Unanswerable-question construction rules**: how to verify a question is truly unanswerable (search procedure), the ≥25-question slice, contamination rules (no near-duplicates of answerable questions)
- **Topic-balance rules**: subfield tags (NLP/LLMs/RAG/CV/GenAI/ML) and per-subfield quotas
- **Query-type mix**: terminology-mismatch / exact-term / survey-style / comparison (per evaluation-plan §1)
- **10 worked examples**: 5 qrels judgments (including at least one disputed 1-vs-2 boundary case) + 5 QA pairs (including one unanswerable), each shown with reasoning
- **Annotator conduct rules**: label independently before any discussion; disagreements go to adjudication, never to silent best-guess changes; log uncertainty in a fixed comment field

### 2. `docs/labeling/file-formats.md`
Exact JSONL schemas so every annotator and every script produces identical rows. For EACH file give: field table (name, type, required, description), one full example line, and validation rules:
- `data/eval/qrels_queries.jsonl` — `{query_id, text, type, subfield}`
- `data/eval/qrels.jsonl` — `{query_id, chunk_id, relevance, annotator_id, adjudicated}` (relevance ∈ {0,1,2})
- `data/eval/qa_pairs.jsonl` — `{query_id, question, gold_answer, gold_chunk_ids[], answerable, subfield, type}`
- **Double-labeling convention**: how a second annotator's rows are stored (separate file per annotator, e.g. `qrels.annotator2.jsonl`, then merged), id conventions (query_id format, annotator_id roster), and the dedup rule (one row per query_id+chunk_id after merge)
- **Working format**: raw labeling happens in per-annotator CSV (columns mirroring the JSONL fields, to lower the tooling bar); a provided converter produces the JSONL. State the CSV headers explicitly.

### 3. `scripts/compute_agreement.py`
A runnable script (stdlib + scikit-learn only) that: reads the per-annotator files, extracts double-labeled rows, computes raw agreement and Cohen's κ per artifact (qrels relevance, qa_pairs answerable, gold-answer span match), prints a per-annotator disagreement table, and writes `reports/agreement.json`. Include usage in a docstring and handle: missing labels, non-numeric relevance values, annotators with zero overlap (error with a clear message).

### 4. `docs/labeling/procedure.md`
The step-by-step operating procedure for the 2–3 person team. Number every step; each step names its owner, input, output, and done-criteria:
1. **Setup** — read guidelines; each annotator labels the 10 worked examples blind; discuss divergences (does NOT count toward IAA)
2. **Pilot** — 100 records, all annotators label ALL 100 independently → run `compute_agreement.py`
3. **Gate** — if raw agreement or κ < 80%: diagnose from the disagreement table, amend guidelines (changelog section at the bottom of guidelines.md), re-pilot 100 NEW records; repeat until ≥80%
4. **Full sprint** — split the pool into disjoint shards (one per annotator, balanced by subfield); 15–20% of each shard duplicated for a second annotator; independent labeling only
5. **Adjudication** — all double-labeled disagreements resolved by a third annotator or team majority; adjudicated rows flagged `"adjudicated": true`
6. **Merge + validate** — converter produces final JSONL; validation script checks schema, dedup, subfield balance, and the row-count floor (≥1,250 total labeled rows)
7. **Report** — fill the agreement report template (below) and commit everything

Also include in `procedure.md`:
- **Agreement report template** (to fill at step 7): one table per artifact — | artifact | labeled rows | double-labeled % | raw agreement | Cohen's κ | — plus unique-question count, per evaluation-plan §6, and a changelog of guideline amendments
- **Effort map**: which steps are solo vs whole-team, and a suggested calendar (pilot in week 1, full sprint in weeks 2–3)
- **RACI-lite table**: who writes questions, who labels, who adjudicates (all annotators label; the story owner runs the gate and the merge)

## Constraints

- Every number/rule must trace to evaluation-plan.md, SPEC CAP-6, or the assignment brief — do not invent new requirements
- JSONL (not eval.xls): this is generative QA, not classification — cite that brief clause in file-formats.md
- Keep tone instructional; the docs are for teammates who have NOT read the SPEC
- If any source contradicts another, stop and report the contradiction instead of resolving it silently

## Acceptance check (do before finishing)

- A new annotator could label 10 records using ONLY guidelines.md + file-formats.md — walk through this mentally and fix gaps
- Every file the procedure references exists (or its creation step is explicit)
- `python scripts/compute_agreement.py --help` works and the script runs on two tiny fixture files you create under `tests/fixtures/agreement/`
