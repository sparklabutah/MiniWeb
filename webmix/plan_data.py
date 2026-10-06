"""Planner training rows by construction (user, 2026-10-06: "lets try to train our planner"; the data made the way
MiniWebGen makes the executor's, for the executor of the paper's MiniWebAgent, pooled_v4; evaluated on the 98-task
WebVoyager sample).

A chain is 2-4 kept single-primitive trajectories of one training site, from the 3.1K executor's own pool, merged into
one request. Its decomposition is known by construction: each part is one delegation (its family and its MiniWebGen
instruction); a part that starts on the site's home page after a part that ended elsewhere is reached by a Navigation
delegation first; the last turn is done, with the answer when the last part answers a question. The real planner Agent
(planner_agent.planner_agent, version v6 as the paper's runs use it) runs each chain with a scripted model: every turn
records the messages the planner sees (browser-use's prompt, the page, the screenshot, the earlier delegations and their
reports) and answers with the known step, its memory written by the base model. The delegate action is the planner's
own (planner_agent.Team.run_step, so each report is worded as in evaluation) with the specialist's model replaced by a
replay of the part's trajectory (replay.Replayer). A chain's rows are kept when every part's own gate passes on the
session and every scripted step ran.

    python -m webmix.plan_data --out data/webmix/planner_rows/v1 --chains 1500 --workers 4 --ports 8320,8321 \\
        --memory-model qwen35-4b [--limit N] [--headful]

Rows: <out>/<chain id>/{rows.jsonl, step_*.png, episode.json}, the format webmix.train reads; every chain's result is
appended to <out>/results.jsonl (chains already there are skipped). Failed chains go to <out>/_failed (never trained on).
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import re
import shutil
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

from datagen import browser as B
from datagen.viewer import FAMILY_OF, _kept_rows
from datagen import config
from webmix import augment as A
from webmix import harness as H
from webmix import planner_agent as PA
from webmix import replay as R

ROOT = Path(__file__).resolve().parent.parent
POOL = ROOT / "experiments" / "pools" / "pool3k_plain_ids.txt"    # the 3.1K executor's kept trajectories
VERSION = "v6"                                                     # the planner version of the paper's runs
EXECUTOR = "pooled_v4"                                             # its executor, as the reports name it
HOME_STEP = "Go to the home page of {site} with the site's own home link."
QA_MACROS = {"report_information", "count_entries"}               # answer-only macros the executor pool leaves out
# parts whose check reads the last page's query string: a trip home after them undoes them (2026-10-06 smoke test)
URL_STATE = {"filter_by_dropdown", "filter_by_options", "filter_by_slider", "filter_by_date_range", "sort_by_form"}


# ── chains ────────────────────────────────────────────────────────────────────

def _record(tid, d):
    traj = json.loads((d / "trajectory.json").read_text())
    task = R.load_task(d.parent.parent.name, tid)
    if task["start"].get("kind") == "mid_chain" or traj.get("history_macro"):
        return None
    start = A._path(task["start"]["url"])
    ctrl = task["control"]
    return {"id": tid, "dir": d, "traj": traj, "task": task, "site": traj["site"], "macro": traj["macro"],
            "start": start, "control": ctrl.get("control_id"), "scope": A._scope(task),
            "answers": A._answers(traj) or task["check"].get("kind") == "answer",
            "fresh": traj.get("start_kind") == "fresh" and not task["start"].get("keep"),
            "stays": A._stays(traj, start),
            "home_start": (task["start"]["kind"] == "fresh" and start == f"/sites/{traj['site']}"
                           and not task["start"].get("keep") and ctrl.get("role") not in A._FLAGGED
                           and not (ctrl.get("prep") or {}))}


def _next(a, b):
    """How part b can follow part a on one session: 'page' (b starts on the page a stays on), 'home' (b starts on the
    home page; a Navigation step gets there), or None."""
    if a["answers"]:
        return None
    if (a["macro"] in A.CHAIN_FIRST and a["stays"] and b["fresh"] and b["start"] == a["start"]
            and (b["macro"] in A.CHAIN_SECOND or b["answers"])):
        return "page"
    if b["home_start"] and a["macro"] not in URL_STATE:
        return "home"
    return None


def chain_specs(items, n_chains, sizes=(2, 3, 4), seed=0, tries=40, answer_share=0.5):
    """items: [(task_id, dir)] of kept trajectories -> [[(record, via)]]: chains of 2-4 parts of one site, walked at
    random; parts act on different controls, watch different tables (augment._scope), and only the last may answer a
    question (when one can follow, it does with probability answer_share). Sites take turns, so every site
    contributes."""
    by_site = defaultdict(list)
    for tid, d in items:
        try:
            r = _record(tid, d)
        except (OSError, KeyError, ValueError):
            continue
        if r:
            by_site[r["site"]].append(r)
    rng, out, seen = random.Random(seed), [], set()
    sites = sorted(by_site)
    misses = Counter()
    while len(out) < n_chains and sites:
        for site in list(sites):
            if len(out) >= n_chains:
                break
            recs = by_site[site]
            got = None
            for _ in range(tries):
                k = rng.choice(sizes)
                a = rng.choice(recs)
                if a["answers"]:
                    continue
                chain = [(a, None)]
                while len(chain) < k:
                    used = {r["id"] for r, _ in chain}
                    ctrls = {r["control"] for r, _ in chain}
                    scopes = set().union(*(r["scope"] for r, _ in chain))
                    last = chain[-1][0]
                    nxt = [(b, v) for b in recs if b["id"] not in used and b["control"] not in ctrls
                           and not (b["scope"] & scopes) and (v := _next(last, b))]
                    if not nxt:
                        break
                    ans = [x for x in nxt if x[0]["answers"]]
                    if len(chain) == k - 1 and ans and rng.random() < answer_share:     # end on a question
                        chain.append(rng.choice(ans))
                        break
                    nxt = [x for x in nxt if not x[0]["answers"]] or nxt
                    page = [x for x in nxt if x[1] == "page"]    # continuing on the page beats a trip home, 3:1
                    chain.append(rng.choice(page if page and rng.random() < 0.75 else nxt))
                    if chain[-1][0]["answers"]:
                        break
                key = "+".join(r["id"] for r, _ in chain)
                if len(chain) >= 2 and key not in seen:
                    got = chain
                    seen.add(key)
                    break
            if got:
                out.append(got)
            else:
                misses[site] += 1
                if misses[site] >= 3:
                    sites.remove(site)
    rng.shuffle(out)
    return out


def chain_key(chain):
    ids = [r["id"] for r, _ in chain]
    return f"plan-{chain[0][0]['site']}-" + hashlib.sha1("+".join(ids).encode()).hexdigest()[:10]


MERGE_ASK = ("Rewrite these requests to a web assistant as ONE natural request that asks for all of them, in this "
             "order. Keep every name, label, number and value exactly as written; add nothing.\n{items}\n"
             "Reply with the merged request only.")


async def merge_all(instructions):
    """-> (one request asking for every part in order, 'merged' | 'joined'): the memory model's rewrite when it keeps
    every value, else the parts joined."""
    joined = " Then ".join(s.strip().rstrip(".") + "." for s in instructions)
    if not R.MEMORY_LLM:
        return joined, "joined"
    try:
        r = await R.MEMORY_LLM["client"].chat.completions.create(
            model=R.MEMORY_LLM["model"], temperature=0, max_completion_tokens=300,
            messages=[{"role": "user", "content": MERGE_ASK.format(
                items="\n".join(f"{i + 1}. {s}" for i, s in enumerate(instructions)))}])
        text = R._clean((r.choices[0].message.content or "").strip().strip('"'))
    except Exception:
        return joined, "joined"
    need = set().union(*(A._values(s) for s in instructions))
    if text and all(v in text for v in need) and len(text) <= sum(map(len, instructions)) + 80 * len(instructions):
        return text, "merged"
    return joined, "joined"


# ── the scripted planner ──────────────────────────────────────────────────────

FINAL_ASK = ("You are the planner in the conversation above, and the task is complete. Write the final message to the "
             "user in one or two sentences: what was done{answer}. Reply with plain text only, not JSON.")


def _plain(text, key):
    """The memory or final message out of a reply: the base model, prompted as browser-use prompts it, often answers
    with a whole {memory, action} object (2026-10-06 smoke test)."""
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", (text or "").strip())
    m = re.search(r"\{.*\}", t, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
        except ValueError:
            d = None
        if isinstance(d, dict):
            if key == "memory":
                return str(d.get("memory") or "")
            for a in d.get("action") or []:
                if isinstance(a, dict) and isinstance(a.get("done"), dict):
                    return str(a["done"].get("text") or "")
            return str(d.get("final_message") or d.get("text") or "")
    return t.strip().strip('"')


async def _ask(messages, prompt, key, need=None, tries=3):
    if not R.MEMORY_LLM:
        return None
    for k in range(tries):
        try:
            r = await R.MEMORY_LLM["client"].chat.completions.create(
                model=R.MEMORY_LLM["model"], temperature=0 if k == 0 else 0.7, max_completion_tokens=320,
                messages=list(messages) + [{"role": "user", "content": prompt}])
            text = R._clean(R.LEAK.sub("", _plain(r.choices[0].message.content, key)))
        except Exception:
            return None
        if text and (need is None or str(need).strip().lower() in text.lower()):
            return text
    return None


def _short(text, n=90):
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[:n - 3].rstrip() + "..."


def template_memory(turns, t):
    """The planner's memory at turn t, from the chain's known decomposition (2026-10-06: the base model's own memories
    contradicted the step taken). The checklist is the parts (trips home are not task items)."""
    items = [x for x in turns if x["kind"] == "delegate" and x["macro"] != "navigate_home"]
    turn = turns[t]
    if t == 0:
        check = " ".join(f"{i + 1}) {_short(x['instruction'], 70)}" for i, x in enumerate(items))
        return f"Checklist: {check} Next: {turn['family']}: {_short(turn['instruction'])}"
    prev = turns[t - 1]
    done = sum(1 for x in turns[:t] if x["kind"] == "delegate" and x["macro"] != "navigate_home")
    said = (f"The {prev['family']} step is done, as its report and page check show." if prev["macro"] != "navigate_home"
            else "The home page is open.")
    if turn["kind"] == "done":
        ans = turn.get("answer")
        return f"{said} All {len(items)} checklist items are done." + (f" The answer is {ans}." if ans else "")
    left = ", ".join(str(i + 1) for i in range(done, len(items)))
    return f"{said} Done: {done} of {len(items)}; left: {left}. Next: {turn['family']}: {_short(turn['instruction'])}"


class PlannerScript:
    """The planner's scripted model: turn t answers with the chain's t-th step and records the planner's input."""

    def __init__(self, turns, rows_dir):
        self.turns, self.rows_dir = turns, rows_dir
        self.t, self.rows, self.response_format = 0, [], None

    async def respond(self, messages, response_format):
        self.response_format = response_format
        if self.t >= len(self.turns):
            raise RuntimeError("script exhausted but the planner asked for another turn")
        turn = self.turns[self.t]
        if turn["kind"] == "delegate":
            action = {"delegate": {"family": turn["family"], "instruction": turn["instruction"]}}
        else:
            ans = turn.get("answer")
            final = await _ask(messages, FINAL_ASK.format(answer=f", including the answer {ans} verbatim" if ans else ""),
                               "final", need=ans)
            final = final or (str(ans) if ans else "The task is done.")
            action = {"done": {"text": final, "success": True}}
        memory = template_memory(self.turns, self.t)
        target = R.canonical({"memory": memory, "action": [action]}, response_format)
        content = json.dumps(target, ensure_ascii=False)
        self.rows.append({"step": self.t, "segment": self.t, "macro": turn.get("macro"), "family": "planner",
                          "op": turn["kind"], "delegated": turn.get("family"),
                          "messages": R.save_images(messages, self.rows_dir, self.t), "target": content})
        self.t += 1
        return content


