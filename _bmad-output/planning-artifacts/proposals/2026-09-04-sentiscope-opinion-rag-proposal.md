# Proposal: SentiScope — a chat assistant that answers "what do people think about X?"

**Project:** AI6127 group assignment (35% of course grade) · **Due:** 7 Nov 2026, 11:59pm SGT · **Presented:** Week 13
**Status:** proposal for team discussion · 4 Sep 2026

---

## 1. The idea

- **Problem:** when people want to know *"Is NVDA hype justified?"* or *"Is the Sony WH-1000XM5 worth it for flights?"*, they get marketing pages or have to scroll through hundreds of messy Reddit posts and reviews themselves.
- **Idea:** build **SentiScope** — a chat assistant. You ask an opinion question in plain English; it searches a large library of real posts/reviews, reads the most relevant ones, and answers with:
  - a **stance breakdown** (e.g., 68% positive / 22% negative / 10% neutral),
  - a **topic-by-topic summary** (e.g., for a headphone: sound ✅, price ❌, comfort ✅),
  - **quotes with links**, so every claim can be checked.

This is exactly the example our assignment sheet gives ("a system that finds relevant opinions about bitcoin … and reports that they are 70% positive and 30% negative"), executed as a polished, conversational product.

## 2. Why this project (and why it should score well)

1. **It matches what the course rewards.** The assignment grades three things: the knowledge base (20 pts), retrieval (40 pts), and the downstream task + generation (40 pts) — plus **novelty and usefulness**. SentiScope has a clear job, a friendly interface, and measurable quality at every stage.
2. **It sits right on the professor's research.** The course is taught by Prof. Cambria's group (SenticNet), whose lab works on sentiment/opinion mining, aspect-based sentiment analysis, explainable AI, and financial sentiment (they literally have a paper on *retrieval-augmented market-sentiment systems*). Building in their field, with the hybrid "knowledge + neural" style they advocate, is a strategic choice.
3. **The data already exists.** We don't need to scrape the internet from scratch — there are large, free, licensed datasets ready to download (millions of finance posts; millions of product reviews). Our effort goes into building the system, not hunting for data.
4. **The hand-labeling requirement is genuinely manageable.** The assignment requires 1,000 hand-labeled records in a standard sentiment-dataset table (`eval.xls`) — these are *opinion labels* (what does this text say: positive/negative/neutral?), not search judgments. In our domains most records come with a "free" first guess (star ratings / post annotations), so teammates mostly *verify* pre-filled labels instead of labeling from zero. Separately, to measure search quality we will label a much smaller set (~100 queries with "was this result relevant?" judgments) — planned as its own small task, not a surprise.

## 3. What it looks like to a user

```
┌────────────────────────────────────────────────────────────────────┐
│  You:  Is the Sony WH-1000XM5 worth it for flights?                │
│                                                                    │
│  SentiScope: Mostly yes — strong on comfort, weak on price.        │
│  Across 1,204 reviews: 68% positive, 22% negative, 10% neutral.    │
│                                                                    │
│  • Noise cancelling:  81% positive — "ANC is unreal on planes" [1] │
│  • Comfort:           74% positive — "wore them 9h, no fatigue" [2]│
│  • Price:             54% negative — "great, but $399 is a lot"[3] │
│                                                                    │
│  [1] ★★★★★ review, verified purchase → link                        │
│  [2] ★★★★☆ review → link        [3] ★★☆☆☆ review → link           │
│                                                                    │
│  Ask a follow-up: "How is the battery?"                            │
└────────────────────────────────────────────────────────────────────┘
```

