"""Pruebas del catalogo. Sin red: se simula la sesion HTTP.

Lo que se prueba es la LOGICA DE PAGINACION, que es donde estuvo el fallo,
no que el servidor de Element84 siga en pie.
"""
from __future__ import annotations

import pytest

from cielociego.catalogo import BarridoIncompleto, busca, por_ano


class RespuestaFalsa:
    def __init__(self, doc):
        self._doc = doc

    def raise_for_status(self):
        pass

    def json(self):
        return self._doc


class SesionFalsa:
    """Devuelve las paginas preparadas, en orden, y guarda lo que se le pidio."""

    def __init__(self, paginas):
        self.paginas = list(paginas)
        self.peticiones = []

    def post(self, url, json=None, timeout=None):
        self.peticiones.append(json)
        return RespuestaFalsa(self.paginas.pop(0))


def pagina(ids, matched, siguiente=None):
    doc = {
        "context": {"matched": matched},
        "features": [
            {"id": i, "properties": {"datetime": f"20{20 + n // 12}-01-01T00:00:00Z"}}
            for n, i in enumerate(ids)
        ],
        "links": [],
    }
    if siguiente is not None:
        doc["links"].append(
            {"rel": "next", "method": "POST", "merge": False, "body": {"next": siguiente}}
        )
    return doc


def test_pagina_hasta_el_final_y_cuadra():
    ses = SesionFalsa([pagina(["a", "b"], 3, "sig1"), pagina(["c"], 3)])
    b = busca("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", sesion=ses)
    assert len(b) == 3 and b.declarados == 3 and b.paginas == 2


def test_usa_el_body_del_enlace_next_tal_cual():
    """El bug real: mandar {"token": ...} en vez del body con {"next": ...}."""
    ses = SesionFalsa([pagina(["a"], 2, "TOKEN_REAL"), pagina(["b"], 2)])
    busca("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", sesion=ses)
    assert ses.peticiones[1] == {"next": "TOKEN_REAL"}, "debe reenviar el body del enlace"


def test_si_faltan_items_revienta_en_vez_de_devolver_de_menos():
    """Este es el corazon del modulo: el barrido corto NO puede pasar callando."""
    ses = SesionFalsa([pagina(["a"], 819)])  # dice 819, trae 1, sin enlace next
    with pytest.raises(BarridoIncompleto) as e:
        busca("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", sesion=ses)
    assert "819" in str(e.value) and "1" in str(e.value)


def test_sin_context_no_puede_verificar_pero_no_inventa():
    doc = {"features": [{"id": "a", "properties": {"datetime": "2020-01-01T00:00:00Z"}}], "links": []}
    b = busca("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", sesion=SesionFalsa([doc]))
    assert b.declarados is None and len(b) == 1


def test_tope_de_paginas_avisa_en_vez_de_dar_vueltas():
    ses = SesionFalsa([pagina(["a"], 99, "x") for _ in range(5)])
    b = busca("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", sesion=ses, tope_paginas=2)
    assert b.avisos and "truncado" in b.avisos[0]


def test_por_ano_agrupa_y_ordena():
    items = [
        {"properties": {"datetime": "2022-05-01T00:00:00Z"}},
        {"properties": {"datetime": "2020-01-01T00:00:00Z"}},
        {"properties": {"datetime": "2022-06-01T00:00:00Z"}},
    ]
    g = por_ano(items)
    assert list(g) == ["2020", "2022"] and len(g["2022"]) == 2
