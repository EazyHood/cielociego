"""Sentinel-1 as a filler for the gaps optical leaves.

Claims that a radar acquisition exists on a given date -- not that it says the
same thing an optical one would. Backscatter and reflectance answer different
questions.

Constellation coverage is counted, not assumed: S1B was retired in late 2021 and
S1C launched at the end of 2024.
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from typing import Any

import numpy as np

# S1A_IW_GRDH_1SDV_20231222T230735_20231222T230800_051774_0640E8
_ID = re.compile(
    r"^(?P<platform>S1[A-D])_(?P<modo>\w{2})_(?P<producto>\w{4})_\w+?"
    r"_(?P<start>\d{8}T\d{6})_(?P<fin>\d{8}T\d{6})"
)


@dataclass(frozen=True)
class Pass:
    date: date
    platform: str
    orbit: str          # ascending | descending
    modo: str
    polarizaciones: tuple[str, ...]

    @property
    def iso(self) -> str:
        return self.date.isoformat()


def s1_identity(item: dict[str, Any]) -> tuple[str, str] | None:
    """(platform, start instant) -- physical identity of the acquisition."""
    m = _ID.match(item.get("id", ""))
    if not m:
        return None
    return m.group("platform"), m.group("start")


def to_passes(items: Iterable[dict[str, Any]]) -> list[Pass]:
    """Convierte items STAC en Pasadas unicas, deduplicando por identity fisica."""
    views: dict[tuple[str, str], Pass] = {}
    for it in items:
        ident = s1_identity(it)
        if ident is None:
            continue
        p = it.get("properties", {})
        try:
            f = datetime.fromisoformat(p["datetime"].replace("Z", "+00:00")).date()
        except (KeyError, ValueError):
            continue
        views.setdefault(
            ident,
            Pass(
                date=f,
                platform=p.get("platform", ident[0]),
                orbit=p.get("sat:orbit_state", "?"),
                modo=p.get("sar:instrument_mode", "?"),
                polarizaciones=tuple(p.get("sar:polarizations") or ()),
            ),
        )
    return sorted(views.values(), key=lambda x: x.date)


@dataclass
class Gap:
    """A stretch of days with no usable optical observation of the field."""

    start: date          # first day with no usable view
    end: date            # last day with no usable view
    radar_passes: int    # S1 acquisitions inside the stretch

    @property
    def days(self) -> int:
        return (self.end - self.start).days + 1

    @property
    def covered(self) -> bool:
        return self.radar_passes > 0


def optical_gaps(
    usable_dates: Sequence[date], start: date, end: date
) -> list[tuple[date, date]]:
    """Stretches between consecutive usable observations.

    A gap is the open interval between two usable views: a view on day 1 and
    day 10 leaves a gap of days 2..9, eight days long. The ends of the series
    count too -- a year that opens with 40 days of nothing is information.
    """
    usable = sorted(d for d in set(usable_dates) if start <= d <= end)
    stretches: list[tuple[date, date]] = []
    cursor = start
    for d in usable:
        if d > cursor:
            stretches.append((cursor, d - timedelta(days=1)))
        cursor = d + timedelta(days=1)
    if cursor <= end:
        stretches.append((cursor, end))
    return stretches


def cross(
    usable_dates: Sequence[date],
    passes: Sequence[Pass],
    start: date,
    end: date,
) -> list[Gap]:
    """For each optical gap, how many radar passes fell inside it."""
    radar_dates = sorted(p.date for p in passes)
    out: list[Gap] = []
    for a, b in optical_gaps(usable_dates, start, end):
        n = sum(1 for d in radar_dates if a <= d <= b)
        out.append(Gap(a, b, n))
    return out


@dataclass
class Cadence:
    """How often an observation actually arrives, optical alone and with radar."""

    optical_days: int
    combined_days: int
    median_optical: float
    median_combined: float
    p95_optical: float
    p95_combined: float
    worst_optical: int
    worst_combined: int

    def dict(self) -> dict[str, Any]:
        return asdict(self)


def cadence(optical: Sequence[date], radar: Sequence[date]) -> Cadence:
    """Interval between usable observations, before and after adding radar.

    This replaces a metric that looked like a result and was not. "What share
    of the long gaps contain a radar pass?" comes out at 100 %, but that is
    Sentinel-1's revisit answering, not the fields: consecutive passes are less
    than 15 days apart in 274 of 275 cases, so any 15-day window contains one
    almost by construction. A published orbital specification is not a finding.

    What is not forced is the cadence. On these fields the median is unchanged
    at 5 days -- on clear days optical is already frequent -- while the 95th
    percentile falls from 25 and 40 days to 12, and the worst stretch from 60
    and 90 days to 24. Radar does not improve the typical case. It cuts the tail.

    `radar` should carry one relative orbit only, or the dates are not
    comparable to each other. See DECISIONS.md #7.
    """
    def spacing(days: Sequence[date]) -> tuple[float, float, int]:
        ordered = sorted(set(days))
        if len(ordered) < 2:
            return float("nan"), float("nan"), 0
        d = np.array([(b - a).days for a, b in zip(ordered[:-1], ordered[1:], strict=True)])
        return float(np.median(d)), float(np.percentile(d, 95)), int(d.max())

    both = sorted(set(optical) | set(radar))
    mo, po, wo = spacing(optical)
    mb, pb, wb = spacing(both)
    return Cadence(len(set(optical)), len(both), mo, mb, po, pb, wo, wb)
