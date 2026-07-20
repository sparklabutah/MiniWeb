"""Expand business-company (Apex Dynamics / Meridian Systems) base data.

The corporate brochure site ships with only 70 rows total. This adds
deterministic (seeded) synthetic bulk where a corporate site plausibly
carries it: newsletter subscribers, contact-form submissions and blog
posts, plus modest growth in testimonials, job openings and services.

Hard task constraints respected:
- team: ZERO new rows (last displayed member must stay Natalie Kim).
- products: ZERO new rows (first product / its video must stay unchanged).
- posts: all new posts get ids > existing max AND dates strictly older than
  the oldest existing post (2025-06-20), so the first Engineering blog stays
  post id 2 by Alex Rivera in both id-order (/blog) and date-desc (/api/posts).
- No new row anywhere contains the name "Alex Rivera" (search task) or the
  phrase "machine learning" (semantic-search task noise).

Insert-only - existing rows are never touched. Inserted ids are recorded in
data/backups/business-company-expansion-2026-07-20/inserted_ids.json.
After inserting, external-content FTS tables (posts, subscribers,
testimonials) are rebuilt.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_business_company_data.py [--dry-run]
"""
import datetime
import json
import random
import re
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(20260720)

BACKUP_DIR = ROOT / "data" / "backups" / "business-company-expansion-2026-07-20"

# Targets (final table sizes)
TARGETS = {
    "subscribers": 2800,   # 15 existing
    "contacts": 1420,      # 7 existing
    "posts": 600,          # 10 existing
    "testimonials": 150,   # 10 existing
    "jobs": 40,            # 7 existing
    "services": 14,        # 6 existing
}

# ---------------------------------------------------------------------------
# Vocabulary (reuses Meridian / Lakeport / Cascadia branding)
# ---------------------------------------------------------------------------

# "Alex" and "Rivera" deliberately excluded (search-task constraint).
FIRST = ["James", "Maria", "Robert", "Linda", "Michael", "Elena", "William",
         "Sofia", "Daniel", "Grace", "Matthew", "Olivia", "Andrew", "Emma",
         "Joshua", "Chloe", "Ethan", "Hannah", "Nathan", "Laura", "Kevin",
         "Rachel", "Brandon", "Megan", "Tyler", "Julia", "Jordan", "Nicole",
         "Aaron", "Vanessa", "Derek", "Priyanka", "Carlos", "Simone", "Victor",
         "Ingrid", "Omar", "Felicia", "Hassan", "Beatriz", "Dmitri", "Amara",
         "Kenji", "Noor", "Lars", "Rosa", "Pablo", "Yuki", "Sven", "Anita",
         "Gordon", "Celeste", "Marcus", "Diane", "Trevor", "Paula"]
LAST = ["Walsh", "Delgado", "Fischer", "Hutchins", "Barnes", "Kowalski",
        "Mendoza", "Osei", "Lindqvist", "Tran", "Novak", "Whitfield",
        "Iyer", "Castellanos", "Bergman", "Adeyemi", "Sorensen", "Vega",
        "MacLeod", "Petrova", "Nakamura", "Olsen", "Duarte", "Kaminski",
        "Brennan", "Silva", "Hargrove", "Ellison", "Mbeki", "Thornton",
        "Vasquez", "Lindstrom", "Okonkwo", "Farrell", "Dietrich", "Salazar",
        "Pemberton", "Choudhury", "Ashworth", "Galvan", "Romano", "Steinberg",
        "Hollis", "Marchetti", "Donovan", "Aldridge", "Beaumont", "Castille"]

COMPANY_A = ["Cascadia", "Lakeport", "Silverline", "Bridgewater", "Summit",
             "Evergreen", "Harborview", "Northgate", "Pinnacle", "Bluecrest",
             "Redwood", "Ironbridge", "Clearwater", "Stonefield", "Westlake",
             "Copperline", "Granite", "Fairhaven", "Kingsley", "Oakmont",
             "Riverbend", "Sagebrush", "Timberline", "Vantage", "Whitmore"]
COMPANY_B = ["Logistics", "Health Systems", "Capital Partners", "Manufacturing",
             "Retail Group", "Energy", "Financial", "Consulting", "Biotech",
             "Insurance Group", "Media Group", "Technologies", "Foods",
             "Aerospace", "Legal Services", "Construction", "Analytics Group",
             "Distribution", "Robotics", "Pharmaceuticals"]

