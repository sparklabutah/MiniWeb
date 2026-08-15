"""Code Editor + Execution -- online Python IDE modeled after GeeksforGeeks IDE.

Serves a snippet gallery, an in-browser code editor, and executes Python code
via subprocess with a 5-second timeout and dangerous-import rejection.
Data lives in data/snippets.json and data/users.json.
"""
import pathlib
import subprocess
import re
import textwrap
import uuid

from flask import (
    Blueprint, Response, abort, jsonify, redirect,
    render_template, request, session, url_for,
)

from app import db
from app.events import emit

SITE = "code-editor-execution"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "code-editor-execution",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Dangerous-import check
# ---------------------------------------------------------------------------

_DANGEROUS_MODULES = {
    "os", "sys", "subprocess", "shutil", "socket", "http", "urllib",
    "requests", "ctypes", "signal", "multiprocessing", "threading",
    "pickle", "shelve", "marshal", "importlib", "builtins", "__builtin__",
    "code", "codeop", "compile", "compileall", "webbrowser", "antigravity",
    "tkinter", "turtle", "pathlib", "glob", "tempfile", "io",
}

def _check_dangerous(code):
    """Return a list of rejected module names found in the code."""
    found = set()
    for mod in _DANGEROUS_MODULES:
        # Match import mod, from mod import ..., __import__('mod')
        patterns = [
            rf'\bimport\s+{re.escape(mod)}\b',
            rf'\bfrom\s+{re.escape(mod)}\b',
            rf"__import__\s*\(\s*['\"]" + re.escape(mod) + r"['\"]",
        ]
        for pat in patterns:
            if re.search(pat, code):
                found.add(mod)
    # Also reject open() for file access
    if re.search(r'\bopen\s*\(', code):
        found.add("open()")
    # Reject exec/eval wrapping attacks
    if re.search(r'\bexec\s*\(', code):
        found.add("exec()")
    if re.search(r'\beval\s*\(', code):
        found.add("eval()")
    return sorted(found)


# ---------------------------------------------------------------------------
# Code execution via subprocess
# ---------------------------------------------------------------------------

def _execute_code(code, timeout=5, stdin=""):
    """Execute Python code in a subprocess. Returns (stdout, stderr, returncode).

    ``stdin`` is fed to the program's standard input so code that calls
    ``input()`` works like it would in a real IDE. It always defaults to an
    empty string (rather than inheriting the server's stdin), so a program
    that reads input without any supplied value gets a clean EOF instead of
    hanging.
    """
    dangerous = _check_dangerous(code)
    if dangerous:
        return ("", f"Blocked: use of {', '.join(dangerous)} is not allowed", 1)
    try:
        result = subprocess.run(
            ["python3", "-c", code],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/tmp",
            input=stdin if stdin is not None else "",
        )
        return (result.stdout, result.stderr, result.returncode)
    except subprocess.TimeoutExpired:
        return ("", f"Error: execution timed out after {timeout} seconds", 1)
    except Exception as e:
        return ("", f"Error: {str(e)}", 1)


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def _load_snippets(language=None, user_id=None, limit=None):
    where = {}
    if language:
        where["language"] = language
    if user_id is not None:
        where["user_id"] = user_id
    return db.query(SITE, "snippets", where=where if where else None, limit=limit)


def _get_snippet(snippet_id):
    return db.get_item(SITE, "snippets", snippet_id)


def _get_categories():
    snippets = _load_snippets()
    cats = sorted(set(s["category"] for s in snippets))
    return cats


