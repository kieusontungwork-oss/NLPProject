---
id: SPEC-sentiscope-rag-mvp
companions: [stack.md, pipeline-stages.md, team-split.md]
sources:
  - ../../../../papers/AI6127_Assignment.md
  - ../../planning-artifacts/proposals/2026-09-04-sentiscope-opinion-rag-proposal.md
---

> **Canonical contract.** This SPEC and its `companions:` define what SentiScope MVP must build, test, and validate for the AI6127 assignment. Sources are for traceability and narrative rationale only.

# SentiScope — Opinion-QA RAG over Finance Posts + Earnings Transcripts (twin: Product Reviews)

## Why

AI6127 group assignment mandates a RAG system: an offline-indexed knowledge base (≥10,000 docs / ≥100,000 words), a self-implemented retriever (sparse + dense + hybrid, optional re-ranker), and a generator/classifier solving a downstream task, evaluated with rank-aware retrieval metrics, task metrics, RAG metrics, and a self-labeled held-out set (≥1,000 records, IAA ≥80%). Grading adds novelty, usefulness, user-friendliness. SentiScope = conversational opinion mining (the assignment's own exemplar task) over finance social data, aligned with the instructor lab's research (SenticNet: ABSA, XAI-for-finance, hybrid symbolic+neural). Domain decision (finance vs product reviews) is a deliberate early fork with identical machinery (see Non-goals / Assumptions).

## Capabilities

- **CAP-1 — Corpus acquisition & KB construction**
  - **intent:** Download, clean, deduplicate, chunk, and index a corpus ≥10,000 passages / ≥100,000 words from the chosen domain (finance: `winddude/reddit_finance_43_250k` + `lamini/earnings-calls-qa`; twin: Amazon Reviews 2023 category slices), fully scriptable and rerunnable. **No dataset enters the plan until a real download test passes (bytes on disk)** — rule adopted 2026-09-04 after the SocialGrep WSB-2021 loader proved dead (NXDOMAIN on exports.socialgrep.com).
  - **success:** One command rebuilds the KB from raw downloads; corpus stats (docs, chunks, tokens, types) emitted as `kb_stats.json`; dedup by content hash; chunking = structure-aware 256–512 tokens + overlap + contextual headers; class-balance report (polarity/stance distribution from silver labels) confirms the brief's "balanced data" requirement before domain lock; single unified index with `source_type`/`date`/`ticker` metadata facets (merged-vs-partitioned retrieval is an ablation row, not a build fork).

- **CAP-2 — Baseline retrieval: sparse + dense + hybrid**
  - **intent:** Implement BM25 (rank_bm25 or Elasticsearch-class inverted index — no SQL `LIKE`), dense retrieval (sentence-transformers: `all-MiniLM-L6-v2` baseline, `BAAI/bge-m3` upgrade, FAISS/Chroma index), fused via Reciprocal Rank Fusion (k=60).
  - **success:** Single `retrieve(query, k)` API returns fused ranking; components individually toggleable via config; latency logged per stage.

- **CAP-3 — Retrieval innovations (Tier-1+ upgrades, non-blocking: CAP-2 hybrid is the mandatory core)**
  - **intent:** Cross-encoder re-ranking (top-50→top-10, `BAAI/bge-reranker-v2-m3`) scheduled first (inference-only, ~1 day, biggest single gain), then query expansion (HyDE + multi-query via local LLM), parent-document retrieval, metadata/time-window filtering (post dates / ratings), and optional contextual chunk prefixes (Anthropic-style) as ablation flags.
  - **success:** Each innovation is a config flag; ablation matrix auto-generated: {baseline, +rerank, +hyde, +multi-query, +parent, +contextual} × {P@5, P@10, Recall@100, MRR, nDCG@10} on the labeled query set.

- **CAP-4 — Agentic evidence-sufficiency loop**
  - **intent:** After first retrieval, an LLM judge checks whether each aspect implied by the query (e.g., "worth it" → value/comfort/ANC; ticker question → valuation/momentum/risk) has sufficient supporting evidence; missing aspects trigger targeted follow-up queries (max N rounds).
  - **success:** For a curated set of multi-aspect queries, recall of aspects covered ≥ baseline single-shot; loop trace (rounds, queries issued, evidence added) logged and renderable in UI.

- **CAP-5 — Downstream task: two-stage opinion classification**
  - **intent:** Per the assignment's suitcase decomposition: (1) subjectivity detection (neutral vs opinionated), then (2) polarity (positive vs negative) on opinionated chunks; plus stance classification (bullish/bearish/neutral for finance; pro/con for reviews) and aspect extraction (lexicon/seeded-ner/LLM hybrid).
  - **success:** Fine-tuned DistilBERT/RoBERTa heads (Colab T4) report P/R/F1 per stage on `eval.xls`; stance distribution computed per evidence pack; aspect-sentiment pairs feed the generator as structured context.

- **CAP-6 — Grounded generation with citations + 3-level Grounding Checker**
  - **intent:** LLM (Ollama Qwen2.5-7B / Llama-3.1-8B local; Gemini Flash free tier for demo/RAGAS judging) generates answers strictly conditioned on the retrieved evidence pack: stance percentages, per-aspect summary, representative quotes with source links; explicit "not enough evidence in the library" path when CAP-4 exhausts rounds. Every answer passes the Grounding Checker: **L1** citation resolvability (each `[n]` maps to a retrieved chunk; programmatic, always-on), **L2** span grounding (quoted spans appear normalized-verbatim in their cited chunk; programmatic, always-on), **L3** semantic faithfulness (RAGAS on ≥200 eval answers + 50-answer manual audit; local NLI fallback (HHEM) or Ollama-as-judge if API quota exhausted).
  - **success:** L1 = 100% on all generated answers; L2 span-coverage % reported; L3 faithfulness reported with audit notes; follow-up questions resolve coreference within session.

- **CAP-7 — Evaluation harness**
  - **intent:** One harness computes: (a) retrieval metrics via `ir_measures` (P@K, Recall@K, MRR, nDCG@10) from hand-labeled qrels — **qrels are a separate labeling effort from `eval.xls`**: ≥100 queries, pool-judged (top-k from sparse/dense/RRF legs) for relevance; (b) task metrics (P/R/F1 per classification stage) on `eval.xls`; (c) RAG metrics via RAGAS (faithfulness, answer relevancy, context precision/recall) with LLM judge; (d) performance: p50/p95 latency, records/sec, est. cost.
  - **success:** `make eval` produces `reports/metrics.json` + human-readable ablation tables; all numbers in the final report reproduce from this harness.

- **CAP-8 — Human eval set & labeling workflow**
  - **intent:** Build `eval.xls` (exact filename/format per assignment — sentiment-benchmark tabular schema; these are **downstream task labels** per the brief's Q4/P-R-F1 requirement, not retrieval relevance judgments) with ≥1,000 records: model-assisted pre-labels (silver: star ratings / vendor annotations / LLM draft) verified by ≥2 human annotators; guidelines doc; pilot batch of 100 with pairwise agreement check before full sprint; majority adjudication; 15–20% double-labeled for reported IAA ≥80%.
  - **success:** Label Studio project export → `eval.xls` validated schema; agreement report (raw agreement + Cohen's κ) committed alongside.

- **CAP-9 — Chat UI**
  - **intent:** Gradio (or Streamlit) chat: streaming answers, inline numbered citations with clickable source links, aspect chips with stance colors, evidence inspector (which chunks were retrieved and why), "rate this answer" widget, session context for follow-ups.
  - **success:** 5 assignment-required demo queries run end-to-end in UI; per-query speed measured and recorded (Q2 requirement); UI runs on laptop CPU.

- **CAP-10 — Report & reproducibility artifacts**
  - **intent:** README (setup/run), `kb_stats.json`, metrics reports, ablation matrix, labeling guidelines + agreement report, demo scripts, 5 speed-measured queries.
  - **success:** A teammate can clone → install → rebuild KB → run eval → launch UI following README alone; report answers Q1–Q5 mapping 1:1 to CAPs.

## Constraints

- Assignment hard rules: ≥10,000 docs/passages and ≥100,000 words; `eval.xls` filename and sentiment-benchmark tabular format (deviation = demerit); ≥1,000 hand-labeled records with IAA ≥80%; retrieval must NOT be SQL-string-matching; system must not be a hosted-RAG mashup — retrieval and generation stages implemented and explainable by us.
- Schedule: content freeze 2026-10-30; submission 2026-11-05 (deadline 2026-11-07 23:59 SGT — submit 2.5 days early by design); Week 9 (11-02..07) is fix-only buffer, no new features after freeze; presentations 2026-11-09..15 → demo polish happens post-submission with zero grading risk.
- Data access discipline: every dataset passes a real-download test (bytes on disk) before entering the plan; loader-script datasets that fetch from third-party CDNs are treated as unverifiable until tested (2026-09-04: SocialGrep WSB loader dead — NXDOMAIN — replaced by winddude dump).
- Compute: laptop CPU-first (MacBooks) + free Colab T4 for classifier fine-tuning; no assumption of local NVIDIA GPU; hosted API usage limited to free tiers (Gemini Flash / Groq) and must remain swappable (generation is a pluggable interface); $0 cash budget.
- Reddit data: Pushshift is dead — no historical backfill via PRAW beyond recent window; KB anchors on the static `winddude/reddit_finance_43_250k` dump; fresh PRAW pull optional garnish only.
- Balanced data: eval set must not be polarity-skewed; stratify by silver labels; corpus-level balance verified at Week-0/1 spike (winddude dump is pre-filtered by upvotes/length — check before domain lock).
- One unified retrieval index with `source_type`/`date`/`ticker` metadata facets; per-source indexes only as an ablation comparison, not a build fork.
- Corpus dedup mandatory (assignment: eval set must not contain duplicates; KB dedup is good practice for chunk hygiene).
- Language: English-only corpus (multilingual is a non-goal).

## Non-goals

- No multimodal retrieval (ColPali/CLIP), no GraphRAG, no multilingual retrieval, no fine-tuning of the generator — recorded as future work; revisit only if all CAPs green by Week 7.
- No production deployment (cloud hosting, auth, mobile); laptop-local demo is the deliverable.
- No custom web app framework (FastAPI/Django) — Gradio/Streamlit suffices per assignment guidance.
- No scraping beyond permitted sources/APIs; ToS and rate limits respected.
- No real-time stock prices/market data integration.
- No attempt at financial advice framing — system reports observed opinion distribution, not recommendations.

## Success signal

From a clean clone on a laptop: `make setup && make kb && make index && make ui` yields a chat that answers 5 demo opinion questions with cited, stance-broken-down answers in <10s p50 per query; `make eval` reproduces every reported number (retrieval metrics on ≥100 labeled queries, P/R/F1 on 1,000-record `eval.xls` with IAA ≥80%, RAGAS on the answer set); ablation matrix shows ≥1 innovation with measurable gain and 2+ "failed-before/works-now" query examples documented.

## Assumptions

- `winddude/reddit_finance_43_250k` (250k post/comment pairs, 43 finance/investing/crypto subreddits, `top.jsonl` hosted directly on HF — verified 2026-09-04 via API) and `lamini/earnings-calls-qa` (jsonl hosted, verified) remain downloadable at the Week-0/1 spike; combined finance corpus clears 10k passages / 100k words with margin (winddude alone: 250k pairs).
- Winddude dump caveat: pre-filtered (≥250 chars, positive score, 70th-quantile per subreddit) — Week-0 spike measured the skew (VADER: posts 74% pos / 25% neg / 1% neu) → managed via stratified eval labeling + balanced `eval.xls` by design; also **no timestamp field** — sentiment-timeline feature runs on earnings-call `date` (Reddit base36 ID→date estimation is an optional stretch). Fallbacks if unusable: blend with earnings calls + `zeroshot/twitter-financial-news-sentiment` corpus slice, or Kaggle `reddit_wsb` (57k titles), or archive.org pushshift WSB mirrors. Full spike evidence: `planning-artifacts/research/data-spike-2026-09-04.md`.
- Amazon Reviews 2023 parquet slices (Headphones/Laptops or Steam reviews) remain the validated twin corpus; star-rating silver labels suffice to anchor human labeling in either domain.
- Labeling anchors for finance: `zeroshot/twitter-financial-news-sentiment` labels + LLM-assisted pre-labels are anchors, not ground truth; all reported eval numbers come from our own human-verified `eval.xls`.
- Free-tier hosted LLMs permit RAGAS judging volume (~1,000 answers × few metrics); Ollama 7B is the offline fallback for generation quality even if judging needs the API.
- Cohort-wide risk accepted: finance-sentiment theme may attract other groups; differentiation = conversational aspect-level opinion QA + agentic sufficiency loop + earnings-transcript subcorpus (assignment allows idea overlap <30%; no implementation sharing).
- Domain fork decision locks end of Week 1 (data spike); post-freeze switch cost ~1 week (accepted only before end of Week 3).

## Open Questions

- Final subgroup roster (names → A/B/C) once teammates confirm; affects who runs the labeling sprint.
- Elasticsearch vs rank_bm25 for the sparse leg: rank_bm25 default (zero-ops); revisit only if corpus >1M chunks makes scoring slow.
- Whether Cohere Rerank free tier replaces bge-reranker for the demo (latency/quality tradeoff) — decide during Week 3–4.
- Optional TA confirmation (cheap, not blocking): that `eval.xls` = downstream task labels in sentiment-benchmark format is the intended reading of Q4 (brief text already supports this: P/R/F1 on the 1,000 records, tabular sentiment format).
