# Story Delivery Loop — Coding Agent Instructions

Reusable per-story instruction prompt for the WIDSKaggle repo. Invoke with:
`do story <N.M> using docs/agent-workflows/story-delivery-loop.md`

---

You are the coding agent for this repository. Your orders: take story `<N.M>` from backlog to merged, running the ENTIRE loop below autonomously — build, test, push, PR, adversarial fresh-context review, patch, retest, merge, post-merge bookkeeping — then STOP and report back to the owner. Do not start the next story without an explicit order. Never ask questions mid-loop unless a decision genuinely requires human intent (see "Escalate only if"); everything else is yours to decide, and you are accountable for the decisions you make.

**Token discipline (binding on every step).** Model tier and token count are separate levers — apply both:
- **Pass paths, not prose.** Prompts to external skills and subagents carry file paths (+ line ranges where known), ids, and short inline snippets (≤ ~30 lines). Never inline a full document the callee can read from the repo itself.
- **Feed exactly the listed inputs.** Each step's input list is exhaustive — nothing more.
- **One model tier throughout.** `glm-5.3-flash` for every external step — spec-writing, build, tests, gap audits, and all review layers (hunter, test-audit, acceptance).

## 0. Ground truth (read before writing any code)

1. `AGENTS.md` — repo policy (branch/PR rules, credentials, never touch `evals/` or `skills/`).
2. `_bmad-output/planning-artifacts/architecture/architecture-WIDSKaggle-2026-09-03/ARCHITECTURE-SPINE.md` — invariants AD-1…AD-14 bind ALL implementation. Read only the ones the story touches.
3. `_bmad-output/planning-artifacts/epics.md` — the story's acceptance criteria, verbatim (that story's section only).
4. `_bmad-output/implementation-artifacts/epic-<N>-context.md` — epic-level constraints and cross-story dependencies.
5. `_bmad-output/implementation-artifacts/deferred-work.md` — absorb anything assigned to this story.
6. The two most recent specs in `_bmad-output/implementation-artifacts/spec-*.md` — read ONLY their frontmatter + Spec Change Log + Review Findings sections; those carry binding decisions. Their role as format template is delegated to `bmad-spec` in Step 2 (it reads the template itself).
7. The landed code you will extend or mirror (`src/`), plus its tests (`tests/`). Mimic, never invent.

Within the same session, ground-truth files already read may be skipped on loop re-entry. After a `git pull` or in a new session, re-read only the ground-truth files the pull touched (`git diff --name-only HEAD@{1} origin/main -- <ground-truth paths>`); if none changed, skip the re-read. Ground truth is never assumed fresh across sessions.

## 0.5 External runner invocation pattern

Every external skill invocation in this loop follows ONE pattern:

`opencode run -m <model> -c model.effort=high --command <skill> "<headless prompt>"`

- **Headless-safe**: the prompt pre-supplies every input the skill needs as repo paths + line ranges, ids, or short inline snippets — never session state, earlier steps, or "as discussed". The external run sees nothing but the prompt, but it executes in the repo, so it reads the referenced files itself. Each calling step lists its required paths/ids.
- **Fallback**: if the external runner is unavailable — not installed, command fails, or the timeout expires — run the same skill in-session instead, regardless of which model this loop itself is running on. Note the fallback in the Step 13 report. An in-session fallback for a review skill must still respect Step 8's fresh-context rules.
- **Timeouts**: 30 minutes for `bmad-spec` and `bmad-code-review`; 60 minutes for `bmad-build` and `bmad-testarch-automate`.

Calling steps reference this section as "invoke per §0.5" and name only skill, model, timeout, and inputs.

## 1. House conventions (non-negotiable, enforced by reviewers)

