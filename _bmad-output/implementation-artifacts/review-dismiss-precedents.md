# Review dismiss precedents

Standing reasons for dismissing review findings. Cite an entry when dismissing.

- **Concurrent file locking.** Outside the offline single-laptop envelope; one build runs at a time.
- **Spec-sanctioned deferrals to named later stories.** If the spec or a story names a later story for the item, it is deferred there, not patched here.
- **Per-section linear scan for duplicate chunk ids (H14).** Fine at section scale (a handful of windows per section).
- **One sqlite connection per lookup (H19).** Acceptable: build time is not a requirement.
- **English heuristic strength.** The owner kept the current ASCII-share check (2026-10-15).
- **argparse usage errors exit 2.** argparse's own convention, documented in each CLI `main`; the 0/1/3 contract covers `run_<x>_command` (story 1.3).
- **Unreachable tie-break terms mandated by the spec.** E.g. the RRF min-leg-rank term (integer ranks make exact float ties at different min ranks unreachable); harmless, kept as specified (story 1.3).
