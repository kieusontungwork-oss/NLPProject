# PaperPilot Spec Review — Round 2

**Reviewer:** Claude (Opus 5) | **Date:** 2026-09-17
**Files reviewed:** SPEC.md, pipeline-stages.md, evaluation-plan.md, stack.md, team-split.md, stories.yaml
**Also checked against:** the assignment brief itself (`git show HEAD:docs/AI6127_Assignment.md` — see N12)

---

## TL;DR

Round-1 §§1–3: **10 of 13 fixed**, several better than recommended (the E6Δ diagnostic and the λ-blend fallback in `pipeline-stages.md` are stronger than what I asked for). **1.3 and 3.3 are still open.**

The second pass, now including a line-by-line check against the brief, found **4 high-severity issues** the first pass missed:

1. **Pool bias will suppress exactly the innovations you are measuring** (N1) — this threatens the project's headline claim.
2. **The spec sets itself a failing IAA bar the brief never asked for** (N2).
3. **The chunk-count arithmetic is internally inconsistent by 2×**, and the FAISS/BM25 sizing hangs off it (N3).
4. **Section-aware weighting — the novelty hook — is still unspecified as a mechanism**, and has a silent polarity trap (N4).

Plus two brief-mandated submission items that are simply missing (N5) and a Q4 metric gap (N6).

---

## 0. Round-1 verification

| #   | Issue                               | Status | Evidence |
| --- | ----------------------------------- | ------ | -------- |
| 1.1 | FAISS "flat IVF"                    | ✅ Fixed | `stack.md`: `IndexIVFFlat` (nlist≈1000, nprobe≈50), `IndexFlatIP` fallback, `train()` noted. Residual: see N4b, N13 |
| 1.2 | Section-aware weighting placement   | ✅ Fixed well | Moved pre-fusion in the diagram + a "why" paragraph + E6Δ diagnostic + λ-blend fallback |
| 1.3 | Week-0 deadline                     | ❌ **Open** | `team-split.md` milestones unchanged ("Week 0 by ~09-19"); no go/no-go rule anywhere; story 1 has no timebox |
| 2.1 | HyDE → dense only                   | ✅ Fixed | Consistent across SPEC CAP-3, pipeline diagram, E5a/E5b, story 5 |
| 2.2 | Ablation vs pipeline order          | ✅ Fixed | "Ladder order ≠ pipeline order" paragraph resolves it cleanly |
| 2.3 | CAP-5 ownership                     | ✅ Fixed | `make eval` ownership section: namespaced `retrieval.*`/`answer.*`/`speed.*` + trigger rule |
| 3.1 | "1,000 records" interpretation      | ✅ Fixed | eval-plan §6 + dated TA question (10-03) + a concrete fallback that satisfies both readings |
| 3.2 | Insufficient-evidence trigger       | ✅ Fixed | Two-stage gate, config-flagged, with an acceptance test and a documented rejection rationale |
| 3.3 | Weighted vs plain Cohen's κ         | ❌ **Open** | No `weights='quadratic'` anywhere; see N2, which supersedes and enlarges this |
| 3.4 | Unanswerable slice size             | ✅ Fixed | 25 questions (~10%), consistent in eval-plan §2 and story 6. But see N9 |
| 3.5 | Checkpoint flags                    | ✅ Fixed | Header comment in `stories.yaml`, including the both-flags case |
| §4  | Recommendations 4.1–4.5             | — | Untouched, as expected. 4.1 is now superseded by N3; 4.3 by N6/quota note |

---

## 1. High severity (new)

### N1. Pooled qrels are built only from the baseline legs — the ablation will understate every innovation

**Where:** `evaluation-plan.md` §1 + `team-split.md` milestones.

**The problem:** pooling takes "top-10 from BM25, dense, and RRF legs" (that is, E1/E2/E3 only), and the milestone table starts pooling in Week 3 — *before* story 5 builds rerank, rewrite, and section-aware weighting in Week 4. Every chunk that only the innovations surface is therefore **unjudged**, and `ir_measures`, like `trec_eval`, scores unjudged documents as **non-relevant**.

**Why it matters more than it sounds:** the bias is not random, it points one way. It penalizes precisely the runs whose gain you need to demonstrate.

