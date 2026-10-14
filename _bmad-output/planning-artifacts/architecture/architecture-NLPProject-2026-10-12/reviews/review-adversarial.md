# Adversarial Review — PaperPilot Architecture Spine

- **Reviewer:** adversarial lens (cross-subgroup compatibility attack)
- **Target:** `ARCHITECTURE-SPINE.md` (AD-1…AD-5, Consistency Conventions, Structural Seed), status `final`, 2026-10-12
- **Method:** for each scenario, two subgroups (A=kb, B=retrieval, C=generation/ui) each behave in a way that violates **no AD as written**, yet the resulting builds are incompatible or produce contradictory graded artifacts. Each scenario names the clash and the AD (new or tightened) that closes it.

---

## Verdict: **PASS WITH FINDINGS**

The spine's load-bearing ideas hold: content-addressed IDs with eval-time dangling checks (AD-2), a single B→C data contract (AD-3), config-row-only toggles (AD-4), and one-writer artifact classes (AD-5) eliminate the classic failure modes. But the attack found **2 critical and 5 high** scenarios where AD-compliant subgroups still ship incompatibly — all closable by tightening existing ADs or adding one AD; none require a paradigm change. The criticals (S1, S2, S4) sit directly on graded outputs (citations, CAP-8 reproducibility, the 100% resolvability criterion) and should be fixed before story slicing.

---

## S1 — The paper store has no artifact, no owner, no writer

**Behaviors (both AD-compliant):**
- **A** ships exactly what AD-5 class 2 names: `data/kb/chunks.jsonl` + `kb_stats.json`. The per-paper record (`arxiv_id, title, authors[], year, abstract, sections{...}, source_link, license` — defined in `pipeline-stages.md` §Knowledge-base schema) is *not* in AD-5's artifact list, so A treats it as internal to the build and never persists it. The chunk schema itself carries no title/year/source_link (`chunk_id, arxiv_id, section_name, section_rank, text, n_tokens, header_prefix`).
- **B** must fill `EvidencePack.hits[].{title, year, source_link}` (AD-3) but has no sanctioned artifact to read them from. Compliant options: re-parse `data/raw/` (HF `scientific_papers` records — which do not even contain title/authors/year as clean fields) or derive `source_link` by convention (`arxiv.org/abs/{arxiv_id}` vs `/pdf/`). **C** (citation checker, UI "list of retrieved papers", CAP-7) and the RAGAS harness need the same fields and can re-derive them a *second* way (generation may legally import `kb` under AD-1).

