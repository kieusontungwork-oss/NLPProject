# PaperPilot labeling — rules and examples (Story 1.6)

Keep this page open while you label. The team guide (`team-guide.md`) says *when* and *where*; this page says *how to decide*.

---

## 1. The relevance scale (for every passage you judge)

Ask one question: **"If I were writing the answer, would I use this passage?"**

| Label | Name | Give it when… | Do NOT give it when… |
| --- | --- | --- | --- |
| **2** | Answers | The passage states (part of) a real answer to the question. You could quote it in your answer. | It only mentions the topic, or only says "X is important". |
| **1** | Related | The passage is about the same topic and helps a little (background, definition, a related method), but it does **not** answer the question. | It is about a different topic that shares a word. |
| **0** | Not relevant | The passage does not help answer the question at all, even if it repeats some of the question's words. | — |

- A passage does **not** need to answer the *whole* question to get **2**. One real part of the answer is enough.
- Judge the **passage text only**. Do not use the paper title alone, and do not use what you know from outside the passage.
- Unsure between two labels? **Pick the lower one** and write a short `comment`.

---

## 2. Tricky cases

- **Abstracts.** Judge them like any other passage. An abstract that says *how* or *why* → can be 2. An abstract that only says "we study X" → usually 1.
- **Survey or related-work passages.** If they explain the answer (even briefly) → 2. If they only list papers ("X was studied in [3, 5, 7]") → 1.
- **Same words, different meaning.** "Attention" in psychology, "network" in power grids when the question is about neural networks, "channel" in a CNN vs a wireless channel → **0**.
- **Numbers and tables.** A passage with only results (accuracy, tables) and no explanation → usually 1. If the question asks "how well does X work" and the passage gives that result → 2.
- **The same text appears twice** (two passages from the same or different papers say the same thing) → give both the same label.
- **Very short or broken passages** (mostly symbols like `@xmath12`) → 0, unless the readable part answers the question.
- **Odd symbols** `@xcite`, `@xmath3`: ignore them. They stand for citations and formulas removed when the papers were converted to text.
- **The passage answers a different question** on the same topic → 1.
- **The passage disagrees with the expected answer** but discusses it directly (e.g. "dropout did not help in our case because…") → 2. It is still evidence.

---

## 3. Ten worked examples (real passages from our library)

Examples 1–7 are passage judgments, 8–9 are unanswerable checks, 10 is a gold answer.

### Question A — "What is dropout and why does it reduce overfitting?"

- **Example 1** — *Efficient batchwise dropout training using submatrices* (2015), section "independent versus batchwise dropout":
  > "dropout is a technique to regularize artificial neural networks it prevents overfitting. a fully connected network with two hidden layers of 80 units each can learn to classify the mnist training set perfectly in about 20 training epochs unfortunately the test error is quite high…"
  - **Label: 2.** It says what dropout is (a regularization technique) and that it prevents overfitting, with an example of the overfitting problem.
- **Example 2** — same paper, abstract:
  > "dropout is a popular technique for regularizing artificial neural networks. dropout networks are generally trained by minibatch gradient descent with a dropout mask turning off some of the units…"
  - **Label: 2.** "turning off some of the units" explains what dropout does. Part of an answer is enough.
- **Example 3** — *No bad local minima…* (2016), discussion:
  > "without data augmentation or dropout, alexnet did exhibit severe overfitting. our analysis is non-asymptotic…"
  - **Label: 1.** It links dropout and overfitting, but does not explain what dropout is or why it helps. (A **1 vs 2 boundary case**: if you are unsure, choose 1.)
- **Example 4** — *Deep Learning in Customer Churn Prediction…* (2017), related work:
  > "…additionally to these regularization techniques, an early stopping mechanic can be implemented within a backpropagation algorithm…"
  - **Label: 0.** It is about early stopping, a different technique. Sharing the word "regularization" is not enough.

### Question B — "How does attention help neural machine translation?"

- **Example 5** — *Video Paragraph Captioning Using Hierarchical RNNs* (2015), related work:
  > "neural machine translation. the methods for nmt generally follow the encoder-decoder paradigm. an encoder maps the source sentence to a fixed-length feature vector in the embedding space. a decoder then conditions on this vector to generate a translated sentence…"
  - **Label: 1.** It explains the encoder–decoder setup (useful background) but does not say what attention adds.
- **Example 6** — *Can Active Memory Replace Attention?* (2016), abstract:
  > "several mechanisms to focus attention of a neural network on selected parts of its input or memory have been used successfully… attention has improved image classification, image captioning, speech recognition…"
  - **Label: 2.** "focus… on selected parts of its input" is the core of the answer (the decoder looks at the relevant source words), and it states that attention improved results.
- **Example 7** — *Can Active Memory Replace Attention?* (2016), introduction:
  > "…it by definition tries to focus on a single element of the memory it is attending to. in the extreme case, also known as hard attention, one of the memory elements is selected…"
  - **Label: 1.** It describes how attention works in general, but not how it helps translation. (If you think "focusing on one element" already answers *how*, write a comment — this is exactly the kind of case we discuss in the pilot meeting.)

