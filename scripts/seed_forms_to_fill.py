#!/usr/bin/env python3
"""Give the logged-in user a real inbox of forms to fill out.

The forms-surveys "Forms to fill out" inbox only surfaced ONE form for the
auto-login user (id=1): every other active form owned by someone else had
already been answered, so the respondent-side flow was effectively a single
3-field survey. That doesn't exercise the site's fill macros — submit_by_form,
submit_by_ranking, select_by_dropdown, upload_by_upload all need forms that
actually contain those field types.

This seeds 8 new ACTIVE forms owned by other users (2-5), each with a rich
mix of field types. Collectively they cover EVERY type the respond page
renders: text, textarea, radio, choice, checkbox, dropdown, rating, slider,
ranking, file. User 1 is never a respondent, so all 8 land in their inbox.

A small, deterministic set of responses (from users other than 1) is seeded
per form so results/analytics pages aren't empty and the forms read as live.

Idempotent: a form whose exact title already exists is skipped. Writes to the
base `forms_surveys_forms` / `forms_surveys_responses` tables (visible to
every session). Deterministic — no randomness.

Run: ~/.conda/envs/miniweb/bin/python scripts/seed_forms_to_fill.py
"""
import json
import os
import pathlib
import sqlite3
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _resolve_db():
    from app import create_app
    import app.db as _appdb
    create_app()
    return _appdb._DB_PATH


DB = os.environ.get("MINIWEB_DB") or _resolve_db()

