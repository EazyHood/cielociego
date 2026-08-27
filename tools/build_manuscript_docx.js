// Builds the RAET-format manuscript. Anonymised on purpose: the review is
// double blind and the checklist demands files with no identifying references.
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, AlignmentType,
  Table, TableRow, TableCell, WidthType, ShadingType, BorderStyle,
  LineNumberRestartFormat, convertInchesToTwip,
} = require("docx");

const USABLE = 9026;           // A4 minus 1" margins, in DXA
const GREY = "F2F4F1";

const p = (text, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.JUSTIFIED,
  spacing: { after: opts.after === undefined ? 160 : opts.after, line: opts.line || 276 },
  indent: opts.indent,
  children: [new TextRun({ text, italics: opts.italics, bold: opts.bold, size: opts.size || 22 })],
});

const rich = (runs, opts = {}) => new Paragraph({
  alignment: opts.align || AlignmentType.JUSTIFIED,
  spacing: { after: opts.after === undefined ? 160 : opts.after, line: 276 },
  children: runs.map(r => new TextRun({
    text: r.t, bold: r.b, italics: r.i, size: r.size || 22, font: r.mono ? "Consolas" : undefined,
  })),
});

const h1 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_1,
  spacing: { before: 320, after: 160 },
  children: [new TextRun({ text, bold: true, size: 28 })],
});

const h2 = (text) => new Paragraph({
  heading: HeadingLevel.HEADING_2,
  spacing: { before: 240, after: 120 },
  children: [new TextRun({ text, bold: true, size: 24 })],
});

const note = (text) => new Paragraph({
  spacing: { before: 120, after: 200 },
  border: { left: { style: BorderStyle.SINGLE, size: 12, color: "A9740A", space: 8 } },
  indent: { left: 200 },
  children: [new TextRun({ text, italics: true, size: 20, color: "7A5A10" })],
});

function table(headers, rows, widths, opts = {}) {
  const cell = (text, { bold = false, shaded = false, align = AlignmentType.LEFT, w }) =>
    new TableCell({
      width: { size: w, type: WidthType.DXA },
      shading: shaded ? { type: ShadingType.CLEAR, fill: GREY } : undefined,
      margins: { top: 60, bottom: 60, left: 100, right: 100 },
      children: [new Paragraph({
        alignment: align,
        spacing: { after: 0, line: 240 },
        children: [new TextRun({ text: String(text), bold, size: 19 })],
      })],
    });

  const headRow = new TableRow({
    tableHeader: true,
    children: headers.map((t, i) => cell(t, { bold: true, shaded: true, w: widths[i],
      align: i === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT })),
  });
  const bodyRows = rows.map(r => new TableRow({
    children: r.map((t, i) => cell(t, {
      w: widths[i],
      bold: opts.boldRows && opts.boldRows.includes(rows.indexOf(r)),
      align: i === 0 ? AlignmentType.LEFT : AlignmentType.RIGHT,
    })),
  }));
  return new Table({ columnWidths: widths, width: { size: USABLE, type: WidthType.DXA },
    rows: [headRow, ...bodyRows] });
}

const caption = (text) => new Paragraph({
  spacing: { before: 120, after: 240 },
  children: [new TextRun({ text, size: 19, italics: true })],
});

const body = [];

// ---------------------------------------------------------------- portada
body.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 200 },
  children: [new TextRun({
    text: "Un filtro que descarta días buenos: sesgo del metadato de nubosidad de Sentinel-2 a escala de predio",
    bold: true, size: 32 })],
}));
body.push(new Paragraph({
  spacing: { after: 320 },
  children: [new TextRun({
    text: "A filter that discards good days: bias of the Sentinel-2 tile cloud metadata at field scale",
    bold: true, italics: true, size: 26 })],
}));
body.push(note("Manuscrito anonimizado para revisión doble ciega, según la lista de comprobación de la revista. Los datos de autoría y filiación se cargan en el formulario de envío, no en este fichero. Los pasajes entre corchetes están pendientes de redacción y no forman parte del texto final."));

