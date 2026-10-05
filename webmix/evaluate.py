"""Run a WebMix arm on datagen-style tasks through the browser-use harness, served by vLLM.

    python -m webmix.evaluate --tasks data/webmix/valgen/runs/val1/tasks.jsonl --arm base --out data/webmix/eval/base
    python -m webmix.evaluate --tasks ... --arm oracle --adapters drag,io,select,rest

Arms (design doc "Routing"): `base` (no adapter), `pooled` (one adapter for every step), `oracle` (the
adapter of the task's own family; for a task with a prefix macro, the prefix family first, switched at
the model's macro_done), `planned` (the planner adapter picks the family at the start and after every
macro_done, from the current screen). The model name of each request picks the adapter on the vLLM server
(webmix/serve.sh). Each episode starts like a replay (webmix.harness.prepare) and is graded by the same
backend gate the datagen trajectories passed (datagen.checks.gate); the flash macro judge can be run on
the saved episodes later.

`--human` evaluates the human-written tasks (data/annotations/*/*/task.json) on the held-out sites instead: the
same harness and arms, started like evaluation.run_agent_verify (recorded start page; logged out for a login
macro; the portal home + an app directory for a cross-site task), graded by the task's own verifier.json over
this session's recorder stream + server log (a task the generator never wrote, unlike validation v1/v2).

`--record-rows` also writes each passing episode's steps as training rows (the exact request browser-use sent and
the model's reply; <out>/<episode>/rows.jsonl + screenshots, the webmix.train layout): rejection sampling on
human tasks (`--human --human-split train --repeats N --temperature 0.7`) for the reasoning adapter.

Each episode also saves its grading inputs (grade_inputs.json: the session's request log, data changes,
clipboard, action events, answer, seen text). `--regrade DIR` recomputes every grade from them: granite
runs grade without the QA chain's LLM tier (no credentials there), and are re-graded here.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from collections import Counter
from pathlib import Path
from types import SimpleNamespace

from datagen import browser as B
from datagen import checks
from datagen.driver import _VISIBLE_TEXT
from datagen.viewer import FAMILY_OF
from webmix import harness as H
from webmix.eval_viewer import copy_screenshots

ADAPTER_OF_FAMILY = {"Drag & gesture": "drag", "Out-of-page I/O": "io", "Discrete selection": "select",
                     "Text entry": "rest", "Form transaction": "rest", "Navigation": "rest", "Reasoning base": "reasoning"}
# Reasoning steps (and the final answer they end in) go to their own specialist: a `reasoning` adapter when one is
# served, else the untouched base model (user, 2026-09-30: an adapter trained without reasoning rows lost question
# answering, 2/12 on validation v2 vs base's 4/12; routing reasoning away from it avoids that forgetting).
REASONING = "Reasoning base"


def family_plan(task):
    """Macro sequence of a task: a human task's annotated macros in order; a datagen task's prefix macro
    (mid-chain start) first, then its own."""
    if task.get("kind") == "human":
        return list(task["macros"])
    pre = ((task.get("start") or {}).get("prefix") or {}).get("macro")
    return ([pre] if pre else []) + [task["macro"]]


MAX_GATES = 3


def premature(plan_left, seg_actions, fam):
    """A `done` is premature when planned steps remain after the current one, or when the current step has not been
    acted on at all (the specialists' trained habit is macro_done immediately followed by done, which skipped the
    re-planned step; 2026-09-30: with the first rule only, 4 gates fired on 56 human tasks while 28 stopped early).
    A reasoning step's done IS its action (the answer), so it counts as acting."""
    return plan_left > 1 or (plan_left == 1 and seg_actions == 0 and fam != REASONING)


def router_note(families):
    """What the router tells the specialist when it gates a done: the planned steps still left, described."""
    from webmix.planner import FAMILY_HINTS
    left = [f"{f} ({FAMILY_HINTS.get(f, '').rstrip('.')})" if FAMILY_HINTS.get(f) else f for f in families]
    return ("The task is not finished yet. The router's plan still has " + str(len(left)) + " step(s): " + "; then ".join(left)
            + ". Re-read the task, find the part that is not done yet, and do it; call done only when every part is "
              "finished.")


def gate_done(out, remaining, gates):
    """Done-gating (2026-09-30): the router, not the specialist, decides when the task is complete. A premature `done`
    (see premature) becomes `macro_done` (the next step's specialist takes over), at most MAX_GATES times per episode.
    -> True when the reply was rewritten."""
    acts = getattr(out.completion, "action", None) or []
    if not remaining or gates >= MAX_GATES:
        return False
    for i, a in enumerate(acts):
        if "done" in a.model_dump(exclude_none=True):
            acts[i] = type(a).model_validate({"macro_done": {}})
            return True
    return False


