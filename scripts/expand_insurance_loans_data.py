#!/usr/bin/env python3
"""Grow the insurance-loans tabs so navigation is actually required.

Each tab for the auto-login user (id=1 / root_user_id=1) had only a handful of
rows — 8 policies, 14 claims, 7 loans — so an agent could eyeball everything
without ever filtering, sorting, or searching. But this site's macros are
overwhelmingly table operations: filter_by_dropdown, filter_by_date_range,
search_by_query, sort_by_ranking, extract_by_extremum, compare_from_table,
compute_from_table, select_by_extremum. Those are trivial at 5-14 rows.

This adds rows (insert-only) for user 1 with deliberately VARIED attributes —
spread across types, statuses, premiums, coverage amounts, balances, rates and
dates over several years — so finding a specific record requires a filter/sort/
search and extremum/compute questions have a non-obvious answer. Matching
premium/loan payment history is added so drill-downs stay consistent.

Deterministic + idempotent: every inserted row has a fixed business key
(policy_number / claim_number / loan_number / payment_id); a row whose key
already exists is skipped, so re-running after a DB rebuild is safe.

Writes to the base insurance_loans_* tables (visible to every session).

Run: ~/.conda/envs/miniweb/bin/python scripts/expand_insurance_loans_data.py
"""
import json
import pathlib
import sqlite3
import sys
import zlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app import create_app
import app.db as adb

create_app()
DB = adb._DB_PATH

USER_ID = 1
ROOT_USER_ID = 1
HOLDER = "Alex Rivera"
UNDERWRITERS = ["Cascadia Mutual Insurance", "Evergreen General", "Pacific Crest Insurance Co.",
                "Rainier Casualty", "Northwest Indemnity Group"]
AGENTS = [("Patricia Dunn", "(555) 700-1100"), ("Marcus Webb", "(555) 700-2214"),
          ("SofiaNguyen", "(555) 700-3390"), ("Derek Paulson", "(555) 700-4471"),
          ("Grace Okafor", "(555) 700-5582")]
ADJUSTERS = [("Thomas Reid", "(555) 710-2227"), ("Lena Ford", "(555) 710-3318"),
             ("Omar Haddad", "(555) 710-4409"), ("Nina Castro", "(555) 710-5590"),
             ("Wes Turner", "(555) 710-6681")]
LENDERS = ["Cascadia Federal Credit Union", "Lakeport Community Bank", "Summit Mortgage Co.",
           "Pacific Auto Finance", "Evergreen Student Servicing", "Harbor Personal Lending"]


def crc(*parts):
    return zlib.crc32("|".join(str(p) for p in parts).encode())


def pick(pool, *seed):
    return pool[crc(*seed) % len(pool)]


# --- POLICIES ---------------------------------------------------------------
# (label, type, subtype, base_monthly, coverage_builder). A spread of types,
# statuses and premiums so type/status filters and premium extremum matter.
def _cov_auto(i):
    liab = pick(["100/300/100", "50/100/50", "250/500/250", "100/300/50"], "liab", i)
    return {"liability": liab, "collision": True, "comprehensive": bool(i % 3),
            "uninsured_motorist": True, "medical_payments": pick([2000, 5000, 10000], "med", i),
            "rental_reimbursement": bool(i % 2), "roadside_assistance": bool(i % 2)}


def _cov_home(i):
    dwell = 300000 + (crc("dw", i) % 40) * 12500
    return {"dwelling": dwell, "other_structures": int(dwell * 0.1),
            "personal_property": int(dwell * 0.5), "loss_of_use": int(dwell * 0.2),
            "liability": pick([300000, 500000, 100000], "hl", i), "medical_payments": 5000,
            "wind_hail": True, "water_backup": bool(i % 2)}


def _cov_renters(i):
    pp = 15000 + (crc("pp", i) % 8) * 5000
    return {"personal_property": pp, "liability": pick([100000, 300000], "rl", i),
            "loss_of_use": int(pp * 0.4), "medical_payments": 1000}


def _cov_life(i):
    db = pick([100000, 250000, 500000, 1000000], "db", i)
    return {"death_benefit": db, "term_years": pick([10, 20, 30], "ty", i),
            "beneficiaries": [{"name": "Elena Vasquez", "relationship": "spouse", "percentage": 100}]}


def _cov_umbrella(i):
    return {"limit": pick([1000000, 2000000, 5000000], "ul", i),
            "underlying_auto": "250/500", "underlying_home": 300000}


def _cov_pet(i):
    return {"annual_limit": pick([5000, 10000, 15000], "al", i),
            "reimbursement_pct": pick([70, 80, 90], "rp", i), "wellness_addon": bool(i % 2)}