// ---------------------------------------------------------------- resumen
body.push(h1("Resumen"));
body.push(p("Los catálogos públicos de Sentinel-2 publican por cada producto un único valor de nubosidad, eo:cloud_cover, calculado sobre la tesela completa de 110 × 110 km. Ese valor es el criterio con el que la mayoría de los portales y bibliotecas de acceso deciden qué imágenes se descargan. Cuando la unidad de decisión no es la tesela sino un predio agrícola, cuatro órdenes de magnitud más pequeño, ese filtro deja de ser conservador y pasa a ser sesgado: descarta observaciones útiles mucho más a menudo de lo que retiene observaciones inservibles."));
body.push(p("Este trabajo cuantifica ese sesgo sobre una cohorte de 323 parcelas agrícolas reales de 23 países, obtenidas de un conjunto público de límites parcelarios, y sobre 5.143 pares de parcela y adquisición medidos entre 2023 y 2024. Para cada par se compara el valor declarado por la tesela con la fracción de la parcela que la banda de clasificación de escena marca como inservible. Con el filtro de referencia, la exhaustividad es de 0,449 (IC 95 %: 0,420–0,480): el filtro conserva menos de la mitad de las observaciones que de verdad servían sobre la parcela. La asimetría entre errores es de 48,5 falsos negativos por cada falso positivo, y empeora al endurecer el filtro, hasta 99,7 cuando se exige menos del 5 % de nubosidad declarada. El usuario más cuidadoso es el más perjudicado."));
body.push(p("Como resultado secundario se documenta y cuantifica un artefacto del propio archivo: la misma adquisición se sirve reprocesada bajo varias líneas base, cada copia declara una nubosidad distinta —hasta 52,10 puntos porcentuales de diferencia— y el instante de sensado difiere entre copias, de modo que deduplicar por fecha falla en silencio. La duplicación no es uniforme: alcanza el 53,8 % de los ítems en 2021 y cae por debajo del 3 % desde 2022."));
body.push(rich([{ t: "Palabras clave: ", b: true }, { t: "Sentinel-2; nubosidad; metadatos; escala espacial; agricultura de precisión; calidad de datos; trópico." }]));

body.push(h1("Abstract"));
body.push(p("Public Sentinel-2 catalogues publish a single cloud value per product, eo:cloud_cover, computed over the full 110 × 110 km tile. That value is the criterion most access portals and client libraries use to decide which images are downloaded. When the decision unit is not the tile but an agricultural field, four orders of magnitude smaller, the filter stops being conservative and becomes biased: it discards usable observations far more often than it retains unusable ones.", { italics: true }));
body.push(p("This work quantifies that bias over a cohort of 323 real agricultural parcels from 23 countries, drawn from a public field-boundary dataset, and over 5,143 measured parcel-acquisition pairs between 2023 and 2024. For each pair, the value declared by the tile is compared with the fraction of the parcel flagged as unusable by the scene classification band. Under the reference filter, recall is 0.449 (95 % CI: 0.420–0.480): the filter keeps fewer than half of the acquisitions that were genuinely usable over the parcel. The asymmetry between error types is 48.5 false negatives per false positive, and it worsens as the filter is tightened, reaching 99.7 when less than 5 % declared cloud is required. The most careful user is the worst served.", { italics: true }));
body.push(p("As a secondary result, an artefact of the archive itself is documented and quantified: the same acquisition is served reprocessed under several baselines, each copy declaring a different cloud cover —up to 52.10 percentage points apart— and with differing sensing timestamps, so that deduplicating by date fails silently. Duplication is not uniform: it reaches 53.8 % of items in 2021 and falls below 3 % from 2022 onwards.", { italics: true }));
body.push(rich([{ t: "Keywords: ", b: true, i: true }, { t: "Sentinel-2; cloud cover; metadata; spatial scale; precision agriculture; data quality; tropics.", i: true }]));

