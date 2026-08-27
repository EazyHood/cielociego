# Un filtro que descarta días buenos: sesgo del metadato de nubosidad de Sentinel-2 a escala de predio

**Jhonatan del Río Mejía** · Universidad del Magdalena, Santa Marta, Colombia
· Autor de correspondencia

> El ORCID y la filiación se cargan en el formulario de envío de la revista, no en el
> manuscrito: la revisión es doble anónima.

> **Estado del manuscrito.** Esqueleto en construcción. Todo número entre dobles corchetes está
> **sin medir todavía** y no puede pasar a una versión enviable. Los números sin corchetes ya
> están medidos y su procedencia está en `outputs/`. Esta convención es deliberada: un borrador
> que no distingue lo medido de lo esperado acaba publicando lo esperado.

## Ficha de envío (verificada el 27-ago-2026)

**Destino:** Revista de Teledetección (RAET), Asociación Española de Teledetección / Universitat
Politècnica de València. Scopus, Web of Science ESCI, DOAJ. JIF 2025 = 0,8 · CiteScore = 1,3.
Diamante: **sin cargos de envío ni de publicación**, literal en sus normas. Licencia CC BY-NC-SA
4.0, el autor conserva el copyright.

| Requisito | Qué obliga a hacer |
|---|---|
| Categoría | **Artículo científico** (revisión por pares, ≥2 especialistas). No «Caso práctico»: ese lo evalúa el Consejo Editorial y se pierden los informes de revisores, que valen tanto como la publicación |
| Extensión | **25 páginas DIN-A4 con todo dentro**, resumen, figuras, tablas y referencias incluidas. Los artículos de los números 67 y 68 andan entre 12 y 22: no aspirar al techo |
| Idioma | Español o inglés en el cuerpo, pero **título, resumen y ≥5 palabras clave son obligatorios en los dos idiomas** |
| Revisión | **Doble anónima.** Ver el aviso de abajo, que afecta al texto |
| Formato | Secciones numeradas · **numeración de líneas continua** · referencias, tablas y pies de figura **al final** · referencias alfabéticas y cita autor-año · figuras aparte en TIF/JPG a ≥300 ppi · envío en Word |
| Autor único | **Aceptado, y probado en el número 68 de 2026**: dos de siete trabajos van firmados por una sola persona. No pide carta de aval ni grupo de investigación |
| Tiempos | Decisión comprometida en **3 meses**; ~10 semanas hasta publicación. Sale en enero y julio → la ventana realista es **enero de 2027** |

> ⚠️ **El aviso que decide cómo se redacta.** La revisión es doble anónima y la lista de
> comprobación exige ficheros sin nombres ni referencias identificativas. Este trabajo se apoya en
> una herramienta publicada en una cuenta pública con DOI: **citarla en primera persona
> desanonimiza el manuscrito en la primera página**. Se cita como software de terceros, en tercera
> persona, y el enlace al repositorio va en el fichero suplementario no anónimo y en los
> comentarios al editor, nunca en el cuerpo.

**Para la carta al editor:** en el buscador de la propia revista, `cloud mask Sentinel` devuelve
**cero resultados** y `nubes series temporales` solo tres, el más reciente de 2020 y sobre radar.
RAET no ha publicado nunca nada sobre disponibilidad óptica real ni sobre enmascarado de nubes.
Este artículo no compite con su catálogo: lo completa.

**Anclas que hay que citar sí o sí**, porque son de la propia revista y sostienen el encuadre:
Anaya et al. (2023), `10.4995/raet.2023.17655`, y Anaya et al. (2018), `10.4995/raet.2018.8618`
—bosque del Caribe colombiano y series temporales en el trópico, en esta misma revista—;
Julien y Sobrino (2018), `10.4995/raet.2018.9749`, sobre reconstrucción de series contaminadas por
nube; y sobre todo **Reyes-Díez et al. (2015)**, `10.4995/raet.2015.3316`, que escribe que
*«homogeneous filtering criteria throughout a heterogeneous region may cause the systematic loss of
information»*. Este trabajo demuestra que el criterio homogéneo del metadato de tesela hace
exactamente eso a escala de predio.

**Plan B:** *Earth Science Informatics* (Springer), ruta suscripción, **0 USD** literal, SCIE y
Scopus, acepta autor único. **Plan C:** *Remote Sensing Letters* por la ruta de suscripción.
Preprint previo en EarthArXiv.

