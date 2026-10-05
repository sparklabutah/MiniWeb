"""UI-TARS-1.5 and MolmoWeb as released, each in its own agent loop, on MiniWeb human tasks (EXPERIMENT_PLAN, RQ1;
2026-10-03). The counterpart of webmix/fara_runner.py for the two other own-loop baselines.

    uitars    UI-TARS-1.5-7B (ByteDance-Seed, Apache-2.0). Prompt and action parser are the released ones (pip `ui-tars`:
              ui_tars.prompt.COMPUTER_USE_DOUBAO, ui_tars.action_parser.parse_action_to_structure_output). The loop is
              OSWorld's UI-TARS-1.5 agent (mm_agents/uitars15_v1.py, run_multienv_uitars15_v1.py): system "You are a
              helpful assistant.", the prompt, then the full response history with the last 5 screenshots, temperature 0,
              top_p 0.9, max_tokens 500 (OSWorld's frequency_penalty 1 is off by default: see --frequency-penalty).
              A failed parse is retried up to 3 times at temperature 1,
              then the episode ends. Coordinates are in the Qwen2.5-VL smart_resize space of the screenshot and are mapped
              back as parsing_response_to_pyautogui_code does. The pyautogui calls become Playwright mouse and keyboard
              calls: type -> keyboard.type, plus Enter for a trailing \\n; scroll -> 5 wheel notches of 100 px at the
              point; wait -> 5 s. The answer is finished(content=...).
    molmoweb  MolmoWeb-4B / -8B (AllenAI, Apache-2.0): the released agent code itself (github.com/allenai/molmoweb:
              agent.multimodal_agent.MultimodalAgent, utils.envs SimpleEnv and its action executor,
              utils.eval_utils.episode.Episode) with its benchmark settings: "molmo_web_think" prompts, the last 10 steps
              as text, no past images, temperature 0.7, top_p 0.8, 1024 new tokens, a 1280x720 viewport. Only the
              predictor is swapped: their HF predictor's single user turn (prompt text + screenshot), sent to a vLLM
              OpenAI endpoint (the repo leaves vLLM to users). Serve it with causal attention on image tokens, as their
              HF predictor runs it (vLLM's Molmo2 default is a bidirectional prefix LM): --hf-overrides
              {"is_mm_prefix_lm":false}, which granite's ownloop.sh passes. The answer is read as their
              benchmarks.evaluate does: the last "[ANSWER] ..." message, else the last other message, else the last
              thought.
    fara7b    Fara-7B (Microsoft, MIT): the released previous-generation agent itself (github.com/microsoft/fara src/,
              fara.fara_7b: FaraAgent, its BrowserBB browser manager and PlaywrightController), as `fara-cli --fara-7b`
              and webeval's WebSurferSystem run it: 1440x900, the last 3 screenshots, temperature 0, single-tab mode,
              their page script. The browser manager is subclassed only to launch our Chromium with our context, in
              place of Firefox with an Edge user agent. The answer is theirs: the terminate step's thoughts. A parse or
              action error ends the episode, as in the released loop, and the task is re-run up to 5 times, as webeval
              (the harness of their published numbers) does by default.
    opencua   OpenCUA-7B (XLANG, MIT): OSWorld's OpenCUAAgent itself (xlang-ai/OSWorld mm_agents/opencua) with the
              OpenCUA-7B command of run_multienv_opencua.py (--coordinate_type qwen25 --use_old_sys_prompt; l2 CoT,
              action history, 3 images, temperature 0, top_p 0.9, max_tokens 2048) on a 1920x1080 page, and the loop of
              lib_run_single.run_single_example_opencua. Only call_llm is swapped (a vLLM endpoint), and the VM's
              `python -c` is a pyautogui-to-Playwright translation (run_pyautogui, literal calls only). The V1 prompt has
              no answer field: the answer is the terminate step's answer= if given, else its Thought + Action text.
              Serve with --trust-remote-code and a tokenizer dir whose tokenizer_config.json drops unk_token/pad_token
              (the remote TikTokenV3 code rejects them under transformers 5; it derives the same [UNK]/[PAD] itself).

Both run in the MiniWeb env (Playwright sync API, DATAGEN_CHROME) and start their own MiniWeb servers on --ports, as
webmix.evaluate does. The released code goes on sys.path through --path (default $OWNLOOP_PATH): a directory holding
`pip install --no-deps --target <dir> ui-tars==0.5.1`, and a clone of allenai/molmoweb. Setup per task is
webmix.evaluate.prepare_human's: /_admin/session-flags (logged out for a login task), then the start page, clipboard
allowed, with the task wrapper of webmix.harness.instruction. Tasks come from `python -m webmix.fara_rq1 prep`
({BASE} placeholders); grading is `python -m webmix.fara_rq1 grade --arm <name>`, from what this saves per task:

    <out>/<task_id>/session.json   {"base", "answer", "status", "rounds", "record": [...], "log": [...], "error", ...}
    <out>/<task_id>/steps.jsonl    one line per model call: raw output, parsed action, url, errors
    <out>/<task_id>/screens/       step_NN.png: the screenshot each step saw, plus the final one

    python -m webmix.ownloop_runner uitars --tasks <out>/tasks.json --out <out> --ports 8312,8313 \\
        --endpoint http://127.0.0.1:8694/v1 --model uitars15-7b --path $W/ownloop_pkgs
    python -m webmix.ownloop_runner molmoweb --tasks <out>/tasks.json --out <out> --ports 8314,8315 \\
        --endpoint http://127.0.0.1:8695/v1 --model molmoweb-4b --path $W/ownloop_pkgs:$W/molmoweb
    python -m webmix.ownloop_runner fara7b --tasks <out>/tasks.json --out <out> --ports 8312,8313 \\
        --endpoint http://127.0.0.1:8696/v1 --model fara-7b --path $W/fara7b_pkgs:$W/fara/src
    python -m webmix.ownloop_runner opencua --tasks <out>/tasks.json --out <out> --ports 8314,8315 \\
        --endpoint http://127.0.0.1:8697/v1 --model opencua-7b --path $W/opencua_pkgs:$W/osworld
"""
import argparse
import base64
import io
import json
import math
import os
import re
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

LAUNCH_ARGS = ["--disable-dev-shm-usage", "--no-first-run", "--disable-blink-features=AutomationControlled"]


def instruction(task_text, start_url):
    """Same wrapper as webmix.harness.instruction (our agents' task text) and webmix/fara_runner.py."""
    return f"You are interacting with a web application at {start_url}. Your task: {task_text}"


def launch_browser(pw):
    from datagen import config
    exe = config.CHROME if os.path.exists(config.CHROME) else None
    return pw.chromium.launch(headless=True, executable_path=exe, args=LAUNCH_ARGS)


def new_context(browser, width, height):
    """datagen.browser.new_context (clipboard granted, focus emulated, en-US / UTC) at this agent's viewport."""
    from datagen.browser import new_context as nc
    return nc(browser, viewport=(width, height))


