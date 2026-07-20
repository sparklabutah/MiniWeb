"""Expand university-academic (Meridian State / UW CSE portal) base data.

The site ships with tiny collections (10 courses, 8 faculty, 5 alumni,
5 events, 5 users), which makes its search/filter/extract macros trivial.
This adds deterministic (seeded) synthetic rows reusing the existing
vocabulary (CSE course codes, Gates/Allen Center offices, cs.washington.edu
emails, Lakeport/Meridian/Cascadia companies, the five research-area slugs).

Render-safety ceiling: /courses, /faculty, /alumni and /events render the
FULL table with no pagination, so those collections are capped below ~500
rows each (courses 490, faculty 200, alumni 490, events 490).  The remaining
bulk goes into `users` (student/alumni portal accounts -> 3,340 rows), which
has no list page (per-netid lookups only) and is consistent with the
department stats (1,200 undergrads + 450 grads).

Task-answer protection ("What course is Dr. Balazinska teaching?" ->
"Introduction to Data Management"):
  * no generated row ever contains the string "Balazinska" (asserted);
  * no new course is titled or described "Data Management" (asserted), so
    cse-344 stays the unique hit;
  * new event dates are all AFTER 2026-01-22 so the homepage "upcoming
    events" top-3 and featured courses are unchanged.

Insert-only -- existing rows are never touched.  Inserted ids are recorded
in data/backups/university-academic-expansion-2026-07-20/inserted_ids.json.

Usage: python scripts/expand_university_academic_data.py [--dry-run]
"""
import datetime
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
BACKUP_DIR = ROOT / "data" / "backups" / "university-academic-expansion-2026-07-20"

rng = random.Random(20260720)

# --------------------------------------------------------------------------
# Targets (final row counts)
# --------------------------------------------------------------------------
TARGET = {"courses": 490, "faculty": 200, "alumni": 490, "events": 490,
          "users": 3340}

FORBIDDEN = ("balazinska", "data management")  # never in generated text

# --------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------
FIRST = [
    "Aaron", "Alan", "Alice", "Amara", "Amir", "Andrea", "Anil", "Anita",
    "Arjun", "Astrid", "Benjamin", "Bianca", "Brian", "Camille", "Carla",
    "Carlos", "Caroline", "Cedric", "Chandra", "Claire", "Colin", "Dana",
    "Daniela", "Darius", "Deepa", "Diego", "Dmitri", "Elena", "Elias",
    "Elif", "Erik", "Esther", "Farah", "Felix", "Fiona", "Gabriel", "Grace",
    "Greta", "Hannah", "Haruto", "Hector", "Ingrid", "Irene", "Ivan",
    "Jasmine", "Javier", "Jonas", "Jorge", "Julia", "Kavya", "Keiko",
    "Kenji", "Lars", "Laura", "Leila", "Liam", "Lucia", "Marco", "Maren",
    "Mateo", "Maya", "Mei", "Mikhail", "Nadia", "Naomi", "Nathan", "Nina",
    "Noor", "Olga", "Omar", "Paulo", "Petra", "Priyanka", "Rafael",
    "Renata", "Rohan", "Rosa", "Samir", "Simone", "Stefan", "Tariq",
    "Tomas", "Uma", "Vera", "Victor", "Wei", "Xin", "Yara", "Yusuf",
    "Zainab", "Zoe",
]
LAST = [
    "Abbott", "Acharya", "Adeyemi", "Aguilar", "Ahmed", "Almeida",
    "Andersson", "Arnold", "Baptiste", "Barnes", "Becker", "Bergman",
    "Bhatt", "Blake", "Bowman", "Brandt", "Bryant", "Calloway", "Cardoso",
    "Carter", "Castillo", "Chandran", "Chowdhury", "Costa", "Crawford",
    "Cruz", "Dawson", "Delgado", "Desai", "Duarte", "Dubois", "Ellington",
    "Emerson", "Farrell", "Fischer", "Fleming", "Fontaine", "Foster",
    "Fujimoto", "Gallagher", "Garrett", "Gustafsson", "Haddad", "Hansen",
    "Harmon", "Hartley", "Hayashi", "Henderson", "Hoffman", "Holloway",
    "Huang", "Ibrahim", "Iyer", "Jansen", "Jensen", "Kapoor", "Kaur",
    "Keller", "Khoury", "Kimura", "Krishnan", "Kumar", "Lindqvist",
    "Lombardi", "Mahoney", "Marchetti", "Mbeki", "McAllister", "Mehta",
    "Mercer", "Moreau", "Moreno", "Nakamura", "Navarro", "Nilsson",
    "Novak", "Okafor", "Oliveira", "Osei", "Palmer", "Pereira", "Petrov",
    "Quinn", "Ramirez", "Rao", "Reyes", "Romano", "Rossi", "Sandoval",
    "Sato", "Schmidt", "Schneider", "Sharpe", "Silva", "Sorensen", "Soto",
    "Sullivan", "Takahashi", "Thompson", "Vargas", "Vasquez", "Vega",
    "Venkatesan", "Vogel", "Wallace", "Weber", "Whitfield", "Winters",
    "Yamamoto", "Yilmaz", "Zhang", "Zielinski",
]

