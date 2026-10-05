"""Review round 1 (2026-10-05): every number the reviewers asked for that needs no training or re-running, from the
paper's own runs (run lists of docs/figures/tables/tables_config.yaml + the extra arms below).

Reporting rule (user, 2026-10-05, round 2): MiniWeb and WebArena-Lite = mean over three runs (per-task means for the
tests); the live web = one run. WebArena-Lite seed 1 alone is kept alongside for reference. Tests: paired permutation
over tasks (MiniWeb, WebArena-Lite), exact McNemar (live web); Holm correction over the main-text family.

    python docs/figures/review/round1_numbers.py      -> prints everything, writes round1_numbers.json next to this file
"""
import ast, collections, glob, json, os, statistics as st, sys
import yaml

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "tables"))
from results import ROOT, task_outcomes, primitive_filter, _records, human_tasks  # noqa: E402
from paper_stats import permutation, mcnemar, no_reddit_gitlab  # noqa: E402
sys.path.insert(0, ROOT)
from datagen.viewer import FAMILY_OF  # noqa: E402

CFG = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "tables", "tables_config.yaml")))
BENCH, RUNS = CFG["benchmarks"], dict(CFG["runs"])
E, WA, G = "data/webmix/eval", "data/webmix/wa/seeds", "data/webmix/om2w/runs/granite"
RUNS["insta"] = {"heldout": [f"{E}/pagent_insta_s1", f"{E}/pagent_insta_s2", f"{E}/pagent_insta_s3"],
                 "wa": [f"{WA}/agent_insta_s1", f"{WA}/agent_insta_s2", f"{WA}/agent_insta_s3"],
                 "wv": [f"{G}/webvoyager100_agent_insta_wvjudge"], "om2w": [f"{G}/om2w100_agent_insta_webjudge"]}
RUNS["pooled7k"] = {"heldout": [f"{E}/pagent_7k_s1", f"{E}/pagent_7k_s2", f"{E}/pagent_7k_s3"]}
RUNS["base9b"] = {"heldout": [f"{E}/seeds/base9b_s2", f"{E}/seeds/base9b_s3"]}
RUNS["planner9b"] = {"heldout": [f"{E}/seeds/pagent9b_base_s1", f"{E}/seeds/pagent9b_base_s2", f"{E}/seeds/pagent9b_base_s3"]}
ARMS = {"base": "single, untrained", "pooled": "single, trained", "planner": "planner, untrained",
        "planner_pooled": "MiniWebAgent", "insta": "planner + InSTA executor", "agent": "planner + family specialists",
        "pooled7k": "planner + 7K executor", "base9b": "Qwen3.5-9B single, untrained", "planner9b": "Qwen3.5-9B planner, untrained",
        "fara": "Fara1.5-4B in our harness"}
OUT = {}


def outcomes(bench, run):
    b = BENCH[bench]
    return task_outcomes(b["kind"], run, b.get("tasks"), primitive_filter(b.get("primitives")))


def per_task(bench, runs, flt=None):
    outs = [outcomes(bench, r) for r in runs]
    ids = set.intersection(*(set(o) for o in outs))
    if flt:
        ids = {i for i in ids if flt(i)}
    return {i: st.mean(o[i] for o in outs) for i in ids}


def rate(o):
    return 100 * st.mean(o.values()) if o else None


def runs_for(arm, bench, seed1_only):
    rl = (RUNS.get(arm) or {}).get(bench) or []
    if seed1_only:
        rl = rl[:1]
    return rl


