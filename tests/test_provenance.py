"""Tests for the provenance record.

Un numero sin provenance no es reproducible. Y la provenance no puede
tumbar una medida: si git no esta, se sigue midiendo igual.
"""
from __future__ import annotations

from cielociego import __version__
from cielociego.provenance import fingerprint, record


def test_the_record_carries_the_essentials():
    f = record()
    assert f["version"] == __version__
    assert f["medido_en"].endswith("+00:00"), "en UTC, para poder comparar"
    assert f["python"] and f["sistema"]


def test_the_measurement_parameters_are_recorded():
    f = record(umbral=0.10, start="2019-01-01", orbit=142)
    assert f["parametros"] == {"umbral": 0.10, "start": "2019-01-01", "orbit": 142}


def test_the_parameters_vacios_not_ensucian_the_record():
    assert record(umbral=0.10, orbit=None)["parametros"] == {"umbral": 0.10}


def test_the_fingerprint_detects_that_the_polygon_change(tmp_path):
    a = tmp_path / "field.geojson"
    a.write_text('{"type":"Polygon"}', encoding="utf-8")
    primera = fingerprint(a)
    a.write_text('{"type":"Polygon","x":1}', encoding="utf-8")
    assert primera != fingerprint(a), "si el field cambia, la fingerprint tiene que cambiar"


def test_the_fingerprint_is_stable_when_nothing_changes(tmp_path):
    a = tmp_path / "p.geojson"
    a.write_text("igual", encoding="utf-8")
    assert fingerprint(a) == fingerprint(a)


def test_a_fichero_that_not_exists_not_raises():
    assert fingerprint("/no/existe.geojson") is None


def test_without_git_the_record_sigue_saliendo(monkeypatch):
    """Provenance is an extra: it must never bring down a measurement."""
    import cielociego.provenance as pr

    def explota(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(pr.subprocess, "run", explota)
    f = pr.record(umbral=0.1)
    assert f["commit"] is None and f["version"] == __version__
