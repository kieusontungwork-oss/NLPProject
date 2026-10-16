---
story: '1.3'
slug: baseline-retrieval
status: in-progress
baseline_commit: 1d5885b16a7c42cf27dbb12931a742b2aabc86cd
context:
  - _bmad-output/planning-artifacts/architecture/architecture-NLPProject-2026-10-12/ARCHITECTURE-SPINE.md
  - _bmad-output/specs/spec-story-1-3-baseline-retrieval
  - _bmad-output/implementation-artifacts/spec-pattern-digest.md
  - _bmad-output/specs/spec-paperpilot-rag/stories.yaml#story-3
  - _bmad-output/planning-artifacts/research/sparse-engine-benchmark-2026-10-15.md
---

# House Spec — Story 1.3: Baseline retrieval (BM25 + dense + RRF hybrid)

<frozen-after-approval>

## Intent

`make index` builds a BM25 index, an exact FAISS dense index, and a chunk docstore from the story-1.2 KB. `Retriever.retrieve(query, k)` then returns an `EvidencePack` (AD-3) holding the RRF-fused top-k. Each leg (sparse, dense) is switched on or off by a validated config row in `configs/ablations.yaml` (E1 BM25 only, E2 dense only, E3 hybrid), and every stage's latency is recorded in the pack and logged. Implements project CAP-2; first code in the `retrieval/` layer.

## Boundaries & Constraints

### Always

- **Layering (AD-1):** `paperpilot.retrieval` imports only from `paperpilot.core` (and the stdlib/deps). The ports `SparseRetriever` and `DenseRetriever` live in `paperpilot.core.ports`; the retriever talks to legs only through them.
- **Sparse engine = `bm25s` 0.3.13** (benchmark gate, `research/sparse-engine-benchmark-2026-10-15.md`), method `lucene`, `k1 = 1.5`, `b = 0.75`; the three values single-sourced in `core.config` and recorded in the sparse manifest.
- **One tokenizer** for indexing and querying, single-sourced in `retrieval/tokenize.py`: lowercase → `re.findall(r"[^\W_]+", text)` → drop tokens shorter than 2 characters → drop the fixed Lucene English stopword set (`a an and are as at be but by for if in into is it no not of on or such that the their then there these they this to was will with`). No stemming.
- **Dense leg:** `sentence-transformers/all-MiniLM-L6-v2` (the configured `embedding_model`), embeddings L2-normalized, FAISS **exact `IndexFlatIP`** (AD-5; IP = cosine). The model is loaded only through `paperpilot.core.clients.load_sentence_transformer(model_id)` (spine Consistency Conventions: one HF loader). The dense retriever takes its encoder by injection (an `Encoder` protocol: `encode(texts: list[str]) -> np.ndarray` of shape `(n, dim)`, float32, L2-normalized), so tests never load a real model.
- **Row alignment:** BM25 doc i, FAISS vector i and docstore row i all correspond to line i of `data/kb/chunks.jsonl`. Leg results cross the port as `LegHit(chunk_id, score, rank)` (frozen dataclass, `rank` 1-based).
- **Config rows (AD-4):** `RetrievalConfig` pydantic model in `core.config` with `extra="forbid"`; fields `id: str`, `description: str = ""`, `use_sparse: bool = True`, `use_dense: bool = True`, `rrf_k: int = 60` (> 0), `candidate_depth: int = 300` (≥ 1), `sparse_engine: Literal["bm25s"] = "bm25s"`, `embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"`. At least one leg must be on. The YAML file is `{rows: [...]}`; unknown top-level keys, duplicate ids, and unknown row keys are rejected. Defaults live only in the model.
- **RRF (k = `rrf_k`):** `rrf_score(d) = Σ_legs 1 / (rrf_k + rank_leg(d))`, ranks 1-based, over each enabled leg's full `candidate_depth` list. One code path for 1 or 2 legs (single-leg RRF preserves that leg's order). Ties broken by `(-rrf_score, min leg rank, chunk_id)`.
- **Deterministic leg order:** each leg sorts its results by `(-score, row)` before ranking; the sparse leg drops results with score ≤ 0 (no lexical match is not a hit).
- **EvidencePack (AD-3)** defined in `core.schemas` as frozen pydantic models, `pack_version = 1`: `query_id, query, effective_queries[{type, text, legs[]}], hits[], stage_timings_ms{str: float}, gate{score_gate_fired: bool = False, generator_declared: bool | None = None}`. A hit is `{rank, chunk_id, text, header_prefix, arxiv_id, title, section_name, year, source_link, leg_scores{bm25: float | None, dense: float | None}, rerank_score: float | None = None, rrf_score: float}`. `rrf_score` is a deliberate v1 field (the fused score the eval run file needs). In this story `effective_queries` is always `[{type: "raw", text: query, legs: [enabled legs]}]`.
- **Hit hydration** reads chunk fields from `chunks.jsonl` by byte offset and title/year/source_link from the docstore's paper-metadata sidecar (derived from `papers.jsonl`, the single source of paper metadata per AD-5). Nothing is re-derived from chunk text.
- **Stage timings:** `stage_timings_ms` keys `sparse`, `dense_encode`, `dense_search`, `fusion`, `hydrate`, `total` (float ms via `time.perf_counter`, through a small `core.timing` helper); a disabled leg's keys are absent. One INFO log line per `retrieve` with query_id, row id, k, and the timings.
- **Index artifacts are class 3 (AD-5):** written only by `index` under `indexes/`; each component directory carries `manifest.json` = `{created, embedding_model, dim, chunk_store_hash, config_row, engine, n_chunks, params}` (`chunk_store_hash` = SHA-256 hex of the `chunks.jsonl` bytes; `embedding_model`/`dim` are `null` for sparse and docstore). Each component is built in a sibling temp directory and swapped in only when complete; a failed build leaves the previous component intact.
- **Loaders refuse on mismatch:** missing component → `IndexMissingError`; `chunk_store_hash` ≠ current `chunks.jsonl`, `embedding_model` ≠ configured model, or `engine` ≠ configured `sparse_engine` → `IndexMismatchError`. Both subclass `RetrievalStageError` (stage base `PaperPilotError`) and the message names the expected and found values and says to run `make index`.
- **CLI:** `python -m paperpilot.retrieval.cli {index,search}`, argparse subparsers, `run_index_command` / `run_search_command` → int, never raise (unexpected exceptions → exit 3). Exit 0 ok, 3 stage error; human output on stdout, errors on stderr. `make index` = `index --row E3`.

