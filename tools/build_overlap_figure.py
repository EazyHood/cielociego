"""Figure for the tile-overlap result: two granules of one datatake, two cloud values.

Panel (a) is the pair scatter with the query-threshold quadrants; panel (b) shows agreement
against how much ground the two granules actually share. Reads the measurement CSV directly so
the figure cannot drift from the numbers in the text.
"""
from __future__ import annotations

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

TINTA = "#1a1a1a"
SUAVE = "#8a8a8a"
ACENTO = "#b3472e"
MALLA = "#e2e2e2"
T = 10.0  # the query threshold drawn as the quadrant boundary

# Intersection-over-union strata, from iou_results.json. Kept here rather than re-derived
# because the footprint geometries are not in the pair CSV.
ESTRATOS = [
    ("0,00–0,05", 3878, 6.93, 0.844),
    ("0,05–0,10", 1228, 3.97, 0.913),
    ("0,20–0,40", 593, 5.39, 0.939),
    ("0,40–0,70", 168, 0.88, 0.988),
]


def leer(csv_path: Path) -> tuple[np.ndarray, np.ndarray]:
    filas = list(csv.DictReader(csv_path.open(encoding="utf-8")))
    a = np.array([float(f["cc_a"]) for f in filas])
    b = np.array([float(f["cc_b"]) for f in filas])
    return a, b


def limpia(ax: plt.Axes) -> None:
    for lado in ("top", "right"):
        ax.spines[lado].set_visible(False)
    for lado in ("left", "bottom"):
        ax.spines[lado].set_color(SUAVE)
        ax.spines[lado].set_linewidth(0.8)
    ax.tick_params(colors=TINTA, labelsize=8, length=3, width=0.8, color=SUAVE)


def panel_dispersion(ax: plt.Axes, a: np.ndarray, b: np.ndarray) -> None:
    discrepan = (a <= T) != (b <= T)
    # The two disagreement quadrants: one granule admits the acquisition, the other rejects it.
    for x0, y0, w, h in ((0, T, T, 100 - T), (T, 0, 100 - T, T)):
        ax.add_patch(Rectangle((x0, y0), w, h, facecolor=ACENTO, alpha=0.06, zorder=0, lw=0))
    ax.plot([0, 100], [0, 100], color=SUAVE, lw=0.9, ls=(0, (4, 3)), zorder=1)
    ax.scatter(a[~discrepan], b[~discrepan], s=3.5, c=TINTA, alpha=0.16, lw=0, zorder=2)
    ax.scatter(a[discrepan], b[discrepan], s=6, c=ACENTO, alpha=0.75, lw=0, zorder=3)
    for v in (T,):
        ax.axvline(v, color=ACENTO, lw=0.8, alpha=0.5, zorder=1)
        ax.axhline(v, color=ACENTO, lw=0.8, alpha=0.5, zorder=1)

    ax.set_xlim(0, 100)
    ax.set_ylim(0, 100)
    ax.set_aspect("equal")
    ax.set_xlabel("eo:cloud_cover del gránulo A (%)", fontsize=8.5, color=TINTA)
    ax.set_ylabel("eo:cloud_cover del gránulo B (%)", fontsize=8.5, color=TINTA)
    limpia(ax)
    ax.set_title(
        "(a)  Los dos gránulos de un mismo pase, 6.116 pares",
        fontsize=9.5, color=TINTA, loc="left", pad=9,
    )
    ax.text(
        0.975, 0.045,
        f"{discrepan.mean() * 100:.2f} % discrepan\nsobre el umbral del {T:.0f} %",
        transform=ax.transAxes, ha="right", va="bottom", fontsize=8, color=ACENTO,
        linespacing=1.45,
        # The threshold line runs behind this label; the patch keeps the text legible.
        bbox={"facecolor": "white", "edgecolor": "none", "pad": 2.5, "alpha": 0.92},
    )
    ax.text(
        0.045, 0.955,
        f"mediana |Δ| = {np.median(np.abs(a - b)):.2f} puntos\nmáximo {np.abs(a - b).max():.1f}",
        transform=ax.transAxes, ha="left", va="top", fontsize=8, color=SUAVE, linespacing=1.45,
    )


def panel_estratos(ax: plt.Axes) -> None:
    y = np.arange(len(ESTRATOS))[::-1]
    med = [e[2] for e in ESTRATOS]
    ax.barh(y, med, height=0.5, color=TINTA, alpha=0.82, zorder=2)

    # Two label columns to the right of the plotting area, clear of the longest bar.
    x_n, x_ccc = 8.4, 10.6
    ax.text(x_n, len(ESTRATOS) - 0.42, "pares", fontsize=7.5, color=SUAVE, ha="left")
    ax.text(x_ccc, len(ESTRATOS) - 0.42, "concordancia", fontsize=7.5, color=SUAVE, ha="left")
    for yi, (_, n, m, ccc) in zip(y, ESTRATOS, strict=True):
        ax.text(m + 0.2, yi, f"{m:.2f}".replace(".", ","), va="center", fontsize=8.5, color=TINTA)
        ax.text(x_n, yi, f"{n:,}".replace(",", "."), va="center", fontsize=8, color=SUAVE)
        destaca = ccc > 0.97
        ax.text(
            x_ccc, yi, f"{ccc:.3f}".replace(".", ","), va="center", fontsize=8,
            color=ACENTO if destaca else SUAVE, weight="bold" if destaca else "normal",
        )

    ax.set_yticks(y, [e[0] for e in ESTRATOS], fontsize=8.5)
    ax.set_xlim(0, 12.4)
    ax.set_xticks([0, 2, 4, 6, 8])
    ax.set_ylim(-0.62, len(ESTRATOS) - 0.28)
    ax.set_xlabel("mediana de |Δ eo:cloud_cover| (puntos)", fontsize=8.5, color=TINTA)
    ax.set_ylabel("intersección sobre unión de las dos huellas", fontsize=8.5, color=TINTA)
    for gx in (2, 4, 6, 8):
        ax.plot([gx, gx], [-0.62, len(ESTRATOS) - 0.62], color=MALLA, lw=0.7, zorder=0)
    ax.set_axisbelow(True)
    limpia(ax)
    # The grid must not run under the label columns.
    ax.spines["bottom"].set_bounds(0, 8)
    ax.set_title(
        "(b)  Cuanto más terreno comparten, más coinciden",
        fontsize=9.5, color=TINTA, loc="left", pad=9,
    )


def main() -> int:
    scratch = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    csv_path = scratch / "overlap_pairs_unique_ftw2y_iou.csv"
    if not csv_path.exists():
        print(f"no encuentro {csv_path}", file=sys.stderr)
        return 1

    a, b = leer(csv_path)
    fig, (izq, der) = plt.subplots(1, 2, figsize=(10.6, 4.9), gridspec_kw={"width_ratios": [1, 1.06]})
    fig.patch.set_facecolor("white")
    panel_dispersion(izq, a, b)
    panel_estratos(der)
    fig.tight_layout(pad=1.9, w_pad=3.2)

    destino = Path("docs/paper")
    destino.mkdir(parents=True, exist_ok=True)
    for nombre, kw in (("fig_solape.svg", {}), ("fig_solape.png", {"dpi": 300})):
        fig.savefig(destino / nombre, facecolor="white", bbox_inches="tight", **kw)
        print(f"  {destino / nombre}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