def admin_entries(ctx, base, path):
    """A privileged /_admin endpoint, read as this browser's session (the context's cookies)."""
    r = ctx.request.get(base + path, timeout=30000)
    return (r.json() or {}).get("entries", []) or []


def png_b64(png):
    return "data:image/png;base64," + base64.b64encode(png).decode()


class EndpointError(RuntimeError):
    """The model server failed (not the model): the task is left unsaved, for a rerun."""


def chat(client, model, messages, **kw):
    """One chat completion; transport errors are retried (harness-level, not the agent's own retry)."""
    for attempt in range(3):
        try:
            r = client.chat.completions.create(model=model, messages=messages, **kw)
            return (r.choices[0].message.content or "").strip()
        except Exception as e:
            if attempt == 2:
                raise EndpointError(f"{type(e).__name__}: {str(e)[:200]}") from e
            time.sleep(5)


class Rec:
    """Per-task output: steps.jsonl lines and screenshots."""

    def __init__(self, ep):
        self.ep = ep
        (ep / "screens").mkdir(parents=True, exist_ok=True)
        self.f = open(ep / "steps.jsonl", "w")

    def step(self, **row):
        self.f.write(json.dumps(row, default=str) + "\n")
        self.f.flush()

    def shot(self, i, png):
        (self.ep / "screens" / f"step_{i:02d}.png").write_bytes(png)

    def close(self):
        self.f.close()


# ── UI-TARS-1.5 ───────────────────────────────────────────────────────────────────────────────────────────────────────

PW_KEYS = {"ctrl": "Control", "control": "Control", "shift": "Shift", "alt": "Alt", "option": "Alt", "cmd": "Meta",
           "command": "Meta", "win": "Meta", "meta": "Meta", "super": "Meta", "enter": "Enter", "return": "Enter",
           "esc": "Escape", "escape": "Escape", "tab": "Tab", "backspace": "Backspace", "delete": "Delete",
           "del": "Delete", "space": "Space", "up": "ArrowUp", "down": "ArrowDown", "left": "ArrowLeft",
           "right": "ArrowRight", "arrowup": "ArrowUp", "arrowdown": "ArrowDown", "arrowleft": "ArrowLeft",
           "arrowright": "ArrowRight", "pageup": "PageUp", "pagedown": "PageDown", "home": "Home", "end": "End",
           "insert": "Insert", "capslock": "CapsLock"}


def pw_key(k):
    k = k.strip()
    if k.lower() in PW_KEYS:
        return PW_KEYS[k.lower()]
    if re.fullmatch(r"[fF]\d{1,2}", k):
        return k.upper()
    return k


class UITars:
    """OSWorld mm_agents/uitars15_v1.py UITARSAgent.predict (infer_mode qwen25vl_normal), with the repo's computer-use
    prompt and an OpenAI-compatible endpoint."""
    MAX_PIXELS, MIN_PIXELS = 16384 * 28 * 28, 100 * 28 * 28

    def __init__(self, client, model, task, history_n=5, max_tokens=500, temperature=0.0, top_p=0.9,
                 frequency_penalty=0.0, language="English"):
        from ui_tars.prompt import COMPUTER_USE_DOUBAO
        self.client, self.model = client, model
        self.prompt = COMPUTER_USE_DOUBAO.format(language=language, instruction=task)
        self.history_n, self.max_tokens = history_n, max_tokens
        self.temperature, self.top_p, self.frequency_penalty = temperature, top_p, frequency_penalty
        self.images, self.responses = [], []

    def _image(self, png):
        """The agent's own resize to [min_pixels, max_pixels] (a no-op at our viewports) -> (png, height, width)."""
        from PIL import Image
        im = Image.open(io.BytesIO(png))
        if im.width * im.height > self.MAX_PIXELS:
            f = math.sqrt(self.MAX_PIXELS / (im.width * im.height))
            im = im.resize((int(im.width * f), int(im.height * f)))
        if im.width * im.height < self.MIN_PIXELS:
            f = math.sqrt(self.MIN_PIXELS / (im.width * im.height))
            im = im.resize((math.ceil(im.width * f), math.ceil(im.height * f)))
        if im.mode != "RGB":
            im = im.convert("RGB")
        buf = io.BytesIO()
        im.save(buf, format="PNG")
        return buf.getvalue(), im.height, im.width

    def predict(self, png):
        """-> (response text or None, parsed actions or None, [failed attempts])."""
        from ui_tars.action_parser import add_box_token, parse_action_to_structure_output
        self.images = (self.images + [png])[-self.history_n:]
        imgs = [self._image(b) for b in self.images]
        messages = [{"role": "system", "content": [{"type": "text", "text": "You are a helpful assistant."}]},
                    {"role": "user", "content": [{"type": "text", "text": self.prompt}]}]
        n = 0
        for i, resp in enumerate(self.responses):
            if i + self.history_n > len(self.responses):              # at most history_n screenshots in all
                messages.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": png_b64(imgs[n][0])}}]})
                n += 1
            messages.append({"role": "assistant", "content": [{"type": "text", "text": add_box_token(resp)}]})
        messages.append({"role": "user", "content": [{"type": "image_url", "image_url": {"url": png_b64(imgs[n][0])}}]})
        _, h, w = imgs[-1]
        temperature, fails = self.temperature, []
        for _ in range(3):
            text = chat(self.client, self.model, messages, max_tokens=self.max_tokens, temperature=temperature,
                        top_p=self.top_p, frequency_penalty=self.frequency_penalty)
            try:
                parsed = parse_action_to_structure_output(text, 1000, h, w, "qwen25vl", self.MAX_PIXELS, self.MIN_PIXELS)
            except Exception as e:                    # as OSWorld: resample at temperature 1
                fails.append({"raw": text, "parse_error": f"{type(e).__name__}: {str(e)[:200]}"})
                temperature = 1.0
                continue
            self.responses.append(text)
            return text, parsed, fails
        return None, None, fails


def _box_center(box, w, h):
    x1, y1, x2, y2 = eval(box) if isinstance(box, str) else box      # the parser's own "[x1, y1, x2, y2]" fractions
    return round((x1 + x2) / 2 * w, 3), round((y1 + y2) / 2 * h, 3)


