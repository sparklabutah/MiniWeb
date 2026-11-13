"""Make the real-web agent's actions visible in the console, one at a time, like a person using the browser.

browser-use acts through events on its session's bus (ClickElementEvent, TypeTextEvent, ...). `Cursor.install` puts a
handler in front of each of them, so before the action runs:
- a cursor drawn in the page glides to the element (or point), with a label saying what is about to happen
  ("Click “Sign in”", "Type “web agent”", "Press Enter", "Scroll down"), then a ripple on the click;
- for a navigation, the console's address bar types the URL out first (`Screen.typing`).
Then the handler waits `pace` seconds, so the live view (a few frames a second) shows it and the person can take over
before the click lands.

The cursor is hidden while browser-use reads the page (BrowserStateRequestEvent), so the model never sees it and it
never hides an element from the DOM snapshot. It has pointer-events: none, so it never takes a click.
"""
from __future__ import annotations

import asyncio
import json

DEFAULTS = {"enabled": True, "pace": 0.7, "move": 0.55}

# the overlay, created once per page; window.__dn keeps the last position so a new page starts the cursor where it was
OVERLAY_JS = r"""
(function (o) {
  const d = document; if (!d.body) return false;
  let root = d.getElementById('__dn_cursor');
  if (!root) {
    root = d.createElement('div'); root.id = '__dn_cursor';
    root.style.cssText = 'position:fixed;left:0;top:0;width:0;height:0;z-index:2147483647;pointer-events:none;';
    root.innerHTML =
      '<div id="__dn_ring" style="position:fixed;width:34px;height:34px;margin:-17px 0 0 -17px;border-radius:50%;' +
      'border:3px solid #ff7f27;opacity:0;transform:scale(.3);transition:transform .45s ease-out,opacity .45s ease-out"></div>' +
      '<div id="__dn_box" style="position:fixed;border:2px solid #ff7f27;border-radius:6px;opacity:0;' +
      'box-shadow:0 0 0 4px rgba(255,127,39,.18);transition:opacity .2s"></div>' +
      '<svg id="__dn_arrow" width="26" height="30" viewBox="0 0 26 30" style="position:fixed;left:0;top:0;' +
      'filter:drop-shadow(0 2px 3px rgba(0,0,0,.45))"><path d="M2 2 L2 24 L8 18 L12.5 28 L16.5 26.2 L12 16.5 L20 16.5 Z" ' +
      'fill="#ff7f27" stroke="#fff" stroke-width="2" stroke-linejoin="round"/></svg>' +
      '<div id="__dn_label" style="position:fixed;left:0;top:0;padding:5px 10px;border-radius:8px;background:#1d1d1d;' +
      'color:#fff;font:600 13px/1.3 -apple-system,BlinkMacSystemFont,Segoe UI,sans-serif;white-space:nowrap;' +
      'max-width:420px;overflow:hidden;text-overflow:ellipsis;box-shadow:0 4px 14px rgba(0,0,0,.35);opacity:0;' +
      'transition:opacity .15s"></div>';
    d.body.appendChild(root);
  }
  const fresh = !root.__place, $ = id => d.getElementById(id);
  if (fresh) root.__place = (x, y, ms) => {
    const t = ms ? `left ${ms}ms cubic-bezier(.3,.7,.2,1), top ${ms}ms cubic-bezier(.3,.7,.2,1)` : 'none';
    for (const id of ['__dn_arrow', '__dn_label']) $(id).style.transition = t + (id === '__dn_label' ? ', opacity .15s' : '');
    void $('__dn_arrow').offsetWidth;
    $('__dn_arrow').style.left = (x - 2) + 'px'; $('__dn_arrow').style.top = (y - 2) + 'px';
    const lw = Math.min(420, $('__dn_label').offsetWidth || 120);
    $('__dn_label').style.left = Math.max(6, Math.min(innerWidth - lw - 6, x + 22)) + 'px';
    $('__dn_label').style.top = (y + 30 > innerHeight - 30 ? y - 34 : y + 30) + 'px';
    window.__dn = {x, y};
  };
  if (fresh) { const p = window.__dn || {x: o.fromX, y: o.fromY}; root.__place(p.x, p.y, 0); }
  return true;
})
"""

