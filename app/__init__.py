import importlib
import json
import os
import pathlib
import sqlite3


def _load_dotenv():
    """Load KEY=VALUE pairs from the project .env into os.environ.

    Real environment variables always win — existing keys are not overridden.
    Must run before any module (e.g. app.db) reads os.environ at import time.
    """
    env_path = pathlib.Path(__file__).resolve().parent.parent / ".env"
    if not env_path.exists():
        return
    lines = env_path.read_text().splitlines()
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        i += 1
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:]
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip()
        if value.startswith('"') and not (len(value) > 1 and value.endswith('"')):
            # multi-line double-quoted value (e.g. GOOGLE_CREDENTIALS_JSON)
            parts = [value[1:]]
            while i < len(lines):
                cont = lines[i]
                i += 1
                r = cont.rstrip()
                if r.endswith('"') and not r.endswith('\\"'):
                    parts.append(r[:-1])
                    break
                parts.append(cont)
            # dotenv-style unescaping inside double-quoted values
            value = "\n".join(parts).replace('\\"', '"').replace("\\\\", "\\")
        else:
            value = value.strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_load_dotenv()

from flask import Flask, redirect, request, session

SITES_DIR = pathlib.Path(__file__).resolve().parent.parent / "sites"

_2FA_TEMPLATE = """<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Verify Transaction</title>
<style>
*{box-sizing:border-box;margin:0;padding:0}body{font-family:Arial,sans-serif;background:#f0f2f5;display:flex;justify-content:center;align-items:center;min-height:100vh}
.card{background:#fff;border-radius:12px;box-shadow:0 2px 16px rgba(0,0,0,.1);padding:40px;max-width:420px;width:100%;text-align:center}
.icon{font-size:48px;margin-bottom:16px}h1{font-size:20px;color:#1a1a2e;margin-bottom:8px}
.desc{font-size:14px;color:#666;margin-bottom:24px;line-height:1.5}
.amount{font-size:24px;font-weight:700;color:#e74c3c;margin:12px 0}
.code-input{width:180px;padding:12px;font-size:24px;text-align:center;letter-spacing:8px;border:2px solid #ddd;border-radius:8px;outline:none;font-family:monospace}
.code-input:focus{border-color:#3498db}
.btn{display:block;width:100%;padding:12px;background:#3498db;color:#fff;border:none;border-radius:8px;font-size:16px;cursor:pointer;margin-top:16px}
.btn:hover{background:#2980b9}.error{color:#e74c3c;font-size:13px;margin-top:8px}
.info{font-size:12px;color:#999;margin-top:20px}
</style></head><body>
<div class="card">
<div class="icon">&#128274;</div>
<h1>Verify Your Transaction</h1>
{% if pending %}
<p class="desc">A 6-digit verification code has been sent to your email.<br>Enter it below to complete your transaction.</p>
{% if pending.kwargs.amount %}<div class="amount">${{ "%.2f"|format(pending.kwargs.amount) }}</div>{% endif %}
<form method="post"><input type="text" name="code" class="code-input" maxlength="6" pattern="[0-9]{6}" placeholder="000000" autofocus required>
{% if error %}<div class="error">{{ error }}</div>{% endif %}
<button type="submit" class="btn">Verify & Complete</button></form>
<p class="info">Check your email inbox for the code. It expires in 10 minutes.<br>Tip: Open Email in a new tab using the + button above.</p>
{% else %}
<p class="desc">{{ error or "No pending transaction." }}</p>
<a href="/" class="btn" style="text-decoration:none;display:inline-block;width:auto;padding:12px 32px">Return Home</a>
{% endif %}
</div></body></html>"""
DATA_SOURCES_DIR = pathlib.Path(
    os.environ.get("MINIWEB_DATA_SOURCES", "/scratch/general/vast/u1653932/data_sources")
)


def _is_implemented(site_dir):
    """A site is implemented if it has tasks.json (fully built) or non-stub routes."""
    if (site_dir / "tasks.json").exists():
        return True
    routes = site_dir / "routes.py"
    if routes.exists() and routes.stat().st_size > 500:
        return True
    return False


