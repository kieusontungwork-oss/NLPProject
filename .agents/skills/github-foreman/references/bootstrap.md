---
name: bootstrap
description: One-time delivery infrastructure setup for a repo — dev branch, Projects board, CI workflow, templates
code: BT
added: 2026-09-02
type: prompt
---

# Bootstrap the Site

The outcome is a repo where the delivery conventions from SKILL.md physically exist on GitHub: `dev` branch cut from `main`; a Projects v2 board (default name "Delivery Board" — ask the owner only if they want it different) with fields `Status` (single-select: Todo, In Progress, In Review, Done), `Epic` (single-select, empty), and `Sprint` (single-select, empty — GitHub's iteration fields can't be fully managed via API, so sprints are an owner-created select); a CI test workflow at `.github/workflows/test.yml`; a PR template at `.github/PULL_REQUEST_TEMPLATE.md`; and an issue template at `.github/ISSUE_TEMPLATE/story.yml`. The owner, who was not in the room for any of this skill's design, must be able to open GitHub afterward and see every convention without being told.

Check what already exists before proposing anything (`gh repo view`, `gh project list`, `git ls-remote --heads origin`) — bootstrap is idempotent; the plan shows only the delta.

The workflow file ships with this skill at `assets/ci-test-workflow.yml`; the templates at `assets/pr-template.md` and `assets/issue-template.yml`. Copy them verbatim into `.github/` — the CI workflow is honest about an empty test suite: it runs pytest when `tests/` exists and skips with a notice when it doesn't, so "CI green" stays meaningful as tests land.

Repo files (`.github/*`) land through a PR, never a direct push to `main`: branch `chore/foreman-bootstrap` from `main`, commit, push, open the PR, and hand it to the owner to merge. Branches and boards are not merges — create `dev` and the board directly.

The gate is absolute: show the complete manifest first and get an explicit go. After executing, report one short paragraph: created, skipped-as-existing, and the PR number awaiting the owner's merge.
