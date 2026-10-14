"""Story 1.2 — kb.dedup: content-hash duplicate removal, keep-first in source order (E-5)."""

from __future__ import annotations

from paperpilot.kb.dedup import content_hash, dedup_papers
from paperpilot.kb.stats import BuildCounters
from tests.conftest import make_paper


def test_content_hash_is_deterministic_and_content_based():
    a = make_paper()
    b = make_paper()
    assert content_hash(a) == content_hash(b)
    assert content_hash(a) != content_hash(make_paper(abstract="Different."))


def test_dedup_keeps_first_occurrence_in_order_e5():
    counters = BuildCounters()
    # content_hash ignores arxiv_id: identical content keeps only the first record.
    papers = [make_paper(), make_paper(arxiv_id="0704.0002"), make_paper(arxiv_id="0704.0003")]
    kept = list(dedup_papers(iter(papers), counters))
    assert [p.arxiv_id for p in kept] == ["0704.0001"]
    assert counters.duplicates == 2


def test_dedup_distinct_content_survives():
    counters = BuildCounters()
    papers = [make_paper(), make_paper(abstract="Distinct abstract.", arxiv_id="0704.0002")]
    kept = list(dedup_papers(iter(papers), counters))
    assert [p.arxiv_id for p in kept] == ["0704.0001", "0704.0002"]
    assert counters.duplicates == 0


def test_dedup_on_empty_stream_is_empty():
    counters = BuildCounters()
    assert list(dedup_papers(iter([]), counters)) == []
    assert counters.duplicates == 0