class Routed:
    """Chooses the served model (base or an adapter) for each request; advances past a macro on macro_done. With
    `gate`, a done before the last planned macro is turned into macro_done (gate_done)."""

    def __init__(self, llm, names, gate=False, fams=None, bs=None, note=False):
        self.llm, self.names, self.k, self.trace, self.gates, self.seg = llm, names, 0, [], 0, 0
        fams = fams or [None] * len(names)
        inner = llm.ainvoke

        async def ainvoke(messages, output_format=None, **kw):
            llm.model = self.names[min(self.k, len(self.names) - 1)]
            out = await inner(messages, output_format, **kw)
            left = max(0, len(self.names) - self.k)            # planned steps not yet closed, the current one included
            fam = fams[min(self.k, len(fams) - 1)] if fams else None
            gated = gate and gate_done(out, premature(left, self.seg, fam), self.gates)
            self.gates += gated
            if gated and note and bs is not None:
                H.ROUTER_NOTES[id(bs)] = router_note(fams[self.k:] if fams and fams[0] else [])
            acts = [a.model_dump(exclude_none=True) for a in getattr(out.completion, "action", []) or []]
            self.trace.append({"model": llm.model, "action": acts, **({"gated": True} if gated else {})})
            if any("macro_done" in a for a in acts):
                self.k += 1
                self.seg = 0
            else:
                self.seg += sum(1 for a in acts if not {"done", "macro_done"} & set(a))
            return out
        llm.ainvoke = ainvoke


def action_events(trace):
    """The model's actions as human-schema action events (the verifier's action_included checks)."""
    kinds = {"input": ("type", "text"), "send_keys": ("key", "keys"), "select_dropdown": ("select", "text"),
             "click": ("click", None), "done": ("answer", "text")}
    out = []
    for t in trace:
        for a in t["action"]:
            (name, p), = a.items()
            kind, field = kinds.get(name, (name, None))
            ev = {"type": "action", "action": kind, "target": ""}
            if field:
                ev["value"] = (p or {}).get(field)
            out.append(ev)
    return out


def history_actions(hist):
    """The model's actions from browser-use histories, in the router-trace form ({name: params}). For the subtask arms
    (oracle_sub, planned_sub, agent_planner), whose trace holds one record per subtask without per-step actions
    (2026-10-02: grading those arms on generated tasks raised KeyError 'action' before grade_inputs.json was written)."""
    acts = []
    for item in getattr(hist, "history", []) or []:
        for a in getattr(getattr(item, "model_output", None), "action", None) or []:
            acts.append(a.model_dump(exclude_none=True))
    return acts


def human_tasks(sites=None, split="test", macros=None):
    """The human-written tasks on `sites` (default: the `split` sites of data/datagen/site_split.json; a task counts
    as held out when any of its sites is) as evaluation dicts, optionally only those with one of `macros`. Start page
    and login rule as evaluation.run_agent_verify."""
    import ast
    from annotation.storage import ANNOTATIONS_DIR
    macros_filter = macros
    from evaluation.run_agent_verify import locate_task, recorded_start_url
    from datagen import config
    sp = json.loads(config.SPLIT_PATH.read_text())
    sites = set(sites or (sp["test"] + sp["train"] if split == "all" else sp[split]))   # all: every human task (376)
    test = set(sp["test"])
    out = []
    for tj in sorted(ANNOTATIONS_DIR.glob("*/*/task.json")):
        try:
            raw = json.loads(tj.read_text())
        except (OSError, ValueError):
            continue
        if not (tj.parent / "verifier.json").exists():
            continue
        raw_sites = raw.get("sites")
        try:
            raw_sites = ast.literal_eval(raw_sites) if isinstance(raw_sites, str) else raw_sites
        except (ValueError, SyntaxError):
            raw_sites = None
        all_sites = {x["id"] if isinstance(x, dict) else x for x in (raw_sites or [raw.get("site")])}
        if split == "train" and not sites.intersection(all_sites) or split == "train" and all_sites & test:
            continue
        if split != "train" and raw.get("site") not in sites:
            continue
        key = f"{tj.parent.parent.name}/{tj.parent.name}"
        tdir, task, verifier = locate_task(key)
        lit = lambda v: ast.literal_eval(v) if isinstance(v, str) and v[:1] in "[{" else v       # noqa: E731
        macros = [m for m in (lit(task.get("macros")) or []) if m]
        if macros_filter and not set(macros_filter) & set(macros):
            continue
        task_sites = [x["id"] if isinstance(x, dict) else x for x in (lit(task.get("sites")) or [task["site"]])]
        subs = lit(task.get("macro_subtasks")) or {}
        spans = lit(task.get("macro_spans")) or {}
        order = sorted(spans, key=lambda m: spans[m][0]) if spans else macros
        gold = [(FAMILY_OF.get(m.split("#")[0], "Other"), str(subs.get(m) or "").strip()) for m in order]
        # a report is the task's deliverable: reasoning subtasks last (span order can put it first, when the annotator
        # read part of the answer early; "Report critical open count and MeridianFlow open count" needs a later page)
        gold = [g for g in gold if g[0] != REASONING] + [g for g in gold if g[0] == REASONING]
        out.append({"kind": "human", "task_id": tdir.name, "key": key, "site": task["site"], "sites": task_sites,
                    "subtasks": gold if gold and all(t for _, t in gold) else None,
                    "macro": macros[-1] if macros else "?", "macros": macros, "instruction": task.get("instruction", ""),
                    "start_hint": recorded_start_url(tdir) or task.get("starting_url"), "verifier": verifier,
                    "needs_login": "authenticate_by_form" in (verifier.get("macros") or {})})
    return out


