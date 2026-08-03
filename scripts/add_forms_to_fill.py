#!/usr/bin/env python
"""Seed a handful of active forms (owned by other users) so a logged-in user
has real forms to fill out on the forms-surveys dashboard.

The dashboard previously only surfaced forms you OWN; the new "Forms to fill
out" section lists active forms owned by others that you haven't answered yet.
Without any such unanswered forms that section is empty, so this adds a small,
realistic set. Idempotent: skips a form whose exact title already exists.
Writes to the base `forms_surveys_forms` table (visible to every session).
"""
import json
import os
import pathlib
import sqlite3
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def _resolve_db():
    from app import create_app
    import app.db as _appdb
    create_app()
    return _appdb._DB_PATH


DB = os.environ.get("MINIWEB_DB") or _resolve_db()

# owner_id references seed users: 2 Priya (admin), 3 Marcus, 4 Jessica (admin), 5 Ryan
FORMS = [
    {
        "title": "IT Equipment Request",
        "description": "Request a new laptop, monitor, or accessories from IT.",
        "owner_id": 4,
        "fields": [
            {"id": "eqreq_1", "type": "text", "label": "Your full name", "required": True, "options": []},
            {"id": "eqreq_2", "type": "dropdown", "label": "Equipment needed", "required": True,
             "options": ["Laptop", "Monitor", "Keyboard", "Headset", "Docking station"]},
            {"id": "eqreq_3", "type": "radio", "label": "Urgency", "required": True,
             "options": ["Low", "Medium", "High"]},
            {"id": "eqreq_4", "type": "textarea", "label": "Justification", "required": False, "options": []},
        ],
    },
    {
        "title": "Return-to-Office Preferences",
        "description": "Help us plan office space by sharing how you'd like to work.",
        "owner_id": 2,
        "fields": [
            {"id": "rto_1", "type": "radio", "label": "Preferred days in office per week", "required": True,
             "options": ["0", "1", "2", "3", "4", "5"]},
            {"id": "rto_2", "type": "checkbox", "label": "Amenities you'd use", "required": False,
             "options": ["Standing desk", "Quiet room", "Gym", "Cafe", "Parking"]},
            {"id": "rto_3", "type": "rating", "label": "How satisfied are you with current arrangements?",
             "required": True, "options": ["1", "2", "3", "4", "5"]},
            {"id": "rto_5", "type": "slider", "label": "How important is a short commute to you? (1-10)",
             "required": True, "options": [], "slider_min": 1, "slider_max": 10},
            {"id": "rto_4", "type": "textarea", "label": "Additional comments", "required": False, "options": []},
        ],
    },
    {
        "title": "Team Offsite — Activity Poll",
        "description": "Vote on activities and let us know your dietary needs for the offsite.",
        "owner_id": 3,
        "fields": [
            {"id": "off_1", "type": "checkbox", "label": "Which activities interest you?", "required": True,
             "options": ["Hiking", "Cooking class", "Escape room", "Bowling", "Board games"]},
            {"id": "off_2", "type": "dropdown", "label": "Dietary preference", "required": True,
             "options": ["No restrictions", "Vegetarian", "Vegan", "Gluten-free", "Other"]},
            {"id": "off_3", "type": "radio", "label": "Bringing a plus-one?", "required": True,
             "options": ["Yes", "No", "Maybe"]},
            {"id": "off_5", "type": "ranking", "label": "Rank these activities by preference (1 = most preferred)",
             "required": True, "options": ["Hiking", "Cooking class", "Escape room", "Bowling", "Board games"]},
            {"id": "off_4", "type": "text", "label": "Anything we should know?", "required": False, "options": []},
        ],
    },
    {
        "title": "Annual Benefits Enrollment",
        "description": "Select your health plan and optional add-ons for the coming year.",
        "owner_id": 4,
        "fields": [
            {"id": "ben_1", "type": "dropdown", "label": "Health plan", "required": True,
             "options": ["Basic", "Standard", "Premium", "Waive coverage"]},
            {"id": "ben_2", "type": "radio", "label": "Adding dependents?", "required": True,
             "options": ["Yes", "No"]},
            {"id": "ben_3", "type": "checkbox", "label": "Optional add-ons", "required": False,
             "options": ["Dental", "Vision", "Life insurance", "Commuter benefit", "FSA"]},
            {"id": "ben_4", "type": "text", "label": "Requested effective date", "required": False, "options": []},
        ],
    },
    {
        "title": "New Hire Onboarding Feedback",
        "description": "Tell us about your first weeks so we can improve onboarding.",
        "owner_id": 5,
        "fields": [
            {"id": "onb_1", "type": "rating", "label": "Rate your onboarding experience", "required": True,
             "options": ["1", "2", "3", "4", "5"]},
            {"id": "onb_2", "type": "radio", "label": "Were you assigned a mentor?", "required": True,
             "options": ["Yes", "No"]},
            {"id": "onb_3", "type": "textarea", "label": "What went well?", "required": False, "options": []},
            {"id": "onb_4", "type": "textarea", "label": "What could we improve?", "required": False, "options": []},
        ],
    },
]


def main():
    conn = sqlite3.connect(DB, timeout=60)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    existing = {r["title"] for r in cur.execute("SELECT title FROM forms_surveys_forms").fetchall()}
    next_id = (cur.execute("SELECT MAX(id) AS m FROM forms_surveys_forms").fetchone()["m"] or 0) + 1

    created = 0
    for i, f in enumerate(FORMS):
        if f["title"] in existing:
            print(f"skip (exists): {f['title']}")
            continue
        fid = next_id + created
        created_at = f"2026-08-0{1 + (i % 2)}T09:{10 + i:02d}:00Z"
        cur.execute(
            "INSERT INTO forms_surveys_forms "
            "(id, title, description, owner_id, status, created_at, responses_count, fields, shared_with, attachments) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (fid, f["title"], f["description"], f["owner_id"], "active", created_at, 0,
             json.dumps(f["fields"]), "[]", "[]"),
        )
        created += 1
        print(f"added form {fid}: {f['title']} (owner {f['owner_id']})")

    conn.commit()
    conn.close()
    print(f"Done. {created} form(s) added.")


if __name__ == "__main__":
    main()
