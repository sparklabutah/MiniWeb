"""The day console: a person gives the agent tasks in a chat and takes over the moment it goes wrong.

    python -m daynight.console --config daynight/configs/v1_sim.yaml --day 1          # real agent, MiniWeb sites
    python -m daynight.console --config daynight/configs/v1_mock.yaml                 # try it: the mock world
    # open http://127.0.0.1:8390 (on the lab machine: ssh -L 8390:127.0.0.1:8390 <host>, then open it locally)

Left, the chat: type a task (or pick an annotated one) and the agent starts on it. Each step it takes appears in the
chat, and anything you type while it works reaches it after its current step. When it says it is done you mark the
result Correct or Wrong (Wrong hands you the task). Right, the agent's browser, live.

**Take over** stops the agent at once, mid-step. The browser stays open and you finish the task in the live view:
clicks, typing and scrolling go into the agent's own tab. Recording never stops. MiniWeb's page recorder logs your
actions after the agent's, the console logs every input, and frames are saved, named by who was in control. Then
**Done** (or **Give up**), with an optional answer, error type and note: a takeover is the agent's failure, and the
error type you pick is the label RQ1 scores the meta agent against.

Every finished episode is appended to `<out>/day_<t>/episodes.jsonl` (schema.Episode, human "real"); its chat, inputs
and frames go to `<out>/day_<t>/console/<n>_<task>/`. An annotated task is graded by its verifier, with your actions
included. A typed task has no verifier, so your verdict grades it. **End day** hands the day to the night:
`python -m daynight.loop --config <out>/config.yaml --resume`.

Real runs need what a real day needs (daynight/README.md), but the browser stays headless: you see it here.
"""
from __future__ import annotations

import argparse
import asyncio
import concurrent.futures
import copy
import html
import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import yaml

from daynight import config as C
from daynight.day import day0_agent, run_probe
from daynight.human_sim import Decision, Human
from daynight.schema import ERROR_TYPES, Label, read_jsonl
from daynight.world import make_backend

PAGE = Path(__file__).with_name("console.html")


def _step_text(s):
    act = s.action or {}
    if "delegate" in act:
        d = act["delegate"] or {}
        return f"{d.get('family') or 'step'}: {d.get('instruction') or ''}" + (f"\n→ {s.report}" if s.report else "")
    if "done" in act:
        return "Done" + (f": {s.report}" if s.report else "")
    if "browse" in act:                                    # the live web's agent: its goal and its actions
        b = act["browse"] or {}
        acts = "; ".join(", ".join(f"{k} {json.dumps(v)[:80]}" for k, v in a.items()) for a in b.get("actions") or [])
        return (b.get("goal") or "step") + (f"\n· {acts}" if acts else "") + (f"\n→ {s.report}" if s.report else "")
    return json.dumps(act)[:300]