// ---------------------------------------------------------------- 1
body.push(h1("1. Introducción"));
body.push(p("Quien trabaja con series ópticas sobre un predio no descarga el archivo entero: filtra. Y filtra por el único número de nubosidad que el catálogo ofrece por producto, eo:cloud_cover, un escalar que describe la tesela. Ese gesto, que parece administrativo, decide qué observaciones existen para el resto del análisis."));
body.push(p("Una tesela de Sentinel-2 cubre 12.100 km². Un predio de 73,5 ha es el 0,006 % de esa superficie. La nube es irregular a escala de kilómetro, de modo que un predio o está debajo de ella o no lo está: la distribución de la fracción nubosa sobre el predio es marcadamente bimodal mientras que la de la tesela no lo es. Un estimador insesgado sobre la tesela no tiene por qué serlo sobre el predio, y su error no tiene por qué ser simétrico."));
body.push(p("El estado del arte conviene delimitarlo con precisión. La calidad de las máscaras de nube por píxel está bien estudiada y comparada (Foga et al., 2017; Baetens et al., 2019; Skakun et al., 2022): esos trabajos evalúan el algoritmo de enmascarado, no el resumen de escena empleado como filtro de consulta. La disponibilidad de observaciones libres de nube se ha cuantificado a escala regional y global (Sudmanns et al., 2019; Flores-Anderson et al., 2023), con el gránulo o el píxel como unidad. El vecino más cercano a este trabajo es Tiede et al. (2021), que escriben que «almost all optical remote sensing data access portals rely to some degree on a cloud cover filter» y que ello produce «a lot of \"hidden\" data […] when each image's estimated cloud cover is used as an automated selection criterion». Su alcance, declarado por ellos, son las áreas de muy alta altitud, con seis sitios de prueba en los Andes, el Himalaya y los Alpes; su unidad de análisis es el gránulo completo; y su causa es la aplicación de umbrales sobre banda única en lugar de una firma multibanda. No hay en ese trabajo polígono de usuario, ni matriz de confusión, ni dependencia del tamaño del área de interés."));
body.push(p("El hueco es, por tanto, concreto: nadie ha evaluado el metadato de nubosidad como filtro frente a la nubosidad observada sobre un polígono de parcela, ni ha construido esa matriz de confusión, ni la ha expresado en función del tamaño del área de interés. En cuanto a los duplicados de reprocesado, no se ha localizado literatura revisada por pares que los cuantifique. Este trabajo aporta ambas cosas, junto con el conjunto de datos que permite rehacerlas."));
body.push(p("Conviene decir también qué no es este trabajo. No es una evaluación de la máscara de nube. Las dos magnitudes que se comparan descienden de la misma clasificación, y ese es justamente el diseño: lo que se mide es lo que se pierde al usar un estimador calculado sobre 12.100 km² para decidir sobre una superficie cuatro órdenes de magnitud menor. Mismo estimador, distinto soporte."));

// ---------------------------------------------------------------- 2
body.push(h1("2. Datos"));
body.push(h2("2.1. Catálogo óptico"));
body.push(p("Se emplea el catálogo STAC público Earth Search v1 (Element 84, sobre AWS Open Data), colección sentinel-2-l2a, accesible sin credenciales ni cuota. Los productos son ficheros GeoTIFF optimizados para la nube en un depósito público y se leen por ventana, nunca la escena completa. Los datos Copernicus son de acceso libre, pleno y abierto."));
body.push(p("Se registra la fecha de consulta del catálogo, porque el archivo cambia: el operador anunció el borrado de productos de líneas base antiguas. Medido el 27 de agosto de 2026, las copias seguían presentes, de modo que las cifras de duplicación que se reportan corresponden a esa fecha."));
body.push(h2("2.2. Fracción inservible sobre el polígono"));
body.push(p("Se emplea la banda de clasificación de escena a 20 m, recortada al polígono de la parcela. Se declaran y se reportan dos definiciones de «inservible»: la estricta, que incluye ausencia de dato, saturación, sombra de nube, nube probable, nube segura y cirro; y la amplia, que añade la sombra orográfica. Una parcela con menos de 25 píxeles se marca y se analiza aparte: por debajo de ese umbral el porcentaje se mueve a saltos de cuatro puntos y el borde del polígono pesa más que su interior."));
body.push(h2("2.3. Cohorte de parcelas"));
body.push(p("Los límites parcelarios proceden de un conjunto público de fronteras agrícolas que publica máscaras de instancia por recorte. Esas máscaras se vectorizan para obtener parcelas reales. Se descartan las que tocan el borde del recorte, porque las corta el teselado y no el agricultor, y conservarlas sesgaría la distribución de tamaños hacia abajo. Los países cuya licencia prohíbe el uso comercial se excluyen por nombre, de forma auditable. La selección no es aleatoria ni lleva semilla: se reparte una cuota por tramo de tamaño, de modo que los estratos que el análisis reporta queden poblados."));
body.push(p("La cohorte resultante es de 323 parcelas de 23 países, entre 0,20 y 255,41 ha, con mediana de 1,60 ha, e incluye trópico húmedo y seco (Ruanda, Kenia, India, Vietnam, Camboya, Brasil y Colombia) junto con Europa continental y nórdica. El extremo superior del rango lo aporta un predio del Caribe colombiano ya publicado, porque un recorte de la fuente mide alrededor de un kilómetro de lado y casi cualquier parcela mayor de unas 20 ha toca el borde."));
body.push(p("Debe declararse un sesgo de selección: el listado del repositorio se lee una página de mil claves por país. Un país de la muestra tiene más de 400.000 máscaras, de modo que un listado exhaustivo agota cientos de peticiones sin salir de él. En consecuencia, la selección recorre la cabeza lexicográfica de los recortes de cada país y no el país entero."));

