"""Corre el barrido SCL completo sobre los dos predios y guarda los resultados."""
import json, sys, time
sys.path.insert(0, "src")
from cielociego.barrido import barre, _barra
from cielociego.predios import carga_predio

for nom in ("predio_fundacion", "predio_corredor"):
    p = carga_predio(f"datos/{nom}.geojson")
    tomas = json.load(open(f"salidas/{nom}_s2_tomas.json", encoding="utf-8"))
    print(f"\n== {p.nombre} ({p.area_ha} ha) - {len(tomas)} tomas", flush=True)
    t0 = time.time()
    r = barre(p, tomas, hilos=12, avisa=_barra)
    ruta = r.guarda(f"salidas/{nom}_scl.json")
    print(f"  medidas {len(r.vistas)} | fallidas {len(r.fallidas)} | {time.time()-t0:.0f}s -> {ruta}", flush=True)
    if r.fallidas:
        for v in r.fallidas[:5]:
            print(f"    ! {v.fecha} {v.error}", flush=True)
print("\nBARRIDO COMPLETO")
