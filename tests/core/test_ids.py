"""Story 1.2 — core.ids: the AD-2 chunk_id recipe and normalization are the repo's only hashers."""

from __future__ import annotations

import hashlib

import pytest

from paperpilot.core.ids import chunk_id, normalize


def test_normalize_collapses_whitespace_and_strips():
    assert normalize("  hello \t\n world  ") == "hello world"


def test_normalize_applies_nfc():
    # "e" + combining acute (decomposed) composes to a single codepoint under NFC.
    decomposed = "e\u0301tude"
    assert normalize(decomposed) == "étude"
    assert normalize(decomposed) == normalize("étude")


@pytest.mark.parametrize(
    ("arxiv_id", "section", "text"),
    [
        ("0704.0001", "abstract", "Hello world"),
        ("nlin/0608019", "Introduction", "Différent text"),
        ("0704.0001", "abstract", "Hello  \n world"),  # same after normalize as row 1
    ],
)
def test_chunk_id_is_16_hex_sha1_prefix_over_unit_separated_payload(arxiv_id, section, text):
    expected = hashlib.sha1(
        f"{arxiv_id}\x1f{section}\x1f{normalize(text)}".encode("utf-8")
    ).hexdigest()[:16]
    assert chunk_id(arxiv_id, section, text) == expected
    assert len(chunk_id(arxiv_id, section, text)) == 16
    assert all(c in "0123456789abcdef" for c in chunk_id(arxiv_id, section, text))


def test_chunk_id_normalizes_before_hashing_so_equivalent_texts_collide():
    assert chunk_id("0704.0001", "abstract", "Hello  world") == chunk_id(
        "0704.0001", "abstract", "Hello world"
    )


def test_chunk_id_differs_across_papers_and_sections():
    base = chunk_id("0704.0001", "abstract", "same text")
    assert base != chunk_id("0704.0002", "abstract", "same text")
    assert base != chunk_id("0704.0001", "methods", "same text")