EXISTING_COMPANIES = ["Silverline Health Systems", "Atlas Logistics",
                      "Verti Capital Partners", "Bridgewater Solutions",
                      "TechNova Inc.", "Horizon Group", "EdgePoint Energy",
                      "Summit Partners", "Crestline Enterprises",
                      "Nexus Financial", "Crestview CPA Group", "BlazeFit",
                      "Grove Retail Group"]

TOPICS = ["product-updates", "blog", "events", "security-insights", "case-studies"]
PRODUCTS = ["MeridianFlow", "MeridianVault", "MeridianLens"]

ASSIGNEES = ["ryan.tanaka@meridiansystems.com",
             "tom.bradley@meridiansystems.com",
             "samantha.liu@meridiansystems.com"]

# Team authors for blog posts (id 1 = Alex Rivera deliberately excluded)
AUTHORS = [(2, "Priya Sharma"), (3, "Marcus Chen"), (4, "Jessica Okafor"),
           (5, "Ryan Tanaka"), (6, "Samantha Liu"), (7, "David Petrov"),
           (8, "Karen Nguyen"), (9, "Tom Bradley"), (10, "Aisha Patel"),
           (11, "Brian Reeves"), (12, "Natalie Kim")]


def full_name():
    return f"{rng.choice(FIRST)} {rng.choice(LAST)}"


def company_name():
    if rng.random() < 0.08:
        return rng.choice(EXISTING_COMPANIES)
    return f"{rng.choice(COMPANY_A)} {rng.choice(COMPANY_B)}"


def domain_of(company):
    return re.sub(r"[^a-z0-9]", "", company.lower())[:22] + ".com"


def email_of(name, company, used):
    first, last = name.lower().split(" ", 1)
    last = re.sub(r"[^a-z]", "", last)
    base = rng.choice([f"{first}.{last}", f"{first[0]}{last}", f"{first}.{last[0]}"])
    email = f"{base}@{domain_of(company)}"
    n = 2
    while email in used:
        email = f"{base}{n}@{domain_of(company)}"
        n += 1
    used.add(email)
    return email


def phone():
    return f"(555) {rng.randint(200, 989)}-{rng.randint(1000, 9999)}"


def ts(day, hmin=8, hmax=18):
    return (f"{day.isoformat()}T{rng.randint(hmin, hmax):02d}:"
            f"{rng.choice([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55]):02d}:00Z")


def rand_day(start, end):
    delta = (end - start).days
    return start + datetime.timedelta(days=rng.randint(0, delta))


def slugify(title):
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")
    return s


# ---------------------------------------------------------------------------
# Blog post generation
# ---------------------------------------------------------------------------

POST_TOPICS = {
    "Engineering": [
        "event-driven architecture", "database sharding", "API versioning",
        "zero-downtime deploys", "observability pipelines", "feature flags",
        "incident response tooling", "schema migrations", "load testing",
        "caching strategies", "service meshes", "queue backpressure",
        "postgres tuning", "frontend performance budgets", "chaos testing",
        "typescript migration", "graphql federation", "rate limiting",
        "secrets management", "container image hygiene", "blue-green releases",
        "distributed tracing", "webhook reliability", "search relevance tuning",
        "data pipeline idempotency", "multi-region failover", "edge caching",
        "accessibility tooling", "monorepo build times", "test flakiness"],
    "Industry Insights": [
        "workflow automation trends", "cloud security posture", "data governance",
        "no-code adoption", "SOC 2 expectations", "vendor consolidation",
        "IT budget planning", "shadow IT", "digital transformation ROI",
        "compliance automation", "remote operations", "procurement modernization",
        "analytics maturity models", "zero trust adoption", "API economies",
        "enterprise integration debt", "audit readiness", "business continuity",
        "supply chain visibility", "identity management"],
    "Customer Success": [
        "approval workflow rollouts", "security operations centers",
        "self-service analytics", "finance close automation", "vendor onboarding",
        "cloud audit readiness", "incident triage", "executive dashboards",
        "procurement automation", "claims processing", "patient intake workflows",
        "logistics exception handling", "franchise reporting", "HR onboarding"],
    "Company News": [
        "annual customer conference", "new Lakeport headquarters expansion",
        "Cascadia tech community sponsorship", "quarterly platform update",
        "partner program launch", "ISO 27001 milestone", "customer advisory board",
        "regional data center", "hackweek results", "sustainability report",
        "developer community program", "university partnership"],
    "Product Launch": [
        "audit trail explorer", "workflow templates gallery", "anomaly alerts",
        "dashboard embedding", "mobile approvals", "SSO enhancements",
        "data connector pack", "report scheduler", "sandbox environments",
        "role delegation", "usage analytics", "compliance report packs"],
    "Engineering Culture": [
        "on-call rotations", "design review rituals", "internal tech talks",
        "mentorship pods", "documentation days", "blameless postmortems",
        "hiring loops", "apprenticeship program", "engineering ladders",
        "hackweek traditions", "pair programming", "RFC processes"],
}

