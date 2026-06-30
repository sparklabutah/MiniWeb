#!/usr/bin/env python3
"""Walk all chains for cloud-dev-consoles site."""
import json
import os
import subprocess
import sys

SITE = "cloud-dev-consoles"
BASE = "/scratch/general/vast/u1653932/projects/MiniWeb"
OUT_DIR = f"{BASE}/annotation/chain_runs/{SITE}"
SCRIPT = f"{BASE}/scripts/chain_walker_lib.py"

def run(cmd):
    r = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=BASE)
    return r.stdout.strip()

def reset():
    run(f"python3 {SCRIPT} reset")

def get(url):
    return run(f"python3 {SCRIPT} get --url {url}")

def post(url, data):
    return run(f"python3 {SCRIPT} post --url {url} --data '{json.dumps(data)}'")

def post_json(url, data):
    return run(f"python3 {SCRIPT} post_json --url {url} --data '{json.dumps(data)}'")

def api(url):
    return run(f"python3 {SCRIPT} api --url {url}")

def save_chain(chain_id, status, trajectory):
    d = f"{OUT_DIR}/{chain_id}"
    os.makedirs(d, exist_ok=True)
    with open(f"{d}/status.json", "w") as f:
        json.dump(status, f, indent=2)
    with open(f"{d}/trajectory.json", "w") as f:
        json.dump(trajectory, f, indent=2)

# Load all data for reference
def load_data():
    data = {}
    for fn in ['services.json','instances.json','functions.json','databases.json',
               'storage_buckets.json','alerts.json','users.json','billing.json',
               'iam_users.json','api_endpoints.json','logs.json','metrics.json']:
        with open(f"/scratch/general/vast/u1653932/data_sources/{SITE}/{fn}") as f:
            data[fn.replace('.json','')] = json.load(f)
    return data

data = load_data()

P = f"/sites/{SITE}"

##############################################################################
# CHAIN DEFINITIONS - Each chain has its macros, difficulty, and step logic
##############################################################################

chains = []

# ============== EASY CHAINS ==============

# easy_001: select_by_dropdown
chains.append({
    "chain_id": f"{SITE}_easy_001",
    "difficulty": "easy",
    "macros": ["select_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/services", "desc": "Navigate to services page"},
        {"action": "get", "url": f"{P}/services?category=Database", "desc": "Select 'Database' from category dropdown to filter services"},
    ],
    "entity_info": {"category": "Database", "page": "services"},
    "action_summary": "Selected 'Database' category from the dropdown on the services page to filter for database services (Relational DB, NoSQL DB, Cache Cluster)."
})

# easy_002: configure_by_query
chains.append({
    "chain_id": f"{SITE}_easy_002",
    "difficulty": "easy",
    "macros": ["configure_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login as admin_sarah"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"default_region": "us-west-2"}, "desc": "Configure default region preference to us-west-2"},
    ],
    "entity_info": {"user": "admin_sarah", "preference": "default_region", "value": "us-west-2"},
    "action_summary": "Configured admin_sarah's default region preference to us-west-2 via preferences API."
})

# easy_003: extract_by_dropdown
chains.append({
    "chain_id": f"{SITE}_easy_003",
    "difficulty": "easy",
    "macros": ["extract_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/billing", "desc": "Navigate to billing page"},
        {"action": "get", "url": f"{P}/billing?month=2026-06", "desc": "Select month '2026-06' from dropdown to view June billing data"},
    ],
    "entity_info": {"month": "2026-06", "total_cost": 3968.05},
    "action_summary": "Used the month dropdown on billing page to filter to June 2026, extracting 9 billing records totaling $3968.05."
})

# easy_004: search_by_semantic
chains.append({
    "chain_id": f"{SITE}_easy_004",
    "difficulty": "easy",
    "macros": ["search_by_semantic"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/services/semantic?q=machine+learning+compute+gpu", "desc": "Semantic search for services related to machine learning compute GPU"},
    ],
    "entity_info": {"query": "machine learning compute gpu", "top_result": "Compute Engine"},
    "action_summary": "Performed semantic search for 'machine learning compute gpu' via API, which ranked services by relevance to the query terms."
})

# easy_005: select_from_table
chains.append({
    "chain_id": f"{SITE}_easy_005",
    "difficulty": "easy",
    "macros": ["select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/instances", "desc": "Navigate to instances page"},
        {"action": "get", "url": f"{P}/instance/i-0a1b2c3d4e5f00009", "desc": "Select ml-training-gpu instance from the table to view its details"},
    ],
    "entity_info": {"instance_id": "i-0a1b2c3d4e5f00009", "instance_name": "ml-training-gpu", "type": "p3.2xlarge"},
    "action_summary": "Selected the ml-training-gpu instance (p3.2xlarge, 8 vCPUs, 61GB RAM) from the instances table to view its detail page with performance metrics."
})

# easy_006: navigate_by_dropdown
chains.append({
    "chain_id": f"{SITE}_easy_006",
    "difficulty": "easy",
    "macros": ["navigate_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/metrics", "desc": "Navigate to metrics page"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00003", "desc": "Select api-server-prod-1 from instance dropdown to navigate to its metrics"},
    ],
    "entity_info": {"instance_id": "i-0a1b2c3d4e5f00003", "instance_name": "api-server-prod-1"},
    "action_summary": "Used the instance dropdown on the metrics page to navigate to api-server-prod-1 metrics, showing 12 data points for that instance."
})

# easy_007: extract_by_query
chains.append({
    "chain_id": f"{SITE}_easy_007",
    "difficulty": "easy",
    "macros": ["extract_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/billing/summary?month=2026-06", "desc": "Query billing summary API for June 2026 to extract total cost and breakdown"},
    ],
    "entity_info": {"month": "2026-06", "total_cost": 3968.05, "total_budget": 4240.0},
    "action_summary": "Queried the billing summary API for June 2026, extracting total cost ($3968.05) vs budget ($4240.00) with category breakdown."
})

# easy_008: verify_by_dropdown
chains.append({
    "chain_id": f"{SITE}_easy_008",
    "difficulty": "easy",
    "macros": ["verify_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/alerts", "desc": "Navigate to alerts page"},
        {"action": "get", "url": f"{P}/alerts?severity=critical", "desc": "Select 'critical' from severity dropdown to verify critical alerts"},
    ],
    "entity_info": {"severity": "critical", "count": 3, "alerts": ["Database Connection Pool", "WAF Blocked Requests", "Dead Letter Queue"]},
    "action_summary": "Used severity dropdown to filter to critical alerts, verifying 3 critical alerts exist: Database Connection Pool, WAF Blocked Requests, and Dead Letter Queue."
})

# easy_009: compute_by_slider
chains.append({
    "chain_id": f"{SITE}_easy_009",
    "difficulty": "easy",
    "macros": ["compute_by_slider"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/metrics", "desc": "Navigate to metrics page"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=80", "desc": "Set CPU threshold slider to 80% to identify instances exceeding threshold"},
    ],
    "entity_info": {"threshold": 80, "exceeding_instances": ["i-0a1b2c3d4e5f00001", "i-0a1b2c3d4e5f00003", "i-0a1b2c3d4e5f00009"]},
    "action_summary": "Adjusted CPU threshold slider to 80% on metrics page to compute which metrics data points exceed this threshold. Multiple instances have metrics above 80% CPU."
})

