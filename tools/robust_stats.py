"""The intervals, recomputed without pretending the rows are independent.

An expert review of the manuscript landed on the same objection three times, and
it is correct: every interval and every p-value in the paper was computed as if
the 3,265 parcel-acquisition pairs were independent Bernoulli trials. They are
not. They come from 323 parcels, each contributing up to sixteen acquisitions
that share a sky, a tile and a geometry, and from a smaller number of dates that
cut across parcels. Worse, in the size model the predictor of interest -- the
area -- is *constant within a parcel*, which is precisely the case where naive
standard errors are most anti-conservative. The effective sample size is closer
to the number of parcels than to the number of rows.

So everything gets recomputed three ways:

* **Cluster bootstrap by parcel** for recall and for the asymmetry. Parcels are
  resampled whole, with replacement; the statistic is recomputed on each
  replicate. That is the honest interval for a quantity read off grouped data.
* **Cluster-robust sandwich** for the logistic model, grouped by parcel, with
  the usual small-sample correction. If the size term stops excluding one, the
  paper says so and changes the claim.
* **Exact Poisson interval on the twelve false positives** that the asymmetry
  divides by. A ratio quoted to three significant figures over twelve events is
  a precision the data does not have.

Plus the control the review asked for and that the manuscript owes: a mechanism
that would produce the same size signal without any change of support. The
reference fraction is estimated from a finite number of pixels and then
binarised at U, so its sampling variance grows as the parcel shrinks. If the
size term survives among parcels large enough for that variance to be
negligible, the mechanical explanation is weakened; if it does not, the paper
cannot claim the effect.

    python tools/robust_stats.py
"""
from __future__ import annotations

import json
import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cielociego.cohort import (
    DEFAULT_BLIND_LIMIT,
    DEFAULT_TILE_FILTER,
    Observation,
)
from cielociego.scl import MIN_PIXELS

ROOT = Path(__file__).resolve().parents[1]
REPLICATES = 2000
RNG_SEED = 20260827  # fixed and declared: the bootstrap must be reproducible


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


def evaluable(obs: list[Observation], min_pixels: int = MIN_PIXELS) -> list[Observation]:
    return [
        o for o in obs
        if not o.error and o.tile_cloud is not None and o.pixels >= min_pixels
        and o.blind == o.blind
    ]


def cells(rows: list[Observation]) -> tuple[int, int, int, int]:
    tp = fp = fn = tn = 0
    for o in rows:
        kept = o.tile_cloud / 100.0 <= DEFAULT_TILE_FILTER
        useful = o.blind <= DEFAULT_BLIND_LIMIT
        if kept and useful:
            tp += 1
        elif kept:
            fp += 1
        elif useful:
            fn += 1
        else:
            tn += 1
    return tp, fp, fn, tn


def cluster_bootstrap(rows: list[Observation], key) -> dict:
    """Resample whole clusters and recompute recall and asymmetry."""
    groups: dict[str, list[Observation]] = {}
    for o in rows:
        groups.setdefault(key(o), []).append(o)
    names = list(groups)
    rng = np.random.default_rng(RNG_SEED)

    recalls, asyms = [], []
    for _ in range(REPLICATES):
        pick = rng.integers(0, len(names), len(names))
        sample: list[Observation] = []
        for i in pick:
            sample.extend(groups[names[i]])
        tp, fp, fn, _ = cells(sample)
        if tp + fn:
            recalls.append(tp / (tp + fn))
        if fp:
            asyms.append(fn / fp)
    return {
        "clusters": len(names),
        "recall": (float(np.percentile(recalls, 2.5)), float(np.percentile(recalls, 97.5))),
        "asymmetry": (float(np.percentile(asyms, 2.5)), float(np.percentile(asyms, 97.5))),
        "asym_replicates_with_zero_fp": REPLICATES - len(asyms),
    }


def poisson_ci(k: int, alpha: float = 0.05) -> tuple[float, float]:
    """Exact (Garwood) interval for a count, from the chi-square quantiles.

    Implemented through the regularised incomplete gamma function by bisection:
    the project does not carry scipy, and a two-sided interval on one count does
    not justify adding it.
    """
    def gamma_cdf(x: float, k_shape: float) -> float:
        # Series expansion of P(k, x); adequate for the small k used here.
        if x <= 0:
            return 0.0
        term = 1.0 / k_shape
        total = term
        n = 1
        while n < 10000:
            term *= x / (k_shape + n)
            total += term
            if term < 1e-14 * total:
                break
            n += 1
        return total * math.exp(-x + k_shape * math.log(x) - math.lgamma(k_shape))

    def solve(target: float, shape: float, upper: bool) -> float:
        lo, hi = 0.0, max(10.0, 4.0 * shape + 20.0)
        for _ in range(200):
            mid = (lo + hi) / 2
            val = 1.0 - gamma_cdf(mid, shape) if upper else gamma_cdf(mid, shape)
            if val < target:
                lo, hi = (mid, hi) if upper else (lo, mid)
            else:
                lo, hi = (lo, mid) if upper else (mid, hi)
        return (lo + hi) / 2

    low = 0.0 if k == 0 else solve(alpha / 2, float(k), upper=True)
    high = solve(alpha / 2, float(k + 1), upper=False)
    return low, high


