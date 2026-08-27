"""Command line: reproduces the whole measurement end to end.

    python -m cielociego measure              # catalogue, SCL, gaps, radar series
    python -m cielociego measure --field my_farm.geojson
    python -m cielociego catalog              # catalogue only, deduplicated
    python -m cielociego tests

No hidden state: each step writes its JSON into `outputs/` and the next reads it
from there. Stop and resume anywhere, and check any figure by hand.

Fields are measured in isolation -- one failure does not bring down the rest,
and the exit code says the measurement is incomplete.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from .analysis import change_shape, hac_trend, leave_one_year_out
from .catalog import S1_GRD, S2_L2A, by_year, search
from .dedup import deduplicate
from .fields import Field, load_field
from .net import session as _sesion
from .provenance import record
from .radar import cross, to_passes
from .sar import measure_backscatter, orbit_breakdown, pick_orbit, search_rtc
from .sweep import _progress, sweep

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
OUTPUTS = ROOT / "outputs"
DEFAULT_START = "2019-01-01"
USABLE_THRESHOLD = 0.10
# One relative orbit only: mixing them invents steps the crop never had.
# Which one is picked per field -- orbits depend on where the field is.


def _log(msg: str = "") -> None:
    print(msg, flush=True)


def _load_all(rutas: list[str] | None) -> list[tuple[str, Field]]:
    if rutas:
        return [(Path(r).stem, load_field(r)) for r in rutas]
    encontrados = sorted(DATA.glob("*.geojson"))
    if not encontrados:
        sys.exit(f"no hay ningun GeoJSON en {DATA}. Pasa uno con --field path.geojson")
    return [(p.stem, load_field(p)) for p in encontrados]


def step_catalog(clave: str, field: Field, start: str, end: str) -> list[dict]:
    """Fetch the optical catalogue and deduplicate it by processing baseline."""
    b = search(S2_L2A, field.bbox, start, end)
    vivos, muertos = deduplicate(b.items)
    pct = 100 * len(muertos) / len(b) if len(b) else 0
    _log(f"  catalog   {b.declared} declaradas = {len(b)} bajadas  (control OK)")
    _log(f"  dedup      {len(vivos)} scenes reales, {len(muertos)} copias fuera ({pct:.1f} %)")

    ejemplo = by_year(vivos)
    if ejemplo:
        ano = max(ejemplo)
        _log(f"  revisita   {ano}: {len(ejemplo[ano])} pasadas")

    scenes = [
        {
            "id": x["id"],
            "date": x["properties"]["datetime"],
            "cc": x["properties"].get("eo:cloud_cover"),
            "uri": x["properties"].get("s2:product_uri"),
            "scl": x["assets"].get("scl", {}).get("href"),
        }
        for x in vivos
    ]
    target = OUTPUTS / f"{clave}_s2_scenes.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(
            {"provenance": record(start=start, end=end, collection=S2_L2A), "scenes": scenes},
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    return scenes


def step_scl(clave: str, field: Field, scenes: list[dict], workers: int) -> dict:
    """Measure the blind fraction of the field on every acquisition."""
    t0 = time.time()
    r = sweep(field, scenes, workers=workers, avisa=_progress)
    r.save(OUTPUTS / f"{clave}_scl.json",
             provenance=record(usable_threshold=USABLE_THRESHOLD, workers=workers))
    rec = f", {r.recovered} recovered en 2a pasada" if r.recovered else ""
    _log(f"  SCL        {len(r.views)} medidas, {len(r.failed)} failed{rec}, "
         f"{time.time() - t0:.0f}s")
    for v in r.failed:
        _log(f"    ! {v.date}  {v.error}")

    utiles = [v for v in r.views if v.blind_strict <= USABLE_THRESHOLD]
    pct = 100 * len(utiles) / len(r.views) if r.views else 0
    _log(f"  utiles     {len(utiles)} de {len(r.views)} ({pct:.0f} %) "
         f"con <= {USABLE_THRESHOLD:.0%} del field tapado")
    return json.loads((OUTPUTS / f"{clave}_scl.json").read_text(encoding="utf-8"))


def step_radar(clave: str, field: Field, scl: dict, start: str, end: str) -> None:
    """Cross the optical gaps with the radar passes."""
    b = search(S1_GRD, field.bbox, start, end)
    pasadas = to_passes(b.items)
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    utiles = [
        date.fromisoformat(v["date"])
        for v in scl["views"]
        if v["blind_strict"] <= USABLE_THRESHOLD
    ]
    huecos = cross(utiles, pasadas, d0, d1)

    days = (d1 - d0).days + 1
    ciegos = sum(h.days for h in huecos)
    largos = [h for h in huecos if h.days >= 15]
    cubiertos = [h for h in largos if h.covered]
    worst = max(huecos, key=lambda h: h.days) if huecos else None

    (OUTPUTS / f"{clave}_radar.json").write_text(
        json.dumps(
            {
                "field": field.name,
                "provenance": record(start=start, end=end, usable_threshold=USABLE_THRESHOLD),
                "pasadas_s1": [
                    {"date": p.iso, "platform": p.platform, "orbit": p.orbit}
                    for p in pasadas
                ],
                "huecos": [
                    {"start": h.start.isoformat(), "end": h.end.isoformat(),
                     "days": h.days, "radar": h.radar_passes}
                    for h in huecos
                ],
            },
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    _log(f"  radar      {len(pasadas)} pasadas de Sentinel-1")
    _log(f"  ciego      {ciegos} de {days} days ({100 * ciegos / days:.0f} %) "
         f"sin observacion optica util")
    if worst:
        _log(f"  worst hueco {worst.days} days ({worst.start} -> {worst.end}) "
             f"con {worst.radar_passes} pasadas de radar")
    if largos:
        _log(f"  huecos >= 15 d: {len(cubiertos)}/{len(largos)} tienen radar dentro "
             f"({100 * len(cubiertos) / len(largos):.0f} %)")


def step_sar(clave: str, field: Field, start: str, end: str, workers: int,
             orbita_pedida: int | None = None) -> None:
    """Extract the backscatter series over the field, from one orbit.

    One orbit on purpose: backscatter depends on incidence angle, so mixing
    them produces steps that do not come from the ground. It costs
    observations and buys comparability. Which orbit is picked per field --
    see `sar.pick_orbit`.
    """
    ses = _sesion()
    todos = search_rtc(field, start, end, session=ses)
    if not todos:
        _log("  radar S1  sin escenas RTC sobre el field")
        return

    reparto = orbit_breakdown(todos)
    orbit = orbita_pedida or pick_orbit(todos)
    items = [x for x in todos if x["properties"].get("sat:relative_orbit") == orbit]
    _log(f"  orbitas    {reparto}  ->  se usa la {orbit} ({len(items)} escenas)")
    if not items:
        _log(f"  radar S1  la orbit {orbit} no cubre este field")
        return

    t0 = time.time()
    medidas: list = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = [pool.submit(measure_backscatter, it, field, session=ses) for it in items]
        for n_, fut in enumerate(as_completed(futuros), 1):
            medidas.append(fut.result())
            if n_ % 25 == 0 or n_ == len(futuros):
                _progress(n_, len(futuros))

    ok = sorted([m for m in medidas if m.error is None], key=lambda m: m.date)
    mal = [m for m in medidas if m.error]
    analysis: dict[str, object] = {}
    if len(ok) >= 20:
        dates = [m.date for m in ok]
        vv = [m.vv_db for m in ok]
        t = hac_trend(dates, vv)
        formas = change_shape(dates, vv)
        analysis = {
            "tendencia_vv": t.dict(),
            "formas": [f.dict() for f in formas],
            "robustez": leave_one_year_out(dates, vv),
        }

    (OUTPUTS / f"{clave}_sar.json").write_text(
        json.dumps(
            {"field": field.name,
             "provenance": record(start=start, end=end, orbit=orbit),
             "orbit": orbit, "orbit_breakdown": reparto, "analysis": analysis,
             "medidas": [m.dict() for m in ok], "errores": [m.dict() for m in mal]},
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    _log(f"  radar S1  {len(ok)} medidas de gamma0, {len(mal)} failed, {time.time() - t0:.0f}s")
    for m in mal[:3]:
        _log(f"    ! {m.date}  {m.error}")

    if analysis:
        import numpy as np

        t = hac_trend([m.date for m in ok], [m.vv_db for m in ok])
        serie = np.array([m.vv_db for m in ok])
        _log(f"  VV medio  {serie.mean():.2f} dB (sd {serie.std():.2f})")
        _log(f"  tendencia {t.slope:+.3f} dB/ano  IC95 [{t.ic95[0]:+.3f}, {t.ic95[1]:+.3f}] "
             f"(HAC; n={t.n}, n_effective={t.n_effective:.0f})")
        best, segundo = formas[0], formas[1]
        _log(f'  forma     gana "{best.name}" por dBIC {segundo.bic - best.bic:.0f} '
             f'sobre "{segundo.name}"')
        antes, despues = best.level_before, best.level_after
        if antes is not None and despues is not None:
            tramo = f"{best.cut}" + (f" -> {best.cut_end}" if best.cut_end else "")
            _log(f"            nivel {antes:+.2f} -> {despues:+.2f} dB "
                 f"({despues - antes:+.2f})  en {tramo}")

        # Control: the trend within a single platform. If it vanishes there, it
        # was a calibration change dressed up as a change on the ground.
        solo = [m for m in ok if m.platform.lower() == "sentinel-1a"]
        if len(solo) > 20:
            ts = hac_trend([m.date for m in solo], [m.vv_db for m in solo])
            _log(f"  control   solo Sentinel-1A (n={len(solo)}): {ts.slope:+.3f} dB/ano "
                 f"IC95 [{ts.ic95[0]:+.3f}, {ts.ic95[1]:+.3f}]")


def cmd_measure(args) -> int:
    """Measure each field separately, carrying on if one fails.

    POR QUE VA AISLADO
    ------------------
    Medido el 2026-08-26: un cut de red a mitad del catalog tumbaba el
    proceso entero con un `ConnectionError` crudo, y se perdia tambien el
    trabajo de los fields que ya habian salido bien. Ahora el que falla se
    declara y se pasa al siguiente, y el **codigo de out es 1** para que
    nadie lea `outputs/` como si estuviera completa.
    """
    fields = _load_all(args.field)
    fallados: list[tuple[str, str]] = []

    for clave, field in fields:
        _log(f"\n=== {field.name}  ({field.area_ha} ha)")
        try:
            scenes = step_catalog(clave, field, args.start, args.end)
            scl = step_scl(clave, field, scenes, args.workers)
            step_radar(clave, field, scl, args.start, args.end)
            if not args.no_radar:
                step_sar(clave, field, args.start, args.end, args.workers, args.orbit)
        except KeyboardInterrupt:
            raise
        except Exception as exc:
            fallados.append((field.name, f"{type(exc).__name__}: {exc}"[:160]))
            _log(f"  !! {field.name} queda SIN MEDIR ({type(exc).__name__})")
            _log(f"     {str(exc)[:150]}")

    if fallados:
        _log(f"\nMEDICION INCOMPLETA: {len(fallados)} de {len(fields)} fields sin medir")
        for name, motivo in fallados:
            _log(f"  - {name}: {motivo}")
        _log("  Si el motivo es de red, relanzalo: lo que ya salio bien esta escrito.")
        return 1

    _log(f"\nlisto. Resultados en {OUTPUTS}")
    return 0


def cmd_catalog(args) -> int:
    for clave, field in _load_all(args.field):
        _log(f"\n=== {field.name}")
        step_catalog(clave, field, args.start, args.end)
    return 0


def cmd_cohort(args) -> int:
    """Run the same protocol over many public parcels instead of one field.

    The catalogue pass always runs: it is cheap and it is what answers the
    duplicate question over a whole archive. The optical pass is opt-in through
    `--cap`, because reading the classification band for every acquisition of
    every parcel is three orders of magnitude more expensive.
    """
    from .cohort import (
        CohortResult,
        catalog_pass,
        confusion,
        confusion_by_area,
        load_cohort,
        optical_pass,
        sensitivity,
    )

    parcels = load_cohort(args.cohort, source=args.source)
    if args.limit:
        parcels = parcels[: args.limit]
    if not parcels:
        sys.exit(f"{args.cohort}: no usable parcel in the file")

    name = args.name or Path(args.cohort).stem
    areas = sorted(p.area_ha for p in parcels)
    _log(f"\n=== cohort {name}: {len(parcels)} parcels, "
         f"{args.start} to {args.end}")
    _log(f"  area       median {areas[len(areas) // 2]:.1f} ha "
         f"(min {areas[0]:.2f}, max {areas[-1]:.1f})")
    countries = sorted({p.country for p in parcels})
    _log(f"  countries  {', '.join(countries)}")

    t0 = time.time()
    rows = catalog_pass(parcels, args.start, args.end, workers=args.workers, notify=_progress)
    ok = [r for r in rows if not r.error]
    items = sum(r.items for r in ok)
    dups = sum(r.duplicates for r in ok)
    _log(f"  catalogue  {items} items over {len(ok)} parcels, "
         f"{dups} reprocessing copies ({100 * dups / items if items else 0:.1f} %), "
         f"{len(rows) - len(ok)} parcels unreachable, {time.time() - t0:.0f}s")
    gaps = [r.cloud_gap_max for r in ok if r.cloud_gap_max is not None]
    if gaps:
        ratios = [r.cloud_gap_ratio_max for r in ok if r.cloud_gap_ratio_max]
        _log(f"  disagreement between baselines: max {max(gaps):.2f} points"
             + (f", up to {max(ratios):.1f}x" if ratios else ""))

    result = CohortResult(
        args.start, args.end, catalog=rows,
        provenance=record(start=args.start, end=args.end, collection=S2_L2A),
    )

    if args.cap:
        _log(f"\n  optical pass, up to {args.cap} acquisitions per parcel")
        t0 = time.time()
        result.observations = optical_pass(
            parcels, args.start, args.end,
            workers=args.workers, cap_per_parcel=args.cap, notify=_progress,
        )
        read = [o for o in result.observations if not o.error]
        _log(f"  measured   {len(read)} acquisition-parcel pairs, "
             f"{len(result.observations) - len(read)} failed, {time.time() - t0:.0f}s")

        m = confusion(result.observations)
        _log(f"\n  filter tile cloud <= {m.tile_threshold:.0%}, "
             f"parcel usable at blind <= {m.blind_limit:.0%}")
        _log(f"    kept and useful   {m.kept_useful}")
        _log(f"    kept but blind    {m.kept_useless}   (false positive)")
        _log(f"    dropped yet clear {m.dropped_useful}   (false negative)")
        _log(f"    dropped and blind {m.dropped_useless}")
        _log(f"    asymmetry         {m.asymmetry:.1f} false negatives per false positive")
        _log(f"    recall            {m.recall:.3f}")

        _log("\n  by parcel size:")
        for label, c in confusion_by_area(result.observations):
            if c.total:
                _log(f"    {label:>12}  n={c.total:>6}  recall {c.recall:.3f}  "
                     f"FN {c.dropped_useful:>5}  FP {c.kept_useless:>4}  "
                     f"asymmetry {c.asymmetry:>6.1f}")

        _log("\n  sensitivity to the thresholds:")
        for c in sensitivity(result.observations):
            _log(f"    tile<={c.tile_threshold:.0%} blind<={c.blind_limit:.0%}  "
                 f"FN {c.dropped_useful:>5}  FP {c.kept_useless:>4}  "
                 f"recall {c.recall:.3f}")

    stem = OUTPUTS / f"cohort_{name}"
    result.save_json(f"{stem}.json")
    result.save_catalog_csv(f"{stem}_catalog.csv")
    if result.observations:
        result.save_csv(f"{stem}_observations.csv")
    _log(f"\n  written to {stem}*.csv / .json")
    return 0


def cmd_tests(_args) -> int:
    import subprocess

    return subprocess.call(
        [sys.executable, "-m", "pytest", str(ROOT / "tests"), "-q"],
        cwd=ROOT,
        env={**__import__("os").environ, "PYTHONPATH": str(ROOT / "src")},
    )


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cielociego",
        description="How many days the optical satellite cannot see a field, "
                    "and whether radar covers the gap.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    def shared(sp):
        sp.add_argument("--field", action="append", metavar="FILE.geojson",
                        help="field to measure (repeatable); defaults to those in data/")
        sp.add_argument("--start", default=DEFAULT_START, metavar="YYYY-MM-DD")
        sp.add_argument("--end", default=date.today().isoformat(), metavar="YYYY-MM-DD")
        return sp

    m = shared(sub.add_parser("measure", help="full measurement: catalogue, SCL and radar"))
    m.add_argument("--workers", type=int, default=12,
                   help="concurrent reads (default 12)")
    m.add_argument("--no-radar", action="store_true",
                   help="skip the backscatter series, which is the slow step")
    m.add_argument("--orbit", type=int, default=None, metavar="N",
                   help="force a relative orbit; by default the best-covered one is picked")
    m.set_defaults(func=cmd_measure)

    shared(sub.add_parser("catalog", help="optical catalogue only, deduplicated")).set_defaults(
        func=cmd_catalog
    )
    c = sub.add_parser(
        "cohort",
        help="the same protocol over many public parcels, to turn a case into a rule",
    )
    c.add_argument("--cohort", required=True, metavar="FILE.geojson",
                   help="many-feature GeoJSON of parcel boundaries")
    c.add_argument("--start", default="2023-01-01", metavar="YYYY-MM-DD")
    c.add_argument("--end", default=date.today().isoformat(), metavar="YYYY-MM-DD")
    c.add_argument("--cap", type=int, default=None, metavar="N",
                   help="also read the classification band, up to N acquisitions per parcel; "
                        "without it only the catalogue is queried")
    c.add_argument("--limit", type=int, default=None, metavar="N",
                   help="first N parcels only, for a dry run")
    c.add_argument("--workers", type=int, default=10)
    c.add_argument("--restart", action="store_true",
                   help="throw away the partial rows on disk and measure from scratch")
    c.add_argument("--source", default=None, help="label for the boundary dataset")
    c.add_argument("--name", default=None, help="output name; defaults to the file stem")
    c.set_defaults(func=cmd_cohort)

    sub.add_parser("tests", help="run the project test suite").set_defaults(func=cmd_tests)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