async def prepare_human(bs, base, task):
    """-> (prompt, start url) after the session flags (logged out for a login task) and the start page load."""
    from urllib.parse import urlencode
    from evaluation.run_agent_verify import app_directory, resolve_start_url
    flags = {"logout": "1"} if task["needs_login"] else {}
    await H.goto(bs, f"{base}/_admin/session-flags" + ("?" + urlencode(flags) if flags else ""))
    if len(task["sites"]) > 1:
        start, prompt = base + "/", task["instruction"] + app_directory(base, task["sites"])
    else:
        start, prompt = resolve_start_url(base, task["start_hint"], task["site"]), task["instruction"]
    await H.goto(bs, start)
    await asyncio.sleep(1.0)
    return prompt, start


async def human_trajectory(bs, base):
    """verify_task's trajectory for this session: the recorder stream (actions + observations) with the server's
    request log merged in as network events (as evaluation.run_agent_verify.build_trajectory, per session)."""
    from evaluation.trajectory import merge_server_log
    rec = (await H.admin_get(bs, base, "/_admin/record")).get("entries", []) or []
    log = (await H.admin_get(bs, base, "/_admin/log")).get("entries", []) or []
    return merge_server_log([e for e in rec if e.get("type") != "network"], log)


def grade_human(task, traj, answer):
    from evaluation.verifiers import verify_task
    report = verify_task(task["verifier"], traj, answer or "", question=task["instruction"])
    return bool(report.get("passed")), str(report.get("summary") or report.get("by_macro") or "")[:300]


class _Hist:
    """AgentHistoryList-like view of a subtask run (one browser-use Agent per subtask, one browser session)."""

    def __init__(self, hists, answer):
        self.hists, self.answer = hists, answer
        self.history = [h for x in hists for h in x.history]

    def final_result(self):
        return self.answer

    def is_done(self):
        return bool(self.hists) and self.hists[-1].is_done()

    def errors(self):
        return [e for x in self.hists for e in x.errors()]

    def save_to_file(self, path):
        for i, x in enumerate(self.hists):
            x.save_to_file(Path(path).with_name(f"history_{i}.json"))


RETRY_HINT = " (A previous attempt at this step did not complete it: check the page and finish it.)"


