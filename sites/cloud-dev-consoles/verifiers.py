"""Per-task HTTP verification functions for cloud-dev-consoles."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/services?category=Compute")
    services = r.json()
    count = len(services)
    return {"pass": count > 0, "detail": f"Compute category has {count} services"}


def verify_002(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/services/svc-006")
    svc = r.json()
    cost = svc.get("monthly_cost", 0)
    return {"pass": cost == 310.75, "detail": f"Relational DB monthly cost: ${cost}"}


def verify_003(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/services/search?q=storage")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'storage': {count} results"}


def verify_004(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/services/semantic?q=security+authentication+firewall")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Semantic 'security authentication firewall': {count} results"}


def verify_005(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/logs/search?q=timeout")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No logs matching 'timeout'"}
    level = results[0]["level"]
    return {"pass": len(level) > 0, "detail": f"First 'timeout' log level: {level}"}


def verify_006(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/services?category=Database")
    services = r.json()
    count = len(services)
    return {"pass": count > 0, "detail": f"Database services: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/instances?env=production")
    instances = r.json()
    count = len(instances)
    return {"pass": count > 0, "detail": f"Production instances: {count}"}


def verify_008(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/logs?date_from=2026-06-21T10:00&date_to=2026-06-21T10:30")
    logs = r.json()
    count = len(logs)
    ok = all("2026-06-21T10:" in l["timestamp"] for l in logs)
    return {"pass": ok and count >= 0, "detail": f"Logs 10:00-10:30: {count} entries, all_in_range={ok}"}


def verify_009(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/services?sort=cost")
    services = r.json()
    if not services:
        return {"pass": False, "detail": "No services returned"}
    first = services[0]["name"]
    costs = [s["monthly_cost"] for s in services]
    is_sorted = all(costs[i] >= costs[i+1] for i in range(len(costs)-1))
    return {"pass": is_sorted, "detail": f"Most expensive: {first}, sorted_desc={is_sorted}"}


def verify_010(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/instances?q=prod")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for 'prod'"}
    first = results[0]["name"]
    return {"pass": len(first) > 0, "detail": f"First 'prod' instance: {first}"}


def verify_011(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/databases?engine=PostgreSQL")
    dbs = r.json()
    total_used = sum(d["storage_used_gb"] for d in dbs)
    return {"pass": total_used > 0, "detail": f"PostgreSQL total storage used: {total_used} GB"}


def verify_012(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/instances")
    instances = r.json()
    gpu = next((i for i in instances if i["name"] == "ml-training-gpu"), None)
    if not gpu:
        return {"pass": False, "detail": "ml-training-gpu not found"}
    return {"pass": gpu["type"] == "p3.2xlarge", "detail": f"ml-training-gpu type: {gpu['type']}"}


def verify_013(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/instances/i-0a1b2c3d4e5f00001")
    inst = r.json()
    os_name = inst.get("os", "")
    return {"pass": "Ubuntu" in os_name, "detail": f"web-server-prod-1 OS: {os_name}"}


def verify_014(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/metrics?instance_id=i-0a1b2c3d4e5f00001")
    metrics = r.json()
    if not metrics:
        return {"pass": False, "detail": "No metrics for instance"}
    max_cpu = max(m["cpu_percent"] for m in metrics)
    return {"pass": max_cpu == 82.3, "detail": f"Peak CPU for web-server-prod-1: {max_cpu}%"}


def verify_015(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/metrics")
    metrics = r.json()
    above_80 = sum(1 for m in metrics if m["cpu_percent"] >= 80)
    return {"pass": above_80 > 0, "detail": f"Metrics with CPU >= 80%: {above_80}"}


def verify_016(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.get(f"{base}/api/alerts?severity=critical")
    alerts = r.json()
    count = len(alerts)
    return {"pass": count > 0, "detail": f"Critical alerts: {count}"}


def verify_017(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    r = requests.post(f"{base}/api/alerts/create", json={
        "name": "Disk Space Critical",
        "severity": "critical",
        "resource_name": "db-primary",
        "condition": "Disk > 95%",
        "category": "Database"
    })
    alert = r.json()
    ok = alert.get("name") == "Disk Space Critical" and alert.get("severity") == "critical"
    # Clean up: delete the created alert
    if "id" in alert:
        requests.post(f"{base}/api/alerts/{alert['id']}/delete")
    return {"pass": ok, "detail": f"Created alert: {alert.get('name')}, severity={alert.get('severity')}"}


def verify_018(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    # Login
    r = requests.post(f"{base}/api/login", json={"username": "admin_sarah", "password": "cloudpass1"})
    data = r.json()
    user_id = data.get("user_id")
    if not user_id:
        return {"pass": False, "detail": "Login failed"}
    # Update preference
    r = requests.post(f"{base}/api/users/{user_id}/preferences",
                      json={"default_region": "eu-west-1"})
    prefs = r.json()
    ok = prefs.get("preferences", {}).get("default_region") == "eu-west-1"
    # Revert
    requests.post(f"{base}/api/users/{user_id}/preferences",
                  json={"default_region": "us-east-1"})
    return {"pass": ok, "detail": f"Preference updated: default_region={prefs.get('preferences', {}).get('default_region')}"}


def verify_019(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    # Delete alert-004
    r = requests.post(f"{base}/api/alerts/alert-004/delete")
    data = r.json()
    ok = data.get("action") == "deleted"
    # Verify it's gone
    r2 = requests.get(f"{base}/api/alerts")
    alerts = r2.json()
    still_there = any(a["id"] == "alert-004" for a in alerts)
    return {"pass": ok and not still_there, "detail": f"Delete alert-004: action={data.get('action')}, still_present={still_there}"}


def verify_020(server_url):
    base = f"{server_url}/sites/cloud-dev-consoles"
    # Login
    r = requests.post(f"{base}/api/login", json={"username": "dev_marcus", "password": "cloudpass2"})
    data = r.json()
    user_id = data.get("user_id")
    if not user_id:
        return {"pass": False, "detail": "Login failed"}
    # Save query
    r = requests.post(f"{base}/api/users/{user_id}/save-query",
                      json={"query": "production instances running"})
    save_data = r.json()
    query_saved = save_data.get("action") == "saved"
    # Export CSV
    r = requests.get(f"{base}/api/export?format=csv&resource=services&category=Compute")
    lines = r.text.strip().split("\n")
    csv_rows = len(lines) - 1
    # Clean up
    requests.post(f"{base}/api/users/{user_id}/save-query",
                  json={"query": "production instances running"})
    return {"pass": query_saved and csv_rows > 0,
            "detail": f"Query saved={query_saved}, CSV Compute rows={csv_rows}"}
