---
id: SPEC-story-1-3-baseline-retrieval
companions: [../spec-paperpilot-rag/SPEC.md, ../spec-paperpilot-rag/pipeline-stages.md, ../spec-paperpilot-rag/stack.md, ../../planning-artifacts/architecture/architecture-NLPProject-2026-10-12/ARCHITECTURE-SPINE.md]
sources: [../../planning-artifacts/research/sparse-engine-benchmark-2026-10-15.md]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the contract for story 1.3. The auditable house contract (frozen block, edge-case matrix) is `_bmad-output/implementation-artifacts/spec-1-3-baseline-retrieval.md`; the project spec and the architecture spine bind anything this kernel condenses.

# Story 1.3 — Baseline retrieval: BM25 + dense + RRF hybrid

## Why

CAP-2 is the course-designated baseline (E1 BM25, E2 dense, E3 hybrid) that every later number is compared against: the eval harness (1.4) scores these rows, the innovations (1.5) toggle on top of them, and the generator (1.7) consumes their `EvidencePack`. The legs must sit behind ports and config rows from day one, or every later ablation becomes a code fork.

## Capabilities

- **CAP-2: Baseline retrieval (sparse + dense + hybrid)**
  - **intent:** BM25 on `bm25s` (proper inverted-index tooling, never SQL `LIKE`), dense retrieval with `all-MiniLM-L6-v2` on an exact FAISS index, and Reciprocal Rank Fusion as the hybrid leg.
  - **success:** one `retrieve(query, k)` call returns the fused ranking as an `EvidencePack`; each leg switches on/off by config row (E1/E2/E3); every stage's latency is recorded in the pack and logged.

## Constraints

- Ports in core (`SparseRetriever`, `DenseRetriever`); the engine and model are config values (AD-1, AD-4).
- Config rows in `configs/ablations.yaml`, pydantic-validated, unknown keys rejected (AD-4).
- `EvidencePack` v1 is the only retrieval output (AD-3).
- Index artifacts are class 3 under `indexes/` with manifests; loaders refuse on chunk-store or model mismatch (AD-5); exact `IndexFlatIP` only.
- Offline tests with an injected fake encoder; no network.

## Non-goals

- Reranking, query rewriting, section weighting (1.5); eval harness and qrels (1.4); UI (1.9).
- IVF / approximate dense search (reserved for the Q4 scalability discussion).

## Success signal

`make index` builds all three components on the real KB; E1/E2/E3 answer queries through one `retrieve(query, k)` call with per-stage timings; a title known-item check puts the paper in the top-10 for ≥ 18/20 titles on E1 and E3; `uv run pytest tests/ -q` is green offline.

## Assumptions

- The full-corpus index build runs on this laptop on CPU (MiniLM over 271k chunks); Colab is not needed for the baseline model.
