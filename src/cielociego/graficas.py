"""Graficas de datos del informe. SVG vectorial, sin dibujos: solo lo medido."""
from __future__ import annotations

import io
from datetime import date

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

# Centinelas: matplotlib fija el color del texto en el SVG, asi que en tema
# oscuro saldria negro sobre negro. Se pintan con estos hex imposibles y
# `_svg()` los cambia por variables CSS, que SI heredan del tema del lector.
TINTA = "#010203"
GRIS = "#040506"
_A_VARIABLE = {TINTA: "var(--tinta)", GRIS: "var(--linea-fuerte)"}
CIEGO = "#c2410c"      # naranja quemado: sin dato optico
UTIL = "#15803d"       # verde: observacion util
RADAR = "#1d4ed8"      # azul: pasada de radar
TESELA = "#a8a29e"     # piedra: el numero de la tesela


def _base(figsize=(9, 3.4)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GRIS)
        ax.spines[lado].set_linewidth(0.8)
    ax.tick_params(colors=TINTA, labelsize=9, length=3, width=0.8, color=GRIS)
    ax.grid(axis="y", color=GRIS, alpha=0.18, linewidth=0.7)
    ax.set_axisbelow(True)
    return fig, ax


def _svg(fig) -> str:
    buf = io.StringIO()
    fig.savefig(buf, format="svg", bbox_inches="tight", transparent=True)
    plt.close(fig)
    svg = buf.getvalue()
    svg = svg[svg.index("<svg") :]
    for centinela, variable in _A_VARIABLE.items():
        svg = svg.replace(centinela, variable).replace(centinela.upper(), variable)
    return svg


def distribucion(ciego_predio, cc_tesela) -> str:
    """El hallazgo: el predio es bimodal, la tesela no."""
    fig, ax = _base((9, 3.6))
    bins = np.linspace(0, 100, 21)
    p = np.asarray(ciego_predio) * 100
    t = np.asarray(cc_tesela)
    ax.hist(p, bins=bins, color=CIEGO, alpha=0.85, label="ciego medido en el PREDIO", zorder=3)
    ax.hist(t, bins=bins, histtype="step", color=TINTA, linewidth=1.8,
            label="nube declarada de la TESELA (110x110 km)", zorder=4)
    ax.set_xlabel("% de superficie inservible por nube o sombra", color=TINTA, fontsize=9.5)
    ax.set_ylabel("nº de tomas", color=TINTA, fontsize=9.5)
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA)
    return _svg(fig)


def calendario(fechas_utiles, huecos, pasadas_radar, desde: date, hasta: date) -> str:
    """Franja temporal: cuando se ve, cuando no, y donde cae el radar."""
    fig, ax = _base((9, 2.5))
    d0 = desde.toordinal()
    span = hasta.toordinal() - d0

    # una sola llamada por capa: dibujar marca a marca inflaba el SVG a 400 kB
    cortos = [h for h in huecos if h["dias"] < 15]
    largos = [h for h in huecos if h["dias"] >= 15]
    for grupo, alfa in ((cortos, 0.45), (largos, 0.9)):
        if grupo:
            ax.barh(
                [1] * len(grupo), [h["dias"] for h in grupo],
                left=[date.fromisoformat(h["inicio"]).toordinal() - d0 for h in grupo],
                height=0.55, color=CIEGO, alpha=alfa, linewidth=0, zorder=2,
            )
    if fechas_utiles:
        ax.barh(
            [1] * len(fechas_utiles), [2.2] * len(fechas_utiles),
            left=[date.fromisoformat(f).toordinal() - d0 for f in fechas_utiles],
            height=0.55, color=UTIL, linewidth=0, zorder=3,
        )
    if pasadas_radar:
        xs = [date.fromisoformat(f).toordinal() - d0 for f in pasadas_radar]
        ax.plot(xs, [0.52] * len(xs), linestyle="none", marker="|",
                color=RADAR, markersize=5, markeredgewidth=0.7, zorder=4)

    ax.set_ylim(0.35, 1.45)
    ax.set_xlim(0, span)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    anos = [date(a, 1, 1) for a in range(desde.year, hasta.year + 1)]
    ax.set_xticks([a.toordinal() - d0 for a in anos])
    ax.set_xticklabels([a.year for a in anos])
    ax.text(0, 1.38, "arriba: naranja = ciego · verde = observación óptica útil     abajo: azul = pasada de radar",
            fontsize=8.5, color=GRIS)
    return _svg(fig)


def huecos_por_duracion(huecos) -> str:
    """Cuantos huecos hay de cada duracion, y si el radar entra en ellos."""
    fig, ax = _base((9, 3.2))
    tramos = [(1, 4), (5, 9), (10, 14), (15, 29), (30, 59), (60, 999)]
    etiq = ["1-4 d", "5-9 d", "10-14 d", "15-29 d", "30-59 d", "60+ d"]
    con, sin = [], []
    for a, b in tramos:
        gr = [h for h in huecos if a <= h["dias"] <= b]
        con.append(sum(1 for h in gr if h["radar"] > 0))
        sin.append(sum(1 for h in gr if h["radar"] == 0))
    x = np.arange(len(tramos))
    ax.bar(x, con, color=RADAR, label="con pasada de radar dentro", zorder=3)
    ax.bar(x, sin, bottom=con, color=CIEGO, alpha=0.55, label="sin ninguna observación", zorder=3)
    for i, (c, s) in enumerate(zip(con, sin)):
        if c + s:
            ax.text(i, c + s + 1.5, str(c + s), ha="center", fontsize=8.5, color=TINTA)
    ax.set_xticks(x)
    ax.set_xticklabels(etiq)
    ax.set_xlabel("duración del hueco sin observación óptica útil", color=TINTA, fontsize=9.5)
    ax.set_ylabel("nº de huecos", color=TINTA, fontsize=9.5)
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA)
    return _svg(fig)


def pasadas_anuales(s2_por_ano, s1_por_ano) -> str:
    """La constelacion cambia: se cuenta, no se supone."""
    fig, ax = _base((9, 3.0))
    anos = sorted(set(s2_por_ano) | set(s1_por_ano))
    x = np.arange(len(anos))
    ax.bar(x - 0.2, [s2_por_ano.get(a, 0) for a in anos], width=0.4,
           color=UTIL, label="pasadas Sentinel-2 (óptico)", zorder=3)
    ax.bar(x + 0.2, [s1_por_ano.get(a, 0) for a in anos], width=0.4,
           color=RADAR, label="pasadas Sentinel-1 (radar)", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(anos)
    ax.set_ylabel("pasadas al año", color=TINTA, fontsize=9.5)
    ax.legend(frameon=False, fontsize=9, labelcolor=TINTA)
    return _svg(fig)
