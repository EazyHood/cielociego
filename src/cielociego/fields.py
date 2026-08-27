"""Load an area of interest from GeoJSON."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry


@dataclass(frozen=True)
class Field:
    """An area of interest: geometry in EPSG:4326 plus its metadata."""

    name: str
    geometry: BaseGeometry
    area_ha: float | None = None
    tile: str | None = None

    @property
    def bbox(self) -> tuple[float, float, float, float]:
        return self.geometry.bounds

    def __str__(self) -> str:  # pragma: no cover - cosmetico
        return f"{self.name} ({self.area_ha or '?'} ha)"


def load_field(path: str | Path) -> Field:
    """Read a GeoJSON (Feature, single-feature collection, or bare geometry).

    Fails loudly on more than one feature: mixing two fields into a single
    measurement is precisely the error this project exists to avoid.
    """
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))

    if doc.get("type") == "FeatureCollection":
        feats = doc["features"]
        if len(feats) != 1:
            raise ValueError(
                f"{path.name}: se esperaba 1 feature y hay {len(feats)}. "
                "Separa los fields en ficheros distintos."
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
        raise ValueError(f"{path.name}: geometry vacia")

    return Field(
        name=props.get("name") or path.stem,
        geometry=geom,
        area_ha=props.get("area_ha"),
        tile=props.get("tile"),
    )
