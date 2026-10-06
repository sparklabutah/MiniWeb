"""Success by chain length, single column, two panels: (a) the ten untrained agents of Tab. 2 on all 376 tasks, with
their mean and what independent primitives would give (p^n); (b) the four Qwen3.5-4B arms of Fig. 7 on the held-out
tasks. Chain length = the number of primitives a human task chains. Settings in chain_config.yaml.

    python docs/figures/chain/make_chain.py [--config docs/figures/chain/chain_config.yaml]
"""
import argparse, collections, json, os, statistics as st, sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from results import ROOT, _records, human_tasks  # noqa: E402
from style import INK, MUTED, BAD, FS, COL_W, rc, header, panel, style_axes, tint, save, _w  # noqa: E402  (the diagrams' look)
rc()
LS = {"solid": "-", "dashed": (0, (3.2, 1.6))}


def binned(outcomes, length, bins):
    """{bin: [outcomes]} with the last bin open-ended."""
    by = collections.defaultdict(list)
    for tid, ok in outcomes:
        by[min(length[tid], bins[-1])].append(ok)
    return by


def ten_agents(cfg, length):
    """Panel (a): each untrained agent's VLM-judge success by primitives per task, their mean, and the independent-
    primitives prediction p^n (p: the mean success on one-primitive tasks), per bin of cfg['bins_a']."""
    ba = cfg["bins_a"]
    agents = []
    for m in yaml.safe_load(open(os.path.join(ROOT, cfg["agents_from"])))["models"]:
        rs = [json.loads(l) for l in open(os.path.join(ROOT, m["judge"])) if l.strip()]
        by = binned([(r["task_id"], float(bool(r["passed"]))) for r in rs if r["task_id"] in length], length, ba)
        agents.append((m["label"], [100 * st.mean(by[k]) for k in ba]))
    mean = [st.mean(v[i] for _, v in agents) for i in range(len(ba))]
    p = mean[0] / 100                                    # independent primitives: a task succeeds with p^n
    indep = [100 * st.mean(p ** n for n in length.values() if min(n, ba[-1]) == k) for k in ba]
    return agents, mean, indep


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "chain_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    length = {t["task_id"]: len(t["macros"]) for t in human_tasks()}
    ba, bb = cfg["bins_a"], cfg["bins_b"]

    # (a) the ten untrained agents
    agents, mean, indep = ten_agents(cfg, length)
    n_a = collections.Counter(min(n, ba[-1]) for n in length.values())

    # (b) the four arms on the held-out tasks
    runs = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "tables", "tables_config.yaml")))["runs"]
    arms, held = [], None
    for a in cfg["arms"]:
        rl = runs[a["runs"]]["heldout"]
        out = [(tid, float(bool(r.get("ok")))) for run in rl for tid, r in _records(run).items()]
        held = held or {tid for tid, _ in out}
        by = binned(out, length, bb)
        arms.append((a, [100 * st.mean(by[k]) for k in bb]))
    n_b = collections.Counter(min(length[t], bb[-1]) for t in held)

    # Drawn at its printed width (style.COL_W) so every size is its size on paper: no text below style.MIN_PT (9 pt).
    W = COL_W
    fig = plt.figure(figsize=(W, 2.6))
    A = fig.add_axes([0, 0, 1, 1]); A.axis("off")
    rp, rpad = 0.17, 0.07                                # legend row pitch and padding (inches)
    lh = 2 * rpad + 4 * rp + 0.13                        # five legend rows: two for the left panel, three for the right
    tit = 0.3                                            # two-line panel titles
    top, ph = 0.22 + lh + 0.12 + tit, cfg.get("plot_height", 1.2)   # plot_height: to match a paired panel
    H = top + ph + 0.56
    fig.set_size_inches(W, H); A.set_xlim(0, W); A.set_ylim(H, 0)
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    header(fig, A, 0.04, 0.1, cfg.get("title", "Failures compound"), cfg.get("subtitle", "success by primitives per task"))
    panel(A, 0.04, 0.22, W - 0.08, lh)
    row = lambda k: 0.22 + rpad + 0.065 + k * rp         # centre of legend row k
    gw, gg = 0.16, 0.05                                  # line glyph width, glyph-to-text gap

    def entry(x, y, kw, lab, **tkw):
        """A legend line glyph and its label; returns the label's right edge."""
        A.add_line(Line2D([x, x + gw / 2, x + gw], [y] * 3, markevery=[1], zorder=3, **kw))
        return x + gw + gg + _w(fig, A.text(x + gw + gg, y, lab, fontsize=FS["legend"], va="center", **tkw))

    # rows 1-2: the left panel; rows 3-5: the right panel (no panel letters). p^n in Unicode (U+207F), not mathtext,
    # whose superscript would print at ~70% of 9 pt.
    x0 = 0.1
    A.text(x0, row(0), "left:", fontsize=FS["legend"], color=MUTED, va="center", style="italic")
    A.text(x0, row(2), "right:", fontsize=FS["legend"], color=MUTED, va="center", style="italic")
    xe = x0 + _w(fig, A.text(0, -1, "right:", fontsize=FS["legend"], style="italic")) + 0.1   # entries start here
    x = entry(xe, row(0), dict(color=tint(INK, 0.3), lw=0.8), "each agent", color=INK) + 0.16
    entry(x, row(0), dict(color=INK, lw=1.8, marker="o", ms=3.6), "mean", color=INK)
    A.add_line(Line2D([xe, xe + gw], [row(1)] * 2, color=BAD, lw=1.4, ls=(0, (1.0, 1.1)), zorder=3))
    x = xe + gw + gg + _w(fig, A.text(xe + gw + gg, row(1), "p\u207f", fontsize=FS["legend"], color=INK, va="center",
                                      style="italic"))
    A.text(x, row(1), ": independent primitives", fontsize=FS["legend"], color=INK, va="center")
    cw = max(_w(fig, A.text(0, -1, a["label"], fontsize=FS["legend"])) for a, _ in arms[0::2])   # right group: 2 x 2
    cw2 = max(_w(fig, A.text(0, -1, a["label"], fontsize=FS["legend"], weight="bold" if a.get("bold") else "normal"))
              for a, _ in arms[1::2])
    cg = (W - 0.1 - x0 - 2 * (gw + gg) - cw - cw2)       # the columns fill the panel, 0.06 in from its right edge
    for i, (a, _) in enumerate(arms):
        x, y = x0 + (i % 2) * (gw + gg + cw + cg), row(3 + i // 2)
        entry(x, y, dict(color=a["color"], ls=LS[a["ls"]], lw=1.8 if a.get("bold") else 1.2, marker=a["marker"],
                         ms=3.4), a["label"], color=a["color"] if a.get("bold") else INK,
              weight="bold" if a.get("bold") else "normal")

    # the two panels share the x scale (inches per primitive), so the left one, with more bins, is wider. Bin counts at
    # 9 pt need all the width: the left panel's first label may overhang into the margin under the y ticks.
    left, gap, right = 0.56, 0.14, 0.1                   # room for the y ticks; between the panels; for the last label
    lim_a, lim_b = (-0.15, len(ba) - 0.75), (-0.25, len(bb) - 0.7)
    span_a, span_b = lim_a[1] - lim_a[0], lim_b[1] - lim_b[0]
    u = (W - left - gap - right) / (span_a + span_b)
    axa, axb = ax_at(left, top, u * span_a, ph), ax_at(left + u * span_a + gap, top, u * span_b, ph)
    xa = list(range(len(ba)))
    for lab, v in agents:
        axa.plot(xa, v, color=tint(INK, 0.3), lw=0.8, zorder=1)
    axa.plot(xa, indep, color=BAD, lw=1.4, ls=(0, (1.0, 1.1)), zorder=4)   # on top: it nearly coincides with the mean
    axa.plot(xa, mean, color=INK, lw=1.8, marker="o", ms=3.6, zorder=3)
    for i, v in enumerate(mean):
        axa.text(i + 0.14, v + 4, f"{v:.0f}", fontsize=FS["value"], color=INK, ha="left", va="bottom", zorder=5,
                 bbox=dict(fc="white", ec="none", pad=0.4))
    xb = list(range(len(bb)))
    for a, v in arms:
        axb.plot(xb, v, color=a["color"], ls=LS[a["ls"]], lw=1.8 if a.get("bold") else 1.2, marker=a["marker"], ms=3.4,
                 zorder=3 if a.get("bold") else 2)
    v = arms[-1][1]
    for i, y in enumerate(v):
        axb.text(i + 0.1, y + 3, f"{y:.0f}", fontsize=FS["value"], color=arms[-1][0]["color"], ha="left", va="bottom",
                 weight="bold", clip_on=False)
    for ax, bins, n, lim, title in ((axa, ba, n_a, lim_a, "Ten untrained agents,\nall sites"),
                                    (axb, bb, n_b, lim_b, "Qwen3.5-4B,\nheld-out sites")):
        ax.set_xlim(*lim); ax.set_ylim(0, 100)
        ax.set_xticks(range(len(bins)))
        ax.set_xticklabels([f"{k}{'+' if k == bins[-1] else ''}\n({n[k]})" for k in bins], linespacing=0.95)
        ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(["0", "25", "50", "75", "100%"])
        style_axes(ax); ax.tick_params(axis="x", labelsize=FS["small"])
        ax.set_title(title, fontsize=FS["small"], color=INK, pad=3, loc="left", linespacing=1.05)
    axb.set_yticklabels([])
    A.text(0.1, top + ph / 2, "task success", fontsize=FS["label"], color=MUTED, rotation=90, ha="center", va="center")
    A.text(left + (W - left - right) / 2, top + ph + 0.38, "primitives in the task (number of tasks)",
           fontsize=FS["label"], color=MUTED, ha="center", va="top")
    for t in [t for t in A.texts if t.get_position()[1] == -1]:
        t.remove()                                       # the width probes

    out = os.path.join(ROOT, cfg["out"])
    save(fig, out)                                        # style.save: trims the heading strip
    print("wrote", out)
    print("  (a) mean", [round(v, 1) for v in mean], "independent p^n", [round(v, 1) for v in indep], "p",
          round(mean[0] / 100, 3),
          "n", [n_a[k] for k in ba])
    for a, v in arms:
        print(f"  (b) {a['label']:24s}", [round(x, 1) for x in v], "n tasks", [n_b[k] for k in bb])


if __name__ == "__main__":
    main()
