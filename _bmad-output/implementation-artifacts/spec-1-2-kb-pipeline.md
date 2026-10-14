---
story: '1.2'
slug: kb-pipeline
status: in-progress
baseline_commit: 7a3dc5704cf848f97d1608edd3ed2504d4b6d8ee
context:
  - _bmad-output/planning-artifacts/architecture/architecture-NLPProject-2026-10-12/ARCHITECTURE-SPINE.md
  - _bmad-output/specs/spec-story-1-2-kb-pipeline
  - _bmad-output/implementation-artifacts/spec-pattern-digest.md
  - _bmad-output/specs/spec-paperpilot-rag/stories.yaml#story-2
---

# House Spec — Story 1.2: Knowledge-base pipeline (clean, dedup, chunk, stats)

<frozen-after-approval>

## Intent

`make kb` rebuilds the entire knowledge base from the verified raw source — acquire → metadata join (+ cs.* filter) → clean → dedup → structure-aware chunk → stats — emitting `data/kb/papers.jsonl`, `data/kb/chunks.jsonl`, and `kb_stats.json` in one unattended command, deterministically (same inputs → identical `chunk_id`s), with zero papers carrying null metadata. Implements project CAP-1; first code of the repo (`core/`, `kb/` layers).

## Boundaries & Constraints

### Always

- `chunk_id` is minted ONLY by `paperpilot.core.ids.chunk_id(arxiv_id, section_name, text)`: leading 16 hex of SHA-1 over UTF-8 `arxiv_id + "\x1f" + section_name + "\x1f" + normalize(text)`; `normalize` = NFC + whitespace collapse (AD-2). Stored chunk `text` is the normalized text.
- Artifact classes (AD-5): this story writes only class 2 (`data/raw/`, `data/kb/`); never writes `data/eval/` (class 1), `indexes/`, or `reports/` (class 3). Outputs atomic: tmp file + `os.replace`; rebuilds are wholesale.
- Bounded RAM: stream `train.txt` (3.5GB) and the metadata JSONL (4.5GB) line-by-line; the metadata join index lives on disk (stdlib `sqlite3` temp table), never a full in-RAM dict.
- No paper emitted with null `title`/`authors`/`year`/`categories`; a paper with no metadata row is dropped + counted (`dropped_no_metadata`).
- English-only: clean drops non-English papers via a documented heuristic; counted (`non_english_dropped`).
- cs.* filter (any `cs.*` category) applied via the metadata join; if pre-clean yield < 12,000, widen to all categories, set `provenance.filter_widened: true`.
- Offline tests: `uv run pytest tests/ -q` green with no network; synthetic fixtures only.
- Bootstrap: `pyproject.toml` + committed `uv.lock`; runtime dep `pydantic==2.14.1`; dev deps `pytest`, `pyyaml`. No other deps. Python 3.11+ via uv (`.venv/` at repo root).
- Ids re-slashed pre-2007 (`nlin0608019` → `nlin/0608019`) and metadata ids stripped of version suffix (`0704.0001v2` → `0704.0001`) before matching. `year` = year parsed from metadata `versions[0].created`; unparseable → drop + count.
- Import direction (AD-1): `kb` imports only `core`; `core` imports nothing from `kb`.
- Malformed JSONL lines (source or metadata): skip + count + warn; never crash the build.
- CLI: argparse subcommand `build`, `run_build_command(...) -> int` never raises; exit 0 success / 1 verification failure / 3 stage error; `--limit N` flag for smoke slices; summary on stdout, errors on stderr.

### Ask First

- Changing the cs.* filter policy or the 12k contingency threshold.
- Changing chunk band (256–512), overlap (~15%), or the token estimator (words × 4/3).
- Swapping the estimator for a model tokenizer, or any new runtime dependency.
- An alternate metadata source (the GCS snapshot is the only joined source today).

### Never

- No `datasets`/HF-hub loader (script loader broken per spike); acquisition = direct S3 zip download + stream parse (`zipfile` over a streamed file).
- No SQL string-matching retrieval patterns in kb code (the sqlite temp table is a build-time index only — never an artifact, never queried with LIKE).
- No network calls inside tests; no committed bulk artifacts (`data/raw/`, `data/kb/` are git-ignored).
- No re-implementation of normalization/chunk_id outside `core.ids`.
- No silent degradation: every drop/duplicate/malformed path increments a reported counter.
- No orchestration frameworks; stdlib + pydantic only.

## I/O & Edge-Case Matrix