---

## Resumen

Los catálogos públicos de Sentinel-2 publican por cada producto un único valor de nubosidad,
`eo:cloud_cover`, calculado sobre la tesela completa de 110 × 110 km. Ese valor es el criterio con
el que casi todos los portales y bibliotecas filtran qué imágenes se descargan. Cuando la unidad
de decisión no es la tesela sino un predio agrícola —cuatro órdenes de magnitud más pequeño— el
filtro deja de ser conservador y pasa a ser sesgado: descarta observaciones útiles mucho más a
menudo de lo que retiene observaciones inservibles.

Este trabajo cuantifica ese sesgo sobre una cohorte de **323 parcelas agrícolas reales de 23
países**, tomadas de un conjunto público de límites parcelarios, y sobre **5.143 pares de parcela
y adquisición medidos**.
Para cada par parcela × adquisición se compara el valor declarado por la tesela con la fracción de
la parcela que la banda de clasificación marca como inservible. El resultado se resume en una
matriz de confusión y en su asimetría: falsos negativos —días despejados sobre el predio que el
filtro tira— por cada falso positivo. Sobre dos predios del Caribe colombiano medidos previamente
la asimetría fue de 37 a 1 (332 contra 9). Sobre la cohorte completa es de **48,5 a 1**, y el
filtro conserva solo el **44,9 %** (IC 95 % 42,0-48,0) de las observaciones que de verdad servían
sobre la parcela: el caso original no era una anomalía. El sesgo empeora cuanto más estricto es el
filtro —al 5 % la asimetría llega a 99,7— de modo que el usuario más cuidadoso es el más
perjudicado.

Como subproducto se documenta y cuantifica un artefacto del propio archivo: la misma adquisición
se sirve reprocesada bajo varias líneas base, cada copia declara una nubosidad distinta, y el
instante de sensado difiere entre copias, de modo que deduplicar por fecha falla en silencio.

**Palabras clave:** Sentinel-2, nubosidad, metadatos, escala, agricultura de precisión, trópico.

---

## 1. Introducción

*(≈ 700 palabras. Estructura fijada; falta redactar sobre las citas verificadas.)*

**Párrafo 1 — el problema práctico.** Quien trabaja con series ópticas sobre un predio no descarga
el archivo entero: filtra. Y filtra por el único número de nubosidad que el catálogo ofrece por
producto, `eo:cloud_cover`. Ese número describe la tesela.

**Párrafo 2 — por qué el desajuste de soporte importa.** Una tesela de Sentinel-2 cubre 12.100 km².
Un predio de 73,5 ha es el 0,006 % de esa superficie. La nube es irregular a escala de kilómetro,
así que el predio o está debajo de la nube o no lo está: la distribución de la fracción nubosa sobre
el predio es fuertemente bimodal mientras que la de la tesela no lo es. Un estimador insesgado sobre
la tesela no tiene por qué serlo sobre el predio, y el error no tiene por qué ser simétrico.

**Párrafo 3 — qué se ha hecho ya, y qué no.** Hay que delimitarlo con precisión o el revisor
supondrá que no se conoce el estado del arte:

- La calidad de las **máscaras de nube por píxel** está bien estudiada y comparada: Foga et al.
  (2017), *Remote Sensing of Environment*, `10.1016/j.rse.2017.03.026`, y el ejercicio
  internacional CMIX, Skakun et al. (2022), `10.1016/j.rse.2022.112990`. Evalúan el algoritmo, no
  el resumen de escena usado como filtro de consulta.
- La **disponibilidad de observaciones libres de nube** se ha cuantificado a escala regional y
  global: Sudmanns et al. (2019), `10.1080/17538947.2019.1572799`; Flores-Anderson et al. (2023),
  *Scientific Data*, `10.1038/s41597-023-02439-x`.
