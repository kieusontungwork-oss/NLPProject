"""Schemas for story 1.2 artifacts: Paper, Chunk, KBStats (pydantic, null-hostile).

Story 1.2 · CAP-1 · spine AD-5 (paper/chunk schemas exactly as pipeline-stages.md
defines; O-1/O-2/O-3 of the house spec). Citation resolvability (CAP-4) depends on
no Paper ever carrying null title/authors/year/categories — the models enforce it.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

HEX16_PATTERN = r"^[0-9a-f]{16}$"


class Paper(BaseModel):
    """One paper in data/kb/papers.jsonl (O-1). Empty string means absent; null is invalid."""

    arxiv_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    authors: list[str] = Field(min_length=1)
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
    duplicate_chunks: int = Field(ge=0)
    malformed_source_lines: int = Field(ge=0)
    malformed_metadata_lines: int = Field(ge=0)
    non_english_dropped: int = Field(ge=0)
    boilerplate_sections_stripped: int = Field(ge=0)
    nameless_sections_dropped: int = Field(ge=0)
    sections_merged_name_collision: int = Field(ge=0)
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


# --- Story 1.3 · CAP-2 · spine AD-3 (EvidencePack) and AD-5 (index manifests) ---


class LegScores(BaseModel):
    """Per-leg raw scores of a hit; null where the leg did not return the chunk (E-8, E-10)."""

    model_config = ConfigDict(frozen=True)

    bm25: float | None = None
    dense: float | None = None


class Hit(BaseModel):
    """One ranked evidence hit (AD-3); `rrf_score` is the deliberate v1 fused-score field."""

    model_config = ConfigDict(frozen=True)

    rank: int = Field(ge=1)
    chunk_id: str
    text: str
    header_prefix: str
    arxiv_id: str
    title: str
    section_name: str
    year: int
    source_link: str
    leg_scores: LegScores
    rerank_score: float | None = None
    rrf_score: float


class EffectiveQuery(BaseModel):
    """A query actually sent to the legs; in story 1.3 always `type == "raw"`."""

    model_config = ConfigDict(frozen=True)

    type: str
    text: str
    legs: list[str]


class Gate(BaseModel):
    """Answer-gate flags (semantics owned by later stories); defaults mean 'not evaluated'."""

    model_config = ConfigDict(frozen=True)

    score_gate_fired: bool = False
    generator_declared: bool | None = None


class EvidencePack(BaseModel):
    """The retrieval -> generation contract (AD-3). Additive-only changes bump `pack_version`."""

    model_config = ConfigDict(frozen=True)

    pack_version: int = 1
    query_id: str
    query: str
    effective_queries: list[EffectiveQuery]
    hits: list[Hit]
    stage_timings_ms: dict[str, float]
    gate: Gate = Field(default_factory=Gate)


class IndexManifest(BaseModel):
    """manifest.json of one index component (AD-5, class 3).

    `embedding_model` and `dim` are null for the sparse and docstore components.
    """

    created: str
    embedding_model: str | None
    dim: int | None
    chunk_store_hash: str
    config_row: str
    engine: str
    n_chunks: int = Field(ge=0)
    params: dict
