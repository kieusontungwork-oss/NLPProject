"""The one BM25 tokenizer, used for both indexing and querying.

Story 1.3 · CAP-2 · AD-4 (single-sourced behavior). lowercase -> `[^\\W_]+` runs -> drop tokens
shorter than 2 characters -> drop the fixed Lucene English stopword set. No stemming.
"""

from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)

_TOKEN_PATTERN = re.compile(r"[^\W_]+")
MIN_TOKEN_LENGTH = 2
STOPWORDS: frozenset[str] = frozenset(
    "a an and are as at be but by for if in into is it no not of on or such that the their then "
    "there these they this to was will with".split()
)


def tokenize(text: str) -> list[str]:
    """Tokenize `text` for BM25 (see module docstring for the exact pipeline)."""
    return [
        token
        for token in _TOKEN_PATTERN.findall(text.lower())
        if len(token) >= MIN_TOKEN_LENGTH and token not in STOPWORDS
    ]