AREAS = ["systems", "machine-learning", "hci", "security",
         "programming-languages"]

AREA_TERMS = {
    "systems": ["systems", "distributed systems", "operating systems",
                "cloud computing", "networking", "databases",
                "storage systems", "edge computing"],
    "machine-learning": ["machine learning", "deep learning",
                         "natural language processing", "computer vision",
                         "reinforcement learning", "data science",
                         "robotics"],
    "hci": ["hci", "accessibility", "social computing",
            "ubiquitous computing", "visualization", "computing education"],
    "security": ["security", "cryptography", "network security", "privacy",
                 "software security"],
    "programming-languages": ["programming languages", "type systems",
                              "software verification", "program analysis",
                              "compilers", "software engineering"],
}

TOPICS = {
    "systems": [
        "Operating Systems", "Distributed Computing", "Cloud Infrastructure",
        "Computer Networks", "Database Systems", "Storage Systems",
        "Systems Programming", "Performance Engineering",
        "Datacenter Systems", "Embedded Systems", "Real-Time Systems",
        "Network Protocols", "Virtualization", "Fault-Tolerant Computing",
        "Edge Computing", "Serverless Computing", "Stream Processing",
        "Query Processing", "Transaction Processing", "Big Data Systems",
        "Operating System Kernels", "Wireless Networking",
        "Systems for Machine Learning", "Caching and Memory Hierarchies",
    ],
    "machine-learning": [
        "Deep Learning", "Natural Language Processing", "Computer Vision",
        "Reinforcement Learning", "Probabilistic Modeling",
        "Statistical Learning Theory", "Neural Networks",
        "Generative Models", "Applied Data Science", "Robotics",
        "Speech Processing", "Information Retrieval", "Recommender Systems",
        "Bayesian Methods", "Graph Learning", "Responsible AI",
        "Knowledge Representation", "Multi-Agent Systems",
        "Computational Biology", "Optimization Methods",
        "Sequence Modeling", "Vision and Language",
    ],
    "hci": [
        "Interaction Design", "Accessible Technology",
        "Ubiquitous Computing", "Social Computing", "Data Visualization",
        "User Research Methods", "Mobile Interface Design",
        "Augmented Reality Interfaces", "Design Prototyping",
        "Computing Education", "Wearable Computing", "Voice Interfaces",
        "Human-AI Interaction", "Interactive Systems",
        "Design of Everyday Software", "Games and Playable Media",
    ],
    "security": [
        "Applied Cryptography", "Network Defense", "Software Security",
        "Privacy-Preserving Computation", "Malware Analysis",
        "Web Security", "Usable Security", "Hardware Security",
        "Blockchain Systems", "Digital Forensics",
        "Secure Protocol Design", "Threat Modeling",
        "Wireless and Mobile Security", "Security Analytics",
    ],
    "programming-languages": [
        "Compiler Construction", "Type Systems", "Program Analysis",
        "Software Verification", "Functional Programming",
        "Concurrent Programming", "Program Synthesis",
        "Domain-Specific Languages", "Runtime Systems",
        "Software Engineering", "Formal Semantics", "Automated Reasoning",
        "Software Testing", "Build Systems and Tooling",
    ],
    "": [
        "Computational Thinking", "Web Programming", "Discrete Structures",
        "Foundations of Computing", "Programming Tools",
        "Digital Logic Design", "Problem Solving with Programming",
        "Software Design", "Technical Communication for Computer Science",
        "Data Programming", "Computer Ethics", "Linear Algebra for Computing",
        "Algorithms", "Theory of Computation", "Numerical Computing",
        "Competitive Programming", "Hardware-Software Interface",
        "Professional Practice in Computing", "Entrepreneurship in Computing",
    ],
}

