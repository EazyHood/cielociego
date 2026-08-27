"""Tests for the CLI steps, with the network faked.

Cubren la fontaneria que orquesta la medicion: que cada paso escriba el JSON
que el siguiente backoff leer, que la orbit se elija sola, y que un field sin
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
from cielociego.catalog import Sweep
from cielociego.fields import Field
from cielociego.sar import Backscatter

CRS, PX, X0, Y0 = "EPSG:32618", 20.0, 500000.0, 1150000.0


@pytest.fixture()
def entorno(tmp_path, monkeypatch):
    """Field de prueba y `outputs/` redirigido al directorio temporal."""
    import pyproj
    from shapely.ops import transform as stransform

    caja = box(X0 + 0.5, Y0 - 10 * PX + 0.5, X0 + 10 * PX - 0.5, Y0 - 0.5)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    field = Field("Finca de prueba", stransform(proy, caja), 4.0)
    monkeypatch.setattr(cli, "OUTPUTS", tmp_path)
    return field, tmp_path


def item_s2(date, cc, uri, scl="http://x/SCL.tif"):
    return {
        "id": f"S2A_{date.replace('-', '')}_0_L2A",
        "properties": {"datetime": f"{date}T15:00:00Z", "eo:cloud_cover": cc,
                       "s2:product_uri": uri},
        "assets": {"scl": {"href": scl}},
    }


def raster(tmp_path, name, clase):
    path = tmp_path / f"{name}.tif"
    with rasterio.open(path, "w", driver="GTiff", height=10, width=10, count=1,
                       dtype="uint8", crs=CRS, transform=from_origin(X0, Y0, PX, PX)) as dst:
        dst.write(np.full((10, 10), clase, dtype="uint8"), 1)
    return str(path)


# --- paso 1: catalog + deduplicacion --------------------------------------
def test_the_catalogue_step_deduplicates_and_saves(entorno, monkeypatch, capsys):
    field, salidas = entorno
    nueva = "S2A_MSIL2A_20230101T150000_N0500_R077_T18PXS"
    vieja = "S2A_MSIL2A_20230101T150000_N0213_R077_T18PXS"
    items = [item_s2("2023-01-01", 5.0, nueva), item_s2("2023-01-01", 40.0, vieja),
             item_s2("2023-01-06", 80.0, "S2B_MSIL2A_20230106T150000_N0500_R077_T18PXS")]
    monkeypatch.setattr(cli, "search", lambda *a, **k: Sweep(items, len(items), "s2", 1))

    scenes = cli.step_catalog("finca", field, "2023-01-01", "2023-12-31")

    assert len(scenes) == 2, "la copia de linea vieja debe caer"
    assert scenes[0]["cc"] == 5.0, "se conserva la linea de procesado mas alta"
    guardado = json.loads((salidas / "finca_s2_scenes.json").read_text(encoding="utf-8"))
    assert guardado["scenes"] == scenes
    assert guardado["provenance"]["version"], "cada out lleva su provenance"
    assert guardado["provenance"]["parametros"]["start"] == "2023-01-01"


# --- paso 2: SCL sobre el poligono -----------------------------------------
def test_the_scl_step_measures_and_declares_failures(entorno, capsys):
    field, salidas = entorno
    from cielociego import scl as m

    scenes = [
        {"scl": raster(salidas, "limpia", m.VEGETATION), "date": "2023-01-01T15:00:00Z",
         "id": "a", "cc": 3.0},
        {"scl": raster(salidas, "tapada", m.CLOUD_HIGH), "date": "2023-01-06T15:00:00Z",
         "id": "b", "cc": 90.0},
        {"scl": "/no/existe.tif", "date": "2023-01-11T15:00:00Z", "id": "c", "cc": 0.0},
    ]
    doc = cli.step_scl("finca", field, scenes, workers=2)

    assert doc["medidas"] == 2 and doc["failed"] == 1
    assert [v["blind_strict"] for v in doc["views"]] == [0.0, 1.0]
    assert "! 2023-01-11" in capsys.readouterr().out, "la fallida se declara, no se esconde"


# --- paso 3 y 4: huecos y cruce con el radar -------------------------------
def test_the_radar_step_crosses_gaps_and_saves(entorno, monkeypatch, capsys):
    field, salidas = entorno
    scl_doc = {"views": [
        {"date": "2023-01-01", "blind_strict": 0.0},
        {"date": "2023-03-01", "blind_strict": 0.0},
        {"date": "2023-02-01", "blind_strict": 0.9},   # ciega: parte el tramo
    ]}
    s1 = [{"id": f"S1A_IW_GRDH_1SDV_2023020{d}T100000_2023020{d}T100030_0_0",
           "properties": {"datetime": f"2023-02-0{d}T10:00:00Z", "platform": "sentinel-1a",
                          "sat:orbit_state": "ascending", "sar:instrument_mode": "IW",
                          "sar:polarizations": ["VV", "VH"]}} for d in (2, 5)]
    monkeypatch.setattr(cli, "search", lambda *a, **k: Sweep(s1, len(s1), "s1", 1))

    cli.step_radar("finca", field, scl_doc, "2023-01-01", "2023-03-01")

    doc = json.loads((salidas / "finca_radar.json").read_text(encoding="utf-8"))
    assert len(doc["pasadas_s1"]) == 2
    hueco = next(h for h in doc["huecos"] if h["start"] == "2023-01-02")
    assert hueco["days"] == 58 and hueco["radar"] == 2
    assert "ciego" in capsys.readouterr().out


# --- step 5: the radar series, with the orbit picked automatically --------
def test_the_sar_step_picks_the_best_covered_orbit(entorno, monkeypatch, capsys):
    field, salidas = entorno

    def item(orb, dia):
        return {"assets": {"vv": {"href": "x"}, "vh": {"href": "y"}},
                "properties": {"sat:relative_orbit": orb, "sat:orbit_state": "ascending",
                               "datetime": f"2023-01-{dia:02d}T10:00:00Z",
                               "platform": "sentinel-1a"}}

    todos = [item(142, d) for d in range(1, 8)] + [item(48, d) for d in range(10, 13)]
    monkeypatch.setattr(cli, "search_rtc", lambda *a, **k: todos)
    monkeypatch.setattr(
        cli, "measure_backscatter",
        lambda it, pr, session=None: Backscatter(
            it["properties"]["datetime"][:10], it["properties"]["sat:relative_orbit"],
            "ascending", "sentinel-1a", 100, -6.0, -12.0),
    )

    cli.step_sar("finca", field, "2023-01-01", "2023-12-31", workers=2)

    doc = json.loads((salidas / "finca_sar.json").read_text(encoding="utf-8"))
    assert doc["orbit"] == 142, "debe elegir la mas poblada, no una fija"
    assert doc["orbit_breakdown"] == {"142": 7, "48": 3}
    assert len(doc["medidas"]) == 7, "solo la orbit elegida entra en la serie"
    assert "se usa la 142" in capsys.readouterr().out


def test_the_sar_step_respects_a_forced_orbit(entorno, monkeypatch):
    field, salidas = entorno

    def item(orb):
        return {"assets": {"vv": {"href": "x"}, "vh": {"href": "y"}},
                "properties": {"sat:relative_orbit": orb, "sat:orbit_state": "ascending",
                               "datetime": "2023-01-01T10:00:00Z", "platform": "sentinel-1a"}}

    monkeypatch.setattr(cli, "search_rtc", lambda *a, **k: [item(142)] * 5 + [item(48)] * 2)
    monkeypatch.setattr(cli, "measure_backscatter",
                        lambda it, pr, session=None: Backscatter("2023-01-01", 48, "ascending",
                                                          "sentinel-1a", 100, -6.0, -12.0))
    cli.step_sar("finca", field, "2023-01-01", "2023-12-31", 2, orbita_pedida=48)
    doc = json.loads((salidas / "finca_sar.json").read_text(encoding="utf-8"))
    assert doc["orbit"] == 48


def test_a_field_with_no_radar_scenes_says_so(entorno, monkeypatch, capsys):
    """It cannot stay quiet: no data is not the same as no cloud."""
    field, salidas = entorno
    monkeypatch.setattr(cli, "search_rtc", lambda *a, **k: [])
    cli.step_sar("finca", field, "2023-01-01", "2023-12-31", workers=2)
    assert "sin escenas RTC" in capsys.readouterr().out
    assert not (salidas / "finca_sar.json").exists()
