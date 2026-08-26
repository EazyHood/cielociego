"""Fraccion del PREDIO inservible por nube, leyendo la banda SCL.

POR QUE NO VALE `eo:cloud_cover`
--------------------------------
Ese campo se calcula sobre la tesela entera: 110 x 110 km = 12.100 km2.
El predio de Fundacion son 73,5 ha = 0,735 km2, el 0,006 % de la tesela.
Usar el numero de la tesela para decidir si SE VE EL PREDIO es medir un
decorado parecido a la partida. Puede fallar en las dos direcciones: la
tesela al 60 % con el predio despejado, o al 15 % con el predio tapado.

Este modulo lee la banda SCL (clasificacion de escena, 20 m/pixel) por
ventana, la recorta al poligono y cuenta pixeles. Nada mas.

LAS CLASES, Y LA DECISION QUE HAY QUE DECLARAR
----------------------------------------------
    0 sin dato        1 saturado/defectuoso   2 sombra orografica
    3 sombra de nube  4 vegetacion            5 sin vegetacion
    6 agua            7 sin clasificar        8 nube probable
    9 nube segura    10 cirro fino           11 nieve/hielo

Que cuenta como "ciego" no es obvio, y de eso depende el resultado. Por
eso se calculan DOS definiciones y se publican las dos:

  ESTRICTA  ciego = {0,1,3,8,9,10}          <- la de referencia
  AMPLIA    ciego = estricta + {2}          <- suma la sombra orografica

La 2 es dudosa a proposito: en llano es casi siempre agua oscura o suelo
humedo, no sombra real. Si las dos definiciones dan lo mismo, la eleccion
no importaba; si dan distinto, hay que decirlo. Nunca publicar una sola.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "3")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "1")

import rasterio  # noqa: E402
from rasterio.errors import NotGeoreferencedWarning  # noqa: E402
from rasterio.features import geometry_mask  # noqa: E402
from rasterio.warp import transform_geom  # noqa: E402
from rasterio.windows import from_bounds  # noqa: E402
from shapely.geometry import mapping, shape  # noqa: E402
from shapely.geometry.base import BaseGeometry  # noqa: E402

SIN_DATO, SATURADO, SOMBRA_OROG, SOMBRA_NUBE = 0, 1, 2, 3
VEGETACION, SIN_VEGETACION, AGUA, SIN_CLASIF = 4, 5, 6, 7
NUBE_PROB, NUBE_SEGURA, CIRRO, NIEVE = 8, 9, 10, 11

CIEGO_ESTRICTO = frozenset({SIN_DATO, SATURADO, SOMBRA_NUBE, NUBE_PROB, NUBE_SEGURA, CIRRO})
CIEGO_AMPLIO = CIEGO_ESTRICTO | {SOMBRA_OROG}

NOMBRES = {
    0: "sin_dato", 1: "saturado", 2: "sombra_orografica", 3: "sombra_nube",
    4: "vegetacion", 5: "sin_vegetacion", 6: "agua", 7: "sin_clasificar",
    8: "nube_probable", 9: "nube_segura", 10: "cirro", 11: "nieve",
}


@dataclass
class Vista:
    """Lo que el satelite pudo ver del predio en UNA pasada."""

    fecha: str
    id_toma: str
    pixeles: int
    ciego_estricto: float          # fraccion 0-1 del predio inservible
    ciego_amplio: float
    cc_tesela: float | None        # lo que declaraba la tesela, para contrastar
    histograma: dict[str, int]
    error: str | None = None

    @property
    def util_estricto(self) -> float:
        return 1.0 - self.ciego_estricto

    def sirve(self, umbral_ciego: float = 0.10) -> bool:
        """True si queda predio suficiente para mirar algo agronomico."""
        return self.error is None and self.ciego_estricto <= umbral_ciego

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _mascara_predio(src, geom_4326: BaseGeometry):
    """Ventana del raster que cubre el predio + mascara booleana del poligono.

    Devuelve (ventana, transform de la ventana, mascara donde True = DENTRO).
    """
    geom_ras = shape(transform_geom("EPSG:4326", src.crs, mapping(geom_4326)))
    ventana = from_bounds(*geom_ras.bounds, transform=src.transform).round_offsets().round_lengths()
    # margen de 1 pixel: from_bounds puede recortar el borde por redondeo
    ventana = ventana.round_lengths()
    tr = src.window_transform(ventana)
    alto, ancho = int(ventana.height), int(ventana.width)
    if alto <= 0 or ancho <= 0:
        raise ValueError("el predio no cae dentro del raster")
    dentro = ~geometry_mask(
        [mapping(geom_ras)], out_shape=(alto, ancho), transform=tr, invert=False
    )
    return ventana, dentro


def _lee_scl(href: str, geom_4326: BaseGeometry):
    """Abre el COG y devuelve (valores dentro del predio).

    Se silencia NotGeoreferencedWarning A PROPOSITO y solo aqui. Con 12 hilos
    sobre el mismo bucket, GDAL lo emitia en 9 de 602 escenas aunque el CRS
    era correcto (EPSG:32618) y la transformada no era la identidad. Se
    comprobo que NO afecta al resultado: las mismas 27 tomas medidas en serie
    y con 12 hilos dieron valores identicos, histograma incluido, 27 de 27.
    La prueba `test_medida_es_determinista_con_hilos` vigila que siga asi.
    Silenciarlo es lo correcto porque 9 avisos falsos en cada barrido tapan
    los avisos de verdad.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
        with rasterio.open(href) as src:
            ventana, dentro = _mascara_predio(src, geom_4326)
            datos = src.read(1, window=ventana)
    return datos, dentro


def mide_vista(
    href_scl: str,
    geom_4326: BaseGeometry,
    *,
    fecha: str = "",
    id_toma: str = "",
    cc_tesela: float | None = None,
) -> Vista:
    """Lee la SCL de una toma y devuelve que fraccion del predio es inservible.

    Nunca lanza por fallo de red o de lectura: devuelve la Vista con `error`
    puesto. Un barrido de 600 escenas no puede morir por una corrupta, pero
    tampoco puede fingir que esa escena estaba despejada.
    """
    vacio = Vista(fecha, id_toma, 0, float("nan"), float("nan"), cc_tesela, {})
    try:
        datos, dentro = _lee_scl(href_scl, geom_4326)
    except Exception as exc:  # noqa: BLE001 - se reporta, no se traga
        vacio.error = f"{type(exc).__name__}: {exc}"[:200]
        return vacio

    if datos.shape != dentro.shape:  # pragma: no cover - defensivo
        vacio.error = f"forma raster {datos.shape} != mascara {dentro.shape}"
        return vacio

    val = datos[dentro]
    n = int(val.size)
    if n == 0:
        vacio.error = "0 pixeles dentro del predio"
        return vacio

    clases, cuentas = np.unique(val, return_counts=True)
    hist = {NOMBRES.get(int(c), f"clase_{int(c)}"): int(k) for c, k in zip(clases, cuentas)}
    ciego_e = float(sum(k for c, k in zip(clases, cuentas) if int(c) in CIEGO_ESTRICTO)) / n
    ciego_a = float(sum(k for c, k in zip(clases, cuentas) if int(c) in CIEGO_AMPLIO)) / n

    return Vista(fecha, id_toma, n, ciego_e, ciego_a, cc_tesela, hist)
