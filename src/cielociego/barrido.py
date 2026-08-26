"""Barrido: mide la SCL de TODAS las tomas de un predio, en paralelo.

Lee por ventana desde el bucket publico, asi que el cuello es la latencia de
red, no la CPU: hilos, no procesos. Cada toma que falla queda registrada con
su error; el barrido no muere por una escena corrupta ni la da por despejada.
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from .predios import Predio
from .scl import Vista, mide_vista


@dataclass
class Resultado:
    predio: str
    area_ha: float | None
    vistas: list[Vista]
    fallidas: list[Vista]

    @property
    def total(self) -> int:
        return len(self.vistas) + len(self.fallidas)

    def guarda(self, ruta: str | Path) -> Path:
        ruta = Path(ruta)
        ruta.parent.mkdir(parents=True, exist_ok=True)
        ruta.write_text(
            json.dumps(
                {
                    "predio": self.predio,
                    "area_ha": self.area_ha,
                    "medidas": len(self.vistas),
                    "fallidas": len(self.fallidas),
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
) -> Resultado:
    """Mide todas las `tomas` (dicts con 'scl', 'fecha', 'id', 'cc')."""
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

    vistas.sort(key=lambda v: v.fecha)
    fallidas.sort(key=lambda v: v.fecha)
    return Resultado(predio.nombre, predio.area_ha, vistas, fallidas)


def _barra(n: int, total: int) -> None:  # pragma: no cover - salida por consola
    hechos = int(30 * n / total)
    sys.stderr.write(f"\r  [{'#' * hechos}{'.' * (30 - hechos)}] {n}/{total}")
    sys.stderr.flush()
    if n == total:
        sys.stderr.write("\n")