// ---------------------------------------------------------------- 3
body.push(h1("3. Métodos"));
body.push(h2("3.1. Deduplicación por línea de procesado"));
body.push(p("El catálogo sirve la misma adquisición reprocesada bajo varias líneas base. La identidad física de una adquisición es la cuaterna (plataforma, instante de sensado, órbita, tesela); el identificador de línea base es solo la versión del procesador. Se deduplica por el identificador de producto y se conserva la línea base más alta."));
body.push(p("Deduplicar por fecha no funciona, y este es un punto operativo con consecuencias: las copias difieren en el instante declarado. En un par real de la tesela 18PWT del 25 de marzo de 2019, las dos copias declaran 2,58 % y 3,40 % de nubosidad y sus marcas de tiempo distan 23,9 s. Un flujo que agrupe por fecha o por instante no las junta y las cuenta como dos observaciones distintas."));
body.push(h2("3.2. El filtro, la referencia y la matriz de confusión"));
body.push(p("Se define el filtro como la regla que conserva la adquisición si la nubosidad declarada por la tesela es menor o igual que un umbral T, con valor de referencia T = 10 %. Se define la referencia para el predio como la condición de que la fracción inservible sobre el polígono sea menor o igual que un umbral U, con valor de referencia U = 10 %. El valor de referencia de T coincide con el empleado en el trabajo previo sobre dos predios, de modo que caso y cohorte quedan comparables."));
body.push(p("Un falso negativo es una adquisición útil sobre el predio que el filtro descarta: es el error caro, porque se pierde una observación que existía y no se recupera. Un falso positivo es una adquisición que el filtro conserva y que sobre el predio resulta inservible: cuesta cómputo, no información. La asimetría se define como el cociente entre ambos."));
body.push(p("Los dos umbrales son parámetros y no constantes ocultas en una conclusión: se reporta la rejilla completa T × U. Un solo par de umbrales invita a la respuesta de que los números se eligieron para que funcionaran."));
body.push(h2("3.3. Estratificación"));
body.push(p("La matriz se reporta además por tramos de superficie. Esa estratificación es la que permitiría convertir el hallazgo en regla: si la exhaustividad del filtro cayera al reducirse la parcela, el sesgo procedería del desajuste de soporte y no del clima de una región concreta."));
body.push(h2("3.4. Lo que no se hace"));
body.push(p("No se valida contra observación en tierra. No hay cámara de nubes ni ceilómetro sobre estas parcelas, y el diseño no lo requiere: la pregunta es la coherencia interna entre dos resúmenes del mismo producto a dos escalas, no cuál de los dos acierta más frente al cielo real."));

