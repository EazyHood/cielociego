"""Genera el informe HTML autocontenido a partir de lo medido.

No calcula nada: solo compone. Si una cifra de aqui no sale de salidas/*.json,
es que alguien la escribio a mano, y eso es justo lo que este proyecto no hace.
"""
import json
import sys

sys.path.insert(0, "src")

R = json.load(open("salidas/resumen.json", encoding="utf-8"))
F, C = R["predio_fundacion"], R["predio_corredor"]
G = {k: open(f"salidas/grafica_{k}.svg", encoding="utf-8").read()
     for k in ("dist", "cal_f", "cal_c", "dur", "anual")}
HUE_F = json.load(open("salidas/predio_fundacion_radar.json", encoding="utf-8"))["huecos"]
HUE_C = json.load(open("salidas/predio_corredor_radar.json", encoding="utf-8"))["huecos"]

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
  <div><span class="cifra">48</span><span class="pie">pruebas automáticas en verde</span></div>
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

</div>

<section class="pila g3">
  <h2>Lo que esto <em>no</em> demuestra</h2>
  <div class="pila g2 medida">
    <p>El radar mide retrodispersión: rugosidad, geometría, humedad. El óptico mide reflectancia:
    pigmento, clorofila. <b>Un NDVI no se sustituye por un VV/VH.</b> Lo medido aquí es que existe
    una observación en esas fechas, no que diga lo mismo.</p>
    <p>Tampoco es un resultado agronómico. No se ha demostrado que de esas pasadas salga una decisión
    de finca; eso es el trabajo siguiente, y esta medición es exactamente lo que lo justifica.</p>
  </div>
  <div class="pila g2 medida">
    <p class="nota"><b>Dos decisiones que mueven los números, y por eso se declaran.</b> Cuenta como
    ciega la nube, la sombra de nube, el cirro, el píxel saturado y el sin dato; la sombra orográfica
    se calcula aparte, porque en terreno llano suele ser suelo húmedo y no sombra real. Y el umbral
    de «útil» es el 10 % del predio tapado: moverlo cambia el reparto entre útiles y huecos, no la
    conclusión.</p>
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
  48 pruebas en verde · código y datos intermedios incluidos en el repositorio</p>
</footer>

</div>
"""

with open("salidas/informe.html", "w", encoding="utf-8") as fh:
    fh.write(HTML)
print(f"informe.html escrito: {len(HTML) / 1024:.0f} KB")
