# SentiScope Data Feasibility Study — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Validate every data-dependent claim in the SentiScope proposal against real Amazon Reviews 2023 (Electronics) data, producing sample evidence files and a pass/fail feasibility report.

**Architecture:** Stream ~1M review records + ~300K product-meta records from the HuggingFace-hosted McAuley-Lab/Amazon-Reviews-2023 dataset (Electronics category, no full 28 GB download unless needed). Run regex/statistical feasibility checks over the sample; emit per-check JSON metrics + JSONL sample files; assemble a verdict report.

**Tech Stack:** Python 3.12 venv, `requests` (HTTP streaming), `pandas`, `pyarrow`, `pytest`, `huggingface_hub` (conditional full download).

**Dataset facts (verified 2026-09-06):**
- Repo: `McAuley-Lab/Amazon-Reviews-2023` (HF). Viewer disabled (script dataset) → do NOT use `datasets.load_dataset`; stream raw JSONL via HTTPS resolve URLs.
- `raw/review_categories/Electronics.jsonl` = 22.62 GB (~43.9M reviews); `raw/meta_categories/meta_Electronics.jsonl` = 5.25 GB (~1.6M products).
- Review fields: `rating, title, text, images, asin, parent_asin, user_id, timestamp` (unix ms)`, helpful_vote, verified_purchase`.
- Meta fields: `main_category, title, average_rating, rating_number, features, description, price, store, categories, details, parent_asin, ...`.
- **No purchase-date field** → ownership duration ("3+ months") must be inferred from review text (check C4).

**Success criteria per check:**

| Check | Criterion for PASS |
|---|---|
| C1 star→sentiment baseline | ≥90% agreement on 50-review manual spot-check |
| C2 metadata coverage | <5% nulls on rating/text/timestamp/verified_purchase |
| C3 aspect coverage | ≥60% of sampled reviews mention ≥1 aspect |
| C4 ownership-duration cues | ≥1% of reviews have explicit cue AND ≥1 top product has ≥50 long-term (≥3mo) reviews |
| C5 durability signals | ≥3% of reviews have a failure/wear signal; hinge + battery examples exist |
| C6 comparison pairs | ≥5 same-subcategory pairs, both products ≥100 in-sample reviews |
| C7 storage | Subset strategy documented to fit 10–15 GB budget |

**No git commits** anywhere in this plan (project rule: no commits without explicit user permission).

---

### Task 0: Environment setup

**Files:** Create `.venv/` (ignored), `scripts/`, `tests/`, `data/feasibility/`

- [ ] **Step 1: Create venv and install deps**

```bash
cd /Users/kieusontung/NTU_Projects/NLPProject
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install requests pandas pyarrow pytest huggingface_hub
```

- [ ] **Step 2: Verify**

```bash
.venv/bin/python -c "import requests, pandas, pyarrow, pytest, huggingface_hub; print('ok')"
```

Expected: `ok`

- [ ] **Step 3: Create directories**

```bash
mkdir -p scripts tests data/feasibility data/amazon
```

---

### Task 1: Text classifiers (TDD)

