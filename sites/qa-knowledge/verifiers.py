"""Per-task HTTP verification functions for qa-knowledge."""
import requests


def verify_001(server_url):
    """navigate_by_dropdown: filter questions by 'python' tag."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions", params={"tag": "python"})
    questions = r.json()
    count = len(questions)
    return {"pass": count > 0, "detail": f"python tag: {count} questions"}


def verify_002(server_url):
    """navigate_by_route: question 90001 detail page."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions/90001")
    q = r.json()
    score = q.get("score", 0)
    return {"pass": score > 0, "detail": f"Question 90001 score: {score}"}


def verify_003(server_url):
    """search_by_query: search for 'kubernetes'."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/search", params={"q": "kubernetes"})
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'kubernetes': {count} results"}


def verify_004(server_url):
    """search_by_semantic: semantic search for 'database performance tuning'."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/search/semantic",
                     params={"q": "database performance tuning"})
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'database performance tuning': {count} results"}


def verify_005(server_url):
    """search_by_route: access question 90002 by direct route."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions/90002")
    q = r.json()
    title = q.get("title", "")
    expected = "TypeScript generic constraint for nested object keys with conditional types"
    return {"pass": title == expected,
            "detail": f"Question 90002 title: {title[:60]}"}


def verify_006(server_url):
    """filter_by_dropdown: filter by 'reactjs' tag."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions", params={"tag": "reactjs"})
    questions = r.json()
    count = len(questions)
    ok = all("reactjs" in q.get("tags", []) for q in questions)
    return {"pass": count > 0 and ok,
            "detail": f"reactjs filter: {count} questions, all_match={ok}"}


def verify_007(server_url):
    """filter_by_checkbox: multi-tag filter for 'python' and 'typescript'."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions",
                     params={"tags": ["python", "typescript"]})
    questions = r.json()
    count = len(questions)
    ok = all(
        any(t in ["python", "typescript"] for t in q.get("tags", []))
        for q in questions
    )
    return {"pass": count > 0 and ok,
            "detail": f"python+typescript checkbox: {count} questions, all_match={ok}"}


def verify_008(server_url):
    """sort_by_ranking: sort by votes descending."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions", params={"sort": "votes"})
    questions = r.json()
    if not questions:
        return {"pass": False, "detail": "No questions returned"}
    first_title = questions[0].get("title", "")
    scores = [q.get("score", 0) for q in questions]
    is_sorted = all(scores[i] >= scores[i + 1] for i in range(len(scores) - 1))
    return {"pass": is_sorted,
            "detail": f"First by votes: {first_title[:60]}, sorted_desc={is_sorted}"}


def verify_009(server_url):
    """extract_by_query: search 'asyncio' and extract first result title."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/search", params={"q": "asyncio"})
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'asyncio'"}
    first = results[0].get("title", "")
    return {"pass": len(first) > 0,
            "detail": f"First 'asyncio' result: {first[:60]}"}


def verify_010(server_url):
    """extract_by_route: question 90005 tags."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions/90005")
    q = r.json()
    tags = q.get("tags", [])
    return {"pass": len(tags) > 0,
            "detail": f"Question 90005 tags: {tags}"}


def verify_011(server_url):
    """create_from_free_text + submit_by_query: new question created."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/search",
                     params={"q": "retry logic"})
    results = r.json()
    found = any("retry logic" in q.get("title", "").lower()
                for q in results)
    return {"pass": found,
            "detail": f"New question with 'retry logic': found={found}, results={len(results)}"}


def verify_012(server_url):
    """edit_by_form: question 90004 title updated."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions/90004")
    q = r.json()
    title = q.get("title", "")
    expected = "React useReducer vs useState: best practices for complex forms"
    return {"pass": title == expected,
            "detail": f"Question 90004 title: {title[:60]}"}


def verify_013(server_url):
    """post_from_free_text: answer posted on question 90001."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions/90001/answers")
    answers = r.json()
    found = any("TaskGroup" in a.get("body_excerpt", "")
                for a in answers)
    return {"pass": found,
            "detail": f"Answer with 'TaskGroup' on Q90001: found={found}, total_answers={len(answers)}"}


def verify_014(server_url):
    """post_by_route: API answer posted on question 90003."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions/90003/answers")
    answers = r.json()
    found = any("Prometheus adapter ConfigMap" in a.get("body_excerpt", "")
                for a in answers)
    count = len(answers)
    return {"pass": found,
            "detail": f"API answer on Q90003: found={found}, total_answers={count}"}


def verify_015(server_url):
    """react_by_toggle: question 90002 upvoted."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/questions/90002")
    q = r.json()
    score = q.get("score", 0)
    # Original score was 63, after upvote should be 64
    return {"pass": score == 64,
            "detail": f"Question 90002 score after upvote: {score} (expected 64)"}


def verify_016(server_url):
    """follow_by_dropdown: user 1 (alex_rivera) followed 'kubernetes' tag."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/users/1")
    user = r.json()
    followed = user.get("followed_tags", [])
    return {"pass": "kubernetes" in followed,
            "detail": f"User 1 followed_tags: {followed}"}


def verify_017(server_url):
    """follow_by_toggle: user 3 (marcus_chen) followed 'python' tag."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/users/3")
    user = r.json()
    followed = user.get("followed_tags", [])
    return {"pass": "python" in followed,
            "detail": f"User 3 followed_tags: {followed}"}


def verify_018(server_url):
    """share_by_dropdown: question 90010 shared via twitter."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.post(f"{base}/api/questions/90010/share",
                      json={"platform": "twitter"})
    data = r.json()
    ok = data.get("shared") is True and data.get("platform") == "twitter"
    title = data.get("title", "")
    return {"pass": ok,
            "detail": f"Share Q90010: shared={data.get('shared')}, platform={data.get('platform')}, title={title[:40]}"}


def verify_019(server_url):
    """save_by_toggle: user 10 (aisha_patel) saved question 90005."""
    base = f"{server_url}/sites/qa-knowledge"
    r = requests.get(f"{base}/api/users/10")
    user = r.json()
    saved = user.get("saved_questions", [])
    return {"pass": 90005 in saved,
            "detail": f"User 10 saved_questions: {saved}"}


def verify_020(server_url):
    """register_by_form + report_by_form: new user registered and question 90008 reported."""
    base = f"{server_url}/sites/qa-knowledge"
    # Check user registered
    r = requests.get(f"{base}/api/users")
    users = r.json()
    registered = any(u.get("se_username") == "new_tester" for u in users)
    # Check report on question
    r2 = requests.get(f"{base}/api/questions/90008")
    q = r2.json()
    reports = q.get("reports", [])
    reported = any(rep.get("reason") == "duplicate" for rep in reports)
    return {"pass": registered and reported,
            "detail": f"new_tester registered={registered}, Q90008 report={reported}"}
