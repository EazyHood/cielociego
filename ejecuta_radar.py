"""Baja el catalogo Sentinel-1 y lo cruza con los huecos del optico."""
import json, sys
from datetime import date
sys.path.insert(0, "src")
from cielociego.catalogo import busca, S1_GRD
from cielociego.predios import carga_predio
from cielociego.radar import a_pasadas, cruza

DESDE, HASTA = date(2019, 1, 1), date(2026, 8, 25)

for nom in ("predio_fundacion", "predio_corredor"):
    p = carga_predio(f"datos/{nom}.geojson")
    b = busca(S1_GRD, p.bbox, DESDE.isoformat(), HASTA.isoformat())
    pas = a_pasadas(b.items)
    print(f"\n== {p.nombre}")
    print(f"   S1: servidor {b.declarados}, bajados {len(b)} -> {len(pas)} pasadas unicas")

    scl = json.load(open(f"salidas/{nom}_scl.json", encoding="utf-8"))
    utiles = [date.fromisoformat(v["fecha"]) for v in scl["vistas"] if v["ciego_estricto"] <= 0.10]
    huecos = cruza(utiles, pas, DESDE, HASTA)

    dias_tot = (HASTA - DESDE).days + 1
    dias_ciegos = sum(h.dias for h in huecos)
    cubiertos = [h for h in huecos if h.cubierto]
    json.dump(
        {"predio": p.nombre,
         "pasadas_s1": [{"fecha": x.iso, "plataforma": x.plataforma, "orbita": x.orbita} for x in pas],
         "huecos": [{"inicio": h.inicio.isoformat(), "fin": h.fin.isoformat(),
                     "dias": h.dias, "radar": h.pasadas_radar} for h in huecos]},
        open(f"salidas/{nom}_radar.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    print(f"   periodo {dias_tot} dias | dias con vista optica util {len(set(utiles))} | dias ciegos {dias_ciegos} ({100*dias_ciegos/dias_tot:.0f}%)")
    print(f"   huecos: {len(huecos)} | mediana {sorted(h.dias for h in huecos)[len(huecos)//2]} d | el mas largo {max(h.dias for h in huecos)} d")
    print(f"   CON pasada de radar dentro: {len(cubiertos)}/{len(huecos)} ({100*len(cubiertos)/len(huecos):.1f}%)")
    largos = [h for h in huecos if h.dias >= 15]
    if largos:
        cl = [h for h in largos if h.cubierto]
        print(f"   huecos de >=15 dias: {len(largos)} | con radar dentro {len(cl)} ({100*len(cl)/len(largos):.0f}%)")
        pk = max(largos, key=lambda h: h.dias)
        print(f"   el peor: {pk.inicio} -> {pk.fin} = {pk.dias} dias sin optico, {pk.pasadas_radar} pasadas de radar")
    # pasadas S1 por ano: la constelacion cambia, se mide
    from collections import Counter
    c = Counter(x.fecha.year for x in pas)
    print("   S1 por ano:", " ".join(f"{a}:{n}" for a, n in sorted(c.items())))
