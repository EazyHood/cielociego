# Secciones para insertar en `manuscrito.es.md`

Todo lo de aquí está medido el 27-ago-2026 y reproducido de forma independiente contra los
ficheros que se citan al final. Ninguna cifra está estimada.

**Dónde va cada bloque:**

| Bloque | Va en | Nota |
|---|---|---|
| A | §2.4, nuevo, tras «2.3 Cohorte de parcelas» | |
| B | §3.6, nuevo, al final de Métodos | La identidad, como premisa |
| C | §3.7, nuevo, detrás del anterior | El emparejamiento |
| D | **§4.1, encabezando Resultados** | Renumerar las 4.1–4.7 actuales a 4.2–4.8 |
| E | §5.1, primer párrafo | |
| F | Referencias | Una cita nueva, verificada en Crossref |

---

## A · §2.4 Parcelas en la zona de solape de dos teselas

La retícula de teselas de Sentinel-2 no es una partición: las teselas miden 110 × 110 km y se
disponen sobre una malla de 100 km, de modo que cada una comparte una franja de unos 10 km con
cada vecina. Una parcela situada en esa franja no se observa dos veces —se observa una sola vez—,
pero el archivo la sirve **en dos gránulos distintos del mismo pase**, uno por tesela, y cada
gránulo lleva su propio valor de `eo:cloud_cover`.

Barriendo las 323 parcelas de la cohorte sobre 2023-2024 se recuperaron **92.914 ítems**. De las
323 parcelas, **84 caen en una zona de solape** (consultando por polígono; 83 consultando por
centroide, con `ftw-lithuania-013` a caballo del límite), repartidas en **14 países**: Ruanda 17,
Luxemburgo 10, España 7, Vietnam 7, Croacia 6, Lituania 6, Suecia 6, Bélgica 5, India 5,
Camboya 4, Finlandia 4, Kenia 3, Estonia 2 y Francia 2.

---

## B · §3.6 Qué es exactamente `eo:cloud_cover`

Conviene establecer qué se está comparando antes de compararlo, porque de ello depende que el
trabajo mida un cambio de soporte y no una diferencia entre dos clasificadores.

El valor `eo:cloud_cover` que publica el catálogo es **exactamente** la suma de tres porcentajes
por clase del propio SCL: `s2:high_proba_clouds_percentage`, `s2:medium_proba_clouds_percentage` y
`s2:thin_cirrus_percentage` —es decir, las clases 9, 8 y 10. La identidad se comprueba en
**4.430 de 4.430 escenas**, con un residuo máximo de **1,2 × 10⁻⁵ puntos porcentuales**, sobre
23 países y cuatro continentes (Europa 2.411, Asia 370, África 298, Sudamérica 147).

La comprobación se llevó al píxel para descartar que sea una coincidencia de redondeo. Leyendo el
ráster SCL completo de 5490 × 5490 y recalculando 100·(n₈+n₉+n₁₀)/(N−n₀), se reproduce el valor
publicado con un error de **4,0 × 10⁻⁶ puntos** en doce teselas que cubren de 0 a 100 % de nube.
El cálculo también fija el denominador: usar el ráster entero en lugar de la **huella válida**
introduce un error de hasta **16,5 puntos**, de modo que `eo:cloud_cover` es una fracción sobre el
área con dato, no sobre la tesela nominal.

La consecuencia es la que interesa: **las dos magnitudes que este trabajo compara descienden del
mismo clasificador, aplicado a los mismos píxeles, y difieren únicamente en el área sobre la que
se agregan.** No se está evaluando la calidad de la máscara de nube —un error del clasificador
afectaría por igual a los dos lados— sino el precio de resumir sobre 11.800 km² una decisión que
se toma sobre unas hectáreas. Es un experimento de cambio de soporte, y esa es su fortaleza.

Un control adicional: 1.041 adquisiciones se sirven a través de dos versiones distintas del
conversor del proveedor del catálogo. Los valores son idénticos bit a bit en 1.031, la diferencia
máxima es de 0,024 puntos y **ninguna adquisición cambia de veredicto** con un umbral del 10 %.
La versión del conversor no mueve el número.

---

## C · §3.7 Emparejamiento de gránulos del mismo pase

