"""Ficha de procedencia que acompana a cada salida.

POR QUE
-------
Sin esto, dentro de un ano nadie puede saber con que version del codigo, que
umbral y que rango de fechas salio un JSON de `salidas/`. Un numero sin su
procedencia no es reproducible: es una cifra suelta que hay que creerse.

Se guarda el hash del GeoJSON de entrada a proposito -- si alguien retoca el
poligono, los resultados viejos dejan de coincidir y se ve por que.
"""
from __future__ import annotations

import hashlib
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from . import __version__


def _commit() -> str | None:
    """SHA corto del repositorio, si lo hay. Nunca revienta."""
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True, text=True, timeout=5, check=False,
        )
        sha = r.stdout.strip()
        return sha or None
    except Exception:
        return None


def huella(ruta: str | Path) -> str | None:
    """SHA-256 de un fichero, para detectar que la entrada cambio."""
    try:
        return hashlib.sha256(Path(ruta).read_bytes()).hexdigest()[:16]
    except Exception:
        return None


def ficha(**parametros: Any) -> dict[str, Any]:
    """Ficha con version, momento, entorno y los parametros de esta medida."""
    return {
        "version": __version__,
        "commit": _commit(),
        "medido_en": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "python": sys.version.split()[0],
        "sistema": platform.system(),
        "parametros": {k: v for k, v in parametros.items() if v is not None},
    }
