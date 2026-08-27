"""Pruebas de la estadistica.

Se fabrican series donde la respuesta se sabe de antemano: una recta pura,
un escalon puro, una meseta-rampa-meseta pura. Si el modulo no distingue
esos tres casos, no puede distinguirlos en datos reales.
"""
from __future__ import annotations

import numpy as np
import pytest

from cielociego.analysis import (
    change_shape,
    hac_trend,
    leave_one_year_out,
)


def dates(n, cada=12, start="2019-01-01"):
    from datetime import date, timedelta

    d0 = date.fromisoformat(start)
    return [(d0 + timedelta(days=cada * i)).isoformat() for i in range(n)]


# --- tendencia con error estandar robusto ----------------------------------
def test_recovers_a_known_slope():
    f = dates(200)
    t = np.arange(200) * 12 / 365.25
    y = 3.0 + 0.5 * t
    r = hac_trend(f, y)
    assert r.slope == pytest.approx(0.5, abs=1e-6)
    assert r.n == 200


def test_a_series_without_trend_is_not_significant():
    rng = np.random.default_rng(20260826)
    r = hac_trend(dates(300), rng.normal(0, 1, 300))
    assert not r.significant, "ruido puro no puede dar una tendencia significant"
    assert r.ic95[0] < 0 < r.ic95[1]


def test_independent_noise_leaves_both_errors_alike():
    """Control: sin autocorrelacion, HAC y clasico deben coincidir mas o menos."""
    rng = np.random.default_rng(1)
    t = np.arange(400) * 12 / 365.25
    r = hac_trend(dates(400), 0.3 * t + rng.normal(0, 0.5, 400))
    assert 0.6 < r.inflation < 1.6, f"sin autocorrelacion no deberia inflarse ({r.inflation:.2f})"
    # at n=400 the typical error of r1 is ~0.05, so |r1|<0.2 is four sigma:
    # enough to catch real drift without failing on the luck of the seed
    assert abs(r.residual_autocorr) < 0.2


def test_autocorrelated_noise_makes_the_classical_error_too_small():
    """The real case: the residuals drag and the classical error lies."""
    rng = np.random.default_rng(7)
    n = 400
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.9 * e[i - 1] + rng.normal(0, 0.3)   # AR(1) fuerte
    t = np.arange(n) * 12 / 365.25
    r = hac_trend(dates(n), 0.3 * t + e)
    assert r.residual_autocorr > 0.6
    assert r.inflation > 1.5, "HAC debe ensanchar el intervalo"
    assert r.n_effective < n / 4, "con arrastre fuerte quedan pocas independientes"


def test_effective_n_falls_as_autocorrelation_rises():
    rng = np.random.default_rng(3)
    n = 300
    previos = []
    for rho in (0.0, 0.5, 0.9):
        e = np.zeros(n)
        for i in range(1, n):
            e[i] = rho * e[i - 1] + rng.normal(0, 0.3)
        previos.append(hac_trend(dates(n), e).n_effective)
    assert previos[0] > previos[1] > previos[2]


def test_too_short_a_series_raises_instead_of_inventing():
    with pytest.raises(ValueError):
        hac_trend(dates(2), [1.0, 2.0])


# --- forma del cambio ------------------------------------------------------
def test_recognises_a_line_as_a_line():
    f = dates(200)
    t = np.arange(200) * 12 / 365.25
    ganador = change_shape(f, 2.0 + 0.4 * t)[0]
    assert ganador.name == "rampa lineal"


def test_recognises_a_step_as_a_step():
    f = dates(200)
    y = np.where(np.arange(200) < 100, -7.0, -3.0)
    ganador = change_shape(f, y)[0]
    assert ganador.name == "escalon"
    assert ganador.level_before == pytest.approx(-7.0, abs=0.05)
    assert ganador.level_after == pytest.approx(-3.0, abs=0.05)


def test_recognises_a_plateau_ramp_plateau():
    """El caso real del corredor: plano, transicion, plano nuevo."""
    n = 240
    f = dates(n)
    x = np.arange(n)
    y = np.piecewise(
        x.astype(float),
        [x < 80, (x >= 80) & (x < 160), x >= 160],
        [-7.0, lambda v: -7.0 + 4.0 * (v - 80) / 80, -3.0],
    )
    ganador = change_shape(f, y)[0]
    assert ganador.name == "meseta-rampa-meseta"
    assert ganador.level_before == pytest.approx(-7.0, abs=0.2)
    assert ganador.level_after == pytest.approx(-3.0, abs=0.2)
    assert ganador.cut and ganador.cut_end and ganador.cut < ganador.cut_end


def test_a_flat_series_is_won_by_the_constant():
    rng = np.random.default_rng(11)
    assert change_shape(dates(200), rng.normal(-6.0, 0.05, 200))[0].name == "constante"


def test_searched_breakpoints_pay_for_their_freedom():
    """Unpenalised, a model with breakpoints would always look better."""
    models = {m.name: m for m in change_shape(dates(200), np.arange(200) * 0.01)}
    assert models["escalon"].k > models["rampa lineal"].k
    assert models["meseta-rampa-meseta"].k > models["escalon"].k


def test_returns_the_models_sorted_by_bic():
    ms = change_shape(dates(200), np.where(np.arange(200) < 100, 0.0, 5.0))
    assert [m.bic for m in ms] == sorted(m.bic for m in ms)


def test_a_short_series_is_not_split():
    """Sin observaciones de sobra, buscar cortes es ajustar ruido."""
    nombres = {m.name for m in change_shape(dates(10), np.arange(10.0), margin=30)}
    assert nombres == {"constante", "rampa lineal"}


# --- robustez --------------------------------------------------------------
def test_dropping_one_year_leaves_a_real_trend_standing():
    f = dates(240, cada=12)
    t = np.arange(240) * 12 / 365.25
    r = leave_one_year_out(f, 2.0 + 0.5 * t)
    assert len(r) >= 5
    assert all(abs(v - 0.5) < 0.05 for v in r.values())


def test_a_trend_resting_on_one_year_is_exposed():
    f = dates(240, cada=12)
    y = np.zeros(240)
    y[-30:] = 20.0                      # todo el "cambio" vive en el ultimo tramo
    r = leave_one_year_out(f, y)
    assert max(r.values()) / max(min(r.values()), 1e-9) > 3, "la dispersion debe delatarlo"