**Clash:** three subgroups, three private derivations of paper metadata. Citations resolve to different title/link text depending on which subgroup's derivation produced them; dedup-removed or title-normalized papers diverge between A's view and B/C's view; `source_link` format is unpinned. AD-5's "one writer each" is silently violated in spirit because the paper store becomes multiply-*derived* (and temptingly multiply-*written*, e.g. B caching a paper lookup into `data/kb/` — which *is* an AD-5 violation the ADs don't prevent, because the artifact was never named).

**Severity:** critical — CAP-4 (every citation → paper title + link), CAP-7, and RAGAS all consume these fields; a graded demo shows dead or inconsistent links.

**AD fix (tighten AD-5, extend AD-3):** add `data/kb/papers.jsonl` to class 2 ("written only by `make kb`"), schema = the pipeline-stages per-paper record, with a canonical `source_link` format pinned in the Consistency Conventions. Tighten AD-3: `hits[].{title, year, source_link}` MUST be copied verbatim from the paper store at pack-build time; no consumer may re-derive them.

---

## S2 — `reports/metrics.json` has two legitimate writers and contradictory merge semantics

**Behaviors (both AD-compliant):**
- The Consistency Conventions namespace the file `retrieval.*` (B), `answer.*` (C), `speed.*` (C), and AD-5 class 3 names its writers as "`make index` / `make eval`" — but `evaluation/` is **B+C** (Structural Seed), and `team-split.md` explicitly says B writes the skeleton in story 4 and C "extends it" in story 8, with a trigger rule: "whoever changes a retrieval-side config re-runs **their own section** immediately."
- The spine also says "indexes and reports are **rebuilt wholesale, never patched in place**." So: **B** runs `make eval` over the E1–E6 ladder (no generation configured), rewriting `metrics.json` wholesale with only `retrieval.*` rows — fully compliant. **C** later runs the answer-level pass (RAGAS/EM-F1/speed), rewriting `metrics.json` wholesale with `answer.*`/`speed.*` — equally compliant. Each run erases the other's namespace. Alternatively C honors "re-runs their own section" by patching one namespace in place — which the spine's own convention forbids.

**Clash:** two compliant readings ("wholesale rebuild" vs "namespaced section re-runs") are mutually exclusive, and nothing pins whether one `make eval` invocation must compute all three namespaces. AD-1 permits *two or more* driver entry points over `retrieval` + `generation` without naming a single harness owner, so a C-forked eval script (story 8) is also AD-compliant. Worst case at the 10-30 freeze: the "binding reproduction" `make eval` run produces a file missing the rows the report cites, or B's last-minute retrieval tweak silently vacates every `answer.*` number in the PDF.

**Severity:** critical — CAP-8's core promise ("every report number traces to `make eval` output"; a teammate reproduces from clean state) can fail at the exact moment it is graded.

**AD fix (tighten AD-5 + new rule in Consistency Conventions):** `make eval` is a single atomic pipeline: one invocation always recomputes **all three namespaces** in one process and writes `metrics.json` once (temp file + rename). Partial re-runs are forbidden; a changed retrieval config requires a full `make eval`. Add an AD-1 clause: exactly one evaluation driver owns the run loop; answer-level metrics plug into it (metric-registry pattern), never a second script that writes `reports/`.

---

## S3 — The pack is B's object, but `gate.generator_declared` and full-system timings are C's state

**Behaviors (both AD-compliant):**
- **B** authors `EvidencePack` (AD-3: "retrieval's only output"). At `retrieve()` return time, `gate.generator_declared` cannot exist yet — the generator hasn't run. B leaves it `None`/`False` and fills `stage_timings_ms` with *retrieval* stage timings only (its notion of "stage").
- **C** must report sufficiency-gate rates split by trigger (evaluation-plan §4: score-gate fire rate vs generator-declared rate are different acceptance criteria) and `speed.*` p50/p95 "per stage … full system" including generation. With nowhere else to put this state, C's compliant move is to mutate the pack in place after generation (nothing in AD-3 forbids mutation) or to shadow the fields in a side log. The UI inspector and RAGAS harness — which AD-3 commands to "read the same object" — now see whichever version of the pack they were handed: pre-mutation (gate stats wrong) or post-mutation (timing provenance mixed into a B-authored object). Separately, *who executes* the score gate is unpinned: B short-circuiting (trim hits? skip nothing?), the driver checking `gate.score_gate_fired`, or C's generation wrapper returning the canned response are all layering-legal, and the canned-response string itself can exist in two copies (C's `generation/` module and C's UI), so the unanswerable-slice metrics measure a different path than the demo shows.

**Clash:** one object, two writers across a runtime boundary, no immutability rule, no ordering rule, no owner for gate execution or the canned response.

**Severity:** high — gate-rate metrics (≥80%/≤10% targets) and per-stage latency tables are graded (Q2/Q4/Q5) and can be silently attributed to the wrong trigger or wrong stage set.

**AD fix (tighten AD-3):** packs are immutable after `retrieve()` returns; `gate.generator_declared` is nullable with defined meaning "not yet evaluated." Introduce the (additive, core-schema) **AnswerRecord** as C's only output: `{query_id, answer, citations[], gate.generator_declared, generation_timings_ms, pack}`. Pin gate execution: the *driver* checks `gate.score_gate_fired` and calls `generation.canned_response()` — the single source of the canned text — instead of invoking the generator. `speed.*` = union of `pack.stage_timings_ms` + `AnswerRecord.generation_timings_ms`.

---

## S4 — "Citation resolves" has two compliant domains: pack hits vs the chunk store

**Behaviors (both AD-compliant):**
- **C-reading 1:** the citation checker resolves `[n]` positionally into the pack that produced the answer (`hits[n-1]`); a hallucinated `[7]` with 5 hits fails loudly. 100% resolvability then genuinely means "every claim points at retrieved evidence."
- **C-reading 2:** AD-1 lets `generation` import `kb` (strictly lower layer), and AD-5 makes `data/kb/chunks.jsonl` readable. A checker that resolves a citation by *title/arxiv_id lookup into the chunk store* is fully compliant — and it certifies a hallucinated citation that names a real paper as "resolved," even though the passage was never retrieved. CAP-4's success criterion ("100% citation resolvability, verified programmatically") *passes under both readings* while meaning opposite things; the UI click-through (which renders only pack passages) dead-ends on any store-resolved citation, and RAGAS faithfulness — a separate, free-tier-judged metric — is the only remaining net.

**Clash:** the resolution domain is never pinned in AD-3 or anywhere in the spine; evaluation-plan's "(each `[n]` → retrieved chunk)" is prose, not a rule, and "retrieved" is exactly the word in dispute.

**Severity:** critical — this is the project's flagship grounded-generation guarantee, directly graded (Q4), and the lenient reading is *easier* to pass, so it will be the natural implementation unless forbidden.

**AD fix (tighten AD-3):** "Citation resolution domain = the producing EvidencePack. `[n]` ∈ 1..len(hits) maps to `hits[n-1]`; out-of-range indices, store lookups, and title/arxiv-id fallbacks are resolver failures. The citation checker may not import `paperpilot.kb`." Optionally extend AD-2's eval-time validation: every citation in every evaluated answer must reference a `chunk_id` present in that answer's pack.

---

## S5 — `pack.query`: raw user query or effective (rewritten) query? Plus: no join key at all

**Behaviors (both AD-compliant):**
- **B-reading 1:** with HyDE on (E5a), the dense leg embeds a generated hypothetical passage; with multi-query on (E5b), 3–5 paraphrases go to both legs. B sets `query` = the *raw user question* (its notion: provenance of the request) and discards the rewrite text — the pack has no field for it.
- **B-reading 2:** B sets `query` = the *effective query string that produced these hits* (HyDE paragraph / first paraphrase), its notion of what the pack documents.
- **C** builds the RAGAS harness assuming `query` is the user question — RAGAS answer-relevancy scores the answer against `pack.query` — and the EM/F1 and "failed-before/works-now" join keys assume the same. Under reading 2, answer-relevancy is scored against a fake hypothetical passage: the E5a/E5b rows report garbage relevancy, and nobody notices because the numbers are plausible-looking floats.

**Clash:** AD-3's schema says only `query`. Compounding it: `data/eval/qrels.jsonl` and `qa_pairs.jsonl` are keyed by `query_id`, but the pack carries **no `query_id`**, so every join between runtime objects and eval artifacts is by query *text* — fragile against whitespace/case drift between A's label sheets and B's runner, and it allows C's harness to enumerate its own question set (qa_pairs answerable-only) while B's runner enumerates qrels, making `answer.*` and `retrieval.*` rows attributable to different question sets.

**Severity:** high — silently wrong RAGAS numbers in the ablation matrix (Q3/Q5) and unstable eval joins.

**AD fix (tighten AD-3):** `query` = the verbatim user question, always. Additive fields `rewrites[]` (multi-query variants) and `embedding_input` (HyDE text, dense-leg-only). Add `query_id` (additive) as the mandatory join key for every eval artifact and runtime record; RAGAS answer-relevancy is defined against `query`, never `embedding_input`.

---

## S6 — Section-aware weighting: raw or weighted scores in `leg_scores`?

**Behaviors (both AD-compliant):**
- **B-reading 1:** `leg_scores{bm25, dense}` hold the raw engine scores; the E6 section boost is applied transiently pre-fusion and vanishes from all records.
- **B-reading 2:** `leg_scores` hold the post-boost weighted scores, since those are "the leg scores that fed fusion."

**Clash:** C's retrieval inspector (a graded UI feature) displays "BM25 score" columns that either do or don't include an undocumented multiplier — a grader or teammate re-deriving BM25 scores sees numbers that don't match the engine; the report's E6 explanation can't show the boost's contribution because it was never recorded; and the documented E6Δ λ-blend fallback (`rerank_score + λ·section_weight`) has no `section_weight` field to draw from, forcing a schema change mid-sprint (allowed only via `pack_version` bump — recoverable but avoidable).

**Severity:** medium — no correctness break (RRF consumes ranks, not scores; the τ gate reads `rerank_score`), but credibility of the inspector and the E6 story suffers.

**AD fix (tighten AD-3):** `leg_scores` are always raw engine scores (pre-boost); when `use_section_weight` is on, an additive `section_boost` field carries the applied multiplier per hit.

---

## S7 — chunk_id determinism stops at "sha1": normalization, encoding, and a single implementation are unpinned

**Behaviors (both AD-compliant):**
- **A on macOS** builds the KB: text and `section_name` pass through whatever normalization A's cleaner happens to apply (macOS toolchains and editors routinely introduce NFD; `\r\n`, `\xa0`, trailing whitespace are unregulated), then `sha1(arxiv_id + "\x1f" + section_name + "\x1f" + text)`.
- **A's rebuild on Linux/Colab** (the documented path: bge-m3 upgrade on Colab T4; a teammate's clean-clone reproduction for CAP-8) applies the same *AD text* but a different byte stream — NFC vs NFD, different whitespace — and mints different chunk_ids for the "same" chunks.

