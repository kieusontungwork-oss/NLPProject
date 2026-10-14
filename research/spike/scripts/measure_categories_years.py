"""Follow-up spike measurement (2026-10-12): AI/ML/NLP yield + year range.

Answers the two unmeasured questions from the Week-0 review (PR #1):
1. What share of the scientific_papers arxiv split is AI/ML/NLP? (CAP-1 10k floor margin)
2. What year range does the corpus cover? (eval-plan subfield feasibility)

Method: the 200-paper slice already on disk (arxiv_train_slice.jsonl) is queried
against the public arXiv API (export.arxiv.org, batched id_list calls, polite 3s
delay). Records primary + all categories and the published date per paper.
"""
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

SLICE = Path(__file__).parents[1] / "data" / "scientific_papers" / "arxiv_train_slice.jsonl"
AI_ML_NLP = {"cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.IR", "cs.LG", "stat.ML"}
AI_ML_NLP = {"cs.AI", "cs.CL", "cs.LG", "cs.CV", "cs.IR", "stat.ML"}
NS = {"a": "http://www.w3.org/2005/Atom", "ax": "http://arxiv.org/schemas/atom"}
SPLIT_TOTAL = 215_000  # arxiv split size (Cohan et al. 2018 release, per HF card)


def api_id(article_id):
    """The dataset strips the slash from pre-2007 arXiv ids (nlin0608019);
    the API requires it (nlin/0608019)."""
    m = re.match(r"^([a-z-]+)(\d{7})$", article_id)
    return f"{m.group(1)}/{m.group(2)}" if m else article_id


def load_ids():
    ids = []
    with open(SLICE) as f:
        for line in f:
            line = line.strip()
            if line:
                ids.append(api_id(json.loads(line)["article_id"]))
    return ids


def fetch_batch(id_chunk):
    url = "http://export.arxiv.org/api/query?id_list=" + ",".join(id_chunk) + "&max_results=500"
    for attempt in range(3):
        try:
            with urllib.request.urlopen(url, timeout=60) as r:
                return ET.fromstring(r.read())
        except Exception as e:  # noqa: BLE001 - spike script, retry then fail loud
            if attempt == 2:
                raise
            print(f"  retry {attempt + 1} after error: {e}")
            time.sleep(5 * (attempt + 1))
    return None


def parse_batch(root):
    out = {}
    for entry in root.findall("a:entry", NS):
        raw = entry.find("a:id", NS).text  # e.g. http://arxiv.org/abs/nlin/0608019v2
        aid = raw.split("/abs/")[-1]
        aid = re.sub(r"v\d+$", "", aid)
        cats = [c.get("term") for c in entry.findall("a:category", NS)]
        primary = entry.find("ax:primary_category", NS)
        prim = primary.get("term") if primary is not None else (cats[0] if cats else None)
        pub = entry.find("a:published", NS)
        year = int(pub.text[:4]) if pub is not None else None
        out[aid] = {"categories": cats, "primary": prim, "year": year}
    return out


def main():
    ids = load_ids()
    print(f"slice papers: {len(ids)}")
    info = {}
    for i in range(0, len(ids), 50):
        chunk = ids[i : i + 50]
        print(f"batch {i // 50 + 1}: {len(chunk)} ids ...")
        root = fetch_batch(chunk)
        info.update(parse_batch(root))
        time.sleep(3)  # arXiv API politeness
    print(f"resolved: {len(info)}/{len(ids)}")

    missing = [a for a in ids if a not in info]
    if missing:
        print(f"WARNING unresolved ids: {missing}")

    ai = [a for a in ids if a in info and set(info[a]["categories"]) & AI_ML_NLP]
    cs = [a for a in ids if a in info and any(c.startswith("cs.") for c in info[a]["categories"])]
    years = [info[a]["year"] for a in ids if a in info and info[a]["year"]]
    prim_ai = [a for a in ids if a in info and info[a]["primary"] in AI_ML_NLP]

    est_total = len(ai) / len(ids) * SPLIT_TOTAL
    result = {
        "sample_n": len(ids),
        "resolved": len(info),
        "ai_ml_nlp_any_category": len(ai),
        "ai_ml_nlp_share_pct": round(100 * len(ai) / len(ids), 1),
        "ai_ml_nlp_primary_only": len(prim_ai),
        "cs_any_category": len(cs),
        "cs_share_pct": round(100 * len(cs) / len(ids), 1),
        "estimated_papers_in_split": round(est_total),
        "estimated_cs_papers_in_split": round(len(cs) / len(ids) * SPLIT_TOTAL),
        "estimated_min_10k_papers_needed_yield": round(len(ai) / len(ids) * 10_000),
        "year_min": min(years),
        "year_max": max(years),
        "year_histogram": dict(sorted(Counter(years).items())),
        "category_counter_top": Counter(
            c for a in ids if a in info for c in info[a]["categories"]
        ).most_common(12),
    }
    out = Path(__file__).parents[1] / "data" / "scientific_papers" / "yield_years_measurement.json"
    out.write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2))
    print(f"\nwrote {out}")


if __name__ == "__main__":
    main()
