# PaperPilot: Tech Stack (companion to SPEC.md)

Chosen for $0 budget, laptop-CPU-first compute, and the brief's "implement and explain it yourselves" rule. Every external dependency is swappable behind a Python interface.

| Component | Choice | Rationale / swap rule |
| --- | --- | --- |
| Language | Python 3.11+ (uv-managed venv) | Team-shared skillset; repo already uses uv scripts |
| Paper acquisition | **HF `scientific_papers` arxiv split** (official S3 zip, ~3.5GB; 200-paper slice verified bytes-on-disk 2026-09-18). Fallbacks: S2AG `s2orc_v2` (needs S2 API key) → public GCS `arxiv-dataset` PDFs (no auth, parse-heavy) | Spike verdict: 99% sectioned pre-parsed JSONL; ranged-zip slicer script probes 200 papers for ~21MB; no live crawling; evidence in `_bmad-output/planning-artifacts/research/data-spike-2026-09-18.md` |
| PDF/text parsing | Not needed on the winning path (pre-parsed JSONL). PyMuPDF is available if the GCS-PDF fallback activates; GROBID-class section parsing is out of $0/laptop scope | Parsing PDFs is a time sink; prefer pre-parsed text with section structure |
| Cleaning/chunking | Custom Python (boilerplate strip, dedup by hash, structure-aware 256-512-token chunks + overlap + section header prefix) | Chunking is a graded design choice: must be ours and documented |
| Sparse retrieval | Ladder (benchmark-gated at Story 3 prep): `rank_bm25` first → SQLite FTS5 `bm25()` if too slow → Elasticsearch last resort (pinned + docker-compose + `make index` rebuild); Pyserini skipped | Zero-ops first: BM25 transparency is graded; engine hidden behind `SparseRetriever` interface, swap = config row |
| Dense retrieval | sentence-transformers `all-MiniLM-L6-v2` (baseline), `BAAI/bge-m3` (Colab T4 upgrade) | CPU-feasible baseline; upgrade path measured, not assumed |
| Vector index | FAISS `IndexIVFFlat` (nlist ≈ 1000, nprobe ≈ 50) for ~500k chunks; exact `IndexFlatIP` as config fallback | Local, no server; IVF is approximate; `index.train(vectors)` required before `add()` |
| Hybrid fusion | Reciprocal Rank Fusion (k=60) | Course-designated approach; ~20 lines, explainable |
| Re-ranker | `BAAI/bge-reranker-v2-m3` cross-encoder | Inference-only, biggest single retrieval gain |
| Generator | Ollama local (Qwen2.5-7B or Llama-3.1-8B) behind `Generator` interface; free-tier hosted API (e.g., Gemini Flash) optional for demo/RAGAS | Pluggable by constraint; local model guarantees offline reproducibility |
| Retrieval metrics | `ir_measures` | P@K, Recall@K, MRR, nDCG@10 straight from qrels |
| RAG metrics | RAGAS | Faithfulness, answer relevance, context precision/recall |
| UI | Streamlit | Proposal's choice; brief says keep it simple |
| Orchestration | Plain Python modules + Makefile (`make kb / index / eval / ui`) | No LangChain/LlamaIndex, because the brief wants the stages implemented and explained by us; frameworks would obscure exactly what is graded |

**Rule:** any component swap (sparse engine, embedding model, generator) happens behind its interface with a config flag, never a code fork; every swap is an ablation row, not a rebuild.
