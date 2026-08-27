"""Which filter should someone working at field scale actually use?

Section 5.2 of the paper cannot end at "the tile metadata is biased". A reader
needs to know what to do instead, and the honest way to answer that is to put
every alternative that costs nothing in the same table as the one that costs a
read, and let the numbers choose.

Four candidates, all available without leaving the catalogue response:

* `eo:cloud_cover` -- the baseline, the field everyone filters on.
* `s2:high_proba_clouds_percentage` -- only the confident cloud.
* opaque cloud = high + medium probability + thin cirrus.
* the tile-level analogue of the definition this work uses on the parcel:
  opaque cloud + cloud shadow + no-data + saturated or defective. Same classes,
  same arithmetic, only computed over the tile instead of the polygon. If this
  one wins, the problem was never the classification -- it was the support.

And one that costs a windowed read: the fraction clipped to the polygon.

Two numbers per candidate, because one is not enough:

* **AUC.** How well the score ranks usable acquisitions above unusable ones,
  independent of any threshold. A threshold-free number stops the discussion
  about whether the thresholds were picked to suit.
* **Recall at a matched false-positive budget.** Thresholds are not comparable
  across scores with different units, so each candidate is set to the threshold
  that admits the same number of unusable acquisitions as the baseline does,
  and then they are compared on how many usable ones they recover. Same cost in
  wasted processing, different yield.

    python tools/filter_alternatives.py
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cielociego.catalog import S2_L2A, search
from cielociego.cohort import (
    DEFAULT_BLIND_LIMIT,
    DEFAULT_TILE_FILTER,
    Observation,
    load_cohort,
)
from cielociego.net import session as _session
from cielociego.scl import MIN_PIXELS

ROOT = Path(__file__).resolve().parents[1]

# Every candidate is a *score*: lower means cleaner. Each is a list of the
# catalogue fields to add up.
CANDIDATES: dict[str, list[str]] = {
    "eo:cloud_cover": ["eo:cloud_cover"],
    "high_proba": ["s2:high_proba_clouds_percentage"],
    "opaque+cirrus": [
        "s2:high_proba_clouds_percentage",
        "s2:medium_proba_clouds_percentage",
        "s2:thin_cirrus_percentage",
    ],
    "same_classes_as_parcel": [
        "s2:high_proba_clouds_percentage",
        "s2:medium_proba_clouds_percentage",
        "s2:thin_cirrus_percentage",
        "s2:cloud_shadow_percentage",
        "s2:nodata_pixel_percentage",
        "s2:saturated_defective_pixel_percentage",
    ],
    "no_nodata": [
        "s2:high_proba_clouds_percentage",
        "s2:medium_proba_clouds_percentage",
        "s2:thin_cirrus_percentage",
        "s2:cloud_shadow_percentage",
    ],
}


def auc(scores: list[float], positive: list[bool]) -> float:
    """Area under the ROC curve, from ranks. Ties get their mean rank.

    Written out rather than imported: the project keeps its dependency list
    short on purpose, and the Mann-Whitney identity is four lines.
    """
    n_pos = sum(positive)
    n_neg = len(positive) - n_pos
    if not n_pos or not n_neg:
        return float("nan")
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    ranks = [0.0] * len(scores)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and scores[order[j + 1]] == scores[order[i]]:
            j += 1
        mean_rank = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = mean_rank
        i = j + 1
    # A *low* score should mean usable, so the positive class is expected to
    # hold the low ranks; the identity is flipped accordingly.
    sum_pos = sum(r for r, pos in zip(ranks, positive, strict=True) if pos)
    u = sum_pos - n_pos * (n_pos + 1) / 2.0
    return 1.0 - u / (n_pos * n_neg)


def recall_at_fp_budget(
    scores: list[float], positive: list[bool], budget: int
) -> tuple[float, float, int]:
    """Highest threshold whose false positives do not exceed `budget`.

    Returns (recall, threshold, true positives kept).
    """
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    n_pos = sum(positive)
    tp = fp = 0
    best = (0.0, float("nan"), 0)
    for idx in order:
        if positive[idx]:
            tp += 1
        else:
            fp += 1
            if fp > budget:
                break
        if fp <= budget:
            best = (tp / n_pos if n_pos else float("nan"), scores[idx], tp)
    return best


def fp_cost_for_recall(scores, positive, targets=(0.60, 0.75, 0.90, 0.95)):
    """How many false positives each level of recall costs.

    This is the number the recommendation hangs on. A ranking can be good --
    the baseline reaches AUC 0.94 -- and still be unusable at the operating
    point a practitioner needs, because buying the last half of the usable
    acquisitions costs an amount of wasted processing nobody would accept.
    """
    order = sorted(range(len(scores)), key=lambda i: scores[i])
    n_pos = sum(positive)
    out, tp, fp = [], 0, 0
    hit = 0
    for idx in order:
        if positive[idx]:
            tp += 1
        else:
            fp += 1
        while hit < len(targets) and n_pos and tp / n_pos >= targets[hit]:
            out.append((targets[hit], fp, scores[idx]))
            hit += 1
    while hit < len(targets):
        out.append((targets[hit], None, None))
        hit += 1
    return out


def load_observations() -> list[Observation]:
    path = ROOT / "outputs" / "cohort_ftw.json"
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [
        Observation(
            o["parcel_id"], o["source"], o["country"], o["area_ha"], o["date"],
            o["scene_id"], o["pixels"], o["tile_cloud"], o["blind"], o["blind_wide"],
            o.get("error"),
        )
        for o in doc["observations"]
    ]


def scene_properties(parcels, start: str, end: str) -> dict[str, dict]:
    """Every catalogue field of every scene the cohort touches, by scene id."""
    from concurrent.futures import ThreadPoolExecutor

    ses = _session()
    props: dict[str, dict] = {}

    def one(parcel):
        try:
            return search(S2_L2A, parcel.geometry.bounds, start, end, session=ses).items
        except Exception:
            return []

    with ThreadPoolExecutor(max_workers=8) as pool:
        for items in pool.map(one, parcels):
            for it in items:
                props[it.get("id", "")] = it.get("properties", {})
    return props


def score_of(props: dict, fields: list[str]) -> float | None:
    total = 0.0
    for f in fields:
        v = props.get(f)
        if v is None:
            return None
        total += float(v)
    return total


def main() -> int:
    print("reading the measured cohort")
    obs = load_observations()
    usable = [
        o for o in obs
        if not o.error and o.tile_cloud is not None and o.pixels >= MIN_PIXELS
        and o.blind == o.blind  # not NaN
    ]
    print(f"  {len(obs)} rows, {len(usable)} above the pixel floor and readable")

    parcels = load_cohort(ROOT / "data" / "cohorts" / "ftw.geojson")
    print(f"re-querying the catalogue for the extra fields ({len(parcels)} parcels)")
    t0 = time.time()
    props = scene_properties(parcels, "2023-01-01", "2024-12-31")
    print(f"  {len(props)} scenes, {time.time() - t0:.0f}s")

    rows = [(o, props.get(o.scene_id)) for o in usable]
    rows = [(o, p) for o, p in rows if p]
    print(f"  {len(rows)} rows joined to their catalogue entry")

    positive = [o.blind <= DEFAULT_BLIND_LIMIT for o, _ in rows]
    print(f"  {sum(positive)} usable over the parcel, {len(positive) - sum(positive)} not")

    # The baseline's own operating point sets the budget everyone must match.
    base = [score_of(p, CANDIDATES["eo:cloud_cover"]) for _, p in rows]
    fp_budget = sum(
        1 for s, pos in zip(base, positive, strict=True)
        if s is not None and s / 100.0 <= DEFAULT_TILE_FILTER and not pos
    )
    base_tp = sum(
        1 for s, pos in zip(base, positive, strict=True)
        if s is not None and s / 100.0 <= DEFAULT_TILE_FILTER and pos
    )
    print(f"\nbaseline at {DEFAULT_TILE_FILTER:.0%}: {base_tp} true positives, "
          f"{fp_budget} false positives -- that is the budget everyone matches")

    print(f"\n{'candidate':<26}{'AUC':>8}{'recall@budget':>16}{'threshold':>12}{'TP':>8}")
    results = {}
    for name, fields in CANDIDATES.items():
        pairs = [
            (score_of(p, fields), pos)
            for (o, p), pos in zip(rows, positive, strict=True)
        ]
        pairs = [(s, pos) for s, pos in pairs if s is not None]
        if len(pairs) < len(rows) * 0.9:
            print(f"{name:<26}{'-- field missing in ' + str(len(rows) - len(pairs)) + ' rows':>44}")
            continue
        s = [x for x, _ in pairs]
        y = [b for _, b in pairs]
        a = auc(s, y)
        r, thr, tp = recall_at_fp_budget(s, y, fp_budget)
        results[name] = (a, r, thr, tp)
        print(f"{name:<26}{a:>8.3f}{r:>16.3f}{thr:>12.2f}{tp:>8}")

    # The one that costs a read.
    s_parcel = [o.blind * 100.0 for o, _ in rows]
    a = auc(s_parcel, positive)
    r, thr, tp = recall_at_fp_budget(s_parcel, positive, fp_budget)
    print(f"{'clipped to the polygon':<26}{a:>8.3f}{r:>16.3f}{thr:>12.2f}{tp:>8}")
    print("  (perfect by construction: it is the reference. Listed for the cost, not the score)")

    print("\nWhat each level of recall costs in false positives, with the best free score:")
    best_name = max(results.items(), key=lambda kv: kv[1][0])[0]
    pairs = [
        (score_of(p, CANDIDATES[best_name]), pos)
        for (o, p), pos in zip(rows, positive, strict=True)
    ]
    pairs = [(x, y) for x, y in pairs if x is not None]
    sb = [x for x, _ in pairs]
    yb = [y for _, y in pairs]
    n_pos = sum(yb)
    print(f"  score: {best_name}   usable acquisitions in play: {n_pos}")
    print(f"{'recall':>10}{'false positives':>18}{'threshold':>12}{'wasted per gained':>20}")
    prev_tp, prev_fp = base_tp, fp_budget
    for target, fp, thr in fp_cost_for_recall(sb, yb):
        if fp is None:
            print(f"{target:>10.0%}{'unreachable':>18}")
            continue
        gained = target * n_pos - prev_tp
        waste = (fp - prev_fp) / gained if gained > 0 else float("nan")
        print(f"{target:>10.0%}{fp:>18}{thr:>12.2f}{waste:>20.1f}")

    best = max(results.items(), key=lambda kv: kv[1][1])
    gain = best[1][3] - base_tp
    print(f"\nbest free candidate: {best[0]} -- recovers {gain} usable acquisitions "
          f"more than the baseline at the same cost in false positives "
          f"({100 * gain / base_tp:+.1f} %)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
