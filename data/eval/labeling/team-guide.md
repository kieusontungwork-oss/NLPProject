# PaperPilot labeling — team guide (Story 1.6)

This guide tells all 5 of us what to do, when, and how. You do not need to know any code.

- Read this guide once, start to finish (about 15 minutes).
- Keep `guidelines.md` (same folder) open while you label. It has the exact rules and examples.
- If something is unclear, ask in the team chat. Do not guess silently.

---

## 1. Why we are doing this

- Our system answers research questions using a library of **12,350 computer-science papers from arXiv (1994–2017)**.
- To grade it, we need an **answer key** written by humans. The assignment requires **at least 1,000 hand-labeled records**, with **at least 80% agreement** between labelers.
- We make two kinds of answer key:
  - **Passage judgments ("qrels")**: for a question, is this passage from the library relevant? This grades the search part.
  - **Question–answer pairs ("QA pairs")**: a question plus a one-sentence correct answer. This grades the answer-writing part.
- Every number in our final report depends on this answer key. Careful labels = a good grade.

---

## 2. Words you will see

- **Question**: a research question someone might ask, e.g. "Why does dropout reduce overfitting?"
- **Passage**: a short piece of text (about 300 words) cut from one paper. The library has 271,171 passages.
- **Judgment**: one label you give to one passage for one question: **2**, **1** or **0** (see `guidelines.md`).
- **Answerable question**: the library *can* answer it (topic from 2017 or earlier).
- **Unanswerable question**: the library *cannot* answer it, on purpose (topic from 2018 or later, e.g. ChatGPT). We use these to check that the system says "I don't know" instead of making things up.
- **Gold answer**: the correct answer, written by us, in one sentence.
- **Pilot**: a small practice round that everyone labels, to check that we all label the same way.
- **Double-labeling**: two people label the same item without talking, so we can measure agreement.
- **Adjudication**: a third person decides when two labelers disagree.

---

## 3. Who does what

| ID | Name (coordinator fills in) | Subgroup | Role |
| --- | --- | --- | --- |
| P1 | | A | **Coordinator** + writer + labeler |
| P2 | | | Writer + labeler |
| P3 | | | Writer + labeler |
| P4 | | | Writer + labeler |
| P5 | | | Writer + labeler |

- **Everyone (P1–P5)** writes questions, labels passages, writes gold answers, and reviews a few of other people's items.
- **The coordinator (P1)**:
  - runs the scripts that create every spreadsheet you will fill in;
  - shares the spreadsheets in the shared Google Drive folder;
  - collects the finished spreadsheets, checks them, and tells you what to fix;
  - runs the agreement check and leads the disagreement meeting;
  - commits the final files to GitHub.
- **You never run code.** You only fill in Google Sheets.
- Subgroups B and C keep coding their own stories in parallel. Everyone's labeling share is equal.

---

## 4. Where the files live

- One shared Google Drive folder: **"PaperPilot Labeling"**. The coordinator creates it and shares it with everyone.
- Inside it:
  - `0-read-me/` — this guide, `guidelines.md`, the paper catalog
  - `1-questions/` — your question sheet
  - `2-pilot/` — the practice round
  - `3-sprint/` — your main labeling sheet
  - `4-unanswerable-check/` — checking your unanswerable questions
  - `5-gold-answers/` — writing gold answers
  - `6-round2/` — the extra round at the end
- Each folder has **one sheet per person**, named with your ID (e.g. `P3`). **Only edit your own sheet.**
- Golden rules for every sheet:
  - Never rename, delete, add or reorder columns.
  - Never delete rows. If a row is broken, write it in the `comment` column.
  - Fill only the columns marked **(fill)**.

---

## 5. Timeline

