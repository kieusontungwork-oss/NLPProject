"""Shared fixtures and builders: synthetic mini-corpus + schema objects (offline; no network ever).

Story 1.2 · house §1 test conventions. The builders mirror the real dataset
shapes recorded in the Week-0 spike: source records carry article_id,
article_text[], abstract_text[], sections[][], section_names[]; metadata lines
carry versioned ids, space-separated categories, versions[].created.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from paperpilot.core.schemas import Chunk, Paper

CREATED = "Mon, 2 Apr 2007 19:30:00 GMT"


def make_paper(**overrides) -> Paper:
    fields = dict(
        arxiv_id="0704.0001",
        title="A Title",
        authors=["A. One"],
        year=2007,
        abstract="Abstract.",
        sections={"Introduction": "Text."},
        source_link="https://arxiv.org/abs/0704.0001",
        license="",
        categories=["cs.CL"],
    )
    fields.update(overrides)
    return Paper(**fields)


def make_chunk(**overrides) -> Chunk:
    fields = dict(
        chunk_id="0123456789abcdef",
        arxiv_id="0704.0001",
        section_name="abstract",
        section_rank=0,
        text="A Title — abstract\n\nAbstract.",
        n_tokens=10,
        header_prefix="A Title — abstract",
    )
    fields.update(overrides)
    return Chunk(**fields)


def make_source_record(
    article_id: str = "0704.0001",
    sections: list[list[str]] | None = None,
    section_names: list[str] | None = None,
    abstract: str = "We study attention for machine translation.",
    article_text: list[str] | None = None,
) -> dict:
    return {
        "article_id": article_id,
        "article_text": article_text or ["Body paragraph one.", "Body paragraph two."],
        "abstract_text": [abstract] if abstract else [],
        "sections": sections if sections is not None else [["Intro sentence one.", "Intro two."], ["Methods text."]],
        "section_names": section_names if section_names is not None else ["Introduction", "Methods"],
    }


def make_meta_line(
    arxiv_id: str = "0704.0001",
    title: str = "Attention Is Not All You Need Yet",
    authors: str = "A. One and B. Two",
    categories: str = "cs.CL stat.ML",
    created: str | None = CREATED,
    abstract: str = "Snapshot abstract.",
    license: str | None = None,
) -> str:
    record: dict = {
        "id": f"{arxiv_id}v2",
        "title": title,
        "authors": authors,
        "categories": categories,
        "abstract": abstract,
        "versions": ([{"version": "v1", "created": created}] if created else []),
    }
    if license is not None:
        record["license"] = license
    return json.dumps(record)


def write_source_zip(path: Path, records: list[dict], member: str = "arxiv-dataset/train.txt") -> Path:
    """Real zip with a JSONL member, plus deliberately malformed lines interleaved."""
    path.parent.mkdir(parents=True, exist_ok=True)
    lines: list[str] = ["{not json"]
    lines.extend(json.dumps(record) for record in records)
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(member, "\n".join(lines) + "\n{also bad\n")
    return path


def write_metadata_file(path: Path, lines: list[str]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(["{broken", *lines]) + "\n", encoding="utf-8")
    return path
