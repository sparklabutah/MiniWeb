"""RQ2, single column: per-skill-family success before and after MiniWeb training, on single-primitive tasks on
held-out sites. (Panel (b), primitives inside the multi-step tasks, was dropped 2026-10-04: too few instances per family.)

Arms and their runs are set in rq2_config.yaml. Both panels are graded by the task verifiers; (b) uses the verifier's
verdict per primitive. Counts pool the seeds of an arm.

    python docs/figures/rq2/make_rq2.py [--config docs/figures/rq2/rq2_config.yaml]
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
from results import ROOT, task_rates, family_counts, instance_family_counts, primitive_filter  # noqa: E402
sys.path.insert(0, ROOT)
from datagen.viewer import FAMILY_OF  # noqa: E402

from style import INK, MUTED, GRID, FAM, FS, rc, header, panel, swatch, bar as sbar, style_axes as sstyle, save  # noqa: E402
rc()
LABEL = {"Drag & gesture": "Drag", "Discrete selection": "Select", "Text entry": "Text",   # as in Tab. 2's header
         "Form transaction": "Form", "Navigation": "Nav.", "Out-of-page I/O": "I/O", "Reasoning base": "Reason",
         "All": "All"}


def bar(ax, x, h, w, arm):
    sbar(ax, x, h, w, arm["color"], hatched=arm.get("style") == "hatched")


def style_axes(ax, ymax=100):
    sstyle(ax)
    ax.set_ylim(0, ymax)
    ax.set_yticks([0, 25, 50, 75, 100]); ax.set_yticklabels(["0", "25", "50", "75", "100%"])
    ax.set_xticks([])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=os.path.join(HERE, "rq2_config.yaml"))
    cfg = yaml.safe_load(open(ap.parse_args().config))
    arms, sets = cfg["arms"], cfg["task_sets"]
    for a in arms:
        a["rates"] = {k: task_rates("miniweb", a.get(k) or [], only=primitive_filter(sets[k].get("primitives")))
                      for k in sets}
    by = {a["label"]: a for a in arms}
    fa = [by[l] for l in cfg["family_arms"]]
    for a in fa:
        a["fam"] = family_counts(a.get(cfg["family_set"]) or [], FAMILY_OF,
                                 only=primitive_filter(sets[cfg["family_set"]].get("primitives")))
    fams = sorted((f for f in fa[0]["fam"] if f in FAM), key=lambda f: fa[0]["fam"][f][0] / fa[0]["fam"][f][1])
    iset = cfg["instance_set"]
    for a in arms:
        a["inst"] = instance_family_counts(a.get(iset) or [], dict(FAMILY_OF, report_information="Reasoning base"),
                                           only=primitive_filter(cfg.get("instance_primitives")))

    top, ph = cfg.get("top", 0.24 + 0.26 + 0.2), cfg.get("plot_height", 1.2)   # plot area under header + legend (in)
    W, H = 3.25, top + ph + cfg.get("bottom", 0.3)      # top/plot_height/bottom: to pair it with another panel
    fig = plt.figure(figsize=(W, H))
    A = fig.add_axes([0, 0, 1, 1]); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
    ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H])

    # the diagrams' header, then the legend in a light panel
    header(fig, A, 0.04, 0.1, cfg.get("title", "Practice"), cfg.get("subtitle", cfg["model"] + ", single primitives, held-out sites"))
    panel(A, 0.04, 0.22, W - 0.08, 0.26)
    for i, a in enumerate(fa):
        x = 0.14 + i * 1.55
        swatch(A, x, 0.35, a["color"], hatched=a.get("style") == "hatched")
        A.text(x + 0.21, 0.35, a["label"], fontsize=FS["legend"], color=INK, va="center",
               weight="bold" if i == len(fa) - 1 else "normal")

    # per family
    ax = ax_at(0.42, top, W - 0.45, ph)
    bw = 0.38
    for gi, f in enumerate(fams):
        vals = []
        for j, a in enumerate(fa):
            k, n = a["fam"].get(f, [0, 1])
            v = 100 * k / n
            vals.append(v)
            bar(ax, gi + (j - 0.5) * bw, v, bw * 0.9, a)
        d = vals[-1] - vals[0]
        ax.text(gi + 0.5 * bw, vals[-1] + 2.5, f"{d:+.0f}", fontsize=FS["value"], weight="bold", ha="center",
                va="bottom", color=fa[-1]["color"] if d >= 3 else MUTED)
        ax.text(gi, -5, LABEL[f], fontsize=FS["label"], weight="bold", color=FAM[f], ha="center", va="top",
                linespacing=1.0, clip_on=False)
    ax.set_xlim(-0.55, len(fams) - 0.45)
    style_axes(ax)
    A.text(0.08, top + ph / 2, "success", fontsize=FS["label"], color=MUTED, rotation=90, ha="center", va="center")

    out = os.path.join(ROOT, cfg["out"])
    save(fig, out)                                        # style.save: trims the heading strip
    print("wrote", out)
    for a in arms:
        print(f"  {a['label']:36s}", {k: [round(x, 1) for x in v] for k, v in a["rates"].items()})


if __name__ == "__main__":
    main()