# ---------------------------------------------------------------------------
# Users (mutable state)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Snippet gallery / landing page."""
    snippets = _load_snippets()
    categories = _get_categories()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    diff = request.args.get("difficulty", "").strip()
    sort = request.args.get("sort", "id").strip()

    results = list(snippets)

    if q:
        ql = q.lower()
        results = [s for s in results if ql in s["title"].lower()
                   or ql in s["description"].lower()
                   or ql in s["category"].lower()]
    if cat:
        results = [s for s in results if s["category"] == cat]
    if diff:
        results = [s for s in results if s["difficulty"] == diff]

    if sort == "title":
        results.sort(key=lambda s: s["title"].lower())
    elif sort == "difficulty":
        order = {"easy": 0, "medium": 1, "hard": 2}
        results.sort(key=lambda s: order.get(s["difficulty"], 99))
    elif sort == "category":
        results.sort(key=lambda s: s["category"])
    else:
        results.sort(key=lambda s: s["id"])

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("code-editor-execution/index.html",
                           snippets=results, categories=categories,
                           q=q, cat=cat, diff=diff, sort=sort, user=user)


@blueprint.route("/editor")
def editor():
    """Blank code editor page, optionally pre-filled with snippet code."""
    snippet_id = request.args.get("snippet_id", type=int)
    share_token = request.args.get("share", "").strip()
    if not snippet_id and share_token:
        share = db.get_item(SITE, "shares", share_token)
        if share:
            snippet_id = share.get("snippet_id")
    snippet = None
    if snippet_id:
        snippet = _get_snippet(snippet_id)
    user = None
    user_settings = {}
    if "user_id" in session:
        user = _get_user(session["user_id"])
        if user:
            user_settings = user.get("settings", {})
    font_size = request.args.get("font_size") or user_settings.get("font_size", 14)
    tab_size = request.args.get("tab_size") or user_settings.get("tab_size", 4)
    return render_template("code-editor-execution/editor.html",
                           snippet=snippet, font_size=font_size,
                           tab_size=tab_size, user=user)