class ConsoleHuman(Human):
    """The person at the console. Hub methods (`on_*`) run on the event loop; `decide` / `take_over` are the backend's
    side of the Human interface."""
    actor = "real"
    can_act = True
    remote_screen = True

    def __init__(self, hub, ep_dir, fps=4, save_every=1.0):
        self.hub, self.ep_dir, self.fps, self.save_every = hub, Path(ep_dir), fps, save_every
        self.interrupt = asyncio.Event()
        self.finish = asyncio.get_running_loop().create_future()
        self.review, self.inbox, self.notes, self.inputs = None, [], [], []
        self.mode, self.shown, self._verdict, self.screen = "agent", 0, None, None
        self.t0, self.takeover_t, self.takeover_step = time.time(), None, None

    # ── the person (via the hub) ──
    def on_message(self, text):
        self.hub.emit("user", text)
        if self.mode == "human":
            self.notes.append(text)
        elif self.review is not None and not self.review.done():
            self.review.set_result(Decision("message", text))
        else:
            self.inbox.append(text)
            self.hub.emit("system", "The agent reads this after its current step.")

    def on_takeover(self):
        if self.mode == "human":
            return
        self._to_human()
        if self.review is not None and not self.review.done():
            self.review.set_result(Decision("takeover"))
        else:
            self.interrupt.set()

    def on_accept(self):
        if self.review is not None and not self.review.done():
            self._verdict = True
            self.hub.set_status("grading")
            self.hub.emit("system", "Marked correct.")
            self.review.set_result(Decision())

    def on_done(self, d):
        if self.mode == "human" and not self.finish.done():
            self.hub.set_status("grading")
            self.finish.set_result(d)

    def _to_human(self):
        self.mode, self.takeover_t = "human", time.time()
        self.hub.set_status("human")
        self.hub.emit("takeover", "You have control. The agent is stopped and recording continues: finish the task "
                                  "in the browser, then press Done.")

    # ── the backend ──
    def _publish(self, steps):
        for s in steps[self.shown:]:
            if s.actor == "agent" and "interrupted" not in (s.action or {}):
                self.hub.emit("agent", _step_text(s), step=s.i, url=s.url)
        self.shown = len(steps)

    async def decide(self, view):
        self._publish(view.steps)
        if view.done:
            self.hub.set_status("review")
            self.hub.emit("done", view.answer or "", answer=view.answer)
            self.review = asyncio.get_running_loop().create_future()
            d = await self.review
            self.review = None
            if d.kind == "message":
                self.hub.set_status("agent")
            return d
        if self.inbox:
            return Decision("message", self.inbox.pop(0))
        return Decision()

    async def take_over(self, view):
        if self.mode != "human":
            self._to_human()
        self._publish(view.steps)
        self.takeover_step = view.steps[-1].i if view.steps else 0
        d = await self.finish
        self._verdict = bool(d.get("passed", True))
        et, macro = d.get("error_type"), d.get("macro")
        label = Label(error_type=et, macro=macro if macro in view.macros else None, step=self.takeover_step) \
            if et in ERROR_TYPES else None
        note = (d.get("note") or "").strip() or "; ".join(self.notes)
        return (d.get("answer") or "").strip() or None, note, label

    async def attach(self, browser, base):
        shared = self.hub.screen
        if shared is not None and shared.bs is browser:      # the console's own browser (the real web): reuse its view
            self.screen, self._shared = shared, True
            shared.save_dir = self.ep_dir / "frames"
            shared.save_dir.mkdir(parents=True, exist_ok=True)
            shared.who = lambda: self.mode
            return
        from daynight.screen import Screen
        self.screen, self._shared = Screen(browser, base, fps=self.fps, save_dir=self.ep_dir / "frames",
                                           save_every=self.save_every, who=lambda: self.mode), False
        await self.screen.start()

    async def detach(self):
        if self.screen and getattr(self, "_shared", False):
            self.screen.save_dir, self.screen.who = None, (lambda: "idle")
        elif self.screen:
            await self.screen.stop()

    def verdict(self):
        return self._verdict

    def recorded_actions(self):
        return [e for e in self.inputs if self.takeover_t and e["t"] >= self.takeover_t]