# easy_010: filter_by_checkbox
chains.append({
    "chain_id": f"{SITE}_easy_010",
    "difficulty": "easy",
    "macros": ["filter_by_checkbox"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/instances", "desc": "Navigate to instances page"},
        {"action": "get", "url": f"{P}/instances?env=staging", "desc": "Check the 'staging' environment checkbox to filter instances"},
    ],
    "entity_info": {"env": "staging", "count": 2, "instances": ["staging-web", "staging-api"]},
    "action_summary": "Checked the 'staging' environment checkbox on instances page, filtering to 2 staging instances: staging-web and staging-api."
})

# easy_011: delete_from_table
chains.append({
    "chain_id": f"{SITE}_easy_011",
    "difficulty": "easy",
    "macros": ["delete_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/alerts", "desc": "Navigate to alerts page to view alert table"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-004/delete", "data": {}, "desc": "Delete the resolved 'Lambda Error Rate Spike' alert (alert-004) from the table"},
    ],
    "entity_info": {"alert_id": "alert-004", "alert_name": "Lambda Error Rate Spike"},
    "action_summary": "Deleted the resolved 'Lambda Error Rate Spike' alert (alert-004) from the alerts table via API."
})

# easy_012: search_by_query
chains.append({
    "chain_id": f"{SITE}_easy_012",
    "difficulty": "easy",
    "macros": ["search_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/logs?q=timeout", "desc": "Search logs for 'timeout' keyword to find timeout-related entries"},
    ],
    "entity_info": {"query": "timeout", "matching_logs": ["log-001"]},
    "action_summary": "Searched logs for 'timeout', finding log entry about connection timeout to prod-users-db after 30s."
})

# easy_013: export_by_dropdown
chains.append({
    "chain_id": f"{SITE}_easy_013",
    "difficulty": "easy",
    "macros": ["export_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/export?resource=instances&format=csv", "desc": "Export instances data as CSV via the export API"},
    ],
    "entity_info": {"resource": "instances", "format": "csv"},
    "action_summary": "Exported all 15 instances data in CSV format via the export API dropdown."
})

# easy_014: compute_by_extremum
chains.append({
    "chain_id": f"{SITE}_easy_014",
    "difficulty": "easy",
    "macros": ["compute_by_extremum"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003", "desc": "Get metrics summary for api-server-prod-1 to find max CPU usage"},
    ],
    "entity_info": {"instance_id": "i-0a1b2c3d4e5f00003", "cpu_max": 88.1, "cpu_min": 8.5, "cpu_avg": 46.69},
    "action_summary": "Computed extremum metrics for api-server-prod-1: max CPU 88.1%, min CPU 8.5%, avg CPU ~46.69%."
})

# easy_015: filter_by_dropdown
chains.append({
    "chain_id": f"{SITE}_easy_015",
    "difficulty": "easy",
    "macros": ["filter_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/functions", "desc": "Navigate to functions page"},
        {"action": "get", "url": f"{P}/functions?runtime=python3.11", "desc": "Filter functions by 'python3.11' runtime using dropdown"},
    ],
    "entity_info": {"runtime": "python3.11", "count": 5, "functions": ["process-order", "resize-image", "data-etl-daily", "pdf-generator", "log-archiver"]},
    "action_summary": "Filtered Lambda functions by python3.11 runtime using dropdown, showing 5 functions: process-order, resize-image, data-etl-daily, pdf-generator, log-archiver."
})

# easy_016: extract_from_table
chains.append({
    "chain_id": f"{SITE}_easy_016",
    "difficulty": "easy",
    "macros": ["extract_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/databases", "desc": "Navigate to databases page to view the databases table"},
    ],
    "entity_info": {"extracted": {"name": "prod-analytics-dw", "engine": "PostgreSQL", "storage": "1456/2000 GB", "cost": 420.0}},
    "action_summary": "Extracted database information from the table: prod-analytics-dw is the most expensive database at $420/mo, using 1456/2000 GB storage."
})

# easy_017: submit_by_query
chains.append({
    "chain_id": f"{SITE}_easy_017",
    "difficulty": "easy",
    "macros": ["submit_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login as admin_sarah"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "status:active region:us-east-1"}, "desc": "Submit and save a search query for later use"},
    ],
    "entity_info": {"user": "admin_sarah", "query": "status:active region:us-east-1"},
    "action_summary": "Submitted and saved the search query 'status:active region:us-east-1' to admin_sarah's saved queries."
})

# easy_018: sort_by_ranking
chains.append({
    "chain_id": f"{SITE}_easy_018",
    "difficulty": "easy",
    "macros": ["sort_by_ranking"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/services?sort=cost", "desc": "Sort services by cost (high to low) using sort dropdown"},
    ],
    "entity_info": {"sort": "cost", "top_service": "Data Warehouse", "top_cost": 420.0},
    "action_summary": "Sorted services by cost (high to low), ranking Data Warehouse ($420.00) as the most expensive service, followed by Relational DB ($310.75)."
})

# easy_019: authenticate_by_form
chains.append({
    "chain_id": f"{SITE}_easy_019",
    "difficulty": "easy",
    "macros": ["authenticate_by_form"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/login", "desc": "Navigate to login page"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Submit login form with admin_sarah credentials"},
    ],
    "entity_info": {"username": "admin_sarah", "role": "Administrator"},
    "action_summary": "Authenticated as admin_sarah (Administrator) via the login form, gaining access to the dashboard."
})

# easy_020: extract_by_route
chains.append({
    "chain_id": f"{SITE}_easy_020",
    "difficulty": "easy",
    "macros": ["extract_by_route"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/services/svc-024", "desc": "Extract Data Warehouse service details via API route"},
    ],
    "entity_info": {"service_id": "svc-024", "name": "Data Warehouse", "category": "Analytics", "cost": 420.0},
    "action_summary": "Extracted Data Warehouse (svc-024) details via API route: Analytics category, active status, us-east-1 region, $420.00/mo."
})

# ============== MEDIUM CHAINS ==============

# medium_001: search_by_query, select_by_dropdown, sort_by_ranking
chains.append({
    "chain_id": f"{SITE}_medium_001",
    "difficulty": "medium",
    "macros": ["search_by_query", "select_by_dropdown", "sort_by_ranking"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/services", "desc": "Navigate to services page"},
        {"action": "get", "url": f"{P}/services?q=production", "desc": "Search services for 'production' keyword"},
        {"action": "get", "url": f"{P}/services?q=production&category=Compute", "desc": "Select 'Compute' category from dropdown to narrow results"},
        {"action": "get", "url": f"{P}/services?q=production&category=Compute&sort=cost", "desc": "Sort filtered results by cost (high to low)"},
    ],
    "entity_info": {"query": "production", "category": "Compute", "sort": "cost"},
    "action_summary": "Searched services for 'production', filtered to Compute category, and sorted by cost. Compute Engine ($245.50) is the most expensive production compute service."
})