- **El vecino más cercano, y hay que citarlo en el primer párrafo:** Tiede, Sudmanns, Augustin y
  Baraldi (2021), *Remote Sensing of Environment* 252, 112163, `10.1016/j.rse.2020.112163`
  (37 citas en OpenAlex, agosto de 2026). Escriben, literal: *«Almost all optical remote sensing
  data access portals rely to some degree on a cloud cover filter»*, y que eso produce
  *«a lot of "hidden" data for very high altitude areas when each image's estimated cloud cover is
  used as an automated selection criterion»*. Su causa es un umbral sobre banda única en lugar de
  una firma multibanda; su alcance, declarado por ellos en la última frase del resumen, es
  *«very high altitude areas»*, con seis sitios de prueba: dos en los Andes, dos en el Himalaya y
  dos en los Alpes. Su unidad de análisis es el **gránulo completo**, comparado contra la máscara
  de un sistema experto. No hay polígono de usuario, ni parcela, ni matriz de confusión.

> ⚠️ **Corrección que hay que llevar bien al texto.** Un análisis previo describió la asimetría de
> este trabajo como «la contraria» a la de Tiede. **Es falsa.** Los 332 falsos negativos son
> observaciones **útiles sobre el predio que el filtro descarta**: la misma dirección del daño que
> describe Tiede, imágenes buenas tiradas por el umbral. Lo que cambia no es el signo, es la
> **causa y la unidad**: Tiede documenta un sesgo del algoritmo en un terreno particular; aquí se
> mide un desajuste de soporte que no depende del terreno y se expresa como función del tamaño de
> la parcela. Escribirlo como «dirección contraria» sería un error de bulto que un revisor que
> haya leído a Tiede detecta en la primera lectura.

**Párrafo 4 — el hueco y la contribución.** Nadie ha evaluado el metadato de nubosidad **como
filtro** contra la nubosidad observada sobre un polígono de parcela, ni ha construido esa matriz de
confusión, ni la ha expresado como función del tamaño del área de interés. En duplicados de
reprocesado el hueco es total: **no hay literatura revisada por pares** que los cuantifique, solo
foros, documentación del operador y una frase de método en un preprint. Eso es lo que aquí se
aporta, junto con el conjunto de datos que permite rehacerlo.

**Párrafo 5 — qué NO es este trabajo.** No es una evaluación de la máscara de nube. Los dos números
que se comparan descienden de la misma clasificación; ese es justamente el diseño. Lo que se mide
es lo que se pierde al usar un estimador calculado sobre 12.100 km² para decidir sobre una
superficie cuatro órdenes de magnitud menor. Mismo estimador, distinto soporte.

---

## 2. Datos

### 2.1 Catálogo óptico

Earth Search v1 (Element 84, sobre AWS Open Data), colección `sentinel-2-l2a`. Acceso público sin
credenciales ni cuota. Los productos son COG en el bucket público `sentinel-cogs` y se leen **por
ventana**, nunca la escena entera. Datos Copernicus, acceso libre, pleno y abierto.

Se registra la fecha de consulta del catálogo y la versión de la colección, porque el archivo
cambia: la ESA anunció el borrado de productos de líneas base antiguas. Medido el 27 de agosto de
2026, **las copias siguen presentes**: el porcentaje que se reporta es un dato de esa fecha.

### 2.2 Fracción inservible sobre el polígono

Banda de clasificación de escena (SCL) a 20 m, recortada al polígono. Se declaran dos definiciones
de «inservible» y se reportan las dos: la **estricta** (sin dato, saturado, sombra de nube, nube
probable, nube segura, cirro) y la **amplia**, que añade la sombra orográfica. Una parcela con
menos de 25 píxeles se marca: por debajo de eso el porcentaje se mueve a saltos de cuatro puntos y
el borde del polígono pesa más que su interior.

### 2.3 Cohorte de parcelas

Fields of The World (Kerner Lab, Source Cooperative). Las máscaras de instancia se vectorizan para
obtener límites parcelarios reales; se descartan las parcelas que tocan el borde del recorte,
porque las corta el teselado y no el agricultor. Los países cuya licencia prohíbe el uso comercial
—Letonia, Portugal y Sudáfrica— se excluyen por nombre. Selección por paso fijo, sin semilla
aleatoria, para que la cohorte sea reproducible a partir del código.

A la cohorte se añaden los dos polígonos del Magdalena (73,5 y 284,1 ha) ya publicados en el
repositorio con DOI, que son el caso que originó la pregunta y el único anclaje en trópico húmedo
del Caribe colombiano.

