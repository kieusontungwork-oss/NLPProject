# PaperPilot labeling — coordinator commands (Story 1.6, P1 only)

This page lists every command the coordinator runs, in the order of `team-guide.md` §5–§11 and the checklist in §13.
Teammates never run code. All commands run from the repository root.

- Every command starts with: `source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli ...`
- Exit codes: **0** = ok, **1** = a sheet or a file is wrong (the message names the file and row), **3** = a stage failed (missing file, KB or index not built, refusing to overwrite).
- Defaults you normally do not change: `--kb-dir data/kb`, `--index-dir indexes`, `--eval-dir data/eval`, `--reports-dir reports`, `--config configs/ablations.yaml`. The indexes must be built first (`make index`).
- The tools are deterministic: the same inputs always give the same sheets. If `reports/` is deleted, run the same command again and you get the same files back.

---

## 0. Before you start (one time)

### Where files live

| What | Folder | Who writes it |
| --- | --- | --- |
| Sheets drafted by the tools (upload these to Drive) | `reports/pooling/<stage>/P<n>.csv` | the tools (safe to delete and regenerate) |
| Returned sheets (download from Drive, save here) | `data/eval/labeling/raw/<stage>/P<n>.csv` | people only; the tools never edit these |
| Adjudication decisions | `data/eval/labeling/adjudication.csv` | the coordinator, by hand |
| Final files | `data/eval/queries.jsonl`, `qrels.jsonl`, `qa_pairs.jsonl` | `merge` only |
| Agreement numbers | `reports/labeling/agreement_<stage>.json` | `agreement` |

- Stage names (use exactly these as folder names): `questions`, `pilot`, `round1`, `round2`, `unanswerable`, `gold`, `gold-review`.
- Annotator ids are fixed: `P1` … `P5`. The file for person `P3` is always called `P3.csv`.

### Moving CSV files in and out of Google Sheets

- **Upload:** in the Drive stage folder, File → Import → Upload → "Create new spreadsheet". In the import dialog **untick "Convert text to numbers, dates, and formulas"**. If you leave it ticked, Google mangles long ids such as `1502.0250` (becomes `1502.025`) and some passage ids (they look like scientific numbers), and then the returned sheet fails the row check.
- Rename the new sheet to the person's id (for example `P3`). Share it with that person only (edit access).
- **Download:** open the sheet → File → Download → **Comma Separated Values (.csv)**. Rename the file to `P<n>.csv` and save it in the folder from the table above.
- Do not open the CSV in Excel and save it again. Do not change anything in it by hand.

### Dropdowns (Data → Data validation)

Add these before you share a sheet. Select the column cells (rows 2 to the end), then Data → Data validation → Add rule → Criteria "Dropdown", **Reject input** for invalid data.

| Sheet | Column | Dropdown values |
| --- | --- | --- |
| Questions | `type` | `terminology-mismatch`, `exact-term`, `survey`, `comparison` (answerable rows 2–51 only) |
| Questions | `subfield` | `Machine learning & AI`, `NLP & IR`, `Computer vision`, `Information theory & signals`, `Algorithms & theory`, `Networks & social`, `Systems, security & data` (answerable rows 2–51 only) |
| Questions | `source_paper` | no dropdown: select the whole column → Format → Number → **Plain text** |
| Pilot, main labeling, round 2 | `relevance` | `0`, `1`, `2` |
| Unanswerable check | `answered_by_library` | `yes`, `no` |
| Gold-answer review | `review` | `agree`, `disagree` |

Tip: set the dropdowns once on the first sheet, then copy the sheet for the others (File → Make a copy) and replace the content.

### How two labels become one (the resolution rule)

The same rule is used by `merge`, `gold-sheets` and `validate`, for every (question, passage) pair, across all annotators who labeled it:

1. If an adjudication row exists for the pair in `adjudication.csv`, that decision is final (`adjudicated = true`).
2. Otherwise, one label only: that label.
3. All labels equal: that label.
4. A strict majority (more than half of the labels): the majority label. (In the pilot, 5 people label every row, so a majority usually decides.)
5. Anything else (a 1–1 split between two people, or a 2–2–1 split in the pilot): an **adjudication row is required**. `merge` stops (exit 1) and lists the missing pairs.

---

## 1. Kickoff — Sat 17 Oct (checklist: Drive folder, names, upload guides + catalog, create question sheets)

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli catalog
```

- Writes to `reports/labeling/kickoff/`: `papers_catalog.csv` and `questions_P1.csv` … `questions_P5.csv` (70 numbered rows each).
- **PASS:** the last line says `catalog ok: 12350 papers` followed by a count per subfield, and exit code 0.
- **FAIL:** exit 3 with `paper metadata not found` → the KB is missing; run `make kb`.
- Upload:
  - `papers_catalog.csv`, `team-guide.md`, `guidelines.md` → Drive `0-read-me/`.
  - `questions_P1.csv` … `questions_P5.csv` → Drive `1-questions/` (one sheet per person, named `P1` … `P5`).
- Add the `type` and `subfield` dropdowns and the plain-text `source_paper` format (see section 0).

## 2. Question check — Mon 19 Oct (Step 1 in the team guide)

1. In Drive `1-questions/`, download each sheet as CSV and save as `data/eval/labeling/raw/questions/P<n>.csv`.
2. Run:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli check-questions
```

