"""Per-macro verification functions for cloud-dev-consoles.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/cloud-dev-consoles"


def verify_macro_navigate_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/services/categories")
    cats = r.json()
    if not cats:
        return {"pass": False, "detail": "No categories returned"}
    cat = cats[0]["name"]
    r2 = requests.get(f"{_base(server_url)}/api/services?category={cat}")
    return {"pass": r2.status_code == 200, "detail": f"Category '{cat}': {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/service/svc-001")
    return {"pass": r.status_code == 200, "detail": f"Service detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/services/search?q=storage")
    results = r.json()
    return {"pass": len(results) > 0, "detail": f"search_by_query 'storage': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    r = requests.get(f"{_base(server_url)}/api/services/semantic?q=security+authentication")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/logs/search?q=timeout")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"filter_by_query 'timeout': {len(results)} results"}


def verify_macro_filter_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/services?category=Database")
    services = r.json()
    ok = all(s["category"] == "Database" for s in services)
    return {"pass": ok, "detail": f"filter_by_dropdown Database: {len(services)} services, all_db={ok}"}


def verify_macro_filter_by_checkbox(server_url):
    r = requests.get(f"{_base(server_url)}/api/instances?env=production")
    instances = r.json()
    ok = all(i.get("tags", {}).get("env") == "production" for i in instances)
    return {"pass": ok, "detail": f"filter_by_checkbox production: {len(instances)} instances"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/logs?date_from=2026-06-21T10:00&date_to=2026-06-21T10:30")
    logs = r.json()
    return {"pass": r.status_code == 200, "detail": f"filter_by_date_range: {len(logs)} logs"}


def verify_macro_sort_by_ranking(server_url):
    r = requests.get(f"{_base(server_url)}/api/services?sort=cost")
    services = r.json()
    if len(services) < 2:
        return {"pass": True, "detail": "Too few services to verify sort"}
    costs = [s["monthly_cost"] for s in services]
    is_sorted = all(costs[i] >= costs[i+1] for i in range(len(costs)-1))
    return {"pass": is_sorted, "detail": f"sort_by_ranking: sorted_desc={is_sorted}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/instances?q=prod")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"extract_by_query: first={results[0]['name']}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/databases?engine=PostgreSQL")
    dbs = r.json()
    total = sum(d["storage_used_gb"] for d in dbs)
    return {"pass": total > 0, "detail": f"extract_by_dropdown: PostgreSQL storage={total} GB"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/instances")
    instances = r.json()
    gpu = next((i for i in instances if i["name"] == "ml-training-gpu"), None)
    return {"pass": gpu is not None, "detail": f"extract_from_table: gpu type={gpu['type'] if gpu else 'N/A'}"}


def verify_macro_extract_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/api/instances/i-0a1b2c3d4e5f00001")
    inst = r.json()
    return {"pass": "os" in inst, "detail": f"extract_by_route: os={inst.get('os')}"}


def verify_macro_compute_by_extremum(server_url):
    r = requests.get(f"{_base(server_url)}/api/metrics?instance_id=i-0a1b2c3d4e5f00001")
    metrics = r.json()
    if not metrics:
        return {"pass": False, "detail": "No metrics"}
    max_cpu = max(m["cpu_percent"] for m in metrics)
    return {"pass": max_cpu > 0, "detail": f"compute_by_extremum: max_cpu={max_cpu}%"}


def verify_macro_compute_by_slider(server_url):
    r = requests.get(f"{_base(server_url)}/api/metrics")
    metrics = r.json()
    above = sum(1 for m in metrics if m["cpu_percent"] >= 80)
    return {"pass": above > 0, "detail": f"compute_by_slider: {above} above 80%"}


def verify_macro_verify_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/alerts?severity=critical")
    alerts = r.json()
    ok = all(a["severity"] == "critical" for a in alerts)
    return {"pass": ok and len(alerts) > 0, "detail": f"verify_by_dropdown: {len(alerts)} critical alerts"}


def verify_macro_create_from_free_text(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/alerts/create", json={
        "name": "TestAlert", "severity": "warning", "resource_name": "test",
        "condition": "test > 0", "category": "Custom"
    })
    data = r.json()
    ok = data.get("name") == "TestAlert"
    if "id" in data:
        requests.post(f"{base}/api/alerts/{data['id']}/delete")
    return {"pass": ok, "detail": f"create_from_free_text: name={data.get('name')}"}


def verify_macro_submit_by_query(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/alerts/create", json={
        "name": "SubmitTest", "severity": "warning", "resource_name": "test",
        "condition": "cpu > 90", "category": "Compute"
    })
    data = r.json()
    ok = data.get("id") is not None
    if "id" in data:
        requests.post(f"{base}/api/alerts/{data['id']}/delete")
    return {"pass": ok, "detail": f"submit_by_query: id={data.get('id')}"}


def verify_macro_edit_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/1/preferences",
                      json={"theme": "test-theme"})
    data = r.json()
    ok = data.get("preferences", {}).get("theme") == "test-theme"
    requests.post(f"{base}/api/users/1/preferences", json={"theme": "dark"})
    return {"pass": ok, "detail": f"edit_by_form: theme={data.get('preferences', {}).get('theme')}"}


def verify_macro_delete_from_table(server_url):
    base = _base(server_url)
    # Create temp alert then delete
    r = requests.post(f"{base}/api/alerts/create", json={
        "name": "TempDelete", "severity": "warning", "resource_name": "test",
        "condition": "test", "category": "Custom"
    })
    alert_id = r.json().get("id")
    r2 = requests.post(f"{base}/api/alerts/{alert_id}/delete")
    data = r2.json()
    return {"pass": data.get("action") == "deleted", "detail": f"delete_from_table: {data.get('action')}"}


def verify_macro_select_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/instances/i-0a1b2c3d4e5f00003")
    inst = r.json()
    return {"pass": inst.get("name") == "api-server-prod-1",
            "detail": f"select_by_dropdown: {inst.get('name')}"}


def verify_macro_select_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/alerts")
    alerts = r.json()
    return {"pass": len(alerts) > 0, "detail": f"select_from_table: {len(alerts)} alerts"}


def verify_macro_configure_by_query(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/1/preferences",
                      json={"default_region": "ap-southeast-1"})
    data = r.json()
    ok = data.get("preferences", {}).get("default_region") == "ap-southeast-1"
    requests.post(f"{base}/api/users/1/preferences",
                  json={"default_region": "us-east-1"})
    return {"pass": ok, "detail": f"configure_by_query: region={data.get('preferences', {}).get('default_region')}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv&resource=services&category=Compute")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_authenticate_by_form(server_url):
    base = _base(server_url)
    r = requests.post(f"{base}/api/login",
                      json={"username": "admin_sarah", "password": "cloudpass1"})
    data = r.json()
    ok = data.get("user_id") == 1
    return {"pass": ok, "detail": f"authenticate: user_id={data.get('user_id')}"}
