"""B3 (review round 1, 2026-10-05): model calls, prompt/output size and wall-clock per episode, per arm and benchmark.

A planner arm's episode = planner_history.json (planner turns) + history_<k>.json (executor steps per delegation);
a single agent's = history.json (or history_0.json). Tokens are not logged, so prompt size is the characters of the
text prompt (state_message; each call also carries one screenshot) and output size the characters of the reply.

    python docs/figures/review/compute_budget.py [--out docs/figures/review/compute_budget.json]
"""
import argparse, glob, json, os, statistics as st

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
D = "data/webmix"
ARMS = {   # arm -> benchmark -> run dirs (the paper's runs; MiniWeb + WA have three runs)
    "single, untrained": {"miniweb": ["eval/human_base"], "wa": ["wa/seeds/base_s1", "wa/seeds/base_s2", "wa/seeds/base_s3"],
                          "wv": ["om2w/runs/granite/webvoyager100_base"], "om2w": ["om2w/runs/granite/om2w100_base"]},
    "single, trained": {"miniweb": ["eval/human_pooled_v4"], "wa": ["wa/seeds/single_pooled_s1", "wa/seeds/single_pooled_s2", "wa/seeds/single_pooled_s3"],
                        "wv": ["om2w/runs/granite/webvoyager100_single_pooled"], "om2w": ["om2w/runs/granite/om2w100_single_pooled"]},
    "planner, untrained": {"miniweb": ["eval/seeds/pagent_v6_baseexec_s1", "eval/seeds/pagent_v6_baseexec_s2", "eval/seeds/pagent_v6_baseexec_s3"],
                           "wa": ["wa/seeds/agent_base_s1", "wa/seeds/agent_base_s2", "wa/seeds/agent_base_s3"],
                           "wv": ["om2w/runs/granite/webvoyager100_agent_planner_base"], "om2w": ["om2w/runs/granite/om2w100_agent_planner_base"]},
    "MiniWebAgent": {"miniweb": ["eval/pagent_pooled_s1"], "wa": ["wa/seeds/agent_pooled31k_s1", "wa/seeds/agent_pooled31k_s2", "wa/seeds/agent_pooled31k_s3"],
                     "wv": ["om2w/runs/granite/webvoyager100_agent_pooled31k"], "om2w": ["om2w/runs/granite/om2w100_agent_pooled31k"]},
}


def hist(p):
    try:
        return json.load(open(p)).get("history") or []
    except (OSError, ValueError):
        return []


def episode(d):
    """-> dict(planner, executor, calls, prompt_chars, output_chars, seconds) or None."""
    ph = hist(os.path.join(d, "planner_history.json")) if os.path.exists(os.path.join(d, "planner_history.json")) else None
    if ph is not None:
        ex = [s for p in sorted(glob.glob(os.path.join(d, "history_*.json"))) for s in hist(p)]
        steps = ph + ex
        planner, executor = len(ph), len(ex)
    else:
        f = next((p for p in (os.path.join(d, "history.json"), os.path.join(d, "history_0.json")) if os.path.exists(p)), None)
        if f is None:
            return None
        steps = hist(f)
        planner, executor = 0, len(steps)
    if not steps:
        return None
    t = [(s.get("metadata") or {}) for s in steps]
    t0 = min((m.get("step_start_time") for m in t if m.get("step_start_time")), default=None)
    t1 = max((m.get("step_end_time") for m in t if m.get("step_end_time")), default=None)
    return dict(planner=planner, executor=executor, calls=planner + executor,
                prompt_chars=sum(len(s.get("state_message") or "") for s in steps),
                output_chars=sum(len(json.dumps(s.get("model_output"))) for s in steps if s.get("model_output")),
                seconds=(t1 - t0) if (t0 and t1) else None)


def summarize(eps, key):
    v = sorted(e[key] for e in eps if e.get(key) is not None)
    if not v:
        return None
    return dict(mean=round(st.mean(v), 1), median=v[len(v) // 2], p95=v[int(0.95 * (len(v) - 1))], max=v[-1])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(ROOT, "docs", "figures", "review", "compute_budget.json"))
    out = {}
    for arm, benches in ARMS.items():
        for b, runs in benches.items():
            eps = []
            for r in runs:
                for d in sorted(glob.glob(os.path.join(ROOT, D, r, "*/"))):
                    if os.path.basename(d.rstrip("/")).startswith("_"):
                        continue
                    e = episode(d)
                    if e:
                        eps.append(e)
            out.setdefault(arm, {})[b] = dict(episodes=len(eps), **{k: summarize(eps, k) for k in
                                              ("calls", "planner", "executor", "prompt_chars", "output_chars", "seconds")})
    json.dump(out, open(ap.parse_args().out, "w"), indent=1)
    print(f"{'arm':20s} {'bench':8s} {'eps':>5s} {'calls mean/med/p95/max':>26s} {'planner':>10s} {'exec':>10s} {'prompt kchar':>13s} {'min':>6s}")
    for arm, bs in out.items():
        for b, s in bs.items():
            c, p, e, pc, sec = s["calls"], s["planner"], s["executor"], s["prompt_chars"], s["seconds"]
            if not c:
                print(f"{arm:20s} {b:8s} {s['episodes']:5d}  (no histories)"); continue
            print(f"{arm:20s} {b:8s} {s['episodes']:5d} {c['mean']:7.1f}/{c['median']:4d}/{c['p95']:4d}/{c['max']:4d}      "
                  f"{p['mean']:6.1f} {e['mean']:10.1f} {pc['mean'] / 1000:13.1f} {(sec['mean'] / 60 if sec else 0):6.1f}")


if __name__ == "__main__":
    main()