| # | Input / trigger | Expected behavior |
| --- | --- | --- |
| I-1 | S3 zip `https://s3.amazonaws.com/datasets.huggingface.co/scientific_papers/1.1.1/arxiv-dataset.zip`, member `train.txt` (JSONL: `article_id`, `article_text[]`, `abstract_text[]`, `sections[][]`, `section_names[]`) | Streamed download to `data/raw/`; parsed line-by-line; raw artifact is class 2 |
| I-2 | Metadata JSONL `gs://arxiv-dataset/metadata-v5/arxiv-metadata-oai.json` (4.5GB; `id` versioned, `categories` space-separated string, `title`, `authors`, `abstract`, `versions[].created`, `license`) | Streamed into a temp sqlite index keyed by suffix-stripped id; deleted after the build |
| I-3 | Build config defaults (band 256–512, overlap 15%, filter `cs.*`, contingency 12k, estimator ×4/3) | Single-sourced in `core.config`; unknown/override keys via CLI flags, never env vars |
| O-1 | `data/kb/papers.jsonl` | One object/line: `arxiv_id, title, authors[], year, abstract, sections{name→text}, source_link, license, categories[]`; `source_link = https://arxiv.org/abs/<arxiv_id>`; empty `abstract`/`license` = `""`, never `null` |
| O-2 | `data/kb/chunks.jsonl` | One object/line: `chunk_id, arxiv_id, section_name, section_rank, text, n_tokens, header_prefix`; ordered by paper file order then section_rank then window index |
| O-3 | `data/kb/kb_stats.json` | `papers, chunks, words, types, chunk_size_histogram{band→count}, year_min, year_max, year_histogram{year→count}, category_composition{cs_papers, aiml_papers, total}, provenance{source_url, metadata_url, filter_mode, filter_widened, dropped_no_metadata, duplicates, malformed_source_lines, malformed_metadata_lines, non_english_dropped, generated_at}` |
| E-1 | Paper has no metadata row | Dropped, `dropped_no_metadata++`; never emitted with nulls |
| E-2 | Dataset id pre-2007 slash-less (`nlin0608019`) | Re-slash before join (`nlin/0608019`); join succeeds |
| E-3 | Metadata id versioned (`0704.0001v2`) | Suffix stripped; join keyed on bare id |
| E-4 | cs.* yield < 12,000 pre-clean | Widen to all categories; `filter_widened: true`; composition reported either way |
| E-5 | Two papers with identical normalized full text | SHA-256 content dedup pre-chunking; first in file order kept; `duplicates++` |
| E-6 | Non-English paper (heuristic) | Dropped at clean; `non_english_dropped++` |
| E-7 | Paper with empty `section_names[]` | Whole `article_text` becomes one section named `body` (joined); ranked per E-18 |
| E-8 | Empty/whitespace section text | No chunk emitted for it |
| E-9 | Missing/empty abstract | No abstract chunk; `abstract` field = `""` in papers.jsonl (not a null-metadata drop) |
| E-10 | Section > 512 tokens | Windowed split, step = floor(512 × 0.85); last window < 128 tokens folds into the previous window |
| E-11 | Section ≤ 512 tokens | Single chunk even if < 256 (band governs splitting, not a floor for emission) |
| E-12 | Unicode text (non-NFC, irregular whitespace) | Normalized (NFC + whitespace collapse) before hashing AND in stored `text` |
| E-13 | chunk_id collision (identical arxiv_id+section+normalized text) | Duplicate chunk dropped + counted under `duplicates`; chunk_ids in chunks.jsonl are unique |
| E-14 | Interrupted rebuild | Tmp files never promoted; next run rebuilds wholesale; no partial data/kb artifacts |
| E-15 | Network failure mid-download | Exit 3, clear stderr message; no `data/kb/` outputs written |
| E-16 | `--limit N` smoke run | Deterministic first-N slice; two identical invocations produce identical chunk_id sequences |
| E-17 | Metadata `categories` space-separated (`"cs.AI stat.ML"`) | Split on whitespace; cs.* test = any token startswith `cs.`; AI/ML/NLP set = {`cs.AI`,`cs.CL`,`cs.LG`,`cs.CV`,`cs.IR`,`stat.ML`} (composition stat only) |
| E-18 | Abstract vs sections duplication | Abstract chunk emitted from `abstract_text` even though sections may repeat it; `section_name = "abstract"`, `section_rank 0`, body sections ranked from 1 |

</frozen-after-approval>

## Code Map

```text
pyproject.toml, uv.lock          # bootstrap: pydantic 2.14.1, pytest, pyyaml; Python 3.11+
Makefile                         # `kb` target -> uv run python -m paperpilot.kb.cli build
.gitignore                       # class fix: ignore data/raw/, data/kb/, indexes/, reports/; track data/eval/
src/paperpilot/core/ids.py       # normalize(), chunk_id() — the only hasher (AD-2)
src/paperpilot/core/schemas.py   # Paper, Chunk, KBStats pydantic models (no-null validation)
src/paperpilot/core/config.py    # KBDefaults: band, overlap, filter, contingency, estimator (single-sourced)
src/paperpilot/kb/acquire.py     # S3 zip download to data/raw/ + stream parse of train.txt
src/paperpilot/kb/metadata.py    # stream metadata -> sqlite index; re-slash; join + cs.* filter (+widening)
src/paperpilot/kb/clean.py       # boilerplate strip (by section name), English heuristic, NFC/whitespace normalize
src/paperpilot/kb/dedup.py       # SHA-256 content-hash dedup, keep-first
src/paperpilot/kb/chunk.py       # section-aware split, band windows, ~15% overlap, abstract chunk, header_prefix
src/paperpilot/kb/stats.py       # kb_stats.json aggregation
src/paperpilot/kb/cli.py         # argparse `build`, run_build_command -> int, --limit
tests/conftest.py                # synthetic mini-corpus fixtures (offline)
tests/core/, tests/kb/           # mirror src/paperpilot/ — pinning tests for every matrix row
```

