# Week-0 Dataset Spike — Findings (2026-09-18)

> Story 1 of `spec-paperpilot-rag/stories.yaml` · plan: `plan-week0-dataset-spike-2026-09-18.md`
> All evidence bytes-on-disk under `research/spike/data/` (gitignored scratch); scripts under `research/spike/scripts/`.

## Decision

**Winner: HF `scientific_papers` — arxiv split (Cohan et al. 2018), served from the official S3 zip.**
Fallback order: (1) S2AG `s2orc_v2` (S2ORC successor) if an S2 API key lands; (2) GCS `arxiv-dataset` PDFs (public, no auth) if both text-level sources fail.

Decision rule applied: no candidate failed download → survivors ranked on full-text + section structure + license → ties broken by smaller/simpler. `scientific_papers` wins on section structure (99% vs 36% machine-detectable) and parse effort (pre-parsed JSONL = zero parsing); the S2AG full corpus now requires an API key (issuance latency incompatible with the 2026-09-19 team-split deadline), and PDFs lose on parse effort + redistribution terms for the CAP-8 data zip.

## Score matrix

| Criterion | S2ORC (S2AG `s2orc_v2`) | HF `scientific_papers` | Kaggle / GCS arXiv |
|---|---|---|---|
| Bytes on disk (slice) | 224KB + 311KB samples (33 docs), ~3s | 14.5MB / 200 articles, 20s (21MB range-read of the 3.4GB train.txt member) | 70.0MB / 200 AI-ML-NLP PDFs, 53s (+12.5MB manifest, +360MB metadata head) |
| Full text? | YES — `body.text` (GROBID-parsed) | YES — `article_text[]`, 200/200 non-empty | YES — but as raw PDFs (parse required) |
| Section structure (0–3) | 3 — `section_header` spans on 22/22 sample docs (9.5/paper); small all-discipline sample | **3 — 99% of papers have ≥2 named sections (5.6/paper); abstract its own field** | 1 — 36% yield ≥2 numbered headers via cheap regex; production needs GROBID/font heuristics |
| License | Collection **ODC-BY** (README verbatim) + per-doc Unpaywall (`CCBY`…`NONE` seen) | HF card license field: **`unknown`**; underlying data derived from arXiv LaTeX (Cohan et al.); long-standing academic redistribution | arXiv ToS — **bulk PDF redistribution in the data zip not permitted**; Kaggle-hosted JSONL = metadata+abstracts only |
| Est. chunks @10k papers | 103k–206k (sample all-discipline; cs.* would run higher) | **189k–378k** | 216k–432k |
| Parse effort | Moderate: JSON + character-span slicing | **Zero: pre-parsed JSONL** | High: PyMuPDF + section heuristics (or GROBID) |
| **Verdict** | Fallback 1 (API key needed) | **WINNER** | Fallback 2 (no-auth rescue path) |

## Per-candidate evidence

### A — S2ORC (via S2AG `s2orc_v2` public samples)
- Legacy `s2orc/` prefix on `ai2-s2-research-public.s3` is **gone** (list returns 0 keys) — the plan's original mirror assumption is stale; recorded as a finding.
- Official distribution is now the S2AG releases API: full corpus requires an API key (Partner Form); **public samples** at `s3://ai2-s2ag/samples/s2orc_v2/s2orc_v2-sample.jsonl.gz` (311,474 B gz, 22 docs) and `s2orc-sample.jsonl.gz` (224,174 B gz, 11 docs — plain text, superseded format).
- Schema: `openaccessinfo` (incl. per-doc `license`, e.g. `CCBY`), `title`, `authors`, `body.text` + `annotations` (JSON-encoded string; `section_header` spans), separate `bibliography.text`. Sample stats: 100% docs with ≥2 section headers, mean 9.5 sections, 3,370 mean words/paper, boilerplate share 34% (all-discipline mix, short bodies; bibliography cleanly strippable as its own field).
- Caveats: sample is tiny and not cs-filtered; production slice needs the API key; cs.* filtering needs the full release's fields of study.

