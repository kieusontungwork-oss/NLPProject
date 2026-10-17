# PaperPilot labeling — coordinator commands (Story 1.6, P1 only)

This page lists every command the coordinator runs, in the order of `team-guide.md` §5–§11 and the checklist in §13.
Teammates never run code. All commands run from the repository root.

- Every command starts with: `source .venv/bin/activate && python -m paperpilot.evaluation.labeling <subcommand> ...`
- Exit codes: **0** = ok, **1** = a sheet or a file is wrong (the message names the file and row), **3** = a stage failed (missing file, KB or index not built, refusing to overwrite).
- Defaults you normally do not change: `--kb-dir data/kb`, `--index-dir indexes`, `--eval-dir data/eval`, `--reports-dir reports`, `--config configs/ablations.yaml`. The indexes must be built first (`make index`).
- The tools are deterministic: the same inputs always give the same sheets.
- Messages are capped at 10 lines per file, followed by `... and N more`. Fix the first ones and run again.

---

## 0. Before you start (one time)

### The one rule about `raw/`

- **The tools never edit anything in `data/eval/labeling/raw/`.** You only save the CSV files that people return (downloaded from Drive) into it.
- There is **one** manual exception: when a question needs a replacement (section 5), you append the replacement question as a new row at the bottom of `raw/questions/P<n>.csv`. Mention it in the commit message.
- Never paste rows from one returned file into another.

### Where files live

| What | Folder | Who writes it |
| --- | --- | --- |
| Sheets drafted by the tools (upload these to Drive) | `reports/pooling/<stage>/P<n>.csv` | the tools |
| Returned sheets (download from Drive, save here) | `data/eval/labeling/raw/<stage>/P<n>.csv` | people only; you only save the downloads |
| Adjudication decisions | `data/eval/labeling/adjudication.csv` | the coordinator, by hand |
| Final files | `data/eval/queries.jsonl`, `qrels.jsonl`, `qa_pairs.jsonl` | `merge` only |
| Agreement numbers | `reports/labeling/agreement_<stage>.json` | `agreement` |
| Merge summary (fills `agreement-report.md`) | `reports/labeling/merge_summary.json` | `merge` |

- Stage names (use exactly these as folder names): `questions`, `pilot`, `round1`, `round2`, `unanswerable`, `gold`, `gold-review`.
- Annotator ids are fixed: `P1` … `P4`. The file for person `P3` must be called exactly `P3.csv`. Any other `.csv` in a stage folder (for example `Copy of P3.csv`) is ignored and reported as `warning: ignored ...`.
- Do not delete `reports/pooling/`: the returned sheets are checked against the drafted ones. If it is lost, run the same drafting command again (it gives the same sheets), with `--force`.

### Do not re-draft a stage once sheets came back

Drafting commands (`pilot`, `sheets`, `unanswerable-sheets`, `gold-sheets`) **refuse** (exit 3) to overwrite the drafted sheets of a stage when `raw/<stage>/` already holds returned sheets, because those sheets are checked against the drafts.

- `--force` overrides this. **Warning:** only use `--force` when you are sure; if the new draft differs from the old one, every returned sheet of that stage will fail the row check.
- The usual reasons for `--force`: the `reports/` folder was deleted and you need to regenerate it, or you deliberately start a stage again after moving the old returned sheets away.

### Moving CSV files in and out of Google Sheets

- **Upload:** in the Drive stage folder, File → Import → Upload → "Create new spreadsheet". In the import dialog **untick "Convert text to numbers, dates, and formulas"**. If you leave it ticked, Google mangles long ids such as `1502.0250` (becomes `1502.025`) and some passage ids (they look like scientific numbers), and the returned sheet fails the row check. The tools then say: `Google Sheets probably converted this id to a number — re-import with 'Convert text to numbers' unticked`.
- Rename the new sheet to the person's id (for example `P3`). Share it with that person only (edit access).
- **Download:** open the sheet → File → Download → **Comma Separated Values (.csv)**. Rename the file to `P<n>.csv` and save it in the folder from the table above.
- Do not open the CSV in Excel and save it again. Do not change anything in it by hand. (An extra empty column at the end, as some exports add, is harmless.)