def _cov_boat(i):
    return {"hull": 20000 + (crc("hu", i) % 20) * 2500, "liability": pick([100000, 300000], "bl", i),
            "trailer": bool(i % 2), "towing": True}


def _cov_condo(i):
    return {"unit_improvements": 60000 + (crc("ui", i) % 10) * 5000,
            "personal_property": 40000, "liability": 300000, "loss_assessment": 25000}


def _cov_flood(i):
    return {"building": 150000 + (crc("fb", i) % 20) * 10000, "contents": 60000,
            "zone": pick(["AE", "X", "VE"], "fz", i)}


def _cov_jewelry(i):
    return {"scheduled_items": pick([3, 5, 8], "ji", i),
            "total_value": 15000 + (crc("jv", i) % 12) * 2500, "worldwide": True}


POLICY_SPECS = [
    ("second family auto", "auto", "personal_auto", 128, "active", _cov_auto),
    ("teen driver auto", "auto", "personal_auto", 214, "active", _cov_auto),
    ("classic car", "auto", "collector_auto", 62, "active", _cov_auto),
    ("primary home", "homeowners", "ho3", 176, "active", _cov_home),
    ("rental property", "homeowners", "dwelling_fire", 143, "active", _cov_home),
    ("lake cabin", "homeowners", "seasonal", 98, "expired", _cov_home),
    ("downtown condo", "condo", "ho6", 71, "active", _cov_condo),
    ("apartment renters", "renters", "ho4", 22, "active", _cov_renters),
    ("term life 20yr", "life", "term", 48, "active", _cov_life),
    ("whole life", "life", "whole", 132, "active", _cov_life),
    ("personal umbrella", "umbrella", "personal", 37, "active", _cov_umbrella),
    ("dog health", "pet", "accident_illness", 54, "active", _cov_pet),
    ("second pet", "pet", "accident_only", 28, "lapsed", _cov_pet),
    ("sailboat", "boat", "watercraft", 44, "active", _cov_boat),
    ("flood policy", "flood", "nfip", 39, "active", _cov_flood),
    ("jewelry floater", "valuables", "scheduled", 19, "active", _cov_jewelry),
    ("old renters (moved)", "renters", "ho4", 18, "expired", _cov_renters),
    ("prior auto (sold car)", "auto", "personal_auto", 116, "expired", _cov_auto),
    ("motorcycle spring-fall", "motorcycle", "cruiser", 41, "pending_renewal", _cov_auto),
    ("umbrella (upgraded)", "umbrella", "personal", 29, "expired", _cov_umbrella),
]


def build_policies():
    rows = []
    for i, (label, typ, subtype, base, status, cov) in enumerate(POLICY_SPECS):
        eff_year = 2017 + (crc("ey", label) % 8)
        eff = f"{eff_year}-{1 + crc('em', label) % 12:02d}-{1 + crc('ed', label) % 27:02d}"
        renew = f"{eff_year + 1}-{eff[5:]}"
        expv = f"{eff_year + (1 if status in ('expired', 'lapsed') else 6)}-{eff[5:]}"
        monthly = float(base + crc("pm", label) % 25)
        pref = {"auto": "AUTO", "homeowners": "HOME", "renters": "RENT", "life": "LIFE",
                "umbrella": "UMBR", "pet": "PET", "boat": "BOAT", "condo": "CONDO",
                "flood": "FLOOD", "valuables": "VAL", "motorcycle": "MOTO"}.get(typ, "GEN")
        polnum = f"POL-{pref}-{eff_year}-{70000 + i * 137 + crc('pn', label) % 90}"
        veh = ""
        if typ in ("auto", "motorcycle"):
            veh = json.dumps({"year": 2015 + crc("vy", label) % 10,
                              "make": pick(["Honda", "Toyota", "Ford", "Mazda", "Subaru", "BMW"], "mk", label),
                              "model": pick(["Civic", "Camry", "F-150", "CX-5", "Outback", "3-Series"], "mo", label),
                              "trim": pick(["EX", "LE", "XLT", "Touring", "Premium"], "tr", label),
                              "vin_last_six": f"XX{1000 + crc('vin', label) % 8999}"})
        rows.append((
            polnum, USER_ID, ROOT_USER_ID, HOLDER, typ, subtype, status, eff, renew, expv,
            monthly, round(monthly * 12, 2), pick([250, 500, 1000, 2500], "ded", label),
            json.dumps(cov(i)), veh, pick(AGENTS, "ag", label)[0], pick(AGENTS, "ag", label)[1],
            pick(UNDERWRITERS, "uw", label),
            pick(["Bundled for multi-policy discount.", "Paperless billing enrolled.",
                  "Loyalty discount applied.", "", "Renewed automatically each term."], "note", label),
            "", ""))
    return rows