### B — HF `scientific_papers` (arxiv split) — WINNER
- Loader script (`armanc/scientific_papers` — canonical repo redirects here) points to `https://s3.amazonaws.com/datasets.huggingface.co/scientific_papers/1.1.1/arxiv-dataset.zip` (live, HTTP 200).
- Slice method (no full download): HTTP range-reads of the remote zip — central directory → `arxiv-dataset/train.txt` local header (offset 356, 3,415,892,996 B compressed) → inflate first 20MB → 200 complete JSONL records in 20.0s. Stats file: `research/spike/data/scientific_papers/download_stats.json`.
- Records: `article_id` (arXiv id), `article_text[]`, `abstract_text[]`, `labels`, `sections[][]`, `section_names[]` — section-aware chunking inputs ready-made.
- Sample stats (n=200): 99% ≥2 sections, 5.6 sections/paper, words/paper mean 6,188 / median 4,858 / p95 16,029 → 10k papers ≈ **61.9M words** (50M+ assumption validated). Boilerplate share 4.5% (references/appendix/acknowledgments named → strippable by name).
- License: card `unknown` (verbatim); dataset is the standard academic release behind the Cohan et al. ACL paper; redistribution-in-data-zip is common practice but should be acknowledged in the README (attribution + arXiv provenance).

### C — Kaggle arXiv dumps / public GCS bucket
- Docs-first check of the Kaggle card (`Cornell-University/arxiv`): 1.7M papers with "article titles, authors, categories, **abstracts**, full text PDFs" — the Kaggle-hosted dataset itself is **metadata+abstract JSONL → abstract-only = disqualifying** for the KB (full text saved time on elimination, as the plan predicted). Kaggle API download without auth: HTTP 404 (friction recorded; no team creds).
- Salvage: the card's "Google Cloud Storage buckets" = `gs://arxiv-dataset`, **publicly listable and downloadable without auth**: `metadata-v5/arxiv-metadata-oai.json` (4.5GB, categories ✓), manifest `arxiv-dataset_list-of-files.txt.gz` (12.5MB, 4.4M files), per-paper PDFs incl. modern IDs up to Dec 2020 under `arxiv/arxiv/pdf/` (verified: 1706.08416 present). `cs/` archive holds only ~18k legacy-format PDFs; AI/ML/NLP papers live under the catch-all `arxiv/` archive (category filter requires the metadata JSONL).
- Slice (script): 360MB of metadata ranges → 600 AI/ML/NLP ids → 200 matched PDFs (70,068,005 B on disk, 53s, 4-way parallel).
- PDF parse test (PyMuPDF 1.28.2): 200/200 parse, but only 36% yield ≥2 numbered section headers with cheap regex (mean 3.8), boilerplate share 9.6% (undercounted — refs headings often missed), 7,075 mean words/paper incl. extraction noise. Sections reliably = GROBID-class tooling = out of $0/laptop scope for Story 2.

## Phase 3 — chunks estimate (input to later sparse-engine decision)

Tokens ≈ 1.33 × words; window step = W × (1−0.15).

| Source basis | words/paper | tokens | chunks/paper (512→256 W) | @10k papers |
|---|---|---|---|---|
| B `scientific_papers` | 6,188 | 8,230 | 18.9–37.8 | **189k–378k** |
| C GCS PDFs | 7,075 | 9,410 | 21.6–43.2 | 216k–432k |
| A s2orc_v2 (all-disc) | 3,370 | 4,482 | 10.3–20.6 | 103k–206k |

Working estimate on the winner: **~190k–380k chunks at 10k papers** (SPEC's 300k–600k bracket remains the conservative planning number). `kb_stats.json` in Story 2 replaces this estimate. Sparse engine (`rank_bm25` vs Pyserini vs Elasticsearch) stays an open question → Story 3 prep, per the scope deviation below.

## Story-1 scope deviation (recorded per plan)

Plan v2 (2026-09-18) reduced Story 1's "sparse-engine decision data" to the chunks-per-paper arithmetic above; the one-off BM25-vs-FAISS scale sanity check was dropped by user decision, moving the `rank_bm25`/Pyserini/Elasticsearch call to Story 3 prep. SPEC's sparse-engine open question remains open; only the dataset question is resolved by this spike.

## Environment notes

- Machine: 255GB free disk (50GB requirement ✓), Linux laptop (plan assumed MacBooks — no impact on the decision).
- Legacy `scientific_papers.py` script-based loader works with modern `datasets` only via the raw S3 URL path documented here (the HF datasets-viewer no longer converts this dataset); the ranged-zip slicer (`research/spike/scripts/download_scientific_papers_slice.py`) is the reproducible acquisition path and downloads only ~21MB per 200-paper probe.
- Production acquisition sketch for Story 2: one 3.5GB zip download → stream-parse `train.txt` (JSONL) → filter AI/ML/NLP by arXiv id against a categories snapshot (public `arxiv-metadata-oai.json` head or arXiv API) → 10k+ papers without any PDF parsing.