# medium_002: compute_by_slider, create_from_free_text, export_by_dropdown
chains.append({
    "chain_id": f"{SITE}_medium_002",
    "difficulty": "medium",
    "macros": ["compute_by_slider", "create_from_free_text", "export_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=75", "desc": "Set CPU threshold slider to 75% to compute high-CPU instances"},
        {"action": "post_json", "url": f"{P}/api/alerts/create", "data": {"name": "CPU Above 75% Alert", "severity": "warning", "resource_name": "web-server-prod-1", "condition": "CPU > 75% for 5 minutes", "category": "Compute"}, "desc": "Create a new alert via free text for high CPU usage"},
        {"action": "api", "url": f"{P}/api/export?resource=services&format=csv", "desc": "Export services data as CSV"},
    ],
    "entity_info": {"threshold": 75, "alert_name": "CPU Above 75% Alert", "export_format": "csv"},
    "action_summary": "Set CPU threshold to 75% on metrics, created a new warning alert for CPU above 75% on web-server-prod-1, then exported services data as CSV."
})

# medium_003: extract_by_route, navigate_by_dropdown, select_from_table
chains.append({
    "chain_id": f"{SITE}_medium_003",
    "difficulty": "medium",
    "macros": ["extract_by_route", "navigate_by_dropdown", "select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/instances/i-0a1b2c3d4e5f00005", "desc": "Extract db-primary instance details via API route"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00005", "desc": "Navigate to metrics for db-primary using instance dropdown"},
        {"action": "get", "url": f"{P}/instance/i-0a1b2c3d4e5f00005", "desc": "Select db-primary from instances table to view detail page"},
    ],
    "entity_info": {"instance_id": "i-0a1b2c3d4e5f00005", "name": "db-primary", "type": "r5.2xlarge"},
    "action_summary": "Extracted db-primary instance info via API (r5.2xlarge, 8 vCPUs, 64GB), navigated to its metrics via dropdown, then viewed its detail page."
})

# medium_004: authenticate_by_form, filter_by_checkbox, filter_by_dropdown
chains.append({
    "chain_id": f"{SITE}_medium_004",
    "difficulty": "medium",
    "macros": ["authenticate_by_form", "filter_by_checkbox", "filter_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Authenticate as admin_sarah via login form"},
        {"action": "get", "url": f"{P}/instances?env=production", "desc": "Filter instances by production environment checkbox"},
        {"action": "get", "url": f"{P}/instances?env=production&status=running", "desc": "Further filter by status=running dropdown"},
    ],
    "entity_info": {"user": "admin_sarah", "env": "production", "status": "running"},
    "action_summary": "Logged in as admin_sarah, filtered instances to production environment via checkbox, then further filtered to running status via dropdown."
})

# medium_005: navigate_by_route, select_from_table, submit_by_query
chains.append({
    "chain_id": f"{SITE}_medium_005",
    "difficulty": "medium",
    "macros": ["navigate_by_route", "select_from_table", "submit_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login first"},
        {"action": "get", "url": f"{P}/api-gateway", "desc": "Navigate to API Gateway page via route"},
        {"action": "api", "url": f"{P}/api/endpoints/api-003", "desc": "Select Create Order endpoint from table to view details"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "method:POST error_rate>1%"}, "desc": "Submit and save query for high-error POST endpoints"},
    ],
    "entity_info": {"endpoint": "Create Order", "saved_query": "method:POST error_rate>1%"},
    "action_summary": "Navigated to API Gateway, selected Create Order endpoint (POST /api/v2/orders), then saved a query for high-error POST endpoints."
})

# medium_006: authenticate_by_form, filter_by_date_range, select_from_table
chains.append({
    "chain_id": f"{SITE}_medium_006",
    "difficulty": "medium",
    "macros": ["authenticate_by_form", "filter_by_date_range", "select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Authenticate via login form"},
        {"action": "get", "url": f"{P}/logs?date_from=2026-06-21T10:00&date_to=2026-06-21T10:30", "desc": "Filter logs by date range 10:00-10:30 on June 21"},
        {"action": "api", "url": f"{P}/api/logs/log-001", "desc": "Select first log entry (Connection timeout) from filtered table"},
    ],
    "entity_info": {"date_from": "2026-06-21T10:00", "date_to": "2026-06-21T10:30", "selected_log": "log-001"},
    "action_summary": "Authenticated as admin_sarah, filtered logs to 10:00-10:30 timeframe, then selected the connection timeout log entry for details."
})

# medium_007: filter_by_dropdown, search_by_query, sort_by_ranking
chains.append({
    "chain_id": f"{SITE}_medium_007",
    "difficulty": "medium",
    "macros": ["filter_by_dropdown", "search_by_query", "sort_by_ranking"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/api-gateway?method=POST", "desc": "Filter API endpoints by POST method dropdown"},
        {"action": "get", "url": f"{P}/api-gateway?method=POST&q=order", "desc": "Search within POST endpoints for 'order'"},
        {"action": "get", "url": f"{P}/api-gateway?method=POST&q=order&sort=latency", "desc": "Sort results by latency (high to low)"},
    ],
    "entity_info": {"method": "POST", "query": "order", "sort": "latency"},
    "action_summary": "Filtered API Gateway to POST methods, searched for 'order', sorted by latency. Create Order endpoint has 142ms average latency."
})

# medium_008: export_by_dropdown, navigate_by_route, select_from_table
chains.append({
    "chain_id": f"{SITE}_medium_008",
    "difficulty": "medium",
    "macros": ["export_by_dropdown", "navigate_by_route", "select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/export?resource=databases&format=json", "desc": "Export databases data as JSON"},
        {"action": "get", "url": f"{P}/databases", "desc": "Navigate to databases page via route"},
        {"action": "api", "url": f"{P}/api/databases/db-001", "desc": "Select prod-users-db from table to view details"},
    ],
    "entity_info": {"export_resource": "databases", "selected_db": "prod-users-db", "db_id": "db-001"},
    "action_summary": "Exported databases as JSON, navigated to databases page, then selected prod-users-db (PostgreSQL, 312/500GB, 145 active connections)."
})

# medium_009: authenticate_by_form, configure_by_query, extract_by_query
chains.append({
    "chain_id": f"{SITE}_medium_009",
    "difficulty": "medium",
    "macros": ["authenticate_by_form", "configure_by_query", "extract_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Authenticate via login form"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"notifications": False, "theme": "light"}, "desc": "Configure user preferences: disable notifications and set light theme"},
        {"action": "api", "url": f"{P}/api/stats", "desc": "Extract overall cloud stats via API query"},
    ],
    "entity_info": {"user": "admin_sarah", "preferences": {"notifications": False, "theme": "light"}},
    "action_summary": "Authenticated as admin_sarah, configured preferences (disabled notifications, set light theme), then extracted overall cloud statistics."
})

