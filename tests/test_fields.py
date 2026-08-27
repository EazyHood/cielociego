"""Tests for loading fields.

El punto clave: un fichero con dos poligonos debe FALLAR, no promediarlos.
Mezclar dos fields en una sola medida es el error que este proyecto existe
para evitar, y seria invisible en el resultado.
"""
from __future__ import annotations

import json

import pytest
from shapely.geometry import box

from cielociego.fields import Field, load_field

CUADRADO = [[[-74.0, 10.0], [-73.9, 10.0], [-73.9, 10.1], [-74.0, 10.1], [-74.0, 10.0]]]


def escribe(tmp_path, doc, name="field.geojson"):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def collection(props=None, coords=None):
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": props if props is not None else {"name": "Finca", "area_ha": 73.5},
            "geometry": {"type": "Polygon", "coordinates": coords or CUADRADO},
        }],
    }


def test_loads_a_single_feature_collection(tmp_path):
    p = load_field(escribe(tmp_path, collection()))
    assert p.name == "Finca" and p.area_ha == 73.5
    assert p.geometry.is_valid


def test_loads_a_bare_feature(tmp_path):
    p = load_field(escribe(tmp_path, collection()["features"][0]))
    assert p.name == "Finca"


def test_loads_a_bare_geometry(tmp_path):
    doc = {"type": "Polygon", "coordinates": CUADRADO}
    p = load_field(escribe(tmp_path, doc, "mi_finca.geojson"))
    assert p.name == "mi_finca", "sin propiedades, el name sale del fichero"


def test_dos_poligonos_FALLAN_en_vez_de_mezclarse(tmp_path):
    """The error this project exists to avoid."""
    doc = collection()
    doc["features"].append(doc["features"][0])
    with pytest.raises(ValueError, match="1 feature"):
        load_field(escribe(tmp_path, doc))


def test_an_empty_collection_also_fails(tmp_path):
    with pytest.raises(ValueError):
        load_field(escribe(tmp_path, {"type": "FeatureCollection", "features": []}))


def test_a_self_intersecting_polygon_is_repaired(tmp_path):
    """A bowtie is invalid; it is repaired rather than blowing up later."""
    lazo = [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]
    p = load_field(escribe(tmp_path, collection(coords=lazo)))
    assert p.geometry.is_valid


def test_an_empty_geometry_fails(tmp_path):
    doc = collection()
    doc["features"][0]["geometry"] = {"type": "Polygon", "coordinates": []}
    with pytest.raises(ValueError, match="vacia"):
        load_field(escribe(tmp_path, doc))


def test_the_bbox_encloses_the_geometry(tmp_path):
    p = load_field(escribe(tmp_path, collection()))
    assert p.bbox == pytest.approx((-74.0, 10.0, -73.9, 10.1))


def test_optional_properties_are_optional(tmp_path):
    p = load_field(escribe(tmp_path, collection(props={})))
    assert p.area_ha is None and p.tile is None


def test_the_geojson_shipped_with_the_repo_loads():
    """Integration control: the bundled GeoJSON must actually open.

    El `assert` del final es para que la prueba no pase EN VACIO si algun dia
    se vacia `data/`: una prueba que no comprueba nada es peor que ninguna.
    """
    from pathlib import Path

    datos = Path(__file__).resolve().parents[1] / "data"
    encontrados = sorted(datos.glob("*.geojson"))
    for path in encontrados:
        p = load_field(path)
        assert p.geometry.is_valid and p.area_ha and p.area_ha > 0
    assert encontrados, "data/ no trae ningun GeoJSON: la prueba estaria pasando en vacio"


def test_the_demo_area_states_it_is_not_a_field():
    """If anyone mistakes it for a real holding, the repo has done something wrong."""
    from pathlib import Path

    demo = Path(__file__).resolve().parents[1] / "data" / "area_demo.geojson"
    doc = json.loads(demo.read_text(encoding="utf-8"))
    note = doc["features"][0]["properties"].get("note", "").lower()
    assert "does not" in note and "correspond to any real field" in note


def test_a_field_is_immutable():
    """A measurement cannot change its area of interest mid-sweep."""
    p = Field("x", box(0, 0, 1, 1), 10.0)
    with pytest.raises(AttributeError):
        p.name = "otro"  # type: ignore[misc]
