"""Pruebas del cruce optico-radar.

El nucleo es `huecos_opticos`: cuenta dias en los que NO hubo observacion
util. Un error de un dia ahi (off-by-one) corre todas las cifras del
informe, y no se nota mirando. Por eso se prueba con casos donde el
resultado esta contado a mano.
"""
from __future__ import annotations

from datetime import date

import pytest

from cielociego.radar import (
    Hueco,
    Pasada,
    a_pasadas,
    cruza,
    huecos_opticos,
    identidad_s1,
)

D = date
ENE = lambda d: date(2023, 1, d)  # noqa: E731


def item_s1(idr, fecha, orbita="ascending"):
    return {
        "id": idr,
        "properties": {
            "datetime": fecha,
            "platform": "sentinel-1a",
            "sat:orbit_state": orbita,
            "sar:instrument_mode": "IW",
            "sar:polarizations": ["VV", "VH"],
        },
    }


REAL = "S1A_IW_GRDH_1SDV_20231222T230735_20231222T230800_051774_0640E8"


# --- identidad y deduplicacion ---------------------------------------------
def test_identidad_de_un_id_real():
    assert identidad_s1({"id": REAL}) == ("S1A", "20231222T230735")


def test_id_ilegible_no_revienta():
    assert identidad_s1({"id": "cualquier_cosa"}) is None


def test_dedup_por_identidad_fisica():
    a = item_s1(REAL, "2023-12-22T23:07:48Z")
    b = item_s1(REAL, "2023-12-22T23:07:48Z")  # mismo producto repetido
    assert len(a_pasadas([a, b])) == 1


def test_asc_y_desc_del_mismo_dia_son_dos_pasadas():
    a = item_s1(REAL, "2023-12-22T23:07:48Z", "ascending")
    b = item_s1(
        "S1A_IW_GRDH_1SDV_20231222T104146_20231222T104215_051766_0640A7",
        "2023-12-22T10:42:01Z", "descending",
    )
    ps = a_pasadas([a, b])
    assert len(ps) == 2
    assert {p.orbita for p in ps} == {"ascending", "descending"}
    assert ps[0].polarizaciones == ("VV", "VH")


# --- huecos: los casos contados a mano -------------------------------------
def test_sin_ninguna_vista_util_el_hueco_es_todo_el_periodo():
    h = huecos_opticos([], ENE(1), ENE(31))
    assert h == [(ENE(1), ENE(31))]
    assert Hueco(*h[0], 0).dias == 31


def test_vista_util_todos_los_dias_no_deja_hueco():
    assert huecos_opticos([ENE(d) for d in range(1, 32)], ENE(1), ENE(31)) == []


def test_hueco_entre_dos_vistas_es_el_intervalo_abierto():
    """Vista el 1 y el 10 -> hueco del 2 al 9 = 8 dias. Contado a mano."""
    h = huecos_opticos([ENE(1), ENE(10)], ENE(1), ENE(10))
    assert h == [(ENE(2), ENE(9))]
    assert Hueco(*h[0], 0).dias == 8


def test_dias_consecutivos_no_dejan_hueco():
    assert huecos_opticos([ENE(5), ENE(6)], ENE(5), ENE(6)) == []


def test_extremos_ciegos_cuentan():
    """Serie que empieza y acaba ciega: los dos bordes son huecos reales."""
    h = huecos_opticos([ENE(10), ENE(20)], ENE(1), ENE(31))
    assert h == [(ENE(1), ENE(9)), (ENE(11), ENE(19)), (ENE(21), ENE(31))]
    assert [Hueco(*t, 0).dias for t in h] == [9, 9, 11]


def test_fechas_fuera_del_periodo_se_ignoran():
    h = huecos_opticos([date(2022, 12, 20), ENE(15), date(2024, 1, 1)], ENE(1), ENE(31))
    assert h == [(ENE(1), ENE(14)), (ENE(16), ENE(31))]


def test_fechas_repetidas_o_desordenadas_dan_lo_mismo():
    ordenado = huecos_opticos([ENE(5), ENE(15)], ENE(1), ENE(20))
    revuelto = huecos_opticos([ENE(15), ENE(5), ENE(15)], ENE(1), ENE(20))
    assert ordenado == revuelto


def test_suma_de_huecos_mas_dias_utiles_es_el_periodo():
    """Invariante: nada se pierde ni se cuenta dos veces."""
    utiles = [ENE(3), ENE(4), ENE(11), ENE(28)]
    h = huecos_opticos(utiles, ENE(1), ENE(31))
    assert sum(Hueco(*t, 0).dias for t in h) + len(utiles) == 31


# --- cruce con el radar ----------------------------------------------------
def test_el_radar_cubre_el_hueco():
    huecos = cruza([ENE(1), ENE(20)], [Pasada(ENE(10), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
    assert len(huecos) == 1
    assert huecos[0].pasadas_radar == 1 and huecos[0].cubierto


def test_radar_fuera_del_hueco_no_cuenta():
    """La pasada cae en un dia con optico util -> no rellena nada."""
    huecos = cruza([ENE(1), ENE(20)], [Pasada(ENE(1), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
    assert huecos[0].pasadas_radar == 0 and not huecos[0].cubierto


def test_radar_en_los_bordes_del_hueco_si_cuenta():
    """El hueco (2..19) incluye sus extremos: dia 2 y dia 19 cuentan."""
    for d in (2, 19):
        h = cruza([ENE(1), ENE(20)], [Pasada(ENE(d), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
        assert h[0].pasadas_radar == 1, f"dia {d} deberia caer dentro"
    for d in (1, 20):
        h = cruza([ENE(1), ENE(20)], [Pasada(ENE(d), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
        assert h[0].pasadas_radar == 0, f"dia {d} NO deberia caer dentro"


def test_varios_huecos_reparten_las_pasadas():
    huecos = cruza(
        [ENE(5), ENE(15)],
        [Pasada(ENE(2), "s1a", "asc", "IW", ()), Pasada(ENE(10), "s1a", "asc", "IW", ()),
         Pasada(ENE(11), "s1a", "desc", "IW", ()), Pasada(ENE(25), "s1a", "asc", "IW", ())],
        ENE(1), ENE(31),
    )
    assert [h.pasadas_radar for h in huecos] == [1, 2, 1]
    assert all(h.cubierto for h in huecos)
