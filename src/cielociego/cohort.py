"""Many fields at once: from a case study to a rule.

The single-field measurement answers "how blind is *this* field". It cannot
answer the question a reviewer actually asks, which is whether the bias is a
property of the metadata or a property of those two polygons. That needs a
cohort: hundreds of public parcel boundaries, spread over climates and sizes,
measured under one protocol.

Two passes, deliberately separated because they cost three orders of magnitude
apart:

* **Catalogue pass** (`catalog_pass`). One STAC query per parcel. No pixels are
  read. Gives revisit, declared-cloud distribution, and how much of the archive
  is reprocessing duplicates. Cheap enough to run over the whole archive.
* **Optical pass** (`optical_pass`). Reads the classification band by window for
  every acquisition of every parcel. This is the expensive one, so it runs on a
  shorter window and, when asked, on a sample.

A note on what the optical pass is *not* measuring, because it decides how the
result must be written up. Both numbers being compared -- the tile's declared
cloud cover and the fraction of the polygon flagged as unusable -- descend from
the same classification. That is the point, not a flaw: this is not an
evaluation of the cloud mask (Foga et al. 2017 and CMIX already do that). It is
a measurement of what is lost when an estimator computed over 12 100 km2 is used
to decide about a parcel four orders of magnitude smaller. Same estimator,
different support.
"""
from __future__ import annotations

import json
import math
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from dataclasses import field as dc_field
from pathlib import Path
from typing import Any

import requests
from shapely.geometry import shape
from shapely.geometry.base import BaseGeometry

from .catalog import S2_L2A, NetworkDown, search
from .dedup import baseline_pairs, deduplicate, identity
from .fields import Field
from .net import session as _session_with_retries
from .scl import MIN_PIXELS

# Filter a practitioner actually applies when browsing a catalogue, and the
# threshold below which enough of the parcel is left to look at anything
# agronomic. Both are parameters, never hard-coded into a conclusion: the
# headline number is reported as a curve over both.
#
# 10 % on both sides is the reference pair because it is the one the published
# two-field result used, so the cohort and the case study stay comparable.
# `test_reproduces_the_published_two_field_result` pins it: with these values
# the stored outputs give back 332 false negatives against 9 false positives.
DEFAULT_TILE_FILTER = 0.10
DEFAULT_BLIND_LIMIT = 0.10

# Equal-area projection used only to put an area in hectares on a lat/lon
# polygon. Cylindrical equal-area is exact in area and wrong in shape, which is
# the correct trade here.
_EARTH_RADIUS_M = 6_371_008.8


@dataclass(frozen=True)
class Parcel:
    """One agricultural parcel from a public boundary dataset."""

    id: str
    source: str
    country: str
    geometry: BaseGeometry
    area_ha: float

    @property
    def centroid(self) -> tuple[float, float]:
        c = self.geometry.centroid
        return (float(c.x), float(c.y))

    def as_field(self) -> Field:
        """Adapt to the single-field type the rest of the package speaks."""
        return Field(name=self.id, geometry=self.geometry, area_ha=self.area_ha)


def area_hectares(geom: BaseGeometry) -> float:
    """Area of a lon/lat polygon, in hectares.

    Uses a cylindrical equal-area projection centred on the polygon's own
    latitude. Good to well under a percent for parcel-sized shapes, needs no
    projection library call per feature, and -- unlike the naive degrees^2
    that this replaces in many scripts -- does not shrink by a factor of two
    between the equator and 60 degrees.
    """
    lat0 = math.radians(geom.centroid.y)
    kx = _EARTH_RADIUS_M * math.cos(lat0) * math.pi / 180.0
    ky = _EARTH_RADIUS_M * math.pi / 180.0
    return float(geom.area * kx * ky / 10_000.0)