**Files:**
- Create: `tests/test_classifiers.py`
- Create: `scripts/classifiers.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/test_classifiers.py
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from classifiers import detect_aspects, detect_duration_cue, detect_durability_issues


class TestDetectAspects:
    def test_battery_and_anc(self):
        assert detect_aspects("Battery lasts forever and the ANC is incredible.") == {
            "battery",
            "noise_cancelling",
        }

    def test_price_and_fit(self):
        found = detect_aspects("Too expensive for what you get, and it doesn't fit my small ears.")
        assert "price_value" in found and "fit" in found

    def test_no_aspect(self):
        assert detect_aspects("Arrived quickly, packaging was fine.") == set()

    def test_empty(self):
        assert detect_aspects("") == set()
        assert detect_aspects(None) == set()


class TestDetectDurationCue:
    def test_numeric_months(self):
        r = detect_duration_cue("I've had these headphones for 6 months now and the battery still lasts.")
        assert r is not None and abs(r["months"] - 6.0) < 0.1

    def test_numeric_years(self):
        r = detect_duration_cue("Works great after 2 years of daily use.")
        assert r is not None and r["months"] > 20

    def test_word_number_months_in(self):
        r = detect_duration_cue("Three months in and no complaints so far.")
        assert r is not None and abs(r["months"] - 3.0) < 0.1

    def test_a_month(self):
        r = detect_duration_cue("Broke after a month of light use.")
        assert r is not None and abs(r["months"] - 1.0) < 0.2

    def test_update_review(self):
        r = detect_duration_cue("UPDATE: after 14 months of use the left ear cup cracked.")
        assert r is not None and abs(r["months"] - 14.0) < 0.1

    def test_no_number_no_match(self):
        assert detect_duration_cue("Bought recently, works great so far.") is None

    def test_warranty_negative(self):
        assert detect_duration_cue("The warranty is 2 years, which is nice for peace of mind.") is None

    def test_hours_not_matched(self):
        assert detect_duration_cue("The battery lasts 30 hours per charge.") is None

    def test_empty(self):
        assert detect_duration_cue("") is None
        assert detect_duration_cue(None) is None


class TestDetectDurabilityIssues:
    def test_hinge_and_crack(self):
        found = detect_durability_issues("The hinge cracked after a year of use.")
        assert "hinge" in found and "broke_cracked" in found

    def test_battery_degradation(self):
        assert "battery_degradation" in detect_durability_issues(
            "Battery now drains within 2 hours; definitely degraded since new."
        )

    def test_stopped_working(self):
        assert "stopped_working" in detect_durability_issues("It just stopped working one day.")

    def test_worn_out(self):
        assert "worn_out" in detect_durability_issues("The ear pads are completely worn out.")

    def test_healthy_review(self):
        assert detect_durability_issues("Great sound, super comfortable, best purchase!") == set()

    def test_empty(self):
        assert detect_durability_issues("") == set()
        assert detect_durability_issues(None) == set()
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
.venv/bin/python -m pytest tests/test_classifiers.py -q
```

Expected: FAIL (ModuleNotFoundError: classifiers)

- [ ] **Step 3: Implement classifiers**

