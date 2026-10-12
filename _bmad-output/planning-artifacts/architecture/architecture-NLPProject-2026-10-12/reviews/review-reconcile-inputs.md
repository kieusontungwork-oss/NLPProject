# Review: Reconcile Inputs — ARCHITECTURE-SPINE.md vs spec package

**Verdict: PASS WITH FINDINGS**

Reviewed: `ARCHITECTURE-SPINE.md` (status: final, 2026-10-12) against `SPEC.md` + companions (`stack.md`, `pipeline-stages.md`, `evaluation-plan.md`, `team-split.md`).

Scope of check: CAP coverage, hard constraints, success-signal representability, quiet requirements.

---

## What checked out clean

- All 8 CAPs have real Capability→Architecture Map entries backed by actual structural elements (modules, Makefile targets, artifact classes, config rows) — no vaporware mappings.
- `make kb / index / eval / ui` flows: all four targets present in the Structural Seed; the SPEC's clean-clone success signal (`make kb && make index && make ui`) is representable.
- No-SQL-LIKE and no-hosted-mashup: honored via the stack ladder (`rank_bm25` first) and the paradigm's "no orchestration framework; graded stages implemented and explained by us."
- $0 / laptop-CPU / Colab-T4 / Ollama-only envelope: stated verbatim in the spine front-matter and Design Paradigm.
- Gate two-trigger semantics: both triggers (`score_gate_fired`, `generator_declared`) are explicit fields in the EvidencePack (AD-3); τ calibration deferred with semantics pinned to `pipeline-stages.md`. Gate-rate targets (≥80% / ≤10%) are computable from `qa_pairs` `answerable` field via `make eval`.
- Citation resolvability 100%: citation checker named as an EvidencePack consumer (AD-3) and `generation/` owns citations; representable.
- Section-aware weighting pre-fusion placement: the Design Paradigm pipeline order is `... dual-leg retrieve → section-weight → fuse → rerank ...` — the E6-killing placement mistake is structurally excluded.
- `header_prefix` on chunks: in the EvidencePack hit schema (AD-3) and chunk schema by reference to `pipeline-stages.md`.
- Per-stage latency: `stage_timings_ms{}` in EvidencePack + timing convention in Consistency Conventions.
- Deterministic rebuilds protecting qrels / `gold_chunk_ids` / citations: AD-2 content-addressed IDs + `make eval` dangling-ID precheck directly serve the SPEC's reproducibility signal.
- Config-row-only toggling (AD-4) + metrics namespace split (`retrieval.*`/`answer.*`/`speed.*`) matches team-split's `make eval` ownership contract, including the trigger rule's section boundaries.
- Chunking-strategy ablation variants, E7 mechanism, Q5 loop, extra novelty features: all correctly parked in Deferred, matching SPEC open questions.

---

## Findings

### F1 — HIGH: "Failed-before / works-now" queries have no architectural home

**Dropped:** The SPEC's explicit success signal — "at least 2 documented 'failed-before/works-now' example queries for every innovation we keep," each recorded with **both rankings** (wrong top-10 without the innovation, correct with it) — appears nowhere in the spine. AD-5's three artifact classes don't allocate it: class 1 lists only code, configs, `data/eval/*.jsonl` (qrels, qa_pairs), labeling guidelines; class 3 lists only `indexes/` and `reports/metrics.json`. No module owns recording or rendering these query dossiers, and no AD governs them. Team-split makes this a graded Q3 evidence artifact ("ablation matrix, failed-before/works-now queries"), and the SPEC Success signal section requires it — so this is a load-bearing deliverable with no writer, no artifact class, and no owning layer.

**Spec source:** SPEC CAP-3 success (last bullet); SPEC §Success signal #3; `pipeline-stages.md` ladder note ("Each retained innovation needs ≥2 documented 'failed before / works now' queries"); `team-split.md` Question→capability map (Q3 row).

### F2 — MEDIUM: "Rows E1–E7" under-specifies the ablation ladder (E5a/E5b/E6Δ) and omits the one-flag-delta rule

