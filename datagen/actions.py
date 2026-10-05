"""Stage 4 core: the ONLY surface an executor script can act through.

The executor LLM writes a Python script against three objects:

    dom     privileged, read-only DOM queries (find targets, read boxes/options/url)
    act     pixel actions — mouse and keyboard at coordinates of VISIBLE elements;
            every call records the screenshot taken just before it plus the pixel action
    expect  expect.backend(): assert the task's expected backend evidence

Enforcement is structural, not by prompt:
  * `validate_script` rejects imports, dunder/underscore attribute access, while-loops,
    class defs, and every Playwright/JS escape hatch (page, evaluate, goto, fill, ...);
  * `run_script` executes with a tiny builtin set (no __import__, open, getattr, type, ...);
  * `Act` refuses hidden, off-screen (scroll first — scrolling is its own recorded
    action), occluded or stale targets, and forged targets (only `El` objects that `dom`
    returned); keys are allow-listed (no reload/back shortcuts); there is no navigation
    call at all — the harness loads the task's start URL, and that is the only goto.

Pure logic (conventions, jitter, drag paths, the sandbox, the policy) lives here with no
Playwright import; `datagen/driver.py` is the Playwright side (`Driver` below is the seam).
"""
from __future__ import annotations

import ast
import builtins
import datetime as dt
import math
import random
import re
import time
from dataclasses import dataclass


class PolicyViolation(BaseException):
    """A forbidden call. BaseException so a script's `except Exception` cannot swallow it."""


class ActionError(Exception):
    """A refused action the script can recover from (scroll first, re-query, ...)."""


# ── geometry ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Box:
    x: float
    y: float
    w: float
    h: float

    @property
    def cx(self):
        return self.x + self.w / 2

    @property
    def cy(self):
        return self.y + self.h / 2

    @property
    def area(self):
        return max(0.0, self.w) * max(0.0, self.h)

    def contains(self, px, py):
        return self.x <= px <= self.x + self.w and self.y <= py <= self.y + self.h

    def clip(self, width, height):
        x0, y0 = max(0.0, self.x), max(0.0, self.y)
        x1, y1 = min(float(width), self.x + self.w), min(float(height), self.y + self.h)
        return Box(x0, y0, max(0.0, x1 - x0), max(0.0, y1 - y0))

    def as_list(self):
        return [round(self.x, 1), round(self.y, 1), round(self.w, 1), round(self.h, 1)]


# ── the student's coordinate convention ──────────────────────────────────────

class CoordConvention:
    """How exported actions express a screen point.

    normalized: ints in [0, scale] relative to the screenshot (Qwen-VL style 0–1000)
    pixel:      pixels at `resolution` (the screenshot size the student sees);
                resolution None = the recording viewport itself
    Recording keeps raw viewport pixels; conversion happens at export, so the
    convention can change without re-running anything."""

    def __init__(self, mode="normalized", scale=1000, resolution=None):
        if mode not in ("normalized", "pixel"):
            raise ValueError(f"unknown coordinate mode {mode!r}")
        self.mode, self.scale = mode, scale
        self.resolution = tuple(resolution) if resolution else None

    @classmethod
    def from_dict(cls, d):
        d = dict(d or {})
        return cls(d.get("mode", "normalized"), d.get("scale", 1000), d.get("resolution"))

    def to_dict(self):
        out = {"mode": self.mode}
        if self.mode == "normalized":
            out["scale"] = self.scale
        else:
            out["resolution"] = list(self.resolution) if self.resolution else None
        return out

    def point(self, x, y, viewport):
        w, h = viewport
        if self.mode == "normalized":
            s = self.scale
            return (min(s, max(0, round(x / w * s))), min(s, max(0, round(y / h * s))))
        rw, rh = self.resolution or (w, h)
        return (min(rw - 1, max(0, round(x * rw / w))), min(rh - 1, max(0, round(y * rh / h))))

    def length(self, dx, dy, viewport):
        """A displacement (scroll amount): same scale, no clamping, sign kept."""
        w, h = viewport
        if self.mode == "normalized":
            return (round(dx / w * self.scale), round(dy / h * self.scale))
        rw, rh = self.resolution or (w, h)
        return (round(dx * rw / w), round(dy * rh / h))

    def inverse(self, a, b, viewport):
        w, h = viewport
        if self.mode == "normalized":
            return (a / self.scale * w, b / self.scale * h)
        rw, rh = self.resolution or (w, h)
        return (a * w / rw, b * h / rh)


def to_student(step, conv: CoordConvention, viewport):
    """A recorded pixel action -> the student's action dict (no privileged fields)."""
    t = step["type"]
    out = {"type": t}
    if "x" in step and "y" in step:
        out["x"], out["y"] = conv.point(step["x"], step["y"], viewport)
    if t == "drag":
        out["x2"], out["y2"] = conv.point(step["x2"], step["y2"], viewport)
    if t == "scroll":
        out["dx"], out["dy"] = conv.length(step.get("dx", 0), step.get("dy", 0), viewport)
    if t == "type":
        out["text"] = step["text"]
    if t == "key":
        out["key"] = step["key"]
    if t in ("click", "double_click") and step.get("button", "left") != "left":
        out["button"] = step["button"]
    if t == "draw":
        out["strokes"] = [[list(conv.point(x, y, viewport)) for x, y in stroke] for stroke in step["strokes"]]
    if t == "upload":
        out["file"] = step["file"]
    if t == "answer":
        out["text"] = step["text"]
    if t in ("goto", "new_tab"):
        out["url"] = step["url"]
    if t == "switch_tab":
        out["index"] = step["index"]
    return out


