"""Tests for the cohort pass: many parcels under one protocol.

The numbers in the confusion cases are hand-counted on purpose. A matrix that
is only checked against itself passes even when the four cells are wired to the
wrong corners, which is exactly the mistake that would invert the paper's
headline.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
from shapely.geometry import Polygon, box

from cielociego.cohort import (
    CohortResult,
    Observation,
    Parcel,
    _scene_list,
    area_hectares,
    catalog_row,
    confusion,
    confusion_by_area,
    load_cohort,
    sensitivity,
    thin,
)

# --- area ------------------------------------------------------------------

def test_a_one_kilometre_square_is_a_hundred_hectares():
    """1 km x 1 km = 100 ha. At the equator the degree box is easy to write."""
    side_deg = 1000.0 / (6_371_008.8 * math.pi / 180.0)
    square = box(0.0, 0.0, side_deg, side_deg)
    assert area_hectares(square) == pytest.approx(100.0, rel=0.01)


def test_the_same_degree_box_shrinks_towards_the_pole():
    """Control: without the cosine the area would be latitude-independent.

    This is the check that would fail if someone 'simplified' the projection
    into degrees squared. At 60 degrees the same box covers half the ground.
    """
    at_equator = area_hectares(box(0.0, 0.0, 0.01, 0.01))
    at_sixty = area_hectares(box(0.0, 60.0, 0.01, 60.01))
    assert at_sixty == pytest.approx(at_equator * 0.5, rel=0.02)


# --- loading ---------------------------------------------------------------

def _collection(*features):
    return {"type": "FeatureCollection", "features": list(features)}


def _feature(coords, **props):
    return {"type": "Feature", "properties": props, "geometry": {"type": "Polygon", "coordinates": [coords]}}


def test_loads_many_features_where_load_field_would_refuse(tmp_path):
    p = tmp_path / "co.geojson"
    p.write_text(json.dumps(_collection(
        _feature([(0, 0), (0, 0.01), (0.01, 0.01), (0.01, 0), (0, 0)], id="a", country="CO"),
        _feature([(1, 1), (1, 1.01), (1.01, 1.01), (1.01, 1), (1, 1)], id="b", country="BR"),
    )), encoding="utf-8")
    parcels = load_cohort(p, source="test")
    assert [x.id for x in parcels] == ["a", "b"]
    assert [x.country for x in parcels] == ["CO", "BR"]
    assert all(x.area_ha > 0 for x in parcels)


def test_missing_identifiers_get_a_stable_fallback(tmp_path):
    p = tmp_path / "anon.geojson"
    p.write_text(json.dumps(_collection(
        _feature([(0, 0), (0, 0.01), (0.01, 0.01), (0.01, 0), (0, 0)]),
    )), encoding="utf-8")
    (parcel,) = load_cohort(p, source="src")
    assert parcel.id == "src-00000"


def test_an_empty_geometry_is_dropped_not_carried(tmp_path):
    p = tmp_path / "mix.geojson"
    p.write_text(json.dumps(_collection(
        _feature([(0, 0), (0, 0), (0, 0), (0, 0)], id="degenerate"),
        _feature([(0, 0), (0, 0.01), (0.01, 0.01), (0.01, 0), (0, 0)], id="good"),
    )), encoding="utf-8")
    parcels = load_cohort(p)
    assert [x.id for x in parcels] == ["good"]


# --- the confusion matrix --------------------------------------------------

def obs(tile, blind, *, area=10.0, pid="p", err=None):
    return Observation("p" if pid == "p" else pid, "src", "CO", area, "2024-01-01", "s", 400,
                       tile, blind, blind, error=err)


def test_the_four_cells_land_where_they_should():
    """Hand-counted. Filter keeps tile<=20 %; the parcel is usable at blind<=10 %."""
    rows = [
        obs(5.0, 0.02),    # kept and useful          -> true positive
        obs(5.0, 0.80),    # kept but blind           -> false positive
        obs(90.0, 0.01),   # dropped yet clear        -> false negative
        obs(90.0, 0.95),   # dropped and blind        -> true negative
    ]
    m = confusion(rows)
    assert (m.kept_useful, m.kept_useless, m.dropped_useful, m.dropped_useless) == (1, 1, 1, 1)
    assert m.total == 4 and m.asymmetry == 1.0


def test_the_asymmetry_is_false_negatives_over_false_positives():
    rows = [obs(90.0, 0.01) for _ in range(37)] + [obs(5.0, 0.80)]
    m = confusion(rows)
    assert m.dropped_useful == 37 and m.kept_useless == 1
    assert m.asymmetry == 37.0


def test_rows_that_could_not_be_read_are_set_aside_never_guessed():
    rows = [
        obs(5.0, 0.02),
        obs(5.0, float("nan"), err="HTTPError: 404"),
        obs(None, 0.02),
        obs(5.0, float("nan")),
    ]
    m = confusion(rows)
    assert m.total == 1 and m.unusable_rows == 3


def test_moving_the_threshold_moves_the_matrix():
    """Mutation control: a matrix that ignores its thresholds would pass the rest."""
    rows = [obs(30.0, 0.02)]
    strict = confusion(rows, tile_threshold=0.20)
    loose = confusion(rows, tile_threshold=0.50)
    assert strict.dropped_useful == 1 and strict.kept_useful == 0
    assert loose.kept_useful == 1 and loose.dropped_useful == 0


def test_recall_and_precision_do_not_divide_by_zero():
    m = confusion([obs(90.0, 0.95)])
    assert math.isnan(m.recall) and math.isnan(m.precision)
    assert m.asymmetry == float("inf") or m.asymmetry == 0.0


# --- the size rule ---------------------------------------------------------

def test_parcels_are_binned_by_area_and_every_row_lands_once():
    rows = [obs(90.0, 0.01, area=a, pid=f"p{i}") for i, a in enumerate([0.5, 3, 10, 50, 200, 900])]
    bins = confusion_by_area(rows)
    assert len(bins) == 6
    assert sum(c.total for _, c in bins) == len(rows)
    assert bins[-1][0].startswith(">=500")


def test_the_grid_of_thresholds_is_complete():
    rows = [obs(30.0, 0.02)]
    assert len(sensitivity(rows, tile_thresholds=(0.1, 0.2), blind_limits=(0.05, 0.1, 0.2))) == 6


# --- sampling --------------------------------------------------------------

def _scenes(n):
    return [{"date": f"2024-{1 + i // 28:02d}-{1 + i % 28:02d}", "scl": "x", "id": str(i), "cc": 0}
            for i in range(n)]


def test_thinning_respects_the_cap_and_keeps_the_span():
    picked = thin(_scenes(100), 10)
    assert len(picked) == 10
    assert picked[0]["date"] == "2024-01-01"
    assert picked[-1]["date"] > "2024-03-01"


def test_thinning_is_reproducible_without_a_seed():
    a = thin(_scenes(100), 7)
    b = thin(_scenes(100), 7)
    assert [x["id"] for x in a] == [x["id"] for x in b]


def test_thinning_below_the_cap_changes_nothing():
    assert len(thin(_scenes(5), 10)) == 5
    assert len(thin(_scenes(5), None)) == 5


def test_scenes_without_a_classification_band_are_not_measured():
    items = [
        {"id": "a", "properties": {"datetime": "2024-01-01T00:00:00Z", "eo:cloud_cover": 1.0,
                                   "s2:product_uri": "S2A_MSIL2A_20240101T000000_N0500_R001_T18PXS"},
         "assets": {"scl": {"href": "http://x/scl.tif"}}},
        {"id": "b", "properties": {"datetime": "2024-01-02T00:00:00Z", "eo:cloud_cover": 2.0,
                                   "s2:product_uri": "S2A_MSIL2A_20240102T000000_N0500_R001_T18PXS"},
         "assets": {}},
    ]
    assert [s["id"] for s in _scene_list(items)] == ["a"]


# --- the catalogue row -----------------------------------------------------

class _FakeSweep:
    def __init__(self, items):
        self.items = items

    def __len__(self):
        return len(self.items)


def _item(uri, cc, datetime_):
    return {"id": uri, "properties": {"s2:product_uri": uri, "eo:cloud_cover": cc,
                                      "datetime": datetime_},
            "assets": {"scl": {"href": "http://x/scl.tif"}}}


def test_the_catalogue_row_counts_copies_and_measures_their_disagreement(monkeypatch):
    """The real pair from tile 18PWT, 25-mar-2019: 2.58 % against 3.3957 %."""
    old = _item("S2A_MSIL2A_20190325T152641_N0211_R025_T18PWT", 2.5800,
                "2019-03-25T15:30:25.936000Z")
    new = _item("S2A_MSIL2A_20190325T152641_N0500_R025_T18PWT", 3.3957,
                "2019-03-25T15:30:02.024000Z")
    monkeypatch.setattr("cielociego.cohort.search", lambda *a, **k: _FakeSweep([old, new]))

    parcel = Parcel("x", "test", "CO", box(0, 0, 0.01, 0.01), 10.0)
    row = catalog_row(parcel, "2019-01-01", "2019-12-31")

    assert row.items == 2 and row.acquisitions == 1 and row.duplicates == 1
    assert row.duplicate_pct == 50.0
    assert row.baseline_pairs == 1
    assert row.cloud_gap_max == pytest.approx(0.8157, abs=1e-4)
    assert row.cloud_gap_ratio_max == pytest.approx(3.3957 / 2.58, rel=1e-6)
    assert row.sensing_gap_ms_min == pytest.approx(23_912.0, abs=1.0)


def test_a_parcel_that_could_not_be_asked_about_is_not_a_parcel_with_no_data(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("the network fell over")

    monkeypatch.setattr("cielociego.cohort.search", boom)
    parcel = Parcel("x", "test", "CO", box(0, 0, 0.01, 0.01), 10.0)
    row = catalog_row(parcel, "2019-01-01", "2019-12-31")
    assert row.error and row.items == 0 and row.acquisitions == 0


# --- writing ---------------------------------------------------------------

def test_the_tidy_table_opens_without_any_dependency(tmp_path):
    res = CohortResult("2023-01-01", "2024-12-31", observations=[obs(5.0, 0.02)])
    path = res.save_csv(tmp_path / "obs.csv")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("parcel_id,source,country,area_ha,date")
    assert len(lines) == 2


def test_the_geometry_survives_a_repair(tmp_path):
    """A bowtie is invalid; buffer(0) makes it measurable instead of dropping it."""
    bowtie = Polygon([(0, 0), (0.01, 0.01), (0.01, 0), (0, 0.01), (0, 0)])
    assert not bowtie.is_valid
    p = tmp_path / "bad.geojson"
    p.write_text(json.dumps(_collection({
        "type": "Feature", "properties": {"id": "bt"},
        "geometry": json.loads(json.dumps(bowtie.__geo_interface__)),
    })), encoding="utf-8")
    (parcel,) = load_cohort(p)
    assert parcel.geometry.is_valid and parcel.area_ha > 0


# --- the control that ties the cohort to the published case study ----------

def test_reproduces_the_published_two_field_result():
    """332 false negatives against 9 false positives, from the stored outputs.

    This is the test that matters most in the file. The cohort code is a
    rewrite of the analysis that produced the published figure, and a rewrite
    that quietly disagrees with the original is worse than no rewrite: the
    paper would report one number and the repository another. Reading the same
    JSON the report was built from, with the same thresholds, must give the
    same four cells.
    """
    root = Path(__file__).resolve().parents[1] / "outputs"
    rows = []
    for key in ("field_fundacion", "field_corridor"):
        doc = json.loads((root / f"{key}_scl.json").read_text(encoding="utf-8"))
        rows += [
            Observation(key, "own", "CO", doc.get("area_ha") or 0.0, v["date"], v["scene_id"],
                        v["pixels"], v["tile_cloud"], v["blind_strict"], v["blind_wide"],
                        v.get("error"))
            for v in doc["views"]
        ]

    m = confusion(rows, tile_threshold=0.10, blind_limit=0.10)
    assert (m.dropped_useful, m.kept_useless) == (332, 9)
    assert m.asymmetry == pytest.approx(332 / 9, rel=1e-9)


def test_the_published_result_is_not_an_artefact_of_one_threshold():
    """Control: the asymmetry survives every threshold worth using.

    If it only appeared at 10 % the honest reading would be that the pair of
    numbers was chosen, not found. It does not: false negatives outnumber false
    positives at every filter setting up to 30 %.
    """
    root = Path(__file__).resolve().parents[1] / "outputs"
    rows = []
    for key in ("field_fundacion", "field_corridor"):
        doc = json.loads((root / f"{key}_scl.json").read_text(encoding="utf-8"))
        rows += [
            Observation(key, "own", "CO", doc.get("area_ha") or 0.0, v["date"], v["scene_id"],
                        v["pixels"], v["tile_cloud"], v["blind_strict"], v["blind_wide"],
                        v.get("error"))
            for v in doc["views"]
        ]

    for t in (0.05, 0.10, 0.20, 0.30):
        m = confusion(rows, tile_threshold=t)
        assert m.dropped_useful > m.kept_useless, f"threshold {t} breaks the asymmetry"


# --- the pixel floor -------------------------------------------------------

def small(tile, blind, pixels, *, area=0.4):
    return Observation("tiny", "src", "RW", area, "2024-01-01", "s", pixels,
                       tile, blind, blind)


def test_a_parcel_too_small_to_measure_is_set_aside_not_counted():
    """A 0.4 ha parcel is 10 pixels of the 20 m band: the fraction moves in
    ten-point steps and the edge outweighs the interior. Letting those rows into
    the main matrix would let rasterisation noise pose as the size effect the
    paper claims to find."""
    rows = [small(90.0, 0.01, 10), small(90.0, 0.01, 400)]
    m = confusion(rows)
    assert m.total == 1 and m.below_pixel_floor == 1


def test_the_floor_can_be_lifted_because_a_reviewer_will_ask():
    rows = [small(90.0, 0.01, 10), small(90.0, 0.01, 400)]
    assert confusion(rows, min_pixels=0).total == 2


def test_the_floor_reaches_the_stratified_table_and_the_grid():
    """Control: a filter that only applied to the pooled matrix would report a
    clean headline and dirty strata, which is the worst of both."""
    rows = [small(90.0, 0.01, 10, area=0.4), small(90.0, 0.01, 400, area=30.0)]
    bins = confusion_by_area(rows)
    assert sum(c.total for _, c in bins) == 1
    assert sum(c.below_pixel_floor for _, c in bins) == 1
    assert all(c.total + c.below_pixel_floor <= 2 for c in sensitivity(rows))