### Ask First

- Changing the tokenizer (stemming, stopwords, token pattern), BM25 method/k1/b, the RRF formula or tie rule.
- Any runtime dependency beyond: `bm25s==0.3.13`, `numpy`, `scipy`, `faiss-cpu==1.15.1`, `sentence-transformers==6.1.0` (torch transitive), `pyyaml` (moved from dev to runtime).
- Any EvidencePack field beyond the list above.
- A second sparse adapter or a dense model other than the configured default.

### Never

- No SQL `LIKE`, no SQLite/FTS retrieval, no LangChain/LlamaIndex.
- No approximate FAISS index (IVF etc.) in this story.
- No reranking, query rewriting, or section weighting code (story 1.5); no eval harness, qrels, or `reports/` writes (story 1.4).
- No writes to `data/kb/`, `data/eval/`, or `configs/` at runtime; no hashing of chunk ids outside `core.ids`.
- No network in tests; no real model download in tests; no committed index artifacts.
- No silent degradation: a missing model, index, or chunk store raises.

## I/O & Edge-Case Matrix

| # | Input / trigger | Expected behavior |
| --- | --- | --- |
| I-1 | `data/kb/chunks.jsonl` + `data/kb/papers.jsonl` (story 1.2 schemas) | Read by `index`; never modified |
| I-2 | `configs/ablations.yaml` rows E1 (`use_sparse: true, use_dense: false`), E2 (`use_sparse: false, use_dense: true`), E3 (both true) | Loaded and validated by `core.config`; rows state both leg flags explicitly; other keys default |
| O-1 | `indexes/docstore/` | `manifest.json`, `chunk_ids.json` (row → chunk_id), `offsets.npy` (row → byte offset, int64), `papers_meta.json` (arxiv_id → `{title, year, source_link}`) |
| O-2 | `indexes/sparse/bm25s/` | bm25s saved index + `manifest.json` (`engine: "bm25s"`, `params: {method, k1, b}`, `n_chunks`) |
| O-3 | `indexes/dense/<model slug>/` (slug = model id with `/` → `__`) | `index.faiss` (IndexFlatIP) + `manifest.json` (`embedding_model`, `dim`, `n_chunks`) |
| O-4 | `Retriever.retrieve(query, k=10, *, query_id=None)` | `EvidencePack` with `min(k, len(fused))` hits ranked 1..n; `query` is the raw query; `query_id` defaults to `core.ids.adhoc_query_id(query)` = `"adhoc-"` + first 12 hex of SHA-1 over `normalize(query)` |
| O-5 | `search "<query>" --row E3 --k 10 [--json]` | Prints rank, rrf_score, leg scores, `title — section`, year per hit, then stage timings; `--json` prints the EvidencePack as JSON instead |
| E-1 | Row with both legs off | Config load fails naming the row id |
| E-2 | Unknown key in a row / unknown top-level key / duplicate row id / unknown `--row` | Load fails naming the key or id (unknown `--row` lists the available ids); CLI exit 3 |
| E-3 | Empty or whitespace-only query | `RetrievalInputError` (a `RetrievalStageError`); CLI exit 3 |
| E-4 | `k < 1` or `k > candidate_depth` | `RetrievalInputError` naming k and the depth |
| E-5 | Query whose tokens are all stopwords / under 2 chars / out of vocabulary | Sparse leg returns `[]` without error; dense leg still runs; with E1 the pack has zero hits |
| E-6 | Sparse candidates with score ≤ 0 | Dropped from the leg |
| E-7 | `candidate_depth` > number of chunks | Each leg returns at most `n_chunks` hits; no padding, no `-1` ids leak from FAISS |
| E-8 | Chunk returned by only one leg | Fused with that leg's term only; the other leg's score is `null` in `leg_scores` |
| E-9 | Equal scores within a leg / equal RRF scores | Order fixed by the tie rules above; two identical calls return identical packs (except timings) |
| E-10 | E1 vs E3 vs E2 | E1 hits carry `leg_scores.dense = null`, E2 carry `bm25 = null`; E1 order equals the BM25 leg order, E2 equals the dense leg order |
| E-11 | `chunks.jsonl` changed after `index` | Loading raises `IndexMismatchError` naming both hashes |
| E-12 | Configured `embedding_model` ≠ dense manifest model | `IndexMismatchError` naming both model ids |
| E-13 | Index component missing (never built, or row enables a leg that wasn't built) | `IndexMissingError` naming the path and `make index` |
| E-14 | `index` fails mid-build (exception in a component) | Exit 3; the previous component directory (if any) is unchanged; no temp directory is left behind |
| E-15 | Chunk whose `arxiv_id` is missing from `papers.jsonl` | `index` fails with exit 3 naming the arxiv_id (KB invariant violated) |
| E-16 | Model cannot be loaded (download failure) | Raises `RetrievalStageError` (stage `dense`) naming the model id; no fallback model |
| E-17 | Every `retrieve` call | `stage_timings_ms` has `fusion`, `hydrate`, `total`, plus `sparse` if the sparse leg is on and `dense_encode` + `dense_search` if the dense leg is on; values are floats ≥ 0; one INFO log line |
| E-18 | Same query, same index, called twice | Identical hit lists (chunk_ids, ranks, scores) |

</frozen-after-approval>

## Code Map

```text
pyproject.toml, uv.lock               # + bm25s==0.3.13, numpy, scipy, faiss-cpu==1.15.1, sentence-transformers==6.1.0, pyyaml (runtime); torch CPU wheels
Makefile                              # + `index` target -> uv run python -m paperpilot.retrieval.cli index --row E3
configs/ablations.yaml                # class 1: rows E1, E2, E3
src/paperpilot/core/config.py         # + RetrievalConfig, load_config_rows/get_row, BM25 params, embed batch size, default paths
src/paperpilot/core/schemas.py        # + EvidencePack, Hit, LegScores, EffectiveQuery, Gate, IndexManifest
src/paperpilot/core/ports.py          # SparseRetriever, DenseRetriever protocols; LegHit
src/paperpilot/core/timing.py         # stage timer writing into a timings dict
src/paperpilot/core/clients.py        # load_sentence_transformer(model_id) — the one HF loader, cached
src/paperpilot/core/errors.py         # + RetrievalStageError, RetrievalInputError, IndexMissingError, IndexMismatchError, ConfigError
src/paperpilot/core/ids.py            # + adhoc_query_id(query)
src/paperpilot/retrieval/tokenize.py  # the BM25 tokenizer + stopword set
src/paperpilot/retrieval/docstore.py  # chunk_store_hash, build/load docstore, hydrate(rows)
src/paperpilot/retrieval/sparse.py    # Bm25sRetriever: build/save/load/search
src/paperpilot/retrieval/dense.py     # Encoder protocol, SentenceTransformerEncoder, FaissDenseRetriever: build/save/load/search
src/paperpilot/retrieval/fusion.py    # rrf(leg_results, rrf_k)
src/paperpilot/retrieval/manifest.py  # write/read/check manifests, atomic component swap
src/paperpilot/retrieval/retriever.py # Retriever.from_config(row, kb_dir, index_dir, encoder=None).retrieve(query, k)
src/paperpilot/retrieval/cli.py       # index / search
tests/core/, tests/retrieval/         # local only (never committed): pinning tests per matrix row
```

## Tasks & Acceptance

1. **Deps + config file** — add the runtime deps (torch from the PyTorch CPU index on Linux/Windows), move `pyyaml` to runtime, `uv lock`; `configs/ablations.yaml` with E1–E3; `Makefile` `index` target. AC: `uv sync` ok; I-2.
2. **core additions** — `RetrievalConfig` + loader, EvidencePack models, `IndexManifest`, ports, timing, clients, errors, `adhoc_query_id`. AC: E-1, E-2; O-4 id format; EvidencePack round-trips through JSON.
3. **retrieval.tokenize + sparse** — AC: E-5, E-6, E-7, E-9 (sparse side); tokenizer pinned examples (case, `<S>` markup, stopwords, unicode letters).
4. **retrieval.dense** — FAISS exact index over injected encoder output. AC: E-7, E-9 (dense side), E-16.
5. **retrieval.docstore + manifest** — AC: O-1, E-11, E-12, E-13, E-14, E-15.
6. **retrieval.fusion + retriever** — AC: O-4, E-3, E-4, E-8, E-10, E-17, E-18.
7. **retrieval.cli + Makefile** — AC: O-2, O-3, O-5, CLI exit codes for E-2, E-3, E-13, E-14.
8. **Acceptance run** (real KB, 271,171 chunks) — `make index`: record per-component build time, peak RSS, disk size. Then, per row E1/E2/E3: cold-start (Retriever load) time and p50/p95 per stage over the 40 queries of the benchmark note. Known-item sanity: 20 papers drawn with a fixed seed, query = paper title; record the share with that paper in the top-10. E1 and E3 must reach ≥ 18/20; E2 is recorded only.

## Review Findings

Fresh-context review: edge-case hunter (H1–H20), test audit (T1–T16, ~70 mutations), acceptance auditor (A1–A5; no contract violated). Three Sonnet subagents, run concurrently.

- [x] [Review][Patch] P1 (H2) — CLI output printed outside the never-raises guard; a non-UTF-8 stdout or closed pipe gives a traceback + exit 1 (`retrieval/cli.py` `run_index_command`, `run_search_command`)
- [x] [Review][Patch] P2 (H3, A2, T2) — killed builds leak `.<name>.tmp-<pid>` / `.old-<pid>` forever, and a kill between the two renames leaves no component; sweep stale siblings at entry, restore an orphaned `.old-*`, never delete `old` when the restore fails (`retrieval/manifest.py` `atomic_component`)
- [x] [Review][Patch] P3 (H4) — query not NFC-normalized; NFD "café" tokenizes to `cafe` and misses (`retrieval/tokenize.py`)
- [x] [Review][Patch] P4 (H5) — sparse load never checks BM25 params or the tokenizer; a changed stopword list silently serves a stale index. Record a tokenizer fingerprint in `params`, compare params at load; pass `engine` in the docstore and dense loads (`sparse.py`, `manifest.py`, `docstore.py`, `dense.py`)
- [x] [Review][Patch] P5 (H6) — dense load and search don't check `index.d` vs manifest `dim` / query vector dim; mismatch is a bare `AssertionError` (`dense.py`)
- [x] [Review][Patch] P6 (H7) — encoder output not checked for finiteness / unit norm (`dense.py` `_check_vectors`)
- [x] [Review][Patch] P7 (H8, H18) — fail fast: build constructs the encoder only after docstore + sparse; `from_config` loads the model before checking the dense index. No progress logging during the multi-hour dense build (`cli.py` `build_indexes`, `retriever.py` `from_config`, `dense.py` `build`)
- [x] [Review][Patch] P8 (H1) — MiniLM's 256-word-piece window truncates long chunks silently; record `max_seq_length` in the dense manifest `params` and log it at build (`dense.py`)
- [x] [Review][Patch] P9 (H11) — `hydrate` failures after a KB rewrite surface as raw `JSONDecodeError` (`docstore.py` `hydrate`)
- [x] [Review][Patch] P10 (H12) — chunk lines not schema-validated; a missing key is a bare `KeyError` with no file/line (`docstore.py` `iter_chunks`)
- [x] [Review][Patch] P11 (H20) — docstore load doesn't check `chunk_ids` / `offsets` / `n_chunks` agree (`docstore.py` `Docstore.load`)
- [x] [Review][Patch] P12 (H15) — a query with no BM25 tokens returns nothing silently; log a warning (`sparse.py` `search`)
- [x] [Review][Patch] P13 (A1, T11) — E-12 only reachable via the manifest (dense dir is keyed by the model slug, so another model is E-13); the missing-dense message lists the models present under `indexes/dense/`. Spec E-12 clarified in the Change Log
- [x] [Review][Patch] P14 (H19) — pin `numpy`/`scipy`/`torch` in `pyproject.toml` to the locked versions; `Makefile` `ROW ?= E3`
- [x] [Review][Patch] P15 (A5) — module conventions: logger in `core/ports.py`, `core/timing.py`; docstring in `retrieval/__init__.py`
- [x] [Review][Patch] P16 (T1, T3, T4, T5, T7, T8, T9, T10, T12, T13, T14, T15 `match=` nits) — test gaps from the mutation run (tests stay local)
- [x] [Review][Patch] P17 (A3) — acceptance record gets fusion/hydrate p95; the 40 benchmark queries are listed in the benchmark note; stale `rank_bm25 first` text in `docs/` and the top-50 RRF note in `pipeline-stages.md` updated
- [x] [Review][Defer] H9 — sparse build holds every token as its own `str` (5.6GB peak measured; fits the team's 16GB laptops). Target: a later retrieval performance pass
- [x] [Review][Defer] H8 (part) — idempotent rebuild (skip unchanged components) and per-batch resume of the dense build. Target: when index rebuilds become frequent (story 1.5 bge-m3)
- [x] [Review][Defer] H10 — the full SHA-256 of `chunks.jsonl` on every load (<1s measured inside the 0.7s/3.8s cold starts). Target: later performance pass
- [x] [Review][Defer] H14, A4 — the dense leg cuts top-k inside FAISS before the `(-score, row)` sort, so exact ties straddling position 300 are FAISS's pick (deterministic on one build; E-18 holds). Target: story 1.4 if eval shows boundary ties
- [x] [Review][Defer] H16 — `embedding_model` id validation, `candidate_depth` upper bound, single-sourcing the `"bm25s"` Literal and leg names. Target: story 1.5 (adds models and flags)
- [x] [Review][Defer] H17 — pin the HF model revision in the manifest; query/document prefixes for asymmetric models. Target: story 1.5 (bge-m3)

Dismissed: H13 cross-component transactions / concurrent searches during a rebuild (concurrent-file-locking precedent: offline single-laptop envelope); H10 TOCTOU with a concurrent `make kb` (same precedent); argparse usage errors exiting 2 (argparse convention, documented in `main`); noisy third-party INFO logs on stderr (stdout stays clean for `--json`); T6 the min-leg-rank tie term is unreachable with integer ranks (harmless, spec-mandated tie rule).

Counts: 17 patch groups, 6 deferred, 5 dismissed.

## Spec Change Log

- 2026-10-15: Initial frozen block from project spec CAP-2 + stories.yaml story 3 + pipeline-stages + stack.md + spine AD-1/3/4/5, and the sparse-engine benchmark gate (bmad-spec, in-session per the story-1.2 precedent). Resolves the spine Deferred item "Sparse engine final pick" → `bm25s`.
- 2026-10-16: Build amendment — `torch` added as a direct (unpinned) runtime dependency. uv applies `[tool.uv.sources]` only to direct dependencies, so with torch only transitive the lock took the CUDA build plus ~16 nvidia packages; as a direct dependency it resolves to `2.14.1+cpu` from the PyTorch CPU index (`sys_platform != 'darwin'`). No new package enters the tree. Spec interpretations by the builder, accepted: `DenseRetriever` port = `encode(query)` + `search(vector, depth)` (separate `dense_encode`/`dense_search` timings, and the shape HyDE needs in 1.5); dense/docstore manifests use `engine: "faiss-flat-ip"` / `"docstore"` with empty `params`; `EMBED_BATCH_SIZE = 128`; device left to sentence-transformers. KEEP: torch from the CPU index; the dense port keeps encode and search separate.
- 2026-10-16: Post-review amendment — P1 CLI output written inside the never-raises guard (`--json` ASCII-safe); P2 `atomic_component` restores an orphaned `.old-*` and sweeps stale `.tmp-*`/`.old-*` siblings from any pid, never deleting `old` when its restore fails; P3 the tokenizer NFC-normalizes first; P4 the sparse manifest `params` carries a tokenizer fingerprint and the loader compares `{method, k1, b, tokenizer}`, docstore/dense loads check `engine`; P5–P6 dense dim, finiteness and unit-norm checks; P7 encoder built before any component, dense index checked before the model loads, progress logged every 100 batches; P8 dense manifest records `max_seq_length`; P9–P11 docstore hydrate/iter/load failures are typed with path:line, chunk lines validated by `core.schemas.Chunk`; P12 warning on token-less queries; P13 a missing dense component lists the models present. E-12 clarified: the dense directory is keyed by the model slug, so a different configured model surfaces as E-13 (`IndexMissingError` listing the models present); `IndexMismatchError` on `embedding_model` fires when a manifest disagrees with its directory. P14 pins numpy 2.4.6 / scipy 1.17.1 / torch 2.14.1 (the lock collapses the per-Python-version splits). The sparse index was rebuilt (`index --row E1`, 59s) for the fingerprint; the dense index was kept (its loader checks are unchanged in what they read). Acceptance re-run after the patches: E1/E2/E3 20/20, total p50 1.2 / 55.2 / 53.8ms. KEEP: the CLI never raises, including on output; stale build siblings are swept and an orphaned previous component is restored, never deleted; the tokenizer fingerprint is checked at load.

## Design Notes

- **Why bm25s:** see the benchmark note — serving RSS 142MB, cold start 0.37s, p50 9ms on the real 271k chunks, vs `rank_bm25` 3.1GB / 4.1s / 334ms. Same top-5 across engines, so the decision is on resources. The spine Stack row `rank-bm25 0.2.2` and stack.md's sparse row are updated to `bm25s 0.3.13` in this story.
- **RRF fuses each leg's full `candidate_depth` list (300).** pipeline-stages' "top-50 cut feeds RRF" belongs to the rerank path (story 1.5, `rerank_depth`). Fusing the full depth keeps Recall@100 measurable for E1–E3.
- **MiniLM truncation:** `all-MiniLM-L6-v2` reads at most 256 word pieces, so the dense leg sees the header prefix plus roughly the first 150–200 words of a 512-token chunk. This is a known baseline limitation for the report; `bge-m3` (8192) is the upgrade path.
- **Docstore by byte offset:** hydrating k hits seeks into `chunks.jsonl` instead of holding 271k chunk texts in RAM (~600MB). The manifest hash check guarantees the offsets still match the file.
- **`rrf_score` in Hit:** AD-3 lists the hit fields; `rrf_score` is added at v1 (before any consumer exists) because the story-1.4 run file needs a fused score. Recorded here, not a later bump.
- **Dataset markup** (`<S>`, `@xmath`) is still in chunk text (story 1.5 cleans it). The tokenizer's 2-character floor drops the `s` from `<S>`; `xmath0`-style tokens remain and get low IDF.
- **Torch CPU wheels:** the spine's envelope is CPU-first (Colab for GPU bursts). Pulling torch from the PyTorch CPU index keeps the lock small and the same on every teammate's laptop.

## Verification

1. `uv sync && uv run pytest tests/ -q` — all green, offline (fake encoder; synthetic chunks/papers fixtures).
2. Smoke on a synthetic KB in `/tmp/claude-…/scratchpad`: `index --row E3 --kb-dir <tmp>/kb --index-dir <tmp>/idx` then `search "…" --row E1|E2|E3` with a fake or real encoder; exit 0; `--json` parses as an EvidencePack.
3. `make index` on the real KB, then the Task 8 measurements; figures recorded below.

### Acceptance run record (task 8, 2026-10-16)

Real KB: 271,171 chunks (`chunk_store_hash` 9eb28acf…be30f), laptop CPU (16 threads), torch CPU wheels. Full build `index --row E3`, run from the activated `.venv`:

- Build time: docstore 2.6s, sparse (bm25s) 49.6s, dense (MiniLM, CPU) 8,573.7s (~2h23m; ~40 min of it shared the CPU with an unrelated pytest run). Wall clock 2:23:50.
- Peak RSS for the whole build: 5.64GB (dominated by the sparse tokenized corpus).
- Disk: docstore 9.2MB, sparse 268MB, dense 398MB (271,171 × 384 float32, IndexFlatIP).
- An earlier build was killed mid-dense by a session exit; it left `indexes/dense/.…tmp-<pid>` behind (the previous component was untouched, as E-14 requires).

Serving, 40 benchmark queries per row, k = 10, after one warm-up query (ms):

| Row | Cold start | sparse p50/p95 | dense_encode p50/p95 | dense_search p50/p95 | fusion p50/p95 | hydrate p50/p95 | total p50/p95 | Peak RSS | Title known-item top-10 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| E1 | 0.73s | 0.70 / 0.94 | — | — | 0.26 / 0.31 | 0.17 / 0.22 | 1.14 / 1.57 | 445MB | 20/20 |
| E2 | 3.79s | — | 19.5 / 24.3 | 35.9 / 41.8 | 0.42 / 0.43 | 0.33 / 0.44 | 55.6 / 65.9 | 995MB | 20/20 |
| E3 | 3.88s | 1.12 / 1.55 | 16.6 / 22.6 | 35.2 / 43.2 | 0.79 / 0.87 | 0.34 / 0.37 | 53.6 / 65.6 | 1,318MB | 20/20 |

Queries: the 40 listed in `research/sparse-engine-benchmark-2026-10-15.md`. Known-item check: 20 papers sampled with `random.Random(13)`, query = paper title; E1 and E3 ≥ 18/20 required — met (20/20 each).

## Suggested Review Order

Post-review patches first: `retrieval/manifest.py` `atomic_component` (P2), `retrieval/cli.py` `_emit` (P1), `retrieval/sparse.py` `load`/params check + `tokenize.py` `tokenizer_fingerprint` (P3–P4), `retrieval/dense.py` `_check_vectors`, `load(encoder_factory)` (P5–P8), `retrieval/docstore.py` `iter_chunks`/`Docstore.load`/`hydrate` (P9–P11). Then the original order:

1. `src/paperpilot/retrieval/retriever.py` — `Retriever.from_config`, `retrieve` (timings, hydration, pack assembly)
2. `src/paperpilot/retrieval/fusion.py` — `rrf` (tie rule, per-leg scores)
3. `src/paperpilot/retrieval/sparse.py` — `Bm25sRetriever.search` (score > 0, exact `(-score, row)` cut)
4. `src/paperpilot/retrieval/dense.py` — `FaissDenseRetriever.build/search`, `SentenceTransformerEncoder`
5. `src/paperpilot/retrieval/manifest.py` — `check_manifest`, `atomic_component`
6. `src/paperpilot/retrieval/docstore.py` — `build_docstore`, `Docstore.hydrate`
7. `src/paperpilot/core/config.py`, `core/schemas.py` — `RetrievalConfig` + loader, `EvidencePack`, `IndexManifest`
8. `src/paperpilot/retrieval/cli.py`, `pyproject.toml` (torch CPU index)