# ── jitter + human-like drags ────────────────────────────────────────────────

def jitter_point(box: Box, rng: random.Random, inset=0.2, sigma=0.22, min_margin=2.0):
    """A click point inside `box`: truncated Gaussian around the centre, kept inside an
    inset region (inset fraction per side, at least `min_margin` px) so it never grazes
    the edge. Tiny boxes fall back to their centre."""
    mx = min(max(box.w * inset, min_margin), box.w / 2)
    my = min(max(box.h * inset, min_margin), box.h / 2)
    x0, x1 = box.x + mx, box.x + box.w - mx
    y0, y1 = box.y + my, box.y + box.h - my
    if x1 <= x0:
        x0 = x1 = box.cx
    if y1 <= y0:
        y0 = y1 = box.cy

    def draw(lo, hi, c, span):
        if hi <= lo:
            return c
        for _ in range(20):
            v = rng.gauss(c, sigma * span)
            if lo <= v <= hi:
                return v
        return min(hi, max(lo, c))
    return (round(draw(x0, x1, box.cx, box.w), 1), round(draw(y0, y1, box.cy, box.h), 1))


def drag_path(src, dst, rng: random.Random, waypoints=(3, 7)):
    """[(x, y, steps)] from src to dst: a bowed path with jittered waypoints and a
    varied number of mouse.move steps per segment (speed). First point is src, last dst."""
    (x0, y0), (x1, y1) = src, dst
    n = rng.randint(*waypoints)
    dist = math.hypot(x1 - x0, y1 - y0)
    bow = rng.uniform(-0.15, 0.15) * dist
    nx, ny = (-(y1 - y0) / dist, (x1 - x0) / dist) if dist else (0.0, 0.0)
    pts = [(x0, y0, 1)]
    for i in range(1, n + 1):
        t = i / (n + 1)
        ease = t * t * (3 - 2 * t)                 # slow-fast-slow
        off = math.sin(math.pi * t) * bow
        jx, jy = rng.gauss(0, 1.5), rng.gauss(0, 1.5)
        pts.append((round(x0 + (x1 - x0) * ease + nx * off + jx, 1),
                    round(y0 + (y1 - y0) * ease + ny * off + jy, 1), rng.randint(2, 8)))
    pts.append((x1, y1, rng.randint(2, 6)))
    return pts


# ── element side-file helpers ────────────────────────────────────────────────

def _safe(fn, *a, **kw):
    """Detail reads for the element side file must never break an action."""
    try:
        return fn(*a, **kw)
    except Exception:
        return None


def _selected(info):
    """{index, value, label} of a <select>'s selected option, from an info dict."""
    for o in (info or {}).get("options") or []:
        if o.get("selected"):
            return {"index": o.get("index"), "value": o.get("value"), "label": o.get("text")}
    return None


# ── keys ─────────────────────────────────────────────────────────────────────

_NAMED_KEYS = {"Enter", "Tab", "Escape", "Backspace", "Delete", "ArrowUp", "ArrowDown", "ArrowLeft",
               "ArrowRight", "Home", "End", "PageUp", "PageDown", "Space", " "}
_COMBOS = {"Shift+Tab", "Shift+ArrowUp", "Shift+ArrowDown", "Shift+ArrowLeft", "Shift+ArrowRight",
           "Control+a", "Control+c", "Control+v", "Control+x", "Control+z", "Control+y", "Control+Shift+z",
           "Control+Backspace", "Control+Home", "Control+End", "Shift+Home", "Shift+End"}


def check_key(key):
    """Allow-list: named editing/navigation keys, single characters, a few editing combos.
    Browser-level shortcuts (reload, back, new tab, address bar, devtools) are violations."""
    if not isinstance(key, str) or not key:
        raise PolicyViolation("key must be a non-empty string")
    if key in _NAMED_KEYS or key in _COMBOS or (len(key) == 1 and key.isprintable()):
        return key
    raise PolicyViolation(f"key {key!r} is not allowed (allowed: {sorted(_NAMED_KEYS - {' '})}, "
                          f"single characters, {sorted(_COMBOS)})")


# ── the sandbox ──────────────────────────────────────────────────────────────

FORBIDDEN_NAMES = {
    "eval", "exec", "compile", "open", "__import__", "getattr", "setattr", "delattr", "hasattr",
    "globals", "locals", "vars", "dir", "input", "breakpoint", "help", "memoryview", "type", "object",
    "super", "classmethod", "staticmethod", "property", "exit", "quit", "id",
    # handles the script must never reach
    "page", "browser", "context", "playwright", "sync_playwright", "document", "window",
}
FORBIDDEN_ATTRS = {
    "evaluate", "evaluate_handle", "eval_on_selector", "eval_on_selector_all", "goto", "go_back",
    "go_forward", "reload", "fill", "select_option", "set_input_files", "set_checked", "check", "uncheck",
    "dispatch_event", "set_content", "add_init_script", "add_script_tag", "expose_function",
    "expose_binding", "route", "mouse", "keyboard", "touchscreen", "locator", "query_selector",
    "query_selector_all", "frame", "frames", "main_frame", "request", "new_page", "set_value",
    "press_sequentially", "tap", "focus", "scroll_into_view_if_needed", "wait_for_selector",
}
_BANNED_NODES = (ast.Import, ast.ImportFrom, ast.While, ast.ClassDef, ast.AsyncFunctionDef, ast.Await,
                 ast.Global, ast.Nonlocal, ast.With, ast.AsyncWith, ast.AsyncFor, ast.Yield, ast.YieldFrom)
