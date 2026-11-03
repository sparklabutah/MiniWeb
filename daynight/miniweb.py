"""The real day backend: MiniWebAgent on the annotated MiniWeb tasks, with a human watching.

Built from the existing harness, unchanged: tasks and start pages come from webmix.evaluate (human_tasks,
prepare_human), the agent is webmix.planner_agent's Team + planner_agent (the agent_planner arm with no family
adapters and the day's executor as the fallback, i.e. MiniWebAgent), servers from datagen.browser.Servers, and grading
is the task's verifier over this session's recorder stream + server log (webmix.evaluate.human_trajectory,
evaluation.verifiers.verify_task, with webmix.evaluate.QA_MODEL as the answer checks' LLM tier).

The planner runs here rather than through webmix.planner_agent.run_planner_agent only to pass an on_step_end hook to
the planner Agent: after every planner turn that delegated a step, the human sees the step and may send a message
(Agent.add_new_task) or take over (Agent.stop()). A message after the agent's own `done` re-runs the planner with it.

Runs in the miniweb env (browser-use, Playwright, chromium-1117) against the vLLM server of the day's agent.
"""
from __future__ import annotations

import asyncio
import json
import os
import random
import time
from pathlib import Path
from types import SimpleNamespace

from daynight.human_sim import View
from daynight.schema import Episode, Intervention, Outcome, Step
from daynight.world import REASONING, Backend, family_of

USER_PREFIX = "Message from the person who gave you this task: "


def inject_message(agent, text):
    """Put the human's message into the running agent's context. browser-use's follow-up mechanism: the message is
    appended to the task, and the agent keeps its history."""
    fn = getattr(agent, "add_new_task", None)
    if fn is None:
        raise RuntimeError("this browser-use has no Agent.add_new_task: see daynight/README.md, Known gaps")
    fn(USER_PREFIX + text)


def by_macro_of(report):
    """The verifier's {macro or macro#k: bool} -> {canonical macro: bool} (a macro tagged twice needs both)."""
    out = {}
    for k, v in (report.get("by_macro") or {}).items():
        m = k.split("#")[0]
        out[m] = out.get(m, True) and bool(v)
    return out