// ---------------------------------------------------------------- 4
body.push(h1("4. Resultados"));
body.push(h2("4.1. Cuánta parte del archivo son copias, y de qué depende"));
body.push(p("Sobre la cohorte completa entre 2023 y 2024 se recuperan 93.072 ítems, de los cuales 834 son copias de reprocesado (0,9 %). La mayor discrepancia de nubosidad declarada entre dos copias de una misma adquisición es de 52,10 puntos porcentuales, y la mayor razón entre las dos cifras declaradas es de 285,7 veces."));
body.push(p("Sobre un predio del Caribe colombiano y el archivo completo entre 2019 y 2026 se recuperan 822 ítems que corresponden a 603 adquisiciones únicas: 219 copias, el 26,6 %. Conviven doce líneas de procesado y la discrepancia máxima es de 25,64 puntos (24,22 % frente a 49,86 %)."));
body.push(p("El contraste entre 0,9 % y 26,6 % no es una contradicción sino el resultado. Desglosada por año (Tabla 5), la duplicación no es una constante sino un escalón: supera el 44 % entre 2019 y 2021, con un máximo del 53,8 % en 2021, y cae por debajo del 3 % desde 2022. La consecuencia práctica es que quien construye una serie que llegue antes de 2022 —lo habitual en fenología, tendencias o líneas base— hereda un catálogo donde hasta la mitad de los ítems son copias con nubosidad declarada distinta, mientras que quien trabaja solo con los últimos años no encuentra el problema ni tiene motivo para sospecharlo."));
body.push(h2("4.2. La matriz de confusión"));
body.push(p("Sobre 5.143 pares parcela × adquisición medidos, con los umbrales de referencia, el filtro por metadato de tesela conserva 475 adquisiciones útiles y 12 inservibles, y descarta 582 útiles y 2.196 inservibles (Tabla 2). La exhaustividad es de 0,449, con intervalo de confianza del 95 % [0,420, 0,480]: el filtro deja pasar menos de la mitad de las observaciones que de verdad servían sobre la parcela. La asimetría es de 48,5 falsos negativos por cada falso positivo."));
body.push(p("Sobre los dos predios del trabajo previo la asimetría había sido de 37 a 1. Sobre 323 parcelas de 23 países es de 48,5 a 1, de modo que el caso original no era una anomalía y, si acaso, se quedaba corto."));
body.push(h2("4.3. Dependencia del tamaño de la parcela"));
body.push(p("La exhaustividad crece con el tamaño de la parcela en el rango de 1 a 100 ha, de 0,429 a 0,520 (Tabla 3, Figura 1), que es la dirección que predice el desajuste de soporte. Ahora bien, el efecto es moderado —nueve puntos entre una parcela de una hectárea y una de cien— y los intervalos de confianza de tramos contiguos se solapan."));
body.push(p("El último tramo rompe la monotonía y conviene explicarlo en lugar de omitirlo: las dieciséis observaciones del tramo de 100 a 500 ha corresponden a una sola parcela situada en trópico húmedo, donde la exhaustividad cae a 0,273 porque el régimen de nubosidad es peor, no porque la parcela sea grande. Con una sola parcela no es posible separar tamaño de clima, y presentar ese punto como efecto de tamaño sería precisamente el tipo de error que este trabajo documenta en el uso del metadato."));
body.push(h2("4.4. Sensibilidad a los umbrales"));
body.push(p("La asimetría no es un artefacto del par de umbrales elegido (Tabla 4). Se conserva en toda la rejilla y solo se invierte cuando el filtro se afloja hasta el 50 %, que equivale a no filtrar. El patrón relevante es el contrario del que cabría esperar: cuanto más estricto es el filtro, peor es el sesgo. Al 5 % de nubosidad declarada la asimetría alcanza 99,7 y la exhaustividad baja a 0,340. El usuario que exige imágenes limpias es el peor servido."));
body.push(h2("4.5. Control: el umbral de píxeles no fabrica el resultado"));
body.push(p("Repitiendo la matriz sin apartar las parcelas por debajo del umbral de píxeles, sobre las mismas 5.143 filas, la exhaustividad es 0,439 y la asimetría 49,4, frente a 0,449 y 48,5 con el umbral aplicado. El hallazgo no depende de esa decisión metodológica."));
body.push(h2("4.6. El estrato que esta banda no puede medir"));
body.push(p("De las 5.143 filas medidas, 1.878 corresponden a parcelas con menos de 25 píxeles de la banda de clasificación, es decir por debajo de una hectárea. No se descartan por sospechosas sino por incontables: con ocho píxeles la fracción inservible se mueve a saltos de doce puntos. Es una limitación del instrumento y no del método, y afecta a buena parte de las parcelas de los países con estructura agraria más fragmentada de la muestra."));

// ---------------------------------------------------------------- 5
body.push(h1("5. Discusión"));
body.push(p("Perder un día despejado y procesar un día nublado no cuestan lo mismo. En una serie de fenología sobre un predio, el día perdido es información que existía y que no se recupera, mientras que el día nublado que se cuela se descarta en el paso siguiente a coste de cómputo. Que el error del filtro sea casi cincuenta veces más frecuente en la dirección cara es, por tanto, el resultado con consecuencias."));
body.push(p("El hallazgo dialoga directamente con Reyes-Díez et al. (2015), que advierten de que criterios de filtrado homogéneos aplicados sobre una región heterogénea pueden causar pérdida sistemática de información. Aquí se muestra que el criterio homogéneo del metadato de tesela hace exactamente eso a escala de predio, y se cuantifica cuánto."));
body.push(note("[Pendiente de redactar: apartado 5.2, la recomendación operativa. El artículo debe terminar en una regla accionable y no en una queja. Requiere comparar en la misma tabla al menos tres filtros alternativos disponibles sin trabajo de campo —el metadato de escena, el porcentaje de nube de alta probabilidad, y la fracción recortada al polígono— y recomendar uno con su umbral.]"));
body.push(p("Los límites del trabajo son cuatro y conviene enunciarlos sin rodeos. Primero, las dos magnitudes comparadas descienden de la misma clasificación, de modo que lo que se mide es el efecto de la agregación espacial y no la calidad del enmascarado. Segundo, el artefacto de los duplicados puede caducar: si el operador completa el borrado de líneas base antiguas, el porcentaje medido pasará a ser un hecho histórico, razón por la cual se fecha la consulta. Tercero, la cohorte hereda el sesgo de muestreo de la fuente de límites parcelarios y de la lectura parcial de su listado. Cuarto, el trópico húmedo está representado por pocas parcelas, y el tramo de mayor superficie por una sola."));

