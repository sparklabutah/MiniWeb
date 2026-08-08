#!/usr/bin/env python3
"""Flesh out the tax-filing-dmv-permits site for the DEFAULT login user
(Alex Rivera, user_id=1) — agents auto-login as user 1, who previously had only
2 filings / 2 permits / 1 vehicle / 4 payments, making the self-service views
look empty even though the DB has thousands of (other users') rows.

Adds multi-year income-tax history, a property-tax filing, a second vehicle,
two historical permits, and the matching payments — all for Alex Rivera.

Writes to the BASE tables (db._get_conn + INSERT OR REPLACE + commit), NOT the
per-session overlay. Deterministic + idempotent: fixed high ids (well above the
existing max), safe to re-run. Dates kept in the site's 2019-2026 range (project
rule: don't shift site dates). Does NOT touch build_db.py.

Run: PYTHONPATH=. ~/.conda/envs/miniweb/bin/python scripts/seed_tax_dmv_user1.py
"""
import json

import app.db as db

P = "tax_filing_dmv_permits_"
NAME = "Alex Rivera"
ADDR = "1247 Maple Ln, Lakeport, WA 98401"
U = dict(user_id=1, root_user_id=1)


def _upsert(table, rows):
    conn = db._get_conn()
    for r in rows:
        cols = list(r.keys())
        ph = ",".join("?" * len(cols))
        conn.execute(f"INSERT OR REPLACE INTO {P}{table} ({','.join(cols)}) VALUES ({ph})",
                     tuple(r[c] for c in cols))
    conn.commit()


# --- income-tax filing history 2019-2023 (existing has 2024, 2025) -------------
INCOME = [  # year, gross, taxable, owed, filing_date, due_date, conf_date
    (2019, 78000, 59280, 2632.0, "2020-04-11", "2020-04-15"),
    (2020, 81500, 61940, 2750.0, "2021-04-09", "2021-04-15"),
    (2021, 85000, 64600, 2868.0, "2022-04-12", "2022-04-15"),
    (2022, 88500, 67260, 2986.0, "2023-04-10", "2023-04-17"),
    (2023, 92000, 69920, 3104.0, "2024-04-13", "2024-04-15"),
]

filings, payments = [], []
for i, (yr, gross, taxable, owed, fdate, ddate) in enumerate(INCOME):
    fid = f"TAX-{yr}-INC-{80 + i:05d}"
    filings.append(dict(id=1700 + i, filing_id=fid, taxpayer_name=NAME, type="income_tax",
                        tax_year=yr, filing_date=fdate, due_date=ddate, status="filed",
                        gross_income=float(gross), taxable_income=float(taxable),
                        tax_owed=owed, tax_paid=owed, refund_amount=0.0,
                        filing_method="online", processed_by="Robert Hensley", **U))
    payments.append(dict(id=2900 + i, payment_id=f"TDPAY-{yr+1}-0090", payer_name=NAME,
                         type="income_tax", related_filing_id=fid, amount=owed, method="ach_debit",
                         account_last_four="4821", payment_date=fdate, due_date=ddate,
                         status="completed", confirmation_number=f"CFM-{fdate.replace('-','')}-{40000+i}",
                         processed_by="Robert Hensley", **U))

# --- a property-tax filing (homeowner) ----------------------------------------
prop_owed = round(412000 * 0.0092, 2)
filings.append(dict(id=1710, filing_id="TAX-2024-PROP-00061", taxpayer_name=NAME,
                    type="property_tax", tax_year=2024, filing_date="2025-04-20",
                    due_date="2025-04-30", status="filed", tax_owed=prop_owed, tax_paid=prop_owed,
                    filing_method="online", processed_by="Denise Fuller",
                    property_address=ADDR, parcel_number="LKP-04417-0083",
                    assessed_value=412000.0, tax_rate=0.0092, **U))
payments.append(dict(id=2910, payment_id="TDPAY-2025-0091", payer_name=NAME, type="property_tax",
                     related_filing_id="TAX-2024-PROP-00061", amount=prop_owed, method="ach_debit",
                     account_last_four="4821", payment_date="2025-04-20", due_date="2025-04-30",
                     status="completed", confirmation_number="CFM-20250420-40910",
                     processed_by="Denise Fuller", **U))