- **PASS:** exit 0 and lines like `P3: 50 answerable, 20 unanswerable questions`. Lines starting with `warning:` do not block:
  - `quota: type 'survey' has 11, expected 10 (+1)` → ask the person to move one question, or accept it at the next meeting.
  - `source_paper '…' not found in papers.jsonl` → ask the person to check the id.
- **FAIL:** exit 1. Each `error:` line names the file and row (for example `raw/questions/P2.csv:9: P2-008: answerable question mentions a 2018+ year`). Typical causes:
  - empty question, no `?` at the end, missing or wrong `type` / `subfield` / `source_paper`;
  - a question that mentions a year 2018–2029 (answerable questions only);
  - `duplicate of P1-001 (…)`: two questions are almost the same (token overlap 0.80 or more), within one person or between two people;
  - `column mismatch` or `columns are reordered`: someone changed the columns. Re-export or fix the sheet header; do not edit the CSV by hand.
- Send each person the error lines for their file. Wait for the fix, download again, run again. Repeat until exit 0.
- When it passes, commit `data/eval/labeling/raw/questions/`.

## 3. Pilot — Mon 19 – Tue 20 Oct (Step 2) and the gate on Tue 20 Oct, evening (second pilot, if needed, Wed 21 Oct)

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli pilot --auto 5
```

- Picks 5 answerable questions, each from a different author and from different subfields. To choose them yourself use `pilot --questions P1-004,P2-010,P3-021,P4-033,P5-007`.
- **PASS:** `pilot ok: 5 questions (…), about 100 rows in each of 5 identical sheets`, exit 0.
- **FAIL:** exit 1 with `fix the question sheets first` → run section 2 again. Exit 3 with an index or KB message → run `make kb` / `make index`.
- Upload `reports/pooling/pilot/P1.csv` … `P5.csv` to Drive `2-pilot/` (each person gets their own copy, named with their id; the content is the same). Add the `relevance` dropdown.
- At the deadline download each sheet as CSV → `data/eval/labeling/raw/pilot/P<n>.csv`.

Then run the gate:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli agreement --stage pilot
```

- **PASS:** a table of the 10 pairs (rows, raw agreement, kappa, binary agreement), the mean, and `gate verdict: PASS` (mean raw agreement 0.80 or more). Go to section 4. The report is saved as `reports/labeling/agreement_pilot.json`.
- **Verdict FAIL (exit is still 0):** below 0.80. Hold the 30-minute meeting on the rows people disagree on (the per-annotator disagreement counts help). Write the new rules in the change log of `guidelines.md` (with the date). Then run a second pilot on 5 new questions:
  1. Move the first pilot out of the way (the tools ignore folders that are not stage names): `mv data/eval/labeling/raw/pilot data/eval/labeling/raw/pilot-1-archive` and `mv reports/pooling/pilot reports/pooling/pilot-1-archive`.
  2. Run `pilot --questions <5 new ids>` (do not use `--auto`: it would pick the same 5 again). The first pilot's questions go back into the main labeling round.
  3. Upload, collect and run `agreement --stage pilot` again.
- **FAIL (exit 1):** the message names the sheet and row. Examples:
  - `relevance '' is not one of 0, 1, 2` → that person left a cell empty or typed another value; ask them to fix it and download again.
  - `column mismatch` → a column was renamed, added or removed.
  - `row … is not in the drafted sheet` or `drafted row(s) missing` → a row was added, deleted, or its `passage_id` was edited.
  - `no annotator pair has overlapping rows` → too few sheets were saved; check `raw/pilot/`.
- A person whose sheet is missing is not a crash: their pairs are skipped with a `warning: pair … has no rows labeled by both`.
- Pilot rows where nobody wins a majority need an adjudication row (see section 6). Commit `raw/pilot/` when done.

