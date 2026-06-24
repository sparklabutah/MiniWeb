"""Documents -- collaborative document editing platform (Google Docs style).

Reads JSON data files for documents, users, folders, and revisions.
Supports full CRUD, sharing/permissions, starring, trash, and folder organization.
"""
import json
import pathlib
import copy
from datetime import datetime

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
DOCUMENTS_FILE = SITE_DIR / "data" / "documents.json"
USERS_FILE = SITE_DIR / "data" / "users.json"
FOLDERS_FILE = SITE_DIR / "data" / "folders.json"
REVISIONS_FILE = SITE_DIR / "data" / "revisions.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "documents",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _load_json(path):
    if path.exists():
        return json.loads(path.read_text())
    return []


def _save_json(path, data):
    path.write_text(json.dumps(data, indent=2))


def _load_documents():
    return _load_json(DOCUMENTS_FILE)


def _save_documents(docs):
    _save_json(DOCUMENTS_FILE, docs)


def _load_users():
    return _load_json(USERS_FILE)


def _save_users(users):
    _save_json(USERS_FILE, users)


def _load_folders():
    return _load_json(FOLDERS_FILE)


def _save_folders(folders):
    _save_json(FOLDERS_FILE, folders)


def _load_revisions():
    return _load_json(REVISIONS_FILE)


def _save_revisions(revisions):
    _save_json(REVISIONS_FILE, revisions)


# ---------------------------------------------------------------------------
# User helpers
# ---------------------------------------------------------------------------

def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _user_can_access(doc, user_id):
    """Check if a user can at least view a document."""
    if doc["owner_id"] == user_id:
        return True
    for c in doc.get("collaborators", []):
        if c["user_id"] == user_id:
            return True
    return False


def _user_permission(doc, user_id):
    """Return the permission level for a user on a document: 'owner', 'edit', 'comment', 'view', or None."""
    if doc["owner_id"] == user_id:
        return "owner"
    for c in doc.get("collaborators", []):
        if c["user_id"] == user_id:
            return c["permission"]
    return None


def _user_can_edit(doc, user_id):
    perm = _user_permission(doc, user_id)
    return perm in ("owner", "edit")


# ---------------------------------------------------------------------------
# Search helper
# ---------------------------------------------------------------------------

def _search_documents(docs, query):
    if not query:
        return docs
    q = query.lower().strip()
    results = []
    for d in docs:
        text = (d["title"] + " " + d["content"]).lower()
        if q in text:
            results.append(d)
    return results


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    """Dashboard / document list showing all non-trashed documents."""
    user = _current_user()
    docs = _load_documents()
    folders = _load_folders()
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "updated").strip()
    folder_filter = request.args.get("folder_id", "", type=str).strip()
    owner_filter = request.args.get("owner_id", "", type=str).strip()

    # Filter out trashed documents
    visible = [d for d in docs if not d.get("is_trashed", False)]

    if q:
        visible = _search_documents(visible, q)

    if folder_filter:
        try:
            fid = int(folder_filter)
            visible = [d for d in visible if d.get("folder_id") == fid]
        except ValueError:
            pass

    if owner_filter:
        try:
            oid = int(owner_filter)
            visible = [d for d in visible if d["owner_id"] == oid]
        except ValueError:
            pass

    # Sorting
    if sort == "title":
        visible.sort(key=lambda d: d["title"].lower())
    elif sort == "created":
        visible.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    elif sort == "name_asc":
        visible.sort(key=lambda d: d["title"].lower())
    elif sort == "name_desc":
        visible.sort(key=lambda d: d["title"].lower(), reverse=True)
    else:  # "updated" default
        visible.sort(key=lambda d: d.get("updated_at", ""), reverse=True)

    return render_template("documents/index.html",
                           documents=visible, folders=folders, user=user,
                           user_map=user_map, users=users, q=q, sort=sort,
                           folder_filter=folder_filter, owner_filter=owner_filter)