**Clash:** AD-2's guarantee is "same **inputs** → identical IDs," which is circular: if normalization differs, the inputs differ, so both builds obey AD-2 while qrels — 1,000+ hand-labeled class-1 rows keyed by `chunk_id` — dangle wholesale. AD-2's eval-time dangling check *does* fail loudly (good), but the recovery options are relabeling the entire eval set or byte-exact environment archaeology, days before freeze. The hash recipe is also unpinned at the mechanical level (UTF-8 `encode`, `hexdigest[:16]`, `\x1f`-collision hygiene) and nothing requires *one* shared implementation — B's eval validator or A's rebuild each re-implementing the recipe is compliant.

**Severity:** high — the entire labeling investment and CAP-8 cross-machine reproduction ride on byte-level determinism the AD asserts but does not specify.

**AD fix (tighten AD-2):** pin the recipe exactly: `sha1(NFC(arxiv_id) + "\x1f" + NFC(section_name) + "\x1f" + NFC(text)).encode("utf-8")` → `hexdigest()[:16]`, with whitespace canonicalization (`\s+`→single space, strip) applied before hashing and NFC mandated via `unicodedata.normalize`. Mandate a single implementation `paperpilot.core.ids.chunk_id()` that `kb`, `retrieval`, and `evaluation` must all import — re-implementation is a lint error. Extend `kb_stats.json` to record the input dataset archive hash so "same inputs" is checkable.

