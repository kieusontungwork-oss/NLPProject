# PaperPilot — pipeline targets (spine Structural Seed: kb / index / eval / ui)
# Story 1.2 delivers `kb`; index/eval/ui land with their own stories.

.PHONY: kb

kb:
	uv sync
	uv run python -m paperpilot.kb.cli build
