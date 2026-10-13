---
name: start-story
description: Open a story for work — branch cut from dev, board flipped, work order handed to the coding agent
code: ST
added: 2026-09-02
type: prompt
---

# Start a Story

The outcome is a story in motion with zero ambiguity for whoever codes it: the issue exists, branch `feature/story-{N.M}-{slug}` is cut from `dev`, the board says `In Progress`, and the owner holds a work order their coding agent can execute without asking a single follow-up. Trigger is the owner naming a story — "start story 1.2" — or any phrasing that clearly means it.

Verify the story's issue exists first (the stamped `- Issue: #N` anchor, or search if unstamped). No issue means the plan was never synced — offer to sync just that story (a one-issue delta of `references/sync-plan.md`) rather than refusing the whole job.

Check the story isn't already live: board status `In Progress` or `In Review`, or the branch existing on the remote. Double-starting a story is the one mistake this capability exists to prevent — if it's already running, say where it stands and stop.

Cut the branch from `dev` (`git fetch origin dev` first; branch from `origin/dev`, never a stale local). Create and push it, flip the board item's `Status` to `In Progress` via `scripts/board.py set-field`, and comment on the issue with the branch name so GitHub shows the handover.

The work order goes to the owner in plain text, assembled for the coding agent: branch name, issue number and link, story file path, the acceptance criteria checklist, and the test plan from the story file. Nothing else — the agent that builds decides how; the foreman decides what "done" will be measured against.

Close with the handover line: story started, where the branch is, and that you'll shepherd the PR when the work is up.