class Hub:
    """What the HTTP threads and the event loop share. Every change runs on the loop (`call`)."""

    def __init__(self, loop, backend, info):
        self.loop, self.backend, self.info = loop, backend, info
        self.lock = threading.Lock()
        self.events, self.status, self.episode, self.human = [], "idle", None, None
        self.screen = None               # the console's own browser view, when the backend keeps one open (real web)
        self.rec, self.day_dir = None, None   # Record: the person's own demonstration, outside any task
        self.requests = asyncio.Queue()
        self.tasks = {t["task_id"]: t for t in backend.catalog()}

    def emit(self, kind, text="", **kw):
        with self.lock:
            e = {"n": len(self.events), "t": round(time.time(), 2), "kind": kind, "text": text, **kw}
            self.events.append(e)
        return e

    def set_status(self, s):
        with self.lock:
            self.status = s

    def snapshot(self, since=0):
        with self.lock:
            scr = (self.human.screen if self.human else None) or self.screen
            n = scr.n if scr else len(self.events) + (len(self.human.inputs) if self.human else 0)
            return {"events": self.events[since:], "status": self.status, "episode": self.episode, "frame": n,
                    "url": scr.url if scr else (self.episode or {}).get("url", ""),
                    "screen_error": scr.error if scr else None, "browser": self.screen is not None,
                    "typing": getattr(scr, "typing", None) if scr else None}

    # ── called from HTTP threads ──
    def call(self, name, data):
        if name in ("input", "nav"):
            return asyncio.run_coroutine_threadsafe(getattr(self, "a_" + name)(data), self.loop).result(15)
        fut = concurrent.futures.Future()

        def run():
            try:
                fut.set_result(getattr(self, "a_" + name)(data))
            except Exception as e:
                fut.set_exception(e)
        self.loop.call_soon_threadsafe(run)
        return fut.result(15)

    def frame(self):
        scr = (self.human.screen if self.human else None) or self.screen
        if scr and scr.jpeg:
            return scr.jpeg, "image/jpeg"
        if self.info.get("mock"):
            return mock_frame(self).encode(), "image/svg+xml"
        return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="800"><rect width="1280" height="800" '
                f'fill="#f7f7f5"/><text x="60" y="120" font-size="28" font-family="sans-serif" fill="#666">'
                f'{"Starting the browser…" if self.screen or not self.human else "Opening the page…"}</text></svg>'
                ).encode(), "image/svg+xml"

    # ── actions (on the loop) ──
    def a_run(self, d):
        if self.status not in ("idle", "ended"):
            raise ValueError("a task is already running")
        if d.get("task_id"):
            if d["task_id"] not in self.tasks:
                raise ValueError(f"no such task: {d['task_id']}")
            task = self.tasks[d["task_id"]]
        else:
            text = (d.get("text") or "").strip()
            if not text or not d.get("site"):
                raise ValueError("type a task and pick a site")
            task = self.backend.free_task(text, d["site"])
        self.set_status("starting")
        self.requests.put_nowait(task)
        return {"task_id": task["task_id"]}

    def _human(self):
        if self.human is None:
            raise ValueError("no task is running")
        return self.human

    def a_message(self, d):
        text = (d.get("text") or "").strip()
        if text:
            self._human().on_message(text)

    def a_takeover(self, d):
        self._human().on_takeover()

    def a_accept(self, d):
        self._human().on_accept()

    def a_done(self, d):
        self._human().on_done(d)

    def a_key(self, d):
        """The real web's API key, pasted in the console: used from the next task on, no restart. `save` also writes
        it to the repo's .env (gitignored). The key is never logged or sent back."""
        key = (d.get("key") or "").strip()
        if not key or any(c.isspace() for c in key) or len(key) < 20:
            raise ValueError("that does not look like an API key")
        name = d.get("name") or "OPENAI_API_KEY"
        if name != "OPENAI_API_KEY":
            raise ValueError(f"unknown key {name}")
        os.environ[name] = key
        if d.get("save"):
            env = C.ROOT / ".env"
            lines = env.read_text().splitlines() if env.exists() else []
            out, done = [], False
            for line in lines:
                if line.strip().removeprefix("export ").startswith(name + "="):
                    out.append(f"{name}={key}"); done = True
                else:
                    out.append(line)
            if not done:
                out.append(f"{name}={key}")
            env.write_text("\n".join(out) + "\n")
            os.chmod(env, 0o600)
        self.info["needs_key"] = False
        self.emit("system", "API key set" + (" and saved to .env" if d.get("save") else " for this session")
                  + ". Type a task.")
        return {"ok": True, "saved": bool(d.get("save"))}

    def a_end(self, d):
        if self.status not in ("idle",):
            raise ValueError("finish the running task first")
        self.set_status("ended")
        self.requests.put_nowait(None)

    # ── Record: no task running, the person demonstrates in the browser; inputs and frames are saved ──
    def a_record_start(self, d):
        if self.status != "idle":
            raise ValueError("finish the running task first")
        k = len(list((self.day_dir / "console").glob("*"))) + 1 if (self.day_dir / "console").exists() else 1
        rdir = self.day_dir / "console" / f"{k:03d}_rec_{time.strftime('%H%M%S')}"
        rdir.mkdir(parents=True, exist_ok=True)
        self.rec = {"dir": rdir, "t0": time.time(), "inputs": [], "start_url": self.screen.url if self.screen else ""}
        if self.screen:
            self.screen.save_dir, self.screen.who = rdir / "frames", (lambda: "human")
            self.screen.save_dir.mkdir(exist_ok=True)
        self.set_status("recording")
        self.emit("record", "Recording. Do the task in the browser, then press Stop and say what you showed.")

    def a_record_stop(self, d):
        if self.rec is None:
            raise ValueError("not recording")
        r, self.rec = self.rec, None
        if self.screen:
            self.screen.save_dir, self.screen.who = None, (lambda: "idle")
        demo = {"task": (d.get("task") or "").strip(), "start_url": r["start_url"],
                "end_url": self.screen.url if self.screen else "", "seconds": round(time.time() - r["t0"], 1),
                "actions": r["inputs"], "dir": str(r["dir"])}
        (r["dir"] / "recording.json").write_text(json.dumps(demo, indent=1, default=str))
        with open(self.day_dir / "recordings.jsonl", "a") as f:
            f.write(json.dumps({k: v for k, v in demo.items() if k != "actions"} | {"n_actions": len(r["inputs"])})
                    + "\n")
        self.set_status("idle")
        self.emit("system", f"Saved the recording: {len(r['inputs'])} actions, {demo['seconds']} s"
                            + (f", \u201c{demo['task']}\u201d" if demo["task"] else "") + ".")
        return {"dir": str(r["dir"])}

    async def _free_input(self, d, nav=False):
        """No task running: the console's browser is the person's. While recording, every input is saved."""
        entry = None
        if self.rec is not None:
            entry = {"t": round(time.time() - self.rec["t0"], 3), "source": "console",
                     **({"type": "nav", "to": d.get("to")} if nav else
                        {k: d[k] for k in ("type", "x", "y", "key", "text", "dx", "dy", "clicks") if k in d})}
            self.rec["inputs"].append(entry)
        if self.screen is None:
            return
        if nav:
            return await self.screen.navigate(d.get("to") or "reload")
        target = await self.screen.input(d)
        if entry is not None and target:
            entry["target"] = target

    async def a_input(self, d):
        if self.human is None and (self.screen is not None or self.rec is not None):
            return await self._free_input(d)
        h = self._human()
        if h.mode != "human":
            raise ValueError("take over first: the agent has the browser")
        h.inputs.append({"t": round(time.time(), 3), "source": "console",
                         **{k: d[k] for k in ("type", "x", "y", "key", "text", "dx", "dy", "clicks") if k in d}})
        if h.screen:
            target = await h.screen.input(d)
            if target:
                h.inputs[-1]["target"] = target            # what was under the click

    async def a_nav(self, d):
        if self.human is None and (self.screen is not None or self.rec is not None):
            return await self._free_input(d, nav=True)
        h = self._human()
        if h.mode != "human":
            raise ValueError("take over first: the agent has the browser")
        h.inputs.append({"t": round(time.time(), 3), "source": "console", "type": "nav", "to": d.get("to")})
        if h.screen:
            await h.screen.navigate(d.get("to") or "reload")