- E4: the cross-encoder reranks the **top-50** from fusion, but you only judged the top-10 per leg. Ranks 11–50 are mostly unlabeled, so a rerank that correctly promotes a chunk from rank 34 to rank 3 scores as if it promoted an irrelevant chunk — a **penalty for working**.
- E5a/E5b: HyDE and multi-query exist to retrieve chunks lexical/dense baselines missed. Every such chunk is by construction outside the pool.
- E6: section-aware weighting reorders the candidate pool pre-fusion; same story.

SPEC's success signal is "the ablation matrix shows ≥1 innovation with measurable gain." As specified, the measurement is biased against that outcome.

**Recommendation** (standard TREC practice, all three together):

1. **Pool deeper:** top-20–25 per leg instead of top-10, so the rerank depth is at least partly covered.
2. **Second pooling pass after story 5:** once the innovation configs run, pool their newly-surfaced top-10s and judge the delta. This is incremental pooling and it is normal — budget a labeling slot for it in Week 5. It is much cheaper than the first pass because most chunks are already judged.
3. **Report `judged@10`** (fraction of each run's top-10 that carries a label) as a per-row column in the ablation matrix, and add **bpref** alongside nDCG. bpref (Buckley & Voorhees 2004) is explicitly designed to be robust to incomplete judgments, and `ir_measures` supports it. If a row's `judged@10` is low, its nDCG is a lower bound and the report should say so.

This also turns a liability into a talking point: "we measured and corrected for pool bias" is exactly the kind of rigor that reads well in a graded report.

---

### N2. `Cohen's κ at IAA ≥80%` sets a bar the brief never asked for — and one you may fail while succeeding

**Where:** `SPEC.md` CAP-6 success, `evaluation-plan.md` §3. Supersedes round-1 item 3.3.

**What the brief actually says** (Q4, verbatim): *"Build an evaluation dataset by manually labeling at least 1,000 records with an inter-annotator agreement of at least 80% (it is recommended to have 3 annotators, but 2 is also OK)."*

**Three distinct problems:**

**(a) You promoted "80% agreement" to "κ ≥ 0.80."** Those are very different bars. κ corrects for chance agreement; under Landis & Koch, 0.81–1.00 is the *top* band ("almost perfect"). Your pooled relevance labels will be heavily skewed toward 0 (most pooled candidates are irrelevant — that is what pooling does), and on a skewed distribution high raw agreement produces a *low* κ. A realistic outcome is **88% raw agreement with κ ≈ 0.55**: you satisfy the brief comfortably, and fail your own SPEC success criterion. Fix the wording: raw agreement ≥80% is the requirement; κ is reported additionally as a stronger, chance-corrected statistic, not gated at 0.80.

**(b) Plain vs weighted κ** (round-1 3.3, still open): the scale is ordinal (0/1/2). Use `cohen_kappa_score(y1, y2, weights='quadratic')` so a 0-vs-2 disagreement counts worse than 0-vs-1, and say so in the labeling guidelines.

**(c) Cohen's κ is a two-rater statistic**, but §3 plans "2–3 annotators" with 15–20% double-labeled. With 3 annotators you get three pairwise κ values and no stated way to aggregate them. Specify: report pairwise κ per annotator pair plus the mean, or use **Fleiss' κ** where ≥3 raters judged the same items. Right now "κ per artifact" is undefined.

---

### N3. The chunk-count estimate is internally inconsistent by ~2×, and three downstream decisions hang off it

**Where:** `SPEC.md` Assumptions → propagates to `stack.md` (FAISS sizing, sparse-engine choice) and `pipeline-stages.md`.

**The problem:** *"10k full papers ≈ 50M+ words / 300k–600k chunks."* Those two halves do not agree.

```
50M words x ~1.3 tokens/word (technical English)  = ~65M tokens
512-token chunks, 15% overlap -> stride 435       = ~150k chunks
256-token chunks, 15% overlap -> stride 218       = ~300k chunks
                                        => 150k - 300k, not 300k - 600k
```

To actually reach 600k chunks you need ~130M tokens ≈ **100M words ≈ 10,000 words/paper** — long for a typical arXiv CS paper. So either the word estimate is low or the chunk range is high; they cannot both stand.

**Why it matters — it is load-bearing in three places:**

- `stack.md` sizes the FAISS index "for ~500k chunks" with `nlist ≈ 1000`.
- `stack.md` gates the sparse-engine decision on "if 300k–600k chunks prove too slow" — `rank_bm25` is far more defensible at 200k than at 600k, so this may pre-commit you to Pyserini/Elasticsearch ops you do not need.
- CPU embedding time (the "hours, feasible one-off" assumption) scales linearly with it.

**Recommendation:** pin the estimate to one chunk size, state the words/paper assumption explicitly, and make story 1 output the measured figure (chunks-per-paper from the test slice) so Week-0 replaces the estimate with a number before any index sizing is frozen.

---

### N4. Section-aware weighting — the novelty hook — is still unspecified as a mechanism

Round-1 fixed *where* it sits in the pipeline. It never specified *what it does*. This is the component the whole novelty claim rests on, and it is the least defined thing in the docs.

**(a) No formula, no weights, no tuning protocol.** "Boost abstract/methodology/results/conclusion over boilerplate" does not say: multiplicative or additive? What weight per section? Fixed by hand or tuned on a dev set? Note the fallback in the same file *is* specified (`rerank_score + λ·section_weight`) while the primary path is not — invert that. Suggested concrete form: re-sort each leg by `score' = score + λ·w[section]` with `w` from a small fixed table and `λ` tuned on a held-out dev slice (the same one as N7), then run RRF over the re-ordered ranks.

**(b) Polarity trap — the boost can silently invert on the dense leg.** `stack.md` specifies `IndexIVFFlat`, whose FAISS default metric is `METRIC_L2` (a **distance**: lower is better), while the stated fallback `IndexFlatIP` is a **similarity** (higher is better). Section weighting is applied "to leg scores before fusion" — so on an L2 index a boost of 1.2× makes a chunk rank **worse**, and the novelty quietly does the opposite of its intent on one of two legs. Also, cosine can be negative, so multiplicative boosting is polarity-unsafe in general. Fix: state that embeddings are L2-normalized and **both** index types are built with `METRIC_INNER_PRODUCT` (so the IVF quantizer is `IndexFlatIP` too), making both legs higher-is-better; or do the weighting in rank space, where the question cannot arise.

**(c) Section-name normalization is unspecified and unowned.** Real arXiv papers carry headers like `3.2 Experimental Setup`, `Related Work`, `Discussion`, `Ablations`, `Appendix A`. Something must map those onto the canonical {abstract, method, results, conclusion, boilerplate} buckets, and that mapping is the practical crux of the whole idea. `pipeline-stages.md` lists `section_rank` in the chunk schema but never defines it (position in paper? the weight bucket?). No story owns the normalizer: subgroup A produces `section_name` in CAP-1, subgroup B consumes it in CAP-3 — **this is the same interface gap between A and B that you just fixed between B and C in 2.3.** Define the taxonomy as a committed artifact (e.g. `config/section_map.yaml`) owned by A, consumed by B, with a documented fallback bucket for unmatched headers and a reported coverage figure ("X% of chunks mapped to a named bucket").

---

## 2. Medium severity (new)

### N5. Two brief-mandated submission items are missing from the checklist

**Where:** `team-split.md` submission checklist.

**(a) Generated answers are not in the data zip.** The brief, §4 item 4, requires a link to an archive with *"your knowledge base, queries and their retrieved results, evaluation dataset, **generated answers or classification results**, and any other data for Questions 3 and 5."* Your checklist has KB, 5 queries + retrieved results, eval datasets, and Q3/Q5 ablation data — the generated answers are the one item dropped.

**(b) The "who did what" decision is never made, and it changes everyone's grade.** The brief, §2: *"you can split your group into up to three subgroups ... and specify who did what in your final report so that each member will be graded accordingly. If this information is not specified, a unique grade will be given to the whole project and this will be shared among all members of the group (recommended option)."*

`team-split.md` builds three subgroups with explicit point allocations (20/40/40) — but nothing decides whether that split gets **declared in the report**. Declaring it means each member is graded on their subgroup's section; not declaring it means one shared grade, which the brief marks as *recommended*. These are materially different risk profiles and the docs are silent. Make it an explicit open question in SPEC.md with a decision date, and add the corresponding line (contribution statement, or a deliberate omission) to the checklist.

---

### N6. Q4 asks for a task-quality metric your answer format does not have one for

**Where:** `evaluation-plan.md` §4, `SPEC.md` CAP-5.

The brief's Q4 bullet: *"Provide task-appropriate quality metrics on such dataset: precision, recall, and F-measure for classification; **Exact Match and F1 for extractive QA**; **ROUGE or BERTScore for summarization**."*

PaperPilot generates prose research answers. You compute EM/F1 **on the extractive subset only** — so the abstractive majority of your answer set has no task-quality metric at all. RAGAS does not fill the gap: it is the *next, separate* bullet in Q4 (answer-level RAG metrics), not a substitute for the task metric.

**Recommendation:** add ROUGE-L and/or BERTScore against the gold answers over the full answerable set, and keep EM/F1 on the extractive subset. Both are cheap (`evaluate`/`bert-score`, no LLM judge, no quota) and they close a bullet on a 40-point question. Add the row to the §4 metric matrix and to story 8.

---

### N7. The τ calibration slice is not stated to be held out

**Where:** `pipeline-stages.md` gate definition, `stories.yaml` story 7.

"Calibrated on a ~50-question dev slice — never a hard-coded default" is the right instinct, but the slice's *origin* is unspecified. If those 50 questions are drawn from the 250 + 25 eval set, τ is tuned on test and the reported ≥80% / ≤10% gate rates are optimistic — in a report that explicitly claims reproducibility.

**Recommendation:** write ~50 extra calibration questions (a mix of answerable and unanswerable), keep them **disjoint** from `qa_pairs.jsonl` and `qrels.jsonl`, and say so in one line in both files. Cheap now, awkward to retrofit after the labeling sprint.

---

### N8. The qrels binarization threshold is unspecified — it changes every retrieval number

**Where:** `evaluation-plan.md` §1 and §4.

The scale is 3-point (2 = supporting, 1 = related but insufficient, 0 = irrelevant). nDCG@10 uses the graded values directly, fine. But **P@5/P@10, Recall@10/100 and MRR are binary measures** and need a cutoff, and `ir_measures` defaults to treating **rel ≥ 1** as relevant. Unless you say otherwise, "related but insufficient" counts as a hit and every precision figure in the report inflates.

**Recommendation:** pin it explicitly — e.g. `P@10(rel=2)`, `R@100(rel=2)`, `RR(rel=2)` — and state the choice in §4 and in the report. If you want both, report rel=2 as primary and rel=1 as a lenient secondary; that is a legitimate extra column, not a hedge.

---

### N9. n=25 is too small for the gate's ≥80% acceptance criterion

**Where:** `SPEC.md` CAP-4 success, `pipeline-stages.md`, `evaluation-plan.md` §2.

Fixing the unanswerable slice at 25 (round-1 3.4) resolved the ambiguity, but the acceptance test is "fires on ≥80% of unanswerable." At n=25 that is 20 questions, **one question moves the rate 4 points**, and the 95% CI around 80% runs roughly 61%–91%. The criterion cannot distinguish a passing system from a failing one.

**Recommendation:** either raise the slice to ~50 unanswerable (still only ~17% of the set, and it is the cheapest labeling in the whole sprint — no gold answer to write), or keep 25 and reframe the criterion as descriptive, reporting the rate with a Wilson interval rather than as a pass/fail gate. The false-fire side (on ~250 answerable) is adequately powered either way.

---

## 3. Low severity (new)

| #   | File | Issue | Fix |
| --- | ---- | ----- | --- |
| N10 | evaluation-plan.md | §1 defines **four** query types (terminology-mismatch, exact-term, survey-style, comparison); §5 says "Five fixed demo queries (**one per query type**)" | Add a fifth type (multi-hop is the natural one, and it pairs with the novelty open question in SPEC) or reword §5 |
| N11 | stories.yaml story 5, SPEC CAP-3 | **E6Δ is missing** — story 5 lists "(E1-E4, E5a, E5b, E6)" and CAP-3's success set omits it, but `pipeline-stages.md` now defines it. Drift introduced by the 1.2/2.2 fix | Add E6Δ to both |
| N12 | SPEC.md frontmatter | `sources:` points to `../../../docs/papers/AI6127_Assignment.md` — **wrong directory and the file is deleted** from the working tree (it was `docs/AI6127_Assignment.md`; still recoverable via `git show HEAD:docs/AI6127_Assignment.md`). A "preservation-validated contract" citing a source nobody can open | Restore the file and fix the path. This is the document that settles N2, N5 and N6 — keep it in the repo |
| N13 | stack.md | `nlist ≈ 1000` is below FAISS's own guidance of 4√N–16√N (≈1,800–7,200 at 200k vectors; ≈2,800–11,300 at 500k). Workable but not the recommendation, and it depends on N3 | Set `nlist` after Week-0 gives the real chunk count; note the rule of thumb in the cell |
| N14 | evaluation-plan.md §1 | `qrels.jsonl` holds **two different record shapes** (`{query_id, text, type, subfield}` and `{query_id, chunk_id, relevance}`) in one file; `ir_measures` expects TREC-style qrels | Split into `queries.jsonl` + `qrels.jsonl` |
| N15 | evaluation-plan.md §1 | "≥250 queries × ~30 candidates ≈ 7,500" **double-counts**: the RRF top-10 is largely a re-ordering of the BM25/dense top-10s, so the unique pool is ~15–20 per query (~4–5k, not 7.5k) | Restate as unique-after-dedup. Does not threaten the ≥1,250 floor; N1's deeper pooling raises it again anyway |
| N16 | stack.md | "No LangChain/LlamaIndex — **the brief wants** the stages implemented by us" overstates: the brief explicitly *lists* LangChain/LlamaIndex/Haystack/DSPy as useful components. Separately, RAGAS pulls `langchain-core` transitively, so it will appear in your lockfile regardless | Reword as a deliberate self-imposed choice (which is a good one and worth defending in the report), and note the transitive dep so a marker does not misread it |
| N17 | team-split.md | Load imbalance: A finishes CAP-1 by Week 2 and then has only labeling coordination for four weeks, while C carries CAP-4 + answer-level eval + UI shell + full report assembly | Move report assembly (CAP-8) or the UI shell to A |
| N18 | SPEC.md | Q5 currently rests on a **single** innovation (E7 self-check), while Q3 carries a nine-row ladder. The brief asks for ablation "if you introduce more than one" — with one, there is nothing to ablate on the 40-point downstream side | Already tracked as an open question with a Week-4 date; just noting the asymmetry is a scoring risk, not only a scope choice |
| N19 | SPEC.md CAP-7 | "The **five assignment demo queries**" — the assignment supplies no queries; Q2 says *"Write five queries."* | Reword to "five fixed demo queries (ours)" and cross-reference `data/demo_queries.txt` (round-1 4.2) |
| N20 | team-split.md | The Q4 row maps "preprocessing" to CAP-4/5/6, but preprocessing/cleaning is CAP-1 (subgroup A) | Add CAP-1 to the Q4 row's evidence column |

---

## 4. What to do next

**Decisions only you can make** (each changes the docs materially):

1. Declare subgroups in the report, or take the brief-recommended shared grade? (N5b)
2. Raise the unanswerable slice to 50, or reframe the gate criterion as descriptive? (N9)
3. Add ROUGE-L/BERTScore to close the Q4 task-metric bullet? (N6 — I recommend yes; it is cheap and it is an explicit brief bullet)
4. Is the Week-0 spike still landing 09-19, and what is the go/no-go fallback? (round-1 1.3, still open)

**Mechanical fixes, ready to apply on your word** — N10, N11, N12, N14, N15, N16, N19, N20, plus the wording changes in N2a/N2b, N8 and N7. None of these need a decision; they are internal consistency and brief-compliance.

**The one to act on first:** N1. Pool depth and the second pooling pass have to be decided *before* the Week-3 labeling sprint starts, because retrofitting judgments after the fact costs a second full annotation round.
