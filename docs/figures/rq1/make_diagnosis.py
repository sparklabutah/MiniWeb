"""Diagnosis figure (2026-10-05, user: merge "where drag fails" and "failures compound" into one narrow figure that sits
next to Table 2). About 2 in wide, stacked:
  top     where drag fails: every drag & gesture instance of the ten untrained agents, sorted into outcomes (the cached
          LLM classification of drag_failures.py; same numbers);
  bottom  failures compound: task success by the number of primitives a task chains, for the ten untrained agents (their
          mean and the independent-primitive curve p^n) and for the four Qwen3.5-4B configurations on held-out tasks
          (the same data as chain/make_chain.py).

    python docs/figures/rq1/make_diagnosis.py [--width 2.0]
"""
import argparse, collections, json, os, statistics as st, sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "chain"))
import drag_failures as DF  # noqa: E402  (MODES, COLORS, classify, the cache; chdirs to the repo root)
from make_rq1_bars import ROOT, FAMILY_OF, primitive_filter  # noqa: E402
from make_chain import binned  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from results import _records, human_tasks  # noqa: E402
from style import INK, MUTED, BAD, BLUE, UNTRAINED, FS, rc, style_axes, tint  # noqa: E402
rc()
SMALL = 6.0                                              # the print floor (style.FS["small"])


def drag_rows(cfg):
    only = primitive_filter(cfg.get("primitives"))
    drag = {m for m in only if FAMILY_OF.get(m) == "Drag & gesture"}
    cache = json.load(open(DF.CACHE)) if os.path.exists(DF.CACHE) else {}
    rows = []
    for m in cfg["models"]:
        c = collections.Counter()
        for line in open(m["judge"]):
            if not line.strip():
                continue
            for v in (json.loads(line).get("instances") or {}).values():
                if v["macro"] in drag:
                    c["passed" if v["passed"] else DF.classify(v["macro"], v.get("why", ""), v.get("agent_target", ""),
                                                               cache)] += 1
        rows.append((m["label"], c))
    json.dump(cache, open(DF.CACHE, "w"), indent=0)
    return sorted(rows, key=lambda r: -r[1]["passed"])


