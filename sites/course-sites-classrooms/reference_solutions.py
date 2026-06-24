"""Per-task reference solutions via Flask test client for course-sites-classrooms."""
import json


def _base():
    return "/sites/course-sites-classrooms"


def solve_001(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1")
    course = json.loads(r.data)
    return str(len(course.get("modules", [])))


def solve_002(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses?department=Computer+Science")
    courses = json.loads(r.data)
    return str(len(courses))


def solve_003(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1/assignments")
    assignments = json.loads(r.data)
    types = sorted(set(a["type"] for a in assignments))
    return f"{len(assignments)} assignments, types: {', '.join(types)}"


def solve_004(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses")
    courses = json.loads(r.data)
    total = sum(len(c.get("enrolled_students", [])) for c in courses)
    return str(total)


def solve_005(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/3")
    course = json.loads(r.data)
    r2 = client.get(f"{base}/api/users/{course['instructor_id']}")
    user = json.loads(r2.data)
    return user["name"]


def solve_006(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1/grades/4")
    data = json.loads(r.data)
    return str(data["weighted_average"])


def solve_007(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1/grades/3")
    data = json.loads(r.data)
    return data["letter_grade"]


def solve_008(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1/discussions")
    discussions = json.loads(r.data)
    return str(len(discussions))


def solve_009(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/assignments/3/submissions")
    subs = json.loads(r.data)
    graded = [s for s in subs if s["status"] == "graded" and s["score"] is not None]
    if not graded:
        return "No graded submissions"
    avg = round(sum(s["score"] for s in graded) / len(graded), 2)
    return str(avg)


def solve_010(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1/gradebook")
    data = json.loads(r.data)
    students = data.get("students", [])
    best = max(students, key=lambda s: s.get("weighted_avg") or 0)
    return f"{best['student_name']} with {best['weighted_avg']}%"


def solve_011(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1/discussions")
    discussions = json.loads(r.data)
    total = sum(len(d.get("replies", [])) for d in discussions)
    return str(total)


def solve_012(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/export/gradebook/1")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_013(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/users/3/courses")
    courses = json.loads(r.data)
    return str(len(courses))


def solve_014(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1")
    course = json.loads(r.data)
    weights = course.get("grade_weights", {})
    parts = [f"{k} {int(v*100)}%" for k, v in weights.items()]
    return ", ".join(parts)


def solve_015(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats["total_submissions"])


def solve_016(client, base=None):
    base = base or _base()
    client.post(f"{base}/api/login",
                json={"username": "prof_johnson", "password": "teach2025"})
    r = client.get(f"{base}/api/courses/1/gradebook")
    data = json.loads(r.data)
    students = data.get("students", [])
    worst = min(students, key=lambda s: s.get("weighted_avg") or 999)
    return f"{worst['student_name']} with {worst['weighted_avg']}%"


def solve_017(client, base=None):
    base = base or _base()
    client.post(f"{base}/api/login",
                json={"username": "alice_wang", "password": "student123"})
    r = client.post(f"{base}/api/courses/1/discussions/new",
                    json={"author_id": 3, "title": "Final Exam Review",
                          "content": "When and where is the final exam review session?"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_018(client, base=None):
    base = base or _base()
    client.post(f"{base}/api/login",
                json={"username": "prof_johnson", "password": "teach2025"})
    r = client.post(f"{base}/api/discussions/1/reply",
                    json={"author_id": 1,
                          "content": "Great discussion everyone. See the updated slides on Canvas."})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_019(client, base=None):
    base = base or _base()
    r = client.get(f"{base}/api/courses/1/gradebook")
    data = json.loads(r.data)
    students = data.get("students", [])
    avgs = [s["weighted_avg"] for s in students if s.get("weighted_avg") is not None]
    if not avgs:
        return "N/A"
    class_avg = round(sum(avgs) / len(avgs), 2)
    return str(class_avg)


def solve_020(client, base=None):
    base = base or _base()
    r_courses = client.get(f"{base}/api/courses")
    courses = json.loads(r_courses.data)
    hw_pcts = []
    exam_pcts = []
    for course in courses:
        r = client.get(f"{base}/api/courses/{course['id']}/assignments")
        assignments = json.loads(r.data)
        for a in assignments:
            r_subs = client.get(f"{base}/api/assignments/{a['id']}/submissions")
            subs = json.loads(r_subs.data)
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
    return f"homework avg: {hw_avg}%, exam avg: {exam_avg}%, higher: {higher}"