# ── 1. canonical table ────────────────────────────────────────────────────────
def canonical():
    rows = {}
    for arm in ARMS:
        r = {}
        for bench in ("single", "heldout", "wa", "wv", "om2w"):
            rl = (RUNS.get(arm) or {}).get(bench) or []
            if not rl:
                continue
            per = [rate(outcomes(bench, x)) for x in rl]
            r[bench] = {"runs": [round(v, 1) for v in per], "mean": round(st.mean(per), 1),
                        "se": round(st.stdev(per) / len(per) ** 0.5, 1) if len(per) > 1 else None,
                        "seed1": round(per[0], 1)}
        rows[arm] = r
    OUT["canonical"] = rows
    print("\n== 1. canonical numbers (MiniWeb: mean of 3 runs; WA: seed 1 [3-run mean ± SE]; live: one run)")
    print(f"{'arm':34s} {'single':>14s} {'held-out':>18s} {'WA s1 [mean±SE]':>22s} {'WV':>6s} {'OM2W':>6s}")
    for arm, r in rows.items():
        f = lambda b: (f"{r[b]['mean']:.1f}±{r[b]['se'] or 0:.1f}" if b in r else "--")  # noqa: E731
        wa = f"{r['wa']['seed1']:.1f} [{r['wa']['mean']:.1f}±{r['wa']['se'] or 0:.1f}]" if "wa" in r else "--"
        print(f"{ARMS[arm]:34s} {f('single'):>14s} {f('heldout'):>18s} {wa:>22s} "
              f"{(r['wv']['seed1'] if 'wv' in r else float('nan')):6.1f} {(r['om2w']['seed1'] if 'om2w' in r else float('nan')):6.1f}")


# ── 2. tests (as reported in the main text) ────────────────────────────────────
TESTS = [  # (bench, A, B, label); B against A
    ("single", "base", "pooled", "practice: single primitives"),
    ("heldout", "base", "pooled", "practice: held-out tasks"),
    ("wa", "base", "pooled", "practice: WA"), ("wv", "base", "pooled", "practice: WV"), ("om2w", "base", "pooled", "practice: OM2W"),
    ("heldout", "base", "planner", "planning: held-out"), ("wa", "base", "planner", "planning: WA"),
    ("wv", "base", "planner", "planning: WV"), ("om2w", "base", "planner", "planning: OM2W"),
    ("heldout", "planner", "planner_pooled", "trained executor: held-out"), ("wa", "planner", "planner_pooled", "trained executor: WA"),
    ("wv", "planner", "planner_pooled", "trained executor: WV"), ("om2w", "planner", "planner_pooled", "trained executor: OM2W"),
    ("heldout", "base", "planner_pooled", "MiniWebAgent vs single: held-out"), ("wa", "base", "planner_pooled", "MiniWebAgent vs single: WA"),
    ("wv", "base", "planner_pooled", "MiniWebAgent vs single: WV"), ("om2w", "base", "planner_pooled", "MiniWebAgent vs single: OM2W"),
    ("heldout", "planner", "insta", "InSTA executor: held-out"), ("wa", "planner", "insta", "InSTA executor: WA"),
    ("wv", "planner", "insta", "InSTA executor: WV"), ("om2w", "planner", "insta", "InSTA executor: OM2W"),
    ("heldout", "insta", "planner_pooled", "ours vs InSTA: held-out"), ("wa", "insta", "planner_pooled", "ours vs InSTA: WA"),
    ("wv", "insta", "planner_pooled", "ours vs InSTA: WV"), ("om2w", "insta", "planner_pooled", "ours vs InSTA: OM2W"),
    ("heldout", "planner_pooled", "agent", "specialists vs pooled: held-out"), ("wa", "planner_pooled", "agent", "specialists vs pooled: WA"),
    ("wv", "planner_pooled", "agent", "specialists vs pooled: WV"), ("om2w", "planner_pooled", "agent", "specialists vs pooled: OM2W"),
    ("heldout", "planner_pooled", "pooled7k", "7K vs 3.1K executor: held-out"),
    ("single", "pooled", "planner_pooled", "MiniWebAgent vs trained single: single primitives"),
]


def holm(ps):
    order = sorted(range(len(ps)), key=lambda i: ps[i])
    adj, run = [0.0] * len(ps), 0.0
    for k, i in enumerate(order):
        run = max(run, min(1.0, (len(ps) - k) * ps[i]))
        adj[i] = run
    return adj


