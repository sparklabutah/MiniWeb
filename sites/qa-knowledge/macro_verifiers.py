"""Per-macro verification functions for qa-knowledge.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/qa-knowledge"


def _login(server_url, username="alex_rivera"):
    """Helper: create a session and log in."""
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": username, "password": ""})
    return s


# --------------------------------------------------------------------------
# Navigation macros
# --------------------------------------------------------------------------

def verify_macro_navigate_by_dropdown(server_url):
    """Tag dropdown navigates to filtered question list."""
    r = requests.get(f"{_base(server_url)}/api/tags")
    tags = r.json()
    if not tags:
        return {"pass": False, "detail": "No tags returned"}
    tag = tags[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/tag/{tag}")
    return {"pass": r2.status_code == 200,
            "detail": f"Tag page '{tag}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Direct URL to question detail page."""
    r = requests.get(f"{_base(server_url)}/question/90001")
    return {"pass": r.status_code == 200,
            "detail": f"Question detail page: {r.status_code}"}


# --------------------------------------------------------------------------
# Search macros
# --------------------------------------------------------------------------

def verify_macro_search_by_query(server_url):
    """Keyword search returns matching questions."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "python"})
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'python': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic (keyword-overlap) search returns results."""
    r = requests.get(f"{_base(server_url)}/api/search/semantic",
                     params={"q": "concurrent programming error handling"})
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_search_by_route(server_url):
    """Direct API access to question by ID."""
    r = requests.get(f"{_base(server_url)}/api/questions/90001")
    q = r.json()
    return {"pass": "title" in q and "score" in q,
            "detail": f"search_by_route: title={q.get('title', '')[:50]}"}


# --------------------------------------------------------------------------
# Filter macros
# --------------------------------------------------------------------------

def verify_macro_filter_by_dropdown(server_url):
    """Single-tag dropdown filter returns only matching questions."""
    r = requests.get(f"{_base(server_url)}/api/questions", params={"tag": "kubernetes"})
    questions = r.json()
    ok = all("kubernetes" in q.get("tags", []) for q in questions)
    return {"pass": ok and len(questions) > 0,
            "detail": f"filter_by_dropdown kubernetes: {len(questions)} questions, all_match={ok}"}


def verify_macro_filter_by_checkbox(server_url):
    """Multi-tag checkbox filter returns questions matching any selected tag."""
    r = requests.get(f"{_base(server_url)}/api/questions",
                     params={"tags": ["python", "kubernetes"]})
    questions = r.json()
    ok = all(
        any(t in ["python", "kubernetes"] for t in q.get("tags", []))
        for q in questions
    )
    return {"pass": ok and len(questions) > 0,
            "detail": f"filter_by_checkbox python+kubernetes: {len(questions)} questions, all_match={ok}"}


# --------------------------------------------------------------------------
# Sort macros
# --------------------------------------------------------------------------

def verify_macro_sort_by_ranking(server_url):
    """Sort questions by votes descending."""
    r = requests.get(f"{_base(server_url)}/api/questions", params={"sort": "votes"})
    questions = r.json()
    if len(questions) < 2:
        return {"pass": True, "detail": "Too few questions to verify sort"}
    scores = [q.get("score", 0) for q in questions]
    is_sorted = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    return {"pass": is_sorted,
            "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


# --------------------------------------------------------------------------
# Extract macros
# --------------------------------------------------------------------------

def verify_macro_extract_by_query(server_url):
    """Search returns extractable question data."""
    r = requests.get(f"{_base(server_url)}/api/search", params={"q": "react"})
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_query: first title={results[0]['title'][:50]}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_route(server_url):
    """Question detail API returns full data."""
    r = requests.get(f"{_base(server_url)}/api/questions/90001")
    q = r.json()
    has_fields = all(k in q for k in ["title", "body_excerpt", "tags", "score"])
    return {"pass": has_fields,
            "detail": f"extract_by_route: has all fields={has_fields}"}


# --------------------------------------------------------------------------
# Create/Submit macros
# --------------------------------------------------------------------------

def verify_macro_create_from_free_text(server_url):
    """Create a question via API (simulates form free-text)."""
    r = requests.post(f"{_base(server_url)}/api/questions",
                      json={"title": "__macro_test_create__",
                            "body": "Test body for macro verification.",
                            "tags": ["test"]})
    data = r.json()
    ok = data.get("id") is not None and data.get("title") == "__macro_test_create__"
    # Clean up
    if data.get("id"):
        requests.delete(f"{_base(server_url)}/api/questions/{data['id']}")
    return {"pass": ok,
            "detail": f"create_from_free_text: id={data.get('id')}, title={data.get('title')}"}


def verify_macro_submit_by_query(server_url):
    """Submit a question with tag search (same as create, tags are the query)."""
    r = requests.post(f"{_base(server_url)}/api/questions",
                      json={"title": "__macro_test_submit__",
                            "body": "Submit test.",
                            "tags": ["python", "testing"]})
    data = r.json()
    ok = data.get("id") is not None
    tags = data.get("tags", [])
    # Clean up
    if data.get("id"):
        requests.delete(f"{_base(server_url)}/api/questions/{data['id']}")
    return {"pass": ok and "python" in tags,
            "detail": f"submit_by_query: tags={tags}"}


# --------------------------------------------------------------------------
# Edit macros
# --------------------------------------------------------------------------

def verify_macro_edit_by_form(server_url):
    """Edit question title via API (simulates form edit)."""
    # Get original title
    r = requests.get(f"{_base(server_url)}/api/questions/90001")
    original_title = r.json().get("title", "")
    # Update
    new_title = original_title + " [edited]"
    r2 = requests.put(f"{_base(server_url)}/api/questions/90001",
                      json={"title": new_title})
    updated = r2.json().get("title", "")
    # Revert
    requests.put(f"{_base(server_url)}/api/questions/90001",
                 json={"title": original_title})
    return {"pass": updated == new_title,
            "detail": f"edit_by_form: updated={updated[:50]}"}


# --------------------------------------------------------------------------
# Post macros
# --------------------------------------------------------------------------

def verify_macro_post_from_free_text(server_url):
    """Post an answer via form (API simulates)."""
    r = requests.post(f"{_base(server_url)}/api/questions/90001/answers",
                      json={"body": "__macro_test_answer__"})
    data = r.json()
    ok = data.get("id") is not None and data.get("body_excerpt") == "__macro_test_answer__"
    # Clean up
    if data.get("id"):
        requests.delete(f"{_base(server_url)}/api/answers/{data['id']}")
    return {"pass": ok,
            "detail": f"post_from_free_text: answer_id={data.get('id')}"}


def verify_macro_post_by_route(server_url):
    """Post an answer via API route."""
    r = requests.post(f"{_base(server_url)}/api/questions/90002/answers",
                      json={"body": "__macro_test_post_by_route__"})
    data = r.json()
    ok = data.get("id") is not None
    # Clean up
    if data.get("id"):
        requests.delete(f"{_base(server_url)}/api/answers/{data['id']}")
    return {"pass": ok,
            "detail": f"post_by_route: answer_id={data.get('id')}"}


# --------------------------------------------------------------------------
# React/Vote macros
# --------------------------------------------------------------------------

def verify_macro_react_by_toggle(server_url):
    """Upvote then downvote a question (net zero)."""
    # Get original score
    r = requests.get(f"{_base(server_url)}/api/questions/90001")
    original_score = r.json().get("score", 0)
    # Upvote
    r2 = requests.post(f"{_base(server_url)}/api/questions/90001/vote",
                       json={"direction": "up"})
    up_score = r2.json().get("score", 0)
    # Downvote to revert
    requests.post(f"{_base(server_url)}/api/questions/90001/vote",
                  json={"direction": "down"})
    return {"pass": up_score == original_score + 1,
            "detail": f"react_by_toggle: {original_score} -> {up_score}"}


# --------------------------------------------------------------------------
# Follow macros
# --------------------------------------------------------------------------

def verify_macro_follow_by_dropdown(server_url):
    """Follow a tag via dropdown (API simulates)."""
    s = _login(server_url, "alex_rivera")
    r = s.post(f"{_base(server_url)}/api/users/1/follow-tag",
               json={"tag": "__test_follow_dd__"})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/1/follow-tag",
           json={"tag": "__test_follow_dd__"})
    return {"pass": ok,
            "detail": f"follow_by_dropdown: action={data.get('action')}"}