class ScriptedTeam(PA.Team):
    """The planner's own delegate action, each specialist's model replaced by the replay of its part."""

    def __init__(self, bs, base, steps, rows_dir, overall, budget):
        super().__init__(pick_model=lambda family: EXECUTOR, vllm_url="", overall=overall, budget=budget,
                         version=VERSION)
        self.bs, self.base, self.steps, self.rows_dir = bs, base, steps, rows_dir
        self.replayers = []

    def specialist_llm(self, family, instruction, model):
        st = self.steps[len(self.replayers)]
        if (st["family"], st["instruction"]) != (family, instruction):
            raise RuntimeError(f"delegation out of script: {family}: {instruction}")
        p = st["part"]
        spec_dir = self.rows_dir / "_spec" / str(len(self.replayers))     # its screenshots, apart from the rows'
        spec_dir.mkdir(parents=True, exist_ok=True)
        rp = R.Replayer(self.bs, self.base, st["plan"], p["dir"], spec_dir, p["traj"], p["task"])
        rp.memory_steps = "done"
        self.replayers.append(rp)
        return R.replay_llm(rp)


def _home_plan(site, macro):
    return [{"op": "home", "segment": 0, "macro": macro, "site": site},
            {"op": "macro_done", "segment": 0, "macro": macro},
            {"op": "done", "segment": 0, "macro": macro, "text": "Done.", "answer": None}]


