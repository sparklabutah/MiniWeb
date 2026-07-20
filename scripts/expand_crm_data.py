"""Expand crm (SalesPro CRM / Meridian Systems) base data.

The CRM ships with 57 companies / 136 contacts / 90 deals / 460 activities,
which is thin for a sales org tracking years of pipeline. Adds deterministic
(seeded) synthetic companies, contacts, deals, and activities themed to the
existing Meridian Systems product line (MeridianLens/Vault/Flow, SalesPro CRM,
Analytics Suite, ...) and Lakeport, WA branding.

Task-safety constraints honored (see data/annotations/*/crm_*):
- No new rows reference Lisa Engstrom (contact id 2) in any way; her most
  recent meeting stays the 2026-02-20 "demo".
- No new contact gets the title "CTO" (or any Chief * title) so the CTO
  search still resolves to Martin Kessler, (360) 555-5601. New contact
  full names are unique against all existing contact names.
- New contact ids stay < 5425 and deal ids < 3345 (form-typed ids in a task).
- New activity dates are spread 2024-04-01..2026-06-18 (all older than the
  newest existing activities), so date-recency answers are unchanged.

Insert-only; inserted ids recorded under data/backups/ for rollback.

Usage: python scripts/expand_crm_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(2026_07_20)

N_COMPANIES = 150
N_CONTACTS = 360
N_DEALS = 330
N_ACTIVITIES = 3415

MAX_ACTS_PER_CONTACT = 35
MAX_ACTS_PER_DEAL = 22

LISA_CONTACT_ID = 2

# ---------------------------------------------------------------------------
# Vocabulary (distinct from existing pools so names can't collide)
# ---------------------------------------------------------------------------

CO_PREFIXES = ["Alder", "Aspen", "Basalt", "Cobalt", "Copper", "Drift", "Elk",
               "Fern", "Glacier", "Harbor", "Hemlock", "Juniper", "Kestrel",
               "Larch", "Madrona", "Maple", "Meadow", "Obsidian", "Orca",
               "Osprey", "Quartz", "Redcedar", "River", "Sequoia", "Silver",
               "Sitka", "Skyline", "Snowcap", "Spruce", "Starling", "Tide",
               "Timber", "Trillium", "Vine", "Willow", "Yarrow"]
CO_ROOTS = ["field", "gate", "haven", "line", "peak", "point", "forge",
            "works", "view", "bridge", "crest", "harbor"]
CO_LEGAL = ["Co", "LLC", "Inc", "Group"]

FIRST_NAMES = ["Abigail", "Adrian", "Alicia", "Andre", "Anika", "Bennett",
               "Bianca", "Brendan", "Callie", "Carmen", "Cedric", "Chandra",
               "Colin", "Daphne", "Darius", "Deirdre", "Dmitri", "Elena",
               "Elliot", "Emiko", "Ernesto", "Felicia", "Gareth", "Gemma",
               "Gustav", "Hazel", "Hector", "Imogen", "Ingrid", "Isaac",
               "Jarrett", "Joelle", "Jonas", "Kendra", "Kiran", "Lachlan",
               "Leona", "Lorenzo", "Magda", "Marcus", "Mireille", "Mona"]
LAST_NAMES = ["Ashford", "Beaumont", "Calloway", "Delgado", "Eastman",
              "Fairbanks", "Galloway", "Hollins", "Ivarsson", "Jacobsen",
              "Kowalski", "Lindqvist", "Marchetti", "Novak", "Oberg",
              "Petrov", "Quintana", "Rosales", "Sandoval", "Thistlewood",
              "Ueda", "Vandermeer", "Winslow", "Ybarra", "Zamora",
              "Takeda", "Ramsey", "Nystrom", "Voss", "Pruitt", "Ortega",
              "Solberg", "Urbina", "Yamada", "Whitfield", "Norwood"]

# Existing titles minus every Chief* title and CTO (task: "the CTO" must stay
# Martin Kessler, and semantic search for CTO must not gain candidates).
TITLES = ["VP of Operations", "IT Director", "Compliance Manager",
          "IT Manager", "Operations Manager", "Director of Supply Chain",
          "IT Coordinator", "SVP of Technology", "Security Operations Lead",
          "Research Director", "Data Analyst", "Project Controls Manager",
          "General Manager", "Director of Analytics", "Procurement Lead",
          "Operations Director", "VP Sales", "Product Manager",
          "Engineering Manager", "Academic Director"]

INDUSTRIES = ["Manufacturing", "SaaS", "Retail", "Finance", "Logistics",
              "Healthcare", "Education", "Construction", "Agriculture",
              "Financial Services", "Energy & Utilities", "Food & Beverage",
              "Logistics & Transportation"]
SIZES = ["1-50", "51-200", "201-1000", "1000+"]
CITIES = ["Lakeport, WA", "Lakeport, WA", "Lakeport, WA", "Lakeport, WA",
          "Vancouver, WA", "Bellingham, WA", "Eugene, OR", "Bend, OR"]

PRODUCTS = ["MeridianLens", "MeridianVault", "MeridianFlow", "SalesPro CRM",
            "Mobile SDK", "Support Desk", "Analytics Suite", "Data Pipeline"]

STAGES = ["prospecting", "qualification", "proposal", "negotiation",
          "closed_won", "closed_lost"]
STAGE_WEIGHTS = [20, 18, 15, 12, 20, 15]
STAGE_PROB = {"prospecting": 10, "qualification": 25, "proposal": 50,
              "negotiation": 75, "closed_won": 100, "closed_lost": 0}

ACT_TYPES = ["call", "meeting", "email", "demo", "note"]
ACT_WEIGHTS = [24, 22, 18, 15, 21]
DURATIONS = [10, 15, 15, 20, 25, 30, 30, 30, 30, 35, 40, 45, 45, 60, 60, 75, 90]

SUBJECTS = {
    "call": ["Discovery call with {co}", "{co} renewal pricing call",
             "Follow-up call with {co}", "Budget discussion with {co}",
             "{co} onboarding check-in call", "Cold outreach call to {co}",
             "{co} support escalation call"],
    "meeting": ["{co} quarterly business review", "Executive briefing with {co}",
                "{co} contract review meeting", "Kickoff meeting with {co}",
                "{co} security review sync", "{co} implementation planning session",
                "Renewal strategy meeting for {co}"],
    "email": ["Sent proposal to {co}", "{prod} pricing summary for {co}",
              "Renewal reminder to {co}", "{co} follow-up on open questions",
              "Shared {prod} case study with {co}",
              "Contract redlines returned to {co}"],
    "demo": ["{prod} live demo for {co}", "{prod} technical deep-dive for {co}",
             "Sandbox walkthrough of {prod} for {co}",
             "{prod} demo follow-up for {co}",
             "{prod} dashboard demo for {co} stakeholders"],
    "note": ["Logged {co} account review notes", "Updated next steps for {co}",
             "{co} risk assessment note", "Competitive notes for {co} evaluation",
             "{co} org chart and buying committee notes"],
}
NOTE_LINES = [
    "{user} walked {contact} through {prod} reporting features; strong interest in dashboards.",
    "{contact} asked for a revised quote; {user} to follow up next week.",
    "{user} confirmed timeline and success criteria with {contact}.",
    "Budget holder looped in; {contact} expects internal sign-off soon.",
    "{contact} raised integration questions; {user} shared API docs.",
    "Competitor mentioned during the conversation; positioning notes updated.",
    "{user} reviewed rollout plan with {contact}; pilot group agreed.",
    "Left detailed voicemail and sent recap email to {contact}.",
]


def d(y, m, dd):
    return datetime.date(y, m, dd)


def rand_date(start, end):
    return (start + datetime.timedelta(days=rng.randint(0, (end - start).days))).isoformat()


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    users = [r["id"] for r in db.execute("SELECT id FROM crm_users ORDER BY id")]
    user_first = {r["id"]: r["name"].split()[0]
                  for r in db.execute("SELECT id, name FROM crm_users")}
    staff = [u for u in users if u != 1]  # keep bulk off the main user (alex)

    existing_names = {r[0] for r in db.execute("SELECT name FROM crm_contacts")}
    existing_phones = {r[0] for r in db.execute("SELECT phone FROM crm_contacts")}
    existing_co_names = {r[0] for r in db.execute("SELECT name FROM crm_companies")}

    next_company = db.execute("SELECT MAX(id)+1 FROM crm_companies").fetchone()[0]
    next_contact = db.execute("SELECT MAX(id)+1 FROM crm_contacts").fetchone()[0]
    next_deal = db.execute("SELECT MAX(id)+1 FROM crm_deals").fetchone()[0]
    next_act = db.execute("SELECT MAX(id)+1 FROM crm_activities").fetchone()[0]

    # ---------------- companies ----------------
    companies_new = []
    names_pool = set()
    while len(companies_new) < N_COMPANIES:
        name = f"{rng.choice(CO_PREFIXES)}{rng.choice(CO_ROOTS)} {rng.choice(CO_LEGAL)}"
        if name in existing_co_names or name in names_pool:
            continue
        names_pool.add(name)
        slug = name.rsplit(" ", 1)[0].replace(" ", "").lower()
        companies_new.append({
            "id": next_company, "name": name,
            "industry": rng.choice(INDUSTRIES), "size": rng.choice(SIZES),
            "website": f"https://{slug}.example.com",
            "address": rng.choice(CITIES),
            "annual_revenue": rng.randint(5, 400) * 100_000,
            "status": rng.choices(["prospect", "active", "customer", "churned"],
                                  weights=[38, 30, 24, 8])[0],
            "primary_contact_id": "",  # matches existing synthetic rows
            "owner_id": rng.choice(staff),
            "created_date": rand_date(d(2024, 1, 2), d(2025, 12, 20)),
            "notes": "",
        })
        next_company += 1

    # company pool contacts/deals may attach to: existing synthetic (11..57) + new
    synth_companies = [dict(r) for r in db.execute(
        "SELECT id, name, website, created_date FROM crm_companies WHERE id > 10")]
    company_pool = synth_companies + companies_new
    co_by_id = {c["id"]: c for c in company_pool}

    # ---------------- contacts ----------------
    contacts_new = []
    used_names = set(existing_names)
    used_phones = set(existing_phones) | {"(360) 555-5601"}
    while len(contacts_new) < N_CONTACTS:
        first, last = rng.choice(FIRST_NAMES), rng.choice(LAST_NAMES)
        full = f"{first} {last}"
        if full in used_names:
            continue
        used_names.add(full)
        while True:
            phone = f"({rng.choice(['360','360','360','206','425','541'])}) 555-{rng.randint(1000, 9999)}"
            if phone not in used_phones:
                used_phones.add(phone)
                break
        co = rng.choice(company_pool)
        domain = co["website"].split("//")[1]
        created = rand_date(d(2024, 1, 1), d(2026, 3, 20))
        last_contacted = rand_date(
            datetime.date.fromisoformat(created), d(2026, 6, 18))
        contacts_new.append({
            "id": next_contact, "first_name": first, "last_name": last,
            "name": full,
            "email": f"{first.lower()}.{last.lower()}@{domain}",
            "phone": phone, "title": rng.choice(TITLES),
            "company_id": co["id"],
            "status": rng.choices(["lead", "active", "qualified", "customer"],
                                  weights=[35, 30, 20, 15])[0],
            "owner_id": rng.choice(staff),
            "created_date": created, "last_contacted": last_contacted,
            "notes": "",
        })
        next_contact += 1

    # company -> contact ids (existing synthetic contacts + new ones)
    co_contacts = {}
    for r in db.execute(
            "SELECT id, company_id FROM crm_contacts WHERE id != ?", (LISA_CONTACT_ID,)):
        co_contacts.setdefault(r["company_id"], []).append(r["id"])
    for c in contacts_new:
        co_contacts.setdefault(c["company_id"], []).append(c["id"])

    # ---------------- deals ----------------
    deals_new = []
    dealable = [c for c in company_pool if co_contacts.get(c["id"])]
    for _ in range(N_DEALS):
        co = rng.choice(dealable)
        product = rng.choice(PRODUCTS)
        stage = rng.choices(STAGES, weights=STAGE_WEIGHTS)[0]
        created = rand_date(d(2024, 6, 1), d(2026, 5, 15))
        close = rand_date(
            datetime.date.fromisoformat(created) + datetime.timedelta(days=45),
            datetime.date.fromisoformat(created) + datetime.timedelta(days=400))
        deals_new.append({
            "id": next_deal, "name": f"{product} — {co['name']}",
            "company_id": co["id"],
            "contact_id": rng.choice(co_contacts[co["id"]]),
            "owner_id": rng.choice(staff), "product": product,
            "stage": stage, "amount": float(rng.randint(8, 260) * 1000),
            "probability": STAGE_PROB[stage],
            "close_date": close, "created_date": created, "notes": "",
        })
        next_deal += 1

    # ---------------- activities ----------------
    # Anchor every activity to a real deal (matches existing data: deal_id
    # is never 0). Pool = existing deals + new deals, minus anything that
    # could touch Lisa Engstrom (no existing deal references contact 2,
    # asserted below).
    existing_deals = [dict(r) for r in db.execute(
        "SELECT id, name, company_id, contact_id, owner_id, product, created_date "
        "FROM crm_deals WHERE contact_id != ?", (LISA_CONTACT_ID,))]
    assert db.execute("SELECT COUNT(*) FROM crm_deals WHERE contact_id = ?",
                      (LISA_CONTACT_ID,)).fetchone()[0] == 0
    deal_pool = existing_deals + deals_new

    co_names_all = {r[0]: r[1] for r in db.execute("SELECT id, name FROM crm_companies")}
    for c in companies_new:
        co_names_all[c["id"]] = c["name"]
    contact_first_by_id = {r[0]: r[1].split()[0] for r in db.execute(
        "SELECT id, name FROM crm_contacts")}
    for c in contacts_new:
        contact_first_by_id[c["id"]] = c["first_name"]

    per_contact = dict(db.execute(
        "SELECT contact_id, COUNT(*) FROM crm_activities GROUP BY contact_id"))
    per_deal = dict(db.execute(
        "SELECT deal_id, COUNT(*) FROM crm_activities GROUP BY deal_id"))

    activities_new = []
    d_start, d_end = d(2024, 4, 1), d(2026, 6, 18)
    while len(activities_new) < N_ACTIVITIES:
        deal = rng.choice(deal_pool)
        cid = deal["contact_id"]
        if cid == LISA_CONTACT_ID:
            continue
        if per_deal.get(deal["id"], 0) >= MAX_ACTS_PER_DEAL:
            continue
        if per_contact.get(cid, 0) >= MAX_ACTS_PER_CONTACT:
            continue
        atype = rng.choices(ACT_TYPES, weights=ACT_WEIGHTS)[0]
        co_name = co_names_all.get(deal["company_id"], "the account")
        product = deal.get("product") or rng.choice(PRODUCTS)
        subject = rng.choice(SUBJECTS[atype]).format(co=co_name, prod=product)
        uid = deal["owner_id"] if rng.random() < 0.7 else rng.choice(staff)
        start = max(d_start, datetime.date.fromisoformat(deal["created_date"])) \
            if deal.get("created_date") else d_start
        if start > d_end:
            start = d_start
        date = rand_date(start, d_end)
        notes = ""
        if rng.random() < 0.35:
            notes = rng.choice(NOTE_LINES).format(
                user=user_first.get(uid, "The rep"),
                contact=contact_first_by_id.get(cid, "the contact"),
                prod=product)
        activities_new.append({
            "id": next_act, "type": atype, "subject": subject,
            "contact_id": cid, "deal_id": deal["id"], "user_id": uid,
            "date": date, "duration_minutes": rng.choice(DURATIONS),
            "notes": notes,
        })
        per_deal[deal["id"]] = per_deal.get(deal["id"], 0) + 1
        per_contact[cid] = per_contact.get(cid, 0) + 1
        next_act += 1

    print(f"companies: +{len(companies_new)}, contacts: +{len(contacts_new)}, "
          f"deals: +{len(deals_new)}, activities: +{len(activities_new)}")
    if dry:
        for c in companies_new[:3]:
            print("  co:", c["id"], c["name"], c["industry"], c["status"])
        for c in contacts_new[:3]:
            print("  ct:", c["id"], c["name"], c["title"], c["phone"])
        for dl in deals_new[:3]:
            print("  dl:", dl["id"], dl["name"], dl["stage"], dl["amount"])
        for a in activities_new[:5]:
            print("  ac:", a["id"], a["type"], a["date"], "|", a["subject"][:60])
        return

    bdir = ROOT / "data" / "backups" / "crm-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "companies": [c["id"] for c in companies_new],
        "contacts": [c["id"] for c in contacts_new],
        "deals": [x["id"] for x in deals_new],
        "activities": [a["id"] for a in activities_new]}, indent=1))

    for table, rows in (("companies", companies_new), ("contacts", contacts_new),
                        ("deals", deals_new), ("activities", activities_new)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO crm_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # sync FTS (external-content tables -> rebuild)
    for table in ("companies", "contacts", "deals", "activities"):
        fts = f"fts_crm_{table}"
        if db.execute("SELECT name FROM sqlite_master WHERE name = ?", (fts,)).fetchone():
            db.execute(f"INSERT INTO [{fts}]([{fts}]) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