# medium_010: delete_from_table, export_by_dropdown, extract_by_dropdown
chains.append({
    "chain_id": f"{SITE}_medium_010",
    "difficulty": "medium",
    "macros": ["delete_from_table", "export_by_dropdown", "extract_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-009/delete", "data": {}, "desc": "Delete resolved SSL Certificate Expiry alert from table"},
        {"action": "api", "url": f"{P}/api/export?resource=billing&format=csv&category=Compute", "desc": "Export Compute billing data as CSV"},
        {"action": "get", "url": f"{P}/alerts?category=Database", "desc": "Extract alerts for Database category via dropdown"},
    ],
    "entity_info": {"deleted_alert": "alert-009", "export_category": "Compute", "alert_category": "Database"},
    "action_summary": "Deleted resolved SSL Certificate Expiry alert, exported Compute billing as CSV, then extracted Database category alerts (3 alerts)."
})

# medium_011: compute_by_slider, filter_by_checkbox, filter_by_query
chains.append({
    "chain_id": f"{SITE}_medium_011",
    "difficulty": "medium",
    "macros": ["compute_by_slider", "filter_by_checkbox", "filter_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=60", "desc": "Set CPU threshold slider to 60% to compute high-CPU data points"},
        {"action": "get", "url": f"{P}/instances?env=production", "desc": "Filter instances by production environment checkbox"},
        {"action": "get", "url": f"{P}/instances?env=production&q=api", "desc": "Further filter production instances by search query 'api'"},
    ],
    "entity_info": {"threshold": 60, "env": "production", "query": "api"},
    "action_summary": "Set CPU threshold to 60% on metrics, filtered instances to production via checkbox, then searched for 'api' within production instances."
})

# medium_012: compute_by_slider, extract_from_table, sort_by_ranking
chains.append({
    "chain_id": f"{SITE}_medium_012",
    "difficulty": "medium",
    "macros": ["compute_by_slider", "extract_from_table", "sort_by_ranking"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=50", "desc": "Set CPU threshold slider to 50% to identify high-CPU periods"},
        {"action": "get", "url": f"{P}/instances?sort=cost", "desc": "Sort instances by cost to extract table data"},
        {"action": "get", "url": f"{P}/functions?sort=invocations", "desc": "Sort functions by invocations (high to low) for ranking"},
    ],
    "entity_info": {"threshold": 50, "top_cost_instance": "ml-training-gpu", "top_invocation_function": "auth-validator"},
    "action_summary": "Set CPU threshold to 50%, extracted instance data sorted by cost (ml-training-gpu at $850/mo is most expensive), sorted functions by invocations (auth-validator leads with 28,750)."
})

# medium_013: authenticate_by_form, extract_by_route, navigate_by_route
chains.append({
    "chain_id": f"{SITE}_medium_013",
    "difficulty": "medium",
    "macros": ["authenticate_by_form", "extract_by_route", "navigate_by_route"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Authenticate via login form"},
        {"action": "api", "url": f"{P}/api/services/svc-006", "desc": "Extract Relational DB service details via API route"},
        {"action": "get", "url": f"{P}/service/svc-006", "desc": "Navigate to Relational DB service detail page via route"},
    ],
    "entity_info": {"service_id": "svc-006", "service_name": "Relational DB", "category": "Database"},
    "action_summary": "Authenticated as admin_sarah, extracted Relational DB (svc-006) details via API ($310.75/mo, us-east-1), then navigated to its detail page showing associated instances."
})

# medium_014: edit_by_form, search_by_query, verify_by_dropdown
chains.append({
    "chain_id": f"{SITE}_medium_014",
    "difficulty": "medium",
    "macros": ["edit_by_form", "search_by_query", "verify_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-001/acknowledge", "data": {}, "desc": "Edit alert-001 by acknowledging it (form-like action)"},
        {"action": "get", "url": f"{P}/logs?q=CPU", "desc": "Search logs for 'CPU' keyword"},
        {"action": "get", "url": f"{P}/alerts?status=active", "desc": "Verify active alerts via status dropdown"},
    ],
    "entity_info": {"alert_id": "alert-001", "alert_name": "High CPU Usage", "search_query": "CPU"},
    "action_summary": "Acknowledged High CPU Usage alert, searched logs for 'CPU' references, then verified remaining active alerts via status dropdown."
})

# medium_015: extract_from_table, filter_by_checkbox, sort_by_ranking
chains.append({
    "chain_id": f"{SITE}_medium_015",
    "difficulty": "medium",
    "macros": ["extract_from_table", "filter_by_checkbox", "sort_by_ranking"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/instances?env=production&sort=cost", "desc": "Filter instances by production checkbox and sort by cost"},
        {"action": "get", "url": f"{P}/instances?env=production&sort=vcpus", "desc": "Re-sort production instances by vCPUs for ranking"},
    ],
    "entity_info": {"env": "production", "top_cost": "ml-training-gpu", "top_vcpus": ["api-server-prod-1", "api-server-prod-2", "db-primary"]},
    "action_summary": "Filtered instances to production, extracted table data sorted by cost (ml-training-gpu highest), then ranked by vCPUs (8 vCPU instances at top)."
})

# medium_016: filter_by_query, navigate_by_dropdown, select_from_table
chains.append({
    "chain_id": f"{SITE}_medium_016",
    "difficulty": "medium",
    "macros": ["filter_by_query", "navigate_by_dropdown", "select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/instances?q=batch", "desc": "Filter instances by query 'batch'"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00001", "desc": "Navigate to web-server-prod-1 metrics via instance dropdown"},
        {"action": "get", "url": f"{P}/instance/i-0a1b2c3d4e5f00007", "desc": "Select worker-batch-1 from instances table"},
    ],
    "entity_info": {"query": "batch", "metrics_instance": "web-server-prod-1", "selected_instance": "worker-batch-1"},
    "action_summary": "Filtered instances for 'batch' (2 workers found), navigated to web-server-prod-1 metrics via dropdown, then selected worker-batch-1 detail page."
})

# medium_017: configure_by_query, filter_by_dropdown, submit_by_query
chains.append({
    "chain_id": f"{SITE}_medium_017",
    "difficulty": "medium",
    "macros": ["configure_by_query", "filter_by_dropdown", "submit_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"default_region": "eu-west-1"}, "desc": "Configure default region to eu-west-1"},
        {"action": "get", "url": f"{P}/services?region=eu-west-1", "desc": "Filter services by eu-west-1 region dropdown"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "region:eu-west-1 status:active"}, "desc": "Submit and save the eu-west-1 active services query"},
    ],
    "entity_info": {"region": "eu-west-1", "saved_query": "region:eu-west-1 status:active"},
    "action_summary": "Configured default region to eu-west-1, filtered services to that region (Block Storage $120/mo), saved the filter query."
})

# medium_018: configure_by_query, export_by_dropdown, search_by_query
chains.append({
    "chain_id": f"{SITE}_medium_018",
    "difficulty": "medium",
    "macros": ["configure_by_query", "export_by_dropdown", "search_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"export_format": "csv"}, "desc": "Configure preferred export format to CSV"},
        {"action": "api", "url": f"{P}/api/export?resource=functions&format=csv", "desc": "Export functions data as CSV"},
        {"action": "get", "url": f"{P}/services?q=cache", "desc": "Search services for 'cache'"},
    ],
    "entity_info": {"export_resource": "functions", "search_query": "cache"},
    "action_summary": "Configured CSV as preferred export format, exported functions data as CSV, then searched services for 'cache' (finding Cache Cluster)."
})

