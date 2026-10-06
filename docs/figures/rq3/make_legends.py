"""Shared legends of the paper's two full-width result figures (2026-10-06, user: combine the paired panels and share the
legend). One row each, drawn at the full text width (style.FULL_W), 9 pt:

  legend_compose  practice (rq2_skills) + composition (rq3_transfer): the four Qwen3.5-4B configurations as bar swatches
  legend_data     our data vs InSTA's (skill_vs_task) + scaling (scaling_wv): each entry's bar swatch and its line or marker

Labels, colours and hatching come from the panels' own configs, so a legend cannot drift from its panels.

    python docs/figures/rq3/make_legends.py
"""
import os, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, os.path.join(ROOT, "docs", "figures", "common"))
from style import FS, FULL_W, INK, MUTED, panel, rc, save, swatch  # noqa: E402

rc()
RH, SW, GAP, SEP = 0.26, 0.14, 0.06, 0.32      # row height; swatch width; swatch-to-text gap; between entries (in)


def strip(name, rows):
    """rows: [[(label, [glyph drawers], bold, colour)]]; a glyph drawer draws at (x, y) and returns its width. Each row
    is centred in a light panel."""
    H = RH * len(rows) + 0.06
    fig = plt.figure(figsize=(FULL_W, H))
    A = fig.add_axes([0, 0, 1, 1]); A.axis("off"); A.set_xlim(0, FULL_W); A.set_ylim(H, 0)
    rnd = fig.canvas.get_renderer()
    panel(A, 0.02, 0.02, FULL_W - 0.04, H - 0.04)
    for r, entries in enumerate(rows):
        widths = []
        for lab, glyphs, bold, color in entries:          # measure, then centre the row
            t = A.text(0, -1, lab, fontsize=FS["legend"], weight="bold" if bold else "normal")
            widths.append(sum(g(None, None) for g in glyphs) + GAP * len(glyphs) +
                          t.get_window_extent(rnd).width / fig.dpi)
            t.remove()
        x = (FULL_W - sum(widths) - SEP * (len(entries) - 1)) / 2
        y = 0.03 + RH * (r + 0.5)
        for (lab, glyphs, bold, color), w in zip(entries, widths):
            xx = x
            for g in glyphs:
                xx += g(A, (xx, y)) + GAP
            A.text(xx, y, lab, fontsize=FS["legend"], va="center", color=color, weight="bold" if bold else "normal")
            x += w + SEP
    save(fig, os.path.join(HERE, name), strip=0.0)
    print("wrote", os.path.join(HERE, name))


def bar(color, hatched):
    def draw(A, at):
        if A is not None:
            swatch(A, at[0], at[1], color, hatched=hatched, w=SW)
        return SW
    return draw


def line(**kw):
    def draw(A, at):
        if A is not None:
            A.add_line(Line2D([at[0], at[0] + 0.1, at[0] + 0.2], [at[1]] * 3, markevery=[1], zorder=3, **kw))
        return 0.2
    return draw


def main():
    rq3 = yaml.safe_load(open(os.path.join(HERE, "rq3_config.yaml")))
    arms = rq3["arms"]
    strip("legend_compose", [[(a["label"], [bar(a["color"], a.get("style") == "hatched")], i == len(arms) - 1,
                               a["color"] if i == len(arms) - 1 else INK) for i, a in enumerate(arms)]])
    data = yaml.safe_load(open(os.path.join(HERE, "data_config.yaml")))["arms"]
    sc = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "scaling", "scaling_wv_config.yaml")))
    col = sc["colors"]
    lines = [line(color=col["untrained"], lw=1.3, ls=(0, (4, 2.5))),                 # the scaling panel's glyph of
             line(color=col["insta"], lw=0, marker="D", ms=4.4),                     # each arm, in the order of the
             line(color=col["miniweb"], lw=1.8, marker="o", ms=4.0)]                 # data panel's arms
    entries = [(a["label"], [bar(a["color"], a.get("style") == "hatched"), g], i == len(data) - 1,
                a["color"] if i == len(data) - 1 else INK) for i, (a, g) in enumerate(zip(data, lines))]
    if sc["legend"].get("references"):
        entries.append((sc["legend"]["references"], [line(color=MUTED, lw=1.2, ls=(0, (1.5, 1.3)), marker="o", ms=3.6,
                                                          mfc="white", mew=1.0)], False, INK))
    strip("legend_data", [entries[:2], entries[2:]])     # four entries with two glyphs each: two rows at 9 pt


if __name__ == "__main__":
    main()
