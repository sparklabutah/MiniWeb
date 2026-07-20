"""Expand health-portals (Lakeport Medical Center Patient Portal) base data.

The portal ships with 4 users / 12 appointments / 10 records / 15 messages /
10 bills / 5 prescriptions — a two-patient demo. Adds a deterministic (seeded)
synthetic patient population: ~52 new patients and 12 new providers, each
patient with a multi-year visit history (appointments -> billing line items ->
medical records), message threads with their care team, and prescriptions.

Hard constraints honored:
  * INSERT-ONLY: no existing row is updated or deleted.
  * ZERO new rows for patients 1 (Alex Rivera) and 2 (James Rivera) — their
    appointment lists, messages, records, bills and prescriptions are exactly
    as before (annotation tasks depend on them: annual-appointment reasoning
    and the cancel-appointment flow).
  * All new appointments belong to new patients; bulk is in the past. The few
    'scheduled' ones are future-dated and also belong to new patients only.
  * Default pages render per-patient (<=60 rows per patient), well under 500.

Insert-only; inserted ids recorded under
data/backups/health-portals-expansion-2026-07-20/inserted_ids.json.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_health_portals_data.py [--dry-run]
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
LOCATION = "Lakeport Medical Center, 800 Health Plaza, Lakeport, WA 98401"
PHARMACY = "Lakeport Pharmacy, 310 Main St, Lakeport, WA 98401"

# ---------------------------------------------------------------------------
# New providers (ids assigned at runtime)
# ---------------------------------------------------------------------------
NEW_PROVIDERS = [
    # first, last, display, type, specialty, department, gender, reg year
    ("Sarah", "Whitfield", "Dr. Sarah Whitfield", "Primary Care Physician",
     "Family Medicine", "Primary Care", "female", 2011),
    ("Marcus", "Bell", "Dr. Marcus Bell", "Primary Care Physician",
     "Internal Medicine", "Primary Care", "male", 2016),
    ("Priya", "Natarajan", "Dr. Priya Natarajan", "Cardiologist",
     "Cardiology", "Cardiology", "female", 2014),
    ("Owen", "Gallagher", "Dr. Owen Gallagher", "Orthopedic Surgeon",
     "Orthopedic Surgery", "Orthopedics", "male", 2012),
    ("Elena", "Vasquez", "Dr. Elena Vasquez", "Dermatologist",
     "Medical Dermatology", "Dermatology", "female", 2017),
    ("Thomas", "Liu", "Dr. Thomas Liu", "Endocrinologist",
     "Diabetes & Metabolism", "Endocrinology", "male", 2015),
    ("Rachel", "Kim", "Dr. Rachel Kim", "OB/GYN",
     "Obstetrics & Gynecology", "Women's Health", "female", 2013),
    ("Samuel", "Adeyemi", "Dr. Samuel Adeyemi", "Gastroenterologist",
     "Gastroenterology", "Gastroenterology", "male", 2018),
    ("Hannah", "Pierce", "Dr. Hannah Pierce", "Psychiatrist",
     "Adult Psychiatry", "Behavioral Health", "female", 2019),
    ("Maria", "Delgado", "Maria Delgado, DPT", "Physical Therapist",
     "Sports Rehabilitation", "Physical Therapy", "female", 2020),
    ("Kevin", "O'Rourke", "Dr. Kevin O'Rourke", "Pulmonologist",
     "Pulmonary Medicine", "Pulmonology", "male", 2014),
    ("Angela", "Foster", "Dr. Angela Foster", "Pediatrician",
     "General Pediatrics", "Pediatrics", "female", 2016),
]

# ---------------------------------------------------------------------------
# New patients
# ---------------------------------------------------------------------------
PATIENT_NAMES = [
    ("Maya", "Thompson", "female"), ("Jordan", "Ellis", "male"),
    ("Sofia", "Marino", "female"), ("Derek", "Hutchinson", "male"),
    ("Priyanka", "Shah", "female"), ("Caleb", "Norwood", "male"),
    ("Ingrid", "Halvorsen", "female"), ("Marcus", "Reed", "male"),
    ("Beatriz", "Fonseca", "female"), ("Trevor", "Lindqvist", "male"),
    ("Naomi", "Castellanos", "female"), ("Felix", "Braun", "male"),
    ("Aisha", "Mbeki", "female"), ("Grant", "Holloway", "male"),
    ("Lucia", "Herrera", "female"), ("Simon", "Turner", "male"),
    ("Yuki", "Tanaka", "female"), ("Brendan", "Walsh", "male"),
    ("Carmen", "Delacruz", "female"), ("Victor", "Osei", "male"),
    ("Heidi", "Zimmermann", "female"), ("Russell", "Pemberton", "male"),
    ("Anika", "Sorensen", "female"), ("Dmitri", "Volkov", "male"),
    ("Paloma", "Reyes", "female"), ("Curtis", "Blackwood", "male"),
    ("Freya", "Dahl", "female"), ("Andre", "Beaumont", "male"),
    ("Rosa", "Villanueva", "female"), ("Wesley", "Chambers", "male"),
    ("Tamara", "Novak", "female"), ("Idris", "Kamara", "male"),
    ("Greta", "Lindholm", "female"), ("Spencer", "McAllister", "male"),
    ("Bianca", "Ferretti", "female"), ("Hugo", "Sandoval", "male"),
    ("Leila", "Farhadi", "female"), ("Clayton", "Briggs", "male"),
    ("Marisol", "Quintero", "female"), ("Everett", "Doyle", "male"),
    ("Sana", "Qureshi", "female"), ("Roland", "Fitzgerald", "male"),
    ("Petra", "Kovacs", "female"), ("Darnell", "Whitaker", "male"),
    ("Ines", "Almeida", "female"), ("Gordon", "Prescott", "male"),
    ("Talia", "Rosenberg", "female"), ("Mateo", "Iglesias", "male"),
    ("Willa", "Hargrove", "female"), ("Quentin", "Ashford", "male"),
    ("Daphne", "Merrick", "female"), ("Silas", "Crowley", "male"),
]

STREETS = ["Maple Ln", "Oak Ave", "Harbor Dr", "Main St", "Cedar Ct",
           "Birch St", "Lakeshore Blvd", "Summit Ave", "Pine Ridge Rd",
           "Willow Way", "Douglas St", "Rainier View Dr"]

INSURERS = [
    # name, id prefix, claim prefix, group template (or "")
    ("Blue Cross Blue Shield of Washington", "BCB", "BCB", "GRP"),
    ("Premera Blue Cross", "PRE", "PRE", "GRP"),
    ("Aetna", "AET", "AET", "GRP"),
    ("UnitedHealthcare", "UHC", "UHC", "GRP"),
    ("Cigna", "CIG", "CIG", "GRP"),
    ("Kaiser Permanente Washington", "KPW", "KPW", "GRP"),
    ("Medicare Part B", "MED", "MED", ""),
]

EMPLOYERS = ["MER-SYSTEMS", "LAKEPORT-SD", "CASCADIA-LOGISTICS", "NORTHSHORE-FOODS",
             "HARBORLINE-MARINE", "EVERGREEN-DENTAL", "SUMMIT-OUTDOORS"]

EMAIL_DOMAINS = ["gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "icloud.com"]
BLOOD_TYPES = ["O+", "O+", "O-", "A+", "A+", "A-", "B+", "B-", "AB+"]
ALLERGY_POOL = ["penicillin", "sulfa drugs", "latex", "shellfish", "peanuts",
                "codeine", "aspirin", "bee stings"]
RELATIONSHIPS = ["spouse", "mother", "father", "sister", "brother", "daughter", "son", "friend"]

# ---------------------------------------------------------------------------
# Visit catalog: (type, category, record_type or None, [procedure codes],
#                 billed range, duration, description)
# provider_pool: "pcp", "pt", or specialist department name
# ---------------------------------------------------------------------------
VISITS = {
    "annual": ("office_visit", "Annual Physical", "annual_physical",
               "99395", (330, 390), 45, "Annual Wellness Exam - Preventive Visit"),
    "quarterly": ("office_visit", "Quarterly Checkup", "quarterly_checkup",
                  "99213", (160, 195), 30, "Office Visit - Established Patient, Level 3"),
    "followup": ("office_visit", "Follow-up Visit", "follow_up",
                 "99214", (195, 250), 30, "Office Visit - Established Patient, Level 4"),
    "blood": ("lab_work", "Blood Panel", None,
              "80053, 85025", (170, 205), 15, "Laboratory - Comprehensive Metabolic Panel & CBC"),
    "chol": ("lab_work", "Cholesterol Panel", None,
             "80061", (85, 115), 15, "Laboratory - Lipid Panel"),
    "flu": ("vaccination", "Flu Shot", "vaccination",
            "90686", (55, 75), 15, "Immunization - Influenza Vaccine, Quadrivalent"),
    "pt_eval": ("physical_therapy", "PT Initial Evaluation", "physical_therapy_evaluation",
                "97161", (240, 290), 60, "Physical Therapy - Initial Evaluation"),
    "pt_follow": ("physical_therapy", "PT Follow-up", "physical_therapy_progress",
                  "97110, 97140", (135, 175), 45, "Physical Therapy - Therapeutic Exercise & Manual Therapy"),
    "referral": ("office_visit", None, "referral",  # category filled per specialist
                 "99243", (250, 320), 40, None),
}

SPECIALIST_DEPTS = ["Cardiology", "Orthopedics", "Dermatology", "Endocrinology",
                    "Women's Health", "Gastroenterology", "Behavioral Health",
                    "Pulmonology"]

DIAGNOSES = {
    "annual": [("Z00.00", "Encounter for general adult medical examination without abnormal findings")],
    "quarterly": [("I10", "Essential (primary) hypertension"),
                  ("E11.9", "Type 2 diabetes mellitus without complications"),
                  ("E78.5", "Hyperlipidemia, unspecified"),
                  ("E03.9", "Hypothyroidism, unspecified")],
    "followup": [("M54.5", "Low back pain"),
                 ("J45.909", "Unspecified asthma, uncomplicated"),
                 ("K21.9", "Gastro-esophageal reflux disease without esophagitis"),
                 ("F41.1", "Generalized anxiety disorder"),
                 ("M25.561", "Pain in right knee"),
                 ("G43.909", "Migraine, unspecified")],
    "flu": [("Z23", "Encounter for immunization")],
    "pt": [("M22.2X9", "Patellofemoral disorders, unspecified knee"),
           ("M54.5", "Low back pain"),
           ("M75.100", "Rotator cuff syndrome, unspecified shoulder"),
           ("S93.401A", "Sprain of right ankle, initial encounter")],
    "referral": [("R00.2", "Palpitations"),
                 ("L82.1", "Seborrheic keratosis"),
                 ("K58.9", "Irritable bowel syndrome without diarrhea"),
                 ("R06.02", "Shortness of breath"),
                 ("E11.9", "Type 2 diabetes mellitus without complications")],
    "lab": [("Z00.00", "Encounter for general adult medical examination"),
            ("E78.5", "Hyperlipidemia, unspecified")],
}

RX_CATALOG = [
    # medication, generic, dosage, frequency, reason
    ("Lisinopril 10mg", "Lisinopril", "10mg", "Once daily in the morning", "Hypertension management"),
    ("Atorvastatin 20mg", "Atorvastatin", "20mg", "Once daily at bedtime", "Hyperlipidemia"),
    ("Metformin 500mg", "Metformin HCl", "500mg", "Twice daily with meals", "Type 2 diabetes management"),
    ("Levothyroxine 50mcg", "Levothyroxine", "50mcg", "Once daily on empty stomach", "Hypothyroidism"),
    ("Sertraline 50mg", "Sertraline", "50mg", "Once daily in the morning", "Generalized anxiety disorder"),
    ("Albuterol HFA Inhaler", "Albuterol sulfate", "90mcg/actuation", "2 puffs every 4-6 hours as needed", "Asthma rescue inhaler"),
    ("Omeprazole 20mg", "Omeprazole", "20mg", "Once daily before breakfast", "GERD"),
    ("Amlodipine 5mg", "Amlodipine besylate", "5mg", "Once daily", "Hypertension management"),
    ("Losartan 50mg", "Losartan potassium", "50mg", "Once daily", "Hypertension management"),
    ("Ibuprofen 600mg", "Ibuprofen", "600mg", "Every 8 hours with food as needed", "Musculoskeletal pain"),
    ("Vitamin D3 2000 IU", "Cholecalciferol", "2000 IU", "Once daily with food", "Vitamin D deficiency"),
    ("Sumatriptan 50mg", "Sumatriptan succinate", "50mg", "At migraine onset, may repeat in 2 hours", "Migraine"),
]

MSG_QUESTIONS = [
    ("medical_question", "Question about {topic}",
     "Hi {prov_last},\n\nI had a quick question about {topic}. {detail} Should I be concerned, or is this something that can wait until my next visit?\n\nThanks,\n{first}"),
]
MSG_TOPICS = [
    ("my blood pressure readings", "I've been checking at home and the numbers have been a bit higher than usual this week, mostly in the 130s over 80s."),
    ("side effects of my new medication", "Since starting it I've noticed some mild dizziness in the mornings that usually passes within an hour."),
    ("my recent lab results", "I saw the results posted in the portal but I'm not sure how to interpret the cholesterol numbers."),
    ("ongoing lower back soreness", "It's been about two weeks now, mostly stiffness in the morning that loosens up with stretching."),
    ("a persistent dry cough", "It's been lingering for about ten days, worse at night, but no fever."),
    ("my exercise plan", "I'd like to start jogging again and wanted to check whether there are any restrictions I should follow."),
    ("recurring headaches", "They tend to come on in the late afternoon a couple of times per week, usually behind the eyes."),
    ("a rash on my forearm", "It appeared a few days ago, slightly itchy but not spreading quickly."),
]
MSG_REPLY = ("medical_advice", "RE: {subject}",
             "Hi {first},\n\nThank you for reaching out. {advice}\n\nIf symptoms worsen or you develop anything new, please call the office or schedule a visit through the portal.\n\nBest,\n{prov_name}")
ADVICE = [
    "Based on what you're describing this is most likely benign, but let's keep an eye on it. Please log your symptoms for the next week and bring the notes to your next appointment.",
    "That can be a common and usually temporary effect. Continue the current dose for another week; if it persists we can adjust the timing or the dosage.",
    "Your results are overall reassuring. The one value slightly out of range is not concerning on its own and we'll recheck it at your next draw.",
    "I'd recommend gentle stretching, heat, and over-the-counter anti-inflammatories with food for now. If there's no improvement in two weeks we should take a closer look.",
    "Please stay well hydrated and consider a humidifier at night. If it lasts beyond another week or you develop a fever, come in so we can listen to your lungs.",
    "There's no restriction on gradually returning to activity — start with shorter sessions and increase weekly as tolerated.",
]
MSG_REFILL = ("prescription_refill", "Refill request - {med}",
              "Hello,\n\nCould you please send a refill of my {med} to {pharmacy}? I have about a week of doses left.\n\nThank you,\n{first} {last}")
MSG_REFILL_REPLY = ("prescription_refill", "RE: Refill request - {med}",
                    "Hi {first},\n\nYour refill for {med} has been sent electronically to {pharmacy}. It should be ready for pickup within 24 hours.\n\nBest,\n{prov_name}")
MSG_VISIT_SUMMARY = ("visit_summary", "Visit summary - {date}",
                     "Hi {first},\n\nThank you for coming in on {date}. A summary of the visit and any updated instructions are now available in your medical records section of the portal. Please review them and message me with any questions.\n\nBest,\n{prov_name}")
SYS_REMINDER = ("appointment_reminder", "Appointment Reminder - {date}",
                "This is a reminder that you have an upcoming appointment at Lakeport Medical Center on {date} at {time} with {prov_name}. Please arrive 15 minutes early and bring your insurance card. To reschedule, visit the Appointments page or call (555) 800-2200.")
SYS_LAB = ("lab_results", "New Lab Results Available",
           "New laboratory results have been posted to your Lakeport Medical Center patient portal. Please log in and visit the Medical Records section to review them. If you have questions about your results, send a secure message to your care team.")

FIRST_NAMES_EC = ["Chris", "Pat", "Morgan", "Taylor", "Jamie", "Casey", "Robin",
                  "Dana", "Lee", "Sam", "Alexis", "Jordan"]


def iso_dt(d, hh, mm):
    return f"{d.isoformat()}T{hh:02d}:{mm:02d}:00Z"


def rand_date(start, end):
    delta = (end - start).days
    return start + datetime.timedelta(days=rng.randint(0, max(delta, 0)))


def money(x):
    return round(x, 2)


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    next_id = {}
    for t in ("users", "appointments", "billing", "medical_records",
              "messages", "prescriptions"):
        next_id[t] = db.execute(
            f"SELECT COALESCE(MAX(id),0)+1 FROM health_portals_{t}").fetchone()[0]

    users_new, appts_new, bills_new, recs_new, msgs_new, rx_new = [], [], [], [], [], []

    # --- providers ------------------------------------------------------
    providers = {}  # dept -> [ids]
    pcp_pool = [3]  # Dr. Lisa Chang
    pt_pool = [4]   # Daniel Okonkwo, DPT
    used_npi = {"1234567890", "9876543210"}
    for first, last, display, ptype, spec, dept, gender, reg in NEW_PROVIDERS:
        uid = next_id["users"]; next_id["users"] += 1
        npi = str(rng.randint(1000000000, 1999999999))
        while npi in used_npi:
            npi = str(rng.randint(1000000000, 1999999999))
        used_npi.add(npi)
        last_clean = last.lower().replace("'", "")
        uname = (f"dr.{first.lower()}.{last_clean}"
                 if display.startswith("Dr.") else f"{first.lower()}.{last_clean}")
        users_new.append({
            "id": uid, "root_user_id": 200 + uid, "username": uname,
            "first_name": first, "last_name": last, "full_name": display,
            "date_of_birth": f"{rng.randint(1962, 1990)}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "gender": gender,
            "email": f"{first[0].lower()}.{last_clean}@lakeportmedical.com",
            "phone": f"(555) {rng.randint(400, 899)}-{rng.randint(1000, 9999)}",
            "address": f"{rng.randint(100, 4800)} {rng.choice(STREETS)}, Lakeport, WA 98401",
            "role": "provider", "insurance_id": "", "insurance_provider": "",
            "insurance_group": "", "primary_physician_id": 0,
            "emergency_contact": "", "allergies": "", "blood_type": "",
            "registered_date": f"{reg}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "last_login": iso_dt(TODAY - datetime.timedelta(days=rng.randint(0, 20)),
                                 rng.randint(7, 18), rng.choice([0, 15, 30, 45])),
            "provider_type": ptype, "specialty": spec, "department": dept,
            "npi_number": npi, "license_state": "WA",
            "accepting_new_patients": rng.choice([1, 1, 1, 0]),
        })
        providers.setdefault(dept, []).append(uid)
        if dept == "Primary Care":
            pcp_pool.append(uid)
        if dept == "Physical Therapy":
            pt_pool.append(uid)

    # --- patients -------------------------------------------------------
    patients = []
    for first, last, gender in PATIENT_NAMES:
        uid = next_id["users"]; next_id["users"] += 1
        birth_year = rng.randint(1948, 2004)
        ins_name, ins_pfx, claim_pfx, grp = rng.choice(
            INSURERS if birth_year <= 1960 else INSURERS[:6])
        if ins_name.startswith("Medicare"):
            group = ""
        else:
            group = f"{rng.choice(EMPLOYERS)}-{rng.randint(1000, 9900)}"
        pcp = rng.choice(pcp_pool)
        reg = rand_date(datetime.date(2014, 1, 5), datetime.date(2025, 6, 1))
        ec_rel = rng.choice(RELATIONSHIPS)
        patient = {
            "id": uid, "root_user_id": 300 + uid,
            "username": f"{first.lower()}.{last.lower()}",
            "first_name": first, "last_name": last,
            "full_name": f"{first} {last}",
            "date_of_birth": f"{birth_year}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}",
            "gender": gender,
            "email": f"{first.lower()}.{last.lower()}{rng.choice(['', str(rng.randint(1, 99))])}@{rng.choice(EMAIL_DOMAINS)}",
            "phone": f"(555) {rng.randint(200, 899)}-{rng.randint(1000, 9999)}",
            "address": f"{rng.randint(100, 4800)} {rng.choice(STREETS)}, Lakeport, WA 98401",
            "role": "patient",
            "insurance_id": f"{ins_pfx}-WA-98401-{rng.randint(1000, 9999)}",
            "insurance_provider": ins_name,
            "insurance_group": group,
            "primary_physician_id": pcp,
            "emergency_contact": json.dumps({
                "name": f"{rng.choice(FIRST_NAMES_EC)} {last}",
                "relationship": ec_rel,
                "phone": f"(555) {rng.randint(200, 899)}-{rng.randint(1000, 9999)}"}),
            "allergies": json.dumps(
                rng.sample(ALLERGY_POOL, rng.choices([0, 1, 2], weights=[45, 40, 15])[0])),
            "blood_type": rng.choice(BLOOD_TYPES),
            "registered_date": reg.isoformat(),
            "last_login": iso_dt(TODAY - datetime.timedelta(days=rng.randint(0, 60)),
                                 rng.randint(6, 22), rng.choice([0, 15, 30, 45])),
            "provider_type": "", "specialty": "", "npi_number": "",
            "department": "", "license_state": "", "accepting_new_patients": 0,
        }
        users_new.append(patient)
        patients.append(patient)

    claim_seq = {p[2]: rng.randint(100000, 140000) for p in INSURERS}
    thread_seq = {}   # year -> next seq (start at 100 to avoid existing ids)
    sys_thread_seq = 100

    def new_thread(year):
        thread_seq.setdefault(year, 100)
        tid = f"THR-{year}-{thread_seq[year]:03d}"
        thread_seq[year] += 1
        return tid

    def add_billing(patient, appt, vkey, dx_code, second_line=None):
        ins = patient["insurance_provider"]
        pfx = next(p[2] for p in INSURERS if p[0] == ins)
        svc = datetime.date.fromisoformat(appt["date"])
        base_desc = VISITS[vkey][6] or f"Specialist Consultation - {appt['category']}"
        for desc, proc, lo, hi in ([ (base_desc, VISITS[vkey][3],
                                      *VISITS[vkey][4]) ] +
                                   ([second_line] if second_line else [])):
            bid = next_id["billing"]; next_id["billing"] += 1
            billed = money(rng.uniform(lo, hi))
            adj = money(-billed * rng.uniform(0.28, 0.46))
            preventive = vkey in ("annual", "flu")
            if preventive:
                copay = coins = 0.0
            else:
                copay = rng.choice([0.0, 25.0, 25.0, 40.0])
                coins = money((billed + adj - copay) * rng.choice([0.0, 0.0, 0.1, 0.2]))
                coins = max(coins, 0.0)
            resp = money(copay + coins)
            paid = money(billed + adj - resp)
            recent = (TODAY - svc).days < 60
            status = "pending" if (recent and rng.random() < 0.7) else "paid_in_full"
            claim_seq[pfx] += rng.randint(1, 9)
            submitted = svc + datetime.timedelta(days=rng.randint(1, 3))
            processed = submitted + datetime.timedelta(days=rng.randint(8, 25))
            bills_new.append({
                "id": bid, "patient_id": patient["id"],
                "appointment_id": appt["id"], "date_of_service": svc.isoformat(),
                "description": desc,
                "procedure_code": proc,
                "diagnosis_code": dx_code, "provider_id": appt["provider_id"],
                "billed_amount": billed, "insurance_adjustment": adj,
                "insurance_paid": paid, "patient_copay": copay,
                "patient_coinsurance": coins, "patient_responsibility": resp,
                "payment_status": status,
                "insurance_claim_id": f"CLM-{svc.year}-{pfx}-{claim_seq[pfx]}",
                "insurance_provider": ins,
                "date_submitted": submitted.isoformat(),
                "date_processed": "" if status == "pending" and processed > TODAY
                                  else min(processed, TODAY).isoformat(),
                "notes": "Preventive visit - fully covered under plan benefits, no patient cost."
                         if preventive else
                         ("Claim processed; patient balance due." if resp > 0 and status == "pending"
                          else "Claim processed under plan benefits."),
                "date_patient_paid": ""
                    if (resp == 0 or status == "pending")
                    else (min(processed, TODAY) + datetime.timedelta(days=rng.randint(2, 20))).isoformat(),
            })

    def make_vitals(patient, full=True):
        base_w = rng.randint(118, 245)
        v = {
            "blood_pressure_systolic": rng.randint(104, 148),
            "blood_pressure_diastolic": rng.randint(64, 92),
            "heart_rate_bpm": rng.randint(56, 92),
            "temperature_f": round(rng.uniform(97.5, 99.0), 1),
            "oxygen_saturation_pct": rng.randint(96, 100),
        }
        if full:
            h = rng.randint(60, 76)
            v = {"height_in": h, "weight_lbs": base_w,
                 "bmi": round(base_w / (h * h) * 703, 1), **v,
                 "respiratory_rate": rng.randint(12, 18)}
        return v

    def make_labs():
        glu = rng.randint(78, 118)
        chol = rng.randint(150, 238)
        ldl = rng.randint(78, 150)
        hdl = rng.randint(38, 72)
        return [
            {"test": "Complete Blood Count (CBC)", "result": "Normal",
             "details": f"WBC {round(rng.uniform(4.2, 9.8),1)}, RBC {round(rng.uniform(4.2, 5.6),1)}, "
                        f"Hemoglobin {round(rng.uniform(12.5, 16.8),1)}, Hematocrit {round(rng.uniform(37, 48),1)}, "
                        f"Platelets {rng.randint(160, 380)}"},
            {"test": "Comprehensive Metabolic Panel (CMP)",
             "result": "Normal" if glu < 100 else "Borderline",
             "details": f"Glucose {glu}, BUN {rng.randint(8, 20)}, Creatinine {round(rng.uniform(0.7, 1.2),1)}, "
                        f"Sodium {rng.randint(136, 143)}, Potassium {round(rng.uniform(3.6, 4.8),1)}, "
                        f"Calcium {round(rng.uniform(8.8, 10.2),1)}"},
            {"test": "Lipid Panel",
             "result": "Normal" if chol < 200 and ldl < 130 else "Elevated",
             "details": f"Total Cholesterol {chol}, LDL {ldl}, HDL {hdl}, "
                        f"Triglycerides {rng.randint(60, 190)}"},
        ]

    def add_record(patient, appt, vkey, dx, prov_name, dept):
        rid = next_id["medical_records"]; next_id["medical_records"] += 1
        rtype = VISITS[vkey][2]
        name = patient["full_name"]
        rec = {
            "id": rid, "patient_id": patient["id"],
            "provider_id": appt["provider_id"], "appointment_id": appt["id"],
            "date": appt["date"], "record_type": rtype,
            "summary": "", "vitals": "", "lab_results": "[]", "diagnosis": f"{dx[0]} - {dx[1]}",
            "prescriptions": "[]", "follow_up": "", "pt_assessment": "",
            "treatment_plan": "", "vaccination_record": "", "referral_details": "",
        }
        if vkey == "annual":
            rec["summary"] = (f"Annual wellness exam for {name}. Patient is in "
                              f"{rng.choice(['good', 'stable', 'good overall'])} health. "
                              f"Vitals reviewed; standard blood panel ordered. "
                              f"{rng.choice(['No acute concerns.', 'Preventive screenings up to date.', 'Discussed diet and exercise habits.'])}")
            rec["vitals"] = json.dumps(make_vitals(patient, full=True))
            rec["lab_results"] = json.dumps(make_labs())
            rec["follow_up"] = rng.choice([
                "Return in 12 months for next annual physical.",
                "Routine follow-up in 1 year. Continue current lifestyle.",
                "Annual physical in 12 months; sooner if concerns arise."])
        elif vkey in ("quarterly", "followup"):
            rec["summary"] = (f"{'Quarterly checkup' if vkey == 'quarterly' else 'Follow-up visit'} "
                              f"for {name} regarding {dx[1].lower()}. "
                              f"{rng.choice(['Symptoms stable since last visit.', 'Reports gradual improvement.', 'Condition well controlled on current regimen.', 'Mild residual symptoms discussed.'])} "
                              f"Plan reviewed and updated as needed.")
            rec["vitals"] = json.dumps(make_vitals(patient, full=False))
            if rng.random() < 0.35:
                rec["lab_results"] = json.dumps(make_labs()[:rng.randint(1, 2)])
            rec["follow_up"] = rng.choice([
                "Follow up in 3 months or sooner if symptoms change.",
                "Recheck at next scheduled visit; labs before appointment.",
                "Continue current medications; follow up in 6-8 weeks."])
        elif vkey == "flu":
            rec["summary"] = (f"Seasonal influenza vaccination administered to {name}. "
                              f"No adverse reaction observed during 15-minute wait.")
            rec["vaccination_record"] = json.dumps({
                "vaccine": "Influenza, quadrivalent (Fluarix)",
                "lot_number": f"FL{rng.randint(10000, 99999)}",
                "site": rng.choice(["left deltoid", "right deltoid"]),
                "administered_by": prov_name})
            rec["follow_up"] = "Next influenza vaccine due next fall."
        elif vkey == "pt_eval":
            rec["summary"] = (f"Physical therapy initial evaluation for {name} "
                              f"referred for {dx[1].lower()}. Baseline strength and "
                              f"range of motion measured; home exercise program issued.")
            rec["pt_assessment"] = rng.choice([
                "Reduced range of motion and mild strength deficit on affected side; good rehab potential.",
                "Pain with resisted movement; functional limitations with stairs and prolonged sitting.",
                "Guarded movement patterns; core stability deficits noted."])
            rec["treatment_plan"] = (f"{rng.choice([4, 6, 8])}-week course, "
                                     f"{rng.choice(['1x', '2x'])}/week: therapeutic exercise, "
                                     f"manual therapy, progressive loading; reassess at midpoint.")
            rec["follow_up"] = "Begin PT sessions per treatment plan."
        elif vkey == "pt_follow":
            rec["summary"] = (f"Physical therapy progress visit for {name}. "
                              f"{rng.choice(['Tolerating exercise progression well.', 'Reports decreased pain with daily activities.', 'Strength improving; range of motion near baseline.'])}")
            rec["pt_assessment"] = rng.choice([
                "Progressing as expected; pain decreased from initial evaluation.",
                "Strength improved approximately one grade; continue progression.",
                "Plateau this week; adjusted loading and added mobility work."])
            rec["treatment_plan"] = "Continue current program; advance resistance as tolerated."
            rec["follow_up"] = rng.choice([
                "Continue weekly PT sessions.",
                "Re-evaluate at next session; discharge planning if progress holds."])
        elif vkey == "referral":
            rec["summary"] = (f"Specialist consultation for {name} in {dept}, "
                              f"referred by primary care for {dx[1].lower()}. "
                              f"History reviewed and focused examination performed.")
            rec["vitals"] = json.dumps(make_vitals(patient, full=False))
            rec["referral_details"] = json.dumps({
                "referred_by": "Primary Care", "department": dept,
                "reason": dx[1], "authorization": f"AUTH-{rng.randint(100000, 999999)}"})
            rec["follow_up"] = rng.choice([
                "Findings sent to referring provider; follow up as needed.",
                "Recommend repeat evaluation in 6 months.",
                "Additional testing ordered; results to be discussed at follow-up."])
        recs_new.append(rec)

    def add_thread(patient, prov, year, kind, med=None, visit_date=None, visit_time=None):
        nonlocal sys_thread_seq
        first = patient["first_name"]
        prov_name = prov["full_name"] if isinstance(prov, dict) else prov
        base = rand_date(datetime.date(year, 1, 2),
                         min(datetime.date(year, 12, 28), TODAY - datetime.timedelta(days=1)))
        hh, mm = rng.randint(7, 20), rng.choice([0, 15, 30, 45])
        if kind == "question":
            tid = new_thread(year)
            topic, detail = rng.choice(MSG_TOPICS)
            cat, subj_t, body_t = MSG_QUESTIONS[0]
            subj = subj_t.format(topic=topic)
            prov_last = prov_name.replace(", DPT", "").replace("Dr. ", "Dr. ")
            mid = next_id["messages"]; next_id["messages"] += 1
            msgs_new.append({
                "id": mid, "thread_id": tid, "sender_id": patient["id"],
                "recipient_id": prov["id"], "date": iso_dt(base, hh, mm),
                "subject": subj,
                "body": body_t.format(prov_last=prov_last, topic=topic,
                                      detail=detail, first=first),
                "read": 1, "category": cat, "priority": rng.choice(["normal", "normal", "low"]),
                "is_system_message": 0})
            reply_d = base + datetime.timedelta(days=rng.randint(0, 2))
            if reply_d <= TODAY and rng.random() < 0.85:
                mid = next_id["messages"]; next_id["messages"] += 1
                cat2, subj2, body2 = MSG_REPLY
                msgs_new.append({
                    "id": mid, "thread_id": tid, "sender_id": prov["id"],
                    "recipient_id": patient["id"],
                    "date": iso_dt(reply_d, rng.randint(8, 17), rng.choice([0, 15, 30, 45])),
                    "subject": subj2.format(subject=subj),
                    "body": body2.format(first=first, advice=rng.choice(ADVICE),
                                         prov_name=prov_name),
                    "read": 1 if (TODAY - reply_d).days > 14 else rng.choice([0, 1, 1]),
                    "category": cat2, "priority": "normal", "is_system_message": 0})
        elif kind == "refill":
            tid = new_thread(year)
            cat, subj_t, body_t = MSG_REFILL
            mid = next_id["messages"]; next_id["messages"] += 1
            msgs_new.append({
                "id": mid, "thread_id": tid, "sender_id": patient["id"],
                "recipient_id": prov["id"], "date": iso_dt(base, hh, mm),
                "subject": subj_t.format(med=med),
                "body": body_t.format(med=med, pharmacy=PHARMACY, first=first,
                                      last=patient["last_name"]),
                "read": 1, "category": cat, "priority": "normal",
                "is_system_message": 0})
            reply_d = base + datetime.timedelta(days=1)
            if reply_d <= TODAY:
                mid = next_id["messages"]; next_id["messages"] += 1
                cat2, subj2, body2 = MSG_REFILL_REPLY
                msgs_new.append({
                    "id": mid, "thread_id": tid, "sender_id": prov["id"],
                    "recipient_id": patient["id"],
                    "date": iso_dt(reply_d, rng.randint(8, 17), 0),
                    "subject": subj2.format(med=med),
                    "body": body2.format(first=first, med=med, pharmacy=PHARMACY,
                                         prov_name=prov_name),
                    "read": 1 if (TODAY - reply_d).days > 14 else rng.choice([0, 1]),
                    "category": cat2, "priority": "normal", "is_system_message": 0})
        elif kind == "summary":
            tid = new_thread(visit_date.year)
            cat, subj_t, body_t = MSG_VISIT_SUMMARY
            d = visit_date + datetime.timedelta(days=1)
            if d > TODAY:
                return
            mid = next_id["messages"]; next_id["messages"] += 1
            msgs_new.append({
                "id": mid, "thread_id": tid, "sender_id": prov["id"],
                "recipient_id": patient["id"],
                "date": iso_dt(d, rng.randint(9, 17), rng.choice([0, 30])),
                "subject": subj_t.format(date=visit_date.strftime("%B %d, %Y")),
                "body": body_t.format(first=first,
                                      date=visit_date.strftime("%B %d, %Y"),
                                      prov_name=prov_name),
                "read": 1 if (TODAY - d).days > 14 else rng.choice([0, 1, 1]),
                "category": cat, "priority": rng.choice(["normal", "low"]),
                "is_system_message": 0})
        elif kind == "reminder":
            tid = f"THR-SYS-{sys_thread_seq:03d}"; sys_thread_seq += 1
            cat, subj_t, body_t = SYS_REMINDER
            d = visit_date - datetime.timedelta(days=3)
            if d > TODAY or d < datetime.date(2015, 1, 1):
                return
            mid = next_id["messages"]; next_id["messages"] += 1
            msgs_new.append({
                "id": mid, "thread_id": tid, "sender_id": 0,
                "recipient_id": patient["id"], "date": iso_dt(d, 8, 0),
                "subject": subj_t.format(date=visit_date.strftime("%B %d, %Y")),
                "body": body_t.format(date=visit_date.strftime("%B %d, %Y"),
                                      time=visit_time, prov_name=prov_name),
                "read": 1 if visit_date <= TODAY else rng.choice([0, 1]),
                "category": cat, "priority": "normal", "is_system_message": 1})
        elif kind == "lab":
            tid = f"THR-SYS-{sys_thread_seq:03d}"; sys_thread_seq += 1
            cat, subj_t, body_t = SYS_LAB
            d = visit_date + datetime.timedelta(days=rng.randint(2, 5))
            if d > TODAY:
                return
            mid = next_id["messages"]; next_id["messages"] += 1
            msgs_new.append({
                "id": mid, "thread_id": tid, "sender_id": 0,
                "recipient_id": patient["id"], "date": iso_dt(d, 8, 0),
                "subject": subj_t, "body": body_t,
                "read": 1 if (TODAY - d).days > 14 else rng.choice([0, 1]),
                "category": cat, "priority": "normal", "is_system_message": 1})

    # --- per-patient history -------------------------------------------
    all_new_providers = {u["id"]: u for u in users_new if u["role"] == "provider"}
    prov_by_id = dict(all_new_providers)
    prov_by_id[3] = {"id": 3, "full_name": "Dr. Lisa Chang", "department": "Primary Care"}
    prov_by_id[4] = {"id": 4, "full_name": "Daniel Okonkwo, DPT", "department": "Physical Therapy"}

    for patient in patients:
        reg = datetime.date.fromisoformat(patient["registered_date"])
        start = max(reg, datetime.date(2019, 1, 15))
        pcp_id = patient["primary_physician_id"]
        pt_id = rng.choice(pt_pool)
        chronic = rng.random() < 0.45  # quarterly-checkup patients
        visits = []  # (date, vkey, provider_id, dept)

        # annual physicals + blood panel + flu shots each year
        year = start.year
        while year <= 2026:
            anniv = rand_date(max(datetime.date(year, 1, 10), start),
                              datetime.date(year, 12, 15))
            if anniv <= TODAY - datetime.timedelta(days=7):
                visits.append((anniv, "annual", pcp_id, "Primary Care"))
                visits.append((anniv, "blood", pcp_id, "Primary Care"))
                if rng.random() < 0.3:
                    visits.append((anniv + datetime.timedelta(days=rng.randint(20, 60)),
                                   "chol", pcp_id, "Primary Care"))
            if year < 2026 and rng.random() < 0.65:
                flu_d = rand_date(datetime.date(year, 9, 20), datetime.date(year, 11, 20))
                if start <= flu_d <= TODAY:
                    visits.append((flu_d, "flu", pcp_id, "Primary Care"))
            if chronic:
                for q_month in (2, 5, 8, 11):
                    if rng.random() < 0.7:
                        qd = rand_date(datetime.date(year, q_month, 1),
                                       datetime.date(year, q_month, 26))
                        if start <= qd <= TODAY - datetime.timedelta(days=3):
                            visits.append((qd, "quarterly", pcp_id, "Primary Care"))
            year += 1

        # follow-ups
        for _ in range(rng.randint(2, 6)):
            d = rand_date(start, TODAY - datetime.timedelta(days=5))
            visits.append((d, "followup", pcp_id, "Primary Care"))

        # PT course
        if rng.random() < 0.55:
            pt_start = rand_date(start, TODAY - datetime.timedelta(days=90))
            visits.append((pt_start, "pt_eval", pt_id, "Physical Therapy"))
            for i in range(rng.randint(4, 9)):
                visits.append((pt_start + datetime.timedelta(days=7 * (i + 1)),
                               "pt_follow", pt_id, "Physical Therapy"))

        # specialist referrals
        for _ in range(rng.choices([0, 1, 2, 3], weights=[20, 40, 28, 12])[0]):
            dept = rng.choice([d for d in SPECIALIST_DEPTS if providers.get(d)])
            d = rand_date(start, TODAY - datetime.timedelta(days=5))
            visits.append((d, "referral", rng.choice(providers[dept]), dept))

        # future scheduled visits (new patients only)
        future = []
        for _ in range(rng.choices([0, 1, 2], weights=[30, 50, 20])[0]):
            fd = TODAY + datetime.timedelta(days=rng.randint(2, 110))
            fkey = rng.choice(["quarterly", "followup", "annual"])
            future.append((fd, fkey, pcp_id, "Primary Care"))

        visits.sort(key=lambda v: v[0])
        rx_budget = rng.choices([2, 3, 4, 5, 6], weights=[15, 25, 30, 20, 10])[0]
        completed_pc_dates = []

        for d, vkey, prov_id, dept in visits + future:
            aid = next_id["appointments"]; next_id["appointments"] += 1
            is_future = d > TODAY
            status = "scheduled" if is_future else \
                ("cancelled" if rng.random() < 0.05 else "completed")
            hh = rng.randint(8, 16)
            mm = rng.choice([0, 15, 30, 45])
            ttype, category, rtype, proc, amt, dur, desc = VISITS[vkey]
            if vkey == "referral":
                category = f"{dept} Referral Consult"
            room = {"lab_work": f"Lab Room {rng.randint(1, 3)}",
                    "physical_therapy": f"PT Suite {rng.choice(['A', 'B'])}",
                    "vaccination": f"Exam Room {rng.randint(1, 8)}",
                    "office_visit": f"Exam Room {rng.randint(1, 8)}"}[ttype]
            prov_name = prov_by_id[prov_id]["full_name"]
            notes_pool = {
                "annual": f"Annual wellness exam for {patient['first_name']}. Full vitals and standard blood panel.",
                "quarterly": "Routine quarterly checkup for chronic condition management.",
                "followup": "Follow-up visit to review symptoms and treatment response.",
                "blood": "Comprehensive metabolic panel and CBC drawn. Results routed to ordering provider.",
                "chol": "Fasting lipid panel drawn per provider order.",
                "flu": "Seasonal influenza vaccination.",
                "pt_eval": "Initial physical therapy evaluation and home exercise program setup.",
                "pt_follow": "Physical therapy progress session.",
                "referral": f"Specialist consultation in {dept} per primary care referral.",
            }
            appt = {
                "id": aid, "patient_id": patient["id"], "provider_id": prov_id,
                "date": d.isoformat(), "time": f"{hh:02d}:{mm:02d}",
                "duration_minutes": dur, "type": ttype, "category": category,
                "status": status, "location": LOCATION,
                "room": room if status != "cancelled" else "",
                "notes": notes_pool[vkey] if status != "cancelled" else
                         "Cancelled by patient prior to visit.",
                "check_in_time": iso_dt(d, hh, max(mm - rng.randint(2, 12), 0))
                                 if status == "completed" else "",
                "check_out_time": iso_dt(d, hh + (dur + 25) // 60,
                                         (mm + dur + 10) % 60)
                                  if status == "completed" else "",
            }
            appts_new.append(appt)

            if status == "scheduled" or (status == "completed" and rng.random() < 0.3):
                add_thread(patient, prov_by_id[prov_id], d.year, "reminder",
                           visit_date=d, visit_time=appt["time"])
            if status != "completed":
                continue

            # diagnosis
            if vkey == "annual":
                dx = DIAGNOSES["annual"][0]
            elif vkey == "quarterly":
                dx = rng.choice(DIAGNOSES["quarterly"])
            elif vkey == "followup":
                dx = rng.choice(DIAGNOSES["followup"])
            elif vkey == "flu":
                dx = DIAGNOSES["flu"][0]
            elif vkey in ("pt_eval", "pt_follow"):
                dx = rng.choice(DIAGNOSES["pt"])
            elif vkey == "referral":
                dx = rng.choice(DIAGNOSES["referral"])
            else:
                dx = rng.choice(DIAGNOSES["lab"])

            add_billing(patient, appt, vkey, dx[0])

            if rtype is not None and rng.random() < 0.78:
                add_record(patient, appt, vkey, dx, prov_name, dept)

            if vkey in ("annual", "blood", "chol") and rng.random() < 0.6:
                add_thread(patient, prov_by_id[prov_id], d.year, "lab", visit_date=d)
            if vkey in ("quarterly", "followup", "referral") and rng.random() < 0.4:
                add_thread(patient, prov_by_id[prov_id], d.year, "summary", visit_date=d)
            if vkey in ("annual", "quarterly", "followup"):
                completed_pc_dates.append(d)

            # prescriptions tied to office visits
            if vkey in ("quarterly", "followup", "referral") and rx_budget > 0 \
                    and rng.random() < 0.5:
                rx_budget -= 1
                med, gen, dose, freq, reason = rng.choice(RX_CATALOG)
                rid = next_id["prescriptions"]; next_id["prescriptions"] += 1
                exp = d + datetime.timedelta(days=365)
                refills_total = rng.choice([0, 1, 2, 3, 3, 5])
                rx_new.append({
                    "id": rid, "patient_id": patient["id"],
                    "prescriber_id": prov_id, "medication": med,
                    "generic_name": gen, "dosage": dose, "frequency": freq,
                    "route": "Oral" if "Inhaler" not in med else "Inhalation",
                    "quantity": rng.choice([30, 30, 60, 90]),
                    "refills_remaining": rng.randint(0, refills_total),
                    "refills_total": refills_total,
                    "date_prescribed": d.isoformat(),
                    "date_filled": (d + datetime.timedelta(days=rng.randint(0, 3))).isoformat(),
                    "expiration_date": exp.isoformat(),
                    "pharmacy": PHARMACY,
                    "status": "active" if exp >= TODAY else "expired",
                    "reason": reason,
                    "notes": rng.choice([
                        "Take with food.", "Do not skip doses.",
                        "Avoid alcohol while taking this medication.",
                        "Store at room temperature.",
                        "Take at the same time each day."]),
                    "previous_dosage": "",
                })

        # free-form message threads
        for _ in range(rng.choices([1, 2, 3, 4], weights=[20, 40, 28, 12])[0]):
            y = rng.randint(max(start.year, 2022), 2026)
            add_thread(patient, prov_by_id[pcp_id], y, "question")
        if rx_budget < 4 and rng.random() < 0.6:
            med = rng.choice(RX_CATALOG)[0]
            add_thread(patient, prov_by_id[pcp_id], rng.randint(2024, 2026),
                       "refill", med=med)

    # -------------------------------------------------------------------
    counts = {"users": len(users_new), "appointments": len(appts_new),
              "billing": len(bills_new), "medical_records": len(recs_new),
              "messages": len(msgs_new), "prescriptions": len(rx_new)}
    total_added = sum(counts.values())
    print("rows to add:", json.dumps(counts), "| total:", total_added)

    # safety: nothing for patients 1 and 2
    for coll, key in ((appts_new, "patient_id"), (bills_new, "patient_id"),
                      (recs_new, "patient_id"), (rx_new, "patient_id")):
        assert not any(r[key] in (1, 2) for r in coll)
    assert not any(m["sender_id"] in (1, 2) or m["recipient_id"] in (1, 2)
                   for m in msgs_new)
    # safety: scheduled appointments are future-dated, new patients only
    for a in appts_new:
        if a["status"] == "scheduled":
            assert a["date"] > TODAY.isoformat()
    # per-patient render bound
    from collections import Counter
    per_patient = Counter(a["patient_id"] for a in appts_new)
    assert max(per_patient.values()) < 100, max(per_patient.values())

    if dry:
        print("dry run — sample rows:")
        for a in appts_new[:3]:
            print(" appt:", a["date"], a["status"], a["category"], "pt", a["patient_id"])
        for m in msgs_new[:2]:
            print(" msg:", m["thread_id"], m["category"], m["subject"][:50])
        for b in bills_new[:2]:
            print(" bill:", b["date_of_service"], b["payment_status"], b["insurance_claim_id"])
        return

    bdir = ROOT / "data" / "backups" / "health-portals-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "appointments": [a["id"] for a in appts_new],
        "billing": [b["id"] for b in bills_new],
        "medical_records": [r["id"] for r in recs_new],
        "messages": [m["id"] for m in msgs_new],
        "prescriptions": [p["id"] for p in rx_new]}, indent=1))

    for table, rows in (("users", users_new), ("appointments", appts_new),
                        ("billing", bills_new), ("medical_records", recs_new),
                        ("messages", msgs_new), ("prescriptions", rx_new)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO health_portals_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # rebuild external-content FTS indexes for touched tables
    for t in ("appointments", "billing", "medical_records", "messages"):
        db.execute(f"INSERT INTO fts_health_portals_{t}(fts_health_portals_{t}) "
                   f"VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
