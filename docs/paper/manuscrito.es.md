# Un filtro que descarta días buenos: sesgo del metadato de nubosidad de Sentinel-2 a escala de predio

**Jhonatan del Río Mejía** · Universidad del Magdalena, Santa Marta, Colombia
· Autor de correspondencia · ORCID [[PENDIENTE: abrir ORCID]]

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
cambia: la ESA anunció el borrado de productos de líneas base antiguas. [[PENDIENTE: fecha y
alcance exacto del borrado, y si los duplicados siguen presentes hoy.]]

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

La cohorte quedó en **232 parcelas de 23 países**, de **0,20 a 255,41 ha**, con mediana de
**0,79 ha**. Incluye trópico: Ruanda, Kenia, India, Vietnam, Camboya y Brasil. El extremo grande lo
aporta el predio propio del Magdalena, porque un recorte de la fuente mide un kilómetro de lado y
casi cualquier parcela mayor de unas 20 ha toca el borde y se descarta por el criterio anterior.

**Sesgo de selección que hay que declarar:** el listado del repositorio se lee **una página de mil
claves por país**. Austria sola tiene más de 400.000 máscaras, así que un listado exhaustivo agota
cientos de peticiones en un país y nunca llega al trópico. La consecuencia es que la selección
recorre la cabeza lexicográfica de los recortes de cada país, no el país entero.

[[PENDIENTE: tabla 1 — parcelas por país, mediana y rango de superficie, y régimen de nubosidad.]]

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

- **Filtro:** se conserva la adquisición si `eo:cloud_cover ≤ T`. Valor de referencia T = 20 %.
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

La matriz se reporta también por tramos de superficie (< 1, 1–5, 5–20, 20–100, 100–500, ≥ 500 ha),
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

Sobre la cohorte completa (232 parcelas, 2023-2024): **60.688 ítems**, de los cuales **547 son
copias de reprocesado (0,9 %)**. La mayor discrepancia de nubosidad declarada entre dos copias de
la misma adquisición es de **43,23 puntos porcentuales**, y la mayor razón entre las dos cifras
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

### 4.3 La regla en función del tamaño

| Tramo | n | Exhaustividad | IC 95 % | FN | FP |
|---|---:|---:|---|---:|---:|
| 1-5 ha | 2.060 | 0,429 | [0,392, 0,466] | 393 | 7 |
| 5-20 ha | 1.077 | 0,492 | [0,439, 0,546] | 169 | 5 |
| 20-100 ha | 112 | 0,520 | [0,335, 0,700] | 12 | 0 |
| 100-500 ha | 16 | 0,273 | [0,097, 0,566] | 8 | 0 |

La exhaustividad **crece con el tamaño de la parcela** en el rango de 1 a 100 ha —0,429 → 0,492 →
0,520—, que es la dirección que predice el desajuste de soporte. Ahora bien, hay que decir tres
cosas y no una:

1. **El efecto es real pero moderado** en ese rango: nueve puntos de exhaustividad entre una
   parcela de 1 ha y una de 100, con intervalos que se solapan entre tramos contiguos.
2. **El último tramo rompe la monotonía y no es un contraejemplo, es un confundido.** Las 16
   observaciones de 100-500 ha son **una sola parcela**, la del Magdalena, en trópico húmedo del
   Caribe. Ahí la exhaustividad cae a 0,273 porque el cielo es peor, no porque la parcela sea
   grande. Con una parcela no se separa el tamaño del clima, y presentarlo como efecto de tamaño
   sería exactamente el error que este artículo denuncia en otros.
3. **Lo que sí sostiene la cohorte, y con holgura, es la asimetría**, que es grande en todos los
   tramos y en todos los umbrales.

[[PENDIENTE: para separar tamaño de clima hace falta un modelo con la nubosidad media de la tesela
como covariable, o más parcelas grandes en climas templados. Es la extensión obvia y honesta.]]

### 4.4 Sensibilidad a los umbrales

La asimetría no es un artefacto del par de umbrales elegido. Se conserva en toda la rejilla y solo
se invierte cuando el filtro se afloja hasta el 50 %, que es tanto como no filtrar:

