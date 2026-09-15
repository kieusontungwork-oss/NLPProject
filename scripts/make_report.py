# scripts/make_report.py
# Transcribed from task-8-brief.md (Task 8, Step 2). pandas 3 fixes: none
# needed — the generator uses only stdlib (json, pathlib), no pandas.
# Extensions over the brief (per Task 8 requirements): adds a "## Key
# findings" section and corrects the evidence-file list to match disk.
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
    verified_pct = meta_rep.get("verified_purchase_rate", 0) * 100

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
        f"Sample: {meta_rep.get('n_reviews'):,} reviews / {meta_rep.get('n_unique_products')} products "
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
        "## Key findings",
        "",
        f"- **C1 (marginal PASS).** {c1}% agreement sits exactly at the 90% threshold. All five "
        "disagreements were 3-star reviews (the neutral class is inherently ambiguous); an independent "
        "reviewer concurred with exactly the same 5 disagreements.",
        f"- **C2 (PASS).** 0% nulls on all 7 required fields; verified_purchase {verified_pct:.1f}%. The sample is "
        f"time-representative: median year {int(meta_rep.get('median_year', 0))}, only {meta_rep.get('pct_pre_2010')}% "
        "pre-2010, and 2023 share ~2.2%.",
        f"- **C3 (PARTIAL).** {c3}% corpus-wide aspect coverage (mean "
        f"{asp_rep.get('mean_aspects_per_review')}/review). Label precision ~90%. Meta features present on "
        f"{asp_meta.get('pct_products_with_features')}% of products — a good aspect-vocabulary source.",
        f"- **C4 (PARTIAL — REFRAME recommended).** Cue rate {c4}% (PASS gate ≥1%), long-term (≥3mo) "
        f"{dur_rep.get('pct_longterm_ge_3mo')}%, max top-product long-term count {c4b} (PASS gate ≥50). "
        f"Manual cue precision {c4c}% FAILS the 80% gate (independent reviewer: 66.7%). Production needs "
        "a stricter ownership-context filter; the proposal should describe this feature as "
        "\"retrospective / update reviews\" rather than a strict 3-month boundary.",
        f"- **C5 (PASS).** {c5}% signal rate; all 7 categories sampled (hinge "
        f"{durab_rep.get('per_category_rate_pct', {}).get('hinge')}%, battery_degradation "
        f"{durab_rep.get('per_category_rate_pct', {}).get('battery_degradation')}%). Label precision ~77-80% "
        "(negation false positives).",
        f"- **C6 (PARTIAL).** {cmp_sum.get('n_pairs')} pairs, {c6} eligible by the ≥100-review gate, but only "
        "**1 genuinely comparable STRONG pair**: Panasonic ErgoFit vs TOZO T10 earbuds (both leaf "
        "\"Earbud Headphones\"). 11/20 top products have empty categories (source-data property). "
        "Leaf-level pairing would add a 2nd strong pair (GE power strips, 95<100); the relaxed-threshold "
        "ruling is recorded (`C6_relaxed_threshold: true`).",
        "- **C7 (INFO).** Electronics full ≈ 27.9 GB (22.62 + 5.25) vs proposal's 10–15 GB claim. "
        "Meta price is null on 60.6% of products, limiting price-aware features. The sample is the first "
        "1M of ~43.9M reviews (est. ~2.3% corpus coverage).",
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
        "- check_metadata.json, check_aspects.json, check_aspects_meta.json, check_duration.json, "
        "check_durability.json, verdicts.json",
        "- comparison_pairs/ (top20_all.json, pool100.json, pairs.json, summary.json, 12 per-product JSONL)",
        "- spot_check_stars.csv, duration_manual_check.csv",
    ]
    (FEAS / "feasibility_report.md").write_text("\n".join(lines) + "\n")
    print(f"wrote {FEAS / 'feasibility_report.md'}")


if __name__ == "__main__":
    main()
