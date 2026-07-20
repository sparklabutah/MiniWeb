"""Expand agency-portals (City of Lakeport) base data.

The site ships with only 86 rows total (18 permits, 16 records, 12 services,
10 announcements, plus small config tables), which makes its filter/extract
macros trivial. This adds deterministic (seeded) synthetic rows:

  - records:       +4400  (public records archive spread over 2017-01 .. 2026-05)
  - permits:       +482   (permit applications 2019-01 .. 2026-05)
  - announcements: +90    (city notices 2024-01 .. 2026-04)
  - services:      +8     (new services in EXISTING categories only)

Task-safety constraints honored (see data/annotations/Minh/agency-portals_*):
  - NO new row mentions fireworks / Fourth of July / Independence Day, so the
    existing "Fourth of July Celebration and Fireworks at Harbor Marina"
    announcement (id 5) remains the unique answer for the fireworks task.
  - NO new record (or permit) is dated in January 2025 (the recorded
    filter_by_date_range task "public records of January 2025" must keep
    returning exactly records 4, 5, 6).
  - Existing services / payment_types / appointment_types rows are untouched
    (no rename, no reorder); new services use only pre-existing categories and
    avoid the words "police" / "report" so the services-page dropdown flow is
    unchanged.
  - New records/permits use owner_user_id / applicant_user_id = 0 (the existing
    convention for non-account citizens) and never the name Alex Rivera.
  - All new dates are <= 2026-05-31, older than each table's newest row.

Insert-only -- existing rows are never touched. Inserted ids are recorded in
data/backups/agency-portals-expansion-2026-07-20/inserted_ids.json for rollback.
FTS5 index tables are rebuilt after insertion.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_agency_portals_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "agency-portals-expansion-2026-07-20"

rng = random.Random(20260720)

FIRST = ["Nancy", "Gerald", "Priya", "Tomas", "Helen", "Marcus", "Linda", "Duane",
         "Sofia", "Walter", "Renee", "Victor", "Gloria", "Frank", "Janet", "Omar",
         "Beverly", "Russell", "Dana", "Felix", "Irene", "Stanley", "Paula", "Hector",
         "Joyce", "Leon", "Marta", "Curtis", "Elaine", "Ramon", "Doris", "Terrence",
         "Yolanda", "Bruce", "Cheryl", "Ivan", "Kathleen", "Norm", "Alicia", "Pete",
         "Ingrid", "Darnell", "Vera", "Sam", "Lucille", "Grant", "Rosa", "Eddie"]
LAST = ["Kowalski", "Tran", "Okafor", "Bergstrom", "Delgado", "Nakamura", "Fitzpatrick",
        "Huang", "Petersen", "Alvarez", "McCready", "Singh", "Womack", "Lindqvist",
        "Barnes", "Castillo", "Novak", "Ferreira", "Doyle", "Yang", "Prescott",
        "Hutchins", "Marsh", "Ellison", "Vaughn", "Chandler", "Beaumont", "Ortega",
        "Weiss", "Kirkland", "Duffy", "Solberg", "Nguyen", "Radford", "Ames", "Coyle"]
STREETS = ["Maple Ln", "Oak Ave", "Cedar Blvd", "Elm Dr", "Birch St", "Harbor Dr",
           "Lakeview Ter", "Pine Ridge Rd", "Willow Ct", "Main St", "Juniper Way",
           "Alder St", "Chestnut Ave", "Douglas Fir Rd", "Meridian Ave", "Summit Trail Rd",
           "Larkspur Ln", "Bayview St", "Spruce Ct", "Cannery Row"]
ZIPS = ["98401", "98402"]
BUSINESS_NAMES = ["Cascadia Coffee Roasters", "Summit Trail Brewing", "Lakeport Hardware & Supply",
                  "Bayview Family Dental", "Meridian Auto Works", "Harborline Seafood Co",
                  "Evergreen Yoga Studio", "Cedar & Sage Salon", "Lakeport Bicycle Outfitters",
                  "Northshore Accounting Group", "Petal & Stem Florists", "Cascadia Lake Kayak Rentals",
                  "Whitecap Cleaning Services", "Old Cannery Antiques", "Pine Ridge Landscaping",
                  "Juniper Street Bakery", "Lakeport Printing Co", "Bluegill Bait & Tackle",
                  "Chestnut Grove Daycare", "Meridian Tax Advisors"]
BUSINESS_SUFFIX = ["LLC", "LLC", "Inc", "Co", ""]
CARS = [(2015, "Honda", "Civic"), (2016, "Toyota", "Camry"), (2018, "Ford", "F-150"),
        (2019, "Toyota", "RAV4"), (2020, "Subaru", "Outback"), (2017, "Chevrolet", "Malibu"),
        (2021, "Mazda", "CX-5"), (2014, "Nissan", "Altima"), (2022, "Hyundai", "Tucson"),
        (2013, "Jeep", "Wrangler"), (2019, "Kia", "Sorento"), (2016, "GMC", "Sierra 1500"),
        (2020, "Honda", "CR-V"), (2018, "Volkswagen", "Jetta"), (2023, "Toyota", "Corolla")]

RECORD_TYPES = ["Property Record", "Utility Account", "Vehicle Registration",
                "Property Tax Record", "Business License"]
RECORD_WEIGHTS = [0.28, 0.22, 0.18, 0.17, 0.15]

PERMIT_TYPES = ["Building", "Renovation", "Electrical", "Plumbing", "Mechanical",
                "Roofing", "Fence", "Sign", "Demolition", "Grading", "Occupancy",
                "Parking Permit", "Building Inquiry"]
PERMIT_WEIGHTS = [0.16, 0.12, 0.10, 0.09, 0.07, 0.08, 0.08, 0.05, 0.03, 0.03, 0.06, 0.10, 0.03]
PERMIT_FEES = {"Building": (250, 1800), "Renovation": (150, 900), "Electrical": (85, 320),
               "Plumbing": (85, 320), "Mechanical": (95, 360), "Roofing": (120, 420),
               "Fence": (60, 160), "Sign": (90, 300), "Demolition": (300, 1200),
               "Grading": (200, 800), "Occupancy": (120, 400), "Parking Permit": (75, 75),
               "Building Inquiry": (0, 0)}
PERMIT_DESC = {
    "Building": ["Construction of a detached {n}-car garage.", "New single-family residence, {n} bedrooms.",
                 "Addition of a rear sunroom.", "New covered deck and stairs at rear of residence."],
    "Renovation": ["Kitchen remodel including new cabinetry and counters.", "Bathroom renovation, fixtures and tile.",
                   "Basement finish with egress window.", "Interior remodel of ground-floor retail space."],
    "Electrical": ["Service panel upgrade to 200 amp.", "Wiring for EV charger in attached garage.",
                   "New circuits for kitchen remodel.", "Exterior lighting installation."],
    "Plumbing": ["Water heater replacement.", "Re-pipe of supply lines.", "New sewer lateral connection.",
                 "Installation of backflow prevention device."],
    "Mechanical": ["Furnace replacement and duct sealing.", "Ductless mini-split heat pump installation.",
                   "Commercial kitchen hood installation."],
    "Roofing": ["Tear-off and re-roof with composition shingles.", "Roof replacement following storm damage."],
    "Fence": ["6-ft cedar privacy fence along rear property line.", "4-ft picket fence in front yard."],
    "Sign": ["Illuminated wall sign for storefront.", "Monument sign at business entrance."],
    "Demolition": ["Demolition of detached shed.", "Demolition of fire-damaged garage."],
    "Grading": ["Site grading for drainage correction.", "Grading and fill for new driveway."],
    "Occupancy": ["Certificate of occupancy for new tenant.", "Change-of-use occupancy review."],
    "Parking Permit": ["Residential parking permit for {addr}. Annual street parking permit."],
    "Building Inquiry": ["Pre-application inquiry regarding setback requirements.",
                         "Inquiry about permit requirements for accessory dwelling unit."],
}
DENIAL_REASONS = [
    "Submitted plans do not meet current setback requirements under R-1 zoning. Revised site plan required.",
    "Incomplete application: structural drawings not stamped by a licensed engineer.",
    "Proposed work conflicts with a recorded utility easement. Alternative routing must be submitted.",
    "Lot coverage would exceed the 40% maximum allowed in this zone.",
    "Property is within the Lakeport Historic Overlay District; Historic Preservation Board review required first.",
    "Application fee unpaid after 60 days; application administratively closed.",
    "Proposed sign area exceeds the maximum allowed under the Lakeport sign code.",
]
REVIEWERS = ["Maria Santos", "Maria Santos", "Maria Santos", "Glen Harada", "Priya Natarajan"]

ANN_CATEGORIES = ["Road Closure", "Park Event", "Utility Maintenance",
                  "Community Meeting", "Finance", "Holiday Schedule"]
# NOTE: none of these mention fireworks / Fourth of July / Independence Day.
ANN_TEMPLATES = {
    "Road Closure": [
        ("{street} Lane Closure for Pavement Repairs",
         "Public Works crews will close one lane of {street} between {cross1} and {cross2} on {mon} {day} for pavement repairs. Flaggers will direct alternating traffic 8 AM - 4 PM. Expect delays."),
        ("Sidewalk Replacement Along {street}",
         "Sections of sidewalk along {street} will be replaced beginning {mon} {day}. Pedestrian detours will be posted. Work is expected to take about two weeks, weather permitting."),
        ("Storm Drain Work to Close {street} Overnight",
         "A storm drain crossing under {street} near {cross1} will be replaced overnight ({mon} {day}, 8 PM - 5 AM). Local access only. Detour via {cross2}."),
    ],
    "Park Event": [
        ("Volunteer Tree Planting at {park}",
         "Parks & Recreation invites volunteers to help plant native trees at {park} on {mon} {day}, 9 AM - noon. Tools and gloves provided. Register at parks@lakeport.gov."),
        ("Outdoor Movie Night at {park}",
         "Bring blankets and chairs for a free outdoor movie at {park} on {mon} {day} at dusk. Concessions benefit the Lakeport Youth Soccer League."),
        ("Fall Harvest Festival at {park}",
         "The annual Fall Harvest Festival returns to {park} on {mon} {day}, 10 AM - 4 PM. Pumpkin patch, hay rides, and local vendors including Juniper Street Bakery."),
        ("Trail Maintenance Day on the Summit Trail",
         "Join Parks & Recreation staff for a volunteer trail maintenance day on the Summit Trail loop, {mon} {day}. Meet at the trailhead kiosk at 8:30 AM."),
    ],
    "Utility Maintenance": [
        ("Hydrant Flushing Schedule - {street} Area",
         "Crews will flush fire hydrants in the {street} area during the week of {mon} {day}. Residents may notice temporary discoloration of tap water; run cold water until clear."),
        ("Planned Water Shutoff: {street}",
         "A planned water shutoff will affect addresses on {street} on {mon} {day}, 9 AM - 2 PM, while crews replace a valve. Affected households have been notified by door hanger."),
        ("Sewer Line Camera Inspections This Month",
         "Public Works contractors will perform camera inspections of sewer mains in the {street} basin beginning {mon} {day}. No service interruption is expected."),
    ],
    "Community Meeting": [
        ("Public Hearing: {street} Corridor Improvements",
         "Planning & Zoning will hold a public hearing on proposed {street} corridor improvements on {mon} {day} at 6:30 PM, City Council Chambers, 100 Civic Center Dr. Written comments accepted through the hearing date."),
        ("Neighborhood Meeting: {park} Playground Renovation",
         "Residents are invited to review concept designs for the {park} playground renovation, {mon} {day}, 6 PM at the {park} shelter. Feedback will guide final design."),
        ("City Council Budget Workshop",
         "The City Council will hold a budget workshop on {mon} {day} at 5:30 PM in Council Chambers. The workshop is open to the public; public comment at the end of the session."),
    ],
    "Finance": [
        ("Utility Rate Adjustment Effective {mon} 1",
         "Water and sewer rates will adjust by 2.4% effective {mon} 1 to fund system maintenance. The average residential bill will increase by about $1.80 per month. Details at Finance & Revenue, Suite 110."),
        ("Business License Renewal Reminder",
         "Annual business license renewals are due by {mon} {day}. Renew online or at Finance & Revenue, 100 Civic Center Dr, Suite 110. Late renewals are assessed a 10% penalty."),
        ("Property Tax Installment Deadline Approaching",
         "The next property tax installment is due {mon} {day}. Payments may be made online, by mail, or in person. Installment plans remain available for balances over $2,000."),
    ],
    "Holiday Schedule": [
        ("City Offices Closed {mon} {day}",
         "All City of Lakeport administrative offices will be closed on {mon} {day} for the observed holiday. Garbage and recycling collection will run one day late for the remainder of the week."),
        ("Holiday Garbage Collection Schedule",
         "Due to the {mon} holiday, garbage and recycling collection will shift one day later during the week of {mon} {day}. Carts should be at the curb by 7 AM on the adjusted day."),
    ],
}
PARKS = ["Liberty Park", "Cascadia Lake Overlook Park", "Pine Ridge Park", "Bayview Commons"]
MONTH_NAMES = ["January", "February", "March", "April", "May", "June", "July",
               "August", "September", "October", "November", "December"]

NEW_SERVICES = [
    # id, name, department_id, code, category, fee_range, online, description
    ("Pet Licenses", 8, "SVC-PET", "Licenses", "$15 - $60", 1,
     "License dogs and cats annually. Discounted fees for spayed or neutered pets. Renewals available online."),
    ("Marriage Licenses", 8, "SVC-MRL", "Vital Records", "$72", 0,
     "Apply for a Washington State marriage license. Both applicants must appear in person at the Clerk & Records office."),
    ("Right-of-Way Permits", 1, "SVC-ROW", "Permits", "$95 - $600", 1,
     "Permits for work within the public right-of-way, including driveway approaches, sidewalk cuts, and utility connections."),
    ("Special Event Permits", 2, "SVC-SEP", "Permits", "$50 - $400", 1,
     "Permits for runs, parades, block parties, and other events held on city streets or in city parks."),
    ("Recycling & Yard Waste Service", 1, "SVC-RCY", "Utilities", "$8 - $22 / month", 1,
     "Sign up for curbside recycling and seasonal yard waste collection. Cart exchanges and extra pickups available."),
    ("Business Tax Filing", 4, "SVC-BTX", "Taxes", "Varies by gross receipts", 1,
     "File quarterly or annual Lakeport business & occupation tax returns online through the Finance & Revenue portal."),
    ("Boat Launch Registration", 2, "SVC-BLR", "Registration", "$40 / season", 1,
     "Seasonal registration for use of the city's public boat launches on Cascadia Lake. Daily passes sold on site."),
    ("Rental Housing Registration", 7, "SVC-RHR", "Registration", "$35 / unit", 1,
     "Annual registration of residential rental units as required by the Lakeport rental housing code."),
]


def person():
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def address():
    return f"{rng.randint(100, 4999)} {rng.choice(STREETS)}, Lakeport, WA {rng.choice(ZIPS)}"


def rand_date(start, end):
    """Random date between two dates (inclusive), never in January 2025."""
    while True:
        n = rng.randint(0, (end - start).days)
        d = start + datetime.timedelta(days=n)
        if not (d.year == 2025 and d.month == 1):
            return d


def make_records(start_id, count):
    rows = []
    start = datetime.date(2017, 1, 3)
    end = datetime.date(2026, 5, 31)
    for i in range(count):
        rid = start_id + i
        rtype = rng.choices(RECORD_TYPES, weights=RECORD_WEIGHTS)[0]
        filed = rand_date(start, end)
        addr = address()
        row = {"id": rid, "record_id": f"REC-{filed.year}-{rid:04d}", "type": rtype,
               "owner": person(), "owner_user_id": 0, "address": addr,
               "description": "", "parcel_number": "", "date_filed": filed.isoformat(),
               "status": "Active", "account_number": "", "registration_number": "",
               "expiration": "", "license_number": "", "tax_year": 0}
        if rtype == "Property Record":
            bought = rng.randint(1988, filed.year)
            value = rng.randint(180, 980) * 1000
            kind = rng.choice(["Single-family residence", "Duplex", "Townhome",
                               "Condominium unit", "Rental property", "Commercial storefront"])
            row["description"] = (f"{kind} at {addr.split(',')[0]}. Purchased {bought}. "
                                  f"Assessed value: ${value:,}.")
            row["parcel_number"] = f"LP-{bought}-{rng.randint(10000, 99999)}"
        elif rtype == "Utility Account":
            zipc = addr.split()[-1]
            row["description"] = (f"Water and sewer utility account for {addr.split(',')[0]}. "
                                  f"Monthly billing cycle."
                                  + (" Auto-pay enrolled." if rng.random() < 0.5 else ""))
            row["account_number"] = f"UTL-{zipc}-{rng.randint(10000, 99999)}"
            row["status"] = rng.choices(["Active", "Pending"], weights=[0.9, 0.1])[0]
        elif rtype == "Vehicle Registration":
            yr, make, model = rng.choice(CARS)
            plate = f"WA-{''.join(rng.choices('ABCDEFGHJKLMNPRSTUVWXYZ', k=3))}-{rng.randint(1000, 9999)}"
            exp = filed + datetime.timedelta(days=365)
            row["description"] = (f"Vehicle registration for {yr} {make} {model}. License plate: {plate}. "
                                  f"Registration valid through {MONTH_NAMES[exp.month-1]} {exp.year}.")
            row["registration_number"] = f"VEH-WA-{filed.year}-{rng.randint(10000, 99999)}"
            row["expiration"] = exp.isoformat()
        elif rtype == "Property Tax Record":
            value = rng.randint(180, 980) * 1000
            tax = round(value * 0.011, 2)
            paid = rng.random() < 0.8
            row["tax_year"] = filed.year
            row["status"] = "Paid" if paid else "Pending"
            row["description"] = (f"{filed.year} property tax assessment for {addr.split(',')[0]}. "
                                  f"Assessed value: ${value:,}. Tax amount: ${tax:,.2f}. "
                                  + ("Status: Paid in full." if paid else f"Due: August 31, {filed.year}."))
        else:  # Business License
            biz = rng.choice(BUSINESS_NAMES)
            suffix = rng.choice(BUSINESS_SUFFIX)
            bizname = f"{biz} {suffix}".strip()
            exp = filed + datetime.timedelta(days=365)
            row["description"] = (f"Business license for {bizname}. "
                                  f"{rng.choice(['License renewed annually.', 'New business registration.', 'Annual renewal filed on time.'])}")
            row["license_number"] = f"BIZ-LP-{filed.year}-{rng.randint(100, 9999):04d}"
            row["expiration"] = exp.isoformat()
        rows.append(row)
    return rows


def make_permits(start_id, count):
    rows = []
    start = datetime.date(2019, 1, 7)
    end = datetime.date(2026, 5, 20)
    for i in range(count):
        pid = start_id + i
        ptype = rng.choices(PERMIT_TYPES, weights=PERMIT_WEIGHTS)[0]
        submitted = rand_date(start, end)
        addr = address()
        lo, hi = PERMIT_FEES[ptype]
        fee = float(lo) if lo == hi else float(rng.randrange(lo, hi, 5))
        desc = rng.choice(PERMIT_DESC[ptype]).format(n=rng.randint(1, 4), addr=addr.split(",")[0])
        status = rng.choices(["Approved", "Pending", "Denied"], weights=[0.62, 0.23, 0.15])[0]
        # Only permits recent enough can still plausibly be pending
        if status == "Pending" and submitted < datetime.date(2025, 9, 1):
            status = "Approved"
        reviewed = "" if status == "Pending" else (submitted + datetime.timedelta(days=rng.randint(5, 30))).isoformat()
        row = {"id": pid, "code": f"PRM-{submitted.year}-{pid:04d}", "type": ptype,
               "applicant": person(), "applicant_user_id": 0, "address": addr,
               "status": status, "date_submitted": submitted.isoformat(),
               "date_reviewed": reviewed,
               "reviewed_by": rng.choice(REVIEWERS) if reviewed else "",
               "department_id": 1 if ptype == "Parking Permit" else 3,
               "fee": fee, "description": desc, "valid_from": "", "valid_to": "",
               "denial_reason": rng.choice(DENIAL_REASONS) if status == "Denied" else ""}
        if ptype == "Parking Permit" and status == "Approved":
            vf = datetime.date.fromisoformat(reviewed) + datetime.timedelta(days=rng.randint(7, 30))
            row["valid_from"] = vf.isoformat()
            row["valid_to"] = (vf + datetime.timedelta(days=364)).isoformat()
        rows.append(row)
    return rows


def make_announcements(start_id, count):
    rows = []
    start = datetime.date(2024, 1, 5)
    end = datetime.date(2026, 4, 30)
    dept_for_cat = {"Road Closure": 1, "Park Event": 2, "Utility Maintenance": 1,
                    "Community Meeting": 3, "Finance": 4, "Holiday Schedule": 8}
    for i in range(count):
        aid = start_id + i
        cat = rng.choice(ANN_CATEGORIES)
        title_t, content_t = rng.choice(ANN_TEMPLATES[cat])
        posted = rand_date(start, end)
        s1, s2, s3 = rng.sample(STREETS, 3)
        event = posted + datetime.timedelta(days=rng.randint(7, 45))
        subs = {"street": s1, "cross1": s2, "cross2": s3, "park": rng.choice(PARKS),
                "mon": MONTH_NAMES[event.month - 1], "day": event.day}
        rows.append({"id": aid, "title": title_t.format(**subs),
                     "department_id": dept_for_cat[cat], "date": posted.isoformat(),
                     "category": cat, "content": content_t.format(**subs)})
    return rows


def make_services(start_id):
    rows = []
    for i, (name, dept, code, cat, fees, online, desc) in enumerate(NEW_SERVICES):
        rows.append({"id": start_id + i, "name": name, "department_id": dept,
                     "code": code, "category": cat, "fee_range": fees,
                     "online": online, "description": desc})
    return rows


FORBIDDEN = ["firework", "fourth of july", "independence day", "july 4", "alex rivera"]


def check_forbidden(rows, fields):
    for r in rows:
        blob = " ".join(str(r.get(f, "")) for f in fields).lower()
        for w in FORBIDDEN:
            assert w not in blob, f"forbidden term {w!r} in row {r.get('id')}"


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    next_id = {}
    for t in ("records", "permits", "announcements", "services"):
        next_id[t] = db.execute(
            f"SELECT COALESCE(MAX(id),0)+1 FROM agency_portals_{t}").fetchone()[0]

    records = make_records(next_id["records"], 4400)
    permits = make_permits(next_id["permits"], 482)
    announcements = make_announcements(next_id["announcements"], 90)
    services = make_services(next_id["services"])

    # ---- safety assertions --------------------------------------------------
    assert not any(r["date_filed"].startswith("2025-01") for r in records)
    assert not any(p["date_submitted"].startswith("2025-01") for p in permits)
    assert all(r["date_filed"] <= "2026-05-31" for r in records)
    assert all(p["date_submitted"] <= "2026-05-31" for p in permits)
    assert all(a["date"] <= "2026-04-30" for a in announcements)
    check_forbidden(records, ["owner", "address", "description"])
    check_forbidden(permits, ["applicant", "address", "description", "denial_reason"])
    check_forbidden(announcements, ["title", "content"])
    check_forbidden(services, ["name", "description"])
    existing_cats = {r[0] for r in db.execute(
        "SELECT DISTINCT category FROM agency_portals_services")}
    assert all(s["category"] in existing_cats for s in services), "new service category"

    plan = {"records": records, "permits": permits,
            "announcements": announcements, "services": services}
    for name, rows in plan.items():
        print(f"{name}: +{len(rows)} (ids {rows[0]['id']}..{rows[-1]['id']})")

    if dry:
        print("\n-- dry run, nothing written. Sample rows:")
        for name, rows in plan.items():
            print(f"\n[{name}]")
            for r in rows[:2]:
                print(" ", r)
        return

    inserted = {}
    with db:
        for name, rows in plan.items():
            cols = list(rows[0].keys())
            sql = (f"INSERT INTO agency_portals_{name} ({', '.join(cols)}) "
                   f"VALUES ({', '.join('?' for _ in cols)})")
            db.executemany(sql, [[r[c] for c in cols] for r in rows])
            inserted[name] = [r["id"] for r in rows]
        # rebuild external-content FTS indexes for touched tables
        for name in plan:
            fts = f"fts_agency_portals_{name}"
            if db.execute("SELECT name FROM sqlite_master WHERE name=?", (fts,)).fetchone():
                db.execute(f"INSERT INTO [{fts}]([{fts}]) VALUES('rebuild')")
                print(f"rebuilt {fts}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    out = BACKUP_DIR / "inserted_ids.json"
    out.write_text(json.dumps(
        {f"agency_portals_{k}": v for k, v in inserted.items()}, indent=1))
    print(f"\ninserted-id backup written to {out}")

    for t in ("records", "permits", "announcements", "services"):
        n = db.execute(f"SELECT COUNT(*) FROM agency_portals_{t}").fetchone()[0]
        print(f"agency_portals_{t}: {n} rows")


if __name__ == "__main__":
    main()
