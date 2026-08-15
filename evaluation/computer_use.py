"""Native computer-use agents for the commercial models.

Instead of browser-use's DOM/text loop, these drive a real Chromium page via the
provider's own computer-use tool — the model sees screenshots and returns
click/type/scroll actions, which we execute with Playwright. Because it's a real
browser hitting the local MiniWeb server, `recorder.js` + `/_admin/log` capture
the same trajectory, so grading (verify_task) is unchanged.

Providers (docs):
  anthropic  computer_20250124 tool, Messages API   (ANTHROPIC_API_KEY)
  openai     computer_use_preview, Responses API     (OPENAI_API_KEY)
  gemini     ComputerUse tool, generate_content      (GEMINI_API_KEY / Vertex)

Exposed as `ComputerUseAgent`, which satisfies the same AgentRunner protocol as
BrowserUseAgent (setup / run / teardown → AgentResult). Selected via
`build_agent(model, harness="computer-use")`.
"""
from __future__ import annotations

import asyncio
import base64
import json
import re
import time
from pathlib import Path

from agents import AgentResult
from helpers.llm import resolve_provider, _get_env, LLMClient, TokenUsage

# Fixed viewport the model reasons about (pixels). Provider coords are scaled to it.
VIEWPORT = (1280, 800)

# Default computer-use-capable model per provider. Computer use is NATIVE in the
# current models (no separate preview model) — override by passing an explicit id.
CU_MODELS = {
    "anthropic": "claude-opus-4-8",   # native computer use
    "openai": "gpt-5.6",              # native computer use since gpt-5.4
    "gemini": "gemini-3-pro",         # native computer use in Gemini 3
}


def _cu_capable(provider: str, model: str) -> bool:
    if provider == "anthropic":
        return model.startswith("claude")
    if provider == "gemini":
        return "gemini-3" in model
    if provider == "openai":
        return any(v in model for v in ("5.4", "5.5", "5.6")) or "computer-use" in model
    return False


def _b64(png: bytes) -> str:
    return base64.b64encode(png).decode()


