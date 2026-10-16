# PaperPilot — Project Overview (start here)

> One-page orientation for new team members. Everything here is summarized from the planning docs — links to the originals are at the bottom. Last updated 2026-10-14.

## What is this project?

**PaperPilot** is a question-answering system for research papers. You ask a research question in plain language; it searches a local library of 10,000+ arXiv AI/ML/NLP papers and writes an answer **using only evidence from those papers**, with numbered citations you can click through and inspect (paper title + passage + link). If the library can't answer, it says so instead of guessing.

It's our **AI6127 assignment** (35% of the course grade), graded in three parts: knowledge base (20 pts), retrieval (40 pts), generation (40 pts).

**The thesis we're proving:** combining lexical search + semantic search + neural re-ranking gives more reliable, evidence-grounded answers than any single method alone. We prove it by adding one component at a time and measuring each step (the "ablation ladder").

## The problem

- Papers describe the same concept with different words → pure keyword (BM25) search misses meaning.
- Pure semantic (dense) search misses exact technical terms and names.
- Raw LLMs hallucinate when they lack evidence → answers must be strictly grounded in retrieved passages.

## Dataset (the knowledge base)

| Fact                   | Value                                                                                                                                                                                       |
| ---------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Source                 | [HF `scientific_papers` arxiv split](https://huggingface.co/datasets/armanc/scientific_papers) (~3.5GB, pre-parsed JSONL — verified on disk)                                              |
| Metadata               | Joined against public arXiv metadata snapshot (`gs://arxiv-dataset/metadata-v5/arxiv-metadata.json`) — fills title/authors/year/categories; papers with no metadata row are dropped      |
| Filter                 | All `cs.*` categories → ≥10k papers with margin (AI/ML/NLP ≈ 7.5k is the primary subcollection; questions target it)                                                                   |
| Years                  | 1995–2017 (corpus ends 2017 — questions target pre-2018 topics; RAG/LLM-era questions are out of scope by construction)                                                                   |
| Scale after processing | ~190k–380k chunks; must exceed the assignment minimums of 10,000 papers / 100,000 words                                                                                                    |
| Processing             | Strip boilerplate/references → dedup by content hash → structure-aware chunking (256–512 tokens, ~15% overlap, abstract kept whole, paper-title+section header prepended to every chunk) |

## How it works (dataflow)

```
OFFLINE (build once)                     ONLINE (every query)
─────────────────────                    ──────────────────────────────────────────────
HF scientific_papers                     research question
  → metadata join (cs.* filter)            → [optional] query rewrite
  → clean + dedup                            · HyDE → dense leg only
  → chunk (structure-aware)                  · multi-query → both legs
  → papers.jsonl + chunks.jsonl             ↓
  → indexes: BM25 + FAISS              BM25 ∥ dense retrieval (top-300 each)
                                           ↓
                                    [optional] section-aware weighting (pre-fusion)
                                           ↓
                                    RRF fusion (k=60)
                                           ↓
                                    [optional] cross-encoder re-rank (top-50 → top-10)
                                           ↓
                                    evidence pack (top-k passages + metadata)
                                           ↓
                                    insufficient-evidence gate (score threshold τ
                                    + LLM-declared INSUFFICIENT_EVIDENCE marker)
                                           ↓
                                    generator (Ollama, conditioned ONLY on evidence)
                                           ↓
                                    answer + numbered citations (100% resolvable)
```

Every `[optional]` stage is a **config flag** — the same pipeline runs with each innovation on/off, which is how we produce the ablation matrix (assignment Q3).

## Tech stack ($0 budget, laptop CPU-first)

| Component        | Choice                                                                                                                                                        |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Language         | Python 3.11+ (uv-managed venv)                                                                                                                                |
| Sparse retrieval | BM25 on `bm25s`, chosen by the 2026-10-15 benchmark gate (the `rank_bm25` → `bm25s` → SQLite FTS5 → Elasticsearch ladder), behind one interface                    |
| Dense retrieval  | `all-MiniLM-L6-v2` (CPU baseline) → `BAAI/bge-m3` (Colab T4 upgrade)                                                                                     |
| Vector index     | FAISS `IndexFlatIP` exact (vectors normalized; IVF kept only for the scalability discussion)                                                                |
| Hybrid fusion    | Reciprocal Rank Fusion (RRF, k=60) — course-designated                                                                                                       |
| Re-ranker        | `ms-marco-MiniLM-L-6-v2` (CPU dev loop) / `bge-reranker-v2-m3` (Colab T4, final numbers)                                                                  |
| Generator        | Ollama local (Qwen2.5-7B or Llama-3.1-8B), free-tier API swappable behind an interface                                                                        |
| Metrics          | `ir_measures` (retrieval), RAGAS (answer-level, one fixed judge + cached responses), EM/F1 (extractive subset)                                              |
| UI               | Streamlit (deliberately simple — the brief discourages fancy UIs)                                                                                            |
| Orchestration    | Plain Python modules + Makefile (`make kb / index / eval / ui`) — **no LangChain/LlamaIndex**: graded stages must be implemented and explained by us |

## Repo rules everyone must follow (architecture spine)

**AD-1 Layering — code dependencies point one way only.**
UI may only call the agreed interfaces (`DenseRetriever`, `Generator`, …), never reach into another module's internals.

- Without it: the UI person imports `retrieval.faiss_stuff._private_helper()`. Next week subgroup B renames that function while swapping MiniLM→bge-m3 → the UI crashes, and every swap becomes a 3-person emergency.
- With it: B can rip out the whole dense backend and UI never notices, because it only knows the interface.

**AD-2 Chunk IDs — one single function decides every chunk's ID.**
ID = hash of (arxiv_id, section, text). Same text → same ID, forever.

- Without it: you generate IDs randomly or ad-hoc. You rebuild the knowledge base the night before submission → all IDs change → the team's ~1,250 hand-labeled eval answers now point at chunks that "don't exist" → weeks of annotation work destroyed.
- With it: rebuild produces identical IDs → labels and old citations stay valid automatically.

**AD-3 EvidencePack — one envelope is the ONLY thing handed from retrieval to the LLM.**
The pack = top-10 passages + scores + metadata. The generator is prompted only with what's inside, and every `[1]`, `[2]` citation must point to an item in that pack.

- Without it: the generator sneaks in its own lookup, or the LLM cites a paper it imagined. You can't prove answers are grounded — and "100% resolvable citations" is an explicit grading criterion.
- With it: a checker can mechanically verify every citation resolves. Grounding becomes a testable fact, not a promise.

**AD-4 Config rows — experiments are rows in one YAML, any two rows differ by exactly one flag.**

- Without it: to test "does re-ranking help?", someone copies the pipeline to `experiment_v2.py` and changes rerank + chunk size + top-k at once. Metrics improve — but you can't say which change did it. The ablation table (the core of the 40-pt retrieval grade) is indefensible.
- With it: row E2 vs E3 differ only by `rerank: on` → the metric delta is proven to come from the reranker.

**AD-5 Artifact classes — three tiers of files, each with strict write rules.**

- class 1 (code, configs, `data/eval/` labels): hand-written, git-tracked. Deleting = losing the project.
- class 2 (`data/raw/`, `data/kb/`): only `make kb` may write them. Deleting = a re-download; never hand-edit.
- class 3 (`indexes/`, `reports/`): derived, always safe to delete and regenerate.
- Without it: someone hand-edits a chunk "just to test", or tweaks a number in `metrics.json` directly → the report no longer matches the data, and nobody knows which files are trustworthy.
- With it: everyone knows what's safe to delete (class 3), what regenerates (class 2), and what must never be touched (class 1).

**AD-6 One metrics writer — only `make eval` produces report numbers, each traceable to a run.**
`metrics.json` is assembled from section files, each stamped with config row + git commit.

- Without it: the report says nDCG 0.82, but nobody can re-run whatever produced 0.82 → unreproducible results, which for a graded assignment is a disaster.
- With it: any number in the report → look up row id + commit → re-run → same number. Every claim is reproducible.

Planned layout: `src/paperpilot/{core,kb,retrieval,generation,evaluation,ui}` + `configs/` + `data/` + `indexes/` + `reports/` + Makefile.

## Evaluation at a glance

**We build our own eval set:**

- ≥250 research questions over the corpus (targeting pre-2018 topics)
- pooled relevance judgments (qrels) — humans mark which passages truly answer each question; the pool is judged in two rounds (once for the baselines, again after the innovations exist) so a new feature that finds passages the baselines missed still gets credit
- QA pairs with gold answers — every question stored together with a human-written reference answer (the "answer key" the system's generated answer is graded against); questions the library cannot answer are marked `answerable: false` instead
- a 100-question **unanswerable** slice — questions the library genuinely cannot answer (post-2017 topics): 40 are used to tune the refusal threshold τ, and a separate 60 are kept untouched so the reported refusal rate is honest (never measured on the questions the threshold was tuned on)

**Labels:**

- target ≥1,250 labeled rows with inter-annotator agreement ≥80%

  - A labeled row = one human judgment: either a QA pair (question + gold answer) or one qrel (one passage marked relevant / not relevant for one question).
  - **Why 1,250?** The brief demands ≥1,000 labeled rows; the team aims for 1,250 so that even if some rows are discarded later (duplicates, mistakes), the count can never drop below the required 1,000. A safety margin, not busywork.
  - **What inter-annotator agreement (IAA) proves:** when two people label the same item, how often do they agree? Example: 100 passages judged by two annotators, same verdict on 85 → 85% ✓. If agreement were only 60%, the labels would be mostly opinion — and every metric built on them (P@5, nDCG, refusal rate) would be noise. IAA ≥80% is the proof that the leaderboard rests on consistent labels; disagreements are settled by discussion (adjudication), not by coin flip.
- whole team annotates; guidelines + agreement report committed

  - **Why the whole team annotates:** 1,250+ rows is weeks of work, and IAA can only be measured if multiple people label the same items (15–20% of rows are double-labeled).
  - **Why guidelines matter:** the rulebook (what counts as "relevant" vs "background", gold-answer length, how to construct an unanswerable question, worked examples) is what makes 80% agreement achievable — without shared rules, annotators guess differently by definition. Example: a survey paper that mentions attention in one paragraph → guideline says relevance 1 (background), not 2, so everyone labels it the same way.
  - **Why "committed":** the guidelines and the final agreement statistics (raw %, Cohen's κ, per artifact) are stored permanently in git — the grader can verify label quality, not just take it on trust. Full protocol: `evaluation-plan.md` §3.

**`make eval` reproduces every number in the report:**

- P@K / Recall / MRR / nDCG per ablation row (retrieval)
- RAGAS faithfulness / relevancy, EM/F1 (answers)
- citation resolvability (must be 100%), gate fire rates, and p50/p95 latency

## Team & schedule

| Subgroup            | Member   | Owns                               | Main stories         |
| ------------------- | -------- | ---------------------------------- | -------------------- |
| A — Knowledge Base | Member 1 | KB pipeline, labeling coordination | 1-2, coordinates 1-6 |
| B — Retrieval      | Member 2 | Baselines, innovations, ablations  | 1-3, 1-4, 1-5        |
| C — Downstream     | Member 3 | Generator, RAGAS, UI, report       | 1-7 → 1-10          |

**Deadlines:** content freeze **2026-10-30** · submit **2026-11-05** · hard deadline 2026-11-07 23:59 SGT (5%/late day). Full schedule + per-story status: `_bmad-output/implementation-artifacts/sprint-status.yaml`.

## Go deeper (reading order)

1. `_bmad-output/specs/spec-paperpilot-rag/SPEC.md` — the full contract
2. `_bmad-output/specs/spec-paperpilot-rag/pipeline-stages.md` — pipeline details + ablation ladder + KB schema
3. `_bmad-output/specs/spec-paperpilot-rag/stack.md` — every stack choice + swap rules
4. `_bmad-output/planning-artifacts/architecture/architecture-NLPProject-2026-10-12/ARCHITECTURE-SPINE.md` — the six rules above, in full
5. `_bmad-output/specs/spec-paperpilot-rag/evaluation-plan.md` — eval set, pooling, metrics, IAA protocol
6. `_bmad-output/specs/spec-paperpilot-rag/team-split.md` — deliverables map + milestones
7. `papers/AI6127_Assignment.md` — the original assignment brief
