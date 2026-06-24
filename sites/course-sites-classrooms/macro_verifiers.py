"""Per-macro verification functions for course-sites-classrooms.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/course-sites-classrooms"


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/course/1")
    return {"pass": r.status_code == 200, "detail": f"Course detail page: {r.status_code}"}


def verify_macro_filter_by_department(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses?department=Computer+Science")
    courses = r.json()
    ok = all(c.get("department") == "Computer Science" for c in courses)
    return {"pass": ok and len(courses) > 0,
            "detail": f"filter_by_department: {len(courses)} CS courses, all_cs={ok}"}


def verify_macro_list_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/assignments")
    assignments = r.json()
    return {"pass": len(assignments) > 0,
            "detail": f"list_by_route: {len(assignments)} assignments for course 1"}


def verify_macro_compute_from_list(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses")
    courses = r.json()
    total = sum(len(c.get("enrolled_students", [])) for c in courses)
    return {"pass": total > 0, "detail": f"compute_from_list: total enrollments={total}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/3")
    course = r.json()
    has_instructor = "instructor_id" in course
    return {"pass": has_instructor, "detail": f"extract_by_route: instructor_id={course.get('instructor_id')}"}


def verify_macro_compute_grade_weighted(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/grades/4")
    data = r.json()
    avg = data.get("weighted_average")
    return {"pass": avg is not None, "detail": f"compute_grade_weighted: Bob avg={avg}"}


def verify_macro_compute_grade_letter(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/grades/3")
    data = r.json()
    letter = data.get("letter_grade", "")
    return {"pass": letter != "N/A" and len(letter) > 0,
            "detail": f"compute_grade_letter: Alice grade={letter}"}


def verify_macro_count_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/discussions")
    discussions = r.json()
    return {"pass": len(discussions) > 0,
            "detail": f"count_by_route: {len(discussions)} discussions in CS201"}


def verify_macro_compute_from_submissions(server_url):
    r = requests.get(f"{_base(server_url)}/api/assignments/3/submissions")
    subs = r.json()
    graded = [s for s in subs if s["status"] == "graded"]
    return {"pass": len(graded) > 0,
            "detail": f"compute_from_submissions: {len(graded)} graded subs for midterm"}


def verify_macro_rank_by_grade(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/gradebook")
    data = r.json()
    students = data.get("students", [])
    avgs = [s for s in students if s.get("weighted_avg") is not None]
    return {"pass": len(avgs) > 0,
            "detail": f"rank_by_grade: {len(avgs)} students with weighted averages"}


def verify_macro_count_nested_items(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/discussions")
    discussions = r.json()
    total = sum(len(d.get("replies", [])) for d in discussions)
    return {"pass": total > 0, "detail": f"count_nested_items: {total} total replies"}


def verify_macro_export_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/export/gradebook/1")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export_by_route: CSV {len(lines)} lines"}


def verify_macro_count_by_user(server_url):
    r = requests.get(f"{_base(server_url)}/api/users/3/courses")
    courses = r.json()
    return {"pass": len(courses) > 0, "detail": f"count_by_user: Alice in {len(courses)} courses"}


def verify_macro_extract_from_config(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1")
    course = r.json()
    weights = course.get("grade_weights", {})
    has_all = all(k in weights for k in ("homework", "exams", "projects", "quizzes"))
    return {"pass": has_all, "detail": f"extract_from_config: weights={weights}"}


def verify_macro_compute_from_stats(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    return {"pass": "total_submissions" in stats,
            "detail": f"compute_from_stats: {stats.get('total_submissions')} submissions"}


def verify_macro_authenticate_by_form(server_url):
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "prof_johnson", "password": "teach2025"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}, role={data.get('role')}"}


def verify_macro_create_discussion(server_url):
    r = requests.post(f"{_base(server_url)}/api/courses/1/discussions/new",
                      json={"author_id": 8, "title": "Test Discussion",
                            "content": "This is a macro test."})
    data = r.json()
    ok = data.get("action") == "created"
    return {"pass": ok, "detail": f"create_discussion: action={data.get('action')}, id={data.get('discussion_id')}"}


def verify_macro_reply_to_discussion(server_url):
    r = requests.post(f"{_base(server_url)}/api/discussions/1/reply",
                      json={"author_id": 8, "content": "Macro test reply."})
    data = r.json()
    ok = data.get("action") == "replied"
    return {"pass": ok, "detail": f"reply_to_discussion: action={data.get('action')}"}


def verify_macro_compute_class_average(server_url):
    r = requests.get(f"{_base(server_url)}/api/courses/1/gradebook")
    data = r.json()
    students = data.get("students", [])
    avgs = [s["weighted_avg"] for s in students if s.get("weighted_avg") is not None]
    if not avgs:
        return {"pass": False, "detail": "No weighted averages found"}
    class_avg = round(sum(avgs) / len(avgs), 2)
    return {"pass": True, "detail": f"compute_class_average: {class_avg}% from {len(avgs)} students"}


def verify_macro_compare_categories(server_url):
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    has_stats = stats.get("total_assignments", 0) > 0
    return {"pass": has_stats,
            "detail": f"compare_categories: {stats.get('total_assignments')} total assignments"}
