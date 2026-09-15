# PaperPilot — Evaluation Plan (companion to SPEC.md)

Two labeled artifacts, both ours (the brief allows public datasets for background, but the held-out eval set must be self-labeled). Format is **JSONL, schema documented in the report** — `eval.xls` tabular format applies to classification tasks only; research QA is not classification.

## 1. Retrieval qrels (feeds CAP-3/5, answers Q3)

- **Query set:** ≥250 natural research questions over the corpus, written by the team across query types (terminology-mismatch queries, exact-term queries, survey-style queries, comparison queries), balanced across subfields (NLP/LLMs/RAG/CV/GenAI/ML).
- **Pooling:** for each query, top-10 from BM25, dense, and RRF legs → pooled candidate passages; annotators judge relevance (2 = supporting evidence, 1 = related but insufficient, 0 = irrelevant).
- **Scale:** pooling over ≥250 queries × ~30 candidates ≈ 7,500 judgments (subsample to fit effort); this plus QA-pair labels carries the total past the 1,000-record requirement with margin.
- **Output:** `data/eval/qrels.jsonl` — `{query_id, text, type, subfield}` and `{query_id, chunk_id, relevance}`.

## 2. QA eval set (feeds CAP-4/5, answers Q4)

- ≥250 questions with gold short answers + evidence spans (extractable where possible so EM/F1 is computable); questions the corpus cannot answer kept as a small "unanswerable" slice to test the insufficient-evidence path.
- **Output:** `data/eval/qa_pairs.jsonl` — `{query_id, question, gold_answer, gold_chunk_ids[], answerable}`.

## 3. Annotation protocol (IAA ≥80% requirement)

1. Write labeling guidelines doc (relevance scale definitions + QA answer-length rules + 10 worked examples).
2. Pilot: 100 records double-labeled → compute raw agreement + Cohen's κ; refine guidelines if agreement <80% before the full sprint.
3. Full pass: divide records among 2–3 annotators; 15–20% of all records double-labeled; disagreements resolved by majority/adjudication.
4. Report: raw agreement + κ per artifact; guidelines + report committed to the repo (CAP-6 success).

## 4. Metric matrix (all from `make eval` → `reports/metrics.json`)

| Layer | Metric | Tool | On |
| --- | --- | --- | --- |
| Retrieval | P@5/P@10, Recall@10/100, MRR, nDCG@10 | ir_measures | qrels, every ablation row |
| QA (extractive subset) | Exact Match, token F1 | custom | qa_pairs |
| RAG answer-level | Faithfulness, answer relevance, context precision, context recall | RAGAS (free-tier judge; Ollama fallback) | generated answers for E-ladder configs |
| Citation grounding | citation resolvability (each `[n]` → retrieved chunk) | custom programmatic | every generated answer (must be 100%) |
| Performance | p50/p95 latency per stage, records/sec, cost estimate, scalability note | timing logs | full system |

## 5. Q2 speed protocol

Five fixed demo queries (one per query type); per-query end-to-end latency + per-stage breakdown recorded from the UI run; numbers go into the report verbatim.