```python
# scripts/classifiers.py
"""Regex classifiers for the SentiScope feasibility study (Electronics reviews)."""

import re

ASPECT_LEXICON = {
    "battery": [r"\bbatt(?:ery|eries)\b", r"\bcharging\b", r"\bcharge life\b"],
    "sound_quality": [r"\bsounds?\b", r"\bsound\b", r"\baudio\b", r"\bbass\b", r"\btreble\b", r"\bsoundstage\b"],
    "noise_cancelling": [r"\bnoise[ -]cancell?(?:ing|ation)\b", r"\bANC\b", r"\bambient (?:mode|sound)\b", r"\btransparency mode\b"],
    "comfort": [r"\bcomfort(?:able|ably)?\b", r"\bear ?(?:fatigue|pain|sore|hurts?)\b", r"\bclamping?\b", r"\bwore (?:them|it) all day\b"],
    "microphone": [r"\bmics?\b", r"\bmicrophone\b", r"\bvoice ?(?:quality|pick ??up)\b"],
    "build_quality": [r"\bbuild\b", r"\bsturdy\b", r"\bwell[ -]made\b", r"\bcheap(?:ly)?[ -](?:made|feeling)\b", r"\bflimsy\b", r"\bplasticky\b"],
    "price_value": [r"\bprice[ds]?\b", r"\bworth\b", r"\bvalue\b", r"\bexpensive\b", r"\boverpriced\b", r"\bsteep\b"],
    "connectivity": [r"\bbluetooth\b", r"\bpairs? with\b", r"\bconnect(?:s|ion|ivity)?\b", r"\bdrop ?outs?\b", r"\bmultipoint\b"],
    "fit": [r"\bfit(?:s|ting|ted)?\b", r"\bsize\b", r"\btoo (?:big|small|tight|loose)\b"],
    "app_software": [r"\bapp\b", r"\bfirmware\b", r"\bsoftware\b"],
    "screen_display": [r"\bscreen\b", r"\bdisplay\b", r"\btouch ?screen\b"],
    "setup_ease": [r"\bset[ -]?up\b", r"\bsetup\b", r"\binstall(?:ation|ed|ing)?\b"],
    "durability": [r"\bdurab\w*\b", r"\blongevity\b", r"\bstands? up to\b"],
    "warranty_support": [r"\bwarranty\b", r"\bcustomer (?:service|support)\b", r"\brefund\b"],
}

_NUM_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "fifteen": 15, "eighteen": 18, "twenty": 20,
}
_UNIT_TO_MONTHS = {"day": 1 / 30.4, "week": 1 / 4.345, "month": 1.0, "year": 12.0}
_NUM_ALT = "|".join(list(_NUM_WORDS) + [r"\d{1,3}"])

_DURATION_RE = re.compile(r"\b(" + _NUM_ALT + r")\s*\+?\s*(day|week|month|year)s?\b", re.IGNORECASE)
_DURATION_IN_RE = re.compile(r"\b(" + _NUM_ALT + r")\s+(day|week|month|year)s?\s+in\b", re.IGNORECASE)
_OWNERSHIP_CTX_RE = re.compile(
    r"(after|own(?:ed|er|ing)|have had|has had|i.?ve had|had (?:it|them|this|these|mine)|"
    r"of (?:use|ownership|daily|light|heavy)|daily use|update|later|since|purchase|bought|"
    r"got (?:it|them|this|these)|used|still (?:going|working|using))",
    re.IGNORECASE,
)

DURABILITY_LEXICON = {
    "hinge": [r"\bhinges?\b"],
    "battery_degradation": [
        r"\bbattery\b[^.!?]{0,80}\b(degrad\w*|drains?\b|draining|doesn.?t hold|no longer holds|"
        r"life (?:has )?(?:dropped|decreased|shortened|gone down|deteriorat\w*))",
        r"\bdegraded\b[^.!?]{0,60}\bbattery\b",
    ],
    "stopped_working": [
        r"stopped working", r"quit working", r"ceased (?:to )?(?:work|function)",
        r"won.?t (?:turn on|power on|charge)", r"dead (?:on arrival|after)", r"stopped charging",
    ],
    "broke_cracked": [r"\bbroke\b", r"\bbroken\b", r"\bcracked\b", r"\bsnapped\b", r"\bshattered\b", r"\b(?:fell|falls?|falling|came|coming) apart\b"],
    "worn_out": [r"\bworn (?:out|down)\b", r"\bfrayed\b", r"\bpeeling\b", r"\bflaking\b", r"\bfoam (?:crumbled|flattened|deteriorated)\b"],
    "intermittent_fault": [
        r"\bintermittent\w*\b", r"cuts? (?:in )?and out",
        r"one (?:side|ear ?cup|channel|bud) (?:stopped|died|went (?:out|dead))",
    ],
    "connection_failure": [r"\bconnection (?:drops?|issues?|problems?)\b", r"\bkeeps? disconnect\w*\b", r"\bwon.?t pair\b", r"\bcan.?t connect\b"],
}

_aspects_c = {a: [re.compile(p, re.IGNORECASE) for p in ps] for a, ps in ASPECT_LEXICON.items()}
_durab_c = {a: [re.compile(p, re.IGNORECASE) for p in ps] for a, ps in DURABILITY_LEXICON.items()}


def _scan(text, compiled):
    if not text:
        return set()
    return {name for name, pats in compiled.items() if any(p.search(text) for p in pats)}


def detect_aspects(text):
    """Return set of aspect names discussed in `text`."""
    return _scan(text, _aspects_c)


def detect_durability_issues(text):
    """Return set of durability/failure categories present in `text`."""
    return _scan(text, _durab_c)


def detect_duration_cue(text):
    """Return {'months': float, 'snippet': str} for the first explicit
    ownership-duration mention, else None. 'N units in' phrasing
    (e.g. 'three months in') is accepted without extra context."""
    if not text:
        return None
    m = _DURATION_IN_RE.search(text)
    if m:
        num = _to_number(m.group(1))
        if num is not None:
            months = num * _UNIT_TO_MONTHS[m.group(2).lower()]
            return {"months": round(months, 1), "snippet": _window(text, m)}
    for m in _DURATION_RE.finditer(text):
        window = _window(text, m)
        if _OWNERSHIP_CTX_RE.search(window):
            num = _to_number(m.group(1))
            if num is None:
                continue
            months = num * _UNIT_TO_MONTHS[m.group(2).lower()]
            return {"months": round(months, 1), "snippet": window}
    return None


def _to_number(group):
    return _NUM_WORDS.get(group.lower(), int(group)) if not group.isdigit() else int(group)


def _window(text, m, pad=60):
    return text[max(0, m.start() - pad):min(len(text), m.end() + pad)].strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
.venv/bin/python -m pytest tests/test_classifiers.py -q
```

Expected: all PASS. If a specific expectation conflicts with regex reality, fix the implementation (not the test intent) — e.g. tighten `_OWNERSHIP_CTX_RE` until `test_warranty_negative` passes while `test_numeric_years` still passes.

---

### Task 2: Streaming sampler

**Files:**
- Create: `scripts/fetch_sample.py`
- Create: `data/feasibility/sample_reviews.parquet` (~1M reviews)
- Create: `data/feasibility/sample_meta.parquet` (~300K products)