MAX_RANGE = 200


def validate_script(code):
    """Static policy check. Returns the parsed tree; raises PolicyViolation listing every problem."""
    try:
        tree = ast.parse(code)
    except SyntaxError as exc:
        raise PolicyViolation(f"syntax error: {exc}") from None
    problems = []
    for node in ast.walk(tree):
        line = getattr(node, "lineno", "?")
        if isinstance(node, _BANNED_NODES):
            what = {ast.While: "while-loops (use `for _ in range(n)`)"}.get(type(node), type(node).__name__)
            problems.append(f"line {line}: {what} not allowed")
        elif isinstance(node, ast.Attribute):
            if node.attr.startswith("_"):
                problems.append(f"line {line}: private/dunder attribute .{node.attr}")
            elif node.attr in FORBIDDEN_ATTRS:
                problems.append(f"line {line}: .{node.attr} is forbidden — act only through act.*")
        elif isinstance(node, ast.Name):
            if node.id in FORBIDDEN_NAMES or node.id.startswith("__"):
                problems.append(f"line {line}: name {node.id!r} is not available")
    if problems:
        raise PolicyViolation("script rejected: " + "; ".join(dict.fromkeys(problems)))
    return tree


def _capped_range(*args):
    r = range(*args)
    if len(r) > MAX_RANGE:
        raise PolicyViolation(f"range() longer than {MAX_RANGE}")
    return r


_SAFE = ("abs", "all", "any", "bool", "dict", "enumerate", "filter", "float", "int", "isinstance", "iter", "len", "next",
         "list", "map", "max", "min", "reversed", "round", "set", "sorted", "str", "sum", "tuple", "zip",
         "Exception", "ValueError", "KeyError", "IndexError", "RuntimeError", "AssertionError",
         "TypeError", "StopIteration", "True", "False", "None")


def safe_builtins(log):
    b = {k: getattr(builtins, k) for k in _SAFE if hasattr(builtins, k)}
    b["range"] = _capped_range
    b["print"] = lambda *a, **_k: log(" ".join(str(x) for x in a))
    return b


def run_script(code, *, act, dom, expect, task, log):
    """Validate, then execute with only the wrapper objects in scope. A script must end by
    asserting the backend state (expect.backend()); finishing without it is a violation."""
    validate_script(code)
    env = {"__builtins__": safe_builtins(log), "act": act, "dom": dom, "expect": expect,
           "task": dict(task), "ActionError": ActionError, "log": log}
    exec(compile(code, "<executor-script>", "exec"), env)
    if expect is not None and not getattr(expect, "asserted", False):
        raise PolicyViolation("the script finished without asserting the backend state (expect.backend())")


# ── the driver seam (Playwright side lives in datagen/driver.py) ─────────────

class Driver:
    """Minimal browser interface the wrapper needs. Element keys are opaque handles.

    info(key) -> dict | None   {tag, text, label, name, id, type, role, value, placeholder, href,
                                visible, box:[x,y,w,h] (viewport px), options, checked, disabled,
                                selected_text}; None when the element is gone (stale)
    """
    def viewport(self): raise NotImplementedError
    def query(self, css=None, text=None, tag=None, limit=20): raise NotImplementedError   # [(key, info)]
    def info(self, key): raise NotImplementedError
    def hit(self, key, x, y): raise NotImplementedError
    def scroll_box(self, key): raise NotImplementedError          # [x,y,w,h] of its scroll container | None
    def focused(self): raise NotImplementedError                   # (key, info) | None
    def screenshot(self): raise NotImplementedError                # PNG bytes
    def click(self, x, y, button="left", clicks=1): raise NotImplementedError
    def move(self, x, y, steps=1): raise NotImplementedError
    def down(self): raise NotImplementedError
    def up(self): raise NotImplementedError
    def wheel(self, x, y, dx, dy): raise NotImplementedError
    def press(self, key): raise NotImplementedError
    def type(self, text): raise NotImplementedError
    def settle(self): raise NotImplementedError
    def url(self): raise NotImplementedError
    def title(self): raise NotImplementedError
    def outline(self, limit=80): raise NotImplementedError
    def visible_text(self): return ""                    # the text inside the viewport right now
    def open_url(self, path): raise NotImplementedError   # type a site path into the address bar
    def new_tab(self, path): raise NotImplementedError    # open a site path in a new tab (it becomes current)
    def switch_tab(self, index): raise NotImplementedError
    # element side-file detail (privileged; optional — defaults record nothing)
    def describe(self, key): return {}                    # {css_path, accessible_name, implicit_role}
    def element_at(self, x, y, key=None): return None     # element under a point: {tag, text, css_path, box, is_target, inside_target}
    def scroll_state(self, key=None): return None         # {window: [sx, sy], container: {css_path, scroll_top, scroll_left} | None}


