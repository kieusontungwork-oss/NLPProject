# PaperPilot — pipeline targets (spine Structural Seed: kb / index / eval / ui)
# Story 1.2 delivers `kb`; Story 1.3 delivers `index`; eval/ui land with their own stories.

.PHONY: kb index

kb:
	uv sync
	uv run python -m paperpilot.kb.cli build

index:
	uv sync
	uv run python -m paperpilot.retrieval.cli index --row E3