POST_TITLE_PATTERNS = {
    "Engineering": ["Lessons Learned from {T}", "A Practical Guide to {T}",
                    "How We Approach {T} at Meridian", "Inside Meridian: {T}",
                    "What {Y} Taught Us About {T}", "Rethinking {T}",
                    "Notes on {T} from the {P} Team"],
    "Industry Insights": ["The State of {T} in {Y}", "Why {T} Matters in {Y}",
                          "{Y} Outlook: {T}", "Five Questions to Ask About {T}",
                          "A Buyer's Guide to {T}", "What Leaders Get Wrong About {T}"],
    "Customer Success": ["Customer Spotlight: {C} Modernizes {T}",
                         "How {C} Tackled {T} with {P}",
                         "Case Study: {C} and {T}",
                         "From Spreadsheets to {P}: {C} on {T}"],
    "Company News": ["Meridian Announces {T}", "An Update on Our {T}",
                     "Meridian in {Y}: {T}", "Celebrating Our {T}"],
    "Product Launch": ["Introducing {T} for {P}", "Now Available: {T} in {P}",
                       "{P} Gets {T}", "New in {P}: {T}"],
    "Engineering Culture": ["How We Run {T} at Meridian", "Building Better {T}",
                            "A Look Inside Our {T}", "Why We Invest in {T}"],
}

BODY_OPENERS = [
    "At Meridian Systems we spend a lot of time thinking about {t}.",
    "Over the past year our team in Lakeport has been heads-down on {t}.",
    "Few subjects generate as much discussion among our customers as {t}.",
    "When we sat down to plan this quarter, {t} was at the top of the list.",
    "This post shares what we have learned about {t} while building {p}.",
]
BODY_MIDDLES = [
    "We started by interviewing teams across engineering, operations, and customer success to understand where the friction really lives. The pattern was consistent: manual handoffs and unclear ownership slow everything down.",
    "The first iteration was deliberately small. We shipped behind a flag to a handful of design partners, gathered feedback weekly, and rewrote the rough edges before rolling out more broadly.",
    "Along the way we leaned heavily on {p} itself, using dashboards to track adoption and workflow runs to coordinate the rollout. Eating our own cooking kept the feedback loop short.",
    "There were setbacks. An early design assumed clean input data, and reality disagreed. We added validation, clearer error states, and a retry path, and the support ticket volume dropped noticeably.",
    "Security and auditability were non-negotiable, so every change ships with role-based access controls and a complete audit trail out of the box.",
    "We benchmarked against our usual bar: sub-second interactions at the 95th percentile and zero data loss during deploys. Hitting that bar required careful attention to caching and queue design.",
]
BODY_CLOSERS = [
    "We will keep sharing what we learn. If this kind of work sounds interesting, our careers page lists open roles in Lakeport and across the Cascadia region.",
    "Thanks to every customer who gave feedback along the way. If you want to dig deeper, reach out through our contact page and we will set up time with the team.",
    "This is one chapter in a longer journey, and we are excited about what comes next. Watch this space for follow-ups.",
    "As always, we would love to hear how your team handles this. Drop us a note or say hello at our next Lakeport meetup.",
]

