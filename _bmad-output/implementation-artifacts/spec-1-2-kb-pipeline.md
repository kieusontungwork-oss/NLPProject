---
story: '1.2'
slug: kb-pipeline
status: done
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
- Bounded RAM: stream the source members (`train.txt` 14.3GB uncompressed + `val.txt` + `test.txt`) and the metadata JSONL (4.5GB) line-by-line; the metadata join index lives on disk (stdlib `sqlite3` temp table), never a full in-RAM dict. Output lists are held in RAM for the cs.* KB (measured peak 2.6GB); streaming emission for the widening path is deferred (deferred-work.md).
- No paper emitted with null `title`/`authors`/`year`/`categories`; a paper with no metadata row is dropped + counted (`dropped_no_metadata`).
- English-only: clean drops non-English papers via a documented heuristic; counted (`non_english_dropped`).
- cs.* filter (any `cs.*` category) applied via the metadata join; if pre-clean yield < 12,000, widen to all categories, set `provenance.filter_widened: true`.
- Offline tests: `uv run pytest tests/ -q` green with no network; synthetic fixtures only.
- Bootstrap: `pyproject.toml` + committed `uv.lock`; runtime dep `pydantic==2.14.1`; dev deps `pytest`, `pyyaml`. No other deps. Python 3.11+ via uv (`.venv/` at repo root).
- Ids re-slashed pre-2007 (`nlin0608019` → `nlin/0608019`) and metadata ids stripped of version suffix (`0704.0001v2` → `0704.0001`) before matching. `year` = first-submission year derived from the bare `arxiv_id` (new-style `YYMM.NNNNN` → `2000+YY`; pre-2007 `archive/YYMMNNN` → `19YY` if `YY ≥ 91` else `20YY`); unparseable id → drop + count (E-19).
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
| I-1 | S3 zip `https://s3.amazonaws.com/datasets.huggingface.co/scientific_papers/1.1.1/arxiv-dataset.zip`, members `train.txt`, `val.txt`, `test.txt`, read in that fixed order as one record stream (JSONL: `article_id`, `article_text[]`, `abstract_text[]`, `sections[][]`, `section_names[]`) | Streamed download to `data/raw/`; parsed line-by-line; raw artifact is class 2 |
| I-2 | Metadata JSONL `gs://arxiv-dataset/metadata-v5/arxiv-metadata-oai.json` (4.5GB; `id` versioned, `categories` a one-element list holding a space-separated string (`["cs.AI stat.ML"]`), `title`, `authors` (free-text string), `abstract`, `versions` a list of bare version strings (`["v1","v2"]`, no dates); no `license` key) | Streamed into a temp sqlite index keyed by suffix-stripped id; deleted after the build |
| I-3 | Build config defaults (band 256–512, overlap 15%, filter `cs.*`, contingency 12k, estimator ×4/3) | Single-sourced in `core.config`; unknown/override keys via CLI flags, never env vars |
| O-1 | `data/kb/papers.jsonl` | One object/line: `arxiv_id, title, authors[], year, abstract, sections{name→text}, source_link, license, categories[]`; `source_link = https://arxiv.org/abs/<arxiv_id>`; empty `abstract`/`license` = `""`, never `null` |
| O-2 | `data/kb/chunks.jsonl` | One object/line: `chunk_id, arxiv_id, section_name, section_rank, text, n_tokens, header_prefix`; ordered by paper file order then section_rank then window index |
| O-3 | `data/kb/kb_stats.json` | `papers, chunks, words, types, chunk_size_histogram{band→count}, year_min, year_max, year_histogram{year→count}, category_composition{cs_papers, aiml_papers, total}, provenance{source_url, metadata_url, filter_mode, filter_widened, dropped_no_metadata, duplicates, malformed_source_lines, malformed_metadata_lines, non_english_dropped, duplicate_chunks, boilerplate_sections_stripped, nameless_sections_dropped, sections_merged_name_collision, generated_at}`; words/types counted over paper text (abstract + sections), not chunk text |
| E-1 | Paper has no metadata row | Dropped, `dropped_no_metadata++`; never emitted with nulls |
| E-2 | Dataset id pre-2007 slash-less (`nlin0608019`) | Re-slash before join (`nlin/0608019`); join succeeds |
| E-3 | Metadata id versioned (`0704.0001v2`) | Suffix stripped; join keyed on bare id |
| E-4 | cs.* yield < 12,000 pre-clean | Widen to all categories; `filter_widened: true`; composition reported either way |
| E-5 | Two papers with identical normalized full text | SHA-256 content dedup pre-chunking; first in file order kept; `duplicates++` |
| E-6 | Non-English paper (heuristic) | Dropped at clean; `non_english_dropped++` |
| E-7 | Paper with empty `section_names[]` | Whole `article_text` becomes one section named `body` (joined); ranked per E-18 |
| E-8 | Empty/whitespace section text | No chunk emitted for it |
| E-9 | Missing/empty abstract | No abstract chunk; `abstract` field = `""` in papers.jsonl (not a null-metadata drop) |
| E-10 | Section > 512 tokens | Windowed split, step = floor(512 × 0.85); last window < 128 tokens folds into the previous window; n_tokens counts body words only (header prefix excluded) |
| E-11 | Section ≤ 512 tokens | Single chunk even if < 256 (band governs splitting, not a floor for emission) |
| E-12 | Unicode text (non-NFC, irregular whitespace) | Normalized (NFC + whitespace collapse) before hashing AND in stored `text` |
| E-13 | chunk_id collision (identical arxiv_id+section+normalized text) | Duplicate chunk dropped + counted under `duplicate_chunks`; chunk_ids in chunks.jsonl are unique |
| E-14 | Interrupted rebuild | Tmp files never promoted; next run rebuilds wholesale; no partial data/kb artifacts |
| E-15 | Network failure mid-download | Exit 3, clear stderr message; no `data/kb/` outputs written |
| E-16 | `--limit N` smoke run | Deterministic first-N slice; two identical invocations produce identical chunk_id sequences |
| E-17 | Metadata `categories` a one-element list of a space-separated string (`["cs.AI stat.ML"]`; a plain string is accepted too) | Join list elements with a space, then split on whitespace; cs.* test = any token startswith `cs.`; AI/ML/NLP set = {`cs.AI`,`cs.CL`,`cs.LG`,`cs.CV`,`cs.IR`,`stat.ML`} (composition stat only) |
| E-18 | Abstract vs sections duplication | Abstract chunk emitted from `abstract_text` even though sections may repeat it; `section_name = "abstract"`, `section_rank 0`, body sections ranked from 1 |
| E-19 | Metadata `versions` carry no dates (`["v1","v2"]`); no `license` key | `year` derived from the bare `arxiv_id` (`0704.0001` → 2007, `hep-th/9901001` → 1999, `math/0211159` → 2002); unparseable id → drop + `dropped_no_metadata++`; `license = ""` |

