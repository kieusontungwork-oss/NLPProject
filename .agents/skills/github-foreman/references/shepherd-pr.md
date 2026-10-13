---
name: shepherd-pr
description: Open the story PR, watch CI to green, hand off for merge, then close the loop after merge
code: SH
added: 2026-09-02
type: prompt
---

# Shepherd a PR

The outcome is a story's work safely through inspection to merged: a PR open against `dev` with the story's bar written on it, CI green or failures named, the merge made by the owner, and the story's status settled on disk and board afterward. Trigger is the owner or coding agent saying work on the story branch is done.

Before opening: confirm the branch is pushed and its commits describe the story's work (`git log origin/dev..origin/{branch}`); if nothing is pushed, say so and wait — you carry work orders, not code. Open the PR with `gh pr create --base dev` and a body shaped like `assets/pr-template.md`: one-paragraph summary from the story, the acceptance criteria as a checklist, the test plan, `Closes #{issue}` so the merge auto-closes it, and the story file's project path.

Then run inspection. `gh pr checks` until terminal — poll, don't sit spinning. Red checks get reported plainly: which check, the failing step, the log link. Green gets reported as ready: "PR #14 is green and on your desk."

Merging is the owner's act: they click, or they explicitly order you to merge this PR — that order must name the PR, and only then do you run `gh pr merge --merge --delete-branch`. After any merge, run `references/sync-status.md` so disk and board catch up, and the story is Done.

Then look up the site: if the merge closed the last open story in the epic's milestone, offer the release PR — `dev` → `main`, titled for the epic, release notes drafted from the merged PRs. The owner confirms and merges it; that click is what ships an epic.

Report the whole run in one short paragraph: PR number, check outcome, merge state, what changed on disk, and any release offer.
