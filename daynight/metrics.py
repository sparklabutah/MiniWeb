"""Metrics per day, and the table over days.

    python -m daynight.metrics --config <cfg> [--model mock]      # or --out <experiment dir>

Each day's row (`<out>/day_<t>/metrics.json`, all rows in `<out>/metrics.jsonl`):

    autonomous_success   passed with no intervention (the day t-1 agent on its own)
    assisted_success     passed after one or more messages, no takeover
    takeover_rate        share of episodes the human took over
    interventions        total, and per episode
    per_macro            {macro: {n, passed, pass_rate}} from the verifier's per-macro result
    intent               meta agent vs the interventions' labels (where labels exist): error type, macro, and step
                         within +-2 of the labelled one; n = labelled episodes (RQ1)
    probe                the fixed probe set run by the same agent with no human: success, per_macro (RQ2/RQ3)
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict

from daynight import config as C
from daynight.schema import read_analyses, read_episodes, write_jsonl

STEP_TOLERANCE = 2


def _rate(a, b):
    return round(a / b, 4) if b else None


def per_macro(episodes):
    per = defaultdict(lambda: {"n": 0, "passed": 0})
    for ep in episodes:
        bm = (ep.outcome.by_macro if ep.outcome else {}) or {}
        for m in set(ep.macros):
            per[m]["n"] += 1
            per[m]["passed"] += bool(bm.get(m))
    return {m: {**r, "pass_rate": _rate(r["passed"], r["n"])} for m, r in sorted(per.items())}


def intent_accuracy(episodes, analyses):
    """The meta agent's reading of each episode's first labelled intervention against its label."""
    an = {a.episode_id: a for a in analyses}
    n = typ = mac = stp = 0
    for ep in episodes:
        iv = next((iv for iv in ep.interventions if iv.label), None)
        a = an.get(ep.episode_id)
        if iv is None or a is None:
            continue
        n += 1
        pred = a.intent or a.failure or {}
        typ += pred.get("error_type") == iv.label.error_type
        mac += iv.label.macro is not None and pred.get("macro") == iv.label.macro
        fstep = (a.failure or {}).get("step")
        stp += iv.label.step is not None and isinstance(fstep, int) and abs(fstep - iv.label.step) <= STEP_TOLERANCE
    return {"n": n, "error_type": _rate(typ, n), "macro": _rate(mac, n), "step": _rate(stp, n)}


def day_metrics(day, episodes, analyses=(), probe=()):
    n = len(episodes)
    auto = sum(ep.autonomous for ep in episodes)
    takeover = sum(any(iv.kind == "takeover" for iv in ep.interventions) for ep in episodes)
    assisted = sum(bool(ep.outcome and ep.outcome.passed) and bool(ep.interventions)
                   and not any(iv.kind == "takeover" for iv in ep.interventions) for ep in episodes)
    ivs = sum(len(ep.interventions) for ep in episodes)
    agent = episodes[0].agent if episodes else (probe[0].agent if probe else {})
    row = {"day": day, "agent": agent.get("executor"), "episodes": n,
           "autonomous_success": _rate(auto, n), "assisted_success": _rate(assisted, n),
           "takeover_rate": _rate(takeover, n), "interventions": ivs, "interventions_per_episode": _rate(ivs, n),
           "messages": sum(iv.kind == "message" for ep in episodes for iv in ep.interventions),
           "errors": sum(bool(ep.error) for ep in episodes),
           "per_macro": per_macro(episodes), "intent": intent_accuracy(episodes, analyses)}
    if probe:
        row["probe"] = {"episodes": len(probe), "success": _rate(sum(bool(e.outcome and e.outcome.passed)
                                                                     for e in probe), len(probe)),
                        "per_macro": per_macro(probe)}
    return row


def collect(cfg):
    """Every day's row from what is on disk (days with episodes or a probe)."""
    rows = []
    out = C.out_dir(cfg)
    days = sorted(int(p.name.split("_")[1]) for p in out.glob("day_*") if p.name.split("_")[1].isdigit())
    for t in days:
        d = C.day_dir(cfg, t)
        eps, probe = read_episodes(d / "episodes.jsonl"), read_episodes(d / "probe.jsonl")
        if not eps and not probe:
            continue
        row = day_metrics(t, eps, read_analyses(d / "analysis.jsonl"), probe)
        (d / "metrics.json").write_text(json.dumps(row, indent=1))
        rows.append(row)
    write_jsonl(out / "metrics.jsonl", rows)
    return rows


def _f(x):
    return "   -" if x is None else f"{100 * x:5.1f}"


def table(rows):
    head = "day  executor     n   auto%  assist%  takeov%  iv/ep  intent(type/macro/step)   probe%"
    lines = [head, "-" * len(head)]
    for r in rows:
        it = r["intent"]
        intent = (f"{_f(it['error_type'])}/{_f(it['macro'])}/{_f(it['step'])} (n={it['n']})" if it["n"] else "-")
        pr = r.get("probe", {}).get("success")
        lines.append(f"{r['day']:>3}  {str(r['agent'])[:11]:<11} {r['episodes']:>3}  {_f(r['autonomous_success'])}  "
                     f"{_f(r['assisted_success'])}    {_f(r['takeover_rate'])}   "
                     f"{(r['interventions_per_episode'] or 0):4.2f}  {intent:<25} {_f(pr)}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m daynight.metrics")
    ap.add_argument("--config", default=None)
    ap.add_argument("--out", default=None, help="an experiment dir (instead of --config)")
    ap.add_argument("--model", default=None)
    args = ap.parse_args(argv)
    cfg = C.load(args.config, model=args.model, out=args.out)
    print(table(collect(cfg)))


if __name__ == "__main__":
    main()