def load_cohort(
    path: str | Path,
    *,
    source: str | None = None,
    id_key: str = "id",
    country_key: str = "country",
) -> list[Parcel]:
    """Read a many-feature GeoJSON of parcel boundaries.

    Unlike `load_field`, more than one feature is the whole point here. Invalid
    geometries are repaired with a zero buffer and empty ones are dropped, both
    counted by the caller through the returned length.
    """
    path = Path(path)
    doc = json.loads(path.read_text(encoding="utf-8"))
    feats = doc["features"] if doc.get("type") == "FeatureCollection" else [doc]
    src = source or path.stem

    out: list[Parcel] = []
    for n, feat in enumerate(feats):
        props = feat.get("properties") or {}
        geom = shape(feat["geometry"])
        if not geom.is_valid:
            geom = geom.buffer(0)
        if geom.is_empty:
            continue
        out.append(
            Parcel(
                id=str(props.get(id_key) or f"{src}-{n:05d}"),
                source=str(props.get("source") or src),
                country=str(props.get(country_key) or "??"),
                geometry=geom,
                area_ha=float(props.get("area_ha") or area_hectares(geom)),
            )
        )
    return out


@dataclass
class CatalogRow:
    """What the catalogue alone says about one parcel."""

    parcel_id: str
    source: str
    country: str
    area_ha: float
    lon: float
    lat: float
    items: int = 0
    acquisitions: int = 0
    duplicates: int = 0
    no_uri: int = 0
    baseline_pairs: int = 0
    cloud_gap_max: float | None = None
    cloud_gap_mean: float | None = None
    cloud_gap_ratio_max: float | None = None
    sensing_gap_ms_min: float | None = None
    error: str | None = None

    @property
    def duplicate_pct(self) -> float:
        return 100.0 * self.duplicates / self.items if self.items else float("nan")

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["duplicate_pct"] = self.duplicate_pct
        return d


def _declared_cloud(item: dict[str, Any]) -> float | None:
    cc = (item.get("properties", item) or {}).get("eo:cloud_cover")
    return None if cc is None else float(cc)


def _sensing_ms(item: dict[str, Any]) -> float | None:
    """Sensing instant in milliseconds, for the copies that differ by one.

    The datetime is what a reasonable person would deduplicate on, and it is
    exactly what fails: the copies of one acquisition are served with
    timestamps that differ, sometimes by a millisecond and sometimes by
    minutes. Measuring that difference is the point.
    """
    dt = (item.get("properties", item) or {}).get("datetime")
    if not dt or "T" not in dt:
        return None
    hhmmss = dt.split("T", 1)[1].rstrip("Z")
    try:
        h, m, s = hhmmss.split(":")
        return (int(h) * 3600 + int(m) * 60 + float(s)) * 1000.0
    except ValueError:  # pragma: no cover - defensive
        return None


def catalog_row(
    parcel: Parcel,
    start: str,
    end: str,
    *,
    session: requests.Session | None = None,
) -> CatalogRow:
    """One STAC query for one parcel. No pixels are read.

    Never raises on a network failure: the row comes back with `error` set, so a
    cohort of 500 cannot die on one parcel -- and a parcel that could not be
    asked about is never recorded as a parcel with no data.
    """
    lon, lat = parcel.centroid
    row = CatalogRow(parcel.id, parcel.source, parcel.country, parcel.area_ha, lon, lat)
    try:
        sweep = search(S2_L2A, parcel.geometry.bounds, start, end, session=session)
    except (NetworkDown, RuntimeError) as exc:
        row.error = f"{type(exc).__name__}: {exc}"[:200]
        return row

    items = sweep.items
    kept, dropped = deduplicate(items)
    row.items = len(items)
    row.acquisitions = len(kept)
    row.duplicates = len(dropped)
    row.no_uri = sum(1 for it in items if identity(it)[0] is None)

    pairs = baseline_pairs(items)
    row.baseline_pairs = len(pairs)
    gaps: list[float] = []
    ratios: list[float] = []
    ms_gaps: list[float] = []
    for older, newer in pairs:
        a, b = _declared_cloud(older), _declared_cloud(newer)
        if a is not None and b is not None:
            gaps.append(abs(b - a))
            lo, hi = sorted((a, b))
            if lo > 0:
                ratios.append(hi / lo)
        ma, mb = _sensing_ms(older), _sensing_ms(newer)
        if ma is not None and mb is not None:
            ms_gaps.append(abs(mb - ma))
    if gaps:
        row.cloud_gap_max = max(gaps)
        row.cloud_gap_mean = sum(gaps) / len(gaps)
    if ratios:
        row.cloud_gap_ratio_max = max(ratios)
    if ms_gaps:
        row.sensing_gap_ms_min = min(ms_gaps)
    return row


