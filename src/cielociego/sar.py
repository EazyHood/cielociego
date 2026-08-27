"""Serie temporal de radar sobre el predio, con Sentinel-1 RTC.

QUE DATO SE USA Y POR QUE
-------------------------
NO el GRD crudo. El GRD de nivel 1 viene en geometria de radar, sin
geocodificar y sin corregir por terreno: no se puede recortar por lat/lon ni
comparar entre fechas. Ademas en AWS vive en un bucket de pago por peticionario.

Se usa **Sentinel-1 RTC** (Radiometrically Terrain Corrected) del Planetary
Computer: ya proyectado a UTM, a 10 m, en gamma0 lineal, y con **firma anonima**
-- sin cuenta, sin clave y sin coste, igual que el optico.

LAS DOS TRAMPAS QUE ARRUINAN UNA SERIE DE RADAR
-----------------------------------------------
1. **Mezclar orbitas.** La retrodispersion depende del angulo de incidencia y
   de la direccion de mirada. Dos pasadas del mismo dia desde orbitas distintas
   dan valores distintos del MISMO cultivo sin que haya cambiado nada. Aqui la
   serie se agrupa SIEMPRE por orbita relativa y nunca se promedian entre si;
   sobre este predio hay tres (142 desc, 77 asc, 69 desc).

2. **Promediar en decibelios.** El dB es logaritmico: promediar dB da la media
   geometrica, no la aritmetica, y sesga el resultado hacia abajo. Lo correcto
   es promediar la **potencia lineal** y convertir despues. La diferencia sobre
   un predio heterogeneo llega a varias decimas de dB, que es justo el orden de
   lo que se quiere detectar. `media_db()` lo hace bien y hay una prueba que lo
   vigila.
"""
from __future__ import annotations

import os
import threading
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import numpy as np
import requests

from .predios import Predio
from .red import sesion as _sesion_con_reintentos

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
COLECCION = "sentinel-1-rtc"

# Los RTC son .tiff (dos efes): la lista de extensiones de scl.py solo admite
# .tif y bloquearia la lectura. Se amplia aqui, en vez de tocar la del optico.
os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif,.tiff"

import rasterio  # noqa: E402
from rasterio.errors import NotGeoreferencedWarning  # noqa: E402

from .scl import _mascara_predio  # noqa: E402


@dataclass
class Retro:
    """Retrodispersion media del predio en una pasada."""

    fecha: str
    orbita_rel: int
    estado: str            # ascending | descending
    plataforma: str
    pixeles: int
    vv_db: float
    vh_db: float
    error: str | None = None

    @property
    def razon_db(self) -> float:
        """VH - VV en dB. Sube con la estructura de la vegetacion."""
        return self.vh_db - self.vv_db

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["razon_db"] = None if self.error else round(self.razon_db, 3)
        return d


def media_db(potencia_lineal: np.ndarray) -> float:
    """Media en dB hecha bien: promediar la POTENCIA, luego convertir.

    Promediar decibelios directamente da la media geometrica y sesga a la baja.
    Se descartan ceros y no finitos (borde del RTC, sombra de radar).
    """
    v = np.asarray(potencia_lineal, dtype="float64")
    v = v[np.isfinite(v) & (v > 0)]
    if v.size == 0:
        return float("nan")
    return float(10.0 * np.log10(v.mean()))


def busca_rtc(
    predio: Predio, desde: str, hasta: str, *, sesion: requests.Session | None = None
) -> list[dict[str, Any]]:
    """Items Sentinel-1 RTC que tocan el predio, paginando hasta el final."""
    ses = sesion or _sesion_con_reintentos()
    payload: dict[str, Any] = {
        "collections": [COLECCION],
        "bbox": list(predio.bbox),
        "datetime": f"{desde}T00:00:00Z/{hasta}T23:59:59Z",
        "limit": 100,
    }
    items: list[dict[str, Any]] = []
    while True:
        doc = ses.post(f"{PC_STAC}/search", json=payload, timeout=120).json()
        items.extend(doc.get("features", []))
        sig = next((e for e in doc.get("links", []) if e.get("rel") == "next"), None)
        if not sig or not sig.get("body"):
            break
        payload = sig["body"]
    return items


class Credencial:
    """Token de lectura del Planetary Computer, pedido UNA vez y reutilizado.

    POR QUE NO SE FIRMA CADA FICHERO
    --------------------------------
    La primera version llamaba al endpoint de firma por cada banda de cada
    escena: 2 peticiones x 590 escenas = 1.180 llamadas con 8 hilos. El
    servidor devolvio **429 Too Many Requests** y solo pasaron 54 de 590
    medidas -- y lo peor es que habrian quedado registradas como "el radar no
    tenia dato", que es una conclusion falsa por un fallo de fontaneria.

    Mirando el token se ve que lleva `sr=c`: es de CONTENEDOR, no de fichero.
    Vale para todas las escenas de la coleccion. Se pide uno, se guarda con su
    caducidad y se renueva solo cuando va a expirar. De 1.180 llamadas a 1.

    Es anonimo: sin cuenta, sin clave y sin coste.
    """

    MARGEN = timedelta(minutes=5)  # renovar antes de que caduque de verdad

    def __init__(self, coleccion: str = COLECCION) -> None:
        self.coleccion = coleccion
        self._token: str | None = None
        self._caduca: datetime | None = None
        self._cerrojo = threading.Lock()
        self.peticiones = 0  # para poder afirmar cuantas se hicieron

    def token(self, sesion: requests.Session | None = None) -> str:
        with self._cerrojo:
            ahora = datetime.now(timezone.utc)
            if self._token and self._caduca and ahora < self._caduca - self.MARGEN:
                return self._token
            ses = sesion or _sesion_con_reintentos()
            r = ses.get(f"{PC_TOKEN}/{self.coleccion}", timeout=60)
            r.raise_for_status()
            doc = r.json()
            self._token = doc["token"]
            self._caduca = datetime.fromisoformat(doc["msft:expiry"].replace("Z", "+00:00"))
            self.peticiones += 1
            return self._token

    def firma(self, href: str, sesion: requests.Session | None = None) -> str:
        """Pega el token al href. Si ya lo trae, lo deja como esta."""
        if "?" in href:
            return href
        return f"{href}?{self.token(sesion)}"


