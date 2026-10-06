"""RQ3, single column: task success of the same Qwen3.5-4B as a single agent, as an untrained planner, and as
MiniWebAgent, on MiniWeb held-out, WebArena-Lite, WebVoyager and Online-Mind2Web. Arms and runs are set in
rq3_config.yaml. Bars are means over seeds; stars mark p against the arm named in `compare` (the tests of
paper_stats.py: paired permutation over tasks after averaging seeds, exact McNemar for single live-web runs).

    python docs/figures/rq3/make_rq3.py [--config docs/figures/rq3/rq3_config.yaml]
"""
import argparse, os, statistics as st, sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from results import ROOT, task_rates  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "tables"))
from paper_stats import per_task, permutation, mcnemar  # noqa: E402

from style import INK, MUTED, FS, COL_W, HEAD_STRIP, rc, header, panel, swatch, bar, style_axes, save  # noqa: E402
rc()


def stars(bench, ref, arm):
    """*, **, *** for p < .05, .01, .001 of `arm` against `ref` on one benchmark, as paper_stats.py tests it."""
    ra, rb = ref.get(bench["key"]) or [], arm.get(bench["key"]) or []
    if not ra or not rb:
        return ""
    pa, pb = per_task(bench, ra), per_task(bench, rb)
    single_live = len(ra) == 1 and len(rb) == 1 and bench["kind"] in ("webvoyager", "om2w")
    p = mcnemar(pa, pb)[3] if single_live else permutation(pa, pb)[3]
    return "***" if p < 0.001 else "**" if p < 0.01 else "*" if p < 0.05 else ""


