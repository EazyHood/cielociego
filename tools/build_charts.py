"""Build the report charts and the summary the HTML builder reads.

Reads the measurement outputs and writes `outputs/grafica_*.svg` plus
`outputs/summary.json`. Computes nothing that the measurement did not already
establish: it only reshapes.
"""
import json
import os
import sys
from collections import Counter
from datetime import date

sys.path.insert(0, "src")
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import numpy as np  # noqa: E402

from cielociego import charts  # noqa: E402

START, END = date(2019, 1, 1), date(2026, 8, 25)
DAYS = (END - START).days + 1
FIELDS = ("field_fundacion", "field_corridor")

P = {}
for key in FIELDS:
    scl = json.load(open(f"outputs/{key}_scl.json", encoding="utf-8"))
    rad = json.load(open(f"outputs/{key}_radar.json", encoding="utf-8"))
    raw = json.load(open(f"outputs/{key}_s2_scenes.json", encoding="utf-8"))
    scenes = raw["scenes"] if isinstance(raw, dict) else raw

    views = scl["views"]
    blind = np.array([v["blind_strict"] for v in views])
    tile = np.array([(v["tile_cloud"] or 0) / 100 for v in views])
    ok_field, ok_tile = blind <= 0.10, tile <= 0.10

    gaps = rad["gaps"]
    blind_days = sum(g["days"] for g in gaps)
    long_gaps = [g for g in gaps if g["days"] >= 15]

    P[key] = dict(
        name=scl["field"], area=scl["area_ha"],
        measured=scl["measured"], failed=scl["failed"], raw_scenes=len(scenes),
        blind=blind, tile=tile,
        usable=int(ok_field.sum()), usable_by_tile=int(ok_tile.sum()),
        false_neg=int((ok_field & ~ok_tile).sum()),
        false_pos=int((~ok_field & ok_tile).sum()),
        corr=float(np.corrcoef(blind, tile)[0, 1]),
        extremes_field=float(((blind < 0.01) | (blind > 0.95)).mean()),
        extremes_tile=float(((tile < 0.01) | (tile > 0.95)).mean()),
        clear=float((blind < 0.01).mean()), covered=float((blind > 0.95).mean()),
        gaps=gaps, blind_days=blind_days, pct_blind=100 * blind_days / DAYS,
        worst=max(gaps, key=lambda g: g["days"]),
        long_gaps=len(long_gaps),
        long_covered=sum(1 for g in long_gaps if g["radar_passes"] > 0),
        s1=[p["date"] for p in rad["s1_passes"]],
        usable_dates=[v["date"] for v in views if v["blind_strict"] <= 0.10],
        s2_year=Counter(v["date"][:4] for v in views),
        s1_year=Counter(p["date"][:4] for p in rad["s1_passes"]),
    )

F, C = P["field_fundacion"], P["field_corridor"]
SAR = {k: json.load(open(f"outputs/{k}_sar.json", encoding="utf-8")) for k in FIELDS}


def winning_model(key: str):
    """The shape that wins by BIC, so the chart draws it instead of a line."""
    return (SAR[key].get("analysis", {}).get("shapes") or [None])[0]


def slope(records, platform=None) -> float:
    """dB per year over those records, optionally within one platform."""
    rows = sorted(records, key=lambda r: r["date"])
    if platform:
        rows = [r for r in rows if r["platform"].lower() == platform]
    t = np.array([date.fromisoformat(r["date"]).toordinal() for r in rows], dtype=float)
    v = np.array([r["vv_db"] for r in rows])
    return float(np.polyfit(t, v, 1)[0] * 365), len(rows)


def platform_control() -> dict:
    """Trend within each platform: the control against a calibration artefact."""
    out = {}
    corridor = SAR["field_corridor"]["measured"]
    out["All platforms"] = slope(corridor)[0]
    for platform, label in (("sentinel-1a", "Sentinel-1A only"),
                            ("sentinel-1b", "Sentinel-1B only")):
        s, n = slope(corridor, platform)
        if n > 20:
            out[f"{label}  (n={n})"] = s
    s, n = slope(SAR["field_fundacion"]["measured"], "sentinel-1a")
    if n > 20:
        out[f"Neighbouring field, S1A  (n={n})"] = s
    return out


G = {
    "dist": charts.distribution(F["blind"], F["tile"] * 100),
    "cal_f": charts.calendar_strip(F["usable_dates"], F["gaps"], F["s1"], START, END),
    "cal_c": charts.calendar_strip(C["usable_dates"], C["gaps"], C["s1"], START, END),
    "dur": charts.gaps_by_length(F["gaps"] + C["gaps"]),
    "anual": charts.passes_per_year(dict(F["s2_year"]), dict(F["s1_year"])),
    "sar_c": charts.radar_series(SAR["field_corridor"]["measured"], C["gaps"], START, END,
                                 model=winning_model("field_corridor")),
    "sar_f": charts.radar_series(SAR["field_fundacion"]["measured"], F["gaps"], START, END,
                                 model=winning_model("field_fundacion")),
    "ctrl": charts.platform_control(platform_control()),
}

SKIP = ("gaps", "s1", "usable_dates")
json.dump(
    {k: {kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv)
         for kk, vv in v.items() if kk not in SKIP}
     for k, v in P.items()},
    open("outputs/summary.json", "w", encoding="utf-8"),
    ensure_ascii=False, indent=1, default=str,
)
for k, svg in G.items():
    open(f"outputs/grafica_{k}.svg", "w", encoding="utf-8").write(svg)

print("charts: " + ", ".join(f"{k}({len(v) // 1024}kb)" for k, v in G.items()))
for label, d in (("FUNDACION", F), ("CORRIDOR", C)):
    print(f"\n{label}  usable {d['usable']}/{d['measured']}  "
          f"tile would say {d['usable_by_tile']}  "
          f"false-neg {d['false_neg']}  false-pos {d['false_pos']}")
    print(f"           blind {d['pct_blind']:.0f}% of days | worst gap "
          f"{d['worst']['days']}d ({d['worst']['start']}) with "
          f"{d['worst']['radar_passes']} radar passes")
    print(f"           gaps >=15d: {d['long_covered']}/{d['long_gaps']} with radar")