class El:
    """Read-only snapshot of a DOM element, as `dom` returned it. The only valid act target."""
    __slots__ = ("_key", "_info", "_token", "_query")
    _FIELDS = ("tag", "text", "label", "name", "id", "type", "role", "value", "placeholder", "href",
               "visible", "checked", "disabled", "selected_text")

    def __init__(self, key, info, token, query=None):
        object.__setattr__(self, "_key", key)
        object.__setattr__(self, "_info", dict(info or {}))
        object.__setattr__(self, "_token", token)
        object.__setattr__(self, "_query", query)        # the dom query that found it (element side file)

    def __setattr__(self, *_a):
        raise PolicyViolation("El is read-only")

    def __getattr__(self, name):
        if name in El._FIELDS:
            return self._info.get(name)
        raise AttributeError(name)

    @property
    def box(self):
        b = self._info.get("box")
        return Box(*b) if b else None

    @property
    def options(self):
        return [dict(o) for o in self._info.get("options") or []]

    @property
    def in_viewport(self):
        return bool(self._info.get("in_viewport"))

    def __repr__(self):
        return (f"El(<{self.tag}> text={str(self.text or '')[:40]!r} label={self.label!r} name={self.name!r} "
                f"visible={self.visible} in_viewport={self.in_viewport} box={self.box})")


class Recorder:
    """The recorded trajectory: one entry per pixel action, screenshot taken just before it."""

    def __init__(self, out_dir, viewport):
        from pathlib import Path
        self.dir = Path(out_dir)
        (self.dir / "shots").mkdir(parents=True, exist_ok=True)
        self.viewport = viewport
        self.steps = []
        self.span = "target"
        self.seen = []          # viewport text at each screenshot: what the student could read
        self.answer = None      # the reply to the human (act.answer), if the task asks for one

    def shot_path(self, name):
        return self.dir / "shots" / name

    def add(self, png, entry):
        i = len(self.steps)
        name = f"{i:03d}.png"
        self.shot_path(name).write_bytes(png)
        entry = {"i": i, "span": self.span, "screenshot": f"shots/{name}",
                 "t": dt.datetime.now(dt.timezone.utc).isoformat(), **entry}
        self.steps.append(entry)
        return entry

    def final(self, png):
        self.shot_path("final.png").write_bytes(png)
        return "shots/final.png"


class Session:
    """Shared state of one attempt: driver, recorder, rng, budgets, element-token guard."""

    def __init__(self, driver: Driver, recorder: Recorder, rng: random.Random, *, max_actions=40,
                 time_budget=240.0):
        self.driver, self.rec, self.rng = driver, recorder, rng
        self.max_actions, self.deadline = max_actions, time.monotonic() + time_budget
        self.token = object()          # proves an El came from this session's dom
        self.n_actions = 0

    def tick(self, acting=False):
        if time.monotonic() > self.deadline:
            raise PolicyViolation("time budget exceeded")
        if acting:
            self.n_actions += 1
            if self.n_actions > self.max_actions:
                raise PolicyViolation(f"more than {self.max_actions} actions")

    def el(self, key, info, query=None):
        vw, vh = self.driver.viewport()
        info = dict(info or {})
        b = info.get("box")
        info["in_viewport"] = bool(b and info.get("visible") and b[0] >= 0 and b[1] >= 0
                                   and b[0] + b[2] <= vw and b[1] + b[3] <= vh)
        return El(key, info, self.token, query)

    def resolve(self, target):
        """(key, fresh info) for a genuine, still-attached El."""
        if not isinstance(target, El) or target._token is not self.token:
            raise PolicyViolation("act.* targets must be elements returned by dom.find/dom.one")
        info = self.driver.info(target._key)
        if info is None:
            raise ActionError("element is stale (the page changed) — re-query it with dom.one(...)")
        return target._key, info


class Dom:
    """Privileged, read-only DOM access for FINDING targets. Nothing here is recorded."""

    def __init__(self, s: Session):
        self._s = s

    def find(self, css=None, text=None, tag=None, limit=20):
        """Elements matching a CSS selector and/or containing `text` (visible text, label,
        placeholder, aria-label, value), visible ones first."""
        self._s.tick()
        query = {k: v for k, v in (("css", css), ("text", text), ("tag", tag)) if v is not None}
        return [self._s.el(k, i, query) for k, i in self._s.driver.query(css=css, text=text, tag=tag, limit=limit)]

    def one(self, css=None, text=None, tag=None):
        """The first VISIBLE match; ActionError if there is none."""
        for e in self.find(css=css, text=text, tag=tag, limit=20):
            if e.visible:
                return e
        raise ActionError(f"no visible element for css={css!r} text={text!r} tag={tag!r}")

    def refresh(self, el):
        """A fresh snapshot of `el` (its box moves when the page scrolls)."""
        self._s.tick()
        key, info = self._s.resolve(el)
        return self._s.el(key, info, el._query)

    def focused(self):
        self._s.tick()
        f = self._s.driver.focused()
        return self._s.el(*f) if f else None

    def url(self):
        return self._s.driver.url()

    def title(self):
        return self._s.driver.title()

    def viewport(self):
        return tuple(self._s.driver.viewport())

    def outline(self, limit=80):
        return self._s.driver.outline(limit)