La cohorte quedó en **323 parcelas de 23 países**, de **0,20 a 255,41 ha**, con mediana de
**1,60 ha**. Las parcelas no se eligen por paso fijo sobre la lista ordenada sino **llenando los
tramos de tamaño que el análisis reporta**: un paso fijo sigue la distribución del país, que es
abrumadoramente pequeña, y dejaba los estratos grandes casi vacíos. Incluye trópico: Ruanda, Kenia, India, Vietnam, Camboya y Brasil. El extremo grande lo
aporta el predio propio del Magdalena, porque un recorte de la fuente mide un kilómetro de lado y
casi cualquier parcela mayor de unas 20 ha toca el borde y se descarta por el criterio anterior.

**Sesgo de selección que hay que declarar:** el listado del repositorio se lee **una página de mil
claves por país**. Austria sola tiene más de 400.000 máscaras, así que un listado exhaustivo agota
cientos de peticiones en un país y nunca llega al trópico. La consecuencia es que la selección
recorre la cabeza lexicográfica de los recortes de cada país, no el país entero.

La composición por país figura en la Tabla 1.

---

## 3. Métodos

### 3.1 Deduplicación por línea de procesado

El catálogo sirve la misma adquisición reprocesada bajo varias líneas base. La identidad física de
una adquisición es (plataforma, instante de sensado, órbita, tesela); `N####` es solo la versión
del procesador. Se deduplica por `s2:product_uri` y se conserva la línea base más alta.

Deduplicar por fecha **no funciona**: las copias difieren en el instante declarado. Sobre el par
real de la tesela 18PWT del 25 de marzo de 2019, las dos copias declaran 2,58 % y 3,40 % de
nubosidad y sus marcas de tiempo distan 23,9 s.

### 3.2 El filtro, la verdad y la matriz

- **Filtro:** se conserva la adquisición si `eo:cloud_cover ≤ T`. Valor de referencia T = 10 %,
  que es el que usa el trabajo previo sobre los dos predios y mantiene comparables caso y cohorte.
- **Verdad para el predio:** la adquisición es útil si la fracción inservible sobre el polígono es
  `≤ U`. Valor de referencia U = 10 %.
- **Falso negativo:** útil para el predio y descartada por el filtro. Es el error caro: se pierde
  una observación que existía.
- **Falso positivo:** conservada por el filtro e inservible sobre el predio. Cuesta cómputo, no
  información.
- **Asimetría:** falsos negativos por cada falso positivo.

Ambos umbrales son parámetros, nunca constantes escondidas en una conclusión: se reporta la rejilla
completa T × U. Un solo par de umbrales invita a la respuesta «elegiste los números que te
convenían».

### 3.3 Estratificación

La matriz se reporta también por tramos de superficie (< 1, 1–5, 5–20, 20–100, 100–500 ha),
por país y por nubosidad declarada de la tesela. La estratificación por superficie es la que
convierte el hallazgo en regla: si la tasa de falsos negativos crece cuando la parcela encoge, el
sesgo es del desajuste de soporte y no del clima de una región.

### 3.4 Lo que no se hace

No se valida contra observación en tierra. No hay cámara de nubes ni ceilómetro sobre estos predios,
y el trabajo no lo necesita: la pregunta es sobre la coherencia interna entre dos resúmenes del
mismo producto a dos escalas, no sobre cuál acierta más frente al cielo real.

---

## 4. Resultados

*(Los apartados están fijados; los números salen de `outputs/cohort_*.csv`.)*

### 4.1 Cuánto del archivo son copias, y de qué depende

Sobre la cohorte completa (323 parcelas, 2023-2024): **93.072 ítems**, de los cuales **834 son
copias de reprocesado (0,9 %)**. La mayor discrepancia de nubosidad declarada entre dos copias de
la misma adquisición es de **52,10 puntos porcentuales**, y la mayor razón entre las dos cifras
declaradas es de **285,7 veces**.

Sobre el predio del Magdalena y el archivo completo 2019-2026, medido el 27 de agosto de 2026:
**822 ítems, 603 adquisiciones únicas, 219 copias (26,6 %)**, con doce líneas de procesado
conviviendo (211, 212, 213, 214, 300, 301, 400, 500, 509, 510, 511, 512) y una discrepancia máxima
de 25,64 puntos (24,22 % contra 49,86 %).

