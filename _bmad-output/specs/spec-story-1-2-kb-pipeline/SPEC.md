---
id: SPEC-story-1-2-kb-pipeline
companions: [../spec-paperpilot-rag/SPEC.md, ../spec-paperpilot-rag/pipeline-stages.md, ../spec-paperpilot-rag/stack.md, ../../planning-artifacts/architecture/architecture-NLPProject-2026-10-12/ARCHITECTURE-SPINE.md]
sources: [../../planning-artifacts/research/data-spike-2026-09-18.md]
---

> **Canonical contract.** This SPEC and the files in `companions:` are the complete, preservation-validated contract for story 1.2. Companion paths resolve from this folder; the parent project spec (`spec-paperpilot-rag`) and the architecture spine bind anything this kernel condenses.

# Story 1.2 — Knowledge-base pipeline: acquire, join, clean, dedup, chunk, stats

## Why

**Mandate + dependency.** The AI6127 assignment (CAP-1) requires a ≥10k-paper knowledge base as the graded substrate of the whole system, and sprint story 1.2 is the first code-bearing story: retrieval (1.3), the eval harness (1.4), and citations (1.7) all consume exactly the artifacts this story emits. Everything downstream joins on `chunk_id`, so the pipeline must be deterministic and the paper metadata complete from day one — a KB rebuilt with drifting ids or null titles would silently invalidate every qrel and citation later.

## Capabilities

- **CAP-1: One-command deterministic KB rebuild**
  - **intent:** `make kb` rebuilds the entire knowledge base from the verified raw source — acquire → metadata join (+ cs.* filter) → clean → dedup → structure-aware chunk → stats — emitting `data/kb/papers.jsonl`, `data/kb/chunks.jsonl`, and `kb_stats.json` with zero human steps.
  - **success:** A full-corpus run reports in `kb_stats.json`: `papers ≥ 10,000` and `words ≥ 100,000` (assignment floors); **zero** papers emitted with null title/year/categories (citations resolve 100%); chunk token counts inside the 256–512 band with ~15% overlap on oversized sections; and a repeat run on the same inputs mints identical `chunk_id`s (determinism). All drop/duplicate/malformed events are counted in `kb_stats.json`, never hidden.

## Constraints

- **`chunk_id` has exactly one minter:** `paperpilot.core.ids.chunk_id(arxiv_id, section_name, text)` per spine AD-2 (leading 16 hex of SHA-1 over `arxiv_id + "\x1f" + section_name + "\x1f" + normalize(text)`; normalize = NFC + whitespace collapse). No other module hashes; stored chunk text is the normalized text so id and text always agree.
- **Artifact classes per AD-5:** `make kb` writes only class 2 (`data/raw/`, `data/kb/`); class 1 (`data/eval/`) is never touched; outputs land atomically (tmp file + `os.replace`); rebuilds are wholesale.
- **Bounded RAM:** the ~3.5GB `train.txt` member and the ~4.5GB metadata JSONL are streamed line-by-line; neither is ever fully loaded.
- **No null metadata escapes:** a paper whose metadata row is missing is dropped and counted (`dropped_no_metadata`), never emitted with nulls.
- **English-only corpus:** the clean stage drops non-English papers via a documented heuristic (no new heavy deps) and counts them.
- **Offline tests:** pytest runs on synthetic mini-corpus fixtures only, no network; the full-corpus `make kb` run is the acceptance run, not a test.
- **Bootstrap deps minimal + pinned:** `pydantic 2.14.1` runtime (+ `pytest`, `pyyaml` dev) in `pyproject.toml` with committed `uv.lock`; heavy deps join in their own stories.
- **Metadata join is exact:** dataset ids are re-slashed pre-2007 (`nlin0608019` → `nlin/0608019`) and metadata ids stripped of version suffix (`0704.0001v2` → `0704.0001`) before matching; title/authors/year/categories/license come only from `gs://arxiv-dataset/metadata-v5/arxiv-metadata-oai.json`.
- **cs.* filter with a measured contingency:** filter = any `cs.*` category (~16k expected pre-clean); if the pre-clean yield is < 12k, widen to all arXiv categories and record composition + the widened flag in `kb_stats.json`.

## Non-goals

- No retrieval, indexing, or embedding (story 1.3+); no eval harness (1.4).
- No GCS-PDF fallback activation; the S3 zip path is the only acquisition route this story builds.
- No chunking-variant ablation rows (fixed-512, no-header) — spine Deferred.
- No AI/ML/NLP-only subcollection export — the primary subcollection appears as composition stats in `kb_stats.json` only.

## Success signal

From a clean clone on the laptop: `make kb` runs end-to-end unattended and lands the three artifacts with the CAP-1 success figures; `uv run pytest tests/ -q` is green offline on synthetic fixtures; rebuilding a small slice twice yields byte-identical `chunk_id` sequences.

## Assumptions

- The acceptance run executes on this laptop (~8GB download+extract headroom; 289GB free) — no Colab needed for the KB.
- The S3 zip and GCS metadata object remain publicly reachable as measured by the 2026-09-18 spike; a failure there is an environment failure, escalated to the owner, not a scope change.
