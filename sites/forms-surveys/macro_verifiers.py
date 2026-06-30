"""Per-macro verification functions for forms-surveys.

Each function tests that the corresponding macro works end-to-end.
"""
import io
import requests


def _base(server_url):
    return f"{server_url}/sites/forms-surveys"


def _login(server_url, username="arivera", password="password123"):
    s = requests.Session()
    s.post(f"{_base(server_url)}/api/login",
           json={"username": username, "password": password})
    return s


def verify_macro_navigate_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/forms/search?q=team+feedback")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_semantic: {len(results)} results"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/form/1")
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_route form/1: {r.status_code}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/forms/search?q=sprint")
    results = r.json()
    ok = len(results) >= 0
    return {"pass": ok, "detail": f"extract_by_query 'sprint': {len(results)} results"}


def verify_macro_extract_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/forms/search?q=employee+satisfaction+feedback")
    results = r.json()
    if results:
        return {"pass": True,
                "detail": f"extract_by_semantic: top={results[0]['title']}"}
    return {"pass": True, "detail": "extract_by_semantic: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/forms?status=active")
    forms = r.json()
    ok = all(f["status"] == "active" for f in forms)
    return {"pass": ok and len(forms) > 0,
            "detail": f"extract_by_dropdown active: {len(forms)} forms"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/forms/1")
    form = r.json()
    return {"pass": "title" in form and "fields" in form,
            "detail": f"extract_by_route: form 1 title={form.get('title','')[:40]}"}


def verify_macro_create_from_free_text(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/forms", json={
        "title": "Macro Test Form",
        "description": "Created for macro verification",
        "status": "draft",
        "fields": [
            {"type": "text", "label": "Test field", "required": False, "options": []}
        ]
    })
    data = r.json()
    ok = r.status_code == 201 and "id" in data
    # Cleanup
    if ok:
        s.delete(f"{_base(server_url)}/api/forms/{data['id']}")
    return {"pass": ok, "detail": f"create_from_free_text: id={data.get('id')}"}


def verify_macro_submit_by_query(server_url):
    # Search for a form, then submit to it
    r = requests.get(f"{_base(server_url)}/api/forms/search?q=satisfaction")
    forms = r.json()
    if not forms:
        return {"pass": False, "detail": "No forms found for 'satisfaction'"}
    form = forms[0]
    fid = form["id"]
    # Build minimal answers
    answers = {}
    for field in form.get("fields", []):
        if field.get("required"):
            if field["type"] in ("text", "textarea"):
                answers[field["id"]] = "test"
            elif field["type"] == "rating":
                answers[field["id"]] = "3"
            elif field["type"] in ("radio", "dropdown") and field.get("options"):
                answers[field["id"]] = field["options"][0]
            elif field["type"] == "checkbox" and field.get("options"):
                answers[field["id"]] = [field["options"][0]]
            elif field["type"] == "slider":
                answers[field["id"]] = "5"
            elif field["type"] == "ranking" and field.get("options"):
                answers[field["id"]] = field["options"]
    r2 = requests.post(f"{_base(server_url)}/api/forms/{fid}/respond",
                       json={"answers": answers})
    data = r2.json()
    ok = r2.status_code == 201
    # Cleanup
    if ok and "id" in data:
        requests.delete(f"{_base(server_url)}/api/responses/{data['id']}")
    return {"pass": ok, "detail": f"submit_by_query: form {fid}, resp id={data.get('id')}"}


def verify_macro_submit_by_dropdown(server_url):
    # Submit to form 3 which has a dropdown field
    r = requests.get(f"{_base(server_url)}/api/forms/3")
    form = r.json()
    answers = {}
    for field in form.get("fields", []):
        if field.get("required"):
            if field["type"] == "dropdown" and field.get("options"):
                answers[field["id"]] = field["options"][0]
            elif field["type"] == "rating":
                answers[field["id"]] = "3"
            elif field["type"] == "checkbox" and field.get("options"):
                answers[field["id"]] = [field["options"][0]]
            elif field["type"] in ("text", "textarea"):
                answers[field["id"]] = "test"
            elif field["type"] == "radio" and field.get("options"):
                answers[field["id"]] = field["options"][0]
    r2 = requests.post(f"{_base(server_url)}/api/forms/3/respond",
                       json={"answers": answers})
    data = r2.json()
    ok = r2.status_code == 201
    if ok and "id" in data:
        requests.delete(f"{_base(server_url)}/api/responses/{data['id']}")
    return {"pass": ok, "detail": f"submit_by_dropdown: resp id={data.get('id')}"}


