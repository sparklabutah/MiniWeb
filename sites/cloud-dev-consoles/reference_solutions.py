"""Per-task reference solutions via Flask test client for cloud-dev-consoles."""
import json


def solve_001(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/services?category=Compute")
    services = json.loads(r.data)
    return str(len(services))


def solve_002(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/services/svc-006")
    svc = json.loads(r.data)
    return str(svc["monthly_cost"])


def solve_003(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/services/search?q=storage")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/services/semantic?q=security+authentication+firewall")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/logs/search?q=timeout")
    results = json.loads(r.data)
    return results[0]["level"] if results else "No results"


def solve_006(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/services?category=Database")
    return str(len(json.loads(r.data)))


def solve_007(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/instances?env=production")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/logs?date_from=2026-06-21T10:00&date_to=2026-06-21T10:30")
    return str(len(json.loads(r.data)))


def solve_009(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/services?sort=cost")
    services = json.loads(r.data)
    return services[0]["name"] if services else ""


def solve_010(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/instances?q=prod")
    results = json.loads(r.data)
    return results[0]["name"] if results else "No results"


def solve_011(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/databases?engine=PostgreSQL")
    dbs = json.loads(r.data)
    total = sum(d["storage_used_gb"] for d in dbs)
    return str(total)


def solve_012(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/instances")
    instances = json.loads(r.data)
    gpu = next((i for i in instances if i["name"] == "ml-training-gpu"), None)
    return gpu["type"] if gpu else "Not found"


def solve_013(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/instances/i-0a1b2c3d4e5f00001")
    inst = json.loads(r.data)
    return inst["os"]


def solve_014(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/metrics?instance_id=i-0a1b2c3d4e5f00001")
    metrics = json.loads(r.data)
    max_cpu = max(m["cpu_percent"] for m in metrics)
    return str(max_cpu)


def solve_015(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/metrics")
    metrics = json.loads(r.data)
    above_80 = sum(1 for m in metrics if m["cpu_percent"] >= 80)
    return str(above_80)


def solve_016(client, base="/sites/cloud-dev-consoles"):
    r = client.get(f"{base}/api/alerts?severity=critical")
    alerts = json.loads(r.data)
    return str(len(alerts))


def solve_017(client, base="/sites/cloud-dev-consoles"):
    r = client.post(f"{base}/api/alerts/create",
                    json={
                        "name": "Disk Space Critical",
                        "severity": "critical",
                        "resource_name": "db-primary",
                        "condition": "Disk > 95%",
                        "category": "Database"
                    },
                    content_type="application/json")
    alert = json.loads(r.data)
    return alert.get("name", "")


def solve_018(client, base="/sites/cloud-dev-consoles"):
    client.post(f"{base}/api/login",
                json={"username": "admin_sarah", "password": "cloudpass1"},
                content_type="application/json")
    r = client.post(f"{base}/api/users/1/preferences",
                    json={"default_region": "eu-west-1"},
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("preferences", {}).get("default_region", "")


def solve_019(client, base="/sites/cloud-dev-consoles"):
    r = client.post(f"{base}/api/alerts/alert-004/delete",
                    content_type="application/json")
    data = json.loads(r.data)
    return data.get("action", "")


def solve_020(client, base="/sites/cloud-dev-consoles"):
    client.post(f"{base}/api/login",
                json={"username": "dev_marcus", "password": "cloudpass2"},
                content_type="application/json")
    client.post(f"{base}/api/users/2/save-query",
                json={"query": "production instances running"},
                content_type="application/json")
    r = client.get(f"{base}/api/export?format=csv&resource=services&category=Compute")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)
