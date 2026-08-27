"""Tests for the SCL measurement. No network: a known raster is built.

La pregunta que responden: si YO pinto el raster, cuenta lo que pinte?
Con control por mutacion -- cambiar un pixel debe mover el resultado en la
direccion y la cantidad esperadas, o la mascara no esta haciendo nada.
"""
from __future__ import annotations

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box

from cielociego import scl
from cielociego.scl import BLIND_STRICT, BLIND_WIDE, measure_view

# UTM 18N raster, 10x10 pixels of 20 m, corner at (500000, 1150000)
CRS = "EPSG:32618"
PX = 20.0
X0, Y0 = 500000.0, 1150000.0


@pytest.fixture()
def raster(tmp_path):
    """Returns a function that writes an SCL with whatever values you give it."""

    def escribe(matriz: np.ndarray, name="scl.tif"):
        path = tmp_path / name
        with rasterio.open(
            path, "w", driver="GTiff", height=matriz.shape[0], width=matriz.shape[1],
            count=1, dtype="uint8", crs=CRS, transform=from_origin(X0, Y0, PX, PX),
        ) as dst:
            dst.write(matriz.astype("uint8"), 1)
        return str(path)

    return escribe


def geom_utm(filas, cols):
    """Polygon in 4326 covering exactly the first `rows` by `cols` pixels."""
    import pyproj
    from shapely.ops import transform as stransform

    caja = box(X0 + 0.5, Y0 - filas * PX + 0.5, X0 + cols * PX - 0.5, Y0 - 0.5)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    return stransform(proy, caja)


def test_all_vegetacion_is_zero_blind(raster):
    r = raster(np.full((10, 10), scl.VEGETATION))
    v = measure_view(r, geom_utm(10, 10))
    assert v.error is None
    assert v.pixels == 100
    assert v.blind_strict == 0.0
    assert v.histogram == {"vegetacion": 100}


def test_all_cloud_is_uno(raster):
    v = measure_view(raster(np.full((10, 10), scl.CLOUD_HIGH)), geom_utm(10, 10))
    assert v.blind_strict == 1.0 and v.usable_strict == 0.0


@pytest.mark.parametrize("clase", sorted(BLIND_STRICT))
def test_each_clase_ciega_counts_como_ciega(raster, clase):
    v = measure_view(raster(np.full((4, 4), clase)), geom_utm(4, 4))
    assert v.blind_strict == 1.0, f"la clase {clase} deberia contar como ciega"


@pytest.mark.parametrize("clase", [scl.VEGETATION, scl.NOT_VEGETATED, scl.WATER, scl.UNCLASSIFIED])
def test_each_clase_usable_not_counts_como_ciega(raster, clase):
    v = measure_view(raster(np.full((4, 4), clase)), geom_utm(4, 4))
    assert v.blind_strict == 0.0


def test_one_pixel_in_a_hundred_moves_it_by_exactly_a_hundredth(raster):
    """Hard control: 1 pixel in 100 must move the result by 0.01. No more, no less."""
    m = np.full((10, 10), scl.VEGETATION)
    antes = measure_view(raster(m.copy(), "a.tif"), geom_utm(10, 10)).blind_strict
    m[3, 3] = scl.CLOUD_HIGH
    despues = measure_view(raster(m, "b.tif"), geom_utm(10, 10)).blind_strict
    assert antes == 0.0
    assert despues == pytest.approx(0.01, abs=1e-9)


def test_the_mask_really_clips(raster):
    """Half cloud, half vegetation; looking only at the clear half must give 0.

    Si la mascara no hiciera nada, saldria 0,5 y esta prueba lo pilla.
    """
    m = np.full((10, 10), scl.VEGETATION)
    m[:, 5:] = scl.CLOUD_HIGH
    path = raster(m)
    entero = measure_view(path, geom_utm(10, 10))
    solo_limpio = measure_view(path, geom_utm(10, 5))
    assert entero.blind_strict == pytest.approx(0.5)
    assert solo_limpio.blind_strict == 0.0
    assert solo_limpio.pixels == 50


def test_strict_and_wide_differ_only_in_cast_shadow(raster):
    m = np.full((10, 10), scl.VEGETATION)
    m[0, :] = scl.CAST_SHADOW  # 10 de 100
    v = measure_view(raster(m), geom_utm(10, 10))
    assert v.blind_strict == 0.0
    assert v.blind_wide == pytest.approx(0.10)
    assert BLIND_WIDE - BLIND_STRICT == {scl.CAST_SHADOW}


def test_a_missing_file_returns_an_error_rather_than_raising(raster):
    v = measure_view("/no/existe/scl.tif", geom_utm(4, 4))
    assert v.error is not None and np.isnan(v.blind_strict)


