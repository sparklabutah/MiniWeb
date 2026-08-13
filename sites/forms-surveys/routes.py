"""Forms & Surveys — Google Forms / SurveyMonkey-style form builder.

Data interpreter: reads real Pew Research Center survey data from a ZIP archive
(pew-research-survey) and merges it with MiniWeb overlay forms/responses from
DATA_SOURCES_DIR/forms-surveys/.  The raw ZIP is read-only; all mutable state
lives in the overlay directory.

Supports creating forms, filling them out, viewing results and analytics.
Supports ranking fields, slider fields, file attachments, sharing, and CSV export.
"""
import csv
import io
import json
import pathlib
import re
import uuid
import zipfile
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)

from app import db, DATA_SOURCES_DIR
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "forms-surveys"
SITE_DIR = pathlib.Path(__file__).resolve().parent

PEW_ZIP_FILE = DATA_SOURCES_DIR / "pew-research-survey"
PEW_CSV_NAME = "Pew Research Center Global Attitudes Spring 2025 Dataset CSV.csv"
PEW_META_NAME = "Pew Research Center Global Attitudes Spring 2025 Metadata.xml"

blueprint = Blueprint(
    "forms-surveys",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Pew Research data interpreter — parses ZIP at startup, cached at module level
# ---------------------------------------------------------------------------

# Which question groups to convert into survey forms.
# Each entry: (form_id, title, description, list of (column_name,) tuples).
# Column labels and value labels are extracted from the metadata XML.
_PEW_SURVEY_DEFS = [
    (
        100,
        "Pew Global Attitudes: Economic & Democratic Satisfaction",
        "Pew Research Center Spring 2025 — Questions on economic conditions and satisfaction with democracy.",
        ["econ_sit", "satisfied_democracy", "trust_people", "respect_current"],
    ),
    (
        101,
        "Pew Global Attitudes: International Threats",
        "Pew Research Center Spring 2025 — Perceived major threats to your country.",
        [
            "intthreat_climatechange", "intthreat_econcondition",
            "intthreat_disease", "intthreat_misinfo", "intthreat_terrorism",
        ],
    ),
    (
        102,
        "Pew Global Attitudes: Views on World Leaders",
        "Pew Research Center Spring 2025 — Confidence in world leaders.",
        ["confid_trump", "confid_xi", "confid_putin"],
    ),
    (
        103,
        "Pew Global Attitudes: Artificial Intelligence",
        "Pew Research Center Spring 2025 — Awareness and attitudes toward AI.",
        ["ai_heard", "ai_cncexc"],
    ),
    (
        104,
        "Pew Global Attitudes: Climate Change",
        "Pew Research Center Spring 2025 — Perceptions of climate change impact and concern.",
        ["climate_local", "climate_concern", "climate_behavior"],
    ),
]

# Number of CSV respondent rows to convert into form responses
_PEW_MAX_RESPONDENTS = 50

# Module-level cache
_pew_forms = None        # list of form dicts
_pew_responses = None    # list of response dicts
_pew_var_meta = None     # {col_name: {label: str, categories: {val: label}}}


def _parse_pew_metadata(zf):
    """Parse the DDI metadata XML inside the ZIP to get variable labels and
    value-label mappings.  Returns {col_name: {label, categories}}."""
    global _pew_var_meta
    if _pew_var_meta is not None:
        return _pew_var_meta

    ns = "ddi:codebook:2_5"
    with zf.open(PEW_META_NAME) as f:
        content = f.read().decode("utf-8")
    root = ET.fromstring(content)

    variables = {}
    for var in root.iter(f"{{{ns}}}var"):
        name = var.get("name", "")
        labl_elem = var.find(f"{{{ns}}}labl")
        label = labl_elem.text if labl_elem is not None else name

        categories = {}
        for cat in var.findall(f"{{{ns}}}catgry"):
            val_elem = cat.find(f"{{{ns}}}catValu")
            cat_labl = cat.find(f"{{{ns}}}labl")
            if val_elem is not None and cat_labl is not None:
                categories[val_elem.text.strip()] = cat_labl.text
        variables[name] = {"label": label, "categories": categories}

    _pew_var_meta = variables
    return variables


def _field_type_for_col(meta_entry):
    """Decide the form field type based on value categories."""
    cats = meta_entry.get("categories", {})
    # Filter out DK/Refused meta-options
    real_cats = {k: v for k, v in cats.items()
                 if "Don't know" not in v and "Refused" not in v
                 and "Never heard" not in v}
    if len(real_cats) == 2:
        return "radio"
    if len(real_cats) <= 6:
        return "radio"
    return "dropdown"


def _build_pew_forms_and_responses():
    """Read the Pew ZIP once, build form dicts and response dicts.
    Cached at module level."""
    global _pew_forms, _pew_responses
    if _pew_forms is not None:
        return

    if not PEW_ZIP_FILE.exists():
        _pew_forms = []
        _pew_responses = []
        return

    zf = zipfile.ZipFile(str(PEW_ZIP_FILE))
    var_meta = _parse_pew_metadata(zf)

    # Read CSV rows (first _PEW_MAX_RESPONDENTS only)
    with zf.open(PEW_CSV_NAME) as f:
        reader = csv.DictReader(io.TextIOWrapper(f, encoding="utf-8"))
        csv_header = reader.fieldnames
        rows = []
        for i, row in enumerate(reader):
            if i >= _PEW_MAX_RESPONDENTS:
                break
            rows.append(row)

    # Country code -> name mapping
    country_meta = var_meta.get("country", {})
    country_map = country_meta.get("categories", {})

    forms = []
    all_responses = []
    response_id_counter = 10000  # high IDs to avoid overlay collision

    for form_id, title, description, col_names in _PEW_SURVEY_DEFS:
        # Build fields from columns
        fields = []
        valid_cols = []  # columns actually present in the CSV
        for idx, col in enumerate(col_names):
            if col not in var_meta:
                continue
            # Also ensure column exists in CSV header
            # Handle BOM in first column name
            found_col = None
            for h in csv_header:
                if h.strip("\ufeff").strip() == col:
                    found_col = h
                    break
            if found_col is None:
                continue

            meta = var_meta[col]
            ftype = _field_type_for_col(meta)

            # Clean label: strip "Q1." prefix and "(SHORTENED)" markers
            label = meta["label"]
            # Remove common prefixes like "Q1. " or "Q17a. "
            label = re.sub(r'^Q\d+[a-z]?\.\s*', '', label)
            label = label.replace("(SHORTENED) ", "").strip()
            # Truncate very long labels for readability
            if len(label) > 200:
                label = label[:197] + "..."

            # Build options from categories, excluding DK/Refused
            cats = meta.get("categories", {})
            options = []
            for val in sorted(cats.keys(), key=lambda x: (int(x) if x.isdigit() else 999, x)):
                cat_label = cats[val]
                if "Don't know" in cat_label or "Refused" in cat_label or "Never heard" in cat_label:
                    continue
                options.append(cat_label)

            field_id = f"f{form_id}_{idx + 1}"
            fields.append({
                "id": field_id,
                "type": ftype,
                "label": label,
                "required": False,
                "options": options,
            })
            valid_cols.append((found_col, col, field_id, cats))

        if not fields:
            continue

        form = {
            "id": form_id,
            "title": title,
            "description": description,
            "owner_id": 0,   # system / Pew Research
            "status": "closed",
            "created_at": "2025-03-01T00:00:00Z",
            "responses_count": 0,
            "fields": fields,
        }

        # Build responses from CSV rows
        form_responses = []
        for row in rows:
            answers = {}
            has_any = False
            for csv_col, col_name, field_id, cats in valid_cols:
                raw_val = row.get(csv_col, "").strip()
                if not raw_val or raw_val in ("", " "):
                    continue
                # Map coded value to label
                mapped = cats.get(raw_val, "")
                if not mapped or "Don't know" in mapped or "Refused" in mapped or "Never heard" in mapped:
                    continue
                answers[field_id] = mapped
                has_any = True

            if not has_any:
                continue

            # Use country as respondent context
            country_code = row.get("country", "").strip()
            # Use a combo of form_id and row id for uniqueness
            resp_id = response_id_counter
            response_id_counter += 1

            form_responses.append({
                "id": resp_id,
                "form_id": form_id,
                "respondent_id": None,
                "submitted_at": "2025-03-15T12:00:00Z",
                "answers": answers,
                "_country": country_map.get(country_code, f"Country {country_code}"),
            })

        form["responses_count"] = len(form_responses)
        forms.append(form)
        all_responses.extend(form_responses)

    _pew_forms = forms
    _pew_responses = all_responses


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _get_users():
    return db.query(SITE, "users")


def _load_forms():
    """Load overlay forms from the database."""
    return db.query(SITE, "forms")


def _save_forms(forms):
    db.save_collection(SITE, "forms", forms)


def _load_responses():
    """Load overlay responses from the database."""
    return db.query(SITE, "responses")


def _save_responses(responses):
    db.save_collection(SITE, "responses", responses)


def _get_forms():
    """Return merged list: overlay forms (IDs 1-12) + Pew Research surveys (IDs 100+)."""
    _build_pew_forms_and_responses()
    overlay = _load_forms()
    return overlay + (_pew_forms or [])


def _get_responses():
    """Return merged list: overlay responses + Pew Research responses."""
    _build_pew_forms_and_responses()
    overlay = _load_responses()
    return overlay + (_pew_responses or [])


def _get_templates():
    return db.query(SITE, "templates_forms")


def _current_user():
    if "user_id" in session:
        return db.get_item(SITE, "users", session["user_id"])
    return None


def _user_name(user_id):
    u = db.get_item(SITE, "users", user_id)
    return u["name"] if u else "Anonymous"


def _next_id(items):
    return max((item["id"] for item in items), default=0) + 1


def _form_stats(form_id):
    """Compute per-field statistics for a form."""
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        return {}

    responses = [r for r in _get_responses() if r["form_id"] == form_id]
    stats = {}

    for field in form["fields"]:
        fid = field["id"]
        ftype = field["type"]
        values = [r["answers"].get(fid) for r in responses if fid in r.get("answers", {})]
        values = [v for v in values if v is not None and v != "" and v != []]

        field_stat = {
            "field_id": fid,
            "label": field["label"],
            "type": ftype,
            "total_answers": len(values),
        }

        if ftype == "rating":
            nums = []
            for v in values:
                try:
                    nums.append(int(v))
                except (ValueError, TypeError):
                    pass
            if nums:
                field_stat["average"] = round(sum(nums) / len(nums), 2)
                field_stat["distribution"] = dict(Counter(str(n) for n in nums))
            else:
                field_stat["average"] = 0
                field_stat["distribution"] = {}

        elif ftype in ("radio", "dropdown"):
            field_stat["distribution"] = dict(Counter(str(v) for v in values))

        elif ftype == "checkbox":
            flat = []
            for v in values:
                if isinstance(v, list):
                    flat.extend(v)
                else:
                    flat.append(v)
            field_stat["distribution"] = dict(Counter(flat))

        elif ftype == "slider":
            nums = []
            for v in values:
                try:
                    nums.append(int(v))
                except (ValueError, TypeError):
                    pass
            if nums:
                field_stat["average"] = round(sum(nums) / len(nums), 2)
                field_stat["min"] = min(nums)
                field_stat["max"] = max(nums)
                field_stat["distribution"] = dict(Counter(str(n) for n in nums))
            else:
                field_stat["average"] = 0
                field_stat["distribution"] = {}

        elif ftype == "ranking":
            # Show positional frequency for each option
            positions = {}
            for v in values:
                if isinstance(v, list):
                    for pos, item in enumerate(v):
                        positions.setdefault(item, []).append(pos + 1)
            avg_positions = {}
            for item, pos_list in positions.items():
                avg_positions[item] = round(sum(pos_list) / len(pos_list), 2)
            field_stat["average_positions"] = avg_positions

        elif ftype in ("text", "textarea"):
            field_stat["sample_answers"] = values[:10]

        stats[fid] = field_stat

    return stats


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user = _current_user()
    forms = _get_forms()
    if user:
        # Show user's own forms + public Pew Research surveys (owner_id 0)
        my_forms = [f for f in forms if f["owner_id"] == user["id"] or f["owner_id"] == 0]
    else:
        my_forms = forms
    # Sort by created_at descending
    my_forms.sort(key=lambda f: f.get("created_at", ""), reverse=True)
    # Enrich with owner name
    for f in my_forms:
        f["_owner_name"] = _user_name(f["owner_id"])

    # "Forms to fill out": active forms shared by OTHERS that this user hasn't
    # responded to yet — a respondent-side to-do inbox.
    to_fill = []
    if user:
        answered = {r["form_id"] for r in _get_responses()
                    if r.get("respondent_id") == user["id"]}
        for f in forms:
            if (f.get("status") == "active"
                    and f["owner_id"] != user["id"]
                    and f["owner_id"] != 0
                    and f["id"] not in answered):
                item = dict(f)
                item["_owner_name"] = _user_name(f["owner_id"])
                item["_qcount"] = len(f.get("fields") or [])
                to_fill.append(item)
        to_fill.sort(key=lambda x: x.get("created_at", ""), reverse=True)
        to_fill = to_fill[:12]

    return render_template("forms-surveys/index.html", forms=my_forms,
                           user=user, to_fill=to_fill, pending_count=len(to_fill))


@blueprint.route("/form/<int:form_id>")
def view_form(form_id):
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    form["_owner_name"] = _user_name(form["owner_id"])
    responses = [r for r in _get_responses() if r["form_id"] == form_id]
    responses.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)
    user = _current_user()
    return render_template("forms-surveys/form.html", form=form, responses=responses, user=user)