def uitars_execute(page, act, w, h):
    """One parsed UI-TARS action on the page, as parsing_response_to_pyautogui_code would run it. -> (stop, answer, note)."""
    t, a = act.get("action_type"), act.get("action_inputs") or {}
    if t == "finished":
        return True, a.get("content", ""), ""
    if t == "call_user":
        return True, None, "call_user"
    if t in ("click", "left_single", "left_double", "right_single", "hover"):
        if not a.get("start_box"):
            return False, None, "no start_box"
        x, y = _box_center(a["start_box"], w, h)
        if t == "left_double":
            page.mouse.dblclick(x, y)
        elif t == "right_single":
            page.mouse.click(x, y, button="right")
        elif t == "hover":
            page.mouse.move(x, y)
        else:
            page.mouse.click(x, y)
    elif t in ("drag", "select"):
        if not (a.get("start_box") and a.get("end_box")):
            return False, None, "drag without both boxes"
        sx, sy = _box_center(a["start_box"], w, h)
        ex, ey = _box_center(a["end_box"], w, h)
        page.mouse.move(sx, sy)
        page.mouse.down()
        page.mouse.move(ex, ey, steps=20)                              # pyautogui.dragTo(duration=1.0)
        page.mouse.up()
    elif t == "hotkey":
        keys = (a.get("key") or a.get("hotkey") or "").split()
        if keys:
            page.keyboard.press("+".join(pw_key(k) for k in keys))
    elif t in ("press", "keydown", "keyup"):
        k = pw_key(a.get("key") or a.get("press") or "")
        if k:
            (page.keyboard.up if t == "keyup" else page.keyboard.down)(k)
            if t == "press":
                page.keyboard.up(k)
    elif t == "type":
        content = a.get("content", "")
        enter = content.endswith("\n") or content.endswith("\\n")
        text = content.rstrip("\\n").rstrip("\n") if enter else content
        if text:
            page.keyboard.type(text)
        if enter:
            page.keyboard.press("Enter")
    elif t == "scroll":
        d = (a.get("direction") or "").lower()
        if a.get("start_box"):
            page.mouse.move(*_box_center(a["start_box"], w, h))
        dx = -500 if "left" in d else 500 if "right" in d else 0
        dy = -500 if "up" in d else 500 if "down" in d else 0
        page.mouse.wheel(dx, dy)
    elif t == "wait":
        time.sleep(5)
    else:
        return False, None, f"unrecognized action {t}"
    return False, None, ""


def settle(ctx, page):
    """-> the active page (a click may open a tab: follow the newest) after its DOM is loaded, plus a short buffer."""
    pages = [p for p in ctx.pages if not p.is_closed()]
    page = pages[-1] if pages else page
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    time.sleep(1.0)
    return page


def run_uitars(t, base, args, ep):
    from openai import OpenAI
    from playwright.sync_api import sync_playwright
    start = t["start"].replace("{BASE}", base)
    prompt = t["prompt"].replace("{BASE}", base)
    flags = base + "/_admin/session-flags" + ("?logout=1" if t["needs_login"] else "")
    res = {"task_id": t["task_id"], "base": base, "answer": None, "status": None, "rounds": 0, "error": None,
           "record": [], "log": [], "seconds": None, "parse_fails": 0, "action_errors": 0}
    t0, rec = time.time(), Rec(ep)
    client = OpenAI(base_url=args.endpoint, api_key="not-needed", timeout=300)
    agent = UITars(client, args.model, instruction(prompt, start), frequency_penalty=args.frequency_penalty)
    with sync_playwright() as pw:
        browser = launch_browser(pw)
        ctx = new_context(browser, args.width, args.height)
        try:
            page = ctx.new_page()
            page.goto(flags, wait_until="domcontentloaded", timeout=60000)
            page.goto(start, wait_until="domcontentloaded", timeout=60000)
            time.sleep(1.0)
            for i in range(1, args.max_steps + 1):
                if time.time() - t0 > args.timeout:
                    res["status"] = "timeout"
                    break
                png = page.screenshot(type="png")
                rec.shot(i, png)
                text, parsed, fails = agent.predict(png)
                res["rounds"] = i
                res["parse_fails"] += sum("parse_error" in f for f in fails)
                if parsed is None:
                    rec.step(step=i, url=page.url, raw=None, fails=fails)
                    res["status"] = "parse_error"                  # OSWorld: no parsable response in 3 tries ends it
                    break
                stop, notes = False, []
                for act in parsed:
                    try:
                        stop, answer, note = uitars_execute(page, act, args.width, args.height)
                    except Exception as e:
                        stop, answer, note = False, None, f"{type(e).__name__}: {str(e)[:200]}"
                    res["action_errors"] += bool(note) and note != "call_user"
                    notes.append(note)
                    if stop:
                        res["answer"], res["status"] = answer, "finished" if note != "call_user" else "call_user"
                        break
                rec.step(step=i, url=page.url, raw=text, actions=[{k: v for k, v in a.items() if k != "text"} for a in parsed],
                         notes=notes, fails=fails)
                if stop:
                    break
                page = settle(ctx, page)
            else:
                res["status"] = "max_steps"
            try:
                rec.shot(res["rounds"] + 1, settle(ctx, page).screenshot(type="png"))
            except Exception:
                pass
        except Exception as e:                   # a harness error still keeps whatever the session did
            res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            if isinstance(e, EndpointError):
                res["status"] = "endpoint_error"
        try:
            res["record"] = admin_entries(ctx, base, "/_admin/record")
            res["log"] = admin_entries(ctx, base, "/_admin/log")
        except Exception as e:
            res["error"] = (res["error"] or "") + f" | backend read: {type(e).__name__}: {str(e)[:200]}"
        browser.close()
    rec.close()
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ── MolmoWeb ──────────────────────────────────────────────────────────────────────────────────────────────────────────

class VllmPredictor:
    """Their HFActionPredictor's request (one user turn: prompt text, then the screenshot(s); sampling with
    temperature / top_p; max_new_tokens 1024), sent to an OpenAI-compatible endpoint. Stops the episode at the task
    deadline: an exception here is the Episode's ACTION_PREDICTION_ERROR, which ends it."""

    def __init__(self, client, model, temperature, top_p, deadline, max_tokens=1024):
        self.client, self.model, self.deadline = client, model, deadline
        self.temperature, self.top_p, self.max_tokens = temperature, top_p, max_tokens
        self.failed = False

    def predict(self, prompt, image_np, past_actions=None, **kw):
        from PIL import Image
        if time.time() > self.deadline:
            raise TimeoutError("task timeout")
        content = [{"type": "text", "text": prompt}]
        for im in (image_np if isinstance(image_np, list) else [image_np]):
            buf = io.BytesIO()
            Image.fromarray(im.astype("uint8")).convert("RGB").save(buf, format="PNG")
            content.append({"type": "image_url", "image_url": {"url": png_b64(buf.getvalue())}})
        try:
            text = chat(self.client, self.model, [{"role": "user", "content": content}], max_tokens=self.max_tokens,
                        temperature=self.temperature, top_p=self.top_p)
        except EndpointError:
            self.failed = True
            raise
        return text or None


def molmoweb_answer(interactions):
    """benchmarks.evaluate.read_trajectory's answer: the last "[ANSWER] ..." message, else the last message that is
    not [EXIT], else the last thought."""
    last_answer = last_msg = last_thought = None
    for it in interactions:
        if not it.action:
            continue
        act = it.action["action_output"].action
        msg = getattr(act, "msg", None)
        if msg is not None:
            if "[ANSWER]" in msg:
                last_answer = msg[9:]
            elif "[EXIT]" not in msg:
                last_msg = msg
        if it.action.get("thought"):
            last_thought = it.action["thought"]
    return last_answer if last_answer is not None else last_msg if last_msg is not None else last_thought