def tests():
    res = []
    for bench, a, b, label in TESTS:
        for mode in ("main", "seed1"):
            if mode == "seed1" and bench != "wa":
                continue
            ra, rb = runs_for(a, bench, mode == "seed1"), runs_for(b, bench, mode == "seed1")
            if not ra or not rb:
                continue
            pa, pb = per_task(bench, ra), per_task(bench, rb)
            if bench in ("wv", "om2w"):
                n, ma, mb, p, up, down = mcnemar(pa, pb)
                extra = f"+{up}/-{down}"
            else:
                n, ma, mb, p = permutation(pa, pb, n=20000)
                extra = ""
            res.append({"label": label + (" (seed 1)" if mode == "seed1" else ""), "bench": bench, "a": a, "b": b, "n": n,
                        "A": round(ma, 1), "B": round(mb, 1), "diff": round(mb - ma, 1), "p": p, "mode": mode, "extra": extra})
    main = [r for r in res if r["mode"] == "main"]
    for r, q in zip(main, holm([r["p"] for r in main])):
        r["p_holm"] = q
    OUT["tests"] = res
    print("\n== 2. tests (main = as the paper reports: MiniWeb + WA 3-run per-task means, live one run; Holm over main)")
    for r in res:
        print(f"  {r['label']:52s} n={r['n']:4d} {r['A']:5.1f} -> {r['B']:5.1f} ({r['diff']:+5.1f})  p={r['p']:.2g}"
              f"{'  holm=' + format(r['p_holm'], '.2g') if 'p_holm' in r else ''} {r['extra']}")