def mock_frame(hub):
    """The mock world has no browser: a drawing of its state, so the console can be tried anywhere."""
    ep, h = hub.episode or {}, hub.human
    steps = [e["text"] for e in hub.events if e["kind"] == "agent"][-6:] if ep else []
    human = h is not None and h.mode == "human"
    color = "#c0392b" if human else "#2c3e50"
    rows = "".join(f'<text x="60" y="{250 + 60 * i}" font-size="22" fill="#333">{html.escape(s[:95])}</text>'
                   for i, s in enumerate(t.split("\n")[0] for t in steps))
    rec = hub.rec is not None
    clicks = "".join(f'<circle cx="{e["x"]}" cy="{e["y"]}" r="9" fill="none" stroke="#c0392b" stroke-width="3"/>'
                     for e in (h.inputs if h else (hub.rec or {}).get("inputs", []))[-12:]
                     if e.get("type") == "down" and "x" in e)
    human = human or rec
    color = "#c0392b" if human else color
    banner = ("Recording your demonstration" if rec else "You have control: clicks and keys are recorded" if human else
              "The agent is working" if ep else "No task running: type one in the chat")
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="1280" height="800" viewBox="0 0 1280 800">'
            f'<rect width="1280" height="800" fill="#f7f7f5"/><rect width="1280" height="70" fill="{color}"/>'
            f'<text x="40" y="45" font-size="26" fill="#fff" font-family="sans-serif">{html.escape(banner)}</text>'
            f'<text x="60" y="140" font-size="30" font-family="sans-serif" fill="#111">mock world · '
            f'{html.escape(ep.get("site") or "")}</text>'
            f'<text x="60" y="185" font-size="20" font-family="sans-serif" fill="#666">'
            f'{html.escape((ep.get("instruction") or "")[:110])}</text>'
            f'<g font-family="monospace">{rows}</g>{clicks}</svg>')


