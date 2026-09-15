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
    # FIX(deviation from brief, documented in task-6-report.md): concat in
    # per_cat order + head(300) truncated the rarest categories
    # (battery_degradation, connection_failure) entirely. Round-robin the
    # per-category picks so the 300 cap cannot drop any category.
    rr = []
    for i in range(max(len(p) for p in picked)):
        for p in picked:
            if i < len(p):
                rr.append(p.iloc[[i]])
    sample = pd.concat(rr).drop_duplicates(subset=["full_text"]).head(300)
    sample[["parent_asin", "rating", "issues", "full_text"]].to_json(
        FEAS / "durability_samples.jsonl", orient="records", lines=True, force_ascii=False)
    print(f"wrote {len(sample)} durability samples across {len(per_cat)} categories")


if __name__ == "__main__":
    main()