El contraste entre 0,9 % y 26,6 % **no es una contradicción, es el resultado**: la duplicación no
es uniforme, se concentra en las adquisiciones antiguas, que son las que han pasado por más
reprocesados. Una serie temporal larga hereda mucha más duplicación que una corta, y es justo la
serie larga la que se usa para fenología y tendencias.

Desglosada por año de adquisición sobre el predio del Magdalena, la duplicación no es una constante
sino un escalón:

| Año | Ítems | Adquisiciones únicas | Copias | % copias |
|---:|---:|---:|---:|---:|
| 2019 | 130 | 72 | 58 | 44,6 % |
| 2020 | 143 | 72 | 71 | 49,7 % |
| 2021 | 158 | 73 | 85 | **53,8 %** |
| 2022 | 73 | 72 | 1 | 1,4 % |
| 2023 | 74 | 72 | 2 | 2,7 % |
| 2024 | 74 | 74 | 0 | 0,0 % |
| 2025 | 102 | 102 | 0 | 0,0 % |
| 2026 | 68 | 66 | 2 | 2,9 % |
| **Total** | **822** | **603** | **219** | **26,6 %** |

En 2021 **más de la mitad de lo que devuelve el catálogo son copias de una adquisición que ya
estaba**. Desde 2022 prácticamente desaparecen. Eso explica por qué la cohorte, medida sobre
2023-2024, da un 0,9 %: las dos cifras no se contradicen, describen el mismo escalón desde los dos
lados.

La consecuencia práctica es la que importa: quien construye una serie que llega antes de 2022
—que es lo que se hace para fenología, tendencias o líneas base— hereda un catálogo donde hasta la
mitad de los ítems son copias con nubosidad declarada distinta, y deduplicar por fecha no las junta.
Quien trabaja solo con los dos últimos años no ve el problema y no tiene motivo para sospecharlo.

**Sobre la caducidad del hallazgo.** La ESA anunció el borrado de productos de líneas base
antiguas. Medido hoy, las copias **siguen presentes** en el catálogo público: el 26,6 % es un dato
del 27 de agosto de 2026, no un dato histórico. Se fecha y se versiona la consulta.

### 4.2 La matriz, agrupada

Sobre **5.143 pares parcela × adquisición medidos** (25 lecturas fallaron y se cuentan aparte),
con el filtro de referencia —se conserva la adquisición si la tesela declara ≤ 10 % de nube— y la
parcela considerada utilizable con ≤ 10 % de su superficie inservible:

| | Adquisición útil sobre la parcela | Adquisición inservible |
|---|---:|---:|
| **El filtro la conserva** | 475 | **12** (falso positivo) |
| **El filtro la descarta** | **582** (falso negativo) | 2.196 |

- **Exhaustividad: 0,449**, IC 95 % [0,420, 0,480]. El filtro por metadato de tesela **deja pasar
  menos de la mitad de las observaciones que de verdad servían sobre la parcela.**
- **Asimetría: 48,5 falsos negativos por cada falso positivo.**
- 1.878 filas quedan por debajo del suelo de píxeles y se reportan como estrato aparte (§4.6).

Sobre los dos predios del Magdalena la asimetría publicada fue de 37 a 1. Sobre 323 parcelas de
23 países es de **48,5 a 1**: el caso original no era una anomalía, y si algo se quedaba corto.

### 4.3 La dependencia del tamaño, ajustada por el cielo

La tabla por tramos muestra la exhaustividad creciendo con el tamaño de la parcela entre 1 y 100 ha
—0,429 → 0,492 → 0,520— y cayendo a 0,273 en el tramo de 100-500 ha. Ese último punto es **una
sola parcela** situada en trópico húmedo, así que tamaño y clima están confundidos y una línea de
tendencia trazada sobre esos puntos no sería evidencia de nada.

La única forma de separarlos desde el escritorio es un modelo que lleve los dos. Se plantea la
pregunta del artículo de forma directa: **entre las adquisiciones que el filtro descarta, ¿la
probabilidad de que la parcela estuviera despejada de verdad depende de su tamaño, con la nubosidad
declarada por la tesela mantenida constante?** Se ajusta una regresión logística sobre las 2.778
filas rechazadas, de las que 582 (el 21,0 %) son falsos negativos, con la nubosidad de la tesela y
el logaritmo decimal de la superficie como predictores, ambos centrados.

