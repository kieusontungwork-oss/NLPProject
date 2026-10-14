# PaperPilot: Evaluation Plan (companion to SPEC.md)

Two labeled artifacts, both ours (the brief allows public datasets for background, but the held-out eval set must be self-labeled). Format is **JSONL, schema documented in the report**: `eval.xls` tabular format applies to classification tasks only; research QA is not classification.

## 1. Retrieval qrels (feeds CAP-3/5, answers Q3)

- **Query set:** ≥250 natural research questions over the corpus, written by the team across query types (terminology-mismatch queries, exact-term queries, survey-style queries, comparison queries), balanced across subfields **present in the KB** (record `year_min/year_max` + composition from `kb_stats.json` first — the corpus ends 2017, so questions target pre-2018 topics: seq2seq, attention, early QA, topic models, classic CV/ML; 2020-era RAG/LLM questions are out of scope by construction).
- **Pooling (two rounds, anti-pooling-bias):** round 1 — for each query, top-20 from BM25, dense, and RRF legs → pooled candidates, judged. **Round 2 (scheduled, Week 5):** after the innovation configs exist, add the top-10 of every E-ladder config (E4, E5a, E5b, E6, E6Δ) to the pool and judge the new candidates — otherwise innovations are penalized for finding passages the baselines missed (unjudged scores as non-relevant). Every ablation row reports `judged@10`; a row below ~90% judged is not comparable and must be re-pooled before entering the report.
- **Plain-English walkthrough (what "pooled qrels" means).** A qrel is one human judgment about one passage, for one question: "for Q17, passage A is relevant." Humans cannot judge all ~380k chunks, so we judge only what our systems return: run every system on the question, merge their top results into one **pool**, and judge every passage in the pool. Worked example on Q17 ("How does attention help seq2seq models?"): round 1 — BM25 returns {A, B, X}, dense returns {A, C, D}, so the pool is {A, B, C, D, X}; humans judge A, B, C, D as relevant and X as not relevant. Later, the re-ranker (E4) returns passage E in first position — genuinely the best passage for Q17, but E has no judgment (the baselines ranked it ~40th, so it never entered the round-1 pool). Scored against round-1 qrels, E counts as "not relevant" and the re-ranker loses points for its best result — the report would wrongly conclude that re-ranking hurts. Round 2 prevents this: after the innovation configs exist, their top results are added to the pool, humans judge the newcomers (E = relevant), and every config is then scored against the complete qrels. The `judged@10` diagnostic above is the tripwire that catches any config scored against incomplete judgments before it reaches the report.
- **Scale:** round 1 pooling over ≥250 queries × ~60 candidates ≈ 15,000 judgments (subsample to fit effort); round 2 adds ~1,500–2,500 new candidates; this plus QA-pair labels carries the total past the 1,000-record requirement with margin.
- **Output:** `data/eval/qrels.jsonl`: `{query_id, text, type, subfield}` and `{query_id, chunk_id, relevance}`.

## 2. QA eval set (feeds CAP-4/5, answers Q4)

- ≥250 questions with gold short answers + evidence spans (extractable where possible so EM/F1 is computable); plus a fixed **100-question "unanswerable" slice**, split into a **40-question dev half** (used to calibrate the gate threshold τ and nothing else) and a **60-question held-out half** (used only for the reported fire rate) — the split is committed with the eval set and the halves never mix. At n=25 a pass/fail gate is statistically meaningless (one question = 4 points; 20/25 ≈ 80% has a 95% CI of ~61–92%); at n=60 the held-out rate is decidable. Unanswerable questions are the cheapest rows to label (no gold answer or span needed). RAGAS and EM/F1 are computed on the answerable subset only; the held-out half feeds the sufficiency-gate rates.
- **Plain-English walkthrough (why the unanswerable slice is split 40/60).** The slice tests the system's most important safety rule: when the library cannot answer a question, say so instead of guessing. All 100 questions are written so that no passage in the corpus can answer them (post-2017 topics such as RLHF; the corpus ends in 2017). The split exists for measurement integrity: a setting must never be tuned and reported on the same questions, or the number is flattered. The **40 dev questions are the tuning set**, used for exactly one thing — choosing the gate threshold τ. Example: run the 40 through retrieval; best-passage scores on unanswerable questions cluster at 0.30–0.45 while answerable questions score 0.55+; setting τ = 0.50 correctly refuses 38 of 40 unanswerable questions while wrongly refusing only ~5% of answerable ones. The **60 held-out questions are the final exam**, never touched during tuning: the system's reported refusal rate is measured only on them. Reported example: "How does RLHF align large language models?" → best score 0.38 < τ 0.50 → gate fires, canned "Not enough evidence in the library", no LLM call; if this happens on 54 of 60, the reported refusal rate is 90% (target ≥80%), while the false-fire rate on answerable questions must stay ≤10%. Without this slice, the system could stitch 2017-era papers into a confident, wrong answer and nothing in the evaluation would catch it.
- **Plain-English walkthrough (what a "QA pair with a gold answer" is).** A QA pair is a question stored together with its answer. The word **gold** means the officially accepted correct answer, written in advance by a human on the team — not generated by the system. It is the standard the system's answer is judged against, like an answer key for an exam. Example (answerable): question "How does attention help seq2seq models?" → gold answer "Attention lets the decoder look back at all encoder states instead of compressing the whole source sentence into one fixed vector, removing the information bottleneck." Example (unanswerable): question "How does RLHF align large language models?" → no gold answer, `answerable: false` — RLHF is a post-2018 topic and the corpus ends in 2017, so the library genuinely cannot answer it; the correct system behavior is to refuse, not guess. At scoring time, EM/F1 and RAGAS compare the system's generated answer against the gold answer; `gold_chunk_ids` records which passages a correct answer should rest on; the refusal rate is measured on the `answerable: false` rows. Division of labor: qrels grade the librarian (retrieval); QA pairs grade the writer (generation).
- **Output:** `data/eval/qa_pairs.jsonl`: `{query_id, question, gold_answer, gold_chunk_ids[], answerable}`.

