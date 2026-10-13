---
name: standup
description: Read-only site report — what's framed, what's in inspection, what's blocked, where the sprint stands
code: SU
added: 2026-09-02
type: prompt
---

# Standup

The outcome is the owner knowing the state of the whole site in under a minute, from one read-only report: no mutations, no syncing, no fixing — just the truth as GitHub holds it right now.

Gather it all before writing a line: milestones with open-vs-closed issue counts per epic, board items grouped by `Status` with their `Epic` and `Sprint` fields (`scripts/board.py list`), open PRs with their check states, and anything labeled or flagged as blocked.

The report, in this order:

1. **In inspection** — PRs open, CI green or red, whose desk each sits on
2. **In progress** — stories on branches, board status for each
3. **Blocked / red** — failed checks, conflicts from the last sync, issues going nowhere; each with what would clear it
4. **The epic picture** — each milestone's progress in closed/total terms, one line each
5. **Next move** — the single most useful thing to do next, stated as a recommendation

Site-diary plain throughout: numbers and states, no adjectives, no padding. A quiet site gets a short report — "Nothing red. Two stories in inspection, PR #14 green and waiting on you." — and that brevity is the feature.
