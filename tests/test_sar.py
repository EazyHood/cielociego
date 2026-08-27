"""Pruebas del modulo de radar.

La mas importante es la del promediado: promediar decibelios en vez de
potencia lineal sesga la media a la baja, y el sesgo es del orden de lo que
se quiere detectar. Es un error que no se ve mirando la grafica.
"""
from __future__ import annotations

import numpy as np
import pytest

from cielociego.sar import Backscatter, by_orbit, mean_db, within_gap


def r(date, orb=142, vv=-5.0, vh=-11.0, error=None):
    return Backscatter(date, orb, "descending", "sentinel-1a", 100, vv, vh, error)


# --- the averaging, which is where the trap is ----------------------------
def test_media_of_a_valor_constant_is_ese_valor():
    lineal = np.full(500, 10 ** (-5.0 / 10))
    assert mean_db(lineal) == pytest.approx(-5.0, abs=1e-9)


def test_averaging_power_is_not_averaging_decibels():
    """Control numerico del sesgo. Dos pixels: -20 dB y 0 dB.

    En potencia:   (0,01 + 1) / 2 = 0,505  ->  -2,97 dB   <- lo correcto
    En decibelios: (-20 + 0)  / 2          ->  -10,00 dB  <- sesgo de 7 dB
    """
    lineal = np.array([10 ** (-20 / 10), 10 ** (0 / 10)])
    correcto = mean_db(lineal)
    ingenuo = float(np.mean(10 * np.log10(lineal)))
    assert correcto == pytest.approx(-2.9671, abs=1e-3)
    assert ingenuo == pytest.approx(-10.0, abs=1e-9)
    assert correcto - ingenuo > 7.0, "el sesgo del promedio en dB debe ser grande"


def test_the_bias_shows_up_on_a_realistic_field_too():
    """With a crop's typical spread the error is still appreciable."""
    rng = np.random.default_rng(20260826)
    db = rng.normal(-8.0, 2.5, 20_000)          # heterogeneidad realista
    lineal = 10 ** (db / 10)
    assert mean_db(lineal) - db.mean() > 0.3, "promediar en dB subestimaria"


def test_ceros_and_not_finitos_descartan():
    lineal = np.array([np.nan, 0.0, -1.0, np.inf, 10 ** (-6 / 10)])
    assert mean_db(lineal) == pytest.approx(-6.0, abs=1e-9)


def test_without_pixels_validos_returns_nan():
    assert np.isnan(mean_db(np.array([0.0, np.nan])))
    assert np.isnan(mean_db(np.array([])))


# --- razon de polarizacion -------------------------------------------------
def test_razon_is_vh_less_vv():
    assert r("2023-01-01", vv=-5.0, vh=-11.5).ratio_db == pytest.approx(-6.5)


# --- agrupacion por orbit: no mezclar geometrias --------------------------
def test_agrupa_by_orbit_and_ordena_by_date():
    g = by_orbit([r("2023-03-01", 142), r("2023-01-01", 142), r("2023-02-01", 77)])
    assert set(g) == {142, 77}
    assert [x.date for x in g[142]] == ["2023-01-01", "2023-03-01"]


def test_the_orbit_more_populated_va_first():
    g = by_orbit([r("2023-01-01", 77)] + [r(f"2023-01-0{d}", 142) for d in range(1, 5)])
    assert next(iter(g)) == 142


def test_the_medidas_with_error_not_enter_in_the_grupos():
    g = by_orbit([r("2023-01-01", 142), r("2023-01-02", 142, error="fallo de red")])
    assert len(g[142]) == 1


def test_two_orbits_on_one_day_are_not_merged():
    """The case that ruins a series: same date, different geometries."""
    g = by_orbit([r("2023-03-26", 142), r("2023-03-26", 77)])
    assert len(g) == 2 and all(len(v) == 1 for v in g.values())


# --- cruce con los huecos --------------------------------------------------
def test_covers_gap_incluye_the_ends():
    serie = [r("2024-04-12"), r("2024-04-13"), r("2024-06-01"), r("2024-07-10"), r("2024-07-11")]
    dentro = within_gap(serie, "2024-04-13", "2024-07-10")
    assert [x.date for x in dentro] == ["2024-04-13", "2024-06-01", "2024-07-10"]


def test_covers_gap_ignores_the_failed():
    serie = [r("2024-05-01"), r("2024-05-02", error="sin pixels")]
    assert len(within_gap(serie, "2024-04-13", "2024-07-10")) == 1


# --- la credential: de 1.180 requests_made a 1 --------------------------------
class SesionToken:
    """Fake session counting how many times the token is requested."""

    def __init__(self, expires="2099-01-01T00:00:00Z"):
        self.veces = 0
        self.expires = expires

    def get(self, url, timeout=None, params=None):
        self.veces += 1
        s = self

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"token": "sp=rl&sr=c&sig=XXX", "msft:expiry": s.expires}

        return R()