| Término | Coef. | e.e. | z | p | IC 95 % |
|---|---:|---:|---:|---:|---|
| Constante | −1,9797 | 0,0741 | −26,71 | < 0,001 | [−2,125, −1,834] |
| Nubosidad de la tesela (0-1) | −5,9858 | 0,2348 | −25,49 | < 0,001 | [−6,446, −5,526] |
| log₁₀ superficie (ha) | −0,3709 | 0,1568 | −2,36 | 0,018 | [−0,678, −0,064] |

**La razón de probabilidades por cada factor diez de superficie es 0,690 (IC 95 % 0,508–0,938).**
Es decir: manteniendo el cielo constante, **cuanto más pequeña es la parcela, mayor es la
probabilidad de que una adquisición descartada estuviera en realidad despejada sobre ella**. Es
exactamente la dirección que predice el desajuste de soporte, y el intervalo excluye el 1.

El modelo confirma además, en el conjunto completo de 3.265 filas, que a igualdad de nubosidad
declarada una parcela más grande es menos probable que esté enteramente despejada (razón de
probabilidades 0,686; IC 95 % 0,509–0,925). Geométricamente es lo esperable —más superficie es más
oportunidad de encontrarse una nube— y explica por qué la tabla por tramos, que no ajusta por el
cielo, es un instrumento demasiado grueso para esta pregunta. El término de interacción entre
nubosidad y tamaño no resulta distinguible de cero (p = 0,15), de modo que no se afirma que la
*forma* de la relación cambie con el tamaño, solo su nivel.

### 4.4 Sensibilidad a los umbrales

La asimetría no es un artefacto del par de umbrales elegido (Tabla 4). Se conserva en toda la
rejilla y solo se invierte cuando el filtro se afloja hasta el 50 %, que equivale a no filtrar. El
patrón relevante es el contrario del que cabría esperar: cuanto más estricto es el filtro, peor es
el sesgo. Al 5 % de nubosidad declarada la asimetría alcanza 99,7 y la exhaustividad baja a 0,340.
El usuario que exige imágenes limpias es el peor servido.

### 4.5 ¿Sirve algún otro campo del catálogo?

Antes de recomendar una lectura conviene descartar lo que no cuesta nada. La respuesta del catálogo
trae, además de la nubosidad de escena, una docena de porcentajes por tesela. Se evalúan como
puntuaciones alternativas —menor significa más limpio— sobre las 3.265 filas legibles: la nube de
alta probabilidad; la nube opaca (alta + media probabilidad + cirro fino); esa misma suma más
sombra de nube, ausencia de dato y píxeles saturados o defectuosos, que es **el análogo exacto de
la definición empleada sobre la parcela, calculado sobre la tesela**; y la variante sin ausencia de
dato.

Cada candidata se compara de dos formas. Con el área bajo la curva ROC, que es independiente del
umbral y evita la discusión sobre si los umbrales se eligieron a conveniencia. Y con la
exhaustividad a **presupuesto igualado de falsos positivos**: como los umbrales no son comparables
entre puntuaciones con unidades distintas, cada una se sitúa en el umbral que admite el mismo
número de adquisiciones inservibles que la de referencia (doce) y se comparan por cuántas útiles
recuperan.

| Puntuación (todas gratuitas) | AUC | Exhaustividad a presupuesto igual |
|---|---:|---:|
| `eo:cloud_cover` (referencia) | 0,939 | 0,462 |
| Nube de alta probabilidad | 0,885 | 0,028 |
| Nube opaca + cirro | 0,939 | 0,462 |
| Mismas clases que en la parcela | 0,910 | 0,364 |
| Mismas clases, sin ausencia de dato | 0,941 | 0,423 |
| *Fracción recortada al polígono (cuesta una lectura)* | *1,000* | *1,000* |

**Ninguna alternativa gratuita mejora a la de referencia de forma apreciable.** La mejor obtiene un
AUC de 0,941 frente a 0,939, diferencia sin consecuencia práctica, y a presupuesto igualado
recupera menos. Es un resultado negativo con contenido: **el problema no es qué campo del catálogo
se elige, sino que cualquier campo de tesela describe el soporte equivocado.** Reordenar los
metadatos no devuelve las observaciones perdidas.

### 4.6 Control: el umbral de píxeles no fabrica el resultado

