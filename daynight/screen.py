"""The console's live view of the agent's browser (real backend): frames out, the human's input in, over CDP.

The agent's browser-use session stays the only browser. `Screen` grabs a JPEG of the current tab `fps` times a second
(Page.captureScreenshot) and saves one every `save_every` seconds to the episode's `frames/`, named by who was in
control. During a takeover the console forwards the person's mouse and keys into the same tab (Input.dispatch*), so
MiniWeb's page recorder logs their actions exactly as it logs the agent's. Uses the CDP calls webmix.harness makes
(`get_or_create_cdp_session`, `cdp_client.send.<Domain>.<method>`).
"""
from __future__ import annotations

import asyncio
import base64
import time
from pathlib import Path

# Keys that type nothing: CDP needs their Windows key code to act (a Backspace without one deletes nothing).
KEY_CODES = {"Backspace": 8, "Tab": 9, "Enter": 13, "Escape": 27, "PageUp": 33, "PageDown": 34, "End": 35,
             "Home": 36, "ArrowLeft": 37, "ArrowUp": 38, "ArrowRight": 39, "ArrowDown": 40, "Delete": 46}
MODS = {"alt": 1, "ctrl": 2, "meta": 4, "shift": 8}


class Screen:
    def __init__(self, bs, base, fps=4, save_dir=None, save_every=1.0, who=lambda: "agent"):
        self.bs, self.base, self.fps = bs, base, fps
        self.save_dir, self.save_every, self.who = Path(save_dir) if save_dir else None, save_every, who
        self.jpeg, self.n, self.url, self.error = None, 0, "", None
        self._task, self._t0, self._saved = None, time.time(), 0.0

    async def _cdp(self):
        cdp = await self.bs.get_or_create_cdp_session()
        return cdp.cdp_client.send, cdp.session_id

    async def start(self):
        if self.save_dir:
            self.save_dir.mkdir(parents=True, exist_ok=True)
        self._task = asyncio.ensure_future(self._loop())

    async def stop(self):
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):
                pass

    async def _loop(self):
        while True:
            try:
                send, sid = await self._cdp()
                r = await send.Page.captureScreenshot(params={"format": "jpeg", "quality": 70}, session_id=sid)
                self.jpeg, self.n = base64.b64decode(r["data"]), self.n + 1
                u = await send.Runtime.evaluate(params={"expression": "location.href", "returnByValue": True},
                                                session_id=sid)
                self.url, self.error = (u.get("result") or {}).get("value") or self.url, None
                now = time.time()
                if self.save_dir and now - self._saved >= self.save_every:
                    self._saved = now
                    (self.save_dir / f"{now - self._t0:08.1f}_{self.who()}.jpg").write_bytes(self.jpeg)
            except asyncio.CancelledError:
                raise
            except Exception as e:                   # a navigation in flight, a closed tab: try the next frame
                self.error = f"{type(e).__name__}: {str(e)[:120]}"
            await asyncio.sleep(1 / self.fps)

    async def input(self, ev):
        """One input event from the console, in page pixels (the screenshot's size: device scale factor 1)."""
        send, sid = await self._cdp()
        kind = ev.get("type")
        if kind in ("down", "up", "move"):
            p = {"type": {"down": "mousePressed", "up": "mouseReleased", "move": "mouseMoved"}[kind],
                 "x": float(ev["x"]), "y": float(ev["y"]), "modifiers": _mods(ev),
                 "button": "left" if kind != "move" or ev.get("buttons") else "none",
                 "buttons": 1 if kind == "down" or (kind == "move" and ev.get("buttons")) else 0}
            if kind != "move":
                p["clickCount"] = int(ev.get("clicks") or 1)
            await send.Input.dispatchMouseEvent(params=p, session_id=sid)
        elif kind == "wheel":
            await send.Input.dispatchMouseEvent(params={"type": "mouseWheel", "x": float(ev["x"]), "y": float(ev["y"]),
                                                        "deltaX": float(ev.get("dx") or 0),
                                                        "deltaY": float(ev.get("dy") or 0)}, session_id=sid)
        elif kind == "key":
            key, mods = ev.get("key") or "", _mods(ev)
            printable = len(key) == 1 and not mods & (MODS["ctrl"] | MODS["meta"] | MODS["alt"])
            down = {"type": "keyDown" if printable or key == "Enter" else "rawKeyDown", "key": key,
                    "code": ev.get("code") or "", "modifiers": mods,
                    "windowsVirtualKeyCode": KEY_CODES.get(key) or (ord(key.upper()) if len(key) == 1 else 0)}
            if printable:
                down.update(text=key, unmodifiedText=key)
            elif key == "Enter":
                down.update(text="\r", unmodifiedText="\r")
            await send.Input.dispatchKeyEvent(params=down, session_id=sid)
            await send.Input.dispatchKeyEvent(params={k: v for k, v in down.items()
                                                      if k not in ("text", "unmodifiedText")} | {"type": "keyUp"},
                                              session_id=sid)
        elif kind == "text" and ev.get("text"):
            await send.Input.insertText(params={"text": str(ev["text"])}, session_id=sid)

    async def navigate(self, what):
        """`what`: "back", "reload", or a path / URL on this MiniWeb server (the agent's browser is localhost-only)."""
        from webmix import harness as H
        send, sid = await self._cdp()
        if what in ("back", "reload"):
            js = "history.back()" if what == "back" else "location.reload()"
            await send.Runtime.evaluate(params={"expression": js}, session_id=sid)
            return
        url = what if what.startswith("http") else self.base + "/" + what.lstrip("/")
        if not url.startswith(self.base):
            raise ValueError(f"only pages of {self.base}")
        await H.goto(self.bs, url)


def _mods(ev):
    return sum(v for k, v in MODS.items() if ev.get(k))