POLICY_COLS = ["policy_number", "user_id", "root_user_id", "policyholder_name", "type", "subtype",
               "status", "effective_date", "renewal_date", "expiration_date", "premium_monthly",
               "premium_annual", "deductible", "coverage", "vehicle", "agent", "agent_phone",
               "underwriter", "notes", "property_address", "landlord_name"]


# --- CLAIMS -----------------------------------------------------------------
CLAIM_TYPES = ["auto_collision", "auto_comprehensive", "auto_glass", "homeowners_property",
               "homeowners_liability", "renters_property", "renters_liability", "pet_medical",
               "watercraft_damage", "flood_damage", "theft"]
CLAIM_STATUSES = ["open", "in_review", "approved", "closed", "denied"]
DESCRIPTIONS = {
    "auto_collision": "Rear-ended at a stop light; bumper and tailgate damage.",
    "auto_comprehensive": "Hail damage to hood and roof during a spring storm.",
    "auto_glass": "Windshield cracked by road debris on the highway.",
    "homeowners_property": "Burst pipe under the kitchen sink flooded the cabinets.",
    "homeowners_liability": "Guest slipped on the front steps and filed a claim.",
    "renters_property": "Laptop and TV stolen during an apartment break-in.",
    "renters_liability": "Accidental kitchen fire caused smoke damage to the unit.",
    "pet_medical": "Emergency surgery after the dog swallowed a foreign object.",
    "watercraft_damage": "Hull scraped a submerged rock at the marina.",
    "flood_damage": "Storm surge flooded the basement and ruined the water heater.",
    "theft": "Bicycle and tools stolen from the detached garage.",
}
SHOPS = [("Lakeport Collision Center", "410 Industrial Way, Lakeport, WA"),
         ("Pine Street Auto Body", "88 Pine St, Lakeport, WA"),
         ("Harbor Glass & Repair", "215 Marina Dr, Lakeport, WA")]


def build_claims(policy_numbers):
    rows = []
    for i in range(38):
        typ = pick(CLAIM_TYPES, "ct", i)
        status = CLAIM_STATUSES[i % len(CLAIM_STATUSES)]
        year = 2019 + (i % 7)
        month = 1 + crc("cm", i) % 12
        day = 1 + crc("cd", i) % 27
        inc = f"{year}-{month:02d}-{day:02d}"
        filed = f"{year}-{month:02d}-{min(day + 2, 28):02d}"
        est = float(300 + crc("est", i) % 47000)
        ded = float(pick([0, 250, 500, 1000], "cded", i))
        resolved = ""
        payout = 0.0
        payout_date = ""
        if status in ("approved", "closed"):
            rm = min(month + 1, 12)
            resolved = f"{year}-{rm:02d}-{min(day + 5, 28):02d}"
            payout = round(max(est - ded, 0) * pick([0.6, 0.8, 1.0], "pf", i), 2)
            payout_date = f"{year}-{rm:02d}-{min(day + 9, 28):02d}"
        elif status == "denied":
            resolved = f"{year}-{month:02d}-{min(day + 12, 28):02d}"
        adj = pick(ADJUSTERS, "adj", i)
        is_vehicle = typ.startswith("auto") or typ == "watercraft_damage"
        shop = pick(SHOPS, "shop", i) if is_vehicle and status in ("approved", "closed") else ("", "")
        police = f"LPD-{year}-{10000 + crc('pol', i) % 89999}" if typ in ("theft", "auto_collision") else ""
        at_fault = pick(["yes", "no", "partial", ""], "af", i) if typ.startswith("auto") else ""
        notes_pool = ["Adjuster inspection completed.", "Awaiting repair estimate from shop.",
                      "Documentation submitted; under review.", "Settled and closed.",
                      "Claimant provided photos and receipts.", ""]
        rows.append((
            f"CLM-{year}-{20000 + i * 173 + crc('cn', i) % 90}",
            pick(policy_numbers, "cp", i), USER_ID, ROOT_USER_ID, HOLDER, typ, status,
            inc, filed, resolved,
            pick(["722 Pine Ridge Rd, Lakeport, WA", "410 Marina Dr, Lakeport, WA",
                  "1247 Maple Ln, Lakeport, WA", "Hwy 12 near Lakeport, WA"], "loc", i),
            DESCRIPTIONS.get(typ, "Claim under review."), est, ded, payout, payout_date,
            at_fault, adj[0], adj[1], police, shop[0], shop[1],
            pick(notes_pool, "cnote", i) if status != "open" else ""))
    return rows