# ── 3. per-family primitive pass rates inside the held-out human tasks ─────────
def family_inside():
    fams = ["Navigation", "Text entry", "Discrete selection", "Form transaction", "Out-of-page I/O", "Drag & gesture",
            "Reasoning base"]
    out = {}
    for arm in ("base", "pooled", "planner", "planner_pooled", "insta", "agent"):
        c = collections.defaultdict(lambda: [0, 0])
        for run in RUNS[arm]["heldout"]:
            for r in _records(run).values():
                try:
                    d = ast.literal_eval(r.get("detail") or "")
                except (ValueError, SyntaxError):
                    continue
                if not isinstance(d, dict):
                    continue
                for m, ok in d.items():
                    for f in (FAMILY_OF.get(m, "Other"), "All"):
                        c[f][0] += bool(ok)
                        c[f][1] += 1
        out[arm] = {f: (round(100 * c[f][0] / c[f][1], 1), c[f][1] // 3) for f in fams + ["All"] if c[f][1]}
    OUT["family_inside_heldout"] = out
    print("\n== 3. primitive instances passed inside the 63 held-out human tasks (%, 3 runs; n instances per run)")
    print(f"{'arm':30s} " + " ".join(f"{f[:8]:>9s}" for f in fams + ['All']))
    for arm, d in out.items():
        print(f"{ARMS[arm]:30s} " + " ".join(f"{d.get(f, ('-', 0))[0]:>9}" for f in fams + ['All']))
    print(f"{'n per run':30s} " + " ".join(f"{out['base'].get(f, ('-', 0))[1]:>9}" for f in fams + ['All']))


# ── 4. failure modes of the trained single agent ───────────────────────────────
def failure_modes():
    out = {}
    for arm in ("base", "pooled"):
        for bench in ("heldout", "wa"):
            rl = RUNS[arm][bench][:1]
            rs = list(_records(rl[0]).values())
            ok = (lambda r: r.get("ok")) if bench == "heldout" else (lambda r: float(r.get("score", 0)) > 0)
            fails = [r for r in rs if not ok(r)]
            prem = [r for r in fails if r.get("done")]
            steps = sorted(r.get("steps") or 0 for r in rs)
            out[f"{arm}/{bench}"] = {"episodes": len(rs), "median_steps": steps[len(steps) // 2],
                                     "fail_with_done_pct": round(100 * len(prem) / max(1, len(fails)), 1),
                                     "at_cap_40_pct": round(100 * sum(s >= 40 for s in steps) / len(steps), 1)}
        for bench, d in (("wv", "webvoyager100"), ("om2w", "om2w100")):
            name = {"base": "base", "pooled": "single_pooled"}[arm]
            dirs = [x for x in glob.glob(os.path.join(ROOT, G, f"{d}_{name}", "*/")) if not os.path.basename(x.rstrip('/')).startswith('_')]
            steps = []
            for x in dirs:
                h = os.path.join(x, "history_0.json")
                if os.path.exists(h):
                    steps.append(len(json.load(open(h)).get("history") or []))
            steps.sort()
            if steps:
                out[f"{arm}/{bench}"] = {"episodes": len(steps), "median_steps": steps[len(steps) // 2],
                                         "at_cap_40_pct": round(100 * sum(s >= 40 for s in steps) / len(steps), 1),
                                         "at_cap_100_pct": round(100 * sum(s >= 100 for s in steps) / len(steps), 1),
                                         "max_steps": steps[-1]}
    OUT["failure_modes"] = out
    print("\n== 4. single agent, untrained vs trained: episode length and how failures end")
    for k, v in out.items():
        print(f"  {k:16s} {v}")


# ── 5. WebArena-Lite per site ──────────────────────────────────────────────────
def wa_domains():
    out = {}
    for arm in ("base", "pooled", "planner", "planner_pooled", "insta"):
        for mode, rl in (("seed1", RUNS[arm]["wa"][:1]), ("3run", RUNS[arm]["wa"])):
            c = collections.defaultdict(list)
            for run in rl:
                for r in _records(run).values():
                    key = "+".join(sorted(r.get("sites") or ["?"]))
                    c[key].append(float(r["score"]))
                    c["ALL"].append(float(r["score"]))
                    if not ({"reddit", "gitlab"} & set(r.get("sites") or [])):
                        c["no reddit/gitlab"].append(float(r["score"]))
            out[f"{arm}/{mode}"] = {k: (round(100 * st.mean(v), 1), len(v) // len(rl)) for k, v in sorted(c.items())}
    OUT["wa_domains"] = out
    print("\n== 5. WebArena-Lite success by site (seed 1 | 3-run mean; n tasks)")
    keys = sorted({k for v in out.values() for k in v})
    for k in keys:
        cells = " ".join(f"{out[f'{a}/seed1'].get(k, ('-', 0))[0]:>6} |{out[f'{a}/3run'].get(k, ('-', 0))[0]:>5}"
                         for a in ("base", "pooled", "planner", "planner_pooled", "insta"))
        print(f"  {k:22s} n={out['base/seed1'].get(k, ('-', 0))[1]:>3}  {cells}")
    print("  columns: single untrained, single trained, planner untrained, MiniWebAgent, InSTA executor")
    for a, b in (("base", "planner_pooled"), ("planner", "planner_pooled")):
        flt = no_reddit_gitlab(RUNS[a]["wa"][0])
        for mode in ("seed1", "3run"):
            ra, rb = (RUNS[a]["wa"][:1], RUNS[b]["wa"][:1]) if mode == "seed1" else (RUNS[a]["wa"], RUNS[b]["wa"])
            n, ma, mb, p = permutation(per_task("wa", ra, flt), per_task("wa", rb, flt), n=20000)
            print(f"  without Reddit/GitLab, {a} -> {b} ({mode}): n={n} {ma:.1f} -> {mb:.1f} ({mb - ma:+.1f}) p={p:.2g}")
            OUT.setdefault("wa_no_reddit_gitlab", []).append({"a": a, "b": b, "mode": mode, "n": n, "A": round(ma, 1),
                                                              "B": round(mb, 1), "diff": round(mb - ma, 1), "p": p})


# ── 6. Table 2 conditional on the upstream primitives passing ──────────────────
def conditional_profiles():
    rq1 = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "rq1", "rq1_config.yaml")))
    fams = ["Navigation", "Text entry", "Discrete selection", "Form transaction", "Out-of-page I/O", "Drag & gesture",
            "Reasoning base"]
    out = {}
    for m in rq1["models"]:
        unc, con = collections.defaultdict(lambda: [0, 0]), collections.defaultdict(lambda: [0, 0])
        for line in open(os.path.join(ROOT, m["judge"])):
            if not line.strip():
                continue
            inst = list((json.loads(line).get("instances") or {}).values())
            upstream_ok = True
            for v in inst:
                f = FAMILY_OF.get(v["macro"], "Other")
                unc[f][0] += bool(v["passed"]); unc[f][1] += 1
                if upstream_ok:
                    con[f][0] += bool(v["passed"]); con[f][1] += 1
                upstream_ok = upstream_ok and bool(v["passed"])
        out[m["label"]] = {f: {"all": round(100 * unc[f][0] / unc[f][1]) if unc[f][1] else None,
                               "after_ok": round(100 * con[f][0] / con[f][1]) if con[f][1] else None,
                               "n_after_ok": con[f][1]} for f in fams}
    OUT["conditional_profiles"] = out
    print("\n== 6. per-family pass rate, all instances vs instances whose earlier primitives all passed (judge)")
    print(f"{'agent':16s} " + " ".join(f"{f[:8]:>13s}" for f in fams))
    for a, d in out.items():
        print(f"{a:16s} " + " ".join(f"{str(d[f]['all']):>5}/{str(d[f]['after_ok']):>3}({d[f]['n_after_ok']:>3})" for f in fams))
    weakest = {a: min(fams, key=lambda f: d[f]["after_ok"] if d[f]["after_ok"] is not None else 999) for a, d in out.items()}
    print("  weakest family conditional on upstream success:", collections.Counter(weakest.values()))


# ── 7. p^n ─────────────────────────────────────────────────────────────────────
def compounding():
    mean = [60.6, 37.3, 21.1, 12.1, 4.4]          # Fig. 6 left (chain/make_chain.py), printed there
    indep = [60.6, 36.7, 22.2, 13.4, 7.1]
    dev = [round(a - b, 1) for a, b in zip(mean, indep)]
    OUT["pn"] = {"mean": mean, "indep": indep, "dev": dev, "max_abs_dev": max(abs(x) for x in dev)}
    print("\n== 7. observed mean vs p^n by chain length 1..5+:", mean, indep, "dev", dev)


# ── 8. drag & gesture training data: does it drag? ─────────────────────────────
def drag_modality():
    ids = set(open(os.path.join(ROOT, "data", "webmix", "review_round1", "v4set_plain_ids.txt")).read().split())
    c = collections.defaultdict(collections.Counter)
    for tid in ids:
        hits = glob.glob(os.path.join(ROOT, "data", "datagen", "runs", "*", "accepted", tid, "trajectory.json"))
        if not hits:
            continue
        t = json.load(open(hits[0]))
        if FAMILY_OF.get(t.get("macro")) != "Drag & gesture":
            continue
        types = collections.Counter(s["action"]["type"] for s in t.get("steps") or [])
        kind = ("drag/draw" if (types.get("drag") or types.get("draw") or types.get("mouse_drag")) else
                "keyboard" if (types.get("press") or types.get("key") or types.get("keypress")) else
                "typed" if types.get("type") or types.get("input") else "click only")
        c[t["macro"]][kind] += 1
        c[t["macro"]]["_types"] += 0
        c["_all_types"].update(types)
    OUT["drag_modality"] = {k: dict(v) for k, v in c.items()}
    print("\n== 8. drag & gesture trajectories in the 3.1K set, by how the gesture was done")
    for k, v in c.items():
        print(f"  {k:28s} {dict(v)}")


# ── 9. planner turn cap and the shared step budget ─────────────────────────────
def planner_caps():
    out = {}
    for name, rl in (("heldout", RUNS["planner_pooled"]["heldout"]), ("wa", RUNS["planner_pooled"]["wa"][:1]),
                     ("wv", [f"{G}/webvoyager100_agent_pooled31k"]), ("om2w", [f"{G}/om2w100_agent_pooled31k"])):
        turns, nleft = [], 0
        for run in rl:
            for d in glob.glob(os.path.join(ROOT, run, "*/")):
                p = os.path.join(d, "planner_history.json")
                if not os.path.exists(p):
                    continue
                h = json.load(open(p)).get("history") or []
                turns.append(len(h))
                nleft += any("specialist steps left: 0" in json.dumps(s.get("result")) for s in h)
        turns.sort()
        if turns:
            cap = 25 if name in ("heldout", "wa") else 60
            out[name] = {"episodes": len(turns), "median_turns": turns[len(turns) // 2], "turn_cap": cap,
                         "at_turn_cap_pct": round(100 * sum(t >= cap for t in turns) / len(turns), 1),
                         "budget_exhausted_pct": round(100 * nleft / len(turns), 1)}
    OUT["planner_caps"] = out
    print("\n== 9. MiniWebAgent planner turns and budget exhaustion")
    for k, v in out.items():
        print(f"  {k:8s} {v}")


# ── 10. held-out tasks that touch a training site ──────────────────────────────
def heldout_overlap():
    split = json.load(open(os.path.join(ROOT, "data", "datagen", "site_split.json")))
    held = set(split.get("heldout") or split.get("held_out") or split.get("test") or [])
    hs = [t for t in human_tasks() if t["site"] in held or set(t.get("sites") or []) & held]
    touch = [t for t in hs if set(t.get("sites") or [t["site"]]) - held]
    OUT["heldout_overlap"] = {"heldout_tasks": len(hs), "touch_training_site": len(touch),
                              "examples": sorted({s for t in touch for s in (set(t.get("sites") or []) - held)})}
    print(f"\n== 10. held-out tasks: {len(hs)}; also using a training site: {len(touch)} ({OUT['heldout_overlap']['examples']})")


def fara_heldout():
    """Fara1.5-4B (own loop, RQ1 run) and the 9B/our-harness Fara runs on the 63 held-out tasks."""
    held_ids = set(_records(RUNS["planner_pooled"]["heldout"][0]))
    out = {}
    for name, path in (("Fara1.5-4B own loop", f"{E}/rq1_fara15_4b_all/judge.jsonl"), ("Qwen3.5-9B", f"{E}/rq1_qwen35_9b_all/judge.jsonl"),
                       ("Qwen3.5-4B", f"{E}/rq1_qwen35_4b_all/judge.jsonl")):
        rs = [json.loads(l) for l in open(os.path.join(ROOT, path)) if l.strip()]
        sub = [r for r in rs if r["task_id"] in held_ids]
        ver = [r.get("verifier") for r in sub if r.get("verifier") is not None]
        out[name] = {"n": len(sub), "judge": round(100 * st.mean(bool(r["passed"]) for r in sub), 1) if sub else None,
                     "verifier": round(100 * st.mean(bool(v) for v in ver), 1) if ver else None}
    OUT["heldout_other_agents"] = out
    print("\n== 11. other agents on the 63 held-out tasks (one RQ1 run each):", out)


if __name__ == "__main__":
    canonical()
    tests()
    family_inside()
    failure_modes()
    wa_domains()
    conditional_profiles()
    compounding()
    drag_modality()
    planner_caps()
    heldout_overlap()
    fara_heldout()
    json.dump(OUT, open(os.path.join(HERE, "round1_numbers.json"), "w"), indent=1, default=str)
    print("\nwrote", os.path.join(HERE, "round1_numbers.json"))
