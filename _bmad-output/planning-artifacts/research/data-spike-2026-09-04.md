# Data Spike Report — Week-0 real-download verification (Stage 0 gate)

**Date:** 4 Sep 2026 · **Runner:** opencode session · **Method:** actual `curl` downloads from HF resolve URLs (bytes on disk, not API checks) · **Artifacts:** `NLPProject/data/spike/`

## Results table

| Dataset | Status | Size | Rows | Fields | Notes |
|---|---|---|---|---|---|
| `winddude/reddit_finance_43_250k` (`top.jsonl`) | ✅ **PASS** (full download, 7m44s) | 649 MB | **250,000** (exact) | `id, title, selftext, z_score, normalized_score, subreddit, body, comment_normalized_score, combined_score` | post + paired comment per row; ⚠️ no timestamp field (see below) |
| `lamini/earnings-calls-qa` (`filtered_predictions.jsonl`) | ✅ PASS (byte-range verified; full 3.9 GB deferred to Wk 1) | 3.9 GB total | ~2k transcripts + QA | `question, answer, date, transcript` | `date` present → timeline feature lives here; many QA answers are "I do not know" → use transcripts as KB, not QA pairs |
| `zeroshot/twitter-financial-news-sentiment` (train+valid CSVs) | ✅ PASS | 1.1 MB | 12,426 (9,939 + 2,487) | `text, label` (0=bearish, 1=bullish, 2=neutral) | label dist: 62% neutral / 19% bullish / 14% bearish → subsample for classifier training; neutral-heavy is fine for subjectivity stage |
| `McAuley-Lab/Amazon-Reviews-2023` (`Digital_Music.jsonl` slice) | ✅ PASS (11 s) | 75 MB | 130,434 | standard Amazon review schema (rating/title/text/…) | twin plan clears 10k-doc bar from one small category alone |
| `StephanAkkerman/wallstreetbets-ner` (parquet) | ✅ PASS | 648 KB | 671 | `id, text, entities` | ticker-extraction eval aid, as planned |
| ~~`SocialGrep/reddit-wallstreetbets-aug-2021`~~ | ❌ **DEAD** (found 4 Sep) | — | — | — | loader fetches `exports.socialgrep.com` → NXDOMAIN; replaced by winddude |

## winddude deep-dive (finance anchor)

- **Corpus scale:** 250k rows ≈ **100.5M words** (all rows counted) — the brief's ≥100k-word bar is cleared ~1000×; ≥10k-doc bar cleared 25×. Even a 1% subsample satisfies both.
- **Subreddit spread (43 subs):** Superstonk 30.3k, personalfinance 16.3k, investing 13.6k, fatFIRE 11.9k, AusFinance 11.3k, … wallstreetbets itself 5.4k. Mix of trading, personal finance, crypto, regional (UK/AU/CA/IN) — all English.
- **⚠️ No timestamp field.** Mitigations for the sentiment-timeline signature feature: (1) earnings-call `date` field carries the feature; (2) Reddit base36 post-IDs are roughly time-ordered → approximate-date mapping possible post-hoc if needed.
- **Polarity skew (VADER on first 5,000 rows):** posts 74% pos / 25% neg / 1% neu; comments 70% / 26% / 4%. Expected consequence of upvote+length pre-filtering. **Interpretation:** this is lexicon polarity, not entity stance; the brief's balance requirement applies to *our eval set*. **Mitigations baked into CAP-8:** stratified sampling for human labeling (deliberately over-sample negative/neutral-leaning texts + entity-centric samples); balanced `eval.xls` by design; earnings-call text (more factual) helps the subjectivity stage; classifier training uses the tweet benchmark labels, not VADER.

## Requirement scorecard (Stage 0 gate)

| Brief requirement | Finance plan | Twin plan |
|---|---|---|
| ≥10,000 docs/passages | ✅ 250k (+ transcripts) | ✅ 130k from one small category |
| ≥100,000 words | ✅ ~100.5M | ✅ (millions) |
| Balanced data | ⚠️ corpus skews positive → managed via stratified labeling + balanced eval design | ✅ star ratings span 1–5 |
| Access/licenses | ✅ all HF-hosted, not gated, tested | ✅ same |

## Decisions

1. **Finance plan is GO** — anchor switched to winddude (done in SPEC/proposal 4 Sep).
2. Week-1 additions: full lamini download (3.9 GB) or transcript-only extraction; decide KB subset size (250k rows → est. 400–800k chunks; FAISS flat ≈ 1.2 GB at 384-dim — laptop-viable, may subsample to ~100–150k rows for iteration speed).
3. Timeline feature scoping: earnings-call dates primary; Reddit ID→date estimation optional stretch.
4. Domain lock stays scheduled Mon 7 Sep per plan; spike found no blocker.
