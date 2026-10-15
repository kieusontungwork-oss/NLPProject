"""Build-time defaults, single-sourced (house convention: defaults live in code, I-3).

Story 1.2 · CAP-1. Every number the KB pipeline needs is defined exactly once here;
modules import from this module, never restate values. CLI overrides target these
values explicitly; env vars are never a toggle path (AD-4 spirit).
"""

from __future__ import annotations

from dataclasses import dataclass

S3_SOURCE_URL = "https://s3.amazonaws.com/datasets.huggingface.co/scientific_papers/1.1.1/arxiv-dataset.zip"
GCS_METADATA_URL = "https://storage.googleapis.com/arxiv-dataset/metadata-v5/arxiv-metadata-oai.json"
# Fixed order: determinism (E-16).
SOURCE_MEMBERS: tuple[str, ...] = ("arxiv-dataset/train.txt", "arxiv-dataset/val.txt", "arxiv-dataset/test.txt")


@dataclass(frozen=True)
class KBDefaults:
    """Frozen defaults for the KB build (I-3 of the house spec); validated at construction."""

    token_floor: int = 256
    token_ceiling: int = 512
    overlap_fraction: float = 0.15
    fold_floor_tokens: int = 128
    widen_threshold: int = 12_000
    ascii_letter_share: float = 0.8
    english_sample_chars: int = 2000
    aiml_categories: frozenset[str] = frozenset(
        {"cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.IR", "stat.ML"}
    )
    category_prefix: str = "cs."

    def __post_init__(self) -> None:
        if 0 >= self.token_floor or self.token_floor >= self.token_ceiling:
            raise ValueError(
                f"token band invalid: floor={self.token_floor} ceiling={self.token_ceiling} (need 0 < floor < ceiling)"
            )
        if not 0 < self.overlap_fraction < 1:
            raise ValueError(f"overlap_fraction={self.overlap_fraction} must be in (0, 1)")
        if self.step_words <= 0:
            raise ValueError(
                f"step_words={self.step_words} (overlap {self.overlap_fraction}) would loop forever"
            )
        if 0 >= self.fold_floor_tokens or self.fold_floor_tokens >= self.token_floor:
            raise ValueError(
                f"fold_floor_tokens={self.fold_floor_tokens} must be in (0, token_floor={self.token_floor})"
            )
        if self.widen_threshold <= 0:
            raise ValueError(f"widen_threshold={self.widen_threshold} must be positive")
        if not 0 < self.ascii_letter_share <= 1:
            raise ValueError(f"ascii_letter_share={self.ascii_letter_share} must be in (0, 1]")

    @property
    def max_window_words(self) -> int:
        """Words per full window: the estimator is words x 4/3, so ceiling*3/4 words ~= ceiling tokens."""
        return int(self.token_ceiling * 3 / 4)

    @property
    def step_words(self) -> int:
        """Window step: ~15% overlap on the word window (E-10)."""
        return int(self.max_window_words * (1 - self.overlap_fraction))

    @property
    def fold_floor_words(self) -> int:
        """Windows below this many words fold into the previous window (E-10)."""
        return int(self.fold_floor_tokens * 3 / 4)


def estimate_tokens(words: int) -> int:
    """Documented token estimator (Design Notes): words x 4/3, rounded — no model tokenizer at KB time."""
    return round(words * 4 / 3)


DEFAULTS = KBDefaults()
