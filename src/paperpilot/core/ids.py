"""Identity: the single chunk_id minter (AD-2) and text normalization.

Story 1.2 · CAP-1 · spine AD-2: `chunk_id` is minted ONLY here — no other module
hashes. Determinism across macOS/Linux/Colab requires NFC + whitespace collapse.
"""

from __future__ import annotations

import hashlib
import unicodedata

_UNIT_SEP = "\x1f"


def normalize(text: str) -> str:
    """NFC-normalize and collapse all whitespace runs to single spaces, then strip.

    normalize is the only sanctioned text canonicalization; stored chunk text is
    the normalized text so the id and the stored bytes always agree.
    """
    return unicodedata.normalize("NFC", " ".join(text.split()))


def chunk_id(arxiv_id: str, section_name: str, text: str) -> str:
    """Mint a chunk id: leading 16 hex of SHA-1 over arxiv_id US section_name US normalize(text).

    US = "\\x1f" (unit separator). The input text is normalized before hashing, so
    callers may pass raw section text; the id they get back matches the text they
    must store (also normalized).
    """
    payload = f"{arxiv_id}{_UNIT_SEP}{section_name}{_UNIT_SEP}{normalize(text)}"
    return hashlib.sha1(payload.encode("utf-8")).hexdigest()[:16]