- [ ] **Step 1: Write fetcher**

```python
# scripts/fetch_sample.py
"""Stream the first N JSONL rows of an Amazon Reviews 2023 category file to parquet."""
import argparse
import json
import time
from pathlib import Path

import pandas as pd
import requests

URL_TMPL = "https://huggingface.co/datasets/McAuley-Lab/Amazon-Reviews-2023/resolve/main/{path}"


def stream_jsonl_to_parquet(remote_path: str, n_rows: int, out_path: str, start_byte: int = 0):
    url = URL_TMPL.format(path=remote_path)
    headers = {"Range": f"bytes={start_byte}-"} if start_byte else {}
    rows, t0 = [], time.time()
    with requests.get(url, stream=True, timeout=120, headers=headers) as resp:
        resp.raise_for_status()
        parsed = 0
        for line in resp.iter_lines(chunk_size=1024 * 1024):
            if not line:
                continue
            rows.append(json.loads(line))
            parsed += 1
            if parsed >= n_rows:
                break
            if parsed % 100_000 == 0:
                print(f"{parsed:,}/{n_rows:,} rows ({time.time() - t0:.0f}s)", flush=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_parquet(out, index=False)
    print(f"wrote {len(rows):,} rows -> {out} ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="repo-relative path, e.g. raw/review_categories/Electronics.jsonl")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start-byte", type=int, default=0)
    args = ap.parse_args()
    stream_jsonl_to_parquet(args.path, args.n, args.out, args.start_byte)
```

- [ ] **Step 2: Fetch review sample (~1M rows; a few minutes)**

```bash
.venv/bin/python scripts/fetch_sample.py --path raw/review_categories/Electronics.jsonl --n 1000000 --out data/feasibility/sample_reviews.parquet
```

Expected: `wrote 1,000,000 rows -> data/feasibility/sample_reviews.parquet`

- [ ] **Step 3: Fetch meta sample (~300K rows)**

```bash
.venv/bin/python scripts/fetch_sample.py --path raw/meta_categories/meta_Electronics.jsonl --n 300000 --out data/feasibility/sample_meta.parquet
```

Expected: `wrote 300,000 rows -> data/feasibility/sample_meta.parquet`

- [ ] **Step 4: Sanity check schema**

```bash
.venv/bin/python -c "
import pandas as pd
r = pd.read_parquet('data/feasibility/sample_reviews.parquet')
m = pd.read_parquet('data/feasibility/sample_meta.parquet')
print(r.dtypes); print('reviews:', len(r), 'meta:', len(m))
print('ts range:', pd.to_datetime(r.timestamp, unit='ms').min(), '->', pd.to_datetime(r.timestamp, unit='ms').max())
"
```

Expected: reviews has columns rating,title,text,asin,parent_asin,user_id,timestamp,helpful_vote,verified_purchase.

---

### Task 3: Check C1 + C2 (metadata & ratings)

**Files:**
- Create: `scripts/check_metadata.py`
- Create: `data/feasibility/check_metadata.json`, `data/feasibility/spot_check_stars.csv`

- [ ] **Step 1: Write and run checker**

```python
# scripts/check_metadata.py
import json
from pathlib import Path

import pandas as pd

FEAS = Path("data/feasibility")


def main():
    df = pd.read_parquet(FEAS / "sample_reviews.parquet")
    ts = pd.to_datetime(df["timestamp"], unit="ms")
    report = {
        "n_reviews": len(df),
        "field_null_rates": df[["rating", "title", "text", "timestamp", "helpful_vote", "verified_purchase", "parent_asin"]].isna().mean().round(4).to_dict(),
        "rating_counts": df["rating"].value_counts().sort_index().to_dict(),
        "rating_pct": (df["rating"].value_counts(normalize=True).sort_index() * 100).round(2).to_dict(),
        "verified_purchase_rate": round(float(df["verified_purchase"].mean()), 4),
        "helpful_vote_mean": round(float(df["helpful_vote"].mean()), 2),
        "helpful_vote_pct_gt0": round(float((df["helpful_vote"] > 0).mean()), 4),
        "timestamp_min": str(ts.min()),
        "timestamp_max": str(ts.max()),
        "n_unique_products": int(df["parent_asin"].nunique()),
        "n_unique_users": int(df["user_id"].nunique()),
    }
    print(json.dumps(report, indent=2, default=str))
    (FEAS / "check_metadata.json").write_text(json.dumps(report, indent=2, default=str))

    spot = df.groupby("rating", group_keys=False).apply(lambda g: g.sample(min(10, len(g)), random_state=42))
    spot[["rating", "title", "text"]].to_csv(FEAS / "spot_check_stars.csv", index=False)
    print(f"wrote {len(spot)} rows -> {FEAS / 'spot_check_stars.csv'}")


if __name__ == "__main__":
    main()
```

