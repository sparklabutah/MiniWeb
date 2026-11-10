"""Where episodes happen: the backend interface, and the mock world.

A backend gives the day tasks and the probe tasks, and runs one episode of an agent with a human watching:

    tasks = backend.day_tasks(day, n)          # disjoint across days
    probe = backend.probe_tasks()              # the same every day
    ep = await backend.run_episode(task, agent, human, day, ep_dir, base)

`agent` is {"planner", "executor", "executor_path", "version", "day"}: the day t-1 agent.

    MiniWebBackend (daynight.miniweb)   the annotated human tasks on real MiniWeb sites: MiniWebAgent through the
                                        webmix harness on vLLM, graded by each task's verifier
    MockBackend (here)                  no browser, server, GPU or API key. Tasks are built from the tracked registry
                                        (data/macros.yaml, data/macro_locations.yaml, data/datagen/site_split.json);
                                        the agent succeeds on each macro with the probability in its adapter's
                                        skills.json, and night training raises the skills it practiced. Its numbers
                                        only show that the loop works; they are not results.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import random
import time
from pathlib import Path

import yaml

from daynight import config as C
from daynight.human_sim import View
from daynight.schema import Episode, Intervention, Outcome, Step


def _h(*parts):
    return int(hashlib.md5(":".join(map(str, parts)).encode()).hexdigest()[:8], 16)


def family_of(macro):
    from datagen.viewer import FAMILY_OF
    return FAMILY_OF.get((macro or "").split("#")[0], "Other")


REASONING = "Reasoning base"
# The error a failure in each family most often is (the mock world draws the rest at random).
FAMILY_ERROR = {"Drag & gesture": "wrong_value", "Discrete selection": "wrong_target", "Text entry": "wrong_value",
                "Form transaction": "missed_step", "Navigation": "wrong_page", "Out-of-page I/O": "wrong_target",
                REASONING: "wrong_answer"}
OTHER_ERRORS = ("wrong_target", "wrong_value", "wrong_page", "missed_step", "looping")
MAX_STEPS = 40


async def until_interrupt(coro, human, on_cut=None):
    """Run the agent (`coro`) until it ends or the human's `interrupt` is set. An interrupt cancels it at once,
    mid-step (`on_cut()` first, e.g. Agent.stop). -> (result or None, interrupted)."""
    ev = getattr(human, "interrupt", None)
    task = asyncio.ensure_future(coro)
    if ev is None:
        return await task, False
    wait = asyncio.ensure_future(ev.wait())
    await asyncio.wait({task, wait}, return_when=asyncio.FIRST_COMPLETED)
    if task.done():
        wait.cancel()
        return task.result(), False
    if on_cut:
        on_cut()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    except Exception:                                # whatever the agent raised on its way out
        pass
    return None, True


class Backend:
    def day_tasks(self, day, n):
        raise NotImplementedError

    def catalog(self):
        """-> the tasks a person can pick in the console (annotated, so the verifier grades them)."""
        return []

    def sites(self):
        """-> site ids a free-text console task can start on."""
        return []

    def free_task(self, text, site):
        """A task typed in the console: no annotation, so the human's verdict grades it."""
        raise NotImplementedError

    def probe_tasks(self):
        raise NotImplementedError

    async def run_episode(self, task, agent, human, day, ep_dir, base=None):
        raise NotImplementedError

    def servers(self):
        """Context manager -> list of base URLs (one per parallel episode slot)."""
        raise NotImplementedError

    async def run_many(self, tasks, agent, human, day, out, workers=1, prefix=""):
        """All `tasks`, `workers` at a time (one at a time with a real human). -> episodes in task order."""
        workers = 1 if human is not None and human.actor == "real" else max(1, workers)
        results = [None] * len(tasks)
        with self.servers() as bases:
            q = asyncio.Queue()
            for i, t in enumerate(tasks):
                q.put_nowait((i, t))

            async def worker(w):
                while not q.empty():
                    i, t = q.get_nowait()
                    ep_dir = Path(out) / f"{prefix}{t['task_id']}"
                    results[i] = await self.run_episode(t, agent, human, day, ep_dir, bases[w % len(bases)])
                    r = results[i]
                    tag = "OK  " if r.outcome and r.outcome.passed else "FAIL"
                    print(f"  [{sum(x is not None for x in results)}/{len(tasks)}] {tag} {r.task_id} "
                          f"{len(r.steps)} steps, {len(r.interventions)} interventions"
                          + (f" ({r.error})" if r.error else ""), flush=True)

            await asyncio.gather(*(worker(w) for w in range(min(workers, len(tasks)) or 1)))
        return results


