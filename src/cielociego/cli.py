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
    sub.add_parser("tests", help="run the project test suite").set_defaults(func=cmd_tests)
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return args.func(args)