@blueprint.route("/form/<int:form_id>/respond")
def respond_form(form_id):
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    if form["status"] != "active":
        abort(403)
    user = _current_user()
    return render_template("forms-surveys/respond.html", form=form, user=user)


@blueprint.route("/form/<int:form_id>/respond", methods=["POST"])
def submit_response_form(form_id):
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    if form["status"] != "active":
        abort(403)

    answers = {}
    for field in form["fields"]:
        fid = field["id"]
        if field["type"] == "checkbox":
            answers[fid] = request.form.getlist(fid)
        elif field["type"] == "ranking":
            # Ranking comes as comma-separated ordered list
            raw = request.form.get(fid, "")
            answers[fid] = [x.strip() for x in raw.split(",") if x.strip()] if raw else []
        else:
            answers[fid] = request.form.get(fid, "")

    responses = _load_responses()
    new_id = _next_id(responses)
    user = _current_user()
    response_obj = {
        "id": new_id,
        "form_id": form_id,
        "respondent_id": user["id"] if user else None,
        "submitted_at": datetime.now().isoformat() + "Z",
        "answers": answers,
    }
    responses.append(response_obj)
    _save_responses(responses)

    # Update response count
    form["responses_count"] = len([r for r in responses if r["form_id"] == form_id])
    _save_forms(forms)

    # Backend signal for verification: log the submission on the event bus.
    emit("form_response", user_id=user["id"] if user else None,
         site_name="forms-surveys", form_id=form_id, form_title=form["title"],
         response_id=new_id, field_count=len(answers))

    _add_email(user["id"] if user else 1, "noreply@forms-surveys.lakeport.local",
               "Form submission received",
               f'Your response to "{form["title"]}" has been recorded. Thank you for your submission.')
    return redirect(url_for("forms-surveys.respond_success", form_id=form_id))


