"""Build a parcel cohort from Fields of The World, without downloading a country.

Fields of The World (Kerner Lab, Source Cooperative) publishes instance masks:
one raster per 256 x 256 chip where every field carries its own integer id. Those
masks are the cheapest public source of *real* parcel boundaries spread over
climates -- Rwanda's tenths of a hectare next to Brazil's hundreds -- and the
whole cohort here weighs a few megabytes instead of the two gigabytes the
European parcel registries cost.

Three decisions worth knowing about, because each one would bias the size
distribution if taken the other way:

1. **Parcels touching the chip edge are dropped.** They are cut by the tiling,
   not by a farmer, so their area is an artefact. Keeping them would pull the
   whole distribution down and make small parcels look more common than they are.
2. **Selection is a stride, never a random draw.** No seed appears anywhere:
   someone with only this file must get the same cohort.
3. **Countries whose licence forbids commercial reuse are excluded by name**, not
   silently skipped, so the exclusion is auditable.

Usage:
    python tools/build_cohort_ftw.py --chips 3 --per-country 12 --out data/cohorts/ftw.geojson
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

os.environ.setdefault("AWS_NO_SIGN_REQUEST", "YES")
os.environ.setdefault("GDAL_DISABLE_READDIR_ON_OPEN", "EMPTY_DIR")
os.environ.setdefault("CPL_VSIL_CURL_ALLOWED_EXTENSIONS", ".tif")

import rasterio
from rasterio.features import shapes
from shapely.geometry import mapping, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from cielociego.cohort import area_hectares

BUCKET = "https://data.source.coop/kerner-lab/fields-of-the-world/"
UA = {"User-Agent": "cielociego/0.1 (research; https://github.com/EazyHood/cielociego)"}

# Fields of The World licenses per country. These three are CC BY-NC or
# CC BY-NC-SA: a derived cohort published under an open licence would breach
# them, so they never enter. Named rather than filtered by a flag, so that the
# reason survives in the file.
NON_COMMERCIAL = {"latvia", "portugal", "south_africa"}

# A parcel below this is a sliver of the rasterisation, and above it is not a
# parcel but a block. Both ends are reported in the paper.
MIN_HA, MAX_HA = 0.2, 2000.0


def _get(url: str) -> str:
    with urllib.request.urlopen(urllib.request.Request(url, headers=dict(UA)), timeout=90) as r:
        return r.read().decode("utf-8", "replace")


def list_masks(verbose: bool = True) -> dict[str, list[str]]:
    """Every instance-mask key in the bucket, grouped by country."""
    by_country: dict[str, list[str]] = {}
    marker = ""
    pages = 0
    while True:
        url = BUCKET + (f"?marker={urllib.parse.quote(marker, safe='')}" if marker else "")
        body = _get(url)
        keys = re.findall(r"<Key>(.*?)</Key>", body)
        if not keys:
            break
        pages += 1
        for k in keys:
            if "/label_masks/instance/" in k and k.endswith(".tif"):
                by_country.setdefault(k.split("/")[1], []).append(k)
        if "<IsTruncated>true</IsTruncated>" not in body:
            break
        nxt = re.findall(r"<NextMarker>(.*?)</NextMarker>", body)
        marker = (nxt[0].split("/", 1)[1] if nxt else keys[-1])
        if pages > 400:  # pragma: no cover - runaway guard
            print("  ! listing cut at 400 pages", file=sys.stderr)
            break
    if verbose:
        total = sum(len(v) for v in by_country.values())
        print(f"  listed {total} masks over {len(by_country)} countries in {pages} pages")
    return {c: sorted(v) for c, v in sorted(by_country.items())}


def spread(items: list, n: int) -> list:
    """`n` items spread evenly across the list. A stride, not a sample."""
    if n >= len(items):
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


def parcels_from_mask(key: str) -> list[dict]:
    """Polygonise one instance mask into parcels, dropping the cut ones."""
    with rasterio.open("/vsicurl/" + BUCKET + key.split("/", 1)[1]) as src:
        band = src.read(1)
        transform = src.transform

    # Ids that touch the frame are parcels the tiling cut in half.
    edge = set(band[0, :]) | set(band[-1, :]) | set(band[:, 0]) | set(band[:, -1])

    out: list[dict] = []
    for geom, value in shapes(band, mask=(band > 0), transform=transform):
        v = int(value)
        if v in edge:
            continue
        poly = shape(geom)
        if not poly.is_valid:
            poly = poly.buffer(0)
        if poly.is_empty:
            continue
        ha = area_hectares(poly)
        if not (MIN_HA <= ha <= MAX_HA):
            continue
        out.append({"geometry": poly, "area_ha": ha, "instance": v})
    return out


def build(chips_per_country: int, per_country: int, out: Path) -> dict:
    masks = list_masks()
    features = []
    stats: dict[str, int] = {}

    for country, keys in masks.items():
        if country in NON_COMMERCIAL:
            print(f"  {country:<14} skipped: licence forbids commercial reuse")
            continue
        found: list[dict] = []
        for key in spread(keys, chips_per_country):
            try:
                found.extend(parcels_from_mask(key))
            except Exception as exc:  # network or a corrupt chip
                print(f"  {country:<14} ! {type(exc).__name__} on {key.split('/')[-1]}")
        if not found:
            print(f"  {country:<14} no usable parcel")
            continue
        # Spread over the size distribution rather than taking the first ones:
        # the point of the cohort is the range of areas.
        found.sort(key=lambda p: p["area_ha"])
        chosen = spread(found, per_country)
        for n, p in enumerate(chosen):
            features.append({
                "type": "Feature",
                "properties": {
                    "id": f"ftw-{country}-{n:03d}",
                    "country": country,
                    "source": "fields-of-the-world",
                    "area_ha": round(p["area_ha"], 4),
                },
                "geometry": mapping(p["geometry"]),
            })
        stats[country] = len(chosen)
        areas = [p["area_ha"] for p in chosen]
        print(f"  {country:<14} {len(chosen):>3} parcels  "
              f"{min(areas):8.2f} - {max(areas):8.2f} ha")

    doc = {
        "type": "FeatureCollection",
        "name": "ftw-cohort",
        "features": features,
        "provenance": {
            "source": "Fields of The World, Kerner Lab, Source Cooperative",
            "url": BUCKET,
            "built_from": "label_masks/instance",
            "chips_per_country": chips_per_country,
            "parcels_per_country": per_country,
            "excluded_non_commercial": sorted(NON_COMMERCIAL),
            "min_ha": MIN_HA,
            "max_ha": MAX_HA,
            "edge_touching_parcels": "dropped",
            "selection": "stride, no random seed",
        },
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc), encoding="utf-8")
    return {"parcels": len(features), "countries": len(stats), "path": str(out)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--chips", type=int, default=3, help="chips read per country")
    ap.add_argument("--per-country", type=int, default=12, help="parcels kept per country")
    ap.add_argument("--out", type=Path, default=Path("data/cohorts/ftw.geojson"))
    args = ap.parse_args()

    print(f"building cohort: {args.chips} chips and {args.per_country} parcels per country")
    info = build(args.chips, args.per_country, args.out)
    print(f"\n{info['parcels']} parcels over {info['countries']} countries -> {info['path']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
