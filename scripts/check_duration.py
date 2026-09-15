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

    n_lt_written = 0
    if len(lt):
        lt_sample = lt.sample(min(300, len(lt)), random_state=42)[
            ["parent_asin", "rating", "months_owned", "full_text"]
        ]
        n_lt_written = len(lt_sample)
        lt_sample.to_json(FEAS / "longterm_samples.jsonl", orient="records", lines=True, force_ascii=False)

    valid = cues[cues.notna()]
    chk = valid.sample(min(30, len(valid)), random_state=42)
    pd.DataFrame({
        "months": chk.map(lambda c: c["months"]),
        "snippet": chk.map(lambda c: c["snippet"]),
    }).to_csv(FEAS / "duration_manual_check.csv", index=False)
    print(f"wrote {n_lt_written} longterm samples; {len(chk)} manual-check rows")


if __name__ == "__main__":
    main()
