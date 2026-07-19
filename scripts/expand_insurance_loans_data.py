"""Expand insurance-loans base data (policies, loans, claims, payments).

The site ships with only a handful of rows (5 claims, 6 loans, 11 policies,
23 payments), which makes its filter/sort/extract macros trivial. This adds
deterministic (seeded) synthetic rows for every user while keeping referential
integrity: claims reference the user's policies, payments reference the user's
policies/loans, names/agents/lenders reuse the existing Lakeport/Cascadia
vocabulary.

Insert-only — existing rows are never touched. Inserted ids are recorded in
data/backups/insurance-loans-expansion-<date>/inserted_ids.json for rollback.

Usage: python scripts/expand_insurance_loans_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(42)

AGENTS = [("Patricia Dunn", "(555) 700-1100"), ("Mark Delaney", "(555) 700-1122"),
          ("Sofia Ramos", "(555) 700-1133"), ("Derek Chan", "(555) 700-1144")]
ADJUSTERS = [("Karen Whitmore", "(555) 710-2201"), ("Rebecca Solis", "(555) 710-2214"),
             ("Thomas Reid", "(555) 710-2227"), ("Nadia Okafor", "(555) 710-2233")]
UNDERWRITERS = ["Cascadia Mutual Insurance", "Pacific Northwest Commercial Underwriters",
                "Evergreen State Insurance Group"]
LENDERS = ["Cascadia Federal Credit Union", "Pacific Northwest Savings Bank",
           "Cascadia Commercial Bank", "Lakeport Community Bank"]
STREETS = ["Maple Ln", "Oak Ave", "Cedar Blvd", "Birch St", "Harbor Dr",
           "Lakeview Ter", "Pine Ridge Rd", "Willow Ct"]

CARS = [(2019, "Toyota", "RAV4", "XLE"), (2022, "Subaru", "Outback", "Premium"),
        (2017, "Ford", "F-150", "XLT"), (2021, "Mazda", "CX-5", "Touring"),
        (2015, "Honda", "Accord", "LX"), (2023, "Hyundai", "Ioniq 5", "SEL"),
        (2018, "Chevrolet", "Equinox", "LT"), (2020, "Kia", "Sorento", "EX")]

# type -> (subtype, deductible choices, monthly premium range)
POLICY_KINDS = {
    "auto": ("personal_auto", [250, 500, 1000], (95, 240)),
    "renters": ("residential_renters", [250, 500], (18, 42)),
    "homeowners": ("ho3_special_form", [1000, 2500], (85, 210)),
    "life": ("term_life_20yr", [0], (22, 78)),
    "umbrella": ("personal_umbrella_1m", [0], (28, 55)),
    "pet": ("accident_illness", [100, 250], (32, 64)),
    "motorcycle": ("standard_motorcycle", [250, 500], (24, 58)),
    "boat": ("inland_watercraft", [500, 1000], (35, 70)),
}

LOAN_KINDS = {
    "auto_loan": ("new_vehicle", (12000, 38000), (3.4, 7.9), [60, 72]),
    "personal_loan": ("unsecured_fixed", (3000, 18000), (7.5, 13.9), [36, 48, 60]),
    "student_loan": ("federal_direct_unsubsidized", (9000, 42000), (3.7, 6.5), [120]),
    "mortgage": ("conventional_30yr_fixed", (180000, 420000), (2.9, 6.8), [360]),
    "home_equity": ("heloc_variable", (25000, 80000), (6.5, 9.2), [120, 180]),
    "medical": ("provider_installment", (1200, 9500), (0.0, 5.9), [12, 24, 36]),
}

# policy type -> claim types it can produce
CLAIM_TYPES = {
    "auto": ["auto_collision", "auto_comprehensive", "auto_glass"],
    "renters": ["renters_property", "renters_liability"],
    "homeowners": ["homeowners_property", "homeowners_liability"],
    "motorcycle": ["auto_collision", "auto_comprehensive"],
    "boat": ["watercraft_damage"],
    "pet": ["pet_medical"],
    "commercial": ["commercial_liability", "commercial_property_damage"],
}

CLAIM_BLURBS = {
    "auto_collision": ("Rear-ended at a stop light on {street}; bumper and trunk damage.",
                       "Side-swiped while parked on {street}; door panel scraped."),
    "auto_comprehensive": ("Windshield cracked by road debris on Hwy 12.",
                           "Hail damage to hood and roof during the spring storm."),
    "auto_glass": ("Rock chip spread into a full crack across the windshield.",),
    "renters_property": ("Kitchen fire damaged cabinets and personal property.",
                         "Burst pipe in the unit above soaked electronics and furniture."),
    "renters_liability": ("Guest slipped on wet entryway tile; medical bills claimed.",),
    "homeowners_property": ("Wind storm tore shingles off the roof; attic water intrusion.",
                            "Water heater failure flooded the utility room."),
    "homeowners_liability": ("Neighbor's mail carrier tripped on the front step.",),
    "watercraft_damage": ("Hull scraped on submerged rocks near Lakeport marina.",),
    "pet_medical": ("Dog swallowed a sock; emergency endoscopy at Lakeport Vet.",
                    "Cat fractured leg falling from a bookshelf; surgery required."),
}

TODAY = datetime.date(2026, 7, 18)


def d(iso):
    return datetime.date.fromisoformat(iso)


def iso(day):
    return day.isoformat()


def months_ago(n):
    y, m = TODAY.year, TODAY.month - n
    while m <= 0:
        y, m = y - 1, m + 12
    return datetime.date(y, m, 1)


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row

    users = [dict(r) for r in db.execute("SELECT * FROM insurance_loans_users ORDER BY id")]
    next_id = {t: db.execute(f"SELECT COALESCE(MAX(id),0)+1 FROM insurance_loans_{t}").fetchone()[0]
               for t in ("policies", "loans", "claims", "payments")}
    pay_seq = 100  # ILPAY numbering continues well past the existing 23 rows

    new = {"policies": [], "loans": [], "claims": [], "payments": []}

    # ---- policies -------------------------------------------------------
    existing_pols = [dict(r) for r in db.execute("SELECT * FROM insurance_loans_policies")]
    pols_by_user = {}
    for u in users:
        pols_by_user[u["id"]] = [p for p in existing_pols if p["user_id"] == u["id"]]

    target_policies = {1: 8, 2: 6, 3: 7, 4: 6, 5: 6}
    for u in users:
        have_types = {p["type"] for p in pols_by_user[u["id"]]}
        pool = [t for t in POLICY_KINDS if t not in have_types]
        rng.shuffle(pool)
        for i in range(target_policies[u["id"]] - len(pols_by_user[u["id"]])):
            ptype = pool[i % len(pool)]
            subtype, deds, prem = POLICY_KINDS[ptype]
            status = rng.choices(["active", "expired", "lapsed", "pending_renewal"],
                                 weights=[55, 20, 10, 15])[0]
            start_year = rng.randint(2016, 2024)
            eff = datetime.date(start_year, rng.randint(1, 12), rng.randint(1, 28))
            monthly = round(rng.uniform(*prem), 0)
            agent = rng.choice(AGENTS)
            if status == "active":
                renewal = eff.replace(year=2026 if eff.month >= 8 else 2027)
                expiration = renewal.replace(year=renewal.year + 1)
            elif status == "pending_renewal":
                renewal = TODAY + datetime.timedelta(days=rng.randint(10, 45))
                expiration = renewal
            else:
                renewal = eff.replace(year=rng.randint(start_year + 1, 2025))
                expiration = renewal
            coverage = {
                "auto": {"liability": "100/300/100", "collision": True,
                         "comprehensive": True, "medical_payments": 5000},
                "renters": {"personal_property": rng.choice([20000, 30000, 45000]),
                            "liability": 100000, "loss_of_use": 10000},
                "homeowners": {"dwelling": rng.choice([320000, 410000, 520000]),
                               "personal_property": 120000, "liability": 300000},
                "life": {"death_benefit": rng.choice([250000, 500000, 750000]),
                         "term_years": 20},
                "umbrella": {"limit": 1000000, "underlying_auto": "250/500",
                             "underlying_home": 300000},
                "pet": {"annual_limit": rng.choice([5000, 10000]),
                        "reimbursement_pct": 80},
                "motorcycle": {"liability": "50/100/50", "collision": True,
                               "comprehensive": True},
                "boat": {"hull": rng.choice([18000, 32000]), "liability": 300000},
            }[ptype]
            vehicle = ""
            if ptype in ("auto", "motorcycle"):
                yr, make, model, trim = rng.choice(CARS)
                vehicle = json.dumps({"year": yr, "make": make, "model": model,
                                      "trim": trim,
                                      "vin_last_six": f"XX{rng.randint(1000, 9999)}"})
            prop_addr = u["address"] if ptype in ("renters", "homeowners") else ""
            row = {
                "id": next_id["policies"],
                "policy_number": f"POL-{ptype[:4].upper()}-{start_year}-{rng.randint(10000, 99999)}",
                "user_id": u["id"], "root_user_id": u["root_user_id"],
                "policyholder_name": u["display_name"], "type": ptype,
                "subtype": subtype, "status": status,
                "effective_date": iso(eff), "renewal_date": iso(renewal),
                "expiration_date": iso(expiration),
                "premium_monthly": monthly, "premium_annual": monthly * 12,
                "deductible": rng.choice(deds), "coverage": json.dumps(coverage),
                "vehicle": vehicle, "agent": agent[0], "agent_phone": agent[1],
                "underwriter": rng.choice(UNDERWRITERS), "notes": "",
                "property_address": prop_addr, "landlord_name": "",
            }
            next_id["policies"] += 1
            new["policies"].append(row)
            pols_by_user[u["id"]].append(row)

    # ---- loans ----------------------------------------------------------
    existing_loans = [dict(r) for r in db.execute("SELECT * FROM insurance_loans_loans")]
    loans_by_user = {u["id"]: [l for l in existing_loans if l["user_id"] == u["id"]]
                     for u in users}
    target_loans = {1: 7, 2: 4, 3: 5, 4: 5, 5: 4}
    for u in users:
        have = {l["type"] for l in loans_by_user[u["id"]]}
        pool = [t for t in LOAN_KINDS if t not in have]
        rng.shuffle(pool)
        for i in range(target_loans[u["id"]] - len(loans_by_user[u["id"]])):
            ltype = pool[i % len(pool)]
            subtype, amt_r, rate_r, terms = LOAN_KINDS[ltype]
            status = rng.choices(["active", "paid_off", "deferred"],
                                 weights=[60, 30, 10])[0]
            amount = round(rng.uniform(*amt_r), -2)
            rate = round(rng.uniform(*rate_r), 2)
            term = rng.choice(terms)
            orig = datetime.date(rng.randint(2015, 2025), rng.randint(1, 12), 1)
            monthly_rate = rate / 100 / 12
            if monthly_rate:
                pmt = amount * monthly_rate / (1 - (1 + monthly_rate) ** -term)
            else:
                pmt = amount / term
            pmt = round(pmt, 0)
            elapsed = min((TODAY.year - orig.year) * 12 + TODAY.month - orig.month, term)
            if status == "paid_off":
                made, balance = term, 0.0
                payoff = orig.replace(year=orig.year + term // 12)
            else:
                made = max(1, elapsed)
                balance = round(max(amount * (1 - made / term), pmt), 2)
                payoff = None
            lender = rng.choice(LENDERS)
            collateral = ""
            if ltype == "auto_loan":
                yr, make, model, trim = rng.choice(CARS)
                collateral = json.dumps({"type": "vehicle",
                                         "description": f"{yr} {make} {model} {trim}"})
            elif ltype in ("mortgage", "home_equity"):
                collateral = json.dumps({"type": "real_property",
                                         "description": u["address"]})
            row = {
                "id": next_id["loans"],
                "loan_number": f"LN-{ltype[:3].upper()}-{orig.year}-{rng.randint(10000, 99999)}",
                "user_id": u["id"], "root_user_id": u["root_user_id"],
                "borrower_name": u["display_name"], "type": ltype,
                "subtype": subtype, "status": status, "lender": lender,
                "servicer": lender, "original_amount": amount,
                "current_balance": balance, "interest_rate": rate,
                "rate_type": "variable" if ltype == "home_equity" else "fixed",
                "term_months": term, "monthly_payment": pmt,
                "origination_date": iso(orig),
                "first_payment_date": iso(orig + datetime.timedelta(days=31)),
                "maturity_date": iso(orig.replace(year=orig.year + term // 12)
                                     if term >= 12 else orig + datetime.timedelta(days=30 * term)),
                "payments_made": made, "payments_remaining": term - made,
                "next_payment_due": "" if status == "paid_off" else iso(TODAY.replace(day=1) + datetime.timedelta(days=45)),
                "autopay_enabled": rng.choice([0, 1]),
                "autopay_account_last_four": str(rng.randint(1000, 9999)),
                "collateral": collateral, "notes": "",
                "payoff_date": iso(payoff) if payoff else "",
            }
            next_id["loans"] += 1
            new["loans"].append(row)
            loans_by_user[u["id"]].append(row)

    # ---- claims ---------------------------------------------------------
    target_claims = {1: 14, 2: 8, 3: 9, 4: 9, 5: 8}
    have_claims = dict(db.execute(
        "SELECT user_id, COUNT(*) FROM insurance_loans_claims GROUP BY user_id"))
    for u in users:
        claimable = [p for p in pols_by_user[u["id"]] if p["type"] in CLAIM_TYPES]
        if not claimable:
            continue
        for _ in range(target_claims[u["id"]] - have_claims.get(u["id"], 0)):
            pol = rng.choice(claimable)
            ctype = rng.choice(CLAIM_TYPES[pol["type"]])
            status = rng.choices(["closed", "open", "in_review", "approved", "denied"],
                                 weights=[45, 15, 15, 15, 10])[0]
            incident = TODAY - datetime.timedelta(days=rng.randint(20, 1300))
            filed = incident + datetime.timedelta(days=rng.randint(0, 6))
            estimate = round(rng.uniform(400, 14000), -1)
            deductible = float(pol.get("deductible") or 0)
            resolved, payout, payout_date = "", 0.0, ""
            if status in ("closed", "approved"):
                resolved_d = filed + datetime.timedelta(days=rng.randint(20, 90))
                resolved = iso(resolved_d)
                payout = max(round(estimate - deductible, 2), 0.0)
                payout_date = iso(resolved_d + datetime.timedelta(days=7))
            elif status == "denied":
                resolved = iso(filed + datetime.timedelta(days=rng.randint(15, 60)))
            adjuster = rng.choice(ADJUSTERS)
            street = rng.choice(STREETS)
            blurb = rng.choice(CLAIM_BLURBS.get(ctype, ("Damage claim filed.",)))
            row = {
                "id": next_id["claims"],
                "claim_number": f"CLM-{filed.year}-{rng.randint(10000, 99999)}",
                "policy_number": pol["policy_number"],
                "user_id": u["id"], "root_user_id": u["root_user_id"],
                "claimant_name": u["display_name"], "type": ctype,
                "status": status, "date_of_incident": iso(incident),
                "date_filed": iso(filed), "date_resolved": resolved,
                "incident_location": f"{rng.randint(100, 4900)} {street}, Lakeport, WA",
                "description": blurb.format(street=street),
                "damage_estimate": estimate, "deductible_applied": deductible if payout else 0.0,
                "payout_amount": payout, "payout_date": payout_date,
                "at_fault": rng.choice(["no", "yes", "shared", ""]),
                "adjuster": adjuster[0], "adjuster_phone": adjuster[1],
                "police_report_number": (f"LPD-{filed.year}-{rng.randint(10000, 99999)}"
                                         if ctype == "auto_collision" else ""),
                "repair_shop": "", "repair_shop_address": "", "notes": "",
            }
            next_id["claims"] += 1
            new["claims"].append(row)

    # ---- payments: 18 months of premium + loan history ------------------
    for u in users:
        streams = []
        for p in pols_by_user[u["id"]]:
            if p["status"] in ("active", "pending_renewal"):
                streams.append(("insurance_premium", p["policy_number"], "",
                                float(p["premium_monthly"]),
                                f"{p['type'].capitalize()} insurance monthly premium"))
        for l in loans_by_user[u["id"]]:
            if l["status"] == "active":
                streams.append(("loan_payment", "", l["loan_number"],
                                float(l["monthly_payment"]),
                                f"{l['type'].replace('_', ' ').capitalize()} monthly payment"))
        for m in range(18, 0, -1):
            due = months_ago(m)
            for ptype, pol_no, loan_no, amount, note in streams:
                method = rng.choices(["autopay_ach", "check", "debit_card"],
                                     weights=[70, 15, 15])[0]
                paid = due + datetime.timedelta(days=rng.choice([0, 0, 0, 1, 3]))
                status = "completed"
                if m == 1 and rng.random() < 0.12:
                    status = "pending"
                elif rng.random() < 0.03:
                    status = "late"
                    paid = due + datetime.timedelta(days=rng.randint(8, 20))
                row = {
                    "id": next_id["payments"],
                    "payment_id": f"ILPAY-{due.year}-{pay_seq:04d}",
                    "user_id": u["id"], "root_user_id": u["root_user_id"],
                    "payer_name": u["display_name"], "type": ptype,
                    "related_policy": pol_no, "amount": amount,
                    "method": method,
                    "account_last_four": str(rng.randint(1000, 9999)),
                    "payment_date": iso(paid), "due_date": iso(due),
                    "status": status,
                    "confirmation_number": f"ILP-{paid.strftime('%Y%m%d')}-{rng.randint(10000, 99999)}",
                    "notes": note, "related_loan": loan_no,
                    "check_number": str(rng.randint(1000, 4000)) if method == "check" else "",
                }
                pay_seq += 1
                next_id["payments"] += 1
                new["payments"].append(row)

    for t in new:
        print(f"{t}: +{len(new[t])}")
    if dry:
        for t in new:
            for r in new[t][:2]:
                print(" ", json.dumps(r, default=str)[:160])
        return

    bdir = ROOT / "data" / "backups" / f"insurance-loans-expansion-{TODAY}"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps(
        {t: [r["id"] for r in rows] for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO insurance_loans_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
