"""Data charts for the report. Vector SVG, measurements only.

Text colours resolve to CSS variables so the charts follow the reader's theme;
a fixed colour makes the report unreadable in dark mode and nobody notices until
it ships.
"""
from __future__ import annotations

import io
from datetime import date

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

# Sentinels: matplotlib bakes the text colour into the SVG, so on a dark
# theme it would be black on black. These impossible hexes get swapped by
# `_svg()` for CSS variables, which do follow the reader's theme.
INK = "#010203"
GREY = "#040506"
_A_VARIABLE = {INK: "var(--tinta)", GREY: "var(--linea-fuerte)"}
BLIND = "#c2410c"      # naranja quemado: sin dato optico
USABLE = "#15803d"       # verde: observacion util
RADAR = "#1d4ed8"      # azul: pasada de radar
TILE = "#a8a29e"     # piedra: el numero de la tile


def _base(figsize=(9, 3.4)):
    fig, ax = plt.subplots(figsize=figsize)
    fig.patch.set_alpha(0)
    ax.patch.set_alpha(0)
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(GREY)
        ax.spines[lado].set_linewidth(0.8)
    ax.tick_params(colors=INK, labelsize=9, length=3, width=0.8, color=GREY)
    ax.grid(axis="y", color=GREY, alpha=0.18, linewidth=0.7)
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


def distribution(ciego_predio, tile_cloud) -> str:
    """The finding: the field is bimodal, the tile is not."""
    fig, ax = _base((9, 3.6))
    bins = np.linspace(0, 100, 21)
    p = np.asarray(ciego_predio) * 100
    t = np.asarray(tile_cloud)
    ax.hist(p, bins=bins, color=BLIND, alpha=0.85, label="ciego medido en el PREDIO", zorder=3)
    ax.hist(t, bins=bins, histtype="step", color=INK, linewidth=1.8,
            label="nube declarada de la TILE (110x110 km)", zorder=4)
    ax.set_xlabel("% de superficie inservible por nube o sombra", color=INK, fontsize=9.5)
    ax.set_ylabel("nº de scenes", color=INK, fontsize=9.5)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    return _svg(fig)


def calendar_strip(fechas_utiles, huecos, radar_passes, start: date, end: date) -> str:
    """Timeline: when it can be seen, when it cannot, and where radar falls."""
    fig, ax = _base((9, 2.5))
    d0 = start.toordinal()
    span = end.toordinal() - d0

    # one call per layer: drawing mark by mark inflated the SVG to 400 kB
    cortos = [h for h in huecos if h["days"] < 15]
    largos = [h for h in huecos if h["days"] >= 15]
    for grupo, alfa in ((cortos, 0.45), (largos, 0.9)):
        if grupo:
            ax.barh(
                [1] * len(grupo), [h["days"] for h in grupo],
                left=[date.fromisoformat(h["start"]).toordinal() - d0 for h in grupo],
                height=0.55, color=BLIND, alpha=alfa, linewidth=0, zorder=2,
            )
    if fechas_utiles:
        ax.barh(
            [1] * len(fechas_utiles), [2.2] * len(fechas_utiles),
            left=[date.fromisoformat(f).toordinal() - d0 for f in fechas_utiles],
            height=0.55, color=USABLE, linewidth=0, zorder=3,
        )
    if radar_passes:
        xs = [date.fromisoformat(f).toordinal() - d0 for f in radar_passes]
        ax.plot(xs, [0.52] * len(xs), linestyle="none", marker="|",
                color=RADAR, markersize=5, markeredgewidth=0.7, zorder=4)

    ax.set_ylim(0.35, 1.45)
    ax.set_xlim(0, span)
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.grid(False)
    anos = [date(a, 1, 1) for a in range(start.year, end.year + 1)]
    ax.set_xticks([a.toordinal() - d0 for a in anos])
    ax.set_xticklabels([a.year for a in anos])
    ax.text(0, 1.38,
            "arriba: naranja = ciego · verde = observación útil     abajo: azul = radar",
            fontsize=8.5, color=GREY)
    return _svg(fig)


def gaps_by_length(huecos) -> str:
    """How many gaps of each length, and whether radar reaches into them."""
    fig, ax = _base((9, 3.2))
    tramos = [(1, 4), (5, 9), (10, 14), (15, 29), (30, 59), (60, 999)]
    etiq = ["1-4 d", "5-9 d", "10-14 d", "15-29 d", "30-59 d", "60+ d"]
    con, sin = [], []
    for a, b in tramos:
        gr = [h for h in huecos if a <= h["days"] <= b]
        con.append(sum(1 for h in gr if h["radar_passes"] > 0))
        sin.append(sum(1 for h in gr if h["radar_passes"] == 0))
    x = np.arange(len(tramos))
    ax.bar(x, con, color=RADAR, label="con pasada de radar dentro", zorder=3)
    ax.bar(x, sin, bottom=con, color=BLIND, alpha=0.55, label="sin ninguna observación", zorder=3)
    for i, (c, s) in enumerate(zip(con, sin, strict=True)):
        if c + s:
            ax.text(i, c + s + 1.5, str(c + s), ha="center", fontsize=8.5, color=INK)
    ax.set_xticks(x)
    ax.set_xticklabels(etiq)
    ax.set_xlabel("duración del hueco sin observación óptica útil", color=INK, fontsize=9.5)
    ax.set_ylabel("nº de huecos", color=INK, fontsize=9.5)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    return _svg(fig)