# --- a second vehicle (active registration) -----------------------------------
veh = {"year": 2018, "make": "Toyota", "model": "RAV4", "trim": "XLE",
       "color": "Magnetic Gray Metallic", "body_type": "suv",
       "vin": "XXXXXXXXXXXX2288", "engine": "2.5L 4-Cylinder", "fuel_type": "gasoline"}
emis = {"last_test_date": "2025-05-20", "result": "pass", "next_due": "2027-05-20"}
vehicles = [dict(id=300, registration_id="VEH-2024-00517", owner_name=NAME, vehicle=json.dumps(veh),
                 plate_number="HRT-2288", plate_state="WA", registration_date="2025-06-01",
                 expiration_date="2026-05-31", renewal_status="active", renewal_due_date="2026-05-31",
                 renewal_fee=85.0, late_penalty=0.0, title_number="WA-TTL-20180622-2288",
                 lien_holder="", insurance_verified=1, emissions_test=json.dumps(emis),
                 address_on_file=ADDR, **U)]
payments.append(dict(id=2911, payment_id="TDPAY-2025-0092", payer_name=NAME, type="vehicle_registration",
                     amount=85.0, method="credit_card", payment_date="2025-06-01", due_date="2025-06-01",
                     status="completed", confirmation_number="CFM-20250601-40911",
                     notes="Online registration renewal", related_registration_id="VEH-2024-00517",
                     card_last_four="9217", **U))

# --- two historical permits ----------------------------------------------------
permits = [
    dict(id=300, permit_id="PRM-2023-0042", agency_portal_permit_id=42, applicant_name=NAME,
         type="Renovation", address=ADDR, status="expired", date_submitted="2023-06-10",
         date_approved="2023-06-25", valid_from="2023-07-01", valid_to="2024-06-30", fee=220.0,
         fee_paid=1, reviewed_by="James Wong",
         description="Kitchen renovation: cabinetry, countertops, and electrical for 1247 Maple Ln.",
         notes="Final inspection passed 2024-02-14.", **U),
    dict(id=301, permit_id="PRM-2024-0031", agency_portal_permit_id=31, applicant_name=NAME,
         type="Parking Permit", address=ADDR, status="expired", date_submitted="2024-04-05",
         date_approved="2024-04-10", valid_from="2024-05-01", valid_to="2025-04-30", fee=75.0,
         fee_paid=1, reviewed_by="Maria Santos",
         description="Residential street parking permit (prior year) for the Maple Ln corridor.", **U),
]
payments += [
    dict(id=2912, payment_id="TDPAY-2023-0093", payer_name=NAME, type="permit_fee", amount=220.0,
         method="credit_card", payment_date="2023-06-25", due_date="2023-06-25", status="completed",
         confirmation_number="CFM-20230625-40912", notes="Renovation permit fee",
         related_permit_id="PRM-2023-0042", card_last_four="9217", **U),
    dict(id=2913, payment_id="TDPAY-2024-0094", payer_name=NAME, type="parking_permit", amount=75.0,
         method="credit_card", payment_date="2024-04-10", due_date="2024-04-10", status="completed",
         confirmation_number="CFM-20240410-40913", notes="Residential parking permit fee",
         related_permit_id="PRM-2024-0031", card_last_four="9217", **U),
]


def main():
    n = lambda t: db.execute(f"SELECT COUNT(*) FROM {P}{t} WHERE user_id=1", (), fetch="val")
    before = {t: n(t) for t in ["tax_filings", "permits", "vehicles", "payments"]}
    _upsert("tax_filings", filings)
    _upsert("permits", permits)
    _upsert("vehicles", vehicles)
    _upsert("payments", payments)
    for t in ["tax_filings", "permits", "vehicles", "payments"]:
        print(f"  user-1 {t:12s}: {before[t]} -> {n(t)}")


if __name__ == "__main__":
    main()