TAG_POOL = {
    "Engineering": ["engineering", "architecture", "scalability", "reliability",
                    "devops", "performance", "infrastructure"],
    "Industry Insights": ["industry insights", "trends", "strategy",
                          "enterprise", "research", "best practices"],
    "Customer Success": ["customer success", "case study", "customer spotlight",
                         "ROI", "adoption"],
    "Company News": ["company news", "announcement", "Lakeport", "community",
                     "milestones"],
    "Product Launch": ["product launch", "release", "new features", "platform"],
    "Engineering Culture": ["engineering culture", "teamwork", "career growth",
                            "process", "people"],
}

POST_CATEGORY_WEIGHTS = [
    ("Engineering", 140), ("Industry Insights", 110), ("Customer Success", 100),
    ("Company News", 95), ("Engineering Culture", 85), ("Product Launch", 60),
]


def gen_posts(n, start_id, used_slugs):
    cats = []
    for cat, w in POST_CATEGORY_WEIGHTS:
        cats.extend([cat] * w)
    rng.shuffle(cats)
    cats = cats[:n]
    days = sorted(rand_day(datetime.date(2014, 6, 1), datetime.date(2025, 6, 10))
                  for _ in range(n))
    posts = []
    titles_seen = set()
    for i in range(n):
        cat = cats[i]
        day = days[i]
        for _ in range(40):
            t = rng.choice(POST_TOPICS[cat])
            pat = rng.choice(POST_TITLE_PATTERNS[cat])
            title = pat.format(T=t.title() if "{T}" in pat else t, t=t,
                               Y=day.year, P=rng.choice(PRODUCTS),
                               C=company_name())
            if title not in titles_seen:
                break
        else:
            title = f"{title} ({day.strftime('%B %Y')})"
        titles_seen.add(title)
        slug = slugify(title)
        k = 2
        while slug in used_slugs:
            slug = f"{slugify(title)}-{k}"
            k += 1
        used_slugs.add(slug)
        author_id, author = rng.choice(AUTHORS)
        prod = rng.choice(PRODUCTS)
        body = " ".join([
            rng.choice(BODY_OPENERS).format(t=t, p=prod),
            rng.choice(BODY_MIDDLES).format(t=t, p=prod),
            rng.choice([m for m in BODY_MIDDLES]).format(t=t, p=prod),
            rng.choice(BODY_CLOSERS),
        ])
        excerpt = (f"Notes from the Meridian team on {t}: what worked, "
                   f"what did not, and what we are doing next.")
        tags = rng.sample(TAG_POOL[cat], k=3)
        if rng.random() < 0.5:
            tags.append(prod)
        posts.append({
            "id": start_id + i, "title": title, "slug": slug,
            "author": author, "author_id": author_id, "date": day.isoformat(),
            "category": cat, "excerpt": excerpt, "body": body,
            "tags": json.dumps(tags),
        })
    return posts


# ---------------------------------------------------------------------------
# Contacts / subscribers / testimonials / jobs / services
# ---------------------------------------------------------------------------

CONTACT_SUBJECTS = [
    ("{P} Demo Request",
     "We are a {size}-person {ind} organization evaluating options to modernize our {proc}. Could we schedule a demo of {P} to see how it would fit our environment?"),
    ("Pricing Information for {P}",
     "Our team at {C} is comparing vendors for {proc}. Can you send over pricing tiers for {P} and information about volume discounts?"),
    ("{P} Integration Question",
     "Before we commit, we need to confirm that {P} integrates with our existing stack. Does it support SSO and connectors for our {ind} tooling?"),
    ("Partnership Inquiry",
     "{C} runs a consulting practice serving {ind} clients across the Cascadia region. We would like to discuss joining the Meridian partner program."),
    ("Support Plan Question",
     "We are an existing {P} customer and want to understand the difference between standard and premium support before our renewal."),
    ("Security Questionnaire for {P}",
     "Our security team at {C} is completing vendor due diligence. Could someone walk us through the {P} compliance documentation and SOC 2 report?"),
    ("Migration from Legacy Tooling",
     "We currently manage our {proc} with spreadsheets and email chains. What does a typical migration to {P} look like for a {size}-person company?"),
    ("Training Options",
     "We recently rolled out {P} to two departments and would like details on the Product Training and Certification program for our admins."),
]
INDUSTRIES = ["healthcare", "logistics", "financial services", "manufacturing",
              "retail", "energy", "insurance", "biotech", "legal", "construction"]