def run_molmoweb(t, base, args, ep):
    import numpy as np
    from openai import OpenAI
    from PIL import Image
    from agent.actions import SendMsgToUser
    from agent.multimodal_agent import MultimodalAgent
    from utils.envs.browser_env import SimpleEnv, _start_playwright
    from utils.eval_utils.episode import Episode

    start = t["start"].replace("{BASE}", base)
    prompt = t["prompt"].replace("{BASE}", base)
    flags = base + "/_admin/session-flags" + ("?logout=1" if t["needs_login"] else "")

    class MiniWebEnv(SimpleEnv):
        """Their local-Chromium env with our Chromium build and context, opening the session flags first."""

        def _launch(self):
            self.playwright = _start_playwright()
            self.browser = launch_browser(self.playwright)
            self.context = new_context(self.browser, self.viewport_width, self.viewport_height)
            self.page = self.context.new_page()

        def _navigate_to_start(self, url, goal):
            self.page.goto(flags, wait_until="domcontentloaded", timeout=60000)
            self.page.goto(url, wait_until="domcontentloaded", timeout=60000)
            time.sleep(1.0)
            return goal

    res = {"task_id": t["task_id"], "base": base, "answer": None, "status": None, "rounds": 0, "error": None,
           "record": [], "log": [], "seconds": None, "parse_fails": 0, "action_errors": 0}
    t0, rec = time.time(), Rec(ep)
    env = MiniWebEnv(start_url=start, goal=instruction(prompt, start), viewport_width=args.width,
                     viewport_height=args.height)
    agent = MultimodalAgent(endpoint_or_checkpoint=args.endpoint, inference_mode="fastapi", system_message="molmo_web_think",
                            max_past_steps=args.max_past_steps, max_past_images=0,
                            sampling_temperature=args.temperature, sampling_top_p=args.top_p)
    agent.predictor = VllmPredictor(OpenAI(base_url=args.endpoint, api_key="not-needed", timeout=300), args.model,
                                    args.temperature, args.top_p, t0 + args.timeout)
    episode = Episode(env=env, agent=agent, eps_name=t["task_id"])
    try:
        inters, _ = episode.run_episode(max_steps=args.max_steps)
    except Exception as e:
        inters = episode.interactions
        res["error"] = f"{type(e).__name__}: {str(e)[:300]}"

    def png(arr):
        buf = io.BytesIO()
        Image.fromarray(np.asarray(arr).astype("uint8")).save(buf, format="PNG")
        return buf.getvalue()
    for i, it in enumerate(inters, 1):
        obs = it.state.get("obs") or {}
        if obs.get("screenshot") is not None:
            rec.shot(i, png(obs["screenshot"]))
        a = it.action or {}
        thought = a.get("thought") or ""
        res["parse_fails"] += thought.startswith("Could not parse predicted action")
        nxt = (it.next_state or {}).get("obs") or {}
        res["action_errors"] += bool(nxt.get("last_action_error"))
        rec.step(step=i, url=obs.get("url"), raw=it.raw_output, action=a.get("action"), action_str=a.get("action_str"),
                 thought=thought, error=it.error, action_error=nxt.get("last_action_error"))
    if inters and (inters[-1].next_state or {}).get("obs", {}).get("screenshot") is not None:
        rec.shot(len(inters) + 1, png(inters[-1].next_state["obs"]["screenshot"]))
    res["rounds"] = len(inters)
    res["answer"] = molmoweb_answer(inters)
    last = inters[-1] if inters else None
    if last is None:
        res["status"] = "no_steps"
    elif last.error:
        err = json.dumps(last.error)
        res["status"] = "timeout" if "task timeout" in err else "endpoint_error" if "EndpointError" in err or \
            agent.predictor.failed else "error"
        res["error"] = res["error"] or json.dumps(last.error)[:300]
    elif last.action and isinstance(last.action["action_output"].action, SendMsgToUser) \
            and (last.action["action_output"].action.msg or "").startswith("[EXIT]"):
        res["status"] = "exit"
    else:
        res["status"] = "max_steps"
    try:
        if env.context is not None:
            res["record"] = admin_entries(env.context, base, "/_admin/record")
            res["log"] = admin_entries(env.context, base, "/_admin/log")
    except Exception as e:
        res["error"] = (res["error"] or "") + f" | backend read: {type(e).__name__}: {str(e)[:200]}"
    try:
        env.close()
    except Exception:
        pass
    rec.close()
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ── Fara-7B (added 2026-10-03) ────────────────────────────────────────────────────────────────────────────────────────

_IMPORT_LOCK = threading.Lock()


def _fara_package():
    """Register the `fara` package of the --path clone (github.com/microsoft/fara src/) without running its __init__.py,
    which imports the Fara1.5 agent and environment stacks and their extra dependencies. fara.fara_7b and
    fara.qwen_helpers are then imported unchanged."""
    import importlib.machinery
    import importlib.util
    with _IMPORT_LOCK:
        if "fara" in sys.modules:
            return
        for p in sys.path:
            d = Path(p or ".") / "fara"
            if (d / "fara_7b" / "fara_agent.py").is_file():
                spec = importlib.machinery.ModuleSpec("fara", None, is_package=True)
                spec.submodule_search_locations = [str(d)]
                sys.modules["fara"] = importlib.util.module_from_spec(spec)
                return
        raise ImportError("no fara/fara_7b on sys.path: put the microsoft/fara src/ dir on --path")


class _ThreadStdout:
    """sys.stdout that sends a worker thread's writes to that thread's task file when one is set. The Fara-7B agent
    print()s every thought, action and observation. Other writes go to the real stdout."""

    def __init__(self, base):
        self.base, self.local = base, threading.local()

    def _f(self):
        return getattr(self.local, "f", None) or self.base

    def write(self, s):
        return self._f().write(s)

    def flush(self):
        return self._f().flush()

    def __getattr__(self, k):
        return getattr(self.base, k)


def _thread_stdout():
    with _IMPORT_LOCK:
        if not isinstance(sys.stdout, _ThreadStdout):
            sys.stdout = _ThreadStdout(sys.stdout)
        return sys.stdout


def fara7b_parse(agent, text):
    """-> (ok, tool-call dict): their _parse_thoughts_and_action, plus the keys their generate_model_call and run() read
    next (a response without them ends the released loop with an exception, as a parse failure does)."""
    try:
        _, action = agent._parse_thoughts_and_action(text)
        return isinstance(action.get("arguments"), dict) and "action" in action["arguments"], action
    except Exception:
        return False, None


