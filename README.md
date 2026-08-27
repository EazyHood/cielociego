# cielociego

[![pruebas](https://github.com/EazyHood/cielociego/actions/workflows/pruebas.yml/badge.svg)](https://github.com/EazyHood/cielociego/actions/workflows/pruebas.yml)
[![cobertura 92%](https://img.shields.io/badge/cobertura-92%25-2f7d4f)](https://github.com/EazyHood/cielociego/actions/workflows/pruebas.yml)
[![licencia MIT](https://img.shields.io/badge/licencia-MIT-1d4ed8)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-555)](pyproject.toml)

**Cuánto tiempo el satélite óptico no puede ver un predio, y si el radar cubre el hueco.**

Medido sobre dos predios reales del Magdalena (Colombia), 2019–2026:
**el 89 % y el 91 % de los días no hubo una sola observación óptica aprovechable.**
El radar, que atraviesa la nube, tuvo pasada dentro de **los 66 huecos largos, sin
una sola excepción** — y su serie no es ruido: en uno de los predios registró un
cambio de **3,5 dB** que sobrevive al control de instrumento, y que **no fue
gradual**: meseta, transición de unos dos años, y meseta nueva.

Datos abiertos, sin cuenta, sin clave y sin coste. La medición completa se
reproduce con un comando: **unos 90 s** sin la serie de radar (`--sin-radar`),
**unos 4 min** con ella.

```bash
pip install -e ".[dev]"
python -m cielociego medir          # mide el area de ejemplo incluida
```

El repositorio trae un **área de demostración** de 256 ha sobre el corredor
bananero, así que se puede ejecutar nada más clonarlo. Sobre ella, solo en 2024:
**90 % de días sin observación óptica aprovechable**, y las 5 rachas de 15 días o
más tienen pasada de radar dentro.

---

## El problema

En el trópico la nubosidad persistente deja áreas enteras **sin una imagen
aprovechable durante semanas o meses**. Colombia está de lleno en esa franja. Eso
rompe cualquier serie temporal de NDVI, que es la base de casi toda la
teledetección agrícola.

Todo el mundo lo sabe de forma vaga. Este proyecto lo pone en número, sobre un
predio concreto, con el método declarado y las pruebas dentro.

## Qué hace, en cinco pasos

Cada paso escribe su JSON en `salidas/` y el siguiente lo lee de ahí. Se puede
parar, retomar y comprobar cualquier cifra a mano.

| | Paso | Módulo |
|---|---|---|
| 1 | Baja el catálogo Sentinel-2 y **deduplica por línea de procesado** | `catalogo` + `dedup` |
| 2 | Lee la banda SCL **recortada al polígono** y calcula la fracción ciega | `scl` + `barrido` |
| 3 | Calcula los **tramos sin observación útil** | `radar` |
| 4 | Cruza esos tramos con las **pasadas de Sentinel-1** | `radar` |
| 5 | Extrae la **serie de retrodispersión** sobre el polígono, una sola órbita | `sar` |

La red va por una sesión con reintentos (`red`), porque en una herramienta de
medida un corte transitorio que se traga en silencio se convierte en un dato.

## Los cinco resultados

### 1. El archivo servía la misma toma dos veces, y con nubes distintas

El catálogo público entrega la misma adquisición reprocesada bajo varias líneas
de procesado. Contarlas todas daba **146 pasadas al año** donde la órbita solo
permite unas 73. Y lo grave no es el doble conteo:

```
2020-01-04   linea N0500  ->  nube  0,11 %      mismo instante de sensado;
             linea N0213  ->  nube  3,15 %      difieren en 1 milisegundo

2020-01-09   linea N0500  ->  nube  0,05 %
             linea N0213  ->  nube  1,88 %      37 veces mas
```

Deduplicar por fecha **no las junta** — el sensado difiere en un milisegundo. La
clave estable es el identificador de producto. Se descartan **218 copias, el
26,6 %**, y las pasadas pasan a cuadrar con la física: 72–73 al año, revisita de
5,0 días. El salto a 101 en 2025 resulta ser real: la entrada de Sentinel-2C.

### 2. El dato de nube de la escena no sirve a escala de predio

`eo:cloud_cover` se calcula sobre la tesela entera: 110 × 110 km, 12.100 km². El
predio de Fundación son 73,5 ha, el 0,006 % de esa superficie.

La nube es irregular a escala de kilómetro, así que un predio pequeño **o está
debajo de ella o no lo está**: el 85 % de las tomas cae en un extremo (despejado
del todo o tapado del todo), frente al 14 % de la tesela.

| | Tomas | Útiles reales | Útiles según tesela | Buenas descartadas | Malas coladas |
|---|---:|---:|---:|---:|---:|
| Fundación · 73,5 ha | 600 | 316 | 120 | **200** | 4 |
| Corredor · 284,1 ha | 602 | 265 | 138 | **132** | 5 |

Una asimetría de **37 a 1**. Filtrar por el número de la tesela no es ser
conservador: es una máquina de falsos negativos. Correlación entre ambas
medidas: 0,772 — parecidas, no intercambiables.

### 3. Con la medida honesta, el predio pasa casi todo el año invisible

```
                          Fundacion      Corredor
dias del periodo .......... 2.794          2.794
dias con vista util .......   315            264
DIAS CIEGOS ...............   89 %           91 %
hueco mas largo ...........   59 d           89 d
                        (2019-08-28)   (2024-04-13)
```

Casi tres meses seguidos sin una sola imagen utilizable del corredor bananero.
Un ciclo de cultivo no espera a que escampe.

### 4. El radar estuvo ahí en todos los huecos largos

Sentinel-1 no mira: ilumina. Al ser radar, la nube le da igual, y es igual de
gratis que el óptico.

```
huecos de >= 15 dias con pasada de radar dentro:
   Fundacion  34 / 34        Corredor  32 / 32        = 100 %

durante los 89 dias en que el optico no vio NADA: 22 pasadas de radar
```

Los huecos cortos, de cuatro días, a veces no llevan radar dentro y da igual: la
siguiente imagen óptica llega enseguida. **Donde el problema duele, el radar
siempre estaba.** El hueco no era de datos. Era de método.

### 5. Y el radar no solo estaba: traía señal

Que exista una pasada no significa que sirva. Se extrajo la serie completa de
retrodispersión sobre el polígono — **590 medidas**, todas de la misma órbita
relativa, porque mezclar geometrías inventa saltos que no vienen del cultivo.

En el corredor bananero la serie no es ruido. Pero **tampoco es la recta que
parecía**. Comparando cuatro formas posibles por BIC —y penalizando los puntos
de corte que hay que buscar— gana *meseta → transición → meseta*:

```
modelo                    SSE    k       BIC   delta
meseta-rampa-meseta      71,5    4    -509,5     0      <- gana
escalon                 126,8    3    -319,8   +190
rampa lineal            163,2    2    -239,6   +270     <- lo que yo dibujaba
constante               968,4    1    +361,7   +871

nivel estable hasta 2021-06   ->  -6,78 dB
TRANSICION  2021-06 -> 2023-08   (unos 26 meses)
nivel estable desde 2023-08   ->  -3,29 dB      salto +3,50 dB
```

**La diferencia importa para leerlo:** una rampa continua parece crecimiento;
una meseta, una transición y una meseta nueva parece un *evento* — una siembra,
una tala, un cambio de uso. El dato no dice cuál, pero sí dice que no fue
gradual a lo largo de siete años.

#### El control: ¿y si fuera el satélite y no el suelo?

El cambio arranca cerca de la retirada de Sentinel-1B, así que podía ser
calibración disfrazada de agronomía. El control es medir la tendencia **dentro
de un solo satélite**: si es artefacto, ahí desaparece.

```
CORREDOR   todas las plataformas ....... +0,643 dB/ano
           solo Sentinel-1A (n=215) .... +0,688 dB/ano   <- no desaparece
           solo Sentinel-1B (n=79) ..... +0,150 dB/ano
FUNDACION  serie completa .............. -0,058 dB/ano   <- 11 veces menos
```

En el mismo año, S1A y S1B difieren entre 0,04 y 0,50 dB: no hay sesgo de
plataforma que explique 3,5.

**Y aquí hay que ser preciso: el predio vecino no es «plano».** Su pendiente es
pequeña pero significativa — IC 95 % `[-0,094, -0,022]`, no cruza el cero. Lo
que dice el control no es que allí no pase nada, sino que **allí no pasa nada
parecido**. Que el método detecte también el cambio pequeño refuerza el control
en vez de debilitarlo.

#### Por qué el intervalo es más ancho de lo que parecería

Un ajuste por mínimos cuadrados supone observaciones independientes, y las de
una serie de radar no lo son: los residuos arrastran (0,76 de autocorrelación),
así que **las 341 pasadas valen como 47 observaciones independientes**. Con
errores de Newey-West, robustos a autocorrelación:

```
pendiente  +0,643 dB/ano   IC95 [+0,591, +0,695]
el error estandar clasico se quedaba 1,7 veces corto
robustez dejando fuera un ano entero:  +0,600 a +0,718 dB/ano
```

#### Una corroboración independiente

Sobre este mismo predio se había hecho antes un análisis **óptico**, sin radar y
sin relación con este trabajo: el NDVI cae en 2021, y el descenso son **tres
bloques compactos —el mayor de 27,6 ha— con los bordes rectos siguiendo los
linderos**, que recuperan NDVI > 0,70 en 2025. Bordes rectos en los linderos
significa **manejo humano**, no clima.

El radar, por su cuenta y con otro método, fecha la transición entre
**jun-2021 y ago-2023**. Dos instrumentos distintos, el mismo evento y las
mismas fechas. Eso es lo más cerca que llega este trabajo de saber qué pasó:
**fue una intervención de manejo** — la hipótesis del análisis óptico era
renovación de lotes.

Algo cambió en esas 284 hectáreas y se estabilizó en un nivel nuevo. **Confirmar
qué exactamente sigue exigiendo campo o registros de siembra.** Lo que queda medido es que el radar lo registró de
principio a fin, y que en el tramo del cambio el óptico llegó a estar **55 días
seguidos** sin una imagen aprovechable.

## Lo que esto *no* demuestra

El radar mide retrodispersión: rugosidad, geometría, humedad. El óptico mide
reflectancia: pigmento, clorofila. **Un NDVI no se sustituye por un VV/VH.** Que la
serie tenga estructura y detecte un cambio no significa que responda las mismas
preguntas.

**El radar tampoco gana siempre en número.** Con Sentinel-1B retirado, entre 2022 y
2024 la órbita 77 dio unas 28 pasadas al año sobre el corredor: menos que las
imágenes ópticas aprovechables de esos mismos años. La ventaja está en el catálogo
completo — **890 pasadas de radar en tres órbitas frente a 264 ópticas útiles** —
no en una sola órbita. Aquí se usa una sola porque es lo correcto para una serie
comparable, y eso cuesta observaciones.

**Y no se sabe qué pasó en el suelo.** Atribuir la subida a una siembra, a un riego
o a un cambio de cultivo exigiría ir al campo o cruzar con registros. Este trabajo
llega hasta donde llega el dato.

## Decisiones que mueven los números, declaradas

- **Qué cuenta como ciego.** Nube, sombra de nube, cirro, píxel saturado y sin
  dato. La sombra orográfica se calcula aparte (`ciego_amplio`) porque en terreno
  llano suele ser suelo húmedo, no sombra real. **Medido: da igual.** La
  diferencia media entre las dos definiciones es de 0,0001 y **ninguna toma
  cambia de bando**. La duda estaba bien planteada y la respuesta es que no
  afectaba; queda cerrada en vez de arrastrada como salvedad.
- **Umbral de «útil»**: 10 % del predio tapado. **Medido en todo el rango:**

  ```
  umbral    dias ciegos Fundacion    dias ciegos Corredor
     0 %            90 %                    92 %
    10 %            89 %                    91 %      <- el usado
    50 %            87 %                    88 %
  ```

  Exigiendo el predio perfectamente despejado o dejando pasar la mitad tapada,
  la conclusión es la misma. **No depende del umbral.**
- **Tamaño mínimo del predio.** Por debajo de 25 píxeles la cifra se marca con
  un aviso: con 8 píxeles el porcentaje solo se mueve de 12 en 12 puntos y el
  borde del polígono pesa más que su interior. No se falla —hay predios
  pequeños legítimos— pero no se deja pasar como si fuera preciso.
- **La máscara de nubes es un modelo, y los modelos se actualizan.** El archivo
  sirve muchas tomas bajo dos versiones del procesador, y no siempre coinciden.
  Comparadas 61 sobre el polígono:

  ```
  identicas al bit ................................. 80 %
  difieren ......................................... 20 %   (|dif| media 6,7 %)
  CRUZAN el umbral de utilidad ..................... 6,6 %
     y siempre en el mismo sentido: la version nueva marca MAS nube
     (36 tomas utiles con la vieja, 32 con la nueva)

  el peor caso medido, 2021-11-29, la MISMA toma:
     linea N0301 -> predio  0,0 % tapado
     linea N0500 -> predio 71,8 % tapado
  ```

  Como se usa siempre la línea más alta, **lo publicado es la estimación
  conservadora**: más días ciegos de los que declararía el procesador antiguo.
  Reproducible con `dedup.pares_de_lineas`.
- **El titular aguanta cualquier definición de «nube».** Contando como ciega
  solo la nube segura —ignorando nube probable, cirro y sombra, lo más generoso
  que se puede defender— quedan **82 % y 84 % de días ciegos**, frente al 89 % y
  91 % de la definición estricta. La conclusión no vive de dónde se ponga la raya.
- **Una toma se perdió.** La del 23-ene-2024 en Fundación apunta a una ruta
  antigua que ya no existe en el bucket. Queda declarada como fallo, no contada
  como despejada.

## Uso

```bash
python -m cielociego medir                              # el area de ejemplo
python -m cielociego medir --predio mi_finca.geojson    # tu predio
python -m cielociego medir --desde 2022-01-01 --hilos 8
python -m cielociego medir --sin-radar                  # salta la serie (lo mas lento)
python -m cielociego medir --orbita 142                 # fuerza una orbita concreta
python -m cielociego catalogo                           # solo el catalogo
python -m cielociego pruebas                            # 190 pruebas
```

La **órbita de la serie de radar se elige sola** según cuál cubra mejor tu predio,
y el reparto se imprime para que puedas comprobarlo:

```
orbitas    {77: 341, 142: 265, 69: 248}  ->  se usa la 77 (341 escenas)
```

Si el fichero trae más de un polígono, **falla a propósito**: mezclar dos predios
en una sola medida es exactamente el error que este proyecto existe para evitar.

```json
{"type":"FeatureCollection","features":[{"type":"Feature",
 "properties":{"nombre":"Mi finca","area_ha":73.5},
 "geometry":{"type":"Polygon","coordinates":[[[-73.82,10.40], ...]]}}]}
```

## Los datos que trae, y los que no

`datos/area_demo.geojson` es un **área de demostración** de 256 ha: un rectángulo
trazado **a propósito cruzando linderos**, que no corresponde a ningún predio ni
a la propiedad de nadie. Está para que la herramienta se pueda ejecutar nada más
clonar el repositorio.

**Los polígonos de los dos predios que se midieron no están incluidos.** Los
resultados del README y del informe salen de dos predios reales del Magdalena
(73,5 ha en Fundación y 284,1 ha en el corredor bananero), pero sus coordenadas
son datos de un curso universitario y uno de ellos es el área de estudio de un
docente. Publicar la ubicación exacta de tierra ajena junto a un análisis que
dice «aquí pasó algo» no es cosa de este repositorio.

Las **cifras agregadas sí están** en `salidas/`, y no permiten reconstruir los
polígonos: lo más fino que aparece es el código de tesela, que cubre 110 × 110 km.

Para medir tu propio predio basta un GeoJSON con **un solo** *feature* de tipo
`Polygon` en EPSG:4326.

## Instalación

```bash
pip install -e ".[dev]"
```

Python 3.10+. Las dependencias llevan **cota por arriba** (`<3`, `<2`…) a
propósito: una herramienta que dice «esto se reproduce» no puede depender de que
la próxima versión mayor de rasterio o numpy no rompa nada. El límite convierte
una rotura silenciosa en un fallo de instalación, que se ve.

## Pruebas

190 pruebas, sin red: las de catálogo simulan el HTTP y las de SCL fabrican
rásters con valores conocidos.

```bash
python -m pytest tests/ -q --cov=cielociego     # 190 pruebas, 91 % de cobertura
mypy src/cielociego                              # limpio en 12 modulos
ruff check src/ tests/                           # limpio
```

Corren en **CI sobre Linux y Windows, en Python 3.10 y 3.12**, con el listón de
cobertura puesto en 75 % para que no pueda bajar sin que alguien se entere. La
medición contra los servicios públicos va en un flujo aparte, semanal: si falla,
no es que el código esté roto — es que cambió el catálogo, y eso también hay que
saberlo.

Lo que vigilan, más allá de que el código no reviente:

- **Paginación**: que un barrido corto **reviente** en vez de devolver de menos
  callando. La primera versión devolvía 100 de 819 sin dar error.
- **Mutación**: cambiar un píxel de 100 debe mover el resultado exactamente 0,01.
- **La máscara recorta de verdad**: mitad nube y mitad limpio; mirando solo la
  mitad limpia debe dar 0. Si la máscara no hiciera nada, saldría 0,5.
- **Huecos contados a mano**: vista el día 1 y el 10 → hueco del 2 al 9 = 8 días.
  Un error de un día ahí corre todas las cifras del informe sin que se note.
- **Determinismo con hilos**: la misma escena en serie y con 8 hilos debe dar
  valores idénticos, histograma incluido.
- **Tema de las gráficas**: que ningún color de texto quede fijo, o el informe se
  vuelve ilegible en tema oscuro y nadie lo nota hasta publicarlo.
- **Promediar potencia, no decibelios**: el dB es logarítmico, así que promediarlo
  da la media geométrica y sesga a la baja. Con dos píxeles de −20 dB y 0 dB el
  sesgo es de **7,03 dB**. La prueba lleva el número contado a mano.
- **Una firma, no mil**: la primera versión pedía una firma por cada banda de cada
  escena — 1.180 llamadas — y el servidor devolvía **429**, dejando 536 medidas
  fuera *como si el radar no tuviera dato*. El token es de contenedor: se pide uno.
  La prueba comprueba que 1.000 ficheros con 16 hilos piden **un** token.
- **No mezclar órbitas**: dos pasadas del mismo día desde geometrías distintas dan
  valores distintos del mismo cultivo sin que haya cambiado nada.
- **La órbita no puede estar fija en el código**: la primera versión tenía escrita
  la 77, que cubre la Zona Bananera del Magdalena. En **Urabá** — la principal zona
  bananera de Colombia — esa órbita no pasa: son la 142 y la 48. La serie de radar
  salía **vacía y en silencio** en cualquier sitio que no fuera estos dos predios.
  Ahora se elige la más poblada de cada predio y se declara el reparto.
- **Un fallo de red no puede volverse un dato**: si una lectura se cae, la escena
  queda registrada como **fallo**, nunca como despejada, y se reintenta lo que es
  reintentable (429 y 5xx, con espera creciente y respetando `Retry-After`).

## De dónde salen los datos

- **Óptico y catálogo de radar**: Sentinel-2 L2A y Sentinel-1 GRD vía el catálogo
  STAC público de [Element84](https://earth-search.aws.element84.com/v1) sobre AWS.
- **Serie de retrodispersión**: Sentinel-1 **RTC** (corregido por terreno, ya
  geocodificado, en gamma0) del
  [Planetary Computer](https://planetarycomputer.microsoft.com), con firma anónima.
  No se usa el GRD crudo: viene en geometría de radar, no se puede recortar por
  lat/lon, y en AWS vive en un bucket de pago por peticionario.

Los COG se leen **por ventana**: nunca se descarga una escena entera.

## Licencia

MIT. Los datos Copernicus son de acceso libre bajo los términos de la ESA.