def chain_data(rq1, ccfg):
    length = {t["task_id"]: len(t["macros"]) for t in human_tasks()}
    ba, bb = ccfg["bins_a"], ccfg["bins_b"]
    agents = []
    for m in rq1["models"]:
        rs = [json.loads(l) for l in open(os.path.join(ROOT, m["judge"])) if l.strip()]
        by = binned([(r["task_id"], float(bool(r["passed"]))) for r in rs if r["task_id"] in length], length, ba)
        agents.append([100 * st.mean(by[k]) for k in ba])
    mean = [st.mean(v[i] for v in agents) for i in range(len(ba))]
    p = mean[0] / 100
    indep = [100 * st.mean(p ** n for n in length.values() if min(n, ba[-1]) == k) for k in ba]
    runs = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "tables", "tables_config.yaml")))["runs"]
    arms = []
    for a in ccfg["arms"]:
        out = [(tid, float(bool(r.get("ok")))) for run in runs[a["runs"]]["heldout"] for tid, r in _records(run).items()]
        by = binned(out, length, bb)
        arms.append((a, [100 * st.mean(by[k]) for k in bb]))
    return ba, bb, agents, mean, indep, arms


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--width", type=float, default=2.0)
    W = ap.parse_args().width
    rq1 = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "rq1", "rq1_config.yaml")))
    ccfg = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "chain", "chain_config.yaml")))
    rows = drag_rows(rq1)
    ba, bb, agents, mean, indep, arms = chain_data(rq1, ccfg)

    pitch = 0.086                                        # drag rows
    y_t1, y_leg1 = 0.08, 0.22
    y_bars = y_leg1 + 0.36
    y_t2 = y_bars + pitch * len(rows) + 0.25
    y_leg2 = y_t2 + 0.15
    y_plot, ph = y_leg2 + 0.32, 0.66                    # two legend rows
    H = y_plot + ph + 0.3
    fig = plt.figure(figsize=(W, H))
    A = fig.add_axes([0, 0, 1, 1], zorder=-1); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])

    # ── where drag fails ────────────────────────────────────────────────────
    A.text(0.02, y_t1, "Where drag fails", fontsize=7.4, weight="bold", color=INK, va="center")
    for k, mo in enumerate(DF.MODES):                    # legend: 2 columns x 3 rows
        x, y = 0.04 + (k % 2) * 0.98, y_leg1 + (k // 2) * 0.115
        A.add_patch(Rectangle((x, y - 0.035), 0.11, 0.07, fc=DF.COLORS[mo], ec="none"))
        A.text(x + 0.15, y, mo, fontsize=SMALL, color=INK, va="center")
    lx = 0.74                                            # agent names end here; the bars start
    ax = ax_at(lx + 0.03, y_bars, W - lx - 0.15, pitch * len(rows))
    for i, (lab, c) in enumerate(rows):
        n, x = sum(c.values()), 0
        for mo in DF.MODES:
            w = 100 * c[mo] / n
            if w:
                ax.add_patch(Rectangle((x, i - 0.4), w, 0.8, fc=DF.COLORS[mo], ec="white", lw=0.4))
                if w >= 12:
                    ax.text(x + w / 2, i, f"{c[mo]}", fontsize=5.2, ha="center", va="center",
                            color="white" if mo in ("passed", "imprecise", "not committed") else INK)
            x += w
        A.text(lx, y_bars + pitch * (i + 0.5), lab, fontsize=SMALL, color=INK, ha="right", va="center")
    ax.set_xlim(0, 100); ax.set_ylim(len(rows) - 0.5, -0.5)
    ax.set_xticks([0, 50, 100]); ax.set_xticklabels(["0", "50", "100%"]); ax.set_yticks([])
    ax.tick_params(labelsize=SMALL, length=2, width=0.6, pad=1.5, colors=MUTED)
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.6); ax.spines["bottom"].set_color(MUTED)

    # ── failures compound ───────────────────────────────────────────────────
    A.text(0.02, y_t2, "Failures compound", fontsize=7.4, weight="bold", color=INK, va="center")
    x = 0.04                                             # legend: line style = single / planner, colour = un/trained
    for row, entries in enumerate(((("agent", dict(color=tint(INK, 0.3), lw=0.8)), ("mean", dict(color=INK, lw=1.5)),
                                     ("$p^n$: independent", dict(color=BAD, lw=1.3, ls=(0, (1.0, 1.1))))),
                                    (("single", dict(color=UNTRAINED, lw=1.0)), ("planner", dict(color=UNTRAINED, lw=1.2, ls=(0, (3, 1.5)))),
                                     ("trained", dict(color=BLUE, lw=1.5))))):
        x, y = 0.04, y_leg2 + row * 0.12                 # row 1: the left plot; row 2: the right plot's encoding
        for lab, kw in entries:
            A.add_line(Line2D([x, x + 0.13], [y] * 2, **kw))
            t = A.text(x + 0.16, y, lab, fontsize=SMALL, color=INK, va="center")
            x += 0.16 + t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi + 0.08
    left, gap = 0.27, 0.12
    pw = (W - left - gap - 0.03) / 2
    axa, axb = ax_at(left, y_plot, pw, ph), ax_at(left + pw + gap, y_plot, pw, ph)
    xa = list(range(len(ba)))
    for v in agents:
        axa.plot(xa, v, color=tint(INK, 0.3), lw=0.6, zorder=1)
    axa.plot(xa, indep, color=BAD, lw=1.2, ls=(0, (1.0, 1.1)), zorder=4)
    axa.plot(xa, mean, color=INK, lw=1.4, marker="o", ms=2.2, zorder=3)
    axa.text(0.15, mean[0] + 4, f"{mean[0]:.0f}", fontsize=5.6, color=INK, va="bottom")
    axa.text(len(ba) - 1, mean[-1] + 7, f"{mean[-1]:.0f}", fontsize=5.6, color=INK, ha="center", va="bottom")
    xb = list(range(len(bb)))
    for a, v in arms:
        planner = a["ls"] == "dashed"
        axb.plot(xb, v, color=a["color"], ls=(0, (3, 1.5)) if planner else "-", lw=1.5 if a.get("bold") else 1.0,
                 marker="s" if planner else "o", ms=2.2, zorder=3 if a.get("bold") else 2)
    v = arms[-1][1]                                      # MiniWebAgent (blue, dashed): its values, in its colour
    for i, y in enumerate(v):
        axb.text(i + 0.13, y + (5 if i < len(v) - 1 else 0), f"{y:.0f}", fontsize=5.6, color=BLUE, weight="bold",
                 ha="left", va="bottom" if i < len(v) - 1 else "center")
    for axx, bins, title in ((axa, ba, "10 agents"), (axb, bb, "Qwen3.5-4B, held-out")):
        axx.set_xlim(-0.3, len(bins) - 0.7 + (0.25 if axx is axb else 0)); axx.set_ylim(0, 100)
        axx.set_xticks(range(len(bins))); axx.set_xticklabels([f"{k}{'+' if k == bins[-1] else ''}" for k in bins])
        axx.set_yticks([0, 50, 100]); axx.set_yticklabels(["0", "50", "100"])
        style_axes(axx); axx.tick_params(labelsize=SMALL, length=2, pad=1.2)
        axx.set_title(title, fontsize=SMALL, color=INK, pad=2)
    axb.set_yticklabels([])
    A.text(0.06, y_plot + ph / 2, "success", fontsize=SMALL, color=MUTED, rotation=90, ha="center", va="center")
    A.text(left + (W - left) / 2, y_plot + ph + 0.2, "primitives per task", fontsize=SMALL, color=MUTED, ha="center",
           va="center")

    out = os.path.join(ROOT, "docs", "figures", "rq1", "diagnosis")
    fig.savefig(out + ".pdf", dpi=600); fig.savefig(out + ".png", dpi=600)
    print("wrote", out, f"{W:.2f} x {H:.2f} in")
    print("  drag", {lab: dict(c) for lab, c in rows[:3]}, "...")
    print("  chain mean", [round(x, 1) for x in mean], "indep", [round(x, 1) for x in indep])
    for a, v in arms:
        print("  ", a["label"], [round(x, 1) for x in v])


if __name__ == "__main__":
    main()