def run_fara7b(t, base, args, ep):
    """One task, with webeval's error retries. Their eval loop (webeval core.run_eval_single_example) re-runs a task
    whose episode raised, which leaves no evaluable trajectory, up to --max_error_task_retries times (default 5). The
    same here: an attempt that ended with status error / parse_error is moved to <ep>/error_attempt_N/, and the task
    runs again in a fresh browser context (a fresh MiniWeb session). The last attempt is the one graded."""
    import asyncio
    import shutil
    t0, failed = time.time(), []
    while True:
        res = asyncio.run(_fara7b(t, base, args, ep))
        if res["status"] not in ("error", "parse_error") or len(failed) >= args.fara7b_error_retries:
            break
        keep = ep / f"error_attempt_{len(failed) + 1}"
        keep.mkdir()
        for p in list(ep.iterdir()):
            if not p.name.startswith("error_attempt_"):
                shutil.move(str(p), str(keep / p.name))
        (keep / "attempt.json").write_text(json.dumps(res, default=str))
        failed.append({k: res[k] for k in ("status", "rounds", "error", "seconds", "parse_fails", "action_errors")})
    res["error_attempts"] = failed
    res["parse_fails"] += sum(f["parse_fails"] for f in failed)
    res["action_errors"] += sum(f["action_errors"] for f in failed)
    res["seconds"] = round(time.time() - t0, 1)
    return res


async def _fara7b(t, base, args, ep):
    """Fara-7B's own agent (fara.fara_7b.FaraAgent) and browser manager (BrowserBB, PlaywrightController) as
    `fara-cli --fara-7b` and webeval's WebSurferSystem run it: 1440x900, the last 3 screenshots, temperature 0. Their
    browser manager is subclassed only to launch our Chromium build with our context (clipboard granted, focus emulated,
    en-US/UTC), in place of Firefox with an Edge user agent."""
    import asyncio
    import logging
    import openai
    from datagen import config
    _fara_package()
    from fara.fara_7b.browser.browser_bb import BrowserBB
    from fara.fara_7b.fara_agent import FaraAgent
    from fara.fara_7b.fara_types import AssistantMessage

    if (args.width, args.height) != (1440, 900):
        raise ValueError("FaraAgent maps coordinates to its fixed 1440x900 viewport")
    start = t["start"].replace("{BASE}", base)
    prompt = t["prompt"].replace("{BASE}", base)
    flags = base + "/_admin/session-flags" + ("?logout=1" if t["needs_login"] else "")
    res = {"task_id": t["task_id"], "base": base, "answer": None, "status": None, "rounds": 0, "error": None,
           "record": [], "log": [], "seconds": None, "parse_fails": 0, "action_errors": 0}
    t0, rec = time.time(), Rec(ep)
    fdir = ep / "fara7b"                       # their downloads folder: screenshot{n}.png, web_surfer.log, prints
    fdir.mkdir(parents=True, exist_ok=True)
    log = logging.getLogger(f"ownloop.fara7b.{t['task_id']}")
    log.setLevel(logging.DEBUG)                # webeval's level: their Thought/Action/Observation traces are DEBUG
    log.propagate = False
    handler = logging.FileHandler(fdir / "web_surfer.log")
    log.addHandler(handler)
    out = _thread_stdout()
    out.local.f = open(fdir / "stdout.log", "w")

    class MiniWebBB(BrowserBB):
        async def _init_regular_browser(self, channel="chromium"):
            exe = config.CHROME if os.path.exists(config.CHROME) else None
            self.browser = await self._playwright.chromium.launch(headless=True, executable_path=exe, args=LAUNCH_ARGS)
            ctx = self._context = await self.browser.new_context(
                viewport={"width": self._viewport_width, "height": self._viewport_height}, device_scale_factor=1,
                locale="en-US", timezone_id="UTC", accept_downloads=True)
            try:
                await ctx.grant_permissions(["clipboard-read", "clipboard-write"])
            except Exception:
                pass

            async def focus(page):                 # datagen.browser._focus
                try:
                    s = await ctx.new_cdp_session(page)
                    await s.send("Emulation.setFocusEmulationEnabled", {"enabled": True})
                except Exception:
                    pass
            ctx.on("page", focus)
            self._page = await ctx.new_page()

    bm = MiniWebBB(viewport_height=args.height, viewport_width=args.width, headless=True, page_script_path=None,
                   browser_channel="chromium", browser_data_dir=None, downloads_folder=str(fdir), to_resize_viewport=True,
                   single_tab_mode=True, animate_actions=False, use_browser_base=False, logger=log)
    agent = FaraAgent(browser_manager=bm, client_config={"model": args.model, "base_url": args.endpoint,
                                                         "api_key": "not-needed"},
                      start_page=flags, downloads_folder=str(fdir), save_screenshots=True, max_rounds=args.max_steps,
                      logger=log)
    answer = None
    try:
        await agent.initialize()                       # browser up at the session-flags page (their start_page)
        await agent._page.goto(start, wait_until="domcontentloaded", timeout=60000)
        await asyncio.sleep(1.0)
        answer, _, _ = await asyncio.wait_for(agent.run(instruction(prompt, start)),
                                              timeout=max(60.0, args.timeout - (time.time() - t0)))
    except (asyncio.TimeoutError, TimeoutError) as e:
        res["status"], res["error"] = "timeout", f"{type(e).__name__}: {str(e)[:200]}"
    except (openai.APIConnectionError, openai.InternalServerError, openai.NotFoundError) as e:
        res["status"], res["error"] = "endpoint_error", f"{type(e).__name__}: {str(e)[:300]}"
    except Exception as e:                    # the released loop has no recovery: a parse or action error ends it
        res["status"], res["error"] = "error", f"{type(e).__name__}: {str(e)[:300]}"
    responses = [m.content for m in agent._chat_history if isinstance(m, AssistantMessage)]
    res["rounds"] = len(responses)
    parsed = [fara7b_parse(agent, r) for r in responses]
    for i, (text, (ok, action)) in enumerate(zip(responses, parsed), 1):
        rec.step(step=i, raw=text, action=(action or {}).get("arguments") if ok else None, parse_error=not ok)
    last_ok, last = parsed[-1] if parsed else (True, None)
    if res["status"] is None:
        if last_ok and last and last["arguments"]["action"] in ("terminate", "stop"):
            res["status"], res["answer"] = "terminate", answer       # their final answer: the terminate step's thoughts
        else:
            res["status"] = "max_steps"
    elif res["status"] == "error" and responses and not last_ok:
        res["status"], res["parse_fails"] = "parse_error", 1
    elif res["status"] == "error":
        res["action_errors"] = 1
    for png in fdir.glob("screenshot*.png"):            # screenshot{n}: after n actions = what step n+1 saw
        m = re.fullmatch(r"screenshot(\d+)\.png", png.name)
        if m:
            os.replace(png, ep / "screens" / f"step_{int(m.group(1)) + 1:02d}.png")
    try:
        if bm.context is not None:
            for key, path in (("record", "/_admin/record"), ("log", "/_admin/log")):
                r = await bm.context.request.get(base + path, timeout=30000)
                res[key] = ((await r.json()) or {}).get("entries", []) or []
    except Exception as e:
        res["error"] = (res["error"] or "") + f" | backend read: {type(e).__name__}: {str(e)[:200]}"
    for close in (agent.close, getattr(bm.browser, "close", None),         # their client is left open: closed here so
                  getattr(agent._openai_client, "close", None)):           # GC does not close it after the loop ends
        try:
            if close is not None:
                await close()
        except Exception:
            pass
    out.local.f.close()
    out.local.f = None
    log.removeHandler(handler)
    handler.close()
    rec.close()
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ── OpenCUA (added 2026-10-03) ────────────────────────────────────────────────────────────────────────────────────────

