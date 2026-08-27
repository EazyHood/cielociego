"""Catalogue tests. No network: the HTTP session is faked.

Lo que se prueba es la LOGICA DE PAGINACION, que es donde estuvo el fallo,
no que el servidor de Element84 siga en pie.
"""
from __future__ import annotations

import pytest

from cielociego.catalog import IncompleteSweep, by_year, search


class RespuestaFalsa:
    def __init__(self, doc):
        self._doc = doc

    def raise_for_status(self):
        pass

    def json(self):
        return self._doc


class SesionFalsa:
    """Returns the prepared pages in order, recording what was asked for."""

    def __init__(self, pages):
        self.pages = list(pages)
        self.requests_made = []

    def post(self, url, json=None, timeout=None):
        self.requests_made.append(json)
        return RespuestaFalsa(self.pages.pop(0))


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


def test_pages_to_the_end_and_the_count_matches():
    ses = SesionFalsa([pagina(["a", "b"], 3, "sig1"), pagina(["c"], 3)])
    b = search("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", session=ses)
    assert len(b) == 3 and b.declared == 3 and b.pages == 2


def test_sends_the_next_link_body_verbatim():
    """The real bug: sending {"token": ...} instead of the body with {"next": ...}."""
    ses = SesionFalsa([pagina(["a"], 2, "TOKEN_REAL"), pagina(["b"], 2)])
    search("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", session=ses)
    assert ses.requests_made[1] == {"next": "TOKEN_REAL"}, "debe reenviar el body del enlace"


def test_raises_rather_than_returning_short():
    """The heart of the module: a short sweep must not pass in silence."""
    ses = SesionFalsa([pagina(["a"], 819)])  # dice 819, trae 1, sin enlace next
    with pytest.raises(IncompleteSweep) as e:
        search("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", session=ses)
    assert "819" in str(e.value) and "1" in str(e.value)


def test_without_a_count_it_verifies_nothing_and_invents_nothing():
    doc = {"features": [{"id": "a", "properties": {"datetime": "2020-01-01T00:00:00Z"}}], "links": []}
    b = search("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", session=SesionFalsa([doc]))
    assert b.declared is None and len(b) == 1


def test_the_page_cap_warns_instead_of_looping():
    ses = SesionFalsa([pagina(["a"], 99, "x") for _ in range(5)])
    b = search("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", session=ses, tope_paginas=2)
    assert b.warnings and "truncado" in b.warnings[0]


def test_by_year_groups_and_sorts():
    items = [
        {"properties": {"datetime": "2022-05-01T00:00:00Z"}},
        {"properties": {"datetime": "2020-01-01T00:00:00Z"}},
        {"properties": {"datetime": "2022-06-01T00:00:00Z"}},
    ]
    g = by_year(items)
    assert list(g) == ["2020", "2022"] and len(g["2022"]) == 2


def test_a_network_failure_is_not_mistaken_for_absent_data():
    """Telling "no scenes" apart from "I could not ask" is the whole point."""
    import requests

    from cielociego.catalog import NetworkDown

    class SesionRota:
        def post(self, *a, **k):
            raise requests.ConnectionError("Read timed out")

    with pytest.raises(NetworkDown) as e:
        search("col", (0, 0, 1, 1), "2020-01-01", "2020-12-31", session=SesionRota())
    assert "could not ask" in str(e.value)
    assert "ConnectionError" in str(e.value)