def test_a_field_outside_the_raster_returns_an_error(raster):
    import pyproj
    from shapely.ops import transform as stransform

    lejos = box(X0 + 100_000, Y0 - 100_100, X0 + 100_100, Y0 - 100_000)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    v = measure_view(raster(np.full((10, 10), 4)), stransform(proy, lejos))
    assert v.error is not None


def test_works_usa_the_threshold(raster):
    m = np.full((10, 10), scl.VEGETATION)
    m[0, :5] = scl.CLOUD_HIGH  # 5 % ciego
    v = measure_view(raster(m), geom_utm(10, 10))
    assert v.usable(umbral_ciego=0.10) is True
    assert v.usable(umbral_ciego=0.01) is False


def test_the_charts_not_llevan_colour_of_text_fixed():
    """Labels must follow the reader's theme, not stay fixed black.

    Si alguien vuelve a poner un hex literal para el texto, el informe se
    vuelve ilegible en tema oscuro y nadie lo nota hasta publicarlo.
    """
    from cielociego import charts

    svg = charts.distribution([0.0, 0.5, 1.0], [10.0, 50.0, 90.0])
    assert "var(--tinta)" in svg, "el texto debe usar la variable del tema"
    assert charts.INK not in svg, "quedo un centinela sin sustituir"
    assert charts.GREY not in svg


def test_measure_is_deterministic_with_threads(raster):
    """The same scene measured serially and threaded must give exactly the same.

    Guarda el silenciado de NotGeoreferencedWarning en `_read_scl`: se silencia
    porque se comprobo que es cosmetico. Si algun dia la concurrencia SI
    cambiara el resultado, esta prueba lo destapa en vez de dejarlo pasar.
    """
    from concurrent.futures import ThreadPoolExecutor

    m = np.full((12, 12), scl.VEGETATION)
    m[2:5, 2:5] = scl.CLOUD_HIGH
    m[7, :] = scl.CLOUD_SHADOW
    path = raster(m)
    geom = geom_utm(12, 12)

    def clave(v):
        return (v.pixels, v.blind_strict, v.blind_wide, sorted(v.histogram.items()), v.error)

    serie = [clave(measure_view(path, geom)) for _ in range(8)]
    with ThreadPoolExecutor(8) as ex:
        paralelo = [clave(v) for v in ex.map(lambda _: measure_view(path, geom), range(8))]

    assert len(set(map(str, serie))) == 1, "la medida en serie ya no es estable"
    assert serie == paralelo, "los workers cambian el resultado"


def test_other_warnings_are_not_silenced(raster, recwarn):
    """The silencing must be surgical: NotGeoreferencedWarning only.

    Un `catch_warnings` demasiado ancho taparia warnings reales de numpy o
    rasterio, que es justo lo que no queremos.
    """
    import warnings as _w

    from cielociego.scl import _read_scl

    with _w.catch_warnings(record=True) as capturados:
        _w.simplefilter("always")
        _w.warn("warning de prueba que SI debe verse", UserWarning, stacklevel=2)
        _read_scl(raster(np.full((6, 6), scl.VEGETATION)), geom_utm(6, 6))
    assert any("SI debe verse" in str(c.message) for c in capturados)


# --- save de tamano minimo -----------------------------------------------
def test_a_tiny_field_is_flagged_not_passed_off_as_good(raster):
    """8 pixels are not enough for percentages: the figure comes out flagged."""
    from cielociego.scl import MIN_PIXELS

    v = measure_view(raster(np.full((3, 3), scl.VEGETATION)), geom_utm(3, 3))
    assert v.error is None, "no se falla: hay fields pequenos legitimos"
    assert v.pixels < MIN_PIXELS
    assert v.warning is not None and "pixels" in v.warning
    assert v.reliable is False


def test_a_normal_field_carries_no_warning(raster):
    v = measure_view(raster(np.full((10, 10), scl.VEGETATION)), geom_utm(10, 10))
    assert v.warning is None and v.reliable is True


def test_the_declared_resolution_is_the_real_one(raster):
    """With 25 pixels the percentage only moves in 4-point steps."""
    v = measure_view(raster(np.full((5, 5), scl.VEGETATION)), geom_utm(5, 5))
    assert v.pixels == 25
    assert v.resolution_pct == pytest.approx(4.0)


def test_the_warning_travels_in_the_json(raster):
    v = measure_view(raster(np.full((2, 2), scl.CLOUD_HIGH)), geom_utm(2, 2))
    assert "warning" in v.dict() and v.dict()["warning"]