PROCESSES = ["approval workflows", "vendor onboarding", "security monitoring",
             "reporting and dashboards", "procurement process", "incident triage",
             "compliance reviews", "invoice approvals", "client intake"]


def gen_contacts(n, start_id, used_emails):
    rows = []
    days = sorted(rand_day(datetime.date(2024, 1, 8), datetime.date(2026, 5, 20))
                  for _ in range(n))
    for i in range(n):
        name = full_name()
        comp = company_name()
        subj_t, msg_t = rng.choice(CONTACT_SUBJECTS)
        prod = rng.choice(PRODUCTS)
        subj = subj_t.format(P=prod, C=comp)
        msg = msg_t.format(P=prod, C=comp, size=rng.choice([40, 80, 120, 250, 400, 900, 1500]),
                           ind=rng.choice(INDUSTRIES), proc=rng.choice(PROCESSES))
        status = rng.choices(["responded", "assigned", "new"], weights=[76, 18, 6])[0]
        rows.append({
            "id": start_id + i, "name": name,
            "email": email_of(name, comp, used_emails), "company": comp,
            "phone": phone(), "subject": subj, "message": msg,
            "submitted_at": ts(days[i]), "source": "Website Contact Form",
            "status": status,
            "assigned_to": rng.choice(ASSIGNEES) if status in ("assigned", "responded") else "",
        })
    return rows


def gen_subscribers(n, start_id, used_emails):
    rows = []
    days = sorted(rand_day(datetime.date(2022, 1, 3), datetime.date(2026, 6, 14))
                  for _ in range(n))
    for i in range(n):
        name = full_name()
        comp = company_name()
        k = rng.choices([1, 2, 3], weights=[35, 45, 20])[0]
        topics = rng.sample(TOPICS, k=k)
        if "blog" not in topics and rng.random() < 0.4:
            topics.append("blog")
        rows.append({
            "id": start_id + i, "email": email_of(name, comp, used_emails),
            "name": name, "company": comp,
            "subscribed_topics": json.dumps(topics),
            "subscribed_at": ts(days[i], 6, 21),
            "active": 1 if rng.random() < 0.93 else 0,
        })
    return rows


TESTIMONIAL_TEXTS = {
    "MeridianFlow": [
        "MeridianFlow cut our {proc} turnaround from days to hours. Approval times dropped {pct}% in the first {tf}, and nothing falls through the cracks anymore.",
        "We replaced a tangle of spreadsheets and email chains with MeridianFlow. Our team processes {num} requests a month now with full visibility at every step.",
        "The visual builder in MeridianFlow meant our operations team automated {proc} without writing a line of code. Adoption was immediate.",
    ],
    "MeridianVault": [
        "MeridianVault gave our security team one view across all our cloud accounts. Mean time to detection improved {pct}% within the first {tf}.",
        "False-positive alerts are down {pct}% since we deployed MeridianVault, and our auditors love the evidence exports at compliance time.",
        "Rolling out MeridianVault ahead of our SOC 2 audit was the best decision we made all year. The audit trail features saved us weeks of prep.",
    ],
    "MeridianLens": [
        "With MeridianLens, our analysts stopped exporting CSVs and started answering questions in minutes. Time-to-insight is down {pct}%.",
        "MeridianLens dashboards became the single source of truth for our leadership team. Reporting that took {num} hours a month is now automatic.",
        "The natural-language querying in MeridianLens means anyone on our team can pull the numbers they need without waiting on the data team.",
    ],
}
ROLES = ["VP of Operations", "CTO", "Director of IT", "CISO", "Head of Analytics",
         "COO", "Operations Manager", "VP of Engineering", "IT Director",
         "Head of Procurement", "Chief Data Officer", "Director of Security"]


def gen_testimonials(n, start_id):
    rows = []
    for i in range(n):
        prod = rng.choice(PRODUCTS)
        text = rng.choice(TESTIMONIAL_TEXTS[prod]).format(
            pct=rng.choice([35, 40, 45, 50, 55, 60, 65, 70, 75, 80]),
            tf=rng.choice(["quarter", "six months", "year"]),
            num=rng.choice([300, 500, 800, 1200, 2000, 20, 40]),
            proc=rng.choice(PROCESSES))
        rows.append({
            "id": start_id + i, "text": text, "author": full_name(),
            "role": rng.choice(ROLES), "company": company_name(),
            "product": prod,
            "rating": rng.choices([5, 4], weights=[70, 30])[0],
        })
    return rows


