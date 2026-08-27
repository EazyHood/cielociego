# Un filtro que descarta días buenos: sesgo del metadato de nubosidad de Sentinel-2 a escala de predio

**Jhonatan del Río Mejía** · Universidad del Magdalena, Santa Marta, Colombia
· Autor de correspondencia · ORCID [[PENDIENTE: abrir ORCID]]

> **Estado del manuscrito.** Esqueleto en construcción. Todo número entre dobles corchetes está
> **sin medir todavía** y no puede pasar a una versión enviable. Los números sin corchetes ya
> están medidos y su procedencia está en `outputs/`. Esta convención es deliberada: un borrador
> que no distingue lo medido de lo esperado acaba publicando lo esperado.

**Revista destino:** Revista de Teledetección (AET / Universitat Politècnica de València).
Indexada en Scopus y ESCI, publica en español, sin cargos de publicación.
Alternativas por la ruta gratuita: *Remote Sensing Letters* (ruta suscripción), *IEEE GRSL*,
*Int. J. Applied Earth Observation and Geoinformation*. Preprint previo en EarthArXiv.

---

## Resumen

Los catálogos públicos de Sentinel-2 publican por cada producto un único valor de nubosidad,
`eo:cloud_cover`, calculado sobre la tesela completa de 110 × 110 km. Ese valor es el criterio con
el que casi todos los portales y bibliotecas filtran qué imágenes se descargan. Cuando la unidad
de decisión no es la tesela sino un predio agrícola —cuatro órdenes de magnitud más pequeño— el
filtro deja de ser conservador y pasa a ser sesgado: descarta observaciones útiles mucho más a
menudo de lo que retiene observaciones inservibles.

Este trabajo cuantifica ese sesgo sobre una cohorte de [[N]] parcelas agrícolas reales de
[[K]] países, tomadas de un conjunto público de límites parcelarios, y sobre [[M]] adquisiciones.
Para cada par parcela × adquisición se compara el valor declarado por la tesela con la fracción de
la parcela que la banda de clasificación marca como inservible. El resultado se resume en una
matriz de confusión y en su asimetría: falsos negativos —días despejados sobre el predio que el
filtro tira— por cada falso positivo. Sobre dos predios del Caribe colombiano medidos previamente
la asimetría fue de **37 a 1** (332 contra 9). Aquí se comprueba si esa asimetría es una propiedad
del metadato o una peculiaridad de esos dos polígonos, y se expresa como función del tamaño de
parcela.

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
- Lo más cercano a este trabajo: Tiede et al. (2021), *Remote Sensing of Environment*,
  `10.1016/j.rse.2020.112163`, que ya documenta que filtrar por la nubosidad estimada de cada
  imagen esconde datos, con el caso de la alta montaña. [[PENDIENTE: cita textual exacta y su
  unidad de análisis, para separar con precisión su aporte del de este trabajo.]]

**Párrafo 4 — el hueco y la contribución.** Nadie ha medido el error del metadato **tomando el
predio agrícola como unidad de decisión**, ni lo ha expresado como matriz de confusión con su
asimetría, ni como función del tamaño de parcela. Eso es lo que aquí se aporta, junto con el
conjunto de datos que permite rehacerlo.

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

### 4.1 Cuánto del archivo son copias

[[PENDIENTE: porcentaje de ítems duplicados sobre la cohorte, discrepancia máxima y media de
nubosidad declarada entre líneas base, y desfase mínimo del instante de sensado.]]

### 4.2 La matriz, agrupada

[[PENDIENTE: tabla 2 — las cuatro celdas, la asimetría, la exhaustividad y la precisión.]]

### 4.3 La regla en función del tamaño

[[PENDIENTE: figura 1 — exhaustividad del filtro frente a superficie de la parcela, con intervalo
de confianza. Es la figura que decide el artículo.]]

### 4.4 Sensibilidad a los umbrales

[[PENDIENTE: tabla 3 — rejilla T × U.]]

### 4.5 Control

[[PENDIENTE: comparar la asimetría medida sobre la cohorte con la de los dos predios del Magdalena.
Si el orden de magnitud coincide, el caso original no era una anomalía; si no coincide, el
resultado del caso original hay que reencuadrarlo, y así se dirá.]]

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