---

## S8 — `chunk_store_hash` has no defined referent: file bytes vs identity set

**Behaviors (both AD-compliant):**
- **B-reading 1:** `chunk_store_hash` = sha1 of the `chunks.jsonl` **file bytes**. A deterministic *IDs* rebuild (per S7-fixed or by luck) still produces different bytes if JSON serialization drifts (key order, separators, `n_tokens` from an unpinned tokenizer, line endings).
- **B-reading 2:** hash = sha1 over the sorted `chunk_id` set (identity-level).

**Clash:** after a teammate's clean-clone `make kb`, reading-1 loaders refuse to serve a perfectly valid index (loud but mysterious failure; "just rebuild" burns hours of laptop CPU on re-embedding), while reading-2 loaders serve across byte-different-but-identical stores. The manifest's `config_row` field has the same disease (S11).

**Severity:** medium — recoverable, but it strikes exactly at the CAP-8 clean-clone demo and the freeze-day reproduction run.

**AD fix (tighten AD-5):** define `chunk_store_hash = sha1(sorted(chunk_ids) joined by "\n")` — identity-level, not byte-level — and pin `chunks.jsonl` serialization (sort_keys, separators, LF, trailing newline) in the Consistency Conventions.

---

## S9 — The UI is a toggle path AD-4 forgot — and Q2's graded numbers come from it