```bash
.venv/bin/python scripts/check_metadata.py
```

- [ ] **Step 2: Gate — timestamp skew**

If `timestamp_min` is before ~2005 (i.e., the file front is ancient reviews), re-fetch with a byte offset at ~40% of the 22.62 GB file:

```bash
.venv/bin/python scripts/fetch_sample.py --path raw/review_categories/Electronics.jsonl --n 1000000 --out data/feasibility/sample_reviews.parquet --start-byte 9050000000
```

Then rerun Step 1.

- [ ] **Step 3: Manual spot-check (executing agent)**

Read `spot_check_stars.csv`; for each of the 50 rows judge sentiment (pos/neg/neutral) from title+text; compare against star mapping (1-2★ neg, 3★ neutral, 4-5★ pos). Record agreement % in `data/feasibility/verdicts.json`:

```json
{"C1_spot_check_agreement_pct": 92.0}
```

Expected: ≥90% agreement → C1 PASS.

---

### Task 4: Check C3 (aspect coverage)

**Files:**
- Create: `scripts/check_aspects.py`
- Create: `data/feasibility/check_aspects.json`, `check_aspects_meta.json`, `aspect_samples.jsonl`

- [ ] **Step 1: Write and run**

```python
# scripts/check_aspects.py
import json
from pathlib import Path

import pandas as pd

from classifiers import detect_aspects

FEAS = Path("data/feasibility")


def main():
    df = pd.read_parquet(FEAS / "sample_reviews.parquet")
    df["full_text"] = df["title"].fillna("") + ". " + df["text"].fillna("")
    found = df["full_text"].map(detect_aspects)
    df["n_aspects"] = found.map(len)

    per_aspect = pd.Series([a for s in found for a in s]).value_counts()
    report = {
        "n_reviews": len(df),
        "pct_with_any_aspect": round(float((df["n_aspects"] > 0).mean()) * 100, 2),
        "mean_aspects_per_review": round(float(df["n_aspects"].mean()), 2),
        "per_aspect_hit_rate_pct": (per_aspect / len(df) * 100).round(2).to_dict(),
    }
    print(json.dumps(report, indent=2))
    (FEAS / "check_aspects.json").write_text(json.dumps(report, indent=2))

    hits = df[df["n_aspects"] > 0].sample(min(500, int((df["n_aspects"] > 0).sum())), random_state=42)
    with open(FEAS / "aspect_samples.jsonl", "w") as f:
        for _, r in hits.iterrows():
            f.write(json.dumps({
                "parent_asin": r["parent_asin"],
                "rating": r["rating"],
                "aspects": sorted(detect_aspects(r["full_text"])),
                "text": r["full_text"][:600],
            }) + "\n")
    print(f"wrote {len(hits)} -> aspect_samples.jsonl")

    meta = pd.read_parquet(FEAS / "sample_meta.parquet")
    meta_report = {
        "n_products": len(meta),
        "pct_products_with_features": round(float((meta["features"].map(len) > 0).mean()) * 100, 2),
        "pct_products_with_description": round(float((meta["description"].map(len) > 0).mean()) * 100, 2),
    }
    print(json.dumps(meta_report, indent=2))
    (FEAS / "check_aspects_meta.json").write_text(json.dumps(meta_report, indent=2))


if __name__ == "__main__":
    main()
```

```bash
PYTHONPATH=scripts .venv/bin/python scripts/check_aspects.py
```

Expected gate: `pct_with_any_aspect >= 60`.

---

### Task 5: Check C4 (ownership duration)

**Files:**
- Create: `scripts/check_duration.py`
- Create: `check_duration.json`, `longterm_samples.jsonl`, `duration_manual_check.csv`

- [ ] **Step 1: Write and run**