COMPANIES = [
    ("Microsoft", "Redmond, WA"), ("Amazon", "Seattle, WA"),
    ("Google", "Seattle, WA"), ("Meta", "Bellevue, WA"),
    ("Apple", "Seattle, WA"), ("Stripe", "Seattle, WA"),
    ("Meridian Systems", "Lakeport, WA"),
    ("Cascadia Federal Credit Union", "Lakeport, WA"),
    ("Lakeport Community Bank", "Lakeport, WA"),
    ("Cascadia Mutual Insurance", "Lakeport, WA"),
    ("Tableau", "Seattle, WA"), ("Zillow", "Seattle, WA"),
    ("Expedia Group", "Seattle, WA"), ("Redfin", "Seattle, WA"),
    ("Boeing", "Everett, WA"), ("T-Mobile", "Bellevue, WA"),
    ("Nordstrom Technology", "Seattle, WA"), ("Qualtrics", "Seattle, WA"),
    ("Salesforce", "San Francisco, CA"), ("Databricks", "San Francisco, CA"),
    ("NVIDIA", "Santa Clara, CA"), ("Duolingo", "Pittsburgh, PA"),
]

JOB_TITLES = ["Software Engineer", "Senior Software Engineer",
              "Staff Software Engineer", "Engineering Manager",
              "Data Scientist", "Product Manager", "Research Scientist",
              "Site Reliability Engineer", "Security Engineer",
              "Machine Learning Engineer", "UX Engineer",
              "Principal Engineer", "Solutions Architect",
              "Technical Program Manager"]

EXT_UNIS = ["Stanford", "MIT", "Carnegie Mellon", "UC Berkeley", "Cornell",
            "Princeton", "Georgia Tech", "UT Austin", "UBC", "ETH Zurich",
            "Oxford", "University of Michigan", "UCLA", "UIUC"]

LABS = ["Systems Research Lab", "Cloud & Networking Lab", "AI & ML Lab",
        "NLP Research Group", "DUB Group", "Accessibility Lab",
        "Security Research Lab", "Privacy & Cryptography Group",
        "PLSE Group", "Verification Lab"]

EXISTING_EVENT_REFS = [
    "CSE Alumni Meetup - Seattle (2026-03-15)",
    "CSE Annual Career Fair (2026-01-22)",
    "DubHacks 2025 (mentor)",
]

SENIOR_PROJECTS = [
    "Distributed cache warm-up scheduler for microservices",
    "Accessibility audit toolkit for campus web apps",
    "Real-time transit arrival predictor for Puget Sound buses",
    "Peer code review recommendation engine",
    "Low-power mesh network for wildfire sensors",
    "Sign-language recognition with on-device vision models",
    "Static analyzer for concurrency bugs in Go services",
    "Privacy-preserving fitness data aggregator",
    "Course planner with degree-requirement solver",
    "Serverless image processing pipeline benchmark",
    "Interactive visualizer for spanning-tree protocols",
    "Automated grading harness for systems assignments",
    "Encrypted group chat with deniable authentication",
    "Compiler playground for a teaching language",
    "Crowd-sourced campus noise map",
    "Recommendation system for student club discovery",
    "Fault-injection framework for replicated key-value stores",
    "Gesture-controlled presentation assistant",
    "Type-checked configuration language for CI pipelines",
    "Drone-based rooftop solar site survey tool",
]


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def j(x):
    return json.dumps(x, ensure_ascii=False)


def check_clean(*texts):
    for t in texts:
        low = str(t).lower()
        for bad in FORBIDDEN:
            assert bad not in low, f"forbidden term {bad!r} in {t!r}"


def make_name_pool(existing_names):
    pool = [(f, l) for f in FIRST for l in LAST]
    rng.shuffle(pool)
    used = {n.lower() for n in existing_names}
    for f, l in pool:
        full = f"{f} {l}"
        if full.lower() in used:
            continue
        used.add(full.lower())
        yield f, l


def uniq_slug(base, taken):
    s = base
    n = 2
    while s in taken:
        s = f"{base}{n}"
        n += 1
    taken.add(s)
    return s


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------