**Behaviors (both AD-compliant):**
- **C-reading 1:** the Streamlit app ships a sidebar of flag overrides (`use_rerank`, `use_hyde`, …) — natural for the retrieval inspector, and arguably covered by "the **CLI** may select one row or override declared flags for ad-hoc runs" stretched to mean "any interactive driver."
- **C-reading 2 / B-report-reading:** AD-4 says config rows are "the **only** toggle path" and "a report number is reproducible only from a committed config row id." But `evaluation-plan.md` §5 requires the Q2 speed numbers to be "recorded **from the UI run**" — five demo queries, per-stage latency, verbatim into the report. Under the strict reading there is no committed row for a UI run with sidebar overrides, so Q2's graded numbers are either unreproducible (violating AD-4) or the UI must be locked to a pinned row (which reading 1's sidebar forbids).

**Clash:** the spine's only ad-hoc-override escape hatch names the CLI; the UI is a different driver, and the one graded metric that must flow through it (Q2 latency) has no compliant provenance story.

**Severity:** high — Q2 is directly graded and the speed table goes into the PDF verbatim.

**AD fix (tighten AD-4):** add a committed `demo` row (pinned to the E6/best config at freeze). The UI runs in demo mode = that row, no overrides; any interactive override must display "ad-hoc — not reportable" and is barred from `reports/`. `speed.*` rows record row id + git commit exactly like every other report number, sourced from the demo-row UI run.

---

## S10 — Class 1 "human-written, never machine-overwritten" collides with the labeling pipeline itself

**Behaviors (both AD-compliant readings):**
- **Reading A (class-granular):** nothing machine-written may appear under `data/eval/` — but CAP-6's qrels flow is machine-fed: pooling (top-10 per leg, a retrieval run) generates the candidate pools, and adjudication of 15–20% double-labeled items is resolved by a script merging label sheets into the final `qrels.jsonl`. Under this reading both steps are violations, and the only legal home for pool candidates is `reports/` (class 3) — which A's labeling workflow (annotation sheets referencing candidates) was not planning to read.
- **Reading B (file-granular):** machine-written *new* files under `data/eval/` (e.g. `candidates.jsonl`) are fine since no existing file is overwritten — but then derived machine files sit in a git-tracked class-1 tree, get committed by accident, and re-pooling after a retrieval change rewrites them (a machine mutation inside class 1).

**Clash:** the AD's wording doesn't say which granularity it means; A coordinates labeling around one reading, B's pooling run assumes the other, and either combination produces either a workflow blockage or polluted git history at freeze.

**Severity:** medium — process friction and repo hygiene rather than runtime breakage, but it lands during the Week-4 labeling sprint when there is no slack.

**AD fix (tighten AD-5):** reword class 1 as "human-originated": `data/eval/*.jsonl` are git-tracked and generated *only* by the labeling pipeline from human label sheets (deterministic merge script, reviewed via PR); machine re-derivation (pooling candidates, agreement stats) writes exclusively to class-3 paths (`reports/pooling/`, `reports/iaa/`).

---

## S11 — Manifest `config_row`: provenance or validity? The refusal clause's scope is ambiguous

**Behaviors (both AD-compliant):**
- **B-reading 1:** `config_row` in the index manifest is *provenance* (which row happened to be selected at `make index` time); the loader enforces exactly what AD-5 lists — `chunk_store_hash` and `embedding_model` — and one shared index serves E1–E6 (rows differ only in non-index flags: rerank, rewrite, section-weight, gate).
- **B-reading 2:** a strict implementer reads the manifest's `config_row` as a *validity* constraint (defensible: why record it otherwise?) and refuses to serve when the manifest row ≠ the current row — so `make eval` over the ladder rebuilds the FAISS/BM25 index per row, multiplying laptop-CPU index time ×7 inside the graded harness, and C's UI (expecting one warm index) times out or reports absurd `speed.*` numbers.

