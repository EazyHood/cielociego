"""Shared HTTP session with retries.

Retries what is worth retrying -- 429 and 5xx, with growing backoff, honouring
`Retry-After`. Not 404: it does not improve by insisting and hiding it would be
worse. See DECISIONS.md #10.
"""
from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Retryable on purpose: 429 (rate limit) and the server-side 5xx. A 404 or a
# 403 is not -- it does not improve by insisting.
RETRYABLE_CODES = (429, 500, 502, 503, 504)
ATTEMPTS = 4
BACKOFF_BASE = 1.0  # 1 s, 2 s, 4 s... exponential backoff
BACKOFF_MAX = 30.0


def session(
    *,
    intentos: int = ATTEMPTS,
    espera_base: float = BACKOFF_BASE,
    espera_maxima: float = BACKOFF_MAX,
) -> requests.Session:
    """Sesion con retries y backoff creciente, lista para un sweep largo."""
    politica = Retry(
        total=intentos,
        connect=intentos,
        read=intentos,
        status=intentos,
        backoff_factor=espera_base,
        status_forcelist=RETRYABLE_CODES,
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
    ses.headers.update({"User-Agent": "cielociego/0.1.0 (+medicion de nubosidad sobre fields)"})
    return ses