async def run_subtasks(bs, llm, subtasks, pick_model, on_end, planner=None, context="", sub_cap=15, overall=None,
                       end_on_macro_done=False, last_step_budget=False, outcome_feedback=False):
    """Hierarchical execution (user, 2026-09-30: "the planner has to output the subtask for the specialist"): each
    subtask runs as its own browser-use episode on the live session (the specialists were trained on one-macro
    episodes with one instruction), the next starting from the page the last one left. `subtasks`: the gold
    (family, instruction) list, or None with `planner` (async () -> [(family, instruction), ...] for the steps
    still left, from the current screen). The final answer is the last reasoning subtask's answer (else the last
    subtask's final message). Each subtask gets at most `sub_cap` of the 40 steps and `context` (a cross-site
    task's app directory). Specialists claim done without the effect (2026-09-30: "sorted by Most Clicks" with no sort
    request sent), so the planner's re-plan from the screen is the check: a step it re-issues is retried once with
    RETRY_HINT, a second repeat stops the run (at most 8 subtasks). `overall`: the whole task, given to each subtask
    as background. `last_step_budget`: the last planned step gets all the steps left, not `sub_cap` (the cap only
    protects later steps; WebArena's one-step plans were cut at 15 of 40, 2026-09-30). `outcome_feedback`: the
    planner gets each finished step as "instruction -> result: <its final message>" (closed loop). -> (_Hist, trace)."""
    from browser_use import Agent
    hists, answers, trace, left, i = [], [], [], H.MAX_STEPS, 0
    queue = list(subtasks or [])
    while left > 0 and len(hists) < 8:
        if planner is not None:
            queue = await planner([f"{t['subtask']} -> result: {str(t['answer'] or 'no result')[:300]}"
                                   if outcome_feedback else t["subtask"] for t in trace])
        if not queue:
            break
        last = len(queue) == 1
        fam, text = queue.pop(0) if planner is None else queue[0]
        tries = sum(t["subtask"] == text for t in trace)
        if planner is not None and tries >= 2:
            break                                          # re-issued twice: no progress left
        llm.model = pick_model(fam)
        url = await bs.get_current_page_url()
        step = text + (RETRY_HINT if tries else "")
        if overall:
            step = f"Overall task (for context only): {overall}\nYour step now: {step}\nDo only this step, then call done."
        # a reasoning step's answer is its done text, so only action steps may end at macro_done
        agent = Agent(task=H.instruction(step + context, url), llm=llm, browser_session=bs,
                      tools=H.make_tools(end_on_macro_done and fam != REASONING), max_failures=3, **H.AGENT_KWARGS)
        H.use_normalized_coordinates(bs)
        cap = left if (last_step_budget and last) else min(sub_cap, left)
        h = await agent.run(max_steps=cap, on_step_start=lambda a: H.enable_clipboard(bs, a),
                            on_step_end=on_end)
        hists.append(h)
        left -= max(1, len(h.history))
        trace.append({"subtask": text, "family": fam, "model": llm.model, "steps": len(h.history), "done": h.is_done(),
                      "answer": h.final_result()})
        if fam == REASONING and h.final_result():
            answers.append(h.final_result())
        i += 1
        if planner is None and not queue:
            break
    final = answers[-1] if answers else (hists[-1].final_result() if hists else None)     # the last report is the answer
    return _Hist(hists, final), trace


class Planned:
    """Routes by the planner adapter (design doc "Routing"): the remaining family plan comes from the planner at the
    start and again after each macro_done (instruction + families done + the current screen, the planner rows'
    format); every step goes to the first remaining family's adapter, else to `fallback` (adapter not loaded, or
    an empty plan). The trace records each plan."""

    def __init__(self, llm, bs, instruction, planner_url, planner_name, adapters, fallback, base_name="qwen35-4b",
                 gate=False, reasoning_to_fallback=False, note=False):
        from openai import AsyncOpenAI
        self.llm, self.bs, self.instruction, self.adapters, self.fallback = llm, bs, instruction, adapters, fallback
        self.base_name, self.gates, self.reasoning_to_fallback, self.seg = base_name, 0, reasoning_to_fallback, 0
        self.client, self.planner_name = AsyncOpenAI(base_url=planner_url, api_key="EMPTY"), planner_name
        self.done, self.plans, self.trace, self.fam, self.current, self.pending = [], [], [], None, fallback, True
        inner = llm.ainvoke

        async def ainvoke(messages, output_format=None, **kw):
            if self.pending:
                await self.replan()
                self.pending = False
            llm.model = self.current
            out = await inner(messages, output_format, **kw)
            plan = next((x["plan"] for x in reversed(self.plans) if "plan" in x), [])
            gated = gate and gate_done(out, premature(len(plan), self.seg, self.fam), self.gates)
            self.gates += gated
            if gated and note:
                H.ROUTER_NOTES[id(self.bs)] = router_note(plan)
            acts = [a.model_dump(exclude_none=True) for a in getattr(out.completion, "action", []) or []]
            self.trace.append({"model": llm.model, "family": self.fam, "action": acts, **({"gated": True} if gated else {})})
            if any("macro_done" in a for a in acts):
                self.done.append(self.fam or "unplanned")
                self.pending = True
                self.seg = 0
            else:
                self.seg += sum(1 for a in acts if not {"done", "macro_done"} & set(a))
            return out
        llm.ainvoke = ainvoke

    async def replan(self):
        import base64
        from webmix import planner as P
        plan = []
        try:
            png = await self.bs.take_screenshot()
            msgs = P.prompt_messages(self.instruction, self.done, "data:image/png;base64," + base64.b64encode(png).decode())
            r = await self.client.chat.completions.create(model=self.planner_name, messages=msgs, temperature=0,
                                                          max_tokens=120)
            plan = P.parse_plan(r.choices[0].message.content or "")
        except Exception as e:
            self.plans.append({"error": f"{type(e).__name__}: {str(e)[:120]}"})
        self.plans.append({"done": list(self.done), "plan": plan})
        self.fam = plan[0] if plan else None
        name = ADAPTER_OF_FAMILY.get(self.fam)
        if name in self.adapters:
            self.current = name
        else:                                      # reasoning without its adapter: the base model (unless told otherwise)
            self.current = self.base_name if self.fam == REASONING and not self.reasoning_to_fallback else self.fallback