def make_backend(cfg):
    if C.is_mock(cfg):
        return MockBackend(cfg)
    if cfg["backend"] == "realweb":
        from daynight.realweb import RealWebBackend
        return RealWebBackend(cfg)
    from daynight.miniweb import MiniWebBackend
    return MiniWebBackend(cfg)


# ── the mock world ─────────────────────────────────────────────────────────────────────────────────────────────────

def initial_skills(macros, seed=0):
    """The mock day-0 executor: a fixed success probability per macro, 0.30-0.90."""
    return {m: round(0.30 + 0.60 * (_h("skill", seed, m) % 1000) / 1000, 3) for m in macros}


def load_skills(path, macros, seed=0):
    p = Path(path) / "skills.json" if path else None
    if p and p.exists():
        return {**initial_skills(macros, seed), **json.loads(p.read_text())}
    return initial_skills(macros, seed)


class _Servers:
    def __enter__(self):
        return ["mock://"]

    def __exit__(self, *exc):
        return False


class MockBackend(Backend):
    POOL = 3000                      # day-stream task pool (disjoint slices per day)
    PROBE = 30
    step_delay = 0.0                 # seconds per agent step (the console slows the agent down to watch it)

    def __init__(self, cfg):
        self.cfg, self.seed = cfg, cfg["seed"]
        reg = yaml.safe_load((C.ROOT / "data" / "macro_locations.yaml").read_text()) or {}
        split = json.loads((C.ROOT / "data" / "datagen" / "site_split.json").read_text())
        from datagen.viewer import FAMILY_OF
        self.locations = {s: {m: v for m, v in (reg.get(s) or {}).items() if m in FAMILY_OF} for s in reg}
        sites = cfg["sites"]
        self.train = [s for s in (split["train"] if sites == "train" else sites) if self.locations.get(s)]
        self.test = [s for s in split["test"] if self.locations.get(s)]
        self.macros = sorted({m for s in self.locations.values() for m in s})
        self._pool = self._tasks(self.train, self.POOL, "d")
        self._probe = self._tasks(self.test, self.PROBE, "p")

    def servers(self):
        return _Servers()

    def _task(self, rng, site, tid, instruction=None):
        avail = sorted(self.locations[site])
        ms = rng.sample(avail, min(len(avail), rng.choice((1, 2, 2, 3))))
        ms = [m for m in ms if family_of(m) != REASONING] + [m for m in ms if family_of(m) == REASONING]
        subs = [(family_of(m), f"{m.replace('_', ' ')}: {self.locations[site][m][0]}") for m in ms]
        return {"kind": "mock", "task_id": tid, "key": f"mock/{tid}", "site": site, "sites": [site], "macros": ms,
                "subtasks": subs, "instruction": instruction or f"[mock] On {site}: " + "; then ".join(s for _, s in subs)}

    def _tasks(self, sites, n, tag):
        rng = random.Random(_h("tasks", self.seed, tag))
        return [self._task(rng, rng.choice(sites), f"mock_{tag}{k:04d}") for k in range(n)]

    def day_tasks(self, day, n):
        return self._pool[(day - 1) * n:day * n]

    def catalog(self):
        return self._pool[:200]

    def sites(self):
        return sorted(set(self.train) | set(self.test))

    def free_task(self, text, site):
        """The mock agent cannot read: it attempts a few of the site's macros, drawn from the text."""
        if site not in self.locations:
            raise ValueError(f"no such site in the mock world: {site}")
        return self._task(random.Random(_h("free", self.seed, site, text)), site,
                          f"free_{_h(site, text) % 16 ** 6:06x}", instruction=text)

    async def _pace(self, human):
        """The agent "works" for `step_delay` seconds. -> True if the human took over meanwhile (Human.interrupt)."""
        ev = getattr(human, "interrupt", None)
        if self.step_delay:
            try:
                await asyncio.wait_for(ev.wait() if ev else asyncio.sleep(self.step_delay), self.step_delay)
            except asyncio.TimeoutError:
                pass
        return bool(ev and ev.is_set())

    def probe_tasks(self):
        lim = self.cfg["probe"].get("limit") or 0
        return self._probe[:lim] if lim else list(self._probe)

    async def run_episode(self, task, agent, human, day, ep_dir, base=None):
        t0 = time.time()
        skills = load_skills(agent.get("executor_path"), self.macros, self.seed)
        eid = f"d{day}_{task['task_id']}" + ("" if human else "_probe")
        rng = random.Random(_h("ep", self.seed, eid, agent.get("executor")))
        ep = Episode(episode_id=eid, day=day, task_id=task["task_id"], instruction=task["instruction"],
                     site=task["site"], sites=task["sites"], macros=list(task["macros"]), agent=dict(agent),
                     human=human.actor if human else "none", subtasks=task["subtasks"],
                     artifacts={"dir": str(ep_dir)})
        by_macro = {m: False for m in task["macros"]}
        help_bonus, k, answer, stopped = 0.0, 0, None, False

        def view(done=False):
            return View(eid, task["instruction"], task["macros"], task["subtasks"], ep.steps, ep.interventions,
                        progress={m: v for m, v in by_macro.items() if family_of(m) != REASONING}, done=done,
                        answer=answer)

        async def watch(done=False):
            """-> "continue" | "retry" | "stop", after the human's decision on the last step."""
            if human is None:
                return "continue"
            d = await human.decide(view(done))
            if d.kind == "continue":
                return "continue"
            iv = Intervention(step=ep.steps[-1].i, kind=d.kind, actor=human.actor, text=d.text, label=d.label,
                              at=round(time.time() - t0, 2))
            ep.interventions.append(iv)
            if d.kind == "message":
                return "retry"
            if human.can_act:
                await take(iv, done)
            return "stop"

        async def take(iv, done=False):
            """A real human finishes the mock task: it counts as done unless they say they gave up."""
            nonlocal answer
            ans, note, label = await human.take_over(view(done))
            iv.text, iv.label = note or iv.text, label or iv.label
            if human.verdict() is not False:
                for m in task["macros"]:
                    by_macro[m] = True
            iv.human_actions = human.recorded_actions() or [
                {"type": "action", "action": "mock_finish", "macro": m} for m in task["macros"]]
            ep.steps.append(Step(i=len(ep.steps), actor="human", action={"takeover": {"text": note or ""}},
                                 report=ans))
            answer = ans if ans is not None else answer

        async def cut():
            """The human took over while the agent was working: it stops at once, before the step lands."""
            ep.steps.append(Step(i=len(ep.steps), actor="agent", action={"interrupted": {"text": "stopped by the human"}}))
            iv = Intervention(step=ep.steps[-1].i, kind="takeover", actor=human.actor, at=round(time.time() - t0, 2))
            ep.interventions.append(iv)
            if human.can_act:
                await take(iv)

        while k < len(task["macros"]) and len(ep.steps) < MAX_STEPS:
            if await self._pace(human):
                await cut()
                stopped = True
                break
            m = task["macros"][k]
            fam = family_of(m)
            p = min(0.97, skills.get(m, 0.5) + help_bonus)
            if k > 0 and rng.random() < (1 - p) * 0.25:          # stops before the task is done
                answer = "Done."
                ep.steps.append(Step(i=len(ep.steps), actor="agent", action={"done": {"text": answer}}, report=answer,
                                     oracle={"macro": m, "ok": False, "deviation": "premature_done"}))
                r = await watch(done=True)
                if r == "retry":
                    help_bonus = 0.35
                    continue
                stopped = True
                break
            ok = rng.random() < p
            dev = None if ok else (FAMILY_ERROR.get(fam, "other") if rng.random() < 0.7 else rng.choice(OTHER_ERRORS))
            report = (f"Answer: {'correct' if ok else 'wrong'} value" if fam == REASONING else
                      f"Did the {m.replace('_', ' ')} step." if ok else f"Tried the {m.replace('_', ' ')} step.")
            ep.steps.append(Step(i=len(ep.steps), actor="agent",
                                 action={"delegate": {"family": fam, "instruction": task["subtasks"][k][1]}},
                                 url=f"/sites/{task['site']}/" + ("" if ok else "?mock_deviation"), report=report,
                                 model=agent.get("planner") if fam == REASONING else agent.get("executor"),
                                 n_actions=1 + rng.randrange(6), oracle={"macro": m, "ok": ok, "deviation": dev}))
            if ok:
                by_macro[m] = True
            if fam == REASONING:
                answer = report
            r = await watch()
            if r == "stop":
                stopped = True
                break
            if r == "retry" and not ok:
                help_bonus = 0.35
                continue
            help_bonus, k = 0.0, k + 1
        if not stopped and (not ep.steps or "done" not in ep.steps[-1].action):
            if await self._pace(human):
                await cut()
            else:
                answer = answer or "Done."
                ep.steps.append(Step(i=len(ep.steps), actor="agent", action={"done": {"text": answer}}, report=answer))
                await watch(done=True)
        took_over = any(iv.kind == "takeover" for iv in ep.interventions)
        ep.outcome = Outcome(passed=all(by_macro.values()), by_macro=by_macro, answer=answer,
                             human_finished=took_over, grader="mock")
        ep.duration_s = round(time.time() - t0, 3)
        return ep