### Dropdowns (Data → Data validation)

Add these before you share a sheet. Select the column cells (rows 2 to the end), then Data → Data validation → Add rule → Criteria "Dropdown", **Reject input** for invalid data.

- Enter the options **one per line, using "Add another item" for each one**. Do not paste them as one comma-separated text: the subfield `Systems, security & data` contains a comma and would be split into two options.

| Sheet | Column | Dropdown items (one each) |
| --- | --- | --- |
| Questions | `type` | `terminology-mismatch`, `exact-term`, `survey`, `comparison` (answerable rows 2–51 only) |
| Questions | `subfield` | `Machine learning & AI`; `NLP & IR`; `Computer vision`; `Information theory & signals`; `Algorithms & theory`; `Networks & social`; `Systems, security & data` (answerable rows 2–51 only) |
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
4. A strict majority (more than half of the labels): the majority label. (In the pilot, 4 people label every row, so a majority usually decides.)
5. Anything else (a 1–1 split between two people, or a 2–2–1 split in the pilot): an **adjudication row is required**. `merge` stops (exit 1) and lists the missing pairs.

---

## 1. Kickoff — Sat 17 Oct (checklist: Drive folder, names, upload guides + catalog, create question sheets)

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling catalog
```

- Writes to `reports/labeling/kickoff/`: `papers_catalog.csv` and `questions_P1.csv` … `questions_P4.csv` (70 numbered rows each).
- **PASS (exit 0):** the first line says `catalog ok: 12350 papers -> reports/labeling/kickoff`, then one line per subfield with its paper count, and the last line says `wrote questions_P1.csv .. questions_P4.csv (70 rows each)`.
- **FAIL:** exit 3 with `paper metadata not found` → the KB is missing; run `make kb`.
- Upload:
  - `papers_catalog.csv`, `team-guide.md`, `guidelines.md` → Drive `0-read-me/`.
  - `questions_P1.csv` … `questions_P4.csv` → Drive `1-questions/` (one sheet per person, named `P1` … `P4`).
- Add the `type` and `subfield` dropdowns and the plain-text `source_paper` format (see section 0).

## 2. Question check — Mon 19 Oct (Step 1 in the team guide)

1. In Drive `1-questions/`, download each sheet as CSV and save as `data/eval/labeling/raw/questions/P<n>.csv`.
2. Run:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling check-questions
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

## 3. Pilot — Mon 19 – Tue 20 Oct (Step 2) and the gate on Tue 20 Oct, evening

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling pilot --auto 4
```

- Picks 4 answerable questions (`--auto N` accepts 1 to 4), each from a different author and from different subfields. To choose them yourself use `pilot --questions P1-004,P2-010,P3-021,P4-033`.
- **PASS:** `pilot ok: 4 questions (…), about 80 rows in each of 4 identical sheets`, exit 0.
- **FAIL:** exit 1 with `fix the question sheets first` → run section 2 again. Exit 3 with an index or KB message → run `make kb` / `make index`.
- Upload `reports/pooling/pilot/P1.csv` … `P4.csv` to Drive `2-pilot/` (each person gets their own copy, named with their id; the content is the same). Add the `relevance` dropdown.
- At the deadline download each sheet as CSV → `data/eval/labeling/raw/pilot/P<n>.csv`.

