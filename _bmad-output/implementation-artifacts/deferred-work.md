# Deferred work

Items found in review of Story 1.2 and consciously deferred. Each: source finding, reason, target story.

- **Dataset markup cleaning (@xmath, @xcite, `<S>`, filler tokens).** Source: edge-case review. Reason: owner decision to accept the markup as-is for now; cleaning is a text-quality change that should be evaluated against retrieval. Target: story 1.5.
- **All-or-nothing writes of the three KB files (H8).** Source: edge-case review. Reason: each file is written atomically but a crash between them can leave a mixed set; acceptable for a single-laptop wholesale rebuild. Target: a later KB hardening pass.
- **`--limit` smoke runs always widen to filter=all (H10).** Source: edge-case review. Reason: a small slice is always below the 12k threshold; smoke runs are not meant to model the scope. Target: later, if smoke runs need cs.* scope.
- **Provenance URLs do not reflect --source-zip/--metadata-file overrides (H13).** Source: edge-case review. Reason: overrides are for offline/test use; URLs record the canonical sources. Target: later KB hardening pass.
- **Downloaded file reused without a size/checksum check (H15).** Source: edge-case review. Reason: the truncation check protects new downloads; a pre-existing corrupt file is a manual-cleanup case. Target: later KB hardening pass.
- **`errors="replace"` on source bytes is not counted (H16).** Source: edge-case review. Reason: invalid bytes in the source are rare and not yet measured. Target: later KB hardening pass.
- **Dedup hash ignores section structure (H18).** Source: edge-case review. Reason: hash is over concatenated abstract + body per spec E-5; changing it changes dedup semantics. Target: later, if evaluation shows a need.
- **LaTeX accents in titles (H20).** Source: edge-case review. Reason: cosmetic; titles are used for headers and citations only. Target: story 1.5 (text cleaning).
- **Extra `verify()` invariants (H21).** Source: edge-case review. Reason: current invariants (unique ids, no orphans, no null metadata) cover the spec. Target: later KB hardening pass.
- **Streaming emission for the widening path (A5/H17).** Source: acceptance + edge-case review. Reason: the cs.* KB peaks at 2.6GB in RAM; only the widening path (all 203k papers) needs streaming, via `CorpusAggregate`. Target: when widening must be supported.
- **I-3 CLI override flags ambiguity.** Source: acceptance review. Reason: spec says "override keys via CLI flags", only file/limit flags exist; config overrides not needed yet. Target: story that first needs a config override.
- **Zip length mismatch between section_names and sections not counted (H11b).** Source: edge-case review. Reason: `zip(strict=False)` silently pairs the shorter length; rare in the dataset. Target: later KB hardening pass.
- **Remaining test-quality items T7–T13.** Source: test audit. Reason: lower-value assertions/matrix gaps not covered by the new patch tests. Target: next test pass on the kb module.