- Python 3.11, `.venv/bin/python` / `.venv/bin/pytest`. Bare `python3` is 3.14 — never use it.
- Modules: `from __future__ import annotations` first; module docstring citing story/AD/FR ids; `logger = logging.getLogger(__name__)`; typed exception hierarchy per stage subclassing a stage base `RuntimeError` with actionable messages naming offending values.
- Values: `@dataclass(frozen=True)`; `TypedDict` for dict schemas; read-only mappings via `MappingProxyType`; full modern type annotations (`str | Path`, `frozenset[...]`).
- Persistence: parquet + `<stem>.manifest.json` sidecar `{"spec": ..., "parquet_sha256": ...}` written `json.dumps(..., indent=2, sort_keys=True) + "\n"`; atomic tmp-file + `os.replace`; idempotent skip only when sidecar spec AND sha match; return `{name: bool_written}`.
- Append-only logs: JSONL, one compact `json.dumps(..., sort_keys=True, allow_nan=False)` record per line; newline-repair on append; validate-before-append so corruption cannot hide; STRICT JSON — no NaN/Infinity tokens anywhere under `runs/`.
- Provenance collectors inside `finally` blocks must degrade, never raise: a tracking failure may never mask a stage's own outcome; log CRITICAL with the full record if an append fails.
- CLI: argparse subparsers, `run_<x>_command(...) -> int` never raises, exit codes 0 / 1 (verify) / 3 (stage); human summary on stdout, errors on stderr.
- Configs: `configs/<stage>.yaml`, all keys optional, defaults single-sourced in code, unknown keys warned + ignored behind `KNOWN_*_CONFIG_KEYS` frozensets.
- Tests: one file per story named `tests/test_<area>.py`, story-named docstring, module-level `_builder` helpers, `tmp_path` for all IO, `pytest.raises(..., match=...)`, `parametrize`, `caplog`/`monkeypatch`, CLI tests assert exit codes, every row of the spec's I/O & Edge-Case Matrix gets at least one pinning test, and every review patch lands with its own pinning test.
- Scope: exactly 7 `src/` subpackages (test_scaffold.py guards it); no gold-plating; no deps beyond `requirements.lock`.

## 2. The loop

### Step 1 — Pre-flight
- Read `_bmad-output/implementation-artifacts/sprint-status.yaml`: if story `<N.M>` is already `in-progress` or `done`, STOP — report and wait for orders (double-invocation or post-crash retry; do not branch again).
- `gh pr list --state open` — resolve or flag anything open before starting.
- `git checkout main && git fetch origin && git pull --ff-only`; confirm CI on main is green (`gh run list --limit 1`).
- Verify the story's GitHub issue exists (`gh issue list`); note its number for the PR body.

### Step 2 — Spec first
Write the spec through the `bmad-spec` skill, invoked per §0.5 (skill=`bmad-spec`, model=`zai-coding-plan/glm-5.3-flash`, timeout 30 minutes). Inputs are paths + ids only: `epics.md` + story id (the callee extracts the ACs verbatim itself), touched spine invariant ids (AD-1…AD-14), `epic-<N>-context.md` path, `deferred-work.md` path + ids absorbed into this story, the two most recent specs by path as format template, and `_bmad-output/implementation-artifacts/spec-pattern-digest.md` (condensed binding conventions; if missing, create it first from the latest spec, ≤ 60 lines). Slug: `story-<N>-<M>-<slug>`.

`bmad-spec` lands at `_bmad-output/specs/spec-story-<N>-<M>-<slug>/` (SPEC.md kernel + companions + `.memlog.md` carrying its self-validate verdicts) AND writes the auditable house contract `_bmad-output/implementation-artifacts/spec-<N>-<M>-<slug>.md` directly in house format — no separate in-session port: frontmatter (status: in-progress, baseline_commit = current main sha, context: spine + epic context + deferred-work + the bmad-spec folder path), then `<frozen-after-approval>` wrapped Intent / Boundaries & Constraints (Always / Ask First / Never) / I/O & Edge-Case Matrix, then Code Map, Tasks & Acceptance, Review Findings (pending), Spec Change Log, Design Notes, Verification (exact commands + expected), Suggested Review Order (left blank until after implementation). The frozen block is the contract you will be audited against — keep it honest, keep it small. Do not proceed to Step 3 while bmad-spec's self-validate leaves load-bearing `open_questions[]` unresolved — resolve or escalate them first.

### Step 3 — Branch
`git checkout -b story-<N>.<M>-<slug> origin/main`. Flip the story to `in-progress` in `_bmad-output/implementation-artifacts/sprint-status.yaml` in the story's first commit.