# owner_id references seed users: 2 Priya (admin), 3 Marcus, 4 Jessica (admin),
# 5 Ryan. Each form gets a unique field-id prefix so ids never collide.
FORMS = [
    {
        "title": "Office Relocation Preferences",
        "description": "We're planning the move to the new Lakeport office. Tell us what matters most to you.",
        "owner_id": 2,
        "fields": [
            {"id": "reloc_1", "type": "text", "label": "Your team / department", "required": True, "options": []},
            {"id": "reloc_2", "type": "dropdown", "label": "Preferred floor", "required": True,
             "options": ["2nd (Quiet)", "3rd (Collaboration)", "4th (Exec)", "No preference"]},
            {"id": "reloc_3", "type": "ranking", "label": "Rank these amenities by importance (1 = most important)", "required": True,
             "options": ["Standing desks", "Phone booths", "Natural light", "Kitchen", "Parking"]},
            {"id": "reloc_4", "type": "checkbox", "label": "Which perks would you actually use?", "required": False,
             "options": ["Gym", "Bike storage", "Nap room", "Game room", "Cafe"]},
            {"id": "reloc_5", "type": "slider", "label": "How important is a short commute? (1-10)", "required": True,
             "options": [], "slider_min": 1, "slider_max": 10},
            {"id": "reloc_6", "type": "radio", "label": "Would you use a hot-desk arrangement?", "required": True,
             "options": ["Yes", "No", "Only sometimes"]},
            {"id": "reloc_7", "type": "textarea", "label": "Anything else we should consider?", "required": False, "options": []},
        ],
    },
    {
        "title": "2026 Learning & Development Interests",
        "description": "Help us build the training calendar. What do you want to learn this year?",
        "owner_id": 3,
        "fields": [
            {"id": "lnd_1", "type": "checkbox", "label": "Topics you're interested in", "required": True,
             "options": ["Public speaking", "Data analysis", "Leadership", "Design", "Security", "Writing"]},
            {"id": "lnd_2", "type": "ranking", "label": "Rank your top learning formats", "required": True,
             "options": ["Live workshop", "Self-paced course", "Lunch & learn", "Conference", "Mentorship"]},
            {"id": "lnd_3", "type": "rating", "label": "How satisfied are you with current training?", "required": True,
             "options": ["1", "2", "3", "4", "5"]},
            {"id": "lnd_4", "type": "dropdown", "label": "Hours per month you can commit", "required": True,
             "options": ["1-2", "3-5", "6-10", "10+"]},
            {"id": "lnd_5", "type": "slider", "label": "Budget priority for L&D vs other perks (1-10)", "required": False,
             "options": [], "slider_min": 1, "slider_max": 10},
            {"id": "lnd_6", "type": "textarea", "label": "A specific course or speaker you'd recommend", "required": False, "options": []},
        ],
    },
    {
        "title": "Cafeteria Menu Feedback — Fall",
        "description": "Rate the new fall menu and tell us what to keep on rotation.",
        "owner_id": 4,
        "fields": [
            {"id": "caf_1", "type": "rating", "label": "Overall menu quality", "required": True,
             "options": ["1", "2", "3", "4", "5"]},
            {"id": "caf_2", "type": "checkbox", "label": "Dishes to keep on the menu", "required": False,
             "options": ["Ramen bar", "Taco Tuesday", "Grain bowls", "Pizza", "Salad bar", "Curry station"]},
            {"id": "caf_3", "type": "dropdown", "label": "How often do you eat here?", "required": True,
             "options": ["Daily", "A few times a week", "Weekly", "Rarely"]},
            {"id": "caf_4", "type": "radio", "label": "Are dietary options sufficient?", "required": True,
             "options": ["Yes", "No", "Unsure"]},
            {"id": "caf_5", "type": "ranking", "label": "Rank cuisines you'd like added", "required": False,
             "options": ["Mediterranean", "Korean", "Vegan", "BBQ", "Indian"]},
            {"id": "caf_6", "type": "file", "label": "Photo of a dish you loved (optional)", "required": False, "options": []},
            {"id": "caf_7", "type": "textarea", "label": "Other comments", "required": False, "options": []},
        ],
    },
    {
        "title": "Internal Conference — Session Proposal",
        "description": "Pitch a talk or workshop for the winter internal conference.",
        "owner_id": 5,
        "fields": [
            {"id": "conf_1", "type": "text", "label": "Session title", "required": True, "options": []},
            {"id": "conf_2", "type": "textarea", "label": "Abstract (2-3 sentences)", "required": True, "options": []},
            {"id": "conf_3", "type": "dropdown", "label": "Track", "required": True,
             "options": ["Engineering", "Design", "Product", "Ops", "Career"]},
            {"id": "conf_4", "type": "choice", "label": "Session length", "required": True,
             "options": ["15 min lightning", "30 min talk", "60 min workshop"]},
            {"id": "conf_5", "type": "checkbox", "label": "What do you need?", "required": False,
             "options": ["Projector", "Whiteboard", "Breakout room", "Recording", "Nothing"]},
            {"id": "conf_6", "type": "file", "label": "Upload draft slides (optional)", "required": False, "options": []},
            {"id": "conf_7", "type": "radio", "label": "Willing to present twice if oversubscribed?", "required": True,
             "options": ["Yes", "No"]},
        ],
    },
    {
        "title": "Wellness Program Sign-Up",
        "description": "Choose the wellness activities you'd like the company to sponsor.",
        "owner_id": 2,
        "fields": [
            {"id": "well_1", "type": "dropdown", "label": "Primary wellness goal", "required": True,
             "options": ["Fitness", "Stress reduction", "Nutrition", "Sleep", "Social connection"]},
            {"id": "well_2", "type": "checkbox", "label": "Activities you'd join", "required": True,
             "options": ["Yoga", "Running club", "Meditation", "Team sports", "Cooking class"]},
            {"id": "well_3", "type": "slider", "label": "How stressed do you feel at work lately? (1-10)", "required": True,
             "options": [], "slider_min": 1, "slider_max": 10},
            {"id": "well_4", "type": "rating", "label": "Rate our current wellness offerings", "required": True,
             "options": ["1", "2", "3", "4", "5"]},
            {"id": "well_5", "type": "radio", "label": "Preferred time for sessions", "required": True,
             "options": ["Before work", "Lunch", "After work"]},
            {"id": "well_6", "type": "text", "label": "An instructor or class you'd recommend", "required": False, "options": []},
        ],
    },
    {
        "title": "Internal Tooling Satisfaction",
        "description": "How well do our internal tools serve you? Help us prioritize improvements.",
        "owner_id": 3,
        "fields": [
            {"id": "tool_1", "type": "rating", "label": "Overall satisfaction with internal tools", "required": True,
             "options": ["1", "2", "3", "4", "5"]},
            {"id": "tool_2", "type": "ranking", "label": "Rank tools by how badly they need improvement", "required": True,
             "options": ["Ticketing", "Wiki", "Chat", "CI/CD", "Dashboards"]},
            {"id": "tool_3", "type": "slider", "label": "How much time do you lose to tooling friction weekly? (hrs)", "required": False,
             "options": [], "slider_min": 0, "slider_max": 20},
            {"id": "tool_4", "type": "checkbox", "label": "Which tools do you use daily?", "required": False,
             "options": ["Ticketing", "Wiki", "Chat", "CI/CD", "Dashboards", "Code review"]},
            {"id": "tool_5", "type": "dropdown", "label": "Your role", "required": True,
             "options": ["Engineering", "Design", "Product", "Ops", "Support", "Other"]},
            {"id": "tool_6", "type": "textarea", "label": "The single change that would help you most", "required": False, "options": []},
        ],
    },
    {
        "title": "Community Volunteer Day — Coordination",
        "description": "Sign up for the quarterly volunteer day and tell us your preferences.",
        "owner_id": 4,
        "fields": [
            {"id": "vol_1", "type": "checkbox", "label": "Causes you'd like to support", "required": True,
             "options": ["Food bank", "Park cleanup", "Tutoring", "Animal shelter", "Habitat build"]},
            {"id": "vol_2", "type": "dropdown", "label": "Preferred shift", "required": True,
             "options": ["Morning", "Afternoon", "Full day"]},
            {"id": "vol_3", "type": "ranking", "label": "Rank sites by preference", "required": False,
             "options": ["Downtown food bank", "Lakeport park", "Elementary school", "Shelter", "Build site"]},
            {"id": "vol_4", "type": "radio", "label": "Do you need transportation?", "required": True,
             "options": ["Yes", "No"]},
            {"id": "vol_5", "type": "slider", "label": "How many hours can you volunteer? (1-8)", "required": True,
             "options": [], "slider_min": 1, "slider_max": 8},
            {"id": "vol_6", "type": "file", "label": "Signed waiver (upload if you have it)", "required": False, "options": []},
            {"id": "vol_7", "type": "text", "label": "Dietary needs for the group lunch", "required": False, "options": []},
        ],
    },
    {
        "title": "New Product Name — Vote",
        "description": "Help pick the name for our next release. Your vote counts!",
        "owner_id": 5,
        "fields": [
            {"id": "name_1", "type": "ranking", "label": "Rank the name candidates (1 = favorite)", "required": True,
             "options": ["Beacon", "Cascade", "Northstar", "Harbor", "Summit"]},
            {"id": "name_2", "type": "choice", "label": "Which style do you prefer overall?", "required": True,
             "options": ["Nature-inspired", "Abstract", "Descriptive"]},
            {"id": "name_3", "type": "dropdown", "label": "Your product area", "required": True,
             "options": ["Core", "Mobile", "Platform", "Growth", "Other"]},
            {"id": "name_4", "type": "checkbox", "label": "Names you could NOT live with", "required": False,
             "options": ["Beacon", "Cascade", "Northstar", "Harbor", "Summit"]},
            {"id": "name_5", "type": "rating", "label": "How confident are you in your top pick?", "required": True,
             "options": ["1", "2", "3", "4", "5"]},
            {"id": "name_6", "type": "text", "label": "A name we didn't list", "required": False, "options": []},
        ],
    },
]