SHOW_JS = r"""
(function (o) {
  const $ = id => document.getElementById(id), root = $('__dn_cursor'); if (!root) return false;
  root.style.display = '';
  $('__dn_label').textContent = o.label || ''; $('__dn_label').style.opacity = o.label ? '1' : '0';
  const box = $('__dn_box');
  if (o.rect) { Object.assign(box.style, {left: o.rect.x - 3 + 'px', top: o.rect.y - 3 + 'px',
                width: o.rect.width + 6 + 'px', height: o.rect.height + 6 + 'px', opacity: '1'}); }
  else box.style.opacity = '0';
  root.__place(o.x, o.y, o.ms);
  return true;
})
"""

CLICK_JS = r"""
(function () {
  const r = document.getElementById('__dn_ring'); if (!r || !window.__dn) return;
  r.style.transition = 'none'; r.style.left = window.__dn.x + 'px'; r.style.top = window.__dn.y + 'px';
  r.style.opacity = '1'; r.style.transform = 'scale(.3)'; void r.offsetWidth;
  r.style.transition = 'transform .45s ease-out, opacity .45s ease-out'; r.style.opacity = '0'; r.style.transform = 'scale(1.6)';
})()
"""

NAME_JS = """function () { const a = n => (this.getAttribute && this.getAttribute(n)) || '';
  return a('aria-label') || (this.innerText || '').trim() || this.value || a('title') || a('alt') || a('placeholder') || ''; }"""

HIDE_JS = r"""(function (all) { const r = document.getElementById('__dn_cursor'); if (!r) return;
  if (all) { r.style.display = 'none'; return; }
  for (const id of ['__dn_label', '__dn_box']) { const e = document.getElementById(id); if (e) e.style.opacity = '0'; } })"""


def short(text, n=48):
    t = " ".join(str(text or "").split())
    return t if len(t) <= n else t[: n - 1] + "…"


def describe(node):
    """A few words naming an element, for the cursor's label."""
    if node is None:
        return ""
    attrs = getattr(node, "attributes", None) or {}
    for k in ("aria-label", "title", "placeholder", "alt", "name", "value"):
        if attrs.get(k):
            return short(attrs[k], 40)
    try:
        txt = node.get_all_children_text(max_depth=3) if hasattr(node, "get_all_children_text") else ""
    except Exception:
        txt = ""
    if txt and txt.strip():
        return short(txt, 40)
    tag = (getattr(node, "tag_name", "") or getattr(node, "node_name", "") or "element").lower()
    return {"a": "link", "input": "field", "textarea": "text box", "button": "button"}.get(tag, tag)