JOB_DEFS = [
    # (title, department, salary_min, salary_max)
    ("Staff Software Engineer", "Engineering", 170000, 210000),
    ("Backend Engineer, Workflow Platform", "Engineering", 120000, 150000),
    ("Senior Frontend Engineer", "Engineering", 135000, 165000),
    ("Data Engineer", "Engineering", 125000, 155000),
    ("Senior Data Engineer", "Engineering", 145000, 175000),
    ("Security Engineer", "Engineering", 130000, 165000),
    ("Senior Security Engineer", "Engineering", 150000, 185000),
    ("DevOps Engineer", "Engineering", 120000, 150000),
    ("Engineering Manager, Analytics", "Engineering", 165000, 200000),
    ("QA Automation Engineer", "Engineering", 100000, 130000),
    ("Mobile Engineer", "Engineering", 120000, 150000),
    ("Platform Engineer", "Engineering", 125000, 160000),
    ("Technical Writer", "Engineering", 90000, 115000),
    ("Solutions Architect", "Engineering", 140000, 170000),
    ("Database Reliability Engineer", "Engineering", 135000, 170000),
    ("Account Executive, Mid-Market", "Sales", 80000, 110000),
    ("Senior Account Executive", "Sales", 95000, 130000),
    ("Sales Engineer", "Sales", 110000, 145000),
    ("Regional Sales Manager, Cascadia", "Sales", 120000, 160000),
    ("Channel Partnerships Manager", "Sales", 100000, 135000),
    ("Revenue Operations Analyst", "Sales", 85000, 110000),
    ("Enterprise Account Manager", "Sales", 95000, 125000),
    ("Product Marketing Manager", "Marketing", 105000, 135000),
    ("Demand Generation Manager", "Marketing", 95000, 125000),
    ("Events Marketing Coordinator", "Marketing", 65000, 85000),
    ("Brand Designer", "Marketing", 85000, 110000),
    ("Marketing Operations Specialist", "Marketing", 75000, 95000),
    ("SEO & Content Strategist", "Marketing", 80000, 105000),
    ("Customer Success Manager", "Customer Success", 85000, 110000),
    ("Senior Customer Success Manager", "Customer Success", 100000, 130000),
    ("Technical Support Engineer", "Customer Success", 75000, 100000),
    ("Onboarding Specialist", "Customer Success", 70000, 90000),
    ("Customer Education Manager", "Customer Success", 85000, 110000),
]
JOB_LOCATIONS = ["Lakeport, WA (Hybrid)", "Seattle, WA or Lakeport, WA (Hybrid)",
                 "Lakeport, WA or Remote"]
JOB_REQS = {
    "Engineering": ["Strong proficiency in Python or TypeScript",
                    "Experience with distributed systems and cloud infrastructure",
                    "Familiarity with PostgreSQL, Redis, and Kafka",
                    "Experience with Kubernetes and AWS",
                    "Excellent written communication skills",
                    "Bachelor's degree in Computer Science or equivalent experience"],
    "Sales": ["Track record of meeting or exceeding quota",
              "Experience selling B2B SaaS to mid-market or enterprise accounts",
              "Strong discovery and negotiation skills",
              "Familiarity with CRM tooling and structured sales processes",
              "Excellent presentation and communication skills"],
    "Marketing": ["Experience in B2B SaaS marketing",
                  "Strong writing and storytelling skills",
                  "Comfort with analytics and campaign measurement",
                  "Experience partnering with sales and product teams",
                  "Bachelor's degree or equivalent experience"],
    "Customer Success": ["Experience in customer success or technical support for SaaS",
                         "Strong troubleshooting and communication skills",
                         "Ability to translate customer feedback into product insights",
                         "Experience running onboarding or training programs",
                         "Empathy and patience with customers of all technical levels"],
}


