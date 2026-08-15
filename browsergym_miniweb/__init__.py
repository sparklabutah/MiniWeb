"""Register every MiniWeb task as a BrowserGym gym env (PoC, browser-gym branch).

Importing this module registers ids `browsergym/miniweb.<annotator>.<task>` for
every task under data/annotations that has a verifier.json.

    import browsergym_miniweb          # registers
    gym.make("browsergym/miniweb.Minh.e-commerce_224c4c")

Set MINIWEB_URL to point the tasks at a running MiniWeb server (default
http://localhost:8099).
"""
import glob
import pathlib

from browsergym.core.registration import register_task

from .task import MiniWebTask


def enforce_offline():
    """Network-isolate every Chromium the BrowserGym env launches to localhost.

    BrowserGym's EnvArgs doesn't expose Chromium launch args, so we wrap Playwright's
    launch to always append a DNS-block flag: every host fails to resolve except
    localhost (127.0.0.1 is an IP, unaffected). This keeps the eval offline even
    though the agent now has `goto`. Idempotent."""
    _FLAG = "--host-resolver-rules=MAP * ~NOTFOUND , EXCLUDE localhost"
    for mod in ("sync_api", "async_api"):
        try:
            BrowserType = getattr(__import__(f"playwright.{mod}", fromlist=["BrowserType"]), "BrowserType")
        except Exception:
            continue
        if getattr(BrowserType, "_miniweb_offline", False):
            continue
        _orig = BrowserType.launch

        def _launch(self, *a, __orig=_orig, **kw):
            args = list(kw.get("args") or [])
            if _FLAG not in args:
                args.append(_FLAG)
            kw["args"] = args
            return __orig(self, *a, **kw)

        BrowserType.launch = _launch
        BrowserType._miniweb_offline = True

    _install_blocked_redirect()


def _install_blocked_redirect():
    """Turn blocked external visits into an in-benchmark page (context-level).

    The DNS flag above keeps the browser offline; this layer replaces the raw
    ERR_NAME_NOT_RESOLVED dead end with MiniWeb's own /_blocked page: external
    document navigations 302 to `{MINIWEB_URL}/_blocked?from=<url>` (which
    explains the sandbox and bounces back to the portal), external subresources
    (CDN scripts, fonts, tiles) are aborted. Patched on Browser.new_context so it
    covers every context — BrowserGym envs AND agentlab-assistant's openended
    task, which never runs MiniWebTask.setup. Sync API only (BrowserGym and
    AgentLab drive sync Playwright). Idempotent."""
    try:
        from playwright.sync_api import Browser
    except Exception:
        return
    if getattr(Browser, "_miniweb_blocked", False):
        return

    _LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}

    def _handler(route, request):
        import os
        import urllib.parse
        host = urllib.parse.urlsplit(request.url).hostname or ""
        if host in _LOCAL_HOSTS:
            return route.fallback()
        if request.resource_type == "document":
            base = os.environ.get("MINIWEB_URL", "http://localhost:8099").rstrip("/")
            return route.fulfill(status=302, headers={
                "Location": base + "/_blocked?from=" + urllib.parse.quote(request.url, safe="")})
        return route.abort()

    _orig = Browser.new_context

    def _new_context(self, *a, __orig=_orig, **kw):
        ctx = __orig(self, *a, **kw)
        try:
            ctx.route("**/*", _handler)
        except Exception:
            pass
        return ctx

    Browser.new_context = _new_context
    Browser._miniweb_blocked = True


enforce_offline()


def register_report_answer():
    """Make the report_answer action available wherever the 'chat' subset is used.

    HighLevelActionSetArgs (the AgentLab args wrapper) can't carry custom_actions, so
    instead of a 'custom' subset we append report_answer to the built-in 'chat'
    subset's function list — every action set that includes 'chat' then gets it.
    Idempotent."""
    from browsergym.core.action.highlevel import ACTION_SUBSETS
    from browsergym_miniweb.actions import report_answer, finish_task
    for fn in (report_answer, finish_task):
        if fn not in ACTION_SUBSETS.get("chat", []):
            ACTION_SUBSETS["chat"].append(fn)


register_report_answer()

_ROOT = pathlib.Path(__file__).resolve().parent.parent
ALL_TASK_IDS = []

for _tf in sorted(glob.glob(str(_ROOT / "data" / "annotations" / "*" / "*" / "task.json"))):
    _d = pathlib.Path(_tf).parent
    if not (_d / "verifier.json").exists():
        continue
    _task_id = f"{_d.parent.name}/{_d.name}"          # "Minh/e-commerce_224c4c"
    # register_task auto-prepends "browsergym/"; gym ids can't contain "/"
    _gym_id = "miniweb." + _task_id.replace("/", ".")
    register_task(_gym_id, MiniWebTask, task_kwargs={"task_id": _task_id})
    ALL_TASK_IDS.append(_task_id)
