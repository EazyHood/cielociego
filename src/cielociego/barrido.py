"""Barrido: mide la SCL de TODAS las tomas de un predio, en paralelo.

Lee por ventana desde el bucket publico, asi que el cuello es la latencia de
red, no la CPU: hilos, no procesos. Cada toma que falla queda registrada con
su error; el barrido no muere por una escena corrupta ni la da por despejada.

POR QUE HAY UNA SEGUNDA PASADA
-------------------------------
Medido el 2026-08-26: el mismo barrido dio **0 fallidas por la manana y 14 por
la tarde**, y al releer esas 14 el error era `Could not resolve host` -- un
fallo de DNS de la maquina, no de los ficheros. Sin segunda pasada, la
herramienta escribe un tropiezo de red como si fuera "aqui no habia dato", y
alguien con mala conexion obtiene otra respuesta sin saber que la diferencia
es su router y no el cielo.

La segunda pasada va **en serie y con espera creciente**: si el problema era
saturacion o un corte, insistir despacio lo resuelve; y si la escena esta
muerta de verdad -- como la del 23-ene-2024, que apunta a una ruta que ya no
existe -- vuelve a fallar y entonces si se declara.
"""
from __future__ import annotations

import json
import sys
import time
from collections.abc import Callable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .predios import Predio
from .scl import Vista, mide_vista


@dataclass
class Resultado:
    predio: str
    area_ha: float | None
    vistas: list[Vista]
    fallidas: list[Vista]
    recuperadas: int = 0      # fallaron a la primera y salieron en la segunda

    @property
    def total(self) -> int:
        return len(self.vistas) + len(self.fallidas)

    def guarda(self, ruta: str | Path, procedencia: dict[str, Any] | None = None) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(
                {
                    "predio": self.predio,
                    "procedencia": procedencia or {},
                    "area_ha": self.area_ha,
                    "medidas": len(self.vistas),
                    "fallidas": len(self.fallidas),
                    "recuperadas_en_segunda_pasada": self.recuperadas,
                    "vistas": [v.dict() for v in self.vistas],
                    "errores": [v.dict() for v in self.fallidas],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        return ruta


def barre(
    predio: Predio,
    tomas: Sequence[dict[str, Any]],
    *,
    hilos: int = 10,
    avisa: Callable[[int, int], None] | None = None,
    reintentos: int = 2,
    espera: float = 3.0,
) -> Resultado:
    """Mide todas las `tomas` (dicts con 'scl', 'fecha', 'id', 'cc').

    Lo que falla en la pasada rapida se reintenta **en serie**, hasta
    `reintentos` veces, esperando `espera` segundos mas cada vez. Poner
    `reintentos=0` desactiva la segunda pasada.
    """
    vistas: list[Vista] = []
    fallidas: list[Vista] = []

    def una(t: dict[str, Any]) -> Vista:
        return mide_vista(
            t["scl"], predio.geometria,
            fecha=t["fecha"][:10], id_toma=t.get("id", ""), cc_tesela=t.get("cc"),
        )

    with ThreadPoolExecutor(max_workers=hilos) as pool:
        futuros = {pool.submit(una, t): t for t in tomas if t.get("scl")}
        for n, fut in enumerate(as_completed(futuros), 1):
            v = fut.result()
            (fallidas if v.error else vistas).append(v)
            if avisa and (n % 25 == 0 or n == len(futuros)):
                avisa(n, len(futuros))

    # Segunda pasada: en serie y despacio, para separar el tropiezo de red
    # del fichero que de verdad ya no esta.
    recuperadas = 0
    for vuelta in range(reintentos):
        if not fallidas:
            break
        time.sleep(espera * (vuelta + 1))
        quedan: list[Vista] = []
        por_fecha = {t["fecha"][:10]: t for t in tomas if t.get("scl")}
        for v in fallidas:
            t = por_fecha.get(v.fecha)
            nueva = una(t) if t else v
            if nueva.error:
                quedan.append(nueva)
            else:
                vistas.append(nueva)
                recuperadas += 1
        fallidas = quedan

    vistas.sort(key=lambda v: v.fecha)
    fallidas.sort(key=lambda v: v.fecha)
    return Resultado(predio.nombre, predio.area_ha, vistas, fallidas, recuperadas)


def _barra(n: int, total: int) -> None:  # pragma: no cover - salida por consola
    hechos = int(30 * n / total)
    sys.stderr.write(f"\r  [{'#' * hechos}{'.' * (30 - hechos)}] {n}/{total}")
    sys.stderr.flush()
    if n == total:
        sys.stderr.write("\n")
