"""Sentinel-1 (radar) como relleno de los huecos que deja el optico.

LO QUE ESTE MODULO AFIRMA, Y LO QUE NO
--------------------------------------
AFIRMA: en la fecha X hubo una adquisicion de radar sobre el predio.
NO AFIRMA: que esa adquisicion diga lo mismo que habria dicho el optico.

El radar mide retrodispersion (rugosidad, geometria, humedad del suelo y
de la planta); el optico mide reflectancia (pigmento, clorofila). Un NDVI
no se sustituye por un VV/VH -- se COMPLEMENTA. Confundir "hay dato" con
"hay el mismo dato" seria vender un decorado por la partida, que es justo
lo que este proyecto existe para no hacer.

La pregunta honesta que se responde aqui es: durante los tramos en que el
optico esta ciego sobre el predio, hay ALGUNA observacion? Si la respuesta
es si, el hueco es de metodo (hay que aprender a usar radar) y no de datos.

CONSTELACION -- se mide, no se supone
-------------------------------------
S1A opera desde 2014. S1B fallo en diciembre de 2021 y se retiro; S1C se
lanzo a finales de 2024. Eso cambia la revisita a lo largo de la serie, y
por eso las pasadas por ano se CUENTAN en vez de asumir "cada 6 dias".
"""
from __future__ import annotations

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

# S1A_IW_GRDH_1SDV_20231222T230735_20231222T230800_051774_0640E8
_ID = re.compile(
    r"^(?P<plataforma>S1[A-D])_(?P<modo>\w{2})_(?P<producto>\w{4})_\w+?"
    r"_(?P<inicio>\d{8}T\d{6})_(?P<fin>\d{8}T\d{6})"
)


@dataclass(frozen=True)
class Pasada:
    fecha: date
    plataforma: str
    orbita: str          # ascending | descending
    modo: str
    polarizaciones: tuple[str, ...]

    @property
    def iso(self) -> str:
        return self.fecha.isoformat()


def identidad_s1(item: dict[str, Any]) -> tuple[str, str] | None:
    """(plataforma, instante de inicio) -- identidad fisica de la adquisicion."""
    m = _ID.match(item.get("id", ""))
    if not m:
        return None
    return m.group("plataforma"), m.group("inicio")


def a_pasadas(items: Iterable[dict[str, Any]]) -> list[Pasada]:
    """Convierte items STAC en Pasadas unicas, deduplicando por identidad fisica."""
    vistas: dict[tuple[str, str], Pasada] = {}
    for it in items:
        ident = identidad_s1(it)
        if ident is None:
            continue
        p = it.get("properties", {})
        try:
            f = datetime.fromisoformat(p["datetime"].replace("Z", "+00:00")).date()
        except (KeyError, ValueError):
            continue
        vistas.setdefault(
            ident,
            Pasada(
                fecha=f,
                plataforma=p.get("platform", ident[0]),
                orbita=p.get("sat:orbit_state", "?"),
                modo=p.get("sar:instrument_mode", "?"),
                polarizaciones=tuple(p.get("sar:polarizations") or ()),
            ),
        )
    return sorted(vistas.values(), key=lambda x: x.fecha)


@dataclass
class Hueco:
    """Tramo de dias sin una sola observacion optica util sobre el predio."""

    inicio: date          # primer dia sin vista util
    fin: date             # ultimo dia sin vista util
    pasadas_radar: int    # adquisiciones S1 dentro del tramo

    @property
    def dias(self) -> int:
        return (self.fin - self.inicio).days + 1

    @property
    def cubierto(self) -> bool:
        return self.pasadas_radar > 0


def huecos_opticos(
    fechas_utiles: Sequence[date], desde: date, hasta: date
) -> list[tuple[date, date]]:
    """Tramos entre observaciones utiles consecutivas, en dias sin dato.

    Un hueco es el intervalo ABIERTO entre dos vistas utiles: si hay vista
    util el dia 1 y el dia 10, el hueco son los dias 2..9 (8 dias). Los
    extremos de la serie tambien cuentan como hueco si empieza o acaba
    ciega, porque un ano que arranca con 40 dias sin ver es informacion.
    """
    utiles = sorted(f for f in set(fechas_utiles) if desde <= f <= hasta)
    tramos: list[tuple[date, date]] = []
    cursor = desde
    for f in utiles:
        if f > cursor:
            tramos.append((cursor, f - timedelta(days=1)))
        cursor = f + timedelta(days=1)
    if cursor <= hasta:
        tramos.append((cursor, hasta))
    return tramos


def cruza(
    fechas_utiles: Sequence[date],
    pasadas: Sequence[Pasada],
    desde: date,
    hasta: date,
) -> list[Hueco]:
    """Para cada hueco del optico, cuenta cuantas pasadas de radar cayeron dentro."""
    fechas_radar = sorted(p.fecha for p in pasadas)
    salida: list[Hueco] = []
    for ini, fin in huecos_opticos(fechas_utiles, desde, hasta):
        n = sum(1 for f in fechas_radar if ini <= f <= fin)
        salida.append(Hueco(ini, fin, n))
    return salida