def sub_model(fam, args):
    """The specialist for one subtask: its family's adapter when served, else --fallback (reasoning: its own adapter,
    else the base model unless --reasoning-to-fallback)."""
    name = ADAPTER_OF_FAMILY.get(fam)
    if name in args.adapters:
        return name
    if fam == REASONING and not args.reasoning_to_fallback:
        return args.base_name
    return args.fallback or args.base_name


def arm_models(arm, task, base_name, adapters, pooled_name="pooled"):
    fams = [FAMILY_OF.get(m, "Other") for m in family_plan(task)]
    if arm == "base":
        return [base_name]
    if arm == "pooled":
        return [pooled_name]
    if arm == "oracle":
        names = [ADAPTER_OF_FAMILY.get(f, "rest") for f in fams]
        return [n if n in adapters else base_name for n in names]
    raise ValueError(arm)


def _record_client(llm, steps):
    """Wrap the ChatOpenAI client so every request (OpenAI-format messages) and reply content is kept in `steps`."""
    from types import SimpleNamespace
    real = llm.get_client()

    async def create(**kw):
        r = await real.chat.completions.create(**kw)
        steps.append({"model": kw.get("model"), "messages": kw.get("messages"), "content": r.choices[0].message.content})
        return r
    proxy = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    llm.get_client = lambda: proxy