Dos gránulos pertenecen al mismo pase si comparten identificador de *datatake*. Se emparejan los
que además difieren en el código de tesela MGRS. Como varias parcelas de la cohorte comparten la
misma combinación de pase y par de teselas, contar un par por parcela contaría el mismo dato
varias veces: las **22.092** parejas parcela × pase se **deduplican a la terna
(pase, tesela A, tesela B)**, que es la unidad de observación independiente.

Quedan **6.116 pares únicos**, procedentes de **1.911 pases**, **37 teselas** y 25 combinaciones
de teselas; los aportan 20 de las 84 parcelas en solape, ya que las demás repiten pares ya
contados. La asignación de A y B es lexicográfica por código de tesela, de modo que el signo de
la diferencia no privilegia a ninguna.

Para descartar que el emparejamiento fabrique el resultado se volvieron a descargar del catálogo
**46 pares (91 ítems)** y se comprobaron campo a campo: **cero discrepancias**.

---

## D · §4.1 El archivo se contradice a sí mismo

La objeción de fondo a cualquier comparación entre el metadato y una medida sobre el polígono es
que exige una referencia, y toda referencia se puede discutir. El solape de teselas permite
esquivarla por completo: **no hace falta polígono, ni umbral de utilizabilidad, ni matriz de
confusión, ni máscara de referencia.** Si `eo:cloud_cover` describiera el estado del cielo sobre
el suelo, los dos gránulos de un mismo pase declararían el mismo valor. Cuanto se separen es, por
construcción, artefacto del teselado.

Los dos gránulos de un par son el mismo instante: la separación entre sus marcas de sensado tiene
una mediana de **5,60 s** (p90 14,78 s; máximo 20,31 s), y **en 0 de los 6.116 pares** difiere la
línea de procesado. Mismo sensor, mismo segundo, mismo procesador.

**Tabla N — Discrepancia entre los dos gránulos de un mismo pase (6.116 pares).**

| | |
|---|---:|
| Mediana de \|Δ `eo:cloud_cover`\| | **5,31 puntos** |
| Media | 10,98 |
| p75 / p90 / p95 | 15,93 / 30,83 / 41,63 |
| Máximo | **85,88** |
| Coeficiente de concordancia de Lin | 0,878 |
| Sesgo (A − B) | −0,887 (IC 95 % −1,335 a −0,438) |
| Desviación típica de la diferencia | 17,89 |
| Límites de concordancia | −35,96 a +34,18 |
| Coinciden en ≤ 0,1 punto | 16,5 % |
| Coinciden en ≤ 1 punto | 28,6 % |
| Coinciden en ≤ 5 puntos | 48,8 % |

El sesgo es pequeño y su intervalo casi toca el cero: **ninguna de las dos teselas está
sistemáticamente equivocada**. Lo que hay no es un error corregible con una constante, sino
dispersión —desviación típica de 17,9 puntos— alrededor de la coincidencia.

**Tabla N+1 — Con qué frecuencia las dos teselas discrepan sobre conservar la imagen.**

| Umbral del filtro | Discrepan |
|---:|---:|
| ≤ 5 % | 6,20 % |
| ≤ 10 % | **7,59 %** |
| ≤ 20 % | 9,32 % |
| ≤ 30 % | 10,27 % |
| ≤ 50 % | 12,34 % |

Entre el 6 % y el 12 % de las adquisiciones, según el umbral, **se conservan o se descartan según
qué gránulo sirva el catálogo**. La consulta deja de ser determinista, y el usuario no tiene
forma de saberlo: cada gránulo, por separado, es internamente coherente.

**El peor caso** ilustra la magnitud. En el pase `GS2A_20230301T100021_040159`, la tesela
`34VEN` declara **6,65 %** de nubosidad y la `34VFP` declara **91,47 %**. Ambos gránulos tienen
huella válida completa (0,000 % sin dato) y la misma línea de procesado (05.09). Son 84,82 puntos
de diferencia sobre el mismo instante.

### La objeción evidente, y por qué no explica el resultado

Un revisor propondrá de inmediato que los dos gránulos no cubren la misma superficie útil, porque
uno puede estar recortado por el borde de la franja de barrido. No es eso. La correlación entre
\|Δ`eo:cloud_cover`\| y \|Δ`s2:nodata_pixel_percentage`\| es de **0,030** (r² = **0,0009**;
Spearman 0,016), y restringiendo a los **2.715** pares en que ambos gránulos tienen menos del 1 %
sin dato, la mediana **sube** a 5,38 puntos. La huella válida no explica nada.

