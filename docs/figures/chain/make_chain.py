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
from style import INK, MUTED, BAD, FS, rc, header, panel, style_axes, tint, save  # noqa: E402  (the diagrams' look)
rc()
LS = {"solid": "-", "dashed": (0, (3.2, 1.6))}


def binned(outcomes, length, bins):
    """{bin: [outcomes]} with the last bin open-ended."""
    by = collections.defaultdict(list)
    for tid, ok in outcomes:
        by[min(length[tid], bins[-1])].append(ok)
    return by


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "chain_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    length = {t["task_id"]: len(t["macros"]) for t in human_tasks()}
    ba, bb = cfg["bins_a"], cfg["bins_b"]

    # (a) the ten untrained agents
    agents = []
    for m in yaml.safe_load(open(os.path.join(ROOT, cfg["agents_from"])))["models"]:
        rs = [json.loads(l) for l in open(os.path.join(ROOT, m["judge"])) if l.strip()]
        by = binned([(r["task_id"], float(bool(r["passed"]))) for r in rs if r["task_id"] in length], length, ba)
        agents.append((m["label"], [100 * st.mean(by[k]) for k in ba]))
    mean = [st.mean(v[i] for _, v in agents) for i in range(len(ba))]
    p = mean[0] / 100                                    # independent primitives: a task succeeds with p^n
    n_a = collections.Counter(min(n, ba[-1]) for n in length.values())
    indep = [100 * st.mean(p ** n for n in length.values() if min(n, ba[-1]) == k) for k in ba]

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

    W = 3.25
    fig = plt.figure(figsize=(W, 2.6))
    A = fig.add_axes([0, 0, 1, 1]); A.axis("off")
    lh = 0.5
    top, ph = 0.22 + lh + 0.3, cfg.get("plot_height", 1.2)   # plot_height: to match a paired panel
    H = top + ph + 0.47
    fig.set_size_inches(W, H); A.set_xlim(0, W); A.set_ylim(H, 0)
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])
    header(fig, A, 0.04, 0.1, cfg.get("title", "Failures compound"), cfg.get("subtitle", "success by primitives per task"))
    panel(A, 0.04, 0.22, W - 0.08, lh)
    ent_a = [("each agent", dict(color=tint(INK, 0.3), lw=0.8)), ("mean", dict(color=INK, lw=1.8, marker="o", ms=3.6)),
             (r"$p^n$: independent primitives", dict(color=BAD, lw=1.4, ls=(0, (1.0, 1.1))))]
    x = 0.1                                              # row 1: the left panel; row 2: the right panel (no panel letters)
    t = A.text(x, 0.33, "left:", fontsize=FS["legend"], color=MUTED, va="center", style="italic")
    x += t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi + 0.08
    for lab, kw in ent_a:
        A.add_line(Line2D([x, x + 0.08, x + 0.16], [0.33] * 3, markevery=[1], zorder=3, **kw))
        t = A.text(x + 0.21, 0.33, lab, fontsize=FS["legend"], color=INK, va="center")
        x += 0.21 + t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi + 0.12
    A.text(0.1, 0.5, "right:", fontsize=FS["legend"], color=MUTED, va="center", style="italic")
    for i, (a, _) in enumerate(arms):
        x, y = 0.42 + (i % 2) * 1.42, 0.5 + (i // 2) * 0.14
        A.add_line(Line2D([x, x + 0.08, x + 0.16], [y] * 3, markevery=[1], color=a["color"], ls=LS[a["ls"]],
                          lw=1.8 if a.get("bold") else 1.2, marker=a["marker"], ms=3.4, zorder=3))
        A.text(x + 0.21, y, a["label"], fontsize=FS["legend"], color=a["color"] if a.get("bold") else INK, va="center",
               weight="bold" if a.get("bold") else "normal")

    left, gap = 0.4, 0.3
    pw = (W - left - gap - 0.06) / 2
    axa, axb = ax_at(left, top, pw, ph), ax_at(left + pw + gap, top, pw, ph)
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
                 weight="bold")
    for ax, bins, n, title in ((axa, ba, n_a, "Ten untrained agents, all sites"),
                               (axb, bb, n_b, "Qwen3.5-4B, held-out sites")):
        ax.set_xlim(-0.3, len(bins) - 0.7); ax.set_ylim(0, 100)
        ax.set_xticks(range(len(bins)))
        ax.set_xticklabels([f"{k}{'+' if k == bins[-1] else ''}\n({n[k]})" for k in bins], linespacing=0.95)
        ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(["0", "25", "50", "75", "100%"])
        style_axes(ax); ax.tick_params(axis="x", labelsize=FS["small"])
        ax.set_title(title, fontsize=FS["small"], color=INK, pad=3, loc="left")
    axb.set_yticklabels([])
    A.text(0.08, top + ph / 2, "task success", fontsize=FS["label"], color=MUTED, rotation=90, ha="center", va="center")
    A.text(left + (W - left - 0.06) / 2, top + ph + 0.33, "primitives in the task (number of tasks)", fontsize=FS["label"], color=MUTED,
           ha="center", va="top")

    out = os.path.join(ROOT, cfg["out"])
    save(fig, out)                                        # style.save: trims the heading strip
    print("wrote", out)
    print("  (a) mean", [round(v, 1) for v in mean], "independent p^n", [round(v, 1) for v in indep], "p", round(p, 3),
          "n", [n_a[k] for k in ba])
    for a, v in arms:
        print(f"  (b) {a['label']:24s}", [round(x, 1) for x in v], "n tasks", [n_b[k] for k in bb])


if __name__ == "__main__":
    main()
