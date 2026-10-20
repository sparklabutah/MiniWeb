"""Public demo mode (MINIWEB_DEMO=1): the sites and a read-only annotation tool, open to anyone.

Visitors never change what other visitors see. Their edits already go to session_overlay, under their own browser
cookie; demo mode adds:

- the site tables refuse every write (db.enable_write_guard), so a bug cannot change them either;
- no LLM calls (helpers/llm.py): the translation site replays the translations recorded in the dataset and translates
  new text with its local NLLB model (sites/translation/routes.py);
- the admin routes that read other visitors' logs or whole tables are closed or bounded;
- a visitor's edits and request logs are dropped after an hour without a request;
- the annotation tool opens with the released tasks filled in and saves nothing (annotation/app.py).

Set up the data with scripts/demo_setup.py; the Hugging Face Space is deploy/space/.
"""
import os
import secrets
import threading
import time

ENABLED = os.environ.get("MINIWEB_DEMO") == "1"

IDLE = 3600          # seconds without a request before a visitor's edits and logs are dropped
SWEEP_EVERY = 120    # how often to look for idle visitors
# Past this many session rows (about 1 GB) the least recently active half of the sessions is dropped too: a client
# without cookies starts a new session on every request, and some pages copy a whole collection into it (one
# translation copies the 7.7K-row history).
MAX_SESSION_ROWS = 2_000_000

# whole-table reads (one request could load a million rows) and the statistics of every session
CLOSED = ("/_admin/user/", "/_overlay_stats")
# ?all=1 merges every visitor's log, ?clear=1 clears every visitor's recording
SHARED_QUERY = {"/_admin/log": ("all",), "/_admin/beacon": ("all",), "/_admin/record": ("all", "clear")}

PILL = ('<a id="miniweb-demo-pill" href="/annotate/" style="position:fixed;left:12px;bottom:12px;'
        'z-index:99999;padding:6px 12px;border-radius:16px;background:#1e293b;color:#f8fafc;'
        'font:13px/1.4 system-ui,sans-serif;text-decoration:none;box-shadow:0 2px 8px rgba(0,0,0,.25)">'
        'MiniWeb demo: your changes are visible only to you &middot; annotation tool &rarr;</a>'
        # not inside the annotation tool, whose task editor shows this page in a frame
        '<script>try{if(window.parent!==window&&window.parent.location.pathname.indexOf("/annotate")===0)'
        'document.getElementById("miniweb-demo-pill").remove()}catch(e){}</script>')


def secret_key():
    """A fresh key per start: sessions end with the server anyway, and the default key would let anyone forge one."""
    return os.environ.get("SECRET_KEY") or secrets.token_hex(32)


def install(app, session_logs):
    """Guard the app's routes and drop idle visitors. `session_logs` are the in-memory per-session logs of
    create_app (requests, action beacons, recordings), keyed by session id."""
    from flask import abort, request, session
    from miniweb.app import db

    db.enable_write_guard()
    seen = {}                    # session id -> last request time
    state = {"swept": time.time()}
    lock = threading.Lock()

    def sweep(now):
        db.evict_stale_sessions()
        cutoff = time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime(now - IDLE))
        conn = db.get_conn()
        conn.execute("DELETE FROM event_log WHERE timestamp < ?", (cutoff,))
        conn.commit()
        if conn.execute("SELECT COUNT(*) FROM session_overlay").fetchone()[0] > MAX_SESSION_ROWS:
            for (sid,) in conn.execute("SELECT session_id FROM sessions ORDER BY last_access "
                                       "LIMIT (SELECT COUNT(*) / 2 FROM sessions)").fetchall():
                db.reset_session(sid)
        for sid in [s for s, t in seen.items() if now - t > IDLE]:
            seen.pop(sid, None)
            for log in session_logs:
                log.pop(sid, None)
        for log in session_logs:     # logs filed under no session id (a request that never read data)
            for sid in [s for s in log if s not in seen]:
                log.pop(sid, None)

    @app.before_request
    def _demo_guard():
        path = request.path
        if path.startswith(CLOSED):
            abort(404)
        if any(request.args.get(k) for k in SHARED_QUERY.get(path, ())):
            abort(403)
        now = time.time()
        if now - state["swept"] > SWEEP_EVERY and lock.acquire(blocking=False):
            try:
                state["swept"] = now
                sweep(now)
            finally:
                lock.release()

    @app.after_request
    def _demo_after(response):
        sid = session.get("_data_overlay_sid") or session.get("_id")   # (a first request gets its id while it runs)
        if sid:
            seen[sid] = time.time()
        if (request.path == "/" and response.status_code == 200 and response.mimetype == "text/html"
                and not response.direct_passthrough):
            html = response.get_data(as_text=True)
            if "</body>" in html:
                response.set_data(html.replace("</body>", PILL + "</body>", 1))
        return response