PY_KEYS = {**PW_KEYS, "ctrlleft": "Control", "ctrlright": "Control", "shiftleft": "Shift", "shiftright": "Shift",
           "altleft": "Alt", "altright": "Alt", "winleft": "Meta", "winright": "Meta", "pgup": "PageUp",
           "pgdn": "PageDown", "prtsc": "PrintScreen", "prtscr": "PrintScreen", "printscreen": "PrintScreen",
           "\n": "Enter", "\r": "Enter", "\t": "Tab", " ": "Space"}


def py_key(k):
    """A pyautogui key name -> a Playwright key."""
    k = str(k)
    if k.lower() in PY_KEYS:
        return PY_KEYS[k.lower()]
    if re.fullmatch(r"[fF]\d{1,2}", k):
        return k.upper()
    return k


class PyAutoGUI:
    """The pyautogui functions OSWorld's VM runs (`python -c "import pyautogui; ...; <code>"`), on a Playwright page of
    the same screen size, with the mouse position tracked as pyautogui tracks it. One scroll click is 100 px, as in the
    UI-TARS translation above."""
    SCROLL_PX = 100
    API = {"click", "doubleClick", "tripleClick", "rightClick", "middleClick", "moveTo", "moveRel", "move", "dragTo",
           "dragRel", "drag", "mouseDown", "mouseUp", "scroll", "vscroll", "hscroll", "write", "typewrite", "press",
           "hotkey", "keyDown", "keyUp", "sleep"}

    def __init__(self, page):
        self.page, self.pos = page, (0.0, 0.0)          # Playwright's mouse starts at (0, 0)

    def _xy(self, x, y):
        if isinstance(x, (tuple, list)):
            x, y = x[0], x[1]
        if x is None or y is None:
            return self.pos
        return float(x), float(y)

    @staticmethod
    def _button(b):
        return {"right": "right", "secondary": "right", "middle": "middle"}.get(str(b).lower(), "left")

    def moveTo(self, x=None, y=None, duration=0.0, *a, **kw):
        self.pos = self._xy(x, y)
        self.page.mouse.move(*self.pos, steps=max(1, int(float(duration or 0) * 20)))

    def moveRel(self, xOffset=0, yOffset=0, *a, **kw):
        self.moveTo(self.pos[0] + float(xOffset or 0), self.pos[1] + float(yOffset or 0))
    move = moveRel

    def click(self, x=None, y=None, clicks=1, interval=0.0, button="left", *a, **kw):
        self.moveTo(x, y)
        self.page.mouse.click(*self.pos, button=self._button(button), click_count=max(1, int(clicks)))

    def doubleClick(self, x=None, y=None, interval=0.0, button="left", *a, **kw):
        self.click(x, y, 2, button=button)

    def tripleClick(self, x=None, y=None, interval=0.0, button="left", *a, **kw):
        self.click(x, y, 3, button=button)

    def rightClick(self, x=None, y=None, *a, **kw):
        self.click(x, y, button="right")

    def middleClick(self, x=None, y=None, *a, **kw):
        self.click(x, y, button="middle")

    def mouseDown(self, x=None, y=None, button="left", *a, **kw):
        if x is not None:
            self.moveTo(x, y)
        self.page.mouse.down(button=self._button(button))

    def mouseUp(self, x=None, y=None, button="left", *a, **kw):
        if x is not None:
            self.moveTo(x, y)
        self.page.mouse.up(button=self._button(button))

    def dragTo(self, x=None, y=None, duration=0.0, button="left", *a, **kw):
        self.page.mouse.down(button=self._button(button))
        self.pos = self._xy(x, y)
        self.page.mouse.move(*self.pos, steps=20)
        self.page.mouse.up(button=self._button(button))

    def dragRel(self, xOffset=0, yOffset=0, duration=0.0, button="left", *a, **kw):
        self.dragTo(self.pos[0] + float(xOffset or 0), self.pos[1] + float(yOffset or 0), button=button)
    drag = dragRel

    def scroll(self, clicks, x=None, y=None, *a, **kw):                  # positive clicks scroll up
        if x is not None and y is not None:
            self.moveTo(x, y)
        self.page.mouse.wheel(0, -float(clicks) * self.SCROLL_PX)
    vscroll = scroll

    def hscroll(self, clicks, x=None, y=None, *a, **kw):                 # positive clicks scroll right
        if x is not None and y is not None:
            self.moveTo(x, y)
        self.page.mouse.wheel(float(clicks) * self.SCROLL_PX, 0)

    def write(self, message, interval=0.0, *a, **kw):
        if isinstance(message, (list, tuple)):                            # typewrite(["a", "enter"]): key names
            for k in message:
                self.press(k)
            return
        parts = str(message).split("\n")                                 # pyautogui types "\n" as Enter
        for i, part in enumerate(parts):
            if part:
                self.page.keyboard.type(part)
            if i < len(parts) - 1:
                self.page.keyboard.press("Enter")
    typewrite = write

    def press(self, keys, presses=1, interval=0.0, *a, **kw):
        for _ in range(max(1, int(presses))):
            for k in (keys if isinstance(keys, (list, tuple)) else [keys]):
                self.page.keyboard.press(py_key(k))

    def hotkey(self, *keys, **kw):
        keys = [py_key(k) for k in (keys[0] if len(keys) == 1 and isinstance(keys[0], (list, tuple)) else keys)]
        for k in keys:
            self.page.keyboard.down(k)
        for k in reversed(keys):
            self.page.keyboard.up(k)

    def keyDown(self, key, *a, **kw):
        self.page.keyboard.down(py_key(key))

    def keyUp(self, key, *a, **kw):
        self.page.keyboard.up(py_key(key))

    def sleep(self, seconds=0, *a, **kw):
        time.sleep(min(max(float(seconds), 0.0), 60.0))


class UnsupportedCode(Exception):
    """A statement that the `pyautogui` + `time` namespace of OSWorld's VM would not run (e.g. computer.triple_click:
    their prompt lists it, but their loop passes it to the VM's python, where it is a NameError)."""


def run_pyautogui(code, gui):
    """OpenCUA's code, statement by statement, as `python -c` runs it: the first failing statement stops the rest.
    Model output is never exec'd: only literal-argument calls of pyautogui.* and time.sleep, `import pyautogui|time`,
    `pass`, and `for _ in range(<int>):` loops over those statements run."""
    import ast

    def call(c):
        f = c.func
        if not (isinstance(f, ast.Attribute) and isinstance(f.value, ast.Name)):
            raise UnsupportedCode(f"unsupported call: {ast.unparse(c)[:120]}")
        mod, name = f.value.id, f.attr
        args = [ast.literal_eval(a) for a in c.args]
        kwargs = {k.arg: ast.literal_eval(k.value) for k in c.keywords if k.arg}
        if mod == "time" and name == "sleep":
            return gui.sleep(*args, **kwargs)
        if mod == "pyautogui" and name in gui.API:
            return getattr(gui, name)(*args, **kwargs)
        raise UnsupportedCode(f"{mod}.{name} is not defined")

    def stmt(node):
        if isinstance(node, ast.Import) and {a.name for a in node.names} <= {"pyautogui", "time"}:
            return
        if isinstance(node, ast.Pass):
            return
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
            return call(node.value)
        if (isinstance(node, ast.For) and not node.orelse and isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name) and node.iter.func.id == "range"):
            n = range(*[int(ast.literal_eval(a)) for a in node.iter.args])
            for _ in range(min(len(n), 100)):
                for s in node.body:
                    stmt(s)
            return
        raise UnsupportedCode(f"unsupported statement: {ast.unparse(node)[:120]}")

    for node in ast.parse(code).body:
        stmt(node)


