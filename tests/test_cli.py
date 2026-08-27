"""Command-line tests.

No tocan la red: comprueban que el parser acepta lo que documenta y que las
ordenes llegan a la funcion correcta con los argumentos correctos.
"""
from __future__ import annotations

import pytest

from cielociego.cli import build_parser


def parse(*argv):
    return build_parser().parse_args(list(argv))


def test_with_no_command_it_fails_rather_than_idling():
    with pytest.raises(SystemExit):
        build_parser().parse_args([])


@pytest.mark.parametrize("cmd", ["measure", "catalog", "tests"])
def test_the_three_documented_commands_exist(cmd):
    assert parse(cmd).command == cmd


def test_measure_has_usable_defaults():
    a = parse("measure")
    assert a.start == "2019-01-01" and a.workers == 12
    assert a.field is None and a.no_radar is False and a.orbit is None


def test_several_fields_can_be_passed():
    a = parse("measure", "--field", "a.geojson", "--field", "b.geojson")
    assert a.field == ["a.geojson", "b.geojson"]


def test_dates_and_workers_can_be_set():
    a = parse("measure", "--start", "2022-01-01", "--end", "2023-12-31", "--workers", "4")
    assert (a.start, a.end, a.workers) == ("2022-01-01", "2023-12-31", 4)


def test_the_orbit_can_be_forced():
    """Picked automatically by default; forcing it reproduces an old measurement."""
    assert parse("measure", "--orbit", "142").orbit == 142


def test_no_radar_skips_the_slow_step():
    assert parse("measure", "--no-radar").no_radar is True


def test_a_non_numeric_worker_count_fails():
    with pytest.raises(SystemExit):
        parse("measure", "--workers", "muchos")


def test_an_unknown_command_fails():
    with pytest.raises(SystemExit):
        parse("inventada")


def test_main_dispatches_to_the_requested_command(monkeypatch):
    """`main` calls the requested command's function and returns its code."""
    import cielociego.cli as cli

    recibido = {}

    def falso(args):
        recibido["start"] = args.start
        return 7

    monkeypatch.setattr(cli, "cmd_catalog", falso)
    # the parser pins args.func when built, so it has to be rebuilt
    monkeypatch.setattr(
        cli, "build_parser",
        lambda: _parser_con(cli, "catalog", falso),
    )
    assert cli.main(["catalog", "--start", "2022-01-01"]) == 7
    assert recibido["start"] == "2022-01-01"


def _parser_con(cli, orden, funcion):
    """Build the real parser and swap the function of a single command."""
    p = build_parser()
    sub = p._subparsers._group_actions[0]  # type: ignore[attr-defined]
    sub.choices[orden].set_defaults(func=funcion)
    return p


def test_with_no_fields_it_warns_rather_than_measuring_nothing(monkeypatch, tmp_path):
    """Un sweep sobre cero fields que dijera 'listo' seria mentira."""
    import cielociego.cli as cli

    monkeypatch.setattr(cli, "DATA", tmp_path)
    with pytest.raises(SystemExit) as e:
        cli._load_all(None)
    assert "GeoJSON" in str(e.value)


def test_explicit_fields_bypass_the_folder(monkeypatch, tmp_path):
    from pathlib import Path

    import cielociego.cli as cli

    datos = Path(__file__).resolve().parents[1] / "data"
    path = str(sorted(datos.glob("*.geojson"))[0])
    monkeypatch.setattr(cli, "DATA", tmp_path)  # vacia, pero da igual
    encontrados = cli._load_all([path])
    assert len(encontrados) == 1 and encontrados[0][1].area_ha


def test_one_failing_field_does_not_kill_the_rest(monkeypatch, tmp_path, capsys):
    """A mid-run network cut used to kill the whole measurement and lose the rest."""
    from shapely.geometry import box

    import cielociego.cli as cli
    from cielociego.fields import Field

    a = Field("Field bueno", box(0, 0, 1, 1), 10.0)
    b = Field("Field roto", box(2, 2, 3, 3), 20.0)
    monkeypatch.setattr(cli, "_load_all", lambda r: [("a", a), ("b", b)])

    hechos = []

    def catalog(clave, field, start, end):
        if field.name == "Field roto":
            raise ConnectionError("Read timed out")
        hechos.append(clave)
        return []

    monkeypatch.setattr(cli, "step_catalog", catalog)
    monkeypatch.setattr(cli, "step_scl", lambda *a, **k: {"views": []})
    monkeypatch.setattr(cli, "step_radar", lambda *a, **k: None)
    monkeypatch.setattr(cli, "step_sar", lambda *a, **k: None)

    args = build_parser().parse_args(["measure"])
    codigo = cli.cmd_measure(args)

    out = capsys.readouterr().out
    assert hechos == ["a"], "el field bueno debe medirse igual"
    assert codigo == 1, "el codigo de out avisa de que quedo incompleta"
    assert "MEDICION INCOMPLETA" in out
    assert "Field roto" in out


def test_when_all_succeed_the_exit_code_is_zero(monkeypatch):
    from shapely.geometry import box

    import cielociego.cli as cli
    from cielociego.fields import Field

    monkeypatch.setattr(cli, "_load_all", lambda r: [("a", Field("X", box(0, 0, 1, 1), 1.0))])
    monkeypatch.setattr(cli, "step_catalog", lambda *a, **k: [])
    monkeypatch.setattr(cli, "step_scl", lambda *a, **k: {"views": []})
    monkeypatch.setattr(cli, "step_radar", lambda *a, **k: None)
    monkeypatch.setattr(cli, "step_sar", lambda *a, **k: None)
    assert cli.cmd_measure(build_parser().parse_args(["measure"])) == 0
