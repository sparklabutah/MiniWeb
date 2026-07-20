"""Expand forms-surveys (FormFlow) base data.

The site ships with 40 forms / 527 responses, which makes the dashboard and
results pages feel sparse. Adds deterministic (seeded) synthetic survey forms
themed to Meridian Systems workplace life (pulse surveys, event planning,
process feedback, ...) plus realistic responses that match each new form's
field schema (answers JSON keyed by field id; rating/slider values as strings,
checkbox/ranking values as lists, optional fields sometimes blank).

Design constraints honored:
- INSERT-ONLY: existing rows untouched. All new responses attach to NEW forms
  so existing forms' responses_count stays accurate.
- Template table untouched (task fs06 asserts /api/templates count == 6).
- New form ids 41..76 stay clear of the Pew Research runtime forms (100-104);
  new response ids stay far below the Pew response ids (10000+).
- New forms are created_at older than the newest existing form (2026-06-26)
  so the "My Forms" ordering top stays familiar; per-form response counts
  capped well below 500 so results pages render sanely.
- FTS5 content tables are rebuilt after inserting.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: python scripts/expand_forms_surveys_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "forms-surveys-expansion-2026-07-20"

rng = random.Random(4242)

TARGET_NEW_RESPONSES = 4450  # brings site total to ~5064

# ---------------------------------------------------------------------------
# Field/answer vocabularies
# ---------------------------------------------------------------------------

TEXTAREA_POOL = [
    "Overall this works well, just needs some polish.",
    "More async options would help the remote folks.",
    "Communication has improved a lot this quarter.",
    "Too many meetings cutting into focus time.",
    "The process is clear but the tooling is clunky.",
    "Would love more documentation on this.",
    "No complaints from me.",
    "Smooth experience end to end.",
    "Response times could be faster.",
    "Great initiative, keep it going.",
    "Hard to find the right point of contact sometimes.",
    "The onboarding docs were out of date in places.",
    "Please share the results with the whole team.",
    "Budget constraints made this harder than it should be.",
    "Let's revisit this again next quarter.",
    "The new setup is a big improvement over last year.",
    "I did not have time to explore all the options.",
    "Cross-team visibility is still the biggest gap.",
    "",
]

TEXT_POOL = [
    "Alex R.", "Engineering", "Platform team", "N/A", "See notes above",
    "Second floor", "Marketing", "Support", "Design", "Data team",
    "Meridian HQ", "Remote", "Lakeport office", "Cascadia office",
]

# Each theme: (title, description, [field spec]) where field spec is
# (type, label, required, options_or_none, extra)
THEMES = [
    ("Engineering Pulse Survey",
     "Monthly pulse check on engineering morale, workload, and blockers.",
     [("rating", "How would you rate your workload this month?", True, ["1", "2", "3", "4", "5"]),
      ("radio", "Do you feel you have enough focus time?", True,
       ["Always", "Usually", "Sometimes", "Rarely", "Never"]),
      ("checkbox", "What is blocking you right now?", False,
       ["CI wait times", "Unclear requirements", "Meetings", "Code review latency", "Flaky tests", "Nothing"]),
      ("textarea", "Anything else on your mind?", False, None)]),
    ("Office Snack Preferences",
     "Help the office team stock the kitchen with things people actually eat.",
     [("checkbox", "Which snacks should we keep stocked?", True,
       ["Fresh fruit", "Trail mix", "Granola bars", "Chips", "Yogurt", "Dark chocolate"]),
      ("radio", "Preferred coffee roast", False, ["Light", "Medium", "Dark", "Decaf", "I drink tea"]),
      ("rating", "How satisfied are you with current kitchen stock?", True, ["1", "2", "3", "4", "5"]),
      ("text", "Any dietary restrictions we should know about?", False, None)]),
    ("Security Training Feedback",
     "Feedback on the annual security awareness training module.",
     [("rating", "How useful was the training content?", True, ["1", "2", "3", "4", "5"]),
      ("radio", "Was the training length appropriate?", True,
       ["Too short", "About right", "Too long"]),
      ("checkbox", "Which topics need more depth?", False,
       ["Phishing", "Password hygiene", "Device security", "Data handling", "Social engineering"]),
      ("textarea", "Suggestions for next year's training", False, None)]),
    ("Website Usability Feedback",
     "Quick usability survey for the redesigned meridiansystems.com website.",
     [("rating", "How easy was it to find what you were looking for?", True, ["1", "2", "3", "4", "5"]),
      ("dropdown", "Which section did you visit most?", True,
       ["Home", "Product", "Pricing", "Docs", "Careers", "Blog"]),
      ("radio", "How does the new design compare to the old one?", True,
       ["Much better", "Somewhat better", "About the same", "Somewhat worse", "Much worse"]),
      ("textarea", "What should we improve first?", False, None)]),
    ("Meeting Culture Survey",
     "Assessing how our meeting habits affect productivity across teams.",
     [("slider", "Hours per week you spend in meetings", True, None, {"slider_min": 0, "slider_max": 25}),
      ("radio", "Could most of your meetings be an email?", True,
       ["Yes, most of them", "Some of them", "No, they are useful"]),
      ("checkbox", "Which meeting practices should we adopt?", False,
       ["No-meeting Wednesdays", "Agendas required", "25-minute default", "Async standups", "Cameras optional"]),
      ("textarea", "Describe your ideal meeting week", False, None)]),
    ("Desk Setup & Ergonomics Check",
     "Facilities survey to plan the next round of ergonomic equipment orders.",
     [("radio", "Where do you primarily work?", True,
       ["Lakeport office", "Cascadia office", "Home office", "Hybrid"]),
      ("checkbox", "Which equipment would improve your setup?", True,
       ["Standing desk", "Ergonomic chair", "Monitor arm", "External keyboard", "Footrest", "Better lighting"]),
      ("rating", "Rate your current workspace comfort", True, ["1", "2", "3", "4", "5"]),
      ("text", "Desk location or home-office city", False, None)]),
    ("On-call Rotation Feedback",
     "Feedback from engineers on the current on-call rotation and paging load.",
     [("rating", "How manageable is the current on-call load?", True, ["1", "2", "3", "4", "5"]),
      ("slider", "Pages received during your last shift", True, None, {"slider_min": 0, "slider_max": 20}),
      ("radio", "Is the runbook coverage sufficient?", True,
       ["Yes", "Mostly", "Significant gaps", "What runbooks?"]),
      ("textarea", "Worst incident of your last rotation (brief)", False, None)]),
    ("Mentorship Program Feedback",
     "Survey for participants of the Meridian mentorship pilot program.",
     [("radio", "Your role in the program", True, ["Mentor", "Mentee", "Both"]),
      ("rating", "How valuable have the sessions been?", True, ["1", "2", "3", "4", "5"]),
      ("radio", "Preferred meeting cadence", False,
       ["Weekly", "Biweekly", "Monthly", "Ad hoc"]),
      ("textarea", "What would make the program better?", False, None)]),
    ("All-Hands Topic Suggestions",
     "Suggest and prioritize topics for the next company all-hands.",
     [("checkbox", "Which topics should we cover?", True,
       ["Product roadmap", "Financial update", "Customer stories", "Team spotlights", "AMA with leadership", "Hiring plans"]),
      ("radio", "Preferred all-hands length", True, ["30 minutes", "45 minutes", "60 minutes"]),
      ("text", "Submit a question for the AMA", False, None)]),
    ("Code Review Process Survey",
     "How well is our code review process working across repos?",
     [("rating", "Overall satisfaction with code review turnaround", True, ["1", "2", "3", "4", "5"]),
      ("slider", "Typical hours until first review", True, None, {"slider_min": 0, "slider_max": 48}),
      ("checkbox", "What slows reviews down?", False,
       ["Large PRs", "Unclear ownership", "Timezone spread", "CI flakiness", "Nitpicking"]),
      ("radio", "Should we adopt a review SLA?", True, ["Yes", "No", "Depends on repo"]),
      ("textarea", "Other process suggestions", False, None)]),
    ("Design System Feedback",
     "Feedback from product teams using the Meridian design system components.",
     [("rating", "How complete does the component library feel?", True, ["1", "2", "3", "4", "5"]),
      ("checkbox", "Which components are missing or lacking?", False,
       ["Data tables", "Date pickers", "Charts", "File upload", "Empty states", "Dark mode tokens"]),
      ("radio", "How often do you need to build custom components?", True,
       ["Rarely", "Monthly", "Weekly", "Daily"]),
      ("textarea", "Biggest pain point with the design system", False, None)]),
    ("Wellness Program Interest",
     "Gauging interest in wellness benefits for next year's plan.",
     [("checkbox", "Which offerings would you actually use?", True,
       ["Gym stipend", "Meditation app", "Ergonomic assessment", "Mental health days", "Cycling allowance", "Flu shots on site"]),
      ("radio", "Preferred stipend model", False,
       ["Monthly allowance", "Annual lump sum", "Reimbursement per receipt"]),
      ("rating", "How would you rate current wellness benefits?", True, ["1", "2", "3", "4", "5"]),
      ("textarea", "Other wellness ideas", False, None)]),
    ("Travel Policy Feedback",
     "Feedback on the updated corporate travel and expense policy.",
     [("radio", "How clear is the new travel policy?", True,
       ["Very clear", "Somewhat clear", "Neutral", "Somewhat unclear", "Very unclear"]),
      ("rating", "Rate the expense reimbursement turnaround", True, ["1", "2", "3", "4", "5"]),
      ("checkbox", "Which parts caused friction on your last trip?", False,
       ["Booking tool", "Hotel caps", "Per diem rates", "Approval chain", "Receipt scanning"]),
      ("textarea", "Describe any recent expense issue", False, None)]),
    ("Internal Docs Findability Survey",
     "How easily can you find internal documentation when you need it?",
     [("rating", "How findable are internal docs today?", True, ["1", "2", "3", "4", "5"]),
      ("dropdown", "Where do you look first?", True,
       ["Confluence", "GitHub READMEs", "Slack search", "Ask a teammate", "Google Drive"]),
      ("radio", "How often are the docs you find outdated?", True,
       ["Rarely", "Sometimes", "Often", "Almost always"]),
      ("textarea", "Which doc did you fail to find recently?", False, None)]),
    ("Hackathon Interest Poll",
     "Planning the next internal hackathon — themes, timing, and teams.",
     [("radio", "Would you participate in a two-day hackathon?", True,
       ["Definitely", "Probably", "Not sure", "Probably not"]),
      ("checkbox", "Which themes interest you?", False,
       ["AI features", "Developer tooling", "Customer dashboards", "Accessibility", "Performance", "Anything goes"]),
      ("dropdown", "Best quarter to hold it", True, ["Q1", "Q2", "Q3", "Q4"]),
      ("text", "Teammates you'd want to team up with", False, None)]),
    ("Quarterly Planning Retro",
     "Retrospective on how the quarterly planning cycle went for your team.",
     [("rating", "How would you rate the planning process overall?", True, ["1", "2", "3", "4", "5"]),
      ("radio", "Did planning finish on schedule for your team?", True,
       ["Yes", "Slipped by days", "Slipped by weeks"]),
      ("ranking", "Rank what to fix first", True,
       ["Clearer priorities", "Earlier headcount clarity", "Fewer planning meetings", "Better templates"]),
      ("textarea", "One change for next cycle", False, None)]),
    ("Support Tooling Satisfaction",
     "Support team survey on the helpdesk and ticketing tool stack.",
     [("rating", "Overall satisfaction with the ticketing tool", True, ["1", "2", "3", "4", "5"]),
      ("slider", "Tickets you handle per day on average", True, None, {"slider_min": 0, "slider_max": 40}),
      ("checkbox", "Which integrations would save you time?", False,
       ["Slack alerts", "CRM sync", "Auto-triage", "Canned responses", "Screen recording"]),
      ("textarea", "Most annoying part of the current stack", False, None)]),
    ("New Hire 30-Day Check-in",
     "Anonymous check-in for employees who joined in the last month.",
     [("rating", "How smooth was your first 30 days?", True, ["1", "2", "3", "4", "5"]),
      ("radio", "Did you have working equipment on day one?", True, ["Yes", "Partially", "No"]),
      ("checkbox", "What helped you most while ramping up?", False,
       ["Onboarding buddy", "Docs", "Team shadowing", "Manager 1:1s", "Training sessions"]),
      ("textarea", "What confused you the most?", False, None)]),
]

WAVES = ["", " — wave 2", " — wave 3"]


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def make_forms():
    """Build 36 new forms with ids 41..76, created 2025-07 .. 2026-01-25
    (all older than the newest existing form, 2026-06-26)."""
    forms = []
    next_id = 41
    # Owner mix: user 1 gets a modest share so their My Forms page stays tidy.
    owner_pool = [2, 3, 4, 5] * 8 + [1] * 6
    rng.shuffle(owner_pool)
    combos = []
    for wave in WAVES:
        for theme in THEMES:
            combos.append((theme, wave))
    rng.shuffle(combos)
    combos = combos[:36]

    # created_at: spread deterministically between 2025-07-05 and 2026-01-25
    start = datetime.datetime(2025, 7, 5)
    end = datetime.datetime(2026, 1, 25)
    span = int((end - start).total_seconds())

    for (title, desc, field_specs), wave in combos:
        fid = next_id
        next_id += 1
        created = start + datetime.timedelta(seconds=rng.randrange(span))
        created = created.replace(minute=rng.choice([0, 15, 30, 45]), second=0, microsecond=0)
        status = rng.choices(["active", "closed", "draft"], weights=[5, 4, 1])[0]
        fields = []
        for i, spec in enumerate(field_specs):
            ftype, label, required, options = spec[0], spec[1], spec[2], spec[3]
            field = {
                "id": f"f{fid}_{i + 1}",
                "type": ftype,
                "label": label,
                "required": required,
                "options": list(options) if options else [],
            }
            if len(spec) > 4:
                field.update(spec[4])
            fields.append(field)
        forms.append({
            "id": fid,
            "title": title + wave,
            "description": desc,
            "owner_id": owner_pool.pop(),
            "status": status,
            "created_at": iso(created),
            "responses_count": 0,   # filled in after responses generated
            "fields": fields,
        })
    return forms


def answer_for_field(field):
    ftype = field["type"]
    opts = field.get("options") or []
    if ftype == "rating":
        return rng.choices(["1", "2", "3", "4", "5"], weights=[1, 2, 4, 6, 4])[0]
    if ftype in ("radio", "dropdown", "choice"):
        return rng.choice(opts) if opts else ""
    if ftype == "checkbox":
        k = rng.randint(1, min(3, len(opts))) if opts else 0
        return rng.sample(opts, k) if k else []
    if ftype == "ranking":
        ranked = list(opts)
        rng.shuffle(ranked)
        return ranked
    if ftype == "slider":
        lo = field.get("slider_min", 1)
        hi = field.get("slider_max", 10)
        return str(rng.randint(lo, hi))
    if ftype == "textarea":
        return rng.choice(TEXTAREA_POOL)
    if ftype == "text":
        return rng.choice(TEXT_POOL) if rng.random() < 0.7 else ""
    return ""


def make_responses(forms):
    """Generate ~TARGET_NEW_RESPONSES responses across the non-draft new forms.
    Response ids start at 528 (existing max 527) and stay far below the Pew
    runtime response ids (10000+)."""
    fillable = [f for f in forms if f["status"] != "draft"]
    # Per-form target counts (60..200), then trim/pad to hit the target sum.
    counts = [rng.randint(60, 200) for _ in fillable]
    diff = TARGET_NEW_RESPONSES - sum(counts)
    i = 0
    while diff != 0:
        step = 1 if diff > 0 else -1
        if 40 <= counts[i % len(counts)] + step <= 280:
            counts[i % len(counts)] += step
            diff -= step
        i += 1

    responses = []
    next_id = 528
    respondent_pool = [1, 2, 3, 4, 5] * 6 + [0]  # 0 = anonymous, rare like base data
    for form, n in zip(fillable, counts):
        created = datetime.datetime.strptime(form["created_at"], "%Y-%m-%dT%H:%M:%SZ")
        window_days = rng.randint(14, 45)
        for _ in range(n):
            answers = {}
            for field in form["fields"]:
                if not field["required"] and rng.random() < 0.22:
                    # skipped optional field — stored as empty like base data
                    answers[field["id"]] = [] if field["type"] in ("checkbox", "ranking") else ""
                else:
                    answers[field["id"]] = answer_for_field(field)
            submitted = created + datetime.timedelta(
                days=rng.randint(0, window_days),
                hours=rng.randint(7, 21),
                minutes=rng.randrange(60),
                seconds=rng.randrange(60),
            )
            responses.append({
                "id": next_id,
                "form_id": form["id"],
                "respondent_id": rng.choice(respondent_pool),
                "submitted_at": iso(submitted),
                "answers": answers,
            })
            next_id += 1
        form["responses_count"] = n
    return responses


def main():
    dry = "--dry-run" in sys.argv
    forms = make_forms()
    responses = make_responses(forms)

    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    # Safety checks: never overwrite existing rows, stay clear of Pew id space.
    max_form = db.execute("SELECT MAX(id) FROM forms_surveys_forms").fetchone()[0]
    max_resp = db.execute("SELECT MAX(id) FROM forms_surveys_responses").fetchone()[0]
    assert min(f["id"] for f in forms) > max_form, "form id collision"
    assert max(f["id"] for f in forms) < 100, "would collide with Pew form ids"
    assert min(r["id"] for r in responses) > max_resp, "response id collision"
    assert max(r["id"] for r in responses) < 10000, "would collide with Pew response ids"
    assert all(f["created_at"] < "2026-06-26" for f in forms), "form newer than existing newest"

    print(f"New forms: {len(forms)} (ids {forms[0]['id']}..{forms[-1]['id']})")
    print(f"New responses: {len(responses)} (ids 528..{responses[-1]['id']})")
    by_status = {}
    for f in forms:
        by_status[f["status"]] = by_status.get(f["status"], 0) + 1
    print("Form statuses:", by_status)
    print("Max responses on one form:", max(f["responses_count"] for f in forms))

    if dry:
        print("\n-- dry run, sample form --")
        print(json.dumps(forms[0], indent=2)[:800])
        print("\n-- sample response --")
        print(json.dumps(responses[0], indent=2))
        return

    cur = db.cursor()
    for f in forms:
        cur.execute(
            "INSERT INTO forms_surveys_forms "
            "(id, title, description, owner_id, status, created_at, responses_count, "
            " fields, shared_with, attachments) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f["id"], f["title"], f["description"], f["owner_id"], f["status"],
             f["created_at"], f["responses_count"], json.dumps(f["fields"]), "", ""),
        )
    for r in responses:
        cur.execute(
            "INSERT INTO forms_surveys_responses "
            "(id, form_id, respondent_id, submitted_at, answers) VALUES (?,?,?,?,?)",
            (r["id"], r["form_id"], r["respondent_id"], r["submitted_at"],
             json.dumps(r["answers"])),
        )

    # Rebuild FTS indexes from the content tables.
    cur.execute("INSERT INTO fts_forms_surveys_forms(fts_forms_surveys_forms) VALUES('rebuild')")
    cur.execute("INSERT INTO fts_forms_surveys_responses(fts_forms_surveys_responses) VALUES('rebuild')")
    db.commit()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(BACKUP_DIR / "inserted_ids.json", "w") as fh:
        json.dump({
            "forms_surveys_forms": [f["id"] for f in forms],
            "forms_surveys_responses": [r["id"] for r in responses],
        }, fh)

    total = 0
    for t in ("forms", "responses", "templates_forms", "users"):
        n = db.execute(f"SELECT COUNT(*) FROM forms_surveys_{t}").fetchone()[0]
        total += n
        print(f"forms_surveys_{t}: {n}")
    print("Site total:", total)
    db.close()


if __name__ == "__main__":
    main()
