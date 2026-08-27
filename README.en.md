# cielociego

[![tests](https://github.com/EazyHood/cielociego/actions/workflows/pruebas.yml/badge.svg)](https://github.com/EazyHood/cielociego/actions/workflows/pruebas.yml)
[![coverage 92%](https://img.shields.io/badge/coverage-92%25-2f7d4f)](https://github.com/EazyHood/cielociego/actions/workflows/pruebas.yml)
[![MIT licence](https://img.shields.io/badge/licence-MIT-1d4ed8)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-555)](pyproject.toml)
[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.22132250.svg)](https://doi.org/10.5281/zenodo.22132250)

**How many days the optical satellite cannot see your field — and whether radar
covers the gap.**

*[Léelo en español](README.md) · [Full report](https://eazyhood.github.io/cielociego/)*

Measured over two real fields in Magdalena, Colombia, 2019–2026:
**on 89 % and 91 % of days there was not a single usable optical observation.**
Radar, which sees through cloud, had a pass inside **all 66 long gaps, without a
single exception** — and its time series is not noise: on one field it recorded a
**3.5 dB change** that survives an instrument control, and that was **not
gradual**: plateau, ~2-year transition, new plateau.

Open data. No account, no API key, no cost.

```bash
pip install -e ".[dev]"
python -m cielociego medir          # measures the bundled demo area
```

---

## The problem

In the tropics, persistent cloud leaves whole areas **without a usable image for
weeks or months**. Colombia sits squarely in that belt. That breaks any NDVI time
series — the backbone of most agricultural remote sensing.

Everyone knows this vaguely. This project puts a number on it, for a specific
field, with the method declared and the tests included.

## Why not just use `eo:cloud_cover`?

Because it is computed over the **whole tile: 110 × 110 km, 12,100 km²**. One of
the fields here is 73.5 ha — **0.006 % of that area**.

Cloud is patchy at the kilometre scale, so a small field is **either under it or
not**: 85 % of takes land at an extreme (fully clear or fully covered), against
14 % for the tile.

| | Takes | Really usable | Usable per tile value | Good ones discarded | Bad ones let through |
|---|---:|---:|---:|---:|---:|
| Field A · 73.5 ha | 600 | 316 | 120 | **200** | 4 |
| Field B · 284.1 ha | 602 | 265 | 138 | **132** | 5 |

A **37-to-1 asymmetry**. Filtering by the tile value is not being conservative:
it is a false-negative machine.

## What it does, in five steps

Each step writes its JSON into `salidas/` and the next one reads it from there.
You can stop, resume, and check any figure by hand.

| | Step | Module |
|---|---|---|
| 1 | Fetch the Sentinel-2 catalogue and **deduplicate by processing baseline** | `catalogo` + `dedup` |
| 2 | Read the SCL band **clipped to the polygon**, compute the blind fraction | `scl` + `barrido` |
| 3 | Derive the **stretches with no usable observation** | `radar` |
| 4 | Cross those stretches with **Sentinel-1 passes** | `radar` |
| 5 | Extract the **backscatter time series**, one relative orbit only | `sar` |

Network access goes through a retrying session (`red`): in a measurement tool, a
transient failure swallowed in silence becomes a data point.

## Headline results

```
                          Field A        Field B
days in period ........... 2,794          2,794
days with a usable view ..   315            264
BLIND DAYS ...............   89 %           91 %
longest gap ..............   59 d           89 d
gaps >=15 d with radar ... 34/34          32/32   = 100 %
```

**The headline survives any definition of "cloud".** Counting only
high-confidence cloud — ignoring probable cloud, thin cirrus and shadow, the most
permissive reading you could defend — still leaves **82 % and 84 % blind days**.
It does not live on where you draw the line.

## Three instrument faults found by measuring

1. **STAC pagination.** The continuation key is `body["next"]`, **not**
   `"token"`. The first version returned **100 of 819 scenes without raising**.
   `busca()` now compares against `context.matched` and **fails loudly** if they
   disagree. *A sweep that truncates silently is worse than one that crashes.*
2. **The archive serves the same acquisition twice, with different cloud.** Under
   two processing baselines, and the sensing timestamps differ by **one
   millisecond**, so deduplicating by date does not merge them. The stable key is
   `s2:product_uri`. **26.6 % of items were duplicates.**
3. **Signing every file returned 429** and left 536 of 590 measurements out,
   recorded as *"radar had no data here"* — a false conclusion caused by
   plumbing. The token is **container-scoped**: one request instead of 1,180.

## The cloud mask is a model, and models get updated

The archive serves many acquisitions under two processor versions, and they do
not always agree. Comparing 61 of them over the polygon:

```
bit-identical .................................... 80 %
differ ........................................... 20 %   (mean |diff| 6.7 %)
CROSS the usability threshold .................... 6.6 %
   and always in the same direction: the newer version flags MORE cloud
   (36 usable takes under the old one, 32 under the new)

worst case measured, 2021-11-29, the SAME acquisition:
   baseline N0301 -> field  0.0 % covered
   baseline N0500 -> field 71.8 % covered
```

Since the highest baseline is always kept, **what is published is the
conservative estimate**: more blind days than the older processor would report,
not fewer. Reproducible via `dedup.pares_de_lineas`.

This is not a bug in the archive or in this code — ESA documents that scene
classification thresholds are tuned between baselines. **What would be a fault is
not saying so.**

## What this does *not* claim

- **An NDVI is not replaced by a VV/VH.** Radar measures backscatter (roughness,
  geometry, moisture); optical measures reflectance (pigment, chlorophyll). That
  the radar series has structure and detects a change does not mean it answers
  the same questions.
- **Radar does not always win on count.** With Sentinel-1B retired, in 2022–2024
  the chosen orbit gave ~28 passes a year — fewer than the usable optical images
  of those same years. The advantage lies in the full catalogue (890 radar passes
  across three orbits against 264 usable optical), not in one orbit. One orbit is
  used because that is what makes a comparable series, and it costs observations.
- **What happened on the ground is not known.** Attributing the change to a
  replanting, an irrigation scheme or a land-use switch would require fieldwork
  or planting records.

## Declared choices that move the numbers

- **What counts as blind:** cloud, cloud shadow, cirrus, saturated and no-data
  pixels. Topographic shadow is computed separately (`ciego_amplio`) because on
  flat terrain it is usually wet soil, not shadow. **Measured: it makes no
  difference** — mean gap 0.0001 and **not a single take changes side**.
- **Usability threshold:** 10 % of the field covered. Measured across the whole
  range: at 0 % it is 90/92 % blind days, at 50 % it is 87/88 %. **The conclusion
  does not depend on it.**
- **Minimum field size:** below 25 pixels the measurement is flagged. With 8
  pixels the percentage only moves in 12-point steps and the polygon edge
  dominates. It does not fail — small fields are legitimate — but it is not
  passed off as precise.
- **One take was lost** (2024-01-23) to a path that no longer exists in the
  bucket. Declared as a failure, never counted as clear.

## Usage

```bash
python -m cielociego medir                              # the demo area
python -m cielociego medir --predio my_field.geojson    # your own field
python -m cielociego medir --desde 2022-01-01 --hilos 8
python -m cielociego medir --sin-radar                  # skip the slow step
python -m cielociego medir --orbita 142                 # force one orbit
python -m cielociego pruebas                            # 190 tests
```

The **radar orbit is chosen per field**, because relative orbits depend on where
the field is — a hard-coded one leaves the series silently empty elsewhere. The
breakdown is printed so you can check it:

```
orbitas    {77: 341, 142: 265, 69: 248}  ->  se usa la 77 (341 escenas)
```

Your field is a GeoJSON with **exactly one** `Polygon` feature in EPSG:4326. More
than one and it **fails on purpose**: mixing two fields into a single measurement
is precisely the error this project exists to avoid.

## Bundled data, and what is not bundled

`datos/area_demo.geojson` is a **256 ha demonstration area** — a rectangle drawn
deliberately across property lines, corresponding to no real holding. It exists
so the tool runs straight after cloning.

**The polygons of the two measured fields are not included.** Their coordinates
come from university coursework and one is a lecturer's study area. Publishing
the exact location of someone else's land next to an analysis saying *"something
happened here"* is not this repository's business. The **aggregate figures are**
in `salidas/`, and they cannot reconstruct the polygons: the finest thing present
is the tile code, which covers 110 × 110 km.

## Tests

190 tests, no network: catalogue tests mock HTTP, SCL tests build rasters with
known values.

```bash
pytest tests/ -q --cov=cielociego     # 190 tests, 92 % coverage
mypy src/cielociego                    # clean across 14 modules
ruff check src/ tests/                 # clean
```

They run in **CI on Linux and Windows, Python 3.10 and 3.12**, with the coverage
floor at 75 % so it cannot slip unnoticed.

What they guard, beyond "it doesn't crash":

- **Pagination** must **fail loudly** rather than silently return fewer results.
- **Mutation**: flipping 1 pixel in 100 must move the result by exactly 0.01.
- **The mask really clips**: half cloud, half clear; looking only at the clear
  half must give 0. If the mask did nothing it would give 0.5.
- **Gaps counted by hand**: a view on day 1 and day 10 → gap from 2 to 9 = 8
  days. A one-day error there shifts every figure in the report unnoticed.
- **Determinism under threads**: identical values, histogram included.
- **Chart theming**: no fixed text colour, or the report is unreadable in dark
  mode and nobody notices until it ships.
- **Averaging power, not decibels**: dB is logarithmic, so averaging it gives the
  geometric mean and biases low. With two pixels at −20 dB and 0 dB the bias is
  **7.03 dB**. The test carries the hand-computed number.
- **One signature, not a thousand**: 1,000 files across 16 threads must request
  **one** token.

## Data sources

- **Optical and radar catalogue:** Sentinel-2 L2A and Sentinel-1 GRD through the
  public [Element84 STAC](https://earth-search.aws.element84.com/v1) on AWS.
- **Backscatter series:** Sentinel-1 **RTC** (terrain-corrected, already
  geocoded, in gamma0) from the
  [Planetary Computer](https://planetarycomputer.microsoft.com), anonymously
  signed. Raw GRD is not used: it comes in radar geometry, cannot be clipped by
  lat/lon, and on AWS lives in a requester-pays bucket.

COGs are read **by window**: a full scene is never downloaded.

## How to cite

```
del Río, J. (2026). cielociego: how many days the optical satellite cannot see a
field (v0.1.1) [software]. Zenodo. https://doi.org/10.5281/zenodo.22132250
```

The DOI above is the **concept DOI**: it always resolves to the latest version.
To cite this exact one, use the version DOI: `10.5281/zenodo.22132251`.

GitHub also renders the citation from `CITATION.cff` via *Cite this repository*.

## Licence

MIT. Copernicus data is openly available under ESA's terms.
