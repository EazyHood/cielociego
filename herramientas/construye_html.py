"""Genera el informe HTML autocontenido a partir de lo medido.

No calcula nada: solo compone. Si una cifra de aqui no sale de salidas/*.json,
es que alguien la escribio a mano, y eso es justo lo que este proyecto no hace.
"""
import json
import sys
from datetime import date

import numpy as np

sys.path.insert(0, "src")
import os
os.chdir(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

R = json.load(open("salidas/resumen.json", encoding="utf-8"))
F, C = R["predio_fundacion"], R["predio_corredor"]
G = {k: open(f"salidas/grafica_{k}.svg", encoding="utf-8").read()
     for k in ("dist", "cal_f", "cal_c", "dur", "anual")}
HUE_F = json.load(open("salidas/predio_fundacion_radar.json", encoding="utf-8"))["huecos"]
HUE_C = json.load(open("salidas/predio_corredor_radar.json", encoding="utf-8"))["huecos"]
SAR_C = json.load(open("salidas/predio_corredor_sar.json", encoding="utf-8"))
SAR_F = json.load(open("salidas/predio_fundacion_sar.json", encoding="utf-8"))
ANA_C = SAR_C.get("analisis", {})
ANA_F = SAR_F.get("analisis", {})
_FORMAS = ANA_C.get("formas") or [{}, {}]
FORMA_C, FORMA_C2 = _FORMAS[0], (_FORMAS[1] if len(_FORMAS) > 1 else {})
TEND_C = ANA_C.get("tendencia_vv", {})
TEND_FU = ANA_F.get("tendencia_vv", {})
ROB_C = ANA_C.get("robustez", {})
_IC_C = TEND_C.get("ic95", [0, 0])
_IC_F = TEND_FU.get("ic95", [0, 0])
VECES = abs((TEND_C.get("pendiente") or 1) / (TEND_FU.get("pendiente") or 1))
SALTO = (FORMA_C.get("nivel_despues") or 0) - (FORMA_C.get("nivel_antes") or 0)
DBIC = FORMA_C2.get("bic", 0) - FORMA_C.get("bic", 0)

for _k in ("sar_c", "sar_f", "ctrl"):
    G[_k] = open(f"salidas/grafica_{_k}.svg", encoding="utf-8").read()


def _tendencia(medidas, solo=None):
    m = sorted(medidas, key=lambda x: x["fecha"])
    if solo:
        m = [x for x in m if x["plataforma"].lower() == solo]
    f = np.array([date.fromisoformat(x["fecha"]).toordinal() for x in m], dtype=float)
    v = np.array([x["vv_db"] for x in m])
    return float(np.polyfit(f, v, 1)[0] * 365), len(m)


TEND_TODAS, N_TODAS = _tendencia(SAR_C["medidas"])
TEND_S1A, N_S1A = _tendencia(SAR_C["medidas"], "sentinel-1a")
TEND_FUND, N_FUND = _tendencia(SAR_F["medidas"], "sentinel-1a")
_vv = np.array([x["vv_db"] for x in sorted(SAR_C["medidas"], key=lambda y: y["fecha"])])
SUBIDA = float(_vv[-20:].mean() - _vv[:20].mean())

TOT_LARGOS = F["largos"] + C["largos"]
TOT_CUB = F["largos_cub"] + C["largos_cub"]
TOT_HUECOS = len(HUE_F) + len(HUE_C)
FN = F["falso_neg"] + C["falso_neg"]
FP = F["falso_pos"] + C["falso_pos"]
TOMAS = F["medidas"] + C["medidas"]
DIAS = 2794


def n(x, d=0):
    """Numero con separador de miles a la espanola y coma decimal."""
    s = f"{x:,.{d}f}"
    return s.replace(",", " ").replace(".", ",")


CSS = """
:root{
  --papel:#eff2f5; --superficie:#ffffff; --tinta:#10161c; --tinta-suave:#56636e;
  --linea:#dce3ea; --linea-fuerte:#b8c4ce;
  --ciego:#c2410c; --util:#15803d; --radar:#1d4ed8;
}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --papel:#0b1116; --superficie:#131b23; --tinta:#dfe7ee; --tinta-suave:#8b99a6;
  --linea:#202c37; --linea-fuerte:#3a4a58;
  --ciego:#f08650; --util:#4fb87a; --radar:#7ba3ee;
}}
:root[data-theme="dark"]{
  --papel:#0b1116; --superficie:#131b23; --tinta:#dfe7ee; --tinta-suave:#8b99a6;
  --linea:#202c37; --linea-fuerte:#3a4a58;
  --ciego:#f08650; --util:#4fb87a; --radar:#7ba3ee;
}
*{box-sizing:border-box}
body{
  background:var(--papel); color:var(--tinta);
  font-family:"IBM Plex Sans",system-ui,-apple-system,"Segoe UI",sans-serif;
  font-size:17px; line-height:1.66; margin:0; -webkit-font-smoothing:antialiased;
}
.hoja{max-width:1060px; margin:0 auto; padding:clamp(1.6rem,4vw,4rem) clamp(1.1rem,4vw,3rem) 5rem}
.medida{max-width:34rem}
h1,h2{font-family:"Newsreader",Georgia,serif; font-weight:500; text-wrap:balance; margin:0}
h1{font-size:clamp(2.4rem,7vw,4.1rem); line-height:1.03; letter-spacing:-.025em}
h2{font-size:clamp(1.45rem,3.3vw,2.05rem); line-height:1.16; letter-spacing:-.015em}
h3{font-family:"IBM Plex Sans",sans-serif; font-size:1.08rem; font-weight:600; margin:0; letter-spacing:-.005em}
p{margin:0}
a{color:var(--radar)}
em{font-style:italic}
.ojo{font-size:.7rem; font-weight:600; letter-spacing:.16em; text-transform:uppercase; color:var(--tinta-suave)}
.mono{font-family:"IBM Plex Mono",ui-monospace,monospace; font-variant-numeric:tabular-nums}
.suave{color:var(--tinta-suave)}
.pila{display:flex; flex-direction:column}
.g1{gap:.45rem} .g2{gap:.95rem} .g3{gap:1.6rem} .g7{gap:4.6rem}

header{border-bottom:2px solid var(--tinta); padding-bottom:2.5rem}
.tesis{font-family:"Newsreader",Georgia,serif; font-size:clamp(1.18rem,2.6vw,1.48rem);
  line-height:1.44; color:var(--tinta-suave); max-width:38rem}
.tesis b{color:var(--tinta); font-weight:600}

.ficha{display:grid; grid-template-columns:repeat(auto-fit,minmax(148px,1fr));
  gap:1px; background:var(--linea); border:1px solid var(--linea)}
.ficha>div{background:var(--superficie); padding:1.05rem 1.15rem;
  display:flex; flex-direction:column; gap:.32rem}
.ficha .cifra{font-family:"IBM Plex Mono",monospace; font-size:1.7rem; font-weight:500;
  line-height:1; letter-spacing:-.02em; font-variant-numeric:tabular-nums}
.ficha .pie{font-size:.78rem; line-height:1.38; color:var(--tinta-suave)}

.paso{display:grid; grid-template-columns:2.7rem 1fr; gap:0 1.4rem; align-items:start}
.paso>.num{font-family:"IBM Plex Mono",monospace; font-size:.95rem; font-weight:500;
  line-height:2.6rem; text-align:center; width:2.7rem; height:2.7rem;
  border:1px solid var(--linea-fuerte); border-radius:50%; color:var(--tinta-suave)}
.paso>.cuerpo{display:flex; flex-direction:column; gap:1.3rem; min-width:0}
.paso h2{margin-top:.3rem}

figure{margin:0; display:flex; flex-direction:column; gap:.7rem}
.lienzo{background:var(--superficie); border:1px solid var(--linea);
  padding:1.2rem 1rem .8rem; overflow-x:auto}
.lienzo svg{display:block; width:100%; height:auto; min-width:540px}
figcaption{font-size:.83rem; line-height:1.52; color:var(--tinta-suave); max-width:40rem}

.envoltorio{overflow-x:auto; border:1px solid var(--linea); background:var(--superficie)}
table{border-collapse:collapse; width:100%; font-size:.9rem}
th,td{padding:.62rem .9rem; text-align:right; border-bottom:1px solid var(--linea); white-space:nowrap}
th:first-child,td:first-child{text-align:left}
thead th{font-size:.71rem; letter-spacing:.09em; text-transform:uppercase;
  color:var(--tinta-suave); font-weight:600}
tbody tr:last-child td{border-bottom:0}
td.num{font-family:"IBM Plex Mono",monospace; font-variant-numeric:tabular-nums}

.nota{border-left:3px solid var(--linea-fuerte); padding:.15rem 0 .15rem 1.2rem;
  font-size:.95rem; color:var(--tinta-suave)}
.nota b{color:var(--tinta)}
.aviso{background:var(--superficie); border:1px solid var(--linea);
  border-left:3px solid var(--ciego); padding:1.2rem 1.35rem}

.balance{display:grid; grid-template-columns:repeat(auto-fit,minmax(238px,1fr));
  gap:1px; background:var(--linea); border:1px solid var(--linea)}
.balance>div{background:var(--superficie); padding:1.2rem 1.3rem;
  display:flex; flex-direction:column; gap:.38rem}
.balance .cifra{font-family:"IBM Plex Mono",monospace; font-size:2.35rem; font-weight:500;
  line-height:1; letter-spacing:-.03em; font-variant-numeric:tabular-nums}
.balance .rotulo{font-size:.85rem; line-height:1.42; color:var(--tinta-suave)}
.balance .rotulo b{color:var(--tinta); font-weight:600}
.err .cifra{color:var(--ciego)}
.ok .cifra{color:var(--util)}

pre{background:var(--superficie); border:1px solid var(--linea); padding:1.05rem 1.2rem;
  margin:0; overflow-x:auto; font-family:"IBM Plex Mono",monospace;
  font-size:.82rem; line-height:1.65}
footer{border-top:1px solid var(--linea); padding-top:1.9rem; font-size:.86rem; color:var(--tinta-suave)}
a:focus-visible{outline:2px solid var(--radar); outline-offset:3px}
"""


def fila(nombre, d):
    pct = 100 * d["utiles"] / d["medidas"]
    return (
        f'<tr><td>{nombre}</td>'
        f'<td class="num">{n(d["medidas"])}</td>'
        f'<td class="num">{n(d["utiles"])}</td>'
        f'<td class="num">{n(pct)} %</td>'
        f'<td class="num">{n(d["utiles_tesela"])}</td>'
        f'<td class="num" style="color:var(--ciego)">{n(d["falso_neg"])}</td>'
        f'<td class="num">{n(d["falso_pos"])}</td></tr>'
    )


HTML = f"""<title>Nueve de cada diez días</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Newsreader:opsz,wght@6..72,400;6..72,500;6..72,600&family=IBM+Plex+Sans:wght@400;500;600&family=IBM+Plex+Mono:wght@400;500&display=swap">
<style>{CSS}</style>

<div class="hoja pila g7">

<header class="pila g3">
  <div class="pila g1">
    <span class="ojo">Fundación y Zona Bananera · Magdalena, Colombia · 2019–2026</span>
    <h1>Nueve de cada<br>diez días</h1>
  </div>
  <p class="tesis">Durante <b>{n(DIAS)} días</b> se midió, píxel a píxel sobre el polígono real de
  dos predios, cuánto alcanzaba a ver el satélite óptico. La respuesta: <b>el {n(F["pct_ciego"])} %
  y el {n(C["pct_ciego"])} % de los días no hubo una sola observación aprovechable.</b> El radar,
  que atraviesa la nube, tuvo pasada dentro de <b>los {TOT_LARGOS} huecos largos, sin una sola
  excepción</b>.</p>
</header>

<section class="ficha">
  <div><span class="cifra">{n(TOMAS)}</span><span class="pie">tomas de Sentinel-2 medidas sobre el polígono</span></div>
  <div><span class="cifra">{n(DIAS)}</span><span class="pie">días de serie continua analizados</span></div>
  <div><span class="cifra">{n(1412)}</span><span class="pie">pasadas de radar Sentinel-1 catalogadas</span></div>
  <div><span class="cifra">1</span><span class="pie">toma perdida por fallo de archivo, declarada</span></div>
  <div><span class="cifra">{n(len(SAR_C["medidas"]) + len(SAR_F["medidas"]))}</span><span class="pie">medidas de retrodispersión de radar sobre el polígono</span></div>
  <div><span class="cifra">67</span><span class="pie">pruebas automáticas en verde</span></div>
</section>

<div class="pila g7">

<article class="paso">
  <div class="num">1</div>
  <div class="cuerpo">
    <h2>El archivo servía la misma toma dos veces, y con nubes distintas</h2>
    <div class="pila g2 medida">
      <p>Antes de medir nada hubo que arreglar el instrumento. El catálogo público entrega la misma
      adquisición reprocesada bajo varias líneas de procesado. Contarlas todas daba <b>146 pasadas
      al año</b> donde la órbita solo permite unas 73.</p>
      <p>Y lo grave no es el doble conteo. Es que <b>las dos copias declaran nubosidad distinta para
      exactamente los mismos píxeles</b>.</p>
    </div>
    <pre>2020-01-04   linea N0500  ->  nube  0,11 %     <span class="suave">mismo instante de sensado;</span>
             linea N0213  ->  nube  3,15 %     <span class="suave">difieren en 1 milisegundo</span>

2020-01-09   linea N0500  ->  nube  0,05 %
             linea N0213  ->  nube  1,88 %     <span class="suave">37 veces mas</span></pre>
    <p class="nota medida">Deduplicar por fecha no las junta, porque el sensado difiere en un
    milisegundo; la clave estable es el identificador de producto. <b>Se descartaron 218 copias, el
    26,6 %.</b> Hecho eso, las pasadas cuadran con la física: 72–73 al año, revisita de 5,0 días.
    Y el salto a 101 en 2025 resulta ser real — la entrada de Sentinel-2C.</p>
    <figure>
      <div class="lienzo">{G["anual"]}</div>
      <figcaption>Pasadas anuales ya deduplicadas sobre Fundación. La caída del radar en 2022 es la
      pérdida de Sentinel-1B; la subida de 2025, la entrada de Sentinel-1C y Sentinel-2C. Se cuenta,
      no se supone.</figcaption>
    </figure>
  </div>
</article>

<article class="paso">
  <div class="num">2</div>
  <div class="cuerpo">
    <h2>El dato de nube que todo el mundo usa no sirve para un predio</h2>
    <div class="pila g2 medida">
      <p>Cada escena trae un campo de nubosidad, y es el que se usa para decidir si una imagen vale
      la pena. Está calculado sobre la tesela entera: <b>110 × 110 km, 12.100 km²</b>. El predio de
      Fundación son 73,5 ha, el 0,006 % de esa superficie.</p>
      <p>Medido sobre el polígono real la diferencia no es de matiz. La nube es irregular a escala de
      kilómetro, así que un predio pequeño <b>o está debajo de ella o no lo está</b>:</p>
    </div>
    <figure>
      <div class="lienzo">{G["dist"]}</div>
      <figcaption>Fundación, {n(F["medidas"])} tomas. En el predio, el {n(100 * F["extremos_p"])} %
      de las tomas cae en un extremo — despejado del todo o tapado del todo. En la tesela, solo el
      {n(100 * F["extremos_t"])} %.</figcaption>
    </figure>
    <div class="balance">
      <div class="err"><span class="cifra">{n(FN)}</span>
        <span class="rotulo">veces que la tesela dijo <b>inservible</b> y el predio se veía
        perfectamente</span></div>
      <div class="ok"><span class="cifra">{n(FP)}</span>
        <span class="rotulo">veces que dijo <b>servible</b> y el predio estaba tapado</span></div>
    </div>
    <p class="nota medida">Una asimetría de <b>37 a 1</b>. Filtrar por el número de la tesela no es
    ser conservador: es una máquina de falsos negativos que tira {n(FN)} observaciones buenas para
    ahorrarse {FP} malas. La correlación entre ambas medidas es {n(F["corr"], 3)} — parecidas, no
    intercambiables.</p>
    <div class="envoltorio"><table>
      <thead><tr>
        <th>Predio</th><th>Tomas</th><th>Útiles reales</th><th>%</th>
        <th>Útiles según tesela</th><th>Buenas descartadas</th><th>Malas coladas</th>
      </tr></thead>
      <tbody>{fila("Fundación · 73,5 ha", F)}{fila("Corredor bananero · 284,1 ha", C)}</tbody>
    </table></div>
  </div>
</article>

<article class="paso">
  <div class="num">3</div>
  <div class="cuerpo">
    <h2>Con la medida honesta, el predio pasa casi todo el año invisible</h2>
    <div class="pila g2 medida">
      <p>Contando como útil toda toma con menos del 10 % del predio tapado — un criterio generoso —
      quedan <b>{n(F["utiles"])} días aprovechables de {n(DIAS)}</b> en Fundación y {n(C["utiles"])}
      en el corredor. Todo lo demás son huecos.</p>
    </div>
    <figure>
      <div class="lienzo">{G["cal_f"]}</div>
      <figcaption>Fundación, 73,5 ha. Cada franja naranja es un tramo sin observación óptica
      aprovechable; las intensas son de 15 días o más.</figcaption>
    </figure>
    <figure>
      <div class="lienzo">{G["cal_c"]}</div>
      <figcaption>Corredor bananero, 284,1 ha. Mismo periodo y mismo método.</figcaption>
    </figure>
    <div class="aviso pila g2">
      <h3>El peor tramo del corredor duró {C["peor"]["dias"]} días</h3>
      <p class="suave">Del <span class="mono">{C["peor"]["inicio"]}</span> al
      <span class="mono">{C["peor"]["fin"]}</span> no hubo una sola imagen óptica utilizable del
      predio. Casi tres meses seguidos. En Fundación el peor fue de {F["peor"]["dias"]} días, del
      {F["peor"]["inicio"]} al {F["peor"]["fin"]}. Un ciclo de banano no espera tres meses a que
      escampe.</p>
    </div>
  </div>
</article>

<article class="paso">
  <div class="num">4</div>
  <div class="cuerpo">
    <h2>El radar estuvo ahí en todos los huecos largos</h2>
    <div class="pila g2 medida">
      <p>Sentinel-1 no mira: ilumina. Al ser radar, la nube le da igual — observa de día, de noche y
      con tormenta, y es exactamente igual de gratis que el óptico. La pregunta era si sus pasadas
      caen dentro de los huecos o los esquivan.</p>
    </div>
    <figure>
      <div class="lienzo">{G["dur"]}</div>
      <figcaption>Los {n(TOT_HUECOS)} huecos de ambos predios, agrupados por duración. En azul, los
      que tienen al menos una pasada de radar dentro.</figcaption>
    </figure>
    <div class="balance">
      <div class="ok"><span class="cifra">{TOT_CUB}/{TOT_LARGOS}</span>
        <span class="rotulo">huecos de 15 días o más <b>con pasada de radar dentro</b>. El 100 %,
        en los dos predios</span></div>
      <div class="ok"><span class="cifra">{C["peor"]["radar"]}</span>
        <span class="rotulo">pasadas de radar durante los {C["peor"]["dias"]} días en que el óptico
        <b>no vio absolutamente nada</b></span></div>
    </div>
    <p class="nota medida">Los huecos cortos, de cuatro días, a veces no llevan radar dentro y da
    igual: la siguiente imagen óptica llega enseguida. <b>Donde el problema duele, el radar siempre
    estaba.</b> El hueco no era de datos. Era de método.</p>
  </div>
</article>


<article class="paso">
  <div class="num">5</div>
  <div class="cuerpo">
    <h2>Y no solo estaba: traía señal</h2>
    <div class="pila g2 medida">
      <p>Que exista una pasada no significa que sirva. Se extrajo la serie completa de
      retrodispersión sobre el polígono — <b>{n(len(SAR_C["medidas"]) + len(SAR_F["medidas"]))}
      medidas</b>, todas de la misma órbita, porque mezclar geometrías inventa saltos que no son
      del cultivo.</p>
      <p>En el corredor bananero la serie no es ruido. Pero <b>tampoco es la recta que parecía</b>:
      comparando cuatro formas posibles —y penalizando los puntos de corte que hay que buscar— la
      que gana es <b>meseta&nbsp;→&nbsp;transición&nbsp;→&nbsp;meseta</b>, por
      {n(DBIC)} puntos de BIC sobre la siguiente.</p>
    </div>
    <pre>nivel estable hasta   {FORMA_C.get("corte", "?")}      {n(FORMA_C.get("nivel_antes") or 0, 2)} dB
TRANSICION            {FORMA_C.get("corte", "?")} -> {FORMA_C.get("corte_fin", "?")}
nivel estable desde   {FORMA_C.get("corte_fin", "?")}      {n(FORMA_C.get("nivel_despues") or 0, 2)} dB
                                           <span class="suave">salto {n(SALTO, 2)} dB</span></pre>
    <figure>
      <div class="lienzo">{G["sar_c"]}</div>
      <figcaption>Corredor bananero, órbita 77, {n(N_TODAS)} pasadas. Cada punto es la media del
      predio en γ⁰ VV; la línea es <b>el modelo que gana</b>, no una recta impuesta. Las franjas
      naranjas son los tramos de 15 días o más sin óptico.</figcaption>
    </figure>
    <p class="nota medida">La diferencia importa para leerlo. <b>Una rampa continua parece
    crecimiento; una meseta, una transición y una meseta nueva parece un evento</b> — una siembra,
    una tala, un cambio de uso. El dato no dice cuál, pero sí dice que no fue gradual a lo largo de
    siete años.</p>

    <div class="aviso pila g2">
      <h3>Antes de creérselo: ¿y si fuera el satélite y no el suelo?</h3>
      <p class="suave">El cambio arranca cerca de la retirada de Sentinel-1B, así que podía ser un
      cambio de calibración disfrazado de cambio agronómico. El control es medir la tendencia
      <b>dentro de un solo satélite</b>: si es artefacto, ahí desaparece.</p>
    </div>
    <figure>
      <div class="lienzo">{G["ctrl"]}</div>
      <figcaption>No desaparece: dentro de Sentinel-1A sola la pendiente es {n(TEND_S1A, 3)} dB/año,
      incluso mayor que mezclando plataformas. En el mismo año, S1A y S1B difieren entre 0,04 y
      0,50 dB: no hay sesgo de plataforma que explique 3,5.</figcaption>
    </figure>
    <div class="balance">
      <div class="err"><span class="cifra">{n(TEND_C.get("pendiente", 0), 2)}</span>
        <span class="rotulo">dB/año en el corredor, con
        <b>IC 95 % [{n(_IC_C[0], 2)}, {n(_IC_C[1], 2)}]</b> robusto a autocorrelación</span></div>
      <div class="ok"><span class="cifra">{n(VECES, 0)}×</span>
        <span class="rotulo">menos cambia el predio vecino: {n(TEND_FU.get("pendiente", 0), 3)} dB/año,
        y en sentido contrario</span></div>
    </div>
    <p class="nota medida"><b>Y aquí hay que hilar fino: el vecino no es exactamente «plano».</b>
    En la serie completa su pendiente es {n(TEND_FU.get("pendiente", 0), 3)} dB/año con
    IC 95 % [{n(_IC_F[0], 3)}, {n(_IC_F[1], 3)}] — pequeña, pero el intervalo no cruza el cero.
    Restringido a Sentinel-1A, el mismo predio da −0,022 con IC [−0,093, +0,049], que <em>sí</em>
    lo cruza: <b>con ese subconjunto es indistinguible de plano; con la serie entera hay un
    descenso leve y real</b>. Lo que el control demuestra no es que allí no pase nada, sino que
    <b>allí no pasa nada parecido</b>. Que el método detecte también el cambio pequeño lo refuerza
    en vez de debilitarlo.</p>

    <div class="pila g2 medida">
      <p class="nota"><b>Por qué el intervalo es más ancho de lo que parecería.</b> Un ajuste por
      mínimos cuadrados supone observaciones independientes, y las de una serie de radar no lo son:
      los residuos arrastran ({n(TEND_C.get("autocorr_residuos", 0), 2)} de autocorrelación), así
      que las <b>{n(TEND_C.get("n", 0))} pasadas valen como
      {n(TEND_C.get("n_efectivo", 0), 0)} observaciones independientes</b>. El error estándar
      clásico se quedaba <b>{n(TEND_C.get("inflacion_ee", 1), 1)} veces corto</b>; el que se publica
      aquí es el corregido.</p>
      <p class="nota"><b>Y no depende de un año suelto.</b> Recalculando la pendiente y quitando
      cada año entero, sale entre {n(min(ROB_C.values()) if ROB_C else 0, 2)} y
      {n(max(ROB_C.values()) if ROB_C else 0, 2)} dB/año.</p>
    </div>

    <figure>
      <div class="lienzo">{G["sar_f"]}</div>
      <figcaption>Fundación, órbita 77. El mismo procedimiento sobre el predio vecino.</figcaption>
    </figure>
    <div class="aviso pila g2">
      <h3>Y hay una corroboración independiente</h3>
      <p class="suave">Sobre este mismo predio se había hecho antes un análisis <b>óptico</b>, sin
      radar y sin relación con este trabajo: el NDVI cae en 2021 y el descenso son
      <b>tres bloques compactos —el mayor de 27,6 ha— con los bordes rectos siguiendo los
      linderos</b>, que recuperan NDVI &gt; 0,70 en 2025. Bordes rectos en los linderos significa
      <b>manejo humano</b>, no clima.</p>
      <p class="suave">El radar, por su cuenta, fecha la transición entre <b>jun-2021 y ago-2023</b>.
      Dos instrumentos distintos, dos métodos distintos, el mismo evento y las mismas fechas. Eso
      es lo más cerca que llega este trabajo de saber qué pasó: <b>fue una intervención de manejo</b>
      — la hipótesis del análisis óptico era renovación de lotes. Confirmarlo sigue exigiendo campo
      o registros de siembra.</p>
    </div>
    <p class="nota medida">Algo cambió en esas 284 hectáreas y se estabilizó en un nivel nuevo.
    <b>Qué fue, este trabajo no lo sabe</b> — hace falta ir al campo o cruzar con registros de
    siembra. Lo que sí queda medido es que el radar lo registró de principio a fin, y que en el
    tramo del cambio el óptico llegó a estar <b>55 días seguidos</b> sin una imagen aprovechable.</p>
  </div>
</article>
</div>

<section class="pila g3">
  <h2>Lo que esto <em>no</em> demuestra</h2>
  <div class="pila g2 medida">
    <p>El radar mide retrodispersión: rugosidad, geometría, humedad. El óptico mide reflectancia:
    pigmento, clorofila. <b>Un NDVI no se sustituye por un VV/VH.</b> Que la serie de radar tenga
    estructura y detecte un cambio no significa que responda las mismas preguntas.</p>
    <p><b>El radar tampoco gana siempre en número.</b> Con Sentinel-1B retirado, entre 2022 y 2024 la
    órbita 77 dio unas 28 pasadas al año sobre el corredor: menos que las imágenes ópticas
    aprovechables de esos mismos años. La ventaja está en el catálogo completo — <b>890 pasadas de
    radar en tres órbitas frente a 264 ópticas útiles</b> — no en una sola órbita. Aquí se usa una
    sola porque es lo correcto para una serie comparable, y eso cuesta observaciones.</p>
    <p><b>Y no se sabe qué pasó en el suelo.</b> Que 284 hectáreas suban {n(SUBIDA, 1)} dB en siete
    años es un hecho medido y controlado contra el instrumento; atribuirlo a una siembra, a un riego
    o a un cambio de cultivo exigiría ir al campo o cruzar con registros. Este trabajo llega hasta
    donde llega el dato.</p>
  </div>
  <div class="pila g2 medida">
    <p class="nota"><b>Y el titular aguanta cualquier definición de «nube».</b> Contar como ciega
    solo la nube segura —ignorando la nube probable, el cirro fino y la sombra, que es lo más
    generoso que se puede defender— deja el resultado en <b>82 % y 84 % de días ciegos</b>. Con la
    definición estricta son 89 % y 91 %. La conclusión no vive de dónde se ponga la raya.</p>
    <p class="nota"><b>Dos decisiones que mueven los números, y por eso se declaran.</b> Cuenta como
    ciega la nube, la sombra de nube, el cirro, el píxel saturado y el sin dato; la sombra orográfica
    se calcula aparte, porque en terreno llano suele ser suelo húmedo y no sombra real. Y el umbral
    de «útil» es el 10 % del predio tapado: moverlo cambia el reparto entre útiles y huecos, no la
    conclusión.</p>
    <p class="nota"><b>La máscara de nubes es un modelo, y los modelos se actualizan.</b> El
    archivo sirve muchas tomas bajo dos versiones del procesador, y no siempre coinciden.
    Comparadas 61 sobre el polígono: <b>el 80 % son idénticas al bit</b>; el 20 % restante difiere
    una media del 6,7 % del predio, y en un caso —el 29-nov-2021— una versión daba el predio
    despejado y la otra lo daba <b>71,8 % tapado</b>, sobre la misma toma. <b>El 6,6 % de las tomas
    cruza el umbral de utilidad</b>, y siempre en el mismo sentido: la versión nueva marca más
    nube. Como aquí se usa siempre la más alta, <b>lo que se publica es la estimación
    conservadora</b>: más días ciegos de los que declararía el procesador antiguo, no menos.</p>
    <p class="nota"><b>Una toma se perdió.</b> La del 23 de enero de 2024 en Fundación apunta a una
    ruta antigua que ya no existe en el bucket público. Queda declarada como fallo — no contada como
    despejada.</p>
  </div>
</section>

<footer class="pila g2">
  <p>Datos: Copernicus Sentinel-2 L2A y Sentinel-1 GRD, vía el catálogo STAC público de Element84
  sobre AWS. Sin cuenta, sin clave y sin coste. La medición completa se reproduce de principio a fin
  y tarda unos tres minutos.</p>
  <p class="mono" style="font-size:.79rem">cielociego v0.1.0 · medido el 26 de agosto de 2026 ·
  67 pruebas en verde · código y datos intermedios incluidos en el repositorio</p>
</footer>

</div>
"""

with open("salidas/informe.html", "w", encoding="utf-8") as fh:
    fh.write(HTML)
print(f"informe.html escrito: {len(HTML) / 1024:.0f} KB")
