# AGENT.md

Instructions for AI coding agents (Claude Code, opencode, etc.) working in this repository.

## Test files are never committed

- Do **not** commit test files. This includes anything under `tests/`, and any file named
  `test_*.py`, `*_test.py`, or `conftest.py`, wherever it lives.
- Tests may be written and run locally (`uv run pytest`), but they stay out of git and out of
  pull requests. `tests/` is listed in `.gitignore` for this reason.
- Before committing, check the staged files (`git diff --cached --name-only`) and unstage any
  test file that slipped in. Never use `git add -f` to force a test file in.
