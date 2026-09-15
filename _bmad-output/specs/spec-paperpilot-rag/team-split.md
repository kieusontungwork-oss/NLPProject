# PaperPilot — Team Split & Deliverables Map (companion to SPEC.md)

Assignment grading: KB construction 20 / Retrieval 40 / Downstream 40. The brief allows up to three subgroups; per-member credit follows the stated split (or shared grade if unspecified — recommended option).

## Subgroups (roster TBD — open question)

| Subgroup | Owns | Points |
| --- | --- | --- |
| A — Knowledge Base | CAP-1 (acquisition, cleaning, chunking, stats), CAP-6 question writing + qrels labeling coordination | 20 |
| B — Retrieval | CAP-2 (BM25/dense/RRF), CAP-3 innovations + ablation harness, retrieval inspector in UI | 40 |
| C — Downstream | CAP-4 generator + citations, RAGAS eval (CAP-5 answer-level), CAP-7 UI shell, CAP-8 report assembly | 40 |

CAP-6 labeling is a whole-team sprint (everyone annotates); A coordinates it.

## Question → capability map (report skeleton)

| Assignment question | Answered by | Evidence artifact |
| --- | --- | --- |
| Q1 corpus gathering/cleaning/chunking/stats + task + sample queries | CAP-1 | `kb_stats.json`, rebuild script, sample queries |
| Q2 UI + 5 queries + speed | CAP-7 | UI, recorded per-query latency |
| Q3 retrieval innovations + rank-aware eval | CAP-2/3 | ablation matrix, failed-before/works-now queries |
| Q4 approach motivation + preprocessing + 1,000-record IAA≥80% eval + task & RAG metrics + performance | CAP-4/5/6 | `qa_pairs.jsonl`, qrels, agreement report, `metrics.json` |
| Q5 downstream innovations + ablation | CAP-4 + E7 | answer-side ablation table |

## Submission checklist (owner: C, checked by all)

- [ ] Single PDF named `<group_number>.pdf` — names + matric numbers page 1, Q1–Q5 answers, pictures included (brief explicitly asks)
- [ ] Data zip link (Drive/Dropbox): KB, 5 queries + retrieved results, eval datasets, Q3/Q5 ablation data
- [ ] Code zip link: source + README (clone → install → rebuild → eval → UI), libs included/documented
- [ ] Week-13 slides (prepped post-submission, zero grading risk)

## Milestones (freeze 2026-10-30, submit 2026-11-05, deadline 2026-11-07 23:59 SGT)

| When | Milestone |
| --- | --- |
| Week 0 (by ~09-19) | Data spike: verify arXiv candidates bytes-on-disk; pick source; sparse-engine decision data |
| Week 1–2 (by ~10-03) | CAP-1 done: KB built + stats; CAP-2 baselines running |
| Week 3 (by ~10-10) | CAP-2 solid; generator choice made; qrels pooling starts |
| Week 4 (by ~10-17) | CAP-3 innovations flagged + first ablation matrix; labeling sprint running |
| Week 5 (by ~10-24) | CAP-4/5 complete: answers + RAGAS + full matrix; UI working |
| Week 6 (by 10-30) | Freeze: numbers reproduced via `make eval`; report drafted |
| 11-05 | Submit (2-day buffer) |