def gen_jobs(n, start_id):
    picks = rng.sample(JOB_DEFS, k=n)
    days = sorted(rand_day(datetime.date(2026, 1, 5), datetime.date(2026, 4, 25))
                  for _ in range(n))
    rows = []
    for i, (title, dept, smin, smax) in enumerate(picks):
        prod = rng.choice(PRODUCTS)
        desc = (f"We are looking for a {title} to join our {dept} organization in "
                f"Lakeport and help grow {prod} and the rest of the Meridian "
                f"platform. You will collaborate across engineering, product, and "
                f"customer-facing teams to deliver measurable value to our "
                f"enterprise customers across the Cascadia region and beyond.")
        reqs = rng.sample(JOB_REQS[dept], k=min(5, len(JOB_REQS[dept])))
        exp = rng.choice(["2+", "3+", "5+", "7+"])
        reqs.insert(0, f"{exp} years of relevant professional experience")
        rows.append({
            "id": start_id + i, "title": title, "department": dept,
            "location": rng.choice(JOB_LOCATIONS), "type": "Full-time",
            "posted_date": days[i].isoformat(),
            "salary_min": smin, "salary_max": smax,
            "description": desc, "requirements": json.dumps(reqs),
        })
    return rows


NEW_SERVICES = [
    ("Managed Detection & Response", "Support",
     "Meridian's security operations team monitors your MeridianVault deployment around the clock, triaging alerts, investigating anomalies, and escalating verified incidents to your on-call staff with full context and recommended remediation steps.",
     "Annual subscription", "Ongoing",
     ["24/7 alert monitoring and triage", "Monthly threat landscape briefings",
      "Incident escalation runbooks", "Quarterly detection tuning sessions",
      "Named security operations contact"]),
    ("Analytics Enablement Program", "Training",
     "A structured program that turns your business teams into confident MeridianLens users. We pair curriculum-based training with hands-on dashboard clinics using your organization's real data.",
     "Fixed-price", "4-6 weeks",
     ["Role-based training tracks", "Hands-on dashboard clinics",
      "Governance and data-literacy workshops", "Adoption measurement plan",
      "Train-the-trainer certification"]),
    ("Workflow Health Check", "Consulting",
     "A short, focused engagement that audits your existing MeridianFlow workflows for bottlenecks, redundant approval steps, and error-prone handoffs, delivering a prioritized optimization backlog.",
     "Fixed-price", "1-2 weeks",
     ["Workflow inventory and usage analysis", "Bottleneck and error-rate report",
      "Prioritized optimization backlog", "Quick-win implementation session",
      "Executive readout"]),
    ("Enterprise Architecture Review", "Consulting",
     "Meridian architects evaluate how the platform fits within your broader systems landscape, covering integration patterns, identity, data flows, and disaster-recovery posture.",
     "Time & Materials", "3-5 weeks",
     ["Current-state architecture assessment", "Integration pattern recommendations",
      "Identity and access design review", "Resilience and DR evaluation",
      "Reference architecture documentation"]),
    ("Data Migration Services", "Implementation",
     "Structured migration of historical workflow records, security events, or reporting datasets into the Meridian platform with validation at every step and zero data loss.",
     "Fixed-price", "2-6 weeks",
     ["Source system assessment", "Migration tooling and mapping",
      "Dry-run and validation cycles", "Cutover planning and execution",
      "Post-migration reconciliation report"]),
    ("Dedicated Technical Account Management", "Support",
     "A named technical account manager who knows your environment, coordinates support and product escalations, and meets with your team on a regular cadence to keep your Meridian investment on track.",
     "Annual subscription", "Ongoing",
     ["Named technical account manager", "Quarterly roadmap and health reviews",
      "Priority escalation handling", "Upgrade and release planning",
      "Usage and adoption reporting"]),
    ("Admin Certification Bootcamp", "Training",
     "An intensive certification course for platform administrators covering configuration, access control, monitoring, and troubleshooting across MeridianFlow, MeridianVault, and MeridianLens.",
     "Per-seat or site license", "3 days per cohort",
     ["Instructor-led admin curriculum", "Hands-on lab environment",
      "Certification exam and credential", "Admin community access",
      "Annual recertification path"]),
    ("Custom Reporting & Dashboard Design", "Implementation",
     "Our visualization specialists design and build executive dashboards and operational reports in MeridianLens tailored to your KPIs, branding, and audience.",
     "Time & Materials", "2-4 weeks",
     ["KPI discovery workshops", "Dashboard information design",
      "Build and iteration cycles", "Stakeholder review sessions",
      "Handoff documentation and training"]),
]


