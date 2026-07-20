"""Expand course-sites-classrooms (EduPortal LMS) base data.

The LMS ships with 5 courses / 5 users / 10 assignments / 15 discussions /
20 submissions (55 rows), which makes the catalog, gradebooks, and discussion
boards nearly empty. Adds a deterministic (seeded) professional-development
catalog: ~45 new courses across 9 departments, ~350 new users (instructors +
students), and per-course assignments, discussions (with JSON replies), and
graded submissions, bringing the site total above 5000 rows.

Constraints honored (insert-only, never UPDATE/DELETE):
- Course 3 "Introduction to Data Visualization" is left completely untouched:
  no new assignments, discussions, or submissions reference course_id=3, no
  new course reuses its title, and its enrolled_students list is unchanged.
- Existing users (ids 1-5, incl. main user alex_rivera) are never enrolled in
  new courses, so the dashboard "My Courses" section is unchanged; new courses
  appear only in the "Browse Courses" catalog below (insertion order after
  ids 1-5).
- Per-page render sizes stay small: <=16 students, <=10 assignments, and
  <=11 discussions per course; submissions are scoped per assignment (<=16).

Insert-only; inserted ids recorded under
data/backups/course-sites-classrooms-expansion-2026-07-20/inserted_ids.json.

Usage: python scripts/expand_course_sites_classrooms_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
rng = random.Random(20260720)

PROTECTED_COURSE_ID = 3          # "Introduction to Data Visualization"
PROTECTED_TITLE = "Introduction to Data Visualization"
EXISTING_USER_IDS = {1, 2, 3, 4, 5}

# ---------------------------------------------------------------------------
# Catalog: department -> (courses, topic nouns)
# ---------------------------------------------------------------------------

CATALOG = {
    "Data Science": (
        ["Statistics for Data Science", "Machine Learning Foundations",
         "SQL for Analytics", "Applied Regression Modeling",
         "Data Storytelling with Dashboards", "Time Series Analysis in Practice",
         "A/B Testing and Experimentation", "Data Wrangling with pandas"],
        ["hypothesis testing", "feature engineering", "SQL joins",
         "regression diagnostics", "dashboard layout", "seasonality",
         "experiment design", "data cleaning", "model evaluation",
         "sampling bias"],
    ),
    "Software Engineering": (
        ["Modern JavaScript for Web Developers", "API Design and REST Fundamentals",
         "Test-Driven Development in Python", "System Design for Backend Engineers",
         "Git and Collaborative Workflows", "Refactoring Legacy Code",
         "Secure Coding Practices"],
        ["async patterns", "API versioning", "unit testing", "caching strategy",
         "branching strategy", "code smells", "input validation",
         "error handling", "code review", "pagination design"],
    ),
    "Writing & Communication": (
        ["Business Writing Essentials", "Public Speaking for Professionals",
         "Editing and Proofreading Workshop", "Storytelling for Product Teams",
         "Grant Writing Fundamentals"],
        ["executive summaries", "audience analysis", "line editing",
         "narrative arcs", "proposal budgets", "slide narration",
         "tone and voice", "revision passes"],
    ),
    "Leadership & Management": (
        ["Coaching and Mentoring Skills", "Strategic Decision Making",
         "Managing Remote and Hybrid Teams", "Negotiation for Managers",
         "Project Leadership Essentials"],
        ["active listening", "decision frameworks", "async communication",
         "anchoring tactics", "stakeholder mapping", "career conversations",
         "meeting facilitation", "conflict resolution"],
    ),
    "Design": (
        ["UX Design Fundamentals", "Typography and Layout Basics",
         "Design Systems in Practice", "User Research Methods",
         "Prototyping with Figma"],
        ["usability heuristics", "type scales", "component tokens",
         "interview scripts", "auto layout", "wireframing",
         "accessibility contrast", "affinity mapping"],
    ),
    "Business & Strategy": (
        ["Financial Literacy for Non-Finance Professionals",
         "Entrepreneurship Bootcamp", "Business Model Innovation",
         "Operations Management Basics"],
        ["cash flow statements", "customer discovery", "value propositions",
         "process bottlenecks", "unit economics", "market sizing",
         "pricing models", "supply forecasting"],
    ),
    "Marketing": (
        ["Digital Marketing Foundations", "Content Marketing Strategy",
         "SEO Essentials", "Email Marketing that Converts"],
        ["conversion funnels", "editorial calendars", "keyword research",
         "subject lines", "attribution models", "landing pages",
         "audience segments", "campaign metrics"],
    ),
    "Product Management": (
        ["Product Management Fundamentals", "Product Discovery and Validation",
         "Roadmapping and Prioritization", "Metrics for Product Managers"],
        ["user interviews", "opportunity trees", "RICE scoring",
         "north star metrics", "problem statements", "MVP scoping",
         "churn analysis", "release planning"],
    ),
    "Cloud & DevOps": (
        ["Cloud Computing Fundamentals", "Docker and Containers for Developers",
         "CI/CD Pipelines in Practice"],
        ["container images", "pipeline stages", "IAM policies",
         "autoscaling rules", "deployment rollbacks", "secrets management",
         "monitoring alerts", "infrastructure as code"],
    ),
}

FIRST_NAMES = [
    "Maya", "Jordan", "Sofia", "Liam", "Ana", "Marcus", "Nina", "Omar",
    "Grace", "Diego", "Hana", "Felix", "Ivy", "Noah", "Leila", "Owen",
    "Tara", "Ravi", "Chloe", "Mateo", "Yuki", "Sam", "Ines", "Kai",
    "Nora", "Andre", "Bianca", "Cole", "Dana", "Emil", "Farah", "Gabe",
    "Hugo", "Iris", "Jonas", "Keisha", "Lucas", "Mona", "Nils", "Paula",
    "Quinn", "Rosa", "Stefan", "Tessa", "Victor", "Wendy", "Xavier", "Zara",
]
LAST_NAMES = [
    "Nguyen", "Okafor", "Larsson", "Moreau", "Tanaka", "Silva", "Kowalski",
    "Haddad", "Petrov", "Jensen", "Alvarez", "Chen", "Dubois", "Eriksen",
    "Fischer", "Garcia", "Hoffman", "Iyer", "Jackson", "Kaur", "Lindqvist",
    "Mbeki", "Novak", "Ortiz", "Popescu", "Quintero", "Rossi", "Santos",
    "Takahashi", "Umar", "Valdez", "Weber", "Yamamoto", "Zhang", "Brennan",
    "Costa", "Dimitrov", "Egede", "Farkas", "Grant",
]
EMAIL_DOMAINS = ["gmail.com", "outlook.com", "yahoo.com"]
PW_WORDS = ["learn", "study", "grow", "focus", "spark", "bright", "campus",
            "skill", "notes", "scholar"]

STUDENT_BIOS = [
    "Working professional building new skills one course at a time.",
    "Career switcher exploring a new field through evening classes.",
    "Lifelong learner who enjoys structured courses and peer discussion.",
    "Taking courses to prepare for the next step in my career.",
    "Enjoys hands-on projects and learning alongside other professionals.",
    "Balancing a full-time job with continuous professional development.",
    "Recent bootcamp graduate rounding out fundamentals with coursework.",
    "Team lead sharpening skills to better support my colleagues.",
]
INSTRUCTOR_BIOS = [
    "Industry practitioner with {yrs}+ years of experience in {dept}. "
    "Focused on practical, project-based learning.",
    "Educator and consultant in {dept}. Has taught working professionals "
    "for {yrs} years and loves seeing course projects ship in the real world.",
    "Former team lead turned instructor. Brings {yrs} years of {dept} "
    "experience into every case study and workshop.",
]

DISCUSSION_TITLES = [
    "How do you approach {topic} in practice?",
    "Struggling with {topic} -- any tips?",
    "Best resources for learning {topic}?",
    "Real-world examples of {topic}?",
    "Question about this week's {topic} material",
    "{topic}: am I overthinking this?",
    "Sharing my notes on {topic}",
    "Tools you actually use for {topic}?",
    "Week recap: what clicked for you about {topic}?",
    "Study group for the {topic} module?",
]
DISCUSSION_BODIES = [
    "I went through the module on {topic} twice and I think I get the theory, "
    "but I'm not sure how it applies at my job. How do you all use this day to day?",
    "The lecture made {topic} look straightforward, but my first attempt on the "
    "exercise went sideways. Anyone else hit the same wall?",
    "I found a couple of articles about {topic} that go deeper than the course "
    "material. Happy to share links if people are interested.",
    "Before this course I had never heard of {topic}. Now I see it everywhere at "
    "work. What finally made it click for you?",
    "Could someone explain how {topic} relates to what we covered last week? "
    "I feel like I'm missing the connection between the two modules.",
    "I put together a one-page summary of {topic} while studying for the quiz. "
    "Posting the highlights here in case it helps anyone else.",
    "Is anyone interested in forming a small study group around {topic}? "
    "I learn much better when I can talk through examples out loud.",
]
REPLY_POOL = [
    "This helped me a lot, thanks for posting. The examples in lesson two are worth revisiting.",
    "I struggled with the same thing. What worked for me was redoing the exercise from scratch without notes.",
    "Great question -- I asked something similar in office hours and the short answer is: practice on a small dataset first.",
    "Following this thread. I'd join a study group if one gets organized.",
    "The recommended reading in the syllabus covers exactly this, chapter three especially.",
    "At my job we handle this slightly differently, but the course approach is a good default.",
    "Good summary. One nuance worth adding: it depends heavily on the context of the project.",
    "Thanks for sharing! I added your notes to my own study doc.",
    "I found a shorter way to do this -- happy to walk through it in the next discussion.",
    "Same here. Honestly it only clicked for me after the second project assignment.",
]
INSTRUCTOR_REPLIES = [
    "Great discussion, everyone. We'll spend the first ten minutes of next session on exactly this.",
    "Good instincts in this thread. Remember the framework from the module -- start simple, then iterate.",
    "Nice summary. I'd add one caution: don't skip the fundamentals before reaching for tools.",
    "This is a common sticking point every term. I've posted an extra worked example in the module resources.",
]

HW_TEMPLATES = ["{topic} Exercise", "Reflection: {topic}",
                "Case Study: {topic}", "Reading Response: {topic}",
                "{topic} Worksheet"]
QUIZ_TEMPLATES = ["Quiz: {topic}", "Knowledge Check: {topic}"]
PROJECT_TEMPLATES = ["{topic} Project", "Portfolio Piece: {topic}",
                     "Applied Project: {topic}"]
ASSIGN_DESCS = [
    "Apply what you learned about {topic} to a scenario from your own work. "
    "Submit a short write-up ({words} words) explaining your approach and what you would do differently.",
    "Complete the {topic} exercise from this week's module. Focus on process over polish; "
    "include a brief note on what was hardest and why.",
    "Work through the provided {topic} brief and deliver your result along with a "
    "{words}-word summary of the decisions you made.",
]
QUIZ_DESC = ("Short knowledge check covering the {topic} module. "
             "Open notes, one attempt, 20 minutes.")
FEEDBACK_POOL = [
    "Solid work. Your reasoning was clear and the examples were well chosen.",
    "Good effort -- the core idea is right, but tighten up the second half.",
    "Excellent submission. This could serve as a model answer for the class.",
    "You clearly understood the material. Watch the small details next time.",
    "Nice progress from your last assignment. Keep building on this.",
    "The approach works, though a simpler structure would make it stronger.",
    "Well organized and thoughtful. Consider pushing the analysis one step further.",
    "Meets expectations. Revisit the module examples to sharpen the weak spots.",
    "Strong grasp of the fundamentals. The practical application needs a bit more depth.",
    "Careful, thorough work. A few minor issues noted inline.",
]
LESSON_TYPES = ["lecture", "reading", "video"]
GRADE_WEIGHT_OPTIONS = [
    {"homework": 0.3, "exams": 0.3, "projects": 0.3, "quizzes": 0.1},
    {"homework": 0.25, "exams": 0.35, "projects": 0.3, "quizzes": 0.1},
    {"homework": 0.3, "exams": 0.2, "projects": 0.4, "quizzes": 0.1},
    {"homework": 0.2, "exams": 0.4, "projects": 0.3, "quizzes": 0.1},
]

SEMESTERS = {
    "Fall 2025": (date(2025, 9, 8), date(2025, 12, 12)),
    "Spring 2026": (date(2026, 1, 26), date(2026, 5, 8)),
}


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S")


def rand_dt(d, h_lo=8, h_hi=22):
    return datetime(d.year, d.month, d.day, rng.randint(h_lo, h_hi),
                    rng.choice([0, 15, 30, 45]))


def rand_date(lo, hi):
    return lo + timedelta(days=rng.randint(0, (hi - lo).days))


def title_case(s):
    small = {"and", "for", "with", "the", "of", "in", "to", "a"}
    words = s.split()
    out = []
    for i, w in enumerate(words):
        out.append(w if (w.lower() in small and i > 0) else w[0].upper() + w[1:])
    return " ".join(out)


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_titles = {r["title"] for r in db.execute(
        "SELECT title FROM course_sites_classrooms_courses")}
    next_user = db.execute(
        "SELECT MAX(id)+1 FROM course_sites_classrooms_users").fetchone()[0]
    next_course = db.execute(
        "SELECT MAX(id)+1 FROM course_sites_classrooms_courses").fetchone()[0]
    next_assign = db.execute(
        "SELECT MAX(id)+1 FROM course_sites_classrooms_assignments").fetchone()[0]
    next_disc = db.execute(
        "SELECT MAX(id)+1 FROM course_sites_classrooms_discussions").fetchone()[0]
    next_sub = db.execute(
        "SELECT MAX(id)+1 FROM course_sites_classrooms_submissions").fetchone()[0]

    # module/lesson ids continue after existing max across all courses
    next_module, next_lesson = 1, 1
    for (m,) in db.execute("SELECT modules FROM course_sites_classrooms_courses"):
        try:
            for mod in json.loads(m or "[]"):
                next_module = max(next_module, mod.get("id", 0) + 1)
                for les in mod.get("lessons", []):
                    next_lesson = max(next_lesson, les.get("id", 0) + 1)
        except (ValueError, TypeError):
            pass

    used_usernames = {r["username"] for r in db.execute(
        "SELECT username FROM course_sites_classrooms_users")}
    used_names = set()

    def make_person():
        for _ in range(200):
            name = f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"
            if name not in used_names:
                break
        used_names.add(name)
        base = name.lower().replace(" ", "_")
        username = base
        n = 2
        while username in used_usernames:
            username = f"{base}{n}"
            n += 1
        used_usernames.add(username)
        email = f"{username.replace('_', '.')}@{rng.choice(EMAIL_DOMAINS)}"
        password = f"{rng.choice(PW_WORDS)}{rng.randint(2024, 2026)}{rng.choice(['!', '', '#'])}"
        return name, username, email, password

    users_new, courses_new, assigns_new, discs_new, subs_new = [], [], [], [], []

    # ------------------------------------------------------------------
    # Instructors (per department)
    # ------------------------------------------------------------------
    dept_instructors = {}
    for dept, (course_titles, _) in CATALOG.items():
        n_instr = 2 if len(course_titles) <= 4 else 3
        ids = []
        for _ in range(n_instr):
            name, username, email, password = make_person()
            uid = next_user
            next_user += 1
            users_new.append({
                "id": uid, "root_user_id": 0, "username": username,
                "password": password, "name": name, "email": email,
                "role": "instructor",
                "bio": rng.choice(INSTRUCTOR_BIOS).format(
                    yrs=rng.randint(6, 18), dept=dept.lower()),
                "enrolled_since": rand_date(date(2024, 11, 1),
                                            date(2025, 6, 30)).isoformat(),
                "department": dept, "secondary_role": "", "ta_for_course_id": 0,
            })
            ids.append(uid)
        dept_instructors[dept] = ids

    # ------------------------------------------------------------------
    # Students
    # ------------------------------------------------------------------
    student_ids = []
    for _ in range(330):
        name, username, email, password = make_person()
        uid = next_user
        next_user += 1
        users_new.append({
            "id": uid, "root_user_id": 0, "username": username,
            "password": password, "name": name, "email": email,
            "role": "student", "bio": rng.choice(STUDENT_BIOS),
            "enrolled_since": rand_date(date(2025, 1, 5),
                                        date(2026, 1, 15)).isoformat(),
            "department": "", "secondary_role": "", "ta_for_course_id": 0,
        })
        student_ids.append(uid)
    user_by_id = {u["id"]: u for u in users_new}

    # ------------------------------------------------------------------
    # Courses + assignments + discussions + submissions
    # ------------------------------------------------------------------
    ta_students_used = set()
    for dept, (course_titles, topics) in CATALOG.items():
        for ctitle in course_titles:
            assert ctitle != PROTECTED_TITLE and ctitle not in existing_titles
            cid = next_course
            next_course += 1
            semester = rng.choice(list(SEMESTERS))
            sem_start, sem_end = SEMESTERS[semester]
            instructor_id = rng.choice(dept_instructors[dept])
            enrolled = rng.sample(student_ids, rng.randint(10, 16))
            assert not (set(enrolled) & EXISTING_USER_IDS)

            # TA for roughly a quarter of courses
            ta_id = 0
            if rng.random() < 0.25:
                candidates = [s for s in enrolled if s not in ta_students_used]
                if candidates:
                    ta_id = rng.choice(candidates)
                    ta_students_used.add(ta_id)
                    user_by_id[ta_id]["secondary_role"] = "ta"
                    user_by_id[ta_id]["ta_for_course_id"] = cid

            # Modules
            ctopics = rng.sample(topics, min(6, len(topics)))
            modules = []
            for mi in range(3):
                mtopic = ctopics[mi]
                lessons = []
                for li in range(rng.randint(2, 3)):
                    ltopic = ctopics[(mi + li + 1) % len(ctopics)]
                    lessons.append({
                        "id": next_lesson,
                        "title": title_case(f"{ltopic} in practice") if li else
                        title_case(f"Foundations of {ltopic}"),
                        "content": f"Covers {ltopic} with worked examples and "
                                   f"short exercises drawn from real {dept.lower()} "
                                   "scenarios. Ends with a self-check to confirm "
                                   "understanding before the next lesson.",
                        "type": rng.choice(LESSON_TYPES),
                    })
                    next_lesson += 1
                modules.append({"id": next_module,
                                "title": title_case(f"{mtopic}"),
                                "lessons": lessons})
                next_module += 1

            syllabus = (
                f"Week 1-3: {modules[0]['title']}. "
                f"Week 4-7: {modules[1]['title']}. "
                f"Week 8-11: {modules[2]['title']}. "
                f"Week 12-14: Applied project work. Week 15: Final review and wrap-up."
            )
            description = (
                f"A practical {dept.lower()} course covering {ctopics[0]}, "
                f"{ctopics[1]}, and {ctopics[2]}. Designed for working "
                "professionals, with weekly exercises, peer discussion, and "
                "feedback on real-world projects."
            )

            courses_new.append({
                "id": cid, "title": ctitle, "description": description,
                "instructor_id": instructor_id, "semester": semester,
                "enrollment_count": len(enrolled), "syllabus": syllabus,
                "modules": json.dumps(modules),
                "enrolled_students": json.dumps(enrolled),
                "department": dept,
                "grade_weights": json.dumps(rng.choice(GRADE_WEIGHT_OPTIONS)),
                "ta_id": ta_id, "npc_instructor": "",
            })

            # ---------------- Assignments ----------------
            course_assigns = []
            span = (sem_end - sem_start).days
            plan = ([("homework", t) for t in
                     rng.sample(HW_TEMPLATES, 3)] +
                    [("quiz", t) for t in
                     rng.sample(QUIZ_TEMPLATES, rng.randint(1, 2))] +
                    [("project", t) for t in
                     rng.sample(PROJECT_TEMPLATES, 2)])
            if rng.random() < 0.7:
                plan.append(("exam", "Midterm Exam"))
            if rng.random() < 0.8:
                plan.append(("exam", "Final Exam"))
            rng.shuffle(plan)
            for i, (cat, tmpl) in enumerate(plan):
                topic = rng.choice(ctopics)
                if cat == "exam":
                    title = tmpl
                    due = sem_start + timedelta(
                        days=span // 2 if tmpl == "Midterm Exam" else span)
                    points = rng.choice([100, 100, 150])
                    desc = (f"{tmpl} covering all modules to date. "
                            "Closed notes, 90 minutes, taken during the scheduled session.")
                else:
                    title = title_case(tmpl.format(topic=topic))
                    frac = (i + 1) / (len(plan) + 1)
                    due = sem_start + timedelta(days=max(7, int(span * frac)))
                    if cat == "quiz":
                        points = rng.choice([20, 25, 30])
                        desc = QUIZ_DESC.format(topic=topic)
                    elif cat == "project":
                        points = rng.choice([100, 100, 150])
                        desc = rng.choice(ASSIGN_DESCS).format(
                            topic=topic, words=rng.choice([300, 500]))
                    else:
                        points = rng.choice([40, 50, 50, 60, 75])
                        desc = rng.choice(ASSIGN_DESCS).format(
                            topic=topic, words=rng.choice([200, 300, 500]))
                due = min(due, sem_end)
                a = {"id": next_assign, "course_id": cid, "title": title,
                     "description": desc, "due_date": due.isoformat(),
                     "points_possible": points, "category": cat}
                next_assign += 1
                assigns_new.append(a)
                course_assigns.append(a)

            # ---------------- Submissions (all graded, like existing) ------
            for a in course_assigns:
                due = date.fromisoformat(a["due_date"])
                for sid_ in enrolled:
                    if rng.random() > 0.84:
                        continue
                    sub_day = due - timedelta(days=rng.choices(
                        [0, 1, 2, 3], weights=[35, 35, 20, 10])[0])
                    pct = min(1.0, max(0.4, rng.gauss(0.85, 0.09)))
                    score = max(1, round(a["points_possible"] * pct))
                    subs_new.append({
                        "id": next_sub, "assignment_id": a["id"],
                        "student_id": sid_, "course_id": cid,
                        "submitted_at": iso(rand_dt(sub_day)),
                        "score": score, "status": "graded",
                        "feedback": rng.choice(FEEDBACK_POOL),
                    })
                    next_sub += 1

            # ---------------- Discussions ----------------
            n_disc = rng.randint(8, 11)
            disc_topics = rng.sample(topics, min(n_disc, len(topics)))
            while len(disc_topics) < n_disc:
                disc_topics.append(rng.choice(topics))
            for di in range(n_disc):
                topic = disc_topics[di]
                created = rand_dt(rand_date(sem_start, sem_end))
                n_replies = rng.choices([0, 1, 2, 3, 4],
                                        weights=[15, 25, 30, 20, 10])[0]
                replies = []
                last = created
                reply_texts = rng.sample(REPLY_POOL, min(n_replies, len(REPLY_POOL)))
                for ri in range(n_replies):
                    last = last + timedelta(hours=rng.randint(1, 40))
                    if rng.random() < 0.18:
                        author, text = instructor_id, rng.choice(INSTRUCTOR_REPLIES)
                    else:
                        author, text = rng.choice(enrolled), reply_texts[ri]
                    replies.append({"id": ri + 1, "author_id": author,
                                    "content": text, "created_at": iso(last)})
                discs_new.append({
                    "id": next_disc, "course_id": cid,
                    "title": title_case(rng.choice(DISCUSSION_TITLES)
                                        .format(topic=topic)),
                    "author_id": rng.choice(enrolled),
                    "created_at": iso(created),
                    "content": rng.choice(DISCUSSION_BODIES).format(topic=topic),
                    "pinned": 1 if (di == 0 and rng.random() < 0.2) else 0,
                    "replies": json.dumps(replies),
                })
                next_disc += 1

    # ------------------------------------------------------------------
    # Safety checks before writing
    # ------------------------------------------------------------------
    assert all(a["course_id"] != PROTECTED_COURSE_ID for a in assigns_new)
    assert all(d["course_id"] != PROTECTED_COURSE_ID for d in discs_new)
    assert all(s["course_id"] != PROTECTED_COURSE_ID for s in subs_new)
    assert all(c["title"] != PROTECTED_TITLE for c in courses_new)
    for c in courses_new:
        assert not (set(json.loads(c["enrolled_students"])) & EXISTING_USER_IDS)

    total_new = (len(users_new) + len(courses_new) + len(assigns_new)
                 + len(discs_new) + len(subs_new))
    print(f"users: +{len(users_new)}, courses: +{len(courses_new)}, "
          f"assignments: +{len(assigns_new)}, discussions: +{len(discs_new)}, "
          f"submissions: +{len(subs_new)}  (total new: {total_new})")
    assert total_new + 55 >= 5000, "target not reached"

    if dry:
        for c in courses_new[:4]:
            print(" course:", c["id"], c["semester"], "|", c["title"],
                  "| enrolled:", c["enrollment_count"], "| ta:", c["ta_id"])
        for a in assigns_new[:4]:
            print(" assignment:", a["course_id"], a["category"],
                  a["points_possible"], "|", a["title"], "| due", a["due_date"])
        for d in discs_new[:3]:
            print(" discussion:", d["course_id"], "|", d["title"])
        for s in subs_new[:3]:
            print(" submission:", s["assignment_id"], s["student_id"],
                  s["score"], s["submitted_at"])
        return

    bdir = ROOT / "data" / "backups" / "course-sites-classrooms-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps({
        "users": [u["id"] for u in users_new],
        "courses": [c["id"] for c in courses_new],
        "assignments": [a["id"] for a in assigns_new],
        "discussions": [d["id"] for d in discs_new],
        "submissions": [s["id"] for s in subs_new]}, indent=1))

    for table, rows in (("users", users_new), ("courses", courses_new),
                        ("assignments", assigns_new), ("discussions", discs_new),
                        ("submissions", subs_new)):
        cols = list(rows[0].keys())
        db.executemany(
            f"INSERT INTO course_sites_classrooms_{table} ({', '.join(cols)}) "
            f"VALUES ({', '.join('?' * len(cols))})",
            [[r[c] for c in cols] for r in rows])

    # Rebuild external-content FTS indexes for the touched searchable tables
    for fts in ("fts_course_sites_classrooms_assignments",
                "fts_course_sites_classrooms_discussions",
                "fts_course_sites_classrooms_submissions"):
        db.execute(f"INSERT INTO [{fts}]([{fts}]) VALUES('rebuild')")

    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