@blueprint.route("/form/<int:form_id>/success")
def respond_success(form_id):
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    user = _current_user()
    return render_template("forms-surveys/success.html", form=form, user=user)


@blueprint.route("/form/<int:form_id>/results")
def form_results(form_id):
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    form["_owner_name"] = _user_name(form["owner_id"])
    responses = [r for r in _get_responses() if r["form_id"] == form_id]
    responses.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)
    stats = _form_stats(form_id)
    user = _current_user()
    return render_template("forms-surveys/results.html", form=form, responses=responses,
                           stats=stats, user=user)


# ---------------------------------------------------------------------------
# Inline-editable response grid (edit_by_cell)
# ---------------------------------------------------------------------------

@blueprint.route("/form/<int:form_id>/grid")
def form_grid(form_id):
    """Spreadsheet-style editable grid of a form's responses.

    Rows = responses, columns = the form's fields. The survey owner can retype
    any cell in place (edit_by_cell) or append a brand-new response row, then
    press Save Changes. Only overlay-backed forms (the user's own forms, IDs
    below the Pew Research block) are editable; the read-only Pew surveys are
    not shown here.
    """
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    form["_owner_name"] = _user_name(form["owner_id"])
    # SQL-level filter + sort + limit (CLAUDE.md DB rules). The grid shows <50
    # rows per the frontend cap; stable ordering by id keeps row indices aligned.
    responses = db.query(SITE, "responses", where={"form_id": form_id},
                         sort="id", limit=50)
    user = _current_user()
    return render_template("forms-surveys/grid.html", form=form,
                           responses=responses, user=user)


