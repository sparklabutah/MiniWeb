"""Browser + server plumbing shared by the privileged stages (site map, dry runs)
and the executor.

Each task attempt gets a fresh browser context, hence a fresh Flask session: its
request log (`/_admin/log`, read with the context's own cookies) holds exactly that
attempt's requests, and its mutations land in its own session overlay.
"""
from __future__ import annotations

import json
import time
from contextlib import contextmanager

from datagen import config


# ── servers ───────────────────────────────────────────────────────────────────

def _port_free(port):
    import socket
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _serving(port):
    import urllib.request
    try:
        return urllib.request.urlopen(f"http://{config.HOST}:{port}/", timeout=3).status == 200
    except OSError:
        return False


class Servers:
    """MiniWeb servers on our own ports (config.PORTS). Reuses one already serving on
    a port (e.g. a dev server) and only stops the ones it started."""

    def __init__(self, n=1, ports=None):
        self.ports = list(ports or config.PORTS)[:max(1, n)]
        self.procs = {}

    def __enter__(self):
        from evaluation.server import start_server, wait_for_server
        for port in self.ports:
            if port not in config.PORTS:
                raise ValueError(f"port {port} is outside the datagen range {config.PORTS[0]}–{config.PORTS[-1]}")
            if _serving(port):
                continue
            self.procs[port] = start_server(port)
        for port in self.procs:
            if not wait_for_server(port, host=config.HOST, timeout=120):
                raise RuntimeError(f"MiniWeb server on :{port} did not start")
        return self

    @property
    def bases(self):
        return [f"http://{config.HOST}:{p}" for p in self.ports]

    def __exit__(self, *exc):
        from evaluation.server import stop_server
        for proc in self.procs.values():
            stop_server(proc)


# ── browser ───────────────────────────────────────────────────────────────────

@contextmanager
def browser(headless=True):
    """A Chromium (config.CHROME) for the current thread (sync API: one per thread)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=config.CHROME, headless=headless,
                              args=["--disable-dev-shm-usage", "--no-first-run"])
        try:
            yield b
        finally:
            b.close()


def _focus(ctx, page):
    """Emulate a focused page: headless pages never have focus, and clipboard writes (a site's
    Copy button) reject on an unfocused document."""
    try:
        ctx.new_cdp_session(page).send("Emulation.setFocusEmulationEnabled", {"enabled": True})
    except Exception:
        pass


def new_context(b, viewport=config.VIEWPORT):
    w, h = viewport
    ctx = b.new_context(viewport={"width": w, "height": h}, device_scale_factor=1, locale="en-US",
                        timezone_id="UTC", accept_downloads=True)
    try:
        ctx.grant_permissions(["clipboard-read", "clipboard-write"])
    except Exception:
        pass
    ctx.on("page", lambda page: _focus(ctx, page))
    return ctx


def session_record(ctx, base):
    """This context's recorder stream (/_admin/record: actions incl. clipboard writes)."""
    try:
        r = ctx.request.get(base + "/_admin/record", timeout=20000)
        return (r.json() or {}).get("entries", []) or []
    except Exception:
        return []


def clipboard_writes(ctx, base):
    return [e.get("value") for e in session_record(ctx, base) if e.get("action") == "clipboard_write"]


def settle(page, nav_grace=0.25, idle_cap=1.5):
    """Let the page react to an action: a navigation it started, its load, a short idle."""
    time.sleep(nav_grace)
    try:
        page.wait_for_load_state("load", timeout=10000)
    except Exception:
        pass
    try:   # pages with live polling never go idle — cap the wait
        page.wait_for_load_state("networkidle", timeout=int(idle_cap * 1000))
    except Exception:
        pass


def session_log(ctx, base):
    """This context's own request log (its Flask session), oldest first."""
    try:
        r = ctx.request.get(base + "/_admin/log", timeout=20000)
        return (r.json() or {}).get("entries", []) or []
    except Exception:
        return []


def session_changes(ctx, base, site=None):
    """This context's session data changes vs the base tables (/_admin/changes)."""
    try:
        r = ctx.request.get(base + "/_admin/changes" + (f"?site={site}" if site else ""), timeout=20000)
        return (r.json() or {}).get("changes", []) or []
    except Exception:
        return None


def session_flags(ctx, base, **flags):
    """Privileged session flags for the context's session (/_admin/session-flags)."""
    from urllib.parse import urlencode
    try:
        return ctx.request.get(base + "/_admin/session-flags?" + urlencode({k: "1" for k, v in flags.items() if v}),
                               timeout=20000).json()
    except Exception:
        return None


def goto_start(page, url):
    """The ONE navigation the harness performs: the task's start URL. The session gets its stable
    id first: a first page that reads no data would otherwise log its requests under none."""
    from urllib.parse import urlsplit
    u = urlsplit(url)
    try:
        page.context.request.get(f"{u.scheme}://{u.netloc}/_admin/session-flags", timeout=10000)
    except Exception:
        pass
    page.goto(url, wait_until="load", timeout=30000)
    settle(page)


def site_name(site_id):
    try:
        return json.loads((config.ROOT / "sites" / site_id / "site.json").read_text()).get("name") or site_id
    except (OSError, ValueError):
        return site_id