# Respondent pool for the seeded responses — deliberately EXCLUDES user 1 so
# every form stays in user 1's "to fill" inbox. Mixes the seed users with a
# few synthetic respondent ids so it reads as many people.
RESPONDENTS = [2, 3, 4, 5, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20]

TEXT_POOL = [
    "Great initiative, thanks for asking.", "Please keep this going every quarter.",
    "The current setup works but could be smoother.", "No strong opinion either way.",
    "This would make a real difference for my team.", "Happy to help organize if needed.",
    "A few small tweaks and this would be perfect.", "Long overdue — glad it's happening.",
    "", "", "Count me in.", "Would prefer more options next time.",
]


def _crc(*parts):
    return zlib.crc32("|".join(str(p) for p in parts).encode())


def _answer_for(field, form_id, resp_i):
    """Deterministic, type-appropriate answer for one field/respondent."""
    ftype = field["type"]
    opts = field.get("options") or []
    seed = _crc(form_id, field["id"], resp_i)
    if ftype in ("text", "textarea"):
        return TEXT_POOL[seed % len(TEXT_POOL)]
    if ftype in ("radio", "choice", "dropdown"):
        return opts[seed % len(opts)] if opts else ""
    if ftype == "rating":
        scale = opts or ["1", "2", "3", "4", "5"]
        # skew toward the middle-high end
        return scale[(seed % (len(scale) - 1)) + 1] if len(scale) > 1 else scale[0]
    if ftype == "slider":
        lo = field.get("slider_min", 0)
        hi = field.get("slider_max", 10)
        return str(lo + seed % (hi - lo + 1))
    if ftype == "checkbox":
        if not opts:
            return []
        # pick a deterministic 1-3 item subset
        k = 1 + seed % min(3, len(opts))
        idxs = sorted({(seed >> (b * 3)) % len(opts) for b in range(k + 2)})[:k]
        return [opts[i] for i in idxs]
    if ftype == "ranking":
        if not opts:
            return []
        # deterministic permutation of the options
        order = sorted(range(len(opts)), key=lambda i: _crc(form_id, field["id"], resp_i, i))
        return [opts[i] for i in order]
    if ftype == "file":
        # respondents rarely attach files
        return f"attachment_{resp_i}.pdf" if seed % 4 == 0 else ""
    return ""


