"""Pruebas del cruce optico-radar.

El nucleo es `optical_gaps`: cuenta days en los que NO hubo observacion
util. Un error de un dia ahi (off-by-one) corre todas las cifras del
informe, y no se nota mirando. Por eso se prueba con casos donde el
resultado esta contado a mano.
"""
from __future__ import annotations

from datetime import date

from cielociego.radar import (
    Gap,
    Pass,
    cross,
    optical_gaps,
    s1_identity,
    to_passes,
)

D = date
ENE = lambda d: date(2023, 1, d)


def item_s1(idr, date, orbit="ascending"):
    return {
        "id": idr,
        "properties": {
            "datetime": date,
            "platform": "sentinel-1a",
            "sat:orbit_state": orbit,
            "sar:instrument_mode": "IW",
            "sar:polarizations": ["VV", "VH"],
        },
    }


REAL = "S1A_IW_GRDH_1SDV_20231222T230735_20231222T230800_051774_0640E8"


# --- identity y deduplicacion ---------------------------------------------
def test_identity_of_a_real_id():
    assert s1_identity({"id": REAL}) == ("S1A", "20231222T230735")


def test_an_unreadable_id_does_not_raise():
    assert s1_identity({"id": "cualquier_cosa"}) is None


def test_deduplicates_by_physical_identity():
    a = item_s1(REAL, "2023-12-22T23:07:48Z")
    b = item_s1(REAL, "2023-12-22T23:07:48Z")  # mismo producto repetido
    assert len(to_passes([a, b])) == 1


def test_ascending_and_descending_on_one_day_are_two_passes():
    a = item_s1(REAL, "2023-12-22T23:07:48Z", "ascending")
    b = item_s1(
        "S1A_IW_GRDH_1SDV_20231222T104146_20231222T104215_051766_0640A7",
        "2023-12-22T10:42:01Z", "descending",
    )
    ps = to_passes([a, b])
    assert len(ps) == 2
    assert {p.orbit for p in ps} == {"ascending", "descending"}
    assert ps[0].polarizaciones == ("VV", "VH")


# --- huecos: los casos contados a mano -------------------------------------
def test_with_no_usable_view_the_whole_period_is_a_gap():
    h = optical_gaps([], ENE(1), ENE(31))
    assert h == [(ENE(1), ENE(31))]
    assert Gap(*h[0], 0).days == 31


def test_vista_usable_all_the_days_not_deja_gap():
    assert optical_gaps([ENE(d) for d in range(1, 32)], ENE(1), ENE(31)) == []


def test_gap_between_two_vistas_is_the_intervalo_abierto():
    """A view on day 1 and day 10 leaves days 2..9, eight days. Counted by hand."""
    h = optical_gaps([ENE(1), ENE(10)], ENE(1), ENE(10))
    assert h == [(ENE(2), ENE(9))]
    assert Gap(*h[0], 0).days == 8


def test_days_consecutivos_not_dejan_gap():
    assert optical_gaps([ENE(5), ENE(6)], ENE(5), ENE(6)) == []


def test_ends_ciegos_cuentan():
    """A series that starts and ends blind: both edges are real gaps."""
    h = optical_gaps([ENE(10), ENE(20)], ENE(1), ENE(31))
    assert h == [(ENE(1), ENE(9)), (ENE(11), ENE(19)), (ENE(21), ENE(31))]
    assert [Gap(*t, 0).days for t in h] == [9, 9, 11]


def test_dates_outside_the_period_are_ignored():
    h = optical_gaps([date(2022, 12, 20), ENE(15), date(2024, 1, 1)], ENE(1), ENE(31))
    assert h == [(ENE(1), ENE(14)), (ENE(16), ENE(31))]


def test_repeated_or_unsorted_dates_give_the_same():
    ordenado = optical_gaps([ENE(5), ENE(15)], ENE(1), ENE(20))
    revuelto = optical_gaps([ENE(15), ENE(5), ENE(15)], ENE(1), ENE(20))
    assert ordenado == revuelto


def test_gaps_plus_usable_days_add_up_to_the_period():
    """Invariante: nada se pierde ni se cuenta dos veces."""
    utiles = [ENE(3), ENE(4), ENE(11), ENE(28)]
    h = optical_gaps(utiles, ENE(1), ENE(31))
    assert sum(Gap(*t, 0).days for t in h) + len(utiles) == 31


# --- cruce con el radar ----------------------------------------------------
def test_radar_covers_the_gap():
    huecos = cross([ENE(1), ENE(20)], [Pass(ENE(10), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
    assert len(huecos) == 1
    assert huecos[0].radar_passes == 1 and huecos[0].covered


def test_a_radar_pass_outside_the_gap_does_not_count():
    """The pass lands on a day with usable optical, so it fills nothing."""
    huecos = cross([ENE(1), ENE(20)], [Pass(ENE(1), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
    assert huecos[0].radar_passes == 0 and not huecos[0].covered


def test_a_radar_pass_on_the_gap_edges_does_count():
    """El hueco (2..19) incluye sus extremos: dia 2 y dia 19 cuentan."""
    for d in (2, 19):
        h = cross([ENE(1), ENE(20)], [Pass(ENE(d), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
        assert h[0].radar_passes == 1, f"dia {d} deberia caer dentro"
    for d in (1, 20):
        h = cross([ENE(1), ENE(20)], [Pass(ENE(d), "s1a", "asc", "IW", ("VV",))], ENE(1), ENE(20))
        assert h[0].radar_passes == 0, f"dia {d} NO deberia caer dentro"


def test_several_gaps_share_out_the_passes():
    huecos = cross(
        [ENE(5), ENE(15)],
        [Pass(ENE(2), "s1a", "asc", "IW", ()), Pass(ENE(10), "s1a", "asc", "IW", ()),
         Pass(ENE(11), "s1a", "desc", "IW", ()), Pass(ENE(25), "s1a", "asc", "IW", ())],
        ENE(1), ENE(31),
    )
    assert [h.radar_passes for h in huecos] == [1, 2, 1]
    assert all(h.covered for h in huecos)


# --- cadence: the metric that replaced one that only looked like a result --
def test_cadence_counts_both_sets():
    from cielociego.radar import cadence

    c = cadence([ENE(1), ENE(10)], [ENE(5)])
    assert c.optical_days == 2 and c.combined_days == 3


def test_radar_cuts_the_tail_without_moving_the_median():
    """The real finding, and the reason the old one was dropped.

    Optical every 5 days with one long outage; radar every 12. The median
    barely moves -- on clear days optical is already frequent -- but the worst
    stretch collapses. Claiming radar improves the typical cadence would be
    overselling it.
    """
    from datetime import timedelta

    from cielociego.radar import cadence

    base = date(2023, 1, 1)
    optical = [base + timedelta(days=d) for d in list(range(0, 40, 5)) + [130, 135]]
    radar = [base + timedelta(days=d) for d in range(0, 140, 12)]
    c = cadence(optical, radar)
    assert c.worst_optical > 80, "the outage must be there to start with"
    assert c.worst_combined <= 12, "radar must cut it down to its own revisit"
    assert c.median_combined <= c.median_optical


def test_cadence_with_no_radar_changes_nothing():
    from cielociego.radar import cadence

    c = cadence([ENE(1), ENE(10), ENE(20)], [])
    assert c.worst_optical == c.worst_combined
    assert c.median_optical == c.median_combined


def test_cadence_needs_two_dates_to_say_anything():
    import math

    from cielociego.radar import cadence

    c = cadence([ENE(1)], [])
    assert math.isnan(c.median_optical) and c.worst_optical == 0
