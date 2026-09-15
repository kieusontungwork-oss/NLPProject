# Stack — SentiScope RAG MVP

> Companion to SPEC.md. The HOW behind CAP-1/2/5/6/7/9. Principle: laptop-CPU-first, zero paid infra, every heavy model pluggable.

## Pin set

| Component | Pin | Why |
|---|---|---|
| Python | 3.11 (venv or uv) | HF ecosystem sweet spot; Mac + Colab both happy |
| Dataframes | pandas 2.x | corpus cleaning, eval.xls export |
| HF Datasets | latest | one-liner loads of winddude finance dump / earnings calls / Amazon slices |
| Sparse retrieval | `rank-bm25` | zero-ops BM25; revisit only if corpus >1M chunks (SPEC Open Question) |
| Dense retrieval | `sentence-transformers` ≥3.x; models: `all-MiniLM-L6-v2` (baseline) → `BAAI/bge-m3` (upgrade) | CPU-viable; bge-m3 = one model, dense+sparse+multilingual headroom |
| Vector index | FAISS (`faiss-cpu`) or Chroma; flat IndexFlatIP (corpus is small — no ANN needed) | exact search, no recall loss, trivially reproducible |
| Re-ranker | `BAAI/bge-reranker-v2-m3` via FlagEmbedding/sentence-transformers CrossEncoder | top open reranker; CPU-OK at top-50→top-10 |
| Local generation | Ollama: `qwen2.5:7b-instruct` primary, `llama3.1:8b` alt | free unlimited iteration; runs on 16GB Mac RAM |
| Hosted generation/judge | Gemini API free tier (`gemini-2.x-flash`) or Groq free tier | demo-day speed + RAGAS judge; behind a `Generator` interface so swappable |
| Classification heads | transformers + PyTorch; DistilBERT/RoBERTa-base fine-tune on Colab free T4 | subjectivity → polarity two-stage (CAP-5) |
| Eval retrieval | `ir_measures` | P@K/Recall@K/MRR/nDCG from qrels (CAP-7a) |
| Eval RAG | `ragas` + LangChain wrapper for judge LLM | faithfulness / answer relevancy / context precision+recall (CAP-7c); HHEM (open NLI checker) or Ollama-as-judge as quota-exhaustion fallback |
| Labeling | Label Studio Community (docker) | multi-annotator overlap, export to tabular → `eval.xls` (CAP-8) |
| UI | Gradio ≥4 (`gr.ChatInterface`) | streaming chat + in-message HTML citations; Streamlit acceptable if dashboards win the vote |
| Stats/agg | numpy, scipy (κ via `sklearn.metrics.cohen_kappa_score`) | IAA reporting (CAP-8) |

## Repo layout (target)

```
sentiscope/
  makefile              # setup | kb | index | eval | ui  (SPEC success signal)
  configs/
    domain_finance.yaml # corpus paths, chunk params, toggles: rerank/hyde/parent/contextual
    domain_reviews.yaml # twin profile — same schema
  src/
    ingest/             # download, clean, dedup, chunk (CAP-1)
    index/              # bm25 + faiss/chroma build (CAP-2)
    retrieve/           # sparse.py dense.py fuse.py rerank.py expand.py agentic_loop.py (CAP-2/3/4)
    classify/           # subjectivity.py polarity.py stance.py aspects.py (CAP-5)
    generate/           # generator.py (interface), ollama_llm.py, gemini_llm.py, prompts/ (CAP-6)
    eval/               # qrels.py, ir_metrics.py, task_metrics.py, ragas_eval.py, perf.py (CAP-7)
    ui/                 # gradio_app.py (CAP-9)
  data/                 # raw/ processed/ chunks/ (gitignored)
  evalsets/             # eval.xls, qrels.tsv, labeling_guidelines.md, agreement_report.md
  reports/              # metrics.json, ablation.md, kb_stats.json, speed_5queries.md
```

## Config-toggle contract (feeds the ablation matrix)

Every CAP-3 innovation is a YAML bool: `rerank`, `hyde`, `multi_query`, `parent_doc`, `contextual_prefix`, `agentic_loop`. `make eval` sweeps the grid {baseline, +each, chosen-full} and emits `reports/ablation.md`. Adding an innovation without a toggle = review reject.

## Data sources (locked candidates; Week-1 spike verifies)

| Domain | Dataset | Role | Access (verified 2026-09-04) |
|---|---|---|---|
| Finance | `winddude/reddit_finance_43_250k` (HF) | KB main (250k posts+comments, 43 subreddits, `top.jsonl` hosted on HF) | ✅ not gated, file-hosted (real download test at spike) ⚠️ pre-filtered by upvotes/length — balance check needed |
| Finance | `lamini/earnings-calls-qa` (HF) | KB secondary (transcripts, jsonl) | ✅ not gated, file-hosted |
| Finance | `zeroshot/twitter-financial-news-sentiment` (HF, 11.9k bull/bear/neutral) | classifier training anchor + eval sanity check | ✅ not gated, CSVs hosted (MIT) |
| Finance | `StephanAkkerman/wallstreetbets-ner` (HF, 671 gold) | ticker/entity extraction aid | ✅ not gated, parquet hosted |
| Finance | FiQA-2018 + Financial PhraseBank | extra labeled eval material only (small) | research-permitted |
| ~~Finance~~ | ~~`SocialGrep/reddit-wallstreetbets-aug-2021`~~ | ~~KB main (original plan)~~ | ❌ DEAD — loader fetches from `exports.socialgrep.com` (NXDOMAIN); replaced by winddude |
| Reviews (twin) | `McAuley-Lab/Amazon-Reviews-2023` — Headphones + Laptops slices | KB + star-rating silver labels | ✅ not gated, 912 files |
| Reviews (twin) | Steam reviews dataset (HF/Kaggle ~7M, rec/not-rec) | alt twin KB | verify at spike |

## Model/memory budget (laptop CPU)

- Embedding corpus once: MiniLM ≈ 30–60 min for 500k chunks (batched, MPS if available); bge-m3 slower — embed overnight or subset.
- Ollama 7B Q4: ~5 GB RAM, ~10–25 tok/s on M-series; answers ≤300 tokens → acceptable demo latency; Gemini Flash covers live-demo snappiness.
- Reranker on top-50: ~1–3 s/query CPU; fine for demo, logged per stage (CAP-2 success).
- Colab T4: DistilBERT fine-tune on ~10–20k texts = minutes; RoBERTa-base = tens of minutes.