def passes_per_year(s2_por_ano, s1_por_ano) -> str:
    """The constellation changes: counted, not assumed."""
    fig, ax = _base((9, 3.0))
    anos = sorted(set(s2_por_ano) | set(s1_por_ano))
    x = np.arange(len(anos))
    ax.bar(x - 0.2, [s2_por_ano.get(a, 0) for a in anos], width=0.4,
           color=USABLE, label="pasadas Sentinel-2 (óptico)", zorder=3)
    ax.bar(x + 0.2, [s1_por_ano.get(a, 0) for a in anos], width=0.4,
           color=RADAR, label="pasadas Sentinel-1 (radar)", zorder=3)
    ax.set_xticks(x)
    ax.set_xticklabels(anos)
    ax.set_ylabel("pasadas al año", color=INK, fontsize=9.5)
    ax.legend(frameon=False, fontsize=9, labelcolor=INK)
    return _svg(fig)


def _curve(model, dates) -> np.ndarray:
    """Fitted values of the winning model, to trace over the points."""
    o = np.array([date.fromisoformat(f).toordinal() for f in dates], dtype=float)
    a, b = model.get("level_before"), model.get("level_after")
    name = model.get("name", "")
    if a is None or b is None:
        return np.full(len(o), np.nan)
    if name == "escalon" and model.get("cut"):
        c = date.fromisoformat(model["cut"]).toordinal()
        return np.where(o < c, a, b)
    if name == "meseta-rampa-meseta" and model.get("cut") and model.get("cut_end"):
        c0 = date.fromisoformat(model["cut"]).toordinal()
        c1 = date.fromisoformat(model["cut_end"]).toordinal()
        return a + (b - a) * np.clip((o - c0) / max(c1 - c0, 1), 0, 1)
    return np.full(len(o), np.nan)


def _label(model) -> str:
    name = model.get("name", "model")
    a, b = model.get("level_before"), model.get("level_after")
    if a is None or b is None:
        return name
    return f"{name}: {a:+.2f} → {b:+.2f} dB ({b - a:+.2f})"


def radar_series(medidas, huecos, start: date, end: date, *,
                titulo_y="γ⁰ VV (dB)", model=None) -> str:
    """Backscatter series with the optical blind stretches shaded.

    One orbit group only: mixing them would create steps the crop never had.
    """
    fig, ax = _base((9, 3.4))
    d0 = start.toordinal()

    for h in huecos:
        if h["days"] >= 15:
            ax.axvspan(
                date.fromisoformat(h["start"]).toordinal() - d0,
                date.fromisoformat(h["end"]).toordinal() - d0,
                color=BLIND, alpha=0.16, linewidth=0, zorder=1,
            )
    xs = [date.fromisoformat(m["date"]).toordinal() - d0 for m in medidas]
    ys = [m["vv_db"] for m in medidas]
    ax.plot(xs, ys, color=RADAR, linewidth=1.0, alpha=0.55, zorder=3)
    ax.plot(xs, ys, linestyle="none", marker="o", markersize=2.3,
            color=RADAR, markeredgewidth=0, zorder=4)

    # The model drawn is not always a straight line: it is whichever wins by
    # BIC. A linear trend used to be drawn regardless, and on this field that
    # was misleading -- the series is plateau-transition-plateau, and a line
    # describes it 270 BIC points worse.
    if model is not None and len(xs) > 2:
        ax.plot(xs, _curve(model, [m["date"] for m in medidas]), color=BLIND,
                linewidth=2.0, zorder=5, label=_label(model))
        ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")
    elif len(xs) > 2:
        b = np.polyfit(xs, ys, 1)
        ax.plot(xs, np.polyval(b, xs), color=BLIND, linewidth=1.9, linestyle=(0, (5, 3)),
                zorder=5, label=f"tendencia lineal {b[0] * 365:+.2f} dB/año")
        ax.legend(frameon=False, fontsize=9, labelcolor=INK, loc="upper left")

    ax.set_xlim(0, end.toordinal() - d0)
    anos = [date(a, 1, 1) for a in range(start.year, end.year + 1)]
    ax.set_xticks([a.toordinal() - d0 for a in anos])
    ax.set_xticklabels([a.year for a in anos])
    ax.set_ylabel(titulo_y, color=INK, fontsize=9.5)
    ax.text(0.5, 1.04, "las franjas naranjas son los tramos de 15+ días sin óptico",
            transform=ax.transAxes, ha="center", fontsize=8.5, color=GREY)
    return _svg(fig)


def platform_control(por_plataforma) -> str:
    """Trend measured within each platform: the control against an artefact."""
    fig, ax = _base((9, 2.9))
    nombres = list(por_plataforma)
    values = [por_plataforma[k] for k in nombres]
    colores = [BLIND if abs(v) > 0.3 else GREY for v in values]
    y = np.arange(len(nombres))
    ax.barh(y, values, color=colores, height=0.6, zorder=3)
    ax.axvline(0, color=INK, linewidth=1.0, zorder=4)
    ax.set_yticks(y)
    ax.set_yticklabels(nombres, fontsize=9)
    ax.set_xlabel("tendencia de γ⁰ VV (dB por año)", color=INK, fontsize=9.5)
    ax.grid(axis="x", color=GREY, alpha=0.18, linewidth=0.7)
    ax.grid(axis="y", visible=False)
    for i, v in enumerate(values):
        ax.text(v + (0.03 if v >= 0 else -0.03), i, f"{v:+.3f}",
                va="center", ha="left" if v >= 0 else "right",
                fontsize=8.5, color=INK)
    ax.set_xlim(min(min(values) * 1.45, -0.25), max(max(values) * 1.45, 0.25))
    return _svg(fig)