**Dropped:** AD-4 says "rows E1–E7 mirror the ablation ladder," but the ladder in `pipeline-stages.md` has **nine** rows: E1, E2, E3, E4, **E5a, E5b**, E6, **E6Δ**, E7. Read literally, "E1–E7" drops the E5a/E5b split and — more damaging — the **E6Δ diagnostic row**, which is load-bearing for the section-aware novelty claim (it separates "overshadowed by the reranker" from "no signal" and gates the λ-blend fallback). Separately, the attribution property the whole matrix exists for — "each row differs from the previous by exactly one flag, so any metric delta is attributable to that single innovation" — is not stated as an AD-4 rule; it is only weakly implied by "mirror the ladder." A config author constructing rows from the spine alone could produce multi-flag deltas or skip E6Δ without violating any spine rule.

**Spec source:** SPEC CAP-3 success (ablation matrix + "differs from the previous by exactly one flag"); `pipeline-stages.md` §Ablation ladder (E5a/E5b/E6Δ rows, E6Δ rationale, λ-blend fallback).

### F3 — MEDIUM: English-only corpus constraint carried by nothing downstream of the SPEC

**Dropped:** SPEC Constraints: "English-only corpus; chunking documented as an explicit design choice." This sentence appears **only** in SPEC.md — no companion restates it, and the spine's kb stage list (`acquire → clean → dedup → chunk → index`) and AD rules don't carry it. Since the chosen dataset (HF `scientific_papers` arxiv split) is predominantly but not guaranteed uniformly English, the language filter is a real cleaning-stage behavior that must exist somewhere. With zero re-statement anywhere in the build substrate, this is exactly the kind of quiet constraint that evaporates during implementation.

**Spec source:** SPEC §Constraints (final bullet pair).

### F4 — MEDIUM: Q2 speed protocol (five fixed demo queries, latency recorded from the UI run) has no representation

**Dropped:** `evaluation-plan.md` §5 and SPEC CAP-7 success require five fixed demo queries run end-to-end **in the UI**, with per-query end-to-end latency + per-stage breakdown "recorded from the UI run," numbers going into the report verbatim. The spine gives this no home: the five demo queries are not an allocated artifact (not in `data/eval/`, not in configs), the UI is declared a terminal driver with no write path to any class-3 artifact, and `reports/metrics.json` is written **only** by `make eval` (AD-5). The spine also doesn't reconcile this with SPEC CAP-8's "every number in the report traces back to `make eval` output" — a mild spec-internal tension the architecture should have resolved (e.g., a `speed.q2_demo` section emitted by an eval-driven replay, or an explicit UI-run log artifact). Not impossible to build, but currently unrepresentable without breaking an AD-5 writer rule.

**Spec source:** SPEC CAP-7 success (five demo queries, per-query speed measured and recorded); SPEC §Success signal #1 ("per-query latency recorded"); `evaluation-plan.md` §5; `team-split.md` Q2 row.

### F5 — MEDIUM: Agreement report (IAA ≥80% evidence) fits no artifact class and no metrics namespace

**Dropped:** CAP-6 success requires "an agreement report showing raw agreement and Cohen's κ, with IAA ≥80%," committed to the repo (`evaluation-plan.md` §3 step 4). Under AD-5 the agreement report is orphaned: class 1 is *human-written* source of truth (labeling guidelines qualify; a κ report is computed, not written); class 3 is *machine-derived written only by `make index`/`make eval`* — but the metrics matrix and the spine's `retrieval.*/answer.*/speed.*` namespace contain no labeling/agreement section, so `make eval` as specified never produces it. Either `make eval` needs a `labeling.*` metrics section or class 1 must explicitly include the agreement report; as written, the "one writer each" guarantee has a hole for a graded Q4 artifact.

**Spec source:** SPEC CAP-6 success; SPEC §Constraints (IAA ≥80% over ≥1,000 records); `evaluation-plan.md` §3 and §6 (count table incl. raw agreement + κ); `team-split.md` Q4 row.

### F6 — LOW: Corpus hard minimums and the Q1.3 kb_stats four-figure requirement not asserted in the spine

**Dropped:** The assignment hard minimums (≥10,000 documents, ≥100,000 words — "aim well above, dedup/cleaning shrink the raw count") and the specific `kb_stats.json` contents (papers, chunks, words, **types**, chunk-size histogram — the four figures Q1.3 grades) appear nowhere in the spine. AD-5 names `kb_stats.json` as a class-2 artifact, but the spine's "paper and chunk schemas exactly as `pipeline-stages.md` defines" covers only paper/chunk schemas — the kb_stats schema is left floating by reference to nothing. Not contradicted, but the graded Q1.3 figures deserve a pinned home.