Lo que sí explica es el **solapamiento real de las dos huellas**, que es el mecanismo previsto.
La mediana de la intersección sobre la unión es de solo 0,047 —dos gránulos vecinos comparten muy
poco terreno— y la concordancia mejora de forma monótona conforme aumenta:

| Intersección sobre unión | n | Mediana \|Δ\| | Concordancia de Lin | Discrepan al 10 % |
|---|---:|---:|---:|---:|
| 0,00 – 0,05 | 3.878 | 6,93 | 0,844 | 8,43 % |
| 0,05 – 0,10 | 1.228 | 3,97 | 0,913 | 7,82 % |
| 0,20 – 0,40 | 593 | 5,39 | 0,939 | 5,90 % |
| **0,40 – 0,70** | **168** | **0,88** | **0,988** | **1,79 %** |

Cuando los dos gránulos comparten de verdad su terreno —el caso de los duplicados entre husos
UTM, 1.272 pares— **coinciden casi exactamente**: concordancia 0,988 y discrepancia del 1,8 %.
Cuando no lo comparten, se separan. El desacuerdo no es ruido del catálogo ni un defecto del
clasificador: **es la firma del soporte**, medida directamente. El valor de r² frente a la
intersección es modesto (0,036) porque la relación es un escalón entre dos regímenes, no una
recta.

**Figura N.** Dos paneles. (a) Las huellas reales de los dos gránulos del pase
`GS2A_20230301T100021_040159`, tomadas de la geometría del catálogo, con la parcela en la franja
compartida y el valor declarado por cada uno. (b) Dispersión de `cc_A` frente a `cc_B` para los
6.116 pares, con la diagonal y los cuadrantes del umbral del 10 % sombreados.

---

## E · §5.1 Primer párrafo

Antes de discutir qué cuesta el filtro conviene fijar qué se ha demostrado sin recurrir a ninguna
referencia discutible. El resultado del solape no compara el metadato con una verdad: compara el
metadato **consigo mismo**. Dos gránulos del mismo pase, separados por cinco segundos y
procesados por la misma versión, describen el mismo suelo con valores que difieren una mediana de
5,3 puntos y que llegan a 85. Entre el 6 % y el 12 % de las adquisiciones cambian de veredicto
según cuál sirva el archivo. Eso basta para establecer que `eo:cloud_cover` **no es una propiedad
del terreno observado sino de la tesela que lo contiene**, y hace de la magnitud del sesgo que
mide el resto del artículo una consecuencia esperable, no una sorpresa.

---

## F · Referencia nueva

Bauer-Marschallinger, B. y Falkner, K. (2023). Wasting petabytes: A survey of the Sentinel-2 UTM
tiling grid and its spatial overhead. *ISPRS Journal of Photogrammetry and Remote Sensing*, 202,
682–690. https://doi.org/10.1016/j.isprsjprs.2023.07.015

**Cómo situarla en la introducción.** Es el trabajo más cercano y conviene citarlo con precisión,
porque delimita exactamente el hueco. Miden el solape de la retícula MGRS como coste de
almacenamiento —superficie inflada un 33 %, de uno a seis gránulos co-localizados— y escriben que
la ambigüedad que eso introduce «no se ha medido hasta ahora». No llegan a abrir los metadatos
por gránulo. Aquí se mide.

---

## Procedencia de cada cifra

Directorio: `…/scratchpad/` (las rutas completas, en el sobre de correcciones).

| Fichero | Qué contiene |
|---|---|
| `overlap_pairs_unique_ftw2y_iou.csv` | los 6.116 pares, una fila por par |
| `overlap_results_ftw2y.json` | barrido por centroide, controles de huella y línea base |
| `overlap_results_poly.json` | barrido por polígono (84 parcelas) |
| `iou_results.json` | estratos de intersección sobre unión |
| `final_tables.json` | reparto por país, reverificación de 46 pares |
| `eocc/task1_identity_*.json` | la identidad sobre 4.430 escenas |
| `eocc/task1c_whole_tile_scl.json` | la comprobación píxel a píxel en 12 teselas |
| `eocc/task45_cross_collection.json` | control de versión del conversor |
