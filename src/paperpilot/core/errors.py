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


class ConfigError(PaperPilotError):
    """A config file or row failed validation (AD-4); the message names the row id or key."""


class RetrievalStageError(PaperPilotError):
    """A retrieval stage failed (index/dense/sparse/docstore/fusion) — exit code 3 path."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(f"[retrieval/{stage}] {message}")
        self.stage = stage


class RetrievalInputError(RetrievalStageError):
    """The caller's query or k is invalid (E-3, E-4)."""

    def __init__(self, message: str) -> None:
        super().__init__("input", message)


class IndexMissingError(RetrievalStageError):
    """An index component is absent; the message names the path and says to run `make index`."""

    def __init__(self, path: object, message: str = "") -> None:
        detail = f" ({message})" if message else ""
        super().__init__("index", f"index component missing at {path}{detail}; run `make index`")
        self.path = path


class IndexMismatchError(RetrievalStageError):
    """An index component disagrees with the current KB or config; names expected vs found."""

    def __init__(self, what: str, expected: object, found: object) -> None:
        super().__init__(
            "index",
            f"index {what} mismatch: expected {expected!r}, found {found!r}; run `make index`",
        )
        self.what = what
