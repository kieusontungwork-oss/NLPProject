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
    df = pd.DataFrame(rows)
    for col in df.columns[df.dtypes == object]:
        types = {type(v) for v in df[col] if v is not None and not isinstance(v, (list, dict, tuple, set))}
        if len(types) > 1:
            df[col] = df[col].astype("string")
    df.to_parquet(out, index=False)
    print(f"wrote {len(rows):,} rows -> {out} ({time.time() - t0:.0f}s total)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="repo-relative path, e.g. raw/review_categories/Electronics.jsonl")
    ap.add_argument("--n", type=int, required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--start-byte", type=int, default=0)
    args = ap.parse_args()
    stream_jsonl_to_parquet(args.path, args.n, args.out, args.start_byte)
