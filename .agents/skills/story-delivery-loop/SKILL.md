---
name: story-delivery-loop
description: >
  Reusable per-story instruction prompt that runs a coding agent through the
  ENTIRE delivery loop autonomously: spec → branch → build + pinning tests →
  test gap audit → commit/push/PR → CI polling → fresh-context adversarial
  review → triage → patch → merge → post-merge bookkeeping → report.
  Invoke with: do story <N.M> using docs/agent-workflows/story-delivery-loop.md
---

# Story Delivery Loop

One instruction file that turns a coding agent into an autonomous story
delivery pipeline. The agent takes a single story from backlog to merged and
STOPS — no next story without an explicit owner order.

## What's in this folder

- `story-delivery-loop.md` — the full loop instructions (the thing you drop
  into a project and invoke). Copied verbatim from its origin project
  (WIDSKaggle), so it ships with that project's ground-truth paths and house
  conventions baked in.

## Install

Copy the workflow file into the target project's docs folder:

```bash
cp -r agent-skills-hub/skills/story-delivery-loop <project>/.agents/skills/
mkdir -p <project>/docs/agent-workflows
cp <project>/.agents/skills/story-delivery-loop/story-delivery-loop.md \
   <project>/docs/agent-workflows/story-delivery-loop.md
```

## Invoke

```
do story <N.M> using docs/agent-workflows/story-delivery-loop.md
```

## Prerequisites

- A BMAD-planned repo: `_bmad-output/` with epics/stories, sprint-status.yaml,
  and per-story GitHub issues (or another backlog source wired into Step 0/1).
- The BMAD skills the loop shells out to: `bmad-spec`, `bmad-build`,
  `bmad-code-review`, `bmad-testarch-automate` (see the sibling skill folders).
- `gh` CLI authenticated; `git` with an `origin` remote; CI workflow on the PR
  checks the loop polls (Step 7).
- The external runner pattern (§0.5) uses `opencode run -m <model> --command
  <skill> "<headless prompt>"`; any headless runner works — adjust the command
  and fallback rules once.

## Adapt when porting (the WIDSKaggle-specific bits)

`story-delivery-loop.md` is project-shaped. Before first use in a new repo,
edit:

1. **§0 Ground truth** — the seven read-first paths (architecture spine,
   epics.md, epic context, deferred-work, recent specs). Point them at your
   repo's equivalents; drop what doesn't exist.
2. **§1 House conventions** — language/toolchain versions, module style,
   persistence formats, CLI conventions, test conventions, dependency policy.
   Replace wholesale with your own; reviewers enforce them (Step 8 layers read
   this section by path).
3. **Model tier (§0 preamble + §0.5)** — the loop pins one model tier
   (`glm-5.3-flash` at `effort=high`) for every external step. Keep or swap.
4. **Story branch/slug and commit message style** (Steps 3, 6, 10, 12) —
   `story-<N>.<M>-<slug>` and `Story <N.M>: <title>` are the shipped defaults.
5. **Merge and bookkeeping precedent** (Steps 11–12) — merge strategy and the
   direct-to-main post-merge stamp commit are per-repo policy. Align with your
   AGENTS.md.

Everything else — the loop order, escalation rules (§3), failure handling
(§4), token discipline, and the fresh-context review gate (Step 8) — is
project-neutral and should be kept as-is.

## How the pieces fit with the other hub skills

- `bmad-*` skills do the planning and the per-step heavy lifting (spec,
  build, review); the loop is the *conductor* that sequences them and owns
  git/CI/PR.
- `github-foreman` is the complementary human-in-the-loop alternative: it
  shepherds branch → PR → CI → merge on explicit owner orders and never
  writes code. Use the loop when you want one autonomous run per story; use
  Foreman when you want step-by-step sign-off.

## Design rules worth keeping

- **Spec first, frozen block binding** — implementation is audited against a
  frozen Intent/Boundaries/Edge-Case-Matrix contract, never the other way.
- **Fresh-context review** — review layers never share context with the build
  session; they see the diff and a listed context bundle only.
- **Token discipline** — pass paths, not prose; every step's input list is
  exhaustive.
- **Ceilings everywhere** — CI poll ceiling, review-loop cap, escalate-only-if
  list, failure handling. The loop stops and reports instead of thrashing.