# Una credencial por coleccion, creada cuando hace falta. Antes era un unico
# singleton de modulo fijado a `sentinel-1-rtc`: funcionaba, pero era estado
# global que se filtraba entre pruebas y que habria servido el token
# equivocado el dia que se leyera otra coleccion.
_CREDENCIALES: dict[str, Credencial] = {}
_CERROJO_CRED = threading.Lock()


def credencial(coleccion: str = COLECCION) -> Credencial:
    """Credencial de esa coleccion, reutilizada si ya existe."""
    with _CERROJO_CRED:
        if coleccion not in _CREDENCIALES:
            _CREDENCIALES[coleccion] = Credencial(coleccion)
        return _CREDENCIALES[coleccion]


def olvida_credenciales() -> None:
    """Tira los tokens guardados. Para las pruebas y para forzar una renovacion."""
    with _CERROJO_CRED:
        _CREDENCIALES.clear()


def firma(
    href: str, *, sesion: requests.Session | None = None, coleccion: str = COLECCION
) -> str:
    """Firma anonima del Planetary Computer, con el token de contenedor cacheado."""
    return credencial(coleccion).firma(href, sesion)


def mide_retro(
    item: dict[str, Any], predio: Predio, *, sesion: requests.Session | None = None
) -> Retro:
    """Lee VV y VH del predio en una pasada y devuelve las medias en dB."""
    p = item.get("properties", {})
    base = Retro(
        fecha=p.get("datetime", "")[:10],
        orbita_rel=int(p.get("sat:relative_orbit") or -1),
        estado=p.get("sat:orbit_state", "?"),
        plataforma=p.get("platform", "?"),
        pixeles=0,
        vv_db=float("nan"),
        vh_db=float("nan"),
    )
    try:
        valores: dict[str, np.ndarray] = {}
        with rasterio.Env(CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff"):
            import warnings

            for pol in ("vv", "vh"):
                href = firma(item["assets"][pol]["href"], sesion=sesion)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
                    with rasterio.open(href) as src:
                        ventana, dentro = _mascara_predio(src, predio.geometria)
                        valores[pol] = src.read(1, window=ventana)[dentro]
    except Exception as exc:
        base.error = f"{type(exc).__name__}: {exc}"[:180]
        return base

    base.pixeles = int(valores["vv"].size)
    base.vv_db = round(media_db(valores["vv"]), 3)
    base.vh_db = round(media_db(valores["vh"]), 3)
    if not np.isfinite(base.vv_db) or not np.isfinite(base.vh_db):
        base.error = "sin pixeles validos (borde del RTC o sombra de radar)"
    return base


def elige_orbita(items: Iterable[dict[str, Any]]) -> int | None:
    """Orbita relativa con mas escenas sobre ESTE predio.

    POR QUE NO SE PUEDE FIJAR EN EL CODIGO
    --------------------------------------
    Las orbitas relativas dependen de DONDE esta el predio. La 77 cubre la
    Zona Bananera del Magdalena, pero en Uraba -- la principal zona bananera
    de Colombia -- no pasa: alli son la 142 y la 48. Una constante fija en el
    codigo dejaba la serie de radar VACIA en cualquier sitio distinto de
    aquellos dos predios, y ademas en silencio.

    Se elige la mas poblada porque da la serie mas densa. El empate se rompe
    por el numero de orbita mas bajo, para que dos ejecuciones sobre los
    mismos datos den siempre lo mismo.
    """
    cuenta: dict[int, int] = {}
    for it in items:
        orb = it.get("properties", {}).get("sat:relative_orbit")
        if orb is not None:
            cuenta[int(orb)] = cuenta.get(int(orb), 0) + 1
    if not cuenta:
        return None
    return min(cuenta, key=lambda o: (-cuenta[o], o))


def reparto_orbitas(items: Iterable[dict[str, Any]]) -> dict[int, int]:
    """Cuantas escenas aporta cada orbita. Para poder declararlo en el informe."""
    cuenta: dict[int, int] = {}
    for it in items:
        orb = it.get("properties", {}).get("sat:relative_orbit")
        if orb is not None:
            cuenta[int(orb)] = cuenta.get(int(orb), 0) + 1
    return dict(sorted(cuenta.items(), key=lambda kv: (-kv[1], kv[0])))


def por_orbita(retros: Iterable[Retro]) -> dict[int, list[Retro]]:
    """Agrupa por orbita relativa. NUNCA promediar entre grupos."""
    salida: dict[int, list[Retro]] = {}
    for r in retros:
        if r.error is None:
            salida.setdefault(r.orbita_rel, []).append(r)
    for v in salida.values():
        v.sort(key=lambda x: x.fecha)
    return dict(sorted(salida.items(), key=lambda kv: -len(kv[1])))


def cubre_hueco(retros: Sequence[Retro], inicio: str, fin: str) -> list[Retro]:
    """Pasadas de radar con medida valida dentro de un tramo ciego."""
    return [r for r in retros if r.error is None and inicio <= r.fecha <= fin]
