"""Carga de predios (AOI) desde GeoJSON."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class Predio:
    """Un area de interes: geometria en EPSG:4326 mas su ficha."""

    nombre: str
    geometria: BaseGeometry
    area_ha: float | None = None
    tesela: str | None = None

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.geometria.bounds

    def __str__(self) -> str:  # pragma: no cover - cosmetico
        return f"{self.nombre} ({self.area_ha or '?'} ha)"


def carga_predio(ruta: str | Path) -> Predio:
    """Lee un GeoJSON (Feature, FeatureCollection de 1, o Geometry) como Predio.

    Falla ruidosamente si el fichero trae mas de un feature: mezclar dos predios
    en una sola medida es justo el error que este proyecto existe para evitar.
    """
    ruta = Path(ruta)
    doc = json.loads(ruta.read_text(encoding="utf-8"))

    if doc.get("type") == "FeatureCollection":
        feats = doc["features"]
        if len(feats) != 1:
            raise ValueError(
                f"{ruta.name}: se esperaba 1 feature y hay {len(feats)}. "
                "Separa los predios en ficheros distintos."
            )
        feat = feats[0]
    elif doc.get("type") == "Feature":
        feat = doc
    else:
        feat = {"geometry": doc, "properties": {}}

    props = feat.get("properties") or {}
    geom = shape(feat["geometry"])
    if not geom.is_valid:
        geom = geom.buffer(0)
    if geom.is_empty:
        raise ValueError(f"{ruta.name}: geometria vacia")

    return Predio(
        nombre=props.get("nombre") or ruta.stem,
        geometria=geom,
        area_ha=props.get("area_ha"),
        tesela=props.get("tesela"),
    )
