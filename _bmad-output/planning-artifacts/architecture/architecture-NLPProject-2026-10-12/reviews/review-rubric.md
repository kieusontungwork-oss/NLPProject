# Review: ARCHITECTURE-SPINE.md (PaperPilot) — rubric checklist

**Verdict: PASS WITH FINDINGS** — no critical or high findings; the spine fixes the real A/B/C divergence surfaces (schemas, ports, toggles, artifacts, metrics namespaces) and is ratifiable against the greenfield repo. Findings below are medium/low hardening items.

Reviewed: 2026-10-12 · Reviewer: architecture-review subagent · Inputs: ARCHITECTURE-SPINE.md, SPEC.md + 4 companions, repo state (no `src/`; legacy `scripts/`, `tests/`, `research/` present).

## Checklist results

### 1. Fixes the real divergence points for A/B/C — covered, two residual gaps

Covered (the incompatibility surfaces two subgroups would actually collide on):

- **A→B chunk contract:** chunk schema pinned by reference to `pipeline-stages.md` (Conventions table), identity pinned by AD-2's content-addressed `chunk_id`, rebuild determinism + eval-time dangling-ID check. A and B cannot diverge on the KB interface.
- **B→C runtime contract:** AD-3 `EvidencePack` — field-level pinned, versioned, additive-only, single consumer shape for generator / citation checker / RAGAS / UI inspector. This is the single riskiest B/C boundary and it is fully decided.
- **Cross-subgroup call discipline:** AD-1's port list (`SparseRetriever`, `DenseRetriever`, `Reranker`, `QueryRewriter`, `Generator`) + strict layering kills lateral coupling; diagram matches the rule.
- **Experiment semantics:** AD-4 config rows as the only toggle path, pydantic-rejected unknown keys — B's harness and C's report numbers share one mechanism.
- **On-disk state:** AD-5's three classes with single writers + manifests kills stale index↔chunk pairings between A's `make kb` and B's `make index`.
- **Shared output file:** `retrieval.*` / `answer.*` / `speed.*` namespace split mirrors team-split.md's `make eval` ownership — B and C writing one `metrics.json` cannot collide.
- **Units & naming:** timings float ms, ISO-8601 UTC, flag names enumerated — prevents metric-key and unit drift.

### 2. Every AD enforceable and prevents its stated divergence — yes, one tension

- AD-1: mechanically enforceable (import-lint test over the layer order; interface imports from `core`).
- AD-2: sha1 recipe is deterministic; `make eval` pre-flight validation makes the failure loud, as stated.
- AD-3: versioned dataclass in `paperpilot.core.schemas`; additive-only rule is reviewable.
- AD-4: pydantic schema rejecting unknown keys is directly enforceable at load.
- AD-5: manifest fields (`chunk_store_hash`, `embedding_model`) with loader refusal is enforceable — see Finding 2 for the class-1 tension.

### 3. Deferred cannot cause divergence — yes

Every deferred item sits behind an already-decided seam: sparse engine and generator model behind ports + config rows (AD-1/AD-4); τ is a config value with gate semantics already fixed in `pipeline-stages.md`; E7/Q5-loop are additive ablation rows governed by AD-4 + team-split's harness-extension rule; bge-m3 swap is bound by AD-5's manifest; chunking variants are extra E-rows. The SentiScope-leftovers disposition is repo hygiene, not a subgroup-divergence vector (folded into Finding 4).

### 4. Named tech current — plausible, nothing suspicious; lock file absent

`rank-bm25 0.2.2`, `all-MiniLM-L6-v2`, `bge-m3`, `bge-reranker-v2-m3`, `armanc/scientific_papers` are all real and correctly characterized. The forward-pinned versions (pydantic 2.14.1, sentence-transformers 6.1.0, faiss-cpu 1.15.1, ir-measures 0.4.3, ragas 0.4.3, streamlit 1.65.0) are internally consistent and plausible; none verifiable offline. Note stack.md's "repo already uses uv scripts" — no `pyproject.toml`/`uv.lock` exists at root yet, so the Stack table is currently unenforced. See Finding 5.

### 5. Ratifies existing reality — yes

Spine's Structural Seed creates a new `src/paperpilot/` tree (repo has none — correct greenfield ratification, no pretend-migration of legacy code); legacy `scripts/`, `tests/`, `research/` are explicitly acknowledged as leftovers with a disposition decision; `docs/` and `papers/` preserved as spec sources. No contradiction with the Week-0 spike verdict (HF scientific_papers, section structure) — section-aware weighting matches the verified 99%-named-sections finding.

### 6. Spec capability coverage — complete

