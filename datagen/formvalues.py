"""Field values for generated form tasks (privileged, parameter stage).

The sampler picks WHICH form; this module proposes WHAT to enter: K diverse, realistic value
sets per form, written once by an LLM from the form's fields (labels, types, options, current
values) and a little site context, cached on disk. Sign-in forms take real accounts from the
site's users table instead. Every set is validated by the dry run (the site must accept it).
"""
from __future__ import annotations

import hashlib
import json
import re

from datagen import config

CACHE = config.DATAGEN_DIR / "formvalues"
SYSTEM = ("You fill in web forms for realistic test tasks. Propose DIFFERENT value sets a real user of this "
          "site might submit. Use only values the form can accept: for fields with options pick one of the "
          "options exactly; dates as YYYY-MM-DD (bookings/deadlines in the future: 2026-10 to 2027-06), times "
          "as HH:MM, numbers plain; emails @example.com unless an existing person below fits. For an edit or "
          "settings form change 1–3 fields from their current values and repeat the others unchanged. Never "
          "invent other people when the context lists who exists. Reply ONLY JSON.")


def field_key(f):
    return f.get("name") or f["css"]


def _people(site, limit=15):
    """A few accounts of the site (privileged, base data; users tables are small)."""
    try:
        from app import db
        rows = db.query(site, "users", limit=limit)
    except Exception:
        return []
    keep = ("username", "name", "display_name", "full_name", "email", "handle")
    return [{k: r.get(k) for k in keep if r.get(k)} for r in rows if isinstance(r, dict)]


def records(site, tables=10, per=25):
    """A few real records of the site (id + title/name per table; base data, bounded queries) so
    values that must exist — a meeting code, an order number — can be chosen, not invented."""
    try:
        from app import db
        prefix = site.replace("-", "_") + "_"
        names = [r["name"] for r in db.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE ? ORDER BY name LIMIT ?",
            (prefix + "%", tables * 3))]
    except Exception:
        return []
    out = []
    for t in names:
        if t.endswith("_users") or len(out) >= tables * per:
            continue
        try:
            cols = [c["name"] for c in db.execute(f"PRAGMA table_info({t})")]
            label = next((c for c in ("title", "name", "subject", "code", "number", "label") if c in cols), None)
            if "id" not in cols:
                continue
            rows = db.execute(f"SELECT id{', ' + label if label else ''} FROM {t} ORDER BY id LIMIT ?", (per,))
        except Exception:
            continue
        out += [{"collection": t[len(prefix):], "id": r["id"], **({label: r[label]} if label else {})} for r in rows]
    return out


def accounts(site, limit=20):
    """Sign-in credentials from the site's users table: [{login, email, password, name}]."""
    try:
        from app import db
        rows = db.query(site, "users", limit=limit)
    except Exception:
        return []
    out = []
    for r in rows or []:
        pw = r.get("password") or r.get("pass") or r.get("pwd")
        if not pw or not isinstance(pw, str) or len(pw) > 40 or pw.startswith(("$2", "pbkdf2", "sha")):
            continue                           # hashed: the task could not state it
        login = r.get("username") or r.get("user") or r.get("handle") or r.get("email")
        if login:
            out.append({"login": str(login), "email": str(r.get("email") or ""), "password": pw,
                        "name": str(r.get("name") or r.get("display_name") or r.get("full_name") or login)})
    return out


def _key(ctrl):
    ident = json.dumps([ctrl.get("site_id"), ctrl.get("page"), ctrl.get("role"),
                        [(f.get("name"), f.get("type")) for f in ctrl.get("fields", [])]], sort_keys=True)
    return hashlib.sha1(ident.encode()).hexdigest()[:16]


K = 12      # value sets per form (a cache written with fewer is topped up with new, different ones)


def value_sets(ctrl, site, k=K, model=None, force=False, grounded=False):
    """[{values: {field_key: value}, summary}] for a form control (cached). `grounded`: also show the
    site's own records so values that must exist are picked from them."""
    path = CACHE / site / f"{_key(ctrl)}.json"
    have = [] if force or not path.exists() else json.loads(path.read_text())
    if have and (len(have) >= k or ctrl.get("_topped_up") == k):
        return have
    out, seen = list(have), {json.dumps(s["values"], sort_keys=True) for s in have}
    for _ in range(8):                                   # batches: one call returns ~a dozen sets at most
        if len(out) >= k:
            break
        more = _generate(ctrl, site, min(15, k - len(out)), model, grounded or ctrl.get("grounded"), avoid=out)
        fresh = [s for s in more if json.dumps(s["values"], sort_keys=True) not in seen]
        if not fresh:
            break
        seen |= {json.dumps(s["values"], sort_keys=True) for s in fresh}
        out += fresh
    ctrl["_topped_up"] = k
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    return out


def _generate(ctrl, site, k, model=None, grounded=False, avoid=()):
    if k <= 0:
        return []
    from annotation import macros as registry
    from helpers.llm import call_llm
    fields = [{"key": field_key(f), "label": f.get("label") or f.get("placeholder") or f.get("name"), "type": f["type"],
               "current": f.get("value") or None, "required": f.get("required", False),
               **({"options": [o["text"] for o in f.get("options", [])][:30]} if f.get("options") else {}),
               **({"min": f.get("min"), "max": f.get("max")} if f.get("min") or f.get("max") else {})}
              for f in ctrl["fields"]]
    prompt = json.dumps({"site": ctrl.get("site_name") or site, "page": ctrl.get("page_title"), "form": ctrl.get("heading"),
                         "purpose": registry.describe(ctrl["macro"]).get("description"), "submit_button": ctrl["submit"].get("text"),
                         "fields": fields, "people_on_this_site": _people(site), "page_context": ctrl.get("context", [])[:25],
                         **({"records_on_this_site": records(site),
                             "note": "a value that refers to something (a code, an id, a number) must be one of these"}
                            if grounded else {}),
                         **({"already_used_do_not_repeat": [x["values"] for x in avoid][-40:]} if avoid else {}),
                         "output": {"sets": [{"values": {"<field key>": "<value>"},
                                              "summary": "one short line: what this submission does"}]},
                         "n_sets": k}, ensure_ascii=False)
    raw = call_llm(prompt, system=SYSTEM, json_mode=True, model=model or config.MODEL_SUGGEST, max_tokens=6000,
                   temperature=0.9)
    try:
        sets = json.loads(raw or "").get("sets") or []
    except (ValueError, AttributeError):
        sets = []
    keys = {field_key(f) for f in ctrl["fields"]}
    clean = []
    for s in sets:
        vals = {k2: str(v) for k2, v in (s.get("values") or {}).items() if k2 in keys and v not in (None, "")}
        if vals:
            clean.append({"values": vals, "summary": str(s.get("summary") or "")[:200]})
    return clean


def option_for(field, value):
    """The option of a select/radio field matching a value (by text, then value)."""
    v = re.sub(r"\s+", " ", str(value)).strip().casefold()
    for o in field.get("options") or []:
        if str(o.get("text", "")).strip().casefold() == v:
            return o
    for o in field.get("options") or []:
        if str(o.get("value", "")).strip().casefold() == v:
            return o
    return None
