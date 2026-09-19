---
id: SPEC-paperpilot-rag
companions: [stack.md, pipeline-stages.md, evaluation-plan.md, team-split.md]
sources:
  - ../../../docs/proposal/Anshika_proposal.md
  - ../../../papers/AI6127_Assignment.md
---
> **Canonical contract.** This SPEC, together with the files listed in `companions:`, is the complete, preservation-validated contract for everything we will build, test, and validate for the AI6127 assignment. The source files listed under `sources:` are kept only for traceability and background rationale.

# PaperPilot: Retrieval-Augmented Research Assistant over arXiv AI/ML/NLP Papers

**In plain terms:** PaperPilot is a question-answering system for research papers. You ask a research question, it searches a library of 10,000+ arXiv papers (AI/ML/NLP), and it writes an answer using only evidence from those papers, with numbered citations you can click through and inspect.

## Why

- **The assignment:** This is our AI6127 assignment, worth 35% of the course grade. It is graded in three parts: knowledge base (20), retrieval (40), and generation (40).
- **What the assignment demands:**
  - A corpus of at least 10,000 documents and at least 100,000 words.
  - A retriever that combines sparse (keyword) search, dense (semantic) search, and a hybrid of both, with an optional re-ranker on top.
  - A generator (LLM) that solves a downstream task.
- **The problem we are solving:**
  - Research papers use varied terminology, so the same concept can be described many different ways.
  - Pure keyword (lexical) search misses meaning: it can't match a question to a paper that uses different words.
  - Pure semantic (dense) search misses exact terms: it can lose specific technical phrases or names that must match precisely.
  - Raw LLMs hallucinate: they invent facts when they don't have real evidence.
- **Our thesis:** Combining lexical search + semantic search + neural re-ranking produces more reliable, evidence-grounded answers than any single method alone. We will prove this by testing the pipeline incrementally, adding one component at a time, and measuring the impact of each addition.

## Capabilities

