"""Pruebas del barrido en paralelo.

Lo que garantizan: que una escena rota no mate el barrido, y -- mas
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
from cielociego.barrido import barre
from cielociego.predios import Predio

CRS, PX, X0, Y0 = "EPSG:32618", 20.0, 500000.0, 1150000.0


@pytest.fixture()
def escenario(tmp_path):
    """Devuelve (predio, hacer_toma) para fabricar rasters con valores dados."""
    import pyproj
    from shapely.ops import transform as stransform

    caja = box(X0 + 0.5, Y0 - 10 * PX + 0.5, X0 + 10 * PX - 0.5, Y0 - 0.5)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    predio = Predio("Predio de prueba", stransform(proy, caja), 4.0)

    def toma(nombre, clase, fecha, cc=None):
        ruta = tmp_path / f"{nombre}.tif"
        with rasterio.open(
            ruta, "w", driver="GTiff", height=10, width=10, count=1,
            dtype="uint8", crs=CRS, transform=from_origin(X0, Y0, PX, PX),
        ) as dst:
            dst.write(np.full((10, 10), clase, dtype="uint8"), 1)
        return {"scl": str(ruta), "fecha": f"{fecha}T15:00:00Z", "id": nombre, "cc": cc}

    return predio, toma


def test_mide_todas_las_tomas(escenario):
    predio, toma = escenario
    tomas = [toma(f"t{i}", scl.VEGETACION, f"2023-01-0{i + 1}") for i in range(5)]
    r = barre(predio, tomas, hilos=3)
    assert len(r.vistas) == 5 and not r.fallidas and r.total == 5


def test_una_escena_rota_no_mata_el_barrido_ni_se_cuela(escenario):
    predio, toma = escenario
    tomas = [toma("buena", scl.VEGETACION, "2023-01-01")]
    tomas.append({"scl": "/no/existe.tif", "fecha": "2023-01-02T15:00:00Z", "id": "rota", "cc": 0})
    r = barre(predio, tomas, hilos=2)
    assert len(r.vistas) == 1 and len(r.fallidas) == 1
    assert r.fallidas[0].error is not None
    assert r.fallidas[0] not in r.vistas, "una rota nunca entra como medida buena"


def test_el_resultado_sale_ordenado_por_fecha(escenario):
    """Los hilos terminan en cualquier orden; la serie no puede depender de eso."""
    predio, toma = escenario
    tomas = [toma(f"t{d}", scl.VEGETACION, f"2023-01-{d:02d}") for d in (9, 3, 7, 1, 5)]
    r = barre(predio, tomas, hilos=5)
    assert [v.fecha for v in r.vistas] == sorted(v.fecha for v in r.vistas)


def test_las_tomas_sin_enlace_se_saltan(escenario):
    predio, toma = escenario
    tomas = [toma("ok", scl.VEGETACION, "2023-01-01"),
             {"scl": None, "fecha": "2023-01-02T15:00:00Z", "id": "sin", "cc": 0}]
    assert barre(predio, tomas, hilos=2).total == 1


def test_guarda_un_json_que_se_puede_releer(escenario, tmp_path):
    predio, toma = escenario
    r = barre(predio, [toma("a", scl.NUBE_SEGURA, "2023-01-01", cc=88.0)], hilos=1)
    destino = r.guarda(tmp_path / "sub" / "salida.json")
    doc = json.loads(destino.read_text(encoding="utf-8"))
    assert doc["predio"] == "Predio de prueba" and doc["medidas"] == 1
    assert doc["vistas"][0]["ciego_estricto"] == 1.0
    assert doc["vistas"][0]["cc_tesela"] == 88.0


def test_el_numero_de_hilos_no_cambia_el_resultado(escenario):
    """Control de determinismo a nivel de barrido, no solo de una lectura."""
    predio, toma = escenario
    tomas = [toma(f"t{i}", scl.VEGETACION if i % 2 else scl.NUBE_SEGURA,
                  f"2023-02-{i + 1:02d}") for i in range(8)]

    def huella(hilos):
        r = barre(predio, tomas, hilos=hilos)
        return [(v.fecha, v.ciego_estricto, v.pixeles) for v in r.vistas]

    assert huella(1) == huella(8)


def test_avisa_del_progreso(escenario):
    predio, toma = escenario
    tomas = [toma(f"t{i}", scl.VEGETACION, f"2023-03-{i + 1:02d}") for i in range(3)]
    visto = []
    barre(predio, tomas, hilos=2, avisa=lambda n, t: visto.append((n, t)))
    assert visto and visto[-1] == (3, 3), "debe avisar del ultimo"


def test_barrido_vacio_no_revienta(escenario):
    predio, _ = escenario
    r = barre(predio, [], hilos=2)
    assert r.total == 0 and not r.vistas
