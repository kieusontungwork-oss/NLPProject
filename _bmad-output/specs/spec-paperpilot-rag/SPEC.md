---
id: SPEC-paperpilot-rag
companions: [stack.md, pipeline-stages.md, evaluation-plan.md, team-split.md]
sources:
  - ../../../docs/proposal/Anshika_proposal.md
  - ../../../papers/AI6127_Assignment.md
---
> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for what to build, test, and validate for the AI6127 assignment. Sources are for traceability and narrative rationale only.

# PaperPilot — Retrieval-Augmented Research Assistant over arXiv AI/ML/NLP Papers

## Why

- AI6127 assignment (35%): RAG system with KB (20) / retrieval (40) / generation (40)
- Corpus: ≥10,000 docs / ≥100,000 words; retriever = sparse + dense + hybrid (+ optional re-ranker); generator solves a downstream task
- Problem: varied terminology, lexical search misses semantics, dense search misses exact terms, raw LLMs hallucinate
- Combining lexical + semantic retrieval + neural re-ranking yields more reliable, evidence-grounded answers than any single method, proven via testing the pipeline incrementally, one component at a time, and measuring the impact of each addition

## Capabilities

- **CAP-1 — arXiv corpus acquisition & KB construction**

  - **intent:** Download ≥10,000 full-text AI/ML/NLP arXiv papers from a verified public dataset (candidate priority resolved by a Week-0 bytes-on-disk spike: S2ORC cs.* slices vs HF `scientific_papers` vs Kaggle arXiv dumps), strip boilerplate/references, dedup by content hash, chunk into passages with a documented structure-aware strategy (256–512 tokens + overlap + section context), and retain metadata (arXiv ID, title, authors, year, abstract, section, source link).
  - **success:** One command rebuilds the KB from raw downloads; `kb_stats.json` reports document/passage counts, chunk count, total words, and types (unique words) — the exact numbers Q1 asks for; ≥10,000 papers and ≥100,000 words cleared with margin; no dataset enters the plan until a real download test puts bytes on disk.
- **CAP-2 — Baseline retrieval: sparse + dense + hybrid**

  - **intent:** Implement BM25 sparse retrieval (inverted-index tooling — never SQL `LIKE`), dense retrieval (sentence-transformers baseline `all-MiniLM-L6-v2`, `BAAI/bge-m3` upgrade path, FAISS index), fused via Reciprocal Rank Fusion.
  - **success:** Single `retrieve(query, k)` API returns the fused ranking; sparse/dense/fusion legs individually toggleable via config; per-stage latency logged.
- **CAP-3 — Retrieval innovations as ablation flags (Q3)**

  - **intent:** Implement, each behind a config flag: cross-encoder re-ranking (`BAAI/bge-reranker-v2-m3`, top-50→top-10), query rewriting/expansion via local LLM with mode-specific routing (HyDE — hypothetical doc embedded for the dense leg only, BM25 keeps the raw query; multi-query — 3–5 variants to both legs), and **section-aware retrieval weighting** (boost abstract/methodology/results/conclusion over boilerplate — PaperPilot's novelty hook), plus chunking/indexing strategy experiments.
  - **success:** Auto-generated ablation matrix over {BM25, dense, hybrid, +rerank, +rewrite(HyDE|multi-query), +section-aware} × {Precision@K, Recall@K, MRR, nDCG@10} on the labeled qrels; ≥2 documented "failed-before / works-now" queries per retained innovation.
- **CAP-4 — Grounded research-QA generation with citations (Q4)**

  - **intent:** A pluggable LLM generator (Ollama local: Qwen2.5-7B or Llama-3.1-8B; swappable free-tier hosted API for demo/evaluation) produces answers strictly conditioned on retrieved passages, with numbered citations resolving to paper title + passage + link, an explicit "not enough evidence in the library" path (two-stage trigger: cross-encoder score gate `τ` when rerank is on + generator-declared `INSUFFICIENT_EVIDENCE` marker; both config-flagged, defined in pipeline-stages.md), and a programmatic citation-resolvability check; answer-side innovation (faithfulness self-check) is ablated for Q5.
  - **success:** 100% citation resolvability on all generated answers (programmatic check); insufficient-evidence gate fires on ≥80% of the unanswerable slice with ≤10% false-fire on answerable questions (reported via `make eval`); RAGAS faithfulness/relevancy reported on the eval answer set; EM/F1 on the extractive-answer subset.
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
- > 30% overlap with any other group's project (this year or past) = disqualification; arXiv-QA is a common theme, so visible differentiation (section-aware retrieval, ablation rigor, citation-grounded answers) is mandatory, and implementation details are never shared.
  >
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
- The QA-pairs + qrels reading of the "1,000 records" requirement is valid for a generative-QA task — brief text supports it ("manually labeling at least 1,000 records" reads as labeled rows, matching the `eval.xls` row-count framing).
- Group of 6 (or 5) splits into up to 3 subgroups mirroring the grading tasks KB(20)/Retrieval(40)/Downstream(40); roster TBD.

## Open Questions

- Sparse engine: `rank_bm25` (zero-ops, slow at 300k–600k chunks) vs Pyserini vs Elasticsearch — decide at the Week-0/1 spike once chunk count is known.
- Which arXiv dataset candidate wins on section-structure quality + license + verified download: S2ORC vs HF `scientific_papers` vs Kaggle dumps?
- Final Ollama generator (Qwen2.5-7B vs Llama-3.1-8B) and whether a free-tier API serves the demo — decide ~Week 3.
- Q5 answer-side innovation scope: faithfulness self-check only, or also iterative/agentic follow-up retrieval? Decide by Week 4 against ablation budget.
- Additional novelty hook beyond section-aware retrieval + ablation rigor (professor weights novelty): multi-hop synthesis queries or method-comparison tables — in or out?
- Group number (PDF filename) and subgroup roster once confirmed.
- Does "≥1,000 labeled records" mean labeled rows (our reading: QA-pair rows + qrels judgment rows) or unique questions? Confirm with TA by ~10-03, before the Week-4 labeling sprint. Fallback if disconfirmed: scale to ~1,000 unique questions with lighter per-question pooling (~5 judgments each, hybrid leg only) — similar total labeling effort, satisfies both readings.
