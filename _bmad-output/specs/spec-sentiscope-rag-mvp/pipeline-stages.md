# Pipeline Stages — SentiScope RAG MVP

> Companion to SPEC.md. Stage map for CAP-1→CAP-9. Each stage = one `make` target, resumable, outputs versioned under `data/` or `reports/`.

```
 Stage 0         Stage 1        Stage 2         Stage 3          Stage 4
 spike           corpus         chunk           index            baseline
 ──────          ──────         ─────           ─────            ────────
 dataset check → clean+dedup → 256-512 tok  →  BM25 + FAISS  →  sparse+dense
 domain lock     + stats        + headers       (+reranker DL)   + RRF fuse
                                                                    │
 Stage 8         Stage 7         Stage 6         Stage 5          ▼
 labeling        UI+demo         generate        classify+      eval harness
 ─────────       ────────        ────────        innovate       ────────────
 LS pilot 100 → Gradio chat  →  grounded      →  subj→pol,     ir_measures+
 1000 sprint     citations       answers+cite    stance,aspects RAGAS+perf
 IAA report      5 speed q's     agentic loop    ablation flags
```

## Stage 0 — Data spike & domain lock (Weekend 5–6 Sep + Week 1, gates everything)

- **✅ DONE 2026-09-04** — real-download test passed for all candidates; SocialGrep WSB confirmed dead and replaced by winddude; balance measured (skew: 74% pos — managed via stratified labeling). Evidence: `planning-artifacts/research/data-spike-2026-09-04.md`; files in `NLPProject/data/spike/`.
- Remaining Week-1 items: full lamini download (3.9 GB) or transcript-only extraction; KB subset-size decision (250k rows → 400–800k chunks est.; subsample to ~100–150k for iteration speed).
- Decision rule (proposal §5): finance unless a blocker found → freeze `configs/domain_*.yaml` profile **Mon 7 Sep**, record decision + evidence in memlog.
- **Gate:** chosen profile downloaded in full + balance acceptable + ≥10k passages / ≥100k words projected with margin. → **All three met (pending domain lock Monday).**

## Stage 1 — Corpus build (`make kb`, CAP-1)

- Pull full dataset(s) → clean: strip deleted/removed/[removed] bodies, URLs-only posts, <20-char texts, non-English (fasttext or langdetect), bot posts; dedup by normalized-content hash.
- Emit `data/processed/corpus.parquet` + `reports/kb_stats.json` (docs, chunks, tokens, types — Q1 answer).
- **Gate:** stats file exists; dedup rate reported; random 20-doc sample eyeballed by 2 people.

## Stage 2 — Chunking (`make kb` continues)

- Structure-aware split 256–512 tokens, 15% overlap; contextual header per chunk (`subreddit | date | title | ticker-mentions` or `product | rating | date`).
- Optional `contextual_prefix` flag: LLM writes 1-sentence chunk context (ablation only — one LLM pass per chunk is expensive).
- **Gate:** chunk length histogram; no chunk > max tokens; headers present ≥99%.

## Stage 3 — Indexing (`make index`, CAP-2)

- BM25 over tokenized chunks (rank_bm25 pickle); FAISS IndexFlatIP over L2-normalized embeddings; store `chunk_id → doc metadata` map.
- Pre-download reranker weights at build time (demo machines must not download at runtime).
- **Gate:** both indexes load <10s; `retrieve("sample")` returns ranked IDs from each leg.

## Stage 4 — Eval harness BEFORE innovations (`make eval`, CAP-7a; Week 2)

- Write 100+ real queries; build qrels by pool-judging: take top-k from each leg (sparse, dense, RRF), dedupe the pool, judge "relevant to this query?" in Label Studio (this doubles as labeling-sprint training; **distinct from `eval.xls` task labels**).
- `ir_measures` baseline numbers: sparse-only, dense-only, RRF. **This baseline is the reference line every later claim beats.**
- **Gate:** `reports/metrics.json` exists with all three legs on the same qrels (≥100 queries).

## Stage 5 — Classification stack (`src/classify/`, CAP-5)

- Two-stage: subjectivity (neutral vs opinionated) → polarity (pos vs neg), DistilBERT on Colab T4; training data: `zeroshot/twitter-financial-news-sentiment` + silver-labeled corpus sample (or SST/Amazon-silver for twin).
- Stance (bull/bear/neutral) head for finance; aspect extraction: seed lexicons (value/comfort/ANC...; valuation/momentum/risk...) + noun-phrase mining + LLM cleanup.
- **Gate:** per-stage P/R/F1 on a dev split; aspect hits on 20 gold queries.

## Stage 6 — Generation + agentic loop (`src/generate/`, CAP-4/6; Weeks 3–5)

- Evidence pack (top-10 reranked) + aspect×stance table + quote candidates → prompt template with strict grounding + citation IDs + "insufficient evidence" escape.
- Agentic loop: judge LLM checks aspect coverage; gaps → follow-up query per gap (max 2 rounds); trace logged for UI inspector.
- Grounding Checker runs on every eval answer: L1 citation resolvability (100% required), L2 verbatim span coverage (%), L3 RAGAS faithfulness on ≥200 answers + 50-answer manual audit (HHEM/Ollama fallback if quota dies).
- **Gate:** L1 = 100%, L2/L3 reported; follow-up context resolution works on 10 scripted dialogs.

## Stage 7 — UI + required measurements (`make ui`, CAP-9 + Q2)

- Gradio chat: streaming, numbered citations with links, aspect chips, evidence inspector, rate-answer widget.
- Run the 5 assignment queries; record per-query latency breakdown (retrieve/fuse/rerank/generate) → `reports/speed_5queries.md`.
- **Gate:** fresh laptop, clone → `make setup && make ui` works; 5 queries answered <10s p50.

## Stage 8 — Labeling sprint + IAA (CAP-8, runs Weeks 3–4 in parallel)

- Guidelines 1 page → LS pilot 100 → agreement check (raw ≥80%, κ report) → revise → sprint 1,000 (pre-filled silver labels; humans verify/correct) → adjudicate → export `eval.xls` (exact schema/name) → agreement report.
- **Gate:** `eval.xls` validated (schema + ≥1,000 rows + balance check); IAA ≥80% documented.

## Stage 9 — Ablations + report + buffered submission (Weeks 5–8; freeze 30 Oct, submit 5 Nov)

- `make eval` sweeps the toggle grid → `reports/ablation.md` (Q3/Q5 evidence); collect ≥2 "failed-before/works-now" queries with before/after screenshots.
- Report sections map 1:1 to CAPs; slides assembled from UI demo + ablation table + architecture diagram. Report is optimized FIRST (it is what is graded, with late penalty); presentation is 9–15 Nov, after submission.
- **Gate:** every number in the report traces to `reports/metrics.json` or `ablation.md`; clean-clone rebuild rehearsed before freeze; **content freeze Fri 30 Oct, submit Thu 5 Nov, Week 9 fix-only buffer**; demo polish in the 8–15 Nov window.
