"""Tables and the one figure the cohort paper stands on.

Reads what `cielociego cohort` wrote and produces, in order: the cohort
description, the pooled confusion matrix, the same matrix split by parcel size
-- which is the result that turns a case study into a rule -- and the grid of
thresholds that shows the finding was not manufactured by picking a pair of
numbers.

The figure is deliberately one figure. A paper whose argument needs six plots
usually has no argument.

    python tools/cohort_report.py --cohort outputs/cohort_ftw.json
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cielociego.cohort import (
    Observation,
    confusion,
    confusion_by_area,
    sensitivity,
)

ROOT = Path(__file__).resolve().parents[1]


def load(path: Path) -> tuple[list[Observation], list[dict]]:
    doc = json.loads(path.read_text(encoding="utf-8"))
    obs = [
        Observation(
            o["parcel_id"], o["source"], o["country"], o["area_ha"], o["date"],
            o["scene_id"], o["pixels"], o["tile_cloud"], o["blind"], o["blind_wide"],
            o.get("error"),
        )
        for o in doc.get("observations", [])
    ]
    return obs, doc.get("catalog", [])


def wilson(hits: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson interval for a proportion.

    Not the textbook normal interval: with recall near 1 and small strata it
    runs past 1 and stops meaning anything. Wilson stays inside [0, 1] and
    behaves with the handful of parcels the smallest size bin will have.
    """
    if n == 0:
        return (float("nan"), float("nan"))
    p = hits / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def table_cohort(obs: list[Observation], catalog: list[dict]) -> None:
    print("\nTABLE 1 - the cohort")
    print(f"{'country':<16}{'parcels':>9}{'median ha':>12}{'min ha':>10}{'max ha':>10}"
          f"{'acquisitions':>14}")
    by_country: dict[str, list[Observation]] = {}
    for o in obs:
        by_country.setdefault(o.country, []).append(o)
    for country, rows in sorted(by_country.items()):
        areas = sorted({(r.parcel_id, r.area_ha) for r in rows}, key=lambda x: x[1])
        med = areas[len(areas) // 2][1]
        print(f"{country:<16}{len(areas):>9}{med:>12.2f}{areas[0][1]:>10.2f}"
              f"{areas[-1][1]:>10.2f}{len(rows):>14}")
    parcels = {o.parcel_id for o in obs}
    print(f"{'TOTAL':<16}{len(parcels):>9}{'':>12}{'':>10}{'':>10}{len(obs):>14}")

    if catalog:
        ok = [r for r in catalog if not r.get("error")]
        items = sum(r["items"] for r in ok)
        dups = sum(r["duplicates"] for r in ok)
        gaps = [r["cloud_gap_max"] for r in ok if r.get("cloud_gap_max") is not None]
        print(f"\n  catalogue: {items} items, {dups} reprocessing copies "
              f"({100 * dups / items if items else 0:.1f} %), "
              f"{len(catalog) - len(ok)} parcels unreachable")
        if gaps:
            print(f"  largest disagreement in declared cloud between baselines: "
                  f"{max(gaps):.2f} points")


def table_confusion(obs: list[Observation]) -> None:
    m = confusion(obs)
    print(f"\nTABLE 2 - the filter judged against the polygon "
          f"(tile <= {m.tile_threshold:.0%}, usable at blind <= {m.blind_limit:.0%})")
    print(f"  kept and useful    {m.kept_useful:>7}")
    print(f"  kept but blind     {m.kept_useless:>7}   false positive")
    print(f"  dropped yet clear  {m.dropped_useful:>7}   false negative")
    print(f"  dropped and blind  {m.dropped_useless:>7}")
    print(f"  rows set aside     {m.unusable_rows:>7}   unreadable or without metadata")
    lo, hi = wilson(m.kept_useful, m.kept_useful + m.dropped_useful)
    print(f"  recall             {m.recall:>7.3f}   95 % CI [{lo:.3f}, {hi:.3f}]")
    print(f"  asymmetry          {m.asymmetry:>7.1f}   false negatives per false positive")


def table_by_area(obs: list[Observation]) -> list[tuple[str, float, float, float, int]]:
    print("\nTABLE 3 - by parcel size (the rule)")
    print(f"{'size':>14}{'n':>8}{'recall':>9}{'95 % CI':>18}{'FN':>7}{'FP':>6}{'asym':>8}")
    points = []
    for label, c in confusion_by_area(obs):
        if not c.total:
            continue
        useful = c.kept_useful + c.dropped_useful
        lo, hi = wilson(c.kept_useful, useful)
        print(f"{label:>14}{c.total:>8}{c.recall:>9.3f}"
              f"{f'[{lo:.3f}, {hi:.3f}]':>18}{c.dropped_useful:>7}{c.kept_useless:>6}"
              f"{c.asymmetry:>8.1f}")
        points.append((label, c.recall, lo, hi, c.total))
    return points


def table_sensitivity(obs: list[Observation]) -> None:
    print("\nTABLE 4 - sensitivity to both thresholds")
    print(f"{'tile filter':>12}{'blind limit':>13}{'FN':>8}{'FP':>7}{'recall':>9}{'asym':>8}")
    for c in sensitivity(obs):
        print(f"{c.tile_threshold:>11.0%}{c.blind_limit:>13.0%}{c.dropped_useful:>8}"
              f"{c.kept_useless:>7}{c.recall:>9.3f}{c.asymmetry:>8.1f}")


def figure(points, out: Path) -> Path | None:
    """Recall of the metadata filter against parcel size, with its interval."""
    if not points:
        return None
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = [p[0] for p in points]
    recall = [p[1] for p in points]
    lo = [p[1] - p[2] for p in points]
    hi = [p[3] - p[1] for p in points]

    fig, ax = plt.subplots(figsize=(7.2, 4.0))
    x = range(len(points))
    ax.errorbar(x, recall, yerr=[lo, hi], fmt="o-", color="#1d4ed8",
                ecolor="#1d4ed8", elinewidth=1.2, capsize=4, markersize=6, linewidth=1.6)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=0)
    ax.set_ylim(0, 1)
    ax.set_ylabel("share of usable acquisitions the filter keeps")
    ax.set_xlabel("parcel size")
    ax.grid(axis="y", alpha=0.25, linewidth=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)
    for xi, (_, r, _, _, n) in zip(x, points, strict=True):
        ax.annotate(f"n={n}", (xi, r), textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=8, color="#555")
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, format="svg")
    plt.close(fig)
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--cohort", type=Path, required=True, help="outputs/cohort_<name>.json")
    ap.add_argument("--figure", type=Path, default=ROOT / "outputs" / "fig_recall_vs_size.svg")
    args = ap.parse_args()

    obs, catalog = load(args.cohort)
    if not obs:
        print("no optical observations in this file: run the cohort with --cap")
        table_cohort([], catalog)
        return 1

    table_cohort(obs, catalog)
    table_confusion(obs)
    points = table_by_area(obs)
    table_sensitivity(obs)
    path = figure(points, args.figure)
    if path:
        print(f"\nfigure written to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
