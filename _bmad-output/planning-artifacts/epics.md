# PaperPilot — Epics & Stories

> Derived from `_bmad-output/specs/spec-paperpilot-rag/stories.yaml` (the SPEC's story contract).
> Keep both in sync when stories change; this file is the sprint-tracking source for `bmad-sprint-planning`.

## Epic 1: PaperPilot RAG delivery (AI6127 assignment)

Deliver the full PaperPilot RAG system — KB build, hybrid retrieval with innovations, grounded generation, evaluation, UI, report — by the 2026-10-30 content freeze, submitting 2026-11-05.

### Story 1.1: Week-0 data spike: verify arXiv candidates and pick the KB source

Downloads test slices of arXiv full-text candidates and produces the source decision plus sparse-engine decision data. Resolved 2026-09-18: HF `scientific_papers` arxiv split wins; yield addendum 2026-10-12 (cs.* filter).

- Checkpoints: done_checkpoint (passed — artifacts in `planning-artifacts/research/`)
- Status: **done**

### Story 1.2: Knowledge-base pipeline: clean, dedup, chunk, and stats

One-command KB rebuild from the chosen source: boilerplate stripping, content-hash dedup, section-aware chunking with header prefixes, arXiv metadata join (cs.* filter), `kb_stats.json`. Implements CAP-1. Owner: subgroup A.

- Checkpoints: done_checkpoint

### Story 1.3: Baseline retrieval: BM25 + dense + RRF hybrid

Three baseline legs (sparse, dense, hybrid fusion) behind toggleable interfaces with per-stage latency logging; single `retrieve(query, k)` API. Implements CAP-2. Owner: subgroup B. Sparse engine benchmark-gated at prep (rank_bm25 → bm25s → FTS5 → ES ladder).

### Story 1.4: Eval harness v1: retrieval metrics from qrels

`make eval` target scoring any retrieval configuration against qrels via ir_measures (P@5/P@10, Recall@10, MRR, nDCG@10, judged@10 diagnostic), emitting `reports/metrics.json` + ablation-table skeleton. Implements the retrieval half of CAP-5. Owner: subgroup B.

### Story 1.5: Retrieval innovations: rerank, query rewrite, section-aware weighting + ablation matrix

Cross-encoder re-ranking, HyDE/multi-query rewriting, section-aware weighting as config flags; full ablation ladder (E1-E4, E5a, E5b, E6, E6Δ) with failed-before/works-now queries. Implements CAP-3 (assignment Q3). Owner: subgroup B.

- Checkpoints: spec_checkpoint

### Story 1.6: Labeling sprint: qrels pooling, QA pairs, guidelines, IAA report

≥250 research questions, two-round pooling, labeling guidelines, 100-record pilot, full pass with 15-20% double-labeling, agreement report; 100-question unanswerable slice (40 dev / 60 held-out). Implements CAP-6; re-runs the E-ladder on final qrels. Whole team annotates; subgroup A coordinates.

- Checkpoints: spec_checkpoint, done_checkpoint

### Story 1.7: Grounded generator: Ollama LLM, citations, insufficient-evidence path, self-check ablation

Pluggable generator conditioned strictly on the evidence pack: numbered citations with 100% programmatic resolvability, two-stage insufficient-evidence gate (τ score gate + INSUFFICIENT_EVIDENCE marker), E7 faithfulness self-check. Implements CAP-4 (assignment Q4/Q5). Owner: subgroup C.

- Checkpoints: done_checkpoint

### Story 1.8: Answer-level evaluation: RAGAS, EM/F1, speed protocol

RAGAS (one fixed judge, cached), EM/F1 on the extractive subset, five-query speed protocol with per-stage latency. Completes CAP-5. Owner: subgroup C.

### Story 1.9: Streamlit UI: grounded answers with inspectable evidence

Simple Streamlit app: cited answers, retrieved papers, passages, source links, retrieval inspector, five recorded demo queries with per-query speed. Implements CAP-7 (assignment Q2). Owner: subgroup C.

### Story 1.10: Report and reproducibility: README, zips, group-numbered PDF

README enabling full reproduction, data zip (derived artifacts) + code zip with cloud-drive links, single `<group_number>.pdf` answering Q1-Q5. Implements CAP-8. Owner: subgroup C; checked by all.

- Checkpoints: done_checkpoint