@blueprint.route("/form/<int:form_id>/grid", methods=["POST"])
def form_grid_submit(form_id):
    """Persist inline cell edits (and appended rows) from the response grid.

    Reads ``cell_<row>_<col>`` fields; ``row_<row>`` carries the existing
    response id for pre-populated rows (blank for JS-appended rows, which become
    new responses). Mutations go to the session overlay only. This is a normal
    /sites/forms-surveys/ route so its POST body is captured by /_admin/log,
    which is what makes the edits gradeable.
    """
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    fields = form.get("fields", [])  # column index -> field id

    responses = _load_responses()
    by_id = {r["id"]: r for r in responses}

    # Group posted cells by row index.
    row_cells = {}  # row_idx -> {col_idx: value}
    for key, value in request.form.items():
        if not key.startswith("cell_"):
            continue
        parts = key.split("_")
        if len(parts) != 3:
            continue
        try:
            r, c = int(parts[1]), int(parts[2])
        except ValueError:
            continue
        row_cells.setdefault(r, {})[c] = value

    user = _current_user()
    # Seed a local id counter from the overlay-aware next_id so multiple appended
    # rows in ONE submit don't collide (db.next_id can't see rows not yet saved).
    next_new = db.next_id(SITE, "responses")
    changes = 0

    for r in sorted(row_cells.keys()):
        cells = row_cells[r]
        resp_id_raw = request.form.get(f"row_{r}", "").strip()
        if resp_id_raw:
            # Existing response — update answers in place.
            try:
                rid = int(resp_id_raw)
            except ValueError:
                continue
            resp = by_id.get(rid)
            if resp is None:
                continue
            answers = resp.setdefault("answers", {})
            for c, val in cells.items():
                if 0 <= c < len(fields):
                    fid = fields[c]["id"]
                    if answers.get(fid) != val:
                        answers[fid] = val
                        changes += 1
        else:
            # Appended row — create a new response only if it has content.
            if not any(str(v).strip() for v in cells.values()):
                continue
            answers = {}
            for c, val in cells.items():
                if 0 <= c < len(fields):
                    answers[fields[c]["id"]] = val
            new_resp = {
                "id": next_new,
                "form_id": form_id,
                "respondent_id": user["id"] if user else None,
                "submitted_at": datetime.now().isoformat() + "Z",
                "answers": answers,
            }
            next_new += 1
            responses.append(new_resp)
            by_id[new_resp["id"]] = new_resp
            changes += 1

    if changes:
        _save_responses(responses)
        form["responses_count"] = len([x for x in responses if x["form_id"] == form_id])
        _save_forms(forms)
        emit("grid_edit", user_id=user["id"] if user else None,
             site_name="forms-surveys", form_id=form_id, form_title=form["title"],
             cells_changed=changes)

    return redirect(url_for("forms-surveys.form_grid", form_id=form_id))