Then run the gate:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling agreement --stage pilot
```

- You get a table of the pairs (rows `n`, raw agreement, kappa, binary agreement), the mean, the **pooled** raw agreement over all double-labeled rows, and the verdict. Pairs with fewer than 10 rows are marked `small`; a kappa of `n/a` means one person used a single label for all shared rows (kappa cannot be computed). The report is saved as `reports/labeling/agreement_pilot.json`.
- **PASS:** `gate verdict: PASS` (the **mean pairwise raw agreement** is 0.80 or more; the pooled value is printed next to it for information). Go to section 4 (main labeling).
- **Verdict FAIL (exit is still 0):** below 0.80. Hold the 30-minute meeting on the rows people disagree on (the per-annotator disagreement counts help). Write the new rules in the change log of `guidelines.md` (with the date). Then run a second pilot on Wed 21 Oct, **before round 1 is drafted** (round 1 is only drafted after the gate passes):
  1. Move the first pilot out of the way (the tools ignore folders that are not stage names): `mv data/eval/labeling/raw/pilot data/eval/labeling/raw/pilot-1-archive` and `mv reports/pooling/pilot reports/pooling/pilot-1-archive`.
  2. Run `pilot --questions <5 new ids>` (do not use `--auto`: it would pick the same 5 again).
  3. Upload, collect and run `agreement --stage pilot` again.
  - The first pilot's labels are **not used**: they were given under the old rules, and the tools cannot merge two pilots into one stage. Its 5 questions are not pilot questions any more, so they are simply labeled in round 1 like all others. Keep the archive folders in Git as evidence.
- **FAIL (exit 1):** the message names the sheet and row. Examples:
  - `relevance '' is not one of 0, 1, 2` → that person left a cell empty or typed another value; ask them to fix it and download again.
  - `column mismatch` → a column was renamed, added or removed.
  - `row … is not in the drafted sheet` or `drafted row(s) missing` → a row was added, deleted, or its `passage_id` was edited.
  - `the row content changed (passage differs from the drafted sheet) — was a single column sorted?` → someone sorted or filtered one column; the labels no longer sit next to their passages. Ask them to start again from the drafted sheet.
  - `no annotator pair has overlapping rows` → too few sheets were saved; check `raw/pilot/`.
- A person whose sheet is missing is not a crash: their pairs are skipped with a `warning: pair … has no rows labeled by both`.
- Pilot rows where nobody wins a majority need an adjudication row (see section 6). Commit `raw/pilot/` when done.

## 4. Main labeling — Wed 21 – Fri 23 Oct (Step 3), drafted only after the pilot passes

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling sheets --round 1
```

- It refuses (exit 1) unless the pilot is drafted and **every** returned pilot sheet is in `raw/pilot/`.
- Pool = top 10 of E1, E2 and E3 for every answerable question (pilot questions are left out). Nobody gets their own questions. 15% of the questions are given to a second person. The sheets are balanced across P1–P4.
- **PASS:** a line with the number of questions, double-labeled questions and rows, then one line per person (`P3: 57 questions, 577 rows`), then `wrote 4 sheets -> reports/pooling/round1`. Exit 0.
- **FAIL:** exit 1 with `load imbalance (> 5% from the mean)`: nothing is written. This should not happen; send the output to the owner instead of editing anything.
- Upload `reports/pooling/round1/P<n>.csv` to Drive `3-sprint/`. Add the `relevance` dropdown.
- At the deadline: download each sheet as CSV → `data/eval/labeling/raw/round1/P<n>.csv`.
- Check them:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling validate
source .venv/bin/activate && python -m paperpilot.evaluation.labeling agreement --stage round1
```

- `validate` PASS: `validate ok`. FAIL messages are the same kinds as in section 3, each with `file:row`; send them to the person. Expected `warning:` lines at this point: `N pair(s) need an adjudication row` (section 6) and, if someone edited a question after pooling, `question text on returned sheets differs from the current question for: …` (check that the sheet still matches the intended question).
- `validate` also warns when an answerable question has no resolved judgment at all, or no passage labeled 1 or 2. The first becomes an error in the final check (section 9).
- `agreement --stage round1` compares only the rows labeled by two people (about 15% of the questions). Same table and verdict as the pilot.
- Commit `raw/round1/` when done.

## 5. Unanswerable check — Tue 20 – Wed 21 Oct (Step 4; it does not depend on the pilot)

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling unanswerable-sheets
```