def catalog_pass(
    parcels: Sequence[Parcel],
    start: str,
    end: str,
    *,
    workers: int = 8,
    notify: Any = None,
) -> list[CatalogRow]:
    """Catalogue-only pass over a cohort. One row per parcel."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    session = _session_with_retries()
    rows: list[CatalogRow] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(catalog_row, p, start, end, session=session): p for p in parcels
        }
        for n, fut in enumerate(as_completed(futures), 1):
            rows.append(fut.result())
            if notify:
                notify(n, len(futures))
    rows.sort(key=lambda r: r.parcel_id)
    return rows


@dataclass
class Observation:
    """One acquisition seen from one parcel: what the tile said, what was there."""

    parcel_id: str
    source: str
    country: str
    area_ha: float
    date: str
    scene_id: str
    pixels: int
    tile_cloud: float | None       # 0-100, as the catalogue declares it
    blind: float                   # 0-1 over the polygon, strict definition
    blind_wide: float
    error: str | None = None

    @property
    def kept_by_filter(self) -> bool | None:
        """Would a tile-cloud filter have kept this acquisition?"""
        if self.tile_cloud is None:
            return None
        return self.tile_cloud / 100.0 <= _FILTER["tile"]

    def dict(self) -> dict[str, Any]:
        return asdict(self)


# Module-level filter setting, only so `kept_by_filter` reads well in the
# dataclass. Every function that matters takes the thresholds explicitly.
_FILTER = {"tile": DEFAULT_TILE_FILTER}


@dataclass
class Confusion:
    """Tile-metadata filter judged against what the polygon actually shows."""

    tile_threshold: float
    blind_limit: float
    kept_useful: int = 0        # true positive
    kept_useless: int = 0       # false positive: processed for nothing
    dropped_useful: int = 0     # false negative: a good day thrown away
    dropped_useless: int = 0    # true negative
    n_parcels: int = 0
    unusable_rows: int = 0
    below_pixel_floor: int = 0  # parcel too small for the number to mean anything

    @property
    def total(self) -> int:
        return self.kept_useful + self.kept_useless + self.dropped_useful + self.dropped_useless

    @property
    def asymmetry(self) -> float:
        """False negatives per false positive. The headline number."""
        return self.dropped_useful / self.kept_useless if self.kept_useless else float("inf")

    @property
    def recall(self) -> float:
        """Share of genuinely useful acquisitions the filter lets through."""
        useful = self.kept_useful + self.dropped_useful
        return self.kept_useful / useful if useful else float("nan")

    @property
    def precision(self) -> float:
        kept = self.kept_useful + self.kept_useless
        return self.kept_useful / kept if kept else float("nan")

    def dict(self) -> dict[str, Any]:
        d = asdict(self)
        d.update(
            total=self.total,
            asymmetry=self.asymmetry,
            recall=self.recall,
            precision=self.precision,
        )
        return d


def confusion(
    observations: Iterable[Observation],
    *,
    tile_threshold: float = DEFAULT_TILE_FILTER,
    blind_limit: float = DEFAULT_BLIND_LIMIT,
    min_pixels: int = MIN_PIXELS,
) -> Confusion:
    """Cross the filter's verdict with the polygon's.

    Rows with an error, with no declared cloud cover, or with a blind fraction
    that is not a number are counted apart and never guessed at. An acquisition
    that could not be read is not evidence either way.

    `min_pixels` matters more than it looks. Half of a cohort drawn from real
    parcel boundaries is under a hectare, and a hectare is 25 pixels of the 20 m
    classification band: below that the blind fraction moves in four-point steps
    and the polygon edge outweighs its interior. Counting those rows in the
    main matrix would let rasterisation noise masquerade as the very
    size effect the paper claims to measure. They are set aside and counted, and
    the paper reports them as their own stratum. Pass `min_pixels=0` to see the
    unfiltered matrix, which is exactly the sensitivity check a reviewer asks for.
    """
    out = Confusion(tile_threshold, blind_limit)
    seen: set[str] = set()
    for obs in observations:
        seen.add(obs.parcel_id)
        if obs.error or obs.tile_cloud is None or math.isnan(obs.blind):
            out.unusable_rows += 1
            continue
        if obs.pixels < min_pixels:
            out.below_pixel_floor += 1
            continue
        kept = obs.tile_cloud / 100.0 <= tile_threshold
        useful = obs.blind <= blind_limit
        if kept and useful:
            out.kept_useful += 1
        elif kept and not useful:
            out.kept_useless += 1
        elif not kept and useful:
            out.dropped_useful += 1
        else:
            out.dropped_useless += 1
    out.n_parcels = len(seen)
    return out


def confusion_by_area(
    observations: Sequence[Observation],
    *,
    edges: Sequence[float] = (0.0, 1.0, 5.0, 20.0, 100.0, 500.0, float("inf")),
    tile_threshold: float = DEFAULT_TILE_FILTER,
    blind_limit: float = DEFAULT_BLIND_LIMIT,
    min_pixels: int = MIN_PIXELS,
) -> list[tuple[str, Confusion]]:
    """The same matrix, split by parcel size.

    This is the table that turns the finding into a rule: if the false-negative
    rate rises as the parcel shrinks, the bias is a function of the mismatch in
    support and not of one region's weather.
    """
    bins: dict[int, list[Observation]] = {}
    for obs in observations:
        idx = max(i for i, e in enumerate(edges[:-1]) if obs.area_ha >= e)
        bins.setdefault(idx, []).append(obs)

    out: list[tuple[str, Confusion]] = []
    for idx in sorted(bins):
        lo, hi = edges[idx], edges[idx + 1]
        label = f">={lo:g} ha" if math.isinf(hi) else f"{lo:g}-{hi:g} ha"
        out.append((
            label,
            confusion(bins[idx], tile_threshold=tile_threshold, blind_limit=blind_limit,
                      min_pixels=min_pixels),
        ))
    return out


def sensitivity(
    observations: Sequence[Observation],
    *,
    tile_thresholds: Sequence[float] = (0.05, 0.10, 0.20, 0.30, 0.50),
    blind_limits: Sequence[float] = (0.05, 0.10, 0.20),
    min_pixels: int = MIN_PIXELS,
) -> list[Confusion]:
    """The whole grid of thresholds.

    A single pair of thresholds invites the reply "you picked the numbers that
    worked". Reporting the grid removes the question.
    """
    return [
        confusion(observations, tile_threshold=t, blind_limit=b, min_pixels=min_pixels)
        for t in tile_thresholds
        for b in blind_limits
    ]


def _scene_list(items: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """STAC items to the shape `sweep` reads, deduplicated and date-sorted."""
    kept, _ = deduplicate(items)
    scenes = [
        {
            "id": it.get("id", ""),
            "date": it["properties"]["datetime"],
            "cc": it["properties"].get("eo:cloud_cover"),
            "scl": (it.get("assets") or {}).get("scl", {}).get("href"),
        }
        for it in kept
    ]
    return [s for s in scenes if s["scl"]]


def thin(scenes: Sequence[dict[str, Any]], cap: int | None) -> list[dict[str, Any]]:
    """At most `cap` acquisitions, spread evenly over the period.

    A stride, not a random sample, and no seed anywhere: the run has to be
    reproducible by someone who only has the code. Taking the first N instead
    would sample one season and call it a year.
    """
    if cap is None or len(scenes) <= cap:
        return list(scenes)
    ordered = sorted(scenes, key=lambda s: s["date"])
    step = len(ordered) / cap
    return [ordered[int(i * step)] for i in range(cap)]


def optical_pass(
    parcels: Sequence[Parcel],
    start: str,
    end: str,
    *,
    workers: int = 10,
    cap_per_parcel: int | None = None,
    notify: Any = None,
    on_parcel: Any = None,
    skip: set[str] | None = None,
) -> list[Observation]:
    """Read the classification band over every parcel. The expensive pass.

    Parcels are processed one after another and their acquisitions in parallel:
    the bottleneck is range reads against one bucket, so widening the outer loop
    as well only earns throttling. A parcel whose catalogue query fails is
    skipped with a row of its own rather than silently contributing nothing.

    `on_parcel` is called with the rows of each parcel as soon as they exist, and
    `skip` holds the parcel ids already on disk. Together they make a run of
    several hundred parcels restartable, which stopped being optional the first
    time a single slow file held the whole cohort for five minutes: with a
    sixty-second timeout and five retries, one unlucky object can cost more than
    the rest of the parcel put together, and losing the work already done to it
    is the difference between an afternoon and a week.
    """
    session = _session_with_retries()
    out: list[Observation] = []
    for n, parcel in enumerate(parcels, 1):
        if skip and parcel.id in skip:
            if notify:
                notify(n, len(parcels))
            continue
        try:
            sweep_res = search(S2_L2A, parcel.geometry.bounds, start, end, session=session)
            scenes = thin(_scene_list(sweep_res.items), cap_per_parcel)
        except (NetworkDown, RuntimeError) as exc:
            out.append(
                Observation(
                    parcel.id, parcel.source, parcel.country, parcel.area_ha,
                    "", "", 0, None, float("nan"), float("nan"),
                    error=f"{type(exc).__name__}: {exc}"[:200],
                )
            )
            if notify:
                notify(n, len(parcels))
            continue

        from .sweep import sweep as _sweep

        res = _sweep(parcel.as_field(), scenes, workers=workers)
        for view in list(res.views) + list(res.failed):
            out.append(
                Observation(
                    parcel_id=parcel.id,
                    source=parcel.source,
                    country=parcel.country,
                    area_ha=parcel.area_ha,
                    date=view.date,
                    scene_id=view.scene_id,
                    pixels=view.pixels,
                    tile_cloud=view.tile_cloud,
                    blind=view.blind_strict,
                    blind_wide=view.blind_wide,
                    error=view.error,
                )
            )
        if on_parcel:
            on_parcel(parcel, [o for o in out if o.parcel_id == parcel.id])
        if notify:
            notify(n, len(parcels))
    return out


@dataclass
class CohortResult:
    """Everything a cohort run produced, ready to be written once."""

    start: str
    end: str
    catalog: list[CatalogRow] = dc_field(default_factory=list)
    observations: list[Observation] = dc_field(default_factory=list)
    provenance: dict[str, Any] = dc_field(default_factory=dict)

    def save_json(self, path: str | Path) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "start": self.start,
                    "end": self.end,
                    "provenance": self.provenance,
                    "catalog": [r.dict() for r in self.catalog],
                    "observations": [o.dict() for o in self.observations],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        return path

    def save_csv(self, path: str | Path) -> Path:
        """Tidy one-row-per-observation table -- the citable artefact.

        Written with the standard library on purpose: a reader should be able to
        open the dataset without installing anything this project depends on.
        """
        import csv

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cols = [
            "parcel_id", "source", "country", "area_ha", "date", "scene_id",
            "pixels", "tile_cloud", "blind", "blind_wide", "error",
        ]
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for o in self.observations:
                w.writerow({k: o.dict()[k] for k in cols})
        return path

    def save_catalog_csv(self, path: str | Path) -> Path:
        import csv

        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        cols = [
            "parcel_id", "source", "country", "area_ha", "lon", "lat", "items",
            "acquisitions", "duplicates", "duplicate_pct", "no_uri", "baseline_pairs",
            "cloud_gap_max", "cloud_gap_mean", "cloud_gap_ratio_max",
            "sensing_gap_ms_min", "error",
        ]
        with path.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            for r in self.catalog:
                w.writerow({k: r.dict()[k] for k in cols})
        return path
