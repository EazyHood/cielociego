"""Pruebas de la estadistica.

Se fabrican series donde la respuesta se sabe de antemano: una recta pura,
un escalon puro, una meseta-rampa-meseta pura. Si el modulo no distingue
esos tres casos, no puede distinguirlos en datos reales.
"""
from __future__ import annotations

import numpy as np
import pytest

from cielociego.analisis import (
    forma_del_cambio,
    robustez_dejando_fuera,
    tendencia_hac,
)


def fechas(n, cada=12, desde="2019-01-01"):
    from datetime import date, timedelta

    d0 = date.fromisoformat(desde)
    return [(d0 + timedelta(days=cada * i)).isoformat() for i in range(n)]


# --- tendencia con error estandar robusto ----------------------------------
def test_recuenta_una_pendiente_conocida():
    f = fechas(200)
    t = np.arange(200) * 12 / 365.25
    y = 3.0 + 0.5 * t
    r = tendencia_hac(f, y)
    assert r.pendiente == pytest.approx(0.5, abs=1e-6)
    assert r.n == 200


def test_una_serie_sin_tendencia_no_es_significativa():
    rng = np.random.default_rng(20260826)
    r = tendencia_hac(fechas(300), rng.normal(0, 1, 300))
    assert not r.significativa, "ruido puro no puede dar una tendencia significativa"
    assert r.ic95[0] < 0 < r.ic95[1]


def test_con_ruido_independiente_los_dos_errores_se_parecen():
    """Control: sin autocorrelacion, HAC y clasico deben coincidir mas o menos."""
    rng = np.random.default_rng(1)
    t = np.arange(400) * 12 / 365.25
    r = tendencia_hac(fechas(400), 0.3 * t + rng.normal(0, 0.5, 400))
    assert 0.6 < r.inflacion < 1.6, f"sin autocorrelacion no deberia inflarse ({r.inflacion:.2f})"
    # con n=400 el error tipico de r1 es ~0,05, asi que |r1|<0,2 son 4 sigma:
    # suficiente para detectar arrastre real sin fallar por azar de la semilla
    assert abs(r.autocorr_residuos) < 0.2


def test_con_ruido_autocorrelado_el_error_clasico_se_queda_corto():
    """El caso real: los residuos arrastran y el error clasico miente."""
    rng = np.random.default_rng(7)
    n = 400
    e = np.zeros(n)
    for i in range(1, n):
        e[i] = 0.9 * e[i - 1] + rng.normal(0, 0.3)   # AR(1) fuerte
    t = np.arange(n) * 12 / 365.25
    r = tendencia_hac(fechas(n), 0.3 * t + e)
    assert r.autocorr_residuos > 0.6
    assert r.inflacion > 1.5, "HAC debe ensanchar el intervalo"
    assert r.n_efectivo < n / 4, "con arrastre fuerte quedan pocas independientes"


def test_el_n_efectivo_baja_cuando_sube_la_autocorrelacion():
    rng = np.random.default_rng(3)
    n = 300
    previos = []
    for rho in (0.0, 0.5, 0.9):
        e = np.zeros(n)
        for i in range(1, n):
            e[i] = rho * e[i - 1] + rng.normal(0, 0.3)
        previos.append(tendencia_hac(fechas(n), e).n_efectivo)
    assert previos[0] > previos[1] > previos[2]


def test_series_demasiado_cortas_fallan_en_vez_de_inventar():
    with pytest.raises(ValueError):
        tendencia_hac(fechas(2), [1.0, 2.0])


# --- forma del cambio ------------------------------------------------------
def test_reconoce_una_recta_como_recta():
    f = fechas(200)
    t = np.arange(200) * 12 / 365.25
    ganador = forma_del_cambio(f, 2.0 + 0.4 * t)[0]
    assert ganador.nombre == "rampa lineal"


def test_reconoce_un_escalon_como_escalon():
    f = fechas(200)
    y = np.where(np.arange(200) < 100, -7.0, -3.0)
    ganador = forma_del_cambio(f, y)[0]
    assert ganador.nombre == "escalon"
    assert ganador.nivel_antes == pytest.approx(-7.0, abs=0.05)
    assert ganador.nivel_despues == pytest.approx(-3.0, abs=0.05)


def test_reconoce_una_meseta_rampa_meseta():
    """El caso real del corredor: plano, transicion, plano nuevo."""
    n = 240
    f = fechas(n)
    x = np.arange(n)
    y = np.piecewise(
        x.astype(float),
        [x < 80, (x >= 80) & (x < 160), x >= 160],
        [-7.0, lambda v: -7.0 + 4.0 * (v - 80) / 80, -3.0],
    )
    ganador = forma_del_cambio(f, y)[0]
    assert ganador.nombre == "meseta-rampa-meseta"
    assert ganador.nivel_antes == pytest.approx(-7.0, abs=0.2)
    assert ganador.nivel_despues == pytest.approx(-3.0, abs=0.2)
    assert ganador.corte and ganador.corte_fin and ganador.corte < ganador.corte_fin


def test_una_serie_plana_gana_con_la_constante():
    rng = np.random.default_rng(11)
    assert forma_del_cambio(fechas(200), rng.normal(-6.0, 0.05, 200))[0].nombre == "constante"


def test_los_cortes_buscados_pagan_su_grado_de_libertad():
    """Sin penalizar la busqueda, un modelo con cortes SIEMPRE pareceria mejor."""
    modelos = {m.nombre: m for m in forma_del_cambio(fechas(200), np.arange(200) * 0.01)}
    assert modelos["escalon"].k > modelos["rampa lineal"].k
    assert modelos["meseta-rampa-meseta"].k > modelos["escalon"].k


def test_devuelve_los_modelos_ordenados_por_bic():
    ms = forma_del_cambio(fechas(200), np.where(np.arange(200) < 100, 0.0, 5.0))
    assert [m.bic for m in ms] == sorted(m.bic for m in ms)


def test_una_serie_corta_no_intenta_partirse():
    """Sin observaciones de sobra, buscar cortes es ajustar ruido."""
    nombres = {m.nombre for m in forma_del_cambio(fechas(10), np.arange(10.0), margen=30)}
    assert nombres == {"constante", "rampa lineal"}


# --- robustez --------------------------------------------------------------
def test_quitar_un_ano_no_cambia_una_tendencia_de_verdad():
    f = fechas(240, cada=12)
    t = np.arange(240) * 12 / 365.25
    r = robustez_dejando_fuera(f, 2.0 + 0.5 * t)
    assert len(r) >= 5
    assert all(abs(v - 0.5) < 0.05 for v in r.values())


def test_una_tendencia_que_depende_de_un_solo_ano_se_destapa():
    f = fechas(240, cada=12)
    y = np.zeros(240)
    y[-30:] = 20.0                      # todo el "cambio" vive en el ultimo tramo
    r = robustez_dejando_fuera(f, y)
    assert max(r.values()) / max(min(r.values()), 1e-9) > 3, "la dispersion debe delatarlo"
