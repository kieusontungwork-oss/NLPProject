# PaperPilot: Evaluation Plan (companion to SPEC.md)

Two labeled artifacts, both ours (the brief allows public datasets for background, but the held-out eval set must be self-labeled). Format is **JSONL, schema documented in the report**: `eval.xls` tabular format applies to classification tasks only; research QA is not classification.

## 1. Retrieval qrels (feeds CAP-3/5, answers Q3)

- **Query set:** ≥250 natural research questions over the corpus, written by the team across query types (terminology-mismatch queries, exact-term queries, survey-style queries, comparison queries), balanced across subfields **present in the KB** (record `year_min/year_max` + composition from `kb_stats.json` first — the corpus ends 2017, so questions target pre-2018 topics: seq2seq, attention, early QA, topic models, classic CV/ML; 2020-era RAG/LLM questions are out of scope by construction).
- **Pooling (two rounds, anti-pooling-bias):** round 1 — for each query, top-20 from BM25, dense, and RRF legs → pooled candidates, judged. **Round 2 (scheduled, Week 5):** after the innovation configs exist, add the top-10 of every E-ladder config (E4, E5a, E5b, E6, E6Δ) to the pool and judge the new candidates — otherwise innovations are penalized for finding passages the baselines missed (unjudged scores as non-relevant). Every ablation row reports `judged@10`; a row below ~90% judged is not comparable and must be re-pooled before entering the report.
- **Scale:** round 1 pooling over ≥250 queries × ~60 candidates ≈ 15,000 judgments (subsample to fit effort); round 2 adds ~1,500–2,500 new candidates; this plus QA-pair labels carries the total past the 1,000-record requirement with margin.
- **Output:** `data/eval/qrels.jsonl`: `{query_id, text, type, subfield}` and `{query_id, chunk_id, relevance}`.

## 2. QA eval set (feeds CAP-4/5, answers Q4)

- ≥250 questions with gold short answers + evidence spans (extractable where possible so EM/F1 is computable); plus a fixed **100-question "unanswerable" slice**, split into a **40-question dev half** (used to calibrate the gate threshold τ and nothing else) and a **60-question held-out half** (used only for the reported fire rate) — the split is committed with the eval set and the halves never mix. At n=25 a pass/fail gate is statistically meaningless (one question = 4 points; 20/25 ≈ 80% has a 95% CI of ~61–92%); at n=60 the held-out rate is decidable. Unanswerable questions are the cheapest rows to label (no gold answer or span needed). RAGAS and EM/F1 are computed on the answerable subset only; the held-out half feeds the sufficiency-gate rates.
- **Output:** `data/eval/qa_pairs.jsonl`: `{query_id, question, gold_answer, gold_chunk_ids[], answerable}`.

## 3. Annotation protocol (IAA ≥80% requirement)

1. Write labeling guidelines doc (relevance scale definitions + QA answer-length rules + unanswerable-question construction rules + 10 worked examples).
2. Pilot: 100 records double-labeled → compute raw agreement + Cohen's κ; refine guidelines if agreement <80% before the full sprint.
3. Full pass: divide records among 2-3 annotators; 15-20% of all records double-labeled; disagreements resolved by majority/adjudication.
4. Report: raw agreement + κ per artifact; guidelines + report committed to the repo (CAP-6 success).

## 4. Metric matrix (all from `make eval` → `reports/metrics.json`)

| Layer | Metric | Tool | On |
| --- | --- | --- | --- |
| Retrieval | P@5/P@10, Recall@10, MRR, nDCG@10, plus `judged@10` diagnostic | ir_measures | qrels, every ablation row |
| QA (extractive subset) | Exact Match, token F1 | custom | qa_pairs |
| RAG answer-level | Faithfulness, answer relevance, context precision, context recall | RAGAS — **one judge fixed for the whole matrix**, judge model+version recorded in `metrics.json`; the judge must NOT be the generator model (self-judging inflates faithfulness); if the judge ever changes, every row re-runs. Raw judge responses cached to `reports/ragas-cache/` (committed at each milestone cut) — with a live LLM judge, caching is what makes `make eval` reproducible at all. Judged on a fixed 100-question subsample of the answerable set, not all of it (volume ≈ 5–10k judge calls otherwise; free-tier quota exhaustion is the normal case, plan for it) | answerable-subset answers, E-ladder configs |
| Citation grounding | citation resolvability (each `[n]` → retrieved chunk) | custom programmatic | every generated answer (must be 100%) |
| Sufficiency gate | fire rate on the 60-question held-out unanswerable half, false-fire rate on answerable | custom | qa_pairs (target ≥80% / ≤10%) |
| Performance | p50/p95 latency per stage, records/sec, cost estimate, scalability note | timing logs | full system |

## 5. Q2 speed protocol

Five fixed demo queries (one per query type); per-query end-to-end latency + per-stage breakdown recorded from the UI run; numbers go into the report verbatim.

## 6. Record counting: what the "≥1,000" counts

The brief says "manually labeling at least 1,000 records": **one record = one manually labeled row**. Two row types: QA-pair rows (`qa_pairs.jsonl`) and qrels judgment rows (`qrels.jsonl`). The two query sets draw from **one shared pool of ≥250 questions**: a question can yield both a QA-pair row and several pooled qrels rows; additions may be disjoint where a question type suits one artifact only (e.g., unanswerable questions are QA-only).

- Floor: ≥1,250 total labeled rows (QA rows + qrels rows) so subsampling can't dip under 1,000.
- The Q4 report includes a count table: | artifact | labeled rows | double-labeled % | raw agreement | Cohen's κ |, plus the unique-question count alongside, for transparency under either reading of the requirement.