def main():
    conn = sqlite3.connect(str(DB), timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    existing = {r["title"] for r in cur.execute("SELECT title FROM forms_surveys_forms")}
    next_form_id = (cur.execute("SELECT MAX(id) AS m FROM forms_surveys_forms").fetchone()["m"] or 0) + 1
    next_resp_id = (cur.execute("SELECT MAX(id) AS m FROM forms_surveys_responses").fetchone()["m"] or 0) + 1

    created = 0
    total_resp = 0
    for i, f in enumerate(FORMS):
        if f["title"] in existing:
            print(f"skip (exists): {f['title']}")
            continue
        fid = next_form_id + created
        # spread creation dates over the last couple weeks so the inbox sorts sanely
        day = 18 + (i % 10)
        created_at = f"2026-07-{day:02d}T{9 + i % 6:02d}:{15 + i * 3:02d}:00Z"

        # seed a deterministic number of responses (never from user 1)
        n_resp = 8 + _crc(f["title"]) % 23   # 8-30
        for j in range(n_resp):
            respondent = RESPONDENTS[_crc(fid, j) % len(RESPONDENTS)]
            answers = {fld["id"]: _answer_for(fld, fid, j) for fld in f["fields"]}
            rday = 19 + (j % 12)
            submitted = f"2026-07-{rday:02d}T{8 + j % 10:02d}:{(j * 7) % 60:02d}:00Z"
            cur.execute(
                "INSERT INTO forms_surveys_responses (id, form_id, respondent_id, submitted_at, answers) "
                "VALUES (?,?,?,?,?)",
                (next_resp_id, fid, respondent, submitted, json.dumps(answers)),
            )
            next_resp_id += 1
            total_resp += 1

        cur.execute(
            "INSERT INTO forms_surveys_forms "
            "(id, title, description, owner_id, status, created_at, responses_count, fields, shared_with, attachments) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (fid, f["title"], f["description"], f["owner_id"], "active", created_at,
             n_resp, json.dumps(f["fields"]), "[]", "[]"),
        )
        created += 1
        types = sorted({fld["type"] for fld in f["fields"]})
        print(f"added form {fid}: {f['title']} (owner {f['owner_id']}, {n_resp} responses) types={types}")

    conn.commit()
    conn.close()
    print(f"\nDone. {created} form(s) + {total_resp} response(s) added.")


if __name__ == "__main__":
    main()
