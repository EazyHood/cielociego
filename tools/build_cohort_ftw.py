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


# The 25 country directories of the release, each verified by a HEAD request on
# its `chips_<country>.parquet`. They are written out rather than discovered
# because the flat listing of this bucket is dominated by one country: Austria
# alone fills more than 400 pages of a thousand keys, so a sequential listing
# never reaches the tropics. Listing per country with `?prefix=` costs one or
# two requests each instead.
COUNTRIES = [
    "austria", "belgium", "brazil", "cambodia", "corsica", "croatia", "denmark",
    "estonia", "finland", "france", "germany", "india", "kenya", "latvia",
    "lithuania", "luxembourg", "netherlands", "portugal", "rwanda", "slovakia",
    "slovenia", "south_africa", "spain", "sweden", "vietnam",
]


def list_masks(
    countries: list[str] | None = None,
    verbose: bool = True,
    pages_per_country: int = 1,
) -> dict[str, list[str]]:
    """Instance-mask keys per country, one prefixed listing at a time.

    Only the first page of a thousand keys is read per country. Austria alone
    holds hundreds of thousands of chips, so a full listing spends four hundred
    requests on one country and never reaches the tropics. Picking four chips
    out of the first thousand instead of out of all of them is a bias worth
    naming: the selection is over the lexicographic head of each country's
    chips, not over the country. The paper says so.
    """
    by_country: dict[str, list[str]] = {}
    for country in countries or COUNTRIES:
        keys: list[str] = []
        marker = ""
        page_no = 0
        while True:
            q = f"?prefix={country}/label_masks/instance/"
            if marker:
                q += "&marker=" + urllib.parse.quote(marker, safe="")
            body = _get(BUCKET + q)
            page = [k for k in re.findall(r"<Key>(.*?)</Key>", body) if k.endswith(".tif")]
            if not page:
                break
            keys.extend(page)
            page_no += 1
            if page_no >= pages_per_country:
                break
            if "<IsTruncated>true</IsTruncated>" not in body:
                break
            nxt = re.findall(r"<NextMarker>(.*?)</NextMarker>", body)
            marker = nxt[0] if nxt else "kerner-lab/" + page[-1]
        if keys:
            by_country[country] = sorted(keys)
        if verbose:
            print(f"  {country:<14} {len(keys):>6} masks")
    return by_country


def spread(items: list, n: int) -> list:
    """`n` items spread evenly across the list. A stride, not a sample."""
    if n >= len(items):
        return list(items)
    step = len(items) / n
    return [items[int(i * step)] for i in range(n)]


SIZE_BINS = (0.2, 0.5, 1.0, 2.0, 5.0, 20.0, MAX_HA)


def fill_bins(found: list[dict], per_country: int) -> list[dict]:
    """Pick `per_country` parcels spread over size bins, not over the list.

    Takes an equal quota from each bin and hands the leftovers to the bins that
    still have candidates, largest first -- the large end is the scarce one, and
    it is also the end where the paper needs contrast.
    """
    bins: list[list[dict]] = [[] for _ in SIZE_BINS[:-1]]
    for parcel in sorted(found, key=lambda x: x["area_ha"]):
        for i in range(len(SIZE_BINS) - 1):
            if SIZE_BINS[i] <= parcel["area_ha"] < SIZE_BINS[i + 1]:
                bins[i].append(parcel)
                break

    quota = max(1, per_country // len(bins))
    chosen: list[dict] = []
    for group in bins:
        chosen.extend(spread(group, quota))
    if len(chosen) < per_country:
        for group in reversed(bins):
            spare = [p for p in group if p not in chosen]
            take = min(len(spare), per_country - len(chosen))
            chosen.extend(spread(spare, take))
            if len(chosen) >= per_country:
                break
    return sorted(chosen, key=lambda x: x["area_ha"])


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
        # Fill size bins rather than spreading over the sorted list. A plain
        # stride follows the country's own size distribution, and that
        # distribution is overwhelmingly small: it left 232 parcels of which
        # only 15 passed 5 ha, so the largest strata of the analysis had almost
        # nothing in them. The bins are the strata the paper reports, so the
        # cohort is built to fill them.
        chosen = fill_bins(found, per_country)
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
            "selection": "stride over the lexicographic head of each country, no random seed",
            "listing": "first page of 1000 keys per country",
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