CLAIM_COLS = ["claim_number", "policy_number", "user_id", "root_user_id", "claimant_name", "type",
              "status", "date_of_incident", "date_filed", "date_resolved", "incident_location",
              "description", "damage_estimate", "deductible_applied", "payout_amount", "payout_date",
              "at_fault", "adjuster", "adjuster_phone", "police_report_number", "repair_shop",
              "repair_shop_address", "notes"]


# --- LOANS ------------------------------------------------------------------
LOAN_SPECS = [
    ("second auto loan", "auto_loan", "new_vehicle", 28000, 4.9, 60, "active"),
    ("rv loan", "personal_loan", "recreational", 41000, 7.2, 84, "active"),
    ("home improvement", "home_equity", "heloc", 35000, 6.1, 120, "active"),
    ("solar panel financing", "personal_loan", "green", 22000, 5.4, 96, "active"),
    ("boat loan", "personal_loan", "marine", 18500, 8.3, 72, "active"),
    ("business line", "commercial_mortgage", "sba", 210000, 6.8, 240, "active"),
    ("grad school loan", "student_loan", "federal_direct", 45000, 5.05, 120, "deferred"),
    ("dental financing", "medical", "care_credit", 6800, 11.9, 36, "active"),
    ("credit card consolidation", "personal_loan", "debt_consolidation", 15000, 9.4, 48, "active"),
    ("furniture financing", "personal_loan", "retail", 4200, 13.9, 24, "paid_off"),
    ("first car (paid off)", "auto_loan", "used_vehicle", 16000, 6.5, 60, "paid_off"),
    ("old personal loan", "personal_loan", "unsecured", 9000, 10.2, 36, "paid_off"),
    ("second mortgage", "mortgage", "fixed_30", 185000, 5.75, 360, "active"),
]


def build_loans():
    rows = []
    for i, (label, typ, subtype, orig, rate, term, status) in enumerate(LOAN_SPECS):
        year = 2016 + (crc("ly", label) % 9)
        orig_date = f"{year}-{1 + crc('lm', label) % 12:02d}-01"
        first_pay = f"{year}-{1 + crc('lm', label) % 12:02d}-15" if year else ""
        mat_year = year + term // 12
        maturity = f"{mat_year}-{orig_date[5:]}"
        # monthly payment (simple amortization)
        r = rate / 100 / 12
        pay = round(orig * r / (1 - (1 + r) ** (-term)), 2) if r else round(orig / term, 2)
        if status == "paid_off":
            made, remaining, bal, payoff = term, 0, 0.0, f"{mat_year - 1}-06-01"
        elif status == "deferred":
            made, remaining, bal, payoff = 0, term, float(orig), ""
        else:
            made = 6 + crc("lmade", label) % (term - 8)
            remaining = term - made
            bal = round(orig * (remaining / term), 2)
            payoff = ""
        lender = pick(LENDERS, "ld", label)
        lnpref = {"auto_loan": "AUTO", "personal_loan": "PER", "home_equity": "HOM",
                  "commercial_mortgage": "COM", "student_loan": "STU", "medical": "MED",
                  "mortgage": "MOR"}.get(typ, "LN")
        rows.append((
            f"LN-{lnpref}-{year}-{30000 + i * 211 + crc('ln', label) % 90}",
            USER_ID, ROOT_USER_ID, HOLDER, typ, subtype, status, lender, lender,
            float(orig), bal, rate, "fixed", term, pay, orig_date, first_pay, maturity,
            made, remaining, f"2026-{7 + i % 6:02d}-01" if status == "active" else "",
            1 if crc("ap", label) % 2 else 0, f"{crc('a4', label) % 9000 + 1000}",
            pick(["Home", "Vehicle title", "None", "Business assets", ""], "col", label),
            pick(["Autopay discount applied.", "Refinanced last year.", "", "Fixed-rate term."], "lnote", label),
            payoff))
    return rows


LOAN_COLS = ["loan_number", "user_id", "root_user_id", "borrower_name", "type", "subtype", "status",
             "lender", "servicer", "original_amount", "current_balance", "interest_rate", "rate_type",
             "term_months", "monthly_payment", "origination_date", "first_payment_date",
             "maturity_date", "payments_made", "payments_remaining", "next_payment_due",
             "autopay_enabled", "autopay_account_last_four", "collateral", "notes", "payoff_date"]


