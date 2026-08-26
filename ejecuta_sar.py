"""Serie temporal de retrodispersion sobre los predios, orbita a orbita."""
import json, sys, time
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
sys.path.insert(0, "src")
from cielociego.predios import carga_predio
from cielociego.sar import busca_rtc, mide_retro, por_orbita

ORBITA = 77  # la mas poblada en ambos predios; ascendente
HILOS = 8

for nom in ("predio_corredor", "predio_fundacion"):
    p = carga_predio(f"datos/{nom}.geojson")
    items = [x for x in busca_rtc(p, "2019-01-01", "2026-08-25")
             if x["properties"].get("sat:relative_orbit") == ORBITA]
    print(f"\n== {p.nombre}: {len(items)} escenas en la orbita {ORBITA}", flush=True)
    t0 = time.time()
    ses = requests.Session()
    hechas = []
    with ThreadPoolExecutor(HILOS) as pool:
        futs = [pool.submit(mide_retro, it, p, sesion=ses) for it in items]
        for n, f in enumerate(as_completed(futs), 1):
            hechas.append(f.result())
            if n % 20 == 0 or n == len(futs):
                sys.stderr.write(f"\r  {n}/{len(futs)}  {time.time()-t0:.0f}s")
                sys.stderr.flush()
    sys.stderr.write("\n")
    ok = [r for r in hechas if r.error is None]
    mal = [r for r in hechas if r.error]
    ok.sort(key=lambda r: r.fecha)
    json.dump({"predio": p.nombre, "orbita": ORBITA,
               "medidas": [r.dict() for r in ok], "errores": [r.dict() for r in mal]},
              open(f"salidas/{nom}_sar.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"  medidas {len(ok)} | fallidas {len(mal)} | {time.time()-t0:.0f}s", flush=True)
    if ok:
        import numpy as np
        vv = np.array([r.vv_db for r in ok]); vh = np.array([r.vh_db for r in ok])
        print(f"  VV {vv.mean():.2f} dB (sd {vv.std():.2f})  |  VH {vh.mean():.2f} dB (sd {vh.std():.2f})", flush=True)
    for m in mal[:3]:
        print(f"    ! {m.fecha} {m.error}", flush=True)
print("\nSAR COMPLETO")
