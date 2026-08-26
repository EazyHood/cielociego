"""Pruebas del modulo de radar.

La mas importante es la del promediado: promediar decibelios en vez de
potencia lineal sesga la media a la baja, y el sesgo es del orden de lo que
se quiere detectar. Es un error que no se ve mirando la grafica.
"""
from __future__ import annotations

import numpy as np
import pytest

from cielociego.sar import Retro, cubre_hueco, media_db, por_orbita


def r(fecha, orb=142, vv=-5.0, vh=-11.0, error=None):
    return Retro(fecha, orb, "descending", "sentinel-1a", 100, vv, vh, error)


# --- el promediado, que es donde esta la trampa ----------------------------
def test_media_de_un_valor_constante_es_ese_valor():
    lineal = np.full(500, 10 ** (-5.0 / 10))
    assert media_db(lineal) == pytest.approx(-5.0, abs=1e-9)


def test_promediar_potencia_no_es_promediar_decibelios():
    """Control numerico del sesgo. Dos pixeles: -20 dB y 0 dB.

    En potencia:   (0,01 + 1) / 2 = 0,505  ->  -2,97 dB   <- lo correcto
    En decibelios: (-20 + 0)  / 2          ->  -10,00 dB  <- sesgo de 7 dB
    """
    lineal = np.array([10 ** (-20 / 10), 10 ** (0 / 10)])
    correcto = media_db(lineal)
    ingenuo = float(np.mean(10 * np.log10(lineal)))
    assert correcto == pytest.approx(-2.9671, abs=1e-3)
    assert ingenuo == pytest.approx(-10.0, abs=1e-9)
    assert correcto - ingenuo > 7.0, "el sesgo del promedio en dB debe ser grande"


def test_el_sesgo_aparece_tambien_en_un_predio_realista():
    """Con dispersion tipica de un cultivo el error sigue siendo apreciable."""
    rng = np.random.default_rng(20260826)
    db = rng.normal(-8.0, 2.5, 20_000)          # heterogeneidad realista
    lineal = 10 ** (db / 10)
    assert media_db(lineal) - db.mean() > 0.3, "promediar en dB subestimaria"


def test_ceros_y_no_finitos_se_descartan():
    lineal = np.array([np.nan, 0.0, -1.0, np.inf, 10 ** (-6 / 10)])
    assert media_db(lineal) == pytest.approx(-6.0, abs=1e-9)


def test_sin_pixeles_validos_devuelve_nan():
    assert np.isnan(media_db(np.array([0.0, np.nan])))
    assert np.isnan(media_db(np.array([])))


# --- razon de polarizacion -------------------------------------------------
def test_razon_es_vh_menos_vv():
    assert r("2023-01-01", vv=-5.0, vh=-11.5).razon_db == pytest.approx(-6.5)


# --- agrupacion por orbita: no mezclar geometrias --------------------------
def test_agrupa_por_orbita_y_ordena_por_fecha():
    g = por_orbita([r("2023-03-01", 142), r("2023-01-01", 142), r("2023-02-01", 77)])
    assert set(g) == {142, 77}
    assert [x.fecha for x in g[142]] == ["2023-01-01", "2023-03-01"]


def test_la_orbita_mas_poblada_va_primera():
    g = por_orbita([r("2023-01-01", 77)] + [r(f"2023-01-0{d}", 142) for d in range(1, 5)])
    assert list(g)[0] == 142


def test_las_medidas_con_error_no_entran_en_los_grupos():
    g = por_orbita([r("2023-01-01", 142), r("2023-01-02", 142, error="fallo de red")])
    assert len(g[142]) == 1


def test_dos_orbitas_del_mismo_dia_no_se_fusionan():
    """El caso que arruina una serie: misma fecha, geometrias distintas."""
    g = por_orbita([r("2023-03-26", 142), r("2023-03-26", 77)])
    assert len(g) == 2 and all(len(v) == 1 for v in g.values())


# --- cruce con los huecos --------------------------------------------------
def test_cubre_hueco_incluye_los_extremos():
    serie = [r("2024-04-12"), r("2024-04-13"), r("2024-06-01"), r("2024-07-10"), r("2024-07-11")]
    dentro = cubre_hueco(serie, "2024-04-13", "2024-07-10")
    assert [x.fecha for x in dentro] == ["2024-04-13", "2024-06-01", "2024-07-10"]


def test_cubre_hueco_ignora_las_fallidas():
    serie = [r("2024-05-01"), r("2024-05-02", error="sin pixeles")]
    assert len(cubre_hueco(serie, "2024-04-13", "2024-07-10")) == 1


# --- la credencial: de 1.180 peticiones a 1 --------------------------------
class SesionToken:
    """Sesion falsa que cuenta cuantas veces se pide el token."""

    def __init__(self, caduca="2099-01-01T00:00:00Z"):
        self.veces = 0
        self.caduca = caduca

    def get(self, url, timeout=None, params=None):
        self.veces += 1
        s = self

        class R:
            status_code = 200

            def raise_for_status(self):
                pass

            def json(self):
                return {"token": "sp=rl&sr=c&sig=XXX", "msft:expiry": s.caduca}

        return R()


def test_el_token_se_pide_una_sola_vez_para_mil_ficheros():
    """El fallo real: 1.180 firmas -> 429 -> 536 medidas perdidas en silencio."""
    from cielociego.sar import Credencial

    cred, ses = Credencial(), SesionToken()
    for i in range(1000):
        cred.firma(f"https://x.blob.core.windows.net/c/escena{i}/iw-vv.rtc.tiff", ses)
    assert ses.veces == 1, f"se pidieron {ses.veces} tokens; debe ser 1"
    assert cred.peticiones == 1


def test_el_token_se_pega_al_href():
    from cielociego.sar import Credencial

    firmado = Credencial().firma("https://x/c/a.tiff", SesionToken())
    assert firmado == "https://x/c/a.tiff?sp=rl&sr=c&sig=XXX"


def test_un_href_ya_firmado_no_se_vuelve_a_firmar():
    from cielociego.sar import Credencial

    cred, ses = Credencial(), SesionToken()
    ya = "https://x/c/a.tiff?sig=ANTERIOR"
    assert cred.firma(ya, ses) == ya
    assert ses.veces == 0


def test_un_token_caducado_se_renueva():
    from cielociego.sar import Credencial

    cred = Credencial()
    cred.firma("https://x/c/a.tiff", SesionToken(caduca="2000-01-01T00:00:00Z"))
    ses2 = SesionToken()
    cred.firma("https://x/c/b.tiff", ses2)
    assert ses2.veces == 1, "un token caducado debe renovarse"


def test_el_token_es_seguro_entre_hilos():
    from concurrent.futures import ThreadPoolExecutor

    from cielociego.sar import Credencial

    cred, ses = Credencial(), SesionToken()
    with ThreadPoolExecutor(16) as ex:
        list(ex.map(lambda i: cred.firma(f"https://x/c/{i}.tiff", ses), range(400)))
    assert ses.veces == 1, f"con 16 hilos se pidieron {ses.veces} tokens; debe ser 1"
