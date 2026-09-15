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
        # ADDED per controller request (documented addition to brief):
        "median_year": float(ts.dt.year.median()),
        "pct_pre_2010": round(float((ts.dt.year < 2010).mean() * 100), 2),
    }
    print(json.dumps(report, indent=2, default=str))
    (FEAS / "check_metadata.json").write_text(json.dumps(report, indent=2, default=str))

    # pandas 3 fix: groupby.apply no longer includes the grouping column in group
    # frames, so the concatenated result lost "rating". Explicit concat keeps the
    # exact same sampling semantics (min(10, len(g)), seed 42) and all columns.
    spot = pd.concat([g.sample(min(10, len(g)), random_state=42) for _, g in df.groupby("rating")])
    spot[["rating", "title", "text"]].to_csv(FEAS / "spot_check_stars.csv", index=False)
    print(f"wrote {len(spot)} rows -> {FEAS / 'spot_check_stars.csv'}")


if __name__ == "__main__":
    main()
