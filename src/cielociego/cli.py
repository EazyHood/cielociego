"""Linea de comandos: reproduce la medicion entera de principio a fin.

    python -m cielociego medir                  # todo: catalogo, SCL, radar, informe
    python -m cielociego medir --predio datos/mi_finca.geojson
    python -m cielociego catalogo               # solo el catalogo, deduplicado
    python -m cielociego pruebas                # el control: 67 pruebas

No hay estado escondido: cada paso escribe su JSON en `salidas/` y el
siguiente lo lee de ahi. Se puede parar y retomar en cualquier punto, y
cualquiera puede abrir el JSON intermedio y comprobar la cifra a mano.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date
from pathlib import Path

from .barrido import _barra, barre
from .catalogo import S1_GRD, S2_L2A, busca, por_ano
from .dedup import deduplica
from .predios import Predio, carga_predio
from .radar import a_pasadas, cruza
from .red import sesion as _sesion
from .sar import busca_rtc, elige_orbita, mide_retro, reparto_orbitas

RAIZ = Path(__file__).resolve().parents[2]
DATOS = RAIZ / "datos"
SALIDAS = RAIZ / "salidas"
DESDE_POR_DEFECTO = "2019-01-01"
UMBRAL_UTIL = 0.10
# Una sola orbita relativa: mezclarlas inventa saltos que no son del cultivo.
# CUAL sea se elige por predio -- las orbitas dependen de donde este.


def _log(msg: str = "") -> None:
    print(msg, flush=True)


def _predios(rutas: list[str] | None) -> list[tuple[str, Predio]]:
    if rutas:
        return [(Path(r).stem, carga_predio(r)) for r in rutas]
    encontrados = sorted(DATOS.glob("predio_*.geojson"))
    if not encontrados:
        sys.exit(f"no hay predios en {DATOS}. Pasa uno con --predio ruta.geojson")
    return [(p.stem, carga_predio(p)) for p in encontrados]


def paso_catalogo(clave: str, predio: Predio, desde: str, hasta: str) -> list[dict]:
    """Baja el catalogo optico y lo deduplica por linea de procesado."""
    b = busca(S2_L2A, predio.bbox, desde, hasta)
    vivos, muertos = deduplica(b.items)
    pct = 100 * len(muertos) / len(b) if len(b) else 0
    _log(f"  catalogo   {b.declarados} declaradas = {len(b)} bajadas  (control OK)")
    _log(f"  dedup      {len(vivos)} tomas reales, {len(muertos)} copias fuera ({pct:.1f} %)")

    ejemplo = por_ano(vivos)
    if ejemplo:
        ano = max(ejemplo)
        _log(f"  revisita   {ano}: {len(ejemplo[ano])} pasadas")

    tomas = [
        {
            "id": x["id"],
            "fecha": x["properties"]["datetime"],
            "cc": x["properties"].get("eo:cloud_cover"),
            "uri": x["properties"].get("s2:product_uri"),
            "scl": x["assets"].get("scl", {}).get("href"),
        }
        for x in vivos
    ]
    destino = SALIDAS / f"{clave}_s2_tomas.json"
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.write_text(json.dumps(tomas, ensure_ascii=False, indent=1), encoding="utf-8")
    return tomas


def paso_scl(clave: str, predio: Predio, tomas: list[dict], hilos: int) -> dict:
    """Mide la fraccion ciega del predio en cada toma."""
    t0 = time.time()
    r = barre(predio, tomas, hilos=hilos, avisa=_barra)
    r.guarda(SALIDAS / f"{clave}_scl.json")
    _log(f"  SCL        {len(r.vistas)} medidas, {len(r.fallidas)} fallidas, "
         f"{time.time() - t0:.0f}s")
    for v in r.fallidas:
        _log(f"    ! {v.fecha}  {v.error}")

    utiles = [v for v in r.vistas if v.ciego_estricto <= UMBRAL_UTIL]
    pct = 100 * len(utiles) / len(r.vistas) if r.vistas else 0
    _log(f"  utiles     {len(utiles)} de {len(r.vistas)} ({pct:.0f} %) "
         f"con <= {UMBRAL_UTIL:.0%} del predio tapado")
    return json.loads((SALIDAS / f"{clave}_scl.json").read_text(encoding="utf-8"))


def paso_radar(clave: str, predio: Predio, scl: dict, desde: str, hasta: str) -> None:
    """Cruza los huecos del optico con las pasadas de radar."""
    b = busca(S1_GRD, predio.bbox, desde, hasta)
    pasadas = a_pasadas(b.items)
    d0, d1 = date.fromisoformat(desde), date.fromisoformat(hasta)
    utiles = [
        date.fromisoformat(v["fecha"])
        for v in scl["vistas"]
        if v["ciego_estricto"] <= UMBRAL_UTIL
    ]
    huecos = cruza(utiles, pasadas, d0, d1)

    dias = (d1 - d0).days + 1
    ciegos = sum(h.dias for h in huecos)
    largos = [h for h in huecos if h.dias >= 15]
    cubiertos = [h for h in largos if h.cubierto]
    peor = max(huecos, key=lambda h: h.dias) if huecos else None

    (SALIDAS / f"{clave}_radar.json").write_text(
        json.dumps(
            {
                "predio": predio.nombre,
                "pasadas_s1": [
                    {"fecha": p.iso, "plataforma": p.plataforma, "orbita": p.orbita}
                    for p in pasadas
                ],
                "huecos": [
                    {"inicio": h.inicio.isoformat(), "fin": h.fin.isoformat(),
                     "dias": h.dias, "radar": h.pasadas_radar}
                    for h in huecos
                ],
            },
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    _log(f"  radar      {len(pasadas)} pasadas de Sentinel-1")
    _log(f"  ciego      {ciegos} de {dias} dias ({100 * ciegos / dias:.0f} %) "
         f"sin observacion optica util")
    if peor:
        _log(f"  peor hueco {peor.dias} dias ({peor.inicio} -> {peor.fin}) "
             f"con {peor.pasadas_radar} pasadas de radar")
    if largos:
        _log(f"  huecos >= 15 d: {len(cubiertos)}/{len(largos)} tienen radar dentro "
             f"({100 * len(cubiertos) / len(largos):.0f} %)")


def paso_sar(clave: str, predio: Predio, desde: str, hasta: str, hilos: int,
             orbita_pedida: int | None = None) -> None:
    """Extrae la serie de retrodispersion sobre el predio, en UNA orbita.

    Se limita a UNA orbita a proposito: la retrodispersion depende del angulo
    de incidencia, asi que mezclar orbitas produce escalones que no vienen del
    suelo. Cuesta observaciones y compra comparabilidad.

    CUAL orbita se elige por predio, no se fija en el codigo: las orbitas
    relativas dependen de la posicion. Ver `sar.elige_orbita`.
    """
    ses = _sesion()
    todos = busca_rtc(predio, desde, hasta, sesion=ses)
    if not todos:
        _log("  radar S1  sin escenas RTC sobre el predio")
        return

    reparto = reparto_orbitas(todos)
    orbita = orbita_pedida or elige_orbita(todos)
    items = [x for x in todos if x["properties"].get("sat:relative_orbit") == orbita]
    _log(f"  orbitas    {reparto}  ->  se usa la {orbita} ({len(items)} escenas)")
    if not items:
        _log(f"  radar S1  la orbita {orbita} no cubre este predio")
        return

    t0 = time.time()
    medidas: list = []
    with ThreadPoolExecutor(max_workers=hilos) as pool:
        futuros = [pool.submit(mide_retro, it, predio, sesion=ses) for it in items]
        for n_, fut in enumerate(as_completed(futuros), 1):
            medidas.append(fut.result())
            if n_ % 25 == 0 or n_ == len(futuros):
                _barra(n_, len(futuros))

    ok = sorted([m for m in medidas if m.error is None], key=lambda m: m.fecha)
    mal = [m for m in medidas if m.error]
    (SALIDAS / f"{clave}_sar.json").write_text(
        json.dumps(
            {"predio": predio.nombre, "orbita": orbita, "reparto_orbitas": reparto,
             "medidas": [m.dict() for m in ok], "errores": [m.dict() for m in mal]},
            ensure_ascii=False, indent=1,
        ),
        encoding="utf-8",
    )
    _log(f"  radar S1  {len(ok)} medidas de gamma0, {len(mal)} fallidas, {time.time() - t0:.0f}s")
    for m in mal[:3]:
        _log(f"    ! {m.fecha}  {m.error}")

    if len(ok) > 2:
        import numpy as np

        f = np.array([date.fromisoformat(m.fecha).toordinal() for m in ok], dtype=float)
        vv = np.array([m.vv_db for m in ok])
        pendiente = float(np.polyfit(f, vv, 1)[0] * 365)
        _log(f"  VV medio  {vv.mean():.2f} dB (sd {vv.std():.2f}) | "
             f"tendencia {pendiente:+.3f} dB/ano")

        # Control: la tendencia DENTRO de un solo satelite. Si desaparece ahi,
        # era un cambio de calibracion disfrazado de cambio en el suelo.
        solo = [m for m in ok if m.plataforma.lower() == "sentinel-1a"]
        if len(solo) > 20:
            fa = np.array([date.fromisoformat(m.fecha).toordinal() for m in solo], dtype=float)
            va = np.array([m.vv_db for m in solo])
            _log(f"  control   solo Sentinel-1A (n={len(solo)}): "
                 f"{float(np.polyfit(fa, va, 1)[0] * 365):+.3f} dB/ano")


def cmd_medir(args) -> int:
    for clave, predio in _predios(args.predio):
        _log(f"\n=== {predio.nombre}  ({predio.area_ha} ha)")
        tomas = paso_catalogo(clave, predio, args.desde, args.hasta)
        scl = paso_scl(clave, predio, tomas, args.hilos)
        paso_radar(clave, predio, scl, args.desde, args.hasta)
        if not args.sin_radar:
            paso_sar(clave, predio, args.desde, args.hasta, args.hilos, args.orbita)
    _log(f"\nlisto. Resultados en {SALIDAS}")
    return 0


def cmd_catalogo(args) -> int:
    for clave, predio in _predios(args.predio):
        _log(f"\n=== {predio.nombre}")
        paso_catalogo(clave, predio, args.desde, args.hasta)
    return 0


def cmd_pruebas(_args) -> int:
    import subprocess

    return subprocess.call(
        [sys.executable, "-m", "pytest", str(RAIZ / "tests"), "-q"],
        cwd=RAIZ,
        env={**__import__("os").environ, "PYTHONPATH": str(RAIZ / "src")},
    )


def construye_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="cielociego",
        description="Cuanto tiempo el satelite optico NO puede ver un predio, "
                    "y si el radar cubre el hueco.",
    )
    sub = p.add_subparsers(dest="orden", required=True)

    def comunes(sp):
        sp.add_argument("--predio", action="append", metavar="RUTA.geojson",
                        help="predio a medir (repetible); por defecto, los de datos/")
        sp.add_argument("--desde", default=DESDE_POR_DEFECTO, metavar="AAAA-MM-DD")
        sp.add_argument("--hasta", default=date.today().isoformat(), metavar="AAAA-MM-DD")
        return sp

    m = comunes(sub.add_parser("medir", help="medicion completa: catalogo, SCL y radar"))
    m.add_argument("--hilos", type=int, default=12,
                   help="lecturas simultaneas (por defecto 12)")
    m.add_argument("--sin-radar", action="store_true",
                   help="salta la serie de retrodispersion (el paso mas lento)")
    m.add_argument("--orbita", type=int, default=None, metavar="N",
                   help="fuerza una orbita relativa; por defecto se elige la mas poblada")
    m.set_defaults(func=cmd_medir)

    comunes(sub.add_parser("catalogo", help="solo el catalogo optico, deduplicado")).set_defaults(
        func=cmd_catalogo
    )
    sub.add_parser("pruebas", help="corre las pruebas del proyecto").set_defaults(func=cmd_pruebas)
    return p


def main(argv: list[str] | None = None) -> int:
    args = construye_parser().parse_args(argv)
    return args.func(args)
