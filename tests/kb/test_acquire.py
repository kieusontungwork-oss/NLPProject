"""Story 1.2 — kb.acquire: zip stream parse (I-1), malformed counting, limit (E-16), atomic download (E-14/E-15)."""

from __future__ import annotations

import io
from pathlib import Path

import pytest

from paperpilot.core.errors import KBStageError
from paperpilot.kb.acquire import download_file, iter_source_records
from paperpilot.kb.stats import BuildCounters
from tests.conftest import make_source_record, write_source_zip


def test_iter_source_records_streams_valid_records_and_counts_malformed(tmp_path):
    records = [make_source_record(f"0704.000{i}") for i in range(3)]
    zip_path = write_source_zip(tmp_path / "src.zip", records)
    counters = BuildCounters()
    got = list(iter_source_records(zip_path, counters))
    assert [r["article_id"] for r in got] == ["0704.0000", "0704.0001", "0704.0002"]
    assert counters.malformed_source_lines == 2  # conftest interleaves two bad lines


def test_limit_stops_after_n_valid_records_e16(tmp_path):
    records = [make_source_record(f"0704.000{i}") for i in range(5)]
    zip_path = write_source_zip(tmp_path / "src.zip", records)
    counters = BuildCounters()
    got = list(iter_source_records(zip_path, counters, limit=2))
    assert len(got) == 2
    assert got[0]["article_id"] == "0704.0000"


def test_missing_member_raises_stage_error(tmp_path):
    import zipfile

    zip_path = tmp_path / "empty.zip"
    with zipfile.ZipFile(zip_path, "w") as archive:
        archive.writestr("other.txt", "x")
    counters = BuildCounters()
    with pytest.raises(KBStageError, match="cannot read"):
        list(iter_source_records(zip_path, counters))


def test_corrupt_zip_raises_stage_error(tmp_path):
    zip_path = tmp_path / "bad.zip"
    zip_path.write_bytes(b"not a zip at all")
    with pytest.raises(KBStageError, match="cannot read"):
        list(iter_source_records(zip_path, BuildCounters()))


class FailingTransport:
    """Writes some bytes then dies — the partial file must never be promoted."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def __call__(self, url: str) -> io.BufferedReader:
        self.calls.append(url)
        raise KBStageError("acquire", f"cannot open {url}: simulated")


def test_download_failure_leaves_no_partial_file_e15(tmp_path):
    dest = tmp_path / "data" / "raw" / "arxiv-dataset.zip"
    transport = FailingTransport()
    with pytest.raises(KBStageError):
        download_file(dest, "https://example.invalid/x.zip", transport=transport)
    assert not dest.exists()
    assert not list(dest.parent.glob("*.partial"))


def test_download_success_promotes_atomically_e14(tmp_path):
    dest = tmp_path / "data" / "raw" / "arxiv-dataset.zip"
    payload = b"fake-zip-bytes"

    def transport(url: str) -> io.BufferedReader:
        return io.BytesIO(payload)  # type: ignore[return-value]

    out = download_file(dest, "https://example.invalid/x.zip", transport=transport)
    assert out == dest
    assert dest.read_bytes() == payload

    # Second call reuses the file: no transport contact (E-14 idempotent re-run).
    transport2 = FailingTransport()
    download_file(dest, "https://example.invalid/x.zip", transport=transport2)
    assert transport2.calls == []