```python
# scripts/check_duration.py
import json
from pathlib import Path

import pandas as pd

from classifiers import detect_duration_cue

FEAS = Path("data/feasibility")


def main():
    df = pd.read_parquet(FEAS / "sample_reviews.parquet")
    df["full_text"] = df["title"].fillna("") + ". " + df["text"].fillna("")
    cues = df["full_text"].map(detect_duration_cue)
    df["months_owned"] = cues.map(lambda c: c["months"] if c else None)

    n_cue = int(df["months_owned"].notna().sum())
    lt = df[df["months_owned"] >= 3]
    buckets = pd.cut(
        df["months_owned"], [-0.1, 1, 3, 12, 120, 1e9],
        labels=["<1mo", "1-3mo", "3-12mo", "1-10yr", "10yr+"],
    ).value_counts().sort_index()

    top10 = df["parent_asin"].value_counts().head(10)
    prod_lt = {
        a: int((df.loc[df["parent_asin"] == a, "months_owned"] >= 3).sum())
        for a in top10.index
    }
    report = {
        "n_reviews": len(df),
        "n_with_duration_cue": n_cue,
        "pct_with_duration_cue": round(n_cue / len(df) * 100, 2),
        "n_longterm_ge_3mo": int(len(lt)),
        "pct_longterm_ge_3mo": round(len(lt) / len(df) * 100, 2),
        "bucket_counts": {str(k): int(v) for k, v in buckets.items()},
        "top10_products_total": {a: int(c) for a, c in top10.items()},
        "top10_products_longterm_counts": prod_lt,
        "max_top10_longterm": int(max(prod_lt.values())),
    }
    print(json.dumps(report, indent=2, default=str))
    (FEAS / "check_duration.json").write_text(json.dumps(report, indent=2, default=str))

    if len(lt):
        lt.sample(min(300, len(lt)), random_state=42)[
            ["parent_asin", "rating", "months_owned", "full_text"]
        ].to_json(FEAS / "longterm_samples.jsonl", orient="records", lines=True, force_ascii=False)

    valid = cues[cues.notna()]
    chk = valid.sample(min(30, len(valid)), random_state=42)
    pd.DataFrame({
        "months": chk.map(lambda c: c["months"]),
        "snippet": chk.map(lambda c: c["snippet"]),
    }).to_csv(FEAS / "duration_manual_check.csv", index=False)
    print(f"wrote {len(lt)} longterm samples; {len(chk)} manual-check rows")


if __name__ == "__main__":
    main()
```

```bash
PYTHONPATH=scripts .venv/bin/python scripts/check_duration.py
```

- [ ] **Step 2: Manual verification (executing agent)**

Read all rows of `duration_manual_check.csv`; judge whether the inferred `months` is a genuine ownership duration. Record precision in `verdicts.json` as `C4_cue_precision_pct`.

Expected gate: `pct_with_duration_cue >= 1.0` AND `max_top10_longterm >= 50` AND precision ≥80%.

---

### Task 6: Check C5 (durability signals)

**Files:**
- Create: `scripts/check_durability.py`
- Create: `check_durability.json`, `durability_samples.jsonl`

- [ ] **Step 1: Write and run**

```python
# scripts/check_durability.py
import json
from pathlib import Path

import pandas as pd

from classifiers import detect_durability_issues

FEAS = Path("data/feasibility")


def main():
    df = pd.read_parquet(FEAS / "sample_reviews.parquet")
    df["full_text"] = df["title"].fillna("") + ". " + df["text"].fillna("")
    found = df["full_text"].map(detect_durability_issues)
    df["n_issues"] = found.map(len)

    per_cat = pd.Series([c for s in found for c in s]).value_counts()
    report = {
        "n_reviews": len(df),
        "pct_with_any_signal": round(float((df["n_issues"] > 0).mean()) * 100, 2),
        "per_category_rate_pct": (per_cat / len(df) * 100).round(3).to_dict(),
    }
    print(json.dumps(report, indent=2))
    (FEAS / "check_durability.json").write_text(json.dumps(report, indent=2))

    hits = df[df["n_issues"] > 0].copy()
    hits["issues"] = found[hits.index].map(sorted)
    # stratified sample: prioritize every category present
    picked = []
    for cat in per_cat.index:
        sub = hits[hits["issues"].map(lambda x: cat in x)]
        picked.append(sub.sample(min(60, len(sub)), random_state=42))
    sample = pd.concat(picked).drop_duplicates(subset=["full_text"]).head(300)
    sample[["parent_asin", "rating", "issues", "full_text"]].to_json(
        FEAS / "durability_samples.jsonl", orient="records", lines=True, force_ascii=False)
    print(f"wrote {len(sample)} durability samples across {len(per_cat)} categories")


if __name__ == "__main__":
    main()
```

```bash
PYTHONPATH=scripts .venv/bin/python scripts/check_durability.py
```

Expected gate: `pct_with_any_signal >= 3` and hinge + battery_degradation categories present with samples.

---

### Task 7: Check C6 (comparison pairs)

