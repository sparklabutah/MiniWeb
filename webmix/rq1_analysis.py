"""RQ1 skill profile (2026-10-02): per-family and per-reasoning-op pass rates of each model on the 376 MiniWeb tasks,
from the flash macro judge's per-instance verdicts (data/webmix/eval/<run>/judge.jsonl, webmix.judge_runs), with the
task-level judge and verifier success rates. Writes docs/figures/rq1/rq1_skill_profile.{pdf,png} (Fig. 1) and
data/webmix/eval/rq1_skill_profile.json.

    python -m webmix.rq1_analysis
"""
import collections
import json
import math
from pathlib import Path

from datagen.viewer import FAMILIES
from evaluation import macro_judge as MJ

# Fara1.5-4B weights in our harness (rq1_fara15_4b_ourharness_all, 28.5%) left out (user 2026-10-03): our action format caps
# it (mostly invalid-JSON actions), so it measures the format, not the model; Fara1.5 is reported as released.
# 2026-10-03: more small (<10B) models as they finish (user: "benchmark more models on MiniWeb", "only small under 10B")
RUNS = {"Qwen3.5-4B": "rq1_qwen35_4b_all", "Qwen3.5-9B": "rq1_qwen35_9b_all", "Fara1.5-4B": "rq1_fara15_4b_all",
        "Qwen3-VL-8B": "rq1_qwen3vl-8b_all", "InternVL3.5-8B": "rq1_internvl35-8b_all",
        "MolmoWeb-4B": "rq1_molmoweb-4b_all", "UI-TARS-1.5-7B": "rq1_uitars15-7b_all",
        "Fara-7B": "rq1_fara-7b_all", "OpenCUA-7B": "rq1_opencua-7b_all",
        "MolmoWeb-8B": "rq1_molmoweb-8b_all"}
EVAL, FIG = Path("data/webmix/eval"), Path("docs/figures/rq1")
FAM = {m: f for f, ms in FAMILIES.items() for m in ms}
FAM_ORDER = ["Navigation", "Text entry", "Discrete selection", "Form transaction", "Drag & gesture", "Out-of-page I/O",
             "Reasoning base"]


def wilson(k, n, z=1.96):
    if not n:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def collect():
    out = {}
    for label, run in RUNS.items():
        fam, op, task_j, task_v, n = (collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0]),
                                      0, 0, 0)
        for line in (EVAL / run / "judge.jsonl").read_text().splitlines():
            if not line.strip():
                continue
            r = json.loads(line)
            n += 1
            task_j += bool(r.get("passed"))
            task_v += bool(r.get("verifier"))
            _d, task, _v = MJ._load(r["key"])
            ops = task.get("macro_operations") or {}
            for inst, v in (r.get("instances") or {}).items():
                f = "Reasoning base" if v["macro"] == "report_information" else FAM.get(v["macro"], "Other")
                fam[f][0] += bool(v["passed"]); fam[f][1] += 1
                if ops.get(inst):
                    op[ops[inst]][0] += bool(v["passed"]); op[ops[inst]][1] += 1
        out[label] = {"episodes": n, "task_judge": task_j / max(n, 1), "task_verifier": task_v / max(n, 1),
                      "family": {k: v for k, v in fam.items()}, "op": {k: v for k, v in op.items()}}
    return out


def plot(res):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    labels = list(res)
    colors = ["#2B5C9E", "#14213D", "#B8860B", "#7A9E7E", "#9E4B5C", "#6B5B95", "#C27C3E", "#4A8C9E", "#8C8C8C", "#B5A642"]
    fams = [f for f in FAM_ORDER if any(f in res[m]["family"] for m in labels)]
    ops = sorted({o for m in labels for o in res[m]["op"]}, key=lambda o: -sum(res[m]["op"].get(o, [0, 0])[1] for m in labels))
    fig, axes = plt.subplots(1, 2, figsize=(11, 3.6), gridspec_kw={"width_ratios": [len(fams), max(len(ops), 1)]})
    for ax, keys, field, title in ((axes[0], fams, "family", "Skill family"), (axes[1], ops, "op", "Reasoning operation")):
        w = 0.8 / len(labels)
        for i, m in enumerate(labels):
            ks, ns = zip(*[res[m][field].get(k, [0, 0]) for k in keys]) if keys else ((), ())
            vals = [100 * a / b if b else 0 for a, b in zip(ks, ns)]
            lo_hi = [wilson(a, b) for a, b in zip(ks, ns)]
            err = [[100 * (v / 100 - lo) for v, (lo, _h) in zip(vals, lo_hi)], [100 * (hi - v / 100) for v, (_l, hi) in zip(vals, lo_hi)]]
            ax.bar([x + (i - (len(labels) - 1) / 2) * w for x in range(len(keys))], vals, w, yerr=err, color=colors[i],
                   label=m, error_kw={"elinewidth": 0.6, "capsize": 1.5})
        n0 = [res[labels[0]][field].get(k, [0, 0])[1] for k in keys]
        ax.set_xticks(range(len(keys)))
        short = {"Discrete selection": "Discrete\nselection", "Form transaction": "Form\ntransaction", "Drag & gesture": "Drag &\ngesture",
                 "Out-of-page I/O": "Out-of-page\nI/O", "Text entry": "Text\nentry", "Reasoning base": "Reasoning"}
        ax.set_xticklabels([f"{short.get(k, k)}\n(n={n})" for k, n in zip(keys, n0)], fontsize=7.5)
        ax.set_ylim(0, 100); ax.set_ylabel("instances passed (%)", fontsize=8); ax.set_title(title, fontsize=9)
        ax.grid(axis="y", color="#E6E9EE", lw=0.6); ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axes[0].legend(fontsize=7, frameon=False, ncol=2, loc="upper left")
    fig.tight_layout()
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / "rq1_skill_profile.pdf"); fig.savefig(FIG / "rq1_skill_profile.png", dpi=200)


def main():
    res = collect()
    (EVAL / "rq1_skill_profile.json").write_text(json.dumps(res, indent=1))
    for m, r in res.items():
        print(f"{m:26s} episodes {r['episodes']}  task success: judge {100*r['task_judge']:.1f}%  verifier {100*r['task_verifier']:.1f}%")
    labels = list(res)
    print("\nfamily (judge, instances passed)" + "".join(f" | {m[:14]:>14s}" for m in labels))
    for f in FAM_ORDER:
        if f in res[labels[0]]["family"]:
            print(f"  {f:24s} n={res[labels[0]]['family'][f][1]:3d}" + "".join(
                f" | {100*res[m]['family'].get(f,[0,1])[0]/max(res[m]['family'].get(f,[0,1])[1],1):13.0f}%" for m in labels))
    print("\nreasoning op" + "".join(f" | {m[:14]:>14s}" for m in labels))
    for o in sorted(res[labels[0]]["op"], key=lambda o: -res[labels[0]]["op"][o][1]):
        print(f"  {o:24s} n={res[labels[0]]['op'][o][1]:3d}" + "".join(
            f" | {100*res[m]['op'].get(o,[0,1])[0]/max(res[m]['op'].get(o,[0,1])[1],1):13.0f}%" for m in labels))
    plot(res)
    print(f"\nfigure -> {FIG / 'rq1_skill_profile.pdf'}")


if __name__ == "__main__":
    main()
