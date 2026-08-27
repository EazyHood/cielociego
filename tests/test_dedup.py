"""Tests for deduplication by processing baseline.

Los casos vienen de datos REALES medidos sobre la tile 18PXS el 2026-08-25,
no de ejemplos inventados: si el archivo publico cambia de forma, estas
pruebas son las que lo destapan.
"""
from __future__ import annotations

from cielociego.dedup import Acquisition, deduplicate, identity


def item(uri: str, *, cc: float = 0.0, date: str = "2020-01-04T15:30:09.520000Z"):
    return {"properties": {"s2:product_uri": uri, "eo:cloud_cover": cc, "datetime": date}}


# --- the real pair that exposed the problem -------------------------------
NUEVA = "S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS"
VIEJA = "S2B_MSIL2A_20200104T152639_N0213_R025_T18PXS"


def test_identity_ignores_the_processing_baseline():
    a, la = identity(item(NUEVA))
    b, lb = identity(item(VIEJA))
    assert a == b == Acquisition("S2B", "20200104T152639", "025", "18PXS")
    assert (la, lb) == (500, 213)


def test_keeps_the_highest_baseline_whatever_the_order():
    for orden in ([NUEVA, VIEJA], [VIEJA, NUEVA]):
        vivos, muertos = deduplicate([item(u) for u in orden])
        assert len(vivos) == 1 and len(muertos) == 1
        assert vivos[0]["properties"]["s2:product_uri"] == NUEVA


def test_the_millisecond_is_useless_as_a_key():
    """Control: grouping by exact datetime does not merge the two copies.

    Es la razon de existir de este modulo. Si esta prueba empieza a fallar
    porque los datetime coinciden, el archivo cambio y hay que revisar
    si la clave por product_uri sigue siendo necesaria.
    """
    a = item(NUEVA, date="2020-01-04T15:30:09.520000Z")
    b = item(VIEJA, date="2020-01-04T15:30:09.519000Z")
    dates = {x["properties"]["datetime"] for x in (a, b)}
    assert len(dates) == 2, "los datetime ya no difieren; revisar el modulo"
    vivos, _ = deduplicate([a, b])
    assert len(vivos) == 1, "product_uri si las junta"


def test_different_acquisitions_are_not_merged():
    """Mutation: changing one identity field must split the group."""
    base = "S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS"
    variantes = [
        base,
        base.replace("S2B", "S2A"),           # otra platform
        base.replace("T152639", "T152640"),   # otro sensado
        base.replace("R025", "R026"),         # otra orbit
        base.replace("T18PXS", "T18PWS"),     # otra tile
    ]
    vivos, muertos = deduplicate([item(u) for u in variantes])
    assert len(vivos) == 5 and not muertos


def test_an_item_without_a_uri_is_kept_not_lost():
    vivos, muertos = deduplicate([{"properties": {"datetime": "2020-01-01T00:00:00Z"}}])
    assert len(vivos) == 1 and not muertos


def test_an_unreadable_uri_does_not_raise():
    toma, linea = identity(item("basura_que_no_es_un_producto"))
    assert toma is None and linea == -1


def test_output_is_sorted_by_date():
    a = item("S2A_MSIL2A_20200109T152631_N0500_R025_T18PXS", date="2020-01-09T15:30:08Z")
    b = item("S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS", date="2020-01-04T15:30:09Z")
    vivos, _ = deduplicate([a, b])
    assert [x["properties"]["datetime"] for x in vivos] == [
        "2020-01-04T15:30:09Z",
        "2020-01-09T15:30:08Z",
    ]


# --- baseline pairs: measuring how much a result depends on the processor -
def test_finds_acquisitions_served_under_two_baselines():
    from cielociego.dedup import baseline_pairs

    pares = baseline_pairs([item(NUEVA), item(VIEJA),
                             item("S2A_MSIL2A_20200109T152631_N0500_R025_T18PXS")])
    assert len(pares) == 1, "solo una toma tiene dos versiones"
    vieja, nueva = pares[0]
    assert vieja["properties"]["s2:product_uri"] == VIEJA
    assert nueva["properties"]["s2:product_uri"] == NUEVA


def test_always_returns_older_first_newer_second():
    """El orden importa: quien compare las dos necesita saber cual es cual."""
    from cielociego.dedup import baseline_pairs

    for orden in ([NUEVA, VIEJA], [VIEJA, NUEVA]):
        vieja, nueva = baseline_pairs([item(u) for u in orden])[0]
        assert "N0213" in vieja["properties"]["s2:product_uri"]
        assert "N0500" in nueva["properties"]["s2:product_uri"]


def test_an_acquisition_with_one_baseline_yields_no_pair():
    from cielociego.dedup import baseline_pairs

    assert baseline_pairs([item(NUEVA)]) == []


def test_with_three_baselines_it_compares_the_extremes():
    from cielociego.dedup import baseline_pairs

    tres = [f"S2A_MSIL2A_20210930T152631_N0{v}_R025_T18PXS" for v in ("213", "301", "500")]
    vieja, nueva = baseline_pairs([item(u) for u in tres])[0]
    assert "N0213" in vieja["properties"]["s2:product_uri"]
    assert "N0500" in nueva["properties"]["s2:product_uri"]
