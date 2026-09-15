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
                "text": r["full_text"],
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
