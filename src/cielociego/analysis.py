"""Trend and change-shape of a time series.

Two things this exists to avoid: quoting a slope without saying what it is worth,
and fitting a straight line to something that is not one. Standard errors are
Newey-West; four candidate shapes are compared by BIC, each charged for the
breakpoints it searches.

See DECISIONS.md #11.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np


@dataclass
class Trend:
    """Slope of a series, with the uncertainty computed honestly."""

    slope: float             # y-units per year
    se_classic: float        # standard error assuming independence (optimistic)
    se_hac: float            # standard error robust to autocorrelation
    ic95: tuple[float, float]
    n: int
    n_effective: float       # genuinely independent observations
    residual_autocorr: float

    @property
    def inflation(self) -> float:
        """How far off the classical standard error was."""
        return self.se_hac / self.se_classic if self.se_classic else float("nan")

    @property
    def significant(self) -> bool:
        """The 95 % interval does not cross zero."""
        return self.ic95[0] * self.ic95[1] > 0

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ic95"] = list(self.ic95)
        d["inflacion_ee"] = round(self.inflation, 3)
        d["significant"] = self.significant
        return d


@dataclass
class Model:
    name: str
    sse: float
    k: int          # parametros efectivos, INCLUYENDO los cortes buscados
    bic: float
    cut: str | None = None
    cut_end: str | None = None
    level_before: float | None = None
    level_after: float | None = None

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _years(dates: Sequence[str]) -> np.ndarray:
    o = np.array([date.fromisoformat(f).toordinal() for f in dates], dtype=float)
    return (o - o[0]) / 365.25


def hac_trend(dates: Sequence[str], values: Sequence[float]) -> Trend:
    """Pendiente por ano con error estandar robusto a autocorrelacion.

    El ancho de banda de Newey-West sale de la regla habitual de Andrews,
    `4*(n/100)^(2/9)`, para no elegirlo a dedo.
    """
    t = _years(dates)
    y = np.asarray(values, dtype=float)
    n = len(y)
    if n < 3:
        raise ValueError("hacen falta al menos 3 observaciones para una tendencia")

    t = t - t.mean()
    X = np.column_stack([np.ones(n), t])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b

    XtXi = np.linalg.inv(X.T @ X)
    se_classic = float(np.sqrt((res**2).sum() / (n - 2) * XtXi[1, 1]))

    u = res[:, None] * X
    S = u.T @ u
    L = max(1, int(np.floor(4 * (n / 100) ** (2 / 9))))
    for lag in range(1, min(L, n - 1) + 1):
        G = u[lag:].T @ u[:-lag]
        S = S + (1 - lag / (L + 1)) * (G + G.T)
    se_hac = float(np.sqrt((XtXi @ S @ XtXi)[1, 1]))

    r1 = float(np.corrcoef(res[:-1], res[1:])[0, 1]) if n > 2 else 0.0
    n_ef = n * (1 - r1) / (1 + r1) if r1 > -1 else float(n)

    return Trend(
        slope=float(b[1]),
        se_classic=se_classic,
        se_hac=se_hac,
        ic95=(float(b[1] - 1.96 * se_hac), float(b[1] + 1.96 * se_hac)),
        n=n,
        n_effective=float(n_ef),
        residual_autocorr=r1,
    )


def _sse(X: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(((y - X @ b) ** 2).sum()), b


def _bic(sse: float, n: int, k: int) -> float:
    return float(n * np.log(sse / n) + k * np.log(n))


def change_shape(
    dates: Sequence[str], values: Sequence[float], *, margin: int = 30
) -> list[Model]:
    """Compara cuatro formas posibles y las devuelve ordenadas, la best primera.

    - constante          (1 parametro)
    - rampa lineal       (2)
    - escalon            (2 + 1 por el cut buscado)
    - meseta-rampa-meseta(2 + 2 por los dos cortes buscados)

    `margin` is how many observations must be left on each side of a cut.
    Without it the best cut hugs the edge and fits noise.
    """
    t = _years(dates)
    y = np.asarray(values, dtype=float)
    n = len(y)
    uno = np.ones(n)
    models: list[Model] = []

    sse, _ = _sse(np.column_stack([uno]), y)
    models.append(Model("constante", sse, 1, _bic(sse, n, 1)))

    sse, _ = _sse(np.column_stack([uno, t]), y)
    models.append(Model("rampa lineal", sse, 2, _bic(sse, n, 2)))

    if n >= 2 * margin + 2:
        best = None
        for c in range(margin, n - margin):
            s, b = _sse(np.column_stack([uno, (t >= t[c]).astype(float)]), y)
            if best is None or s < best[0]:
                best = (s, c, b)
        s, c, b = best  # type: ignore[misc]
        models.append(Model("escalon", s, 3, _bic(s, n, 3), dates[c],
                              level_before=float(b[0]), level_after=float(b[0] + b[1])))

        mejor2 = None
        paso = max(1, n // 120)  # grid: exact on short series, fast on long ones
        for a in range(margin, n - 2 * margin, paso):
            for z in range(a + margin, n - margin, paso):
                rampa = np.clip((t - t[a]) / (t[z] - t[a]), 0, 1)
                s, b = _sse(np.column_stack([uno, rampa]), y)
                if mejor2 is None or s < mejor2[0]:
                    mejor2 = (s, a, z, b)
        if mejor2:
            s, a, z, b = mejor2
            models.append(Model("meseta-rampa-meseta", s, 4, _bic(s, n, 4),
                                  dates[a], dates[z],
                                  level_before=float(b[0]), level_after=float(b[0] + b[1])))

    return sorted(models, key=lambda m: m.bic)


def leave_one_year_out(
    dates: Sequence[str], values: Sequence[float]
) -> dict[str, float]:
    """Pendiente recalculada quitando un ano entero cada vez.

    Si la conclusion depende de un solo ano, no era una conclusion.
    """
    anos = np.array([int(f[:4]) for f in dates])
    y = np.asarray(values, dtype=float)
    t = _years(dates)
    out: dict[str, float] = {}
    for a in sorted(set(anos.tolist())):
        s = anos != a
        if s.sum() > 3:
            out[f"sin {a}"] = float(np.polyfit(t[s], y[s], 1)[0])
    return out
