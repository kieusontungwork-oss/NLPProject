"""Story 1.2 — kb.cli end-to-end on the synthetic mini-corpus: artifacts, exit codes, determinism (E-14/E-16)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from paperpilot.core.config import DEFAULTS, KBDefaults
from paperpilot.core.errors import PaperPilotError
from paperpilot.kb.cli import EXIT_OK, EXIT_STAGE, EXIT_VERIFY, build, run_build_command


@pytest.fixture
def corpus(tmp_path: Path):
    from tests.conftest import make_meta_line, make_source_record, write_metadata_file, write_source_zip

    records = [
        make_source_record("0704.0001"),
        make_source_record(
            "0704.0002",
            sections=[["Only one section here."]],
            section_names=["Introduction"],
        ),
        make_source_record("math/0309136", sections=[["Body."]], section_names=["Body"]),
    ]
    zip_path = write_source_zip(tmp_path / "src" / "arxiv-dataset.zip", records)
    meta_path = write_metadata_file(
        tmp_path / "src" / "arxiv-metadata-oai.json",
        [
            make_meta_line("0704.0001", categories="cs.CL"),
            make_meta_line("0704.0002", categories="cs.AI"),
            make_meta_line("math/0309136", categories="math.AG"),
        ],
    )
    return {"zip": zip_path, "meta": meta_path, "out": tmp_path / "out", "records": records}


def test_build_emits_valid_artifacts(corpus):
    # widen_threshold=1 keeps the cs.* scope on this smoke corpus (2 cs papers).
    stats = build(
        data_dir=corpus["out"],
        limit=None,
        defaults=KBDefaults(widen_threshold=1),
        source_zip=corpus["zip"],
        metadata_file=corpus["meta"],
    )
    kb_dir = corpus["out"] / "data" / "kb"
    assert (kb_dir / "papers.jsonl").exists()
    assert (kb_dir / "chunks.jsonl").exists()
    assert (kb_dir / "kb_stats.json").exists()
    assert stats.papers == 2  # math paper filtered out by cs.* scope

    papers = [json.loads(line) for line in (kb_dir / "papers.jsonl").read_text().splitlines()]
    chunks = [json.loads(line) for line in (kb_dir / "chunks.jsonl").read_text().splitlines()]
    assert {p["arxiv_id"] for p in papers} == {"0704.0001", "0704.0002"}
    assert all(p["title"] and p["year"] and p["categories"] for p in papers)
    assert all(c["chunk_id"] and c["text"].startswith(c["header_prefix"]) for c in chunks)
    assert len({c["chunk_id"] for c in chunks}) == len(chunks)

    on_disk = json.loads((kb_dir / "kb_stats.json").read_text())
    assert on_disk["papers"] == 2
    assert on_disk["provenance"]["filter_mode"] == "cs"
    assert on_disk["provenance"]["filter_widened"] is False
    assert on_disk["provenance"]["dropped_no_metadata"] == 0
    assert on_disk["provenance"]["malformed_source_lines"] == 2  # conftest bad lines
    assert on_disk["provenance"]["malformed_metadata_lines"] == 1


def test_build_is_deterministic_across_runs_e16(corpus):
    tiny = KBDefaults(widen_threshold=1)
    first = build(data_dir=corpus["out"], limit=None, defaults=tiny, source_zip=corpus["zip"], metadata_file=corpus["meta"])
    kb_dir = corpus["out"] / "data" / "kb"
    ids_first = [json.loads(l)["chunk_id"] for l in (kb_dir / "chunks.jsonl").read_text().splitlines()]
    papers_first = (kb_dir / "papers.jsonl").read_text()

    second = build(data_dir=corpus["out"], limit=None, defaults=tiny, source_zip=corpus["zip"], metadata_file=corpus["meta"])
    ids_second = [json.loads(l)["chunk_id"] for l in (kb_dir / "chunks.jsonl").read_text().splitlines()]
    assert first.chunks == second.chunks
    assert ids_first == ids_second
    assert papers_first == (kb_dir / "papers.jsonl").read_text()


def test_limit_slice_is_prefix_deterministic_e16(corpus):
    stats = build(data_dir=corpus["out"], limit=1, source_zip=corpus["zip"], metadata_file=corpus["meta"])
    assert stats.papers == 1


def test_widening_fires_below_threshold_e4(corpus):
    tiny = KBDefaults(widen_threshold=5)
    stats = build(
        data_dir=corpus["out"],
        limit=None,
        defaults=tiny,
        source_zip=corpus["zip"],
        metadata_file=corpus["meta"],
    )
    assert stats.provenance.filter_widened is True
    assert stats.provenance.filter_mode == "all"
    assert stats.papers == 3  # math paper now in scope


def test_missing_zip_is_stage_error_exit_3(tmp_path):
    code = run_build_command(
        [
            "build",
            "--data-dir",
            str(tmp_path),
            "--source-zip",
            str(tmp_path / "nope.zip"),
            "--metadata-file",
            str(tmp_path / "nope.jsonl"),
        ]
    )
    assert code == EXIT_STAGE


def test_verify_failure_is_exit_1(corpus, monkeypatch):
    # Force two identical chunks past the in-paper guard to hit the global verify.
    from paperpilot.kb import chunk as chunk_mod

    original = chunk_mod._chunks_for_section

    def sneaky(paper, section_name, section_rank, body, defaults, counters):
        chunks = original(paper, section_name, section_rank, body, defaults, counters)
        if section_name == "Methods" and chunks:
            return [chunks[0], chunks[0].model_copy()]
        return chunks

    monkeypatch.setattr(chunk_mod, "_chunks_for_section", sneaky)
    with pytest.raises(PaperPilotError, match="uniqueness"):
        build(data_dir=corpus["out"], limit=None, source_zip=corpus["zip"], metadata_file=corpus["meta"])

    # And the CLI maps that failure class to exit 1.
    from paperpilot.kb import cli as cli_mod

    def boom(**kwargs):
        raise PaperPilotError("chunk_id uniqueness violated: forced")

    monkeypatch.setattr(cli_mod, "build", boom)
    assert run_build_command(["build", "--data-dir", str(corpus["out"])]) == EXIT_VERIFY
    assert DEFAULTS.token_ceiling == 512  # untouched by tests


def test_cli_happy_path_exit_0_with_summary(corpus, capsys):
    code = run_build_command(
        [
            "build",
            "--data-dir",
            str(corpus["out"]),
            "--source-zip",
            str(corpus["zip"]),
            "--metadata-file",
            str(corpus["meta"]),
        ]
    )
    assert code == EXIT_OK
    out = capsys.readouterr().out
    # The production defaults widen on any tiny corpus (cs yield 2 < 12000): 3 papers, filter=all.
    assert "kb build ok" in out and "papers=3" in out and "filter=all" in out


def test_non_english_paper_dropped_and_counted_e6(tmp_path):
    from tests.conftest import make_meta_line, make_source_record, write_metadata_file, write_source_zip

    records = [
        make_source_record("0704.0001"),
        make_source_record(
            "0704.0003",
            sections=[["Это текст на русском языке про машинное обучение."]],
            section_names=["Введение"],
            abstract="Русский реферат про обучение.",
        ),
    ]
    zip_path = write_source_zip(tmp_path / "src.zip", records)
    meta_path = write_metadata_file(
        tmp_path / "meta.jsonl",
        [
            make_meta_line("0704.0001", categories="cs.CL"),
            make_meta_line("0704.0003", categories="cs.CL"),
        ],
    )
    stats = build(
        data_dir=tmp_path / "out",
        limit=None,
        defaults=KBDefaults(widen_threshold=1),
        source_zip=zip_path,
        metadata_file=meta_path,
    )
    assert stats.papers == 1
    assert stats.provenance.non_english_dropped == 1


def test_cli_requires_subcommand():
    with pytest.raises(SystemExit) as exc:
        run_build_command([])
    assert exc.value.code == 2