# medium_019: create_from_free_text, navigate_by_dropdown, submit_by_query
chains.append({
    "chain_id": f"{SITE}_medium_019",
    "difficulty": "medium",
    "macros": ["create_from_free_text", "navigate_by_dropdown", "submit_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/alerts/create", "data": {"name": "Memory Usage Critical", "severity": "critical", "resource_name": "db-primary", "condition": "Memory > 90% for 10 minutes", "category": "Database"}, "desc": "Create new alert via free text"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00005", "desc": "Navigate to db-primary metrics via instance dropdown"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "instance:db-primary memory>90%"}, "desc": "Submit and save monitoring query"},
    ],
    "entity_info": {"alert_name": "Memory Usage Critical", "instance": "db-primary"},
    "action_summary": "Created critical memory alert for db-primary, navigated to its metrics via dropdown, saved a monitoring query for future use."
})

# medium_020: compute_by_extremum, extract_by_dropdown, select_from_table
chains.append({
    "chain_id": f"{SITE}_medium_020",
    "difficulty": "medium",
    "macros": ["compute_by_extremum", "extract_by_dropdown", "select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00001", "desc": "Compute extremum metrics (max/min CPU) for web-server-prod-1"},
        {"action": "get", "url": f"{P}/billing?category=Compute", "desc": "Extract Compute billing data via category dropdown"},
        {"action": "get", "url": f"{P}/instance/i-0a1b2c3d4e5f00001", "desc": "Select web-server-prod-1 from instances table for detail view"},
    ],
    "entity_info": {"instance_id": "i-0a1b2c3d4e5f00001", "instance_name": "web-server-prod-1", "billing_category": "Compute"},
    "action_summary": "Computed extremum metrics for web-server-prod-1 (max CPU 82.3%), extracted Compute billing via dropdown, then viewed instance details."
})

# ============== HARD CHAINS ==============

# hard_001: compute_by_extremum, compute_by_slider, extract_by_query, filter_by_query, navigate_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_001",
    "difficulty": "hard",
    "macros": ["compute_by_extremum", "compute_by_slider", "extract_by_query", "filter_by_query", "navigate_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00009", "desc": "Compute extremum metrics for ml-training-gpu (max CPU)"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=90", "desc": "Set CPU threshold slider to 90%"},
        {"action": "api", "url": f"{P}/api/billing/summary?month=2026-06", "desc": "Extract billing summary for June 2026 via query"},
        {"action": "get", "url": f"{P}/instances?q=gpu", "desc": "Filter instances by query 'gpu'"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00009", "desc": "Navigate to ml-training-gpu metrics via dropdown"},
    ],
    "entity_info": {"instance": "ml-training-gpu", "max_cpu": 95.8, "threshold": 90, "june_cost": 3968.05},
    "action_summary": "Computed ml-training-gpu extremum (max CPU 95.8%), set threshold to 90%, extracted June billing ($3968.05), filtered instances for 'gpu', navigated to GPU metrics."
})

# hard_002: configure_by_query, delete_from_table, extract_by_route, navigate_by_route, select_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_002",
    "difficulty": "hard",
    "macros": ["configure_by_query", "delete_from_table", "extract_by_route", "navigate_by_route", "select_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"alert_view": "active_only"}, "desc": "Configure alert view preference to active_only"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-010/delete", "data": {}, "desc": "Delete resolved 'Disk Space Low' alert from table"},
        {"action": "api", "url": f"{P}/api/services/svc-018", "desc": "Extract Log Analytics service details via route"},
        {"action": "get", "url": f"{P}/logs", "desc": "Navigate to logs page via route"},
        {"action": "get", "url": f"{P}/logs?level=ERROR", "desc": "Select ERROR level from dropdown"},
    ],
    "entity_info": {"deleted_alert": "alert-010", "service": "Log Analytics", "log_level": "ERROR"},
    "action_summary": "Configured alert preferences, deleted resolved Disk Space Low alert, extracted Log Analytics service details, navigated to logs, filtered to ERROR level."
})

# hard_003: compute_by_extremum, configure_by_query, extract_by_route, search_by_semantic, submit_by_query
chains.append({
    "chain_id": f"{SITE}_hard_003",
    "difficulty": "hard",
    "macros": ["compute_by_extremum", "configure_by_query", "extract_by_route", "search_by_semantic", "submit_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "api", "url": f"{P}/api/metrics/summary", "desc": "Compute extremum across all instances"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"monitoring_interval": "5m"}, "desc": "Configure monitoring interval to 5 minutes"},
        {"action": "api", "url": f"{P}/api/services/svc-019", "desc": "Extract Metrics Dashboard service details"},
        {"action": "api", "url": f"{P}/api/services/semantic?q=real+time+monitoring+observability", "desc": "Semantic search for monitoring/observability services"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "category:Monitoring status:active"}, "desc": "Submit and save monitoring query"},
    ],
    "entity_info": {"monitoring_interval": "5m", "service": "Metrics Dashboard", "query": "real time monitoring observability"},
    "action_summary": "Computed global extremum metrics, configured 5m monitoring interval, extracted Metrics Dashboard details, performed semantic search for monitoring services, saved monitoring query."
})

# hard_004: extract_by_route, filter_by_query, navigate_by_dropdown, navigate_by_route, verify_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_004",
    "difficulty": "hard",
    "macros": ["extract_by_route", "filter_by_query", "navigate_by_dropdown", "navigate_by_route", "verify_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/instances/i-0a1b2c3d4e5f00003", "desc": "Extract api-server-prod-1 details via route"},
        {"action": "get", "url": f"{P}/logs?q=api-server", "desc": "Filter logs by query 'api-server'"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00003", "desc": "Navigate to api-server-prod-1 metrics via dropdown"},
        {"action": "get", "url": f"{P}/service/svc-001", "desc": "Navigate to Compute Engine service page via route"},
        {"action": "get", "url": f"{P}/alerts?status=active", "desc": "Verify active alerts via status dropdown"},
    ],
    "entity_info": {"instance": "api-server-prod-1", "service": "Compute Engine"},
    "action_summary": "Extracted api-server-prod-1 details, filtered logs for api-server entries, checked its metrics, navigated to Compute Engine service, verified active alerts."
})

# hard_005: authenticate_by_form, compute_by_extremum, extract_by_route, filter_by_dropdown, search_by_query
chains.append({
    "chain_id": f"{SITE}_hard_005",
    "difficulty": "hard",
    "macros": ["authenticate_by_form", "compute_by_extremum", "extract_by_route", "filter_by_dropdown", "search_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Authenticate via login form"},
        {"action": "api", "url": f"{P}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00005", "desc": "Compute extremum for db-primary"},
        {"action": "api", "url": f"{P}/api/databases/db-001", "desc": "Extract prod-users-db details via route"},
        {"action": "get", "url": f"{P}/databases?engine=PostgreSQL", "desc": "Filter databases by PostgreSQL engine dropdown"},
        {"action": "get", "url": f"{P}/databases?engine=PostgreSQL&q=prod", "desc": "Search within PostgreSQL databases for 'prod'"},
    ],
    "entity_info": {"db_engine": "PostgreSQL", "db_name": "prod-users-db", "instance": "db-primary"},
    "action_summary": "Authenticated, computed db-primary extremum metrics (max CPU 62.3%), extracted prod-users-db details, filtered databases to PostgreSQL, searched for 'prod'."
})

