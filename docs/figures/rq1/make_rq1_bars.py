"""RQ1, single column: instances passed per skill family and per reasoning operation, as grouped bars.

Which models appear, and where their results come from, is set in rq1_config.yaml (one entry per model). Each entry
points at a run's per-instance macro-judge verdicts (Gemini 3.5 Flash, webmix.judge_runs); this script recomputes the
family and operation rates from them, the same way webmix/rq1_analysis.py does. Whiskers are Wilson 95% intervals.

    python docs/figures/rq1/make_rq1_bars.py [--config docs/figures/rq1/rq1_config.yaml]
"""
import argparse, collections, json, math, os, sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
os.chdir(ROOT)
from datagen.viewer import FAMILY_OF  # noqa: E402
from evaluation import macro_judge as MJ  # noqa: E402
sys.path.insert(0, os.path.join(ROOT, "docs", "figures", "common"))
from results import primitive_filter  # noqa: E402

plt.rcParams.update({"font.family": "Nimbus Sans", "font.size": 6.5, "pdf.fonttype": 42, "ps.fonttype": 42,
                     "hatch.linewidth": 0.5})
INK, MUTED, GRID = "#14213D", "#4A5568", "#E6E9EE"
FAM = {"Drag & gesture": "#6B4C9A", "Discrete selection": "#2B5C9E", "Text entry": "#2E7D6B",
       "Form transaction": "#A8520F", "Navigation": "#8A6D0B", "Out-of-page I/O": "#A33B4C", "Reasoning base": "#14213D"}
LABEL = {"Drag & gesture": "Drag &\ngesture", "Discrete selection": "Discrete\nselection", "Text entry": "Text\nentry",
         "Form transaction": "Form\ntransaction", "Navigation": "Navigation", "Out-of-page I/O": "Out-of-page\nI/O",
         "Reasoning base": "Reasoning"}
FIXED_ORDER = ["Drag & gesture", "Discrete selection", "Text entry", "Form transaction", "Navigation", "Out-of-page I/O",
               "Reasoning base"]
# the dataviz reference palette, for entries without a color
DEFAULT_PALETTE = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#4a3aa7", "#e34948"]


def collect(path, only=None):
    """Task success and per-family / per-operation instance counts [passed, total] from a run's judge.jsonl.
    `only`: count the instances of these primitives (task success always uses the whole task)."""
    fam, op = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
    n = task_j = task_v = 0
    for line in open(path):
        if not line.strip():
            continue
        r = json.loads(line)
        n += 1
        task_j += bool(r.get("passed"))
        task_v += bool(r.get("verifier"))
        _, task, _ = MJ._load(r["key"])
        ops = task.get("macro_operations") or {}
        for inst, v in (r.get("instances") or {}).items():
            if only is not None and v["macro"] not in only:
                continue
            f = "Reasoning base" if v["macro"] == "report_information" else FAMILY_OF.get(v["macro"], "Other")
            fam[f][0] += bool(v["passed"]); fam[f][1] += 1
            if ops.get(inst):
                op[ops[inst]][0] += bool(v["passed"]); op[ops[inst]][1] += 1
    return {"episodes": n, "task_judge": task_j / max(n, 1), "task_verifier": task_v / max(n, 1),
            "family": dict(fam), "op": dict(op)}


