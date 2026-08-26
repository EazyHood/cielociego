"""Pruebas de la carga de predios.

El punto clave: un fichero con dos poligonos debe FALLAR, no promediarlos.
Mezclar dos predios en una sola medida es el error que este proyecto existe
para evitar, y seria invisible en el resultado.
"""
from __future__ import annotations

import json

import pytest
from shapely.geometry import box

from cielociego.predios import Predio, carga_predio

CUADRADO = [[[-74.0, 10.0], [-73.9, 10.0], [-73.9, 10.1], [-74.0, 10.1], [-74.0, 10.0]]]


def escribe(tmp_path, doc, nombre="predio.geojson"):
    ruta = tmp_path / nombre
    ruta.write_text(json.dumps(doc), encoding="utf-8")
    return ruta


def coleccion(props=None, coords=None):
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": props if props is not None else {"nombre": "Finca", "area_ha": 73.5},
            "geometry": {"type": "Polygon", "coordinates": coords or CUADRADO},
        }],
    }


def test_lee_una_coleccion_de_un_feature(tmp_path):
    p = carga_predio(escribe(tmp_path, coleccion()))
    assert p.nombre == "Finca" and p.area_ha == 73.5
    assert p.geometria.is_valid


def test_lee_un_feature_suelto(tmp_path):
    p = carga_predio(escribe(tmp_path, coleccion()["features"][0]))
    assert p.nombre == "Finca"


def test_lee_una_geometria_pelada(tmp_path):
    doc = {"type": "Polygon", "coordinates": CUADRADO}
    p = carga_predio(escribe(tmp_path, doc, "mi_finca.geojson"))
    assert p.nombre == "mi_finca", "sin propiedades, el nombre sale del fichero"


def test_dos_poligonos_FALLAN_en_vez_de_mezclarse(tmp_path):
    """El error que este proyecto existe para evitar."""
    doc = coleccion()
    doc["features"].append(doc["features"][0])
    with pytest.raises(ValueError, match="1 feature"):
        carga_predio(escribe(tmp_path, doc))


def test_una_coleccion_vacia_tambien_falla(tmp_path):
    with pytest.raises(ValueError):
        carga_predio(escribe(tmp_path, {"type": "FeatureCollection", "features": []}))


def test_un_poligono_que_se_cruza_a_si_mismo_se_repara(tmp_path):
    """Un lazo (bowtie) es invalido; se arregla en vez de reventar despues."""
    lazo = [[[0, 0], [1, 1], [1, 0], [0, 1], [0, 0]]]
    p = carga_predio(escribe(tmp_path, coleccion(coords=lazo)))
    assert p.geometria.is_valid


def test_una_geometria_vacia_falla(tmp_path):
    doc = coleccion()
    doc["features"][0]["geometry"] = {"type": "Polygon", "coordinates": []}
    with pytest.raises(ValueError, match="vacia"):
        carga_predio(escribe(tmp_path, doc))


def test_el_bbox_envuelve_la_geometria(tmp_path):
    p = carga_predio(escribe(tmp_path, coleccion()))
    assert p.bbox == pytest.approx((-74.0, 10.0, -73.9, 10.1))


def test_propiedades_opcionales_no_son_obligatorias(tmp_path):
    p = carga_predio(escribe(tmp_path, coleccion(props={})))
    assert p.area_ha is None and p.tesela is None


def test_los_predios_reales_del_repo_cargan():
    """Control de integracion: los dos GeoJSON incluidos deben abrirse."""
    from pathlib import Path

    datos = Path(__file__).resolve().parents[1] / "datos"
    for ruta in sorted(datos.glob("predio_*.geojson")):
        p = carga_predio(ruta)
        assert p.geometria.is_valid and p.area_ha and p.area_ha > 0


def test_el_predio_es_inmutable():
    """Una medida no puede cambiar el area de interes a mitad de barrido."""
    p = Predio("x", box(0, 0, 1, 1), 10.0)
    with pytest.raises(AttributeError):
        p.nombre = "otro"  # type: ignore[misc]
