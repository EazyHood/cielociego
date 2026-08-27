"""Backscatter time series over a field, from Sentinel-1 RTC.

RTC rather than raw GRD, one relative orbit per series, linear power averaged
before conversion to dB, and one container token instead of a signature per
file. Each of those is a decision that changed a result: see DECISIONS.md #6-#9.
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

from .fields import Field
from .net import session as _sesion_con_reintentos

PC_STAC = "https://planetarycomputer.microsoft.com/api/stac/v1"
PC_TOKEN = "https://planetarycomputer.microsoft.com/api/sas/v1/token"
COLLECTION = "sentinel-1-rtc"

# RTC files are .tiff: scl.py's extension list only allows .tif and would
# block the read. Widened here rather than touching the optical side.
os.environ["CPL_VSIL_CURL_ALLOWED_EXTENSIONS"] = ".tif,.tiff"

import rasterio  # noqa: E402
from rasterio.errors import NotGeoreferencedWarning  # noqa: E402

from .scl import _field_mask  # noqa: E402


@dataclass
class Backscatter:
    """Mean backscatter over the field on one pass."""

    date: str
    rel_orbit: int
    orbit_state: str            # ascending | descending
    platform: str
    pixels: int
    vv_db: float
    vh_db: float
    error: str | None = None

    @property
    def ratio_db(self) -> float:
        """VH minus VV in dB. Rises with vegetation structure."""
        return self.vh_db - self.vv_db

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["ratio_db"] = None if self.error else round(self.ratio_db, 3)
        return d


def mean_db(potencia_lineal: np.ndarray) -> float:
    """Mean in dB done properly: average the power, then convert.

    Averaging decibels gives the geometric mean and biases low. Zeros and
    non-finite values are dropped (RTC edge, radar shadow).
    """
    v = np.asarray(potencia_lineal, dtype="float64")
    v = v[np.isfinite(v) & (v > 0)]
    if v.size == 0:
        return float("nan")
    return float(10.0 * np.log10(v.mean()))


def search_rtc(
    field: Field, start: str, end: str, *, session: requests.Session | None = None
) -> list[dict[str, Any]]:
    """Sentinel-1 RTC items touching the field, paged to the end."""
    ses = session or _sesion_con_reintentos()
    payload: dict[str, Any] = {
        "collections": [COLLECTION],
        "bbox": list(field.bbox),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
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


class Credential:
    """Planetary Computer read token, requested once and reused.

    Signing every file meant 1,180 calls and a 429 that silently dropped 536
    of 590 measurements. The token is container-scoped (`sr=c`), so one
    request covers the whole collection. Anonymous: no account, no key, no
    cost. See DECISIONS.md #9.
    """

    MARGEN = timedelta(minutes=5)  # refresh before it actually expires

    def __init__(self, collection: str = COLLECTION) -> None:
        self.collection = collection
        self._token: str | None = None
        self._caduca: datetime | None = None
        self._cerrojo = threading.Lock()
        self.requests_made = 0  # so the count can be asserted

    def token(self, session: requests.Session | None = None) -> str:
        with self._cerrojo:
            ahora = datetime.now(timezone.utc)
            if self._token and self._caduca and ahora < self._caduca - self.MARGEN:
                return self._token
            ses = session or _sesion_con_reintentos()
            r = ses.get(f"{PC_TOKEN}/{self.collection}", timeout=60)
            r.raise_for_status()
            doc = r.json()
            self._token = doc["token"]
            self._caduca = datetime.fromisoformat(doc["msft:expiry"].replace("Z", "+00:00"))
            self.requests_made += 1
            return self._token

    def sign(self, href: str, session: requests.Session | None = None) -> str:
        """Append the token to the href. Left alone if it already has one."""
        if "?" in href:
            return href
        return f"{href}?{self.token(session)}"


# One credential per collection, created on demand. This used to be a single
# module-level singleton pinned to `sentinel-1-rtc`: it worked, but the state
# leaked between tests and it would have served the wrong token the day
# another collection was read.
_CREDENCIALES: dict[str, Credential] = {}
_CERROJO_CRED = threading.Lock()


def credential(collection: str = COLLECTION) -> Credential:
    """Credential for that collection, reused if it already exists."""
    with _CERROJO_CRED:
        if collection not in _CREDENCIALES:
            _CREDENCIALES[collection] = Credential(collection)
        return _CREDENCIALES[collection]


def forget_credentials() -> None:
    """Drop the cached tokens. For tests, and to force a refresh."""
    with _CERROJO_CRED:
        _CREDENCIALES.clear()


def sign(
    href: str, *, session: requests.Session | None = None, collection: str = COLLECTION
) -> str:
    """Anonymous Planetary Computer signature, container token cached."""
    return credential(collection).sign(href, session)


def measure_backscatter(
    item: dict[str, Any], field: Field, *, session: requests.Session | None = None
) -> Backscatter:
    """Read VV and VH over the field and return the means in dB."""
    p = item.get("properties", {})
    base = Backscatter(
        date=p.get("datetime", "")[:10],
        rel_orbit=int(p.get("sat:relative_orbit") or -1),
        orbit_state=p.get("sat:orbit_state", "?"),
        platform=p.get("platform", "?"),
        pixels=0,
        vv_db=float("nan"),
        vh_db=float("nan"),
    )
    try:
        values: dict[str, np.ndarray] = {}
        with rasterio.Env(CPL_VSIL_CURL_ALLOWED_EXTENSIONS=".tif,.tiff"):
            import warnings

            for pol in ("vv", "vh"):
                href = sign(item["assets"][pol]["href"], session=session)
                with warnings.catch_warnings():
                    warnings.filterwarnings("ignore", category=NotGeoreferencedWarning)
                    with rasterio.open(href) as src:
                        ventana, dentro = _field_mask(src, field.geometry)
                        values[pol] = src.read(1, window=ventana)[dentro]
    except Exception as exc:
        base.error = f"{type(exc).__name__}: {exc}"[:180]
        return base

    base.pixels = int(values["vv"].size)
    base.vv_db = round(mean_db(values["vv"]), 3)
    base.vh_db = round(mean_db(values["vh"]), 3)
    if not np.isfinite(base.vv_db) or not np.isfinite(base.vh_db):
        base.error = "sin pixels validos (borde del RTC o sombra de radar)"
    return base


def pick_orbit(items: Iterable[dict[str, Any]]) -> int | None:
    """Relative orbit best covering this field.

    POR QUE NO SE PUEDE FIJAR EN EL CODIGO
    --------------------------------------
    Las orbitas relativas dependen de DONDE esta el field. La 77 cubre la
    Zona Bananera del Magdalena, pero en Uraba -- la principal zona bananera
    de Colombia -- no pasa: alli son la 142 y la 48. Una constante fija en el
    codigo dejaba la serie de radar VACIA en cualquier sitio distinto de
    aquellos dos fields, y ademas en silencio.

    Se elige la mas poblada porque da la serie mas densa. El empate se rompe
    por el numero de orbit mas bajo, para que dos ejecuciones sobre los
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


def orbit_breakdown(items: Iterable[dict[str, Any]]) -> dict[int, int]:
    """How many scenes each orbit contributes, so it can be declared."""
    cuenta: dict[int, int] = {}
    for it in items:
        orb = it.get("properties", {}).get("sat:relative_orbit")
        if orb is not None:
            cuenta[int(orb)] = cuenta.get(int(orb), 0) + 1
    return dict(sorted(cuenta.items(), key=lambda kv: (-kv[1], kv[0])))


def by_orbit(retros: Iterable[Backscatter]) -> dict[int, list[Backscatter]]:
    """Group by relative orbit. Never average across groups."""
    out: dict[int, list[Backscatter]] = {}
    for r in retros:
        if r.error is None:
            out.setdefault(r.rel_orbit, []).append(r)
    for v in out.values():
        v.sort(key=lambda x: x.date)
    return dict(sorted(out.items(), key=lambda kv: -len(kv[1])))


def within_gap(retros: Sequence[Backscatter], start: str, fin: str) -> list[Backscatter]:
    """Radar passes with a valid measurement inside a blind stretch."""
    return [r for r in retros if r.error is None and start <= r.date <= fin]
