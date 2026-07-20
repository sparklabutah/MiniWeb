"""Expand tax-filing-dmv-permits base data (users, tax filings, vehicles, permits, payments).

The Lakeport Government Services Portal ships with only 39 rows total
(5 users, 10 tax filings, 3 vehicles, 6 permits, 15 payments), which makes its
filter/extract/compute macros trivial. This adds deterministic (seeded)
synthetic citizens with multi-year histories while keeping referential
integrity: payments reference the payer's real filings (related_filing_id),
vehicle registrations (related_registration_id) and permits
(related_permit_id); id/key formats (TDPAY-YYYY-NNNN, TAX-YYYY-INC-NNNNN,
PRM-YYYY-NNNN, VEH-YYYY-NNNNN, PKL parcel numbers, CFM confirmation numbers)
and the Lakeport/Cascadia vocabulary are reused.

Task-safety guarantees (saved annotation tasks must stay valid):
- ZERO rows are added for user 1 (alex.rivera) in ANY table. The /payments
  page defaults to the logged-in user's rows, so Alex's payment list — and its
  max/min (3479.30, 75.00) used by task tax-filing-dmv-permits_ed6515 — is
  byte-identical before and after.
- No new payment `type` values are introduced (the payments page type dropdown
  is built from DISTINCT types), keeping the pay_by_form task (c2f3f1) intact.
- No new user reuses existing display names / surnames (Rivera, Mendez,
  Santos, Hensley).

Insert-only — existing rows are never touched. Inserted ids are recorded in
data/backups/tax-filing-dmv-permits-expansion-2026-07-20/inserted_ids.json.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_tax_filing_dmv_permits_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(20260720)

TODAY = datetime.date(2026, 7, 20)
N_USERS = 140
YEARS = list(range(2018, 2026))  # tax years; existing data covers 2024-2025

FIRST = ["Nora", "Devon", "Priya", "Marcus", "Elena", "Trevor", "Yuki", "Colin",
         "Dana", "Felix", "Grace", "Hector", "Imani", "Jonas", "Katie", "Leo",
         "Mabel", "Nathan", "Olive", "Pete", "Quinn", "Rosa", "Stefan", "Tara",
         "Umar", "Vera", "Wesley", "Ximena", "Yusuf", "Zoe", "Arthur", "Bianca",
         "Cedric", "Daphne", "Emmett", "Farrah", "Gideon", "Hazel", "Ivan", "June"]
LAST = ["Whitfield", "Okafor", "Lindqvist", "Barros", "Chalmers", "Dubois",
        "Eastman", "Fontaine", "Galvez", "Hoshino", "Ibarra", "Jamison",
        "Kowalski", "Lachlan", "Moreau", "Nakamura", "Oberg", "Pruitt",
        "Quintana", "Rasmussen", "Sorenson", "Tran", "Ulrich", "Vandermeer",
        "Winslow", "Yates", "Zielinski", "Ashworth", "Beaumont", "Calloway",
        "Drummond", "Ellery", "Farnsworth", "Granger", "Holloway", "Iverson"]
STREETS = ["Maple Ln", "Oak Ave", "Cedar Blvd", "Birch St", "Harbor Dr",
           "Lakeview Ter", "Pine Ridge Rd", "Willow Ct", "Main St", "Elm St",
           "Juniper Way", "Marina Blvd"]
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com", "aol.com", "icloud.com"]
BIZ_WORDS = ["Consulting", "Properties", "Landscaping", "Catering", "Design",
             "Plumbing", "Auto Care", "Books", "Coffee", "Marine Services"]
LENDERS = ["Cascadia Federal Credit Union", "Pacific Northwest Savings Bank",
           "Lakeport Community Bank"]

# (year_range, make, model, trim, colors, body_type, engine, fuel_type, renewal_fee)
CARS = [
    ((2015, 2023), "Honda", "Civic", "EX", ["Lunar Silver Metallic", "Crystal Black Pearl"], "sedan", "2.0L 4-Cylinder", "gasoline", 85.0),
    ((2016, 2024), "Toyota", "Camry", "SE", ["Celestial Silver", "Midnight Black"], "sedan", "2.5L 4-Cylinder", "gasoline", 85.0),
    ((2017, 2024), "Subaru", "Outback", "Premium", ["Autumn Green Metallic", "Ice Silver"], "wagon", "2.5L 4-Cylinder Boxer", "gasoline", 95.0),
    ((2016, 2023), "Ford", "F-150", "XLT SuperCrew", ["Oxford White", "Race Red"], "pickup truck", "3.5L V6 EcoBoost", "gasoline", 95.0),
    ((2018, 2024), "Chevrolet", "Silverado 1500", "LT", ["Shadow Gray Metallic", "Summit White"], "pickup truck", "5.3L V8", "gasoline", 105.0),
    ((2018, 2025), "Toyota", "RAV4", "XLE", ["Magnetic Gray", "Blueprint"], "suv", "2.5L 4-Cylinder", "gasoline", 95.0),
    ((2019, 2025), "Tesla", "Model 3", "Long Range", ["Pearl White", "Deep Blue Metallic"], "sedan", "Dual Motor Electric", "electric", 115.0),
    ((2017, 2023), "Mazda", "CX-5", "Touring", ["Soul Red Crystal", "Machine Gray"], "suv", "2.5L 4-Cylinder", "gasoline", 95.0),
    ((2015, 2021), "Honda", "Odyssey", "EX-L", ["Modern Steel Metallic", "White Diamond Pearl"], "minivan", "3.5L V6", "gasoline", 95.0),
    ((2020, 2025), "Hyundai", "Ioniq 5", "SEL", ["Cyber Gray", "Atlas White"], "suv", "Dual Motor Electric", "electric", 115.0),
]

PERMIT_KINDS = {
    # type: (fee_range_or_fixed, description templates)
    "Parking Permit": ((75.0, 75.0), [
        "Residential parking permit for {addr}. Annual permit for street parking in the {street} corridor.",
        "Renewal of residential parking permit for {addr}.",
    ]),
    "Building": ((200.0, 850.0), [
        "Deck addition at rear of property at {addr}. Includes footings and railing per code.",
        "Detached storage shed (120 sq ft) at {addr}.",
        "Garage extension and new foundation work at {addr}.",
    ]),
    "Renovation": ((120.0, 450.0), [
        "Kitchen renovation at {addr}: cabinet replacement and new countertops.",
        "Bathroom remodel at {addr}, fixtures and tile replacement.",
        "Basement finishing at {addr}, non-structural interior work.",
    ]),
    "Electrical": ((35.0, 35.0), [
        "Panel upgrade to 200A service at {addr}. Licensed electrician on file.",
        "EV charger circuit installation at {addr}.",
        "Rewiring of kitchen circuits at {addr}.",
    ]),
    "Building Inquiry": ((0.0, 0.0), [
        "Pre-application inquiry regarding accessory dwelling unit feasibility at {addr}.",
        "Zoning feasibility question for fence height variance at {addr}.",
    ]),
}

PAY_NOTES = {
    "income_tax": ["", "", "Annual income tax payment", "Balance due with return"],
    "property_tax": ["First half installment", "Second half installment"],
    "business_tax": ["", "Quarterly estimated payment", "Business tax balance due"],
    "vehicle_registration": ["Online registration renewal", "", "Registration renewal"],
    "permit_fee": ["", "Permit application fee"],
    "parking_permit": ["Residential parking permit fee", ""],
}


def iso(d):
    return d.isoformat()


def rand_date(y, m1, m2):
    m = rng.randint(m1, m2)
    return datetime.date(y, m, rng.randint(1, 28))


class Seq:
    """Per-key sequence counters for formatted id strings."""

    def __init__(self, starts):
        self.n = dict(starts)

    def next(self, key, default_start=1):
        v = self.n.get(key, default_start)
        self.n[key] = v + 1
        return v


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    P = "tax_filing_dmv_permits_"
    next_id = {t: db.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM {P}{t}").fetchone()[0]
               for t in ("users", "tax_filings", "vehicles", "permits", "payments")}

    # payment_id seq per year: 2025 has ...0011, 2026 has ...0004 in base data;
    # runtime POSTs mint TDPAY-2026-<max_id+1> (>=2000 after expansion), so the
    # 0500+ block never collides with base rows or runtime-created ones.
    pay_seq = Seq({2025: 500, 2026: 500})
    filing_seq = Seq({})   # key (year, code) -> start 300 (existing max is 203)
    permit_seq = Seq({})   # key year -> start 100 (existing max is 0010)
    veh_seq = Seq({})      # key year -> start 1000 (existing max is 00531)

    new = {"users": [], "tax_filings": [], "vehicles": [], "permits": [], "payments": []}
    used_usernames = {r[0] for r in db.execute(f"SELECT username FROM {P}users")}

    def add_payment(u, ptype, amount, due, paid, *, filing_id="", reg_id="",
                    permit_id="", note=None):
        if paid > TODAY:
            return
        method = rng.choices(["credit_card", "ach_debit", "check"],
                             weights=[45, 35, 20])[0]
        processed = ""
        if method == "check":
            processed = "Robert Hensley"
        elif method == "ach_debit" and rng.random() < 0.3:
            processed = "Robert Hensley"
        row = {
            "id": next_id["payments"],
            "payment_id": f"TDPAY-{paid.year}-{pay_seq.next(paid.year):04d}",
            "user_id": u["id"], "root_user_id": u["root_user_id"],
            "payer_name": u["display_name"], "type": ptype,
            "related_filing_id": filing_id, "amount": round(amount, 2),
            "method": method,
            "account_last_four": str(rng.randint(1000, 9999)) if method == "ach_debit" else "",
            "payment_date": iso(paid), "due_date": iso(due),
            "status": "completed",
            "confirmation_number": f"CFM-{paid.strftime('%Y%m%d')}-{rng.randint(10000, 99999)}",
            "processed_by": processed,
            "notes": note if note is not None else rng.choice(PAY_NOTES[ptype]),
            "related_registration_id": reg_id,
            "card_last_four": str(rng.randint(1000, 9999)) if method == "credit_card" else "",
            "related_permit_id": permit_id,
            "check_number": str(rng.randint(1000, 5000)) if method == "check" else "",
        }
        next_id["payments"] += 1
        new["payments"].append(row)

    # ---- users ----------------------------------------------------------
    name_pairs = rng.sample([(f, l) for f in FIRST for l in LAST], N_USERS)
    for fn, ln in name_pairs:
        uid = next_id["users"]
        next_id["users"] += 1
        username = f"{fn.lower()}.{ln.lower()}"
        while username in used_usernames:
            username += str(rng.randint(2, 9))
        used_usernames.add(username)
        is_biz = rng.random() < 0.12
        biz_name = f"{ln} {rng.choice(BIZ_WORDS)} LLC" if is_biz else ""
        street = rng.choice(STREETS)
        addr = f"{rng.randint(100, 4900)} {street}, Lakeport, WA 98401"
        reg_year = rng.randint(2004, 2024)
        u = {
            "id": uid, "root_user_id": 1000 + uid,
            "username": username, "display_name": f"{fn} {ln}",
            "email": f"{username}@{rng.choice(EMAIL_DOMAINS)}",
            "role": "citizen",
            "tax_id": f"XXX-XX-{rng.randint(1000, 9999)}",
            "account_type": "individual_and_business" if is_biz else "individual",
            "address": addr,
            "phone": f"(555) {rng.randint(200, 899)}-{rng.randint(1000, 9999)}",
            "registered_date": iso(rand_date(reg_year, 1, 12)),
            "last_login": f"{iso(rand_date(2026, 1, 6))}T{rng.randint(7, 20):02d}:{rng.randint(0, 59):02d}:00Z",
            "status": "active",
            "business_name": biz_name,
            "business_tax_id": f"XX-XXX{rng.randint(1000, 9999)}" if is_biz else "",
            "department": "", "title": "", "employee_id": "",
        }
        u["_is_biz"] = is_biz
        u["_homeowner"] = rng.random() < 0.5
        u["_street"] = street
        new["users"].append(u)

    # ---- tax filings + tax payments ------------------------------------
    for u in new["users"]:
        for year in YEARS:
            # --- income tax
            if rng.random() < 0.88:
                fid = f"TAX-{year}-INC-{filing_seq.next((year, 'INC'), 300):05d}"
                gross = round(rng.uniform(32000, 180000), -2)
                taxable = round(gross * rng.uniform(0.68, 0.82), -1)
                refund = rng.random() < 0.2
                owed = 0.0 if refund else round(taxable * rng.uniform(0.042, 0.046), 2)
                due = datetime.date(year + 1, 4, 15)
                status = "filed"
                if year == 2025 and rng.random() < 0.1:
                    status = "pending"
                elif not refund and rng.random() < 0.06:
                    status = "overdue"
                filed_date = rand_date(year + 1, 1, 4)
                if filed_date > due:
                    filed_date = due - datetime.timedelta(days=rng.randint(1, 20))
                paid = owed if status == "filed" and not refund else 0.0
                method = rng.choices(["online", "mail"], weights=[78, 22])[0]
                row = {
                    "id": next_id["tax_filings"], "filing_id": fid,
                    "user_id": u["id"], "root_user_id": u["root_user_id"],
                    "taxpayer_name": u["display_name"], "type": "income_tax",
                    "tax_year": year, "filing_date": iso(filed_date) if status != "overdue" else "",
                    "due_date": iso(due), "status": status,
                    "gross_income": gross, "taxable_income": taxable,
                    "tax_owed": owed, "tax_paid": paid,
                    "refund_amount": round(rng.uniform(120, 1800), 2) if refund else 0.0,
                    "filing_method": method if status != "overdue" else "",
                    "processed_by": "Robert Hensley" if status == "filed" else "",
                    "notes": "Late notice sent" if status == "overdue" else "",
                    "property_address": "", "parcel_number": "",
                    "assessed_value": 0.0, "tax_rate": 0.0,
                    "gross_revenue": 0.0, "taxable_revenue": 0.0,
                }
                next_id["tax_filings"] += 1
                new["tax_filings"].append(row)
                if paid > 0:
                    add_payment(u, "income_tax", paid, due,
                                filed_date + datetime.timedelta(days=rng.randint(0, 3)),
                                filing_id=fid, note="")

            # --- property tax
            if u["_homeowner"] and rng.random() < 0.9:
                fid = f"TAX-{year}-PROP-{filing_seq.next((year, 'PROP'), 300):05d}"
                house_no = u["address"].split(" ")[0]
                street_word = u["_street"].split(" ")[0].upper()
                assessed = round(rng.uniform(240000, 720000), -3)
                rate = round(rng.uniform(0.0105, 0.0125), 4)
                owed = round(assessed * rate, 2)
                due = datetime.date(year + 1, 4, 30)
                filed_date = rand_date(year + 1, 1, 3)
                half1 = round(owed / 2, 2)
                half2 = round(owed - half1, 2)
                due2 = datetime.date(year + 1, 10, 31)
                paid = owed if due2 <= TODAY else half1
                row = {
                    "id": next_id["tax_filings"], "filing_id": fid,
                    "user_id": u["id"], "root_user_id": u["root_user_id"],
                    "taxpayer_name": u["display_name"], "type": "property_tax",
                    "tax_year": year, "filing_date": iso(filed_date),
                    "due_date": iso(due), "status": "filed",
                    "gross_income": 0.0, "taxable_income": 0.0,
                    "tax_owed": owed, "tax_paid": paid, "refund_amount": 0.0,
                    "filing_method": rng.choices(["online", "mail"], weights=[60, 40])[0],
                    "processed_by": "Robert Hensley",
                    "notes": "",
                    "property_address": u["address"],
                    "parcel_number": f"PKL-{year}-{house_no}{street_word}",
                    "assessed_value": assessed, "tax_rate": rate,
                    "gross_revenue": 0.0, "taxable_revenue": 0.0,
                }
                next_id["tax_filings"] += 1
                new["tax_filings"].append(row)
                add_payment(u, "property_tax", half1, due,
                            due - datetime.timedelta(days=rng.randint(2, 25)),
                            filing_id=fid, note="First half installment")
                if due2 <= TODAY:
                    add_payment(u, "property_tax", half2, due2,
                                due2 - datetime.timedelta(days=rng.randint(2, 25)),
                                filing_id=fid, note="Second half installment")

            # --- business tax
            if u["_is_biz"] and rng.random() < 0.85:
                fid = f"TAX-{year}-BIZ-{filing_seq.next((year, 'BIZ'), 300):05d}"
                gross_rev = round(rng.uniform(80000, 900000), -2)
                taxable_rev = round(gross_rev * rng.uniform(0.85, 0.92), -2)
                owed = round(taxable_rev * rng.uniform(0.022, 0.028), 2)
                due = datetime.date(year + 1, 4, 15)
                filed_date = rand_date(year + 1, 2, 3)
                row = {
                    "id": next_id["tax_filings"], "filing_id": fid,
                    "user_id": u["id"], "root_user_id": u["root_user_id"],
                    "taxpayer_name": f"{u['display_name']} / {u['business_name']}",
                    "type": "business_tax",
                    "tax_year": year, "filing_date": iso(filed_date),
                    "due_date": iso(due), "status": "filed",
                    "gross_income": 0.0, "taxable_income": 0.0,
                    "tax_owed": owed, "tax_paid": owed, "refund_amount": 0.0,
                    "filing_method": "online",
                    "processed_by": "Robert Hensley",
                    "notes": f"Business license BL-{year}-{rng.randint(100, 999):04d} on file",
                    "property_address": "", "parcel_number": "",
                    "assessed_value": 0.0, "tax_rate": 0.0,
                    "gross_revenue": gross_rev, "taxable_revenue": taxable_rev,
                }
                next_id["tax_filings"] += 1
                new["tax_filings"].append(row)
                if rng.random() < 0.5:
                    q = round(owed / 4, 2)
                    quarters = [datetime.date(year, 4, 15), datetime.date(year, 6, 15),
                                datetime.date(year, 9, 15), datetime.date(year + 1, 1, 15)]
                    for i, qd in enumerate(quarters):
                        amt = q if i < 3 else round(owed - 3 * q, 2)
                        add_payment(u, "business_tax", amt, qd,
                                    qd - datetime.timedelta(days=rng.randint(0, 10)),
                                    filing_id=fid, note="Quarterly estimated payment")
                else:
                    add_payment(u, "business_tax", owed, due,
                                filed_date + datetime.timedelta(days=rng.randint(0, 5)),
                                filing_id=fid, note="Business tax balance due")

    # ---- vehicles + registration renewal payments -----------------------
    for u in new["users"]:
        n_veh = rng.choices([0, 1, 2, 3], weights=[25, 40, 25, 10])[0]
        for _ in range(n_veh):
            (y1, y2), make, model, trim, colors, body, engine, fuel, fee = rng.choice(CARS)
            model_year = rng.randint(y1, y2)
            owned_since = rng.randint(max(model_year, 2016), 2025)
            vin4 = f"{rng.randint(1000, 9999)}"
            purchase = rand_date(owned_since, 1, 12)
            # last renewal anniversary on/before TODAY
            last_renew = purchase.replace(year=2026)
            if last_renew > TODAY:
                last_renew = purchase.replace(year=2025)
            expiration = last_renew.replace(year=last_renew.year + 1) - datetime.timedelta(days=1)
            lapsed = rng.random() < 0.12
            if lapsed:  # missed the latest renewal
                last_renew = last_renew.replace(year=last_renew.year - 1)
                expiration = expiration.replace(year=expiration.year - 1)
            reg_id = f"VEH-{last_renew.year}-{veh_seq.next(last_renew.year, 1000):05d}"
            emis_last = last_renew - datetime.timedelta(days=rng.randint(3, 30))
            row = {
                "id": next_id["vehicles"], "registration_id": reg_id,
                "user_id": u["id"], "root_user_id": u["root_user_id"],
                "owner_name": u["display_name"],
                "vehicle": json.dumps({
                    "year": model_year, "make": make, "model": model, "trim": trim,
                    "color": rng.choice(colors), "body_type": body,
                    "vin": f"XXXXXXXXXXXX{vin4}", "engine": engine, "fuel_type": fuel,
                }),
                "plate_number": f"{''.join(rng.choice('ABCDEFGHJKLMNPRSTVWXYZ') for _ in range(3))}-{rng.randint(1000, 9999)}",
                "plate_state": "WA",
                "registration_date": iso(last_renew),
                "expiration_date": iso(expiration),
                "renewal_status": "expired" if expiration < TODAY else "current",
                "renewal_due_date": iso(expiration),
                "renewal_fee": fee,
                "late_penalty": 25.0 if expiration < TODAY else 0.0,
                "title_number": f"WA-TTL-{purchase.strftime('%Y%m%d')}-{vin4}",
                "lien_holder": rng.choice(LENDERS) if rng.random() < 0.35 else "",
                "insurance_verified": 1 if rng.random() < 0.9 else 0,
                "emissions_test": "" if fuel == "electric" else json.dumps({
                    "last_test_date": iso(emis_last), "result": "pass",
                    "next_due": iso(emis_last.replace(year=emis_last.year + 2)),
                }),
                "address_on_file": u["address"],
            }
            next_id["vehicles"] += 1
            new["vehicles"].append(row)
            # yearly renewal payments since ownership (registration history)
            for yr in range(max(owned_since + 1, 2019), last_renew.year + 1):
                anniv = purchase.replace(year=yr)
                if anniv > TODAY:
                    continue
                late = rng.random() < 0.08
                amt = fee + (25.0 if late else 0.0)
                paid = anniv + datetime.timedelta(days=rng.randint(10, 40)) if late \
                    else anniv - datetime.timedelta(days=rng.randint(0, 20))
                add_payment(u, "vehicle_registration", amt, anniv, paid, reg_id=reg_id)

    # ---- permits + permit fee payments ----------------------------------
    for u in new["users"]:
        n_permits = rng.choices([0, 1, 2, 3, 4, 5], weights=[20, 25, 25, 15, 10, 5])[0]
        for _ in range(n_permits):
            ptype = rng.choices(list(PERMIT_KINDS), weights=[30, 20, 20, 15, 15])[0]
            (fee_lo, fee_hi), descs = PERMIT_KINDS[ptype]
            fee = round(rng.uniform(fee_lo, fee_hi) / 5) * 5.0 if fee_hi else 0.0
            submitted = rand_date(rng.randint(2019, 2026), 1, 12)
            while submitted > TODAY:
                submitted = rand_date(rng.randint(2019, 2025), 1, 12)
            pending = submitted > TODAY - datetime.timedelta(days=60) and rng.random() < 0.7
            if ptype == "Building Inquiry":
                status = "pending" if pending else "approved"
            elif pending:
                status = "pending"
            else:
                status = "active" if ptype == "Parking Permit" else \
                    rng.choices(["approved", "active"], weights=[70, 30])[0]
            approved = "" if status == "pending" else \
                iso(submitted + datetime.timedelta(days=rng.randint(3, 21)))
            valid_from = valid_to = ""
            if approved and ptype != "Building Inquiry":
                vf = datetime.date.fromisoformat(approved) + datetime.timedelta(days=rng.randint(1, 20))
                valid_from = iso(vf)
                valid_to = iso(vf.replace(year=vf.year + 1) - datetime.timedelta(days=1))
            fee_paid = 1 if (fee > 0 and status != "pending") else 0
            pid = f"PRM-{submitted.year}-{permit_seq.next(submitted.year, 100):04d}"
            row = {
                "id": next_id["permits"], "permit_id": pid,
                "agency_portal_permit_id": 0,
                "user_id": u["id"], "root_user_id": u["root_user_id"],
                "applicant_name": u["display_name"], "type": ptype,
                "address": u["address"], "status": status,
                "date_submitted": iso(submitted), "date_approved": approved,
                "valid_from": valid_from, "valid_to": valid_to,
                "fee": fee, "fee_paid": fee_paid,
                "reviewed_by": "Maria Santos" if approved else "",
                "description": rng.choice(descs).format(addr=u["address"], street=u["_street"]),
                "notes": "",
            }
            next_id["permits"] += 1
            new["permits"].append(row)
            if fee_paid:
                pay_type = "parking_permit" if ptype == "Parking Permit" else "permit_fee"
                pay_day = datetime.date.fromisoformat(approved)
                add_payment(u, pay_type, fee, pay_day, pay_day, permit_id=pid)

    # ---- report / insert -------------------------------------------------
    for u in new["users"]:  # strip helper keys
        for k in ("_is_biz", "_homeowner", "_street"):
            u.pop(k)

    total_new = sum(len(v) for v in new.values())
    for t in new:
        print(f"{t}: +{len(new[t])}")
    print(f"total new rows: {total_new}")

    # safety: never touch user 1
    assert all(r["user_id"] != 1 for t in ("tax_filings", "vehicles", "permits", "payments")
               for r in new[t])
    assert all(r["id"] != 1 for r in new["users"])
    per_user_pay = {}
    for r in new["payments"]:
        per_user_pay[r["user_id"]] = per_user_pay.get(r["user_id"], 0) + 1
    print(f"max payments for a single user: {max(per_user_pay.values())}")

    if dry:
        for t in new:
            for r in new[t][:2]:
                print(" ", json.dumps(r, default=str)[:200])
        return

    bdir = ROOT / "data" / "backups" / "tax-filing-dmv-permits-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps(
        {t: [r["id"] for r in rows] for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO {P}{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])

    # rebuild FTS indexes (external-content tables)
    for t in ("payments", "tax_filings"):
        fts = f"fts_{P}{t}"
        if db.execute("SELECT name FROM sqlite_master WHERE name=?", (fts,)).fetchone():
            db.execute(f"INSERT INTO [{fts}]([{fts}]) VALUES('rebuild')")
            print(f"rebuilt {fts}")

    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
