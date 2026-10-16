"""The one HuggingFace model loader (spine Consistency Conventions: one HF loader).

Story 1.3 · CAP-2 · AD-1. Loading failures raise; there is no fallback model (no silent degradation).
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any

from paperpilot.core.errors import RetrievalStageError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def load_sentence_transformer(model_id: str) -> Any:
    """Load (and cache) a sentence-transformers model by id; raises RetrievalStageError('dense') on failure."""
    try:
        from sentence_transformers import SentenceTransformer

        logger.info("loading sentence-transformer model %s", model_id)
        return SentenceTransformer(model_id)
    except Exception as exc:
        raise RetrievalStageError(
            "dense", f"cannot load embedding model {model_id!r}: {type(exc).__name__}: {exc}"
        ) from exc
