# PaperPilot spec-pattern digest (binding conventions; refreshed each story, ≤60 lines)

Sources: `_bmad-output/specs/spec-paperpilot-rag/` (SPEC.md + companions) and
`_bmad-output/planning-artifacts/architecture/architecture-NLPProject-2026-10-12/ARCHITECTURE-SPINE.md`.
Full invariants live in the spine (AD-1…AD-6) — this digest condenses; the spine wins on conflict.

## Layers & ports (AD-1)
- `core < kb < retrieval < generation < drivers (ui, evaluation)`; imports point strictly forward.
- Ports in core: `SparseRetriever`, `DenseRetriever`, `Reranker`, `QueryRewriter`, `Generator`, `EvidencePack`.
- Swaps are config rows, never code forks; engine choice hidden behind the port.

## chunk_id (AD-2)
- ONLY `paperpilot.core.ids.chunk_id(arxiv_id, section_name, text)`: leading 16 hex of SHA-1 over
  UTF-8 `arxiv_id + "\x1f" + section_name + "\x1f" + normalize(text)`; normalize = NFC + whitespace collapse.
- KB build deterministic; `make eval` fails loudly on dangling chunk_ids.

## EvidencePack (AD-3)
- `{pack_version, query_id, query, effective_queries[], hits[], stage_timings_ms{}, gate}`; additive-only changes bump `pack_version`.
- `hits[]` = `{rank, chunk_id, text, header_prefix, arxiv_id, title, section_name, year, source_link, leg_scores{bm25,dense}, rerank_score}`.
- Citations `[n]` valid iff `1 ≤ n ≤ len(hits)`.

## Config rows (AD-4)
- `configs/ablations.yaml`; pydantic-validated at load; unknown keys rejected; rows mirror the E-ladder; report comparisons differ by exactly one flag.

## Artifact classes (AD-5)
- Class 1 (git-tracked, human-written): `configs/`, `data/eval/` — never machine-overwritten.
- Class 2 (`make kb` only): `data/raw/`, `data/kb/{papers,chunks}.jsonl`, `kb_stats.json`.
- Class 3 (tool-written, deletable): `indexes/`, `reports/`; index manifests `{created, embedding_model, dim, chunk_store_hash, config_row}`; loaders refuse on hash/model mismatch; dense index default exact `IndexFlatIP`.

## Reports (AD-6)
- `reports/metrics.json` single writer = `make eval` merge; sections: B→`retrieval.json`, C→`answer.json`+`speed.json`; each section records config row id + git commit.

## Naming & formats
- Package `paperpilot` under `src/`; flags snake_case: `use_sparse`, `use_dense`, `rrf_k`, `use_rerank`, `rerank_model`, `rerank_depth`, `candidate_depth`, `use_hyde`, `use_multi_query`, `use_section_weight`, `section_weights`, `gate_tau`, `generator_model`.
- JSONL UTF-8; JSON manifests/metrics; ISO-8601 UTC; timings float ms; English-only corpus (clean stage drops non-English).
- KB schemas per `pipeline-stages.md`: paper = `arxiv_id, title, authors[], year, abstract, sections{...}, source_link, license, categories[]`; chunk = `chunk_id, arxiv_id, section_name, section_rank, text, n_tokens, header_prefix`.

## Stack pins (spine Stack table; `uv.lock` is the authority)
- Python 3.11+ (uv); pydantic 2.14.1; sentence-transformers 6.1.0; faiss-cpu 1.15.1; bm25s 0.3.13 (replaced rank-bm25 at the story-1.3 gate); ir-measures 0.4.3; ragas 0.4.3; streamlit 1.65.0; HF `armanc/scientific_papers` arxiv split + `gs://arxiv-dataset/metadata-v5/arxiv-metadata-oai.json` join (pre-2007 ids re-slash).
- No orchestration frameworks; Ollama only local server; keys from git-ignored `.env`.

## Patterns minted by story 1.2 (binding for later stories)
- Writes are atomic: tmp file + `os.replace`; rebuilds wholesale, never in-place appends.
- Every drop/dup/malformed path gets a named provenance counter; nothing is silently discarded.
- CLI `run_<x>_command` catches unexpected exceptions → exit 3 (never raises); stage errors carry offending values.
- Mid-build contract changes need owner approval and a dated Spec Change Log entry with a "KEEP:" line.
- House spec ends with an "Acceptance run record" on the real corpus (figures + peak RSS).
- Real KB (cs.*, train+val+test): 12,350 papers, 271,171 chunks (max 561 tokens), years 1994–2017; build peak RSS ~2.6GB.
