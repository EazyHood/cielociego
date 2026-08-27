"""Deduplicacion de escenas Sentinel-2 por linea de procesado.

EL PROBLEMA, medido el 2026-08-25 sobre la tesela 18PXS
-------------------------------------------------------
El archivo publico sirve la MISMA toma reprocesada bajo varias lineas de
procesado (N0213 antigua, N0500 de la campana de reprocesado). Contarlas
todas infla las pasadas de ~73 a ~146 al ano, el doble de la realidad
fisica (Sentinel-2A + 2B dan revisita de 5 dias -> 365/5 = 73).

Y hay una trampa peor que el doble conteo: las dos copias declaran
NUBOSIDAD DISTINTA para los mismos pixeles.

    2020-01-04  N0500 -> 0,11 %      N0213 -> 3,15 %      (29x)
    2020-01-09  N0500 -> 0,05 %      N0213 -> 1,88 %      (37x)
    2020-01-19  N0500 -> 1,98 %      N0213 -> 1,60 %      (al reves)

POR QUE NO BASTA DEDUPLICAR POR FECHA
-------------------------------------
Los `datetime` de las dos copias difieren en UN MILISEGUNDO
(15:30:09.520 vs 15:30:09.519), asi que agrupar por instante exacto no
las junta. La clave estable es el identificador de producto:

    S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS
    ^^^        ^^^^^^^^^^^^^^^ ^^^^^ ^^^^ ^^^^^^
    plataforma  sensado         linea orbita tesela

La identidad fisica de la toma es (plataforma, sensado, orbita, tesela).
`N####` es SOLO la version del procesado: se agrupa por lo primero y se
elige la linea mas alta.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS(.SAFE)
_URI = re.compile(
    r"^(?P<plataforma>S2[A-D])_MSIL\w+?_(?P<sensado>\d{8}T\d{6})"
    r"_N(?P<linea>\d{4})_R(?P<orbita>\d{3})_T(?P<tesela>\w{5})"
)


@dataclass(frozen=True)
class Toma:
    """Identidad fisica de una toma, sin la version de procesado."""

    plataforma: str
    sensado: str
    orbita: str
    tesela: str


def identidad(item: dict[str, Any]) -> tuple[Toma | None, int]:
    """Devuelve (identidad fisica, numero de linea de procesado) de un item STAC.

    Si el `s2:product_uri` no se puede leer devuelve (None, -1); quien llama
    decide que hacer. No se inventa una identidad a partir del `id`, porque
    el `id` de earth-search ya lleva dentro un contador de version
    (`..._0_L2A`, `..._1_L2A`) que NO es la linea de procesado.
    """
    props = item.get("properties", item)
    uri = props.get("s2:product_uri") or ""
    m = _URI.match(uri)
    if not m:
        return None, -1
    g = m.groupdict()
    return (
        Toma(g["plataforma"], g["sensado"], g["orbita"], g["tesela"]),
        int(g["linea"]),
    )


def deduplica(
    items: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Deja una sola copia por toma fisica: la de linea de procesado mas alta.

    Devuelve (conservados, descartados). Los items sin `s2:product_uri`
    legible se CONSERVAN -- perderlos en silencio seria peor que un duplicado,
    y el informe los cuenta aparte.
    """
    mejor: dict[Toma, tuple[int, dict[str, Any]]] = {}
    sin_uri: list[dict[str, Any]] = []
    descartados: list[dict[str, Any]] = []

    for it in items:
        toma, linea = identidad(it)
        if toma is None:
            sin_uri.append(it)
            continue
        previo = mejor.get(toma)
        if previo is None:
            mejor[toma] = (linea, it)
        elif linea > previo[0]:
            descartados.append(previo[1])
            mejor[toma] = (linea, it)
        else:
            descartados.append(it)

    conservados = [it for _, it in mejor.values()] + sin_uri
    conservados.sort(key=lambda x: x.get("properties", x).get("datetime", ""))
    return conservados, descartados


def pares_de_lineas(
    items: Iterable[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Tomas que el archivo sirve bajo DOS lineas de procesado: (vieja, nueva).

    Sirve para medir cuanto depende un resultado de la version del procesador,
    en vez de suponer que no depende.

    MEDIDO SOBRE FUNDACION, 2019-2021 (n=61 tomas comparadas)
    ----------------------------------------------------------
    El SCL de las dos copias es **identico al bit en el 80 % de los casos**.
    En el 20 % restante difiere, con |diferencia| media del 6,7 % del predio y
    maxima del 100 %: el 29-nov-2021 la linea N0301 daba el predio despejado y
    la N0500 lo daba **71,8 % tapado**, sobre la misma toma.

    **El 6,6 % de las tomas cruza el umbral de utilidad**, y siempre en el
    mismo sentido: la linea nueva marca mas nube (36 utiles con la vieja, 32
    con la nueva). Por eso quedarse con la linea MAS ALTA -- lo que hace
    `deduplica` -- da el resultado **conservador**: declara mas dias ciegos de
    los que declararia el procesador antiguo, no menos.

    No es un fallo del archivo ni de este codigo: la mascara de nubes es la
    salida de un modelo, y los modelos se actualizan. Lo que seria un fallo es
    no decirlo.
    """
    grupos: dict[Toma, list[tuple[int, dict[str, Any]]]] = {}
    for it in items:
        toma, linea = identidad(it)
        if toma is not None:
            grupos.setdefault(toma, []).append((linea, it))
    pares = []
    for versiones in grupos.values():
        if len(versiones) > 1:
            ordenadas = sorted(versiones, key=lambda x: x[0])
            pares.append((ordenadas[0][1], ordenadas[-1][1]))
    return pares