SITE_CATEGORIES = {
    "academic-paper-db": "Search & Reference", "agency-portals": "Government & Civic",
    "ai-chatbots": "Communication", "auctions-p2p-marketplaces": "Shopping & Transactional",
    "banking": "Financial", "blogs": "Dynamic Info & Feeds", "books-comics": "Streaming & Media",
    "brokerage": "Financial", "business-company": "Static & Informational",
    "calendar-todo": "Productivity",
    "cloud-dev-consoles": "Productivity", "cloud-storage-file-transfer": "Productivity",
    "code-editor-execution": "Editing", "comparison-aggregators": "Search & Reference",
    "conference-review-submission": "Education & LMS", "converters-calculators": "Utilities",
    "course-sites-classrooms": "Education & LMS",
    "crm": "Productivity", "crowdfunding-donations": "Shopping & Transactional",
    "dating": "Communication", "design-creative": "Productivity",
    "dictionaries-language-tools": "Utilities", "documentation-api-docs": "Static & Informational",
    "documents": "Editing", "e-commerce": "Shopping & Transactional", "email": "Communication",
    "flights-hotels": "Shopping & Transactional", "forms-surveys": "Productivity",
    "forums": "Social Media", "handwritten-notes-whiteboards": "Editing",
    "health-fitness-tracking": "Health", "health-portals": "Health",
    "instant-messaging": "Communication", "insurance-loans": "Shopping & Transactional",
    "job-sites": "Shopping & Transactional", "live": "Streaming & Media",
    "map-services": "Maps & Navigation", "multimedia-posting": "Social Media",
    "music": "Streaming & Media", "news": "Dynamic Info & Feeds",
    "password-managers": "Utilities", "personal-portfolio": "Static & Informational",
    "petitions-voting-info": "Government & Civic", "podcasts-audiobooks": "Streaming & Media",
    "project-homepages": "Static & Informational", "project-mgmt-issue-tracking": "Productivity",
    "qa-knowledge": "Search & Reference", "rating-review": "Social Media",
    "real-estate-buy-rent": "Shopping & Transactional", "remote-calls": "Communication",
    "software-marketplace": "Shopping & Transactional", "sports-esports": "Dynamic Info & Feeds",
    "spreadsheets-slides": "Editing",
    "tax-filing-dmv-permits": "Government & Civic", "team-chat-workspace": "Communication",
    "ticketing-events": "Shopping & Transactional", "transit-directions": "Maps & Navigation",
    "translation": "Utilities", "university-academic": "Static & Informational",
    "url-shorteners-qr": "Utilities", "version-control": "Productivity",
    "video": "Streaming & Media", "visual-how-to-guides": "Search & Reference",
    "weather": "Dynamic Info & Feeds", "wikis": "Search & Reference",
}


SITE_DOMAINS = {
    "academic-paper-db": "scholarbase.edu",
    "agency-portals": "lakeport.gov",
    "ai-chatbots": "chatbotshub.ai",
    "auctions-p2p-marketplaces": "bidmarket.com",
    "banking": "securebank.com",
    "blogs": "tumblevibe.com",
    "books-comics": "readshelf.com",
    "brokerage": "tradepulse.com",
    "business-company": "apexdynamics.com",
    "calendar-todo": "calflow.app",
    "cloud-dev-consoles": "meridiancloud.dev",
    "cloud-storage-file-transfer": "meridiancloud.com",
    "code-editor-execution": "codeforge.dev",
    "comparison-aggregators": "comparewise.com",
    "conference-review-submission": "peerportal.org",
    "converters-calculators": "convertall.tools",
    "course-sites-classrooms": "learnhub.edu",
    "crm": "salesflow.io",
    "crowdfunding-donations": "fundspark.com",
    "dating": "sparkconnect.app",
    "design-creative": "canvastudio.design",
    "dictionaries-language-tools": "wordwise.com",
    "documentation-api-docs": "devdocs.io",
    "documents": "meridianflow.com",
    "e-commerce": "shopwave.com",
    "email": "lakeportmail.com",
    "flights-hotels": "skylodge.travel",
    "forms-surveys": "formstack.io",
    "forums": "lakeforum.com",
    "handwritten-notes-whiteboards": "notecraft.app",
    "health-fitness-tracking": "fitpulse.health",
    "health-portals": "lakeportmedical.org",
    "instant-messaging": "quickchat.app",
    "insurance-loans": "cascadiainsure.com",
    "job-sites": "jobscout.careers",
    "live": "livestream.tv",
    "map-services": "cascadiamaps.com",
    "multimedia-posting": "pixshare.social",
    "music": "soundwave.fm",
    "news": "lakeporttimes.com",
    "password-managers": "vaultguard.security",
    "personal-portfolio": "alexrivera.dev",
    "petitions-voting-info": "civicvoice.org",
    "podcasts-audiobooks": "podstream.fm",
    "project-homepages": "flownet.dev",
    "project-mgmt-issue-tracking": "taskflow.pm",
    "qa-knowledge": "askoverflow.com",
    "rating-review": "ratespot.com",
    "real-estate-buy-rent": "lakeportrealty.com",
    "remote-calls": "meetwave.app",
    "software-marketplace": "appvault.store",
    "sports-esports": "lakeportsports.com",
    "spreadsheets-slides": "sheetdeck.app",
    "tax-filing-dmv-permits": "lakeportgov.org",
    "team-chat-workspace": "meridianchat.work",
    "ticketing-events": "eventpass.live",
    "transit-directions": "lakeporttransit.org",
    "translation": "linguabridge.app",
    "university-academic": "meridianstate.edu",
    "url-shorteners-qr": "snplnk.io",
    "version-control": "codehost.dev",
    "video": "streamtube.tv",
    "visual-how-to-guides": "stepvista.com",
    "weather": "lakeportweather.com",
    "wikis": "lakeportwiki.org",
}