def test_one_token_covers_a_thousand_files():
    """El fallo real: 1.180 firmas -> 429 -> 536 medidas perdidas en silencio."""
    from cielociego.sar import Credential

    cred, ses = Credential(), SesionToken()
    for i in range(1000):
        cred.sign(f"https://x.blob.core.windows.net/c/escena{i}/iw-vv.rtc.tiff", ses)
    assert ses.veces == 1, f"se pidieron {ses.veces} tokens; debe ser 1"
    assert cred.requests_made == 1


def test_the_token_pega_to_the_href():
    from cielociego.sar import Credential

    firmado = Credential().sign("https://x/c/a.tiff", SesionToken())
    assert firmado == "https://x/c/a.tiff?sp=rl&sr=c&sig=XXX"


def test_a_href_ya_firmado_not_vuelve_to_firmar():
    from cielociego.sar import Credential

    cred, ses = Credential(), SesionToken()
    ya = "https://x/c/a.tiff?sig=ANTERIOR"
    assert cred.sign(ya, ses) == ya
    assert ses.veces == 0


def test_a_token_caducado_renueva():
    from cielociego.sar import Credential

    cred = Credential()
    cred.sign("https://x/c/a.tiff", SesionToken(expires="2000-01-01T00:00:00Z"))
    ses2 = SesionToken()
    cred.sign("https://x/c/b.tiff", ses2)
    assert ses2.veces == 1, "un token caducado debe renovarse"


def test_the_token_is_safe_between_threads():
    from concurrent.futures import ThreadPoolExecutor

    from cielociego.sar import Credential

    cred, ses = Credential(), SesionToken()
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda i: cred.sign(f"https://x/c/{i}.tiff", ses), range(400)))
    assert ses.veces == 1, f"con 16 workers se pidieron {ses.veces} tokens; debe ser 1"


# --- orbit choice: the defect that left the series empty away from home ---
def item_orb(orb, date="2023-01-01T00:00:00Z"):
    return {"properties": {"sat:relative_orbit": orb, "datetime": date}}


def test_picks_the_orbit_with_the_most_scenes():
    from cielociego.sar import pick_orbit

    items = [item_orb(77)] * 5 + [item_orb(142)] * 3 + [item_orb(69)] * 9
    assert pick_orbit(items) == 69


def test_the_tie_broken_igual_always():
    """Dos ejecuciones sobre los mismos datos deben elegir lo mismo."""
    from cielociego.sar import pick_orbit

    a = [item_orb(142)] * 4 + [item_orb(48)] * 4
    b = [item_orb(48)] * 4 + [item_orb(142)] * 4
    assert pick_orbit(a) == pick_orbit(b) == 48


def test_with_no_scenes_it_picks_nothing():
    from cielociego.sar import pick_orbit

    assert pick_orbit([]) is None
    assert pick_orbit([{"properties": {}}]) is None


def test_uraba_not_tiene_the_orbit_that_estaba_fixed_in_the_code():
    """The real defect, with the numbers measured on 2026-08-26.

    En Uraba -- la principal zona bananera de Colombia -- pasan la 142 y la 48,
    NO la 77 que estaba escrita en el codigo. Con la constante fija, la serie
    de radar salia vacia alli, y ademas en silencio.
    """
    from cielociego.sar import orbit_breakdown, pick_orbit

    uraba = [item_orb(142)] * 30 + [item_orb(48)] * 28
    reparto = orbit_breakdown(uraba)
    assert 77 not in reparto, "si la 77 apareciera, el caso de prueba ya no vale"
    assert pick_orbit(uraba) == 142
    assert reparto == {142: 30, 48: 28}


def test_the_breakdown_is_sorted_high_to_low():
    from cielociego.sar import orbit_breakdown

    items = [item_orb(77)] * 2 + [item_orb(142)] * 9 + [item_orb(69)] * 5
    assert list(orbit_breakdown(items)) == [142, 69, 77]


# --- registro de credenciales (antes era un singleton global) --------------
def test_the_same_collection_reuses_its_credential():
    from cielociego.sar import credential, forget_credentials

    forget_credentials()
    assert credential("sentinel-1-rtc") is credential("sentinel-1-rtc")


def test_different_collections_do_not_share_a_token():
    """El singleton viejo habria servido el token equivocado."""
    from cielociego.sar import credential, forget_credentials

    forget_credentials()
    a, b = credential("sentinel-1-rtc"), credential("otra-collection")
    assert a is not b
    assert a.collection == "sentinel-1-rtc" and b.collection == "otra-collection"


def test_the_tokens_can_be_forgotten():
    """Without this the state leaks between tests."""
    from cielociego.sar import credential, forget_credentials

    forget_credentials()
    primera = credential()
    forget_credentials()
    assert credential() is not primera


def test_the_registry_survives_many_threads():
    from concurrent.futures import ThreadPoolExecutor

    from cielociego.sar import credential, forget_credentials

    forget_credentials()
    with ThreadPoolExecutor(16) as ex:
        creds = list(ex.map(lambda _: credential("x"), range(200)))
    assert len({id(c) for c in creds}) == 1, "16 workers deben compartir una sola"
