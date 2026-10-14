# PaperPilot: Pipeline Stages & Ablation Ladder (companion to SPEC.md)

## Pipeline

```
User research question
        |
        v
[ Query processing ]---------> (optional) Query rewriting / expansion (local LLM)
        |                       mode-specific routing:
        v                         - HyDE: embed the hypothetical answer passage,
   +----+----+                      DENSE leg only (BM25 always sees the raw query)
    |         |                     - multi-query: 3-5 variants to BOTH legs,
    v         v                      variant rankings pooled (RRF) per leg
  BM25      Dense (FAISS)
  (sparse)  (MiniLM / bge-m3)
    |         |
    +----+----+
         |
         v
  Section-aware weighting (boost abstract/method/results/conclusion, optional;
  applied to leg scores BEFORE fusion so it shapes the candidate pool)
         |
         v
  Hybrid fusion (RRF, k=60)
         |
         v
  Cross-encoder re-rank (top-50 -> top-10, optional)
         |
         v
  Evidence pack: top-k passages + metadata (paper, section, year, link)
        |
        v
  Generator (Ollama local, pluggable) -- conditioned ONLY on evidence pack
        |                                  + insufficient-evidence path: 2-stage gate
        v
   +----+----+
   |         |
   v         v
 Answer     Numbered citations
 (with       -> paper title + passage + link
  self-check
  flag)
```

- Every optional stage is a configuration flag (see the swap rule in `stack.md`), so the ablation matrix is produced by running the same harness with different flags toggled.

### Why section-aware weighting sits before fusion

- If it were applied after the top-50 → top-10 re-rank cut, it could only reorder the ten surviving chunks, leaving P@10 and Recall@10 unchanged — E6 would be a near no-op.
- Applied as a pre-fusion boost, it shapes each leg's ranking and therefore determines which 50 chunks the cross-encoder sees: a recall prior at the first stage, semantic precision at the re-rank stage.
- Note: the chunk `header_prefix` already gives BM25 and the embeddings implicit section context; this flag adds the explicit rank prior on top.
- Fallback if E6 gains are weak: use a post-re-rank score blend (`rerank_score + λ · section_weight` over the top-50) as an extra ablation row.

### Candidate depth (pinned 2026-10-12)

- The boost is applied to each leg's `candidate_depth` of **300** retrieved chunks (a configuration value). The leg then re-sorts, and only afterwards is the top-50 cut taken into RRF.
- Applying the boost to an already-truncated top-50 reproduces the same no-op one stage earlier: a relevant Methods chunk at rank 63 could never be promoted.
- E6 reports the candidate depth it used; comparing 50 vs 300 is one additional ablation row if time permits.

### Section weights (pinned initial values)

- abstract — 1.3
- methodology / methods — 1.5
- results — 1.4
- conclusion — 1.3
- related work — 0.8
- other — 1.0
- These are the documented initial values (tunable on the dev slice); the report quotes them as-is.

### Insufficient-evidence trigger (defined and testable)

A two-stage gate; both stages are configuration-flagged.

- **Score gate (pre-LLM, cheap):** when re-ranking is on, if the best cross-encoder score falls below the threshold `τ`, return the canned "not enough evidence in the library" response without calling the generator.
  - Calibrate `τ` only on the 40-question unanswerable dev half — never on the 60-question held-out half from which the reported fire rate comes.
  - Recalibrate `τ` whenever the re-ranker model changes, because score scales differ between models.
- **Generator-declared:** the prompt instructs the model to emit an `INSUFFICIENT_EVIDENCE` marker when the passages do not support an answer; the marker maps to the canned response.
  - This is the primary trigger when re-ranking is off, and the semantic backstop in every configuration.
- **Rejected alternative — thresholding dense-leg cosine:**
  - In a hybrid + re-rank pipeline the dense leg is not the final signal, so BM25-strong queries would misfire.
  - Cosine values are model-dependent (MiniLM vs bge-m3), so a fixed threshold such as 0.25 would not survive the planned embedding swap.
- **Acceptance test (unanswerable slice):** the gate fires on ≥ 80% of unanswerable questions with ≤ 10% false fires on answerable questions; both rates are reported via `make eval`.

## Ablation ladder (the project's core experiment: Q3 & Q5)

| # | Configuration | Proves |
| --- | --- | --- |
| E1 | BM25 only | Sparse-retrieval baseline |
| E2 | Dense only | Semantic-retrieval baseline |
| E3 | BM25 + dense (RRF) | Hybrid gain |
| E4 | E3 + cross-encoder re-rank | Re-ranking gain |
| E5a | E4 + HyDE (hypothetical document embedded; dense leg only — BM25 keeps the raw query) | Rewriting gain on the embedding side |
| E5b | E4 + multi-query (variants sent to both legs; RRF-pooled per leg) | Rewriting gain on both the lexical and embedding sides |
| E6 | best(E5a, E5b) + section-aware weighting | **PaperPilot's proposed system** |
| E6Δ (diagnostic) | E3 + section-aware weighting (no re-rank, no rewrite) | Section-aware gain without the re-ranker overshadowing it |
| E7 (answer side, Q5) | E6 ± faithfulness self-check | Generation-side innovation gain |

- **Metrics per run:** P@5 / P@10, Recall@10 / Recall@100, MRR, and nDCG@10 on qrels; downstream answer quality (RAGAS) for the generation configurations; p50 / p95 latency per stage.
- Each retained innovation needs at least two documented "failed before / works now" queries.
- **Ladder order ≠ pipeline order.** Each row toggles flags in one fixed architecture: when section-aware weighting is on, it always applies pre-fusion (see the diagram above); enabling it at E6 does not move it downstream.
- Components are added from standard to novel, so the ladder ends on the proposed system, and E3 remains the course-designated hybrid baseline (comparable across groups).
- E6Δ separates "overshadowed by the re-ranker" (E6Δ healthy, E6 small) from "no signal" (both weak). If E6Δ is strong but E6 is not, the λ-blend fallback above is the fix to try.

## Knowledge-base schema

- **Per paper:** `arxiv_id, title, authors[], year, abstract, sections{...}, source_link, license, categories[]`.
  - Title, authors, year, categories, and license come from the **arXiv metadata join** (the public `gs://arxiv-dataset/metadata-v5/arxiv-metadata-oai.json`, keyed by `arxiv_id`; pre-2007 ids need their slash re-inserted) — the source dataset carries none of them.
  - A paper with no metadata row is dropped, not emitted with nulls, because citations must resolve to a real title 100% of the time.
- **Per chunk** (JSONL, one object per line): `chunk_id, arxiv_id, section_name, section_rank, text, n_tokens, header_prefix` (the paper title and section header are prepended for context).
- Deduplicate by content hash before chunking.
- `kb_stats.json` contains: papers, chunks, words, types, a chunk-size histogram, `year_min`, `year_max`, a year histogram, and category composition.

## Chunking design (graded design choice; document it in the report)

- Split on structure at section boundaries, using the dataset's parsed structure rather than a fixed-length hack.
- Target 256–512 tokens per chunk with ~15% overlap; keep the abstract as its own chunk.
- Add a header prefix (paper title + section name) to every chunk so that both the embeddings and BM25 see the context.
- If time permits, run the alternatives (fixed 512 tokens, no overlap, no header prefix) as ablation rows in E-ladder style.