async def run_episode(task, base, arm, args, out_dir, rep=0):
    from browser_use import Agent
    from webmix.replay import _rebase
    human = task.get("kind") == "human"
    if not human:
        task = _rebase(task, base)       # values recorded with the generating server's origin -> this server's
        task["check"] = checks.relax_recorded_dates(task["check"], [task["instruction"], json.dumps(task.get("option"))])
    t0 = time.time()
    epn = task["task_id"] + (f"~r{rep}" if args.repeats > 1 else "")
    res = {"task_id": task["task_id"], "episode": epn, "macro": task["macro"], "site": task["site"], "arm": arm,
           "ok": False}
    rec = []
    bs = H.make_session()
    try:
        await bs.start()
        await H.enable_clipboard(bs)
        if human:
            prompt, start = await prepare_human(bs, base, task)
        else:
            await H.prepare(bs, base, task)
            prompt, start = task["instruction"], base + task["start"]["url"]
        llm = H.make_llm(args.base_name, base_url=args.vllm, temperature=args.temperature, max_tokens=args.max_tokens)
        if args.record_rows:
            _record_client(llm, rec)
        if arm == "planned":
            router = Planned(llm, bs, task["instruction"], args.vllm, args.planner_name, args.adapters,
                             args.fallback or args.base_name, args.base_name, gate=args.gate_done or args.gate_note,
                             reasoning_to_fallback=args.reasoning_to_fallback, note=args.gate_note)
        elif arm in ("oracle_sub", "planned_sub", "agent_planner"):
            router = SimpleNamespace(trace=[], plans=[])
        else:
            router = Routed(llm, arm_models(arm, task, args.base_name, args.adapters, args.pooled_name),
                            gate=(args.gate_done or args.gate_note) and arm == "oracle",
                            fams=[FAMILY_OF.get(m, "Other") for m in family_plan(task)] if arm == "oracle" else None,
                            bs=bs, note=args.gate_note)
        seen = []

        async def after_step(a):                 # viewport text of every screen (answer checks need the evidence seen)
            try:
                seen.append(await H.evaluate(bs, _VISIBLE_TEXT) or "")
            except Exception:
                pass
        seen.append(await H.evaluate(bs, _VISIBLE_TEXT) or "")
        if arm == "oracle_sub":
            if not task.get("subtasks"):
                raise ValueError("no gold subtasks for this task")
            hist, sub_trace = await asyncio.wait_for(
                run_subtasks(bs, llm, task["subtasks"], lambda f: sub_model(f, args), after_step,
                             context=prompt[len(task["instruction"]):], sub_cap=args.sub_cap,
                             overall=task["instruction"] if args.sub_context else None,
                             end_on_macro_done=args.end_on_macro_done,
                             last_step_budget=args.last_step_budget,
                             outcome_feedback=args.planner_prompt == "closed"), timeout=args.timeout)
            router.trace = sub_trace
        elif arm == "planned_sub":
            import base64
            from openai import AsyncOpenAI
            from webmix import planner as P
            pclient, examples = AsyncOpenAI(base_url=args.vllm, api_key="EMPTY"), (P.fewshot_examples() if args.prompted_planner or args.planner_prompt in ("defined", "closed") else None)
            plans = []

            async def replan(done_texts):
                png = await bs.take_screenshot()
                steps = await P.plan_steps(pclient, args.planner_name, task["instruction"], done_texts,
                                           "data:image/png;base64," + base64.b64encode(png).decode(), examples,
                                           defined=args.planner_prompt == "defined", closed=args.planner_prompt == "closed")
                plans.append({"done": list(done_texts), "steps": steps})
                return steps
            hist, sub_trace = await asyncio.wait_for(
                run_subtasks(bs, llm, None, lambda f: sub_model(f, args), after_step, planner=replan,
                             context=prompt[len(task["instruction"]):], sub_cap=args.sub_cap,
                             overall=task["instruction"] if args.sub_context else None,
                             end_on_macro_done=args.end_on_macro_done,
                             last_step_budget=args.last_step_budget,
                             outcome_feedback=args.planner_prompt == "closed"), timeout=args.timeout)
            router.trace, router.plans = sub_trace, plans
        elif arm == "agent_planner":
            from webmix.planner_agent import run_planner_agent
            hist, sub_trace, phist = await asyncio.wait_for(
                run_planner_agent(bs, task["instruction"], start, lambda f: sub_model(f, args), args.vllm,
                                  args.planner_name, context=prompt[len(task["instruction"]):], sub_cap=args.sub_cap,
                                  max_turns=args.planner_turns, on_end=after_step, temperature=args.temperature,
                                  version=args.agent_version),
                timeout=args.timeout)
            router.trace = sub_trace
            (out_dir / epn).mkdir(parents=True, exist_ok=True)
            phist.save_to_file(out_dir / epn / "planner_history.json")
        else:
            agent = Agent(task=H.instruction(prompt, start), llm=llm, browser_session=bs,
                          tools=H.make_tools(), max_failures=3, **H.AGENT_KWARGS)
            H.use_normalized_coordinates(bs)
            hist = await asyncio.wait_for(agent.run(max_steps=args.max_steps or H.MAX_STEPS,
                                                    on_step_start=lambda a: H.enable_clipboard(bs, a),
                                                    on_step_end=after_step), timeout=args.timeout)
        answer = hist.final_result()
        ep = out_dir / epn
        ep.mkdir(parents=True, exist_ok=True)
        try:
            if human:
                traj = await human_trajectory(bs, base)
                (ep / "grade_inputs.json").write_text(json.dumps({"base": base, "traj": traj, "answer": answer}, default=str))
                ok, detail = grade_human(task, traj, answer)
            else:
                log, changes, clip = await H.backend_state(bs, base)
                steps = router.trace if all("action" in t for t in router.trace) else [{"action": history_actions(hist)}]
                events = action_events(steps) + [{"type": "action", "action": "clipboard_write", "target": "",
                                                         "value": v} for v in clip]
                (ep / "grade_inputs.json").write_text(json.dumps(
                    {"base": base, "log": log, "events": events, "changes": changes, "clip": clip, "answer": answer,
                     "seen": seen}, default=str))
                ok, detail, _ = checks.gate(task["check"], task["verifier"], log, events, changes, clip, answer, seen)
        except Exception as e:                   # e.g. the QA chain's LLM tier without credentials: --regrade later
            ok, detail = False, f"grade error {type(e).__name__}: {str(e)[:200]}"
            res["grade_error"] = True
        res.update(ok=bool(ok), detail=str(detail)[:300], steps=len(hist.history), answer=answer,
                   done=hist.is_done(), models=[t["model"] for t in router.trace], errors=[e for e in hist.errors() if e][:5])
        hist.save_to_file(ep / "history.json")
        (ep / "trace.json").write_text(json.dumps(router.trace, indent=1, default=str))
        if args.record_rows and ok and rec:           # a passing episode's steps, as training rows
            from webmix.replay import save_images
            fam = args.record_family or FAMILY_OF.get(task["macro"], "Other")
            with open(ep / "rows.jsonl", "w") as f:
                for i, st in enumerate(rec):
                    f.write(json.dumps({"task_id": epn, "step": i, "family": fam, "source": "rejection_sampling",
                                        "model": st["model"], "messages": save_images(st["messages"], ep, i),
                                        "target": st["content"]}, ensure_ascii=False) + "\n")
            (ep / "episode.json").write_text(json.dumps({"task_id": epn, "instruction": task["instruction"],
                                                         "macros": task.get("macros"), "variant": "rejection_sampling"}))
        if arm == "planned":
            (ep / "plans.json").write_text(json.dumps(router.plans, indent=1))
            res["plans"] = [x.get("plan") for x in router.plans if "plan" in x]
        if arm in ("oracle_sub", "planned_sub", "agent_planner"):
            (ep / "subtasks.json").write_text(json.dumps({"trace": router.trace, "plans": router.plans}, indent=1,
                                                         default=str, ensure_ascii=False))
            res["subtasks"] = [(t["family"], t["subtask"], t["steps"]) for t in router.trace]
        copy_screenshots(ep)                     # out of browser-use's /tmp dir, for webmix.eval_viewer
    except asyncio.TimeoutError:
        res["error"] = "timeout"
    except Exception as e:
        res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
    finally:
        res["duration_s"] = round(time.time() - t0, 1)
        try:
            await bs.kill()
        except Exception:
            pass
    return res


