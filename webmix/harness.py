"""The one browser-use harness every WebMix arm runs in, and that replays record training rows from.

Observation: browser-use's standard state message (DOM element list + screenshot), flash mode
(output = memory + action), one action per step. Actions: browser-use's defaults minus the ones no
MiniWeb task can use offline (EXCLUDED_ACTIONS; `upload_file` among them: a file is picked in MiniWeb's
own Finder, which opens when the file control is clicked), click by index OR viewport coordinates,
plus three custom actions the datagen action set
needs: `drag` (press, move, release), `draw` (strokes) and `macro_done` (ends a macro segment; the
planner arms switch adapters on it). The action schema is appended to the system prompt
(`add_schema_to_system_prompt`), so a local model sees the actions it is decoding into.

Viewport 1280 × 800 at device scale 1, the datagen recording size: screenshot pixels, viewport CSS
pixels and the coordinates in click/drag/draw are the same numbers.
"""
from __future__ import annotations

import asyncio
import json
import os
from urllib.parse import urlencode, urlsplit

from pydantic import BaseModel, Field

VIEWPORT = (1280, 800)
CHROME = os.path.expanduser(os.environ.get("MINIWEB_BROWSER") or os.environ.get(
    "DATAGEN_CHROME", "~/.cache/ms-playwright/chromium-1117/chrome-linux/chrome"))

# Agent settings shared by replay and eval. Planning is off (flash mode strips it anyway; our own
# planner replaces it); message compaction would call the model to summarize and change the prompt.
AGENT_KWARGS = dict(
    use_vision=True,
    flash_mode=True,
    use_judge=False,
    enable_planning=False,
    message_compaction=False,
    max_actions_per_step=1,
    directly_open_url=False,     # the harness puts the tab on the start page itself
)

MACRO_DONE_MEMORY = "Macro step finished."
# the router's note for a session's next macro_done result (webmix.evaluate done-gating: what is still left to do),
# keyed by id(browser_session); the action's schema is unchanged (browser_session is injected, not model-visible)
ROUTER_NOTES: dict = {}
MAX_STEPS = 40                   # shown in every prompt ("Step 3 maximum:40"): the same for replay and eval


# ── actions ───────────────────────────────────────────────────────────────────

# Coordinates in every action are on a 0-1000 scale of the screenshot (x: left->right, y: top->bottom), the
# convention Qwen3.5 grounds in natively. Found 2026-09-29: the base model's drags and coordinate clicks hit
# their targets only when read that way, and the harness had applied them as viewport pixels. Converted to
# pixels when executed (to_px; browser-use's own click via use_normalized_coordinates).
COORD_SCALE = 1000


def to_px(x, y):
    return x * VIEWPORT[0] / COORD_SCALE, y * VIEWPORT[1] / COORD_SCALE


def to_norm(x, y):
    """Viewport pixels -> the 0-1000 scale (replayed targets)."""
    return round(x * COORD_SCALE / VIEWPORT[0]), round(y * COORD_SCALE / VIEWPORT[1])


class DragAction(BaseModel):
    start_x: int = Field(description="Where the drag starts (the thing being dragged): x on a 0-1000 scale of the screenshot width")
    start_y: int = Field(description="Where the drag starts: y on a 0-1000 scale of the screenshot height")
    end_x: int = Field(description="Where the drag is released: x on a 0-1000 scale of the screenshot width")
    end_y: int = Field(description="Where the drag is released: y on a 0-1000 scale of the screenshot height")


class DrawAction(BaseModel):
    strokes: list[list[list[int]]] = Field(
        description="Pen strokes, each a list of [x, y] points (0-1000 scale of the screenshot) drawn with the mouse button held")


def _describe_click_coordinates():
    """browser-use's click takes coordinate_x/y; say (in the schema the model reads) that they are on the 0-1000 scale."""
    from browser_use.tools.views import ClickElementAction
    f = ClickElementAction.model_fields
    f["coordinate_x"].description = "x on a 0-1000 scale of the screenshot width (0 = left edge, 1000 = right edge)"
    f["coordinate_y"].description = "y on a 0-1000 scale of the screenshot height (0 = top edge, 1000 = bottom edge)"
    ClickElementAction.model_rebuild(force=True)


