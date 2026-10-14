"""Schemas for story 1.2 artifacts: Paper, Chunk, KBStats (pydantic, null-hostile).

Story 1.2 · CAP-1 · spine AD-5 (paper/chunk schemas exactly as pipeline-stages.md
defines; O-1/O-2/O-3 of the house spec). Citation resolvability (CAP-4) depends on
no Paper ever carrying null title/authors/year/categories — the models enforce it.
"""

from __future__ import annotations

from pydantic import BaseModel, Field

HEX16_PATTERN = r"^[0-9a-f]{16}$"


class Paper(BaseModel):
    """One paper in data/kb/papers.jsonl (O-1). Empty string means absent; null is invalid."""

    arxiv_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str]
    year: int
    abstract: str = ""
    sections: dict[str, str]
    source_link: str = Field(min_length=1)
    license: str = ""
    categories: list[str] = Field(min_length=1)


class Chunk(BaseModel):
    """One chunk in data/kb/chunks.jsonl (O-2); minted via paperpilot.core.ids.chunk_id (AD-2)."""

    chunk_id: str = Field(pattern=HEX16_PATTERN)
    arxiv_id: str = Field(min_length=1)
    section_name: str = Field(min_length=1)
    section_rank: int = Field(ge=0)
    text: str = Field(min_length=1)
    n_tokens: int = Field(gt=0)
    header_prefix: str = Field(min_length=1)


class CategoryComposition(BaseModel):
    """Corpus composition (O-3); AI/ML/NLP is the primary subcollection, reported only."""

    cs_papers: int = Field(ge=0)
    aiml_papers: int = Field(ge=0)
    total: int = Field(ge=0)


class Provenance(BaseModel):
    """Build provenance (O-3): every drop/dup/malformed path is counted here, never hidden."""

    source_url: str
    metadata_url: str
    filter_mode: str
    filter_widened: bool = False
    dropped_no_metadata: int = Field(ge=0)
    duplicates: int = Field(ge=0)
    malformed_source_lines: int = Field(ge=0)
    malformed_metadata_lines: int = Field(ge=0)
    non_english_dropped: int = Field(ge=0)
    generated_at: str


class KBStats(BaseModel):
    """kb_stats.json (O-3): the four assignment Q1.3 figures plus structure and provenance."""

    papers: int = Field(ge=0)
    chunks: int = Field(ge=0)
    words: int = Field(ge=0)
    types: int = Field(ge=0)
    chunk_size_histogram: dict[str, int]
    year_min: int | None = None
    year_max: int | None = None
    year_histogram: dict[str, int]
    category_composition: CategoryComposition
    provenance: Provenance