## 3. Annotation protocol (IAA ≥80% requirement)

1. Write labeling guidelines doc (relevance scale definitions + QA answer-length rules + unanswerable-question construction rules + 10 worked examples).
2. Pilot: 100 records double-labeled → compute raw agreement + Cohen's κ; refine guidelines if agreement <80% before the full sprint.
3. Full pass: divide records among 2-3 annotators; 15-20% of all records double-labeled; disagreements resolved by majority/adjudication.
4. Report: raw agreement + κ per artifact; guidelines + report committed to the repo (CAP-6 success).

## 4. Metric matrix (all from `make eval` → `reports/metrics.json`)

| Layer | Metric | Tool | On |
| --- | --- | --- | --- |
| Retrieval | P@5/P@10, Recall@10, MRR, nDCG@10, plus `judged@10` diagnostic | ir_measures | qrels, every ablation row |
| QA (extractive subset) | Exact Match, token F1 | custom | qa_pairs |
| RAG answer-level | Faithfulness, answer relevance, context precision, context recall | RAGAS — **one judge fixed for the whole matrix**, judge model+version recorded in `metrics.json`; the judge must NOT be the generator model (self-judging inflates faithfulness); if the judge ever changes, every row re-runs. Raw judge responses cached to `reports/ragas-cache/` (committed at each milestone cut) — with a live LLM judge, caching is what makes `make eval` reproducible at all. Judged on a fixed 100-question subsample of the answerable set, not all of it (volume ≈ 5–10k judge calls otherwise; free-tier quota exhaustion is the normal case, plan for it) | answerable-subset answers, E-ladder configs |
| Citation grounding | citation resolvability (each `[n]` → retrieved chunk) | custom programmatic | every generated answer (must be 100%) |
| Sufficiency gate | fire rate on the 60-question held-out unanswerable half, false-fire rate on answerable | custom | qa_pairs (target ≥80% / ≤10%) |
| Performance | p50/p95 latency per stage, records/sec, cost estimate, scalability note | timing logs | full system |

## 5. Q2 speed protocol

Five fixed demo queries (one per query type); per-query end-to-end latency + per-stage breakdown recorded from the UI run; numbers go into the report verbatim.

## 6. Record counting: what the "≥1,000" counts

The brief says "manually labeling at least 1,000 records": **one record = one manually labeled row**. Two row types: QA-pair rows (`qa_pairs.jsonl`) and qrels judgment rows (`qrels.jsonl`). The two query sets draw from **one shared pool of ≥250 questions**: a question can yield both a QA-pair row and several pooled qrels rows; additions may be disjoint where a question type suits one artifact only (e.g., unanswerable questions are QA-only).

- Floor: ≥1,250 total labeled rows (QA rows + qrels rows) so subsampling can't dip under 1,000.
- The Q4 report includes a count table: | artifact | labeled rows | double-labeled % | raw agreement | Cohen's κ |, plus the unique-question count alongside, for transparency under either reading of the requirement.

### Why ≥250 questions (the arithmetic, for anyone about to ask)

- **Questions are seeds; records are the harvest.** One question yields ~61 labeled rows: 1 QA-pair row + ~60 pooled passage judgments (≈60 candidates per query, §1). So ≥250 questions × ~61 ≈ 15,000 raw judgments — subsample to fit annotator effort and you still clear the ≥1,250-row floor with margin. The question count is the *recipe* for exceeding 1,000 records without judging all ~380k chunks in the library.
- **Why not just 20 questions (20 × 61 ≈ 1,220 also clears the floor)?**
  1. *Stability:* with 10 questions, one failure moves a metric by 10 points; with 250, by 0.4. Small-n leaderboards jitter (same reason a coin needs ~300 flips to reveal 50/50).
  2. *Coverage:* 4 query types × the subfields present in the KB — at 20 questions some cells hold a single question, and that cell's measurement is a coin toss.
  3. *Ablation sensitivity:* the E-ladder compares configs whose true differences are small; small differences are only visible when averaged over many questions (Q3 depends on this).