# hard_006: configure_by_query, export_by_dropdown, filter_by_query, navigate_by_route, select_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_006",
    "difficulty": "hard",
    "macros": ["configure_by_query", "export_by_dropdown", "filter_by_query", "navigate_by_route", "select_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"export_format": "csv"}, "desc": "Configure export format preference"},
        {"action": "api", "url": f"{P}/api/export?resource=storage&format=csv", "desc": "Export storage data as CSV"},
        {"action": "get", "url": f"{P}/storage?q=prod", "desc": "Filter storage buckets by query 'prod'"},
        {"action": "get", "url": f"{P}/storage", "desc": "Navigate to storage page via route"},
        {"action": "get", "url": f"{P}/storage?storage_class=Standard", "desc": "Select Standard storage class from dropdown"},
    ],
    "entity_info": {"export_resource": "storage", "query": "prod", "storage_class": "Standard"},
    "action_summary": "Configured CSV export, exported storage data, filtered for 'prod' buckets, navigated to storage page, selected Standard class via dropdown."
})

# hard_007: extract_by_route, search_by_query, search_by_semantic, submit_by_query, verify_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_007",
    "difficulty": "hard",
    "macros": ["extract_by_route", "search_by_query", "search_by_semantic", "submit_by_query", "verify_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "api", "url": f"{P}/api/services/svc-009", "desc": "Extract API Gateway service details via route"},
        {"action": "get", "url": f"{P}/api-gateway?q=authentication", "desc": "Search API endpoints for 'authentication'"},
        {"action": "api", "url": f"{P}/api/services/semantic?q=network+api+gateway+routing", "desc": "Semantic search for networking services"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "endpoint:auth method:POST"}, "desc": "Submit and save auth endpoint query"},
        {"action": "get", "url": f"{P}/api-gateway?status=active", "desc": "Verify active endpoints via status dropdown"},
    ],
    "entity_info": {"service": "API Gateway", "search_query": "authentication", "semantic_query": "network api gateway routing"},
    "action_summary": "Extracted API Gateway details, searched endpoints for 'authentication', semantic-searched for networking services, saved query, verified active endpoints."
})

# hard_008: compute_by_slider, create_from_free_text, filter_by_checkbox, navigate_by_dropdown, sort_by_ranking
chains.append({
    "chain_id": f"{SITE}_hard_008",
    "difficulty": "hard",
    "macros": ["compute_by_slider", "create_from_free_text", "filter_by_checkbox", "navigate_by_dropdown", "sort_by_ranking"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=70", "desc": "Set CPU threshold slider to 70%"},
        {"action": "post_json", "url": f"{P}/api/alerts/create", "data": {"name": "Production Memory Alert", "severity": "warning", "resource_name": "web-server-prod-1", "condition": "Memory > 70% sustained", "category": "Compute"}, "desc": "Create new alert for production memory via free text"},
        {"action": "get", "url": f"{P}/instances?env=production", "desc": "Filter instances by production environment checkbox"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00001", "desc": "Navigate to web-server-prod-1 metrics via dropdown"},
        {"action": "get", "url": f"{P}/instances?env=production&sort=cost", "desc": "Sort production instances by cost"},
    ],
    "entity_info": {"threshold": 70, "alert_name": "Production Memory Alert", "env": "production", "sort": "cost"},
    "action_summary": "Set CPU threshold to 70%, created production memory alert, filtered to production instances, navigated to web-server-prod-1 metrics, sorted by cost."
})

# hard_009: export_by_dropdown, extract_by_query, search_by_semantic, submit_by_query, verify_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_009",
    "difficulty": "hard",
    "macros": ["export_by_dropdown", "extract_by_query", "search_by_semantic", "submit_by_query", "verify_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "api", "url": f"{P}/api/export?resource=billing&format=csv", "desc": "Export billing data as CSV"},
        {"action": "api", "url": f"{P}/api/billing/summary?month=2026-05", "desc": "Extract billing summary for May 2026"},
        {"action": "api", "url": f"{P}/api/logs/semantic?q=database+connection+timeout+error", "desc": "Semantic search logs for database connection issues"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "level:ERROR category:Database"}, "desc": "Submit and save database error query"},
        {"action": "get", "url": f"{P}/alerts?severity=critical", "desc": "Verify critical alerts via severity dropdown"},
    ],
    "entity_info": {"export": "billing", "may_summary": True, "semantic_query": "database connection timeout error"},
    "action_summary": "Exported billing CSV, extracted May 2026 summary, semantic-searched logs for database issues, saved error query, verified critical alerts."
})

# hard_010: compute_by_slider, configure_by_query, delete_from_table, extract_from_table, search_by_semantic
chains.append({
    "chain_id": f"{SITE}_hard_010",
    "difficulty": "hard",
    "macros": ["compute_by_slider", "configure_by_query", "delete_from_table", "extract_from_table", "search_by_semantic"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=85", "desc": "Set CPU threshold slider to 85%"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"cpu_alert_threshold": 85}, "desc": "Configure CPU alert threshold to 85%"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-004/delete", "data": {}, "desc": "Delete resolved Lambda Error Rate Spike alert"},
        {"action": "get", "url": f"{P}/databases", "desc": "View databases table to extract data"},
        {"action": "api", "url": f"{P}/api/services/semantic?q=serverless+function+event+processing", "desc": "Semantic search for serverless services"},
    ],
    "entity_info": {"threshold": 85, "deleted_alert": "alert-004", "semantic_query": "serverless function event processing"},
    "action_summary": "Set CPU threshold to 85%, configured alert threshold preference, deleted resolved Lambda alert, extracted database table data, semantic-searched for serverless services."
})

# hard_011: configure_by_query, extract_by_dropdown, extract_by_query, filter_by_query, navigate_by_route
chains.append({
    "chain_id": f"{SITE}_hard_011",
    "difficulty": "hard",
    "macros": ["configure_by_query", "extract_by_dropdown", "extract_by_query", "filter_by_query", "navigate_by_route"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"dashboard_view": "detailed"}, "desc": "Configure dashboard view to detailed"},
        {"action": "get", "url": f"{P}/billing?month=2026-04", "desc": "Extract April billing data via month dropdown"},
        {"action": "api", "url": f"{P}/api/billing/summary?month=2026-04", "desc": "Extract April billing summary via API query"},
        {"action": "get", "url": f"{P}/services?q=monitoring", "desc": "Filter services by query 'monitoring'"},
        {"action": "get", "url": f"{P}/service/svc-019", "desc": "Navigate to Metrics Dashboard service page via route"},
    ],
    "entity_info": {"month": "2026-04", "query": "monitoring", "service": "Metrics Dashboard"},
    "action_summary": "Configured detailed dashboard view, extracted April billing via dropdown and API, filtered services for 'monitoring', navigated to Metrics Dashboard page."
})