- Each person gets their own 20 questions plus 3 questions of other people, each with the top 10 E3 passages in one cell (each passage is shown cut to 2,000 characters, and a cell to 45,000, to stay under Google Sheets' cell limit; the sheet is only for reading).
- **PASS:** `unanswerable-sheets ok: rows per sheet P1=23, …`, exit 0. **FAIL:** exit 1 → fix the question sheets (section 2).
- Upload `reports/pooling/unanswerable/P<n>.csv` to Drive `4-unanswerable-check/`. Add the `answered_by_library` dropdown.
- At the deadline: download as CSV → `data/eval/labeling/raw/unanswerable/P<n>.csv`.
- Check:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling validate
source .venv/bin/activate && python -m paperpilot.evaluation.labeling agreement --stage unanswerable
```

- `validate` prints `unanswerable slice: N of 100 questions survive`, and one `warning:` per `yes` answer (with the replacement the author proposed). The slice must be **exactly 100** questions at the final check.
- **Replacing a `yes` question (for example `P3-U05`):**
  1. Append one row at the bottom of `data/eval/labeling/raw/questions/P3.csv`: `query_id` = the next free id (`P3-U21`, then `P3-U22`, …), `question` = the `new_question` text. This is the single manual edit allowed in `raw/` (see section 0). Run `check-questions` again.
  2. Run `unanswerable-sheets --only P3-U21` (several ids: `--only P3-U21,P4-U21`). It writes `reports/pooling/unanswerable/replacements/P3.csv` and nothing else (the full sheets are not touched). Send that file to P3 (Drive `4-unanswerable-check/`).
  3. When P3 answers, save the downloaded CSV as `data/eval/labeling/raw/unanswerable/replacements/P3.csv`. Do not paste anything into `raw/unanswerable/P3.csv`.
  4. A replacement question joins the slice when its answer is `no`. Until then it is listed as `not yet checked`. If it is also `yes`, append another replacement row in `raw/questions/` and run `--only` again with the new id: the replacement sheet then lists all of that person's replacement questions, and you save the new download over the old one (this needs `--force`, see section 0).
- If the author says `no` and the double-checker says `yes` (or the reverse), you need an adjudication row for it (section 6, key `UNANSWERABLE`).

## 6. Disagreement meeting and adjudication — Sat 24 Oct

- List what is open:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling validate
```

- The warning `N pair(s) need an adjudication row in adjudication.csv: (P1-007, 37b6…), …` lists every pair that two or more people labeled without a majority. The warning about `UNANSWERABLE` lists the unanswerable questions with disagreeing answers.
- In the meeting, each person says their label and a one-sentence reason; a third person decides. The adjudicator must **not** be one of the people who labeled that pair (for unanswerable rows: not the author or the double-checker). The tools reject such a row. The only exception: a pilot row that all four people labeled, where anyone may decide.
- Record each decision as one row in `data/eval/labeling/adjudication.csv` (UTF-8 CSV, this exact header):

```
query_id,chunk_id,final_relevance,adjudicator,reason
P1-007,37b60e50d6739d5d,1,P4,"related but does not answer"
P3-U05,UNANSWERABLE,no,P2,"no passage answers it"
```

- `final_relevance` is `0`, `1` or `2` for passages, and `yes` or `no` for rows with `chunk_id` = `UNANSWERABLE` (the final value of `answered_by_library`).
- Run `validate` again until the adjudication warnings are gone. Commit `adjudication.csv`.
- Mistakes are reported with `file:row` (`final_relevance '3'`, `adjudicator 'P9'`, `adjudicator P2 labeled this pair`, `duplicate adjudication`).

## 7. Gold answers — Sat 24 Oct – Sun 25 Oct, 12:00 (Step 5); reviews until Mon 26 Oct, 09:00

Gold sheets need **all** pilot and round-1 sheets back (and round-2 sheets if round 2 was drafted) and no adjudication row missing. If something is missing the command stops with exit 1 and names the files or lists the pairs. All warnings are printed. Run it right after the disagreement meeting (and, if round 2 runs this weekend, **before** you draft round 2; section 8):

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling gold-sheets
```

- **PASS:** `gold-sheets gold ok: rows per sheet P1=50, …`. Upload `reports/pooling/gold/P<n>.csv` to Drive `5-gold-answers/`. (Passages are shown cut to 2,000 characters each; the `gold_passages` ids are complete.)
- At the deadline (Sun 25 Oct, 12:00): download as CSV → `data/eval/labeling/raw/gold/P<n>.csv`, then run `validate`. FAIL examples:
  - `gold_answer is empty` → ask the author to write an answer or `NO_EVIDENCE`;
  - `gold_passages not labeled 2 for this question: [...]` → the author listed a passage that is not a 2;
  - `gold_passages is empty` → a real answer needs at least one passage.
- `NO_EVIDENCE` is allowed (any capitalisation). These questions are kept out of `qa_pairs.jsonl`; `validate` and `merge` list them. There must be at least **250** answerable QA rows at the final check; if `NO_EVIDENCE` answers push the number below 250, decide with the owner (for example write a better question) or accept it explicitly with `--allow-short-qa`.

Then the reviews (each person gets about 8 answers written by others), on Sun 25 Oct, afternoon:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling gold-sheets --review
```

- Upload `reports/pooling/gold-review/P<n>.csv` to Drive `5-gold-answers/` (a second sheet per person). Add the `review` dropdown. At the deadline (Mon 26 Oct, 09:00) collect → `data/eval/labeling/raw/gold-review/P<n>.csv`. The review stage is **required** for the final merge.
- Run `agreement --stage gold-review` (reviewer against the answer's author; its output says "kappa not meaningful") and `validate`. Every `disagree` is listed with its reason (also in the merge summary): settle them with the author; they do not block the merge.
- Commit `raw/gold/` and `raw/gold-review/`.

## 8. Round 2 — Sat 24 – Sun 25 Oct (Step 6, needs Story 1.5)

Save the pilot and round-1 sheets in `raw/` first: the command needs a returned sheet for **every** person who got a pilot or round-1 sheet (otherwise exit 1 naming the missing files) and it also counts already returned round-2 sheets as judged. Then, with the config rows from Story 1.5 (names as in `configs/ablations.yaml`):

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling sheets --round 2 --rows E4,E5a
```

- Only (question, passage) pairs without a pilot, round-1 or round-2 judgment are drafted, from the top 10 of the rows you name.
- **PASS:** a summary with the rows added per person and the cumulative load (round 1 + round 2); loads are balanced on the cumulative total and there is no 5% stop for round 2. Then `wrote 4 sheets -> reports/pooling/round2`. If every passage is already judged: `nothing to draft`, and no files.
- **FAIL:** exit 3 with `unknown config row` (check the ids in `configs/ablations.yaml`), `--rows` missing, or `no returned … sheets` (save the earlier sheets first). Exit 1 with `returned sheet missing` → a pilot or round-1 sheet is not in `raw/`.
- Upload `reports/pooling/round2/P<n>.csv` to Drive `6-round2/`. Collect → `data/eval/labeling/raw/round2/P<n>.csv`. Check with `validate` and `agreement --stage round2`. Once round 2 is drafted, every drafted sheet must come back before `merge`. Commit `raw/round2/`.
- Order of work this weekend: `gold-sheets` first (it refuses to run while round-2 sheets are drafted but not back), then round 2, then `gold-sheets --review` after the round-2 sheets are in.

## 9. Final merge — Mon 26 Oct

1. Check everything is in place:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling validate --final
```

- **PASS:** `validate ok (final)`. It also prints `labeled rows: N qrels + M QA = T (floor 1250)` and `answerable QA rows: N (floor 250)`.
- **FAIL (exit 1):** a required stage (including `gold-review`) has no or incomplete returned sheets, an adjudication row is missing, an answerable question has no judgment, a chunk id is no longer in `chunks.jsonl` (the KB was rebuilt after labeling: tell the owner, do not edit the CSVs), the unanswerable slice is not exactly 100 questions split 40 dev / 60 held-out, there are fewer than 250 answerable QA rows, or the total is below 1,250.
- Only with the owner's agreement, you can accept a short slice with `--allow-short-slice` (the split is then `round(0.4 × n)` dev) or fewer than 250 QA rows with `--allow-short-qa`. More than 100 questions in the slice is always an error (it names the extras to drop).

2. Write the three files:

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling merge
```

- `merge` runs the same checks first and writes `data/eval/queries.jsonl`, `qrels.jsonl` and `qa_pairs.jsonl` only if they pass. The 40/60 split is made automatically (by author) and kept stable on later merges: questions that stay in the slice keep their split. It prints the counts, the summary table, the `NO_EVIDENCE` list and the gold-review disagreements, and writes `reports/labeling/merge_summary.json`.
- **FAIL:** exit 1 names `file:row` or lists missing adjudication pairs, nothing is written. Exit 3 with `refusing to overwrite … pass --replace`: the files already exist. Only use `--replace` when you really want to regenerate them (ask the owner first):

```
source .venv/bin/activate && python -m paperpilot.evaluation.labeling merge --replace
```

  The old files are kept as `.bak` copies while the three new files are written; if anything fails they are restored, so you never end up with a mixed set.

3. Commit and push: `data/eval/labeling/raw/` (all stages), `data/eval/labeling/adjudication.csv`, `data/eval/queries.jsonl`, `data/eval/qrels.jsonl`, `data/eval/qa_pairs.jsonl`, and the guides (with the change log). `reports/` is not committed: copy the numbers into `agreement-report.md` first.

4. Fill in `data/eval/labeling/agreement-report.md` from the printed tables, `reports/labeling/agreement_<stage>.json` (pilot, round 1, round 2, unanswerable, gold review) and `reports/labeling/merge_summary.json`: for each of `qrels_pilot_round1`, `qrels_round2`, `qa_pairs_answerable`, `unanswerable_check` and `gold_review` it has `labeled_rows`, `double_labeled_pct`, `raw_agreement_pooled` and `cohen_kappa_mean`; plus `unique_questions`, `total_labeled_rows`, `unanswerable_slice`, `no_evidence` and `gold_review_disagreements`. Add what you changed in the guidelines.

## 10. Quick reference

| Step | Command | Upload (Drive) | Save returned CSV in |
| --- | --- | --- | --- |
| Kickoff | `catalog` | `0-read-me/`, `1-questions/` | — |
| Question check | `check-questions` | — | `raw/questions/` |
| Pilot | `pilot --auto 4`, then `agreement --stage pilot` | `2-pilot/` | `raw/pilot/` |
| Unanswerable | `unanswerable-sheets`, then `validate`, `agreement --stage unanswerable` | `4-unanswerable-check/` | `raw/unanswerable/` (replacements: `raw/unanswerable/replacements/`) |
| Main labeling | `sheets --round 1`, then `validate`, `agreement --stage round1` | `3-sprint/` | `raw/round1/` |
| Adjudication | write `adjudication.csv`, then `validate` | — | — |
| Gold answers | `gold-sheets`, then `gold-sheets --review`, `agreement --stage gold-review` | `5-gold-answers/` | `raw/gold/`, `raw/gold-review/` |
| Round 2 | `sheets --round 2 --rows <ids>`, then `agreement --stage round2` | `6-round2/` | `raw/round2/` |
| Final | `validate --final`, then `merge` | — | — |

(All paths in the last column are under `data/eval/labeling/`; drafted sheets are under `reports/pooling/<stage>/`. Every command is `python -m paperpilot.evaluation.labeling <subcommand>`.)