**Spec source:** SPEC §Why (assignment demands), CAP-1 success; SPEC §Constraints (first hard rule); `pipeline-stages.md` §Knowledge-base schema.

### F7 — LOW: HyDE leg-routing semantics not carried by the spine

**Dropped:** The correctness-critical routing rule — HyDE's hypothetical passage is embedded for the **dense leg only** while BM25 always sees the raw query (a hallucinated paragraph would poison keyword matching); multi-query variants go to **both** legs, RRF-pooled per leg — lives only in a `pipeline-stages.md` diagram annotation and SPEC CAP-3 prose. The spine names the `QueryRewriter` port and `use_hyde`/`use_multi_query` flags but states no routing contract, so an adapter author reading the spine can silently implement "HyDE to both legs" without violating any AD.

**Spec source:** SPEC CAP-3 intent (Query rewriting routing bullets); `pipeline-stages.md` pipeline diagram annotations and E5a/E5b rows.

### F8 — LOW: RRF k=60 default not pinned

**Dropped:** `stack.md` fixes RRF at k=60 ("course-designated approach"). The spine names the `rrf_k` config flag (consistent with team-split's "whoever changes... RRF k... re-runs") but records no default and no "course-designated, do not drift" guard. A config-row author can change it without any spine-level flag that this is the comparability anchor for E3.

**Spec source:** `stack.md` Hybrid fusion row; `pipeline-stages.md` fusion stage.

### F9 — LOW: Envelope says "Ollama is the only local server" while the deferred sparse ladder's last resort is Elasticsearch

**Contradicted (latent):** The spine's operational envelope hard-codes "Ollama as the only external process / no deployment," but the Deferred section keeps the spec's Elasticsearch last resort — a JVM server on every teammate's laptop, which would violate the envelope sentence if the benchmark ever escalates that far. Stack.md's mitigations (pinned version, `docker-compose.yml`, `make index` rebuild) are not referenced in the spine's Deferred entry, so the tension is unreconciled rather than conditional.

**Spec source:** SPEC §Open Questions (sparse engine ladder); `stack.md` Sparse retrieval row; spine front-matter `scope` + Design Paradigm.

### F10 — LOW: RAGAS judge LLM sits behind no named port

**Dropped:** The evaluation plan specifies "RAGAS (free-tier judge; **Ollama fallback**)." The spine's port list is `SparseRetriever`, `DenseRetriever`, `Reranker`, `QueryRewriter`, `Generator` — the judge LLM is a sixth engine boundary (separate from the answer `Generator`: different model, different failure mode, free-tier-first ordering) and is not covered by AD-1's interface discipline. The judge fallback swap would currently be an ad-hoc code path rather than a config row, undercutting AD-4's "every toggle is a config row" intent.

**Spec source:** `evaluation-plan.md` §4 metric matrix (RAGAS row); SPEC CAP-5 intent (RAGAS answer-level metrics); `stack.md` Generator row (free-tier hosted API "optional for demo/RAGAS").

### F11 — LOW (informational): Deadlines, originality, and data-discipline constraints are plausibly deferred

Freeze 2026-10-30 / submit 2026-11-05 / deadline 2026-11-07, the >30%-overlap disqualification rule, bytes-on-disk dataset admission, and permissive-license/ToS discipline are process-and-schedule constraints with no architectural expression. They are carried by `team-split.md` milestones and the submission checklist; the spine neither contradicts nor needs them. Accepted as deferred.

---

## Summary

The spine is structurally faithful: every CAP has a real home, the pipeline order encodes the two subtle placement decisions the spec fought for (section-weight pre-fusion; HyDE dense-only would fit the same way if stated), and the artifact/config/invariant machinery (AD-2, AD-3, AD-4, AD-5) covers most of the reproducibility story. The gaps are concentrated in **qualitative and labeling-side deliverables** — failed-before/works-now dossiers, the agreement report, the Q2 UI speed protocol — which the AD structure (built around machine-written metrics and config rows) silently drops, plus one spec-only constraint (English-only) that nothing downstream restates. F1 should be fixed before build stories are cut; F2–F5 should be fixed in the same pass; F6–F10 are cheap clarifications.