@blueprint.route("/create")
def create_form_page():
    user = _current_user()
    templates = _get_templates()

    # When arriving via "Use Template", prefill the builder from that template
    # instead of opening a blank form.
    prefill = None
    tpl_id = request.args.get("template", "").strip()
    if tpl_id:
        tpl = next((t for t in templates if str(t.get("id")) == tpl_id), None)
        if tpl:
            prefill = {
                "title": tpl.get("name", ""),
                "description": tpl.get("description", ""),
                "fields": tpl.get("fields", []) or [],
            }

    return render_template("forms-surveys/create.html", user=user,
                           templates=templates, prefill=prefill)


@blueprint.route("/create", methods=["POST"])
def create_form_submit():
    user = _current_user()
    if not user:
        return redirect(url_for("forms-surveys.login_page"))

    forms = _load_forms()
    new_id = _next_id(forms)

    # Parse fields from form submission
    fields = []
    idx = 0
    while True:
        label = request.form.get(f"field_label_{idx}")
        if label is None:
            break
        ftype = request.form.get(f"field_type_{idx}", "text")
        required = request.form.get(f"field_required_{idx}") == "on"
        options_raw = request.form.get(f"field_options_{idx}", "")
        options = [o.strip() for o in options_raw.split(",") if o.strip()] if options_raw else []
        fields.append({
            "id": f"f{new_id}_{idx + 1}",
            "type": ftype,
            "label": label.strip(),
            "required": required,
            "options": options,
        })
        idx += 1

    form = {
        "id": new_id,
        "title": request.form.get("title", "").strip(),
        "description": request.form.get("description", "").strip(),
        "owner_id": user["id"],
        "status": request.form.get("status", "draft"),
        "created_at": datetime.now().isoformat() + "Z",
        "responses_count": 0,
        "fields": fields,
    }
    forms.append(form)
    _save_forms(forms)

    return redirect(url_for("forms-surveys.view_form", form_id=new_id))


