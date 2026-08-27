"""Pruebas de la ficha de procedencia.

Un numero sin procedencia no es reproducible. Y la procedencia no puede
tumbar una medida: si git no esta, se sigue midiendo igual.
"""
from __future__ import annotations

from cielociego import __version__
from cielociego.procedencia import ficha, huella


def test_la_ficha_lleva_lo_imprescindible():
    f = ficha()
    assert f["version"] == __version__
    assert f["medido_en"].endswith("+00:00"), "en UTC, para poder comparar"
    assert f["python"] and f["sistema"]


def test_los_parametros_de_la_medida_quedan_dentro():
    f = ficha(umbral=0.10, desde="2019-01-01", orbita=142)
    assert f["parametros"] == {"umbral": 0.10, "desde": "2019-01-01", "orbita": 142}


def test_los_parametros_vacios_no_ensucian_la_ficha():
    assert ficha(umbral=0.10, orbita=None)["parametros"] == {"umbral": 0.10}


def test_la_huella_detecta_que_el_poligono_cambio(tmp_path):
    a = tmp_path / "predio.geojson"
    a.write_text('{"type":"Polygon"}', encoding="utf-8")
    primera = huella(a)
    a.write_text('{"type":"Polygon","x":1}', encoding="utf-8")
    assert primera != huella(a), "si el predio cambia, la huella tiene que cambiar"


def test_la_huella_es_estable_si_nada_cambia(tmp_path):
    a = tmp_path / "p.geojson"
    a.write_text("igual", encoding="utf-8")
    assert huella(a) == huella(a)


def test_un_fichero_que_no_existe_no_revienta():
    assert huella("/no/existe.geojson") is None


def test_sin_git_la_ficha_sigue_saliendo(monkeypatch):
    """La procedencia es un extra: nunca puede tumbar una medicion."""
    import cielociego.procedencia as pr

    def explota(*a, **k):
        raise FileNotFoundError("git")

    monkeypatch.setattr(pr.subprocess, "run", explota)
    f = pr.ficha(umbral=0.1)
    assert f["commit"] is None and f["version"] == __version__
