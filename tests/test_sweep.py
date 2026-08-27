"""Pruebas del sweep en paralelo.

Lo que garantizan: que una escena rota no mate el sweep, y -- mas
importante -- que TAMPOCO se cuele como si estuviera despejada. En una
herramienta de medida, un fallo tragado en silencio se convierte en un dato.
"""
from __future__ import annotations

import json

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from cielociego import scl
from cielociego.fields import Field
from cielociego.sweep import sweep

CRS, PX, X0, Y0 = "EPSG:32618", 20.0, 500000.0, 1150000.0


@pytest.fixture()
def escenario(tmp_path):
    """Devuelve (field, hacer_toma) para fabricar rasters con values dados."""
    import pyproj
    from shapely.ops import transform as stransform

    caja = box(X0 + 0.5, Y0 - 10 * PX + 0.5, X0 + 10 * PX - 0.5, Y0 - 0.5)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    field = Field("Field de prueba", stransform(proy, caja), 4.0)

    def toma(name, clase, date, cc=None):
        path = tmp_path / f"{name}.tif"
        with rasterio.open(
            path, "w", driver="GTiff", height=10, width=10, count=1,
            dtype="uint8", crs=CRS, transform=from_origin(X0, Y0, PX, PX),
        ) as dst:
            dst.write(np.full((10, 10), clase, dtype="uint8"), 1)
        return {"scl": str(path), "date": f"{date}T15:00:00Z", "id": name, "cc": cc}

    return field, toma


def test_measures_every_acquisition(escenario):
    field, toma = escenario
    scenes = [toma(f"t{i}", scl.VEGETATION, f"2023-01-0{i + 1}") for i in range(5)]
    r = sweep(field, scenes, workers=3)
    assert len(r.views) == 5 and not r.failed and r.total == 5


def test_a_broken_scene_neither_kills_the_sweep_nor_slips_through(escenario):
    field, toma = escenario
    scenes = [toma("buena", scl.VEGETATION, "2023-01-01")]
    scenes.append({"scl": "/no/existe.tif", "date": "2023-01-02T15:00:00Z", "id": "rota", "cc": 0})
    r = sweep(field, scenes, workers=2)
    assert len(r.views) == 1 and len(r.failed) == 1
    assert r.failed[0].error is not None
    assert r.failed[0] not in r.views, "una rota nunca entra como medida buena"


def test_the_result_comes_out_sorted_by_date(escenario):
    """Workers finish in any order; the series cannot depend on that."""
    field, toma = escenario
    scenes = [toma(f"t{d}", scl.VEGETATION, f"2023-01-{d:02d}") for d in (9, 3, 7, 1, 5)]
    r = sweep(field, scenes, workers=5)
    assert [v.date for v in r.views] == sorted(v.date for v in r.views)


def test_acquisitions_without_a_link_are_skipped(escenario):
    field, toma = escenario
    scenes = [toma("ok", scl.VEGETATION, "2023-01-01"),
             {"scl": None, "date": "2023-01-02T15:00:00Z", "id": "sin", "cc": 0}]
    assert sweep(field, scenes, workers=2).total == 1


def test_saves_a_json_that_can_be_read_back(escenario, tmp_path):
    field, toma = escenario
    r = sweep(field, [toma("a", scl.CLOUD_HIGH, "2023-01-01", cc=88.0)], workers=1)
    target = r.save(tmp_path / "sub" / "out.json")
    doc = json.loads(target.read_text(encoding="utf-8"))
    assert doc["field"] == "Field de prueba" and doc["medidas"] == 1
    assert doc["views"][0]["blind_strict"] == 1.0
    assert doc["views"][0]["tile_cloud"] == 88.0


def test_the_worker_count_does_not_change_the_result(escenario):
    """Determinism control at sweep level, not just for one read."""
    field, toma = escenario
    scenes = [toma(f"t{i}", scl.VEGETATION if i % 2 else scl.CLOUD_HIGH,
                  f"2023-02-{i + 1:02d}") for i in range(8)]

    def fingerprint(workers):
        r = sweep(field, scenes, workers=workers)
        return [(v.date, v.blind_strict, v.pixels) for v in r.views]

    assert fingerprint(1) == fingerprint(8)


def test_reports_progress(escenario):
    field, toma = escenario
    scenes = [toma(f"t{i}", scl.VEGETATION, f"2023-03-{i + 1:02d}") for i in range(3)]
    visto = []
    sweep(field, scenes, workers=2, avisa=lambda n, t: visto.append((n, t)))
    assert visto and visto[-1] == (3, 3), "debe avisar del ultimo"


def test_barrido_empty_not_raises(escenario):
    field, _ = escenario
    r = sweep(field, [], workers=2)
    assert r.total == 0 and not r.views


# --- second pass: tell a network stumble from a genuinely dead file -------
def test_a_scene_that_fails_and_luego_va_recovers(escenario, monkeypatch):
    """The real case: 0 failures in the morning, 14 in the afternoon, all DNS."""
    field, toma = escenario
    t = toma("intermitente", scl.VEGETATION, "2023-01-01")

    from cielociego import sweep as mod

    real = mod.measure_view
    fallos = {"n": 0}

    def falla_la_primera(href, geom, **kw):
        if fallos["n"] == 0:
            fallos["n"] += 1
            v = real("/no/existe.tif", geom, **kw)   # provoca un error real
            return v
        return real(href, geom, **kw)

    monkeypatch.setattr(mod, "measure_view", falla_la_primera)
    r = sweep(field, [t], workers=1, retries=2, backoff=0.01)
    assert len(r.views) == 1 and not r.failed
    assert r.recovered == 1, "debe contar cuantas salvo la segunda pasada"


def test_a_fichero_dead_of_real_sigue_fallando(escenario):
    """The 2024-01-23 one points at a path that is gone: insisting will not save it."""
    field, _ = escenario
    t = {"scl": "/no/existe.tif", "date": "2024-01-23T15:00:00Z", "id": "muerta", "cc": 0}
    r = sweep(field, [t], workers=1, retries=2, backoff=0.01)
    assert len(r.failed) == 1 and r.recovered == 0
    assert r.failed[0].error


def test_can_disable_the_second_pass(escenario):
    field, _ = escenario
    t = {"scl": "/no/existe.tif", "date": "2023-01-01T15:00:00Z", "id": "x", "cc": 0}
    r = sweep(field, [t], workers=1, retries=0)
    assert len(r.failed) == 1 and r.recovered == 0


def test_the_recuperadas_stay_escritas_in_the_json(escenario, tmp_path):
    field, toma = escenario
    r = sweep(field, [toma("a", scl.VEGETATION, "2023-01-01")], workers=1, retries=0)
    doc = json.loads(r.save(tmp_path / "s.json").read_text(encoding="utf-8"))
    assert "recovered_on_retry" in doc