@blueprint.route("/templates")
def templates_page():
    templates = _get_templates()
    user = _current_user()
    return render_template("forms-surveys/templates.html", templates=templates, user=user)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("forms-surveys/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _get_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("forms-surveys/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="forms-surveys", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return redirect(url_for("forms-surveys.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("forms-surveys.login_page"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/forms", methods=["GET"])
def api_forms_list():
    forms = _get_forms()
    status = request.args.get("status", "").strip()
    owner_id = request.args.get("owner_id", type=int)
    q = request.args.get("q", "").strip().lower()

    results = list(forms)
    if status:
        results = [f for f in results if f["status"] == status]
    if owner_id:
        results = [f for f in results if f["owner_id"] == owner_id]
    if q:
        results = [f for f in results if q in f["title"].lower() or q in f.get("description", "").lower()]

    results.sort(key=lambda f: f.get("created_at", ""), reverse=True)
    return jsonify(results)


@blueprint.route("/api/forms", methods=["POST"])
def api_forms_create():
    data = request.get_json(silent=True) or {}
    forms = _load_forms()
    new_id = _next_id(forms)

    fields = data.get("fields", [])
    # Ensure field IDs are set
    for i, field in enumerate(fields):
        if "id" not in field:
            field["id"] = f"f{new_id}_{i + 1}"
        field.setdefault("type", "text")
        field.setdefault("label", "")
        field.setdefault("required", False)
        field.setdefault("options", [])

    form = {
        "id": new_id,
        "title": data.get("title", "").strip(),
        "description": data.get("description", "").strip(),
        "owner_id": data.get("owner_id", session.get("user_id", 1)),
        "status": data.get("status", "draft"),
        "created_at": datetime.now().isoformat() + "Z",
        "responses_count": 0,
        "fields": fields,
    }
    forms.append(form)
    _save_forms(forms)
    return jsonify(form), 201


@blueprint.route("/api/forms/<int:form_id>", methods=["GET"])
def api_form_get(form_id):
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    return jsonify(form)


@blueprint.route("/api/forms/<int:form_id>", methods=["PUT"])
def api_form_update(form_id):
    data = request.get_json(silent=True) or {}
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)

    for key in ["title", "description", "status", "fields"]:
        if key in data:
            form[key] = data[key]

    _save_forms(forms)
    return jsonify(form)


@blueprint.route("/form/<int:form_id>/delete", methods=["POST"])
def form_delete(form_id):
    """Delete a form via POST (for HTML button)."""
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    forms = [f for f in forms if f["id"] != form_id]
    _save_forms(forms)
    responses = _load_responses()
    responses = [r for r in responses if r["form_id"] != form_id]
    _save_responses(responses)
    return redirect(url_for("forms-surveys.index"))


@blueprint.route("/api/forms/<int:form_id>", methods=["DELETE"])
def api_form_delete(form_id):
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)

    forms = [f for f in forms if f["id"] != form_id]
    _save_forms(forms)

    # Also remove associated responses
    responses = _load_responses()
    responses = [r for r in responses if r["form_id"] != form_id]
    _save_responses(responses)

    return jsonify({"status": "deleted", "id": form_id})


@blueprint.route("/api/forms/<int:form_id>/responses", methods=["GET"])
def api_form_responses(form_id):
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)

    responses = [r for r in _get_responses() if r["form_id"] == form_id]
    responses.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)
    return jsonify(responses)


@blueprint.route("/api/forms/<int:form_id>/respond", methods=["POST"])
def api_form_respond(form_id):
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    if form["status"] != "active":
        return jsonify({"error": "Form is not accepting responses"}), 400

    data = request.get_json(silent=True) or {}
    answers = data.get("answers", {})

    # Validate required fields
    for field in form["fields"]:
        if field["required"]:
            val = answers.get(field["id"])
            if val is None or val == "" or val == []:
                return jsonify({
                    "error": f"Required field '{field['label']}' is missing",
                    "field_id": field["id"],
                }), 400

    responses = _load_responses()
    new_id = _next_id(responses)
    user = _current_user()
    response_obj = {
        "id": new_id,
        "form_id": form_id,
        "respondent_id": data.get("respondent_id", user["id"] if user else None),
        "submitted_at": datetime.now().isoformat() + "Z",
        "answers": answers,
    }
    responses.append(response_obj)
    _save_responses(responses)

    # Update response count
    form["responses_count"] = len([r for r in responses if r["form_id"] == form_id])
    _save_forms(forms)

    # Backend signal for verification: log the submission on the event bus.
    emit("form_response", user_id=response_obj["respondent_id"],
         site_name="forms-surveys", form_id=form_id, form_title=form["title"],
         response_id=new_id, field_count=len(answers))

    return jsonify(response_obj), 201