def _ext(t, ax):
    """A text's extent in ax's data coordinates: (x0, x1, y0, y1)."""
    bb = t.get_window_extent(ax.figure.canvas.get_renderer()).transformed(ax.transData.inverted())
    return bb.x0, bb.x1, bb.y0, bb.y1


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "rq3_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    benches, arms = cfg["benchmarks"], cfg["arms"]
    by = {a["label"]: a for a in arms}
    for a in arms:
        a["rates"] = {b["key"]: task_rates(b["kind"], a.get(b["key"]) or [], b.get("tasks")) for b in benches}

    # Drawn at its printed width (style.COL_W), so every size below is its size on paper (>= style.MIN_PT).
    n = len(arms)
    two = cfg.get("legend_cols", 2 if n > 3 else 1) == 2  # 2 x 2 legend for four arms, one column otherwise
    rows = (n + 1) // 2 if two else n
    pitch = 0.165                                        # legend row pitch (inches)
    lh = 0.1 + pitch * rows                              # legend panel height
    show_legend = cfg.get("legend", True)                # legend: false when a figure shares one legend (paper Figs. 7, 8)
    top, ph = cfg.get("top", 0.22 + lh + 0.16 if show_legend else 0.42), cfg.get("plot_height", 1.75)
    left, right = 0.39, 0.02                             # room for the axis title and the "80%" tick; right margin
    W = cfg.get("width", COL_W)
    H = top + ph + 0.1 + 0.155 * max(b["label"].count("\n") + 1 for b in benches)
    fig = plt.figure(figsize=(W, H))
    A = fig.add_axes([0, 0, 1, 1]); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    rnd = fig.canvas.get_renderer()
    header(fig, A, 0.04, 0.1, cfg.get("title", "Training and composition"), cfg.get("subtitle", cfg["model"] + ", task success"))
    if show_legend:
        panel(A, 0.04, 0.22, W - 0.08, lh)               # legend in a light panel, as the diagrams group things
    sw, tg, cg = 0.13, 0.05, 0.1                         # swatch width, swatch-to-text gap, gap between the columns
    texts = []
    for i, a in enumerate(arms):
        texts.append(A.text(0, 0, a["label"], fontsize=FS["legend"], color=a["color"] if i == n - 1 else INK,
                            va="center", weight="bold" if i == n - 1 else "normal"))   # MiniWebAgent: bold, coloured
    tw = [t.get_window_extent(rnd).width / fig.dpi for t in texts]
    c1 = max(tw[0::2]) if two else max(tw)               # width of the first column's labels
    cols = [0, sw + tg + c1 + cg] if two else [0]
    used = cols[-1] + sw + tg + (max(tw[1::2]) if two else c1)
    x0 = 0.04 + (max(0.05, (W - 0.08 - used) / 2) if two else 0.08)   # two columns: centred in the panel
    for i, a in enumerate(arms):
        x = x0 + (cols[i % 2] if two else 0)
        y = 0.22 + 0.05 + pitch * ((i // 2 if two else i) + 0.5)
        if show_legend:
            swatch(A, x, y, a["color"], hatched=a.get("style") == "hatched", w=sw)
            texts[i].set_position((x + sw + tg, y))
        else:
            texts[i].remove()

    aw = W - left - right
    ax = ax_at(left, top, aw, ph)
    pad = cfg.get("xpad", 0.47)                          # x-range beyond the outer groups' centres (group units)
    ax.set_xlim(-pad, len(benches) - 1 + pad); ax.set_ylim(0, cfg.get("ymax", 80))
    pt = cfg.get("ymax", 80) / (ph * 72)                 # one point in y data units
    fill = cfg.get("group_fill", 0.88)                   # share of a group's width its bars take
    bw = fill / n
    for gi, b in enumerate(benches):
        ms = [st.mean(a["rates"][b["key"]]) if a["rates"][b["key"]] else None for a in arms]
        for j, a in enumerate(arms):
            xx = gi - fill / 2 + (j + 0.5) * bw
            m = ms[j]
            if m is None:
                ax.text(xx, 2, "pending", rotation=90, fontsize=FS["small"], color=MUTED, ha="center", va="bottom")
                continue
            bar(ax, xx, m, bw * 0.86, a["color"], hatched=a.get("style") == "hatched")
            last = j == n - 1                            # the highlighted arm keeps a decimal; narrow bars round
            # The value reads upwards above its bar: at 9 pt a value is wider than a bar, so upright values would run
            # into their neighbours. Its stars sit right above it, in the same column, so each belongs to one bar.
            v = ax.text(xx, m + 1.2, f"{m:.1f}" if (last or n <= 3) else f"{m:.0f}", fontsize=FS["value"],
                        color=a["color"] if last else INK, rotation=90, rotation_mode="anchor", ha="left",
                        va="center_baseline", weight="bold" if last else "normal")
            st_ = stars(b, by[a["compare"]], a) if a.get("compare") else ""
            if st_:                                      # baseline just under the value's end; an asterisk's ink is ~4 pt up
                ax.text(xx, _ext(v, ax)[3] - pt * 0.8, st_, fontsize=FS["value"], color=INK, ha="center", va="baseline")
        for ref in cfg.get("references") or []:
            if ref["benchmark"] == b["key"]:
                ax.plot([gi - 0.42, gi + 0.42], [ref["value"]] * 2, color=MUTED, lw=0.9, ls=(0, (3, 2)), zorder=1)
                ax.text(gi + 0.42, ref["value"] + 1, ref["label"], fontsize=FS["small"], color=MUTED, ha="right", va="bottom")
    labs = [ax.text(gi, -3.5, b["label"], fontsize=FS["label"], color=INK, ha="center", va="top", linespacing=1.05,
                    clip_on=False) for gi, b in enumerate(benches)]
    for _ in range(20):                                  # neighbouring benchmark names: push apart to a 4 pt gap
        moved = False
        for l1, l2 in zip(labs, labs[1:]):
            gap = (_ext(l2, ax)[0] - _ext(l1, ax)[1]) * aw / (ax.get_xlim()[1] - ax.get_xlim()[0]) * 72
            if gap < 4:
                d = (4 - gap) / 2 / 72 / aw * (ax.get_xlim()[1] - ax.get_xlim()[0])
                l1.set_x(l1.get_position()[0] - d); l2.set_x(l2.get_position()[0] + d); moved = True
        if not moved:
            break
    yt = list(range(0, cfg.get("ymax", 80) + 1, 20))
    ax.set_yticks(yt); ax.set_yticklabels([str(v) for v in yt[:-1]] + [f"{yt[-1]}%"])
    style_axes(ax); ax.set_xticks([])
    A.text(0.08, top + ph / 2, "task success", fontsize=FS["label"], color=MUTED, rotation=90, ha="center", va="center")

    out = os.path.join(ROOT, cfg["out"])
    save(fig, out)                                        # style.save: trims the heading strip
    print("wrote", out, f"({W:.3f} x {H - HEAD_STRIP:.3f} in)")
    for a in arms:
        print(f"  {a['label']:26s}", {k: [round(x, 1) for x in v] for k, v in a["rates"].items()})


if __name__ == "__main__":
    main()
