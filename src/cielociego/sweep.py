"""Measure every acquisition of a field, in parallel.

Reads are network-bound rather than CPU-bound, so threads. Whatever fails in the
fast pass is retried serially: a transient stumble must not end up recorded as
"no data here". See DECISIONS.md #10.
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

from .fields import Field
from .scl import View, measure_view


@dataclass
class Result:
    field: str
    area_ha: float | None
    views: list[View]
    failed: list[View]
    recovered: int = 0      # failed first time round, came through on the retry

    @property
    def total(self) -> int:
        return len(self.views) + len(self.failed)

    def save(self, path: str | Path, provenance: dict[str, Any] | None = None) -> Path:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "field": self.field,
                    "provenance": provenance or {},
                    "area_ha": self.area_ha,
                    "medidas": len(self.views),
                    "failed": len(self.failed),
                    "recovered_on_retry": self.recovered,
                    "views": [v.dict() for v in self.views],
                    "errores": [v.dict() for v in self.failed],
                },
                ensure_ascii=False,
                indent=1,
            ),
            encoding="utf-8",
        )
        return path


def sweep(
    field: Field,
    scenes: Sequence[dict[str, Any]],
    *,
    workers: int = 10,
    avisa: Callable[[int, int], None] | None = None,
    retries: int = 2,
    backoff: float = 3.0,
) -> Result:
    """Measure every acquisition (dicts with 'scl', 'date', 'id', 'cc').

    Whatever fails in the fast pass is retried serially, up to `retries` times,
    waiting `backoff` seconds longer each round. `retries=0` disables it.
    """
    views: list[View] = []
    failed: list[View] = []

    def una(t: dict[str, Any]) -> View:
        return measure_view(
            t["scl"], field.geometry,
            date=t["date"][:10], scene_id=t.get("id", ""), tile_cloud=t.get("cc"),
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futuros = {pool.submit(una, t): t for t in scenes if t.get("scl")}
        for n, fut in enumerate(as_completed(futuros), 1):
            v = fut.result()
            (failed if v.error else views).append(v)
            if avisa and (n % 25 == 0 or n == len(futuros)):
                avisa(n, len(futuros))

    # Second pass: serial and slow, to tell a network stumble apart from a file
    # that genuinely is not there any more.
    recovered = 0
    for vuelta in range(retries):
        if not failed:
            break
        time.sleep(backoff * (vuelta + 1))
        quedan: list[View] = []
        por_fecha = {t["date"][:10]: t for t in scenes if t.get("scl")}
        for v in failed:
            t = por_fecha.get(v.date)
            nueva = una(t) if t else v
            if nueva.error:
                quedan.append(nueva)
            else:
                views.append(nueva)
                recovered += 1
        failed = quedan

    views.sort(key=lambda v: v.date)
    failed.sort(key=lambda v: v.date)
    return Result(field.name, field.area_ha, views, failed, recovered)


def _progress(n: int, total: int) -> None:  # pragma: no cover - out por consola
    hechos = int(30 * n / total)
    sys.stderr.write(f"\r  [{'#' * hechos}{'.' * (30 - hechos)}] {n}/{total}")
    sys.stderr.flush()
    if n == total:
        sys.stderr.write("\n")
