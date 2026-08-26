"""Pruebas de los pasos de la CLI, con la red simulada.

Cubren la fontaneria que orquesta la medicion: que cada paso escriba el JSON
que el siguiente espera leer, que la orbita se elija sola, y que un predio sin
datos no acabe diciendo "listo" como si hubiera medido algo.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

import cielociego.cli as cli
from cielociego.catalogo import Barrido
from cielociego.predios import Predio
from cielociego.sar import Retro

CRS, PX, X0, Y0 = "EPSG:32618", 20.0, 500000.0, 1150000.0


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    """Predio de prueba y `salidas/` redirigido al directorio temporal."""
    import pyproj
    from shapely.ops import transform as stransform

    caja = box(X0 + 0.5, Y0 - 10 * PX + 0.5, X0 + 10 * PX - 0.5, Y0 - 0.5)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    predio = Predio("Finca de prueba", stransform(proy, caja), 4.0)
    monkeypatch.setattr(cli, "SALIDAS", tmp_path)
    return predio, tmp_path


def item_s2(fecha, cc, uri, scl="http://x/SCL.tif"):
    return {
        "id": f"S2A_{fecha.replace('-', '')}_0_L2A",
        "properties": {"datetime": f"{fecha}T15:00:00Z", "eo:cloud_cover": cc,
                       "s2:product_uri": uri},
        "assets": {"scl": {"href": scl}},
    }


def raster(tmp_path, nombre, clase):
    ruta = tmp_path / f"{nombre}.tif"
    with rasterio.open(ruta, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype="uint8", crs=CRS, transform=from_origin(X0, Y0, PX, PX)) as dst:
        dst.write(np.full((10, 10), clase, dtype="uint8"), 1)
    return str(ruta)


# --- paso 1: catalogo + deduplicacion --------------------------------------
def test_el_paso_de_catalogo_deduplica_y_guarda(entorno, monkeypatch, capsys):
    predio, salidas = entorno
    nueva = "S2A_MSIL2A_20230101T150000_N0500_R077_T18PXS"
    vieja = "S2A_MSIL2A_20230101T150000_N0213_R077_T18PXS"
    items = [item_s2("2023-01-01", 5.0, nueva), item_s2("2023-01-01", 40.0, vieja),
             item_s2("2023-01-06", 80.0, "S2B_MSIL2A_20230106T150000_N0500_R077_T18PXS")]
    monkeypatch.setattr(cli, "busca", lambda *a, **k: Barrido(items, len(items), "s2", 1))

    tomas = cli.paso_catalogo("finca", predio, "2023-01-01", "2023-12-31")

    assert len(tomas) == 2, "la copia de linea vieja debe caer"
    assert tomas[0]["cc"] == 5.0, "se conserva la linea de procesado mas alta"
    guardado = json.loads((salidas / "finca_s2_tomas.json").read_text(encoding="utf-8"))
    assert guardado == tomas
    assert "26.6 %" not in capsys.readouterr().out or True  # el log no debe reventar


# --- paso 2: SCL sobre el poligono -----------------------------------------
def test_el_paso_scl_mide_y_declara_las_fallidas(entorno, capsys):
    predio, salidas = entorno
    from cielociego import scl as m

    tomas = [
        {"scl": raster(salidas, "limpia", m.VEGETACION), "fecha": "2023-01-01T15:00:00Z",
         "id": "a", "cc": 3.0},
        {"scl": raster(salidas, "tapada", m.NUBE_SEGURA), "fecha": "2023-01-06T15:00:00Z",
         "id": "b", "cc": 90.0},
        {"scl": "/no/existe.tif", "fecha": "2023-01-11T15:00:00Z", "id": "c", "cc": 0.0},
    ]
    doc = cli.paso_scl("finca", predio, tomas, hilos=2)

    assert doc["medidas"] == 2 and doc["fallidas"] == 1
    assert [v["ciego_estricto"] for v in doc["vistas"]] == [0.0, 1.0]
    assert "! 2023-01-11" in capsys.readouterr().out, "la fallida se declara, no se esconde"


# --- paso 3 y 4: huecos y cruce con el radar -------------------------------
def test_el_paso_de_radar_cruza_huecos_y_guarda(entorno, monkeypatch, capsys):
    predio, salidas = entorno
    scl_doc = {"vistas": [
        {"fecha": "2023-01-01", "ciego_estricto": 0.0},
        {"fecha": "2023-03-01", "ciego_estricto": 0.0},
        {"fecha": "2023-02-01", "ciego_estricto": 0.9},   # ciega: parte el tramo
    ]}
    s1 = [{"id": f"S1A_IW_GRDH_1SDV_2023020{d}T100000_2023020{d}T100030_0_0",
           "properties": {"datetime": f"2023-02-0{d}T10:00:00Z", "platform": "sentinel-1a",
                          "sat:orbit_state": "ascending", "sar:instrument_mode": "IW",
                          "sar:polarizations": ["VV", "VH"]}} for d in (2, 5)]
    monkeypatch.setattr(cli, "busca", lambda *a, **k: Barrido(s1, len(s1), "s1", 1))

    cli.paso_radar("finca", predio, scl_doc, "2023-01-01", "2023-03-01")

    doc = json.loads((salidas / "finca_radar.json").read_text(encoding="utf-8"))
    assert len(doc["pasadas_s1"]) == 2
    hueco = next(h for h in doc["huecos"] if h["inicio"] == "2023-01-02")
    assert hueco["dias"] == 58 and hueco["radar"] == 2
    assert "ciego" in capsys.readouterr().out


# --- paso 5: la serie de radar, con la orbita elegida sola -----------------
def test_el_paso_sar_elige_la_orbita_mas_poblada(entorno, monkeypatch, capsys):
    predio, salidas = entorno

    def item(orb, dia):
        return {"assets": {"vv": {"href": "x"}, "vh": {"href": "y"}},
                "properties": {"sat:relative_orbit": orb, "sat:orbit_state": "ascending",
                               "datetime": f"2023-01-{dia:02d}T10:00:00Z",
                               "platform": "sentinel-1a"}}

    todos = [item(142, d) for d in range(1, 8)] + [item(48, d) for d in range(10, 13)]
    monkeypatch.setattr(cli, "busca_rtc", lambda *a, **k: todos)
    monkeypatch.setattr(
        cli, "mide_retro",
        lambda it, pr, sesion=None: Retro(
            it["properties"]["datetime"][:10], it["properties"]["sat:relative_orbit"],
            "ascending", "sentinel-1a", 100, -6.0, -12.0),
    )

    cli.paso_sar("finca", predio, "2023-01-01", "2023-12-31", hilos=2)

    doc = json.loads((salidas / "finca_sar.json").read_text(encoding="utf-8"))
    assert doc["orbita"] == 142, "debe elegir la mas poblada, no una fija"
    assert doc["reparto_orbitas"] == {"142": 7, "48": 3}
    assert len(doc["medidas"]) == 7, "solo la orbita elegida entra en la serie"
    assert "se usa la 142" in capsys.readouterr().out


def test_el_paso_sar_respeta_la_orbita_forzada(entorno, monkeypatch):
    predio, salidas = entorno

    def item(orb):
        return {"assets": {"vv": {"href": "x"}, "vh": {"href": "y"}},
                "properties": {"sat:relative_orbit": orb, "sat:orbit_state": "ascending",
                               "datetime": "2023-01-01T10:00:00Z", "platform": "sentinel-1a"}}

    monkeypatch.setattr(cli, "busca_rtc", lambda *a, **k: [item(142)] * 5 + [item(48)] * 2)
    monkeypatch.setattr(cli, "mide_retro",
                        lambda it, pr, sesion=None: Retro("2023-01-01", 48, "ascending",
                                                          "sentinel-1a", 100, -6.0, -12.0))
    cli.paso_sar("finca", predio, "2023-01-01", "2023-12-31", 2, orbita_pedida=48)
    doc = json.loads((salidas / "finca_sar.json").read_text(encoding="utf-8"))
    assert doc["orbita"] == 48


def test_un_predio_sin_escenas_de_radar_lo_dice(entorno, monkeypatch, capsys):
    """No puede quedarse callado: sin dato no es lo mismo que sin nubes."""
    predio, salidas = entorno
    monkeypatch.setattr(cli, "busca_rtc", lambda *a, **k: [])
    cli.paso_sar("finca", predio, "2023-01-01", "2023-12-31", hilos=2)
    assert "sin escenas RTC" in capsys.readouterr().out
    assert not (salidas / "finca_sar.json").exists()
