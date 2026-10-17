"""`python -m paperpilot.evaluation.labeling <subcommand>` entry point.

Story 1.6 · CAP-6 · AD-1: a thin alias of `paperpilot.evaluation.labeling.cli` (which stays runnable too).
"""

from __future__ import annotations

import sys

from paperpilot.evaluation.labeling.cli import main

if __name__ == "__main__":
    sys.exit(main())