Follow-up questions keep their context ("How is the battery?" still knows we're talking about the XM5), and every answer shows where its evidence came from — that transparency is a big part of the pitch.

### Three signature features (what makes SentiScope more than the assignment's example)

1. **"Wall Street vs. Main Street."** Ask *"What do professional earnings calls vs. Reddit traders say about NVDA?"* — the system contrasts formal, fundamentals-focused language against informal crowd hype on the same ticker, side by side, each with its own evidence. Our two-source library makes this possible; a plain Reddit-only project can't do it.
2. **Sentiment timeline.** Ask *"How did sentiment on TSLA shift this month?"* — answers come with a before/after breakdown, not just a snapshot. (Searching within time windows is itself one of the improvements the assignment explicitly rewards.)
3. **Head-to-head comparison.** Ask *"NVDA vs AMD — which do people trust?"* or *"XM5 vs Bose QC Ultra for flights?"* — the system decomposes the question, retrieves evidence for both sides, and answers with a balanced contrast.

## 4. How it works (three parts = three graded components)

Think of a very fast research assistant working in a library:

| Part                        | What it is (plain English)                                                                                                                                                                                        | Analogy                                 | Assignment weight |
| --------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------- | ----------------- |
| **1. Knowledge base** | We collect hundreds of thousands of real posts/reviews, clean them, and cut them into small searchable pieces                                                                                                     | Building and organizing the library     | 20 pts            |
| **2. Retriever**      | Two search engines run in parallel — one matches**exact words**, one matches **meaning** — and their results are merged, then double-checked by a sharper "re-ranker" that reads candidates closely | The librarian who finds the right pages | 40 pts            |
| **3. Generator**      | An AI language model reads only the found pages and writes the final answer — stance percentages, per-topic summary, quotes with sources                                                                         | The analyst who writes the briefing     | 40 pts            |

A key design point (and a grading requirement): the model **must answer from the retrieved pages, not from its own memory**, and we will *measure* how faithful it is — every citation must point to a real retrieved passage, quoted text must actually appear in that passage, and an independent checker scores how well every claim is backed by evidence. Everything is implemented by us on standard open-source building blocks — it is not a paid "RAG in a box" service.

**What it runs on (infrastructure & budget):** zero cash budget. All search indexes and the answering model run on our own laptops (free open-source models); a free-tier cloud model is used only to speed up the live demo and automated quality scoring, with a fully-local fallback if quotas run out; the small opinion classifiers are trained on free Google Colab GPUs. Disk needed: ~10–20 GB. No paid services anywhere.

## 5. Which domain? Finance first, product reviews as twin

Both domains fit the same system. We run a 2-day data check in Week 1 and lock the choice:

|                  | **A. Finance (primary plan)**                                          | **B. Product reviews (twin plan)**                                    |
| ---------------- | ---------------------------------------------------------------------------- | --------------------------------------------------------------------------- |
| Library content  | Reddit finance posts + company earnings-call transcripts                     | Amazon customer reviews (e.g., headphones, laptops)                         |
| Example question | "Is NVDA hype justified?"                                                    | "Is the XM5 worth it for flights?"                                          |
| Data status      | 250,000 posts/comments across 43 finance & crypto subreddits + earnings-call transcripts — both download-tested ✅ | Millions of reviews with star ratings — download-tested ✅ |
| Labeling ease    | Good — finance-tweet sentiment labels anchor our verification                | **Best** — star ratings give an instant quality check for our labels |
| Demo appeal      | High (tickers, hype, drama) + enables the "Wall St vs. Main St" feature      | High (products everyone knows)                                              |

The switch between A and B costs about one week of work because the machinery is identical — so the decision is low-risk. (The Reddit-finance route is the more novel one; the reviews route is the safest one.)

One lesson already applied: our originally-planned Reddit dataset turned out to be dead — its host is offline even though it still looks "available" online, and we only caught this by test-downloading. Rule adopted: **no dataset enters the plan until a real download has succeeded.**

## 6. Who does what (3 subgroups, as the assignment allows)

The assignment lets us report subgroup contributions so each member gets an individual grade. Natural split:

| Subgroup               | Owns                                                                                         | Size |
| ---------------------- | -------------------------------------------------------------------------------------------- | ---- |
| **A. Library**   | Download & clean data, cut into passages, build search indexes, report corpus statistics     | ~2   |
| **B. Search**    | Word-search + meaning-search engines, merging, re-ranking, speed, search quality metrics, UI | ~2   |
| **C. Answering** | Opinion/stance/topic classifier, answer writing with citations, quality evaluation           | ~2   |
| **Everyone**     | Hand-labeling shift (~1 week, spread out), report & slides sections for their part           | all  |

Details in the companion spec (`spec-sentiscope-rag-mvp/team-split.md`).

## 7. Timeline (with buffers — we finish *before* the deadline, not at it)

Hard dates: report due **Sat 7 Nov 23:59**; presentations **9–15 Nov** (after submission). Our plan: everything frozen **8 days before** the deadline, submitted **2.5 days early**, final week pure buffer.

| Weeks (dates) | Milestone |
| --- | --- |
| 0 — this weekend (5–6 Sep) | Real-download test of every candidate dataset (one already failed and was replaced this way); balance check |
| 1 (7–13 Sep) | Data cleaned & chunked; first search engine live; **domain locked Mon 7 Sep**; labeling guidelines drafted |
| 2 (14–20 Sep) | Full hybrid search (word + meaning + merge); quality harness with baseline numbers; ~100 search-relevance judgments; labeling pilot |
| 3 (21–27 Sep) | Chat UI v1; first grounded answers with citations; **1,000-label sprint done** |
| 4 (28 Sep–4 Oct) | Tier-1 upgrades: re-ranker, query expansion; `eval.xls` frozen with agreement report |
| 5 (5–11 Oct) | Signature features v1 (Wall St vs. Main St, timeline, comparisons); opinion classifiers trained |
| 6 (12–18 Oct) | Full before/after experiment table; "failed earlier / works now" examples collected |
| 7 (19–25 Oct) | UI polish; report drafting (every section has real numbers); clean-rebuild rehearsal |
| 8 (26–30 Oct) | **Content freeze Fri 30 Oct.** Report finalized + cross-reviewed by all six |
| 9 (2–7 Nov) | Pure buffer: fixes only, no new features. **Submit Thu 5 Nov** |
| after (8–15 Nov) | Demo polish & rehearsal for the presentation week — zero grading risk |

## 8. What we deliver (per the assignment rules)

1. One PDF report answering the assignment's 5 questions, named by group number
2. Our knowledge base, queries & retrieved results, `eval.xls` (the required name/format for the labeled evaluation set), and generated answers — via a shareable cloud link
3. Source code + README via a shareable cloud link
4. A live demo at the Week 13 presentation

## 9. Risks & fallbacks

| Risk                                                   | Fallback                                                                                                                                                     |
| ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| Finance posts turn out too messy to label consistently | Switch to product reviews (twin plan, ~1 week cost; decision safe until end of Week 3)                                                                       |
| Dataset download blocked / license surprise            | Every dataset passes a real download test *before* entering the plan (this already caught one dead dataset); multiple verified backups listed in the tech spec |
| Reddit data skews one-sided (pre-filtered by upvotes)  | Week-0 balance check; blend in earnings calls + finance tweets; assignment demands balanced data, so this is checked before the domain locks |
| Answer quality unimpressive early                      | The re-ranker + "read more evidence" loop are known, high-impact upgrades; ablation results themselves earn marks                                            |
| Labeling drags on                                      | Pre-filled labels + short guidelines + one focused sprint week; assignment needs ≥80% agreement, which our anchored setup is designed to hit                |
| Schedule slips                                          | Week 9 is deliberate empty buffer; content freeze 30 Oct gives 8 days of slack before the deadline                                                          |
| Another group does "finance sentiment"                 | Our differentiation is the*conversational, topic-level, citation-backed* experience, the "Wall St vs. Main St" contrast, and the earnings-transcript library — not a one-shot sentiment score |

## References

1. AI6127 assignment brief (Blackboard / `papers/AI6127_Assignment.md` in this repo)
2. SenticNet project page — https://sentic.net/projects (lab themes: sentiment & opinion mining, XAI for finance, etc.)
3. Anthropic, *Contextual Retrieval* — evidence that hybrid search + re-ranking sharply cuts retrieval failures
4. Gao et al., *Retrieval-Augmented Generation for Large Language Models: A Survey* (arXiv:2312.10967)
5. Esuli et al. (RAGAS team), RAGAS evaluation metrics — faithfulness, answer relevance, context relevance
6. Dataset leads (all download-tested 4 Sep 2026): `winddude/reddit_finance_43_250k` (250k posts/comments, 43 subreddits); `lamini/earnings-calls-qa`; `zeroshot/twitter-financial-news-sentiment`; McAuley-Lab Amazon Reviews 2023 (twin plan); `StephanAkkerman/wallstreetbets-ner` (ticker-extraction aid)