</frozen-after-approval>

## Code Map

```text
pyproject.toml, uv.lock          # bootstrap: pydantic 2.14.1, pytest, pyyaml; Python 3.11+
Makefile                         # `kb` target -> uv run python -m paperpilot.kb.cli build
.gitignore                       # class fix: ignore data/raw/, data/kb/, indexes/, reports/; track data/eval/
src/paperpilot/core/ids.py       # normalize(), chunk_id() — the only hasher (AD-2)
src/paperpilot/core/schemas.py   # Paper, Chunk, KBStats pydantic models (no-null validation)
src/paperpilot/core/config.py    # KBDefaults: band, overlap, filter, contingency, estimator (single-sourced)
src/paperpilot/kb/acquire.py     # S3 zip download to data/raw/ + stream parse of train/val/test
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
6. **kb.metadata** — index + join + filter + widening. AC: E-1, E-2, E-3, E-4, E-17, E-19; year from the bare `arxiv_id`, unparseable → drop + count.
7. **kb.clean** — boilerplate strip, English heuristic, normalization. AC: E-6, E-12; boilerplate section names (references/appendix/acknowledgments) stripped, counted.
8. **kb.dedup** — content-hash keep-first. AC: E-5.
9. **kb.chunk** — split + windows + abstract + header_prefix. AC: E-7..E-11, E-13, E-18.
10. **kb.stats + kb.cli** — aggregation, atomic writes, exit codes. AC: O-3, E-14, E-15, E-16; CLI exit codes pinned.
11. **Acceptance run** — full-corpus `make kb`; record figures in the story report (papers ≥ 10,000; words ≥ 100,000; chunks in the 190k–380k ballpark; drop counters documented).

## Review Findings

Fresh-context review: edge-case hunter, test audit, acceptance auditor (three Sonnet subagents).

- [x] [Review][Patch] P1 — E-10 fold repeated the 58 overlap words; fold now appends only words past the previous window's end (`src/paperpilot/kb/chunk.py` `_windows`)
- [x] [Review][Patch] P2 — stale metadata index reused after a killed run; index deleted before rebuild, and `cli.build` builds/checks it inside the try/finally (`metadata.py` `build_metadata_index`, `cli.py` `build`)
- [x] [Review][Patch] P3 — "never raises": final `except Exception` in `run_build_command` returns exit 3; metadata lines decoded as strict UTF-8, bad bytes counted as malformed (`cli.py`, `metadata.py`)
- [x] [Review][Patch] P4 — section-name collision now concatenates (was last-wins overwrite); counter kept (`metadata.py` `join_paper`)
- [x] [Review][Patch] P5 — E-7 `body` fallback applies whenever no named section survives (`metadata.py` `join_paper`)
- [x] [Review][Patch] P6 — chunk text = prefix + single space + body, so stored text equals its normalized form (AD-2/E-12); chunk_ids unchanged (verified on a `--limit 200` run before/after) (`chunk.py` `chunk_text_for`)
- [x] [Review][Patch] P7 — `words`/`types` counted over paper text (abstract + sections) in `CorpusAggregate.add_paper`, not chunk text (`stats.py`)
- [x] [Review][Patch] P8 — boilerplate match strips a leading `[label]` and punctuation, then matches `^(appendix|appendices|acknowledg\w*|references?|bibliography)\b` (`clean.py`)
- [x] [Review][Patch] P9 — `_parse_authors` collapses whitespace, drops parenthesized affiliations, splits on commas / "and" (`metadata.py`)
- [x] [Review][Defer] Dataset markup (@xmath/@xcite/<S>/filler) not cleaned — story 1.5 (owner decision)
- [x] [Review][Defer] All-or-nothing writes of the three KB files (H8)
- [x] [Review][Defer] `--limit` smoke runs always widen to filter=all (H10)
- [x] [Review][Defer] Provenance URLs do not reflect --source-zip/--metadata-file overrides (H13)
- [x] [Review][Defer] Downloaded file reused without a size/checksum check (H15)
- [x] [Review][Defer] `errors="replace"` on source bytes is not counted (H16)
- [x] [Review][Defer] Dedup hash ignores section structure (H18)
- [x] [Review][Defer] LaTeX accents in titles (H20)
- [x] [Review][Defer] Extra `verify()` invariants (H21)
- [x] [Review][Defer] Streaming emission for the widening path (A5/H17)
- [x] [Review][Defer] I-3 CLI override flags ambiguity
- [x] [Review][Defer] Zip length mismatch between section_names and sections not counted (H11b)
- [x] [Review][Defer] Remaining test-quality items T7–T13 not covered by the patches above

Dismissed: concurrent file locking (outside the offline single-laptop envelope); per-section linear scan for duplicate chunk ids (H14, fine at section scale); one sqlite connection per lookup (H19, build time is not a requirement); English heuristic strength (owner kept the ASCII-share check, 2026-10-15). See review-dismiss-precedents.md.

Counts: 9 patched, 13 deferred, 4 dismissed.

## Spec Change Log

- 2026-10-14: Initial frozen block from project spec CAP-1 + stories.yaml story 2 + pipeline-stages schemas + stack.md acquisition + spine AD-1/2/5 (bmad-spec, in-session fallback per loop §0.5).
- 2026-10-14: Pre-build amendment — `provenance.metadata_url` added to O-3 (reproducibility; nothing has consumed the matrix yet). KEEP: provenance fields are exhaustive — every drop/dup/malformed path appears there.
- 2026-10-14: Pre-build amendment — E-7 rank special case removed; body sections rank uniformly from 1 (E-18), abstract chunk alone takes rank 0. KEEP: one rank rule, dataset section order.
- 2026-10-15: Mid-build amendment (owner-approved, Option A) — the real `metadata-v5` snapshot has `versions` as bare strings (no `created` date), `categories` as a one-element list, and no `license` key (found by the first full-corpus `make kb`, which crashed in `build_metadata_index`). `year` is now derived from the bare `arxiv_id` (E-19); categories list is joined then split (E-17); missing license = `""`. Rejected: switching to the Kaggle snapshot (needs per-teammate auth, unpinned weekly updates). KEEP: one year rule (from the id), no network/auth beyond the two public URLs.
- 2026-10-15: Mid-build amendment (owner-approved) — measured cs.* yield is 5.7%, not the spike's 7.5% (15/200 sample): `train.txt` alone joins 11,512 cs.* papers (< 12k → widen to all 203,037 papers → OOM at 23.7GB RSS and ~4.3M chunks, outside the 190k–380k band). I-1 now reads all three zip members (`train`, `val`, `test`; 215,913 papers, 12,352 cs.* — clears 12k pre-clean); held-out splits carry no meaning for this KB (no model is trained on them). Threshold and filter policy unchanged. Measured peak RSS: 0.23GB at 1,000 papers (~3GB projected for the cs.* KB). KEEP: fixed member order train→val→test (determinism, E-16); widening rule unchanged.
- 2026-10-15: Post-review amendment — P1 fold appends only non-overlapping words (E-10); P2 temp metadata index always rebuilt from scratch; P3 `run_build_command` never raises (unexpected exception → exit 3) and metadata bytes decoded strictly (bad lines counted); P4 name collisions concatenate; P5 `body` fallback when no named section survives; P6 chunk text joins prefix and body with a single space (stored text already normalized); P7 `words`/`types` over paper text; P8 boilerplate names matched after stripping `[label]`/punctuation; P9 author parsing drops affiliations and splits on commas/"and". Known limitations accepted by owner: dataset markup (@xmath/@xcite/<S>) not cleaned (deferred to story 1.5), English heuristic is ASCII-share only (some non-English papers pass). KEEP: fold appends only non-overlapping words; temp index always rebuilt from scratch; run_build_command never raises.

## Design Notes

- **Metadata join index:** the 4.5GB metadata JSONL is streamed into a temp `sqlite3` table (stdlib; keyed by bare arxiv_id) so the join needs bounded RAM. This is a build-time index only — it is never an emitted artifact and unrelated to the assignment's "no SQL retrieval" rule (which bans string-matching retrieval, not build tooling).
- **Widening decision:** index all papers once, count the cs.* yield during the join pass, and apply the ≥12k widening decision at emission time — one index build, no second pass.
- **Token estimator:** `n_tokens = round(words × 4/3)` (spike arithmetic; ≈1.33 tokens/word), single-sourced in `core.config`; a real tokenizer swap later is a config-visible change (Ask First).
- **English heuristic:** drop when ASCII-letter share of the normalized text < 0.8 (documented, dep-free); heuristic swaps are Ask First.
- **Determinism:** no timestamps inside emitted chunk/paper records; `generated_at` lives only in kb_stats provenance. Dedup keep-first = source file order. Windows enumerated deterministically (section_rank, window index).
- **header_prefix format:** `f"{title} — {section_name}"` prepended to chunk text with a single space separator; single-sourced in `chunk.py`.

## Verification

1. `uv sync && uv run pytest tests/ -q` — all green, offline, on synthetic fixtures.
2. `uv run python -m paperpilot.kb.cli build --limit 200 --data-dir /tmp/opencode/kb-smoke` — twice; `diff` of the two chunks.jsonl chunk_id sequences is empty (E-16).
3. `make kb` (full corpus) — `kb_stats.json`: `papers ≥ 10000`, `words ≥ 100000`, `chunks` in 190k–380k ballpark, `dropped_no_metadata` small and documented, zero papers with null metadata (schema-enforced). Figures recorded in the story report.

### Acceptance run record (task 11, 2026-10-15, after the post-review patches)

Full-corpus `build` (train + val + test members, local files from `data/raw/`), `filter=cs`, `filter_widened=false`. Peak RSS observed 2,609,652 kB (~2.6 GB). Figures copied from `data/kb/kb_stats.json`:

- papers = 12350; chunks = 271171; words = 81422705 (paper text); types = 870850 (paper text, lowercased); year_min = 1994; year_max = 2017
- category_composition: cs_papers = 12350, aiml_papers = 2741, total = 12350
- chunk_size_histogram: 0-128 = 2755, 129-255 = 26987, 256-384 = 25640, 385-512 = 208399, 513+ = 7390 (max n_tokens = 561, within 512 + fold floor)
- provenance: dropped_no_metadata = 0, duplicates = 2, duplicate_chunks = 285, malformed_source_lines = 0, malformed_metadata_lines = 0, non_english_dropped = 0, boilerplate_sections_stripped = 5215, nameless_sections_dropped = 191, sections_merged_name_collision = 22, filter_mode = cs, filter_widened = false
- Checks on the outputs: 12350 papers, 0 with a null/empty title, authors, year, or categories; 0 authors containing a newline or "("; 0 remaining boilerplate sections; 0 chunks with a repeated 58-word block.
- Smoke (`--limit 200`, run twice): chunk_id sequences identical (4187 chunks each).

## Suggested Review Order

1. `src/paperpilot/kb/chunk.py` — `_windows` (fold without repeated overlap), `chunk_text_for`
2. `src/paperpilot/kb/metadata.py` — `build_metadata_index`, `join_paper`, `_parse_authors`, `year_from_arxiv_id`
3. `src/paperpilot/kb/cli.py` — `run_build_command`, `build` (try/finally around the index)
4. `src/paperpilot/kb/clean.py` — `is_boilerplate`
5. `src/paperpilot/kb/stats.py` — `CorpusAggregate`, `render_stats`

## GitHub Links

- PR: #2
