"""The threshold curve, corrected for chance -- and the figure the paper needs.

Two jobs, and they are the same computation.

**The chance correction.** The manuscript says that the stricter the filter, the
worse the bias, and quotes the asymmetry rising to 99.7 at a 5 % threshold. A
reviewer objected, correctly, that most of that movement is forced arithmetic:
lowering the threshold retains fewer acquisitions, usable ones included, so
recall has to fall and the ratio has to move. A claim about a filter has to be
made against what a filter that knows nothing would do.

So each operating point is compared with a random filter that retains the same
number of acquisitions. If k of N are retained and P of them are usable, chance
alone gives an expected FN of P(1 - k/N) and an expected FP of (N - P)(k/N).
The ratio of the observed asymmetry to that expectation is the part that is not
arithmetic. If the lift is flat across thresholds, the sentence in section 4.4
is describing the threshold and not the metadata, and it has to go.

**The figure.** The single figure of the manuscript plots recall by size bin --
the very analysis section 4.3 declares too coarse to answer its question. This
draws the curve the paper actually argues: what the filter costs and yields
across the whole range of thresholds, with the chance expectation underneath.

    python tools/threshold_curve.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from cielociego.cohort import DEFAULT_BLIND_LIMIT, Observation
from cielociego.scl import MIN_PIXELS

ROOT = Path(__file__).resolve().parents[1]
THRESHOLDS = [0.02, 0.05, 0.10, 0.20, 0.30, 0.40, 0.50, 0.70, 0.90]


def load() -> list[Observation]:
    doc = json.loads((ROOT / "outputs" / "cohort_ftw.json").read_text(encoding="utf-8"))
    rows = [
        Observation(
            o["parcel_id"], o["source"], o["country"], o["area_ha"], o["date"],
            o["scene_id"], o["pixels"], o["tile_cloud"], o["blind"], o["blind_wide"],
            o.get("error"),
        )
        for o in doc["observations"]
    ]
    return [
        o for o in rows
        if not o.error and o.tile_cloud is not None and o.pixels >= MIN_PIXELS
        and o.blind == o.blind
    ]


def curve(rows: list[Observation]) -> list[dict]:
    n = len(rows)
    usable = sum(1 for o in rows if o.blind <= DEFAULT_BLIND_LIMIT)
    out = []
    for t in THRESHOLDS:
        tp = fp = fn = 0
        for o in rows:
            kept = o.tile_cloud / 100.0 <= t
            good = o.blind <= DEFAULT_BLIND_LIMIT
            if kept and good:
                tp += 1
            elif kept:
                fp += 1
            elif good:
                fn += 1
        kept_n = tp + fp
        # What a filter that retains the same number of acquisitions, but picks
        # them at random, would produce.
        share = kept_n / n if n else 0.0
        exp_fn = usable * (1 - share)
        exp_fp = (n - usable) * share
        obs_asym = fn / fp if fp else float("inf")
        exp_asym = exp_fn / exp_fp if exp_fp else float("inf")
        out.append({
            "t": t, "kept": kept_n, "tp": tp, "fp": fp, "fn": fn,
            "recall": tp / usable if usable else float("nan"),
            "recall_chance": share,
            "asymmetry": obs_asym,
            "asymmetry_chance": exp_asym,
            "lift": obs_asym / exp_asym if exp_asym not in (0.0, float("inf")) else float("nan"),
        })
    return out


def figure(rows: list[dict], out: Path) -> Path:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    t = [r["t"] * 100 for r in rows]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9.6, 3.9))

    ax1.plot(t, [r["recall"] for r in rows], "o-", color="#1d4ed8", lw=1.8, ms=5,
             label="filtro por metadato de tesela")
    ax1.plot(t, [r["recall_chance"] for r in rows], "--", color="#9aa3a0", lw=1.4,
             label="filtro aleatorio de igual tamaño")
    ax1.set_xscale("log")
    ax1.set_xlabel("umbral sobre la nubosidad declarada (%)")
    ax1.set_ylabel("observaciones utilizables conservadas")
    ax1.set_ylim(0, 1.02)
    ax1.grid(alpha=.25, lw=.6)
    ax1.legend(fontsize=8, frameon=False, loc="lower right")
    ax1.set_title("(a) lo que el filtro conserva", fontsize=10, loc="left")

    ax2.plot(t, [r["fn"] for r in rows], "o-", color="#8E2F2A", lw=1.8, ms=5,
             label="descartadas siendo utilizables")
    ax2.plot(t, [r["fp"] for r in rows], "s-", color="#1D6A57", lw=1.8, ms=5,
             label="conservadas siendo inservibles")
    ax2.set_xscale("log")
    ax2.set_xlabel("umbral sobre la nubosidad declarada (%)")
    ax2.set_ylabel("número de adquisiciones")
    ax2.grid(alpha=.25, lw=.6)
    ax2.legend(fontsize=8, frameon=False)
    ax2.set_title("(b) el precio de cada umbral", fontsize=10, loc="left")

    for ax in (ax1, ax2):
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    fig.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, format="svg")
    plt.close(fig)
    return out


def main() -> int:
    rows = load()
    usable = sum(1 for o in rows if o.blind <= DEFAULT_BLIND_LIMIT)
    print(f"{len(rows)} filas evaluables, {usable} utilizables sobre la parcela\n")
    data = curve(rows)

    print(f"{'umbral':>8}{'conserva':>10}{'FN':>7}{'FP':>6}{'exhaust.':>10}"
          f"{'azar':>8}{'asimetria':>11}{'azar':>9}{'lift':>8}")
    for r in data:
        print(f"{r['t']:>7.0%}{r['kept']:>10}{r['fn']:>7}{r['fp']:>6}"
              f"{r['recall']:>10.3f}{r['recall_chance']:>8.3f}"
              f"{r['asymmetry']:>11.1f}{r['asymmetry_chance']:>9.1f}{r['lift']:>8.2f}")

    lifts = [r["lift"] for r in data if r["lift"] == r["lift"]]
    print(f"\nlift entre {min(lifts):.2f} y {max(lifts):.2f}")
    print("Si el lift no crece al endurecer el umbral, la frase «cuanto mas estricto")
    print("el filtro, peor el sesgo» describe el umbral y no el metadato.")

    path = figure(data, ROOT / "outputs" / "fig_umbral.svg")
    (ROOT / "outputs" / "threshold_curve.json").write_text(
        json.dumps(data, indent=1), encoding="utf-8")
    print(f"\nfigura en {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