def chat_full(client, model, messages, **kw):
    """chat() that also returns the finish reason; a 400 (e.g. a prompt over the context) is the request's own error,
    not an endpoint failure."""
    import openai
    for attempt in range(3):
        try:
            r = client.chat.completions.create(model=model, messages=messages, **kw)
            return r.choices[0].message.content or "", r.choices[0].finish_reason
        except openai.BadRequestError:
            raise
        except Exception as e:
            if attempt == 2:
                raise EndpointError(f"{type(e).__name__}: {str(e)[:200]}") from e
            time.sleep(5)


_OPENCUA = {}


def opencua_agent_class():
    """Their OpenCUAAgent (xlang-ai/OSWorld mm_agents/opencua) with call_llm pointed at a vLLM endpoint. Everything else
    is theirs: the prompt, the history, the retries, the parsing and the coordinate projection."""
    with _IMPORT_LOCK:
        if "cls" in _OPENCUA:
            return _OPENCUA["cls"]
        from loguru import logger
        logger.remove()                      # their module logs every prompt and response through loguru
        from mm_agents.opencua.opencua_agent import OpenCUAAgent

        class VllmOpenCUAAgent(OpenCUAAgent):
            """Their call_llm posts to their hosted endpoint and re-posts the same payload (up to 20 times) until
            finish_reason == "stop". At temperature 0 a re-post repeats the same output, so here a non-"stop" finish
            returns None at once; their predict() then retries (5 calls in all, temperature >= 0.2 after the first)."""

            def __init__(self, client, deadline, **kw):
                super().__init__(**kw)
                self.client, self.deadline = client, deadline
                self.calls, self.endpoint_failed, self.timed_out = [], None, False

            def call_llm(self, payload, model):
                if self.endpoint_failed:
                    raise EndpointError(self.endpoint_failed)
                if time.time() > self.deadline:
                    self.timed_out = True
                    raise TimeoutError("task timeout")
                try:
                    text, finish = chat_full(self.client, **payload)
                except EndpointError as e:
                    self.endpoint_failed = str(e)
                    raise
                except Exception as e:
                    self.calls.append({"error": f"{type(e).__name__}: {str(e)[:300]}",
                                       "temperature": payload.get("temperature")})
                    raise
                self.calls.append({"raw": text, "finish_reason": finish, "temperature": payload.get("temperature")})
                return text if finish == "stop" else None

        _OPENCUA["cls"] = VllmOpenCUAAgent
        return VllmOpenCUAAgent


def opencua_answer(cot):
    """The answer of a terminate step: its answer= argument (their V2 prompt's terminate has one) if given, else the
    step's Thought and Action text. OpenCUA-7B's V1 prompt has no answer field, and OSWorld grades no text answers."""
    import ast
    code = cot.get("original_code") or ""
    try:
        for node in ast.walk(ast.parse(code)):
            if isinstance(node, ast.Call) and getattr(node.func, "attr", None) == "terminate":
                for k in node.keywords:
                    if k.arg == "answer":
                        return str(ast.literal_eval(k.value))
    except Exception:
        m = re.search(r"answer\s*=\s*('''|\"\"\"|'|\")(.*?)\1", code, re.S)
        if m:
            return m.group(2)
    return "\n".join(p for p in (cot.get("thought"), cot.get("action")) if p) or None


def front_page(ctx, page):
    """The page on screen: a click may open a tab, which a desktop browser brings to the front."""
    pages = [p for p in ctx.pages if not p.is_closed()]
    page = pages[-1] if pages else page
    try:
        page.wait_for_load_state("domcontentloaded", timeout=5000)
    except Exception:
        pass
    return page


def run_opencua(t, base, args, ep):
    """OSWorld's OpenCUA-7B command (run_multienv_opencua.py --coordinate_type qwen25 --use_old_sys_prompt, the
    defaults: cot_level l2, action_history, 3 images, temperature 0, top_p 0.9, max_tokens 2048) and loop
    (lib_run_single.run_single_example_opencua) on a 1920x1080 page: predict, then each returned action through
    env.step semantics (DONE / FAIL end the episode, WAIT sleeps, pyautogui code runs), each step followed by
    sleep_after_execution (5 s)."""
    from openai import OpenAI
    from playwright.sync_api import sync_playwright
    start = t["start"].replace("{BASE}", base)
    prompt = t["prompt"].replace("{BASE}", base)
    flags = base + "/_admin/session-flags" + ("?logout=1" if t["needs_login"] else "")
    res = {"task_id": t["task_id"], "base": base, "answer": None, "status": None, "rounds": 0, "error": None,
           "record": [], "log": [], "seconds": None, "parse_fails": 0, "action_errors": 0}
    t0, rec = time.time(), Rec(ep)
    agent = opencua_agent_class()(
        OpenAI(base_url=args.endpoint, api_key="not-needed", timeout=300), t0 + args.timeout,
        model=args.model, history_type="action_history", max_steps=args.max_steps, max_image_history_length=3,
        platform="ubuntu", max_tokens=args.opencua_max_tokens, top_p=0.9, temperature=0.0, action_space="pyautogui",
        observation_type="screenshot", cot_level="l2", screen_size=(args.width, args.height), coordinate_type="qwen25",
        use_old_sys_prompt=True)
    task = instruction(prompt, start)
    pause = args.opencua_pause
    with sync_playwright() as pw:
        browser = launch_browser(pw)
        ctx = new_context(browser, args.width, args.height)
        try:
            page = ctx.new_page()
            page.goto(flags, wait_until="domcontentloaded", timeout=60000)
            page.goto(start, wait_until="domcontentloaded", timeout=60000)
            time.sleep(1.0)
            gui = PyAutoGUI(page)
            for i in range(1, args.max_steps + 1):
                if time.time() - t0 > args.timeout:
                    res["status"] = "timeout"
                    break
                png = page.screenshot(type="png")
                rec.shot(i, png)
                n_actions, n_calls = len(agent.actions), len(agent.calls)
                response, actions, cot = agent.predict(task, {"screenshot": png})
                calls, accepted = agent.calls[n_calls:], len(agent.actions) > n_actions
                res["rounds"] = i
                res["parse_fails"] += len(calls) - accepted
                row = {"step": i, "url": page.url, "raw": response if accepted else None,
                       "attempts": calls if len(calls) != 1 or not accepted else None, "action": cot.get("action"),
                       "code": cot.get("original_code"), "executed": actions}
                if agent.endpoint_failed or agent.timed_out or not accepted:
                    rec.step(**row, error=response)
                    res["status"] = "endpoint_error" if agent.endpoint_failed else "timeout" if agent.timed_out \
                        else "parse_error"                      # their predict: 5 failed calls -> FAIL, the episode ends
                    res["error"] = agent.endpoint_failed or str(response)[:300]
                    break
                if not actions or actions[0] == "" or actions[0].lower().startswith("error"):
                    rec.step(**row)
                    res["status"] = "no_action"
                    break
                stop, notes = False, []
                for a in actions:
                    note = ""
                    if a in ("DONE", "FAIL"):
                        stop = True
                    elif a == "WAIT":
                        time.sleep(pause)                       # env.step sleeps `pause` for WAIT, then once more
                    else:
                        try:
                            run_pyautogui(a, gui)
                        except Exception as e:
                            note = f"{type(e).__name__}: {str(e)[:200]}"
                            res["action_errors"] += 1
                    notes.append(note)
                    if stop:
                        break
                    time.sleep(pause)
                    gui.page = page = front_page(ctx, page)
                rec.step(**row, notes=notes)
                if stop:
                    code = (cot.get("original_code") or "").lower()
                    if "computer.terminate" in code:            # theirs: "fail" in the code -> FAIL, else "success"
                        res["status"] = "fail" if "fail" in code else "done"
                        res["answer"] = opencua_answer(cot)
                    else:                                       # predict() forces FAIL at the step budget
                        res["status"] = "max_steps"
                    break
            else:
                res["status"] = "max_steps"
            try:
                rec.shot(res["rounds"] + 1, front_page(ctx, page).screenshot(type="png"))
            except Exception:
                pass
        except Exception as e:                   # a harness error still keeps whatever the session did
            res["error"] = f"{type(e).__name__}: {str(e)[:300]}"
            res["status"] = res["status"] or "error"
        try:
            res["record"] = admin_entries(ctx, base, "/_admin/record")
            res["log"] = admin_entries(ctx, base, "/_admin/log")
        except Exception as e:
            res["error"] = (res["error"] or "") + f" | backend read: {type(e).__name__}: {str(e)[:200]}"
        browser.close()
    rec.close()
    res["seconds"] = round(time.time() - t0, 1)
    return res