@blueprint.route("/snippet/<int:snippet_id>")
def snippet_detail(snippet_id):
    """Detail page for a single snippet."""
    snippet = _get_snippet(snippet_id)
    if snippet is None:
        abort(404)
    snippets = _load_snippets()
    related = [s for s in snippets if s["category"] == snippet["category"]
               and s["id"] != snippet_id][:5]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("code-editor-execution/snippet.html",
                           snippet=snippet, related=related, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("code-editor-execution/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("code-editor-execution/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="code-editor-execution", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("code-editor-execution.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("code-editor-execution.index"))


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("code-editor-execution.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("code-editor-execution.login_page"))
    snippets = _load_snippets()
    saved = [s for s in snippets if s["id"] in user.get("saved_snippets", [])]
    settings = user.get("settings", {})
    return render_template("code-editor-execution/dashboard.html",
                           user=user, saved_snippets=saved, settings=settings)


# ---------------------------------------------------------------------------
# Form-based mutation routes
# ---------------------------------------------------------------------------

@blueprint.route("/snippet/<int:snippet_id>/save", methods=["POST"])
def form_save_snippet(snippet_id):
    if "user_id" not in session:
        return redirect(url_for("code-editor-execution.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("code-editor-execution.login_page"))
    saved = user.setdefault("saved_snippets", [])
    if snippet_id in saved:
        saved.remove(snippet_id)
    else:
        saved.append(snippet_id)
    _save_users(users)
    return redirect(url_for("code-editor-execution.snippet_detail", snippet_id=snippet_id))


@blueprint.route("/snippet/<int:snippet_id>/unsave", methods=["POST"])
def form_unsave_snippet(snippet_id):
    if "user_id" not in session:
        return redirect(url_for("code-editor-execution.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("code-editor-execution.login_page"))
    saved = user.setdefault("saved_snippets", [])
    if snippet_id in saved:
        saved.remove(snippet_id)
    _save_users(users)
    return redirect(url_for("code-editor-execution.dashboard"))


@blueprint.route("/settings", methods=["GET", "POST"])
def settings_page():
    """User settings page for editor preferences."""
    if "user_id" not in session:
        return redirect(url_for("code-editor-execution.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("code-editor-execution.login_page"))
    message = None
    if request.method == "POST":
        users = _load_users()
        u = next((u for u in users if u["id"] == session["user_id"]), None)
        if u:
            settings = u.setdefault("settings", {})
            fs = request.form.get("font_size")
            ts = request.form.get("tab_size")
            theme = request.form.get("theme")
            if fs:
                settings["font_size"] = min(max(int(fs), 8), 32)
            if ts:
                settings["tab_size"] = min(max(int(ts), 2), 8)
            if theme:
                settings["theme"] = theme if theme in ("dark", "light") else "dark"
            _save_users(users)
            user = u
            message = "Settings saved successfully."
    return render_template("code-editor-execution/settings.html",
                           user=user, message=message)


@blueprint.route("/upload", methods=["GET", "POST"])
def upload_page():
    """Upload / create a new snippet via form."""
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    message = None
    new_snippet = None
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        code = request.form.get("code", "").strip()
        description = request.form.get("description", "").strip()
        category = request.form.get("category", "custom").strip()
        difficulty = request.form.get("difficulty", "medium").strip()
        if not title or not code:
            message = "Title and code are required."
        else:
            snippets = _load_snippets()
            new_id = max((s["id"] for s in snippets), default=0) + 1
            new_snippet = {
                "id": new_id,
                "title": title,
                "language": "python",
                "code": code,
                "description": description,
                "category": category,
                "difficulty": difficulty,
                "expected_output": "",
            }
            snippets.append(new_snippet)
            db.save_collection(SITE, "snippets", snippets)
            message = f"Snippet '{title}' created with ID {new_id}."
    return render_template("code-editor-execution/upload.html",
                           user=user, message=message, new_snippet=new_snippet)


@blueprint.route("/export")
def export_page():
    """Export snippets page with download links."""
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    categories = _get_categories()
    return render_template("code-editor-execution/export.html",
                           user=user, categories=categories)


@blueprint.route("/execute", methods=["POST"])
def form_execute():
    """Execute code submitted via a form (non-API path)."""
    code = request.form.get("code", "")
    timeout = int(request.form.get("timeout", "5"))
    timeout = min(max(timeout, 1), 10)
    stdin = request.form.get("stdin", "")
    stdout, stderr, rc = _execute_code(code, timeout=timeout, stdin=stdin)
    snippet_id = request.form.get("snippet_id", type=int)
    snippet = _get_snippet(snippet_id) if snippet_id else None
    font_size = request.form.get("font_size", "14")
    tab_size = request.form.get("tab_size", "4")
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("code-editor-execution/editor.html",
                           snippet=snippet, code=code, stdout=stdout,
                           stderr=stderr, returncode=rc, stdin=stdin,
                           font_size=font_size, tab_size=tab_size, user=user)


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/execute", methods=["POST"])
def api_execute():
    """Execute code submitted as JSON. Returns stdout, stderr, returncode."""
    data = request.get_json(silent=True) or {}
    code = data.get("code", "")
    timeout = data.get("timeout", 5)
    timeout = min(max(int(timeout), 1), 10)
    stdin = data.get("stdin", "")
    if not code.strip():
        return jsonify({"error": "No code provided"}), 400
    stdout, stderr, rc = _execute_code(code, timeout=timeout, stdin=stdin)

    # Record in execution history if logged in
    if "user_id" in session:
        users = _load_users()
        user = next((u for u in users if u["id"] == session["user_id"]), None)
        if user:
            history = user.setdefault("execution_history", [])
            history.append({
                "code": code[:500],
                "stdout": stdout[:500],
                "stderr": stderr[:500],
                "returncode": rc,
            })
            # Keep last 50
            user["execution_history"] = history[-50:]
            _save_users(users)

    return jsonify({
        "stdout": stdout,
        "stderr": stderr,
        "returncode": rc,
    })


@blueprint.route("/api/snippets")
def api_snippets():
    """List all snippets, with optional filtering."""
    snippets = _load_snippets()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    diff = request.args.get("difficulty", "").strip()
    sort = request.args.get("sort", "id").strip()
    limit = request.args.get("limit", type=int)

    results = list(snippets)

    if q:
        ql = q.lower()
        results = [s for s in results if ql in s["title"].lower()
                   or ql in s["description"].lower()
                   or ql in s["category"].lower()]
    if cat:
        results = [s for s in results if s["category"] == cat]
    if diff:
        results = [s for s in results if s["difficulty"] == diff]

    if sort == "title":
        results.sort(key=lambda s: s["title"].lower())
    elif sort == "difficulty":
        order = {"easy": 0, "medium": 1, "hard": 2}
        results.sort(key=lambda s: order.get(s["difficulty"], 99))
    elif sort == "category":
        results.sort(key=lambda s: s["category"])
    else:
        results.sort(key=lambda s: s["id"])

    if limit:
        results = results[:limit]

    return jsonify(results)


@blueprint.route("/api/snippets/<int:snippet_id>")
def api_snippet(snippet_id):
    """Get a single snippet by ID."""
    snippet = _get_snippet(snippet_id)
    if snippet is None:
        abort(404)
    return jsonify(snippet)


@blueprint.route("/api/snippets/<int:snippet_id>/run", methods=["POST"])
def api_run_snippet(snippet_id):
    """Execute a stored snippet by ID."""
    snippet = _get_snippet(snippet_id)
    if snippet is None:
        abort(404)
    stdout, stderr, rc = _execute_code(snippet["code"])
    return jsonify({
        "snippet_id": snippet_id,
        "title": snippet["title"],
        "stdout": stdout,
        "stderr": stderr,
        "returncode": rc,
        "expected_output": snippet.get("expected_output", ""),
        "matches_expected": stdout == snippet.get("expected_output", ""),
    })


@blueprint.route("/api/categories")
def api_categories():
    """List all snippet categories with counts."""
    snippets = _load_snippets()
    counts = {}
    for s in snippets:
        c = s["category"]
        counts[c] = counts.get(c, 0) + 1
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/categories/<cat_name>/snippets")
def api_category_snippets(cat_name):
    """Get all snippets in a given category."""
    snippets = _load_snippets()
    return jsonify([s for s in snippets if s["category"] == cat_name])


@blueprint.route("/api/stats")
def api_stats():
    """Aggregate statistics about the snippet collection."""
    snippets = _load_snippets()
    cat = request.args.get("category", "").strip()
    if cat:
        snippets = [s for s in snippets if s["category"] == cat]
    if not snippets:
        return jsonify({"count": 0})
    diff_counts = {}
    cat_counts = {}
    for s in snippets:
        diff_counts[s["difficulty"]] = diff_counts.get(s["difficulty"], 0) + 1
        cat_counts[s["category"]] = cat_counts.get(s["category"], 0) + 1
    return jsonify({
        "count": len(snippets),
        "difficulty_breakdown": diff_counts,
        "category_breakdown": cat_counts,
    })


@blueprint.route("/api/export")
def api_export():
    """Export snippets as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    cat = request.args.get("category", "").strip()
    snippets = list(_load_snippets())
    if cat:
        snippets = [s for s in snippets if s["category"] == cat]

    if fmt == "csv":
        lines = ["id,title,category,difficulty,description"]
        for s in snippets:
            title = s["title"].replace('"', '""')
            desc = s["description"].replace('"', '""')
            lines.append(f'{s["id"]},"{title}","{s["category"]}","{s["difficulty"]}","{desc}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=snippets.csv"})
    return jsonify(snippets)


@blueprint.route("/api/share/<int:snippet_id>")
def api_share(snippet_id):
    """Generate a shareable link for a snippet."""
    snippet = _get_snippet(snippet_id)
    if snippet is None:
        abort(404)
    share_token = uuid.uuid5(uuid.NAMESPACE_URL, f"snippet-{snippet_id}").hex[:12]
    # Persist the token -> snippet mapping in the (overlay-aware) shares collection
    # so it can be resolved later via /s/<token> or ?share=<token>.
    db.save_item(SITE, "shares", share_token, {
        "id": share_token,
        "snippet_id": snippet_id,
    })
    share_url = url_for("code-editor-execution.resolve_share", token=share_token)
    return jsonify({
        "snippet_id": snippet_id,
        "title": snippet["title"],
        "share_token": share_token,
        "share_url": share_url,
    })


@blueprint.route("/s/<token>")
def resolve_share(token):
    """Resolve a share token to its snippet and open it in the editor."""
    share = db.get_item(SITE, "shares", token)
    if not share:
        abort(404)
    return redirect(url_for("code-editor-execution.editor",
                            snippet_id=share["snippet_id"]))


# ---------------------------------------------------------------------------
# User API routes (mutable state)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_save_snippet(user_id):
    """Toggle saving a snippet to a user's saved list."""
    data = request.get_json(silent=True) or {}
    snippet_id = data.get("snippet_id")
    if snippet_id is None:
        return jsonify({"error": "snippet_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_snippets", [])
    if snippet_id in saved:
        saved.remove(snippet_id)
        action = "unsaved"
    else:
        saved.append(snippet_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "snippet_id": snippet_id,
                    "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/history")
def api_user_history(user_id):
    """Get a user's code execution history."""
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify(user.get("execution_history", []))


@blueprint.route("/api/users/<int:user_id>/settings", methods=["GET", "POST"])
def api_user_settings(user_id):
    """Get or update user editor settings (font_size, tab_size, theme)."""
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    if request.method == "GET":
        return jsonify({"settings": user.get("settings", {})})

    data = request.get_json(silent=True) or {}
    settings = user.setdefault("settings", {})
    if "font_size" in data:
        settings["font_size"] = min(max(int(data["font_size"]), 8), 32)
    if "tab_size" in data:
        settings["tab_size"] = min(max(int(data["tab_size"]), 2), 8)
    if "theme" in data:
        settings["theme"] = data["theme"] if data["theme"] in ("dark", "light") else "dark"
    _save_users(users)
    return jsonify({"settings": settings})


@blueprint.route("/api/snippets/upload", methods=["POST"])
def api_upload_snippet():
    """Upload / create a new custom snippet."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    code = data.get("code", "").strip()
    if not title or not code:
        return jsonify({"error": "title and code are required"}), 400

    snippets = _load_snippets()
    new_id = max((s["id"] for s in snippets), default=0) + 1
    new_snippet = {
        "id": new_id,
        "title": title,
        "language": "python",
        "code": code,
        "description": data.get("description", ""),
        "category": data.get("category", "custom"),
        "difficulty": data.get("difficulty", "medium"),
        "expected_output": data.get("expected_output", ""),
    }
    snippets.append(new_snippet)
    db.save_collection(SITE, "snippets", snippets)

    return jsonify(new_snippet), 201


@blueprint.route("/api/snippets/<int:snippet_id>/edit", methods=["POST"])
def api_edit_snippet(snippet_id):
    """Edit an existing snippet's title, code, description, etc."""
    data = request.get_json(silent=True) or {}
    snippets = _load_snippets()
    snippet = next((s for s in snippets if s["id"] == snippet_id), None)
    if snippet is None:
        abort(404)

    if "title" in data:
        snippet["title"] = data["title"].strip()
    if "code" in data:
        snippet["code"] = data["code"]
    if "description" in data:
        snippet["description"] = data["description"].strip()
    if "category" in data:
        snippet["category"] = data["category"].strip()
    if "difficulty" in data:
        snippet["difficulty"] = data["difficulty"].strip()
    if "expected_output" in data:
        snippet["expected_output"] = data["expected_output"]

    db.save_collection(SITE, "snippets", snippets)

    return jsonify(snippet)