| Date | Step | What you do | Time needed |
| --- | --- | --- | --- |
| Sat 17 Oct | Kickoff meeting | Agree on IDs and roles; read this guide | 30 min |
| Sun 18 – Mon 19 Oct | **Step 1: write questions** | Write 50 answerable + 20 unanswerable questions | ~5–6 h |
| Tue 20 Oct | Coordinator checks questions | Fix anything the coordinator flags | ~30 min |
| Tue 20 – Wed 21 Oct | **Step 2: pilot** | Label ~100 passages (same sheet for everyone) | ~1 h |
| Thu 22 Oct | Agreement result | ≥80% → go. Below → 30-min fix meeting, then a second pilot | — |
| Thu 22 – Sun 25 Oct | **Step 3: main labeling** | Label ~1,100 passages | ~8 h (≈2 h/day) |
| Thu 22 – Sun 25 Oct | **Step 4: check unanswerable** | One yes/no per unanswerable question | ~1 h |
| Mon 26 Oct | Disagreement meeting | Decide the disagreements together | 1 h |
| Mon 26 – Tue 27 Oct | **Step 5: gold answers** | One-sentence answer for each of your 50 questions + review a few of others' | ~3 h |
| Tue 27 – Wed 28 Oct | **Step 6: round 2** | Label extra passages found by the improved search | ~3 h |
| Thu 29 Oct | Coordinator merges | Final files + scores re-run | — |
| Fri 30 Oct | **Freeze** | No more changes | — |

- Total: about **20 hours per person** over two weeks.
- Deadlines are **end of day (23:59)**. If you will be late, tell the coordinator **before** the deadline.
- If we fall behind, we cut other work, never labels.

---

## 6. Step 1 — Write questions (Sun 18 – Mon 19 Oct)

### What you get

- Your sheet `1-questions/P<your ID>` with 70 rows already numbered:
  - `P3-001` … `P3-050` → answerable questions
  - `P3-U01` … `P3-U20` → unanswerable questions
- The **paper catalog** (`0-read-me/papers_catalog`): every paper in our library with its title, year, subfield and the start of its abstract. Use it to find topics the library really covers.

### Columns

| Column | What to write |
| --- | --- |
| `query_id` | Already filled. Do not change. |
| `question` **(fill)** | Your question, one sentence, ending with `?` |
| `type` **(fill)** | Pick from the dropdown (see below). Answerable rows only. |
| `subfield` **(fill)** | Pick from the dropdown (see below). Answerable rows only. |
| `source_paper` **(fill)** | arXiv id of the paper that inspired the question, e.g. `1502.02478`. Answerable rows only. |
| `comment` | Optional note |

### Your quota (answerable, 50 questions)

- **By type** (what kind of question):

  | Type | Count | What it means | Example |
  | --- | --- | --- | --- |
  | `terminology-mismatch` | 15 | Ask with **different words** than the paper uses | Paper says "dropout"; you ask "Why does randomly switching off neurons during training help a network generalize?" |
  | `exact-term` | 15 | Use the paper's **exact technical name** | "What is batchwise dropout?" |
  | `survey` | 10 | Ask for an **overview** of a topic | "What methods exist for detecting communities in social networks?" |
  | `comparison` | 10 | Ask to **compare** two things | "How does neural machine translation compare with phrase-based translation in quality?" |

- **By subfield** (topic area). These numbers follow what our library actually contains:

  | Subfield | Count |
  | --- | --- |
  | Machine learning & AI | 10 |
  | NLP & IR | 8 |
  | Computer vision | 7 |
  | Information theory & signals | 7 |
  | Algorithms & theory | 7 |
  | Networks & social | 6 |
  | Systems, security & data | 5 |

- Any type can go with any subfield. Just make the totals match.

### How to write a good answerable question

