# Copyright (c) 2026 Jhonatan del Rio Mejia. All rights reserved.
# Codigo bajo licencia MIT (ver LICENSE).
# El contenido escrito va aparte: CC BY-NC-ND 4.0 (ver LICENSE-TEXTO.md).
"""cielociego -- how many days the optical satellite cannot see a field.

Measures, over a real polygon rather than the whole tile:
  1. how many Sentinel-2 passes there are per year,
  2. what fraction of the field each pass leaves unusable,
  3. how long the stretches with no usable observation run,
  4. whether Sentinel-1, which sees through cloud, passes inside them.
"""

__version__ = "0.1.0"
