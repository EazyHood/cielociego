"""Reprocessing duplicates across the whole cohort, year by year.

The manuscript reports the duplication step -- above 44 % of items in 2019-2021,
below 3 % from 2022 -- from a single tile in the Colombian Caribbean, and then
draws a general prescription from it. A reviewer was right to object: one tile
does not license "any time series reaching before 2022".

The fix costs almost nothing, because counting duplicates needs no pixels. The
same catalogue query that the cohort already runs, widened to the full archive,
turns an anecdote from one tile into a multi-country measurement.

    python tools/duplication_by_year.py --start 2019-01-01 --end 2026-08-27
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cielociego.catalog import S2_L2A, search
from cielociego.cohort import load_cohort
from cielociego.dedup import deduplicate
from cielociego.net import session as _session

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--start", default="2019-01-01")
    ap.add_argument("--end", default="2026-08-27")
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    parcels = load_cohort(ROOT / "data" / "cohorts" / "ftw.geojson")
    ses = _session()
    print(f"{len(parcels)} parcels, {args.start} to {args.end}")

    # Counting per tile-year rather than per parcel-year: parcels that share a
    # tile would otherwise count the same copies several times and inflate the
    # totals. The unit of the claim is the archive, not the field.
    seen: dict[str, dict] = {}
    failed = 0

    def one(parcel):
        try:
            return search(S2_L2A, parcel.geometry.bounds, args.start, args.end,
                          session=ses).items
        except Exception:
            return None

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        for n, items in enumerate(pool.map(one, parcels), 1):
            if items is None:
                failed += 1
                continue
            for it in items:
                seen[it.get("id", "")] = it
            if n % 40 == 0:
                print(f"  {n}/{len(parcels)} parcels, {len(seen)} distinct items")

    print(f"\n{len(seen)} distinct catalogue items, {failed} parcels unreachable")

    by_year: dict[str, list] = defaultdict(list)
    for it in seen.values():
        by_year[it["properties"]["datetime"][:4]].append(it)

    print(f"\n{'year':>6}{'items':>10}{'unique':>10}{'copies':>9}{'% copies':>11}")
    rows = []
    ti = tc = 0
    for year in sorted(by_year):
        kept, dropped = deduplicate(by_year[year])
        n, c = len(by_year[year]), len(dropped)
        ti += n
        tc += c
        rows.append({"year": year, "items": n, "unique": len(kept), "copies": c,
                     "pct": 100 * c / n if n else 0.0})
        print(f"{year:>6}{n:>10}{len(kept):>10}{c:>9}{100 * c / n:>10.1f}%")
    print(f"{'TOTAL':>6}{ti:>10}{'':>10}{tc:>9}{100 * tc / ti:>10.1f}%")

    out = ROOT / "outputs" / "duplication_by_year.json"
    out.write_text(json.dumps({
        "start": args.start, "end": args.end,
        "parcels": len(parcels), "unreachable": failed,
        "distinct_items": len(seen), "by_year": rows,
    }, indent=1), encoding="utf-8")
    print(f"\nwritten to {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
