"""Build-time defaults, single-sourced (house convention: defaults live in code, I-3).

Story 1.2 · CAP-1. Every number the KB pipeline needs is defined exactly once here;
modules import from this module, never restate values. CLI overrides target these
values explicitly; env vars are never a toggle path (AD-4 spirit).
"""

from __future__ import annotations

from dataclasses import dataclass

S3_SOURCE_URL = "https://s3.amazonaws.com/datasets.huggingface.co/scientific_papers/1.1.1/arxiv-dataset.zip"
GCS_METADATA_URL = "https://storage.googleapis.com/arxiv-dataset/metadata-v5/arxiv-metadata-oai.json"
SOURCE_MEMBER = "arxiv-dataset/train.txt"


@dataclass(frozen=True)
class KBDefaults:
    """Frozen defaults for the KB build (I-3 of the house spec)."""

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
