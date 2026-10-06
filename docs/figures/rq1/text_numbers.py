"""Numbers that Sec. 4.1 quotes in its text, from the same runs as Table 2 (rq1_config.yaml; VLM judge, instances of
well-covered primitives):
  - drag & gesture pooled over the ten agents, with a 95% interval from resampling tasks, against the next-weakest family
  - the six web and computer-use agents against the four general models: mean drag and text-entry pass rates
  - from Qwen3.5-4B to Qwen3.5-9B: the gain of each family
  - Spearman's rho across the ten agents between task success and each family's pass rate
Group means and gains are taken over Table 2's cells as printed (whole percents), so a reader can check them there.

    python docs/figures/rq1/text_numbers.py        # prints them; writes docs/figures/rq1/text_numbers.json
"""
import collections, json, os, random, statistics as st, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "docs", "figures", "common"))
from datagen.viewer import FAMILY_OF  # noqa: E402
from results import judge_rows, primitive_filter  # noqa: E402

N_BOOT, SEED = 1000, 0
DRAG, TEXT = "Drag & gesture", "Text entry"


def family(macro):
    return "Reasoning base" if macro == "report_information" else FAMILY_OF.get(macro, "Other")


def load(cfg):
    """{agent: {task_id: (passed, {family: [passed, total]})}} from each agent's judge.jsonl."""
    only = primitive_filter(cfg.get("primitives"))
    out = {}
    for m in cfg["models"]:
        tasks = {}
        for r in judge_rows(m["judge"]):
            fam = collections.defaultdict(lambda: [0, 0])
            for v in (r.get("instances") or {}).values():
                if only is not None and v["macro"] not in only:
                    continue
                f = fam[family(v["macro"])]
                f[0] += bool(v["passed"])
                f[1] += 1
            tasks[r["task_id"]] = (bool(r.get("passed")), dict(fam))
        out[m["label"]] = tasks
    return out


def rate(tasks, fam, ids=None):
    k = n = 0
    for t in (ids if ids is not None else tasks):
        if t in tasks:
            a, b = tasks[t][1].get(fam, (0, 0))
            k, n = k + a, n + b
    return 100 * k / n if n else float("nan")


def pooled(data, fam, ids):
    k = n = 0
    for tasks in data.values():
        for t in ids:
            if t in tasks:
                a, b = tasks[t][1].get(fam, (0, 0))
                k, n = k + a, n + b
    return 100 * k / n if n else float("nan")


def ranks(xs):
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        for k in range(i, j + 1):
            r[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    ra, rb = ranks(a), ranks(b)
    ma, mb = st.mean(ra), st.mean(rb)
    num = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    den = (sum((x - ma) ** 2 for x in ra) * sum((y - mb) ** 2 for y in rb)) ** 0.5
    return num / den


def main():
    cfg = yaml.safe_load(open(os.path.join(HERE, "rq1_config.yaml")))
    data = load(cfg)
    fams = cfg["table"]["families"]
    ids = sorted(set().union(*data.values()))
    out = {}

    # pooled drag vs the next-weakest family, 95% percentile interval over task resamples
    pool = {f: pooled(data, f, ids) for f in fams}
    nxt = sorted(fams, key=pool.get)[1]
    rng, boot = random.Random(SEED), collections.defaultdict(list)
    for _ in range(N_BOOT):
        smp = [rng.choice(ids) for _ in ids]
        for f in (DRAG, nxt):
            boot[f].append(pooled(data, f, smp))
    ci = {f: (sorted(v)[int(0.025 * N_BOOT)], sorted(v)[int(0.975 * N_BOOT) - 1]) for f, v in boot.items()}
    out["pooled"] = {f: {"rate": pool[f], "ci95": ci.get(f)} for f in (DRAG, nxt)}
    out["pooled"]["next_weakest"] = nxt
    print(f"pooled over the ten agents: drag {pool[DRAG]:.1f}% (95% CI {ci[DRAG][0]:.1f}-{ci[DRAG][1]:.1f}) vs "
          f"{nxt} {pool[nxt]:.1f}% ({ci[nxt][0]:.1f}-{ci[nxt][1]:.1f}); {N_BOOT} task resamples, seed {SEED}")

    # the table's two groups: general models (browser-use harness) vs web and computer-use agents (own loops)
    groups = {g["name"]: g["models"] for g in cfg["table"]["groups"]}
    out["groups"] = {}
    cell = lambda l, f: round(rate(data[l], f))           # Table 2's cell
    for name, labs in groups.items():
        d, t = st.mean(cell(l, DRAG) for l in labs), st.mean(cell(l, TEXT) for l in labs)
        out["groups"][name] = {"n": len(labs), "drag": d, "text": t}
        print(f"{name} ({len(labs)}): drag {d:.1f}%, text entry {t:.1f}% (mean over agents)")

    # Qwen3.5-4B -> 9B
    gain = {f: cell("Qwen3.5-9B", f) - cell("Qwen3.5-4B", f) for f in fams}
    out["gain_4b_to_9b"] = gain
    print("Qwen3.5-4B -> 9B gain (points): " + ", ".join(f"{f} {g:+.0f}" for f, g in gain.items()))

    # Spearman across agents: task success vs each family's pass rate
    labs = list(data)
    succ = [100 * st.mean(p for p, _ in data[l].values()) for l in labs]
    rho = {f: spearman(succ, [rate(data[l], f) for l in labs]) for f in fams}
    out["spearman_task_success"] = rho
    print("Spearman rho (task success vs family, ten agents): " + ", ".join(f"{f} {r:.2f}" for f, r in rho.items()))

    json.dump(out, open(os.path.join(HERE, "text_numbers.json"), "w"), indent=1)


if __name__ == "__main__":
    main()