# hard_012: edit_by_form, extract_by_route, filter_by_date_range, select_by_dropdown, verify_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_012",
    "difficulty": "hard",
    "macros": ["edit_by_form", "extract_by_route", "filter_by_date_range", "select_by_dropdown", "verify_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-006/acknowledge", "data": {}, "desc": "Edit/acknowledge WAF Blocked Requests alert"},
        {"action": "api", "url": f"{P}/api/services/svc-017", "desc": "Extract WAF Service details via route"},
        {"action": "get", "url": f"{P}/logs?date_from=2026-06-21T09:00&date_to=2026-06-21T10:00", "desc": "Filter logs by date range 09:00-10:00"},
        {"action": "get", "url": f"{P}/logs?date_from=2026-06-21T09:00&date_to=2026-06-21T10:00&level=ERROR", "desc": "Select ERROR level from dropdown"},
        {"action": "get", "url": f"{P}/alerts?status=active", "desc": "Verify active alerts via status dropdown"},
    ],
    "entity_info": {"alert": "WAF Blocked Requests", "service": "WAF Service", "date_range": "09:00-10:00"},
    "action_summary": "Acknowledged WAF alert, extracted WAF Service details, filtered logs to 09:00-10:00 window, selected ERROR level, verified active alerts."
})

# hard_013: compute_by_extremum, create_from_free_text, delete_from_table, export_by_dropdown, verify_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_013",
    "difficulty": "hard",
    "macros": ["compute_by_extremum", "create_from_free_text", "delete_from_table", "export_by_dropdown", "verify_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00003", "desc": "Compute extremum for api-server-prod-1"},
        {"action": "post_json", "url": f"{P}/api/alerts/create", "data": {"name": "API Server High Load", "severity": "critical", "resource_name": "api-server-prod-1", "condition": "CPU > 85% sustained for 15 minutes", "category": "Compute"}, "desc": "Create new critical alert via free text"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-009/delete", "data": {}, "desc": "Delete resolved SSL Certificate Expiry alert"},
        {"action": "api", "url": f"{P}/api/export?resource=services&category=Compute&format=json", "desc": "Export Compute services as JSON"},
        {"action": "get", "url": f"{P}/alerts?severity=critical", "desc": "Verify critical alerts including newly created one"},
    ],
    "entity_info": {"instance": "api-server-prod-1", "new_alert": "API Server High Load", "deleted_alert": "alert-009"},
    "action_summary": "Computed api-server-prod-1 extremum (max CPU 88.1%), created critical alert, deleted resolved SSL alert, exported Compute services, verified critical alerts."
})

# hard_014: edit_by_form, extract_by_dropdown, filter_by_query, navigate_by_route, sort_by_ranking
chains.append({
    "chain_id": f"{SITE}_hard_014",
    "difficulty": "hard",
    "macros": ["edit_by_form", "extract_by_dropdown", "filter_by_query", "navigate_by_route", "sort_by_ranking"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-003/acknowledge", "data": {}, "desc": "Edit/acknowledge Storage Capacity Warning alert"},
        {"action": "get", "url": f"{P}/billing?category=Storage", "desc": "Extract Storage billing data via category dropdown"},
        {"action": "get", "url": f"{P}/storage?q=data", "desc": "Filter storage buckets by query 'data'"},
        {"action": "get", "url": f"{P}/storage", "desc": "Navigate to storage page via route"},
        {"action": "get", "url": f"{P}/storage?sort=size", "desc": "Sort storage buckets by size (largest first)"},
    ],
    "entity_info": {"alert": "Storage Capacity Warning", "billing_category": "Storage", "query": "data"},
    "action_summary": "Acknowledged Storage Capacity Warning, extracted Storage billing via dropdown, filtered buckets for 'data', navigated to storage page, sorted by size."
})

# hard_015: configure_by_query, create_from_free_text, export_by_dropdown, extract_from_table, filter_by_query
chains.append({
    "chain_id": f"{SITE}_hard_015",
    "difficulty": "hard",
    "macros": ["configure_by_query", "create_from_free_text", "export_by_dropdown", "extract_from_table", "filter_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"auto_refresh": True, "refresh_interval": 30}, "desc": "Configure auto-refresh with 30s interval"},
        {"action": "post_json", "url": f"{P}/api/alerts/create", "data": {"name": "Network Latency Alert", "severity": "warning", "resource_name": "Load Balancer", "condition": "Latency p99 > 500ms", "category": "Networking"}, "desc": "Create network latency alert via free text"},
        {"action": "api", "url": f"{P}/api/export?resource=instances&format=json", "desc": "Export instances as JSON"},
        {"action": "get", "url": f"{P}/instances", "desc": "View instances table to extract data"},
        {"action": "get", "url": f"{P}/instances?q=server", "desc": "Filter instances by query 'server'"},
    ],
    "entity_info": {"auto_refresh": True, "alert": "Network Latency Alert", "query": "server"},
    "action_summary": "Configured auto-refresh, created network latency alert for Load Balancer, exported instances JSON, extracted table data, filtered for 'server' instances."
})

# hard_016: authenticate_by_form, export_by_dropdown, extract_from_table, filter_by_checkbox, filter_by_query
chains.append({
    "chain_id": f"{SITE}_hard_016",
    "difficulty": "hard",
    "macros": ["authenticate_by_form", "export_by_dropdown", "extract_from_table", "filter_by_checkbox", "filter_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Authenticate via login form"},
        {"action": "api", "url": f"{P}/api/export?resource=databases&format=csv", "desc": "Export databases as CSV"},
        {"action": "get", "url": f"{P}/databases", "desc": "View databases table to extract data"},
        {"action": "get", "url": f"{P}/instances?env=development", "desc": "Filter instances by development environment checkbox"},
        {"action": "get", "url": f"{P}/instances?env=development&q=sandbox", "desc": "Filter development instances by query 'sandbox'"},
    ],
    "entity_info": {"export": "databases", "env": "development", "query": "sandbox"},
    "action_summary": "Authenticated, exported databases CSV, extracted database table data, filtered instances to development environment, searched for 'sandbox' instance."
})

# hard_017: compute_by_slider, configure_by_query, extract_from_table, filter_by_query, navigate_by_dropdown
chains.append({
    "chain_id": f"{SITE}_hard_017",
    "difficulty": "hard",
    "macros": ["compute_by_slider", "configure_by_query", "extract_from_table", "filter_by_query", "navigate_by_dropdown"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=65", "desc": "Set CPU threshold slider to 65%"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"cpu_warning_threshold": 65}, "desc": "Configure CPU warning threshold to 65%"},
        {"action": "get", "url": f"{P}/functions", "desc": "View functions table to extract data"},
        {"action": "get", "url": f"{P}/functions?q=notification", "desc": "Filter functions by query 'notification'"},
        {"action": "get", "url": f"{P}/metrics?instance_id=i-0a1b2c3d4e5f00001", "desc": "Navigate to web-server-prod-1 metrics via dropdown"},
    ],
    "entity_info": {"threshold": 65, "query": "notification", "metrics_instance": "web-server-prod-1"},
    "action_summary": "Set CPU threshold to 65%, configured warning preference, extracted functions table data, filtered for 'notification', navigated to web-server-prod-1 metrics."
})