# --- PAYMENTS (history for the new policies + loans) ------------------------
PAY_COLS = ["payment_id", "user_id", "root_user_id", "payer_name", "type", "related_policy", "amount",
            "method", "account_last_four", "payment_date", "due_date", "status", "confirmation_number",
            "notes", "related_loan", "check_number"]


def build_payments(policies, loans):
    rows = []
    seq = 4000  # continues past existing ILPAY numbering
    methods = ["autopay_ach", "check", "debit_card"]
    for pol in policies:
        polnum, monthly = pol[0], pol[10]
        if pol[6] not in ("active", "pending_renewal"):
            continue
        for m in range(6):  # last 6 months of premium
            month = 6 - m
            method = pick(methods, "pmeth", polnum, m)
            status = pick(["completed", "completed", "completed", "late", "pending"], "pst", polnum, m)
            seq += 1
            rows.append((
                f"ILPAY-2026-{seq:04d}", USER_ID, ROOT_USER_ID, HOLDER, "insurance_premium", polnum,
                round(monthly, 2), method, "4821", f"2026-{month:02d}-01", f"2026-{month:02d}-01",
                status, f"ILP-2026{month:02d}01-{seq}", "Monthly premium", "",
                f"{crc('ck', polnum, m) % 9000 + 1000}" if method == "check" else ""))
    for ln in loans:
        lnnum, pay, status_l = ln[0], ln[14], ln[6]
        if status_l != "active":
            continue
        for m in range(6):
            month = 6 - m
            method = pick(methods, "lmeth", lnnum, m)
            status = pick(["completed", "completed", "completed", "late"], "lst", lnnum, m)
            seq += 1
            rows.append((
                f"ILPAY-2026-{seq:04d}", USER_ID, ROOT_USER_ID, HOLDER, "loan_payment", "",
                round(pay, 2), method, "4821", f"2026-{month:02d}-15", f"2026-{month:02d}-15",
                status, f"ILP-2026{month:02d}15-{seq}", "Monthly loan payment", lnnum,
                f"{crc('ck', lnnum, m) % 9000 + 1000}" if method == "check" else ""))
    return rows


def insert_missing(cur, table, cols, rows, keycol, keyidx):
    existing = {r[0] for r in cur.execute(f"SELECT {keycol} FROM {table}")}
    maxid = (cur.execute(f"SELECT MAX(id) FROM {table}").fetchone()[0] or 0)
    placeholders = ",".join("?" * (len(cols) + 1))
    added = 0
    for row in rows:
        if row[keyidx] in existing:
            continue
        maxid += 1
        cur.execute(f"INSERT INTO {table} (id,{','.join(cols)}) VALUES ({placeholders})",
                    (maxid, *row))
        added += 1
    return added


def main():
    conn = sqlite3.connect(str(DB), timeout=60)
    cur = conn.cursor()

    policies = build_policies()
    policy_numbers = [p[0] for p in policies]
    # include existing user-1 policy numbers as claim targets too
    existing_pols = [r[0] for r in cur.execute(
        "SELECT policy_number FROM insurance_loans_policies WHERE root_user_id=1")]
    claims = build_claims(policy_numbers + existing_pols)
    loans = build_loans()
    payments = build_payments(policies, loans)

    n_p = insert_missing(cur, "insurance_loans_policies", POLICY_COLS, policies, "policy_number", 0)
    n_c = insert_missing(cur, "insurance_loans_claims", CLAIM_COLS, claims, "claim_number", 0)
    n_l = insert_missing(cur, "insurance_loans_loans", LOAN_COLS, loans, "loan_number", 0)
    n_pay = insert_missing(cur, "insurance_loans_payments", PAY_COLS, payments, "payment_id", 0)
    conn.commit()

    # rebuild FTS indexes if present so search picks up new rows
    for tbl in ("insurance_loans_policies", "insurance_loans_claims", "insurance_loans_loans"):
        fts = "fts_" + tbl
        try:
            cur.execute(f"INSERT INTO {fts}({fts}) VALUES('rebuild')")
            conn.commit()
        except sqlite3.Error:
            pass

    def cnt(t):
        return cur.execute(f"SELECT COUNT(*) FROM {t} WHERE root_user_id=1").fetchone()[0]
    print(f"policies +{n_p}  -> user1 total {cnt('insurance_loans_policies')}")
    print(f"claims   +{n_c}  -> user1 total {cnt('insurance_loans_claims')}")
    print(f"loans    +{n_l}  -> user1 total {cnt('insurance_loans_loans')}")
    print(f"payments +{n_pay} -> user1 total {cnt('insurance_loans_payments')}")
    conn.close()


if __name__ == "__main__":
    main()
