"""Files a visitor's requests leave on disk, kept apart for each session.

A few sites keep a file rather than a row: password-managers stores entry icons, NoteCanvas
(handwritten-notes-whiteboards) draws the images of its notes. Each session gets its own folder,
MINIWEB_UPLOADS_DIR/<session id>/<area>/ (data/uploads by default, a folder used for nothing else), so

- a visitor, or one of several agents evaluated on one server as the same user, never overwrites or sees another
  session's files: the URL stored in the data stays the same for everyone, and each session is served its own file;
- a file name sent by the browser cannot reach outside the folder;
- the files go with the session's data (db.reset_session, db.evict_stale_sessions, db.reset_all).
"""
import os
import re
import shutil

from werkzeug.exceptions import BadRequest, NotFound
from werkzeug.utils import secure_filename

from helpers.paths import REPO_ROOT

ROOT = REPO_ROOT / os.environ.get("MINIWEB_UPLOADS_DIR", "data/uploads")
_SID = re.compile(r"[\w-]{1,64}")     # db._get_session_id makes 12 hex digits and dashes


def _folder(sid, area):
    if not _SID.fullmatch(sid or ""):
        raise BadRequest("bad session")
    return ROOT / sid / area


def path(area, name):
    """Where this session keeps the file `name` of `area` (a site, or "generated"); the folder is created. The name
    loses any folder part and unsafe characters."""
    from miniweb.app import db
    safe = secure_filename(name or "")
    if not safe:
        raise BadRequest("bad file name")
    folder = _folder(db._get_session_id(), area)
    folder.mkdir(parents=True, exist_ok=True)
    return folder / safe


def find(area, name):
    """This session's file `name` of `area`, or None. Never starts a session."""
    from flask import has_request_context, session
    sid = session.get("_data_overlay_sid") if has_request_context() else None
    if not sid or not name or secure_filename(name) != name or not _SID.fullmatch(sid):
        return None
    file = ROOT / sid / area / name
    return file if file.is_file() else None


def send(area, name):
    """Serve this session's file `name` of `area`; 404 when the session has none."""
    from flask import send_file
    file = find(area, name)
    if file is None:
        raise NotFound()
    response = send_file(file, max_age=0)
    # an uploaded SVG must not run scripts, and a browser must not read a file as another type
    response.headers["Content-Security-Policy"] = "sandbox"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def drop(sids):
    """Delete the files of these sessions."""
    for sid in sids:
        if _SID.fullmatch(sid or ""):
            shutil.rmtree(ROOT / sid, ignore_errors=True)


def drop_all():
    """Delete the files of every session."""
    if ROOT.is_dir():
        drop(entry.name for entry in ROOT.iterdir() if entry.is_dir())