def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    ex_courses = [dict(r) for r in db.execute(
        "SELECT * FROM university_academic_courses")]
    ex_faculty = [dict(r) for r in db.execute(
        "SELECT * FROM university_academic_faculty")]
    ex_alumni = [dict(r) for r in db.execute(
        "SELECT * FROM university_academic_alumni")]
    ex_events = [dict(r) for r in db.execute(
        "SELECT * FROM university_academic_events")]
    ex_users = [dict(r) for r in db.execute(
        "SELECT * FROM university_academic_users")]

    existing_people = ([f["name"].replace("Dr. ", "") for f in ex_faculty]
                       + [a["name"] for a in ex_alumni]
                       + [u["display_name"] for u in ex_users]
                       + ["Robert Kim", "Magdalena Balazinska"])
    names = make_name_pool(existing_people)
    taken_netids = {u["net_id"] for u in ex_users}
    taken_slugs = {a["linkedin"].rsplit("/", 1)[-1] for a in ex_alumni}
    taken_emails = {f["email"] for f in ex_faculty}

    # ---------------- faculty ----------------
    n_fac = TARGET["faculty"] - len(ex_faculty)
    fac_rows = []
    titles_w = (["Professor"] * 22 + ["Associate Professor"] * 25
                + ["Assistant Professor"] * 22 + ["Teaching Professor"] * 10
                + ["Assistant Teaching Professor"] * 8
                + ["Professor Emeritus"] * 6 + ["Affiliate Professor"] * 7)
    phone_n = 2209
    for i in range(n_fac):
        f, l = next(names)
        full = f"Dr. {f} {l}"
        title = rng.choice(titles_w)
        if title == "Assistant Professor":
            joined = rng.randint(2018, 2025)
            pubs = rng.randint(8, 40)
        elif title == "Associate Professor":
            joined = rng.randint(2010, 2019)
            pubs = rng.randint(40, 110)
        elif title == "Professor":
            joined = rng.randint(1988, 2014)
            pubs = rng.randint(80, 260)
        elif title == "Professor Emeritus":
            joined = rng.randint(1975, 1995)
            pubs = rng.randint(120, 300)
        else:
            joined = rng.randint(2005, 2023)
            pubs = rng.randint(5, 60)
        area = rng.choice(AREAS)
        terms = AREA_TERMS[area]
        ras = [terms[0]] + rng.sample(terms[1:], rng.randint(1, 2))
        netid = uniq_slug((f[0] + l).lower(), taken_netids)
        email = f"{netid}@cs.washington.edu"
        assert email not in taken_emails
        taken_emails.add(email)
        bio_t = rng.choice([
            "Works on {a} and {b}. Teaches core and advanced courses in the area.",
            "Leads research on {a}, with recent projects spanning {b}.",
            "Research focuses on {a}; frequent collaborator with the {lab}.",
            "Studies {a} and {b}. Advises undergraduate research through the {lab}.",
        ]).format(a=ras[0], b=ras[-1], lab=rng.choice(LABS))
        row = {
            "id": f"fac-{len(ex_faculty) + i + 1:03d}",
            "name": full, "title": title, "email": email,
            "office": f"{rng.choice(['Gates Center', 'Allen Center'])} {rng.randint(100, 599)}",
            "phone": f"(206) 543-{phone_n}",
            "research_areas": j(ras), "bio": bio_t,
            "publications_count": pubs, "joined_year": joined,
            "homepage": f"https://homes.cs.washington.edu/~{netid}/",
        }
        phone_n += 1
        check_clean(*row.values())
        fac_rows.append(row)

    all_faculty = ex_faculty + fac_rows  # dicts with name + joined_year
    instructor_pool = [f["name"] for f in all_faculty]

    # ---------------- courses ----------------
    n_crs = TARGET["courses"] - len(ex_courses)
    used_nums = {int(c["code"].split()[1]) for c in ex_courses}
    avail = [n for n in range(100, 600) if n not in used_nums]
    nums = sorted(rng.sample(avail, n_crs))
    used_titles = {c["title"].lower() for c in ex_courses}
    crs_rows = []
    all_codes = [c["code"] for c in ex_courses]
    for n in nums:
        if n < 300:
            level, area = "introductory", rng.choice(["", ""] + AREAS)
            patterns = ["Introduction to {t}", "Foundations of {t}", "{t}",
                        "Fundamentals of {t}"]
            credits = rng.choice([4, 4, 4, 5, 3])
            max_e = rng.randint(120, 350)
        elif n < 400:
            level, area = "intermediate", rng.choice(AREAS + [""])
            patterns = ["{t}", "Intermediate {t}", "Principles of {t}"]
            credits = rng.choice([4, 4, 4, 3])
            max_e = rng.randint(80, 200)
        elif n < 500:
            level, area = "advanced", rng.choice(AREAS)
            patterns = ["{t}", "Advanced {t}", "Topics in {t}"]
            credits = rng.choice([4, 4, 4, 3])
            max_e = rng.randint(40, 140)
        else:
            level, area = "advanced", rng.choice(AREAS)
            patterns = ["Graduate {t}", "Seminar in {t}",
                        "Advanced Topics in {t}", "Research Methods in {t}"]
            credits = rng.choice([4, 4, 3, 2, 1])
            max_e = rng.randint(15, 60)
        topic_pool = TOPICS[area] if area else TOPICS[""]
        title = None
        for _ in range(60):
            cand = rng.choice(patterns).format(t=rng.choice(topic_pool))
            if cand.lower() not in used_titles:
                title = cand
                break
        if title is None:  # deterministic fallback
            title = f"Special Topics in Computing ({n})"
        used_titles.add(title.lower())
        prereqs = []
        if n >= 300:
            lower = [c for c in all_codes if int(c.split()[1]) < n]
            if lower:
                prereqs = sorted(rng.sample(lower, min(len(lower), rng.randint(0, 2))))
        desc = rng.choice([
            "Covers {t} in depth, including core models, practical techniques, and current research directions. Weekly programming assignments and a final project.",
            "A hands-on study of {t}. Students design, build, and evaluate working systems while reading foundational and recent papers.",
            "Concepts and practice of {t}: theory, tools, and case studies drawn from industry and research. Includes labs and a team project.",
            "Explores {t} with an emphasis on rigorous foundations and real-world applications. Problem sets, labs, and an open-ended final assignment.",
        ]).format(t=title.split("(")[0].strip().lower())
        quarters = rng.choice([["autumn"], ["winter"], ["spring"],
                               ["autumn", "spring"], ["winter", "spring"],
                               ["autumn", "winter"], ["autumn", "winter", "spring"],
                               ["spring", "summer"]])
        row = {
            "id": f"cse-{n}", "code": f"CSE {n}", "title": title,
            "credits": credits, "level": level, "description": desc,
            "prerequisites": j(prereqs), "instructor": rng.choice(instructor_pool),
            "quarters_offered": j(quarters), "max_enrollment": max_e,
            "research_area": area,
        }
        check_clean(*row.values())
        crs_rows.append(row)
        all_codes.append(row["code"])

    # ---------------- events ----------------
    n_evt = TARGET["events"] - len(ex_events)
    # All dates strictly after 2026-01-22 so the homepage top-3 upcoming
    # events (2025-10-18, 2025-11-06, 2026-01-22) are unchanged.
    start = datetime.date(2026, 1, 26)
    span = (datetime.date(2027, 6, 30) - start).days
    type_plan = (["seminar"] * 200 + ["colloquium"] * 60 + ["workshop"] * 50
                 + ["info_session"] * 40 + ["thesis_defense"] * 45
                 + ["lecture"] * 30 + ["alumni_meetup"] * 25
                 + ["celebration"] * 15 + ["career_fair"] * 10
                 + ["hackathon"] * 10)
    assert len(type_plan) == n_evt
    rng.shuffle(type_plan)
    evt_rows = []
    all_topics = [t for lst in TOPICS.values() for t in lst]
    cities = ["Seattle", "Bellevue", "Portland", "San Francisco", "New York",
              "Lakeport", "Vancouver BC", "Boston", "Austin", "Chicago"]
    rooms = ["Gates Center 271", "Gates Center 371", "Allen Center Atrium",
             "Gates Center Zillow Commons", "Allen Center 305",
             "HUB Ballroom, University of Washington", "Kane Hall 130", "Zoom (online)"]
    for i, etype in enumerate(type_plan):
        d = start + datetime.timedelta(days=rng.randint(0, span))
        date = d.isoformat()
        end_date, companies, sponsors = "", "", ""
        featured, speaker, keynote = "", "", ""
        reg, tags = 0, []
        topic = rng.choice(all_topics)
        if etype == "seminar":
            lab = rng.choice(LABS)
            title = f"{lab} Seminar: {topic}"
            desc = f"Weekly research seminar of the {lab}. This week: {topic.lower()} — recent results, open problems, and work-in-progress talks."
            organizer, time_s = lab, "12:30 PM - 1:20 PM"
            att = rng.randint(18, 60)
            tags = ["seminar", "research"]
            speaker = f"Dr. {' '.join(next(names))}" if rng.random() < 0.5 else ""
        elif etype == "colloquium":
            f, l = next(names)
            uni = rng.choice(EXT_UNIS)
            title = f"CSE Colloquium: {topic}"
            desc = f"Departmental colloquium on {topic.lower()}, with a survey of the state of the art and directions for the next decade. Open to all students and faculty."
            organizer, time_s = "CSE Colloquium Committee", "3:30 PM - 4:30 PM"
            att = rng.randint(60, 180)
            speaker = f"Dr. {f} {l} ({uni})"
            tags = ["colloquium", "research"]
        elif etype == "workshop":
            title = f"Workshop: Hands-on {topic}"
            desc = f"Interactive workshop introducing {topic.lower()} through guided exercises. Laptops required; no prior experience needed. Space is limited."
            organizer = rng.choice(["CSE Student Affairs", rng.choice(LABS),
                                    "GEN1 @ CSE", "ACM Student Chapter"])
            time_s = "5:00 PM - 7:00 PM"
            att, reg = rng.randint(25, 80), 1
            tags = ["workshop", "hands-on"]
        elif etype == "info_session":
            comp = rng.choice(COMPANIES)[0]
            title = f"{comp} Info Session"
            desc = f"Engineers and recruiters from {comp} discuss internships, new-grad roles, and their current technical stack. Bring your resume — food provided."
            organizer, time_s = "CSE Career Services", "6:00 PM - 7:30 PM"
            att, reg = rng.randint(40, 150), 1
            companies = j([comp])
            tags = ["career", "recruiting"]
        elif etype == "thesis_defense":
            f, l = next(names)
            title = f"Ph.D. Defense: {f} {l} — {topic}"
            desc = f"Public dissertation defense on {topic.lower()}. All members of the university community are welcome to attend the open portion."
            organizer, time_s = "Graduate Program Office", "10:00 AM - 12:00 PM"
            att = rng.randint(15, 45)
            speaker = f"{f} {l}"
            tags = ["defense", "graduate"]
        elif etype == "lecture":
            f, l = next(names)
            uni = rng.choice(EXT_UNIS)
            title = f"Distinguished Lecture: {topic}"
            desc = f"Distinguished lecture series talk on {topic.lower()}: what we have learned, what remains hard, and why it matters. Reception to follow in the Allen Center Atrium."
            organizer, time_s = "CSE Distinguished Lecture Series", "3:30 PM - 5:00 PM"
            att = rng.randint(120, 400)
            featured = f"Dr. {f} {l} ({uni})"
            tags = ["lecture", "distinguished-speaker"]
        elif etype == "alumni_meetup":
            city = rng.choice(cities)
            title = f"CSE Alumni Meetup - {city} ({d.year})"
            desc = f"Casual networking evening for CSE alumni in the {city} area. Reconnect with classmates, meet current students, and hear a short department update."
            organizer, time_s = "CSE Alumni Relations", "6:30 PM - 9:00 PM"
            att, reg = rng.randint(30, 120), 1
            tags = ["alumni", "networking"]
        elif etype == "celebration":
            title = rng.choice([
                f"CSE Graduation Celebration {d.year}",
                f"Undergraduate Research Showcase {d.year}",
                f"Women in CSE {rng.choice(['Winter', 'Spring', 'Autumn'])} Social {d.year}",
                f"CSE Awards Night {d.year}",
                f"New Student Welcome {d.year}",
            ])
            desc = "Departmental celebration with student awards, posters, and remarks from faculty and alumni. Family and friends welcome."
            organizer, time_s = "CSE Student Affairs", "4:00 PM - 6:30 PM"
            att = rng.randint(100, 500)
            tags = ["celebration", "community"]
        elif etype == "career_fair":
            title = f"CSE {rng.choice(['Winter', 'Spring', 'Autumn'])} Career Fair {d.year}"
            desc = "Companies recruiting for internships and full-time roles in software engineering, data science, and product roles. Open to all CSE students and alumni."
            organizer, time_s = "CSE Career Services", "10:00 AM - 4:00 PM"
            att, reg = rng.randint(400, 900), 1
            picks = rng.sample(COMPANIES, 6)
            companies = j([c[0] for c in picks])
            tags = ["career", "recruiting", "networking"]
        else:  # hackathon
            title = f"{rng.choice(['DubHacks', 'HuskyHacks', 'Allen School Hack Night'])} {d.year} ({d.strftime('%b')})"
            desc = "Student hackathon: form a team, build something over 24 hours, and demo to judges. Workshops, mentors, prizes, and free food."
            organizer, time_s = "DubHacks Student Organization", f"6:00 PM ({d.strftime('%b %d')}) - 6:00 PM ({(d + datetime.timedelta(days=1)).strftime('%b %d')})"
            att, reg = rng.randint(150, 600), 1
            end_date = (d + datetime.timedelta(days=1)).isoformat()
            sponsors = j([c[0] for c in rng.sample(COMPANIES, 4)])
            tags = ["hackathon", "coding", "competition"]
        row = {
            "id": f"evt-{len(ex_events) + i + 1:03d}", "title": title,
            "type": etype, "date": date, "time": time_s,
            "location": rng.choice(rooms) if etype != "alumni_meetup" else f"{rng.choice(['Rooftop Bar', 'Brewpub', 'Conference Center'])}, {title.split(' - ')[-1].split(' (')[0]}",
            "description": desc, "organizer": organizer,
            "registration_required": reg, "attendee_count": att,
            "companies_attending": companies, "tags": j(tags),
            "end_date": end_date, "sponsors": sponsors,
            "featured_speaker": featured, "speaker": speaker,
            "keynote": keynote,
        }
        check_clean(*row.values())
        evt_rows.append(row)

    # ---------------- alumni ----------------
    n_al = TARGET["alumni"] - len(ex_alumni)
    al_rows = []
    year_pool = list(range(1985, 2024))
    weights = [1 + max(0, y - 2000) * 0.25 for y in year_pool]
    for i in range(n_al):
        f, l = next(names)
        full = f"{f} {l}"
        gy = rng.choices(year_pool, weights=weights)[0]
        degree = rng.choices(
            ["B.S. Computer Science", "M.S. Computer Science",
             "Ph.D. Computer Science"], weights=[72, 18, 10])[0]
        eligible = [fa["name"] for fa in all_faculty
                    if fa["joined_year"] <= gy - 1]
        advisor = rng.choice(eligible) if eligible and rng.random() < 0.6 else ""
        comp, loc = rng.choice(COMPANIES)
        pos = {"title": rng.choice(JOB_TITLES), "company": comp,
               "location": loc,
               "start_year": min(2025, gy + rng.randint(0, 6))}
        ach = []
        if rng.random() < 0.35:
            ach.append(f"Dean's List {gy - rng.randint(1, 3)}-{gy}")
        if rng.random() < 0.30:
            ach.append(f"TA for {rng.choice(all_codes)} "
                       f"({rng.choice(['Autumn', 'Winter', 'Spring'])} {gy - rng.randint(0, 2)})")
        if rng.random() < 0.20:
            ach.append(rng.choice([
                "DubHacks finalist", "Undergraduate Research Award",
                "ACM ICPC regional competitor", "Husky 100",
                f"Undergraduate Research Assistant, {rng.choice(LABS)}"]))
        slug = uniq_slug((f + l).lower(), taken_slugs)
        row = {
            "id": f"alum-{len(ex_alumni) + i + 1:03d}", "root_user_id": 0,
            "name": full, "graduation_year": gy, "degree": degree,
            "advisor": advisor,
            "senior_project": rng.choice(SENIOR_PROJECTS),
            "current_position": j(pos),
            "linkedin": f"linkedin.com/in/{slug}",
            "notable_achievements": j(ach),
            "alumni_donor": 1 if rng.random() < 0.35 else 0,
            "last_event_attended": rng.choice(EXISTING_EVENT_REFS) if rng.random() < 0.45 else "",
        }
        check_clean(*row.values())
        al_rows.append(row)

    # ---------------- users ----------------
    n_us = TARGET["users"] - len(ex_users)
    role_plan = ["student"] * 1650 + ["alumni"] * 1650 + ["faculty_affiliate"] * 35
    assert len(role_plan) == n_us
    rng.shuffle(role_plan)
    us_rows = []
    for i, role in enumerate(role_plan):
        f, l = next(names)
        full = f"{f} {l}"
        netid = uniq_slug((f[0] + l).lower(), taken_netids)
        honors, advisor, affiliation = "", "", ""
        if role == "student":
            degree = rng.choices(
                ["B.S. Computer Science", "M.S. Computer Science",
                 "Ph.D. Computer Science"], weights=[73, 16, 11])[0]
            enrolled = rng.randint(2019, 2025) if degree.startswith("Ph.D.") else rng.randint(2022, 2025)
            gy = 0
            if degree.startswith("Ph.D."):
                advisor = rng.choice(instructor_pool)
        elif role == "alumni":
            degree = rng.choices(
                ["B.S. Computer Science", "M.S. Computer Science",
                 "Ph.D. Computer Science"], weights=[72, 18, 10])[0]
            gy = rng.choices(year_pool, weights=weights)[0]
            enrolled = gy - {"B": 4, "M": 2, "P": 6}[degree[0]]
            if rng.random() < 0.18:
                honors = rng.choice(["cum laude", "magna cum laude",
                                     "summa cum laude"])
            if rng.random() < 0.4:
                eligible = [fa["name"] for fa in all_faculty
                            if fa["joined_year"] <= gy - 1]
                if eligible:
                    advisor = rng.choice(eligible)
        else:
            degree = f"M.S. Computer Science ({rng.choice(EXT_UNIS)})"
            gy, enrolled = 0, 0
            affiliation = rng.choice([
                "Adjunct Lecturer, CSE", "Industry Advisory Board, CSE",
                "Visiting Scholar, CSE", "Research Affiliate, CSE"])
        login = datetime.datetime(2025, 1, 1) + datetime.timedelta(
            minutes=rng.randint(0, 555 * 24 * 60))
        row = {
            "id": f"uw-u{len(ex_users) + i + 1:03d}", "root_user_id": 0,
            "net_id": netid, "display_name": full,
            "email": f"{netid}@uw.edu", "role": role, "degree": degree,
            "graduation_year": gy, "enrolled_year": enrolled,
            "advisor": advisor, "honors": honors,
            "last_login": login.strftime("%Y-%m-%dT%H:%M:00Z"),
            "affiliation": affiliation,
        }
        check_clean(*row.values())
        us_rows.append(row)

    # ---------------- summary / insert ----------------
    plan = {"courses": crs_rows, "faculty": fac_rows, "alumni": al_rows,
            "events": evt_rows, "users": us_rows}
    print("Rows to insert:")
    for k, v in plan.items():
        print(f"  {k:8s} +{len(v):5d}  (existing {len({'courses': ex_courses, 'faculty': ex_faculty, 'alumni': ex_alumni, 'events': ex_events, 'users': ex_users}[k])})")

    # global safety: Balazinska untouched
    assert not any("balazinska" in json.dumps(r).lower()
                   for rows in plan.values() for r in rows)

    if dry:
        print("\n--dry-run: no changes written. Samples:")
        for k, v in plan.items():
            print(f"\n[{k}]")
            for r in v[:2]:
                print(" ", json.dumps(r, ensure_ascii=False)[:300])
        db.close()
        return

    def ins(table, rows):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})",
            [tuple(r[c] for c in cols) for r in rows])

    ins("university_academic_courses", crs_rows)
    ins("university_academic_faculty", fac_rows)
    ins("university_academic_alumni", al_rows)
    ins("university_academic_events", evt_rows)
    ins("university_academic_users", us_rows)

    # FTS sync (courses has an FTS5 index)
    db.execute("INSERT INTO fts_university_academic_courses"
               "(fts_university_academic_courses) VALUES('rebuild')")
    db.commit()

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    with open(BACKUP_DIR / "inserted_ids.json", "w") as fh:
        json.dump({f"university_academic_{k}": [r["id"] for r in v]
                   for k, v in plan.items()}, fh, indent=1)

    total = db.execute(
        "SELECT (SELECT COUNT(*) FROM university_academic_courses)"
        " + (SELECT COUNT(*) FROM university_academic_faculty)"
        " + (SELECT COUNT(*) FROM university_academic_alumni)"
        " + (SELECT COUNT(*) FROM university_academic_events)"
        " + (SELECT COUNT(*) FROM university_academic_users)"
        " + (SELECT COUNT(*) FROM university_academic_departments)").fetchone()[0]
    print(f"\nInserted. Site total rows now: {total}")
    print(f"Backup: {BACKUP_DIR / 'inserted_ids.json'}")
    db.close()


if __name__ == "__main__":
    main()
