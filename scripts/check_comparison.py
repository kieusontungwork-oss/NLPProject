# scripts/check_comparison.py
import json
from pathlib import Path

import pandas as pd

FEAS = Path("data/feasibility")
OUT = FEAS / "comparison_pairs"

COLS = ["parent_asin", "title", "store", "categories", "rating_number", "average_rating", "price"]


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    meta = pd.read_parquet(FEAS / "sample_meta.parquet")
    reviews = pd.read_parquet(FEAS / "sample_reviews.parquet")
    counts = reviews["parent_asin"].value_counts()
    sample_frac = len(reviews) / 43_900_000  # Electronics total (dataset card)

    def enrich(df):
        df = df.copy()
        df["reviews_in_sample"] = df["parent_asin"].map(counts).fillna(0).astype(int)
        df["est_total_reviews"] = (df["reviews_in_sample"] / sample_frac).round().astype(int)
        # FIX: parquet round-trip returns categories as numpy.ndarray, not list.
        # Normalize to plain lists so list-based logic works unchanged.
        df["categories"] = df["categories"].map(
            lambda c: c.tolist() if hasattr(c, "tolist") else (list(c) if isinstance(c, (list, tuple)) else [])
        )
        df["cat2"] = df["categories"].map(lambda c: c[1] if len(c) > 1 else (c[0] if c else None))
        return df

    # Original top-20 over ALL products (display only; many Amazon 1P devices
    # have empty categories in the source data and cannot be category-paired).
    top_all = enrich(
        meta[meta["rating_number"] >= 1000]
        .sort_values("rating_number", ascending=False)
        .head(20)[COLS]
    )
    n_top20_empty_categories = int((top_all["categories"].map(len) == 0).sum())

    # Pairing pool (controller fix round 1): popular AND category-bearing.
    pool = enrich(
        meta[
            (meta["rating_number"] >= 1000)
            & meta["categories"].map(lambda c: hasattr(c, "__len__") and not isinstance(c, str) and len(c) > 0)
        ]
        .sort_values("rating_number", ascending=False)
        .head(100)[COLS]
    )

    pairs = []
    for cat, grp in pool.dropna(subset=["cat2"]).groupby("cat2"):
        if len(grp) >= 2:
            rows = grp.sort_values("reviews_in_sample", ascending=False).head(2).to_dict("records")
            pairs.append({"category": cat, "products": rows})

    # Clean stale artifacts from round 1 (old top20.json + old per-product JSONLs).
    for stale in list(OUT.glob("*.jsonl")) + [OUT / "top20.json"]:
        if stale.exists():
            stale.unlink()

    # Per-product JSONL only for pool products that appear in a pair (documented choice:
    # keeps the artifact set focused; all-pool extraction would add ~100 files of which
    # only pair members are consumed downstream).
    pair_asins = {p["parent_asin"] for pr in pairs for p in pr["products"]}
    for asin in sorted(pair_asins):
        sub = reviews[reviews["parent_asin"] == asin]
        sub[["rating", "title", "text", "verified_purchase", "helpful_vote", "timestamp"]].head(150).to_json(
            OUT / f"{asin}.jsonl", orient="records", lines=True, force_ascii=False)

    (OUT / "top20_all.json").write_text(top_all.to_json(orient="records", indent=2))
    (OUT / "pool100.json").write_text(pool.to_json(orient="records", indent=2))
    (OUT / "pairs.json").write_text(json.dumps(pairs, indent=2, default=str))

    eligible = sum(1 for p in pairs if p["products"][0]["reviews_in_sample"] >= 100 and p["products"][1]["reviews_in_sample"] >= 100)
    summary = {"n_top20": len(top_all), "n_pool": len(pool), "n_top20_empty_categories": n_top20_empty_categories,
               "n_pairs": len(pairs), "n_eligible_pairs_both_ge_100": eligible,
               "sample_fraction_of_corpus": round(sample_frac, 5)}
    (OUT / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    print("--- top-20 (all products) ---")
    print(top_all[["title", "rating_number", "reviews_in_sample", "cat2"]].to_string(max_colwidth=48))
    print("--- pool-100 (pairing pool) ---")
    print(pool[["title", "rating_number", "reviews_in_sample", "cat2"]].to_string(max_colwidth=48))
    print("--- pairs with eligibility ---")
    for p in pairs:
        a, b = p["products"]
        mark = "ELIGIBLE" if a["reviews_in_sample"] >= 100 and b["reviews_in_sample"] >= 100 else "not eligible"
        print(f"[{mark}] {p['category']}: {a['parent_asin']} ({a['reviews_in_sample']}) + {b['parent_asin']} ({b['reviews_in_sample']})")


if __name__ == "__main__":
    main()