**Files:**
- Create: `scripts/check_comparison.py`
- Create: `data/feasibility/comparison_pairs/top20.json`, `pairs.json`, `<ASIN>.jsonl` per product

- [ ] **Step 1: Write and run**

```python
# scripts/check_comparison.py
import json
from pathlib import Path

import pandas as pd

FEAS = Path("data/feasibility")
OUT = FEAS / "comparison_pairs"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = pd.read_parquet(FEAS / "sample_meta.parquet")
    top = (
        meta[meta["rating_number"] >= 1000]
        .sort_values("rating_number", ascending=False)
        .head(20)[["parent_asin", "title", "store", "categories", "rating_number", "average_rating", "price"]]
        .copy()
    )

    reviews = pd.read_parquet(FEAS / "sample_reviews.parquet")
    counts = reviews["parent_asin"].value_counts()
    top["reviews_in_sample"] = top["parent_asin"].map(counts).fillna(0).astype(int)
    sample_frac = len(reviews) / 43_900_000  # Electronics total (dataset card)
    top["est_total_reviews"] = (top["reviews_in_sample"] / sample_frac).round().astype(int)

    top["cat2"] = top["categories"].map(
        lambda c: c[1] if isinstance(c, list) and len(c) > 1 else (c[0] if isinstance(c, list) and c else None)
    )

    pairs = []
    for cat, grp in top.dropna(subset=["cat2"]).groupby("cat2"):
        if len(grp) >= 2:
            rows = grp.sort_values("reviews_in_sample", ascending=False).head(2).to_dict("records")
            pairs.append({"category": cat, "products": rows})

    for _, r in top.iterrows():
        sub = reviews[reviews["parent_asin"] == r["parent_asin"]]
        sub[["rating", "title", "text", "verified_purchase", "helpful_vote", "timestamp"]].head(150).to_json(
            OUT / f"{r['parent_asin']}.jsonl", orient="records", lines=True, force_ascii=False)

    (OUT / "top20.json").write_text(top.to_json(orient="records", indent=2))
    (OUT / "pairs.json").write_text(json.dumps(pairs, indent=2, default=str))

    eligible = sum(1 for p in pairs if p["products"][0]["reviews_in_sample"] >= 100 and p["products"][1]["reviews_in_sample"] >= 100)
    summary = {"n_top20": len(top), "n_pairs": len(pairs), "n_eligible_pairs_both_ge_100": eligible,
               "sample_fraction_of_corpus": round(sample_frac, 5)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    print(top[["title", "rating_number", "reviews_in_sample", "cat2"]].to_string(max_colwidth=48))


if __name__ == "__main__":
    main()
```

```bash
.venv/bin/python scripts/check_comparison.py
```

Expected gate: `n_eligible_pairs_both_ge_100 >= 5`. If < 5: (a) relax threshold to ≥50 and record, or (b) escalate to Task 9 full download for true per-product counts.

---

### Task 8: Feasibility report (C7 + verdicts)

**Files:**
- Create: `data/feasibility/verdicts.json` (assembled during execution)
- Create: `data/feasibility/feasibility_report.md`

- [ ] **Step 1: Assemble verdicts**

The executing agent writes `verdicts.json` combining manual judgments from Tasks 3 & 5 plus computed gates:

```json
{
  "C1_spot_check_agreement_pct": 0.0,
  "C4_cue_precision_pct": 0.0,
  "C6_relaxed_threshold": false
}
```

- [ ] **Step 2: Write report generator**

