"""Consulta al catalogo STAC publico (Element84 / earth-search sobre AWS).

Sin cuenta, sin clave, sin cuota. Los COG viven en el bucket publico
`sentinel-cogs` y se leen por ventana, sin bajar la escena entera.

TRAMPA DE PAGINACION (medida el 2026-08-25)
-------------------------------------------
El enlace `next` trae la continuacion en `body["next"]`, NO en
`body["token"]`, y viene con `merge:false` (el body ya esta completo).
La primera version de este codigo uso "token": devolvia 100 items y paraba
sin error. Habrian faltado 719 de 819 escenas EN SILENCIO.

Por eso `busca()` compara siempre lo bajado contra el `context.matched` que
declara el servidor y revienta si no cuadran. Un barrido que se corta solo
es peor que uno que falla: el que falla se ve.
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

import requests

from .red import sesion as _sesion_con_reintentos

STAC = "https://earth-search.aws.element84.com/v1/search"
S2_L2A = "sentinel-2-l2a"
S1_GRD = "sentinel-1-grd"


class BarridoIncompleto(RuntimeError):
    """El servidor declaro N resultados y se bajaron otros. No seguir."""


@dataclass
class Barrido:
    items: list[dict[str, Any]]
    declarados: int | None
    coleccion: str
    paginas: int = 0
    avisos: list[str] = field(default_factory=list)

    def __len__(self) -> int:
        return len(self.items)


def busca(
    coleccion: str,
    bbox: tuple[float, float, float, float],
    desde: str,
    hasta: str,
    *,
    limite_pagina: int = 100,
    sesion: requests.Session | None = None,
    tope_paginas: int = 500,
) -> Barrido:
    """Todos los items de `coleccion` que tocan `bbox` entre `desde` y `hasta`.

    Fechas en ISO (`2020-01-01`). Lanza BarridoIncompleto si el conteo no
    cuadra con lo declarado por el servidor.
    """
    ses = sesion or _sesion_con_reintentos()
    payload: dict[str, Any] = {
        "collections": [coleccion],
        "bbox": list(bbox),
        "datetime": f"{desde}T00:00:00Z/{hasta}T23:59:59Z",
        "limit": limite_pagina,
    }
    items: list[dict[str, Any]] = []
    declarados: int | None = None
    paginas = 0
    avisos: list[str] = []

    while True:
        r = ses.post(STAC, json=payload, timeout=120)
        r.raise_for_status()
        doc = r.json()
        paginas += 1
        if declarados is None:
            declarados = (doc.get("context") or {}).get("matched")
        items.extend(doc.get("features", []))

        sig = next((e for e in doc.get("links", []) if e.get("rel") == "next"), None)
        if not sig or not sig.get("body"):
            break
        if paginas >= tope_paginas:
            avisos.append(f"tope de {tope_paginas} paginas alcanzado; barrido truncado")
            break
        payload = sig["body"]

    if declarados is not None and len(items) != declarados and not avisos:
        raise BarridoIncompleto(
            f"{coleccion}: el servidor declaro {declarados} items y se bajaron "
            f"{len(items)} en {paginas} paginas. Revisar la clave de paginacion."
        )

    return Barrido(items, declarados, coleccion, paginas, avisos)


def por_ano(items: Iterable[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    salida: dict[str, list[dict[str, Any]]] = {}
    for it in items:
        ano = it.get("properties", it)["datetime"][:4]
        salida.setdefault(ano, []).append(it)
    return dict(sorted(salida.items()))