## 4. Main labeling — Wed 21 – Fri 23 Oct (draft the sheets only after the pilot gate passes) (Step 3)

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli sheets --round 1
```

- Pool = top 10 of E1, E2 and E3 for every answerable question (pilot questions are left out). Nobody gets their own questions. 15% of the questions are given to a second person. The sheets are balanced across P1–P5.
- **PASS:** a line with the number of questions, double-labeled questions and rows, then one line per person (`P3: 57 questions, 577 rows`), then `wrote 5 sheets -> reports/pooling/round1`. Exit 0.
- **FAIL:** exit 1 with `load imbalance (> 5% from the mean)`: nothing is written. This should not happen; send the output to the owner instead of editing anything.
- Upload `reports/pooling/round1/P<n>.csv` to Drive `3-sprint/`. Add the `relevance` dropdown.
- At the deadline: download each sheet as CSV → `data/eval/labeling/raw/round1/P<n>.csv`.
- Check them:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli validate
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli agreement --stage round1
```

- `validate` PASS: `validate ok`. FAIL messages are the same kinds as in section 3, each with `file:row`; send them to the person. A `warning: N pair(s) need an adjudication row` is expected at this point (section 6).
- `agreement --stage round1` compares only the rows labeled by two people. Report it, same table and gate verdict as the pilot.
- Commit `raw/round1/` when done.

## 5. Unanswerable check — Tue 20 – Wed 21 Oct (Step 4)

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli unanswerable-sheets
```

- Each person gets their own 20 questions plus 3 questions of other people, each with the top 10 E3 passages in one cell.
- **PASS:** `unanswerable-sheets ok: rows per sheet P1=23, …`, exit 0. **FAIL:** exit 1 → fix the question sheets (section 2).
- Upload `reports/pooling/unanswerable/P<n>.csv` to Drive `4-unanswerable-check/`. Add the `answered_by_library` dropdown.
- At the deadline: download as CSV → `data/eval/labeling/raw/unanswerable/P<n>.csv`.
- Check:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli validate
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli agreement --stage unanswerable
```

- `validate` prints `unanswerable slice: N of 100 questions survive`, and one `warning:` per `yes` answer (with the replacement the author proposed).
- **Replacing a `yes` question (for example `P3-U05`):**
  1. Open `data/eval/labeling/raw/questions/P3.csv` and add one new row by hand: `query_id` = the next free id (`P3-U21`, then `P3-U22`, …), `question` = the `new_question` text. This is the only manual edit allowed in `raw/`. Mention it in the commit message. Run `check-questions` again.
  2. Run `unanswerable-sheets --only P3-U21` and send `reports/pooling/unanswerable/replacements/P3.csv` to P3 (several ids: `--only P3-U21,P4-U21`).
  3. When P3 answers, run `unanswerable-sheets` once more (the full sheet now includes `P3-U21`) and paste the answered row(s) at the bottom of `raw/unanswerable/P3.csv`, so that the file again matches `reports/pooling/unanswerable/P3.csv`.
  4. A replacement question joins the slice when its answer is `no`. Until then it is listed as `not yet checked` and the slice count stays below 100.
- If the author says `no` and the double-checker says `yes` (or the reverse), you need an adjudication row for it (section 6, key `UNANSWERABLE`).

## 6. Disagreement meeting and adjudication — Sat 24 Oct (weekly meeting)

- List what is open:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli validate
```

- The warning `N pair(s) need an adjudication row in adjudication.csv: (P1-007, 37b6…), …` lists every pair that two or more people labeled without a majority. The warning about `UNANSWERABLE` lists the unanswerable questions with disagreeing answers.
- In the meeting, each person says their label and a one-sentence reason; a third person (not one of the two labelers) decides.
- Record each decision as one row in `data/eval/labeling/adjudication.csv` (UTF-8 CSV, this exact header):

```
query_id,chunk_id,final_relevance,adjudicator,reason
P1-007,37b60e50d6739d5d,1,P4,"related but does not answer"
P3-U05,UNANSWERABLE,no,P2,"no passage answers it"
```

- `final_relevance` is `0`, `1` or `2` for passages, and `yes` or `no` for rows with `chunk_id` = `UNANSWERABLE` (the final value of `answered_by_library`).
- Run `validate` again until the adjudication warnings are gone. Commit `adjudication.csv`.
- Mistakes are reported with `file:row` (`final_relevance '3'`, `adjudicator 'P9'`, `duplicate adjudication`).

## 7. Gold answers — Sat 24 – Sun 25 Oct 12:00; review sheets out Sun afternoon, back by Mon 26 Oct 09:00 (Step 5)

Gold sheets need the round-1 labels to be complete (no adjudication row missing). If one is missing the command stops with exit 1 and lists the pairs.

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli gold-sheets
```

- **PASS:** `gold-sheets gold ok: rows per sheet P1=50, …`. Upload `reports/pooling/gold/P<n>.csv` to Drive `5-gold-answers/`.
- At the deadline: download as CSV → `data/eval/labeling/raw/gold/P<n>.csv`, then run `validate`. FAIL examples:
  - `gold_answer is empty` → ask the author to write an answer or `NO_EVIDENCE`;
  - `gold_passages not labeled 2 for this question: [...]` → the author listed a passage that is not a 2;
  - `gold_passages is empty` → a real answer needs at least one passage.
