"""Pruebas de las graficas.

No comprueban que se vean bonitas -- eso se mira. Comprueban lo que SI se
puede romper sin que nadie lo note: que el SVG salga bien formado, que los
colores del texto hereden el tema del lector (o el informe es ilegible en
oscuro) y que los datos que se pasan acaben dentro.
"""
from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import date

import pytest

from cielociego import graficas

HUECOS = [
    {"inicio": "2019-03-01", "fin": "2019-03-20", "dias": 20, "radar": 3},
    {"inicio": "2019-05-01", "fin": "2019-05-04", "dias": 4, "radar": 0},
    {"inicio": "2020-01-01", "fin": "2020-03-30", "dias": 90, "radar": 12},
]
UTILES = ["2019-01-15", "2019-04-01", "2019-06-01", "2020-05-01"]
RADAR = ["2019-03-05", "2019-03-15", "2020-02-01", "2020-02-13"]
MEDIDAS = [
    {"fecha": f"2019-0{m}-01", "vv_db": -6.0 + m * 0.2, "vh_db": -12.0 + m * 0.1}
    for m in range(1, 9)
]
D0, D1 = date(2019, 1, 1), date(2020, 12, 31)


def graficas_todas():
    return {
        "distribucion": graficas.distribucion([0.0, 0.03, 0.5, 0.98, 1.0], [5, 22, 48, 77, 96]),
        "calendario": graficas.calendario(UTILES, HUECOS, RADAR, D0, D1),
        "huecos": graficas.huecos_por_duracion(HUECOS),
        "anuales": graficas.pasadas_anuales({"2019": 72, "2020": 73}, {"2019": 55, "2020": 60}),
        "serie": graficas.serie_radar(MEDIDAS, HUECOS, D0, D1),
        "control": graficas.control_plataforma({"Todas": 0.643, "Solo S1A": 0.688, "Vecino": -0.022}),
    }


@pytest.mark.parametrize("nombre", list(graficas_todas()))
def test_cada_grafica_produce_svg_bien_formado(nombre):
    svg = graficas_todas()[nombre]
    assert svg.startswith("<svg")
    raiz = ET.fromstring(svg)  # revienta si el XML esta roto
    assert raiz.tag.endswith("svg")


@pytest.mark.parametrize("nombre", list(graficas_todas()))
def test_ninguna_grafica_lleva_color_de_texto_fijo(nombre):
    """Un hex fijo en el texto deja el informe ilegible en tema oscuro."""
    svg = graficas_todas()[nombre]
    assert graficas.TINTA not in svg, "quedo un centinela sin sustituir"
    assert graficas.GRIS not in svg
    assert "var(--tinta)" in svg, "el texto debe heredar del tema"


def test_el_calendario_dibuja_los_tres_tipos_de_marca():
    """Si una capa desapareciera, el SVG encogeria y nadie lo notaria."""
    completo = graficas.calendario(UTILES, HUECOS, RADAR, D0, D1)
    sin_radar = graficas.calendario(UTILES, HUECOS, [], D0, D1)
    sin_nada = graficas.calendario([], [], [], D0, D1)
    assert len(completo) > len(sin_radar) > len(sin_nada)


def test_la_serie_de_radar_declara_su_tendencia():
    svg = graficas.serie_radar(MEDIDAS, HUECOS, D0, D1)
    assert "dB/año" in svg, "la pendiente debe quedar escrita en la grafica"


def test_las_graficas_aguantan_datos_vacios():
    """Un predio sin escenas no puede tumbar la generacion del informe."""
    assert graficas.calendario([], [], [], D0, D1).startswith("<svg")
    assert graficas.huecos_por_duracion([]).startswith("<svg")
    assert graficas.pasadas_anuales({}, {}).startswith("<svg")


def test_el_control_de_plataforma_marca_las_tendencias_grandes():
    """Las que superan 0,3 dB/ano se pintan en color de aviso, no en gris."""
    svg = graficas.control_plataforma({"grande": 0.688, "plano": -0.022})
    assert graficas.CIEGO.lstrip("#") in svg.lower().replace("#", "")


# --- la grafica debe dibujar el modelo que gana, no una recta siempre -------
MODELO_MESETA = {
    "nombre": "meseta-rampa-meseta", "corte": "2019-03-01", "corte_fin": "2019-06-01",
    "nivel_antes": -6.8, "nivel_despues": -3.3,
}


def test_la_serie_dibuja_el_modelo_que_se_le_pasa():
    svg = graficas.serie_radar(MEDIDAS, HUECOS, D0, D1, modelo=MODELO_MESETA)
    assert "meseta-rampa-meseta" in svg
    assert "-6.80" in svg or "−6.80" in svg or "-6.8" in svg


def test_sin_modelo_avisa_de_que_la_recta_es_solo_una_referencia():
    """La recta queda punteada a proposito: es un resumen, no el modelo."""
    svg = graficas.serie_radar(MEDIDAS, HUECOS, D0, D1)
    assert "tendencia lineal" in svg


def test_un_modelo_de_escalon_se_dibuja_como_escalon():
    escalon = {"nombre": "escalon", "corte": "2019-05-01",
               "nivel_antes": -7.0, "nivel_despues": -3.0}
    assert "escalon" in graficas.serie_radar(MEDIDAS, HUECOS, D0, D1, modelo=escalon)


def test_un_modelo_sin_niveles_no_revienta_la_grafica():
    pobre = {"nombre": "rampa lineal", "nivel_antes": None, "nivel_despues": None}
    assert graficas.serie_radar(MEDIDAS, HUECOS, D0, D1, modelo=pobre).startswith("<svg")
