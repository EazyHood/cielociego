"""Collapse the same Sentinel-2 acquisition served under several baselines.

Physical identity is (platform, sensing, orbit, tile); `N####` is only the
processing version. Grouping by timestamp does not work -- the copies differ by
one millisecond -- and the copies disagree about the clouds.

See DECISIONS.md #1.
"""
from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

# S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS(.SAFE)
_URI = re.compile(
    r"^(?P<platform>S2[A-D])_MSIL\w+?_(?P<sensado>\d{8}T\d{6})"
    r"_N(?P<linea>\d{4})_R(?P<orbit>\d{3})_T(?P<tile>\w{5})"
)


@dataclass(frozen=True)
class Acquisition:
    """Physical identity of an acquisition, minus the processing version."""

    platform: str
    sensado: str
    orbit: str
    tile: str


def identity(item: dict[str, Any]) -> tuple[Acquisition | None, int]:
    """Physical identity and processing baseline of a STAC item.

    Si el `s2:product_uri` no se puede leer devuelve (None, -1); quien llama
    decide que hacer. No se inventa una identity a partir del `id`, porque
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
        Acquisition(g["platform"], g["sensado"], g["orbit"], g["tile"]),
        int(g["linea"]),
    )


def deduplicate(
    items: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Keep one copy per physical acquisition: the highest baseline.

    Returns (kept, discarded). Items with no readable `s2:product_uri` are
    kept -- losing them silently would be worse than a duplicate -- and the
    report counts them separately.
    """
    best: dict[Acquisition, tuple[int, dict[str, Any]]] = {}
    sin_uri: list[dict[str, Any]] = []
    descartados: list[dict[str, Any]] = []

    for it in items:
        toma, linea = identity(it)
        if toma is None:
            sin_uri.append(it)
            continue
        previo = best.get(toma)
        if previo is None:
            best[toma] = (linea, it)
        elif linea > previo[0]:
            descartados.append(previo[1])
            best[toma] = (linea, it)
        else:
            descartados.append(it)

    conservados = [it for _, it in best.values()] + sin_uri
    conservados.sort(key=lambda x: x.get("properties", x).get("datetime", ""))
    return conservados, descartados


def baseline_pairs(
    items: Iterable[dict[str, Any]],
) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """Acquisitions the archive serves under two baselines: (older, newer).

    For measuring how much a result depends on the processor version instead
    of assuming it does not. Over 61 pairs on one field the SCL was
    bit-identical 80 % of the time; of the rest, 6.6 % crossed the usability
    threshold, always with the newer baseline flagging more cloud. Keeping the
    highest therefore gives the conservative answer.

    See DECISIONS.md #1.
    """
    grupos: dict[Acquisition, list[tuple[int, dict[str, Any]]]] = {}
    for it in items:
        toma, linea = identity(it)
        if toma is not None:
            grupos.setdefault(toma, []).append((linea, it))
    pares = []
    for versiones in grupos.values():
        if len(versiones) > 1:
            ordenadas = sorted(versiones, key=lambda x: x[0])
            pares.append((ordenadas[0][1], ordenadas[-1][1]))
    return pares
