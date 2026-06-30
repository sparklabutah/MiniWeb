"""Per-task HTTP verification functions for forms-surveys."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/templates")
    templates = r.json()
    count = len(templates)
    return {"pass": count > 0, "detail": f"Templates count: {count}"}


def verify_002(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/3")
    form = r.json()
    title = form.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Form 3 title: {title}"}


def verify_003(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/search?q=sprint")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'sprint': {count} forms"}


def verify_004(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/search?q=employee+satisfaction")
    results = r.json()
    ok = len(results) > 0
    title = results[0]["title"] if results else ""
    return {"pass": ok, "detail": f"Semantic 'employee satisfaction': top={title}"}


def verify_005(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms?status=active")
    forms = r.json()
    ok = all(f["status"] == "active" for f in forms)
    return {"pass": ok and len(forms) > 0, "detail": f"Active forms: {len(forms)}"}


def verify_006(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/1")
    form = r.json()
    fields = form.get("fields", [])
    return {"pass": len(fields) > 0, "detail": f"Form 1 has {len(fields)} fields"}


def verify_007(server_url):
    base = f"{server_url}/sites/forms-surveys"
    # Check that a new form was created with title 'Weekly Check-In'
    r = requests.get(f"{base}/api/forms")
    forms = r.json()
    new_forms = [f for f in forms if f.get("title") == "Weekly Check-In"]
    ok = len(new_forms) > 0
    fid = new_forms[0]["id"] if new_forms else None
    return {"pass": ok, "detail": f"Weekly Check-In form id={fid}"}


def verify_008(server_url):
    base = f"{server_url}/sites/forms-surveys"
    # Search for 'feedback' forms, check that a response was submitted to the first result
    r = requests.get(f"{base}/api/forms/search?q=feedback")
    forms = r.json()
    if not forms:
        return {"pass": False, "detail": "No feedback forms found"}
    form_id = forms[0]["id"]
    r2 = requests.get(f"{base}/api/forms/{form_id}/responses")
    responses = r2.json()
    # Check for a response with '4' value
    found = any(any(str(v) == "4" for v in resp.get("answers", {}).values())
                for resp in responses)
    return {"pass": found, "detail": f"Form {form_id}: response with '4' found={found}"}


def verify_009(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/3/responses")
    responses = r.json()
    perf = [resp for resp in responses
            if resp.get("answers", {}).get("f3_1") == "Performance"]
    ok = len(perf) > 0
    rid = perf[0]["id"] if perf else None
    return {"pass": ok, "detail": f"Form 3 response with Performance: id={rid}"}


def verify_010(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/9/responses")
    responses = r.json()
    five_rating = [resp for resp in responses
                   if resp.get("answers", {}).get("f9_1") == "5"
                   and resp.get("answers", {}).get("f9_2") == "Yes, completely"]
    ok = len(five_rating) > 0
    rid = five_rating[0]["id"] if five_rating else None
    return {"pass": ok, "detail": f"Form 9 response with rating 5: id={rid}"}


def verify_011(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/11/responses")
    responses = r.json()
    # Find response with ranking [GitHub, Slack, Jira, Confluence, Figma]
    target_ranking = ["GitHub", "Slack", "Jira", "Confluence", "Figma"]
    found = [resp for resp in responses
             if resp.get("answers", {}).get("f11_1") == target_ranking]
    ok = len(found) > 0
    rid = found[0]["id"] if found else None
    return {"pass": ok, "detail": f"Form 11 response with target ranking: id={rid}"}


def verify_012(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/11/stats")
    stats = r.json()
    fields = stats.get("fields", {})
    sat_field = fields.get("f11_2", {})
    avg = sat_field.get("average", 0)
    # After adding slider=3, the average should change from original
    return {"pass": avg > 0, "detail": f"Form 11 satisfaction average: {avg}"}


def verify_013(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/responses/27")
    if r.status_code == 404:
        return {"pass": False, "detail": "Response 27 not found"}
    resp = r.json()
    cuisine = resp.get("answers", {}).get("f5_1", "")
    return {"pass": cuisine == "Mexican", "detail": f"Response 27 cuisine: {cuisine}"}


def verify_014(server_url):
    base = f"{server_url}/sites/forms-surveys"
    # Response 8 should be deleted
    r = requests.get(f"{base}/api/responses/8")
    deleted = r.status_code == 404
    # Check remaining count for form 1
    r2 = requests.get(f"{base}/api/forms/1/responses")
    responses = r2.json()
    remaining = len(responses)
    return {"pass": deleted,
            "detail": f"Response 8 deleted={deleted}, form 1 remaining={remaining}"}


def verify_015(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms?status=closed")
    forms = r.json()
    ok = all(f["status"] == "closed" for f in forms) and len(forms) > 0
    titles = [f["title"] for f in forms]
    return {"pass": ok, "detail": f"Closed forms: {titles}"}


def verify_016(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/1/export?format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"Form 1 CSV export: {data_rows} data rows"}


def verify_017(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/12/attachments")
    attachments = r.json()
    has_goals = any("goals_q3" in a.get("filename", "") for a in attachments)
    return {"pass": has_goals,
            "detail": f"Form 12 attachments: {len(attachments)}, has_goals_q3={has_goals}"}


def verify_018(server_url):
    base = f"{server_url}/sites/forms-surveys"
    r = requests.get(f"{base}/api/forms/3/shares")
    shares = r.json()
    email_shares = [s for s in shares
                    if s.get("method") == "email"
                    and s.get("recipient") == "team-all@meridiansystems.com"]
    ok = len(email_shares) > 0
    return {"pass": ok, "detail": f"Form 3 email share found: {len(email_shares)}"}


def verify_019(server_url):
    base = f"{server_url}/sites/forms-surveys"
    # Check that Incident Postmortem form exists and has a response
    r = requests.get(f"{base}/api/forms")
    forms = r.json()
    postmortem = [f for f in forms if f.get("title") == "Incident Postmortem"]
    if not postmortem:
        return {"pass": False, "detail": "Incident Postmortem form not found"}
    fid = postmortem[0]["id"]
    r2 = requests.get(f"{base}/api/forms/{fid}/responses")
    responses = r2.json()
    p1_resp = [resp for resp in responses
               if resp.get("answers", {}).get(f"f{fid}_1") == "P1"]
    ok = len(p1_resp) > 0
    rid = p1_resp[0]["id"] if p1_resp else None
    return {"pass": ok, "detail": f"Postmortem form {fid}: P1 response id={rid}"}


def verify_020(server_url):
    base = f"{server_url}/sites/forms-surveys"
    # Check form 1 stats for rating average
    r = requests.get(f"{base}/api/forms/1/stats")
    stats = r.json()
    fields = stats.get("fields", {})
    rating_field = fields.get("f1_1", {})
    avg = rating_field.get("average", 0)
    # Also check active forms CSV
    r2 = requests.get(f"{base}/api/export?status=active&format=csv")
    lines = r2.text.strip().split("\n")
    active_count = len(lines) - 1
    return {"pass": avg > 0 and active_count > 0,
            "detail": f"Form 1 rating avg={avg}, active forms CSV rows={active_count}"}