@blueprint.route("/editor/<int:doc_id>")
def editor(doc_id):
    """Document editor page."""
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        abort(404)
    user = _current_user()
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    revisions = [r for r in _load_revisions() if r["document_id"] == doc_id]
    revisions.sort(key=lambda r: r["timestamp"], reverse=True)
    can_edit = user and _user_can_edit(doc, user["id"])
    permission = _user_permission(doc, user["id"]) if user else None
    return render_template("documents/editor.html", doc=doc, user=user,
                           user_map=user_map, users=users, revisions=revisions,
                           can_edit=can_edit, permission=permission)


@blueprint.route("/view/<int:doc_id>")
def view_doc(doc_id):
    """Read-only document view."""
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        abort(404)
    user = _current_user()
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    revisions = [r for r in _load_revisions() if r["document_id"] == doc_id]
    revisions.sort(key=lambda r: r["timestamp"], reverse=True)
    permission = _user_permission(doc, user["id"]) if user else None
    return render_template("documents/view.html", doc=doc, user=user,
                           user_map=user_map, revisions=revisions,
                           permission=permission)


@blueprint.route("/folder/<int:folder_id>")
def folder_view(folder_id):
    """Show documents in a specific folder."""
    folders = _load_folders()
    folder = next((f for f in folders if f["id"] == folder_id), None)
    if folder is None:
        abort(404)
    user = _current_user()
    docs = _load_documents()
    folder_docs = [d for d in docs if d.get("folder_id") == folder_id
                   and not d.get("is_trashed", False)]

    folder_docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
    users = _load_users()
    user_map = {u["id"]: u for u in users}

    return render_template("documents/folder.html", folder=folder,
                           documents=folder_docs, user=user,
                           user_map=user_map, folders=_load_folders())


@blueprint.route("/starred")
def starred():
    """Show starred documents (no login required for viewing)."""
    user = _current_user()
    docs = _load_documents()
    starred_docs = [d for d in docs if d.get("is_starred", False)
                    and not d.get("is_trashed", False)]
    starred_docs.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    return render_template("documents/starred.html", documents=starred_docs,
                           user=user, user_map=user_map)


@blueprint.route("/trash")
def trash():
    """Show trashed documents (no login required for viewing)."""
    user = _current_user()
    docs = _load_documents()
    trashed = [d for d in docs if d.get("is_trashed", False)]
    trashed.sort(key=lambda d: d.get("updated_at", ""), reverse=True)
    users = _load_users()
    user_map = {u["id"]: u for u in users}
    return render_template("documents/trash.html", documents=trashed,
                           user=user, user_map=user_map)