def _site_name(site):
    try:
        t = (ROOT / "sites" / site / "doc" / "README.md").read_text().split("\n")[0]
        return t.lstrip("# ").split("(")[0].strip() or site
    except OSError:
        return site


async def run_chain(chain, base, out_root, headless=True, budget=H.MAX_STEPS, turns_cap=25, log=print):
    cid = chain_key(chain)
    out_root = Path(out_root)
    res = {"task_id": cid, "site": chain[0][0]["site"], "parts": [r["id"] for r, _ in chain],
           "via": [v for _, v in chain], "ok": False, "error": None}
    tmp = out_root / "_tmp" / cid
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    bs = None
    try:
        parts = [R.load_part(r["dir"], base) for r, _ in chain]
        steps = []
        for (r, via), p in zip(chain, parts):
            if via == "home":
                steps.append({"family": "Navigation", "instruction": HOME_STEP.format(site=_site_name(r["site"])),
                              "plan": _home_plan(r["site"], r["macro"]), "part": p, "macro": "navigate_home"})
            steps.append({"family": FAMILY_OF.get(r["macro"], "Navigation"), "instruction": p["task"]["instruction"],
                          "plan": R.build_plan(p["traj"], p["elements"]), "part": p, "macro": r["macro"]})
        answer = steps[-1]["plan"][-1].get("answer")
        instruction, how = await merge_all([p["task"]["instruction"] for p in parts])
        turns = [{"kind": "delegate", "family": s["family"], "instruction": s["instruction"], "macro": s["macro"]}
                 for s in steps] + [{"kind": "done", "answer": answer}]
        first = parts[0]["task"]
        bs = H.make_session(headless=headless)
        await bs.start()
        await H.enable_clipboard(bs)
        await H.prepare(bs, base, first)
        team = ScriptedTeam(bs, base, steps, tmp, instruction, budget)
        script = PlannerScript(turns, tmp)
        planner = PA.planner_agent(bs, instruction, base + first["start"]["url"], R.replay_llm(script), team, VERSION)
        H.use_normalized_coordinates(bs)
        await asyncio.wait_for(planner.run(max_steps=turns_cap), timeout=120 + 40 * len(turns))
        entries, changes, clip = await H.backend_state(bs, base)
        events = [e for rp in team.replayers for e in rp.events]
        events += [{"type": "action", "action": "clipboard_write", "target": "", "value": v} for v in clip]
        seen = [s for rp in team.replayers for s in rp.seen]
        got = next((rp.answer for rp in reversed(team.replayers) if rp.answer is not None), None)
        oks, details = [], []
        for p in parts:
            ok_p, detail_p, _ = R.checks.gate(p["task"]["check"], p["task"]["verifier"], entries, events, changes,
                                              clip, got, seen)
            oks.append(bool(ok_p))
            details.append(str(detail_p))
        ran = (script.t == len(turns) and len(team.replayers) == len(steps)
               and all(rp.cursor >= len(rp.plan) and not rp.queue for rp in team.replayers))
        res.update(ok=bool(all(oks) and ran), turns=len(turns), steps=len(steps), instruction_by=how,
                   detail=" | ".join(details)[:300])
        if not res["ok"]:
            res["error"] = ("script not finished" if not ran else "check failed: " + res["detail"])[:300]
        meta = {"task_id": cid, "site": res["site"], "instruction": instruction, "instruction_by": how,
                "start_url": first["start"]["url"], "parts": res["parts"], "via": res["via"],
                "macros": [r["macro"] for r, _ in chain], "turns": turns, "answer": answer, "version": VERSION,
                "executor": EXECUTOR, "budget": budget, "planner_turns": turns_cap,
                "response_format": script.response_format}
        (tmp / "episode.json").write_text(json.dumps(meta, indent=1, default=str))
        with open(tmp / "rows.jsonl", "w") as f:
            for row in script.rows:
                f.write(json.dumps({"task_id": cid, **row}, ensure_ascii=False) + "\n")
    except Exception as e:                                    # noqa: BLE001  (one chain's failure is a result)
        res["error"] = f"{type(e).__name__}: {e}"[:300]
    finally:
        if bs is not None:
            try:
                await bs.kill()
            except Exception:
                pass
    shutil.rmtree(tmp / "_spec", ignore_errors=True)           # the specialists' own steps are not rows here
    dest = out_root / (cid if res["ok"] else f"_failed/{cid}")
    shutil.rmtree(dest, ignore_errors=True)
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(tmp), str(dest))
    res["duration_s"] = round(time.time() - t0, 1)
    return res


