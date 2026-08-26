"""Sesion HTTP con reintentos. Una sola, compartida por todo el paquete.

POR QUE EXISTE
--------------
Durante el desarrollo el Planetary Computer devolvio **429 Too Many Requests**
y 536 de 590 medidas quedaron fuera -- registradas como si el radar no tuviera
dato, que es una conclusion falsa por fontaneria. Se arreglo la causa (pedir un
token de contenedor en vez de firmar cada fichero), pero eso no basta: un
barrido de 1.200 lecturas contra un servicio publico se topa con cortes
transitorios haga lo que haga.

En una herramienta de medida, un fallo de red que se traga en silencio se
convierte en un dato. Por eso se reintenta lo que es reintentable -- 429 y los
5xx -- con espera creciente, y se deja fallar todo lo demas: un 404 no mejora
por insistir, y esconderlo seria peor.

`Retry` de urllib3 respeta la cabecera `Retry-After` cuando el servidor la
manda, que es lo educado con un servicio gratuito.
"""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Reintentables a proposito: 429 (limite de peticiones) y los 5xx del servidor.
# Un 404 o un 403 NO se reintentan: no mejoran por insistir.
CODIGOS_REINTENTABLES = (429, 500, 502, 503, 504)
INTENTOS = 4
ESPERA_BASE = 1.0  # 1 s, 2 s, 4 s... (backoff exponencial)
ESPERA_MAXIMA = 30.0


def sesion(
    *,
    intentos: int = INTENTOS,
    espera_base: float = ESPERA_BASE,
    espera_maxima: float = ESPERA_MAXIMA,
) -> requests.Session:
    """Sesion con reintentos y espera creciente, lista para un barrido largo."""
    politica = Retry(
        total=intentos,
        connect=intentos,
        read=intentos,
        status=intentos,
        backoff_factor=espera_base,
        status_forcelist=CODIGOS_REINTENTABLES,
        allowed_methods=frozenset({"GET", "POST"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    if hasattr(politica, "backoff_max"):  # urllib3 >= 2
        politica.backoff_max = espera_maxima

    ses = requests.Session()
    adaptador = HTTPAdapter(max_retries=politica, pool_maxsize=32, pool_connections=32)
    ses.mount("https://", adaptador)
    ses.mount("http://", adaptador)
    ses.headers.update({"User-Agent": "cielociego/0.1.0 (+medicion de nubosidad sobre predios)"})
    return ses