def use_normalized_coordinates(browser_session):
    """browser-use converts click coordinates from 'LLM screenshot' space to the viewport when both sizes are
    set on the session. Declaring a 1000x1000 model space makes it read them on the 0-1000 scale; the screenshot
    the model sees is not resized (the Agent keeps its own copy of llm_screenshot_size, None). Call after the
    Agent is created (its constructor resets the session's value)."""
    browser_session.llm_screenshot_size = (COORD_SCALE, COORD_SCALE)
    browser_session._original_viewport_size = VIEWPORT


async def _mouse(browser_session):
    cdp = await browser_session.get_or_create_cdp_session()
    send = cdp.cdp_client.send.Input.dispatchMouseEvent

    async def ev(kind, x, y, buttons=0, button="none"):
        p = {"type": kind, "x": float(x), "y": float(y), "button": button, "buttons": buttons}
        if kind in ("mousePressed", "mouseReleased"):
            p["clickCount"] = 1
        await send(params=p, session_id=cdp.session_id)
    return ev


async def _stroke(ev, points, hold=0.2, steps_between=4):
    """Press at the first point, move through the rest (interpolated), release at the last."""
    x0, y0 = points[0]
    await ev("mouseMoved", x0, y0)
    await ev("mousePressed", x0, y0, buttons=1, button="left")
    await asyncio.sleep(hold)
    px, py = x0, y0
    for x, y in points[1:]:
        for k in range(1, steps_between + 1):
            await ev("mouseMoved", px + (x - px) * k / steps_between, py + (y - py) * k / steps_between,
                     buttons=1, button="left")
            await asyncio.sleep(0.01)
        px, py = x, y
    await asyncio.sleep(hold)
    await ev("mouseReleased", px, py, button="left")


# browser-use actions no MiniWeb task can use offline, dropped for every arm (user, 2026-09-28): web search,
# LLM page extraction, PDF export, the agent's scratch file system, JS evaluation and DOM query tools. Their
# schema was ~2.3k of the ~6.6k prompt tokens. upload_file: a file is picked in MiniWeb's Finder instead.
EXCLUDED_ACTIONS = ["upload_file", "search", "extract", "save_as_pdf", "search_page", "find_elements", "evaluate",
                    "write_file", "replace_file", "read_file"]


def make_tools(end_on_macro_done=False, guard_text=None):
    """browser-use tools with macro_done. `end_on_macro_done`: macro_done also ends the episode (the subtask executor,
    where one episode is one step: 40% of its episodes kept acting after macro_done, 2026-09-30). `guard_text`: the
    task's own text; typing a password that it does not contain is refused (v7, see GuardedTools)."""
    from browser_use import BrowserSession, Tools
    from browser_use.agent.views import ActionResult

    _describe_click_coordinates()
    if guard_text is None:
        tools = Tools(exclude_actions=EXCLUDED_ACTIONS)
    else:
        tools = _guarded_tools_class()(exclude_actions=EXCLUDED_ACTIONS)
        tools.guard_text = guard_text
    tools.set_coordinate_clicking(True)

    @tools.registry.action("Drag with the mouse: press at (start_x, start_y), move, release at (end_x, end_y), all on "
                           "a 0-1000 scale of the screenshot. For sliders, drag-and-drop, reordering, panning a map.",
                           param_model=DragAction)
    async def drag(params: DragAction, browser_session):
        ev = await _mouse(browser_session)
        await _stroke(ev, [to_px(params.start_x, params.start_y), to_px(params.end_x, params.end_y)], steps_between=12)
        msg = f"Dragged from ({params.start_x}, {params.start_y}) to ({params.end_x}, {params.end_y})"
        return ActionResult(extracted_content=msg, long_term_memory=msg)

    @tools.registry.action("Draw with the mouse on a canvas or signature pad: each stroke is a list of "
                           "[x, y] points (0-1000 scale of the screenshot) drawn with the button held.", param_model=DrawAction)
    async def draw(params: DrawAction, browser_session):
        ev = await _mouse(browser_session)
        for s in params.strokes:
            if s:
                await _stroke(ev, [to_px(*p[:2]) for p in s], hold=0.05, steps_between=1)
        msg = f"Drew {len(params.strokes)} stroke(s)"
        return ActionResult(extracted_content=msg, long_term_memory=msg)

    async def macro_done(browser_session):
        note = ROUTER_NOTES.pop(id(browser_session), None)
        text = MACRO_DONE_MEMORY + (" " + note if note else "")
        if end_on_macro_done:
            return ActionResult(is_done=True, success=True, extracted_content=text, long_term_memory=text)
        return ActionResult(extracted_content=text, long_term_memory=text)
    # the real class, not the postponed-annotation string: the registry injects browser_session by its type
    macro_done.__annotations__ = {"browser_session": BrowserSession}
    tools.registry.action("Mark the current step of the task (one sub-goal, e.g. a form submitted, a filter "
                          "applied, an item found) as finished, before starting the next one or calling done.")(macro_done)

    return tools


