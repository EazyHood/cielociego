"""Pruebas de la linea de comandos.

No tocan la red: comprueban que el parser acepta lo que documenta y que las
ordenes llegan a la funcion correcta con los argumentos correctos.
"""
from __future__ import annotations

import pytest

from cielociego.cli import construye_parser


def analiza(*argv):
    return construye_parser().parse_args(list(argv))


def test_sin_orden_falla_en_vez_de_no_hacer_nada():
    with pytest.raises(SystemExit):
        construye_parser().parse_args([])


@pytest.mark.parametrize("orden", ["medir", "catalogo", "pruebas"])
def test_las_tres_ordenes_documentadas_existen(orden):
    assert analiza(orden).orden == orden


def test_medir_trae_valores_por_defecto_usables():
    a = analiza("medir")
    assert a.desde == "2019-01-01" and a.hilos == 12
    assert a.predio is None and a.sin_radar is False and a.orbita is None


def test_se_pueden_pasar_varios_predios():
    a = analiza("medir", "--predio", "a.geojson", "--predio", "b.geojson")
    assert a.predio == ["a.geojson", "b.geojson"]


def test_las_fechas_y_los_hilos_se_pueden_fijar():
    a = analiza("medir", "--desde", "2022-01-01", "--hasta", "2023-12-31", "--hilos", "4")
    assert (a.desde, a.hasta, a.hilos) == ("2022-01-01", "2023-12-31", 4)


def test_la_orbita_se_puede_forzar():
    """Por defecto se elige sola; forzarla es para reproducir una medida vieja."""
    assert analiza("medir", "--orbita", "142").orbita == 142


def test_sin_radar_salta_el_paso_lento():
    assert analiza("medir", "--sin-radar").sin_radar is True


def test_hilos_no_numerico_falla():
    with pytest.raises(SystemExit):
        analiza("medir", "--hilos", "muchos")


def test_orden_inventada_falla():
    with pytest.raises(SystemExit):
        analiza("inventada")


def test_main_despacha_a_la_orden_pedida(monkeypatch):
    """`main` llama a la funcion de la orden pedida y devuelve su codigo."""
    import cielociego.cli as cli

    recibido = {}

    def falso(args):
        recibido["desde"] = args.desde
        return 7

    monkeypatch.setattr(cli, "cmd_catalogo", falso)
    # el parser fija args.func al construirse, asi que hay que reconstruirlo
    monkeypatch.setattr(
        cli, "construye_parser",
        lambda: _parser_con(cli, "catalogo", falso),
    )
    assert cli.main(["catalogo", "--desde", "2022-01-01"]) == 7
    assert recibido["desde"] == "2022-01-01"


def _parser_con(cli, orden, funcion):
    """Construye el parser real y sustituye la funcion de una sola orden."""
    p = construye_parser()
    sub = p._subparsers._group_actions[0]  # type: ignore[attr-defined]
    sub.choices[orden].set_defaults(func=funcion)
    return p


def test_sin_predios_avisa_en_vez_de_medir_la_nada(monkeypatch, tmp_path):
    """Un barrido sobre cero predios que dijera 'listo' seria mentira."""
    import cielociego.cli as cli

    monkeypatch.setattr(cli, "DATOS", tmp_path)
    with pytest.raises(SystemExit) as e:
        cli._predios(None)
    assert "no hay predios" in str(e.value)


def test_predios_explicitos_no_miran_la_carpeta(monkeypatch, tmp_path):
    from pathlib import Path

    import cielociego.cli as cli

    datos = Path(__file__).resolve().parents[1] / "datos"
    ruta = str(sorted(datos.glob("predio_*.geojson"))[0])
    monkeypatch.setattr(cli, "DATOS", tmp_path)  # vacia, pero da igual
    encontrados = cli._predios([ruta])
    assert len(encontrados) == 1 and encontrados[0][1].area_ha


def test_un_predio_que_falla_no_tumba_a_los_demas(monkeypatch, tmp_path, capsys):
    """Un corte de red a mitad tumbaba la medicion entera y perdia lo ya hecho."""
    from shapely.geometry import box

    import cielociego.cli as cli
    from cielociego.predios import Predio

    a = Predio("Predio bueno", box(0, 0, 1, 1), 10.0)
    b = Predio("Predio roto", box(2, 2, 3, 3), 20.0)
    monkeypatch.setattr(cli, "_predios", lambda r: [("a", a), ("b", b)])

    hechos = []

    def catalogo(clave, predio, desde, hasta):
        if predio.nombre == "Predio roto":
            raise ConnectionError("Read timed out")
        hechos.append(clave)
        return []

    monkeypatch.setattr(cli, "paso_catalogo", catalogo)
    monkeypatch.setattr(cli, "paso_scl", lambda *a, **k: {"vistas": []})
    monkeypatch.setattr(cli, "paso_radar", lambda *a, **k: None)
    monkeypatch.setattr(cli, "paso_sar", lambda *a, **k: None)

    args = construye_parser().parse_args(["medir"])
    codigo = cli.cmd_medir(args)

    salida = capsys.readouterr().out
    assert hechos == ["a"], "el predio bueno debe medirse igual"
    assert codigo == 1, "el codigo de salida avisa de que quedo incompleta"
    assert "MEDICION INCOMPLETA" in salida
    assert "Predio roto" in salida


def test_si_todos_van_bien_el_codigo_es_cero(monkeypatch):
    from shapely.geometry import box

    import cielociego.cli as cli
    from cielociego.predios import Predio

    monkeypatch.setattr(cli, "_predios", lambda r: [("a", Predio("X", box(0, 0, 1, 1), 1.0))])
    monkeypatch.setattr(cli, "paso_catalogo", lambda *a, **k: [])
    monkeypatch.setattr(cli, "paso_scl", lambda *a, **k: {"vistas": []})
    monkeypatch.setattr(cli, "paso_radar", lambda *a, **k: None)
    monkeypatch.setattr(cli, "paso_sar", lambda *a, **k: None)
    assert cli.cmd_medir(construye_parser().parse_args(["medir"])) == 0
