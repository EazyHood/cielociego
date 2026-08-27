"""Pruebas de las charts.

No comprueban que se vean bonitas -- eso se mira. Comprueban lo que SI se
puede romper sin que nadie lo note: que el SVG salga bien formado, que los
colores del texto hereden el tema del lector (o el informe es ilegible en
oscuro) y que los datos que se pasan acaben dentro.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date

import pytest

from cielociego import charts

HUECOS = [
    {"start": "2019-03-01", "end": "2019-03-20", "days": 20, "radar_passes": 3},
    {"start": "2019-05-01", "end": "2019-05-04", "days": 4, "radar_passes": 0},
    {"start": "2020-01-01", "end": "2020-03-30", "days": 90, "radar_passes": 12},
]
UTILES = ["2019-01-15", "2019-04-01", "2019-06-01", "2020-05-01"]
RADAR = ["2019-03-05", "2019-03-15", "2020-02-01", "2020-02-13"]
MEDIDAS = [
    {"date": f"2019-0{m}-01", "vv_db": -6.0 + m * 0.2, "vh_db": -12.0 + m * 0.1}
    for m in range(1, 9)
]
D0, D1 = date(2019, 1, 1), date(2020, 12, 31)


def graficas_todas():
    return {
        "distribution": charts.distribution([0.0, 0.03, 0.5, 0.98, 1.0], [5, 22, 48, 77, 96]),
        "calendar_strip": charts.calendar_strip(UTILES, HUECOS, RADAR, D0, D1),
        "huecos": charts.gaps_by_length(HUECOS),
        "anuales": charts.passes_per_year({"2019": 72, "2020": 73}, {"2019": 55, "2020": 60}),
        "serie": charts.radar_series(MEDIDAS, HUECOS, D0, D1),
        "control": charts.platform_control({"Todas": 0.643, "Solo S1A": 0.688, "Vecino": -0.022}),
    }


@pytest.mark.parametrize("name", list(graficas_todas()))
def test_every_chart_produces_well_formed_svg(name):
    svg = graficas_todas()[name]
    assert svg.startswith("<svg")
    raiz = ET.fromstring(svg)  # revienta si el XML esta roto
    assert raiz.tag.endswith("svg")


@pytest.mark.parametrize("name", list(graficas_todas()))
def test_no_chart_carries_a_fixed_text_colour(name):
    """A fixed hex on text makes the report unreadable in dark mode."""
    svg = graficas_todas()[name]
    assert charts.INK not in svg, "quedo un centinela sin sustituir"
    assert charts.GREY not in svg
    assert "var(--tinta)" in svg, "el texto debe heredar del tema"


def test_the_calendar_draws_all_three_kinds_of_mark():
    """If a layer vanished the SVG would shrink and nobody would notice."""
    completo = charts.calendar_strip(UTILES, HUECOS, RADAR, D0, D1)
    no_radar = charts.calendar_strip(UTILES, HUECOS, [], D0, D1)
    sin_nada = charts.calendar_strip([], [], [], D0, D1)
    assert len(completo) > len(no_radar) > len(sin_nada)


def test_the_radar_series_states_its_trend():
    svg = charts.radar_series(MEDIDAS, HUECOS, D0, D1)
    assert "dB/año" in svg, "la slope debe quedar escrita en la grafica"


def test_the_charts_survive_empty_data():
    """A field with no scenes must not bring down the report."""
    assert charts.calendar_strip([], [], [], D0, D1).startswith("<svg")
    assert charts.gaps_by_length([]).startswith("<svg")
    assert charts.passes_per_year({}, {}).startswith("<svg")


def test_the_platform_control_flags_the_large_trends():
    """Anything past 0.3 dB/yr is drawn in the warning colour, not grey."""
    svg = charts.platform_control({"grande": 0.688, "plano": -0.022})
    assert charts.BLIND.lstrip("#") in svg.lower().replace("#", "")


# --- the chart must draw the winning model, not always a line -------------
MODELO_MESETA = {
    "name": "meseta-rampa-meseta", "cut": "2019-03-01", "cut_end": "2019-06-01",
    "level_before": -6.8, "level_after": -3.3,
}


def test_the_series_draws_the_model_it_is_given():
    svg = charts.radar_series(MEDIDAS, HUECOS, D0, D1, model=MODELO_MESETA)
    assert "meseta-rampa-meseta" in svg
    assert "-6.80" in svg or "−6.80" in svg or "-6.8" in svg


def test_without_a_model_the_line_is_marked_as_a_reference():
    """The line is dashed on purpose: it is a summary, not the model."""
    svg = charts.radar_series(MEDIDAS, HUECOS, D0, D1)
    assert "tendencia lineal" in svg


def test_a_step_model_is_drawn_as_a_step():
    escalon = {"name": "escalon", "cut": "2019-05-01",
               "level_before": -7.0, "level_after": -3.0}
    assert "escalon" in charts.radar_series(MEDIDAS, HUECOS, D0, D1, model=escalon)


def test_a_model_without_levels_does_not_break_the_chart():
    pobre = {"name": "rampa lineal", "level_before": None, "level_after": None}
    assert charts.radar_series(MEDIDAS, HUECOS, D0, D1, model=pobre).startswith("<svg")
