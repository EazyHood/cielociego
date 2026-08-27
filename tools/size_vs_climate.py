"""Is it the size of the parcel, or the sky above it?

The stratified table shows recall rising with parcel size, and then falling in
the largest bin -- which happens to hold a single parcel in the wet tropics.
With one parcel per extreme, size and climate are confounded, and reporting the
trend as a size effect would be exactly the mistake this paper documents in the
use of the metadata.

So the two are separated the only way they can be separated from a desk: with a
model that carries both. The response is whether the acquisition was usable over
the parcel; the predictors are the cloud the tile declares (which stands for the
sky that day), the logarithm of the parcel area, and their interaction. The
interaction is the term that matters. If it is not distinguishable from zero,
the honest sentence is that this cohort does not resolve a size effect once the
sky is accounted for -- and that sentence is worth more than a trend line drawn
through two confounded points.

Logistic regression by iteratively reweighted least squares, in numpy: the
project keeps its dependencies short and this is twenty lines. Standard errors
from the inverse of the information matrix at convergence.

    python tools/size_vs_climate.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cielociego.cohort import DEFAULT_BLIND_LIMIT, Observation
from cielociego.scl import MIN_PIXELS

ROOT = Path(__file__).resolve().parents[1]


def logistic(X: np.ndarray, y: np.ndarray, iters: int = 60, tol: float = 1e-10):
    """IRLS. Returns (coefficients, standard errors, iterations, converged)."""
    beta = np.zeros(X.shape[1])
    for it in range(1, iters + 1):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-9, None)
        z = eta + (y - mu) / w
        XtW = X.T * w
        # Ridge of 1e-8 only to keep the solve well posed; it does not move the
        # estimates at this sample size and it stops a separated cell from
        # blowing the matrix up.
        A = XtW @ X + 1e-8 * np.eye(X.shape[1])
        new = np.linalg.solve(A, XtW @ z)
        if np.max(np.abs(new - beta)) < tol:
            beta = new
            cov = np.linalg.inv(A)
            return beta, np.sqrt(np.diag(cov)), it, True
        beta = new
    eta = np.clip(X @ beta, -30, 30)
    mu = 1.0 / (1.0 + np.exp(-eta))
    w = np.clip(mu * (1 - mu), 1e-9, None)
    A = (X.T * w) @ X + 1e-8 * np.eye(X.shape[1])
    return beta, np.sqrt(np.diag(np.linalg.inv(A))), iters, False


def load() -> list[Observation]:
    doc = json.loads((ROOT / "outputs" / "cohort_ftw.json").read_text(encoding="utf-8"))
    return [
        Observation(
            o["parcel_id"], o["source"], o["country"], o["area_ha"], o["date"],
            o["scene_id"], o["pixels"], o["tile_cloud"], o["blind"], o["blind_wide"],
            o.get("error"),
        )
        for o in doc["observations"]
    ]


def report(names, beta, se) -> None:
    print(f"{'term':<28}{'coef':>10}{'s.e.':>10}{'z':>9}{'p':>10}{'95 % CI':>24}")
    for n, b, s in zip(names, beta, se, strict=True):
        z = b / s if s else float("nan")
        # Two-sided normal p-value without scipy.
        p = math.erfc(abs(z) / math.sqrt(2))
        lo, hi = b - 1.96 * s, b + 1.96 * s
        star = " *" if p < 0.05 else ""
        print(f"{n:<28}{b:>10.4f}{s:>10.4f}{z:>9.2f}{p:>10.4f}"
              f"{f'[{lo:+.4f}, {hi:+.4f}]':>24}{star}")


def main() -> int:
    obs = [
        o for o in load()
        if not o.error and o.tile_cloud is not None and o.pixels >= MIN_PIXELS
        and o.blind == o.blind
    ]
    y = np.array([1.0 if o.blind <= DEFAULT_BLIND_LIMIT else 0.0 for o in obs])
    tile = np.array([o.tile_cloud / 100.0 for o in obs])
    logarea = np.log10(np.array([o.area_ha for o in obs]))

    # Centred so the main effects read at the middle of the cohort instead of
    # at zero hectares and a cloudless sky, neither of which exists here.
    tile_c = tile - tile.mean()
    area_c = logarea - logarea.mean()

    print(f"n = {len(obs)} rows, {int(y.sum())} usable over the parcel")
    print(f"tile cloud: mean {tile.mean():.3f}, sd {tile.std():.3f}")
    print(f"log10 area: mean {logarea.mean():.3f} "
          f"({10 ** logarea.mean():.2f} ha), sd {logarea.std():.3f}\n")

    X = np.column_stack([np.ones(len(obs)), tile_c, area_c, tile_c * area_c])
    beta, se, it, ok = logistic(X, y)
    print(f"P(usable over the parcel) ~ tile cloud + log10 area + interaction "
          f"[IRLS, {it} iterations, converged={ok}]")
    report(["intercept", "tile cloud (0-1)", "log10 area (ha)",
            "tile cloud x log10 area"], beta, se)

    print("\nSame model without the interaction, for comparison:")
    X2 = np.column_stack([np.ones(len(obs)), tile_c, area_c])
    beta2, se2, _, _ = logistic(X2, y)
    report(["intercept", "tile cloud (0-1)", "log10 area (ha)"], beta2, se2)

    # Odds ratio for a tenfold increase in area, at average cloudiness.
    orr = math.exp(beta2[2])
    lo = math.exp(beta2[2] - 1.96 * se2[2])
    hi = math.exp(beta2[2] + 1.96 * se2[2])
    print(f"\nOdds ratio for a tenfold larger parcel, at mean tile cloud: "
          f"{orr:.3f}  95 % CI [{lo:.3f}, {hi:.3f}]")
    if lo <= 1.0 <= hi:
        print("The interval covers 1: this cohort does not resolve a size effect once")
        print("the sky is accounted for.")
    elif hi < 1.0:
        print("Below 1, and the interval excludes it: with the sky held constant, a")
        print("LARGER parcel is LESS likely to be entirely clear. Geometrically that is")
        print("what one should expect -- more ground is more chance of meeting a cloud --")
        print("and it runs opposite to the raw stratified recall, which is unadjusted.")
    else:
        print("Above 1, and the interval excludes it: larger parcels are more often clear.")

    # The question the paper actually asks, put directly: among the acquisitions
    # the filter THROWS AWAY, does the chance that the parcel was in fact clear
    # depend on its size? That is the false-negative rate as a function of area,
    # holding the declared cloud constant. Asking it on the rejected subset
    # avoids the degeneracy of conditioning on the very quantity the filter uses.
    print("\n" + "=" * 74)
    print("Among the acquisitions the filter REJECTS: was the parcel clear anyway?")
    rej = [i for i in range(len(obs)) if tile[i] > 0.10]
    yr = y[rej]
    tr = tile[rej] - tile[rej].mean()
    ar = logarea[rej] - logarea[rej].mean()
    print(f"n = {len(rej)} rejected rows, {int(yr.sum())} of them false negatives "
          f"({100 * yr.mean():.1f} %)")
    Xr = np.column_stack([np.ones(len(rej)), tr, ar])
    br, sr, _, _ = logistic(Xr, yr)
    report(["intercept", "tile cloud (0-1)", "log10 area (ha)"], br, sr)
    orr2 = math.exp(br[2])
    lo2, hi2 = math.exp(br[2] - 1.96 * sr[2]), math.exp(br[2] + 1.96 * sr[2])
    print(f"\nOdds of a rejected acquisition being a false negative, per tenfold "
          f"larger parcel: {orr2:.3f}  95 % CI [{lo2:.3f}, {hi2:.3f}]")
    if lo2 <= 1.0 <= hi2:
        print("The interval covers 1. This cohort DOES NOT resolve a dependence of the")
        print("false-negative rate on parcel size once the declared cloud is held")
        print("constant, and the paper must say so instead of drawing the trend line.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
