"""Pruebas de la sesion con reintentos.

Lo que garantizan: que un 429 o un 5xx transitorio NO acabe convertido en
"aqui no habia dato", y que un 404 no se reintente en balde.
"""
from __future__ import annotations

import pytest
from urllib3.util.retry import Retry

from cielociego.red import CODIGOS_REINTENTABLES, sesion


def politica(ses) -> Retry:
    return ses.get_adapter("https://x/").max_retries


def test_la_sesion_trae_reintentos_montados():
    p = politica(sesion())
    assert isinstance(p, Retry)
    assert p.total >= 3, "menos de 3 intentos no cubre un corte transitorio"


def test_reintenta_el_429_que_nos_mordio_de_verdad():
    """429 es el que dejo 536 de 590 medidas fuera durante el desarrollo."""
    assert 429 in politica(sesion()).status_forcelist


@pytest.mark.parametrize("codigo", [500, 502, 503, 504])
def test_reintenta_los_errores_del_servidor(codigo):
    assert codigo in politica(sesion()).status_forcelist


@pytest.mark.parametrize("codigo", [400, 401, 403, 404, 422])
def test_no_reintenta_lo_que_no_mejora_insistiendo(codigo):
    """Un 404 no se arregla repitiendo, y esconderlo seria peor que fallar."""
    assert codigo not in politica(sesion()).status_forcelist


def test_la_espera_crece_entre_intentos():
    assert politica(sesion()).backoff_factor > 0, "sin backoff se martillea el servidor"


def test_respeta_la_cabecera_retry_after():
    """Es lo educado con un servicio publico y gratuito."""
    assert politica(sesion()).respect_retry_after_header is True


def test_reintenta_tambien_en_POST():
    """El STAC se consulta por POST: si no, el catalogo no tendria reintentos."""
    assert "POST" in politica(sesion()).allowed_methods


def test_se_identifica_con_un_user_agent_propio():
    assert "cielociego" in sesion().headers["User-Agent"]


def test_los_parametros_se_pueden_ajustar():
    p = politica(sesion(intentos=7, espera_base=2.5))
    assert p.total == 7 and p.backoff_factor == 2.5


def test_la_lista_de_reintentables_es_la_declarada():
    assert set(politica(sesion()).status_forcelist) == set(CODIGOS_REINTENTABLES)