@blueprint.route("/api/forms/<int:form_id>/stats")
def api_form_stats(form_id):
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)

    responses = [r for r in _get_responses() if r["form_id"] == form_id]
    stats = _form_stats(form_id)

    return jsonify({
        "form_id": form_id,
        "title": form["title"],
        "total_responses": len(responses),
        "status": form["status"],
        "fields": stats,
    })


@blueprint.route("/api/templates")
def api_templates():
    templates = _get_templates()
    category = request.args.get("category", "").strip()
    if category:
        templates = [t for t in templates if t["category"] == category]
    return jsonify(templates)


@blueprint.route("/api/stats")
def api_stats():
    forms = _get_forms()
    responses = _get_responses()

    total_forms = len(forms)
    active_forms = len([f for f in forms if f["status"] == "active"])
    draft_forms = len([f for f in forms if f["status"] == "draft"])
    closed_forms = len([f for f in forms if f["status"] == "closed"])
    total_responses = len(responses)
    avg_responses = round(total_responses / total_forms, 1) if total_forms > 0 else 0

    # Responses over time (by date)
    by_date = Counter()
    for r in responses:
        date_str = r.get("submitted_at", "")[:10]
        if date_str:
            by_date[date_str] += 1

    return jsonify({
        "total_forms": total_forms,
        "active_forms": active_forms,
        "draft_forms": draft_forms,
        "closed_forms": closed_forms,
        "total_responses": total_responses,
        "avg_responses_per_form": avg_responses,
        "responses_by_date": dict(sorted(by_date.items())),
    })


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _get_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"], "name": user["name"]})


# ---------------------------------------------------------------------------
# Semantic / text search (navigate_by_semantic, extract_by_semantic)
# ---------------------------------------------------------------------------

@blueprint.route("/api/forms/search", methods=["GET"])
def api_forms_search():
    """Keyword search across form titles, descriptions, and field labels."""
    q = request.args.get("q", "").strip().lower()
    if not q:
        return jsonify([])
    forms = _get_forms()
    results = []
    for f in forms:
        score = 0
        text = f"{f['title']} {f.get('description', '')}".lower()
        for word in q.split():
            if word in text:
                score += 1
            for field in f.get("fields", []):
                if word in field.get("label", "").lower():
                    score += 1
        if score > 0:
            f["_relevance"] = score
            results.append(f)
    results.sort(key=lambda x: x["_relevance"], reverse=True)
    # Strip internal key before returning
    for r in results:
        r.pop("_relevance", None)
    return jsonify(results)


# ---------------------------------------------------------------------------
# Export (export_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/forms/<int:form_id>/export", methods=["GET"])
def api_form_export(form_id):
    """Export form responses as CSV or JSON. ?format=csv|json"""
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)

    responses = [r for r in _get_responses() if r["form_id"] == form_id]
    responses.sort(key=lambda r: r.get("submitted_at", ""), reverse=True)

    fmt = request.args.get("format", "json").lower()

    if fmt == "csv":
        output = io.StringIO()
        field_ids = [field["id"] for field in form["fields"]]
        field_labels = [field["label"] for field in form["fields"]]
        writer = csv.writer(output)
        writer.writerow(["response_id", "submitted_at", "respondent_id"] + field_labels)
        for resp in responses:
            row = [resp["id"], resp.get("submitted_at", ""), resp.get("respondent_id", "")]
            for fid in field_ids:
                val = resp.get("answers", {}).get(fid, "")
                if isinstance(val, list):
                    val = "; ".join(str(v) for v in val)
                row.append(val)
            writer.writerow(row)
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": f"attachment; filename=form_{form_id}_responses.csv"},
        )

    # Default: JSON
    return jsonify(responses)


@blueprint.route("/api/export", methods=["GET"])
def api_export_all():
    """Export all forms (optionally filtered by status) as CSV or JSON."""
    forms = _get_forms()
    status = request.args.get("status", "").strip()
    if status:
        forms = [f for f in forms if f["status"] == status]

    fmt = request.args.get("format", "json").lower()

    if fmt == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["id", "title", "description", "owner_id", "status",
                          "created_at", "responses_count", "num_fields"])
        for f in forms:
            writer.writerow([
                f["id"], f["title"], f.get("description", ""), f["owner_id"],
                f["status"], f.get("created_at", ""), f.get("responses_count", 0),
                len(f.get("fields", [])),
            ])
        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=forms_export.csv"},
        )

    return jsonify(forms)


# ---------------------------------------------------------------------------
# Upload (upload_by_upload)
# ---------------------------------------------------------------------------

