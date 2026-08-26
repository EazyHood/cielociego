# cielociego

**Cuánto tiempo el satélite óptico no puede ver un predio, y si el radar cubre el hueco.**

Medido sobre dos predios reales del Magdalena (Colombia), 2019–2026:
**el 89 % y el 91 % de los días no hubo una sola observación óptica aprovechable.**
El radar, que atraviesa la nube, tuvo pasada dentro de **los 66 huecos largos, sin
una sola excepción** — y su serie no es ruido: detectó en uno de los predios una
subida sostenida de **3,5 dB en siete años** que sobrevive al control de
instrumento.

Datos abiertos, sin cuenta, sin clave y sin coste. La medición completa se
reproduce en unos 90 segundos.

```bash
python -m cielociego medir
```

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

En el corredor bananero la serie **sube 3,5 dB en siete años**, de forma
sostenida, con autocorrelación de 0,96 entre pasadas consecutivas.

La subida arranca justo cuando se retiró Sentinel-1B, así que podía ser un cambio
de calibración disfrazado de cambio agronómico. **El control es medir la tendencia
dentro de un solo satélite:**

```
                                        tendencia de gamma0 VV
CORREDOR   todas las plataformas .............. +0,643 dB/ano
           solo Sentinel-1A (n=215) ........... +0,688 dB/ano   <- no desaparece
           solo Sentinel-1B (n=79) ............ +0,150 dB/ano
FUNDACION  solo Sentinel-1A (n=123) ........... -0,022 dB/ano   <- el vecino, plano
```

No desaparece: dentro de S1A sola la subida es incluso mayor. Y el predio vecino,
con los mismos satélites, la misma órbita y el mismo procesado, sale plano. En el
mismo año S1A y S1B difieren entre 0,04 y 0,50 dB, así que no hay sesgo de
plataforma que explique 3,5.

Algo cambió en esas 284 hectáreas entre 2021 y 2022 y siguió cambiando. **Qué fue,
este trabajo no lo sabe.** Lo que queda medido es que el radar lo registró de
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
  llano suele ser suelo húmedo, no sombra real. Se publican las dos.
- **Umbral de «útil»**: 10 % del predio tapado. Moverlo cambia el reparto entre
  útiles y huecos, no la conclusión.
- **Una toma se perdió.** La del 23-ene-2024 en Fundación apunta a una ruta
  antigua que ya no existe en el bucket. Queda declarada como fallo, no contada
  como despejada.

## Uso

```bash
python -m cielociego medir                              # todo
python -m cielociego medir --predio datos/mi_finca.geojson
python -m cielociego medir --desde 2022-01-01 --hilos 8
python -m cielociego medir --sin-radar                   # salta la serie (lo mas lento)
python -m cielociego catalogo                           # solo el catalogo
python -m cielociego pruebas                            # 67 pruebas
```

Un predio es un GeoJSON con **un solo** *feature* de tipo `Polygon` en EPSG:4326.
Si trae más de uno, falla a propósito: mezclar dos predios en una medida es
exactamente el error que este proyecto existe para evitar.

```json
{"type":"FeatureCollection","features":[{"type":"Feature",
 "properties":{"nombre":"Mi finca","area_ha":73.5},
 "geometry":{"type":"Polygon","coordinates":[[[-73.82,10.40], ...]]}}]}
```

## Instalación

```bash
pip install -e ".[dev]"
```

Necesita Python 3.10+, `rasterio`, `shapely`, `pyproj`, `numpy`, `requests` y
`matplotlib`.

## Pruebas

67 pruebas, sin red: las de catálogo simulan el HTTP y las de SCL fabrican
rásters con valores conocidos.

```bash
python -m pytest tests/ -q
```

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

## Datos

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
