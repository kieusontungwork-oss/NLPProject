"""Typed exception hierarchy (house convention: stage base RuntimeError with actionable messages).

Story 1.2 · CAP-1 · spine AD-1 (core layer owns shared contracts).
"""

from __future__ import annotations


class PaperPilotError(RuntimeError):
    """Base for every PaperPilot failure; messages name offending values."""


class KBStageError(PaperPilotError):
    """A knowledge-base stage failed (acquire/join/clean/dedup/chunk/stats) — exit code 3 path."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"[kb/{stage}] {message}")
        self.stage = stage
