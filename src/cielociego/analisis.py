"""Estadistica de la serie temporal: tendencia honesta y forma del cambio.

DOS ERRORES QUE ESTE MODULO EXISTE PARA NO COMETER
---------------------------------------------------

**1. Dar una pendiente sin decir cuanto vale.**
Un ajuste por minimos cuadrados supone que las observaciones son
independientes. Las de una serie de radar NO lo son: los residuos de este
predio tienen autocorrelacion de 0,76, asi que 341 pasadas valen como **47
observaciones independientes**. El error estandar clasico sale 1,7 veces
demasiado pequeno y el intervalo de confianza, demasiado estrecho. Se usa
Newey-West (HAC), que corrige justo eso.

**2. Ajustar una recta a algo que no es una recta.**
Una pendiente media de "+0,64 dB/ano" describe bien una rampa continua y
describe MAL un cambio que ocurre de golpe y luego se estabiliza -- aunque
las dos cosas empiecen y acaben en el mismo sitio. Y son historias
agronomicas distintas: una rampa parece crecimiento; una meseta-transicion-
meseta parece un evento (siembra, tala, inundacion, cambio de uso).

Por eso `forma_del_cambio` compara cuatro modelos por BIC en vez de suponer
uno. Y **penaliza los puntos de corte buscados**: encontrar el mejor sitio
para partir la serie es un grado de libertad mas, y no contarlo hace que
cualquier modelo con cortes parezca mejor de lo que es.
"""
from __future__ import annotations

from collections.abc import Sequence
from dataclasses import asdict, dataclass
from datetime import date
from typing import Any

import numpy as np


@dataclass
class Tendencia:
    """Pendiente de una serie, con la incertidumbre bien calculada."""

    pendiente: float          # unidades de y por ano
    ee_clasico: float         # error estandar suponiendo independencia (optimista)
    ee_hac: float             # error estandar robusto a autocorrelacion
    ic95: tuple[float, float]
    n: int
    n_efectivo: float         # observaciones realmente independientes
    autocorr_residuos: float

    @property
    def inflacion(self) -> float:
        """Cuantas veces se equivocaba el error estandar clasico."""
        return self.ee_hac / self.ee_clasico if self.ee_clasico else float("nan")

    @property
    def significativa(self) -> bool:
        """El IC del 95 % no cruza el cero."""
        return self.ic95[0] * self.ic95[1] > 0

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ic95"] = list(self.ic95)
        d["inflacion_ee"] = round(self.inflacion, 3)
        d["significativa"] = self.significativa
        return d


@dataclass
class Modelo:
    nombre: str
    sse: float
    k: int          # parametros efectivos, INCLUYENDO los cortes buscados
    bic: float
    corte: str | None = None
    corte_fin: str | None = None
    nivel_antes: float | None = None
    nivel_despues: float | None = None

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _anos(fechas: Sequence[str]) -> np.ndarray:
    o = np.array([date.fromisoformat(f).toordinal() for f in fechas], dtype=float)
    return (o - o[0]) / 365.25


def tendencia_hac(fechas: Sequence[str], valores: Sequence[float]) -> Tendencia:
    """Pendiente por ano con error estandar robusto a autocorrelacion.

    El ancho de banda de Newey-West sale de la regla habitual de Andrews,
    `4*(n/100)^(2/9)`, para no elegirlo a dedo.
    """
    t = _anos(fechas)
    y = np.asarray(valores, dtype=float)
    n = len(y)
    if n < 3:
        raise ValueError("hacen falta al menos 3 observaciones para una tendencia")

    t = t - t.mean()
    X = np.column_stack([np.ones(n), t])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    res = y - X @ b

    XtXi = np.linalg.inv(X.T @ X)
    ee_clasico = float(np.sqrt((res**2).sum() / (n - 2) * XtXi[1, 1]))

    u = res[:, None] * X
    S = u.T @ u
    L = max(1, int(np.floor(4 * (n / 100) ** (2 / 9))))
    for lag in range(1, min(L, n - 1) + 1):
        G = u[lag:].T @ u[:-lag]
        S = S + (1 - lag / (L + 1)) * (G + G.T)
    ee_hac = float(np.sqrt((XtXi @ S @ XtXi)[1, 1]))

    r1 = float(np.corrcoef(res[:-1], res[1:])[0, 1]) if n > 2 else 0.0
    n_ef = n * (1 - r1) / (1 + r1) if r1 > -1 else float(n)

    return Tendencia(
        pendiente=float(b[1]),
        ee_clasico=ee_clasico,
        ee_hac=ee_hac,
        ic95=(float(b[1] - 1.96 * ee_hac), float(b[1] + 1.96 * ee_hac)),
        n=n,
        n_efectivo=float(n_ef),
        autocorr_residuos=r1,
    )


