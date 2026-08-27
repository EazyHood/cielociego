"""Pruebas de la medida sobre SCL. Sin red: se fabrica un raster conocido.

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
from cielociego.scl import CIEGO_AMPLIO, CIEGO_ESTRICTO, mide_vista

# raster UTM 18N de 10x10 pixeles de 20 m, esquina en (500000, 1150000)
CRS = "EPSG:32618"
PX = 20.0
X0, Y0 = 500000.0, 1150000.0


@pytest.fixture()
def raster(tmp_path):
    """Devuelve una funcion que escribe un SCL con los valores que le des."""

    def escribe(matriz: np.ndarray, nombre="scl.tif"):
        ruta = tmp_path / nombre
        with rasterio.open(
            ruta, "w", driver="GTiff", height=matriz.shape[0], width=matriz.shape[1],
            count=1, dtype="uint8", crs=CRS, transform=from_origin(X0, Y0, PX, PX),
        ) as dst:
            dst.write(matriz.astype("uint8"), 1)
        return str(ruta)

    return escribe


def geom_utm(filas, cols):
    """Poligono en 4326 que cubre exactamente las primeras `filas` x `cols` px."""
    import pyproj
    from shapely.ops import transform as stransform

    caja = box(X0 + 0.5, Y0 - filas * PX + 0.5, X0 + cols * PX - 0.5, Y0 - 0.5)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    return stransform(proy, caja)


def test_todo_vegetacion_es_cero_ciego(raster):
    r = raster(np.full((10, 10), scl.VEGETACION))
    v = mide_vista(r, geom_utm(10, 10))
    assert v.error is None
    assert v.pixeles == 100
    assert v.ciego_estricto == 0.0
    assert v.histograma == {"vegetacion": 100}


def test_todo_nube_es_uno(raster):
    v = mide_vista(raster(np.full((10, 10), scl.NUBE_SEGURA)), geom_utm(10, 10))
    assert v.ciego_estricto == 1.0 and v.util_estricto == 0.0


@pytest.mark.parametrize("clase", sorted(CIEGO_ESTRICTO))
def test_cada_clase_ciega_cuenta_como_ciega(raster, clase):
    v = mide_vista(raster(np.full((4, 4), clase)), geom_utm(4, 4))
    assert v.ciego_estricto == 1.0, f"la clase {clase} deberia contar como ciega"


@pytest.mark.parametrize("clase", [scl.VEGETACION, scl.SIN_VEGETACION, scl.AGUA, scl.SIN_CLASIF])
def test_cada_clase_util_no_cuenta_como_ciega(raster, clase):
    v = mide_vista(raster(np.full((4, 4), clase)), geom_utm(4, 4))
    assert v.ciego_estricto == 0.0


def test_mutacion_un_pixel_mueve_exactamente_un_centesimo(raster):
    """Control duro: 1 pixel de 100 debe mover el resultado 0,01. Ni mas ni menos."""
    m = np.full((10, 10), scl.VEGETACION)
    antes = mide_vista(raster(m.copy(), "a.tif"), geom_utm(10, 10)).ciego_estricto
    m[3, 3] = scl.NUBE_SEGURA
    despues = mide_vista(raster(m, "b.tif"), geom_utm(10, 10)).ciego_estricto
    assert antes == 0.0
    assert despues == pytest.approx(0.01, abs=1e-9)


def test_la_mascara_recorta_de_verdad(raster):
    """Mitad nube / mitad vegetacion; si miro solo la mitad limpia debe dar 0.

    Si la mascara no hiciera nada, saldria 0,5 y esta prueba lo pilla.
    """
    m = np.full((10, 10), scl.VEGETACION)
    m[:, 5:] = scl.NUBE_SEGURA
    ruta = raster(m)
    entero = mide_vista(ruta, geom_utm(10, 10))
    solo_limpio = mide_vista(ruta, geom_utm(10, 5))
    assert entero.ciego_estricto == pytest.approx(0.5)
    assert solo_limpio.ciego_estricto == 0.0
    assert solo_limpio.pixeles == 50


def test_estricta_y_amplia_solo_difieren_en_la_sombra_orografica(raster):
    m = np.full((10, 10), scl.VEGETACION)
    m[0, :] = scl.SOMBRA_OROG  # 10 de 100
    v = mide_vista(raster(m), geom_utm(10, 10))
    assert v.ciego_estricto == 0.0
    assert v.ciego_amplio == pytest.approx(0.10)
    assert CIEGO_AMPLIO - CIEGO_ESTRICTO == {scl.SOMBRA_OROG}


def test_fichero_inexistente_devuelve_error_no_lanza(raster):
    v = mide_vista("/no/existe/scl.tif", geom_utm(4, 4))
    assert v.error is not None and np.isnan(v.ciego_estricto)


def test_predio_fuera_del_raster_devuelve_error(raster):
    import pyproj
    from shapely.ops import transform as stransform

    lejos = box(X0 + 100_000, Y0 - 100_100, X0 + 100_100, Y0 - 100_000)
    proy = pyproj.Transformer.from_crs(CRS, "EPSG:4326", always_xy=True).transform
    v = mide_vista(raster(np.full((10, 10), 4)), stransform(proy, lejos))
    assert v.error is not None


def test_sirve_usa_el_umbral(raster):
    m = np.full((10, 10), scl.VEGETACION)
    m[0, :5] = scl.NUBE_SEGURA  # 5 % ciego
    v = mide_vista(raster(m), geom_utm(10, 10))
    assert v.sirve(umbral_ciego=0.10) is True
    assert v.sirve(umbral_ciego=0.01) is False


def test_las_graficas_no_llevan_color_de_texto_fijo():
    """Las etiquetas deben heredar el tema del lector, no quedar en negro fijo.

    Si alguien vuelve a poner un hex literal para el texto, el informe se
    vuelve ilegible en tema oscuro y nadie lo nota hasta publicarlo.
    """
    from cielociego import graficas

    svg = graficas.distribucion([0.0, 0.5, 1.0], [10.0, 50.0, 90.0])
    assert "var(--tinta)" in svg, "el texto debe usar la variable del tema"
    assert graficas.TINTA not in svg, "quedo un centinela sin sustituir"
    assert graficas.GRIS not in svg


def test_medida_es_determinista_con_hilos(raster):
    """La misma escena medida en serie y con hilos debe dar EXACTAMENTE lo mismo.

    Guarda el silenciado de NotGeoreferencedWarning en `_lee_scl`: se silencia
    porque se comprobo que es cosmetico. Si algun dia la concurrencia SI
    cambiara el resultado, esta prueba lo destapa en vez de dejarlo pasar.
    """
    from concurrent.futures import ThreadPoolExecutor

    m = np.full((12, 12), scl.VEGETACION)
    m[2:5, 2:5] = scl.NUBE_SEGURA
    m[7, :] = scl.SOMBRA_NUBE
    ruta = raster(m)
    geom = geom_utm(12, 12)

    def clave(v):
        return (v.pixeles, v.ciego_estricto, v.ciego_amplio, sorted(v.histograma.items()), v.error)

    serie = [clave(mide_vista(ruta, geom)) for _ in range(8)]
    with ThreadPoolExecutor(8) as ex:
        paralelo = [clave(v) for v in ex.map(lambda _: mide_vista(ruta, geom), range(8))]

    assert len(set(map(str, serie))) == 1, "la medida en serie ya no es estable"
    assert serie == paralelo, "los hilos cambian el resultado"


def test_no_se_silencian_otros_avisos(raster, recwarn):
    """El silenciado debe ser QUIRURGICO: solo NotGeoreferencedWarning.

    Un `catch_warnings` demasiado ancho taparia avisos reales de numpy o
    rasterio, que es justo lo que no queremos.
    """
    import warnings as _w

    from cielociego.scl import _lee_scl

    with _w.catch_warnings(record=True) as capturados:
        _w.simplefilter("always")
        _w.warn("aviso de prueba que SI debe verse", UserWarning, stacklevel=2)
        _lee_scl(raster(np.full((6, 6), scl.VEGETACION)), geom_utm(6, 6))
    assert any("SI debe verse" in str(c.message) for c in capturados)


# --- guarda de tamano minimo -----------------------------------------------
def test_un_predio_diminuto_se_marca_en_vez_de_pasar_por_bueno(raster):
    """8 pixeles no dan para hablar de porcentajes: la cifra sale AVISADA."""
    from cielociego.scl import PIXELES_MINIMOS

    v = mide_vista(raster(np.full((3, 3), scl.VEGETACION)), geom_utm(3, 3))
    assert v.error is None, "no se falla: hay predios pequenos legitimos"
    assert v.pixeles < PIXELES_MINIMOS
    assert v.aviso is not None and "pixeles" in v.aviso
    assert v.fiable is False


def test_un_predio_normal_no_lleva_aviso(raster):
    v = mide_vista(raster(np.full((10, 10), scl.VEGETACION)), geom_utm(10, 10))
    assert v.aviso is None and v.fiable is True


def test_la_resolucion_declarada_es_la_real(raster):
    """Con 25 pixeles el porcentaje solo se mueve de 4 en 4 puntos."""
    v = mide_vista(raster(np.full((5, 5), scl.VEGETACION)), geom_utm(5, 5))
    assert v.pixeles == 25
    assert v.resolucion_pct == pytest.approx(4.0)


def test_el_aviso_viaja_en_el_json(raster):
    v = mide_vista(raster(np.full((2, 2), scl.NUBE_SEGURA)), geom_utm(2, 2))
    assert "aviso" in v.dict() and v.dict()["aviso"]