def wilson(k, n, z=1.96):
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return 100 * (c - h), 100 * (c + h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "rq1_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    models = cfg["models"]
    used = {m.get("color") for m in models}
    spare = iter(c for c in DEFAULT_PALETTE if c not in used)
    for m in models:
        if not m.get("color"):                 # draw a spare color only when the config sets none
            m["color"] = next(spare)
        m.setdefault("style", "solid")
        m["res"] = collect(m["judge"], primitive_filter(cfg.get("primitives")))
    solid = [m for m in models if m["style"] == "solid"] or models

    # rows: families (all seen) and operations (rare ones pooled into "other")
    fams = sorted({f for m in models for f in m["res"]["family"] if f in FAM}, key=FIXED_ORDER.index)
    ref = models[0]["res"]["op"]
    big = [o for o in ref if ref[o][1] >= cfg.get("min_op_instances", 15)]
    small = sorted(o for o in ref if o not in big)
    pool = cfg.get("rare_ops", "pool") == "pool"           # pool rare operations into "other", or drop them
    for m in models:
        ops = m["res"]["op"]
        m["ops"] = {o: ops.get(o, [0, ref[o][1]]) for o in big}
        if small and pool:
            m["ops"]["other"] = [sum(ops.get(o, [0, 0])[0] for o in small), sum(ref[o][1] for o in small)]
    rate = lambda m, field, k: m["res"]["family"][k][0] / m["res"]["family"][k][1] if field == "family" else \
        m["ops"][k][0] / m["ops"][k][1]
    if cfg.get("sort", "weakest_first") == "weakest_first":
        fams.sort(key=lambda f: sum(rate(m, "family", f) for m in solid) / len(solid))
        op_keys = sorted(big, key=lambda o: sum(rate(m, "op", o) for m in solid) / len(solid)) + (["other"] if small and pool else [])
    else:
        op_keys = big + (["other"] if small and pool else [])

    W = 3.25
    nl = math.ceil(len(models) / 2)
    leg_h = 0.17 + 0.17 * nl
    ya, ha_, yb, hb = leg_h + 0.2, 1.0, leg_h + 0.2 + 1.0 + 0.62, 0.78
    H = yb + hb + 0.3
    fig = plt.figure(figsize=(W, H))
    A = fig.add_axes([0, 0, 1, 1]); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])

    # legend: swatch, logo, name, task success
    A.text(W - 0.04, 0.08, "task success (judge)", fontsize=4.8, color=MUTED, style="italic", ha="right", va="center")
    for i, m in enumerate(models):
        col, row = i % 2, i // 2
        x0, y = 0.04 + col * 1.6, 0.25 + row * 0.17
        A.add_patch(Rectangle((x0, y - 0.04), 0.1, 0.08, fc=m["color"] if m["style"] == "solid" else "white",
                              ec=m["color"], lw=0.6, hatch="//////" if m["style"] == "hatched" else None, zorder=3))
        la = ax_at(x0 + 0.14, y - 0.065, 0.13, 0.13)
        la.imshow(Image.open(m["logo"]).convert("RGBA"), interpolation="lanczos"); la.axis("off")
        t = A.text(x0 + 0.32, y, m["label"], fontsize=5.6, weight="bold", color=INK, va="center")
        if m.get("note"):
            A.text(x0 + 0.32 + t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi + 0.04, y, m["note"],
                   fontsize=4.9, color=MUTED, va="center")
        A.text(x0 + 1.52, y, f"{100 * m['res']['task_judge']:.0f}%", fontsize=5.6, weight="bold", color=INK, ha="right",
               va="center")

    def bars(y0, h, tag, title, keys, field, label_fn):
        A.text(0.02, y0 - 0.09, tag, fontsize=7, weight="bold", color=INK, va="center")
        A.text(0.2, y0 - 0.09, title, fontsize=6.4, color=INK, va="center")
        ax = ax_at(0.36, y0, W - 0.4, h)
        k = len(models)
        bw = 0.8 / k
        for gi, key in enumerate(keys):
            for j, m in enumerate(models):
                kk, n = (m["res"]["family"][key] if field == "family" else m["ops"][key])
                x = gi - 0.4 + (j + 0.5) * bw
                v = 100 * kk / n
                hatched = m["style"] == "hatched"
                ax.bar(x, v, bw * 0.92, color="white" if hatched else m["color"], edgecolor=m["color"] if hatched else "none",
                       hatch="//////" if hatched else None, lw=0.6 if hatched else 0, zorder=2)
                lo, hi = wilson(kk, n)
                ax.plot([x, x], [lo, hi], color=INK, lw=0.45, alpha=0.55, zorder=3, solid_capstyle="butt")
            label_fn(ax, gi, key)
        ax.set_xlim(-0.55, len(keys) - 0.45); ax.set_ylim(0, 100)
        ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(["0", "25", "50", "75", "100%"], fontsize=5)
        ax.tick_params(axis="y", length=2, width=0.5, pad=1.5, colors=MUTED)
        ax.set_xticks([])
        ax.grid(axis="y", color=GRID, lw=0.5); ax.set_axisbelow(True)
        for sp in ("top", "right"): ax.spines[sp].set_visible(False)
        for sp in ("left", "bottom"): ax.spines[sp].set_linewidth(0.5); ax.spines[sp].set_color(MUTED)
        return ax

    def fam_label(ax, gi, f):
        ax.text(gi, -6, LABEL[f], fontsize=5.0, weight="bold", color=FAM[f], ha="center", va="top", linespacing=1.0,
                transform=ax.transData, clip_on=False)

    def op_label(ax, gi, o):
        ax.text(gi, -6, o, fontsize=5.2, family="DejaVu Sans Mono", color=INK, ha="center", va="top", clip_on=False)

    axa = bars(ya, ha_, "(a)", "Skill family: instances passed", fams, "family", fam_label)
    axb = bars(yb, hb, "(b)", "Reasoning operation: instances passed", op_keys, "op", op_label)

    if cfg.get("annotate", True):
        weakest = fams[0]
        if all(min(fams, key=lambda f: rate(m, "family", f)) == weakest for m in solid):
            top = max(wilson(*m["res"]["family"][weakest])[1] for m in models)
            axa.text(0, top + 4, "weakest\nfor every\nagent", fontsize=4.6, style="italic", color=FAM[weakest],
                     ha="center", va="bottom", linespacing=1.0)
        same = [m for m in solid if m["logo"] == solid[0]["logo"]]      # one model family at two scales
        if len(same) >= 2 and "Reasoning base" in fams:
            a, b = (100 * rate(m, "family", "Reasoning base") for m in same[:2])
            gi = fams.index("Reasoning base")
            top = max(wilson(*m["res"]["family"]["Reasoning base"])[1] for m in models)
            txt = "flat with\nscale" if abs(a - b) < 3 else f"{a:.0f}→{b:.0f}%"
            axa.text(gi, top + 4, txt, fontsize=4.6, style="italic", color=INK, ha="center", va="bottom", linespacing=1.0)

    out = os.path.join(ROOT, cfg["out"])
    fig.savefig(out + ".pdf", dpi=600); fig.savefig(out + ".png", dpi=600)
    print("wrote", out)
    for m in models:
        r = m["res"]
        print(f"  {m['label']:12s} {m.get('note', ''):12s} task judge {100 * r['task_judge']:.1f}%  "
              + "  ".join(f"{f[:8]} {100 * rate(m, 'family', f):.0f}" for f in fams))


if __name__ == "__main__":
    main()