async def _run(tasks, bases, args):
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    q = asyncio.Queue()
    for t in tasks:
        for rep in range(args.repeats):
            q.put_nowait((t, rep))
    tally = Counter()

    async def worker(w):
        while not q.empty():
            t, rep = q.get_nowait()
            res = await run_episode(t, bases[w % len(bases)], args.arm, args, out, rep)
            res["repeat"] = rep
            tally["ok" if res["ok"] else "fail"] += 1
            with open(out / "results.jsonl", "a") as f:
                f.write(json.dumps(res, default=str) + "\n")
            print(f"[{sum(tally.values())}] {'OK  ' if res['ok'] else 'FAIL'} {res['task_id']} {res.get('steps')} steps "
                  f"{res['duration_s']}s {res.get('error') or res.get('detail', '')[:120]}", flush=True)

    await asyncio.gather(*(worker(w) for w in range(args.workers)))
    print(f"{args.arm}: {dict(tally)}", flush=True)


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m webmix.evaluate")
    ap.add_argument("--tasks", default=None, help="a datagen tasks.jsonl (e.g. from the validation root)")
    ap.add_argument("--human", action="store_true", help="the human-written tasks on the held-out sites instead")
    ap.add_argument("--human-split", default="test", choices=["test", "train", "all"], help="--human: held-out sites, train sites, or all tasks")
    ap.add_argument("--human-macros", type=lambda s: set(s.split(",")), default=None,
                    help="--human: only tasks with one of these macros")
    ap.add_argument("--record-rows", action="store_true", help="write passing episodes as training rows")
    ap.add_argument("--record-family", default=None, help="--record-rows: the rows' family (default: the task macro's)")
    ap.add_argument("--arm", required=True, choices=["base", "pooled", "oracle", "planned", "oracle_sub", "planned_sub", "agent_planner"])
    ap.add_argument("--planner-name", default="planner", help="planned arm: the planner adapter's served name")
    ap.add_argument("--sub-cap", type=int, default=15, help="oracle_sub/planned_sub: steps per subtask (of the 40)")
    ap.add_argument("--planner-turns", type=int, default=12, help="agent_planner: the planner agent's own turns")
    ap.add_argument("--agent-version", default="v1", help="agent_planner: planner_agent version (v1, v2, ...)")
    ap.add_argument("--sub-context", action="store_true", help="oracle_sub/planned_sub: each subtask sees the whole task")
    ap.add_argument("--last-step-budget", action="store_true",
                    help="oracle_sub/planned_sub: the last planned step gets all remaining steps (not --sub-cap)")
    ap.add_argument("--end-on-macro-done", action="store_true",
                    help="oracle_sub/planned_sub: a non-reasoning subtask ends at its macro_done (not only at done)")
    ap.add_argument("--planner-prompt", default="", choices=["", "defined", "closed"],
                    help="planned_sub: an untrained planner with the family-definitions prompt: 'defined' (SYSTEM_DEF) or "
                         "'closed' (SYSTEM_DEF_CLOSED, step results fed back)")
    ap.add_argument("--prompted-planner", action="store_true",
                    help="planned_sub: an untrained planner prompted with worked examples (planner.fewshot_examples)")
    ap.add_argument("--reasoning-to-fallback", action="store_true",
                    help="planned arm: reasoning steps go to --fallback too (e.g. planner + pooled_v4 only)")
    ap.add_argument("--gate-note", action="store_true",
                    help="done-gating that also tells the specialist the planned steps still left (implies --gate-done)")
    ap.add_argument("--gate-done", action="store_true",
                    help="oracle/planned arms: the router turns a premature done into macro_done (gate_done)")
    ap.add_argument("--fallback", default=None, help="planned arm: model for an unplanned family (default: the base)")
    ap.add_argument("--adapters", type=lambda s: set(s.split(",")), default=set(), help="adapters loaded on the server")
    ap.add_argument("--base-name", default="qwen35-4b")
    ap.add_argument("--vllm", default="http://127.0.0.1:8400/v1")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int, default=1024,
                    help="reply budget per agent call; a thinking model (GLM-4.1V-Thinking) needs its thinking to fit too")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument("--max-steps", type=int, default=0,
                    help="single agent: step cap (default harness.MAX_STEPS = 40). Review round 1, A3 (2026-10-05): the "
                         "untrained single agent with MiniWebAgent's model-call budget")
    ap.add_argument("--ports", type=lambda s: [int(p) for p in s.split(",")], default=[8318, 8319])
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--task-ids", type=lambda s: set(s.split(",")), default=None, help="only these task ids")
    ap.add_argument("--out", required=True)
    ap.add_argument("--pooled-name", default="pooled", help="served adapter name the pooled arm uses")
    ap.add_argument("--regrade", default=None, help="an earlier --out dir: recompute its grades from grade_inputs.json")
    ap.add_argument("--resume", action="store_true", help="skip tasks already in --out/results.jsonl (repeats=1 runs)")
    ap.add_argument("--verifier-only", action="store_true",
                    help="grade with the backend check + the task's verifier as-is (its QA tier chain included: regex, "
                         "exact, precise, then the LLM tier), never the flash macro judge. webmix runs never use the "
                         "macro judge; the flag records the intent")
    args = ap.parse_args(argv)
    # the QA tier chain's LLM tier: flash-lite for our validation runs (user, 2026-09-28); repo default untouched
    os.environ.setdefault("VERIFIER_JUDGE_MODEL", "gemini-3.5-flash-lite")
    if args.human:
        tasks = human_tasks(split=args.human_split, macros=args.human_macros)
    else:
        tasks = [json.loads(line) for line in Path(args.tasks).read_text().split("\n") if line.strip()]
    if args.task_ids:
        tasks = [t for t in tasks if t["task_id"] in args.task_ids]
    if args.limit:
        tasks = tasks[:args.limit]
    if args.regrade:
        return regrade(tasks, Path(args.regrade))
    if args.resume and (Path(args.out) / "results.jsonl").exists():
        # 2026-10-03: a Slurm job ended mid-run; finish the run instead of redoing it (episodes in results.jsonl are kept)
        done = {json.loads(line)["task_id"] for line in (Path(args.out) / "results.jsonl").read_text().split("\n")
                if line.strip()}
        tasks = [t for t in tasks if t["task_id"] not in done]
        print(f"resume: {len(done)} tasks already in {args.out}, {len(tasks)} to run", flush=True)
    with B.Servers(ports=args.ports) as srv:
        asyncio.run(_run(tasks, srv.bases, args))