# ── model ─────────────────────────────────────────────────────────────────────

def make_llm(model, base_url, api_key="EMPTY", temperature=0.0, max_tokens=1024, **kw):
    """The eval model: an OpenAI-compatible server (vLLM) with the action schema in the system prompt."""
    from browser_use.llm.openai.chat import ChatOpenAI
    return ChatOpenAI(model=model, base_url=base_url, api_key=api_key, temperature=temperature,
                      frequency_penalty=None, max_completion_tokens=max_tokens,
                      add_schema_to_system_prompt=True, **kw)


def instruction(task_text, start_url):
    """The task wrapper evaluation.agents.BrowserUseAgent uses."""
    return f"You are interacting with a web application at {start_url}. Your task: {task_text}"


# ── browser session ───────────────────────────────────────────────────────────

def _route_uploads():
    from evaluation.agents import _route_uploads_through_miniweb_picker
    _route_uploads_through_miniweb_picker()


def _pin_viewport_for_coordinates():
    """browser-use re-caches the viewport for coordinate conversion on every state read as the page's inner
    width (1265 with a scrollbar), but the model's 0-1000 refers to the whole 1280-px screenshot. Keep the
    screenshot's size whenever normalized coordinates are on. Patched before a session binds its handlers."""
    import functools

    from browser_use.browser.watchdogs.dom_watchdog import DOMWatchdog as W
    if getattr(W, "_webmix_pinned_viewport", False):
        return
    original = W.on_BrowserStateRequestEvent

    @functools.wraps(original)
    async def on_BrowserStateRequestEvent(self, event):
        out = await original(self, event)
        if self.browser_session.llm_screenshot_size == (COORD_SCALE, COORD_SCALE):
            self.browser_session._original_viewport_size = VIEWPORT
        return out

    W.on_BrowserStateRequestEvent = on_BrowserStateRequestEvent
    W._webmix_pinned_viewport = True