// ---------------------------------------------------------------- 6
body.push(h1("6. Conclusiones"));
body.push(p("El valor de nubosidad que los catálogos públicos publican por producto describe una tesela de 12.100 km² y se usa de forma rutinaria para decidir sobre superficies cuatro órdenes de magnitud menores. Medido sobre 323 parcelas de 23 países y 5.143 pares parcela × adquisición, ese uso conserva el 44,9 % de las observaciones realmente utilizables y descarta 48,5 observaciones buenas por cada mala que retiene, con un sesgo que se agrava al endurecer el filtro."));
body.push(p("Para el trabajo a escala de predio, la recomendación es no filtrar por el metadato de tesela como criterio único, y decidir con la fracción de nube recortada al polígono. El coste adicional es una lectura por ventana de la banda de clasificación; el beneficio, más de la mitad de las observaciones que hoy se pierden en silencio."));
body.push(p("Además, cualquier serie temporal que se remonte antes de 2022 debe deduplicarse por identificador de producto y no por fecha: en 2021 más de la mitad de los ítems que devuelve el catálogo son copias de reprocesado de una adquisición ya presente, y sus copias declaran nubosidades que difieren hasta en 52 puntos porcentuales."));

// ---------------------------------------------------------------- cierre
body.push(h1("Disponibilidad de datos y código"));
body.push(p("La herramienta de medición empleada es de código abierto y está archivada con DOI; la tabla ordenada con una fila por parcela y adquisición se deposita con licencia abierta. No se redistribuyen los límites parcelarios de las fuentes con licencia no comercial: se publican los identificadores y el guion que los reconstruye. [Las referencias concretas se aportan en el fichero suplementario no anónimo, para no comprometer la revisión doble ciega.]"));

body.push(h1("Agradecimientos"));
body.push(p("Contiene datos Copernicus Sentinel modificados. Los límites parcelarios proceden de un conjunto público de fronteras agrícolas."));