- **CAP-1: arXiv corpus acquisition & knowledge base (KB) construction**

  - **intent:**
    - Download at least 10,000 full-text arXiv papers on AI/ML/NLP topics.
    - Use the source verified by the Week-0 "bytes-on-disk" spike (2026-09-18): the **[HF scientific_papers arxiv split](https://huggingface.co/datasets/armanc/scientific_papers)** . Fallback order: S2AG `s2orc_v2` (only if an S2 API key becomes available), then public GCS `arxiv-dataset` PDFs.
    - Clean the papers: strip boilerplate and reference sections.
    - Remove duplicate papers by comparing content hashes.
    - Split each paper into passages ("chunks") using a documented, structure-aware strategy: 256-512 tokens per chunk, with overlap between chunks and section context attached.
    - Keep metadata for every paper: arXiv ID, title, authors, year, abstract, section, and source link.
  - **success:**
    - One command rebuilds the entire KB from the raw downloads.
    - `kb_stats.json` reports document/passage counts, chunk count, total words, and types (unique words): the four figures Question 1.3 of the assignment brief (`papers/AI6127_Assignment.md`) asks to report.
    - The corpus must comfortably exceed the assignment's hard minimums of 10,000 papers and 100,000 words (brief: `papers/AI6127_Assignment.md`); aim well above them, since dedup, cleaning, and topic filtering will shrink the raw download before the final count.
    - Hard rule: a dataset only counts as real once we have actually downloaded a test slice of it and seen the files on disk; documentation or a dataset card alone never qualifies (this spike proved why: one candidate's mirror had vanished, another's card overstated its contents).
- **CAP-2: Baseline retrieval (sparse + dense + hybrid)**

  - **intent:**
    - Implement **sparse retrieval** with BM25 (keyword search built on proper inverted-index tooling, never SQL `LIKE` string matching).
    - Implement **dense retrieval** (semantic search) using the sentence-transformers baseline `all-MiniLM-L6-v2`, with `BAAI/bge-m3` as an upgrade path, indexed with FAISS.
    - Fuse the two result lists into one ranking using **Reciprocal Rank Fusion (RRF)**, which is the hybrid leg.
  - **success:**
    - A single `retrieve(query, k)` API returns the fused ranking.
    - Each leg (sparse / dense / fusion) can be switched on and off individually via config.
    - Latency is logged for every stage separately.
- **CAP-3: Retrieval innovations as ablation flags (answers Q3)**

  - **intent:** Implement each innovation behind a config flag, so it can be turned on/off for controlled experiments:
    - **Cross-encoder re-ranking** (`BAAI/bge-reranker-v2-m3`): first-pass retrieval fetches a loose top-50, the cross-encoder reads query+passage together and keeps the true top-10: cheap recall first, expensive precision second.
    - **Query rewriting/expansion** via local LLM, routed by search mode:
      - **HyDE**: embeds a generated answer-shaped paragraph for the dense leg only, fixing the question-vs-answer embedding mismatch; BM25 keeps the raw query (a hallucinated paragraph would poison keyword matching).
      - **Multi-query**: 3-5 paraphrases sent to both legs, results pooled via RRF (user questions are often poor search queries).
    - **Section-aware retrieval weighting**: boost abstract/methodology/results/conclusion over boilerplate, exploiting the section structure verified in the Week-0 spike (99% of `scientific_papers` have named sections); PaperPilot's novelty hook.
    - Experiments with alternative chunking and indexing strategies.
  - **how the evidence reads:** flags (not code forks) let the same pipeline run with each innovation on/off, so the ablation matrix isolates one addition per row. A "failed-before / works-now" query (evidence pattern the assignment explicitly asks for: "queries that did not work earlier but now work because of the improvements you made") is a concrete question whose top-10 ranking was wrong without the innovation and correct with it, recorded with both rankings.
  - **success:**
    - An auto-generated ablation matrix covering {BM25, dense, hybrid, +rerank, +rewrite(HyDE|multi-query), +section-aware} × {Precision@K, Recall@K, MRR, nDCG@10}, computed on the labeled qrels (relevance judgments). Output shape (illustrative, numbers filled by `make eval`):

      | Config                        | P@5 | R@10 | MRR | nDCG@10 |
      | ----------------------------- | --- | ---- | --- | ------- |
      | BM25 alone                    |     |      |     |         |
      | dense alone                   |     |      |     |         |
      | hybrid (RRF)                  |     |      |     |         |
      | hybrid + rerank               |     |      |     |         |
      | hybrid + rerank + HyDE        |     |      |     |         |
      | hybrid + rerank + multi-query |     |      |     |         |
      | … + section-aware            |     |      |     |         |

      Each row differs from the previous by exactly one flag, so any metric delta is attributable to that single innovation.
    - At least 2 documented "failed-before / works-now" example queries for every innovation we keep.
- **CAP-4: Grounded research-QA generation with citations (answers Q4)**

  - **intent:**
    - A pluggable LLM generator: Ollama local models (Qwen2.5-7B or Llama-3.1-8B), with a swappable free-tier hosted API for demo/evaluation.
    - Answers must be strictly grounded in (conditioned on) the retrieved passages; no free invention.
    - Every claim carries numbered citations that resolve to a paper title + passage + link.
    - An explicit **"not enough evidence in the library"** path: the system says "I can't answer this from the papers I have" instead of hallucinating. Two independent triggers (either one is enough):
      - A cross-encoder score gate `τ` (active when re-ranking is on): if even the best retrieved passage scores below the threshold, skip the LLM and return the canned response, a cheap pre-generation check that also saves compute.
      - A generator-declared `INSUFFICIENT_EVIDENCE` marker: the prompt instructs the LLM to emit this when the passages look relevant but don't actually support an answer.
      - The gate blocks hopeless questions before generation; the marker catches look-relevant-but-aren't cases. Both triggers are config-flagged and defined in `pipeline-stages.md`.
    - A programmatic check verifies that every citation actually resolves.
  - **success:**
    - 100% citation resolvability on all generated answers (verified programmatically).
    - The system must say "not enough evidence" on ≥80% of unanswerable questions, while wrongly refusing at most 10% of answerable ones.
    - RAGAS (LLM-as-judge) checks every generated answer: is each claim backed by the retrieved passages (faithfulness), and does it actually address the question (relevancy)?
    - On questions whose gold answer is a span copied from a paper, the answer is also scored by string match (EM) and word overlap (F1).
- **CAP-5: Evaluation harness**

  - **intent:** One harness computes all metrics:
    - **Retrieval metrics** via `ir_measures` on qrels: P@K, Recall@K, MRR, nDCG@10.
    - **QA metrics:** EM/F1.
    - **RAGAS answer-level metrics:** faithfulness, answer relevance, context precision/recall.
    - **Performance metrics:** p50/p95 latency, records/sec, cost estimate, scalability notes.
  - **success:**
    - `make eval` reproduces every number in the final report, writing to `reports/metrics.json` plus human-readable ablation tables.
- **CAP-6: Human eval set (QA pairs + qrels mix)**

  - **intent:**
    - Build the required ≥1,000 hand-labeled-record eval set from two parts:
      - ≥250 natural research questions, each with a gold answer and (where possible) a short extracted evidence span.
      - Pooled passage-relevance judgments (taking the top-k results from each retrieval leg), bringing the total to ≥1,000 labeled records.
    - Use 2-3 annotators with majority adjudication; 15-20% of items are double-labeled to check consistency.
    - Document the JSONL schema (this task is generative QA, so the brief's `eval.xls` tabular rule for classification tasks does not apply).
    - Deduplicate the set and balance topics across subfields.
  - **success:**
    - A validated JSONL eval set, labeling guidelines, and an agreement report showing raw agreement and Cohen's κ, with IAA ≥80%.
- **CAP-7: Query UI (answers Q2)**

  - **intent:**
    - A deliberately simple Streamlit app (the brief asks for simplicity): you type a research question and get a grounded answer with inline numbered citations.
    - The UI also shows: the list of retrieved papers, the supporting passages, source links, and a retrieval inspector.
  - **success:**
    - The five assignment demo queries run end-to-end in the UI, with per-query speed measured and recorded.
    - Everything runs on laptop CPU.
- **CAP-8: Report & reproducibility artifacts**

  - **intent:**
    - A README covering the full path: clone → install → rebuild KB → run eval → launch UI.
    - `kb_stats.json`, metrics reports, and the ablation matrix.
    - Labeling guidelines + agreement report.
    - Data zip + code zip, shared via Dropbox/Drive links.
    - A single PDF named by group number, with answers to Q1-Q5 mapped 1:1 to the capabilities above.
    - Week-13 presentation slides, prepared after submission.
  - **success:**
    - A teammate can reproduce the full pipeline from the README alone.
    - Every number in the report traces back to `make eval` output.

## Constraints

- **Assignment hard rules:**
  - At least 10,000 documents/passages and at least 100,000 words.
  - At least 1,000 hand-labeled records with inter-annotator agreement (IAA) ≥80%.
  - No SQL string-matching retrieval.
  - Not a hosted-RAG-API mashup; retrieval and generation must be implemented and explainable by us.
  - The eval set must be deduplicated and balanced.
  - The non-classification eval format must be documented (JSONL).
  - A single PDF named by group number, submitted via Blackboard only.
- **Deadlines:**
  - Due 2026-11-07 23:59 SGT (5% penalty per rounded late day, applied to the first submission only).
  - Internal content freeze 2026-10-30; target submission 2026-11-05.
  - Week-13 in-person presentation.
- **Originality:**
  - More than 30% overlap with any other group's project (this year or past) = disqualification.
  - arXiv-QA is a common theme, so visible differentiation (section-aware retrieval, ablation rigor, citation-grounded answers) is mandatory.
  - Implementation details are never shared between groups.
- **Budget ($0 cash):**
  - Laptop CPU-first.
  - Free Colab T4 for heavy compute only.
  - Hosted LLMs on free tiers, always behind a pluggable interface.
- **Data discipline:**
  - A dataset enters the plan only after a real download test puts bytes on disk.
  - Only permissively licensed open sources.
  - Terms of service and rate limits are respected.
- English-only corpus; chunking documented as an explicit design choice.
- The UI stays simple (Streamlit); the brief explicitly discourages sophisticated UIs.

## Non-goals

- No fine-tuning of the generator, only prompting/grounding innovations (fine-tuning is recorded as future work).
- No multimodal (figure/table/image) retrieval, no GraphRAG, no multilingual retrieval; all recorded as future work.
- No production deployment (cloud hosting, auth, mobile); the laptop-local demo is the deliverable.
- No custom web framework (FastAPI/Django app layer); Streamlit suffices.
- No full-corpus live crawling of arXiv; static verified datasets only.

## Success signal

- From a clean clone on a laptop: `make kb && make index && make ui` produces a Streamlit app that answers the five demo research questions with cited, inspectable evidence at usable speed (per-query latency recorded).
- `make eval` reproduces every reported number: retrieval metrics on the qrels, RAGAS on the answer set, and IAA ≥80% on the ≥1,000-record eval set.
- The ablation matrix shows at least 1 innovation with measurable gain, plus at least 2 documented "failed-before/works-now" queries.

## Open Questions

- **Sparse engine choice**: agreed ladder (user decision 2026-09-18); final call benchmark-gated at Story 3 prep:

  - **1st choice, `rank_bm25`:** pure Python, zero setup; scores a query in ~100-300ms at our scale; scoring code is readable, which the brief rewards.
  - **2nd, SQLite FTS5:** swap here only if `rank_bm25` proves too slow; native `bm25()` over an inverted index; ships in the stdlib `sqlite3` module: no server, no Java, one file, so reproducibility stays perfect (verify FTS5 is compiled into the Macs' Python first).
  - **Last resort, Elasticsearch:** only if the benchmark demands it; fastest, but puts a JVM server on every teammate's laptop (pinned version + `docker-compose.yml` + `make index` rebuild required to keep reproducibility).
  - Engine swaps always happen behind the `SparseRetriever` interface as a config row, never a code fork.
  - Scale context: Week-0 spike estimates ~190k-380k chunks at 10k papers (`_bmad-output/planning-artifacts/research/data-spike-2026-09-18.md`).
- ~~Which arXiv dataset candidate wins on section-structure quality + license + verified download: S2ORC vs HF `scientific_papers` vs Kaggle dumps?~~ **RESOLVED 2026-09-18: HF `scientific_papers` arxiv split.**

  - **Why it won:** 99% of papers have named sections (5.6 per paper); 6,188 mean words/paper (10k papers ≈ 62M words); pre-parsed JSONL means zero parsing work.
  - **Why not the others:** S2ORC's full corpus is now API-key-gated; the Kaggle dump is abstract-only (its GCS PDF salvage is a parse-heavy fallback, third in the fallback order).
  - Evidence: `_bmad-output/planning-artifacts/research/data-spike-2026-09-18.md`.
- **Final generator:** Ollama model choice (Qwen2.5-7B vs Llama-3.1-8B), and whether a free-tier API serves the demo; decide around Week 3.
- **Q5 answer-side innovation scope**, default agreed (user decision 2026-09-18): **faithfulness self-check (E7) only**, with iterative/agentic follow-up retrieval as a *contingency* innovation. Final call at Week 4, driven by data in this order:

  - **Ablation budget:** if the E1-E6 retrieval ladder + labeling sprint leave little eval budget before the content freeze, E7 alone is the complete answer.
  - **Measured trigger for adding the loop:** the insufficient-evidence gate is false-firing on answerable questions in the dev slice (retrieval gaps are the demonstrated bottleneck). Healthy gate rates = the loop solves a problem we don't have.
  - **Label-sprint schedule:** agentic rows need multi-round qrels; if Story 6 slips, cut scope, not labels.
  - Guard against scope creep either way: a retrieval loop can compensate for weak first-pass retrieval and muddle the Q3 ablation story; the loop never ships without its own ablation rows.
- **Extra novelty feature for the report?** The professor rewards novelty, and we already have section-aware retrieval + ablation rigor on the list. Two candidate extras: (a) the generator answers comparison questions with a built-up table of methods (e.g., method × property, citations in every cell), or (b) support questions that combine evidence from two or more papers (multi-hop). Include either, both, or neither; decide later.
