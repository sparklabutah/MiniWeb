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

    # 2026-10-06 (user): two square plots side by side, a minimal legend (line styles only; what the lines and colours
    # are goes in the caption), no task counts under the ticks. Drawn at its printed width (style.COL_W), 9 pt text.
    W = COL_W
    left, gap, right = 0.4, 0.12, 0.04                   # room for the y ticks; between the plots; right margin
    s_ = (W - left - gap - right) / 2                    # each plot is square
    leg, top = 0.24, 0.26                                # legend row; plots start below it
    H = top + s_ + 0.48
    fig = plt.figure(figsize=(W, H))
    A = fig.add_axes([0, 0, 1, 1]); A.axis("off"); A.set_xlim(0, W); A.set_ylim(H, 0)
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    axa, axb = ax_at(left, top, s_, s_), ax_at(left + s_ + gap, top, s_, s_)
    gw, gg = 0.15, 0.05                                  # legend line glyph width, glyph-to-text gap

    def entry(x, y, kw, lab, **tkw):
        A.add_line(Line2D([x, x + gw], [y] * 2, zorder=3, **kw))
        return x + gw + gg + _w(fig, A.text(x + gw + gg, y, lab, fontsize=FS["legend"], va="center", color=INK, **tkw))

    y0 = leg / 2 + 0.02                                  # the legend: above each plot, its own line kinds
    x = entry(left, y0, dict(color=INK, lw=1.8), "mean") + 0.14
    entry(x, y0, dict(color=BAD, lw=1.4, ls=(0, (1.0, 1.1))), "p\u207f", style="italic")
    x = entry(left + s_ + gap - 0.08, y0, dict(color=INK, lw=1.4), "single") + 0.1
    entry(x, y0, dict(color=INK, lw=1.4, ls=LS["dashed"]), "planner")

    xa = list(range(len(ba)))
    for lab, v in agents:
        axa.plot(xa, v, color=tint(INK, 0.25), lw=0.7, zorder=1)
    axa.plot(xa, indep, color=BAD, lw=1.4, ls=(0, (1.0, 1.1)), zorder=4)   # on top: it nearly coincides with the mean
    axa.plot(xa, mean, color=INK, lw=1.8, marker="o", ms=3.6, zorder=3)
    for i, v in enumerate(mean):
        axa.text(i + 0.12, v + 3, f"{v:.0f}", fontsize=FS["value"], color=INK, ha="left", va="bottom", zorder=5,
                 bbox=dict(fc="white", ec="none", pad=0.3))
    xb = list(range(len(bb)))
    for a, v in arms:
        axb.plot(xb, v, color=a["color"], ls=LS[a["ls"]], lw=1.8 if a.get("bold") else 1.2, marker=a["marker"], ms=3.4,
                 zorder=3 if a.get("bold") else 2)
    v = arms[-1][1]
    for i, y in enumerate(v):
        last = i == len(v) - 1                            # the last label sits above its point, inside the plot
        axb.text(i + (0 if last else 0.1), y + (5 if last else 3), f"{y:.0f}", fontsize=FS["value"],
                 color=arms[-1][0]["color"], ha="center" if last else "left", va="bottom", weight="bold", clip_on=False)
    for ax, bins in ((axa, ba), (axb, bb)):
        ax.set_xlim(-0.25, len(bins) - 0.75); ax.set_ylim(0, 100)
        ax.set_xticks(range(len(bins)))
        ax.set_xticklabels([f"{k}{'+' if k == bins[-1] else ''}" for k in bins])
        ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(["0", "25", "50", "75", "100%"])
        style_axes(ax); ax.tick_params(axis="x", labelsize=FS["tick"])
    axb.set_yticklabels([])
    A.text(left + (W - left - right) / 2, top + s_ + 0.3, "primitives per task", fontsize=FS["label"], color=MUTED,
           ha="center", va="center")
    for t in [t for t in A.texts if t.get_position()[1] == -1]:
        t.remove()

    out = os.path.join(ROOT, cfg["out"])
    save(fig, out, strip=0.0)                                        # style.save: trims the heading strip
    print("wrote", out)
    print("  (a) mean", [round(v, 1) for v in mean], "independent p^n", [round(v, 1) for v in indep], "p",
          round(mean[0] / 100, 3),
          "n", [n_a[k] for k in ba])
    for a, v in arms:
        print(f"  (b) {a['label']:24s}", [round(x, 1) for x in v], "n tasks", [n_b[k] for k in bb])


if __name__ == "__main__":
    main()