// ---------------------------------------------------------------- referencias
body.push(h1("Referencias"));
const refs = [
  "Anaya, J.A., Rodríguez-Buriticá, S., Londoño, M.C., 2023. Land cover classification with spatial resolution of 10 meters in forests of the Colombian Caribbean based on Sentinel 1 and 2 missions. Revista de Teledetección, 61, 29-41. https://doi.org/10.4995/raet.2023.17655",
  "Anaya, J.A., Sione, W., Rodriguez-Montellano, A.M., 2018. Burned area detection based on time-series analysis in a cloud computing environment. Revista de Teledetección, 51, 61-73. https://doi.org/10.4995/raet.2018.8618",
  "Baetens, L., Desjardins, C., Hagolle, O., 2019. Validation of Copernicus Sentinel-2 cloud masks obtained from MAJA, Sen2Cor, and FMask processors using reference cloud masks generated with a supervised active learning procedure. Remote Sensing, 11(4), 433. https://doi.org/10.3390/rs11040433",
  "Flores-Anderson, A.I. et al., 2023. Spatial and temporal availability of cloud-free optical observations in the tropics to monitor deforestation. Scientific Data, 10, 550. https://doi.org/10.1038/s41597-023-02439-x",
  "Foga, S., Scaramuzza, P.L., Guo, S., Zhu, Z., Dilley, R.D., Beckmann, T., Schmidt, G.L., Dwyer, J.L., Hughes, M.J., Laue, B., 2017. Cloud detection algorithm comparison and validation for operational Landsat data products. Remote Sensing of Environment, 194, 379-390. https://doi.org/10.1016/j.rse.2017.03.026",
  "Julien, Y., Sobrino, J.A., 2018. TISSBERT: A benchmark for the validation and comparison of NDVI time series reconstruction methods. Revista de Teledetección, 51, 19-31. https://doi.org/10.4995/raet.2018.9749",
  "Reyes-Díez, A., Alcaraz-Segura, D., Cabello-Piñar, J., 2015. Implications of quality filtering of Enhanced Vegetation Index (EVI) for ecosystem functioning monitoring. Revista de Teledetección, 43, 11-30. https://doi.org/10.4995/raet.2015.3316",
  "Skakun, S. et al., 2022. Cloud Mask Intercomparison eXercise (CMIX): An evaluation of cloud masking algorithms for Landsat 8 and Sentinel-2. Remote Sensing of Environment, 274, 112990. https://doi.org/10.1016/j.rse.2022.112990",
  "Sudmanns, M., Tiede, D., Augustin, H., Lang, S., 2019. Assessing global Sentinel-2 coverage dynamics and data availability for operational Earth observation (EO) applications using the EO-Compass. International Journal of Digital Earth, 13(7), 768-784. https://doi.org/10.1080/17538947.2019.1572799",
  "Tiede, D., Sudmanns, M., Augustin, H., Baraldi, A., 2021. Investigating ESA Sentinel-2 products' systematic cloud cover overestimation in very high altitude areas. Remote Sensing of Environment, 252, 112163. https://doi.org/10.1016/j.rse.2020.112163",
];
refs.forEach(r => body.push(new Paragraph({
  alignment: AlignmentType.LEFT,
  spacing: { after: 120, line: 260 },
  indent: { left: 400, hanging: 400 },
  children: [new TextRun({ text: r, size: 20 })],
})));
body.push(note("[Pendiente: completar la referencia del conjunto de límites parcelarios y la del catálogo STAC, que en el texto van citadas de forma genérica para no desanonimizar el manuscrito.]"));

// ---------------------------------------------------------------- tablas
body.push(h1("Tablas"));

body.push(caption("Tabla 1. Composición de la cohorte: 323 parcelas de 23 países. Se listan los diecisiete países con trece parcelas o más; los seis restantes (Brasil, Colombia, Córcega, Dinamarca, Kenia y Eslovaquia) se agrupan. Las adquisiciones son pares parcela × adquisición planificados."));
body.push(table(
  ["País", "Parcelas", "Mediana (ha)", "Mín (ha)", "Máx (ha)", "Adquisiciones"],
  [
    ["Austria", "18", "2,06", "0,32", "9,01", "288"],
    ["Bélgica", "18", "2,02", "0,20", "7,12", "288"],
    ["Camboya", "18", "2,02", "0,20", "2,91", "288"],
    ["Croacia", "18", "2,02", "0,20", "7,30", "288"],
    ["Eslovenia", "18", "1,52", "0,21", "5,67", "288"],
    ["España", "18", "2,04", "0,20", "11,11", "288"],
    ["Estonia", "13", "7,56", "0,48", "20,92", "208"],
    ["Finlandia", "18", "2,01", "0,24", "9,38", "288"],
    ["Alemania", "18", "2,19", "0,21", "16,50", "288"],
    ["Francia", "18", "2,05", "0,29", "53,14", "288"],
    ["India", "18", "1,22", "0,21", "1,94", "288"],
    ["Lituania", "18", "2,08", "0,21", "23,42", "288"],
    ["Luxemburgo", "18", "2,01", "0,22", "12,84", "288"],
    ["Países Bajos", "18", "2,11", "0,23", "6,84", "288"],
    ["Ruanda", "18", "2,04", "0,21", "23,61", "288"],
    ["Suecia", "18", "2,37", "0,29", "15,96", "288"],
    ["Vietnam", "18", "2,02", "0,20", "3,32", "288"],
    ["Otros seis países", "22", "—", "0,25", "255,41", "352"],
    ["TOTAL", "323", "1,60", "0,20", "255,41", "5.168"],
  ],
  [1900, 1250, 1500, 1300, 1300, 1776],
  { boldRows: [18] },
));

body.push(caption("Tabla 2. Matriz de confusión del filtro por metadato de tesela frente a la fracción inservible medida sobre el polígono. Umbrales de referencia: tesela ≤ 10 %, parcela utilizable con ≤ 10 % de superficie inservible. n = 5.143 pares medidos."));
body.push(table(
  ["", "Útil sobre la parcela", "Inservible sobre la parcela"],
  [
    ["El filtro la conserva", "475", "12  (falso positivo)"],
    ["El filtro la descarta", "582  (falso negativo)", "2.196"],
  ],
  [3026, 3000, 3000],
));
body.push(p("Exhaustividad 0,449, IC 95 % [0,420, 0,480]. Asimetría 48,5 falsos negativos por falso positivo. Filas apartadas: 25 sin lectura o sin metadato y 1.878 por debajo del umbral de píxeles.", { after: 240 }));

