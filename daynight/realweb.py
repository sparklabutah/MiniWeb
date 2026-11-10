"""The real web in the console: an agent works on live websites while a person watches and takes over.

    python -m daynight.console --config daynight/configs/v1_realweb.yaml        # then open http://127.0.0.1:8390

Type a task and the page it starts on (or pick an example). The agent is browser-use's own Agent on an API model
(`realweb.model`, OPENAI_API_KEY from the environment or `.env`). It runs in a headless Chromium that the console
shows live on the right. Each of its steps appears in the chat, and a message you send reaches it after its current
step.

**Take over** stops it at once. You finish in the same tab through the live view while recording continues: every
click (with the element under it), key, scroll and navigation goes to the episode's takeover, and frames are saved.
There is no verifier on the live web, so your verdict grades the episode. Episodes are logged like any other day's
(schema.Episode), under `<out>/day_<t>/`.

Needs `browser-use` and a Chromium (requirements.txt), and an API key; no GPU, MiniWeb server or database.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import time
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

from daynight import config as C
from daynight.human_sim import View
from daynight.miniweb import inject_message
from daynight.schema import Episode, Intervention, Outcome, Step
from daynight.world import Backend, until_interrupt

VIEWPORT = {"width": 1280, "height": 800}


def start_url(text):
    """A start page as the person typed it: a URL, or a bare host (example.com)."""
    u = (text or "").strip()
    if not u:
        raise ValueError("give the page the task starts on")
    if "://" not in u:
        u = "https://" + u
    p = urlsplit(u)
    if p.scheme not in ("http", "https") or not p.netloc:
        raise ValueError(f"not a web page: {text}")
    return u


def api_key(name="OPENAI_API_KEY"):
    """From the environment, else the repo's .env (helpers.llm reads it the same way)."""
    if os.environ.get(name):
        return os.environ[name]
    env = C.ROOT / ".env"
    for line in env.read_text().splitlines() if env.exists() else []:
        s = line.strip().removeprefix("export ")
        if s.startswith(name + "="):
            return s.split("=", 1)[1].strip().strip('"').strip("'")
    return ""


def _task(text, url, tid=None):
    host = urlsplit(url).netloc.removeprefix("www.")
    tid = tid or "web_" + hashlib.md5(f"{url}:{text}".encode()).hexdigest()[:6]
    return {"kind": "web", "task_id": tid, "key": None, "site": host, "sites": [host], "subtasks": None,
            "macros": [], "instruction": text, "start_hint": url, "verifier": None}


def _step(i, item):
    """One browser-use history item -> schema.Step."""
    mo = getattr(item, "model_output", None)
    acts = []
    for a in (getattr(mo, "action", None) or []):
        try:
            acts.append({k: v for k, v in a.model_dump(exclude_none=True).items() if v not in ({}, None)})
        except Exception:
            acts.append({"action": str(a)[:200]})
    res = getattr(item, "result", None) or []
    said = next((r.extracted_content for r in reversed(res) if getattr(r, "extracted_content", None)), None)
    err = next((r.error for r in res if getattr(r, "error", None)), None)
    st = getattr(item, "state", None)
    return Step(i=i, actor="agent", action={"browse": {"goal": getattr(mo, "next_goal", None) or "", "actions": acts}},
                url=getattr(st, "url", None), report=(f"error: {err}" if err else said),
                n_actions=len(acts))