def gen_services(start_id):
    rows = []
    for i, (name, cat, desc, model, dur, inc) in enumerate(NEW_SERVICES):
        rows.append({
            "id": start_id + i, "name": name, "category": cat,
            "description": desc, "engagement_model": model,
            "typical_duration": dur, "includes": json.dumps(inc),
        })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

FORBIDDEN = ("alex rivera", "machine learning")


def assert_clean(rows, table):
    for r in rows:
        blob = json.dumps(r).lower()
        for phrase in FORBIDDEN:
            if phrase in blob:
                raise SystemExit(f"forbidden phrase '{phrase}' in new {table} row {r['id']}")


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    counts = {}
    next_id = {}
    for t in TARGETS:
        counts[t] = db.execute(f"SELECT COUNT(*) FROM business_company_{t}").fetchone()[0]
        next_id[t] = db.execute(
            f"SELECT COALESCE(MAX(id),0)+1 FROM business_company_{t}").fetchone()[0]

    used_emails = {r[0] for r in db.execute(
        "SELECT email FROM business_company_subscribers UNION "
        "SELECT email FROM business_company_contacts")}
    used_slugs = {r[0] for r in db.execute("SELECT slug FROM business_company_posts")}

    # Sanity guards for task constraints (fail loudly if base data shifted)
    first_eng = db.execute(
        "SELECT id, author, date FROM business_company_posts "
        "WHERE category='Engineering' ORDER BY id LIMIT 1").fetchone()
    assert first_eng["author"] == "Alex Rivera", "first Engineering post changed!"
    oldest_post = db.execute("SELECT MIN(date) FROM business_company_posts").fetchone()[0]

    new = {}
    new["subscribers"] = gen_subscribers(max(0, TARGETS["subscribers"] - counts["subscribers"]),
                                         next_id["subscribers"], used_emails)
    new["contacts"] = gen_contacts(max(0, TARGETS["contacts"] - counts["contacts"]),
                                   next_id["contacts"], used_emails)
    new["posts"] = gen_posts(max(0, TARGETS["posts"] - counts["posts"]),
                             next_id["posts"], used_slugs)
    new["testimonials"] = gen_testimonials(max(0, TARGETS["testimonials"] - counts["testimonials"]),
                                           next_id["testimonials"])
    new["jobs"] = gen_jobs(max(0, TARGETS["jobs"] - counts["jobs"]), next_id["jobs"])
    new["services"] = gen_services(next_id["services"]) if counts["services"] < TARGETS["services"] else []

    # Constraint assertions on generated data
    for t, rows in new.items():
        assert_clean(rows, t)
    for p in new["posts"]:
        assert p["date"] < oldest_post, f"post {p['id']} dated {p['date']} not older than {oldest_post}"
        assert p["id"] > 10 and p["author"] != "Alex Rivera"

    for t, rows in new.items():
        print(f"{t}: +{len(rows)} -> {counts[t] + len(rows)}")
    total = sum(counts[t] + len(new[t]) for t in TARGETS) + 12 + 3  # + team + products
    print(f"site total (incl. team=12, products=3): {total}")

    if dry:
        for t, rows in new.items():
            for r in rows[:2]:
                print(" ", t, json.dumps(r, default=str)[:150])
        return

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    (BACKUP_DIR / "inserted_ids.json").write_text(json.dumps(
        {t: [r["id"] for r in rows] for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        if not rows:
            continue
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO business_company_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])
    db.commit()

    # Rebuild external-content FTS indexes for touched tables that have one
    for t in ("posts", "subscribers", "testimonials"):
        fts = f"fts_business_company_{t}"
        if db.execute("SELECT name FROM sqlite_master WHERE name=?", (fts,)).fetchone():
            db.execute(f"INSERT INTO [{fts}]([{fts}]) VALUES('rebuild')")
            db.commit()
            print(f"rebuilt {fts}")

    print(f"inserted; rollback ids at {BACKUP_DIR}/inserted_ids.json")


if __name__ == "__main__":
    main()