class ComputerUseAgent:
    """AgentRunner that drives Chromium via a provider's native computer-use tool."""

    def __init__(self, model: str, *, provider: str | None = None, use_vision=True,
                 max_steps: int = 40, timeout: int = 300, headless: bool = True,
                 available_file_paths=None):
        self.model = model
        self.provider = provider or resolve_provider(model)
        self.max_steps = max_steps
        self.timeout = timeout
        self.headless = headless
        self._pw = None
        self._browser = None
        self._page = None
        self._steps = []   # [{step, actions, text, screenshot}] — meaningful per-step log
        self._usage = TokenUsage()  # per-run token usage (also fed into LLMClient.GLOBAL)

    def _add_usage(self, prompt: int, completion: int) -> None:
        """Record one model turn's tokens on this run and on the process-wide
        counter that run_agent_verify diffs. The CU loops call provider SDKs
        directly (not via LLMClient), so usage must be fed in here."""
        self._usage.add(prompt or 0, completion or 0)
        with LLMClient._lock:
            LLMClient.GLOBAL.add(prompt or 0, completion or 0)

    async def setup(self, server_url: str) -> None:
        from playwright.async_api import async_playwright
        self._pw = await async_playwright().start()
        self._browser = await self._pw.chromium.launch(
            headless=self.headless, args=[
                "--disable-gpu", "--no-sandbox",
                # OFFLINE: fail DNS for every host except localhost so the agent
                # cannot reach the outside web (127.0.0.1 is an IP, unaffected).
                "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost"])
        ctx = await self._browser.new_context(
            viewport={"width": VIEWPORT[0], "height": VIEWPORT[1]})
        self._page = await ctx.new_page()
        # Explicitly reset this task's session before starting (session-scoped).
        try:
            from urllib.parse import urlparse
            o = urlparse(server_url)
            await self._page.goto(f"{o.scheme}://{o.netloc}/_reset_data")
        except Exception:
            pass
        await self._page.goto(server_url)
        await asyncio.sleep(1.5)

    async def teardown(self) -> None:
        try:
            if self._browser: await self._browser.close()
        finally:
            if self._pw: await self._pw.stop()
            self._browser = self._pw = self._page = None

    # -- Playwright action executor (shared across providers) -------------------

    async def _screenshot(self) -> bytes:
        return await self._page.screenshot(type="png")

    def _record_step(self, task_dir, n, obs_png, actions, text):
        """Save the observation screenshot + the model's chosen actions/reasoning."""
        sdir = Path(task_dir) / "screenshots"; sdir.mkdir(parents=True, exist_ok=True)
        rel = f"screenshots/step_{n:02d}.png"
        (Path(task_dir) / rel).write_bytes(obs_png)
        summary = "; ".join(_fmt_action(a) for a in actions) or "(done / no action)"
        self._steps.append({"step": n, "url": self._page.url, "actions": actions,
                            "text": (text or "").strip(), "screenshot": rel})
        print(f"    [cu {n:>2}] {summary}"
              + (f"   \033[2m{(text or '').strip()[:70]}\033[0m" if text else ""))

    async def _exec(self, act: dict) -> None:
        """Execute a normalized action dict on the page."""
        p = self._page
        t = act.get("type")
        x, y = act.get("x"), act.get("y")
        try:
            if t in ("click", "left_click"):
                await p.mouse.click(x, y)
            elif t == "double_click":
                await p.mouse.dblclick(x, y)
            elif t == "triple_click":
                await p.mouse.click(x, y, click_count=3)
            elif t in ("right_click",):
                await p.mouse.click(x, y, button="right")
            elif t == "middle_click":
                await p.mouse.click(x, y, button="middle")
            elif t == "mouse_down":
                await p.mouse.move(x, y); await p.mouse.down()
            elif t == "mouse_up":
                await p.mouse.move(x, y); await p.mouse.up()
            elif t in ("move", "mouse_move", "hover"):
                await p.mouse.move(x, y)
            elif t == "type":
                await p.keyboard.type(act.get("text", ""), delay=15)
                if act.get("enter"):
                    await p.keyboard.press("Enter")
            elif t in ("key", "keypress", "key_combination"):
                for combo in act.get("keys", []) or [act.get("text", "")]:
                    await p.keyboard.press(_pw_key(combo))
            elif t == "key_down":
                for k in act.get("keys", []):
                    await p.keyboard.down(_pw_key(k))
            elif t == "key_up":
                for k in act.get("keys", []):
                    await p.keyboard.up(_pw_key(k))
            elif t == "scroll":
                await p.mouse.move(x or VIEWPORT[0] // 2, y or VIEWPORT[1] // 2)
                await p.mouse.wheel(act.get("dx", 0), act.get("dy", 0))
            elif t == "drag":
                await p.mouse.move(x, y); await p.mouse.down()
                await p.mouse.move(act.get("x2", x), act.get("y2", y)); await p.mouse.up()
            elif t in ("goto", "navigate", "open_web_page"):
                await p.goto(act.get("url", ""))
            elif t in ("back",):
                await p.go_back()
            elif t == "forward":
                await p.go_forward()
            elif t in ("wait",):
                await asyncio.sleep(min(act.get("seconds", 1), 5))
            # screenshot / cursor_position / etc. → no-op (we re-screenshot each turn)
            await asyncio.sleep(0.4)
        except Exception:
            pass  # a bad action is a failed step, not a crash

    async def run(self, task: str, server_url: str, task_dir: Path) -> AgentResult:
        runner = {"anthropic": _run_anthropic, "openai": _run_openai,
                  "gemini": _run_gemini}.get(self.provider)
        if runner is None:
            raise ValueError(f"computer-use harness has no provider for model {self.model!r} "
                             f"(provider={self.provider}); use browser-use for it.")
        # computer use is native in current flagships; keep the model if it supports
        # it, else fall back to the provider's default CU model.
        model = self.model.split("/", 1)[-1] if "/" in self.model else self.model
        if not _cu_capable(self.provider, model):
            model = CU_MODELS[self.provider]
        print(f"    [computer-use] provider={self.provider} model={model}")
        instruction = (f"You are operating a web browser already open at {server_url}. "
                       f"Complete this task, then state the answer if one is asked for:\n{task}")
        t0 = time.time()
        final_text, steps, err = "", 0, []
        try:
            final_text, steps = await asyncio.wait_for(
                runner(self, model, instruction, task_dir), timeout=self.timeout)
        except asyncio.TimeoutError:
            err = ["timeout"]
        except Exception as e:  # provider/API error
            err = [f"{type(e).__name__}: {e}"]
        try:
            (Path(task_dir) / "steps.json").write_text(json.dumps(self._steps, indent=1))
        except Exception:
            pass
        return AgentResult(elapsed=round(time.time() - t0, 1), steps=steps or len(self._steps),
                           is_done=not err, final_result=final_text or None, errors=err)


def _fmt_action(a: dict) -> str:
    """One-line human summary of a normalized action, for the step log."""
    t = a.get("type", "?")
    if t in ("click", "left_click", "double_click", "right_click", "move"):
        return f"{t}({a.get('x')},{a.get('y')})"
    if t == "type":
        return f'type("{(a.get("text") or "")[:30]}")'
    if t in ("key", "keypress"):
        return f"key({'+'.join(a.get('keys') or []) or a.get('text','')})"
    if t == "scroll":
        return f"scroll(dx={a.get('dx',0)},dy={a.get('dy',0)})"
    if t in ("goto", "navigate", "open_web_page"):
        return f"goto({a.get('url','')[:40]})"
    return t


def _pw_key(combo: str) -> str:
    """Map provider key names to Playwright key syntax ('ctrl+a' -> 'Control+a')."""
    parts = re.split(r"[+\-]", combo.strip()) if combo else []
    m = {"ctrl": "Control", "control": "Control", "cmd": "Meta", "super": "Meta",
         "alt": "Alt", "opt": "Alt", "shift": "Shift", "enter": "Enter", "return": "Enter",
         "esc": "Escape", "escape": "Escape", "space": "Space", "tab": "Tab",
         "backspace": "Backspace", "delete": "Delete", "up": "ArrowUp", "down": "ArrowDown",
         "left": "ArrowLeft", "right": "ArrowRight", "pageup": "PageUp", "pagedown": "PageDown"}
    if len(parts) <= 1:
        k = (parts[0] if parts else combo)
        return m.get(k.lower(), k)
    return "+".join(m.get(p.lower(), p) for p in parts)


# ── Anthropic (Messages API, computer_20250124) ───────────────────────────────

async def _run_anthropic(agent: ComputerUseAgent, model, task, task_dir):
    from anthropic import Anthropic
    key = _get_env("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set")
    client = Anthropic(api_key=key)
    W, H = VIEWPORT
    tools = [{"type": "computer_20250124", "name": "computer",
              "display_width_px": W, "display_height_px": H, "display_number": 1}]
    shot = await agent._screenshot()
    messages = [{"role": "user", "content": [
        {"type": "text", "text": task},
        {"type": "image", "source": {"type": "base64", "media_type": "image/png", "data": _b64(shot)}}]}]
    final, steps = "", 0
    for steps in range(1, agent.max_steps + 1):
        # Ample output budget so a turn's reasoning + tool call + answer never
        # truncate (16384 is well under the non-streaming ceiling and far exceeds a
        # single computer-use turn). The max_tokens handler below is a safety net.
        resp = client.beta.messages.create(
            model=model, max_tokens=16384, tools=tools, messages=messages,
            betas=["computer-use-2025-01-24"])
        if getattr(resp, "usage", None):
            agent._add_usage(getattr(resp.usage, "input_tokens", 0) or 0,
                             getattr(resp.usage, "output_tokens", 0) or 0)
        messages.append({"role": "assistant", "content": [b.model_dump() for b in resp.content]})
        turn_text = " ".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
        tool_uses = [b for b in resp.content if getattr(b, "type", "") == "tool_use"]
        actions = [_anthropic_action(tu.input) for tu in tool_uses]
        agent._record_step(task_dir, steps, shot, actions, turn_text)
        if not tool_uses:  # no action this turn
            if resp.stop_reason == "max_tokens":  # truncated before a tool call → keep going
                messages.append({"role": "user", "content": [{"type": "text", "text": (
                    "Your previous turn was cut off before you issued a tool call. Take the "
                    "next action now, or give the final answer if the task is complete.")}]})
                continue
            final = turn_text or final  # genuine end_turn = task complete
            break
        results = []
        for tu in tool_uses:
            await agent._exec(_anthropic_action(tu.input))
            shot = await agent._screenshot()
            results.append({"type": "tool_result", "tool_use_id": tu.id,
                            "content": [{"type": "image", "source": {"type": "base64",
                                        "media_type": "image/png", "data": _b64(shot)}}]})
        messages.append({"role": "user", "content": results})
    return final, steps


def _anthropic_action(inp: dict) -> dict:
    a = inp.get("action"); c = inp.get("coordinate") or [None, None]
    base = {"x": c[0], "y": c[1], "text": inp.get("text", "")}
    if a == "scroll":
        d = inp.get("scroll_direction"); amt = (inp.get("scroll_amount") or 3) * 40
        base.update(type="scroll", dx=(amt if d == "right" else -amt if d == "left" else 0),
                    dy=(amt if d == "down" else -amt if d == "up" else 0))
        return base
    base["type"] = {"left_click": "click", "double_click": "double_click",
                    "right_click": "right_click", "mouse_move": "move", "type": "type",
                    "key": "key", "left_click_drag": "drag", "wait": "wait"}.get(a, a)
    if a == "key":
        base["keys"] = [inp.get("text", "")]
    return base


# ── OpenAI (Responses API, computer_use_preview) ──────────────────────────────

async def _run_openai(agent: ComputerUseAgent, model, task, task_dir):
    from openai import OpenAI
    key = _get_env("OPENAI_API_KEY")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    client = OpenAI(api_key=key)
    W, H = VIEWPORT
    tools = [{"type": "computer_use_preview", "display_width": W, "display_height": H,
              "environment": "browser"}]
    shot = await agent._screenshot()
    resp = client.responses.create(model=model, tools=tools, truncation="auto",
        input=[{"role": "user", "content": [
            {"type": "input_text", "text": task},
            {"type": "input_image", "image_url": f"data:image/png;base64,{_b64(shot)}"}]}])
    _track_openai_usage(agent, resp)
    final, steps = "", 0
    for steps in range(1, agent.max_steps + 1):
        calls = [o for o in resp.output if getattr(o, "type", "") == "computer_call"]
        turn_text = _openai_text(resp)
        agent._record_step(task_dir, steps, shot, [_openai_action(c.action) for c in calls], turn_text)
        if not calls:  # no computer_call this turn
            incomplete = getattr(resp, "status", "") == "incomplete" or (
                getattr(getattr(resp, "incomplete_details", None), "reason", "") == "max_output_tokens")
            if incomplete:  # truncated before a call → nudge and keep going
                resp = client.responses.create(model=model, tools=tools, truncation="auto",
                    previous_response_id=resp.id, input=[{"role": "user", "content": [{"type": "input_text",
                        "text": "Your previous turn was cut off before you issued a browser action. "
                                "Take the next action now, or give the final answer if complete."}]}])
                _track_openai_usage(agent, resp)
                continue
            final = turn_text or final  # genuinely done
            break
        outputs = []
        for call in calls:
            await agent._exec(_openai_action(call.action))
            shot = await agent._screenshot()
            outputs.append({"type": "computer_call_output", "call_id": call.call_id,
                            "acknowledged_safety_checks": [c.__dict__ for c in (getattr(call, "pending_safety_checks", None) or [])],
                            "output": {"type": "input_image", "image_url": f"data:image/png;base64,{_b64(shot)}"}})
        resp = client.responses.create(model=model, tools=tools, truncation="auto",
                                       previous_response_id=resp.id, input=outputs)
        _track_openai_usage(agent, resp)
    return final, steps


def _track_openai_usage(agent, resp) -> None:
    u = getattr(resp, "usage", None)
    if u:
        agent._add_usage(getattr(u, "input_tokens", 0) or 0,
                         getattr(u, "output_tokens", 0) or 0)


def _openai_text(resp) -> str:
    out = []
    for o in resp.output:
        if getattr(o, "type", "") == "message":
            for c in getattr(o, "content", []) or []:
                if getattr(c, "type", "") in ("output_text", "text"):
                    out.append(getattr(c, "text", ""))
    return " ".join(out)


def _openai_action(a) -> dict:
    d = a.__dict__ if hasattr(a, "__dict__") else dict(a)
    t = d.get("type")
    base = {"x": d.get("x"), "y": d.get("y")}
    if t == "click":
        base["type"] = {"right": "right_click"}.get(d.get("button"), "click")
    elif t == "double_click":
        base["type"] = "double_click"
    elif t == "type":
        base.update(type="type", text=d.get("text", ""))
    elif t == "keypress":
        base.update(type="key", keys=d.get("keys", []))
    elif t == "scroll":
        base.update(type="scroll", dx=d.get("scroll_x", 0), dy=d.get("scroll_y", 0))
    elif t == "move":
        base["type"] = "move"
    elif t == "drag":
        path = d.get("path") or []
        if path:
            base.update(type="drag", x=path[0].get("x"), y=path[0].get("y"),
                        x2=path[-1].get("x"), y2=path[-1].get("y"))
    elif t == "wait":
        base = {"type": "wait", "seconds": 1}
    else:
        base["type"] = t
    return base


# ── Gemini (ComputerUse tool, generate_content) ───────────────────────────────

async def _run_gemini(agent: ComputerUseAgent, model, task, task_dir):
    from google import genai
    from google.genai import types
    if _get_env("GOOGLE_GENAI_USE_VERTEXAI").lower() in ("1", "true", "yes"):
        creds = None
        cj = _get_env("GOOGLE_CREDENTIALS_JSON")
        if cj:
            import json as _json
            from google.oauth2 import service_account
            creds = service_account.Credentials.from_service_account_info(
                _json.loads(cj), scopes=["https://www.googleapis.com/auth/cloud-platform"])
        client = genai.Client(vertexai=True, credentials=creds,
                              project=_get_env("GOOGLE_CLOUD_PROJECT"),
                              location=_get_env("GOOGLE_CLOUD_LOCATION") or "global")
    else:
        client = genai.Client(api_key=_get_env("GEMINI_API_KEY") or _get_env("GOOGLE_API_KEY"))
    # Gemini 3 thinks before acting; the default output budget lets hidden thinking
    # eat the whole response so the turn truncates (finish_reason MAX_TOKENS) BEFORE
    # the function call. Never truncate thinking/action/answer — give it the model's
    # full output capacity (gemini-3 = 65536). The MAX_TOKENS handler below stays as
    # a safety net but should not fire.
    cfg = types.GenerateContentConfig(
        max_output_tokens=65536,
        tools=[types.Tool(computer_use=types.ComputerUse(
            environment=types.Environment.ENVIRONMENT_BROWSER))])
    shot = await agent._screenshot()
    contents = [types.Content(role="user", parts=[
        types.Part(text=task), types.Part.from_bytes(data=shot, mime_type="image/png")])]
    final, steps = "", 0
    for steps in range(1, agent.max_steps + 1):
        resp = client.models.generate_content(model=model, contents=contents, config=cfg)
        um = getattr(resp, "usage_metadata", None)
        if um:
            agent._add_usage(getattr(um, "prompt_token_count", 0) or 0,
                             getattr(um, "candidates_token_count", 0) or 0)
        cand = resp.candidates[0]
        parts = cand.content.parts or []
        contents.append(cand.content)
        fcs = [p.function_call for p in parts if getattr(p, "function_call", None)]
        # answer text excludes hidden thinking parts (thought=True)
        turn_text = " ".join(p.text for p in parts
                             if getattr(p, "text", None) and not getattr(p, "thought", False))
        agent._record_step(task_dir, steps, shot, [_gemini_action(fc) for fc in fcs], turn_text)
        if not fcs:
            fr = str(getattr(cand, "finish_reason", "") or "")
            if "MAX_TOKENS" in fr:  # truncated mid-turn, NOT done → nudge and keep going
                contents.append(types.Content(role="user", parts=[types.Part(text=(
                    "Your previous turn was cut off before you issued a browser action. "
                    "Take the next single UI action now; if the task is fully complete, "
                    "reply with the final answer only."))]))
                continue
            final = turn_text or final  # genuine stop with no action = task complete
            break
        fresps = []
        for fc in fcs:
            await agent._exec(_gemini_action(fc))
            shot = await agent._screenshot()
            fresps.append(types.Part.from_function_response(
                name=fc.name, response={"url": agent._page.url}))
        # attach the fresh screenshot alongside the function responses
        contents.append(types.Content(role="user", parts=fresps + [
            types.Part.from_bytes(data=shot, mime_type="image/png")]))
    return final, steps


def _gemini_action(fc) -> dict:
    """Map a Gemini Computer Use function_call to a normalized action dict.

    Function names/args follow the official predefined UI actions
    (ai.google.dev/gemini-api/docs/computer-use): click/double_click/triple_click/
    right_click/middle_click/mouse_down/mouse_up/move, type(text, press_enter),
    press_key(key), hotkey(keys), scroll(x, y, direction, magnitude_in_pixels),
    drag_and_drop(start_x..end_y), navigate/go_back/go_forward/wait/take_screenshot.
    Coordinates are 0..999 normalized — scaled to the pixel viewport here.
    """
    name = fc.name; a = dict(fc.args or {})
    sx = VIEWPORT[0] / 1000.0; sy = VIEWPORT[1] / 1000.0  # gemini coords are 0..999
    def px(k): return int(a[k] * sx) if a.get(k) is not None else None
    def py(k): return int(a[k] * sy) if a.get(k) is not None else None
    x, y = px("x"), py("y")
    if name in ("click", "left_click", "click_at"):
        return {"type": "click", "x": x, "y": y}
    if name == "double_click":
        return {"type": "double_click", "x": x, "y": y}
    if name == "triple_click":
        return {"type": "triple_click", "x": x, "y": y}
    if name == "right_click":
        return {"type": "right_click", "x": x, "y": y}
    if name == "middle_click":
        return {"type": "middle_click", "x": x, "y": y}
    if name == "mouse_down":
        return {"type": "mouse_down", "x": x, "y": y}
    if name == "mouse_up":
        return {"type": "mouse_up", "x": x, "y": y}
    if name in ("move", "hover", "hover_at"):
        return {"type": "move", "x": x, "y": y}
    if name in ("type", "type_text_at"):
        return {"type": "type", "text": a.get("text", ""), "enter": bool(a.get("press_enter"))}
    if name == "press_key":
        return {"type": "key", "keys": [a.get("key", a.get("keys", ""))]}
    if name == "key_down":
        return {"type": "key_down", "keys": [a.get("key", "")]}
    if name == "key_up":
        return {"type": "key_up", "keys": [a.get("key", "")]}
    if name in ("hotkey", "key_combination"):  # a chord: join into one Playwright combo
        keys = a.get("keys") or ([a["combination"]] if a.get("combination") else [])
        return {"type": "key", "keys": ["+".join(keys)] if isinstance(keys, list) else [keys]}
    if name == "scroll":
        d = a.get("direction", "down"); amt = int(a.get("magnitude_in_pixels") or 300)
        return {"type": "scroll", "x": x, "y": y,
                "dy": amt if d == "down" else -amt if d == "up" else 0,
                "dx": amt if d == "right" else -amt if d == "left" else 0}
    if name in ("navigate", "open_web_page"):
        return {"type": "goto", "url": a.get("url", "")}
    if name == "go_back":
        return {"type": "back"}
    if name == "go_forward":
        return {"type": "forward"}
    if name == "wait":
        return {"type": "wait", "seconds": a.get("seconds", 1)}
    if name in ("take_screenshot", "screenshot"):
        return {"type": "screenshot"}
    if name == "drag_and_drop":
        return {"type": "drag",
                "x": px("start_x"), "y": py("start_y"),
                "x2": px("end_x"), "y2": py("end_y")}
    return {"type": name, "x": x, "y": y}