class Act:
    """Pixel actions. Each one: validate the target is visible & on screen & hit-testable,
    screenshot, act at a jittered point inside its box, let the page settle, record."""

    def __init__(self, s: Session):
        self._s = s

    # -- helpers -------------------------------------------------------------
    def _visible_box(self, target, need_hit=True):
        s = self._s
        key, info = s.resolve(target)
        if not info.get("visible") or not info.get("box"):
            raise ActionError(f"target is hidden ({target.tag} {str(target.text or '')[:30]!r})")
        vw, vh = s.driver.viewport()
        box = Box(*info["box"])
        vis = box.clip(vw, vh)
        if vis.area <= 0 or (vis.area < 0.5 * box.area and vis.h < 0.9 * vh):
            raise ActionError("target is off-screen — call act.scroll_into_view(el) first "
                              "(scrolling is recorded as its own action)")
        return key, info, vis

    def _point_on(self, key, vis, need_hit=True):
        for _ in range(8):
            x, y = jitter_point(vis, self._s.rng)
            if not need_hit or self._s.driver.hit(key, x, y):
                return x, y
        raise ActionError("target is covered by another element at every tried point")

    @staticmethod
    def _describe(info):
        return {k: info.get(k) for k in ("tag", "label", "name", "id", "role") if info.get(k)} | \
               {"text": str(info.get("text") or "")[:80], "box": [round(v, 1) for v in info.get("box") or []]}

    def _element(self, key, info, target=None, role="target"):
        """Identity of the element an action targets (privileged; element side file only)."""
        extra = _safe(self._s.driver.describe, key) or {}
        return {"role_in_action": role, "selector": getattr(target, "_query", None) if target is not None else None,
                "css_path": extra.get("css_path"), "tag": info.get("tag"),
                "role": info.get("role") or extra.get("implicit_role") or "",
                "accessible_name": extra.get("accessible_name") or info.get("label") or "",
                "label": info.get("label") or "", "context_label": extra.get("context_label") or "",
                "text": str(info.get("text") or "")[:120],
                "id": info.get("id") or "", "name": info.get("name") or "", "type": info.get("type") or "",
                "box": [round(v, 1) for v in info.get("box") or []]}

    def _context(self, key=None, info=None, target=None, role="target", point=None):
        """The element-file entry of one action: what it targeted, where, page scroll, the
        element actually under the (jittered) point when that is not the target itself,
        and for <select> targets the selected option before (after is filled post-action)."""
        d = self._s.driver
        rec = {"element": self._element(key, info, target, role) if key is not None else None,
               "url": d.url(), "point": [point[0], point[1]] if point else None,
               "scroll": _safe(d.scroll_state, key), "at_point": None, "select": None, "drag": None}
        if point is not None and key is not None:
            at = _safe(d.element_at, point[0], point[1], key)
            if at and not at.get("is_target"):
                rec["at_point"] = at
        if info is not None and info.get("tag") == "select":
            rec["select"] = {"before": _selected(info), "after": None}
        return rec

    def _select_after(self, key, el):
        """Post-action hook: the select's option once the action settled (re-found by css path
        when the page reloaded)."""
        def post(rec):
            if rec.get("select") is None:
                return
            info = _safe(self._s.driver.info, key)
            css = (rec.get("element") or {}).get("css_path")
            if info is None and css:
                hits = _safe(self._s.driver.query, css=css, limit=1) or []
                info = hits[0][1] if hits else None
            rec["select"]["after"] = _selected(info) if info else None
            rec["select"]["reloaded"] = _safe(self._s.driver.info, key) is None
        return post

    def _record(self, entry, perform, el=None, post=None):
        s = self._s
        png = s.driver.screenshot()
        s.rec.seen.append(_safe(s.driver.visible_text) or "")
        url = s.driver.url()
        perform()
        s.driver.settle()
        if el is not None and post is not None:
            post(el)
        # goto / new_tab carry their target in "url" (the student's action); the page they left is from_url
        page = {"url": entry["url"], "from_url": url} if entry.get("url") else {"url": url}
        entry = s.rec.add(png, {**entry, **page, "url_after": s.driver.url(), **({"el": el} if el else {})})
        return entry

    def _focused_context(self):
        f = _safe(self._s.driver.focused)
        if not f:
            return self._context(), None
        key, info = f
        return self._context(key, info, role="focused"), key

    # -- actions -------------------------------------------------------------
    def click(self, target, button="left", at=None):
        """Click `target` (an El). `at=(fx, fy)` clicks that fraction of its box instead of a
        jittered point near the centre (e.g. a spot on a canvas)."""
        self._s.tick(acting=True)
        if button not in ("left", "right", "middle"):
            raise PolicyViolation("button must be left/right/middle")
        key, info, vis = self._visible_box(target)
        if at is not None:
            fx, fy = at
            if not (0 <= fx <= 1 and 0 <= fy <= 1):
                raise PolicyViolation("at= fractions must be within [0, 1]")
            b = Box(*info["box"])
            x, y = round(b.x + fx * b.w, 1), round(b.y + fy * b.h, 1)
            if not vis.contains(x, y):
                raise ActionError("at= point is off-screen")
        else:
            x, y = self._point_on(key, vis)
        el = self._context(key, info, target, point=(x, y))
        return self._record({"type": "click", "x": x, "y": y, "button": button, "target": self._describe(info)},
                            lambda: self._s.driver.click(x, y, button=button), el, self._select_after(key, el))

    def double_click(self, target):
        self._s.tick(acting=True)
        key, info, vis = self._visible_box(target)
        x, y = self._point_on(key, vis)
        el = self._context(key, info, target, point=(x, y))
        return self._record({"type": "double_click", "x": x, "y": y, "target": self._describe(info)},
                            lambda: self._s.driver.click(x, y, clicks=2), el, self._select_after(key, el))

    def hover(self, target):
        self._s.tick(acting=True)
        key, info, vis = self._visible_box(target)
        x, y = self._point_on(key, vis)
        return self._record({"type": "hover", "x": x, "y": y, "target": self._describe(info)},
                            lambda: self._s.driver.move(x, y, steps=self._s.rng.randint(3, 10)),
                            self._context(key, info, target, point=(x, y)))

    def type(self, text):
        """Type into whatever has focus (an input, or an open <select> list: type-ahead)."""
        self._s.tick(acting=True)
        if not isinstance(text, str) or not text or len(text) > 500:
            raise PolicyViolation("type() takes a non-empty string of at most 500 characters")
        el, fkey = self._focused_context()
        return self._record({"type": "type", "text": text}, lambda: self._s.driver.type(text), el,
                            self._select_after(fkey, el) if fkey is not None else None)

    def press(self, key):
        self._s.tick(acting=True)
        key = check_key(key)
        if key in (getattr(self._s, "forbidden_keys", None) or ()):
            raise PolicyViolation(f"act.press({key!r}) is not allowed for this control: set it with the pointer "
                                  "(click or drag on it), not the keyboard")
        el, fkey = self._focused_context()
        return self._record({"type": "key", "key": key}, lambda: self._s.driver.press(key), el,
                            self._select_after(fkey, el) if fkey is not None else None)

    def scroll(self, dy, at=None, dx=0):
        """Mouse-wheel by (dx, dy) px (dy > 0 scrolls down) with the pointer over `at` (an El:
        scrolls its container) or over the middle of the page."""
        self._s.tick(acting=True)
        if not isinstance(dy, (int, float)) or abs(dy) > 2000 or abs(dx) > 2000:
            raise PolicyViolation("scroll amounts must be numbers within ±2000 px")
        vw, vh = self._s.driver.viewport()
        if at is not None:
            key, info, vis = self._visible_box(at)
            x, y = jitter_point(vis, self._s.rng, inset=0.25)
            el = self._context(key, info, at, role="scroll_at", point=(x, y))
        else:
            x, y = jitter_point(Box(vw * 0.3, vh * 0.3, vw * 0.4, vh * 0.4), self._s.rng)
            el = self._context(point=(x, y))
        return self._record({"type": "scroll", "x": x, "y": y, "dx": dx, "dy": dy},
                            lambda: self._s.driver.wheel(x, y, dx, dy), el)

    def scroll_into_view(self, target, margin=40):
        """Wheel-scroll (recorded, one action per wheel) until `target` is fully on screen.
        Returns a fresh El."""
        s = self._s
        vw, vh = s.driver.viewport()
        last = None
        for _ in range(12):
            key, info = s.resolve(target)
            if not info.get("visible") or not info.get("box"):
                raise ActionError("target is hidden — it cannot be scrolled into view")
            b = Box(*info["box"])
            fits = b.h <= vh - 2 * margin
            if (fits and b.y >= margin and b.y + b.h <= vh - margin) or (not fits and 0 <= b.y <= vh * 0.5):
                return s.el(key, info, target._query)
            if last is not None and abs(last - b.y) < 1:
                if b.clip(vw, vh).area >= 0.85 * b.area:      # the page ends: as far on screen as it gets
                    return s.el(key, info, target._query)
                raise ActionError("scrolling does not move the target (fixed/inside another scroller?)")
            last = b.y
            want = b.y - vh * s.rng.uniform(0.25, 0.45)
            dy = max(-vh * 0.8, min(vh * 0.8, want))
            dy = int(round(dy / 10.0) * 10) or (10 if want > 0 else -10)
            container = s.driver.scroll_box(key)
            region = Box(*container).clip(vw, vh) if container else Box(vw * 0.2, vh * 0.25, vw * 0.6, vh * 0.5)
            if region.area <= 0:
                region = Box(vw * 0.2, vh * 0.25, vw * 0.6, vh * 0.5)
            s.tick(acting=True)
            x, y = jitter_point(region, s.rng, inset=0.25)
            el = self._context(key, info, target, role="scroll_target")
            el["point"] = [x, y]
            self._record({"type": "scroll", "x": x, "y": y, "dx": 0, "dy": dy},
                         lambda: s.driver.wheel(x, y, 0, dy), el)
        raise ActionError("could not scroll the target into view")

    def drag(self, source, target, at_source=None, at_target=None):
        """Press on `source`, move along a bowed, jittered path, release on `target`."""
        self._s.tick(acting=True)
        k1, i1, v1 = self._visible_box(source)
        k2, i2, v2 = self._visible_box(target, need_hit=False)
        p1 = (Box(*i1["box"]).x + at_source[0] * Box(*i1["box"]).w, Box(*i1["box"]).y + at_source[1] * Box(*i1["box"]).h) \
            if at_source else self._point_on(k1, v1)
        p2 = (Box(*i2["box"]).x + at_target[0] * Box(*i2["box"]).w, Box(*i2["box"]).y + at_target[1] * Box(*i2["box"]).h) \
            if at_target else jitter_point(v2, self._s.rng)
        path = drag_path(p1, p2, self._s.rng)
        d = self._s.driver

        def perform():
            d.move(path[0][0], path[0][1], steps=1)
            d.down()
            for x, y, steps in path[1:]:
                d.move(x, y, steps=steps)
                time.sleep(self._s.rng.uniform(0.0, 0.03))
            time.sleep(self._s.rng.uniform(0.15, 0.3))     # settle before letting go (no fling)
            d.up()
        waypoints = [[round(x, 1), round(y, 1)] for x, y, _ in path]
        el = self._context(k1, i1, source, role="drag_source", point=p1)
        el["drag"] = {"start": el["element"], "end": self._element(k2, i2, target, role="drag_target"),
                      "end_point": [round(p2[0], 1), round(p2[1], 1)], "waypoints": waypoints}
        return self._record({"type": "drag", "x": p1[0], "y": p1[1], "x2": p2[0], "y2": p2[1],
                             "path": waypoints,
                             "target": self._describe(i1), "drop": self._describe(i2)}, perform, el)

    def draw(self, target, strokes):
        """Freehand strokes on `target` (a canvas): each stroke is a list of (fx, fy) fractions
        of its box — pressed at the first point, moved through the rest, released."""
        self._s.tick(acting=True)
        key, info, vis = self._visible_box(target)
        b = Box(*info["box"])
        if not strokes or len(strokes) > 12 or any(len(st) < 2 or len(st) > 80 for st in strokes):
            raise PolicyViolation("draw() takes 1-12 strokes of 2-80 points")
        px = []
        for st in strokes:
            pts = []
            for fx, fy in st:
                if not (0 <= fx <= 1 and 0 <= fy <= 1):
                    raise PolicyViolation("draw() points are fractions within [0, 1]")
                x, y = round(b.x + fx * b.w, 1), round(b.y + fy * b.h, 1)
                if not vis.contains(x, y):
                    raise ActionError("a draw() point is off-screen")
                pts.append((x, y))
            px.append(pts)
        d = self._s.driver

        def perform():
            for pts in px:
                d.move(pts[0][0], pts[0][1], steps=1)
                d.down()
                for x, y in pts[1:]:
                    d.move(x, y, steps=self._s.rng.randint(1, 3))
                d.up()
        return self._record({"type": "draw", "x": px[0][0][0], "y": px[0][0][1],
                             "strokes": [[[x, y] for x, y in pts] for pts in px], "target": self._describe(info)},
                            perform, self._context(key, info, target, point=px[0][0]))

    def upload(self, target, file):
        """Click `target` (a file input, or the button/label that opens the file dialog) and choose
        `file` — one of task["files"] (paths in the user's file system, e.g. "Pictures/city.jpg")."""
        self._s.tick(acting=True)
        allowed = getattr(self._s, "files", {}) or {}
        if file not in allowed:
            raise PolicyViolation(f"upload(): {file!r} is not one of the task's files")
        key, info, vis = self._visible_box(target, need_hit=False)
        # a styled "Choose file" button or label usually covers the input: clicking it is the point
        x, y = self._point_on(key, vis, need_hit=False)
        return self._record({"type": "upload", "x": x, "y": y, "file": file, "target": self._describe(info)},
                            lambda: self._s.driver.choose_file(x, y, allowed[file], getattr(self._s, "upload_input", None)),
                            self._context(key, info, target, point=(x, y)))

    def open_url(self, path, new_tab=False):
        """Go to another page by typing its address (a site path like "/sites/email/"); new_tab=True
        opens it in a new browser tab instead (the current page, e.g. an open dialog, stays as it is
        in its own tab). Only for steps that say which pages may be opened (task["open_urls"])."""
        self._s.tick(acting=True)
        allowed = getattr(self._s, "open_urls", None) or []
        if not isinstance(path, str) or not path.startswith("/") or not any(path.startswith(p) for p in allowed):
            raise PolicyViolation(f"open_url(): {path!r} is not one of the pages this step may open: {allowed}")
        if new_tab:
            return self._record({"type": "new_tab", "url": path}, lambda: self._s.driver.new_tab(path), self._context())
        return self._record({"type": "goto", "url": path}, lambda: self._s.driver.open_url(path), self._context())

    def switch_tab(self, index):
        """Bring browser tab `index` (0 = the first one) to the front."""
        self._s.tick(acting=True)
        tabs = getattr(self._s.driver, "pages", [None])
        if not isinstance(index, int) or not 0 <= index < len(tabs):
            raise PolicyViolation(f"switch_tab(): there are {len(tabs)} tabs")
        return self._record({"type": "switch_tab", "index": index}, lambda: self._s.driver.switch_tab(index),
                            self._context())

    def answer(self, text):
        """Reply to the human with `text` (the task's answer). Recorded as the final action, with a
        screenshot of what is on screen as you answer; nothing else may follow except expect.backend()."""
        self._s.tick(acting=True)
        text = str(text or "").strip()
        if not text or len(text) > 400:
            raise PolicyViolation("answer(): give a non-empty answer of at most 400 characters")
        if self._s.rec.answer is not None:
            raise PolicyViolation("answer() may be called only once")
        self._s.rec.answer = text
        return self._record({"type": "answer", "text": text}, lambda: None, self._context())

    def wait(self, seconds=1.0):
        """Let the page catch up (not recorded as an action). At most 5 s."""
        self._s.tick()
        time.sleep(min(5.0, max(0.0, float(seconds))))
        self._s.driver.settle()