def get_site_domain(site_id):
    """Return the simulated domain for a site."""
    return SITE_DOMAINS.get(site_id, f"{site_id}.lakeport.local")


def discover_sites():
    """Scan sites/*/site.json and return only implemented sites."""
    sites = []
    for site_json in sorted(SITES_DIR.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue
        if not _is_implemented(site_json.parent):
            continue
        meta = json.loads(site_json.read_text())
        meta["path"] = f"/sites/{meta['id']}/"
        meta["category"] = SITE_CATEGORIES.get(meta["id"], "Other")
        meta["domain"] = SITE_DOMAINS.get(meta["id"], f"{meta['id']}.lakeport.local")
        sites.append(meta)
    return sites


def register_site_blueprints(app: Flask):
    """Import each implemented site's routes.py and mount its blueprint.

    Set MINIWEB_SITES=site1,site2 to load only specific sites (faster dev startup).
    """
    site_filter = os.environ.get("MINIWEB_SITES")
    allowed = {s.strip() for s in site_filter.split(",")} if site_filter else None

    for site_json in sorted(SITES_DIR.glob("*/site.json")):
        if site_json.parent.name.startswith("_"):
            continue
        if not _is_implemented(site_json.parent):
            continue

        meta = json.loads(site_json.read_text())
        site_id = meta["id"]

        if allowed and site_id not in allowed:
            continue

        site_dir = site_json.parent

        module_path = f"sites.{site_dir.name}.routes"
        module = importlib.import_module(module_path)
        bp = module.blueprint

        app.register_blueprint(bp, url_prefix=f"/sites/{site_id}")


def _register_recovery_routes(app):
    """Token-gated, DB-independent endpoint to replace the SQLite file.

    Exists so a corrupt or half-uploaded database on the persistent volume
    can be replaced through the app itself (the app boots in recovery mode
    even when the DB is unreadable). Enabled only when MINIWEB_RECOVERY_TOKEN
    is set. Chunked + resumable: uploads append to <db>.upload.tmp, then an
    explicit /complete call validates and atomically renames onto the DB.
    """
    import hmac
    import threading
    import time as _time

    from flask import jsonify, request as _req

    from app import db as _db

    def _authed():
        token = os.environ.get("MINIWEB_RECOVERY_TOKEN", "")
        given = _req.headers.get("X-Recovery-Token", "")
        return bool(token) and hmac.compare_digest(token, given)

    def _annotations_dir():
        from annotation.storage import ANNOTATIONS_DIR
        return pathlib.Path(ANNOTATIONS_DIR)

    def _paths(target="db"):
        if target == "annotations":
            ann = _annotations_dir()
            return ann, ann.parent / "annotations.upload.tmp"
        db_path = pathlib.Path(_db._DB_PATH)
        return db_path, db_path.with_suffix(db_path.suffix + ".upload.tmp")

    @app.route("/recovery/db", methods=["GET"])
    def _recovery_status():
        if not _authed():
            return "not found", 404
        db_path, tmp = _paths()
        _, ann_tmp = _paths("annotations")
        return jsonify({
            "db_healthy": bool(app.config.get("DB_HEALTHY")),
            "db_size": db_path.stat().st_size if db_path.exists() else 0,
            "tmp_size": tmp.stat().st_size if tmp.exists() else 0,
            "annotations_tmp_size": ann_tmp.stat().st_size if ann_tmp.exists() else 0,
        })

    @app.route("/recovery/db", methods=["POST"])
    def _recovery_chunk():
        if not _authed():
            return "not found", 404
        _, tmp = _paths(_req.args.get("target", "db"))
        offset = _req.args.get("offset", type=int)
        have = tmp.stat().st_size if tmp.exists() else 0
        if offset is None or (offset != 0 and offset != have):
            # resumable protocol: chunks must append exactly at tmp's end
            return jsonify({"error": "bad offset", "tmp_size": have}), 409
        mode = "wb" if offset == 0 else "ab"
        written = 0
        with open(tmp, mode) as f:
            while True:
                chunk = _req.stream.read(8 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                written += len(chunk)
        return jsonify({"tmp_size": offset + written})

    @app.route("/recovery/db/complete", methods=["POST"])
    def _recovery_complete():
        if not _authed():
            return "not found", 404
        db_path, tmp = _paths()
        if not tmp.exists():
            return jsonify({"error": "no uploaded file"}), 400
        # validate: SQLite header + readable schema
        with open(tmp, "rb") as f:
            if f.read(16) != b"SQLite format 3\x00":
                return jsonify({"error": "not a SQLite database"}), 400
        try:
            check = sqlite3.connect(str(tmp), timeout=30)
            check.execute("PRAGMA schema_version").fetchone()
            n_tables = check.execute(
                "SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0]
            check.close()
        except sqlite3.Error as e:
            return jsonify({"error": f"validation failed: {e}"}), 400
        # stale WAL/SHM from the old file would corrupt the new one
        for suffix in ("-wal", "-shm"):
            side = pathlib.Path(str(db_path) + suffix)
            if side.exists():
                side.unlink()
        os.replace(tmp, db_path)
        # workers hold connections/fds to the old inode — restart the process
        # so every worker reopens the new file (Railway restarts on exit)
        if _req.args.get("restart", "1") != "0":
            def _bye():
                _time.sleep(1.5)
                os._exit(0)
            threading.Thread(target=_bye, daemon=True).start()
        return jsonify({"replaced": True, "tables": n_tables,
                        "restarting": _req.args.get("restart", "1") != "0"})

    @app.route("/recovery/annotations/complete", methods=["POST"])
    def _recovery_annotations_complete():
        """Extract an uploaded tar.gz of task dirs into ANNOTATIONS_DIR.

        Additive by default: task directories in the archive replace their
        counterparts; tasks not present in the archive are left untouched.
        Members must be relative paths shaped like <annotator>/<task_id>/<file>
        (an optional leading 'annotations/' component is stripped).

        With ?prune=1 and a _manifest.json member (a list of
        "annotator/task_id" strings covering the uploader's full live set),
        remote task dirs NOT in the manifest are moved to the .trash — this is
        how local deletions propagate; without it the two copies drift and
        task counts on the deployed tool go stale.
        """
        import tarfile

        if not _authed():
            return "not found", 404
        ann_dir, tmp = _paths("annotations")
        if not tmp.exists():
            return jsonify({"error": "no uploaded file"}), 400
        try:
            tf = tarfile.open(tmp, "r:gz")
            tf.getmembers()          # force full parse: truncated gzip raises here
        except (tarfile.TarError, EOFError, OSError) as e:
            return jsonify({"error": f"not a valid tar.gz: {e}"}), 400
        replaced_dirs, files = set(), 0
        manifest = None
        with tf:
            members = tf.getmembers()
            for m in members:
                parts = pathlib.PurePosixPath(m.name).parts
                if parts and parts[0] in ("annotations", "."):
                    parts = parts[1:]
                if any(p in ("..", "") or p.startswith("/") for p in parts):
                    return jsonify({"error": f"unsafe path: {m.name}"}), 400
                if m.isdir() or not parts:
                    continue
                if list(parts) == ["_manifest.json"] and m.isreg():
                    with tf.extractfile(m) as src:
                        try:
                            manifest = set(json.loads(src.read().decode()))
                        except (ValueError, UnicodeDecodeError):
                            return jsonify({"error": "bad _manifest.json"}), 400
                    continue
                if len(parts) < 3 or not (m.isreg()):
                    return jsonify({"error": f"unexpected member: {m.name} "
                                    "(want <annotator>/<task_id>/<file>)"}), 400
            # second pass: wipe each task dir once, then write files
            import shutil as _shutil
            for m in members:
                if not m.isreg():
                    continue
                parts = pathlib.PurePosixPath(m.name).parts
                if parts[0] in ("annotations", "."):
                    parts = parts[1:]
                if len(parts) < 3:      # _manifest.json and other root files
                    continue
                task_dir = ann_dir / parts[0] / parts[1]
                key = str(task_dir)
                if key not in replaced_dirs:
                    if task_dir.exists():
                        _shutil.rmtree(task_dir)
                    task_dir.mkdir(parents=True, exist_ok=True)
                    replaced_dirs.add(key)
                dest = ann_dir.joinpath(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                with tf.extractfile(m) as src, open(dest, "wb") as out:
                    while True:
                        chunk = src.read(1 << 20)
                        if not chunk:
                            break
                        out.write(chunk)
                files += 1
        tmp.unlink()

        pruned = []
        if _req.args.get("prune") == "1":
            if manifest is None:
                return jsonify({"error": "prune=1 requires _manifest.json in the archive"}), 400
            from annotation.storage import trash_task
            for adir in ann_dir.iterdir():
                if not adir.is_dir() or adir.name.startswith(".") or adir.name == "annotations":
                    continue
                for tdir in adir.iterdir():
                    if not tdir.is_dir() or not (tdir / "task.json").exists():
                        continue
                    if f"{adir.name}/{tdir.name}" not in manifest:
                        dest = trash_task(adir.name, tdir.name)
                        if dest:
                            pruned.append(f"{adir.name}/{tdir.name}")

        return jsonify({"replaced_tasks": len(replaced_dirs), "files": files,
                        "pruned_to_trash": pruned})


def create_app():
    app = Flask(
        __name__,
        static_folder="static",
        static_url_path="/static",
    )
    app.secret_key = os.environ.get("SECRET_KEY", "miniweb-dev-key-change-in-production")

    # Generated images (covers, avatars, thumbnails) live under data/ so they
    # sit on the persistent volume instead of the image/git. URLs stay
    # /static/<sub>/... — this route shadows the bundled static folder for
    # those three subdirs, falling back to it for anything not in data/.
    from flask import send_from_directory
    from pathlib import Path as _Path
    data_static = _Path(os.environ.get(
        "MINIWEB_DATA_STATIC",
        str(_Path(__file__).resolve().parent.parent / "data" / "static")))

    @app.route("/static/<any(generated, avatars, thumbnails):sub>/<path:filename>")
    def _data_static_files(sub, filename):
        target = data_static / sub / filename
        if target.is_file():
            return send_from_directory(data_static / sub, filename)
        return send_from_directory(_Path(app.static_folder) / sub, filename)

    # Session cookie config for production (behind reverse proxy / HTTPS)
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    if os.environ.get("RAILWAY_ENVIRONMENT") or os.environ.get("RAILWAY_PUBLIC_DOMAIN"):
        app.config["SESSION_COOKIE_SECURE"] = True
        app.config["PREFERRED_URL_SCHEME"] = "https"
        from werkzeug.middleware.proxy_fix import ProxyFix
        app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # Initialize SQLite database (per-site tables).
    # All sites use db.query() / db.save_item() for data access.
    # Session mutations are isolated in the session_overlay table.
    # A corrupt/partial DB (e.g. an interrupted volume upload) must not
    # crash-loop the app — boot anyway so /recovery/db can replace it.
    from app import db
    try:
        db.init_db()
        app.config["DB_HEALTHY"] = True
    except sqlite3.Error as e:
        app.config["DB_HEALTHY"] = False
        app.logger.error("DB unusable at boot (%s) — recovery mode; "
                         "replace it via POST /recovery/db", e)

    _register_recovery_routes(app)

    @app.teardown_appcontext
    def _close_db(exc):
        db.close()

    # 2FA verification page for financial transactions
    @app.route("/verify-payment", methods=["GET", "POST"])
    def _verify_payment():
        from flask import jsonify, render_template_string
        from app.events import verify_2fa

        pending = session.get("_pending_2fa")
        if not pending:
            return render_template_string(_2FA_TEMPLATE, error="No pending transaction.", pending=None)

        if request.method == "POST":
            code = request.form.get("code", "").strip()
            success, return_url, error = verify_2fa(code)
            if success:
                return redirect(return_url)
            return render_template_string(_2FA_TEMPLATE, error=error, pending=pending)

        return render_template_string(_2FA_TEMPLATE, error=None, pending=pending)

    # Admin endpoint: view cross-site event log
    @app.route("/_admin/events")
    def _admin_events():
        from flask import jsonify
        from app.events import get_event_log
        sid = session.get("_data_overlay_sid", "")
        return jsonify(get_event_log(session_id=sid if sid else None, limit=100))

    from app.portal.routes import portal_bp
    app.register_blueprint(portal_bp)

    register_site_blueprints(app)

    # Register annotation interface (same origin — enables iframe + trajectory recording)
    from annotation.app import annotation_bp
    app.register_blueprint(annotation_bp)

    # -----------------------------------------------------------------
    # Per-site session namespacing.
    #
    # 58 sites read session["user_id"], but they store incompatible id
    # types in it: ints (1), numeric strings, and site-specific strings
    # ("rc-u-001", "tc-u001", "im-u001", "mp-u-001"). With one shared key,
    # logging into site A leaks A's id into site B — B either resolves the
    # wrong user, silently falls back to "first user", or crashes (the
    # team-chat f"tc-u{uid:03d}" ValueError seen on Railway).
    #
    # Rather than rewrite every site, swap the value in and out around each
    # request: on the way in, load that site's own saved id into
    # session["user_id"]; on the way out, store whatever the site left there
    # back under its own key. Sites keep using session["user_id"] unchanged,
    # but each one now has an isolated login state.
    # -----------------------------------------------------------------
    def _site_of(path):
        parts = path.split("/", 3)
        return parts[2] if len(parts) > 2 and parts[1] == "sites" and parts[2] else None

    @app.before_request
    def _load_site_session():
        site = _site_of(request.path)
        if not site:
            return
        from flask import g
        g._session_site = site
        key = f"_uid_{site}"
        if key in session:
            uid = session[key]
            if uid is None:
                session.pop("user_id", None)   # explicit logout on this site
            else:
                session["user_id"] = uid
        else:
            session.pop("user_id", None)       # no login on this site yet

    @app.after_request
    def _save_site_session(response):
        from flask import g
        site = getattr(g, "_session_site", None)
        if site:
            # None marks "logged out here" and is distinct from "never seen"
            session[f"_uid_{site}"] = session.get("user_id")
        return response

    # Auto-login: default to user 1 on any site request if not logged in.
    # This means tasks don't need an explicit "log in as X" step unless
    # they specifically test authentication or need a different user.
    # Pass MINIWEB_NO_AUTOLOGIN=1 to disable (for browser-agent eval).
    # Registered AFTER _load_site_session so it sees this site's own state.
    if not os.environ.get("MINIWEB_NO_AUTOLOGIN"):
        @app.before_request
        def _auto_login():
            site = _site_of(request.path)
            if not site or session.get("_no_autologin"):
                return
            # only auto-login where this site has no session of its own yet
            if f"_uid_{site}" not in session and "user_id" not in session:
                session["user_id"] = 1

    # -----------------------------------------------------------------
    # Admin API — verification layer for the annotation/eval pipeline.
    # No auth required. Reads go through the data overlay so the
    # evaluator sees the agent's mutations within the same session.
    # -----------------------------------------------------------------

    # Request log — records every /sites/ request for interaction history
    _request_logs = {}  # session_id -> [entries]

    @app.before_request
    def _log_request():
        if not request.path.startswith("/sites/"):
            return
        from flask import g
        g._req_start = __import__("time").time()

    @app.after_request
    def _log_response(response):
        if not request.path.startswith("/sites/"):
            return response
        from flask import g
        sid = session.get("_id", id(session))
        if sid not in _request_logs:
            _request_logs[sid] = []
        entry = {
            "method": request.method,
            "path": request.path,
            "query": dict(request.args),
            "status": response.status_code,
            "timestamp": __import__("datetime").datetime.now().isoformat(),
        }
        # Capture request body for mutations
        if request.method in ("POST", "PUT", "DELETE"):
            try:
                body = request.get_json(silent=True)
                if body:
                    entry["body"] = body
                elif request.form:
                    entry["body"] = dict(request.form)
            except Exception:
                pass
        # Capture response snippet for API calls
        if "/api/" in request.path and response.content_type == "application/json":
            try:
                resp_text = response.get_data(as_text=True)
                if len(resp_text) < 500:
                    entry["response"] = json.loads(resp_text)
                else:
                    entry["response_preview"] = resp_text[:200] + "..."
            except Exception:
                pass
        elapsed = getattr(g, "_req_start", None)
        if elapsed:
            entry["duration_ms"] = round((__import__("time").time() - elapsed) * 1000)
        _request_logs[sid].append(entry)
        # Cap at 500 entries per session
        if len(_request_logs[sid]) > 500:
            _request_logs[sid] = _request_logs[sid][-500:]
        return response

    @app.route("/_admin/data/<site_id>/<collection>")
    def _admin_data(site_id, collection):
        """Read a site's collection from SQLite. Supports filtering, field extraction, counting."""
        from flask import jsonify, abort
        # Strip .json suffix if present (backward compat)
        if collection.endswith(".json"):
            collection = collection[:-5]

        data = db.query(site_id, collection)
        if not data and not db.get_table_name(site_id, collection):
            abort(404)

        # Filter by query params (e.g. ?user_id=1&status=paid)
        if isinstance(data, list) and request.args:
            for key, val in request.args.items():
                if key.startswith("_"):
                    continue
                data = [item for item in data if str(item.get(key, "")) == val]

        # Get by ID (e.g. ?_id=3)
        _id = request.args.get("_id")
        if _id and isinstance(data, list):
            item = next(
                (d for d in data if str(d.get("id", "")) == _id), None
            )
            if item is None:
                abort(404)
            return jsonify(item)

        # Extract a field (e.g. ?_field=username)
        _field = request.args.get("_field")
        if _field and isinstance(data, list):
            return jsonify([d.get(_field) for d in data])

        # Return just the count (e.g. ?_count=1)
        if request.args.get("_count") and isinstance(data, list):
            return jsonify({"count": len(data)})

        return jsonify(data)

    @app.route("/_admin/files/<site_id>")
    def _admin_files(site_id):
        """List collections for a site."""
        from flask import jsonify
        collections = db.list_collections(site_id)
        return jsonify(collections)

    @app.route("/_admin/user/<site_id>/<int:user_id>")
    def _admin_user(site_id, user_id):
        """Get all data for a specific user across all collections.

        Aggregates: user profile + any records where user_id/author_id/
        seller_id/sender_id matches.
        """
        from flask import jsonify, abort
        collections = db.list_collections(site_id)
        if not collections:
            abort(404)

        result = {"user_id": user_id, "site": site_id}
        user_id_str = str(user_id)
        USER_REF_FIELDS = ("user_id", "author_id", "seller_id", "sender_id",
                           "owner_id", "creator_id", "reviewer_id", "buyer_id")

        for coll in collections:
            data = db.query(site_id, coll)
            if not data:
                continue

            if coll == "users" and isinstance(data, list):
                user = next((u for u in data if str(u.get("id", "")) == user_id_str), None)
                if user:
                    result["profile"] = {k: v for k, v in user.items() if k != "password"}
            elif isinstance(data, list) and data:
                sample = data[0]
                ref_field = next((rf for rf in USER_REF_FIELDS if rf in sample), None)
                if ref_field:
                    user_records = [d for d in data if str(d.get(ref_field, "")) == user_id_str]
                    if user_records:
                        result[coll] = user_records
                        result[f"{coll}_count"] = len(user_records)

        if "profile" not in result:
            abort(404)
        return jsonify(result)

    @app.route("/_admin/log")
    def _admin_log():
        """Get the request log for the current session.

        Shows all /sites/ HTTP requests made in this session — methods,
        paths, bodies, responses, timestamps. Use for verifying that the
        agent performed the expected API interactions.

        Query params:
          ?method=POST  — filter by HTTP method
          ?path=transfer — filter by path substring
          ?last=N       — only the last N entries
        """
        from flask import jsonify
        if request.args.get("all") == "1":
            log = [e for s in _request_logs.values() for e in s]
        else:
            log = list(_request_logs.get(session.get("_id", id(session)), []))

        method_filter = request.args.get("method", "").upper()
        path_filter = request.args.get("path", "")
        last_n = request.args.get("last", type=int)

        if method_filter:
            log = [e for e in log if e["method"] == method_filter]
        if path_filter:
            log = [e for e in log if path_filter in e["path"]]
        if last_n:
            log = log[-last_n:]

        return jsonify({"count": len(log), "entries": log})

    @app.route("/_admin/log/clear", methods=["POST"])
    def _admin_log_clear():
        """Clear the request log for the current session."""
        from flask import jsonify
        sid = session.get("_id", id(session))
        _request_logs.pop(sid, None)
        _action_beacons.pop(sid, None)
        return jsonify({"status": "cleared"})

    # ── Action beacon — UI-level action log from recorder.js ──────────
    _action_beacons = {}  # session_id -> [entries]

    @app.route("/_admin/beacon", methods=["POST"])
    def _admin_beacon():
        """Receive UI action beacons from recorder.js.

        Every click, type, select, submit, navigation fires a beacon here.
        Works identically for human annotators and browser-use agents.
        """
        sid = session.get("_id", id(session))
        if sid not in _action_beacons:
            _action_beacons[sid] = []

        data = request.get_json(silent=True) or {}
        if not data.get("action"):
            return "", 204

        entry = {
            "action": data.get("action", ""),
            "target": data.get("target", ""),
            "selector": data.get("selector", ""),
            "url": data.get("url", ""),
            "timestamp": data.get("timestamp", ""),
            "x": data.get("x"),
            "y": data.get("y"),
            "value": data.get("value"),
            "text": data.get("text"),
            "option_text": data.get("option_text"),
            "href": data.get("href"),
            "key": data.get("key"),
            "checked": data.get("checked"),
            "formData": data.get("formData"),
        }
        # Strip None values
        entry = {k: v for k, v in entry.items() if v is not None}
        _action_beacons[sid].append(entry)

        # Cap at 1000
        if len(_action_beacons[sid]) > 1000:
            _action_beacons[sid] = _action_beacons[sid][-1000:]

        return "", 204

    @app.route("/_admin/beacon")
    def _admin_beacon_get():
        """Read the action beacon log.

        ?all=1 merges every session (see /_admin/record) — for harnesses
        reading an agent browser's beacons from outside its session.
        """
        from flask import jsonify
        if request.args.get("all") == "1":
            entries = [e for s in _action_beacons.values() for e in s]
        else:
            entries = _action_beacons.get(session.get("_id", id(session)), [])
        return jsonify({"count": len(entries), "entries": entries})

    # ------------------------------------------------------------------
    # Recorder collector — the same action+observation stream recorder.js
    # sends to the annotation iframe, but for runs with no parent window
    # (browser agents). Lets an agent trajectory be recorded in exactly the
    # human trajectory.json schema.
    # ------------------------------------------------------------------
    _recorder_stream = {}   # session_id -> [records]

    @app.route("/_admin/record", methods=["POST"])
    def _admin_record():
        sid = _sid_for_recording()
        data = request.get_json(silent=True) or {}
        kind = data.get("mw")
        if kind not in ("action", "observation"):
            return "", 204

        from datetime import datetime, timezone
        rec = {k: v for k, v in data.items() if k != "mw"}
        rec["type"] = kind
        rec.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        stream = _recorder_stream.setdefault(sid, [])
        stream.append(rec)
        if len(stream) > 5000:
            del stream[:-5000]
        return "", 204

    @app.route("/_admin/record")
    def _admin_record_get():
        """Read the recorded stream.

        ?all=1 merges every session on this server, ordered by timestamp —
        needed when the reader is not the browser that produced the records
        (an eval harness fetching an agent's trajectory). Only meaningful on
        a single-run server; the default is the caller's own session.
        """
        from flask import jsonify
        if request.args.get("all") == "1":
            entries = [e for s in _recorder_stream.values() for e in s]
            entries.sort(key=lambda e: e.get("timestamp", ""))
        else:
            entries = _recorder_stream.get(_sid_for_recording(), [])
        if request.args.get("clear") == "1":
            _recorder_stream.clear()
        return jsonify({"count": len(entries), "entries": entries})

    def _sid_for_recording():
        # Agents drive a real browser, so the Flask session cookie is stable
        # for the run; fall back to the data-overlay id used elsewhere.
        return session.get("_data_overlay_sid") or session.get("_id") or id(session)

    @app.route("/_admin/session")
    def _admin_session():
        """Expose current Flask session state for verification."""
        from flask import jsonify
        return jsonify({k: v for k, v in session.items()
                        if not k.startswith("_")})

    @app.route("/_reset_data", methods=["POST"])
    def _reset_data():
        """Reset session overlay (revert site data to pristine) and clear session."""
        # Get current session ID before clearing
        sid = session.get("_data_overlay_sid", "")
        # Clear the overlay for this session
        if sid:
            db.reset_session(sid)
        # Clear Flask session (user_id, login state, etc.)
        # Preserve annotator auth so reset doesn't log out the annotator
        annotator_auth = session.get("annotator_authenticated")
        annotator_name = session.get("annotator_name")
        disable_2fa = session.get("_disable_2fa")
        session.clear()
        if annotator_auth:
            session["annotator_authenticated"] = annotator_auth
            session["annotator_name"] = annotator_name
        if disable_2fa:
            session["_disable_2fa"] = disable_2fa
        # Also clear request logs and beacons
        _request_logs.pop(sid, None) if sid else None
        _action_beacons.pop(sid, None) if sid else None
        return {"status": "reset", "cleared_sid": sid}

    @app.route("/_overlay_stats")
    def _overlay_stats():
        return db.get_stats()

    # -----------------------------------------------------------------
    # Broken-image fallback — inject a small script into every HTML
    # response under /sites/ that replaces broken <img> elements with
    # styled placeholder <div>s showing the alt text.  This avoids
    # broken-image icons across all sites without touching individual
    # templates.
    # -----------------------------------------------------------------
    _BROKEN_IMG_SCRIPT = b"""<script>(function(){
function fix(img){
var d=document.createElement('div');
d.textContent=img.alt||'Image';
d.style.cssText='background:#f1f5f9;display:flex;align-items:center;justify-content:center;color:#94a3b8;font-size:.75rem;border:1px dashed #cbd5e1;border-radius:.25rem;padding:.5rem;min-height:80px;overflow:hidden;';
d.style.width=img.width?img.width+'px':'100%';
d.style.height=img.height?img.height+'px':'120px';
if(img.className)d.className=img.className;
img.parentNode.replaceChild(d,img);
}
document.addEventListener('DOMContentLoaded',function(){
document.querySelectorAll('img').forEach(function(img){
img.onerror=function(){this.onerror=null;fix(this);};
if(img.complete&&img.naturalWidth===0&&img.src)fix(img);
});
});
})()</script>"""

    _RECORDER_SCRIPT = b'<script src="/static/recorder.js"></script>'
    _FILE_PICKER_SCRIPT = b'<script src="/static/file-picker.js"></script>'
    _EXPORT_FEEDBACK_SCRIPT = b'<script src="/static/export-feedback.js"></script>'
    # Shared video player — enhances any [data-mini-player] container across all sites.
    _PLAYER_ASSETS = b'<link rel="stylesheet" href="/static/player.css"><script src="/static/player.js"></script>'

    @app.after_request
    def _inject_site_scripts(response):
        if (request.path.startswith("/sites/")
                and response.content_type
                and "text/html" in response.content_type
                and response.status_code == 200):
            data = response.get_data()
            inject = (_BROKEN_IMG_SCRIPT + b"\n" + _RECORDER_SCRIPT + b"\n" + _FILE_PICKER_SCRIPT
                      + b"\n" + _EXPORT_FEEDBACK_SCRIPT + b"\n" + _PLAYER_ASSETS)
            idx = data.rfind(b"</body>")
            if idx != -1:
                response.set_data(data[:idx] + inject + b"\n" + data[idx:])
            else:
                response.set_data(data + inject)
        return response

    # Register cross-site event handlers (must be after all imports settle)
    __import__("app.handlers")  # triggers @on() decorator registration

    return app
