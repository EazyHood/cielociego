"""Genera el informe HTML con las cifras y graficas medidas."""
import json, sys
from collections import Counter
from datetime import date
sys.path.insert(0, "src")
import numpy as np
from cielociego import graficas

DESDE, HASTA = date(2019, 1, 1), date(2026, 8, 25)
P = {}
for nom in ("predio_fundacion", "predio_corredor"):
    scl = json.load(open(f"salidas/{nom}_scl.json", encoding="utf-8"))
    rad = json.load(open(f"salidas/{nom}_radar.json", encoding="utf-8"))
    tom = json.load(open(f"salidas/{nom}_s2_tomas.json", encoding="utf-8"))
    v = scl["vistas"]
    ciego = np.array([x["ciego_estricto"] for x in v])
    tes = np.array([(x["cc_tesela"] or 0) / 100 for x in v])
    up, ut = ciego <= 0.10, tes <= 0.10
    huecos = rad["huecos"]
    dias_ciegos = sum(h["dias"] for h in huecos)
    largos = [h for h in huecos if h["dias"] >= 15]
    P[nom] = dict(
        nombre=scl["predio"], area=scl["area_ha"], medidas=scl["medidas"], fallidas=scl["fallidas"],
        tomas_brutas=len(tom), ciego=ciego, tesela=tes,
        utiles=int(up.sum()), utiles_tesela=int(ut.sum()),
        falso_neg=int((up & ~ut).sum()), falso_pos=int((~up & ut).sum()),
        corr=float(np.corrcoef(ciego, tes)[0, 1]),
        extremos_p=float(((ciego < 0.01) | (ciego > 0.95)).mean()),
        extremos_t=float(((tes < 0.01) | (tes > 0.95)).mean()),
        despejado=float((ciego < 0.01).mean()), tapado=float((ciego > 0.95).mean()),
        huecos=huecos, dias_ciegos=dias_ciegos,
        pct_ciego=100 * dias_ciegos / ((HASTA - DESDE).days + 1),
        peor=max(huecos, key=lambda h: h["dias"]),
        largos=len(largos), largos_cub=sum(1 for h in largos if h["radar"] > 0),
        s1=[x["fecha"] for x in rad["pasadas_s1"]],
        fechas_utiles=[x["fecha"] for x in v if x["ciego_estricto"] <= 0.10],
        s2_ano=Counter(x["fecha"][:4] for x in v),
        s1_ano=Counter(x["fecha"][:4] for x in rad["pasadas_s1"]),
    )

F, C = P["predio_fundacion"], P["predio_corredor"]
G = {
    "dist": graficas.distribucion(F["ciego"], F["tesela"] * 100),
    "cal_f": graficas.calendario(F["fechas_utiles"], F["huecos"], F["s1"], DESDE, HASTA),
    "cal_c": graficas.calendario(C["fechas_utiles"], C["huecos"], C["s1"], DESDE, HASTA),
    "dur": graficas.huecos_por_duracion(F["huecos"] + C["huecos"]),
    "anual": graficas.pasadas_anuales(dict(F["s2_ano"]), dict(F["s1_ano"])),
}
json.dump({k: {kk: (vv.tolist() if isinstance(vv, np.ndarray) else vv)
               for kk, vv in v.items() if kk not in ("huecos", "s1", "fechas_utiles")}
           for k, v in P.items()},
          open("salidas/resumen.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
for k, s in G.items():
    open(f"salidas/grafica_{k}.svg", "w", encoding="utf-8").write(s)
print("graficas:", ", ".join(f"{k}({len(v)//1024}kb)" for k, v in G.items()))
print(f"\nFUNDACION  utiles {F['utiles']}/{F['medidas']}  tesela diria {F['utiles_tesela']}  falsos-neg {F['falso_neg']}  falsos-pos {F['falso_pos']}")
print(f"           ciego {F['pct_ciego']:.0f}% de dias | peor hueco {F['peor']['dias']}d ({F['peor']['inicio']}) con {F['peor']['radar']} radar")
print(f"           huecos >=15d: {F['largos_cub']}/{F['largos']} con radar")
print(f"CORREDOR   utiles {C['utiles']}/{C['medidas']}  tesela diria {C['utiles_tesela']}  falsos-neg {C['falso_neg']}  falsos-pos {C['falso_pos']}")
print(f"           ciego {C['pct_ciego']:.0f}% de dias | peor hueco {C['peor']['dias']}d ({C['peor']['inicio']}) con {C['peor']['radar']} radar")
print(f"           huecos >=15d: {C['largos_cub']}/{C['largos']} con radar")
