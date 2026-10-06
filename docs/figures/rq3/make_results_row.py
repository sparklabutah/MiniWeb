"""Paper Fig. 7: practice and scaling, two square panels side by side in one column with one legend (user, 2026-10-06:
the benchmark comparison became Tab. 3, rq3/make_rq3_table.py), drawn at the printed width (style.COL_W), 9 pt:

  (a) practice   success per skill family on the generated single-primitive tasks, single agent untrained / trained
  (b) scaling    the planner on the WebVoyager sample against its executor's training steps

The runs come from the panels' own configs (rq2_config, scaling_wv_config, and rq3_config / data_config for the legend's
colours), so this figure cannot drift from them; results_row_config.yaml holds the layout and the labels.

    python docs/figures/rq3/make_results_row.py
"""
import os, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
FIGS = os.path.dirname(HERE)
for d in ("common", "rq3", "scaling", "tables"):
    sys.path.insert(0, os.path.join(FIGS, d))
from results import ROOT, family_counts, primitive_filter  # noqa: E402
sys.path.insert(0, ROOT)
from datagen.viewer import FAMILY_OF  # noqa: E402
from style import COL_W, FAM, FS, INK, MUTED, bar, panel, rc, save, style_axes, swatch  # noqa: E402
from make_scaling import panel as scaling_panel, LW, MS  # noqa: E402

rc()
FAMILY = {"Drag & gesture": "Drag", "Discrete selection": "Select", "Text entry": "Text",   # as in Tab. 2's header
          "Form transaction": "Form", "Navigation": "Nav.", "Out-of-page I/O": "I/O", "Reasoning base": "Reason"}


def cfg_of(path):
    return yaml.safe_load(open(os.path.join(ROOT, path)))


def practice(ax, cfg):
    """(a): per family, the untrained and the trained single agent."""
    sets, fa = cfg["task_sets"], [a for l in cfg["family_arms"] for a in cfg["arms"] if a["label"] == l]
    only = primitive_filter(sets[cfg["family_set"]].get("primitives"))
    for a in fa:
        a["fam"] = family_counts(a.get(cfg["family_set"]) or [], FAMILY_OF, only=only)
    fams = sorted((f for f in fa[0]["fam"] if f in FAM), key=lambda f: fa[0]["fam"][f][0] / fa[0]["fam"][f][1])
    bw = 0.4
    for gi, f in enumerate(fams):
        vals = [100 * a["fam"][f][0] / a["fam"][f][1] for a in fa]
        for j, (a, v) in enumerate(zip(fa, vals)):
            bar(ax, gi + (j - 0.5) * bw, v, bw * 0.9, a["color"])
        d = vals[-1] - vals[0]                           # the gains are read off the bars (the caption gives them)
        ax.text(gi + 0.1, -3, FAMILY[f], fontsize=FS["label"], weight="bold", color=FAM[f], ha="right", va="top",
                rotation=60, rotation_mode="anchor")    # 60 degrees: at 45 the bold names touch
        print(f"  (a) {f:20s} {vals[0]:5.1f} -> {vals[-1]:5.1f}  gain {d:+5.1f}  (n {fa[0]['fam'][f][1]})")
    ax.set_xlim(-0.5, len(fams) - 0.5)


def legend(A, rows, top, x0, x1):
    """rows of (label, [glyph drawers], bold, colour); columns aligned across rows, the grid centred in [x0, x1]."""
    rnd = A.figure.canvas.get_renderer()
    SW, GAP, SEP, RH = 0.14, 0.05, 0.12, 0.21

    def width(e):
        t = A.text(0, -1, e[0], fontsize=FS["legend"], weight="bold" if e[2] else "normal")
        w = sum(g(None, None) + GAP for g in e[1]) + t.get_window_extent(rnd).width / A.figure.dpi
        t.remove()
        return w
    cols = [max(width(r[c]) for r in rows if c < len(r)) for c in range(max(map(len, rows)))]
    used = sum(cols) + SEP * (len(cols) - 1)
    assert used <= x1 - x0 - 0.1, f"legend needs {used:.2f} in of {x1 - x0 - 0.1:.2f}: shorten a label"
    h = RH * len(rows) + 0.06
    panel(A, x0, top, x1 - x0, h)
    left = x0 + (x1 - x0 - used) / 2
    for r, entries in enumerate(rows):
        x, y = left, top + 0.03 + RH * (r + 0.5)
        for (lab, glyphs, bold, color), cw in zip(entries, cols):
            xx = x
            for g in glyphs:
                xx += g(A, (xx, y)) + GAP
            A.text(xx, y, lab, fontsize=FS["legend"], va="center", color=color, weight="bold" if bold else "normal")
            x += cw + SEP
    return h