**Clash:** the field is mandatory in the manifest but its semantics and enforcement are undefined; the two readings differ by an order of magnitude in eval runtime.

**Severity:** medium.

**AD fix (tighten AD-5):** state that `config_row` is provenance-only and enumerate the index-validity keys exhaustively (`chunk_store_hash`, `embedding_model`, `dim`, `nlist`, sparse-engine id) — the loader's refusal check is exactly that set; all other row flags never require re-indexing.

---

## S12 — "Consumers tolerate unknown fields" — but not absent or `None` known fields

**Behaviors (both AD-compliant):**
- **B** under E1 (BM25-only) or E2 (dense-only) builds packs where one leg never ran and no reranker exists. AD-3's schema lists `leg_scores{bm25, dense}` and `rerank_score` unconditionally. B may emit `leg_scores.dense = None`, omit the key, or omit the whole `leg_scores` object — all defensible readings of a schema whose nullability was never specified.
- **C**'s UI inspector, citation layer, and RAGAS harness were developed against full E6 packs; they dereference `hits[i].leg_scores.dense` / `.rerank_score` and crash — or worse, silently render `None` as `0.0` — on baseline-row packs. The additive-tolerance rule protects against *extra* fields, the exact opposite direction.

**Clash:** E1/E2 packs are first-class outputs of the ablation runner yet schema-ambiguous; C's consumers are only guaranteed against the failure mode they won't encounter.

**Severity:** low — crash-class, caught in CI quickly, but it generates cross-subgroup bug noise every time a baseline row runs through any C consumer.

**AD fix (tighten AD-3):** specify per-field presence: `leg_scores` keys present iff that leg ran (`null` forbidden; omit instead), `rerank_score` present iff `use_rerank`; consumers must feature-detect, and pydantic schemas in `core` encode the conditionals so both sides import one truth.

---

## Summary table

| # | Scenario | Clash in one line | Severity | AD to fix |
|---|----------|-------------------|----------|-----------|
| S1 | Paper store orphaned | chunks ship with no paper metadata artifact; B/C each re-derive title/year/link | critical | AD-5 + AD-3 |
| S2 | metrics.json dual writer | wholesale-rebuild vs namespaced-section rules contradict; B and C runs clobber | critical | AD-5 + conventions + AD-1 |
| S3 | Pack carries C's state | `gate.generator_declared` / full timings written into B's object; mutation, ordering, gate-execution ownership unpinned | high | AD-3 |
| S4 | Citation resolution domain | pack-hits vs chunk-store lookups both legal; hallucinated citations can "resolve" | critical | AD-3 (+AD-2) |
| S5 | `query` semantics + no join key | raw vs rewritten query breaks RAGAS; no `query_id` to join eval artifacts | high | AD-3 |
| S6 | leg_scores raw vs weighted | E6 pre-fusion boost's provenance invisible or mislabeled in inspector | medium | AD-3 |
| S7 | chunk_id byte determinism | NFC/NFD + whitespace + recipe unpinned; cross-OS rebuild invalidates all qrels | high | AD-2 |
| S8 | chunk_store_hash referent | file-bytes vs identity-set; clean-clone rebuilds deadlock the loaders | medium | AD-5 |
| S9 | UI vs config-row-only | Q2 graded speed numbers come from UI runs that strict AD-4 can't trace to a row | high | AD-4 |
| S10 | Class-1 machine writes | pooling candidates + adjudication scripts vs "never machine-overwritten" | medium | AD-5 |
| S11 | manifest config_row meaning | provenance vs validity → shared index or ×7 rebuilds inside make eval | medium | AD-5 |
| S12 | field nullability | E1/E2 packs' absent legs crash or zero-fill in C consumers | low | AD-3 |