def make_session(headless=True, allowed_domains=("localhost", "127.0.0.1"), online=False):
    """allowed_domains: MiniWeb is localhost only; WebArena adds its host (webmix.wa). online: the live web
    (Online-Mind2Web, webmix.om2w): no offline host-resolver rule and no domain allow-list."""
    from browser_use import BrowserSession
    from evaluation.agents import _EXTRA_CHROME_ARGS
    _route_uploads()                           # before the session binds its handlers
    _pin_viewport_for_coordinates()
    # the browser inherits this process's environment: UTC, the timezone datagen recorded in (datagen/browser.py
    # new_context), so client-rendered times match the tasks' answers; browser-use has no timezone option
    os.environ["TZ"] = "UTC"
    w, h = VIEWPORT
    # the offline rule (MAP * ~NOTFOUND , EXCLUDE localhost) also catches IP literals: exclude each allowed host
    extra = [d for d in allowed_domains if d not in ("localhost", "127.0.0.1")]
    args = [a + "".join(f" , EXCLUDE {d}" for d in extra) if a.startswith("--host-resolver-rules=") else a
            for a in _EXTRA_CHROME_ARGS]
    kw = {}
    if online:
        # automation markers (navigator.webdriver) trip bot checks (2026-10-01: Cloudflare "verify you are human" on
        # Cambridge Dictionary for 40 steps); same setting for every arm
        args = [a for a in args if not a.startswith("--host-resolver-rules=")] + [
            "--disable-blink-features=AutomationControlled"]
        # live sites refuse "HeadlessChrome" (2026-10-01: new.mta.info answered Access Denied for 40 steps); present the
        # pinned Chromium as a desktop Chrome
        kw["user_agent"] = ("Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/124.0.0.0 Safari/537.36")
    return BrowserSession(headless=headless, keep_alive=True, args=args,
                          executable_path=CHROME, viewport={"width": w, "height": h}, device_scale_factor=1,
                          allowed_domains=None if online else list(allowed_domains), **kw)


async def enable_clipboard(browser_session, agent=None):
    """Headless pages have no focus, so the sites' Copy buttons fail; grant clipboard access and
    emulate focus (evaluation.agents.BrowserUseAgent._enable_clipboard). Also an on_step_start hook."""
    try:
        cdp = await browser_session.get_or_create_cdp_session()
        if agent is None:
            await cdp.cdp_client.send.Browser.grantPermissions(
                params={"permissions": ["clipboardReadWrite", "clipboardSanitizedWrite"]})
        await cdp.cdp_client.send.Emulation.setFocusEmulationEnabled(
            params={"enabled": True}, session_id=cdp.session_id)
    except Exception:
        pass


async def evaluate(browser_session, js, *args):
    page = await browser_session.get_current_page()
    out = await page.evaluate(js, *args)
    try:
        return json.loads(out)
    except (TypeError, ValueError):
        return out


async def goto(browser_session, url, timeout=10.0):
    """A privileged navigation (session preparation): raw CDP, no browser-use readiness wait, which
    times out on a JSON endpoint like /_admin/session-flags."""
    cdp = await browser_session.get_or_create_cdp_session()
    await cdp.cdp_client.send.Page.navigate(params={"url": url}, session_id=cdp.session_id)
    t0 = asyncio.get_event_loop().time()
    await asyncio.sleep(0.2)
    while asyncio.get_event_loop().time() - t0 < timeout:
        try:
            r = await cdp.cdp_client.send.Runtime.evaluate(params={"expression": "document.readyState + ' ' + location.href",
                                                                   "returnByValue": True}, session_id=cdp.session_id)
            state = (r.get("result") or {}).get("value") or ""
            if state.startswith("complete") and "about:blank" not in state:
                break
        except Exception:
            pass
        await asyncio.sleep(0.1)
    await asyncio.sleep(0.3)


# ── session preparation (privileged, before the agent's first step) ─────────

_CART_CLICK = """(css, text) => {
  const els = [...document.querySelectorAll(css)].filter(e => !text || (e.innerText || e.value || '').includes(text));
  if (!els.length) return false;
  els[0].click();
  return true;
}"""