body.push(caption("Tabla 3. Matriz por tramos de superficie. El tramo de 100-500 ha corresponde a una única parcela en trópico húmedo y no es comparable con los anteriores."));
body.push(table(
  ["Tramo", "n", "Exhaustividad", "IC 95 %", "FN", "FP"],
  [
    ["1-5 ha", "2.060", "0,429", "[0,392, 0,466]", "393", "7"],
    ["5-20 ha", "1.077", "0,492", "[0,439, 0,546]", "169", "5"],
    ["20-100 ha", "112", "0,520", "[0,335, 0,700]", "12", "0"],
    ["100-500 ha", "16", "0,273", "[0,097, 0,566]", "8", "0"],
  ],
  [1700, 1100, 1700, 2226, 1150, 1150],
));

body.push(caption("Tabla 4. Sensibilidad a los dos umbrales. T es el filtro sobre la nubosidad declarada por la tesela; U, el límite de superficie inservible bajo el que la parcela se considera utilizable."));
body.push(table(
  ["T", "U", "FN", "FP", "Exhaustividad", "Asimetría"],
  [
    ["5 %", "5 %", "678", "11", "0,344", "61,6"],
    ["5 %", "10 %", "698", "7", "0,340", "99,7"],
    ["10 %", "5 %", "562", "16", "0,456", "35,1"],
    ["10 %", "10 %", "582", "12", "0,449", "48,5"],
    ["20 %", "10 %", "469", "59", "0,556", "7,9"],
    ["30 %", "10 %", "355", "95", "0,664", "3,7"],
    ["50 %", "10 %", "202", "243", "0,809", "0,8"],
  ],
  [1200, 1200, 1350, 1350, 2000, 1926],
  { boldRows: [3] },
));

body.push(caption("Tabla 5. Duplicación por año de adquisición sobre un predio del Caribe colombiano, archivo completo consultado el 27 de agosto de 2026."));
body.push(table(
  ["Año", "Ítems", "Adquisiciones únicas", "Copias", "% copias"],
  [
    ["2019", "130", "72", "58", "44,6"],
    ["2020", "143", "72", "71", "49,7"],
    ["2021", "158", "73", "85", "53,8"],
    ["2022", "73", "72", "1", "1,4"],
    ["2023", "74", "72", "2", "2,7"],
    ["2024", "74", "74", "0", "0,0"],
    ["2025", "102", "102", "0", "0,0"],
    ["2026", "68", "66", "2", "2,9"],
    ["Total", "822", "603", "219", "26,6"],
  ],
  [1400, 1600, 2426, 1800, 1800],
  { boldRows: [8] },
));

// ---------------------------------------------------------------- figuras
body.push(h1("Pies de figura"));
body.push(p("Figura 1. Fracción de las adquisiciones realmente utilizables sobre la parcela que el filtro por metadato de tesela conserva, por tramo de superficie, con intervalo de confianza del 95 % de Wilson. El punto del tramo de 100-500 ha corresponde a una sola parcela en trópico húmedo y su descenso se explica por el régimen de nubosidad, no por la superficie. Umbrales: tesela ≤ 10 %, parcela utilizable con ≤ 10 % inservible."));
body.push(note("[La figura se envía aparte en TIF o JPG a 300 ppi, como piden las normas de la revista. El fichero fuente es outputs/fig_recall_vs_size.svg.]"));

const doc = new Document({
  styles: {
    default: { document: { run: { font: "Times New Roman", size: 22 } } },
  },
  sections: [{
    properties: {
      page: {
        margin: {
          top: convertInchesToTwip(1), bottom: convertInchesToTwip(1),
          left: convertInchesToTwip(1), right: convertInchesToTwip(1),
        },
        lineNumbers: { countBy: 1, restart: LineNumberRestartFormat.CONTINUOUS, distance: 360 },
      },
    },
    children: body,
  }],
});

Packer.toBuffer(doc).then(buf => {
  fs.writeFileSync(process.argv[2], buf);
  console.log("escrito:", process.argv[2], buf.length, "bytes");
});
