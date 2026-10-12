# Review — Stack Version Verification (ARCHITECTURE-SPINE.md)

- **Reviewer role:** verification subagent (read-only; spine untouched)
- **Date:** 2026-10-12
- **Scope:** Stack table, AD-1/AD-4 rules, Deferred ladder entries naming external technologies
- **Method:** every claim below checked against live web sources (PyPI JSON API, HuggingFace Hub pages, Ollama library pages, official docs: ir-measur.es, sqlite.org/fts5.html, github.com/facebookresearch/faiss wiki, huggingface.co/docs/datasets). No packages were installed; runtime behavior was not exercised.

## Verdict

**PASS WITH FINDINGS** — every pinned version exists and is plausible; several are the current latest. No technology has disappeared, and no breaking-major-version mismatch was found against the pins. Findings are risk notes (one open CVE, one script-based-dataset friction, transitive-dependency gaps), not blockers.

## Per-technology status

| # | Technology (pin) | Status | Evidence (checked 2026-10-12) |
|---|---|---|---|
| 1 | pydantic 2.14.1 | **OK — current latest** | PyPI JSON: 2.14.1 exists, uploaded 2026-10-11; `/pypi/pydantic/json` `info.version` = 2.14.1 (last 2.x releases: 2.13.3→2.14.1). `requires_python >=3.10`, fine with Python 3.11+. |
| 2 | sentence-transformers 6.1.0 | **OK — exists (2026-09-18)** | PyPI JSON resolves; quickstart in its README loads `all-MiniLM-L6-v2`; BAAI/bge-m3 HF page tagged `sentence-transformers` with an official `SentenceTransformer("BAAI/bge-m3")` snippet (32.8M downloads/mo). Note: 6.1.0 requires `transformers>=5.0.0,<6` and `torch>=2.2` (see F3). |
| 3 | faiss-cpu 1.15.1 | **OK — exists (2026-09-16)** | PyPI JSON resolves; wheels for cp310–cp314 Linux/macOS/Windows. `IndexIVFFlat` + `train()` → `add()` workflow documented verbatim in the official FAISS wiki "Faster search" page (quantizer = IndexFlatL2, `nlist`/`nprobe`). |
| 4 | rank-bm25 0.2.2 | **OK — exists; dormant** | PyPI JSON resolves. Last (and only recent) release uploaded **2022-02-16** — ~4.5+ years without a release. Pure-Python + numpy, tiny, stable; acceptable for a 6-week project (see F4). |
| 5 | ir-measures 0.4.3 | **OK — exists (2025-11-25), latest 0.4.x** | PyPI JSON resolves; official measures docs confirm `P` (Precision@k), `R` (Recall@k), `RR`/alias `MRR`, `nDCG` with `cutoff` — all four required metrics supported. |
| 6 | ragas 0.4.3 | **OK — exists (2026-01-13); latest = 0.4.3; see CVE finding F1** | PyPI JSON resolves and `info.version` = 0.4.3 (0.4.x line: 0.4.0–0.4.3). GitHub tag `v0.4.3` source tree contains `_faithfulness.py`, `_answer_relevance.py`, `_context_precision.py`, `_context_recall.py` under `src/ragas/metrics/` — all four named metrics still present in this version. |
| 7 | streamlit 1.65.0 | **OK — current line (2026-10-02)** | PyPI JSON resolves; requires Python >=3.10 — compatible with the spine's Python 3.11+. |
| 8 | Ollama `qwen2.5:7b` / `llama3.1:8b` | **OK — both tags still listed** | ollama.com/library/qwen2.5 shows `qwen2.5:7b` (4.7GB, 32K ctx); /library/llama3.1 shows `llama3.1:8b` (4.9GB, **128K ctx**). Pages marked "updated 2 years / 1 year ago" — frozen but pullable. |
| 9 | BAAI/bge-reranker-v2-m3 | **OK — exists, loadable** | HF model page live; tagged `sentence-transformers` with official `CrossEncoder("BAAI/bge-reranker-v2-m3")` snippet; 16M downloads/mo; Apache-2.0; 0.6B params (F32). |
| 10 | HF dataset `armanc/scientific_papers` (arxiv) | **OK — exists; script-based caveat (F2)** | HF dataset page live; arxiv split documented (train 203,037 / val 6,436 / test 6,440; 4.5GB download, 7.58GB generated). Viewer is **disabled**: "this dataset repo requires arbitrary Python code execution" — loading-script dataset needing `trust_remote_code=True`. Consistent with the Week-0 spike (2026-09-18) having verified downloadability. |
| 11 | SQLite FTS5 `bm25()` | **OK — real, documented** | sqlite.org/fts5.html §5.1.1 "The bm25() function": built-in auxiliary function, `ORDER BY bm25(ft)`, k1=1.2 / b=0.75 hard-coded, result sign-flipped so lower = better. A valid fallback rung in the Deferred sparse-engine ladder. |