class RealWebBackend(Backend):
    def __init__(self, cfg):
        self.cfg = cfg
        self.rw = cfg["realweb"]
        self.bs, self.screen = None, None

    def _session(self):
        from browser_use import BrowserSession
        kw = {"executable_path": os.path.expanduser(self.rw["chrome"])} if self.rw.get("chrome") else {}
        return BrowserSession(headless=True, keep_alive=True, viewport=VIEWPORT, device_scale_factor=1, **kw)

    async def open(self, fps=4):
        """The console's browser: started once, on the start page, shown live and reused by every task."""
        from daynight.screen import Screen
        self.bs = self._session()
        await self.bs.start()
        self.screen = Screen(self.bs, None, fps=fps, who=lambda: "idle")
        await self.screen.start()
        await self.screen.navigate(self.rw["start_url"])
        await asyncio.sleep(1.5)
        return self.screen

    async def close(self):
        if self.screen:
            await self.screen.stop()
        if self.bs:
            try:
                await self.bs.kill()
            except Exception:
                pass

    def warnings(self):
        if not (api_key() or self.rw.get("base_url")):
            return ["OPENAI_API_KEY is empty: the browser works, but the agent cannot run. Put the key in .env "
                    "(OPENAI_API_KEY=...) and restart the console."]
        return []

    def servers(self):
        @contextmanager
        def ctx():
            yield [None]                          # no MiniWeb server: the browser goes to the live site
        return ctx()

    def day_tasks(self, day, n):
        raise SystemExit("a real-web day needs a person: python -m daynight.console --config <cfg>")

    def probe_tasks(self):
        return []

    def catalog(self):
        return [_task(e["task"], start_url(e["url"]), tid=f"ex{k + 1}") for k, e in enumerate(self.rw.get("examples")
                                                                                            or [])]

    def sites(self):
        return []

    def free_task(self, text, site):
        return _task(text, start_url(site or self.rw["start_url"]))

    async def run_episode(self, task, agent, human, day, ep_dir, base=None):
        from browser_use import Agent
        from browser_use.llm.openai.chat import ChatOpenAI

        base_url = self.rw.get("base_url")
        key = api_key() or ("EMPTY" if base_url else "")
        if not key:
            raise RuntimeError("OPENAI_API_KEY is empty: put it in .env (OPENAI_API_KEY=...) and restart the console")
        hcfg, t0 = self.cfg["human"], time.time()
        eid = f"d{day}_{task['task_id']}"
        ep_dir = Path(ep_dir)
        ep_dir.mkdir(parents=True, exist_ok=True)
        model = self.rw["model"]
        ep = Episode(episode_id=eid, day=day, task_id=task["task_id"], instruction=task["instruction"],
                     site=task["site"], sites=task["sites"], macros=[], agent={"model": model, "day": day - 1},
                     human=human.actor if human else "none", artifacts={"dir": str(ep_dir),
                                                                        "start": task["start_hint"]})
        own = self.bs is None                     # outside the console: a browser for this episode only
        bs = self._session() if own else self.bs
        state = {"takeover": False, "seen": 0, "answer": None}
        try:
            if own:
                await bs.start()
            if human is not None:
                await human.attach(bs, None)
            agent_obj = Agent(task=task["instruction"] + f"\n\nStart at {task['start_hint']}.",
                              llm=ChatOpenAI(model=model, api_key=key, base_url=base_url), browser_session=bs,
                              initial_actions=[{"navigate": {"url": task["start_hint"], "new_tab": False}}])

            def history():
                h = getattr(agent_obj, "history", None) or agent_obj.state.history
                return list(getattr(h, "history", h) or [])

            def sync_steps():
                items = history()
                for it in items[state["seen"]:]:
                    ep.steps.append(_step(len(ep.steps), it))
                new = len(items) - state["seen"]
                state["seen"] = len(items)
                return new

            async def ask(done=False):
                d = await human.decide(View(eid, task["instruction"], [], None, ep.steps, ep.interventions,
                                            done=done, answer=state["answer"]))
                if d.kind != "continue":
                    ep.interventions.append(Intervention(step=ep.steps[-1].i if ep.steps else 0, kind=d.kind,
                                                         actor=human.actor, text=d.text, label=d.label,
                                                         at=round(time.time() - t0, 2)))
                return d

            async def on_step(a):
                if human is None or state["takeover"] or not sync_steps():
                    return
                d = await ask()
                if d.kind == "message":
                    inject_message(a, d.text)
                elif d.kind == "takeover":
                    state["takeover"] = True
                    a.stop()

            async def drive():
                runs = 0
                while True:
                    runs += 1
                    h = await agent_obj.run(max_steps=self.rw["max_steps"], on_step_end=on_step)
                    sync_steps()
                    state["answer"] = h.final_result()
                    if human is None or state["takeover"] or runs > hcfg["max_messages"]:
                        return h
                    ep.steps.append(Step(i=len(ep.steps), actor="agent", action={"done": {"text": state["answer"]}},
                                         report=state["answer"]))
                    d = await ask(done=True)
                    if d.kind == "message":
                        inject_message(agent_obj, d.text)
                        continue
                    if d.kind == "takeover":
                        state["takeover"] = True
                    return h

            _, cut = await until_interrupt(drive(), human, on_cut=agent_obj.stop)
            if cut and not state["takeover"]:        # stopped mid-step
                sync_steps()
                state["takeover"] = True
                ep.steps.append(Step(i=len(ep.steps), actor="agent",
                                     action={"interrupted": {"text": "stopped by the human"}}))
                ep.interventions.append(Intervention(step=ep.steps[-1].i, kind="takeover", actor=human.actor,
                                                     at=round(time.time() - t0, 2)))
            answer = state["answer"]
            if state["takeover"] and human.can_act:
                ans, note, label = await human.take_over(View(eid, task["instruction"], [], None, ep.steps,
                                                              ep.interventions, answer=answer))
                iv = ep.interventions[-1]
                iv.text, iv.label = note or iv.text, label or iv.label
                iv.human_actions = human.recorded_actions()
                ep.steps.append(Step(i=len(ep.steps), actor="human", action={"takeover": {"n": len(iv.human_actions)}},
                                     report=ans))
                answer = ans if ans is not None else answer
            try:
                hist = getattr(agent_obj, "history", None) or agent_obj.state.history
                hist.save_to_file(ep_dir / "agent_history.json")
            except Exception:
                pass
            try:
                (ep_dir / "final.png").write_bytes(await bs.take_screenshot())
            except Exception:
                pass
            verdict = human.verdict() if human else None
            ep.outcome = Outcome(passed=bool(verdict), answer=answer, human_finished=state["takeover"],
                                 grader="human", detail="" if verdict is not None else "no verdict")
            (ep_dir / "steps.json").write_text(json.dumps([s.__dict__ for s in ep.steps], indent=1, default=str))
        except Exception as e:
            ep.error = f"{type(e).__name__}: {str(e)[:300]}"
        finally:
            if ep.outcome is None:
                ep.outcome = Outcome(passed=False, human_finished=state["takeover"], grader="human",
                                     detail=ep.error or "")
            ep.duration_s = round(time.time() - t0, 1)
            if human is not None:
                try:
                    await human.detach()
                except Exception:
                    pass
            if own:
                try:
                    await bs.kill()
                except Exception:
                    pass
        return ep
