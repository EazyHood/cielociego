# Registro de cambios

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado semántico.

## [0.1.0] — 2026-08-27

Primera versión pública. Mide, **sobre el polígono real de un predio y no sobre
la tesela**, cuántos días el satélite óptico no puede verlo, y si el radar cubre
el hueco.

### Qué hace

- Descarga el catálogo Sentinel-2 y **deduplica por línea de procesado**.
- Lee la banda SCL **recortada al polígono** y calcula la fracción inservible.
- Calcula los tramos sin observación útil y los cruza con las pasadas de
  Sentinel-1.
- Extrae la serie de retrodispersión (Sentinel-1 RTC), **eligiendo la órbita por
  predio** para no mezclar geometrías.
- Analiza la serie: pendiente con error estándar robusto a autocorrelación y
  comparación de cuatro formas de cambio por BIC.

### Lo medido sobre dos predios del Magdalena, 2019–2026

- **89 % y 91 % de los días** sin una sola observación óptica aprovechable.
- Hueco más largo: **89 días** seguidos.
- **66 de 66** huecos de 15 días o más tienen pasada de radar dentro.
- El titular aguanta cualquier definición de nube: con la más generosa siguen
  siendo **82 % y 84 %**.

### Decisiones de método que se declaran, no se esconden

- La deduplicación se queda con la línea de procesado más alta, lo que da la
  estimación **conservadora**: el 6,6 % de las tomas cruza el umbral de utilidad
  según la versión, y siempre en el sentido de marcar más nube.
- Una sola órbita relativa por serie: mezclarlas inventa escalones que no vienen
  del suelo.
- Umbral de «útil» al 10 % del predio tapado; moverlo entre 0 % y 50 % no cambia
  la conclusión.
- Por debajo de 25 píxeles la medida sale **marcada con aviso**: con menos, el
  porcentaje no tiene resolución y el borde del polígono domina.

### Lo que NO afirma

Un NDVI no se sustituye por un VV/VH. El radar tampoco gana siempre en número.
Y qué pasó en el suelo del predio que cambió no se sabe: hace falta campo o
registros de siembra.

### Fiabilidad

190 pruebas sin red · 92 % de cobertura · `ruff` y `mypy` limpios · CI en Linux
y Windows sobre Python 3.10 y 3.12 · procedencia (versión, commit, fecha,
parámetros) en cada salida.

[0.1.0]: https://github.com/EazyHood/cielociego/releases/tag/v0.1.0