# ── driver ────────────────────────────────────────────────────────────────────────────────────────────────────────────

RUNNERS = {"uitars": (run_uitars, (1280, 800)), "molmoweb": (run_molmoweb, (1280, 720)),
           "fara7b": (run_fara7b, (1440, 900)), "opencua": (run_opencua, (1920, 1080))}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("agent", choices=sorted(RUNNERS))
    ap.add_argument("--tasks", required=True, help="tasks.json of `python -m webmix.fara_rq1 prep`")
    ap.add_argument("--out", required=True)
    ap.add_argument("--ports", required=True, help="MiniWeb server ports to start (8300-8320), e.g. 8312,8313")
    ap.add_argument("--endpoint", required=True, help="vLLM OpenAI endpoint, e.g. http://127.0.0.1:8694/v1")
    ap.add_argument("--model", required=True, help="served model name")
    ap.add_argument("--path", default=os.environ.get("OWNLOOP_PATH", ""),
                    help="colon list prepended to sys.path: the ui-tars --target dir, the molmoweb clone")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--max-steps", type=int, default=40, help="model actions per task (our MiniWeb budget: 40)")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--width", type=int, default=0, help="viewport; default uitars 1280x800, molmoweb 1280x720")
    ap.add_argument("--height", type=int, default=0)
    ap.add_argument("--frequency-penalty", type=float, default=0.0,
                    help="uitars: 0 as the UI-TARS README's deployment example; OSWorld's request sends 1, which turned "
                         "answers that repeat the thought's words into Chinese in the smoke test")
    ap.add_argument("--temperature", type=float, default=0.7, help="molmoweb sampling (their default)")
    ap.add_argument("--top-p", type=float, default=0.8)
    ap.add_argument("--max-past-steps", type=int, default=10, help="molmoweb text history (their benchmark default)")
    ap.add_argument("--fara7b-error-retries", type=int, default=5,
                    help="fara7b: webeval's --max_error_task_retries (an episode that raised is re-run)")
    ap.add_argument("--opencua-max-tokens", type=int, default=2048,
                    help="opencua: run_multienv_opencua.py's --max_tokens (the agent class's own default is 1500)")
    ap.add_argument("--opencua-pause", type=float, default=5.0,
                    help="opencua: run_multienv_opencua.py's --sleep_after_execution, slept after every action")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--task-ids", default="")
    args = ap.parse_args(argv)
    for p in reversed([p for p in args.path.split(":") if p]):
        sys.path.insert(0, p)
    run, (w, h) = RUNNERS[args.agent]
    args.width, args.height = args.width or w, args.height or h
    out = Path(args.out)
    tasks = json.loads(Path(args.tasks).read_text())
    if args.task_ids:
        keep = set(args.task_ids.split(","))
        tasks = [t for t in tasks if t["task_id"] in keep]
    done = {p.parent.name for p in out.glob("*/session.json")}
    tasks = [t for t in tasks if t["task_id"] not in done]                  # resume
    if args.limit:
        tasks = tasks[:args.limit]
    from datagen import browser as B
    lock, queue = threading.Lock(), list(tasks)
    ports = [int(p) for p in args.ports.split(",")]
    with B.Servers(n=len(ports), ports=ports) as srv:
        bases = srv.bases
        print(f"{args.agent}: {len(tasks)} tasks, {args.workers} workers on {bases}", flush=True)

        def worker(i):
            while True:
                with lock:
                    if not queue:
                        return
                    t = queue.pop(0)
                ep = out / t["task_id"]
                ep.mkdir(parents=True, exist_ok=True)
                try:
                    r = run(t, bases[i % len(bases)], args, ep)
                except Exception as e:
                    r = {"task_id": t["task_id"], "base": bases[i % len(bases)], "answer": None, "status": "crash",
                         "rounds": 0, "error": f"{type(e).__name__}: {str(e)[:300]}", "record": [], "log": []}
                # a harness or model-server failure is kept aside, unsaved, so a rerun (resume) repeats the task
                name = "session_failed.json" if r["status"] in ("crash", "endpoint_error") else "session.json"
                (ep / name).write_text(json.dumps(r, default=str))
                print(f"{t['task_id']}: status={r['status']} rounds={r['rounds']} {r.get('seconds')}s "
                      f"parse_fails={r.get('parse_fails')} action_errors={r.get('action_errors')} err={r['error']} "
                      f"answer={str(r['answer'])[:80]!r}", flush=True)
        with ThreadPoolExecutor(args.workers) as ex:
            list(ex.map(worker, range(args.workers)))


if __name__ == "__main__":
    main()
