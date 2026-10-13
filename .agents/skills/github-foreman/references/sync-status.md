---
name: sync-status
description: Pull GitHub truth back into local BMAD files so plan and tracker never drift
code: SS
added: 2026-09-02
type: prompt
---

# Sync GitHub → Plan

The outcome is the local plans telling the same story GitHub does: story files carry current stamps and status, the board reflects reality, and any disagreement between disk and remote is named, not smoothed over. This is the return trip of sync-plan and the closing move after every merge — GitHub is the source of truth for where work stands.

Pull remote state: issues with their states and milestones, PRs with their merged/closed status and linked issues, board items with their field values (`scripts/board.py list`). Then reconcile disk: a merged PR means its story is Done — stamp the story file's `## GitHub Links` with the PR number and update any local status marker (story frontmatter, sprint-status file) that tracks it; an open PR puts the story In Review; a started branch with an open issue stays In Progress; a closed-but-unmerged PR is not Done — find out why before touching the story.

Stamps only, never story content: you update `## GitHub Links` and status fields, never acceptance criteria or descriptions — the plan says what to build, and editing it is planning, not syncing.

When the two sides disagree, surface it instead of silently picking: story file says done but the issue is open, issue closed but no PR exists, board item missing for a stamped story. List each conflict with both sides of the record and ask the owner which is true; your job is to make the disagreement visible, not to referee it blind.

Report in one short paragraph: stories updated, board flips, conflicts found. Zero conflicts and zero updates is a valid, quiet answer.
