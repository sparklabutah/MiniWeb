"""Per-task HTTP verification functions for course-sites-classrooms."""
import requests


def _base(server_url):
    return f"{server_url}/sites/course-sites-classrooms"


def verify_001(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1")
    course = r.json()
    modules = course.get("modules", [])
    count = len(modules)
    return {"pass": count == 3, "detail": f"CS201 has {count} modules"}


def verify_002(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses?department=Computer+Science")
    courses = r.json()
    count = len(courses)
    return {"pass": count == 4, "detail": f"CS department has {count} courses"}


def verify_003(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/assignments")
    assignments = r.json()
    count = len(assignments)
    types = [a["type"] for a in assignments]
    return {"pass": count == 5, "detail": f"CS201 has {count} assignments, types: {types}"}


def verify_004(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses")
    courses = r.json()
    total = sum(len(c.get("enrolled_students", [])) for c in courses)
    return {"pass": total > 0, "detail": f"Total enrollments: {total}"}


def verify_005(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/3")
    course = r.json()
    instructor_id = course.get("instructor_id")
    r2 = requests.get(f"{_base(server_url)}/api/users/{instructor_id}")
    user = r2.json()
    name = user.get("name", "")
    return {"pass": "Martinez" in name, "detail": f"MATH301 instructor: {name}"}


def verify_006(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/grades/4")
    data = r.json()
    avg = data.get("weighted_average")
    return {"pass": avg is not None, "detail": f"Bob Smith CS201 weighted avg: {avg}%"}


def verify_007(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/grades/3")
    data = r.json()
    letter = data.get("letter_grade", "")
    return {"pass": len(letter) > 0 and letter != "N/A",
            "detail": f"Alice Wang CS201 letter grade: {letter}"}


def verify_008(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/discussions")
    discussions = r.json()
    count = len(discussions)
    return {"pass": count > 0, "detail": f"CS201 discussions: {count}"}


def verify_009(server_url):
    # Midterm Exam is assignment ID 3 in CS201
    r = requests.get(f"{_base(server_url)}/api/assignments/3/submissions")
    subs = r.json()
    graded = [s for s in subs if s["status"] == "graded" and s["score"] is not None]
    if not graded:
        return {"pass": False, "detail": "No graded submissions for midterm"}
    avg = round(sum(s["score"] for s in graded) / len(graded), 2)
    return {"pass": True, "detail": f"CS201 Midterm avg score: {avg} ({len(graded)} graded)"}


def verify_010(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/gradebook")
    data = r.json()
    students = data.get("students", [])
    if not students:
        return {"pass": False, "detail": "No students in gradebook"}
    best = max(students, key=lambda s: s.get("weighted_avg") or 0)
    return {"pass": best.get("weighted_avg") is not None,
            "detail": f"Highest in CS201: {best['student_name']} with {best['weighted_avg']}%"}


def verify_011(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/discussions")
    discussions = r.json()
    total_replies = sum(len(d.get("replies", [])) for d in discussions)
    return {"pass": total_replies > 0, "detail": f"CS201 total replies: {total_replies}"}


def verify_012(server_url):
    r = requests.get(f"{_base(server_url)}/api/export/gradebook/1")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CS201 gradebook CSV: {data_rows} data rows"}


def verify_013(server_url):
    r = requests.get(f"{_base(server_url)}/api/users/3/courses")
    courses = r.json()
    count = len(courses)
    return {"pass": count > 0, "detail": f"Alice Wang enrolled in {count} courses"}


def verify_014(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1")
    course = r.json()
    weights = course.get("grade_weights", {})
    hw = weights.get("homework", 0)
    exams = weights.get("exams", 0)
    projects = weights.get("projects", 0)
    quizzes = weights.get("quizzes", 0)
    ok = (hw == 0.30 and exams == 0.40 and projects == 0.20 and quizzes == 0.10)
    return {"pass": ok,
            "detail": f"Weights: hw={hw}, exams={exams}, projects={projects}, quizzes={quizzes}"}


def verify_015(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    total = stats.get("total_submissions", 0)
    return {"pass": total > 0, "detail": f"Total submissions: {total}"}


def verify_016(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/gradebook")
    data = r.json()
    students = data.get("students", [])
    if not students:
        return {"pass": False, "detail": "No students in gradebook"}
    worst = min(students, key=lambda s: s.get("weighted_avg") or 999)
    return {"pass": worst.get("weighted_avg") is not None,
            "detail": f"Lowest in CS201: {worst['student_name']} with {worst['weighted_avg']}%"}


def verify_017(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/discussions")
    discussions = r.json()
    titles = [d["title"] for d in discussions]
    found = "Final Exam Review" in titles
    return {"pass": found,
            "detail": f"'Final Exam Review' found: {found}. Titles: {titles}"}


def verify_018(server_url):
    r = requests.get(f"{_base(server_url)}/api/discussions/1")
    disc = r.json()
    replies = disc.get("replies", [])
    found = any("updated slides" in r.get("content", "").lower() for r in replies)
    return {"pass": found,
            "detail": f"Reply with 'updated slides' found: {found}. {len(replies)} replies."}


def verify_019(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/gradebook")
    data = r.json()
    students = data.get("students", [])
    avgs = [s["weighted_avg"] for s in students if s.get("weighted_avg") is not None]
    if not avgs:
        return {"pass": False, "detail": "No weighted averages found"}
    class_avg = round(sum(avgs) / len(avgs), 2)
    return {"pass": True, "detail": f"CS201 class average: {class_avg}% ({len(avgs)} students)"}


def verify_020(server_url):
    # Compute average pct for homework vs exam across all courses
    r_assignments = requests.get(f"{_base(server_url)}/api/courses")
    courses = r_assignments.json()
    hw_pcts = []
    exam_pcts = []
    for course in courses:
        r = requests.get(f"{_base(server_url)}/api/courses/{course['id']}/assignments")
        assignments = r.json()
        for a in assignments:
            r_subs = requests.get(f"{_base(server_url)}/api/assignments/{a['id']}/submissions")
            subs = r_subs.json()
            for s in subs:
                if s["status"] == "graded" and s["score"] is not None:
                    pct = s["score"] / a["points"] * 100
                    if a["type"] == "homework":
                        hw_pcts.append(pct)
                    elif a["type"] == "exam":
                        exam_pcts.append(pct)
    hw_avg = round(sum(hw_pcts) / len(hw_pcts), 2) if hw_pcts else 0
    exam_avg = round(sum(exam_pcts) / len(exam_pcts), 2) if exam_pcts else 0
    higher = "homework" if hw_avg > exam_avg else "exams"
    return {"pass": True,
            "detail": f"Homework avg: {hw_avg}%, Exam avg: {exam_avg}%. Higher: {higher}"}