- Open the paper catalog and filter by a subfield.
- Pick a paper whose abstract you understand.
- Write a question that this paper (or papers like it) can answer.
- Rules:
  - The topic must be from **2017 or earlier** (our library stops in 2017).
  - Ask like a real student or researcher would. One question, one sentence.
  - **Do not copy the paper title** into the question (except for `exact-term`, where you use the method's name, not the whole title).
  - The answer should fit in **one or two sentences**. Avoid "list everything about X".
  - No yes/no questions ("Is dropout good?" ✗ → "Why does dropout reduce overfitting?" ✓).
  - Do not ask about one paper's specific numbers ("What accuracy did paper X get on MNIST?" ✗).
  - Do not write a question someone else on the team already wrote. If you are not sure, check the team's question sheets — they are readable by everyone.
- Good examples:
  - "How does attention help neural machine translation?" (exact-term, NLP & IR)
  - "Why is it hard for a network to learn when a sentence is squeezed into one fixed-length vector?" (terminology-mismatch, NLP & IR)
  - "What techniques are used to reduce interference in wireless networks?" (survey, Networks & social)
  - "How do LDPC codes compare with turbo codes for error correction?" (comparison, Information theory & signals)
- Bad examples:
  - "Can Active Memory Replace Attention?" ✗ (copies a paper title)
  - "How do large language models use RLHF?" ✗ (2022 topic — that is an *unanswerable* question)
  - "Is deep learning useful?" ✗ (yes/no, too vague)

### How to write a good unanswerable question (20 questions)

- These must look like **normal, reasonable research questions**, but the library cannot answer them.
- Use topics that appeared **in 2018 or later**. Ideas:
  - BERT, GPT-2/3/4, ChatGPT, RLHF, instruction tuning, prompt engineering, retrieval-augmented generation (RAG)
  - Diffusion models, Stable Diffusion, vision transformers (ViT), CLIP
  - Federated learning at scale (post-2018 work), large-scale self-supervised learning (SimCLR, MAE)
  - 5G/6G deployment results, COVID-19 contact-tracing apps
- Rules:
  - Search the paper catalog for your topic word (Ctrl+F). If any paper is about it, pick another topic.
  - Do not make them silly or off-topic ("What is the capital of France?" ✗). They should sound like they belong in our library.
  - Do not reuse the same topic more than twice in your 20.
  - Leave `type`, `subfield`, `source_paper` empty for these rows.
- Examples:
  - "How does reinforcement learning from human feedback align large language models?"
  - "What makes diffusion models better than GANs for image generation?"
  - "How does BERT's masked-language-model pretraining work?"

### When you are done

- Check that all 70 rows have a question, and the 50 answerable rows have type, subfield and source paper.
- Write "done" in the team chat. The coordinator checks the sheets on Tue 20 Oct and may ask you to fix a few rows (duplicates, wrong year, unclear wording).

---

## 7. Step 2 — Pilot (Tue 20 – Wed 21 Oct)

- **Goal:** check that we all label the same way **before** the big round.
- Everyone gets the **same** sheet with about 100 rows (5 questions × ~20 passages).
- Label **alone**. Do not discuss the pilot rows with anyone until the coordinator says so.
- Columns:

  | Column | Meaning |
  | --- | --- |
  | `row_id` | Row number. Do not change. |
  | `query_id`, `question` | The question |
  | `passage_id` | The passage's id. Do not change. |
  | `paper_title`, `section`, `year` | Where the passage comes from |
  | `passage` | The passage text — read this |
  | `relevance` **(fill)** | `2`, `1` or `0` (see `guidelines.md`) |
  | `comment` | Optional: why you were unsure |

- How to label one row:
  1. Read the question. Ask yourself: "What would a good answer contain?"
  2. Read the passage.
  3. Give **2** if it contains (part of) a real answer, **1** if it is on-topic but does not answer, **0** if it does not help. Details and examples are in `guidelines.md`.
  4. Unsure between two numbers? Pick the lower one and write a short `comment`.
- Ignore odd symbols in the text such as `@xcite`, `@xmath3`, `<S>`, `</S>`. They are leftovers from the PDF conversion.
- Passages are in random order. Do not try to guess which search method found them.
- **Result (Thu 22 Oct):**
  - If we agree on ≥80% of rows → we start the main round.
  - If not → 30-minute meeting to look at the disagreements, the coordinator updates `guidelines.md`, and we do a second short pilot (Thu–Fri).

---

## 8. Step 3 — Main labeling (Thu 22 – Sun 25 Oct)

- Your sheet `3-sprint/P<your ID>` has about **1,100 rows**. Same columns and same rules as the pilot.
- You will **not** get passages for your own questions (it keeps the labels independent).
- About 15% of your rows are also labeled by someone else. You will not know which ones. **Do not compare answers with anyone.**
- Tips:
  - Work in blocks of 30–45 minutes, then take a break. Tired labeling is bad labeling.
  - Aim for about 25 seconds per row. Read the question first; often the first two lines of the passage are enough to decide **0**.
  - Rows are grouped by question, so you read each question once for ~20 passages.
  - Aim for ~300 rows per day.
- Before the deadline, check: every row has `2`, `1` or `0` in `relevance` (no blanks, no other values).

---

## 9. Step 4 — Check your unanswerable questions (Thu 22 – Sun 25 Oct)

- Your sheet `4-unanswerable-check/P<your ID>` has your 20 unanswerable questions. Each question shows the **10 passages** our system finds for it.
- For each question, fill **one** cell:
  - `answered_by_library` = `no` if **none** of the 10 passages answers it (this is what we want).
  - `answered_by_library` = `yes` if **any** passage really answers it. Then write a replacement question in `new_question` (it will be checked again).
- You also get 3 questions from other people to double-check the same way.

---

## 10. Step 5 — Gold answers (Mon 26 – Tue 27 Oct)

- Your sheet `5-gold-answers/P<your ID>` lists your 50 answerable questions.
- For each question you see the passages people marked **2**.
- Fill:
  - `gold_answer` **(fill)**: the correct answer in **one sentence** (max ~30 words), based only on those passages.
  - `gold_passages` **(fill)**: keep only the passage ids your answer really uses (the column is pre-filled with all the 2s; delete the ones you did not use).
- If no passage was marked 2, or the passages do not really answer the question, write `NO_EVIDENCE` in `gold_answer`. The coordinator will decide what to do.
- You also review about 8 gold answers written by others: mark `agree` or `disagree` (+ a short reason).

---

## 11. Step 6 — Round 2 (Tue 27 – Wed 28 Oct)

- After Subgroup B finishes the improved search (Story 1.5), it finds some passages nobody has judged yet.
- You get a short sheet (~300–500 rows) with only those new passages. Same columns, same rules as Step 3.
- Why: otherwise the improved search is punished for finding good passages that we never labeled.

---

## 12. Rules everyone must follow

- **Label alone.** Never look at someone else's labels before you finish yours.
- **Never change someone else's sheet.**
- **Never change a label after the deadline** without telling the coordinator. Changes go through the disagreement meeting.
- **Use only the three values** `2`, `1`, `0` for relevance. No `1.5`, no `?`, no blanks.
- **Unsure?** Pick the lower value and write a `comment`. Comments help us improve the rules.
- **Do not use ChatGPT or other AI tools** to label or to write gold answers. The assignment requires human labels.
- **Ask early.** A question in the team chat costs 1 minute; a misunderstanding repeated over 1,000 rows costs a day.

---

## 13. Coordinator checklist (P1 only)

- [ ] Create the "PaperPilot Labeling" Drive folder and subfolders; share with P2–P5 (edit access).
- [ ] Fill in the names in section 3.
- [ ] Upload `team-guide.md`, `guidelines.md`, `papers_catalog.csv` to `0-read-me/`.
- [ ] Create the five question sheets from `questions_template.csv`; add dropdowns for `type` and `subfield` (Data → Data validation).
- [ ] Tue 20 Oct: download the question sheets as CSV, run the question check, send fix requests.
- [ ] Generate and upload the pilot sheets; collect them; run the agreement check.
- [ ] Generate and upload the sprint and unanswerable-check sheets.
- [ ] Collect sheets at each deadline (File → Download → CSV), run the checks, commit the CSVs to `data/eval/labeling/raw/`.
- [ ] Run the disagreement meeting; record each decision in the adjudication sheet.
- [ ] Generate gold-answer sheets; collect; run the final merge and validation.
- [ ] Round 2 when Story 1.5 is ready.
- [ ] Write `agreement-report.md` and commit everything.
- The exact commands for each step are in `coordinator-commands.md` (added with the labeling tools).
