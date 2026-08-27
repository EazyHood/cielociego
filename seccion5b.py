"""Corrige la seccion 5 del informe con lo que salio de la auditoria.

Tres afirmaciones publicadas que la auditoria demostro imprecisas:
  1. "sube 3,5 dB en siete anos, de forma sostenida" -> es meseta-transicion-
     meseta, y la recta la describe peor por 270 puntos de BIC.
  2. "el vecino, plano" -> Fundacion cambia poco pero de forma significativa.
  3. la pendiente iba sin intervalo de confianza, y el clasico se queda corto.
"""
import pathlib

RUTA = pathlib.Path("herramientas/construye_html.py")
s = RUTA.read_text(encoding="utf-8")

# --- cargar el analisis nuevo que ya viene dentro del JSON ------------------
ANCLA = "for _k in (\"sar_c\", \"sar_f\", \"ctrl\"):"
NUEVO_CARGA = '''ANA_C = SAR_C.get("analisis", {})
ANA_F = SAR_F.get("analisis", {})
FORMA_C = (ANA_C.get("formas") or [{}])[0]
FORMA_C2 = (ANA_C.get("formas") or [{}, {}])[1] if len(ANA_C.get("formas") or []) > 1 else {}
TEND_C = ANA_C.get("tendencia_vv", {})
TEND_FU = ANA_F.get("tendencia_vv", {})
ROB_C = ANA_C.get("robustez", {})

for _k in ("sar_c", "sar_f", "ctrl"):'''
assert ANCLA in s
s = s.replace(ANCLA, NUEVO_CARGA, 1)

# --- reemplazar el cuerpo de la seccion 5 ----------------------------------
INI = '    <h2>Y no solo estaba: traía señal</h2>'
FIN = '</article>\n\n</div>\n\n<section class="pila g3">'
i = s.index(INI)
j = s.index(FIN)