@blueprint.route("/new")
def new_doc_page():
    """Form to create a new document."""
    user = _current_user()
    folders = _load_folders()
    users = _load_users()
    return render_template("documents/new.html", user=user, folders=folders, users=users)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("documents/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("documents/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    next_url = request.form.get("next") or request.args.get("next")
    if next_url:
        return redirect(next_url)
    return redirect(url_for("documents.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("documents.login_page"))


# ---------------------------------------------------------------------------
# Form-based mutation routes (browser automation compatible)
# ---------------------------------------------------------------------------

@blueprint.route("/document/<int:doc_id>/star", methods=["POST"])
def form_star_document(doc_id):
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        abort(404)
    doc["is_starred"] = not doc.get("is_starred", False)
    _save_documents(docs)
    redirect_to = request.form.get("redirect_to")
    if redirect_to:
        return redirect(redirect_to)
    return redirect(url_for("documents.index"))


@blueprint.route("/document/<int:doc_id>/trash", methods=["POST"])
def form_trash_document(doc_id):
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        abort(404)
    user = _current_user()
    if doc["owner_id"] != user["id"]:
        abort(403)
    doc["is_trashed"] = True
    doc["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_documents(docs)
    return redirect(url_for("documents.index"))


@blueprint.route("/document/<int:doc_id>/restore", methods=["POST"])
def form_restore_document(doc_id):
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        abort(404)
    user = _current_user()
    if doc["owner_id"] != user["id"]:
        abort(403)
    doc["is_trashed"] = False
    doc["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_documents(docs)
    return redirect(url_for("documents.trash"))


@blueprint.route("/document/<int:doc_id>/delete", methods=["POST"])
def form_delete_document(doc_id):
    """Permanently delete a trashed document."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        abort(404)
    user = _current_user()
    if doc["owner_id"] != user["id"]:
        abort(403)
    docs = [d for d in docs if d["id"] != doc_id]
    _save_documents(docs)
    # Also remove revisions for this document
    revisions = _load_revisions()
    revisions = [r for r in revisions if r["document_id"] != doc_id]
    _save_revisions(revisions)
    return redirect(url_for("documents.trash"))


@blueprint.route("/document/<int:doc_id>/share", methods=["POST"])
def form_share_document(doc_id):
    """Add a collaborator to a document via form submission."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        abort(404)

    user_id = request.form.get("user_id", type=int)
    permission = request.form.get("permission", "view")
    if not user_id:
        return redirect(url_for("documents.editor", doc_id=doc_id))
    if permission not in ("view", "comment", "edit"):
        permission = "view"

    collaborators = doc.setdefault("collaborators", [])
    existing = next((c for c in collaborators if c["user_id"] == user_id), None)
    if existing:
        existing["permission"] = permission
    else:
        collaborators.append({"user_id": user_id, "permission": permission})

    _save_documents(docs)
    return redirect(url_for("documents.editor", doc_id=doc_id))


@blueprint.route("/document/<int:doc_id>/update", methods=["POST"])
def form_update_document(doc_id):
    """Update a document title/content via form submission."""
    if "user_id" not in session:
        return jsonify({"error": "Authentication required"}), 401
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if not doc:
        abort(404)

    user = _current_user()
    if not _user_can_edit(doc, user["id"]):
        abort(403)

    title = request.form.get("title", "").strip()
    content = request.form.get("content", "")

    changed = False
    if title and title != doc["title"]:
        doc["title"] = title
        changed = True
    if content != doc["content"]:
        doc["content"] = content
        doc["word_count"] = len(content.split()) if content.strip() else 0
        changed = True

    if changed:
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        doc["updated_at"] = now
        _save_documents(docs)

        revisions = _load_revisions()
        rev_id = max((r["id"] for r in revisions), default=0) + 1
        revisions.append({
            "id": rev_id,
            "document_id": doc_id,
            "user_id": user["id"],
            "timestamp": now,
            "summary": "Updated via form",
        })
        _save_revisions(revisions)

    return redirect(url_for("documents.editor", doc_id=doc_id))


@blueprint.route("/document/create", methods=["POST"])
def form_create_document():
    """Create a new document via form submission."""
    title = request.form.get("title", "Untitled Document").strip()
    content = request.form.get("content", "").strip()
    owner_id = request.form.get("owner_id", type=int)
    folder_id = request.form.get("folder_id", type=int)

    if not owner_id:
        user = _current_user()
        if user:
            owner_id = user["id"]
        else:
            return redirect(url_for("documents.login_page"))

    docs = _load_documents()
    new_id = max((d["id"] for d in docs), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    word_count = len(content.split()) if content else 0

    new_doc = {
        "id": new_id,
        "title": title,
        "content": content,
        "owner_id": owner_id,
        "folder_id": folder_id,
        "collaborators": [],
        "word_count": word_count,
        "is_starred": False,
        "is_trashed": False,
        "created_at": now,
        "updated_at": now,
    }
    docs.append(new_doc)
    _save_documents(docs)

    revisions = _load_revisions()
    rev_id = max((r["id"] for r in revisions), default=0) + 1
    revisions.append({
        "id": rev_id,
        "document_id": new_id,
        "user_id": owner_id,
        "timestamp": now,
        "summary": "Created document",
    })
    _save_revisions(revisions)

    return redirect(url_for("documents.editor", doc_id=new_id))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/documents")
def api_documents():
    """List documents. Supports query params: q, sort, folder_id, owner_id, starred, trashed."""
    docs = _load_documents()
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "updated").strip()
    folder_id = request.args.get("folder_id", type=int)
    owner_id = request.args.get("owner_id", type=int)
    starred = request.args.get("starred", "").strip().lower()
    trashed = request.args.get("trashed", "").strip().lower()

    results = list(docs)

    # Filter trashed (default: exclude trashed)
    if trashed == "true" or trashed == "only":
        results = [d for d in results if d.get("is_trashed", False)]
    else:
        results = [d for d in results if not d.get("is_trashed", False)]

    if q:
        results = _search_documents(results, q)
    if folder_id is not None:
        results = [d for d in results if d.get("folder_id") == folder_id]
    if owner_id is not None:
        results = [d for d in results if d["owner_id"] == owner_id]
    if starred == "true":
        results = [d for d in results if d.get("is_starred", False)]

    # Sort
    if sort == "title":
        results.sort(key=lambda d: d["title"].lower())
    elif sort == "created":
        results.sort(key=lambda d: d.get("created_at", ""), reverse=True)
    elif sort == "word_count":
        results.sort(key=lambda d: d.get("word_count", 0), reverse=True)
    else:
        results.sort(key=lambda d: d.get("updated_at", ""), reverse=True)

    return jsonify(results)


@blueprint.route("/api/documents/<int:doc_id>")
def api_document(doc_id):
    """Get a single document by ID."""
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404
    return jsonify(doc)


@blueprint.route("/api/documents", methods=["POST"])
def api_create_document():
    """Create a new document."""
    data = request.get_json(silent=True) or {}
    title = data.get("title", "Untitled Document").strip()
    content = data.get("content", "").strip()
    owner_id = data.get("owner_id")
    folder_id = data.get("folder_id")

    if not owner_id:
        return jsonify({"error": "owner_id required"}), 400

    docs = _load_documents()
    new_id = max((d["id"] for d in docs), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    word_count = len(content.split()) if content else 0

    new_doc = {
        "id": new_id,
        "title": title,
        "content": content,
        "owner_id": owner_id,
        "folder_id": folder_id,
        "collaborators": [],
        "word_count": word_count,
        "is_starred": False,
        "is_trashed": False,
        "created_at": now,
        "updated_at": now,
    }
    docs.append(new_doc)
    _save_documents(docs)

    # Create initial revision
    revisions = _load_revisions()
    rev_id = max((r["id"] for r in revisions), default=0) + 1
    revisions.append({
        "id": rev_id,
        "document_id": new_id,
        "user_id": owner_id,
        "timestamp": now,
        "summary": "Created document",
    })
    _save_revisions(revisions)

    return jsonify(new_doc), 201


@blueprint.route("/api/documents/<int:doc_id>", methods=["PUT"])
def api_update_document(doc_id):
    """Update a document's title and/or content."""
    data = request.get_json(silent=True) or {}
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404

    changed = False
    if "title" in data:
        doc["title"] = data["title"].strip()
        changed = True
    if "content" in data:
        doc["content"] = data["content"]
        doc["word_count"] = len(data["content"].split()) if data["content"] else 0
        changed = True

    if changed:
        now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
        doc["updated_at"] = now
        _save_documents(docs)

        # Create revision
        user_id = data.get("user_id", doc["owner_id"])
        summary = data.get("summary", "Updated document")
        revisions = _load_revisions()
        rev_id = max((r["id"] for r in revisions), default=0) + 1
        revisions.append({
            "id": rev_id,
            "document_id": doc_id,
            "user_id": user_id,
            "timestamp": now,
            "summary": summary,
        })
        _save_revisions(revisions)

    return jsonify(doc)


@blueprint.route("/api/documents/<int:doc_id>", methods=["PATCH"])
def api_patch_document(doc_id):
    """Partial update a document (same as PUT)."""
    return api_update_document(doc_id)


@blueprint.route("/api/documents/<int:doc_id>/star", methods=["POST"])
def api_star_document(doc_id):
    """Toggle star on a document."""
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404
    doc["is_starred"] = not doc.get("is_starred", False)
    _save_documents(docs)
    return jsonify({"id": doc_id, "is_starred": doc["is_starred"]})


@blueprint.route("/api/documents/<int:doc_id>/trash", methods=["POST"])
def api_trash_document(doc_id):
    """Move a document to trash or restore it."""
    data = request.get_json(silent=True) or {}
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404

    action = data.get("action", "trash")
    if action == "restore":
        doc["is_trashed"] = False
    else:
        doc["is_trashed"] = True

    doc["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_documents(docs)
    return jsonify({"id": doc_id, "is_trashed": doc["is_trashed"], "action": action})


@blueprint.route("/api/documents/<int:doc_id>/share", methods=["POST"])
def api_share_document(doc_id):
    """Add or update a collaborator on a document."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    permission = data.get("permission", "view")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400
    if permission not in ("view", "comment", "edit"):
        return jsonify({"error": "permission must be view, comment, or edit"}), 400

    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404

    collaborators = doc.setdefault("collaborators", [])
    existing = next((c for c in collaborators if c["user_id"] == user_id), None)
    if existing:
        existing["permission"] = permission
        action = "updated"
    else:
        collaborators.append({"user_id": user_id, "permission": permission})
        action = "added"

    _save_documents(docs)
    return jsonify({"action": action, "user_id": user_id, "permission": permission,
                    "total_collaborators": len(collaborators)})


@blueprint.route("/api/documents/<int:doc_id>/unshare", methods=["POST"])
def api_unshare_document(doc_id):
    """Remove a collaborator from a document."""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")

    if not user_id:
        return jsonify({"error": "user_id required"}), 400

    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404

    collaborators = doc.get("collaborators", [])
    before = len(collaborators)
    doc["collaborators"] = [c for c in collaborators if c["user_id"] != user_id]
    after = len(doc["collaborators"])

    _save_documents(docs)
    return jsonify({"action": "removed" if after < before else "not_found",
                    "user_id": user_id,
                    "total_collaborators": after})


@blueprint.route("/api/documents/<int:doc_id>/move", methods=["POST"])
def api_move_document(doc_id):
    """Move a document to a different folder."""
    data = request.get_json(silent=True) or {}
    folder_id = data.get("folder_id")

    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404

    doc["folder_id"] = folder_id
    doc["updated_at"] = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    _save_documents(docs)
    return jsonify({"id": doc_id, "folder_id": folder_id})


@blueprint.route("/api/documents/<int:doc_id>/delete", methods=["POST", "DELETE"])
def api_delete_document(doc_id):
    """Permanently delete a document."""
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404

    docs = [d for d in docs if d["id"] != doc_id]
    _save_documents(docs)

    revisions = _load_revisions()
    revisions = [r for r in revisions if r["document_id"] != doc_id]
    _save_revisions(revisions)

    return jsonify({"action": "deleted", "id": doc_id})


@blueprint.route("/api/documents/<int:doc_id>/revisions")
def api_document_revisions(doc_id):
    """Get revision history for a document."""
    docs = _load_documents()
    doc = next((d for d in docs if d["id"] == doc_id), None)
    if doc is None:
        return jsonify({"error": "Document not found"}), 404
    revisions = [r for r in _load_revisions() if r["document_id"] == doc_id]
    revisions.sort(key=lambda r: r["timestamp"], reverse=True)
    return jsonify(revisions)


# ---------------------------------------------------------------------------
# Folder API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/folders")
def api_folders():
    """List all folders."""
    folders = _load_folders()
    owner_id = request.args.get("owner_id", type=int)
    if owner_id is not None:
        folders = [f for f in folders if f["owner_id"] == owner_id]
    return jsonify(folders)


@blueprint.route("/api/folders/<int:folder_id>")
def api_folder(folder_id):
    """Get a single folder with its documents."""
    folders = _load_folders()
    folder = next((f for f in folders if f["id"] == folder_id), None)
    if folder is None:
        return jsonify({"error": "Folder not found"}), 404
    docs = _load_documents()
    folder_docs = [d for d in docs if d.get("folder_id") == folder_id
                   and not d.get("is_trashed", False)]
    result = dict(folder)
    result["documents"] = folder_docs
    return jsonify(result)


@blueprint.route("/api/folders", methods=["POST"])
def api_create_folder():
    """Create a new folder."""
    data = request.get_json(silent=True) or {}
    name = data.get("name", "New Folder").strip()
    owner_id = data.get("owner_id")
    color = data.get("color", "#4A90D9")

    if not owner_id:
        return jsonify({"error": "owner_id required"}), 400

    folders = _load_folders()
    new_id = max((f["id"] for f in folders), default=0) + 1
    now = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    new_folder = {
        "id": new_id,
        "name": name,
        "owner_id": owner_id,
        "color": color,
        "created_at": now,
    }
    folders.append(new_folder)
    _save_folders(folders)
    return jsonify(new_folder), 201


# ---------------------------------------------------------------------------
# User API routes
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


@blueprint.route("/api/users")
def api_users():
    """List all users (passwords excluded)."""
    users = _load_users()
    return jsonify([{k: v for k, v in u.items() if k != "password"} for u in users])


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({k: v for k, v in user.items() if k != "password"})


# ---------------------------------------------------------------------------
# Stats / search API
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats")
def api_stats():
    """Aggregate statistics about documents."""
    docs = _load_documents()
    active = [d for d in docs if not d.get("is_trashed", False)]
    trashed = [d for d in docs if d.get("is_trashed", False)]
    starred = [d for d in active if d.get("is_starred", False)]
    total_words = sum(d.get("word_count", 0) for d in active)
    folders = _load_folders()
    revisions = _load_revisions()

    owner_ids = set(d["owner_id"] for d in active)

    return jsonify({
        "total_documents": len(active),
        "trashed_documents": len(trashed),
        "starred_documents": len(starred),
        "total_word_count": total_words,
        "total_folders": len(folders),
        "total_revisions": len(revisions),
        "unique_owners": len(owner_ids),
        "avg_word_count": round(total_words / len(active), 1) if active else 0,
    })


@blueprint.route("/api/search")
def api_search():
    """Search documents by content/title."""
    q = request.args.get("q", "").strip()
    docs = _load_documents()
    active = [d for d in docs if not d.get("is_trashed", False)]
    results = _search_documents(active, q)
    return jsonify(results)


@blueprint.route("/api/export")
def api_export():
    """Export documents as JSON or CSV."""
    fmt = request.args.get("format", "json").lower()
    folder_id = request.args.get("folder_id", type=int)
    owner_id = request.args.get("owner_id", type=int)

    docs = _load_documents()
    active = [d for d in docs if not d.get("is_trashed", False)]

    if folder_id is not None:
        active = [d for d in active if d.get("folder_id") == folder_id]
    if owner_id is not None:
        active = [d for d in active if d["owner_id"] == owner_id]

    if fmt == "csv":
        lines = ["id,title,owner_id,folder_id,word_count,is_starred,created_at,updated_at"]
        for d in active:
            title = d["title"].replace('"', '""')
            fid = d.get("folder_id") or ""
            wc = d.get("word_count", 0)
            star = d.get("is_starred", False)
            cat = d.get("created_at", "")
            uat = d.get("updated_at", "")
            lines.append(f'{d["id"]},"{title}",{d["owner_id"]},{fid},{wc},{star},"{cat}","{uat}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=documents.csv"})
    return jsonify(active)