class MiniWebBackend(Backend):
    def __init__(self, cfg):
        self.cfg = cfg
        from webmix.evaluate import human_tasks
        split_sites = None if cfg["sites"] == "train" else cfg["sites"]
        day = human_tasks(sites=split_sites, split="train")
        random.Random(cfg["seed"]).shuffle(day)
        self._day = day
        p = cfg["probe"]
        self._probe = human_tasks(split=p.get("split", "test")) if p.get("enabled") else []
        if p.get("limit"):
            self._probe = self._probe[:p["limit"]]

    def servers(self):
        from contextlib import contextmanager
        from datagen import browser as B

        @contextmanager
        def ctx():
            with B.Servers(ports=self.cfg["agent"]["ports"]) as srv:
                yield srv.bases
        return ctx()

    def day_tasks(self, day, n):
        tasks = self._day[(day - 1) * n:day * n]
        if len(tasks) < n:
            print(f"  day {day}: only {len(tasks)} unused day tasks left (of {len(self._day)})", flush=True)
        return tasks

    def probe_tasks(self):
        return list(self._probe)

    async def _progress(self, bs, base, task):
        """Per-macro progress on the trace so far (non-reasoning macros: an answer is only graded at the end)."""
        from evaluation.verifiers import verify_task
        from webmix import evaluate as E
        spec = dict(task["verifier"])
        spec["macros"] = {k: v for k, v in (spec.get("macros") or {}).items() if family_of(k) != REASONING}
        if not spec["macros"]:
            return {}
        traj = await E.human_trajectory(bs, base)
        return by_macro_of(await asyncio.to_thread(verify_task, spec, traj, "", task["instruction"]))

    async def run_episode(self, task, agent, human, day, ep_dir, base=None):
        from webmix import evaluate as E
        from webmix import harness as H
        from webmix.planner_agent import VERSIONS, Team, planner_agent
        from evaluation.verifiers import verify_task

        a, hcfg = self.cfg["agent"], self.cfg["human"]
        t0 = time.time()
        eid = f"d{day}_{task['task_id']}" + ("" if human else "_probe")
        ep_dir = Path(ep_dir)
        ep_dir.mkdir(parents=True, exist_ok=True)
        ep = Episode(episode_id=eid, day=day, task_id=task["task_id"], instruction=task["instruction"],
                     site=task["site"], sites=task["sites"], macros=list(task["macros"]), agent=dict(agent),
                     human=human.actor if human else "none", subtasks=task.get("subtasks"),
                     artifacts={"dir": str(ep_dir), "key": task["key"]})
        real = human is not None and human.actor == "real"
        bs = H.make_session(headless=a["headless"] and not real)
        state = {"takeover": False, "seen": 0, "answer": None}
        try:
            await bs.start()
            await H.enable_clipboard(bs)
            os.environ.setdefault("VERIFIER_JUDGE_MODEL", E.QA_MODEL)
            prompt, start = await E.prepare_human(bs, base, task)
            pick = SimpleNamespace(adapters=set(), fallback=agent["executor"], base_name=agent["planner"],
                                   reasoning_to_fallback=False)
            team = Team(lambda fam: E.sub_model(fam, pick), a["vllm"], task["instruction"],
                        context=prompt[len(task["instruction"]):], sub_cap=a["sub_cap"], budget=H.MAX_STEPS,
                        temperature=a["temperature"], version=agent["version"])
            planner = planner_agent(bs, prompt, start,
                                    H.make_llm(agent["planner"], base_url=a["vllm"], temperature=a["temperature"]),
                                    team, agent["version"])
            H.use_normalized_coordinates(bs)

            def sync_steps():
                for t in team.trace[state["seen"]:]:
                    ep.steps.append(Step(i=len(ep.steps), actor="agent",
                                         action={"delegate": {"family": t.get("family"), "instruction": t.get("subtask")}},
                                         url=t.get("url_after"), model=t.get("model"), report=t.get("answer"),
                                         n_actions=t.get("steps") or 0))
                new = len(team.trace) - state["seen"]
                state["seen"] = len(team.trace)
                return new

            async def ask(done=False):
                prog = await self._progress(bs, base, task) if hcfg.get("partial_verify") and not real else None
                d = await human.decide(View(eid, task["instruction"], ep.macros, ep.subtasks, ep.steps,
                                            ep.interventions, progress=prog, done=done, answer=state["answer"]))
                if d.kind != "continue":
                    ep.interventions.append(Intervention(step=ep.steps[-1].i if ep.steps else 0, kind=d.kind,
                                                         actor=human.actor, text=d.text, label=d.label))
                return d

            async def on_turn(agent_obj):
                if human is None or state["takeover"] or not sync_steps():
                    return
                d = await ask()
                if d.kind == "message":
                    inject_message(agent_obj, d.text)
                elif d.kind == "takeover":
                    state["takeover"] = True
                    agent_obj.stop()

            turns = VERSIONS[agent["version"]].get("max_turns", a["planner_turns"])

            async def drive():
                runs = 0
                while True:
                    runs += 1
                    ph = await planner.run(max_steps=turns, on_step_end=on_turn)
                    sync_steps()
                    state["answer"] = ph.final_result() or next((t["answer"] for t in reversed(team.trace)
                                                                 if t.get("answer")), None)
                    if human is None or state["takeover"] or runs > hcfg["max_messages"]:
                        return ph
                    ep.steps.append(Step(i=len(ep.steps), actor="agent", action={"done": {"text": state["answer"]}},
                                         report=state["answer"]))
                    d = await ask(done=True)
                    if d.kind == "message":
                        inject_message(planner, d.text)
                        continue
                    if d.kind == "takeover":
                        state["takeover"] = True
                    return ph

            ph = await (drive() if real else asyncio.wait_for(drive(), timeout=a["timeout"]))
            ph.save_to_file(ep_dir / "planner_history.json")
            answer = state["answer"]
            if state["takeover"] and human.can_act:
                rec0 = len((await H.admin_get(bs, base, "/_admin/record")).get("entries", []) or [])
                ans, note, label = await human.take_over(View(eid, task["instruction"], ep.macros, ep.subtasks,
                                                              ep.steps, ep.interventions, answer=answer))
                rec = (await H.admin_get(bs, base, "/_admin/record")).get("entries", []) or []
                iv = ep.interventions[-1]
                iv.text, iv.label = note or iv.text, label or iv.label
                iv.human_actions = [e for e in rec[rec0:] if e.get("type") != "network"]
                ep.steps.append(Step(i=len(ep.steps), actor="human", action={"takeover": {"n": len(iv.human_actions)}},
                                     report=ans))
                answer = ans if ans is not None else answer
            traj = await E.human_trajectory(bs, base)
            log, changes, clip = await H.backend_state(bs, base)
            (ep_dir / "grade_inputs.json").write_text(json.dumps(
                {"base": base, "traj": traj, "answer": answer, "log": log, "changes": changes, "clip": clip},
                default=str))
            report = await asyncio.to_thread(verify_task, task["verifier"], traj, answer or "", task["instruction"])
            ep.outcome = Outcome(passed=bool(report.get("passed")), by_macro=by_macro_of(report), answer=answer,
                                 human_finished=state["takeover"],
                                 detail=str(report.get("summary") or "")[:300])
            E._Hist(team.hists, answer).save_to_file(ep_dir / "history.json")
            (ep_dir / "trace.json").write_text(json.dumps(team.trace, indent=1, default=str))
            # specialist histories (their screenshot paths point into browser-use's temp dir)
            ep.artifacts.update(history=str(ep_dir / "history_0.json"), grade_inputs=str(ep_dir / "grade_inputs.json"),
                                planner_history=str(ep_dir / "planner_history.json"))
        except asyncio.TimeoutError:
            ep.error = "timeout"
        except Exception as e:
            ep.error = f"{type(e).__name__}: {str(e)[:300]}"
        finally:
            if ep.outcome is None:
                ep.outcome = Outcome(passed=False, human_finished=state["takeover"], detail=ep.error or "")
            ep.duration_s = round(time.time() - t0, 1)
            try:
                await bs.kill()
            except Exception:
                pass
        return ep
