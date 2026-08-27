"""Public STAC catalogue (Element84 / earth-search on AWS).

No account, no key, no quota. COGs live in the public `sentinel-cogs` bucket
and are read by window, never a whole scene.

`search` verifies its own result against the count the server declares and
raises rather than returning short. See DECISIONS.md #2.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import requests

from .net import session as _sesion_con_reintentos

STAC = "https://earth-search.aws.element84.com/v1/search"
S2_L2A = "sentinel-2-l2a"
S1_GRD = "sentinel-1-grd"


class IncompleteSweep(RuntimeError):
    """The server declared N results and a different number arrived. Stop."""


class NetworkDown(RuntimeError):
    """The network failed and the retries ran out.

    Existe para poder distinguir "no hay dato" de "no pude preguntar". Un
    `ConnectionError` crudo saliendo del catalog tumbaba la medicion entera
    y no decia cual de las dos cosas habia pasado.
    """


@dataclass
class Sweep:
    items: list[dict[str, Any]]
    declared: int | None
    collection: str
    pages: int = 0
    warnings: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)


def search(
    collection: str,
    bbox: tuple[float, float, float, float],
    start: str,
    end: str,
    *,
    limite_pagina: int = 100,
    session: requests.Session | None = None,
    tope_paginas: int = 500,
) -> Sweep:
    """Every item of `collection` touching `bbox` between the two dates.

    Fechas en ISO (`2020-01-01`). Lanza IncompleteSweep si el conteo no
    cuadra con lo declarado por el servidor.
    """
    ses = session or _sesion_con_reintentos()
    payload: dict[str, Any] = {
        "collections": [collection],
        "bbox": list(bbox),
        "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z",
        "limit": limite_pagina,
    }
    items: list[dict[str, Any]] = []
    declared: int | None = None
    pages = 0
    warnings: list[str] = []

    while True:
        try:
            r = ses.post(STAC, json=payload, timeout=120)
            r.raise_for_status()
            doc = r.json()
        except requests.RequestException as exc:
            raise NetworkDown(
                f"{collection}: the network failed after exhausting retries on page "
                f"{pages + 1} ({type(exc).__name__}). It is not that there is no data: "
                "it is that I could not ask."
            ) from exc
        pages += 1
        if declared is None:
            declared = (doc.get("context") or {}).get("matched")
        items.extend(doc.get("features", []))

        sig = next((e for e in doc.get("links", []) if e.get("rel") == "next"), None)
        if not sig or not sig.get("body"):
            break
        if pages >= tope_paginas:
            warnings.append(f"tope de {tope_paginas} pages alcanzado; sweep truncado")
            break
        payload = sig["body"]

    if declared is not None and len(items) != declared and not warnings:
        raise IncompleteSweep(
            f"{collection}: el servidor declaro {declared} items y se bajaron "
            f"{len(items)} en {pages} pages. Revisar la clave de paginacion."
        )

    return Sweep(items, declared, collection, pages, warnings)


def by_year(items: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        ano = it.get("properties", it)["datetime"][:4]
        out.setdefault(ano, []).append(it)
    return dict(sorted(out.items()))