async def prepare(browser_session, base, task):
    """What datagen's Kind.setup does in a Playwright context, done in this browser: the session's
    stable id (+ logged-out / 2FA-off flags for auth and payment forms), and an item in the cart for
    a checkout page. Mirrors datagen/kinds/base.py `prepare` and forms.py / tools.py `setup`."""
    ctrl = task["control"]
    flags = {}
    if ctrl["kind"] == "form" and ctrl.get("role") == "authenticate_by_form":
        flags = {"logout": "1", "disable_2fa": "1"}
    elif ctrl["kind"] == "form" and ctrl.get("role") in ("pay_by_form", "checkout_by_form", "book_by_form"):
        flags = {"disable_2fa": "1"}
    await goto(browser_session, f"{base}/_admin/session-flags" + ("?" + urlencode(flags) if flags else ""))
    prep = (ctrl.get("prep") or {}) if ctrl["kind"] != "tools" else {}
    if prep.get("add_to_cart"):
        a = prep["add_to_cart"]
        await goto(browser_session, base + a["page"])
        await asyncio.sleep(0.5)
        if not await evaluate(browser_session, _CART_CLICK, a["css"], a.get("text") or ""):
            raise RuntimeError(f"cart preparation failed: {a}")
        await asyncio.sleep(1.0)
    await goto(browser_session, base + task["start"]["url"])
    await asyncio.sleep(1.0)


# ── backend reads (the session's own log / data changes / recorder stream) ───

async def _cookie_header(browser_session, base):
    host = urlsplit(base).hostname
    cookies = await browser_session.cookies()
    return "; ".join(f"{c['name']}={c['value']}" for c in cookies if (c.get("domain") or "").lstrip(".") in (host, ""))


async def admin_get(browser_session, base, path):
    """GET a privileged /_admin endpoint AS this browser's session (its cookies), outside the page."""
    import urllib.request
    req = urllib.request.Request(base + path, headers={"Cookie": await _cookie_header(browser_session, base)})

    def fetch():
        with urllib.request.urlopen(req, timeout=20) as r:
            return json.loads(r.read().decode())
    return await asyncio.to_thread(fetch)


async def backend_state(browser_session, base):
    """-> (request log entries, data changes, clipboard writes) of this browser's session."""
    log = (await admin_get(browser_session, base, "/_admin/log")).get("entries", []) or []
    try:
        changes = (await admin_get(browser_session, base, "/_admin/changes")).get("changes", []) or []
    except Exception:
        changes = None
    try:
        rec = (await admin_get(browser_session, base, "/_admin/record")).get("entries", []) or []
    except Exception:
        rec = []
    clip = [e.get("value") for e in rec if e.get("action") == "clipboard_write"]
    return log, changes, clip


# ── v7 (2026-10-02): page state for progress checks, and the credential guard ─────────────────────────────────────
# From the WebVoyager / Online-Mind2Web failure study (user: "do all those fixes and test on MiniWeb only first"):
# specialists report success for steps that changed nothing, the planner re-issues refused steps, and the agent once
# typed made-up credentials into a real login form. The page state below is what the planner is told actually changed.
PAGE_STATE_JS = r"""() => {
  const vis = el => { const r = el.getBoundingClientRect(); const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none'; };
  const txt = s => (s || '').replace(/\s+/g, ' ').trim().slice(0, 60);
  const lab = el => txt((el.labels && el.labels[0] && el.labels[0].innerText) || el.getAttribute('aria-label') ||
    el.getAttribute('placeholder') || el.getAttribute('name') || el.id || el.tagName.toLowerCase());
  const fields = [], checked = [], selected = [];
  for (const el of document.querySelectorAll('input, textarea, select')) {
    if (!vis(el)) continue;
    const t = (el.type || '').toLowerCase();
    if (t === 'hidden' || t === 'submit' || t === 'button' || t === 'image' || t === 'file') continue;
    if (t === 'checkbox' || t === 'radio') { if (el.checked) checked.push(lab(el)); continue; }
    let v = el.tagName === 'SELECT' ? (el.selectedOptions[0] ? el.selectedOptions[0].text : '') : el.value;
    if (t === 'password') v = v ? '(filled)' : '';
    if (fields.length < 40) fields.push([lab(el), txt(v)]);
  }
  for (const el of document.querySelectorAll('[aria-selected="true"], [aria-checked="true"], [aria-pressed="true"], [aria-current]:not([aria-current="false"])')) {
    if (selected.length >= 30 || !vis(el)) continue;
    selected.push(txt(el.getAttribute('aria-label') || el.innerText));
  }
  let h = 0; const body = (document.body ? document.body.innerText : '').slice(0, 60000);
  for (let i = 0; i < body.length; i++) h = (h * 31 + body.charCodeAt(i)) | 0;
  let sc = 0, k = 0;              // scroll positions of inner containers (a calendar grid, a results pane), not only the window
  for (const el of document.querySelectorAll('body *')) {
    if (++k > 20000) break;
    if (el.scrollTop || el.scrollLeft) sc = (sc * 31 + el.scrollTop * 7 + el.scrollLeft + k) | 0;
  }
  return JSON.stringify({url: location.href, title: document.title, y: Math.round(window.scrollY), s: sc, h: h,
                         n: body.length, fields: fields, checked: checked, selected: selected});
}"""


