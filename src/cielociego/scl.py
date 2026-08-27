"""Fraction of a field made unusable by cloud, from the scene classification band.

Not `eo:cloud_cover`: that is computed over the whole 110 x 110 km tile, and a
73 ha field is 0.006 % of it. This reads the 20 m classification band by window
and clips it to the polygon.

Two blind definitions are computed and both reported. See DECISIONS.md #3-#5.
"""
from __future__ import annotations

import os
import warnings
from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")
# GDAL retries range reads on its own, but without the codes spelled out it
# does not retry the ones S3 returns when it throttles.
os.environ.setdefault("GDAL_HTTP_MAX_RETRY", "5")
os.environ.setdefault("GDAL_HTTP_RETRY_DELAY", "2")
os.environ.setdefault("GDAL_HTTP_RETRY_CODES", "429,500,502,503,504")
os.environ.setdefault("GDAL_HTTP_TIMEOUT", "60")

import rasterio
from rasterio.errors import NotGeoreferencedWarning
from rasterio.features import geometry_mask
from rasterio.warp import transform_geom
from rasterio.windows import from_bounds
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry

NO_DATA, SATURATED, CAST_SHADOW, CLOUD_SHADOW = 0, 1, 2, 3
VEGETATION, NOT_VEGETATED, WATER, UNCLASSIFIED = 4, 5, 6, 7
CLOUD_MEDIUM, CLOUD_HIGH, CIRRUS, SNOW = 8, 9, 10, 11

# Below this the figure stops meaning anything: with 20 pixels a percentage
# only moves in 5-point steps and the polygon edge outweighs its interior.
# Small fields are legitimate, so this flags rather than refuses.
MIN_PIXELS = 25

BLIND_STRICT = frozenset({NO_DATA, SATURATED, CLOUD_SHADOW, CLOUD_MEDIUM, CLOUD_HIGH, CIRRUS})
BLIND_WIDE = BLIND_STRICT | {CAST_SHADOW}

CLASS_NAMES = {
    0: "sin_dato", 1: "saturado", 2: "sombra_orografica", 3: "sombra_nube",
    4: "vegetacion", 5: "sin_vegetacion", 6: "agua", 7: "sin_clasificar",
    8: "nube_probable", 9: "nube_segura", 10: "cirro", 11: "nieve",
}


@dataclass
class View:
    """What the satellite managed to see of the field on one pass."""

    date: str
    scene_id: str
    pixels: int
    blind_strict: float             # 0-1 fraction of the field that is unusable
    blind_wide: float
    tile_cloud: float | None        # what the tile claimed, for contrast
    histogram: dict[str, int]
    error: str | None = None
    warning: str | None = None      # the value stands, but read it with care

    @property
    def resolution_pct(self) -> float:
        """What one pixel is worth in percentage points -- the real precision."""
        return 100.0 / self.pixels if self.pixels else float("inf")

    @property
    def reliable(self) -> bool:
        return self.error is None and self.pixels >= MIN_PIXELS

    @property
    def usable_strict(self) -> float:
        return 1.0 - self.blind_strict

    def usable(self, umbral_ciego: float = 0.10) -> bool:
        """Enough field left to look at anything agronomic."""
        return self.error is None and self.blind_strict <= umbral_ciego

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def _field_mask(src, geom_4326: BaseGeometry):
    """Raster window covering the field, plus a boolean mask of the polygon."""
    geom_ras = shape(transform_geom("EPSG:4326", src.crs, mapping(geom_4326)))
    ventana = from_bounds(*geom_ras.bounds, transform=src.transform).round_offsets().round_lengths()
    # one-pixel margin: from_bounds can clip the edge through rounding
    ventana = ventana.round_lengths()
    tr = src.window_transform(ventana)
    alto, ancho = int(ventana.height), int(ventana.width)
    if alto <= 0 or ancho <= 0:
        raise ValueError("el field no cae dentro del raster")
    dentro = ~geometry_mask(
        [mapping(geom_ras)], out_shape=(alto, ancho), transform=tr, invert=False
    )
    return ventana, dentro


def _read_scl(href: str, geom_4326: BaseGeometry):
    """Abre el COG y devuelve (values dentro del field).

    Se silencia NotGeoreferencedWarning A PROPOSITO y solo aqui. Con 12 workers
    sobre el mismo bucket, GDAL lo emitia en 9 de 602 escenas aunque el CRS
    era correcto (EPSG:32618) y la transformada no era la identity. Se
    comprobo que NO afecta al resultado: las mismas 27 scenes medidas en serie
    y con 12 workers dieron values identicos, histogram incluido, 27 de 27.
    La prueba `test_medida_es_determinista_con_hilos` vigila que siga asi.
    Silenciarlo es lo correcto porque 9 warnings falsos en cada sweep tapan
    los warnings de verdad.
    """
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
        with rasterio.open(href) as src:
            ventana, dentro = _field_mask(src, geom_4326)
            datos = src.read(1, window=ventana)
    return datos, dentro


def measure_view(
    href_scl: str,
    geom_4326: BaseGeometry,
    *,
    date: str = "",
    scene_id: str = "",
    tile_cloud: float | None = None,
) -> View:
    """Read one acquisition's SCL and return the unusable fraction of the field.

    Never raises on a network or read failure: the View comes back with
    `error` set. A sweep of 600 scenes cannot die on one bad file -- and it
    must not pretend that file was clear either.
    """
    vacio = View(date, scene_id, 0, float("nan"), float("nan"), tile_cloud, {})
    try:
        datos, dentro = _read_scl(href_scl, geom_4326)
    except Exception as exc:
        vacio.error = f"{type(exc).__name__}: {exc}"[:200]
        return vacio

    if datos.shape != dentro.shape:  # pragma: no cover - defensivo
        vacio.error = f"forma raster {datos.shape} != mascara {dentro.shape}"
        return vacio

    val = datos[dentro]
    n = int(val.size)
    if n == 0:
        vacio.error = "0 pixels dentro del field"
        return vacio

    warning = None
    if n < MIN_PIXELS:
        warning = (f"solo {n} pixels ({n * 4 / 100:.2f} ha): el porcentaje se mueve "
                 f"de {100 / n:.0f} en {100 / n:.0f} puntos y el borde domina")

    clases, cuentas = np.unique(val, return_counts=True)
    # strict=True on purpose: were the two to disagree, zip() would truncate
    # silently and the histogram would come out short with nobody noticing.
    pares = list(zip(clases, cuentas, strict=True))
    hist = {CLASS_NAMES.get(int(c), f"clase_{int(c)}"): int(k) for c, k in pares}
    ciego_e = float(sum(k for c, k in pares if int(c) in BLIND_STRICT)) / n
    ciego_a = float(sum(k for c, k in pares if int(c) in BLIND_WIDE)) / n

    return View(date, scene_id, n, ciego_e, ciego_a, tile_cloud, hist, warning=warning)
