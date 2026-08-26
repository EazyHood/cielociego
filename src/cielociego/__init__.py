"""cielociego - cuanto tiempo el satelite optico NO puede ver un predio, y si el radar lo cubre.

Mide, sobre un poligono real y no sobre la tesela entera:
  1. cuantas pasadas de Sentinel-2 hay al ano,
  2. que fraccion del predio queda inservible por nube y sombra en cada pasada,
  3. cuanto duran los huecos sin una sola observacion util,
  4. si Sentinel-1 (radar, atraviesa nubes) tiene pasada dentro de esos huecos.
"""

__version__ = "0.1.0"
