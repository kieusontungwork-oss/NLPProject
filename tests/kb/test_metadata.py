"""Story 1.2 — kb.metadata: id repair (E-2/E-3), join drops (E-1), filter (E-17), widening (E-4)."""

from __future__ import annotations

import json

import pytest

from paperpilot.core.config import DEFAULTS
from paperpilot.kb.metadata import (
    bare_dataset_id,
    bare_metadata_id,
    build_metadata_index,
    category_in_scope,
    count_in_scope,
    iter_scope,
    join_paper,
    parse_year,
    resolve_filter_mode,
    split_categories,
)
from paperpilot.kb.stats import BuildCounters
from tests.conftest import make_meta_line, make_source_record
from tests.conftest import write_metadata_file as write_meta
from tests.conftest import write_source_zip


@pytest.fixture
def indexed(tmp_path):
    def _index(meta_lines: list[str]):
        meta_path = write_meta(tmp_path / "meta.jsonl", meta_lines)
        db_path = tmp_path / "index.sqlite3"
        counters = BuildCounters()
        build_metadata_index(meta_path, db_path, counters)
        return db_path, counters

    return _index


def test_bare_dataset_id_reslashes_pre2007_and_leaves_new_style_e2():
    assert bare_dataset_id("nlin0608019") == "nlin/0608019"
    assert bare_dataset_id("0704.0001") == "0704.0001"
    assert bare_dataset_id("math/0309136") == "math/0309136"
    assert bare_dataset_id("weird") == "weird"  # not matchable; join will miss -> drop


def test_bare_metadata_id_strips_version_suffix_e3():
    assert bare_metadata_id("0704.0001v2") == "0704.0001"
    assert bare_metadata_id("math/0309136v1") == "math/0309136"
    assert bare_metadata_id("0704.0001") == "0704.0001"


def test_split_categories_e17():
    assert split_categories("cs.AI stat.ML") == ["cs.AI", "stat.ML"]
    assert split_categories("") == []


def test_parse_year_from_created_and_none_on_garbage():
    assert parse_year("Mon, 2 Apr 2007 19:30:00 GMT") == 2007
    assert parse_year(None) is None
    assert parse_year("not a date") is None


def test_category_in_scope_modes_e17():
    # cs.* scope: any category starting with "cs."; stat.ML is NOT cs.* scope
    # (it feeds the AI/ML/NLP composition stat only).
    assert category_in_scope(["cs.CL"], DEFAULTS, "cs")
    assert not category_in_scope(["stat.ML", "math.AG"], DEFAULTS, "cs")
    assert not category_in_scope(["math.AG"], DEFAULTS, "cs")
    assert category_in_scope(["math.AG"], DEFAULTS, "all")


def test_resolve_filter_mode_widens_below_threshold_e4():
    assert resolve_filter_mode(12_000, DEFAULTS) == ("cs", False)
    assert resolve_filter_mode(11_999, DEFAULTS) == ("all", True)


def test_build_metadata_index_counts_malformed_lines(indexed):
    _, counters = indexed([make_meta_line("0704.0001")])
    # conftest writes one broken line before the valid ones.
    assert counters.malformed_metadata_lines == 1


def test_join_paper_full_path(indexed):
    db_path, _ = indexed([make_meta_line("0704.0001", categories="cs.CL")])
    paper = join_paper(make_source_record("0704.0001"), db_path)
    assert paper is not None
    assert paper.title == "Attention Is Not All You Need Yet"
    assert paper.authors == ["A. One", "B. Two"]
    assert paper.year == 2007
    assert paper.categories == ["cs.CL"]
    assert paper.abstract == "We study attention for machine translation."
    assert list(paper.sections) == ["Introduction", "Methods"]
    assert paper.source_link == "https://arxiv.org/abs/0704.0001"


def test_join_paper_drops_when_metadata_row_missing_e1(indexed):
    db_path, _ = indexed([make_meta_line("0704.0001")])
    assert join_paper(make_source_record("0704.9999"), db_path) is None


def test_join_paper_drops_when_year_unparseable(indexed):
    db_path, _ = indexed([make_meta_line("0704.0001", created="garbage")])
    assert join_paper(make_source_record("0704.0001"), db_path) is None


def test_join_paper_body_fallback_when_no_sections_e7(indexed):
    db_path, _ = indexed([make_meta_line("0704.0001")])
    record = make_source_record("0704.0001", sections=[], section_names=[], article_text=["Only body text."])
    paper = join_paper(record, db_path)
    assert paper is not None
    assert list(paper.sections) == ["body"]
    assert paper.sections["body"] == "Only body text."


def test_join_paper_tolerates_extra_sections_or_names_mismatch(indexed):
    db_path, _ = indexed([make_meta_line("0704.0001")])
    record = make_source_record("0704.0001", sections=[["A"], ["B"], ["C"]], section_names=["One", "Two"])
    paper = join_paper(record, db_path)
    assert paper is not None
    assert sorted(paper.sections) == ["One", "Two"]  # zip strict=False keeps the pair count aligned


def test_count_and_iter_scope_end_to_end_e1_e17(tmp_path):
    records = [
        make_source_record("0704.0001"),          # cs.CL -> in scope
        make_source_record("0704.0002"),          # stat only -> in scope (cs.* includes stat.ML? no!)
        make_source_record("math/0309136"),       # math -> out of cs scope
        make_source_record("0704.9999"),          # no metadata -> dropped + counted
    ]
    records[1] = make_source_record(
        "0704.0002", sections=[["S."]], section_names=["Intro"]
    )
    zip_path = write_source_zip(tmp_path / "src.zip", records)
    meta_path = write_meta(
        tmp_path / "meta.jsonl",
        [
            make_meta_line("0704.0001", categories="cs.CL"),
            make_meta_line("0704.0002", categories="cs.AI"),
            make_meta_line("math/0309136", categories="math.AG"),
        ],
    )
    db_path = tmp_path / "idx.sqlite3"
    counters = BuildCounters()
    build_metadata_index(meta_path, db_path, BuildCounters())

    cs_yield = count_in_scope(iter(records), db_path, DEFAULTS, BuildCounters())
    assert cs_yield == 2

    counters = BuildCounters()
    papers = list(iter_scope(iter(records), db_path, DEFAULTS, counters, "cs"))
    assert [p.arxiv_id for p in papers] == ["0704.0001", "0704.0002"]
    assert counters.dropped_no_metadata == 1


def test_metadata_lines_are_valid_json_after_index_write(indexed):
    db_path, _ = indexed([make_meta_line("0704.0001")])
    import sqlite3

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute("SELECT arxiv_id, title FROM metadata").fetchall()
    finally:
        conn.close()
    assert rows == [("0704.0001", "Attention Is Not All You Need Yet")]
    assert json.loads(json.dumps(rows[0]))  # sanity: json round-trip of stored values
