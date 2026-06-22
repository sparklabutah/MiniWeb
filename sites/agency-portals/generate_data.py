"""Generate synthesized data for the agency-portals MiniWeb site.

Creates departments, services, permits, public_records, users, appointments,
payments, and announcements JSON files.
"""
import json
import os
import pathlib
import random
import shutil
import string

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_DIR = SITE_DIR / "data"
PRISTINE_DIR = DATA_DIR / ".pristine"
CONFIG_FILE = SITE_DIR / "config" / "config.json"


def load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


def generate(seed=42):
    rng = random.Random(seed)

    # ── Departments ──────────────────────────────────────────────
    departments = [
        {"id": 1, "name": "Public Works", "code": "DPW", "phone": "(555) 234-0100",
         "email": "publicworks@cedargrove.gov", "hours": "Mon-Fri 8:00 AM - 5:00 PM",
         "description": "Maintains roads, water systems, sewers, and public infrastructure.",
         "head": "Maria Vasquez", "location": "100 Civic Center Dr, Suite 200"},
        {"id": 2, "name": "Parks & Recreation", "code": "PRD", "phone": "(555) 234-0200",
         "email": "parks@cedargrove.gov", "hours": "Mon-Fri 8:00 AM - 5:00 PM",
         "description": "Manages public parks, recreational facilities, and community events.",
         "head": "James Okonkwo", "location": "100 Civic Center Dr, Suite 210"},
        {"id": 3, "name": "Planning & Zoning", "code": "PLZ", "phone": "(555) 234-0300",
         "email": "planning@cedargrove.gov", "hours": "Mon-Fri 9:00 AM - 4:30 PM",
         "description": "Handles land use, zoning regulations, and development permits.",
         "head": "Linda Chang", "location": "100 Civic Center Dr, Suite 300"},
        {"id": 4, "name": "Finance & Revenue", "code": "FIN", "phone": "(555) 234-0400",
         "email": "finance@cedargrove.gov", "hours": "Mon-Fri 8:30 AM - 4:30 PM",
         "description": "Manages municipal budget, tax collection, and utility billing.",
         "head": "Robert Hensley", "location": "100 Civic Center Dr, Suite 110"},
        {"id": 5, "name": "Police Department", "code": "PD", "phone": "(555) 234-0500",
         "email": "police@cedargrove.gov", "hours": "24/7",
         "description": "Provides law enforcement, emergency response, and community safety.",
         "head": "Captain Diane Rourke", "location": "250 Justice Way"},
        {"id": 6, "name": "Fire & Rescue", "code": "FRD", "phone": "(555) 234-0600",
         "email": "fire@cedargrove.gov", "hours": "24/7",
         "description": "Provides fire suppression, emergency medical services, and fire prevention.",
         "head": "Chief Alan Torres", "location": "300 Firehouse Ln"},
        {"id": 7, "name": "Community Development", "code": "CDD", "phone": "(555) 234-0700",
         "email": "commdev@cedargrove.gov", "hours": "Mon-Fri 8:00 AM - 5:00 PM",
         "description": "Promotes economic development, housing programs, and neighborhood revitalization.",
         "head": "Patricia Hawkins", "location": "100 Civic Center Dr, Suite 320"},
        {"id": 8, "name": "Clerk & Records", "code": "CLK", "phone": "(555) 234-0800",
         "email": "clerk@cedargrove.gov", "hours": "Mon-Fri 8:30 AM - 4:00 PM",
         "description": "Maintains public records, vital records, business licenses, and election administration.",
         "head": "Nancy Whitfield", "location": "100 Civic Center Dr, Suite 100"},
    ]

    # ── Services ─────────────────────────────────────────────────
    services = [
        {"id": 1, "name": "Water/Sewer Utility Service", "department_id": 1, "code": "SVC-WTR",
         "category": "Utilities", "fee": 0.00, "online": True,
         "description": "Start, stop, or transfer water and sewer utility accounts."},
        {"id": 2, "name": "Pothole Repair Request", "department_id": 1, "code": "SVC-POT",
         "category": "Infrastructure", "fee": 0.00, "online": True,
         "description": "Report a pothole for repair by Public Works crews."},
        {"id": 3, "name": "Park Shelter Reservation", "department_id": 2, "code": "SVC-PKR",
         "category": "Recreation", "fee": 50.00, "online": True,
         "description": "Reserve a park shelter or pavilion for events."},
        {"id": 4, "name": "Youth Sports Registration", "department_id": 2, "code": "SVC-YSR",
         "category": "Recreation", "fee": 75.00, "online": True,
         "description": "Register youth for seasonal sports leagues."},
        {"id": 5, "name": "Building Permit Application", "department_id": 3, "code": "SVC-BLD",
         "category": "Permits", "fee": 150.00, "online": True,
         "description": "Apply for residential or commercial building permits."},
        {"id": 6, "name": "Zoning Variance Request", "department_id": 3, "code": "SVC-ZVR",
         "category": "Permits", "fee": 250.00, "online": False,
         "description": "Request a variance from current zoning regulations."},
        {"id": 7, "name": "Property Tax Payment", "department_id": 4, "code": "SVC-PTX",
         "category": "Taxes", "fee": 0.00, "online": True,
         "description": "Pay property taxes online or set up payment plans."},
        {"id": 8, "name": "Utility Bill Payment", "department_id": 4, "code": "SVC-UBP",
         "category": "Utilities", "fee": 0.00, "online": True,
         "description": "Pay your monthly utility bill online."},
        {"id": 9, "name": "Police Report Request", "department_id": 5, "code": "SVC-PRR",
         "category": "Public Safety", "fee": 10.00, "online": True,
         "description": "Request a copy of a filed police report."},
        {"id": 10, "name": "Fire Inspection Scheduling", "department_id": 6, "code": "SVC-FIS",
         "category": "Public Safety", "fee": 0.00, "online": True,
         "description": "Schedule a fire safety inspection for commercial properties."},
        {"id": 11, "name": "Business License Application", "department_id": 8, "code": "SVC-BLA",
         "category": "Licenses", "fee": 100.00, "online": True,
         "description": "Apply for a new business license in Cedar Grove."},
        {"id": 12, "name": "Birth Certificate Request", "department_id": 8, "code": "SVC-BCR",
         "category": "Vital Records", "fee": 15.00, "online": True,
         "description": "Request a certified copy of a birth certificate."},
        {"id": 13, "name": "Marriage License Application", "department_id": 8, "code": "SVC-MLA",
         "category": "Vital Records", "fee": 35.00, "online": False,
         "description": "Apply for a marriage license (in-person required)."},
        {"id": 14, "name": "Neighborhood Grant Program", "department_id": 7, "code": "SVC-NGP",
         "category": "Community", "fee": 0.00, "online": True,
         "description": "Apply for neighborhood improvement grants up to $5,000."},
        {"id": 15, "name": "Street Light Repair", "department_id": 1, "code": "SVC-SLR",
         "category": "Infrastructure", "fee": 0.00, "online": True,
         "description": "Report a broken or malfunctioning street light."},
        {"id": 16, "name": "Parking Permit", "department_id": 5, "code": "SVC-PPM",
         "category": "Permits", "fee": 25.00, "online": True,
         "description": "Apply for residential or commercial parking permits."},
    ]

    # ── Permits ──────────────────────────────────────────────────
    permit_types = ["Building", "Demolition", "Electrical", "Plumbing", "Mechanical",
                    "Sign", "Fence", "Driveway", "Grading", "Roofing"]
    statuses = ["Approved", "Pending", "Under Review", "Denied", "Expired"]
    streets = ["Main St", "Oak Ave", "Elm Dr", "Cedar Blvd", "Pine Rd",
               "Maple Ln", "Birch Ct", "Spruce Way", "Walnut Pl", "Ash Ter"]
    first_names = ["John", "Sarah", "Michael", "Jennifer", "David", "Lisa",
                   "Robert", "Emily", "William", "Angela", "Thomas", "Karen"]
    last_names = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Garcia",
                  "Miller", "Davis", "Rodriguez", "Martinez", "Anderson", "Taylor"]

    permits = []
    for i in range(1, 41):
        ptype = rng.choice(permit_types)
        year = rng.choice([2023, 2024, 2025, 2026])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        applicant = f"{rng.choice(first_names)} {rng.choice(last_names)}"
        address = f"{rng.randint(100, 9999)} {rng.choice(streets)}"
        status = rng.choice(statuses)
        code = f"PRM-{year}-{i:04d}"
        permits.append({
            "id": i,
            "code": code,
            "type": ptype,
            "applicant": applicant,
            "address": address,
            "status": status,
            "date_submitted": f"{year}-{month:02d}-{day:02d}",
            "department_id": 3,
            "fee": rng.choice([75.0, 100.0, 150.0, 200.0, 250.0, 500.0]),
            "description": f"{ptype} permit for {address}"
        })

    # ── Public Records ───────────────────────────────────────────
    record_types = ["Council Meeting Minutes", "Budget Report", "Ordinance",
                    "Resolution", "Public Hearing Notice", "Annual Report",
                    "Audit Report", "Contract Award", "Bid Solicitation",
                    "Environmental Impact Study"]
    records = []
    for i in range(1, 31):
        rtype = rng.choice(record_types)
        year = rng.choice([2022, 2023, 2024, 2025, 2026])
        month = rng.randint(1, 12)
        day = rng.randint(1, 28)
        doc_id = f"DOC-{year}-{i:04d}"
        dept = rng.choice(departments)
        records.append({
            "id": i,
            "doc_id": doc_id,
            "type": rtype,
            "title": f"{rtype} - {dept['name']} ({month:02d}/{year})",
            "department_id": dept["id"],
            "department_name": dept["name"],
            "date_published": f"{year}-{month:02d}-{day:02d}",
            "file_format": rng.choice(["PDF", "PDF", "PDF", "DOCX"]),
            "pages": rng.randint(2, 85),
            "summary": f"Official {rtype.lower()} document published by {dept['name']}."
        })

    # ── Users (residents) ────────────────────────────────────────
    users = [
        {"id": 1, "username": "resident_jane", "password": "cedar123",
         "name": "Jane Cooper", "email": "jane.cooper@email.com",
         "address": "1234 Main St", "phone": "(555) 111-2233",
         "verified": True, "verification_code": "VRF-100001",
         "saved_services": [], "permits": [], "payments": [], "appointments": []},
        {"id": 2, "username": "resident_mark", "password": "grove456",
         "name": "Mark Sullivan", "email": "mark.sullivan@email.com",
         "address": "567 Oak Ave", "phone": "(555) 222-3344",
         "verified": True, "verification_code": "VRF-100002",
         "saved_services": [], "permits": [], "payments": [], "appointments": []},
        {"id": 3, "username": "business_lisa", "password": "biz789",
         "name": "Lisa Tran", "email": "lisa.tran@tranenterprises.com",
         "address": "890 Cedar Blvd", "phone": "(555) 333-4455",
         "verified": False, "verification_code": "VRF-100003",
         "saved_services": [], "permits": [], "payments": [], "appointments": []},
        {"id": 4, "username": "resident_omar", "password": "civic321",
         "name": "Omar Patel", "email": "omar.patel@email.com",
         "address": "2100 Elm Dr", "phone": "(555) 444-5566",
         "verified": True, "verification_code": "VRF-100004",
         "saved_services": [], "permits": [], "payments": [], "appointments": []},
        {"id": 5, "username": "newresident_amy", "password": "new2026",
         "name": "Amy Nakamura", "email": "amy.nakamura@email.com",
         "address": "3456 Pine Rd", "phone": "(555) 555-6677",
         "verified": False, "verification_code": "VRF-100005",
         "saved_services": [], "permits": [], "payments": [], "appointments": []},
    ]

    # ── Announcements ────────────────────────────────────────────
    announcements = [
        {"id": 1, "title": "Water Main Repair on Oak Avenue", "department_id": 1,
         "date": "2026-06-15", "category": "Infrastructure",
         "content": "Public Works will be conducting water main repairs on Oak Avenue between Elm Dr and Cedar Blvd from June 18-22. Expect intermittent water service disruptions."},
        {"id": 2, "title": "Summer Concert Series in Liberty Park", "department_id": 2,
         "date": "2026-06-10", "category": "Events",
         "content": "Join us every Friday evening in July for the Summer Concert Series at Liberty Park amphitheater. Free admission. Food vendors on site."},
        {"id": 3, "title": "Public Hearing: Downtown Rezoning Proposal", "department_id": 3,
         "date": "2026-06-08", "category": "Planning",
         "content": "A public hearing regarding the proposed rezoning of the downtown corridor from C-2 to mixed-use MU-1 will be held on June 25 at City Hall."},
        {"id": 4, "title": "Property Tax Bills Mailed", "department_id": 4,
         "date": "2026-06-01", "category": "Finance",
         "content": "2026 property tax bills have been mailed. Payment is due by August 31, 2026. Pay online or at the Finance office."},
        {"id": 5, "title": "National Night Out Registration Open", "department_id": 5,
         "date": "2026-05-28", "category": "Community",
         "content": "Register your neighborhood block party for National Night Out on August 6. Contact the Police Department community outreach office."},
        {"id": 6, "title": "Fire Hydrant Testing Schedule", "department_id": 6,
         "date": "2026-05-20", "category": "Public Safety",
         "content": "Fire & Rescue will conduct annual hydrant flow testing June 1-15. Temporary discoloration of water may occur. Water is safe to use."},
        {"id": 7, "title": "Small Business Grant Applications Open", "department_id": 7,
         "date": "2026-05-15", "category": "Economic Development",
         "content": "Community Development is accepting applications for the Small Business Recovery Grant. Grants up to $10,000 for qualifying businesses."},
        {"id": 8, "title": "Election Day: Vote on Bond Measure", "department_id": 8,
         "date": "2026-05-10", "category": "Elections",
         "content": "Polls are open 7 AM - 8 PM on November 5 for the Parks and Infrastructure bond measure. Check your polling location at cedargrove.gov/vote."},
    ]

    # ── Appointments slots ───────────────────────────────────────
    appointment_types = [
        {"id": 1, "name": "Building Permit Consultation", "department_id": 3,
         "duration_min": 30, "available_days": "Mon-Fri"},
        {"id": 2, "name": "Business License Review", "department_id": 8,
         "duration_min": 20, "available_days": "Mon-Thu"},
        {"id": 3, "name": "Tax Payment Assistance", "department_id": 4,
         "duration_min": 15, "available_days": "Mon-Fri"},
        {"id": 4, "name": "Planning Review Meeting", "department_id": 3,
         "duration_min": 45, "available_days": "Tue-Thu"},
        {"id": 5, "name": "Code Enforcement Consultation", "department_id": 7,
         "duration_min": 30, "available_days": "Mon-Wed"},
    ]

    # ── Payments ─────────────────────────────────────────────────
    payment_types = [
        {"id": "PAY-PTX", "name": "Property Tax", "category": "Taxes"},
        {"id": "PAY-UTL", "name": "Utility Bill", "category": "Utilities"},
        {"id": "PAY-PRM", "name": "Permit Fee", "category": "Permits"},
        {"id": "PAY-LIC", "name": "License Fee", "category": "Licenses"},
        {"id": "PAY-PKR", "name": "Park Reservation", "category": "Recreation"},
        {"id": "PAY-PPN", "name": "Parking Penalty", "category": "Fines"},
    ]

    data = {
        "departments": departments,
        "services": services,
        "permits": permits,
        "records": records,
        "users": users,
        "announcements": announcements,
        "appointment_types": appointment_types,
        "payment_types": payment_types,
    }

    return data


def write_data():
    config = load_config()
    seed = config.get("random_seed", 42)
    data = generate(seed)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRISTINE_DIR.mkdir(parents=True, exist_ok=True)

    for name, items in data.items():
        fpath = DATA_DIR / f"{name}.json"
        fpath.write_text(json.dumps(items, indent=2))
        pristine_path = PRISTINE_DIR / f"{name}.json"
        pristine_path.write_text(json.dumps(items, indent=2))

    print(f"Generated data: {', '.join(f'{k}({len(v)})' for k, v in data.items())}")


if __name__ == "__main__":
    write_data()