### Step 4 — Build + pinning tests (one pass)
Builder model: `glm-5.3-flash` at `model.effort=high`. Invoke `bmad-build` per §0.5 (skill=`bmad-build`, model=`zai-coding-plan/glm-5.3-flash`, timeout 60 minutes; in-session fallback = build directly) with inputs: the house spec path (the frozen block binds — not suggests), touched spine invariant ids, the story issue number, and the test mandate: write the FULL pinning suite for every row of the spec's I/O & Edge-Case Matrix in `tests/test_<area>.py`, following §1's test conventions. Do not invoke a second skill for routine test-writing.
Implement inside the boundaries. Prefer pure functions of `(config, input artifacts)`. Single-source everything the spine names (RMSE, config hash, registry, identity, splits) — never re-implement, import from the owner. Respect AD-11 import direction strictly forward; `tracking` imports only stdlib + numpy + pyyaml (spec-recorded exceptions only, and document them in the spec if you add one).

### Step 5 — Test gap audit
In-session (no fresh agent): audit the suite from Step 4 against the spec's I/O & Edge-Case Matrix row by row; write any missing pinning tests directly. Escalate to `bmad-testarch-automate` per §0.5 (model=`zai-coding-plan/glm-5.3-flash`, timeout 60 minutes) only if gaps exceed roughly a third of the matrix rows. Full suite `.venv/bin/pytest tests/ -q` must be green offline before anything is pushed. Also smoke the real CLI surface end-to-end on synthetic data in `/tmp/opencode` (never commit artifacts; `runs/`, `data/`, `*.parquet` are git-ignored — keep them out of commits).

### Step 6 — Commit, push, PR
- Commit message style: `Story <N>.<M>: <short title>` (match `git log --oneline -10`).
- `git push -u origin story-<N>.<M>-<slug>`.
- `gh pr create` with body sections: story title line + one-sentence capability summary + `Closes #<issue>`; **What lands** (bullet per module, concrete names); **Verification** (test counts, e2e smoke results); **Process notes** (spec path, absorbed deferred items).

### Step 7 — CI
`sleep 90 && gh pr checks <PR>`; poll until green, ceiling 20 polls (~30 min). If red: fix on the branch, push, re-check (each new push resets the ceiling). Never merge red. Ceiling hit with CI still unresolved — hung, not failed — stop and report per Section 4.

### Step 8 — Fresh-context adversarial review (the quality gate)

**Review depth.** Full gate = three layers (below). A light gate (layers 1 + 3 only) is allowed only when ALL hold: diff ≤ 200 changed lines confined to one new `src/` module + its test file; zero contact with AD-1…AD-14; no new config keys or default changes; no changes to `tracking`/registry/splits/RMSE code paths; full suite green on first push. Anything else — or any doubt — runs the full three. The Step 13 report must state which gate ran and why.

Run the review layers as fresh contexts (no shared context with your build session — they must not see your reasoning, only the diff and their listed context bundle). Run all layers CONCURRENTLY and join before Step 9; the external acceptance-auditor call may overlap with the in-session layers. If the runtime cannot parallelize, run in listed order and note it in the report.

1. **hunter** (flash) — adversarial sweep: "find at least ten issues, what's missing not just what's wrong", following `.agents/skills/bmad-code-review/review-prompts/edge-case-hunter.md`. Context: this workflow file's §1, the diff (`git diff origin/main...HEAD`), the touched `src/` modules.
2. **test-audit** (flash) — must follow the `bmad-testarch-test-review` skill: run the new tests, audit every new/changed test against best-practice criteria (assertion strength, leakage of implementation detail, edge-matrix coverage), and hunt claims the suite doesn't actually pin. Context: the new/changed test files, the spec's I/O & Edge-Case Matrix + Verification sections (line ranges).
3. **acceptance-auditor** — audits the diff against the spec's frozen block + AC list + touched spine invariants + deferred-work; must output which ACs are clean and which are violated, with file:line evidence. Context: the spine, the story's epics section, the spec, deferred-work — all by path. Prefer external per §0.5 (skill=`bmad-code-review`, model=`zai-coding-plan/glm-5.3-flash`, timeout 30 minutes); otherwise an in-session fresh subagent is acceptable (fresh-context discipline per §0.5).