class Expect:
    """expect.backend(): the task's expected backend evidence must already be present."""

    def __init__(self, s: Session, checker):
        self._s, self._checker = s, checker
        self.asserted = False           # set once the script asserted the backend state

    def backend(self):
        self._s.tick()
        ok, detail = self._checker()
        self.asserted = True
        if not ok:
            raise AssertionError(f"expected backend evidence missing: {detail}")
        return detail


API_DOC = '''
You write the BODY of a Python script (no imports, no function wrapper needed) that completes
ONE step on an already-open web page. Only these objects exist:

dom  — read-only page access for FINDING targets (never recorded):
  dom.find(css=None, text=None, tag=None, limit=20) -> [El]  elements matching a CSS selector
        and/or containing text (visible text, label, placeholder, aria-label); visible first
  dom.one(css=None, text=None, tag=None) -> El        first VISIBLE match (raises ActionError)
  dom.refresh(el) -> El      fresh snapshot (boxes move after scrolling)
  dom.focused() -> El|None   dom.url() -> str   dom.title() -> str   dom.viewport() -> (w, h)
  dom.outline(limit=80) -> str   short text outline of the visible page
  El fields: tag text label name id type role value placeholder href visible in_viewport
             checked disabled selected_text box(.x .y .w .h .cx .cy) options([{index, value, text, selected}])

act  — the ONLY way to act. Each call is a real mouse/keyboard action at pixel coordinates,
       recorded with a screenshot. Targets must be El objects from dom that are visible AND
       on screen (otherwise ActionError). Call dom.one(...) again after the page changes.
  act.click(el, button="left", at=None)   at=(fx, fy) clicks that fraction of the box
  act.double_click(el)   act.hover(el)
  act.type(text)          types into the focused element / open dropdown list (type-ahead)
  act.press(key)          "Enter", "Tab", "Escape", "ArrowDown", "ArrowUp", "Backspace", "Control+a", ...
  act.scroll(dy, at=None) mouse wheel (dy>0 = down); at=el scrolls the container under el
  act.scroll_into_view(el) -> El   wheel-scrolls (recorded) until el is fully visible
  act.draw(el, strokes)   freehand strokes on a canvas: [[(fx, fy), ...], ...] fractions of el's box
  act.upload(el, file)    click a file input / its "Choose file" button and pick `file` (one of task["files"])
  act.drag(src_el, dst_el, at_source=None, at_target=None)   at_*=(fx, fy) fractions of each box
                          (a slider: act.drag(s, s, at_source=(0.3, 0.5), at_target=(0.7, 0.5)))
  act.wait(seconds)       pause, not recorded (≤5 s)
  act.open_url(path, new_tab=False)   type a site path ("/sites/email/") into the address bar — ONLY paths
                          listed in task["open_urls"]; new_tab=True opens it in a new tab (keeps this page)
  act.switch_tab(i)       bring tab i to the front (0 = the tab the step started in)
  act.answer(text)        reply to the human (only when the step asks for an answer): the LAST action,
                          taken while the information it is based on is on screen

expect.backend() — raises AssertionError unless the server already received the request that
                   proves the step is done (for an answer step: the answer is right AND every
                   fact it rests on was on screen in one of your screenshots).
                   END EVERY SCRIPT WITH expect.backend().

task — dict with the step's parameters. log(msg) prints to your debug log.

Rules:
- NO imports, no while-loops (use `for _ in range(n)`), no names/attributes starting with "_",
  no page/evaluate/goto/fill/select_option/locator/keyboard/mouse — they do not exist here.
- Do not navigate away: stay on the page you start on (links that re-sort/filter it are fine),
  unless the step says NAVIGATION — then clicking that link is the step.
- NATIVE DATE INPUTS (<input type=date>): act.click(el, at=(0.12, 0.5)) focuses the month segment;
  then act.type("MMDDYYYY") digits with no separators fills the whole date.
- Scroll before acting on anything that is not in_viewport.
- NATIVE <select> DROPDOWNS: act.click(select_el) opens its option list (it shows in the
  screenshot, but mouse clicks cannot reach it). Choose with the keyboard: act.press("ArrowDown")
  / act.press("ArrowUp") once per option to move the highlight (from the currently selected
  option), or act.type(<first letters of the option text>), then act.press("Enter") to commit.
  Afterwards check dom.refresh(select_el).selected_text (or the new URL) before continuing.
- If the control needs a submit/apply button, find it (it may need scrolling) and click it.
- Wrap nothing in try/except that hides failures; let errors surface.
'''.strip()
