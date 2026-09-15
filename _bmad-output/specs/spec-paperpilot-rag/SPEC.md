---
id: SPEC-paperpilot-rag
companions: [stack.md, pipeline-stages.md, evaluation-plan.md, team-split.md]
sources:
  - ../../../docs/proposal/Anshika_proposal.md
  - ../../../docs/AI6127_Assignment.md
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate for the AI6127 assignment. Sources are for traceability and narrative rationale only. Supersedes `spec-sentiscope-rag-mvp` (retired 2026-09-15 by team decision; folder kept for reference only).

# PaperPilot — Retrieval-Augmented Research Assistant over arXiv AI/ML/NLP Papers

## Why

AI6127 group assignment (35% of grade) mandates a RAG system: an offline-indexed knowledge base (≥10,000 docs / ≥100,000 words), a self-implemented retriever (sparse + dense + hybrid, optional re-ranker), and a generator solving a downstream task — graded 20/40/40 across KB/retrieval/generation, with novelty, usefulness, and user-friendliness weighting the score. PaperPilot answers this with **research question answering over a large arXiv corpus**: finding evidence in thousands of papers is hard because terminology varies across papers, lexical search misses semantically relevant work, dense search misses exact technical terms, and raw LLMs hallucinate. The project's thesis — and its measurable contribution — is that **combining lexical retrieval, semantic retrieval, and neural re-ranking yields more reliable, evidence-grounded answers than any single method**, demonstrated by a full ablation ladder rather than a single working pipeline.

## Capabilities

- **CAP-1 — arXiv corpus acquisition & KB construction**
  - **intent:** Download ≥10,000 full-text AI/ML/NLP arXiv papers from a verified public dataset (candidate priority resolved by a Week-0 bytes-on-disk spike: S2ORC cs.* slices vs HF `scientific_papers` vs Kaggle arXiv dumps), strip boilerplate/references, dedup by content hash, chunk into passages with a documented structure-aware strategy (256–512 tokens + overlap + section context), and retain metadata (arXiv ID, title, authors, year, abstract, section, source link).
  - **success:** One command rebuilds the KB from raw downloads; `kb_stats.json` reports document/passage counts, chunk count, total words, and types (unique words) — the exact numbers Q1 asks for; ≥10,000 papers and ≥100,000 words cleared with margin; no dataset enters the plan until a real download test puts bytes on disk.

- **CAP-2 — Baseline retrieval: sparse + dense + hybrid**
  - **intent:** Implement BM25 sparse retrieval (inverted-index tooling — never SQL `LIKE`), dense retrieval (sentence-transformers baseline `all-MiniLM-L6-v2`, `BAAI/bge-m3` upgrade path, FAISS index), fused via Reciprocal Rank Fusion.
  - **success:** Single `retrieve(query, k)` API returns the fused ranking; sparse/dense/fusion legs individually toggleable via config; per-stage latency logged.