Repitiendo la matriz sin apartar las parcelas por debajo del umbral de píxeles, sobre las mismas
5.143 filas, la exhaustividad es 0,439 y la asimetría 49,4, frente a 0,449 y 48,5 con el umbral
aplicado. El hallazgo no depende de esa decisión metodológica.

### 4.7 El estrato que esta banda no puede medir

De las 5.143 filas medidas, 1.878 corresponden a parcelas con menos de 25 píxeles de la banda de
clasificación, es decir por debajo de una hectárea. No se descartan por sospechosas sino por
incontables: con ocho píxeles la fracción inservible se mueve a saltos de doce puntos. Es una
limitación del instrumento y no del método, y afecta a buena parte de las parcelas de los países
con estructura agraria más fragmentada de la muestra. Conviene subrayar la consecuencia, porque
apunta en la misma dirección que el modelo de la sección 4.3: **el estrato peor servido por el
metadato de tesela es también el que peor puede medirse con la banda que lo evaluaría.**

---

## 5. Discusión

### 5.1 Qué significa la asimetría para quien decide

Perder un día despejado y procesar un día nublado no cuestan lo mismo. En una serie de fenología
sobre un predio, el día perdido es información que existía y que no se recupera, mientras que el día
nublado que se cuela se descarta en el paso siguiente a coste de cómputo. Que el error del filtro
sea casi cincuenta veces más frecuente en la dirección cara es, por tanto, el resultado con
consecuencias.

El hallazgo dialoga directamente con Reyes-Díez et al. (2015), que advierten de que criterios de
filtrado homogéneos aplicados sobre una región heterogénea pueden causar pérdida sistemática de
información. Aquí se muestra que el criterio homogéneo del metadato de tesela hace exactamente eso a
escala de predio, se cuantifica cuánto, y se añade que el daño no se reparte por igual: recae sobre
las parcelas pequeñas, que son la mayoría de las explotaciones del mundo.

### 5.2 Qué hacer en su lugar

La sección 4.5 descarta la salida barata: ninguna combinación de los porcentajes que el catálogo ya
entrega mejora a `eo:cloud_cover`. Queda por decidir entre dos estrategias reales, y la elección se
puede plantear con números.

**Estrategia A, seguir filtrando por metadato pero aflojando el umbral.** Con la mejor puntuación
gratuita, alcanzar el 90 % de las adquisiciones útiles exige subir el umbral hasta cerca del 70 % de
nubosidad declarada y aceptar 435 falsos positivos, frente a los 12 del umbral del 10 %. Para el
95 % hacen falta 621. Dicho de otro modo: **cada observación útil adicional se compra al precio de
aproximadamente una inservible**, y el filtro deja de merecer el nombre.

**Estrategia B, decidir con la fracción recortada al polígono.** Recupera por construcción el 100 %
de las adquisiciones útiles y no admite ninguna inservible bajo el mismo criterio. Su coste es una
lectura por ventana de la banda de clasificación: sobre esta cohorte, 5.143 lecturas tardaron 206 s
con doce hilos, es decir **40 ms por adquisición**, sobre datos públicos y sin credenciales. Para un
predio con dos años de archivo son unas ciento cincuenta lecturas: seis segundos.

La recomendación operativa es, por tanto, la combinación de las dos. **Usar el metadato de tesela
solo como criba grosera —descartar únicamente lo que declara nubosidad muy alta— y resolver cada
superviviente con la fracción recortada al polígono.** El metadato conserva su utilidad, que es
evitar leer lo que no tiene ninguna posibilidad; lo que no debe hacer es decidir.

Conviene añadir un matiz que el propio análisis obliga a reconocer: como ordenador, la nubosidad de
escena no es mala. Su área bajo la curva es 0,939, de modo que **clasifica bien y decide mal**. El
problema no está en la información que contiene sino en el punto de operación al que se la somete
por costumbre, y esa distinción es la que permite seguir usándola sin confiarle la decisión.

### 5.3 Límites

Los límites del trabajo son cinco y conviene enunciarlos sin rodeos.

Primero, las dos magnitudes comparadas descienden de la misma clasificación, de modo que lo que se
mide es el efecto de la agregación espacial y no la calidad del enmascarado. Un error del propio
clasificador afectaría a ambos lados de la comparación y no crearía la asimetría observada.