CUERPO = '''    <h2>Y no solo estaba: traía señal</h2>
    <div class="pila g2 medida">
      <p>Que exista una pasada no significa que sirva. Se extrajo la serie completa de
      retrodispersión sobre el polígono — <b>{n(len(SAR_C["medidas"]) + len(SAR_F["medidas"]))}
      medidas</b>, todas de la misma órbita, porque mezclar geometrías inventa saltos que no son
      del cultivo.</p>
      <p>En el corredor bananero la serie no es ruido. Pero <b>tampoco es la recta que parecía</b>:
      comparando cuatro formas posibles, la que gana es <b>meseta&nbsp;→&nbsp;transición&nbsp;→
      &nbsp;meseta</b>, por {n(FORMA_C2.get("bic", 0) - FORMA_C.get("bic", 0))} puntos de BIC sobre
      la siguiente.</p>
    </div>
    <pre>nivel estable hasta   {FORMA_C.get("corte", "?")}        {n(FORMA_C.get("nivel_antes") or 0, 2)} dB
TRANSICION            {FORMA_C.get("corte", "?")} -> {FORMA_C.get("corte_fin", "?")}
nivel estable desde   {FORMA_C.get("corte_fin", "?")}        {n(FORMA_C.get("nivel_despues") or 0, 2)} dB
                                             <span class="suave">salto {n((FORMA_C.get("nivel_despues") or 0) - (FORMA_C.get("nivel_antes") or 0), 2)} dB</span></pre>
    <figure>
      <div class="lienzo">{G["sar_c"]}</div>
      <figcaption>Corredor bananero, órbita 77, {n(N_TODAS)} pasadas. Cada punto es la media del
      predio en γ⁰ VV; la línea es el modelo que gana, no una recta impuesta. Las franjas naranjas
      son los tramos de 15 días o más sin óptico.</figcaption>
    </figure>
    <p class="nota medida">La diferencia importa para leerlo: <b>una rampa continua parece
    crecimiento; una meseta, transición y meseta nueva parece un evento</b> — una siembra, una
    tala, un cambio de uso. El dato no dice cuál, pero sí dice que no fue gradual a lo largo de
    siete años.</p>

    <div class="aviso pila g2">
      <h3>Antes de creérselo: ¿y si fuera el satélite y no el suelo?</h3>
      <p class="suave">El cambio arranca cerca de la retirada de Sentinel-1B, así que podía ser un
      cambio de calibración disfrazado de cambio agronómico. El control es medir la tendencia
      <b>dentro de un solo satélite</b>: si es artefacto, ahí desaparece.</p>
    </div>
    <figure>
      <div class="lienzo">{G["ctrl"]}</div>
      <figcaption>No desaparece: dentro de Sentinel-1A sola la pendiente es
      {n(TEND_S1A, 3)} dB/año, incluso mayor que mezclando plataformas.</figcaption>
    </figure>
    <div class="balance">
      <div class="err"><span class="cifra">{n(TEND_C.get("pendiente", 0), 2)}</span>
        <span class="rotulo">dB/año en el corredor.
        <b>IC 95 % [{n(TEND_C.get("ic95", [0, 0])[0], 2)}, {n(TEND_C.get("ic95", [0, 0])[1], 2)}]</b>,
        con errores robustos a autocorrelación</span></div>
      <div class="ok"><span class="cifra">{n(TEND_FU.get("pendiente", 0), 3)}</span>
        <span class="rotulo">dB/año en Fundación: <b>{n(abs((TEND_C.get("pendiente") or 1) / (TEND_FU.get("pendiente") or 1)), 0)} veces menos</b>,
        y en sentido contrario</span></div>
    </div>
    <p class="nota medida"><b>Y aquí hay que ser preciso: el predio vecino no es «plano».</b>
    Su pendiente es pequeña pero significativa — el intervalo no cruza el cero. Lo que dice el
    control no es que allí no pase nada, sino que <b>allí no pasa nada parecido</b>: el corredor
    cambia {n(abs((TEND_C.get("pendiente") or 1) / (TEND_FU.get("pendiente") or 1)), 0)} veces más.
    Que el método detecte también el cambio pequeño refuerza el control en vez de debilitarlo.</p>

    <div class="pila g2 medida">
      <p class="nota"><b>Por qué el intervalo es más ancho de lo que parecería.</b> Un ajuste
      normal supone observaciones independientes, y las de una serie de radar no lo son: los
      residuos arrastran ({n(TEND_C.get("autocorr_residuos", 0), 2)} de autocorrelación), así que
      las <b>{n(TEND_C.get("n", 0))} pasadas valen como {n(TEND_C.get("n_efectivo", 0), 0)}
      observaciones independientes</b>. El error clásico se quedaba
      <b>{n(TEND_C.get("inflacion_ee", 1), 1)} veces corto</b>; aquí se publica el corregido.</p>
      <p class="nota"><b>Y no depende de un año suelto.</b> Recalculando la pendiente y quitando
      cada año entero, sale entre {n(min(ROB_C.values()) if ROB_C else 0, 2)} y
      {n(max(ROB_C.values()) if ROB_C else 0, 2)} dB/año.</p>
    </div>

    <figure>
      <div class="lienzo">{G["sar_f"]}</div>
      <figcaption>Fundación, órbita 77. El mismo procedimiento sobre el predio vecino.</figcaption>
    </figure>
    <p class="nota medida">Algo cambió en esas 284 hectáreas y se estabilizó en un nivel nuevo.
    <b>Qué fue, este trabajo no lo sabe</b> — hace falta ir al campo o cruzar con registros de
    siembra. Lo que sí queda medido es que el radar lo registró de principio a fin, y que en el
    tramo del cambio el óptico llegó a estar <b>55 días seguidos</b> sin una imagen aprovechable.</p>
  </div>
'''
s = s[:i] + CUERPO + s[j:]
RUTA.write_text(s, encoding="utf-8")
print("seccion 5 corregida")