## Findings

### F1 — MEDIUM: ragas 0.4.3 has an open SSRF CVE with no fixed release
PyPI metadata for ragas 0.4.3 lists **CVE-2026-6587 / GHSA-95ww-475f-pr4f** (PYSEC-2026-3046): SSRF in `_try_process_local_file/_try_process_url` of `src/ragas/metrics/collections/multi_modal_faithfulness/util.py`, affecting versions **up to and including 0.4.3**, `fixed_in: []` — and 0.4.3 *is* the latest release, so there is currently no patched version to upgrade to. Mitigations for this project: laptop-local, no untrusted multi-modal contexts, the vulnerable path is the **multi-modal** faithfulness util while PaperPilot uses text-only faithfulness. Risk accepted is probably fine, but the team should make that acceptance explicit, and re-check for a 0.4.4+ before Week 5 eval harness work.

### F2 — MEDIUM-LOW: `armanc/scientific_papers` is a loading-script dataset, and ragas forces `datasets>=4.0.0` into the same env
Two verified facts interact: (a) the HF dataset requires executing its loading script (`trust_remote_code=True`; HF viewer disabled, HF's own card suggests parquet conversion); (b) ragas 0.4.3 declares `datasets>=4.0.0` as a hard dependency. The spine's Stack table does not pin `datasets` at all. The Week-0 spike (2026-09-18) proved a working combination exists — but the spine should pin `datasets` to that exact spike-tested version in the uv lockfile, or `make kb` reproduction may silently break when a fresh resolve picks an incompatible `datasets` major.

### F3 — LOW: sentence-transformers 6.x rides on transformers v5 / torch ≥2.2; transitive pins absent from the Stack table
sentence-transformers 6.1.0 requires `transformers>=5.0.0,<6.0.0`, `torch>=2.2`, `huggingface-hub>=1.3.0,<2`. None of `torch`, `transformers`, `datasets`, `numpy` appear in the spine's Stack table even though the manifest rule (AD-5) keys reproducibility off `embedding_model`. The lockfile will resolve them, but the spine should either name them or explicitly delegate version capture to the uv lock + index manifest.

### F4 — LOW: rank-bm25 is dormant (last release 2022-02-16)
Not abandoned-broken — it is a ~200-line pure-Python+numpy package that still installs — but it has had no release in ~4.5 years and predates numpy 2.x, so any numpy-2 incompatibility would surface as a runtime, not install, failure. Acceptable for a 6-week course project, and the Deferred ladder's SQLite FTS5 fallback rung (bm25() verified above) is a genuine, documented de-risk. Suggest a 10-minute smoke test (`BM25Okapi.get_scores` under the locked numpy) in Story 3 prep rather than waiting for the benchmark gate.

### F5 — INFO: ragas stewardship moved from `explodinggradients` to `vibrantlabsai`; Ollama model pages are frozen but live
ragas PyPI/GitHub/docs now point at `github.com/vibrantlabsai/ragas` — any spine companion docs citing the old org should be updated to avoid dead links. Both Ollama tags remain pullable; note `llama3.1:8b` advertises 128K context vs `qwen2.5:7b`'s 32K, which may matter for the Week-3 generator choice given the evidence-pack sizes.

## Could not verify via web (honest gaps)

- **Runtime install/execution** of any pin in the actual project venv — this was a read-only review; no `pip/uv` resolutions were performed. Version *existence* and *declared compatibility* are verified; successful co-installation is not.
- **Which exact `datasets` version the Week-0 spike used** — taken on faith from the task statement (spike verified 2026-09-18); recommend recording it per F2.
- **rank-bm25 repo commit activity on GitHub** — not fetched; dormancy claim rests on PyPI release dates (last upload 2022-02-16), which are sufficient for the finding as stated.
- **Whether a ragas CVE fix ships after 0.4.3** — as of this check `fixed_in` is empty and 0.4.3 is latest; re-check at eval-harness time (F1).