def swatch_glyph(color, hatched):
    def draw(A, at):
        if A is not None:
            swatch(A, at[0], at[1], color, hatched=hatched, w=0.14)
        return 0.14
    return draw


def line_glyph(**kw):
    def draw(A, at):
        if A is not None:
            A.add_line(Line2D([at[0], at[0] + 0.1, at[0] + 0.2], [at[1]] * 3, markevery=[1], zorder=3, **kw))
        return 0.2
    return draw


def main():
    cfg = cfg_of("docs/figures/rq3/results_row_config.yaml")
    rq2, rq3, data, sc = (cfg_of(cfg["configs"][k]) for k in ("practice", "compose", "data", "scaling"))
    L, lab = cfg["layout"], cfg["legend"]
    W = COL_W
    col = sc["colors"]
    rows = [[(lab["single_untrained"], [swatch_glyph(rq3["arms"][0]["color"], False)], False, INK),
             (lab["single_trained"], [swatch_glyph(rq3["arms"][1]["color"], False)], False, INK)],
            [(lab["planner_untrained"], [line_glyph(color=col["untrained"], lw=1.3, ls=(0, (4, 2.5)))], False, INK),
             (lab["insta"], [line_glyph(color=col["insta"], lw=0, marker="D", ms=MS + 0.4)], False, INK)],
            [(lab["ours"], [line_glyph(color=col["miniweb"], lw=LW, marker="o", ms=MS)], True, col["miniweb"]),
             (lab["references"], [line_glyph(color=MUTED, lw=1.2, ls=(0, (1.5, 1.3)), marker="o", ms=3.6, mfc="white",
                                             mew=1.0)], False, INK)]]

    sq = (W - L["left"] - L["gap"] - L["right"]) / 2     # two square panels
    xs = [L["left"], L["left"] + sq + L["gap"]]
    fig = plt.figure(figsize=(W, 4))
    A = fig.add_axes([0, 0, 1, 1]); A.axis("off")
    A.set_xlim(0, W); A.set_ylim(4, 0)
    lh = legend(A, rows, 0.02, 0.02, W - 0.02)
    top = 0.02 + lh + L["title_h"]
    H = top + sq + L["bottom"]
    fig.set_size_inches(W, H); A.set_ylim(H, 0)
    axes = [fig.add_axes([x / W, 1 - (top + sq) / H, sq / W, sq / H]) for x in xs]

    practice(axes[0], rq2)
    style_axes(axes[0])
    axes[0].set_ylim(0, 100); axes[0].set_yticks([0, 25, 50, 75, 100]); axes[0].set_xticks([])
    axes[0].set_yticklabels(["0", "25", "50", "75", "100%"])
    p = {k: v for k, v in sc["panels"][0].items() if k != "title"}
    p.update(cfg.get("scaling_panel") or {})
    p["references"] = [dict(r, **(cfg.get("reference_labels") or {}).get(r["label"], {}))   # label positions for
                       for r in p.get("references", [])]                                    # the narrow panel
    scaling_panel(axes[1], p, sc)

    for x, t in zip(xs, cfg["titles"]):
        A.text(x, top - 0.1, t, fontsize=FS["label"], weight="bold", color=INK, va="baseline")
    A.text(0.08, top + sq / 2, "task success", fontsize=FS["label"], color=MUTED, rotation=90, ha="center", va="center")
    A.text(xs[1] + sq / 2, top + sq + 0.2, "training steps", fontsize=FS["label"], color=MUTED, ha="center", va="top")
    out = os.path.join(ROOT, cfg["out"])
    save(fig, out, strip=0.0)
    print("wrote", out, f"({W:.3f} x {H:.3f} in)")


if __name__ == "__main__":
    main()
