"""Scaling, single column: one line plot per panel, side by side (e.g. WebArena-Lite, WebVoyager sample), in the style
of the RQ3 figure.
In each panel, the planner with one pooled adapter trained on growing subsets of the generated data, the same recipe on
InSTA's live-web trajectories at matched size, and the untrained planner as a dashed reference; task success against
training steps. Panels, runs and step counts are set in scaling_config.yaml; points are means over the listed runs.

    python docs/figures/scaling/make_scaling.py [--config docs/figures/scaling/scaling_config.yaml]
"""
import argparse, os, statistics as st, sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from results import ROOT, task_rates  # noqa: E402

from style import INK, MUTED, GRID, FS, rc, header, logo, style_axes, panel as legend_panel, save  # noqa: E402  (the diagrams' look)
rc()
ORDER = ["100", "300", "1K", "3.1K", "7K"]
LW, MS = 1.8, 4.2                                        # our curve: line width, marker size (pt)


def panel(ax, p, cfg):
    col, steps = cfg["colors"], cfg["steps"]
    fig = ax.figure
    rate = lambda runs: st.mean(task_rates(p["kind"], runs, p.get("tasks"))) if runs else None
    ylo, yhi = p["ylim"]
    xr = p.get("xlim", [450, 100000])
    ax.set_xscale("log"); ax.set_xlim(*xr); ax.set_ylim(ylo, yhi)
    for r in p.get("references", []):                  # published curves, for reference only (other setups)
        xs, ys = zip(*r["points"])
        ax.plot(xs, ys, color=r["color"], lw=1.2, ls=(0, (1.5, 1.3)), marker=r.get("marker", "o"), ms=3.6,
                mfc="white", mew=1.0, zorder=2)
        dy = (yhi - ylo) * r.get("label_dy", 0.04)
        i = r.get("label_at", -1)                        # which point carries the name
        t = ax.text(xs[i] * r.get("label_dx", 1.0), ys[i] + dy, r["label"], fontsize=FS["small"], color=r["color"],
                    ha=r.get("ha", "right"), va=("bottom" if dy > 0 else "top" if dy < 0 else "center"), weight="bold")
        if r.get("logo"):                                # the model's logo just left of its name
            fig.canvas.draw()
            bb = t.get_window_extent(fig.canvas.get_renderer())
            W, H = fig.get_size_inches()
            logo(fig, bb.x0 / fig.dpi - 0.09, H - (bb.y0 + bb.y1) / 2 / fig.dpi, os.path.join(ROOT, r["logo"]),
                 size=0.12)
    b0 = rate(p["untrained"])
    if b0 is not None:
        ax.axhline(b0, color=col["untrained"], lw=1.3, ls=(0, (4, 2.5)), zorder=1)
        ax.text(1600, b0 - (yhi - ylo) * 0.015, f"planner, untrained: {b0:.1f}", fontsize=FS["value"], color=MUTED,
                ha="left", va="top")             # under the line, clear of the curve and the reference markers (review round 3)
    pts = [(steps[k], rate(p["miniweb"].get(k) or []), k) for k in ORDER if k in p["miniweb"]]   # absent key: not drawn
    have = [(x, y) for x, y, _ in pts if y is not None]
    best = max([y for _, y in have] + [rate(p["insta"]) or 0])
    for x, y, k in pts:
        if y is None:
            ax.text(x, ylo + (yhi - ylo) * 0.05, "pending", rotation=90, fontsize=FS["small"], color=MUTED, ha="center",
                    va="bottom")
            continue
        below = (b0 is not None and y < b0) or k in p.get("label_below", [])   # under the dashed line, or asked:
                                                                            # label it below
        ax.text(x * 1.15, y + (yhi - ylo) * (-0.035 if below else 0.035), f"{y:.1f}", fontsize=FS["value"], color=INK,
                ha="left", va="top" if below else "bottom", weight="bold" if y == best else "normal", zorder=5,
                bbox=dict(fc="white", ec="none", pad=0.4) if k in p.get("label_below", []) else None)
    if have:
        ax.plot(*zip(*have), color=col["miniweb"], lw=LW, marker="o", ms=MS, zorder=3)
    vi = rate(p["insta"])
    if vi is not None:
        ax.plot([steps["insta"]], [vi], color=col["insta"], marker="D", ms=MS + 0.4, lw=0, zorder=4)
        ax.text(steps["insta"] / 1.3, vi, f"{vi:.1f}", fontsize=FS["value"], color=col["insta"], ha="right",
                va="center", weight="bold" if vi == best else "normal")
    else:
        ax.text(steps["insta"], ylo + (yhi - ylo) * 0.05, "InSTA pending", rotation=90, fontsize=FS["small"],
                color=col["insta"], ha="center", va="bottom", alpha=0.8)
    ticks = [t for t in (1e3, 1e4, 1e5, 1e6) if xr[0] <= t <= xr[1]]
    ax.set_xticks(ticks); ax.set_xticklabels([{1e3: "1K", 1e4: "10K", 1e5: "100K", 1e6: "1M"}[t] for t in ticks])
    ax.set_xticks([], minor=True)
    yt = list(range(ylo, yhi + 1, 10 if yhi - ylo > 25 else 5))
    ax.set_yticks(yt); ax.set_yticklabels([str(v) for v in yt[:-1]] + [f"{yt[-1]}%"])
    style_axes(ax)
    if p.get("title"):
        ax.set_title(p["title"], fontsize=FS["label"], color=INK, pad=9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "scaling_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    col, leg = cfg["colors"], cfg["legend"]

    W = cfg.get("width", 3.25)                           # inches; a narrower figure keeps the same font sizes
    fig = plt.figure(figsize=(W, 1.78))
    A = fig.add_axes([0, 0, 1, 1]); A.axis("off")
    entries = [(leg["untrained"], dict(color=col["untrained"], lw=1.3, ls=(0, (4, 2.5)))),
               (leg["miniweb"], dict(color=col["miniweb"], lw=LW, marker="o", ms=MS)),
               (leg["insta"], dict(color=col["insta"], lw=0, marker="D", ms=MS + 0.4))]
    if leg.get("references"):                           # one entry for the published curves
        entries.append((leg["references"], dict(color=MUTED, lw=1.2, ls=(0, (1.5, 1.3)), marker="o", ms=3.6,
                                                 mfc="white", mew=1.0)))
    x, y, rows = 0.12, 0.33, 1                           # legend in a light panel; entries wrap onto new rows
    for lab, kw in entries:
        t = A.text(0, 0, lab.replace(", ", ",\n") if cfg.get("legend_split", True) else lab, fontsize=FS["legend"],
                   color=INK, va="center", linespacing=1.0)
        w = 0.25 + t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi
        if x > 0.12 and x + w > W - 0.08:
            x, y, rows = 0.12, y + 0.155, rows + 1
        A.add_line(Line2D([x, x + 0.09, x + 0.18], [y] * 3, markevery=[1], zorder=3, **kw))
        t.set_position((x + 0.25, y))
        x += w + 0.22
    lh = 0.22 + 0.155 * (rows - 1)
    legend_panel(A, 0.04, 0.22, W - 0.08, lh)
    top, ph, left, gap = 0.22 + lh + (0.32 if any(p.get("title") for p in cfg["panels"]) else 0.2), \
        cfg.get("plot_height", 1.25), 0.4, 0.3
    H = top + ph + 0.36
    fig.set_size_inches(W, H); A.set_xlim(0, W); A.set_ylim(H, 0)
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    header(fig, A, 0.04, 0.1, cfg.get("title", "Scaling"), cfg.get("subtitle", cfg["model"] + ", planner + one pooled adapter"),
           logo_path=os.path.join(ROOT, cfg["model_logo"]) if cfg.get("header_logo") else None)
    n = len(cfg["panels"])                                # one panel, or several side by side
    pw = (W - left - gap * (n - 1) - 0.06) / n
    for i, p in enumerate(cfg["panels"]):
        panel(ax_at(left + i * (pw + gap), top, pw, ph), p, cfg)
    A.text(0.08, top + ph / 2, "task success", fontsize=FS["label"], color=MUTED, rotation=90, ha="center", va="center")
    A.text(left + (W - left - 0.06) / 2, top + ph + 0.16, "training steps (log scale)", fontsize=FS["label"],
           color=MUTED, ha="center", va="top")

    out = os.path.join(ROOT, cfg["out"])
    save(fig, out)                                        # style.save: trims the heading strip
    print("wrote", out)
    for p in cfg["panels"]:
        r = lambda runs: round(st.mean(task_rates(p["kind"], runs, p.get("tasks"))), 1) if runs else "pending"
        print(f"  {p['title']:24s} untrained {r(p['untrained'])}", {k: r(p['miniweb'].get(k) or []) for k in ORDER},
              "insta", r(p["insta"]))


if __name__ == "__main__":
    main()