CAP-1..CAP-8 all present in the Capability → Architecture Map, each with a module home and governing ADs/conventions; bindings in the front-matter (`binds: CAP-1..CAP-8`) and per-AD Binds lines make the mapping traceable in both directions. Verified against each CAP's success criteria: one-command rebuild (CAP-1↔AD-5 class 2), per-leg config switching (CAP-2↔AD-4), ablation matrix reproducibility (CAP-3/5↔AD-4), citation resolution + gate (CAP-4↔AD-3 gate fields), IAA artifacts (CAP-6↔AD-2/5 class 1), UI inspector (CAP-7↔AD-1/3), report tracing (CAP-8↔AD-4/5). No capability left unmapped.

### 7. Altitude-owned dimensions — decided; two minor undeclared spots

The operational/environmental envelope is explicitly decided in the scope line (laptop-local, CPU-first, $0, Colab T4 bursts, Ollama as the only local server, no deployment — ratifying SPEC constraints/non-goals); infrastructure/provider strategy is decided (stack table + fallback ladders); operations are decided (Makefile runners, AD-5 artifact lifecycle, logging convention, no-silent-degradation error rule). No whole dimension is silent. Gaps: secrets handling (Finding 3) and test framework/layout (Finding 4).

### 8. Mermaid diagrams — valid and structural

- AD-1 `graph TD`: 6 nodes, 11 edges, quoted labels with subgroup tags; matches the written layer rule exactly (ui/evaluation terminal; generation→core only, not retrieval). Valid syntax.
- Structural Seed `flowchart LR`: 3 subgraphs (artifact classes), labeled solid and dotted edges (`-->|...|`, `-.->|...|`), valid quoted edge labels including `·` separators. Conveys the artifact-class dataflow, including the manifest-checked serve path. Valid syntax.

## Findings

| # | Severity | Checklist | Finding |
| --- | --- | --- | --- |
| 1 | medium | 1 | **Shared local-LLM client not pinned.** `QueryRewriter` (B: HyDE/multi-query) and `Generator` (C) both call the same Ollama server, but the spine doesn't say whether the Ollama adapter (model pinning, timeouts, streaming/parsing, marker detection) is one shared core component or two subgroup-owned adapters — two subgroups can build divergent clients, and a Week-3 model-tag swap then has to be made twice. Add one line: the Ollama client lives in core and both ports adapt over it. |
| 2 | medium | 2, 5 | **AD-5 class-1 "never machine-overwritten" vs the pooling workflow.** evaluation-plan's qrels pooling machine-generates the candidate pool that annotators then label, but `data/eval/*.jsonl` is class-1 human-written and classes 2/3 don't cover the draft pool either. Strict reading outlaws the machine step A+B rely on. Clarify: pooling drafts are class-3 scratch written by `make eval` (or a `make pool` target); only hand-adjudicated rows enter class-1 files. |
| 3 | low | 7 | **Secrets/credential handling undeclared.** Free-tier hosted adapters (Generator swap, RAGAS judge) imply API keys; AD-4 rightly bans env-var toggles but nothing states where credentials live (uncommitted `.env`, never in configs/ rows). Laptop-local scope keeps this minor, but one convention line prevents a key landing in git or in a config row. |
| 4 | low | 7 | **Test framework and layout unnamed; legacy `tests/` collision.** Conventions say "tests use local fixtures, no network" but no framework (pytest), no test layout, and the Deferred SentiScope disposition should be bound to the bootstrap story — until then a default `pytest` run collects the abandoned `tests/test_classifiers.py` and fails confusingly. |
| 5 | low | 4 | **Stack table unlocked.** Pinned versions are plausible but the repo has no `pyproject.toml`/`uv.lock`, so nothing enforces them; bootstrap story must `uv lock` (and re-verify ragas/faiss/ST pins resolve at those exact versions). Also note Ollama tags Qwen2.5-7B/Llama-3.1-8B are 2024-era — consistent with the spec, but worth a currency glance at the Week-3 decision. |
| 6 | low | 1 | **`retrieve(query, k)` not in the core-interface list.** The fused entry point the UI driver (C) calls across the B boundary appears only in the Structural Seed; AD-1's port enumeration omits it. SPEC success criteria pin the signature, so divergence risk is minimal — adding it to the AD-1 interface list closes the gap. |

## Positives worth keeping

- EvidencePack's `gate: {score_gate_fired, generator_declared}` makes the sufficiency-gate rates (≥80%/≤10% CAP-4 criteria) directly measurable from the contract object — a clean B/C alignment.
- AD-5 manifests binding `embedding_model` + `chunk_store_hash` pre-solves the deferred bge-m3 swap and the qrels-invalidation problem simultaneously.
- The scope line deciding the entire operational envelope up front (laptop, $0, Colab T4, Ollama-only, no deployment) is exactly what a feature-altitude spine should do.
