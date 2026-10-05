"""Stage 5 — filter. Keep a trajectory only if BOTH the backend gate (the script's own
assertion, re-checked by the harness) AND the LLM judge pass; then dedup on
(site, target element, argument) and cap per site.

    failure pool  every failed attempt (policy/script error, backend fail, judge fail),
                  with its reason and trajectory dir — DPO negatives, never the bin
    surplus       valid trajectories dropped only by dedup / the per-site cap
"""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor

from datagen import config
from datagen.judge import judge


def failure_reason(rec):
    e = rec.get("error") or ""
    if e.startswith("policy violation"):
        return "policy_violation", e
    if e.startswith("backend check failed"):
        return "backend_fail", e
    if e.startswith("assertion failed"):
        return "script_assert", e
    if e.startswith("action refused"):
        return "action_refused", e
    return ("script_error" if e else "unknown"), e


def kept_keys(exclude_run=None):
    """Dedup keys already kept by earlier runs (and their per-(macro, site) counts)."""
    keys, per_site = set(), {}
    gone = config.retired()
    for p in sorted(config.RUNS_DIR.glob("*/kept.jsonl")):
        if exclude_run and p.parent.name == exclude_run:
            continue
        for line in p.read_text().split("\n"):
            if line.strip():
                r = json.loads(line)
                if gone(p.parent.name, r):
                    continue
                keys.add(tuple(r["dedup_key"]))
                per_site[(r["macro"], r["site"])] = per_site.get((r["macro"], r["site"]), 0) + 1
    return keys, per_site


def run_filter(tasks, executions, run_id, per_site_cap=3, workers=4, log=print, caps=None, use_judge=True):
    """tasks: [task]; executions: {task_id: [attempt records]} -> (kept, surplus, failures, judged).
    use_judge=False: the deterministic backend gate alone decides (the gate's former holes -- rejected
    logins, text that never reached the server, background polling, login bounces -- are closed in
    checks/sampler since 2026-09-29); the verdict row records {"passed": True, "why": "deterministic gate"}."""
    failures, judged_rows = [], []
    to_judge = []
    for t in tasks:
        recs = executions.get(t["task_id"]) or []
        for r in recs:
            if not r["ok"]:
                kind, why = failure_reason(r)
                # backend_ok: the goal state was reached even though the script failed afterwards —
                # such an attempt is NOT a clean negative (filter these out before using it for DPO)
                failures.append({"task_id": t["task_id"], "macro": t["macro"], "site": t["site"], "stage": "execute",
                                 "reason": kind, "detail": why[:500], "attempt": r["attempt"], "dir": r.get("dir"),
                                 "n_actions": len(r.get("steps", [])), "instruction": t["instruction"],
                                 "backend_ok": bool((r.get("backend") or {}).get("ok"))})
        ok = [r for r in recs if r["ok"]]
        if ok:
            to_judge.append((t, ok[-1]))

    def one(item):
        t, r = item
        if not use_judge:
            return t, r, {"passed": True, "why": "deterministic gate only (no LLM judge)", "votes": "gate"}
        return t, r, judge(t, config.ROOT / r["dir"])
    with ThreadPoolExecutor(workers) as pool:
        verdicts = list(pool.map(one, to_judge))

    seen, per_site = kept_keys(exclude_run=run_id)
    kept, surplus = [], []
    for t, r, v in verdicts:
        row = {"task_id": t["task_id"], "macro": t["macro"], "site": t["site"], "dedup_key": t["dedup_key"],
               "attempt": r["attempt"], "dir": r["dir"], "judge": v, "backend": r["backend"]["detail"],
               "start_kind": t["start"]["kind"], "instruction": t["instruction"]}
        judged_rows.append(row)
        if not v["passed"]:
            failures.append({**{k: row[k] for k in ("task_id", "macro", "site", "attempt", "dir", "instruction")},
                             "stage": "judge", "reason": "judge_fail", "detail": v.get("why", ""),
                             "votes": v.get("votes"), "n_actions": len(r.get("steps", []))})
            continue
        key = tuple(t["dedup_key"])
        if key in seen:
            surplus.append({**row, "dropped": "duplicate"})
            continue
        cap = (caps or {}).get(t["macro"]) or {}
        if per_site.get((t["macro"], t["site"]), 0) >= cap.get("site_cap", per_site_cap):
            surplus.append({**row, "dropped": "site_cap"})
            continue
        if cap.get("target") and sum(c for (mm, _s), c in per_site.items() if mm == t["macro"]) >= cap["target"]:
            surplus.append({**row, "dropped": "target"})
            continue
        seen.add(key)
        per_site[(t["macro"], t["site"])] = per_site.get((t["macro"], t["site"]), 0) + 1
        kept.append(row)
    log(f"filter: judged {len(verdicts)}, kept {len(kept)}, surplus {len(surplus)}, failures {len(failures)}")
    return kept, surplus, failures, judged_rows
