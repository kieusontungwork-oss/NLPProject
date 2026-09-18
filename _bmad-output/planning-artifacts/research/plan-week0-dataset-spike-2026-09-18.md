# Week-0 Dataset Spike Plan — arXiv KB Source Selection (v2)

> **For agentic workers:** Execute phase-by-phase with checkboxes for tracking. This is an analysis spike (Story 1 of `spec-paperpilot-rag/stories.yaml`), not a code feature — TDD does not apply; bytes-on-disk evidence does.

**Goal:** Pick the PaperPilot KB source (S2ORC vs HF `scientific_papers` vs Kaggle arXiv) with bytes-on-disk evidence. Sparse-engine decision deferred.

**Timebox:** ~half day (dated 2026-09-18; team-split deadline ~2026-09-19)

**Deliverable:** `_bmad-output/planning-artifacts/research/data-spike-2026-09-18.md` (findings note) + updates to SPEC.md / `.memlog.md` / `stack.md`

**Spec traceability:** Story 1 in `stories.yaml`, CAP-1 in SPEC.md, open questions at SPEC.md ("Which arXiv dataset candidate wins…" and "Sparse engine…").

**Scope change vs Story 1:** "sparse-engine decision data" is reduced to the chunks-per-paper estimate only (Phase 3, arithmetic — no BM25 timing test per user decision 2026-09-18). The rank_bm25-vs-Pyserini-vs-Elasticsearch call moves to Story 3 prep. Record this deviation in the spike writeup.

---

## Decision criteria

| # | Criterion | Why it matters |
|---|-----------|----------------|
| 1 | **Verified download** (real bytes on disk) | SPEC hard rule — no commitment without a real download test |
| 2 | **Full text present** (not abstract-only) | Brief requires ≥10k full-text papers; abstract-only = disqualifying |
| 3 | **Section structure** (abstract/method/results/conclusion separable) | Feeds the section-aware weighting novelty hook (CAP-3) |
| 4 | **License** permissive enough for redistribution in the data zip | CAP-8 ships a data zip |
| 5 | **Chunks-per-paper estimate** → total at 10k papers | Feeds CAP-1 sizing + later sparse-engine choice (expect 300k–600k total) |
| 6 | Practicality: size, parse effort, English-only | $0 budget, laptop-first (MacBook CPU) |

## Phases

- [ ] **Phase 0 — Setup (~30 min)**
  - Create scratch dir `research/spike/` (project root, gitignored or deleted after)
  - Check free disk: need ~50 GB headroom for slices + working copies
  - Write one small download script per candidate, each grabbing a **test slice of ~100–200 papers only** (never the full corpus)
- [ ] **Phase 1 — Download verification per candidate (~2 h, parallelizable)**
  - **A: S2ORC cs.\*** — pull a cs.* slice from Semantic Scholar's public mirrors; record bytes, docs, JSON structure
  - **B: HF `scientific_papers`** — load `arxiv` split via `datasets` streaming; verify the full-text field (not just abstract) with bytes-on-disk evidence
  - **C: Kaggle arXiv dumps** — check dataset cards/docs first for full-text presence (many dumps are abstract/metadata-only → cheap elimination before any download)
  - Record per candidate: bytes on disk, docs in slice, download time, auth/rate-limit friction
- [ ] **Phase 2 — Sample analysis, 15–20 papers per surviving candidate (~1.5 h)**
  - % of papers with parseable section headers; can abstract/method/results/conclusion be split out?
  - Words/paper distribution (validates the 50M+ words assumption)
  - Boilerplate pollution level (references, appendices, hashes)
  - License string, recorded verbatim
  - Parse effort estimate (pre-parsed text vs JSON vs LaTeX/PDF)
- [ ] **Phase 3 — Estimate only (~15 min, no compute)**
  - Arithmetic: chunks/paper at 256–512 tokens with ~15% overlap → total chunks at 10k papers
  - Recorded as **input for a later sparse-engine decision** — SPEC sparse-engine open question stays open until Story 3 prep
- [ ] **Phase 4 — Decision + writeup (~45 min)**
  - Fill the score matrix below
  - Decision rule: **download-failure = out → rank survivors on full-text + section structure + license → ties broken by smaller/simpler**
  - Write `data-spike-2026-09-18.md` with filled table, per-candidate evidence, decision + fallback order, and the Story-1 scope deviation note
  - Update SPEC.md (resolve the dataset open question only), `.memlog.md`, `stack.md` acquisition row

## Report skeleton (fill during Phase 4)

| Criterion | S2ORC cs.* | HF scientific_papers | Kaggle |
|---|---|---|---|
| Bytes on disk (slice) | | | |
| Full text? | | | |
| Section structure (0–3) | | | |
| License | | | |
| Est. chunks @10k papers | | | |
| Parse effort | | | |
| **Verdict** | | | |

## Risks

- Kaggle likely fails the full-text check → test via docs first; may save time
- S2ORC slices run tens of GB → test slice only, never the full corpus
- Download mirrors may throttle → fall back to alternate mirror or `datasets` streaming
