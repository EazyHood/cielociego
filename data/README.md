# data/

`area_demo.geojson` — **área de demostración**, 256 ha sobre el corredor bananero
del Magdalena. Es un rectángulo trazado **a propósito cruzando linderos**: no
corresponde a ningún predio ni a la propiedad de nadie. Está solo para poder
ejecutar la herramienta sobre una zona donde el fenómeno se ve.

## Por qué no están los dos predios que se midieron

Los resultados publicados en el README y en el informe se midieron sobre dos
predios reales del Magdalena (73,5 ha en Fundación y 284,1 ha en el corredor
bananero). **Sus polígonos no se incluyen aquí a propósito**: son datos de un
curso universitario y uno de ellos es el área de estudio de un docente, usada
para el informe de un compañero. Publicar coordenadas exactas de tierra ajena
junto a un análisis que dice «aquí pasó algo» no es cosa de este repositorio.

Las **cifras agregadas** sí están (`outputs/`), y no permiten reconstruir los
polígonos: lo más fino que aparece es el código de tesela, que cubre 110×110 km.

## Tu propio predio

Un GeoJSON con **un solo** *feature* de tipo `Polygon` en EPSG:4326, y ya:

```bash
python -m cielociego measure --field mi_finca.geojson
```

Si el fichero trae más de un polígono, la herramienta **falla a propósito**:
mezclar dos predios en una sola medida es justo el error que existe para evitar.