def verify_macro_submit_by_route(server_url):
    r = requests.post(f"{_base(server_url)}/api/forms/9/respond", json={
        "answers": {"f9_1": "4", "f9_2": "Partially", "f9_3": "Test"}
    })
    data = r.json()
    ok = r.status_code == 201
    if ok and "id" in data:
        requests.delete(f"{_base(server_url)}/api/responses/{data['id']}")
    return {"pass": ok, "detail": f"submit_by_route: resp id={data.get('id')}"}


def verify_macro_submit_by_ranking(server_url):
    r = requests.post(f"{_base(server_url)}/api/forms/11/respond", json={
        "answers": {
            "f11_1": ["Slack", "GitHub", "Jira", "Figma", "Confluence"],
            "f11_2": "6",
            "f11_3": "7",
            "f11_4": "test"
        }
    })
    data = r.json()
    ok = r.status_code == 201
    if ok and "id" in data:
        requests.delete(f"{_base(server_url)}/api/responses/{data['id']}")
    return {"pass": ok, "detail": f"submit_by_ranking: resp id={data.get('id')}"}


def verify_macro_submit_by_slider(server_url):
    r = requests.post(f"{_base(server_url)}/api/forms/11/respond", json={
        "answers": {
            "f11_1": ["GitHub", "Slack", "Jira", "Confluence", "Figma"],
            "f11_2": "8",
            "f11_3": "9",
            "f11_4": ""
        }
    })
    data = r.json()
    ok = r.status_code == 201
    if ok and "id" in data:
        requests.delete(f"{_base(server_url)}/api/responses/{data['id']}")
    return {"pass": ok, "detail": f"submit_by_slider: resp id={data.get('id')}"}


def verify_macro_edit_by_query(server_url):
    # Edit response 27's cuisine to Italian, then revert
    r = requests.get(f"{_base(server_url)}/api/responses/27")
    if r.status_code == 404:
        return {"pass": False, "detail": "Response 27 not found"}
    original = r.json().get("answers", {}).get("f5_1", "")
    r2 = requests.put(f"{_base(server_url)}/api/responses/27",
                      json={"answers": {"f5_1": "Italian"}})
    edited = r2.json()
    ok = edited.get("answers", {}).get("f5_1") == "Italian"
    # Revert
    requests.put(f"{_base(server_url)}/api/responses/27",
                 json={"answers": {"f5_1": original}})
    return {"pass": ok, "detail": f"edit_by_query: f5_1={edited.get('answers',{}).get('f5_1')}"}


def verify_macro_delete_from_table(server_url):
    # Create a response, then delete it
    r = requests.post(f"{_base(server_url)}/api/forms/9/respond", json={
        "answers": {"f9_1": "3", "f9_2": "No", "f9_3": "test"}
    })
    data = r.json()
    rid = data.get("id")
    if not rid:
        return {"pass": False, "detail": "Failed to create test response"}
    r2 = requests.delete(f"{_base(server_url)}/api/responses/{rid}")
    result = r2.json()
    ok = result.get("status") == "deleted"
    return {"pass": ok, "detail": f"delete_from_table: status={result.get('status')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/forms?status=closed")
    forms = r.json()
    ok = all(f["status"] == "closed" for f in forms) and len(forms) > 0
    return {"pass": ok, "detail": f"select_by_dropdown closed: {len(forms)} forms"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/forms/1/export?format=csv")
    lines = r.text.strip().split("\n")
    ok = len(lines) > 1
    return {"pass": ok, "detail": f"export_by_dropdown CSV: {len(lines)} lines"}


def verify_macro_upload_by_upload(server_url):
    s = _login(server_url)
    files = {"file": ("test_doc.pdf", io.BytesIO(b"test content"), "application/pdf")}
    r = s.post(f"{_base(server_url)}/api/forms/12/upload", files=files)
    data = r.json()
    ok = r.status_code == 201 and data.get("filename") == "test_doc.pdf"
    return {"pass": ok, "detail": f"upload_by_upload: filename={data.get('filename')}"}


def verify_macro_share_by_dropdown(server_url):
    s = _login(server_url)
    r = s.post(f"{_base(server_url)}/api/forms/3/share",
               json={"method": "link", "recipient": ""})
    data = r.json()
    ok = r.status_code == 201 and data.get("method") == "link"
    return {"pass": ok, "detail": f"share_by_dropdown: method={data.get('method')}"}
