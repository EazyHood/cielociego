"""Pruebas de la deduplicacion por linea de procesado.

Los casos vienen de datos REALES medidos sobre la tesela 18PXS el 2026-08-25,
no de ejemplos inventados: si el archivo publico cambia de forma, estas
pruebas son las que lo destapan.
"""
from __future__ import annotations

from cielociego.dedup import Toma, deduplica, identidad


def item(uri: str, *, cc: float = 0.0, fecha: str = "2020-01-04T15:30:09.520000Z"):
    return {"properties": {"s2:product_uri": uri, "eo:cloud_cover": cc, "datetime": fecha}}


# --- el par real que destapo el problema -----------------------------------
NUEVA = "S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS"
VIEJA = "S2B_MSIL2A_20200104T152639_N0213_R025_T18PXS"


def test_identidad_ignora_la_linea_de_procesado():
    a, la = identidad(item(NUEVA))
    b, lb = identidad(item(VIEJA))
    assert a == b == Toma("S2B", "20200104T152639", "025", "18PXS")
    assert (la, lb) == (500, 213)


def test_conserva_la_linea_mas_alta_venga_en_el_orden_que_venga():
    for orden in ([NUEVA, VIEJA], [VIEJA, NUEVA]):
        vivos, muertos = deduplica([item(u) for u in orden])
        assert len(vivos) == 1 and len(muertos) == 1
        assert vivos[0]["properties"]["s2:product_uri"] == NUEVA


def test_el_milisegundo_no_sirve_como_clave():
    """Control: agrupar por datetime exacto NO junta las dos copias.

    Es la razon de existir de este modulo. Si esta prueba empieza a fallar
    porque los datetime coinciden, el archivo cambio y hay que revisar
    si la clave por product_uri sigue siendo necesaria.
    """
    a = item(NUEVA, fecha="2020-01-04T15:30:09.520000Z")
    b = item(VIEJA, fecha="2020-01-04T15:30:09.519000Z")
    fechas = {x["properties"]["datetime"] for x in (a, b)}
    assert len(fechas) == 2, "los datetime ya no difieren; revisar el modulo"
    vivos, _ = deduplica([a, b])
    assert len(vivos) == 1, "product_uri si las junta"


def test_tomas_distintas_no_se_fusionan():
    """Mutacion: cambiar UN campo de la identidad debe partir el grupo."""
    base = "S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS"
    variantes = [
        base,
        base.replace("S2B", "S2A"),           # otra plataforma
        base.replace("T152639", "T152640"),   # otro sensado
        base.replace("R025", "R026"),         # otra orbita
        base.replace("T18PXS", "T18PWS"),     # otra tesela
    ]
    vivos, muertos = deduplica([item(u) for u in variantes])
    assert len(vivos) == 5 and not muertos


def test_item_sin_uri_se_conserva_no_se_pierde():
    vivos, muertos = deduplica([{"properties": {"datetime": "2020-01-01T00:00:00Z"}}])
    assert len(vivos) == 1 and not muertos


def test_uri_ilegible_no_revienta():
    toma, linea = identidad(item("basura_que_no_es_un_producto"))
    assert toma is None and linea == -1


def test_salida_ordenada_por_fecha():
    a = item("S2A_MSIL2A_20200109T152631_N0500_R025_T18PXS", fecha="2020-01-09T15:30:08Z")
    b = item("S2B_MSIL2A_20200104T152639_N0500_R025_T18PXS", fecha="2020-01-04T15:30:09Z")
    vivos, _ = deduplica([a, b])
    assert [x["properties"]["datetime"] for x in vivos] == [
        "2020-01-04T15:30:09Z",
        "2020-01-09T15:30:08Z",
    ]


# --- pares de lineas: para poder medir cuanto depende del procesador -------
def test_encuentra_las_tomas_servidas_bajo_dos_lineas():
    from cielociego.dedup import pares_de_lineas

    pares = pares_de_lineas([item(NUEVA), item(VIEJA),
                             item("S2A_MSIL2A_20200109T152631_N0500_R025_T18PXS")])
    assert len(pares) == 1, "solo una toma tiene dos versiones"
    vieja, nueva = pares[0]
    assert vieja["properties"]["s2:product_uri"] == VIEJA
    assert nueva["properties"]["s2:product_uri"] == NUEVA


def test_devuelve_siempre_vieja_primero_nueva_despues():
    """El orden importa: quien compare las dos necesita saber cual es cual."""
    from cielociego.dedup import pares_de_lineas

    for orden in ([NUEVA, VIEJA], [VIEJA, NUEVA]):
        vieja, nueva = pares_de_lineas([item(u) for u in orden])[0]
        assert "N0213" in vieja["properties"]["s2:product_uri"]
        assert "N0500" in nueva["properties"]["s2:product_uri"]


def test_una_toma_con_una_sola_linea_no_da_par():
    from cielociego.dedup import pares_de_lineas

    assert pares_de_lineas([item(NUEVA)]) == []


def test_con_tres_lineas_compara_los_extremos():
    from cielociego.dedup import pares_de_lineas

    tres = [f"S2A_MSIL2A_20210930T152631_N0{v}_R025_T18PXS" for v in ("213", "301", "500")]
    vieja, nueva = pares_de_lineas([item(u) for u in tres])[0]
    assert "N0213" in vieja["properties"]["s2:product_uri"]
    assert "N0500" in nueva["properties"]["s2:product_uri"]