### Example 8 — an unanswerable question: "How does reinforcement learning from human feedback (RLHF) align large language models?"

- The system's top passages are about "spin glass models of syntax", "word-to-word translation models" (1998) and "the One Billion Word benchmark" (2013).
- None of them is about RLHF or aligning language models with human feedback (RLHF is a 2020s topic; our library ends in 2017).
- **Check result:** `answered_by_library = no`. This is a good unanswerable question.

### Example 9 — a question that looks unanswerable but is not: "How does a neural network decide which input words to focus on when translating?"

- This is about attention in translation (2014–2016 work), which our library contains (see Question B).
- **Check result:** `answered_by_library = yes`, so replace it with a real post-2017 topic.


### Example 10 — a gold answer (Step 5)

- Question A again: "What is dropout and why does it reduce overfitting?"
- Passages marked 2: Examples 1 and 2.
- **Good gold answer:** "Dropout regularizes a neural network by randomly turning off units during training, which prevents the network from overfitting the training data." (one sentence, uses only what Examples 1–2 say)
- `gold_passages`: the ids of Examples 1 and 2.
- **Bad gold answers:**
  - "Dropout, introduced by Srivastava et al. in 2014, randomly drops units with probability p = 0.5 …" ✗ (adds facts that are not in the passages)
  - "According to the paper, it helps." ✗ (does not answer)
- If no passage for a question was marked 2 → write `NO_EVIDENCE`.

---

## 4. Question-writing rules (Step 1)

### Answerable questions

- One sentence, ends with `?`, asked like a real researcher would ask it.
- Topic from **2017 or earlier**; the answer fits in one or two sentences.
- No year of 2018 or later in the question.
- No yes/no questions. No questions about one paper's exact numbers. Do not copy paper titles.
- No near-duplicates: if your question is the same as another one with a few words changed, it is a duplicate (the check flags questions that share 80% or more of their words).
- Types: `terminology-mismatch`, `exact-term`, `survey`, `comparison` (definitions and examples are in `team-guide.md` §6).
- Subfields: `Machine learning & AI`, `NLP & IR`, `Computer vision`, `Information theory & signals`, `Algorithms & theory`, `Networks & social`, `Systems, security & data`.

### Unanswerable questions (how to build them)

- **Goal:** a question that sounds like it belongs in our library, but that no passage can answer. The system should then say "not enough evidence" instead of inventing an answer.
- **Pick a topic from 2018 or later.** Good sources: BERT, GPT-2/3/4, ChatGPT, RLHF, instruction tuning, prompt engineering, retrieval-augmented generation, diffusion models, vision transformers, CLIP, SimCLR/MAE, 5G/6G deployment, COVID-19 apps.
- **Make it look normal.** Same style as an answerable question: one sentence, a real research question, about computer science.
- **Check the catalog.** Search (Ctrl+F) the paper catalog for the topic's key words. If any paper is about the topic, choose another topic.
- **Avoid giveaways.** Do not write "in 2023" or "recently released"; the topic itself should be what makes it unanswerable.
- **No silly or off-topic questions** ("What is the capital of France?" ✗).
- **Variety:** use at most two questions per topic in your 20, and spread them over different subfields.
- **No near-duplicates** of anyone's questions, answerable or not.
- **Step 4 checks each one:** you see the 10 passages the system finds; if any of them answers the question, you replace it (Examples 8 and 9).

## 5. Gold-answer rules (Step 5)

- **One sentence**, at most ~30 words.
- Based **only** on passages marked 2 for that question. Do not add facts from outside the library.
- Write in your own words, but keep key technical terms from the passages (so automatic scoring can match them).
- Answer the question directly. Start with the answer, not with "According to the paper…".
- Keep in `gold_passages` only the passage ids your sentence actually uses.
- If the 2-passages do not really answer the question → write `NO_EVIDENCE`.
- Example:
  - Question: "What is dropout and why does it reduce overfitting?"
  - Gold answer: "Dropout regularizes a neural network by randomly turning off units during training, which prevents the network from overfitting the training data."
  - Gold passages: Examples 1 and 2 (the two passages marked 2 for Question A).

---

## 6. Reviewing someone else's item

- **Double-labeled passages**: you label them like any other row. You will not know which rows are double-labeled.
- **Gold-answer review**: `agree` if the sentence is correct, one sentence, and supported by the listed passages; otherwise `disagree` + a short reason.
- **Disagreement meeting**: for each disagreement, each person says their label and reason in one sentence; the adjudicator (a third person) decides; the coordinator records it. If the same kind of disagreement keeps coming up, we add a rule to this page.

---

## 7. Change log

Every rule change after the pilot is written here with the date, so everyone labels by the same rules.

- 2026-10-17: first version.