Every layer keeps repo access for spot-checks, but its listed context is the mandatory read set — reviewers read their bundle by path, not the whole repo.

### Step 9 — Triage (yours, not the reviewers')
Normalize + deduplicate across layers; read the actual code at every cited location before rating (reviewers operate information-blind — their severity is input, not verdict). Route each finding: **patch** (unambiguous fix), **defer** (real, out of scope — record in deferred-work.md), **dismiss** (noise — with reasoning). Dismiss precedents live in `_bmad-output/implementation-artifacts/review-dismiss-precedents.md` — read it and apply (create it with the standing entries if missing: concurrent-file-locking outside the offline single-laptop envelope; append-only log refusing to grow past corruption — deliberate house pattern; spec-sanctioned deferrals to named later stories). Record the full triage (patched/deferred/dismissed counts) in the spec's Review Findings section as `[Review][Patch]` / `[Review][Defer]` checklist lines with file references.

### Step 10 — Patch
Default: patch in-session — you already hold the triage context; do not pay a fresh cold start for what is usually a handful of small fixes. Apply every patch finding; each behavior change gets a pinning test. Escalate to external `bmad-build` per §0.5 (skill=`bmad-build`, model=`zai-coding-plan/glm-5.3-flash`, timeout 60 minutes) only when findings exceed 8 or any touches spine-owned single-sourcing (RMSE, config hash, registry, identity, splits) — and then feed it ONLY: the findings (file:line), the touched file paths, the spec's Boundaries & Constraints + Spec Change Log sections (line ranges), and §1 by path.
Append any newly minted dismiss precedent to `review-dismiss-precedents.md` (rides this commit through PR review). Update the spec: Review Findings checklist, Spec Change Log entry (dated, "KEEP:" line stating what must not regress), and Suggested Review Order pointing at the patched code. Re-run the FULL suite. Commit: `Story <N>.<M>: address fresh-context code review (<k> patches, <one-line theme>)`. Push. CI must be green again.

### Step 11 — Merge
`gh pr merge <PR> --merge` (merge commit, matches repo history). Then `git checkout main && git pull --ff-only`.

### Step 12 — Post-merge bookkeeping (direct commit to main, per repo precedent)
- Append to the spec:
  `## GitHub Links` / `- Issue: #<n>` / `- PR: #<m>`
- Spec frontmatter `status: 'done'`; sprint-status.yaml story key `: done`.
- Refresh `_bmad-output/implementation-artifacts/spec-pattern-digest.md` (keep ≤ 60 lines) with any new recurring spec pattern this story minted.
- Parse-guard before pushing: `.venv/bin/python -c "import yaml; yaml.safe_load(open('_bmad-output/implementation-artifacts/sprint-status.yaml'))"` — and the same on the spec file if its frontmatter changed. Parse failure → stop and report per Section 4; never push malformed metadata to main.
- One commit: `Stamp story <N>.<M> spec with GitHub links (issue #<n>, PR #<m>); sprint status <N>.<M> done`; push to main.
- Verify: issue auto-closed, `gh pr list --state open` empty.

### Step 13 — Report back and STOP
Report to the owner in the numbered site-diary style: what merged, test counts before/after review, review stats (gate depth, layers run + model per layer, findings normalized → patched/deferred/dismissed, one-line key patches, any fallbacks used), links (PR, issue, spec), post-merge state, and a one-line readiness note for the next story. Then stop — the owner decides whether to continue.

## 3. Escalate only if

- A frozen spec block would need renegotiation (changing AD invariants, the AD-7 record fields, registered splits, PRISTINE_DAYS, default windows).
- A new dependency is required.
- A finding has two defensible fixes with different user-visible behavior.
- Anything requires pushing to main outside the bookkeeping precedent, or touching `evals/`/`skills/`/credentials.

Otherwise: decide, document the decision in the spec, keep moving.

## 4. Failure handling

- CI red twice on the same cause → stop and report instead of thrashing.
- CI unresolved (hung/stuck, not red) when the Step 7 poll ceiling is hit → stop and report; do not merge, do not extend polling.
- Review layer returns empty/fails → note it in the report (review may be incomplete), proceed with remaining layers.
- Any loop step unrecoverable → leave the branch/PR in a clean state, report exactly where you stopped and what unblocks it.
