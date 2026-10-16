"""Stage timer: writes float milliseconds into a timings dict.

Story 1.3 · CAP-2 · spine AD-3 (`stage_timings_ms`); timings are float ms via `time.perf_counter`.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

logger = logging.getLogger(__name__)


@contextmanager
def stage_timer(timings: dict[str, float], key: str) -> Iterator[None]:
    """Record the elapsed milliseconds of the `with` body under `key` (also when it raises)."""
    start = time.perf_counter()
    try:
        yield
    finally:
        timings[key] = (time.perf_counter() - start) * 1000.0