# hard_018: compute_by_extremum, compute_by_slider, edit_by_form, export_by_dropdown, select_from_table
chains.append({
    "chain_id": f"{SITE}_hard_018",
    "difficulty": "hard",
    "macros": ["compute_by_extremum", "compute_by_slider", "edit_by_form", "export_by_dropdown", "select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "api", "url": f"{P}/api/metrics/summary?instance_id=i-0a1b2c3d4e5f00001", "desc": "Compute extremum for web-server-prod-1"},
        {"action": "get", "url": f"{P}/metrics?cpu_threshold=50", "desc": "Set CPU threshold slider to 50%"},
        {"action": "post_json", "url": f"{P}/api/alerts/alert-005/acknowledge", "data": {}, "desc": "Edit/acknowledge Redis Eviction Rate alert"},
        {"action": "api", "url": f"{P}/api/export?resource=billing&format=json", "desc": "Export billing data as JSON"},
        {"action": "get", "url": f"{P}/instance/i-0a1b2c3d4e5f00005", "desc": "Select db-primary from instances table"},
    ],
    "entity_info": {"instance_1": "web-server-prod-1", "instance_2": "db-primary", "alert": "Redis Eviction Rate"},
    "action_summary": "Computed web-server-prod-1 extremum (max CPU 82.3%), set threshold to 50%, acknowledged Redis Eviction alert, exported billing JSON, selected db-primary instance."
})

# hard_019: filter_by_date_range, filter_by_dropdown, search_by_query, sort_by_ranking, submit_by_query
chains.append({
    "chain_id": f"{SITE}_hard_019",
    "difficulty": "hard",
    "macros": ["filter_by_date_range", "filter_by_dropdown", "search_by_query", "sort_by_ranking", "submit_by_query"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "get", "url": f"{P}/logs?date_from=2026-06-21T09:00&date_to=2026-06-21T10:30", "desc": "Filter logs by date range 09:00-10:30"},
        {"action": "get", "url": f"{P}/logs?date_from=2026-06-21T09:00&date_to=2026-06-21T10:30&level=WARN", "desc": "Filter by WARN level dropdown"},
        {"action": "get", "url": f"{P}/services?q=security", "desc": "Search services for 'security'"},
        {"action": "get", "url": f"{P}/services?q=security&sort=cost", "desc": "Sort security services by cost"},
        {"action": "post_json", "url": f"{P}/api/users/1/save-query", "data": {"query": "level:WARN timerange:09:00-10:30"}, "desc": "Submit and save warning log query"},
    ],
    "entity_info": {"date_range": "09:00-10:30", "level": "WARN", "search": "security"},
    "action_summary": "Filtered logs to 09:00-10:30 date range, narrowed to WARN level, searched services for 'security', sorted by cost, saved warning query."
})

# hard_020: configure_by_query, extract_from_table, filter_by_checkbox, select_by_dropdown, select_from_table
chains.append({
    "chain_id": f"{SITE}_hard_020",
    "difficulty": "hard",
    "macros": ["configure_by_query", "extract_from_table", "filter_by_checkbox", "select_by_dropdown", "select_from_table"],
    "steps": [
        {"action": "reset", "desc": "Reset state"},
        {"action": "post", "url": f"{P}/login", "data": {"username": "admin_sarah", "password": "cloudpass1"}, "desc": "Login"},
        {"action": "post_json", "url": f"{P}/api/users/1/preferences", "data": {"table_page_size": 25}, "desc": "Configure table page size to 25"},
        {"action": "get", "url": f"{P}/iam", "desc": "View IAM users table to extract data"},
        {"action": "get", "url": f"{P}/instances?env=production", "desc": "Filter instances by production checkbox"},
        {"action": "get", "url": f"{P}/instances?env=production&status=running", "desc": "Select running status from dropdown"},
        {"action": "get", "url": f"{P}/instance/i-0a1b2c3d4e5f00003", "desc": "Select api-server-prod-1 from table for details"},
    ],
    "entity_info": {"page_size": 25, "env": "production", "status": "running", "selected_instance": "api-server-prod-1"},
    "action_summary": "Configured table page size, extracted IAM table data, filtered instances to production, selected running status, viewed api-server-prod-1 details."
})

##############################################################################
# EXECUTION
##############################################################################

def execute_chain(chain_def):
    chain_id = chain_def["chain_id"]
    print(f"Walking chain: {chain_id}")

    trajectory = []
    step_num = 0
    steps_completed = 0
    valid = True
    failure_reason = None

    for step in chain_def["steps"]:
        step_num += 1
        action = step["action"]
        desc = step["desc"]

        entry = {
            "step": step_num,
            "action": action,
            "description": desc,
        }

        try:
            if action == "reset":
                result = reset()
                entry["result"] = "State reset"
                entry["url"] = None
            elif action == "get":
                url = step["url"]
                entry["url"] = url
                result = get(url)
                entry["result"] = result[:500] if result else "OK"
                if "[HTTP 404]" in result or "[HTTP 500]" in result:
                    valid = False
                    failure_reason = f"HTTP error at step {step_num}: {url}"
            elif action == "post":
                url = step["url"]
                data = step["data"]
                entry["url"] = url
                entry["data"] = data
                result = post(url, data)
                entry["result"] = result[:500] if result else "OK"
                if "[HTTP 401]" in result or "[HTTP 500]" in result:
                    valid = False
                    failure_reason = f"POST error at step {step_num}: {url}"
            elif action == "post_json":
                url = step["url"]
                data = step["data"]
                entry["url"] = url
                entry["data"] = data
                result = post_json(url, data)
                entry["result"] = result[:500] if result else "OK"
                if "[HTTP 404]" in result or "[HTTP 500]" in result:
                    valid = False
                    failure_reason = f"POST_JSON error at step {step_num}: {url}"
            elif action == "api":
                url = step["url"]
                entry["url"] = url
                result = api(url)
                entry["result"] = result[:500] if result else "OK"
                if "error" in result.lower() and "404" in result:
                    valid = False
                    failure_reason = f"API error at step {step_num}: {url}"

            steps_completed = step_num

        except Exception as e:
            entry["error"] = str(e)
            valid = False
            failure_reason = f"Exception at step {step_num}: {str(e)}"

        trajectory.append(entry)

        if not valid:
            break

    status = {
        "chain_id": chain_id,
        "site": SITE,
        "macros": chain_def["macros"],
        "difficulty": chain_def["difficulty"],
        "valid": valid,
        "failure_reason": failure_reason,
        "steps_completed": steps_completed,
        "entity_info": chain_def["entity_info"],
        "action_summary": chain_def["action_summary"]
    }

    save_chain(chain_id, status, trajectory)
    print(f"  -> {'VALID' if valid else 'INVALID: ' + str(failure_reason)}")

# Run all chains
for c in chains:
    execute_chain(c)

print(f"\nDone! Walked {len(chains)} chains.")