| Filtro de tesela | Límite de inservible | FN | FP | Exhaustividad | Asimetría |
|---:|---:|---:|---:|---:|---:|
| 5 % | 5 % | 678 | 11 | 0,344 | 61,6 |
| 5 % | 10 % | 698 | 7 | 0,340 | 99,7 |
| 10 % | 5 % | 562 | 16 | 0,456 | 35,1 |
| **10 %** | **10 %** | **582** | **12** | **0,449** | **48,5** |
| 20 % | 10 % | 469 | 59 | 0,556 | 7,9 |
| 30 % | 10 % | 355 | 95 | 0,664 | 3,7 |
| 50 % | 10 % | 202 | 243 | 0,809 | 0,8 |

Cuanto más estricto es el filtro —que es como lo usa quien quiere imágenes limpias— **peor es el
sesgo**: al 5 % la asimetría llega a 99,7 y la exhaustividad baja a 0,340. El usuario cuidadoso es
el más perjudicado.

### 4.5 Control: el suelo de píxeles no fabrica el resultado

Repitiendo la matriz **sin** apartar las parcelas pequeñas, sobre las 5.143 filas medidas:
exhaustividad **0,439** y asimetría **49,4**, contra 0,449 y 48,5 con el suelo puesto. El hallazgo
no depende de esa decisión metodológica.

### 4.6 El estrato que no se puede medir con esta banda

1.878 de las 5.143 filas corresponden a parcelas con menos de 25 píxeles de la banda de
clasificación, es decir por debajo de una hectárea. No se descartan por sospechosas sino por
incontables: con ocho píxeles la fracción inservible se mueve a saltos de doce puntos. Es una
limitación del instrumento, no del método, y afecta a la mitad de las parcelas de un país como
Ruanda o Kenia. [[PENDIENTE: decir si con la banda de 10 m del propio producto —que no trae
clasificación— o con un enmascarador externo se podría bajar ese suelo.]]

---

## 5. Discusión

**5.1 Qué significa la asimetría para quien decide.** Perder un día despejado y procesar un día
nublado no cuestan lo mismo. En una serie de fenología sobre un predio, el día perdido es
información que existía y no se recupera; el día nublado de más se descarta en el siguiente paso.

**5.2 Qué recomendar en su lugar.** [[PENDIENTE: comparar en la misma tabla al menos tres filtros
alternativos disponibles sin trabajo de campo, y recomendar uno con su umbral.]] El artículo tiene
que terminar en una regla accionable, no en una queja.

**5.3 Límites.**
- Las dos magnitudes comparadas descienden de la misma clasificación (§1, párrafo 5).
- El artefacto de los duplicados puede caducar: si la ESA completa el borrado de líneas base
  antiguas, el porcentaje medido pasa a ser un hecho histórico. Por eso se fecha la consulta y se
  versiona el catálogo.
- La cohorte hereda el sesgo de muestreo de la fuente de límites parcelarios.
- El trópico húmedo está representado por pocos predios. [[PENDIENTE: cuántos, exactamente.]]

---

## 6. Conclusión

[[PENDIENTE: una sola frase con el número, del estilo «por debajo de X ha el filtro por metadato de
tesela descarta más del Y % de las observaciones útiles».]]

---

## Disponibilidad de datos y código

Código: `https://github.com/EazyHood/cielociego`, licencia MIT.
Versión archivada con DOI: `10.5281/zenodo.22132250`.
Datos derivados de la cohorte: tabla ordenada, una fila por parcela × adquisición, depositada en
Zenodo con DOI propio y licencia CC BY 4.0. No se redistribuyen los límites parcelarios de las
fuentes con licencia no comercial: se publican los identificadores y el script que los reconstruye.

## Agradecimientos

Datos Copernicus Sentinel modificados. Límites parcelarios de Fields of The World (Kerner Lab).

## Declaración sobre el uso de herramientas de IA

[[PENDIENTE: redactar. La revista puede exigirla y arXiv la exige; conviene escribirla explícita y
sin adornos.]]
