---
name: sync-plan
description: Mirror BMAD epics and stories from _bmad-output into GitHub milestones, issues, and the board
code: SP
added: 2026-09-02
type: prompt
---

# Sync Plan → GitHub

The outcome is GitHub holding exactly what the plans say, no more and no less: one milestone per epic, one issue per story, every issue on the board with its `Epic` field set, and every story file stamped with its issue number. The owner reads the manifest once, says go once, and can then work entirely from GitHub.

Run `references/sync-status.md` first — remote truth lands on disk before you compute the delta, or you will re-create things that already exist.

If `{project-root}/_bmad-output/` is missing or holds no epics/stories, the plans aren't posted yet: tell the owner plainly and stop. Do not scaffold fake plans.

Read the plans and map them: epics (epic-level docs or epic sections) become milestones — title, goal as description, due date if the plan names one; stories become issues — body carries the story summary, the acceptance criteria as a checklist, the test plan, and the story file's project path so GitHub can point back at disk. Label issues `epic:{N}` and `story:{N.M}` so they stay queryable. If a story's file shape or epic/story split is ambiguous, ask the owner once — their answer is the convention for this project; don't re-ask next sync.

Idempotency anchors on the stamps: a story file with `- Issue: #N` under `## GitHub Links` is already posted — verify the issue still exists and move on; only the stampless delta gets created. Board placement runs through `scripts/board.py` (`add-item`, `set-field` — `--help` documents the surface); do not hand-write Projects GraphQL. When the plans name sprints, set the `Sprint` field to match; when they don't, leave it empty rather than inventing a schedule.

Show the full manifest before creating anything: what gets created, what already exists and is skipped, anything from the plans you couldn't map. The owner's go is per-manifest, not per-session. After executing, stamp the new story files and report the counts in one short paragraph — created, skipped, unmapped.