def logistic_cluster(X: np.ndarray, y: np.ndarray, groups: np.ndarray):
    """Logistic fit with a cluster-robust sandwich covariance.

    Point estimates are the usual maximum likelihood; only the covariance
    changes. The correction factor is the standard G/(G-1) x (N-1)/(N-K).
    """
    beta = np.zeros(X.shape[1])
    for _ in range(80):
        eta = np.clip(X @ beta, -30, 30)
        mu = 1.0 / (1.0 + np.exp(-eta))
        w = np.clip(mu * (1 - mu), 1e-9, None)
        z = eta + (y - mu) / w
        A = (X.T * w) @ X + 1e-9 * np.eye(X.shape[1])
        new = np.linalg.solve(A, (X.T * w) @ z)
        if np.max(np.abs(new - beta)) < 1e-11:
            beta = new
            break
        beta = new

    eta = np.clip(X @ beta, -30, 30)
    mu = 1.0 / (1.0 + np.exp(-eta))
    w = np.clip(mu * (1 - mu), 1e-9, None)
    bread = np.linalg.inv((X.T * w) @ X + 1e-9 * np.eye(X.shape[1]))
    resid = y - mu

    meat = np.zeros((X.shape[1], X.shape[1]))
    uniq = np.unique(groups)
    for g in uniq:
        m = groups == g
        s = (X[m] * resid[m][:, None]).sum(axis=0)
        meat += np.outer(s, s)
    n, k, G = len(y), X.shape[1], len(uniq)
    corr = (G / (G - 1)) * ((n - 1) / (n - k))
    cov = bread @ (meat * corr) @ bread
    naive = np.sqrt(np.diag(bread))
    return beta, np.sqrt(np.diag(cov)), naive, G


def show(names, beta, se, label) -> None:
    print(f"\n  {label}")
    print(f"  {'term':<26}{'coef':>10}{'s.e.':>10}{'z':>8}{'p':>9}{'95 % CI':>22}")
    for nm, b, s in zip(names, beta, se, strict=True):
        z = b / s
        p = math.erfc(abs(z) / math.sqrt(2))
        print(f"  {nm:<26}{b:>10.4f}{s:>10.4f}{z:>8.2f}{p:>9.4f}"
              f"{f'[{b - 1.96 * s:+.4f}, {b + 1.96 * s:+.4f}]':>22}")


def size_model(rows: list[Observation], title: str) -> None:
    rej = [o for o in rows if o.tile_cloud / 100.0 > DEFAULT_TILE_FILTER]
    if len(rej) < 100:
        print(f"\n{title}: solo {len(rej)} filas rechazadas, no se ajusta")
        return
    y = np.array([1.0 if o.blind <= DEFAULT_BLIND_LIMIT else 0.0 for o in rej])
    tile = np.array([o.tile_cloud / 100.0 for o in rej])
    area = np.log10(np.array([o.area_ha for o in rej]))
    groups = np.array([o.parcel_id for o in rej])
    X = np.column_stack([np.ones(len(rej)), tile - tile.mean(), area - area.mean()])

    beta, robust, naive, G = logistic_cluster(X, y, groups)
    print(f"\n{title}")
    print(f"  n = {len(rej)} filas rechazadas en {G} parcelas, "
          f"{int(y.sum())} falsos negativos ({100 * y.mean():.1f} %)")
    names = ["constante", "nubosidad tesela", "log10 superficie"]
    show(names, beta, naive, "errores ingenuos (independencia)")
    show(names, beta, robust, "errores agrupados por parcela (sandwich, CR1)")
    orr = math.exp(beta[2])
    lo, hi = math.exp(beta[2] - 1.96 * robust[2]), math.exp(beta[2] + 1.96 * robust[2])
    verdict = "SIGUE excluyendo el 1" if hi < 1 or lo > 1 else "YA NO excluye el 1"
    print(f"  razon de probabilidades por x10 de superficie: {orr:.3f} "
          f"IC robusto [{lo:.3f}, {hi:.3f}]  ->  {verdict}")


def main() -> int:
    obs = load()
    rows = evaluable(obs)
    tp, fp, fn, tn = cells(rows)
    print(f"filas evaluables: {len(rows)}  (de {len(obs)} medidas)")
    print(f"matriz: TP {tp}  FP {fp}  FN {fn}  TN {tn}  -> suma {tp + fp + fn + tn}")
    print(f"exhaustividad puntual: {tp / (tp + fn):.4f}   asimetria: {fn / fp:.1f}")

    lo, hi = poisson_ci(fp)
    print(f"\nlos {fp} falsos positivos, intervalo de Poisson 95 %: [{lo:.2f}, {hi:.2f}]")
    print(f"  -> la asimetria queda entre {fn / hi:.0f} y {fn / lo:.0f} solo por esa via")

    print(f"\nbootstrap por conglomerados, {REPLICATES} replicas, semilla {RNG_SEED}")
    for label, key in (("parcela", lambda o: o.parcel_id), ("fecha", lambda o: o.date)):
        b = cluster_bootstrap(rows, key)
        print(f"  agrupando por {label:<8} ({b['clusters']:>4} grupos): "
              f"exhaustividad IC [{b['recall'][0]:.3f}, {b['recall'][1]:.3f}]   "
              f"asimetria IC [{b['asymmetry'][0]:.1f}, {b['asymmetry'][1]:.1f}]")
    print("  (comparar con el intervalo binomial publicado: [0,420, 0,480])")

    size_model(rows, "MODELO DE TAMANO -- todas las parcelas sobre el suelo de 25 pixeles")

    # The control the review asked for: if the size term is an artefact of the
    # reference fraction being noisier on small parcels, it should weaken or
    # vanish among parcels where that noise is negligible.
    big = evaluable(obs, min_pixels=100)
    size_model(big, "CONTROL -- solo parcelas con >= 100 pixeles (>= 4 ha)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
