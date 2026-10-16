"""Build-time defaults, single-sourced (house convention: defaults live in code, I-3).

Story 1.2 · CAP-1 (KB defaults); Story 1.3 · CAP-2 · AD-4 (retrieval config rows, BM25
params, embedding batch size, default paths). Every number the pipelines need is defined
exactly once here; modules import from this module, never restate values. CLI overrides target these
values explicitly; env vars are never a toggle path (AD-4 spirit).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from paperpilot.core.errors import ConfigError

logger = logging.getLogger(__name__)

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


# --- Story 1.3: retrieval ---------------------------------------------------------------

BM25_METHOD = "lucene"
BM25_K1 = 1.5
BM25_B = 0.75
EMBED_BATCH_SIZE = 128
DEFAULT_EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
DEFAULT_KB_DIR = Path("data/kb")
DEFAULT_INDEX_DIR = Path("indexes")
DEFAULT_ABLATIONS_PATH = Path("configs/ablations.yaml")


class RetrievalConfig(BaseModel):
    """One row of configs/ablations.yaml (AD-4): unknown keys rejected; defaults live only here."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    description: str = ""
    use_sparse: bool = True
    use_dense: bool = True
    rrf_k: int = Field(default=60, gt=0)
    candidate_depth: int = Field(default=300, ge=1)
    sparse_engine: Literal["bm25s"] = "bm25s"
    embedding_model: str = DEFAULT_EMBEDDING_MODEL

    @model_validator(mode="after")
    def _at_least_one_leg(self) -> RetrievalConfig:
        if not (self.use_sparse or self.use_dense):
            raise ValueError("at least one of use_sparse / use_dense must be true")
        return self


def load_config_rows(path: str | Path = DEFAULT_ABLATIONS_PATH) -> list[RetrievalConfig]:
    """Load and validate `{rows: [...]}`; every failure raises ConfigError naming the row id or key."""
    path = Path(path)
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"config file not found: {path}") from exc
    except (OSError, yaml.YAMLError) as exc:
        raise ConfigError(f"cannot read config file {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"{path}: expected a mapping with a 'rows' list, found {type(raw).__name__}")
    unknown = sorted(str(key) for key in raw if key != "rows")
    if unknown:
        raise ConfigError(f"{path}: unknown top-level key(s) {unknown}; only 'rows' is allowed")
    rows_raw = raw.get("rows")
    if not isinstance(rows_raw, list) or not rows_raw:
        raise ConfigError(f"{path}: 'rows' must be a non-empty list")

    rows: list[RetrievalConfig] = []
    seen: set[str] = set()
    for index, row_raw in enumerate(rows_raw):
        label = row_raw.get("id", f"#{index}") if isinstance(row_raw, dict) else f"#{index}"
        if not isinstance(row_raw, dict):
            raise ConfigError(f"{path}: row {label} must be a mapping, found {type(row_raw).__name__}")
        try:
            row = RetrievalConfig(**row_raw)
        except (ValidationError, TypeError) as exc:
            raise ConfigError(f"{path}: invalid row {label!r}: {exc}") from exc
        if row.id in seen:
            raise ConfigError(f"{path}: duplicate row id {row.id!r}")
        seen.add(row.id)
        rows.append(row)
    return rows


def get_row(row_id: str, path: str | Path = DEFAULT_ABLATIONS_PATH) -> RetrievalConfig:
    """Return the row with `row_id`; an unknown id raises ConfigError listing the available ids."""
    rows = load_config_rows(path)
    for row in rows:
        if row.id == row_id:
            return row
    raise ConfigError(f"unknown config row {row_id!r}; available rows: {[r.id for r in rows]}")