def regrade(tasks, out):
    """Recompute every episode's grade in `out` from its saved inputs, with this machine's full QA tier chain.
    Writes results_regraded.jsonl (the latest result per task, ok/detail replaced) and prints the tally."""
    from webmix.replay import _rebase
    last = {}
    for line in (out / "results.jsonl").read_text().split("\n"):
        if line.strip():
            r = json.loads(line)
            last[r["task_id"]] = r
    by_id = {t["task_id"]: t for t in tasks}
    tally, changed = Counter(), 0
    with open(out / "results_regraded.jsonl", "w") as f:
        for tid, r in last.items():
            gi = out / tid / "grade_inputs.json"
            if tid in by_id and gi.exists() and by_id[tid].get("kind") == "human":
                g = json.loads(gi.read_text())
                ok, detail = grade_human(by_id[tid], g["traj"], g["answer"])
                changed += bool(ok) != bool(r.get("ok"))
                r = {**r, "ok": ok, "detail": detail, "regraded": True}
                r.pop("grade_error", None)
            elif tid in by_id and gi.exists():
                g = json.loads(gi.read_text())
                task = _rebase(by_id[tid], g["base"])
                task["check"] = checks.relax_recorded_dates(task["check"], [task["instruction"], json.dumps(task.get("option"))])
                ok, detail, _ = checks.gate(task["check"], task["verifier"], g["log"], g["events"], g["changes"], g["clip"],
                                            g["answer"], g["seen"])
                changed += bool(ok) != bool(r.get("ok"))
                r = {**r, "ok": bool(ok), "detail": str(detail)[:300], "regraded": True}
                r.pop("grade_error", None)
            tally["ok" if r.get("ok") else "fail"] += 1
            f.write(json.dumps(r, default=str) + "\n")
    print(f"regraded {out}: {dict(tally)} ({changed} changed)", flush=True)


if __name__ == "__main__":
    main()
