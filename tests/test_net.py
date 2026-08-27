"""Tests for the retrying session.

Lo que garantizan: que un 429 o un 5xx transitorio NO acabe convertido en
"aqui no habia dato", y que un 404 no se reintente en balde.
"""
from __future__ import annotations

import pytest
from urllib3.util.retry import Retry

from cielociego.net import RETRYABLE_CODES, session


def politica(ses) -> Retry:
    return ses.get_adapter("https://x/").max_retries


def test_the_session_trae_reintentos_montados():
    p = politica(session())
    assert isinstance(p, Retry)
    assert p.total >= 3, "menos de 3 intentos no cubre un cut transitorio"


def test_retries_the_429_that_actually_bit_us():
    """429 is what left 536 of 590 measurements out during development."""
    assert 429 in politica(session()).status_forcelist


@pytest.mark.parametrize("codigo", [500, 502, 503, 504])
def test_retries_the_server_side_errors(codigo):
    assert codigo in politica(session()).status_forcelist


@pytest.mark.parametrize("codigo", [400, 401, 403, 404, 422])
def test_not_retries_the_that_not_improves_insisting(codigo):
    """A 404 is not fixed by repeating, and hiding it beats failing only in appearance."""
    assert codigo not in politica(session()).status_forcelist


def test_the_espera_grows_between_intentos():
    assert politica(session()).backoff_factor > 0, "sin backoff se martillea el servidor"


def test_respects_the_retry_after_header():
    """Es lo educado con un servicio publico y gratuito."""
    assert politica(session()).respect_retry_after_header is True


def test_reintenta_tambien_en_POST():
    """STAC is queried by POST: otherwise the catalogue would have no retries."""
    assert "POST" in politica(session()).allowed_methods


def test_identifies_with_a_user_agent_own():
    assert "cielociego" in session().headers["User-Agent"]


def test_the_parameters_can_be_tuned():
    p = politica(session(intentos=7, espera_base=2.5))
    assert p.total == 7 and p.backoff_factor == 2.5


def test_the_retryable_list_is_the_declared_one():
    assert set(politica(session()).status_forcelist) == set(RETRYABLE_CODES)