async def page_state(browser_session):
    """-> the page's URL, title, scroll position, a hash of its text, form field values and selected / checked
    controls; {} when it cannot be read (navigation in flight, closed tab)."""
    try:
        st = await evaluate(browser_session, PAGE_STATE_JS)
        return st if isinstance(st, dict) else {}
    except Exception:
        return {}


def fingerprint(state, scroll=False):
    """Equal fingerprints = nothing a user could see changed (scroll position only counts when `scroll`)."""
    keys = ("url", "title", "h", "fields", "checked", "selected") + (("y", "s") if scroll else ())
    return json.dumps([state.get(k) for k in keys], sort_keys=True, default=str) if state else None


def diff_states(a, b, limit=6):
    """-> short lines saying what changed between two page states (URL, fields, checked and selected controls)."""
    if not a or not b:
        return ["the page could not be read"]
    out = []
    if a.get("url") != b.get("url"):
        out.append(f"URL now {b.get('url')}")
    elif a.get("title") != b.get("title"):
        out.append(f"title now '{b.get('title')}'")
    fa, fb = dict(map(tuple, a.get("fields") or [])), dict(map(tuple, b.get("fields") or []))
    for k, v in fb.items():
        if fa.get(k, "") != v and len(out) < limit:
            out.append(f"field '{k}' = '{v}'")
    for key, word in (("checked", "checked"), ("selected", "selected")):
        new = [x for x in b.get(key) or [] if x not in (a.get(key) or [])]
        gone = [x for x in a.get(key) or [] if x not in (b.get(key) or [])]
        if new and len(out) < limit:
            out.append(f"now {word}: " + ", ".join(f"'{x}'" for x in new[:4]))
        if gone and len(out) < limit:
            out.append(f"no longer {word}: " + ", ".join(f"'{x}'" for x in gone[:4]))
    if not out and a.get("h") != b.get("h"):
        out.append("the page content changed")
    return out


def _guarded_tools_class():
    from browser_use import Tools
    from browser_use.agent.views import ActionResult

    class GuardedTools(Tools):
        """Refuses to type a password the task's own text does not contain: on a live site the agent once guessed
        a login and locked the account (Online-Mind2Web, 2026-10-01). Specialists only; the planner cannot type."""
        guard_text = ""

        async def act(self, action, browser_session, *args, **kwargs):
            d = action.model_dump(exclude_none=True)
            name = next(iter(d), "")
            p = d.get(name) or {}
            text = str(p.get("text") or "") if name == "input" else ""
            if text and text not in (self.guard_text or ""):
                attrs = {}
                try:
                    node = await browser_session.get_element_by_index(int(p.get("index")))
                    attrs = {str(k).lower(): str(v).lower() for k, v in (getattr(node, "attributes", None) or {}).items()}
                except Exception:
                    pass
                if attrs.get("type") == "password" or "password" in attrs.get("autocomplete", ""):
                    msg = ("Refused: never type a password the task did not give. Continue without logging in, or "
                           "report that the task needs a login.")
                    return ActionResult(error=msg, include_in_memory=True)
            return await super().act(action, browser_session, *args, **kwargs)
    return GuardedTools