## Tasks & Acceptance

1. **Bootstrap** — pyproject + `uv lock` + `.gitignore` class fix + `Makefile` kb target. AC: `uv sync` succeeds; `uv run pytest` collects.
2. **core.ids** — `normalize()` + `chunk_id()` per AD-2. AC: pinned test vectors (incl. pre-2007 id, NFC input, whitespace irregularities).
3. **core.schemas** — Paper/Chunk/KBStats models. AC: null metadata raises; O-1/O-2/O-3 field-exact.
4. **core.config** — defaults single-sourced. AC: I-3.
5. **kb.acquire** — download + stream parse. AC: I-1; E-14/E-15 (synthetic zip fixture; failure path via monkeypatched transport).
6. **kb.metadata** — index + join + filter + widening. AC: E-1, E-2, E-3, E-4, E-17; year from `versions[0].created`, unparseable → drop + count.
7. **kb.clean** — boilerplate strip, English heuristic, normalization. AC: E-6, E-12; boilerplate section names (references/appendix/acknowledgments) stripped, counted.
8. **kb.dedup** — content-hash keep-first. AC: E-5.
9. **kb.chunk** — split + windows + abstract + header_prefix. AC: E-7..E-11, E-13, E-18.
10. **kb.stats + kb.cli** — aggregation, atomic writes, exit codes. AC: O-3, E-14, E-15, E-16; CLI exit codes pinned.
11. **Acceptance run** — full-corpus `make kb`; record figures in the story report (papers ≥ 10,000; words ≥ 100,000; chunks in the 190k–380k ballpark; drop counters documented).

## Review Findings

(pending — populated at Step 9 triage)

## Spec Change Log

- 2026-10-14: Initial frozen block from project spec CAP-1 + stories.yaml story 2 + pipeline-stages schemas + stack.md acquisition + spine AD-1/2/5 (bmad-spec, in-session fallback per loop §0.5).
- 2026-10-14: Pre-build amendment — `provenance.metadata_url` added to O-3 (reproducibility; nothing has consumed the matrix yet). KEEP: provenance fields are exhaustive — every drop/dup/malformed path appears there.
- 2026-10-14: Pre-build amendment — E-7 rank special case removed; body sections rank uniformly from 1 (E-18), abstract chunk alone takes rank 0. KEEP: one rank rule, dataset section order.

## Design Notes

- **Metadata join index:** the 4.5GB metadata JSONL is streamed into a temp `sqlite3` table (stdlib; keyed by bare arxiv_id) so the join needs bounded RAM. This is a build-time index only — it is never an emitted artifact and unrelated to the assignment's "no SQL retrieval" rule (which bans string-matching retrieval, not build tooling).
- **Widening decision:** index all papers once, count the cs.* yield during the join pass, and apply the ≥12k widening decision at emission time — one index build, no second pass.
- **Token estimator:** `n_tokens = round(words × 4/3)` (spike arithmetic; ≈1.33 tokens/word), single-sourced in `core.config`; a real tokenizer swap later is a config-visible change (Ask First).
- **English heuristic:** drop when ASCII-letter share of the normalized text < 0.8 (documented, dep-free); heuristic swaps are Ask First.
- **Determinism:** no timestamps inside emitted chunk/paper records; `generated_at` lives only in kb_stats provenance. Dedup keep-first = source file order. Windows enumerated deterministically (section_rank, window index).
- **header_prefix format:** `f"{title} — {section_name}"` prepended to chunk text with a blank-line separator; single-sourced in `chunk.py`.

## Verification

1. `uv sync && uv run pytest tests/ -q` — all green, offline, on synthetic fixtures.
2. `uv run python -m paperpilot.kb.cli build --limit 200 --data-dir /tmp/opencode/kb-smoke` — twice; `diff` of the two chunks.jsonl chunk_id sequences is empty (E-16).
3. `make kb` (full corpus) — `kb_stats.json`: `papers ≥ 10000`, `words ≥ 100000`, `chunks` in 190k–380k ballpark, `dropped_no_metadata` small and documented, zero papers with null metadata (schema-enforced). Figures recorded in the story report.

## Suggested Review Order

(blank until after implementation)