- `NO_EVIDENCE` is allowed. These questions are kept out of `qa_pairs.jsonl`; `validate` and `merge` list them for you. Decide with the owner what to do with them (for example write a better question).

Then the reviews (each person gets about 8 answers written by others):

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli gold-sheets --review
```

- Upload `reports/pooling/gold-review/P<n>.csv` to Drive `5-gold-answers/` (a second sheet per person). Add the `review` dropdown. Collect → `data/eval/labeling/raw/gold-review/P<n>.csv`.
- Run `agreement --stage gold-review` (reviewer against the answer's author) and `validate`. Every `disagree` is listed as a warning with its reason: settle them in a short meeting and, if needed, ask the author to update the gold sheet (download and save again).
- Commit `raw/gold/` and `raw/gold-review/`.

## 8. Round 2 — Sat 24 – Sun 25 Oct (Step 6, needs Story 1.5)

Save the round-1 and pilot sheets in `raw/` first (the command reads them). Then, with the config rows from Story 1.5 (names as in `configs/ablations.yaml`):

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli sheets --round 2 --rows E4,E5a
```

- Only (question, passage) pairs without a pilot or round-1 judgment are drafted, from the top 10 of the rows you name.
- **PASS:** the same summary as round 1, `wrote 5 sheets -> reports/pooling/round2`. If every passage is already judged: `nothing to draft`, and no files.
- **FAIL:** exit 3 with `unknown config row` (check the ids in `configs/ablations.yaml`), `--rows` missing, or `no returned … sheets` (save the earlier sheets first).
- Upload `reports/pooling/round2/P<n>.csv` to Drive `6-round2/`. Collect → `data/eval/labeling/raw/round2/P<n>.csv`. Check with `validate` and `agreement --stage round2`. Commit `raw/round2/`.

## 9. Final merge — Mon 26 Oct

1. Check everything is in place:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli validate --final
```

- **PASS:** `validate ok (final)`. It also prints `labeled rows: N qrels + M QA = T (floor 1250)`.
- **FAIL (exit 1):** a required stage has no returned sheets, an adjudication row is missing, a chunk id is no longer in `chunks.jsonl` (the KB was rebuilt after labeling: tell the owner, do not edit the CSVs), or the total is below 1,250.

2. Write the three files:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli merge
```

- `merge` runs the same checks first and writes `data/eval/queries.jsonl`, `qrels.jsonl` and `qa_pairs.jsonl` only if they pass. It prints the counts, the unanswerable slice size (target 100; the 40 dev / 60 held-out split is made automatically, by author) and the `NO_EVIDENCE` list.
- **FAIL:** exit 1 names `file:row` or lists missing adjudication pairs, nothing is written. Exit 3 with `refusing to overwrite … pass --replace`: the files already exist. Only use `--replace` when you really want to regenerate them (ask the owner first):

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling.cli merge --replace
```

3. Commit and push: `data/eval/labeling/raw/` (all stages), `data/eval/labeling/adjudication.csv`, `data/eval/queries.jsonl`, `data/eval/qrels.jsonl`, `data/eval/qa_pairs.jsonl`, and the guides (with the change log). `reports/` is not committed: copy the agreement numbers into `agreement-report.md` first.

4. Fill in `data/eval/labeling/agreement-report.md` from the printed tables and the JSON files in `reports/labeling/` (pilot, round 1, round 2, unanswerable, gold review: mean raw agreement, kappa, binary agreement, gate verdict, and what you changed in the guidelines).

## 10. Quick reference

| Step | Command | Upload (Drive) | Save returned CSV in |
| --- | --- | --- | --- |
| Kickoff | `catalog` | `0-read-me/`, `1-questions/` | — |
| Question check | `check-questions` | — | `raw/questions/` |
| Pilot | `pilot --auto 5`, then `agreement --stage pilot` | `2-pilot/` | `raw/pilot/` |
| Main labeling | `sheets --round 1`, then `validate`, `agreement --stage round1` | `3-sprint/` | `raw/round1/` |
| Unanswerable | `unanswerable-sheets`, then `validate`, `agreement --stage unanswerable` | `4-unanswerable-check/` | `raw/unanswerable/` |
| Adjudication | write `adjudication.csv`, then `validate` | — | — |
| Gold answers | `gold-sheets`, then `gold-sheets --review`, `agreement --stage gold-review` | `5-gold-answers/` | `raw/gold/`, `raw/gold-review/` |
| Round 2 | `sheets --round 2 --rows <ids>`, then `agreement --stage round2` | `6-round2/` | `raw/round2/` |
| Final | `validate --final`, then `merge` | — | — |

(All paths in the last column are under `data/eval/labeling/`; drafted sheets are under `reports/pooling/<stage>/`.)