Segundo, el artefacto de los duplicados puede caducar: si el operador completa el borrado de líneas
base antiguas, el porcentaje medido pasará a ser un hecho histórico. Por eso se fecha la consulta y
se conserva la lista de identificadores.

Tercero, la cohorte hereda el sesgo de muestreo de la fuente de límites parcelarios y de la lectura
parcial de su listado, descrita en la sección 2.3.

Cuarto, el trópico húmedo está representado por pocas parcelas y el tramo de mayor superficie por
una sola, razón por la cual la dependencia del tamaño se estima con un modelo que ajusta por la
nubosidad declarada en lugar de leerse de la tabla por tramos.

Quinto, la ventana temporal de la cohorte es de dos años, elegida para acotar el coste de lectura.
La duplicación de reprocesado, que es un fenómeno de archivo, se mide aparte sobre la serie completa
porque dos años no la contienen.

---

## 6. Conclusión

El valor de nubosidad que los catálogos públicos publican por producto describe una tesela de
12.100 km² y se emplea de forma rutinaria para decidir sobre superficies cuatro órdenes de magnitud
menores. Medido sobre 323 parcelas de 23 países y 5.143 pares de parcela y adquisición, ese uso
conserva el 44,9 % de las observaciones realmente utilizables y descarta 48,5 observaciones buenas
por cada mala que retiene.

El daño no se reparte por igual. Manteniendo constante la nubosidad que declara la tesela, **por
cada factor diez de reducción de la superficie de la parcela la probabilidad de que una adquisición
descartada estuviera en realidad despejada se multiplica por 1,45** (razón de probabilidades 0,690
por factor diez de aumento; IC 95 % 0,508–0,938). El estrato peor servido es el de las
explotaciones pequeñas, que son la mayoría en buena parte del mundo, y es también el que peor puede
medirse con la banda de clasificación a 20 m.

Ninguna recombinación de los porcentajes que el propio catálogo entrega corrige el problema: la
mejor alternativa gratuita alcanza un área bajo la curva de 0,941 frente a 0,939 de la referencia.
Como ordenador, la nubosidad de escena es buena; lo que falla es el punto de operación al que se la
somete por costumbre. La recomendación práctica es en consecuencia doble: **usar el metadato de
tesela solo como criba grosera y resolver cada superviviente con la fracción de nube recortada al
polígono**, que cuesta 40 ms por adquisición sobre datos públicos y sin credenciales.

Por último, cualquier serie temporal que se remonte antes de 2022 debe deduplicarse por
identificador de producto y no por fecha: en 2021 más de la mitad de los ítems que devuelve el
catálogo son copias de reprocesado de una adquisición ya presente, y esas copias declaran
nubosidades que difieren hasta en 52 puntos porcentuales.

---

## Disponibilidad de datos y código

La herramienta de medición es de código abierto, con licencia MIT, y está archivada con DOI. La
tabla ordenada resultante —una fila por parcela y adquisición, con la nubosidad declarada por la
tesela, la fracción inservible sobre el polígono, el número de píxeles y el identificador de
producto— se deposita con licencia CC BY 4.0. No se redistribuyen los límites parcelarios de las
fuentes cuya licencia prohíbe el uso comercial: se publican los identificadores y el guion que los
reconstruye. Las referencias concretas se aportan en el fichero suplementario no anónimo, para no
comprometer la revisión doble ciega.

## Agradecimientos

Contiene datos Copernicus Sentinel modificados. Los límites parcelarios proceden de un conjunto
público de fronteras agrícolas.

## Declaración sobre el uso de herramientas de inteligencia artificial

Durante la preparación de este trabajo se emplearon asistentes de programación basados en modelos
de lenguaje para escribir y revisar el código de adquisición y análisis, para redactar y depurar el
texto, y para localizar y verificar bibliografía. Todo el diseño experimental, la definición de las
métricas, la interpretación de los resultados y las decisiones sobre qué se afirma y qué no son
responsabilidad del autor, que ha comprobado una a una las cifras que aparecen en el manuscrito
contra las salidas del código publicado. Ninguna cifra procede de la memoria de un modelo: todas se
recalculan ejecutando el repositorio. Las herramientas no figuran como autoras porque no pueden
asumir responsabilidad sobre el contenido.
