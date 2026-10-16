# Sparse-engine benchmark gate (Story 1.3 prep) — 2026-10-15

Resolves the spine Deferred item "Sparse engine final pick" (stack.md ladder
`rank_bm25` → `bm25s` → SQLite FTS5 → Elasticsearch; gate criteria = peak RSS + cold start + p50 latency).

## Setup

- Corpus: the real story-1.2 KB, `data/kb/chunks.jsonl` — 271,171 chunks (cs.*, 12,350 papers).
- Laptop: Linux, 30GB RAM, CPU only. Python 3.11.15.
- Versions: `bm25s 0.3.13`, `rank-bm25 0.2.2`, stdlib `sqlite3` FTS5, `numpy 2.4.6`, `scipy 1.17.1`.
- One shared tokenizer for all engines: lowercase, `[a-z0-9]+`, small English stopword list (FTS5 indexed the pre-tokenized, space-joined text).
- Retrieval depth 300 (the pinned `candidate_depth`), 40 research-style queries.
- Each (engine, phase) ran in its own process, so `ru_maxrss` is that phase's own peak.
  Cold start = time from process start of the query phase until the index is ready to answer.

## Results

| Engine | Build (s) | Build peak RSS | Disk | Cold start | Serving peak RSS | p50 | p95 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `bm25s` (mmap load) | 25.6 | 5.3GB | 266MB | 0.37s | 142MB | 9.1ms | 11.6ms |
| SQLite FTS5 `bm25()` | 11.9 | 3.6GB | 613MB | ~0s | 31MB | 31.3ms | 57.6ms |
| `rank_bm25` (pickle) | 18.7 | 6.0GB | 381MB | 4.1s | 3.1GB | 334.1ms | 467.2ms |

Tokenizing the corpus took 22–25s in every case and is included in the build peak RSS (the
tokenized corpus is held in memory). All three engines returned the same top-5 chunks for the
first query, so ranking quality does not separate them; the gate is decided on resources.

## Decision

**`bm25s` 0.3.13** is the sparse engine behind `SparseRetriever`.

- `rank_bm25` fails the gate: 3.1GB resident just to serve, 4s cold start, and ~0.3s per query on
  the sparse leg alone. It also has no persistence beyond pickle.
- FTS5 is the leanest at serving time but 3.4× slower at p50 than `bm25s`, and its index is 2.3×
  larger. Its `bm25()` ranking also depends on SQLite's own tokenizer configuration rather than our
  tokenizer, which makes the BM25 explanation in the report less transparent.
- `bm25s` stores BM25 as sparse matrices, saves/loads with mmap, serves at ~142MB resident, and
  answers in ~9ms. The build peak (5.3GB) is dominated by holding the tokenized corpus and fits
  the team's laptops.

`rank-bm25` (pinned in the spine Stack table) is therefore not added to `uv.lock`; `bm25s` replaces
it. The engine stays a config value (`sparse_engine`), so a later swap is a new adapter plus a config
row, never a fork.

## The 40 benchmark queries

Used for the sparse gate above and for the story-1.3 acceptance latencies (k = 10, one warm-up query first).

1. attention mechanism for neural machine translation
2. convolutional neural network image classification
3. generative adversarial networks training instability
4. word embeddings semantic similarity
5. reinforcement learning policy gradient
6. graph neural networks node classification
7. dropout regularization overfitting deep networks
8. stochastic gradient descent convergence rate
9. recurrent neural network long short-term memory
10. variational autoencoder latent space
11. named entity recognition conditional random fields
12. sentiment analysis of tweets
13. question answering reading comprehension dataset
14. knowledge graph embedding link prediction
15. batch normalization internal covariate shift
16. adversarial examples robustness
17. transfer learning domain adaptation
18. topic modeling latent dirichlet allocation
19. speech recognition acoustic model
20. object detection region proposal
21. differential privacy machine learning
22. federated optimization communication cost
23. compressed sensing sparse recovery
24. matrix factorization recommender systems
25. monte carlo tree search game playing
26. bayesian optimization hyperparameter tuning
27. kernel methods support vector machines
28. clustering high dimensional data
29. semantic segmentation fully convolutional
30. image captioning encoder decoder
31. dependency parsing transition based
32. SAT solver satisfiability heuristics
33. formal verification model checking
34. distributed consensus byzantine fault tolerance
35. wireless network scheduling throughput
36. cryptographic protocol security proof
37. approximation algorithm submodular maximization
38. social network community detection
39. information retrieval ranking function
40. low rank matrix completion