@blueprint.route("/api/forms/<int:form_id>/upload", methods=["POST"])
def api_form_upload(form_id):
    """Upload a file attachment to a form. Stored in-memory on the form object."""
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    uploaded = request.files["file"]
    if not uploaded.filename:
        return jsonify({"error": "Empty filename"}), 400

    attachment = {
        "id": str(uuid.uuid4())[:8],
        "filename": uploaded.filename,
        "size": 0,
        "uploaded_at": datetime.now().isoformat() + "Z",
        "uploaded_by": session.get("user_id"),
    }

    # Read content to compute size (content is discarded; this is a simulation)
    content = uploaded.read()
    attachment["size"] = len(content)

    if not isinstance(form.get("attachments"), list):
        form["attachments"] = []
    form["attachments"].append(attachment)
    _save_forms(forms)

    return jsonify(attachment), 201


@blueprint.route("/api/forms/<int:form_id>/attachments", methods=["GET"])
def api_form_attachments(form_id):
    """List attachments for a form."""
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    return jsonify(form.get("attachments", []))


# ---------------------------------------------------------------------------
# Share (share_by_dropdown)
# ---------------------------------------------------------------------------

@blueprint.route("/api/forms/<int:form_id>/share", methods=["POST"])
def api_form_share(form_id):
    """Share a form with a user by email or user_id. Method via dropdown: email or link."""
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)

    data = request.get_json(silent=True) or {}
    method = data.get("method", "link")  # 'link' or 'email'
    recipient = data.get("recipient", "").strip()

    if not isinstance(form.get("shared_with"), list):
        form["shared_with"] = []

    share_record = {
        "id": str(uuid.uuid4())[:8],
        "method": method,
        "recipient": recipient,
        "shared_at": datetime.now().isoformat() + "Z",
        "shared_by": session.get("user_id"),
    }
    form["shared_with"].append(share_record)
    _save_forms(forms)

    return jsonify(share_record), 201


@blueprint.route("/api/forms/<int:form_id>/shares", methods=["GET"])
def api_form_shares(form_id):
    """List share records for a form."""
    forms = _get_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if not form:
        abort(404)
    return jsonify(form.get("shared_with", []))


# ---------------------------------------------------------------------------
# Edit response by query (edit_by_query)
# ---------------------------------------------------------------------------

@blueprint.route("/api/responses/<int:response_id>", methods=["GET"])
def api_response_get(response_id):
    """Get a specific response by ID."""
    responses = _get_responses()
    resp = next((r for r in responses if r["id"] == response_id), None)
    if not resp:
        abort(404)
    return jsonify(resp)


@blueprint.route("/api/responses/<int:response_id>", methods=["PUT"])
def api_response_update(response_id):
    """Edit a specific response's answers by response ID."""
    responses = _load_responses()
    resp = next((r for r in responses if r["id"] == response_id), None)
    if not resp:
        abort(404)

    data = request.get_json(silent=True) or {}
    new_answers = data.get("answers", {})
    for key, val in new_answers.items():
        resp["answers"][key] = val

    _save_responses(responses)
    return jsonify(resp)


# ---------------------------------------------------------------------------
# Delete response (delete_from_table)
# ---------------------------------------------------------------------------

@blueprint.route("/api/responses/<int:response_id>", methods=["DELETE"])
def api_response_delete(response_id):
    """Delete a specific response."""
    responses = _load_responses()
    resp = next((r for r in responses if r["id"] == response_id), None)
    if not resp:
        abort(404)

    form_id = resp["form_id"]
    responses = [r for r in responses if r["id"] != response_id]
    _save_responses(responses)

    # Update response count on the form
    forms = _load_forms()
    form = next((f for f in forms if f["id"] == form_id), None)
    if form:
        form["responses_count"] = len([r for r in responses if r["form_id"] == form_id])
        _save_forms(forms)

    return jsonify({"status": "deleted", "id": response_id})


# ---------------------------------------------------------------------------
# Users API (for verifiers)
# ---------------------------------------------------------------------------

@blueprint.route("/api/users", methods=["GET"])
def api_users_list():
    users = _get_users()
    # Strip passwords
    safe = [{k: v for k, v in u.items() if k != "password"} for u in users]
    return jsonify(safe)


@blueprint.route("/api/users/<int:user_id>", methods=["GET"])
def api_user_get(user_id):
    users = _get_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    safe = {k: v for k, v in user.items() if k != "password"}
    return jsonify(safe)
