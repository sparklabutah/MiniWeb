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

from style import INK, MUTED, FS, rc, header, panel, swatch, bar, style_axes, save  # noqa: E402  (the diagrams' look)
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "rq3_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    benches, arms = cfg["benchmarks"], cfg["arms"]
    by = {a["label"]: a for a in arms}
    for a in arms:
        a["rates"] = {b["key"]: task_rates(b["kind"], a.get(b["key"]) or [], b.get("tasks")) for b in benches}

    n = len(arms)
    two = cfg.get("legend_cols", 2 if n > 3 else 1) == 2  # 2 x 2 legend for four arms, one column otherwise
    rows = (n + 1) // 2 if two else n
    pitch = 0.16
    lh = 0.12 + pitch * rows                             # legend panel height
    top, ph = cfg.get("top", 0.24 + lh + 0.2), cfg.get("plot_height", 1.4)   # plot area: top edge and height (inches)
    W, H = cfg.get("width", 3.25), top + ph + 0.4       # width/top/plot_height: to pair it with another panel
    fig = plt.figure(figsize=(W, H))
    A = fig.add_axes([0, 0, 1, 1]); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    header(fig, A, 0.04, 0.1, cfg.get("title", "Training and composition"), cfg.get("subtitle", cfg["model"] + ", task success"))
    panel(A, 0.04, 0.22, W - 0.08, lh)                   # legend in a light panel, as the diagrams group things
    for i, a in enumerate(arms):
        x, y = (0.14 + (i % 2) * 1.55, 0.22 + 0.06 + pitch * (i // 2 + 0.5)) if two else (0.14, 0.22 + 0.06 + pitch * (i + 0.5))
        swatch(A, x, y, a["color"], hatched=a.get("style") == "hatched")
        A.text(x + 0.21, y, a["label"], fontsize=FS["legend"], color=a["color"] if i == n - 1 else INK, va="center",
               weight="bold" if i == n - 1 else "normal")      # MiniWebAgent: bold, in its colour

    ax = ax_at(0.42, top, W - 0.46, ph)
    bw = 0.8 / n
    LH = 5.0                                             # a value label's height in % units (6.3 pt on this axis)
    xin = (W - 0.46) / len(benches)                      # inches per group on the x-axis
    for gi, b in enumerate(benches):
        ms = [st.mean(a["rates"][b["key"]]) if a["rates"][b["key"]] else None for a in arms]
        for j, a in enumerate(arms):
            xx = gi - 0.4 + (j + 0.5) * bw
            m = ms[j]
            if m is None:
                ax.text(xx, 2, "pending", rotation=90, fontsize=FS["small"], color=MUTED, ha="center", va="bottom")
                continue
            bar(ax, xx, m, bw * 0.86, a["color"], hatched=a.get("style") == "hatched")
            last = j == n - 1                            # the highlighted arm keeps a decimal; narrow bars round
            ax.text(xx, m + 1.0, f"{m:.1f}" if (last or n <= 3) else f"{m:.0f}", fontsize=FS["value"],
                    color=a["color"] if last else INK, ha="center", va="bottom", weight="bold" if last else "normal")
            st_ = stars(b, by[a["compare"]], a) if a.get("compare") else ""
            if st_:
                sy = m + LH - 0.1                        # above its own value; bars sit close, so if a neighbour's
                for k in (j - 1, j + 1):                 # value label is at that height and as wide, move up to its row
                    if not (0 <= k < n and ms[k] is not None):
                        continue
                    lab_k = f"{ms[k]:.1f}" if (k == n - 1 or n <= 3) else f"{ms[k]:.0f}"
                    half = (len(st_) * 0.5 * (FS["value"] + 0.7) + len(lab_k) * 0.58 * FS["value"]) / 72 / 2
                    if bw * xin < half and ms[k] + 1.0 < sy + LH * 0.8 and sy < ms[k] + 1.0 + LH:
                        sy = max(sy, ms[k] + LH - 0.1)
                ax.text(xx, sy, st_, fontsize=FS["value"] + 0.7, color=INK, ha="center", va="bottom")
        for ref in cfg.get("references") or []:
            if ref["benchmark"] == b["key"]:
                ax.plot([gi - 0.42, gi + 0.42], [ref["value"]] * 2, color=MUTED, lw=0.9, ls=(0, (3, 2)), zorder=1)
                ax.text(gi + 0.42, ref["value"] + 1, ref["label"], fontsize=FS["small"], color=MUTED, ha="right", va="bottom")
        ax.text(gi, -4, b["label"], fontsize=FS["label"], color=INK, ha="center", va="top", linespacing=1.05, clip_on=False)
    ax.set_xlim(-0.5, len(benches) - 0.5); ax.set_ylim(0, cfg.get("ymax", 80))
    yt = list(range(0, cfg.get("ymax", 80) + 1, 20))
    ax.set_yticks(yt); ax.set_yticklabels([str(v) for v in yt[:-1]] + [f"{yt[-1]}%"])
    style_axes(ax); ax.set_xticks([])
    A.text(0.08, top + ph / 2, "task success", fontsize=FS["label"], color=MUTED, rotation=90, ha="center", va="center")

    out = os.path.join(ROOT, cfg["out"])
    save(fig, out)                                        # style.save: trims the heading strip
    print("wrote", out)
    for a in arms:
        print(f"  {a['label']:26s}", {k: [round(x, 1) for x in v] for k, v in a["rates"].items()})


if __name__ == "__main__":
    main()
