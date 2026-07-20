"""Expand spreadsheets-slides (SheetDeck) base data.

SheetDeck ships with 15 spreadsheets / 10 presentations / 6 templates / 5 users
(36 rows total), which makes the Files dashboard look like a demo account.
Adds deterministic (seeded) synthetic users, templates, spreadsheets with fully
populated 20x10 cell grids, and presentations with realistic slide decks.

Ceiling note: the dashboard route renders ALL spreadsheets + presentations in
one unpaginated list, and every edit route rewrites the whole collection via
db.save_collection. The row total is therefore capped at a defensible ceiling
(~480 files on the default dashboard render, < 500 row limit) instead of 5000:
  users:        5 ->  60
  templates_ss: 6 ->  44
  spreadsheets: 15 -> 300
  presentations:10 -> 180
  site total:   36 -> 584

Task-safety:
- Insert-only. "Sales Pipeline Tracker" (id 4) stays unique and untouched; no
  new title contains "Sales Pipeline"; vocab never emits "Spark" or "Alex Lee".
- All new files get created_at <= 2026-01-04 and updated_at <= 2026-06-09, i.e.
  strictly older than every existing file, so the existing 25 files (incl. the
  tracker) stay on top of the dashboard under both "updated" and "created" sort.

Inserted ids recorded under data/backups/ for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_spreadsheets_slides_data.py [--dry-run]
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

CREATED_LO = datetime.datetime(2024, 6, 1, 7, 0)
CREATED_HI = datetime.datetime(2026, 1, 4, 18, 0)   # before oldest existing created_at (2026-01-05)
UPDATED_HI = datetime.datetime(2026, 6, 9, 20, 0)   # before oldest existing updated_at (2026-06-10)

TARGET_USERS = 60
TARGET_TEMPLATES = 44
TARGET_SPREADSHEETS = 300
TARGET_PRESENTATIONS = 180

FORBIDDEN = ("sales pipeline", "spark", "alex lee")


def zdate(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def rand_dt(lo, hi):
    span = int((hi - lo).total_seconds())
    return lo + datetime.timedelta(seconds=rng.randint(0, span))


# ---------------------------------------------------------------------------
# Vocabulary
# ---------------------------------------------------------------------------

FIRST = ["Maya", "Liam", "Priya", "Noah", "Ines", "Kenji", "Sofia", "Marcus",
         "Amara", "Tomas", "Lena", "Ravi", "Greta", "Omar", "Hana", "Felix",
         "Nadia", "Jonas", "Aisha", "Diego", "Elin", "Victor", "Mei", "Stefan",
         "Rosa", "Anders", "Tara", "Miguel", "Yuki", "Petra", "Sam", "Ingrid",
         "Kofi", "Clara", "Mateo", "Freya", "Arjun", "Paula", "Nils", "Zara",
         "Henrik", "Leila", "Owen", "Bianca", "Tariq", "Astrid", "Ruben",
         "Salma", "Emil", "Chloe", "Dmitri", "Alma", "Idris", "Nora", "Pablo"]
LAST = ["Torres", "Lindqvist", "Patel", "Berg", "Moreau", "Sato", "Ricci",
        "Webb", "Diallo", "Novak", "Hoffmann", "Iyer", "Klein", "Haddad",
        "Kimura", "Braun", "Petrov", "Ekström", "Bello", "Vargas", "Dahl",
        "Costa", "Chen", "Wolf", "Delgado", "Nygaard", "Singh", "Rojas",
        "Tanaka", "Vasquez", "Holt", "Larsen", "Mensah", "Fontaine", "Silva",
        "Johansen", "Rao", "Weber", "Strand", "Amini", "Foss", "Karam",
        "Doyle", "Romano", "Aziz", "Lund", "Ortega", "Farah", "Bakker",
        "Martin", "Volkov", "Perez", "Osei", "Eriksen", "Alvarez"]
ROLES = [("Data Analyst", "analyst"), ("Project Manager", "pm"),
         ("Software Engineer", "eng"), ("Marketing Lead", "mktg"),
         ("HR Manager", "hr"), ("Account Executive", "sales"),
         ("Product Designer", "design"), ("Finance Manager", "fin"),
         ("Operations Lead", "ops"), ("Customer Success Manager", "cs"),
         ("QA Engineer", "qa"), ("Content Strategist", "content"),
         ("Recruiter", "talent"), ("Support Specialist", "support")]
AVATAR_COLORS = ["#4285F4", "#EA4335", "#34A853", "#FBBC04", "#9C27B0",
                 "#FF7043", "#26A69A", "#5C6BC0", "#8D6E63", "#EC407A",
                 "#7CB342", "#00ACC1", "#F4511E", "#3949AB", "#00897B"]

COMPANIES = ["Acme Corp", "TechStart Inc", "Global Media", "HealthPlus",
             "Meridian Systems", "Lakeport Labs", "Cascadia Partners",
             "Northwind Traders", "BlueRiver Foods", "Vertex Analytics",
             "Summit Logistics", "Harborview Clinic", "Orchid Design Co",
             "Pinecrest Retail", "Solstice Energy", "Ridgeline Media",
             "Copperfield Bank", "Juniper Software", "Beacon Insurance",
             "Willow & Finch", "Stonebridge Consulting", "Aurora Biotech"]
PEOPLE = ["John Smith", "Maria Garcia", "Li Wei", "Sarah Jones", "Priya Patel",
          "Tom Becker", "Ana Souza", "David Kim", "Fatima Noor", "Peter Novak",
          "Grace Obi", "Hugo Larsen", "Emma Wilson", "Carlos Ruiz", "Mia Chen",
          "Oscar Dahl", "Julia Weber", "Sam Holt", "Nina Petrova", "Leo Costa"]
OWNER_FIRSTS = ["Alice", "Bob", "Carol", "Dan", "Eve"]
DEPARTMENTS = ["Engineering", "Marketing", "Sales", "Finance", "HR",
               "Operations", "Design", "Support", "Product", "Legal"]
REGIONS = ["EMEA", "APAC", "North America", "LATAM", "Nordics", "DACH", "UK & Ireland"]
CITIES = ["Portland", "Austin", "Berlin", "Singapore", "Toronto", "Lisbon",
          "Amsterdam", "Denver", "Oslo", "Dublin"]
QUARTERS = ["Q3 2024", "Q4 2024", "Q1 2025", "Q2 2025", "Q3 2025", "Q4 2025"]
MONTHS = ["Jul 2024", "Aug 2024", "Sep 2024", "Oct 2024", "Nov 2024", "Dec 2024",
          "Jan 2025", "Feb 2025", "Mar 2025", "Apr 2025", "May 2025", "Jun 2025",
          "Jul 2025", "Aug 2025", "Sep 2025", "Oct 2025", "Nov 2025", "Dec 2025"]
STATUS_GEN = ["On Track", "At Risk", "Done", "In Progress", "Blocked", "Planned"]
YESNO = ["Yes", "No"]
NOTES_POOL = ["Reviewed in weekly sync", "Carried over from last cycle",
              "Needs follow-up", "Approved by finance", "Pending confirmation",
              "Flagged for review", "Updated after retro", "See linked doc",
              "Double-checked totals", "Awaiting vendor reply", "", "", ""]


def money(lo, hi, step=100):
    return str(rng.randrange(lo, hi, step))


def pct(lo=1, hi=99):
    return f"{rng.randint(lo, hi)}%"


def dstr(lo_year=2024, hi_year=2025):
    d = rand_dt(datetime.datetime(lo_year, 1, 1), datetime.datetime(hi_year, 12, 28))
    return d.strftime("%Y-%m-%d")


# ---------------------------------------------------------------------------
# Spreadsheet archetypes: (title templates, sheet name, headers, row builder)
# ---------------------------------------------------------------------------

def _budget_row(i):
    b = rng.randrange(2000, 60000, 500)
    a = int(b * rng.uniform(0.7, 1.25))
    return [rng.choice(["Software", "Travel", "Contractors", "Events", "Office",
                        "Cloud Hosting", "Training", "Recruiting", "Advertising", "Equipment"]),
            rng.choice(DEPARTMENTS), str(b), str(a), str(a - b),
            rng.choice(MONTHS), rng.choice(PEOPLE),
            rng.choice(["Approved", "Pending", "Rejected"]),
            rng.choice(YESNO), rng.choice(NOTES_POOL)]

def _expense_row(i):
    return [dstr(), rng.choice(PEOPLE),
            rng.choice(["Meals", "Airfare", "Lodging", "Ground Transport", "Supplies", "Conference"]),
            rng.choice(["Client dinner", "Team offsite", "Sales trip", "Workshop materials",
                        "Booth supplies", "Onsite visit", "Quarterly summit"]),
            str(rng.randrange(20, 2400, 5)), "USD", rng.choice(YESNO),
            rng.choice(OWNER_FIRSTS), rng.choice(["Submitted", "Approved", "Reimbursed"]),
            rng.choice(NOTES_POOL)]

def _timesheet_row(i):
    hrs = [rng.choice([6, 7, 8, 8, 8, 9]) for _ in range(5)]
    total = sum(hrs)
    return [rng.choice(PEOPLE)] + [str(h) for h in hrs] + \
           [str(total), str(max(0, total - 40)),
            rng.choice(["Atlas", "Beacon", "Orion", "Delta", "Internal"]),
            rng.choice(NOTES_POOL)]

def _inventory_row(i):
    return [f"SKU-{rng.randint(1000, 9999)}",
            rng.choice(["USB-C Cable", "Monitor Stand", "Desk Lamp", "Keyboard",
                        "Webcam", "Headset", "Docking Station", "Chair Mat",
                        "Whiteboard Kit", "Label Printer"]),
            rng.choice(["Electronics", "Furniture", "Accessories", "Office"]),
            rng.choice(["Lakeport DC", "Cascadia DC", "Meridian Hub"]),
            str(rng.randint(0, 500)), str(rng.choice([10, 20, 25, 50])),
            str(rng.randrange(5, 400, 5)), rng.choice(COMPANIES), dstr(),
            rng.choice(["In Stock", "Low", "Reorder", "Backordered"])]

def _campaign_row(i):
    imp = rng.randrange(5000, 900000, 1000)
    clicks = int(imp * rng.uniform(0.005, 0.06))
    conv = max(1, int(clicks * rng.uniform(0.01, 0.2)))
    spend = rng.randrange(500, 40000, 100)
    return [rng.choice(["Spring Promo", "Brand Awareness", "Retargeting", "Launch Teaser",
                        "Webinar Push", "Newsletter Signup", "Free Trial", "Holiday Sale"]),
            rng.choice(["Email", "Paid Search", "Social", "Display", "Podcast", "Organic"]),
            str(imp), str(clicks), f"{clicks / imp * 100:.1f}%", str(conv),
            str(spend), f"{spend / conv:.0f}", dstr(),
            rng.choice(["Active", "Paused", "Completed"])]

def _bug_row(i):
    return [f"BUG-{rng.randint(100, 4999)}",
            rng.choice(["Login loop on expired session", "Chart tooltip misaligned",
                        "CSV import drops header row", "Notification sent twice",
                        "Search ignores accents", "Timeout on large upload",
                        "Dark mode contrast issue", "Currency rounding error",
                        "Broken link in footer", "Filter resets on refresh"]),
            rng.choice(["Critical", "Major", "Minor", "Trivial"]),
            rng.choice(["P0", "P1", "P2", "P3"]),
            rng.choice(["API", "Frontend", "Auth", "Reports", "Billing", "Mobile"]),
            rng.choice(PEOPLE), rng.choice(PEOPLE), dstr(),
            rng.choice(["Open", "In Progress", "Fixed", "Won't Fix", "Verified"]),
            rng.choice(NOTES_POOL)]

def _content_row(i):
    return [dstr(), rng.choice(["How-to guide", "Customer story", "Release notes",
                                "Industry report", "Checklist", "Webinar recap",
                                "Comparison post", "FAQ update"]),
            rng.choice(["Blog", "Video", "Email", "Whitepaper", "Social"]),
            rng.choice(["Website", "YouTube", "Newsletter", "LinkedIn", "Docs"]),
            rng.choice(PEOPLE), rng.choice(["Draft", "In Review", "Scheduled", "Published"]),
            rng.choice(OWNER_FIRSTS), dstr(),
            rng.choice(["product, launch", "guide, onboarding", "report, data",
                        "customers, story", "seo, evergreen"]),
            rng.choice(NOTES_POOL)]

def _headcount_row(i):
    return [rng.choice(["Backend Engineer", "Account Manager", "UX Researcher",
                        "Payroll Specialist", "Field Marketer", "Data Engineer",
                        "Support Agent", "Solutions Architect", "Copywriter"]),
            rng.choice(DEPARTMENTS), rng.choice(["L2", "L3", "L4", "L5"]),
            rng.choice(CITIES), rng.choice(PEOPLE), dstr(2025, 2025),
            rng.choice(["Open", "Interviewing", "Offer Out", "Filled", "On Hold"]),
            rng.choice(YESNO), rng.choice(PEOPLE), rng.choice(NOTES_POOL)]

def _survey_row(i):
    p, pa, d = rng.randint(20, 200), rng.randint(10, 100), rng.randint(5, 80)
    return [rng.choice(["Ease of setup", "Value for money", "Support quality",
                        "Feature completeness", "Performance", "Documentation",
                        "Onboarding experience", "Reliability"]),
            str(p + pa + d), f"{rng.uniform(2.8, 4.8):.1f}", str(p), str(pa), str(d),
            str(round((p - d) / (p + pa + d) * 100)),
            rng.choice(["SMB", "Mid-Market", "Enterprise", "All"]),
            rng.choice(QUARTERS), rng.choice(NOTES_POOL)]

def _uptime_row(i):
    return [rng.choice(["auth-service", "billing-api", "web-frontend", "search",
                        "notifications", "reports-worker", "file-store", "gateway"]),
            rng.choice(["us-east", "us-west", "eu-central", "ap-south"]),
            f"{rng.uniform(97.5, 100.0):.2f}%", str(rng.randint(0, 6)),
            str(rng.randint(4, 90)), dstr(), "99.9%",
            rng.choice(["Healthy", "Degraded", "Watch"]),
            rng.choice(PEOPLE), rng.choice(NOTES_POOL)]

def _vendor_row(i):
    return [rng.choice(COMPANIES),
            rng.choice(["SaaS", "Hardware", "Consulting", "Facilities", "Legal", "Catering"]),
            rng.choice(PEOPLE),
            f"contact{rng.randint(1, 99)}@vendor.example.com",
            money(2000, 250000, 1000), dstr(2025, 2026),
            f"{rng.uniform(2.5, 5.0):.1f}",
            rng.choice(["Net 30", "Net 45", "Net 60"]),
            rng.choice(["Active", "Under Review", "Expiring"]),
            rng.choice(NOTES_POOL)]

def _training_row(i):
    return [rng.choice(PEOPLE),
            rng.choice(["Security Awareness", "Advanced SQL", "Public Speaking",
                        "First Aid", "Accessibility 101", "Negotiation Skills",
                        "Cloud Fundamentals", "Management Basics"]),
            rng.choice(["Coursera", "Internal L&D", "LinkedIn Learning", "Udemy", "Workshop"]),
            dstr(), dstr(), str(rng.randint(60, 100)), rng.choice(YESNO),
            rng.choice(PEOPLE), rng.choice(["Enrolled", "In Progress", "Completed"]),
            rng.choice(NOTES_POOL)]

def _abtest_row(i):
    users = rng.randrange(1000, 50000, 500)
    conv = int(users * rng.uniform(0.01, 0.15))
    return [rng.choice(["Signup CTA copy", "Pricing page layout", "Onboarding steps",
                        "Email subject line", "Checkout button color", "Trial length"]),
            rng.choice(["Control", "Variant A", "Variant B"]),
            str(users), str(conv), f"{conv / users * 100:.1f}%",
            f"{rng.uniform(-8, 18):+.1f}%", f"{rng.randint(72, 99)}%",
            dstr(), dstr(), rng.choice(["Ship", "Iterate", "Abandon", "Pending"])]

def _forecast_row(i):
    t = rng.randrange(50000, 900000, 10000)
    return [rng.choice(REGIONS),
            rng.choice(["Core Platform", "Analytics Add-on", "Enterprise Plan",
                        "Support Package", "API Credits"]),
            str(t), str(int(t * rng.uniform(0.3, 0.8))),
            str(int(t * rng.uniform(0.8, 1.2))), str(int(t * rng.uniform(0.1, 0.6))),
            f"{rng.uniform(1.0, 3.5):.1f}x", rng.choice(PEOPLE), dstr(2025, 2025),
            rng.choice(NOTES_POOL)]

def _event_row(i):
    e = rng.randrange(300, 25000, 100)
    return [rng.choice(["Venue rental", "AV equipment", "Catering", "Badges & signage",
                        "Speaker travel", "Photography", "Swag", "Security", "Livestream"]),
            rng.choice(COMPANIES), rng.choice(["Venue", "Food", "Production", "Travel", "Marketing"]),
            str(e), str(int(e * rng.uniform(0.85, 1.2))), money(0, 5000, 50),
            dstr(2025, 2025), rng.choice(YESNO), rng.choice(OWNER_FIRSTS),
            rng.choice(NOTES_POOL)]

def _analytics_row(i):
    s = rng.randrange(500, 120000, 100)
    return [rng.choice(["/home", "/pricing", "/blog", "/docs", "/signup", "/features",
                        "/customers", "/about", "/integrations", "/changelog"]),
            str(s), str(int(s * rng.uniform(0.6, 0.95))), pct(20, 80),
            f"{rng.randint(0, 4)}:{rng.randint(10, 59):02d}",
            str(int(s * rng.uniform(0.005, 0.08))),
            rng.choice(["Organic", "Direct", "Referral", "Paid", "Social"]),
            rng.choice(["Desktop", "Mobile", "Tablet"]),
            rng.choice(MONTHS), rng.choice(NOTES_POOL)]

def _procurement_row(i):
    qty = rng.randint(1, 40)
    unit = rng.randrange(20, 3000, 10)
    return [f"PO-{rng.randint(10000, 99999)}",
            rng.choice(["Laptops", "Monitors", "Standing desks", "Software licenses",
                        "Server parts", "Office chairs", "Test devices", "Books"]),
            rng.choice(PEOPLE), rng.choice(DEPARTMENTS), str(qty), str(unit),
            str(qty * unit), rng.choice(OWNER_FIRSTS), dstr(),
            rng.choice(["Requested", "Approved", "Ordered", "Received"])]

def _okr_row(i):
    base, target = rng.randint(10, 60), rng.randint(70, 100)
    cur = rng.randint(base, target)
    return [rng.choice(["Improve activation", "Grow ARR", "Reduce churn",
                        "Ship platform v2", "Raise NPS", "Hire key roles",
                        "Cut infra costs", "Expand to new regions"]),
            rng.choice(["Increase weekly active teams", "Close enterprise deals",
                        "Cut page load time", "Publish case studies",
                        "Automate onboarding emails", "Reduce ticket backlog"]),
            rng.choice(PEOPLE), str(base), str(target), str(cur),
            f"{int((cur - base) / max(1, target - base) * 100)}%",
            rng.choice(["High", "Medium", "Low"]), rng.choice(QUARTERS),
            rng.choice(NOTES_POOL)]


SS_ARCHETYPES = [
    (["{dept} Budget - {month}", "{region} Budget Plan - {q}", "Annual Budget Draft - {dept} {q}"],
     "Budget", ["Category", "Department", "Budgeted ($)", "Actual ($)", "Variance ($)",
                "Month", "Owner", "Status", "Recurring", "Notes"], _budget_row),
    (["Expense Report - {month}", "{dept} Expenses - {month}", "Travel Expenses - {region} {q}"],
     "Expenses", ["Date", "Employee", "Category", "Description", "Amount ($)",
                  "Currency", "Receipt", "Approved By", "Status", "Notes"], _expense_row),
    (["Timesheet - Week of {week}", "{dept} Timesheet - {month}"],
     "Hours", ["Employee", "Mon", "Tue", "Wed", "Thu", "Fri", "Total Hours",
               "Overtime", "Project", "Notes"], _timesheet_row),
    (["Stock Count - {month}", "{city} Warehouse Inventory - {q}", "Supplies Inventory - {dept} {month}"],
     "Stock", ["SKU", "Item", "Category", "Warehouse", "Qty", "Reorder Level",
               "Unit Cost ($)", "Supplier", "Last Restock", "Status"], _inventory_row),
    (["Campaign Metrics - {month}", "{region} Campaign Results - {q}", "Ad Performance - {month}"],
     "Campaigns", ["Campaign", "Channel", "Impressions", "Clicks", "CTR",
                   "Conversions", "Spend ($)", "CPA ($)", "Start Date", "Status"], _campaign_row),
    (["Bug Triage - {month}", "QA Findings - {q}", "Release Blockers - {month}"],
     "Bugs", ["Bug ID", "Summary", "Severity", "Priority", "Component",
              "Reporter", "Assignee", "Opened", "Status", "Notes"], _bug_row),
    (["Content Calendar - {month}", "Editorial Plan - {q}"],
     "Calendar", ["Date", "Title", "Type", "Channel", "Author", "Status",
                  "Reviewer", "Publish Date", "Tags", "Notes"], _content_row),
    (["Headcount Plan - {q}", "{dept} Hiring Plan - {q}"],
     "Roles", ["Role", "Department", "Level", "Location", "Hiring Manager",
               "Target Start", "Status", "Budgeted", "Recruiter", "Notes"], _headcount_row),
    (["NPS Survey Breakdown - {q}", "Customer Survey - {month}", "Pulse Survey Results - {q}"],
     "Results", ["Question", "Responses", "Avg Score", "Promoters", "Passives",
                 "Detractors", "NPS", "Segment", "Quarter", "Notes"], _survey_row),
    (["Service Uptime - {month}", "SLA Report - {q}"],
     "Services", ["Service", "Region", "Uptime %", "Incidents", "MTTR (min)",
                  "Last Incident", "SLA Target", "Status", "Owner", "Notes"], _uptime_row),
    (["Vendor Register - {q}", "Supplier Contracts - {dept}", "Vendor Renewals - {q}"],
     "Vendors", ["Vendor", "Category", "Contact", "Email", "Annual Cost ($)",
                 "Contract End", "Rating", "Payment Terms", "Status", "Notes"], _vendor_row),
    (["Training Roster - {q}", "{dept} Training Log - {month}"],
     "Roster", ["Employee", "Course", "Provider", "Start", "Completion",
                "Score", "Certificate", "Manager", "Status", "Notes"], _training_row),
    (["A/B Test Log - {q}", "Experiment Results - {month}"],
     "Experiments", ["Test", "Variant", "Users", "Conversions", "Conv Rate",
                     "Lift", "Confidence", "Start", "End", "Decision"], _abtest_row),
    (["Revenue Forecast - {region} {q}", "Bookings Forecast - {q}"],
     "Forecast", ["Region", "Product", "Target ($)", "Committed ($)", "Best Case ($)",
                  "Closed ($)", "Coverage", "Rep", "Updated", "Notes"], _forecast_row),
    (["Offsite Budget - {city} {q}", "Launch Event Costs - {month}", "Summit Planning Budget - {q}"],
     "Line Items", ["Item", "Vendor", "Category", "Estimated ($)", "Actual ($)",
                    "Deposit ($)", "Due Date", "Paid", "Owner", "Notes"], _event_row),
    (["Website Analytics - {month}", "Traffic Report - {q}"],
     "Pages", ["Page", "Sessions", "Users", "Bounce %", "Avg Time",
               "Conversions", "Source", "Device", "Month", "Notes"], _analytics_row),
    (["Purchase Orders - {month}", "{dept} Procurement - {q}"],
     "Orders", ["PO Number", "Item", "Requester", "Department", "Qty",
                "Unit Price ($)", "Total ($)", "Approver", "Order Date", "Status"], _procurement_row),
    (["OKR Check-in - {dept} {q}", "Goal Tracking - {q}"],
     "OKRs", ["Objective", "Key Result", "Owner", "Baseline", "Target",
              "Current", "Progress %", "Confidence", "Quarter", "Notes"], _okr_row),
]

WEEKS = ["Jan 6", "Feb 3", "Mar 10", "Apr 14", "May 12", "Jun 2", "Jul 7",
         "Aug 11", "Sep 8", "Oct 6", "Nov 3", "Dec 1"]


def make_title(templates, used):
    for _ in range(60):
        t = rng.choice(templates).format(
            dept=rng.choice(DEPARTMENTS), region=rng.choice(REGIONS),
            month=rng.choice(MONTHS), q=rng.choice(QUARTERS),
            city=rng.choice(CITIES), week=rng.choice(WEEKS) + rng.choice([" 2025", " 2024"]))
        if t.lower() not in used:
            used.add(t.lower())
            return t
    return None


def build_grid(headers, row_fn):
    n_data = rng.randint(12, 19)
    grid = [list(headers)]
    for i in range(n_data):
        row = [str(c) for c in row_fn(i)]
        row = (row + [""] * 10)[:10]
        grid.append(row)
    while len(grid) < 20:
        grid.append([""] * 10)
    return grid


# ---------------------------------------------------------------------------
# Presentation archetypes
# ---------------------------------------------------------------------------

def _deck_metrics():
    return (f"Revenue: ${rng.randrange(80, 900, 10)}K\n"
            f"New Customers: {rng.randint(8, 90)}\n"
            f"Churn: {rng.uniform(1.0, 6.0):.1f}%\n"
            f"NPS: {rng.randint(20, 68)}")

def _deck_agenda():
    items = rng.sample(["Welcome", "Metrics review", "Wins & lowlights", "Roadmap",
                        "Customer spotlight", "Team updates", "Budget", "Q&A",
                        "Action items", "Next steps"], 5)
    return "\n".join(f"{i+1}. {x}" for i, x in enumerate(items))

def _deck_bullets(pool, n=4):
    return "\n".join("- " + b for b in rng.sample(pool, n))

TAKEAWAY = ["Focus on fewer, bigger bets", "Automate the manual steps first",
            "Talk to customers weekly", "Ship smaller, ship sooner",
            "Document decisions as we go", "Measure before optimizing",
            "Align hiring with roadmap", "Cut meetings, add write-ups"]
RISKS = ["Vendor contract renewal slipping", "Hiring pace behind plan",
         "Cloud costs trending over budget", "Key dependency on one engineer",
         "Competitor launched similar feature", "Data migration complexity",
         "Seasonal dip in signups", "Support backlog growing"]
WINS = ["Closed two enterprise deals", "Cut page load time by 40%",
        "Launched self-serve onboarding", "Hit 99.95% uptime",
        "Doubled webinar attendance", "Shipped mobile beta",
        "Reduced ticket backlog by half", "Signed reseller agreement"]

def deck_review(topic):
    slides = [
        {"title": topic, "content": f"{topic}\nPrepared by the team", "notes": "Intro and context."},
        {"title": "Agenda", "content": _deck_agenda(), "notes": "Keep this to one minute."},
        {"title": "Key Metrics", "content": _deck_metrics(), "notes": "Numbers pulled from the dashboard."},
        {"title": "Highlights", "content": _deck_bullets(WINS), "notes": "Celebrate the wins first."},
        {"title": "Risks & Watch Items", "content": _deck_bullets(RISKS, 3), "notes": "Mitigations in appendix."},
        {"title": "Next Steps", "content": _deck_bullets(TAKEAWAY, 3), "notes": "Owners assigned in tracker."},
    ]
    return slides[:1] + slides[1:1 + rng.randint(3, 5)] + slides[-1:]

def deck_training(topic):
    slides = [
        {"title": topic, "content": f"{topic}\nInternal training session", "notes": "Check attendance."},
        {"title": "Learning Objectives", "content": _deck_bullets(
            ["Understand the core workflow", "Know where to find help",
             "Practice with real examples", "Avoid common mistakes",
             "Set up your own environment"], 3), "notes": "Set expectations."},
        {"title": "Walkthrough", "content": "Live demo of the main flow\nPause for questions after each step",
         "notes": "Demo account is preloaded."},
        {"title": "Exercise", "content": "Complete the practice scenario in pairs\n15 minutes",
         "notes": "Circulate and help."},
        {"title": "Key Takeaways", "content": _deck_bullets(TAKEAWAY, 3), "notes": "Share the cheat sheet link."},
    ]
    return slides[:rng.randint(4, 5)]

def deck_pitch(topic):
    return [
        {"title": topic, "content": f"{topic}\nProposal draft", "notes": "One-line summary up front."},
        {"title": "Problem", "content": _deck_bullets(
            ["Manual process wastes hours weekly", "Data lives in silos",
             "No visibility for leadership", "Errors caught too late",
             "Onboarding takes too long"], 3), "notes": "Anchor with a real example."},
        {"title": "Proposal", "content": _deck_bullets(
            ["Pilot with one team first", "Reuse existing tooling",
             "Phased rollout over two quarters", "Clear success metrics",
             "Weekly check-ins"], 3), "notes": "Emphasize low risk."},
        {"title": "Costs & Timeline", "content":
            f"Budget: ${rng.randrange(10, 120, 5)}K\nTimeline: {rng.choice(['6 weeks', '2 months', 'one quarter'])}\nTeam: {rng.randint(2, 6)} people",
         "notes": "Numbers validated with finance."},
        {"title": "Ask", "content": "Approve pilot budget\nNominate pilot team\nKickoff next month",
         "notes": "End with the decision needed."},
    ][:rng.randint(4, 5)]

def deck_retro(topic):
    return [
        {"title": topic, "content": f"{topic}\nTeam retrospective", "notes": "Safe space reminder."},
        {"title": "What Went Well", "content": _deck_bullets(WINS, 3), "notes": "Round-robin sharing."},
        {"title": "What Didn't", "content": _deck_bullets(RISKS, 3), "notes": "No blame, just facts."},
        {"title": "Experiments for Next Cycle", "content": _deck_bullets(TAKEAWAY, 3),
         "notes": "Pick at most three."},
        {"title": "Action Items", "content": "Owners and due dates captured in the tracker",
         "notes": "Review at next retro."},
    ][:rng.randint(4, 5)]


PRES_ARCHETYPES = [
    (["{dept} Review - {q}", "{region} Business Review - {q}", "Monthly Report - {month}"], deck_review),
    (["Onboarding Basics - {dept}", "Tool Training - {month}", "Workshop: {dept} Essentials"], deck_training),
    (["Proposal: {noun}", "Pitch - {noun}", "{noun} Initiative"], deck_pitch),
    (["{dept} Retro - {q}", "Sprint Retro - {month}", "Postmortem Review - {month}"], deck_retro),
]
PITCH_NOUNS = ["Automation Rollout", "Data Warehouse Upgrade", "Partner Program",
               "Docs Revamp", "Support Chatbot", "Referral Scheme", "Tooling Consolidation",
               "Accessibility Push", "Localization Effort", "Analytics Migration"]


# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

NEW_TEMPLATES = [
    ("Expense Report", "spreadsheet", "Finance", "Log employee expenses with categories, receipts, and approval status."),
    ("Invoice Tracker", "spreadsheet", "Finance", "Track outgoing invoices, due dates, and payment status."),
    ("Cash Flow Forecast", "spreadsheet", "Finance", "Project monthly cash in and out with running balance."),
    ("Content Calendar", "spreadsheet", "Marketing", "Plan posts, authors, channels, and publish dates."),
    ("Campaign Tracker", "spreadsheet", "Marketing", "Measure impressions, clicks, conversions, and spend per campaign."),
    ("Social Media Planner", "spreadsheet", "Marketing", "Schedule posts across channels with status and owners."),
    ("Bug Tracker", "spreadsheet", "Engineering", "Log bugs with severity, component, assignee, and status."),
    ("Sprint Backlog", "spreadsheet", "Engineering", "Prioritized backlog with estimates and sprint assignments."),
    ("On-call Schedule", "spreadsheet", "Engineering", "Weekly rotation with primary, secondary, and escalation contacts."),
    ("Interview Scorecard", "spreadsheet", "HR", "Score candidates per competency with interviewer notes."),
    ("PTO Tracker", "spreadsheet", "HR", "Track vacation balances and requested days per employee."),
    ("Onboarding Checklist", "spreadsheet", "HR", "Tasks for a new hire's first 30 days with owners."),
    ("Inventory Count", "spreadsheet", "Operations", "Count stock by SKU with reorder levels and suppliers."),
    ("Vendor Register", "spreadsheet", "Operations", "Contracts, costs, renewal dates, and vendor ratings."),
    ("Purchase Order Log", "spreadsheet", "Operations", "Track POs from request through receipt."),
    ("Event Budget", "spreadsheet", "Events", "Line-item budget with estimates, actuals, and deposits."),
    ("Guest List Manager", "spreadsheet", "Events", "RSVPs, dietary notes, and seating assignments."),
    ("Habit Tracker", "spreadsheet", "Personal", "Daily habit grid with streaks and weekly totals."),
    ("Reading List", "spreadsheet", "Personal", "Books to read with ratings and completion dates."),
    ("Grade Book", "spreadsheet", "Education", "Student scores by assignment with weighted totals."),
    ("Lesson Planner", "spreadsheet", "Education", "Weekly lesson topics, materials, and homework."),
    ("A/B Test Log", "spreadsheet", "Product", "Experiments with variants, lift, confidence, and decisions."),
    ("Feature Prioritization", "spreadsheet", "Product", "Score features by reach, impact, confidence, and effort."),
    ("OKR Tracker", "spreadsheet", "Project Management", "Objectives and key results with progress check-ins."),
    ("Risk Register", "spreadsheet", "Project Management", "Project risks with likelihood, impact, and mitigations."),
    ("Gantt Lite", "spreadsheet", "Project Management", "Simple timeline view of tasks by week."),
    ("Sales Forecast", "spreadsheet", "Sales", "Pipeline coverage and committed revenue by region."),
    ("Commission Calculator", "spreadsheet", "Sales", "Compute rep commissions from closed deals and rates."),
    ("Team Retrospective", "presentation", "Meetings", "Went well, didn't go well, experiments, and actions."),
    ("Project Kickoff", "presentation", "Project Management", "Goals, scope, team, timeline, and communication plan."),
    ("All-Hands Update", "presentation", "Business", "Company metrics, team highlights, and announcements."),
    ("Sales Proposal", "presentation", "Sales", "Problem, solution, pricing, and next steps for a prospect."),
    ("Product Launch Plan", "presentation", "Marketing", "Positioning, channels, timeline, and success metrics."),
    ("Research Readout", "presentation", "Product", "Methodology, findings, insights, and recommendations."),
    ("Incident Postmortem", "presentation", "Engineering", "Timeline, root cause, impact, and prevention actions."),
    ("Design Review", "presentation", "Design", "Explorations, chosen direction, and open questions."),
    ("Course Syllabus", "presentation", "Education", "Course overview, schedule, grading, and expectations."),
    ("Conference Talk", "presentation", "Education", "Reusable talk skeleton: hook, story, demo, takeaways."),
]


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_users = [dict(r) for r in db.execute("SELECT * FROM spreadsheets_slides_users")]
    used_usernames = {u["username"] for u in existing_users}
    used_emails = {u["email"] for u in existing_users}
    used_titles = {r[0].lower() for r in db.execute(
        "SELECT title FROM spreadsheets_slides_spreadsheets UNION SELECT title FROM spreadsheets_slides_presentations")}
    n_ss = db.execute("SELECT COUNT(*) FROM spreadsheets_slides_spreadsheets").fetchone()[0]
    n_pres = db.execute("SELECT COUNT(*) FROM spreadsheets_slides_presentations").fetchone()[0]
    next_ss = db.execute("SELECT MAX(id)+1 FROM spreadsheets_slides_spreadsheets").fetchone()[0]
    next_pres = db.execute("SELECT MAX(id)+1 FROM spreadsheets_slides_presentations").fetchone()[0]
    next_user = db.execute("SELECT MAX(id)+1 FROM spreadsheets_slides_users").fetchone()[0]
    next_tpl = db.execute("SELECT MAX(id)+1 FROM spreadsheets_slides_templates_ss").fetchone()[0]

    # --- users ---
    users_new = []
    fl = [(f, l) for f in FIRST for l in LAST]
    rng.shuffle(fl)
    for f, l in fl:
        if len(users_new) >= TARGET_USERS - len(existing_users):
            break
        role, tag = rng.choice(ROLES)
        username = f"{f.lower()}_{tag}"
        email = f"{f.lower()}.{l.lower().replace('ö', 'o').replace('é', 'e')}@example.com"
        if username in used_usernames or email in used_emails:
            continue
        used_usernames.add(username)
        used_emails.add(email)
        users_new.append({
            "id": next_user, "username": username, "name": f"{f} {l}",
            "email": email, "password": f"pass{rng.randint(100, 999)}",
            "avatar_color": rng.choice(AVATAR_COLORS), "role": role})
        next_user += 1
    all_user_ids = [u["id"] for u in existing_users] + [u["id"] for u in users_new]

    # owners: existing five users stay prominent, new users share the rest
    def pick_owner():
        if rng.random() < 0.42:
            return rng.choice([1, 1, 2, 3, 4, 5])
        return rng.choice(all_user_ids[5:])

    def pick_shared(owner):
        others = [u for u in all_user_ids if u != owner]
        k = rng.choices([0, 1, 2, 3], weights=[45, 30, 17, 8])[0]
        return json.dumps(sorted(rng.sample(others, k)))

    # --- templates ---
    templates_new = []
    for name, ttype, cat, desc in NEW_TEMPLATES[:TARGET_TEMPLATES - 6]:
        templates_new.append({"id": next_tpl, "name": name, "type": ttype,
                              "category": cat, "description": desc})
        next_tpl += 1

    # --- spreadsheets ---
    ss_new = []
    while len(ss_new) < TARGET_SPREADSHEETS - n_ss:
        titles, sheet_name, headers, row_fn = rng.choice(SS_ARCHETYPES)
        title = make_title(titles, used_titles)
        if title is None:
            continue
        created = rand_dt(CREATED_LO, CREATED_HI)
        updated = min(created + datetime.timedelta(days=rng.randint(1, 200),
                                                   hours=rng.randint(0, 12)), UPDATED_HI)
        owner = pick_owner()
        sheets = [{"name": sheet_name, "data": build_grid(headers, row_fn)}]
        if rng.random() < 0.12:
            sheets.append({"name": rng.choice(["Archive", "Notes", "Summary", "Prior Period"]),
                           "data": build_grid(headers, row_fn)})
        ss_new.append({
            "id": next_ss, "title": title, "owner_id": owner,
            "created_at": zdate(created), "updated_at": zdate(updated),
            "shared_with": pick_shared(owner), "rows": 20, "cols": 10,
            "sheets": json.dumps(sheets)})
        next_ss += 1

    # --- presentations ---
    pres_new = []
    while len(pres_new) < TARGET_PRESENTATIONS - n_pres:
        titles, builder = rng.choice(PRES_ARCHETYPES)
        title = None
        for _ in range(60):
            t = rng.choice(titles).format(
                dept=rng.choice(DEPARTMENTS), region=rng.choice(REGIONS),
                month=rng.choice(MONTHS), q=rng.choice(QUARTERS),
                noun=rng.choice(PITCH_NOUNS))
            if t.lower() not in used_titles:
                used_titles.add(t.lower())
                title = t
                break
        if title is None:
            continue
        created = rand_dt(CREATED_LO, CREATED_HI)
        updated = min(created + datetime.timedelta(days=rng.randint(1, 120),
                                                   hours=rng.randint(0, 12)), UPDATED_HI)
        owner = pick_owner()
        slides = builder(title)
        pres_new.append({
            "id": next_pres, "title": title, "owner_id": owner,
            "created_at": zdate(created), "updated_at": zdate(updated),
            "shared_with": pick_shared(owner), "slides_count": len(slides),
            "slides": json.dumps(slides)})
        next_pres += 1

    # --- safety: forbidden strings never appear in new content ---
    blob = json.dumps([users_new, templates_new, ss_new, pres_new]).lower()
    for bad in FORBIDDEN:
        assert bad not in blob, f"forbidden string {bad!r} found in generated data"
    # all new files strictly older than every existing file
    assert max(s["updated_at"] for s in ss_new + pres_new) < "2026-06-10"
    assert max(s["created_at"] for s in ss_new + pres_new) < "2026-01-05"

    print(f"users: +{len(users_new)}, templates_ss: +{len(templates_new)}, "
          f"spreadsheets: +{len(ss_new)}, presentations: +{len(pres_new)}")
    if dry:
        for s in ss_new[:5]:
            print("  SS ", s["id"], s["owner_id"], s["created_at"], "|", s["title"])
        for p in pres_new[:5]:
            print("  PR ", p["id"], p["owner_id"], p["slides_count"], "slides |", p["title"])
        g = json.loads(ss_new[0]["sheets"])[0]["data"]
        print("  grid check:", len(g), "rows x", set(len(r) for r in g), "cols")
        print("  sample row:", g[1])
        return

    bdir = ROOT / "data" / "backups" / "spreadsheets-slides-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "templates_ss": [t["id"] for t in templates_new],
        "spreadsheets": [s["id"] for s in ss_new],
        "presentations": [p["id"] for p in pres_new]}, indent=1))

    for table, rows in (("users", users_new), ("templates_ss", templates_new),
                        ("spreadsheets", ss_new), ("presentations", pres_new)):
        if not rows:
            continue
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO spreadsheets_slides_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # rebuild content-linked FTS indexes for the tables we touched
    db.execute("INSERT INTO fts_spreadsheets_slides_spreadsheets"
               "(fts_spreadsheets_slides_spreadsheets) VALUES('rebuild')")
    db.execute("INSERT INTO fts_spreadsheets_slides_presentations"
               "(fts_spreadsheets_slides_presentations) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