- **CAP-3 — Retrieval innovations as ablation flags (Q3)**
  - **intent:** Implement, each behind a config flag: cross-encoder re-ranking (`BAAI/bge-reranker-v2-m3`, top-50→top-10), query rewriting/expansion (HyDE or multi-query via local LLM), and **section-aware retrieval weighting** (boost abstract/methodology/results/conclusion over boilerplate — PaperPilot's novelty hook), plus chunking/indexing strategy experiments.
  - **success:** Auto-generated ablation matrix over {BM25, dense, hybrid, +rerank, +rewrite, +section-aware} × {Precision@K, Recall@K, MRR, nDCG@10} on the labeled qrels; ≥2 documented "failed-before / works-now" queries per retained innovation.

- **CAP-4 — Grounded research-QA generation with citations (Q4)**
  - **intent:** A pluggable LLM generator (Ollama local: Qwen2.5-7B or Llama-3.1-8B; swappable free-tier hosted API for demo/evaluation) produces answers strictly conditioned on retrieved passages, with numbered citations resolving to paper title + passage + link, an explicit "not enough evidence in the library" path, and a programmatic citation-resolvability check; answer-side innovation (faithfulness self-check) is ablated for Q5.
  - **success:** 100% citation resolvability on all generated answers (programmatic check); RAGAS faithfulness/relevancy reported on the eval answer set; EM/F1 on the extractive-answer subset.

- **CAP-5 — Evaluation harness**
  - **intent:** One harness computes: retrieval metrics via `ir_measures` on qrels (P@K, Recall@K, MRR, nDCG@10); QA metrics (EM/F1); RAGAS answer-level metrics (faithfulness, answer relevance, context precision/recall); performance metrics (p50/p95 latency, records/sec, cost estimate, scalability notes).
  - **success:** `make eval` reproduces every number in the final report into `reports/metrics.json` + human-readable ablation tables.

- **CAP-6 — Human eval set: QA pairs + qrels mix**
  - **intent:** Build the ≥1,000 hand-labeled-record eval set as: ≥250 natural research questions (gold answers + short extracted evidence spans where possible) plus pooled passage-relevance judgments (top-k from each retrieval leg) reaching ≥1,000 labeled records total; 2–3 annotators, majority adjudication, 15–20% double-labeled; JSONL schema documented (task is generative QA, so the brief's `eval.xls` tabular rule for classification tasks does not apply); deduplicated, topic-balanced across subfields.
  - **success:** Validated JSONL eval set + labeling guidelines + agreement report showing raw agreement and Cohen's κ at IAA ≥80%.

- **CAP-7 — Query UI (Q2)**
  - **intent:** Simple Streamlit app: research question in → grounded answer with inline numbered citations out, retrieved papers list, supporting passages, source links, and a retrieval inspector; deliberately simple per the brief.
  - **success:** The five assignment demo queries run end-to-end in the UI with per-query speed measured and recorded; runs on laptop CPU.

- **CAP-8 — Report & reproducibility artifacts**
  - **intent:** README (clone → install → rebuild KB → run eval → launch UI), `kb_stats.json`, metrics reports, ablation matrix, labeling guidelines + agreement report, data zip + code zip with Dropbox/Drive links, single PDF named by group number with Q1–Q5 answers mapped 1:1 to capabilities; week-13 presentation slides prepped post-submission.
  - **success:** A teammate reproduces the full pipeline from the README alone; every report number traces to `make eval` output.

## Constraints

- Assignment hard rules: ≥10,000 documents/passages and ≥100,000 words; ≥1,000 hand-labeled records with IAA ≥80%; no SQL-string-matching retrieval; not a hosted-RAG-API mashup — retrieval and generation implemented and explainable by us; eval set deduplicated and balanced; non-classification eval format documented (JSONL); single PDF named by group number, Blackboard only.
- Deadline 2026-11-07 23:59 SGT (5%/rounded-day late penalty, first submission only); internal content freeze 2026-10-30; target submission 2026-11-05; week-13 in-person presentation.
- >30% overlap with any other group's project (this year or past) = disqualification; arXiv-QA is a common theme, so visible differentiation (section-aware retrieval, ablation rigor, citation-grounded answers) is mandatory, and implementation details are never shared.
- $0 cash budget: laptop CPU-first (MacBooks), free Colab T4 for heavy compute only, hosted LLMs on free tiers behind a pluggable interface.
- Data discipline: a dataset enters the plan only after a real download test puts bytes on disk; permissively licensed open sources; ToS and rate limits respected.
- English-only corpus; chunking documented as an explicit design choice.
- UI stays simple (Streamlit); sophisticated UI is explicitly discouraged by the brief.

## Non-goals

- No fine-tuning of the generator (prompting/grounding innovations only; fine-tuning recorded as future work).
- No multimodal (figure/table/image) retrieval, no GraphRAG, no multilingual retrieval — recorded as future work.
- No production deployment (cloud hosting, auth, mobile); laptop-local demo is the deliverable.
- No custom web framework (FastAPI/Django app layer); Streamlit suffices.
- No full-corpus live crawling of arXiv; static verified datasets only.

## Success signal

From a clean clone on a laptop: `make kb && make index && make ui` yields a Streamlit app that answers the five demo research questions with cited, inspectable evidence at usable speed (per-query latency recorded); `make eval` reproduces every reported number — retrieval metrics on the qrels, RAGAS on the answer set, IAA ≥80% on the ≥1,000-record eval set — and the ablation matrix shows ≥1 innovation with measurable gain plus ≥2 documented "failed-before/works-now" queries.

## Assumptions

- arXiv full-text candidates (S2ORC cs.* slices, HF `scientific_papers` arXiv split, Kaggle arXiv dumps) remain downloadable at the Week-0 spike; 10k full papers ≈ 50M+ words / 300k–600k chunks — comfortably clearing the corpus minimums.
- CPU embedding of 300k–600k chunks with `all-MiniLM-L6-v2` is a feasible one-off (hours); `bge-m3` upgrade runs on Colab T4 if quality demands.
- Free-tier hosted LLM (e.g., Gemini Flash) suffices for RAGAS judging volume; Ollama-as-judge fallback if quota exhausted.
- The QA-pairs + qrels reading of the "1,000 records" requirement is valid for a generative-QA task (optional cheap TA confirmation).
- Group of 6 (or 5) splits into up to 3 subgroups mirroring the grading tasks KB(20)/Retrieval(40)/Downstream(40); roster TBD.

## Open Questions

- Sparse engine: `rank_bm25` (zero-ops, slow at 300k–600k chunks) vs Pyserini vs Elasticsearch — decide at the Week-0/1 spike once chunk count is known.
- Which arXiv dataset candidate wins on section-structure quality + license + verified download: S2ORC vs HF `scientific_papers` vs Kaggle dumps?
- Final Ollama generator (Qwen2.5-7B vs Llama-3.1-8B) and whether a free-tier API serves the demo — decide ~Week 3.
- Q5 answer-side innovation scope: faithfulness self-check only, or also iterative/agentic follow-up retrieval? Decide by Week 4 against ablation budget.
- Additional novelty hook beyond section-aware retrieval + ablation rigor (professor weights novelty): multi-hop synthesis queries or method-comparison tables — in or out?
- Group number (PDF filename) and subgroup roster once confirmed.