def make_handler(hub):
    page = PAGE.read_bytes()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            u = urlsplit(self.path)
            if u.path == "/":
                return self._send(200, page, "text/html; charset=utf-8")
            if u.path == "/api/info":
                return self._send(200, hub.info)
            if u.path == "/api/events":
                return self._send(200, hub.snapshot(int((parse_qs(u.query).get("since") or ["0"])[0])))
            if u.path == "/api/frame":
                body, ctype = hub.frame()
                return self._send(200, body, ctype) if body else self._send(204, b"", ctype)
            self._send(404, {"error": "not found"})

        def do_POST(self):
            # a custom header: a page on another origin cannot send it without a CORS preflight, which never passes
            if self.headers.get("X-Console") != "1":
                return self._send(403, {"error": "missing X-Console header"})
            name = urlsplit(self.path).path.removeprefix("/api/")
            if not hasattr(hub, "a_" + name):
                return self._send(404, {"error": f"no action {name}"})
            try:
                data = json.loads(self.rfile.read(int(self.headers.get("Content-Length") or 0)) or b"{}")
                self._send(200, hub.call(name, data) or {"ok": True})
            except Exception as e:
                self._send(400, {"error": f"{e}"})

    return Handler


def _append(path, ep):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(ep.to_dict(), ensure_ascii=False, default=str) + "\n")


def hand_to_night(cfg, saved_cfg, day, agent):
    """End of a console day: the loop's next phase for this day is its night."""
    out = C.out_dir(cfg)
    sp = out / "state.json"
    state = json.loads(sp.read_text()) if sp.exists() else {"day": day, "phase": "day", "agent": agent}
    if (state["day"], state["phase"]) != (day, "day"):
        print(f"state.json is at day {state['day']}, phase {state['phase']}: left as it is", flush=True)
        return
    state["phase"] = "night"
    sp.write_text(json.dumps(state, indent=1, default=str))
    if not (out / "config.yaml").exists():
        (out / "config.yaml").write_text(yaml.safe_dump(saved_cfg, sort_keys=False))
    print(f"day {day} handed to the night: python -m daynight.loop --config {out / 'config.yaml'} --resume", flush=True)


async def session(cfg, saved_cfg, day, backend, agent, ready=None):
    """Serve the console and run one episode per task the person gives, until End day. -> the episodes' count."""
    ccfg = cfg["console"]
    d = C.day_dir(cfg, day)
    log = d / "episodes.jsonl"
    web = cfg["backend"] == "realweb"
    info = {"name": cfg["name"], "backend": cfg["backend"], "mock": C.is_mock(cfg), "day": day,
            "agent": cfg["realweb"]["model"] if web else agent["executor"],
            "start": {"kind": "url", "default": cfg["realweb"]["start_url"]} if web else {"kind": "site"}, "needs_key": bool(getattr(backend, "needs_key", lambda: False)()), "out": str(C.out_dir(cfg)), "error_types": list(ERROR_TYPES),
            "sites": backend.sites(),
            "tasks": [{"id": t["task_id"], "site": t["site"], "instruction": t["instruction"][:240],
                       "macros": t["macros"]} for t in backend.catalog()]}
    hub = Hub(asyncio.get_running_loop(), backend, info)
    hub.day_dir = d
    httpd = ThreadingHTTPServer((ccfg["host"], int(ccfg["port"])), make_handler(hub))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    url = f"http://{ccfg['host']}:{httpd.server_address[1]}"
    print(f"console: {url}  (day {day}, agent {info['agent']}, {cfg['backend']} backend; episodes -> {log})",
          flush=True)
    if ready:
        ready(hub, url)
    n = 0
    try:
        if hasattr(backend, "open"):            # the real web: one browser for the whole session, live from the start
            hub.screen = await backend.open(fps=ccfg["fps"])
            hub.emit("system", f"Browser open on {hub.screen.url or 'the start page'}. Type a task, or use the page "
                               "yourself first.")
        for msg in backend.warnings() if hasattr(backend, "warnings") else []:
            hub.emit("error", msg)
        with backend.servers() as bases:
            while True:
                hub.set_status("idle")
                task = await hub.requests.get()
                if task is None:
                    break
                done = [e["task_id"] for e in read_jsonl(log)]
                k = sum(1 for t in done if t == task["task_id"] or t.startswith(task["task_id"] + "~"))
                task = dict(task, task_id=task["task_id"] + (f"~{k + 1}" if k else ""))
                ep_dir = d / "console" / f"{len(done) + 1:03d}_{task['task_id']}"
                human = ConsoleHuman(hub, ep_dir, fps=ccfg["fps"], save_every=ccfg["save_every"])
                first = len(hub.events)
                hub.episode = {"task_id": task["task_id"], "site": task["site"], "instruction": task["instruction"],
                               "macros": task["macros"],
                               "graded_by": "mock" if C.is_mock(cfg) else
                               "human" if task.get("verifier") is None else "verifier",
                               "url": task.get("start_hint") if cfg["backend"] == "realweb" else
                               f"/sites/{task['site']}/"}
                hub.human = human
                hub.set_status("agent")
                hub.emit("task", task["instruction"], task_id=task["task_id"], site=task["site"])
                try:
                    ep = await backend.run_episode(task, agent, human, day, ep_dir, bases[0])
                except Exception as e:                  # keep the console up; the episode is not logged
                    hub.emit("error", f"{type(e).__name__}: {e}")
                    hub.human = hub.episode = None
                    continue
                ep.artifacts.update(console=str(ep_dir))
                _append(log, ep)
                n += 1
                ep_dir.mkdir(parents=True, exist_ok=True)
                with hub.lock:
                    chat = hub.events[first:]
                (ep_dir / "chat.jsonl").write_text("".join(json.dumps(e, default=str) + "\n" for e in chat))
                (ep_dir / "inputs.jsonl").write_text("".join(json.dumps(e) + "\n" for e in human.inputs))
                o = ep.outcome
                hub.emit("result", ("Passed" if o and o.passed else "Not passed") + f" ({o.grader if o else '-'})"
                         + (" after your takeover" if ep.takeover_step is not None else
                            " with your messages" if ep.interventions else " on its own")
                         + (f". Error: {ep.error}" if ep.error else ""),
                         passed=bool(o and o.passed), episode_id=ep.episode_id, autonomous=ep.autonomous)
                hub.human, hub.episode = None, None
        hub.emit("system", f"Day {day} ended: {n} episodes this session.")
        if n or log.exists():
            hand_to_night(cfg, saved_cfg, day, agent)
    finally:
        if hasattr(backend, "close"):
            await backend.close()
        httpd.shutdown()
    return n