def _sse(X: np.ndarray, y: np.ndarray) -> tuple[float, np.ndarray]:
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    return float(((y - X @ b) ** 2).sum()), b


def _bic(sse: float, n: int, k: int) -> float:
    return float(n * np.log(sse / n) + k * np.log(n))


def forma_del_cambio(
    fechas: Sequence[str], valores: Sequence[float], *, margen: int = 30
) -> list[Modelo]:
    """Compara cuatro formas posibles y las devuelve ordenadas, la mejor primera.

    - constante          (1 parametro)
    - rampa lineal       (2)
    - escalon            (2 + 1 por el corte buscado)
    - meseta-rampa-meseta(2 + 2 por los dos cortes buscados)

    `margen` es cuantas observaciones se dejan como minimo a cada lado de un
    corte: sin el, el "mejor" corte se pega al borde y ajusta ruido.
    """
    t = _anos(fechas)
    y = np.asarray(valores, dtype=float)
    n = len(y)
    uno = np.ones(n)
    modelos: list[Modelo] = []

    sse, _ = _sse(np.column_stack([uno]), y)
    modelos.append(Modelo("constante", sse, 1, _bic(sse, n, 1)))

    sse, _ = _sse(np.column_stack([uno, t]), y)
    modelos.append(Modelo("rampa lineal", sse, 2, _bic(sse, n, 2)))

    if n >= 2 * margen + 2:
        mejor = None
        for c in range(margen, n - margen):
            s, b = _sse(np.column_stack([uno, (t >= t[c]).astype(float)]), y)
            if mejor is None or s < mejor[0]:
                mejor = (s, c, b)
        s, c, b = mejor  # type: ignore[misc]
        modelos.append(Modelo("escalon", s, 3, _bic(s, n, 3), fechas[c],
                              nivel_antes=float(b[0]), nivel_despues=float(b[0] + b[1])))

        mejor2 = None
        paso = max(1, n // 120)  # rejilla: exacto en series cortas, rapido en largas
        for a in range(margen, n - 2 * margen, paso):
            for z in range(a + margen, n - margen, paso):
                rampa = np.clip((t - t[a]) / (t[z] - t[a]), 0, 1)
                s, b = _sse(np.column_stack([uno, rampa]), y)
                if mejor2 is None or s < mejor2[0]:
                    mejor2 = (s, a, z, b)
        if mejor2:
            s, a, z, b = mejor2
            modelos.append(Modelo("meseta-rampa-meseta", s, 4, _bic(s, n, 4),
                                  fechas[a], fechas[z],
                                  nivel_antes=float(b[0]), nivel_despues=float(b[0] + b[1])))

    return sorted(modelos, key=lambda m: m.bic)


def robustez_dejando_fuera(
    fechas: Sequence[str], valores: Sequence[float]
) -> dict[str, float]:
    """Pendiente recalculada quitando un ano entero cada vez.

    Si la conclusion depende de un solo ano, no era una conclusion.
    """
    anos = np.array([int(f[:4]) for f in fechas])
    y = np.asarray(valores, dtype=float)
    t = _anos(fechas)
    salida: dict[str, float] = {}
    for a in sorted(set(anos.tolist())):
        s = anos != a
        if s.sum() > 3:
            salida[f"sin {a}"] = float(np.polyfit(t[s], y[s], 1)[0])
    return salida
