**Project Proposal: PaperPilot**

**A Retrieval-Augmented AI Research Assistant**

**1. Project Overview**

**PaperPilot** is a Retrieval-Augmented Generation (RAG) system designed to help users **search, understand, and synthesize information from a large collection of AI/ML/NLP research papers**.

Instead of relying solely on an LLM's internal knowledge, PaperPilot will first retrieve relevant evidence from a large research-paper corpus and then generate an answer grounded in those sources.

**Example**

**User query:**

*“What are the main approaches used to reduce hallucination in RAG systems?”*

PaperPilot would:

1. Search thousands of research papers.
2. Retrieve the most relevant passages.
3. Combine different retrieval approaches to improve results.
4. Re-rank the retrieved passages.
5. Generate an answer based on the retrieved evidence.
6. Show the papers/passages supporting the answer.

**2. Motivation**

Finding useful information in research literature is difficult because:

* There are thousands of papers on similar topics.
* Different papers use different terminology for the same concepts.
* Keyword search can miss semantically relevant papers.
* Pure semantic search can sometimes miss exact technical terms.
* LLMs can generate plausible but unsupported information.

PaperPilot aims to combine **traditional information retrieval + neural retrieval + generation** to provide answers that are both useful and evidence-grounded.

**3. Main Objective**

Build and evaluate a RAG pipeline that can:

**Retrieve relevant scientific evidence from a large research corpus and generate accurate, grounded answers to natural-language research questions.**

The project will specifically investigate whether combining different retrieval techniques can improve the quality of the final answers.

**4. Proposed System**

At a high level:

User Query

│

▼

Query Processing

│

┌───────┴───────┐

▼ ▼

BM25 Search Dense Search

│ │

└───────┬───────┘

▼

Hybrid Retrieval

│

▼

Re-ranking

│

▼

Relevant Passages

│

▼

LLM / Generator

│

▼

┌──────────┴──────────┐

▼ ▼

Final Answer Citations

The system will therefore have three major components corresponding closely to the assignment:

**1. Knowledge Base**

A large collection of AI/ML/NLP research papers.

**2. Retrieval**

Multiple retrieval approaches, including:

* **Sparse retrieval:** BM25
* **Dense retrieval:** neural embeddings
* **Hybrid retrieval:** combination of sparse + dense results
* **Re-ranking:** improve ordering of retrieved passages

**3. Generation**

An LLM will use the retrieved passages as context to generate an answer.

**5. Dataset / Knowledge Base**

We plan to build a corpus of **at least 10,000 research papers**, comfortably exceeding the assignment requirement.

Possible sources include publicly available research papers and datasets covering areas such as:

* Natural Language Processing
* Large Language Models
* Retrieval-Augmented Generation
* Computer Vision
* Generative AI
* Machine Learning
* Deep Learning

Each paper will be processed into smaller passages/chunks so that the retrieval system can search at the passage level.

We will also retain useful metadata such as:

* Paper title
* Authors
* Publication year
* Abstract
* Section
* Source/link

**6. Retrieval Approach**

One of the main focuses of the project will be comparing different retrieval strategies.

**Baseline 1 — BM25**

Traditional keyword-based retrieval.

Useful for queries containing specific technical terms.

**Baseline 2 — Dense Retrieval**

Represent queries and passages as embeddings and retrieve semantically similar passages.

Useful when the query and relevant document use different terminology.

**Proposed Hybrid Retrieval**

Combine BM25 and dense retrieval to take advantage of both approaches.

For example:

Query: *“How can language models generate unsupported information?”*

Keyword retrieval may focus on papers containing **“hallucination”**, while dense retrieval may find papers discussing the same concept using different terminology.

**7. Potential Improvements**

After establishing the baseline, we can experiment with improvements such as:

**Re-ranking**

Retrieve a larger set of candidates and use a neural re-ranker to identify the most relevant passages.

**Query Rewriting**

Transform the user's query into a form that is better suited for retrieval.

For example:

**Original:**
“How do we reduce hallucinations in RAG?”

→

**Expanded:**
“Methods for reducing factual hallucination and improving grounding in retrieval-augmented generation systems.”

**Section-aware Retrieval**

Give greater importance to relevant sections such as:

* Abstract
* Methodology
* Experiments
* Results
* Conclusion

rather than treating every part of a paper equally.

These improvements can be evaluated individually to determine which actually contribute to better retrieval.

**8. Downstream Task**

The primary task will be **research question answering**.

Users can ask questions about the research corpus and receive answers based on retrieved evidence.

Example:

**Question:**
“What are the advantages of LoRA compared with full fine-tuning?”

**Output**

**Answer:**
A concise explanation generated using retrieved research evidence.

**Sources:**

* Paper A
* Paper B
* Paper C

**Supporting passages:**

Relevant excerpts from the retrieved papers.

This makes the system more transparent than a standard chatbot.

**9. Evaluation**

We will evaluate both **retrieval quality** and **answer quality**.

**Retrieval metrics**

Potential metrics include:

* Recall@K
* Precision@K
* MRR
* nDCG

These will tell us whether the system is actually finding the relevant evidence.

**Generation / RAG metrics**

We can evaluate:

* Answer relevance
* Faithfulness
* Context relevance
* Exact Match / F1 where appropriate

We also plan to create a manually evaluated benchmark of research questions and relevant evidence for testing the system.

**10. Key Experiments**

A major part of the project will be an **ablation study**, comparing progressively stronger systems.

For example:

Experiment 1

BM25

↓

Experiment 2

Dense Retrieval

↓

Experiment 3

BM25 + Dense Retrieval

↓

Experiment 4

Hybrid + Re-ranking

↓

Experiment 5

Hybrid + Re-ranking + Query Rewriting

↓

Experiment 6

Final Proposed System

This allows us to answer an important question:

**Which techniques actually improve the system, and by how much?**

Rather than simply building a RAG system, we can demonstrate measurable improvements at each stage.

**11. User Interface**

A simple web-based interface will be developed, potentially using **Streamlit**.

The interface would allow users to:

* Enter a research question
* View the generated answer
* See retrieved papers
* View supporting passages
* Follow source links
* Potentially inspect retrieval results

The UI will intentionally remain simple because the primary focus of the project is **retrieval and generation**, rather than frontend development.

**12. Contribution**

The project aims to demonstrate that:

**Combining lexical retrieval, semantic retrieval, and neural re-ranking can provide more reliable evidence for research-oriented question answering than using a single retrieval method.**

We also hope to identify **which retrieval improvements are most useful for different types of research queries**.

**13. Proposed Tech Stack**

At a high level:

| **Component** | **Possible Technology** |
| --- | --- |
| Data processing | Python |
| Paper processing | PyMuPDF / similar |
| Sparse retrieval | BM25 |
| Dense retrieval | Sentence Transformers |
| Vector search | FAISS |
| Re-ranking | Cross-encoder |
| Generation | Hugging Face / local LLM / API |
| Evaluation | RAGAS + retrieval metrics |
| UI | Streamlit |

![](data:image/png;base64...)