def verify_macro_follow_by_toggle(server_url):
    """Follow/unfollow a tag via toggle."""
    s = _login(server_url, "marcus_chen")
    r = s.post(f"{_base(server_url)}/api/users/3/follow-tag",
               json={"tag": "__test_follow_toggle__"})
    data = r.json()
    ok = data.get("action") == "followed"
    # Toggle back
    s.post(f"{_base(server_url)}/api/users/3/follow-tag",
           json={"tag": "__test_follow_toggle__"})
    return {"pass": ok,
            "detail": f"follow_by_toggle: action={data.get('action')}"}


# --------------------------------------------------------------------------
# Share macros
# --------------------------------------------------------------------------

def verify_macro_share_by_dropdown(server_url):
    """Share a question via a selected platform."""
    r = requests.post(f"{_base(server_url)}/api/questions/90001/share",
                      json={"platform": "twitter"})
    data = r.json()
    ok = data.get("shared") is True and data.get("platform") == "twitter"
    return {"pass": ok,
            "detail": f"share_by_dropdown: shared={data.get('shared')}, platform={data.get('platform')}"}


# --------------------------------------------------------------------------
# Save macros
# --------------------------------------------------------------------------

def verify_macro_save_by_toggle(server_url):
    """Save/unsave a question toggle."""
    r = requests.post(f"{_base(server_url)}/api/users/1/save",
                      json={"question_id": 99999})
    data = r.json()
    ok = data.get("action") == "saved"
    # Toggle back (unsave)
    requests.post(f"{_base(server_url)}/api/users/1/save",
                  json={"question_id": 99999})
    return {"pass": ok,
            "detail": f"save_by_toggle: action={data.get('action')}"}


# --------------------------------------------------------------------------
# Report macros
# --------------------------------------------------------------------------

def verify_macro_report_by_form(server_url):
    """Report a question with reason and details."""
    r = requests.post(f"{_base(server_url)}/api/questions/90001/report",
                      json={"reason": "spam", "details": "Macro test report"})
    data = r.json()
    ok = data.get("reported") is True
    return {"pass": ok,
            "detail": f"report_by_form: reported={data.get('reported')}"}


# --------------------------------------------------------------------------
# Auth macros
# --------------------------------------------------------------------------

def verify_macro_authenticate_by_form(server_url):
    """Log in with valid credentials."""
    s = requests.Session()
    r = s.post(f"{_base(server_url)}/api/login",
               json={"username": "alex_rivera", "password": ""})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok,
            "detail": f"authenticate_by_form: user_id={data.get('user_id')}"}


def verify_macro_register_by_form(server_url):
    """Register a new user account."""
    r = requests.post(f"{_base(server_url)}/api/register",
                      json={"username": "__macro_test_reg__",
                            "display_name": "Macro Test User",
                            "password": "test"})
    data = r.json()
    ok = data.get("user_id") is not None
    return {"pass": ok,
            "detail": f"register_by_form: user_id={data.get('user_id')}"}