# ── CLI ───────────────────────────────────────────────────────────────────────

def pool_items(pool=POOL, qa=True):
    """[(task_id, dir)]: the pool's kept trajectories, plus (qa) every kept trajectory of a training site that answers a
    question. Those were left out of the executor's training (their answers came from the script that wrote them),
    but here they only end a chain: the planner learns to answer from the specialist's report."""
    ids = set(Path(pool).read_text().split())
    test = set(json.loads((ROOT / "data" / "datagen" / "site_split.json").read_text())["test"])
    kept = _kept_rows()
    items = []
    for tid, r in kept.items():
        d = config.RUNS_DIR / r["run"] / "accepted" / tid
        if not ((d / "trajectory.json").exists() and (d / "elements.json").exists()):
            continue
        if tid in ids or (qa and r.get("macro") in QA_MACROS):
            items.append((tid, d))
    items = [(tid, d) for tid, d in items
             if json.loads((d / "trajectory.json").read_text())["site"] not in test]    # training sites only
    return sorted(items)


async def _run(chains, bases, workers, out, headless, budget, turns_cap):
    q = asyncio.Queue()
    for c in chains:
        q.put_nowait(c)
    tally, t0, res_path = Counter(), time.time(), Path(out) / "results.jsonl"

    async def worker(w):
        base = bases[w % len(bases)]
        while not q.empty():
            c = q.get_nowait()
            res = await run_chain(c, base, out, headless, budget, turns_cap)
            tally["ok" if res["ok"] else "fail"] += 1
            with open(res_path, "a") as f:
                f.write(json.dumps(res, default=str) + "\n")
            print(f"[{sum(tally.values())}/{len(chains)}] {'OK  ' if res['ok'] else 'FAIL'} {res['task_id']} "
                  f"{len(res['parts'])} parts {res.get('duration_s')}s {res.get('error') or ''}"[:260], flush=True)

    await asyncio.gather(*(worker(w) for w in range(workers)))
    print(f"done: {dict(tally)} in {round(time.time() - t0)}s", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--out", required=True)
    ap.add_argument("--pool", default=str(POOL), help="ids of the kept trajectories to chain")
    ap.add_argument("--chains", type=int, default=1500)
    ap.add_argument("--sizes", type=lambda s: tuple(int(x) for x in s.split(",")), default=(2, 3, 4))
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--ports", type=lambda s: [int(p) for p in s.split(",")], default=[8320, 8321])
    # The evaluation's settings: the prompt shows the planner's step cap and each report the specialist steps left.
    # MiniWeb and WebArena-Lite (the default): 40 steps, v6's 25 planner turns; the live web (experiments/paper.yaml,
    # eval_flags.live): --budget 100 --planner-turns 60 (planner_rows/v1_wvsettings, 2026-10-06).
    ap.add_argument("--budget", type=int, default=H.MAX_STEPS, help="specialist steps the reports count down from")
    ap.add_argument("--planner-turns", type=int, default=PA.VERSIONS[VERSION]["max_turns"],
                    help="the planner's step cap its prompt shows")
    ap.add_argument("--memory-model", default="qwen35-4b")
    ap.add_argument("--memory-url", default="http://127.0.0.1:8400/v1")
    ap.add_argument("--headful", action="store_true")
    ap.add_argument("--shard", default=None, help="k/n: one of n processes over the same chain list (own --ports each)")
    args = ap.parse_args(argv)
    R.configure_memory(args.memory_url, args.memory_model)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    chains = chain_specs(pool_items(args.pool), args.chains, args.sizes, args.seed)
    done = set()
    if (out / "results.jsonl").exists():
        done = {json.loads(l)["task_id"] for l in (out / "results.jsonl").read_text().split("\n") if l.strip()}
    chains = [c for c in chains if chain_key(c) not in done]
    if args.shard:                              # k/n: this process takes every n-th chain from k (one event loop
        k, n = (int(v) for v in args.shard.split("/"))      # saturates a core at ~6 chains a minute)
        chains = chains[k::n]
    if args.limit:
        chains = chains[:args.limit]
    sizes = Counter(len(c) for c in chains)
    print(f"{len(chains)} chains to run ({dict(sorted(sizes.items()))} parts; "
          f"{sum(v == 'home' for c in chains for _, v in c)} home steps)", flush=True)
    with B.Servers(ports=args.ports) as srv:
        asyncio.run(_run(chains, srv.bases, args.workers, out, not args.headful, args.budget, args.planner_turns))


if __name__ == "__main__":
    sys.exit(main())