def console_config(cfg, port=None, host=None):
    """-> (the console's config: its `console` settings, the person as the human; the experiment's config as loaded,
    for <out>/config.yaml)."""
    saved = copy.deepcopy(cfg)
    cfg["console"].update({k: v for k, v in (("port", port), ("host", host)) if v is not None})
    # the person reviews every `done`, however many times they correct the agent
    cfg["human"] = {**cfg["human"], "kind": "real", "max_messages": cfg["console"]["max_messages"]}
    return cfg, saved


def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m daynight.console")
    ap.add_argument("--config", required=True)
    ap.add_argument("--day", type=int, default=None, help="default: the experiment's current day (state.json), or 1")
    ap.add_argument("--model", default=None, help="mock: the mock world (no browser, server, GPU or API key)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--port", type=int, default=None)
    ap.add_argument("--host", default=None, help="default 127.0.0.1 (reach a lab machine through an ssh tunnel)")
    ap.add_argument("--probe", action="store_true", help="run the day's probe (no human) before opening the console")
    args = ap.parse_args(argv)
    cfg, saved = console_config(C.load(args.config, model=args.model, out=args.out), port=args.port, host=args.host)
    sp = C.out_dir(cfg) / "state.json"
    state = json.loads(sp.read_text()) if sp.exists() else None
    day = args.day or (state["day"] if state else 1)
    agent = state["agent"] if state else day0_agent(cfg)
    d = C.day_dir(cfg, day)
    if (d / "episodes.jsonl").exists() and not (d / "console.json").exists():
        raise SystemExit(f"{d}/episodes.jsonl was written by another day runner; pick another --day or --out")
    d.mkdir(parents=True, exist_ok=True)
    (d / "console.json").write_text(json.dumps({"by": "daynight.console", "agent": agent}, indent=1))
    backend = make_backend(cfg)
    if args.probe and not (d / "probe.jsonl").exists():
        from daynight.miniweb import MiniWebBackend        # the probe is MiniWeb's held-out tasks, whatever the day
        run_probe(cfg, day, backend if cfg["backend"] == "miniweb" else MiniWebBackend(cfg), agent)
    if C.is_mock(cfg):
        backend.step_delay = cfg["console"]["mock_step_delay"]
    try:
        asyncio.run(session(cfg, saved, day, backend, agent))
    except KeyboardInterrupt:
        print(f"\nconsole stopped; episodes so far are in {d / 'episodes.jsonl'} (End day hands them to the night)",
              flush=True)


if __name__ == "__main__":
    main()