```python
# scripts/make_report.py
import json
from pathlib import Path

FEAS = Path("data/feasibility")


def load(name):
    p = FEAS / name
    return json.loads(p.read_text()) if p.exists() else {}


def main():
    meta_rep = load("check_metadata.json")
    asp_rep = load("check_aspects.json")
    asp_meta = load("check_aspects_meta.json")
    dur_rep = load("check_duration.json")
    durab_rep = load("check_durability.json")
    cmp_sum = load("comparison_pairs/summary.json")
    verdicts = load("verdicts.json")

    c1 = verdicts.get("C1_spot_check_agreement_pct", 0)
    c2_bad = [k for k, v in meta_rep.get("field_null_rates", {}).items() if v > 0.05 and k != "title"]
    c3 = asp_rep.get("pct_with_any_aspect", 0)
    c4 = dur_rep.get("pct_with_duration_cue", 0)
    c4b = dur_rep.get("max_top10_longterm", 0)
    c4c = verdicts.get("C4_cue_precision_pct", 0)
    c5 = durab_rep.get("pct_with_any_signal", 0)
    c5b = sorted(durab_rep.get("per_category_rate_pct", {}).keys())
    c6 = cmp_sum.get("n_eligible_pairs_both_ge_100", 0)

    rows = [
        ("C1 star→sentiment baseline", f"{c1}% agreement", "PASS" if c1 >= 90 else "FAIL"),
        ("C2 metadata coverage", f"nulls>5%: {c2_bad or 'none'}", "PASS" if not c2_bad else "FAIL"),
        ("C3 aspect coverage", f"{c3}% reviews w/ >=1 aspect; features on {asp_meta.get('pct_products_with_features')}% products",
         "PASS" if c3 >= 60 else "PARTIAL" if c3 >= 40 else "FAIL"),
        ("C4 ownership duration", f"{c4}% cue rate; precision {c4c}%; max top-product long-term {c4b}",
         "PASS" if (c4 >= 1 and c4b >= 50 and c4c >= 80) else "PARTIAL" if c4 >= 1 else "REFRAME"),
        ("C5 durability signals", f"{c5}% signal rate; categories: {', '.join(c5b)}",
         "PASS" if c5 >= 3 else "PARTIAL" if c5 >= 1 else "FAIL"),
        ("C6 comparison pairs", f"{c6} eligible pairs", "PASS" if c6 >= 5 else "PARTIAL" if c6 >= 2 else "FAIL"),
        ("C7 storage", "Electronics full = 22.62 GB reviews + 5.25 GB meta; subset strategy: top-2000 products + audio/wearables subcategories (~10-15 GB)", "INFO"),
    ]

    lines = [
        "# SentiScope Data Feasibility Report (Amazon Reviews 2023 — Electronics)",
        "",
        f"Sample: {meta_rep.get('n_reviews')} reviews / {meta_rep.get('n_unique_products')} products "
        f"(streamed from HF McAuley-Lab/Amazon-Reviews-2023 on 2026-09-06)",
        f"Review window in sample: {meta_rep.get('timestamp_min')} → {meta_rep.get('timestamp_max')}",
        f"Verified purchase rate: {meta_rep.get('verified_purchase_rate')}",
        "",
        "## Verdicts",
        "",
        "| Claim | Evidence | Verdict |",
        "|---|---|---|",
    ]
    for name, ev, v in rows:
        lines.append(f"| {name} | {ev} | {v} |")
    lines += [
        "",
        "## Key risk",
        "",
        "The dataset has NO purchase-date field. Ownership duration is text-inferred only.",
        "If C4 verdict is REFRAME, recommend the proposal describe this feature as",
        "'retrospective / update reviews' rather than a strict 3-month boundary.",
        "",
        "## Evidence files",
        "",
        "- aspect_samples.jsonl, longterm_samples.jsonl, durability_samples.jsonl",
        "- comparison_pairs/ (top20.json, pairs.json, per-product JSONL)",
        "- spot_check_stars.csv, duration_manual_check.csv",
    ]
    (FEAS / "feasibility_report.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {FEAS / 'feasibility_report.md'}")


if __name__ == "__main__":
    main()
```

```bash
.venv/bin/python scripts/make_report.py
```

Expected: `feasibility_report.md` exists with all 7 rows filled.

---

### Task 9 (CONDITIONAL — only if C6 gate fails or user approves KB start): Full download

**Files:**
- Create: `scripts/download_full.py`
- Create: `data/amazon/electronics/Electronics.jsonl`, `meta_Electronics.jsonl` (~28 GB)

- [ ] **Step 1: Download**

```python
# scripts/download_full.py
from huggingface_hub import hf_hub_download

for fname in ["raw/review_categories/Electronics.jsonl", "raw/meta_categories/meta_Electronics.jsonl"]:
    p = hf_hub_download(
        repo_id="McAuley-Lab/Amazon-Reviews-2023",
        repo_type="dataset",
        filename=fname,
        local_dir="data/amazon/electronics",
    )
    print("downloaded:", p)
```

```bash
.venv/bin/python scripts/download_full.py
```

Note: resumable; requires ~28 GB free. **Ask the user before running this task.**

---

## Self-review notes

- Spec coverage: all 7 checks (C1–C7) map to Tasks 3–8; classifiers feed C3/C4/C5; conditional full-download path (Task 9) covers C6 escalation.
- No placeholders: every script is complete; every command has expected output.
- Type consistency: `detect_*` signatures consistent between classifiers.py and consumers; report keys match checker outputs.
- No git commits (project rule).
