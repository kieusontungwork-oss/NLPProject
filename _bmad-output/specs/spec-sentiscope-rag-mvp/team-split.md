# Team Split — SentiScope RAG MVP

> Companion to SPEC.md. Maps the 3 assignment components (KB 20 / Retrieval 40 / Downstream 40) to subgroups so individual grades can be reported (assignment §2, recommended option). Everyone shares labeling + report duties.

## Subgroups (5–6 people → 2/2/2 or 2/2/1+float)

| Sub | Owns (SPEC CAPs) | Headline deliverables | Est. load |
|---|---|---|---|
| **A — Library** | CAP-1, CAP-2 (sparse leg), CAP-8 tooling | corpus pipeline, `kb_stats.json`, BM25 index, chunking experiments, Label Studio setup | steady Wks 1–4 |
| **B — Search** | CAP-2 (dense+fusion), CAP-3, CAP-4, CAP-7a qrels (w/ A), CAP-9, Q2 speed | RRF hybrid, reranker, HyDE/multi-query, agentic loop, qrels judging, Gradio chat, speed report | heaviest, Wks 1–7 |
| **C — Answering** | CAP-5, CAP-6, CAP-7 (task+RAG metrics) | subjectivity/polarity/stance/aspect stack, grounded generation, RAGAS, ablation matrix | steady Wks 2–7 |
| **All** | CAP-8 sprint, CAP-10 | ≥200 labels each (pre-filled verification), own report/slides sections, demo rehearsal | 1 focused week Wks 3–4 |

## Report-question ownership (assignment Q1–Q5)

| Question | Primary | Support |
|---|---|---|
| Q1 corpus (sources, cleaning, stats) | A | all (stats verify) |
| Q2 UI + 5 queries + speed | B | — |
| Q3 retrieval innovations + rank metrics | B | A (index-side toggles) |
| Q4 eval set, task metrics, RAG metrics, performance | C | A (IAA logistics), B (latency data) |
| Q5 downstream innovations + ablations | C | B (loop/rerank deltas) |

## Cross-subgroup contracts (prevent integration hell)

1. `retrieve(query, k) -> [chunk_id, score, leg]` and `generate(evidence_pack, query) -> answer` are frozen interfaces — subgroups develop against stubs from Week 1.
2. All toggles via YAML (stack.md config contract) — no hand-edited runs, or ablations are unreproducible.
3. Every artifact lands in `reports/` with a generator script — the report must be rebuildable, not copy-pasted.
4. Labeling guidelines freeze after the 100-pilot; changes after freeze require re-annotating affected rows.
5. Weekly 30-min sync: demo something running, update memlog, unblock interfaces — no status-only meetings.
6. Hard dates everyone plans around: content freeze **Fri 30 Oct**, submission **Thu 5 Nov** (deadline 7 Nov), presentations 9–15 Nov (demo polish happens after submission).