class Cursor:
    """Install once per browser session: `Cursor(bs, screen, **cfg).install()`."""

    def __init__(self, bs, screen=None, enabled=True, pace=0.7, move=0.55):
        self.bs, self.screen = bs, screen
        self.enabled, self.pace, self.move = enabled, float(pace), float(move)
        self.pos = (640, 400)
        self.actions = 0                       # how many actions it showed (tests, the episode's log)

    # ── wiring ──
    def install(self):
        if not self.enabled:
            return self
        from browser_use.browser import events as E
        bus = self.bs.event_bus
        if getattr(bus, "_dn_cursor", None) is self:
            return self
        old = getattr(bus, "_dn_cursor", None)
        before = {E.ClickElementEvent: self.on_click, E.ClickCoordinateEvent: self.on_click_xy,
                  E.TypeTextEvent: self.on_type, E.SendKeysEvent: self.on_keys, E.ScrollEvent: self.on_scroll,
                  E.NavigateToUrlEvent: self.on_nav, E.BrowserStateRequestEvent: self.hide}
        for ev, fn in before.items():
            hs = bus.handlers[ev.__name__]
            if old is not None:                # a new episode on the same browser: replace the last one's handlers
                hs[:] = [h for h in hs if getattr(h, "__self__", None) is not old]
            hs.insert(0, fn)                   # first: it runs, and waits, before the action itself
        bus._dn_cursor = self
        return self

    async def _eval(self, expr, cdp=None):
        try:
            cdp = cdp or await asyncio.wait_for(self.bs.get_or_create_cdp_session(), 3)
            r = await asyncio.wait_for(cdp.cdp_client.send.Runtime.evaluate(
                params={"expression": expr, "returnByValue": True}, session_id=cdp.session_id), 3)
            return (r.get("result") or {}).get("value")
        except Exception:
            return None

    async def _show(self, x, y, label, rect=None, click=False, cdp=None):
        """Glide the cursor to (x, y) with a label, wait for the person to see it, ripple on a click."""
        x, y = int(x), int(y)
        o = {"fromX": self.pos[0], "fromY": self.pos[1]}
        ok = await self._eval(f"{OVERLAY_JS}({json.dumps(o)})", cdp)
        if ok:
            ms = int(self.move * 1000)
            await self._eval(f"{SHOW_JS}({json.dumps({'x': x, 'y': y, 'ms': ms, 'label': label, 'rect': rect})})",
                             cdp)
        self.pos = (x, y)
        self.actions += 1
        await asyncio.sleep(self.move + self.pace)
        if click and ok:
            await self._eval(CLICK_JS, cdp)
            await asyncio.sleep(0.15)

    async def _node_point(self, node):
        cdp = await self.bs.cdp_client_for_node(node)
        rect = await self.bs.get_element_coordinates(node.backend_node_id, cdp)
        if not rect:
            return None, None, cdp
        r = {"x": rect.x, "y": rect.y, "width": rect.width, "height": rect.height}
        return (rect.x + rect.width / 2, rect.y + rect.height / 2), r, cdp

    async def _name(self, node, cdp):
        """What a person would call the element: its visible text or label, read from the live page."""
        try:
            send = cdp.cdp_client.send
            obj = await asyncio.wait_for(send.DOM.resolveNode(params={"backendNodeId": node.backend_node_id},
                                                              session_id=cdp.session_id), 2)
            r = await asyncio.wait_for(send.Runtime.callFunctionOn(params={
                "functionDeclaration": NAME_JS, "objectId": obj["object"]["objectId"], "returnByValue": True},
                session_id=cdp.session_id), 2)
            name = short((r.get("result") or {}).get("value") or "", 40)
            if name:
                return name
        except Exception:
            pass
        return describe(node)

    # ── before each action ──
    async def on_click(self, event):
        try:
            pt, rect, cdp = await self._node_point(event.node)
            if pt:
                await self._show(*pt, f"Click “{await self._name(event.node, cdp)}”", rect, click=True, cdp=cdp)
        except Exception:
            pass

    async def on_click_xy(self, event):
        await self._show(event.coordinate_x, event.coordinate_y, "Click", click=True)

    async def on_type(self, event):
        try:
            pt, rect, cdp = await self._node_point(event.node)
            text = "••••••" if getattr(event, "is_sensitive", False) else short(event.text, 40)
            if pt:
                await self._show(*pt, f"Type “{text}”", rect, click=True, cdp=cdp)
        except Exception:
            pass

    async def on_keys(self, event):
        await self._show(*self.pos, f"Press {short(event.keys, 30)}")

    async def on_scroll(self, event):
        await self._show(*self.pos, f"Scroll {event.direction}")

    async def on_nav(self, event):
        """No page element to point at: the console's address bar types the URL out, then the page loads."""
        url = event.url
        if self.screen is not None:
            self.screen.typing = {"url": url, "n": self.actions, "ms": int(min(1600, 250 + 45 * len(url)))}
        await self._eval(f"{HIDE_JS}(false)")
        self.actions += 1
        await asyncio.sleep(min(1.6, 0.25 + 0.045 * len(url)) + self.pace)
        if self.screen is not None:
            self.screen.typing = None

    async def hide(self, event=None):
        """Before browser-use reads the page: the cursor goes, so the model and the DOM snapshot never see it."""
        await self._eval(f"{HIDE_JS}(true)")


# Told to the model in visible mode: act through the page, one action at a time, the way a person would.
HUMAN_LIKE = """A person is watching your browser live and may take over at any moment, so act the way a person would and \
keep every step easy to follow:
- Take exactly one action per step.
- Use `navigate` only to open a site's home page, as if typing it into the address bar. Never navigate to a deep URL \
you guessed or built yourself (a repository, article, search-results or profile URL); reach those pages through the \
site itself: its search box, menus and links.
- To find something, type it into the site's search box and press Enter or click the search button, then click the \
right result.
- Do not use the `search` action; search on the page instead."""
