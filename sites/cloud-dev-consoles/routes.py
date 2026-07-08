"""Cloud Dev Consoles -- AWS/GCP-style cloud management console.

Data interpreter: reads synthesized cloud infrastructure JSON files,
serves through Flask routes. Mutable state (users.json, alerts.json)
is modified via API calls.
"""
import hashlib
import json
import math
import pathlib
from collections import Counter
from datetime import datetime, timedelta, timezone

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db
from app.events import emit
from app.handlers.email_handler import _add_email

SITE = "cloud-dev-consoles"
SITE_DIR = pathlib.Path(__file__).resolve().parent

blueprint = Blueprint(
    "cloud-dev-consoles",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data loading helpers
# ---------------------------------------------------------------------------

def _get_services():
    return db.query(SITE, "services")

def _get_instances():
    return db.query(SITE, "instances")

def _get_functions():
    return db.query(SITE, "functions")

def _get_databases():
    return db.query(SITE, "databases")

def _get_buckets():
    return db.query(SITE, "storage_buckets")

def _get_iam_users():
    return db.query(SITE, "iam_users")

def _get_billing():
    return db.query(SITE, "billing")

def _get_metrics():
    return db.query(SITE, "metrics")

def _get_logs():
    return db.query(SITE, "logs")

def _get_api_endpoints():
    return db.query(SITE, "api_endpoints")


# ---------------------------------------------------------------------------
# Users (mutable state for console auth)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# Alerts (mutable state)
# ---------------------------------------------------------------------------

def _load_alerts(status=None):
    where = {"status": status} if status else None
    return db.query(SITE, "alerts", where=where)


def _save_alerts(alerts):
    db.save_collection(SITE, "alerts", alerts)


# ---------------------------------------------------------------------------
# Temporal simulation helpers
# ---------------------------------------------------------------------------

def _deterministic_float(seed_str, min_val=0.0, max_val=1.0):
    """Return a deterministic pseudo-random float in [min_val, max_val] from a string seed."""
    h = int(hashlib.md5(seed_str.encode()).hexdigest()[:8], 16)
    normalized = (h % 10000) / 10000.0
    return min_val + normalized * (max_val - min_val)


def _simulated_metrics_for_instance(instance_id, now=None):
    """Generate time-varying metrics for an instance based on the current time.

    The same minute always produces the same values (deterministic).
    Returns a dict with cpu_percent, memory_percent, network_in_mbps,
    network_out_mbps, disk_read_iops, disk_write_iops, request_count.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    # Quantize to the current minute for reproducibility
    minute_key = now.strftime("%Y%m%d%H%M")
    seed = f"{instance_id}:{minute_key}"

    # Use instance_id hash as a per-instance phase offset
    phase_offset = _deterministic_float(f"phase:{instance_id}", 0, 2 * math.pi)

    # Hours as a float for daily pattern (0.0 - 24.0)
    hour_frac = now.hour + now.minute / 60.0

    # --- CPU: sine wave following daily load pattern + noise ---
    # Daily pattern: low at night (0-5), ramp up to peak at ~13, back down
    daily_factor = 0.5 + 0.5 * math.sin((hour_frac - 7) * math.pi / 12)
    daily_factor = max(0.0, min(1.0, daily_factor))
    noise = _deterministic_float(f"cpu:{seed}", -0.12, 0.12)
    cpu_base = 15 + daily_factor * 55 + phase_offset * 3  # 15-85 range
    cpu = max(5.0, min(95.0, cpu_base + noise * 100))
    cpu = round(cpu, 1)

    # --- Memory: gradual climb with periodic drops (GC simulation) ---
    # Slow sawtooth: climbs over ~20 minutes, drops periodically
    cycle_pos = (now.minute % 20) / 20.0  # 0..1 within a 20-minute cycle
    gc_seed = _deterministic_float(f"gc:{instance_id}:{now.minute // 20}", 0, 1)
    if gc_seed > 0.7:
        # GC event: memory drops at the start of a new cycle
        mem_base = 35 + daily_factor * 20
    else:
        mem_base = 35 + daily_factor * 20 + cycle_pos * 18
    mem_noise = _deterministic_float(f"mem:{seed}", -3, 3)
    memory = max(20.0, min(92.0, mem_base + mem_noise))
    memory = round(memory, 1)

    # --- Network I/O: random bursts tied to request load ---
    net_base_in = 5 + daily_factor * 60
    net_burst = _deterministic_float(f"net:{seed}", 0.6, 1.5)
    network_in = round(max(1.0, net_base_in * net_burst), 1)
    network_out = round(max(1.0, network_in * _deterministic_float(f"netout:{seed}", 1.2, 2.0)), 1)

    # --- Request rate: daily pattern (low at night, peak midday) ---
    req_base = 100 + daily_factor * 9000
    req_noise = _deterministic_float(f"req:{seed}", 0.7, 1.3)
    request_count = max(10, int(req_base * req_noise))

    # --- Disk I/O ---
    disk_read = max(20, int(150 + daily_factor * 600 + _deterministic_float(f"dr:{seed}", -80, 80)))
    disk_write = max(10, int(80 + daily_factor * 400 + _deterministic_float(f"dw:{seed}", -60, 60)))

    return {
        "timestamp": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "instance_id": instance_id,
        "cpu_percent": cpu,
        "memory_percent": memory,
        "network_in_mbps": network_in,
        "network_out_mbps": network_out,
        "disk_read_iops": disk_read,
        "disk_write_iops": disk_write,
        "request_count": request_count,
    }


def _generate_live_metrics(instances, now=None):
    """Generate current simulated metrics for all running instances."""
    if now is None:
        now = datetime.now(timezone.utc)
    results = []
    for inst in instances:
        if inst.get("status") == "running":
            results.append(_simulated_metrics_for_instance(inst["id"], now))
    return results


def _generate_recent_metrics(instance_id, count=12, now=None):
    """Generate a time series of recent metrics for an instance (one per 5 min)."""
    if now is None:
        now = datetime.now(timezone.utc)
    series = []
    for i in range(count - 1, -1, -1):
        t = now - timedelta(minutes=i * 5)
        series.append(_simulated_metrics_for_instance(instance_id, t))
    return series


def _simulated_service_health(service, now=None):
    """Deterministically assign a health status to a service based on time.

    Most services are 'healthy' most of the time. Occasionally one will
    show 'degraded' or 'warning'. Returns one of: healthy, degraded, warning.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    minute_key = now.strftime("%Y%m%d%H%M")
    seed = f"health:{service['id']}:{minute_key}"
    roll = _deterministic_float(seed, 0, 1)
    # ~85% healthy, ~10% degraded, ~5% warning
    if roll < 0.85:
        return "healthy"
    elif roll < 0.95:
        return "degraded"
    else:
        return "warning"


def _relativize_log_timestamps(logs, now=None):
    """Return copies of log entries with timestamps adjusted relative to now.

    Offsets are preserved from the original data: the newest log becomes
    'just now', and older ones are spaced proportionally.
    """
    if now is None:
        now = datetime.now(timezone.utc)
    if not logs:
        return []

    result = []
    sorted_logs = sorted(logs, key=lambda l: l["timestamp"], reverse=True)
    for idx, log in enumerate(sorted_logs):
        entry = dict(log)
        # Space logs out: newest=0min, each subsequent +2-3 min
        offset_minutes = idx * 2 + int(_deterministic_float(
            f"logoff:{log['id']}", 0, 2))
        log_time = now - timedelta(minutes=offset_minutes)
        entry["timestamp"] = log_time.strftime("%Y-%m-%dT%H:%M:%SZ")
        entry["relative_time"] = _format_relative_time(offset_minutes)
        result.append(entry)
    return result


def _format_relative_time(minutes):
    """Format a minute offset as a human-readable relative time string."""
    if minutes < 1:
        return "just now"
    elif minutes < 60:
        return f"{minutes} min ago"
    elif minutes < 1440:
        hours = minutes // 60
        return f"{hours}h ago"
    else:
        days = minutes // 1440
        return f"{days}d ago"


# ---------------------------------------------------------------------------
# Search / filter helpers
# ---------------------------------------------------------------------------

def _search_resources(resources, query, fields=None):
    """Generic keyword search across resource fields."""
    if not query:
        return resources
    q = query.lower().strip()
    results = []
    for r in resources:
        searchable = ""
        if fields:
            for f in fields:
                val = r.get(f, "")
                if isinstance(val, list):
                    searchable += " ".join(str(v) for v in val) + " "
                elif isinstance(val, dict):
                    searchable += " ".join(str(v) for v in val.values()) + " "
                else:
                    searchable += str(val) + " "
        else:
            searchable = json.dumps(r)
        if q in searchable.lower():
            results.append(r)
    return results


def _semantic_search(resources, query, fields=None):
    """Score-based search that ranks by term frequency."""
    if not query:
        return resources
    terms = query.lower().split()
    scored = []
    for r in resources:
        if fields:
            text = ""
            for f in fields:
                val = r.get(f, "")
                if isinstance(val, list):
                    text += " ".join(str(v) for v in val) + " "
                elif isinstance(val, dict):
                    text += " ".join(str(v) for v in val.values()) + " "
                else:
                    text += str(val) + " "
        else:
            text = json.dumps(r)
        text = text.lower()
        score = sum(1 for t in terms if t in text)
        if score > 0:
            scored.append((r, score))
    scored.sort(key=lambda x: -x[1])
    return [r for r, _ in scored]


# ---------------------------------------------------------------------------
# Service categories
# ---------------------------------------------------------------------------

def _get_service_categories():
    services = _get_services()
    return sorted(set(s["category"] for s in services))


def _get_regions():
    services = _get_services()
    instances = _get_instances()
    regions = set()
    for s in services:
        regions.add(s["region"])
    for i in instances:
        regions.add(i["region"])
    return sorted(regions)


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    services = _get_services()
    instances = _get_instances()
    alerts = _load_alerts()
    billing = _get_billing()
    logs = _get_logs()
    categories = _get_service_categories()

    now = datetime.now(timezone.utc)

    # Summary stats
    running_instances = sum(1 for i in instances if i["status"] == "running")
    total_instances = len(instances)
    active_alerts = sum(1 for a in alerts if a["status"] == "active")
    critical_alerts = sum(1 for a in alerts if a["status"] == "active" and a["severity"] == "critical")

    # Current month billing
    current_month = now.strftime("%Y-%m")
    month_billing = [b for b in billing if b["month"] == current_month]
    if not month_billing:
        month_billing = [b for b in billing if b["month"] == "2026-06"]
    total_cost = sum(b["cost"] for b in month_billing)
    total_budget = sum(b["budget"] for b in month_billing)

    # Simulated real-time metrics for running instances
    live_metrics = _generate_live_metrics(instances, now)

    # Aggregate live metrics for dashboard summary
    if live_metrics:
        avg_cpu = round(sum(m["cpu_percent"] for m in live_metrics) / len(live_metrics), 1)
        avg_memory = round(sum(m["memory_percent"] for m in live_metrics) / len(live_metrics), 1)
        total_requests = sum(m["request_count"] for m in live_metrics)
    else:
        avg_cpu = 0.0
        avg_memory = 0.0
        total_requests = 0

    # Service health status
    services_with_health = []
    for svc in services:
        svc_copy = dict(svc)
        svc_copy["health"] = _simulated_service_health(svc, now)
        services_with_health.append(svc_copy)

    health_counts = Counter(s["health"] for s in services_with_health)

    # Recent logs with relative timestamps
    recent_logs = _relativize_log_timestamps(logs[:10], now)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/index.html",
                           services=services_with_health, categories=categories,
                           running_instances=running_instances,
                           total_instances=total_instances,
                           active_alerts=active_alerts,
                           critical_alerts=critical_alerts,
                           total_cost=total_cost, total_budget=total_budget,
                           alerts=alerts, user=user,
                           live_metrics=live_metrics,
                           avg_cpu=avg_cpu, avg_memory=avg_memory,
                           total_requests=total_requests,
                           health_counts=health_counts,
                           recent_logs=recent_logs,
                           now=now)


@blueprint.route("/services")
def services_page():
    services = _get_services()
    categories = _get_service_categories()
    now = datetime.now(timezone.utc)

    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    region = request.args.get("region", "").strip()
    sort = request.args.get("sort", "name").strip()

    # Attach health status
    results = []
    for svc in services:
        svc_copy = dict(svc)
        svc_copy["health"] = _simulated_service_health(svc, now)
        results.append(svc_copy)

    if q:
        results = _search_resources(results, q, ["name", "description", "category", "tags"])
    if cat:
        results = [s for s in results if s["category"] == cat]
    if status:
        results = [s for s in results if s["status"] == status]
    if region:
        results = [s for s in results if s["region"] == region]

    if sort == "name":
        results.sort(key=lambda s: s["name"].lower())
    elif sort == "cost":
        results.sort(key=lambda s: -s["monthly_cost"])
    elif sort == "category":
        results.sort(key=lambda s: (s["category"], s["name"].lower()))
    elif sort == "date":
        results.sort(key=lambda s: s["created_date"], reverse=True)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/services.html",
                           services=results, categories=categories,
                           regions=_get_regions(), q=q, cat=cat,
                           status=status, region=region, sort=sort, user=user)


@blueprint.route("/service/<service_id>")
def service_detail(service_id):
    services = _get_services()
    service = next((s for s in services if s["id"] == service_id), None)
    if service is None:
        abort(404)

    now = datetime.now(timezone.utc)

    # Add health status to service
    service = dict(service)
    service["health"] = _simulated_service_health(service, now)

    instances = [i for i in _get_instances() if i.get("service_id") == service_id]
    related_logs = [l for l in _get_logs()
                    if l.get("source") == service_id or
                    any(i["id"] == l.get("source") for i in instances)][:10]
    related_logs = _relativize_log_timestamps(related_logs, now)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/service_detail.html",
                           service=service, instances=instances,
                           logs=related_logs, user=user)


@blueprint.route("/instances")
def instances_page():
    instances = _get_instances()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    region = request.args.get("region", "").strip()
    env = request.args.get("env", "").strip()
    sort = request.args.get("sort", "name").strip()

    results = list(instances)
    if q:
        results = _search_resources(results, q, ["name", "id", "type", "os", "tags"])
    if status:
        results = [i for i in results if i["status"] == status]
    if region:
        results = [i for i in results if i["region"] == region]
    if env:
        results = [i for i in results if i.get("tags", {}).get("env") == env]

    if sort == "name":
        results.sort(key=lambda i: i["name"].lower())
    elif sort == "cost":
        results.sort(key=lambda i: -i["monthly_cost"])
    elif sort == "type":
        results.sort(key=lambda i: i["type"])
    elif sort == "vcpus":
        results.sort(key=lambda i: -i["vcpus"])

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/instances.html",
                           instances=results, regions=_get_regions(),
                           q=q, status=status, region=region, env=env,
                           sort=sort, user=user)


@blueprint.route("/instance/<instance_id>")
def instance_detail(instance_id):
    instances = _get_instances()
    instance = next((i for i in instances if i["id"] == instance_id), None)
    if instance is None:
        abort(404)

    now = datetime.now(timezone.utc)

    # Use simulated recent metrics (last hour, every 5 min) for running instances
    if instance.get("status") == "running":
        metrics = _generate_recent_metrics(instance_id, count=12, now=now)
    else:
        metrics = [m for m in _get_metrics() if m["instance_id"] == instance_id]
        metrics.sort(key=lambda m: m["timestamp"])

    # Current live metric snapshot
    live = _simulated_metrics_for_instance(instance_id, now)

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/instance_detail.html",
                           instance=instance, metrics=metrics,
                           live=live, user=user)


@blueprint.route("/instance/<instance_id>/delete", methods=["POST"])
def form_delete_instance(instance_id):
    """Delete (terminate) an instance."""
    instances = _get_instances()
    instance = next((i for i in instances if i["id"] == instance_id), None)
    if not instance:
        abort(404)
    instance["status"] = "terminated"
    db.save_collection(SITE, "instances", instances)
    return redirect(url_for("cloud-dev-consoles.instances_page"))


@blueprint.route("/instances/create", methods=["POST"])
def form_create_instance():
    """Launch a new instance from the Instances page form (create_by_form)."""
    instances = _get_instances()
    region = request.form.get("region", "us-west-2").strip() or "us-west-2"
    instances.append({
        "id": f"i-user{len(instances) + 1:012d}",
        "name": request.form.get("name", "").strip() or f"new-instance-{len(instances) + 1}",
        "type": request.form.get("type", "t3.medium").strip() or "t3.medium",
        "vcpus": request.form.get("vcpus", 2, type=int) or 2,
        "memory_gb": request.form.get("memory_gb", 4, type=int) or 4,
        "status": "running", "region": region, "availability_zone": f"{region}a",
        "private_ip": f"10.0.9.{(len(instances) % 250) + 1}", "public_ip": "",
        "os": request.form.get("os", "Amazon Linux 2023").strip() or "Amazon Linux 2023",
        "service_id": "", "monthly_cost": 0.0,
        "launched": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "tags": {"env": request.form.get("env", "development").strip() or "development"},
    })
    db.save_collection(SITE, "instances", instances)
    return redirect(url_for("cloud-dev-consoles.instances_page"))


@blueprint.route("/instance/<instance_id>/edit", methods=["POST"])
def form_edit_instance(instance_id):
    """Edit instance configuration from the detail page form (edit_by_form)."""
    instances = _get_instances()
    instance = next((i for i in instances if i["id"] == instance_id), None)
    if not instance:
        abort(404)
    for field in ("name", "type", "os"):
        val = request.form.get(field, "").strip()
        if val:
            instance[field] = val
    for field in ("vcpus", "memory_gb"):
        val = request.form.get(field, type=int)
        if val:
            instance[field] = val
    db.save_collection(SITE, "instances", instances)
    return redirect(url_for("cloud-dev-consoles.instance_detail", instance_id=instance_id))


@blueprint.route("/functions/create", methods=["POST"])
def form_create_function():
    """Create a new function from the Functions page form (create_by_form)."""
    functions = _get_functions()
    functions.append({
        "id": f"fn-user{len(functions) + 1:03d}",
        "name": request.form.get("name", "").strip() or f"new-function-{len(functions) + 1}",
        "runtime": request.form.get("runtime", "python3.12").strip() or "python3.12",
        "memory_mb": request.form.get("memory_mb", 256, type=int) or 256,
        "timeout_sec": request.form.get("timeout_sec", 30, type=int) or 30,
        "status": "active",
        "region": request.form.get("region", "us-west-2").strip() or "us-west-2",
        "handler": request.form.get("handler", "").strip() or "index.handler",
        "last_invoked": "", "invocations_24h": 0, "avg_duration_ms": 0,
        "error_rate": 0.0, "monthly_cost": 0.0,
        "tags": {"env": request.form.get("env", "development").strip() or "development"},
    })
    db.save_collection(SITE, "functions", functions)
    return redirect(url_for("cloud-dev-consoles.functions_page"))


@blueprint.route("/databases")
def databases_page():
    databases = _get_databases()
    q = request.args.get("q", "").strip()
    engine = request.args.get("engine", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name").strip()

    results = list(databases)
    if q:
        results = _search_resources(results, q, ["name", "engine", "tags"])
    if engine:
        results = [d for d in results if d["engine"] == engine]
    if status:
        results = [d for d in results if d["status"] == status]

    if sort == "name":
        results.sort(key=lambda d: d["name"].lower())
    elif sort == "cost":
        results.sort(key=lambda d: -d["monthly_cost"])
    elif sort == "storage":
        results.sort(key=lambda d: -d["storage_used_gb"])
    elif sort == "connections":
        results.sort(key=lambda d: -d["connections_active"])

    engines = sorted(set(d["engine"] for d in databases))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/databases.html",
                           databases=results, engines=engines,
                           q=q, engine=engine, status=status,
                           sort=sort, user=user)


@blueprint.route("/functions")
def functions_page():
    functions = _get_functions()
    q = request.args.get("q", "").strip()
    runtime = request.args.get("runtime", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name").strip()

    results = list(functions)
    if q:
        results = _search_resources(results, q, ["name", "runtime", "handler", "tags"])
    if runtime:
        results = [f for f in results if f["runtime"] == runtime]
    if status:
        results = [f for f in results if f["status"] == status]

    if sort == "name":
        results.sort(key=lambda f: f["name"].lower())
    elif sort == "invocations":
        results.sort(key=lambda f: -f["invocations_24h"])
    elif sort == "duration":
        results.sort(key=lambda f: -f["avg_duration_ms"])
    elif sort == "errors":
        results.sort(key=lambda f: -f["error_rate"])

    runtimes = sorted(set(f["runtime"] for f in functions))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/functions.html",
                           functions=results, runtimes=runtimes,
                           q=q, runtime=runtime, status=status,
                           sort=sort, user=user)


@blueprint.route("/storage")
def storage_page():
    buckets = _get_buckets()
    q = request.args.get("q", "").strip()
    storage_class = request.args.get("storage_class", "").strip()
    sort = request.args.get("sort", "name").strip()

    results = list(buckets)
    if q:
        results = _search_resources(results, q, ["name", "region", "tags"])
    if storage_class:
        results = [b for b in results if b["storage_class"] == storage_class]

    if sort == "name":
        results.sort(key=lambda b: b["name"].lower())
    elif sort == "size":
        results.sort(key=lambda b: -b["size_gb"])
    elif sort == "objects":
        results.sort(key=lambda b: -b["object_count"])
    elif sort == "cost":
        results.sort(key=lambda b: -b["monthly_cost"])

    storage_classes = sorted(set(b["storage_class"] for b in buckets))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/storage.html",
                           buckets=results, storage_classes=storage_classes,
                           q=q, storage_class=storage_class, sort=sort,
                           user=user)


@blueprint.route("/iam")
def iam_page():
    iam_users = _get_iam_users()
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name").strip()

    results = list(iam_users)
    if q:
        results = _search_resources(results, q, ["username", "name", "email", "role", "policies"])
    if role:
        results = [u for u in results if u["role"] == role]
    if status:
        results = [u for u in results if u["status"] == status]

    if sort == "name":
        results.sort(key=lambda u: u["name"].lower())
    elif sort == "role":
        results.sort(key=lambda u: u["role"])
    elif sort == "last_login":
        results.sort(key=lambda u: u["last_login"], reverse=True)

    roles = sorted(set(u["role"] for u in iam_users))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/iam.html",
                           iam_users=results, roles=roles,
                           q=q, role=role, status=status,
                           sort=sort, user=user)


@blueprint.route("/billing")
def billing_page():
    billing = _get_billing()
    month = request.args.get("month", "").strip()
    category = request.args.get("category", "").strip()

    results = list(billing)
    if month:
        results = [b for b in results if b["month"] == month]
    if category:
        results = [b for b in results if b["service_category"] == category]

    months = sorted(set(b["month"] for b in billing))
    bill_categories = sorted(set(b["service_category"] for b in billing))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/billing.html",
                           billing=results, months=months,
                           bill_categories=bill_categories,
                           month=month, category=category, user=user)


@blueprint.route("/logs")
def logs_page():
    logs = _get_logs()
    now = datetime.now(timezone.utc)
    q = request.args.get("q", "").strip()
    level = request.args.get("level", "").strip()
    category = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "time").strip()

    # Relativize timestamps so logs look fresh
    results = _relativize_log_timestamps(logs, now)

    if q:
        results = _search_resources(results, q, ["message", "service", "source", "trace_id"])
    if level:
        results = [l for l in results if l["level"] == level]
    if category:
        results = [l for l in results if l["category"] == category]
    if date_from:
        results = [l for l in results if l["timestamp"] >= date_from]
    if date_to:
        results = [l for l in results if l["timestamp"] <= date_to]

    if sort == "time":
        results.sort(key=lambda l: l["timestamp"], reverse=True)
    elif sort == "level":
        level_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        results.sort(key=lambda l: level_order.get(l["level"], 3))
    elif sort == "service":
        results.sort(key=lambda l: l["service"])

    levels = sorted(set(l["level"] for l in logs))
    log_categories = sorted(set(l["category"] for l in logs))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/logs.html",
                           logs=results, levels=levels,
                           log_categories=log_categories,
                           q=q, level=level, category=category,
                           date_from=date_from, date_to=date_to,
                           sort=sort, user=user)


@blueprint.route("/alerts")
def alerts_page():
    alerts = _load_alerts()
    status_filter = request.args.get("status", "").strip()
    severity = request.args.get("severity", "").strip()
    category = request.args.get("category", "").strip()

    results = list(alerts)
    if status_filter:
        results = [a for a in results if a["status"] == status_filter]
    if severity:
        results = [a for a in results if a["severity"] == severity]
    if category:
        results = [a for a in results if a["category"] == category]

    results.sort(key=lambda a: a["triggered_at"], reverse=True)

    alert_categories = sorted(set(a["category"] for a in alerts))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/alerts.html",
                           alerts=results, alert_categories=alert_categories,
                           status=status_filter, severity=severity,
                           category=category, user=user)


@blueprint.route("/metrics")
def metrics_page():
    instances = _get_instances()
    instance_id = request.args.get("instance_id", "").strip()
    threshold = request.args.get("cpu_threshold", type=float)

    now = datetime.now(timezone.utc)

    # Include simulated live metrics alongside historical data
    metrics = list(_get_metrics())
    live_metrics = _generate_live_metrics(instances, now)
    metrics.extend(live_metrics)

    if instance_id:
        metrics = [m for m in metrics if m["instance_id"] == instance_id]

    metrics.sort(key=lambda m: m["timestamp"])

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/metrics.html",
                           metrics=metrics, instances=instances,
                           instance_id=instance_id,
                           threshold=threshold, user=user)


@blueprint.route("/api-gateway")
def api_gateway_page():
    endpoints = _get_api_endpoints()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    method = request.args.get("method", "").strip()
    sort = request.args.get("sort", "name").strip()

    results = list(endpoints)
    if q:
        results = _search_resources(results, q, ["name", "path", "description"])
    if status:
        results = [e for e in results if e["status"] == status]
    if method:
        results = [e for e in results if e["method"] == method]

    if sort == "name":
        results.sort(key=lambda e: e["name"].lower())
    elif sort == "requests":
        results.sort(key=lambda e: -e["requests_24h"])
    elif sort == "latency":
        results.sort(key=lambda e: -e["avg_latency_ms"])
    elif sort == "errors":
        results.sort(key=lambda e: -e["error_rate_percent"])

    methods = sorted(set(e["method"] for e in endpoints))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("cloud-dev-consoles/api_gateway.html",
                           endpoints=results, methods=methods,
                           q=q, status=status, method=method,
                           sort=sort, user=user)


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return render_template("cloud-dev-consoles/login.html", error=None)
    user = _get_user(session["user_id"])
    if not user:
        return render_template("cloud-dev-consoles/login.html", error=None)

    return render_template("cloud-dev-consoles/dashboard.html", user=user,
                           recent_services=user.get("recent_services", []),
                           saved_queries=user.get("saved_queries", []))


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("cloud-dev-consoles/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("cloud-dev-consoles/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    emit("signup", user_id=user["id"], site_name="cloud-dev-consoles", username=request.form.get("username", ""), password=request.form.get("password", ""), email="")
    return render_template("cloud-dev-consoles/dashboard.html", user=user,
                           recent_services=user.get("recent_services", []),
                           saved_queries=user.get("saved_queries", []))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("cloud-dev-consoles/login.html", error=None)


# ---------------------------------------------------------------------------
# API routes -- Services
# ---------------------------------------------------------------------------

@blueprint.route("/api/services")
def api_services():
    services = _get_services()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    status = request.args.get("status", "").strip()
    region = request.args.get("region", "").strip()
    sort = request.args.get("sort", "name")
    limit = request.args.get("limit", type=int)

    results = list(services)
    if q:
        results = _search_resources(results, q, ["name", "description", "category", "tags"])
    if cat:
        results = [s for s in results if s["category"] == cat]
    if status:
        results = [s for s in results if s["status"] == status]
    if region:
        results = [s for s in results if s["region"] == region]

    if sort == "name":
        results.sort(key=lambda s: s["name"].lower())
    elif sort == "cost":
        results.sort(key=lambda s: -s["monthly_cost"])
    elif sort == "category":
        results.sort(key=lambda s: (s["category"], s["name"].lower()))

    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/services/<service_id>")
def api_service(service_id):
    services = _get_services()
    service = next((s for s in services if s["id"] == service_id), None)
    if service is None:
        abort(404)
    return jsonify(service)


@blueprint.route("/api/services/search")
def api_services_search():
    q = request.args.get("q", "").strip()
    services = _get_services()
    return jsonify(_search_resources(services, q, ["name", "description", "category", "tags"]))


@blueprint.route("/api/services/semantic")
def api_services_semantic():
    q = request.args.get("q", "").strip()
    services = _get_services()
    return jsonify(_semantic_search(services, q, ["name", "description", "category", "tags"]))


@blueprint.route("/api/services/categories")
def api_service_categories():
    services = _get_services()
    counts = Counter(s["category"] for s in services)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/services/categories/<cat_name>")
def api_services_by_category(cat_name):
    services = _get_services()
    return jsonify([s for s in services if s["category"] == cat_name])


# ---------------------------------------------------------------------------
# API routes -- Instances
# ---------------------------------------------------------------------------

@blueprint.route("/api/instances")
def api_instances():
    instances = _get_instances()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    region = request.args.get("region", "").strip()
    env = request.args.get("env", "").strip()
    sort = request.args.get("sort", "name")

    results = list(instances)
    if q:
        results = _search_resources(results, q, ["name", "id", "type", "os", "tags"])
    if status:
        results = [i for i in results if i["status"] == status]
    if region:
        results = [i for i in results if i["region"] == region]
    if env:
        results = [i for i in results if i.get("tags", {}).get("env") == env]

    if sort == "name":
        results.sort(key=lambda i: i["name"].lower())
    elif sort == "cost":
        results.sort(key=lambda i: -i["monthly_cost"])
    elif sort == "vcpus":
        results.sort(key=lambda i: -i["vcpus"])
    elif sort == "memory":
        results.sort(key=lambda i: -i["memory_gb"])

    return jsonify(results)


@blueprint.route("/api/instances/<instance_id>")
def api_instance(instance_id):
    instances = _get_instances()
    instance = next((i for i in instances if i["id"] == instance_id), None)
    if instance is None:
        abort(404)
    return jsonify(instance)


# ---------------------------------------------------------------------------
# API routes -- Functions
# ---------------------------------------------------------------------------

@blueprint.route("/api/functions")
def api_functions():
    functions = _get_functions()
    q = request.args.get("q", "").strip()
    runtime = request.args.get("runtime", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name")

    results = list(functions)
    if q:
        results = _search_resources(results, q, ["name", "runtime", "handler", "tags"])
    if runtime:
        results = [f for f in results if f["runtime"] == runtime]
    if status:
        results = [f for f in results if f["status"] == status]

    if sort == "name":
        results.sort(key=lambda f: f["name"].lower())
    elif sort == "invocations":
        results.sort(key=lambda f: -f["invocations_24h"])
    elif sort == "duration":
        results.sort(key=lambda f: -f["avg_duration_ms"])
    elif sort == "errors":
        results.sort(key=lambda f: -f["error_rate"])

    return jsonify(results)


@blueprint.route("/api/functions/<function_id>")
def api_function(function_id):
    functions = _get_functions()
    func = next((f for f in functions if f["id"] == function_id), None)
    if func is None:
        abort(404)
    return jsonify(func)


# ---------------------------------------------------------------------------
# API routes -- Databases
# ---------------------------------------------------------------------------

@blueprint.route("/api/databases")
def api_databases():
    databases = _get_databases()
    q = request.args.get("q", "").strip()
    engine = request.args.get("engine", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name")

    results = list(databases)
    if q:
        results = _search_resources(results, q, ["name", "engine", "tags"])
    if engine:
        results = [d for d in results if d["engine"] == engine]
    if status:
        results = [d for d in results if d["status"] == status]

    if sort == "name":
        results.sort(key=lambda d: d["name"].lower())
    elif sort == "cost":
        results.sort(key=lambda d: -d["monthly_cost"])
    elif sort == "storage":
        results.sort(key=lambda d: -d["storage_used_gb"])
    elif sort == "connections":
        results.sort(key=lambda d: -d["connections_active"])

    return jsonify(results)


@blueprint.route("/api/databases/<db_id>")
def api_database(db_id):
    databases = _get_databases()
    db = next((d for d in databases if d["id"] == db_id), None)
    if db is None:
        abort(404)
    return jsonify(db)


# ---------------------------------------------------------------------------
# API routes -- Storage
# ---------------------------------------------------------------------------

@blueprint.route("/api/storage")
def api_storage():
    buckets = _get_buckets()
    q = request.args.get("q", "").strip()
    storage_class = request.args.get("storage_class", "").strip()
    sort = request.args.get("sort", "name")

    results = list(buckets)
    if q:
        results = _search_resources(results, q, ["name", "region", "tags"])
    if storage_class:
        results = [b for b in results if b["storage_class"] == storage_class]

    if sort == "name":
        results.sort(key=lambda b: b["name"].lower())
    elif sort == "size":
        results.sort(key=lambda b: -b["size_gb"])
    elif sort == "objects":
        results.sort(key=lambda b: -b["object_count"])
    elif sort == "cost":
        results.sort(key=lambda b: -b["monthly_cost"])

    return jsonify(results)


@blueprint.route("/api/storage/<bucket_id>")
def api_bucket(bucket_id):
    buckets = _get_buckets()
    bucket = next((b for b in buckets if b["id"] == bucket_id), None)
    if bucket is None:
        abort(404)
    return jsonify(bucket)


# ---------------------------------------------------------------------------
# API routes -- IAM
# ---------------------------------------------------------------------------

@blueprint.route("/api/iam")
def api_iam():
    iam_users = _get_iam_users()
    q = request.args.get("q", "").strip()
    role = request.args.get("role", "").strip()
    status = request.args.get("status", "").strip()
    sort = request.args.get("sort", "name")

    results = list(iam_users)
    if q:
        results = _search_resources(results, q, ["username", "name", "email", "role", "policies"])
    if role:
        results = [u for u in results if u["role"] == role]
    if status:
        results = [u for u in results if u["status"] == status]

    if sort == "name":
        results.sort(key=lambda u: u["name"].lower())
    elif sort == "role":
        results.sort(key=lambda u: u["role"])
    elif sort == "last_login":
        results.sort(key=lambda u: u["last_login"], reverse=True)

    return jsonify(results)


@blueprint.route("/api/iam/<user_id>")
def api_iam_user(user_id):
    iam_users = _get_iam_users()
    user = next((u for u in iam_users if u["id"] == user_id), None)
    if user is None:
        abort(404)
    return jsonify(user)


# ---------------------------------------------------------------------------
# API routes -- Billing
# ---------------------------------------------------------------------------

@blueprint.route("/api/billing")
def api_billing():
    billing = _get_billing()
    month = request.args.get("month", "").strip()
    category = request.args.get("category", "").strip()

    results = list(billing)
    if month:
        results = [b for b in results if b["month"] == month]
    if category:
        results = [b for b in results if b["service_category"] == category]

    return jsonify(results)


@blueprint.route("/api/billing/summary")
def api_billing_summary():
    billing = _get_billing()
    month = request.args.get("month", "").strip()

    if month:
        month_data = [b for b in billing if b["month"] == month]
    else:
        month_data = billing

    total_cost = sum(b["cost"] for b in month_data)
    total_budget = sum(b["budget"] for b in month_data)
    by_category = {}
    for b in month_data:
        cat = b["service_category"]
        if cat not in by_category:
            by_category[cat] = {"cost": 0, "budget": 0}
        by_category[cat]["cost"] += b["cost"]
        by_category[cat]["budget"] += b["budget"]

    return jsonify({
        "total_cost": round(total_cost, 2),
        "total_budget": round(total_budget, 2),
        "by_category": by_category,
        "month": month if month else "all"
    })


# ---------------------------------------------------------------------------
# API routes -- Metrics
# ---------------------------------------------------------------------------

@blueprint.route("/api/metrics")
def api_metrics():
    metrics = _get_metrics()
    now = datetime.now(timezone.utc)
    instances = _get_instances()

    # Append current live metrics
    results = list(metrics)
    results.extend(_generate_live_metrics(instances, now))

    instance_id = request.args.get("instance_id", "").strip()
    time_from = request.args.get("time_from", "").strip()
    time_to = request.args.get("time_to", "").strip()

    if instance_id:
        results = [m for m in results if m["instance_id"] == instance_id]
    if time_from:
        results = [m for m in results if m["timestamp"] >= time_from]
    if time_to:
        results = [m for m in results if m["timestamp"] <= time_to]

    results.sort(key=lambda m: m["timestamp"])
    return jsonify(results)


@blueprint.route("/api/metrics/summary")
def api_metrics_summary():
    metrics = _get_metrics()
    instance_id = request.args.get("instance_id", "").strip()

    if instance_id:
        metrics = [m for m in metrics if m["instance_id"] == instance_id]

    if not metrics:
        return jsonify({"count": 0})

    cpu_values = [m["cpu_percent"] for m in metrics]
    mem_values = [m["memory_percent"] for m in metrics]
    req_values = [m["request_count"] for m in metrics]

    return jsonify({
        "count": len(metrics),
        "cpu_avg": round(sum(cpu_values) / len(cpu_values), 2),
        "cpu_max": max(cpu_values),
        "cpu_min": min(cpu_values),
        "memory_avg": round(sum(mem_values) / len(mem_values), 2),
        "memory_max": max(mem_values),
        "total_requests": sum(req_values),
    })


# ---------------------------------------------------------------------------
# API routes -- Logs
# ---------------------------------------------------------------------------

@blueprint.route("/api/logs")
def api_logs():
    logs = _get_logs()
    q = request.args.get("q", "").strip()
    level = request.args.get("level", "").strip()
    category = request.args.get("category", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "time")

    results = list(logs)
    if q:
        results = _search_resources(results, q, ["message", "service", "source", "trace_id"])
    if level:
        results = [l for l in results if l["level"] == level]
    if category:
        results = [l for l in results if l["category"] == category]
    if date_from:
        results = [l for l in results if l["timestamp"] >= date_from]
    if date_to:
        results = [l for l in results if l["timestamp"] <= date_to]

    if sort == "time":
        results.sort(key=lambda l: l["timestamp"], reverse=True)
    elif sort == "level":
        level_order = {"ERROR": 0, "WARN": 1, "INFO": 2}
        results.sort(key=lambda l: level_order.get(l["level"], 3))

    return jsonify(results)


@blueprint.route("/api/logs/<log_id>")
def api_log(log_id):
    logs = _get_logs()
    log = next((l for l in logs if l["id"] == log_id), None)
    if log is None:
        abort(404)
    return jsonify(log)


@blueprint.route("/api/logs/search")
def api_logs_search():
    q = request.args.get("q", "").strip()
    logs = _get_logs()
    return jsonify(_search_resources(logs, q, ["message", "service", "source", "trace_id"]))


@blueprint.route("/api/logs/semantic")
def api_logs_semantic():
    q = request.args.get("q", "").strip()
    logs = _get_logs()
    return jsonify(_semantic_search(logs, q, ["message", "service", "source", "category"]))


# ---------------------------------------------------------------------------
# API routes -- Alerts
# ---------------------------------------------------------------------------

@blueprint.route("/api/alerts")
def api_alerts():
    alerts = _load_alerts()
    status_filter = request.args.get("status", "").strip()
    severity = request.args.get("severity", "").strip()
    category = request.args.get("category", "").strip()

    results = list(alerts)
    if status_filter:
        results = [a for a in results if a["status"] == status_filter]
    if severity:
        results = [a for a in results if a["severity"] == severity]
    if category:
        results = [a for a in results if a["category"] == category]

    results.sort(key=lambda a: a["triggered_at"], reverse=True)
    return jsonify(results)


@blueprint.route("/api/alerts/<alert_id>")
def api_alert(alert_id):
    alerts = _load_alerts()
    alert = next((a for a in alerts if a["id"] == alert_id), None)
    if alert is None:
        abort(404)
    return jsonify(alert)


@blueprint.route("/api/alerts/<alert_id>/acknowledge", methods=["POST"])
def api_acknowledge_alert(alert_id):
    alerts = _load_alerts()
    alert = next((a for a in alerts if a["id"] == alert_id), None)
    if alert is None:
        abort(404)
    alert["acknowledged"] = True
    _save_alerts(alerts)
    return jsonify({"action": "acknowledged", "alert_id": alert_id})


@blueprint.route("/api/alerts/<alert_id>/resolve", methods=["POST"])
def api_resolve_alert(alert_id):
    alerts = _load_alerts()
    alert = next((a for a in alerts if a["id"] == alert_id), None)
    if alert is None:
        abort(404)
    alert["status"] = "resolved"
    alert["acknowledged"] = True
    _save_alerts(alerts)
    return jsonify({"action": "resolved", "alert_id": alert_id})


@blueprint.route("/api/alerts/create", methods=["POST"])
def api_create_alert():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    severity = data.get("severity", "warning")
    resource_name = data.get("resource_name", "").strip()
    condition = data.get("condition", "").strip()
    category = data.get("category", "Custom")

    if not name:
        return jsonify({"error": "name required"}), 400

    alerts = _load_alerts()
    new_id = f"alert-{len(alerts)+1:03d}"
    new_alert = {
        "id": new_id,
        "name": name,
        "severity": severity,
        "status": "active",
        "resource_id": "",
        "resource_name": resource_name,
        "condition": condition,
        "triggered_at": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
        "acknowledged": False,
        "category": category
    }
    alerts.append(new_alert)
    _save_alerts(alerts)
    _add_email(session.get("user_id", 1), "noreply@cloud-dev-consoles.lakeport.local",
               "Deployment notification",
               f'Alert "{name}" has been created for resource "{resource_name}". Severity: {severity}.')
    return jsonify(new_alert)


@blueprint.route("/api/alerts/<alert_id>/delete", methods=["POST"])
def api_delete_alert(alert_id):
    alerts = _load_alerts()
    alert = next((a for a in alerts if a["id"] == alert_id), None)
    if alert is None:
        abort(404)
    alerts.remove(alert)
    _save_alerts(alerts)
    return jsonify({"action": "deleted", "alert_id": alert_id})


# ---------------------------------------------------------------------------
# API routes -- API Endpoints
# ---------------------------------------------------------------------------

@blueprint.route("/api/endpoints")
def api_endpoints_list():
    endpoints = _get_api_endpoints()
    q = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    method = request.args.get("method", "").strip()
    sort = request.args.get("sort", "name")

    results = list(endpoints)
    if q:
        results = _search_resources(results, q, ["name", "path", "description"])
    if status:
        results = [e for e in results if e["status"] == status]
    if method:
        results = [e for e in results if e["method"] == method]

    if sort == "name":
        results.sort(key=lambda e: e["name"].lower())
    elif sort == "requests":
        results.sort(key=lambda e: -e["requests_24h"])
    elif sort == "latency":
        results.sort(key=lambda e: -e["avg_latency_ms"])
    elif sort == "errors":
        results.sort(key=lambda e: -e["error_rate_percent"])

    return jsonify(results)


@blueprint.route("/api/endpoints/<endpoint_id>")
def api_endpoint(endpoint_id):
    endpoints = _get_api_endpoints()
    ep = next((e for e in endpoints if e["id"] == endpoint_id), None)
    if ep is None:
        abort(404)
    return jsonify(ep)


# ---------------------------------------------------------------------------
# API routes -- Stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats")
def api_stats():
    services = _get_services()
    instances = _get_instances()
    functions = _get_functions()
    databases = _get_databases()
    buckets = _get_buckets()
    billing = _get_billing()

    running = sum(1 for i in instances if i["status"] == "running")
    total_storage = sum(b["size_gb"] for b in buckets)
    total_functions = len(functions)
    active_functions = sum(1 for f in functions if f["status"] == "active")
    total_invocations = sum(f["invocations_24h"] for f in functions)

    current_billing = [b for b in billing if b["month"] == "2026-06"]
    total_cost = sum(b["cost"] for b in current_billing)

    return jsonify({
        "total_services": len(services),
        "total_instances": len(instances),
        "running_instances": running,
        "stopped_instances": len(instances) - running,
        "total_databases": len(databases),
        "total_buckets": len(buckets),
        "total_storage_gb": round(total_storage, 1),
        "total_functions": total_functions,
        "active_functions": active_functions,
        "total_invocations_24h": total_invocations,
        "current_month_cost": round(total_cost, 2),
        "service_categories": dict(Counter(s["category"] for s in services)),
    })


# ---------------------------------------------------------------------------
# API routes -- Export
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    fmt = request.args.get("format", "json").lower()
    resource = request.args.get("resource", "services").lower()
    category = request.args.get("category", "").strip()

    if resource == "services":
        data = list(_get_services())
        if category:
            data = [s for s in data if s["category"] == category]
    elif resource == "instances":
        data = list(_get_instances())
    elif resource == "databases":
        data = list(_get_databases())
    elif resource == "functions":
        data = list(_get_functions())
    elif resource == "storage":
        data = list(_get_buckets())
    elif resource == "billing":
        data = list(_get_billing())
        if category:
            data = [b for b in data if b["service_category"] == category]
    else:
        data = list(_get_services())

    if fmt == "csv":
        if not data:
            return Response("", mimetype="text/csv")
        headers = list(data[0].keys())
        lines = [",".join(headers)]
        for item in data:
            row = []
            for h in headers:
                val = item.get(h, "")
                if isinstance(val, (list, dict)):
                    val = json.dumps(val)
                val = str(val).replace('"', '""')
                row.append(f'"{val}"')
            lines.append(",".join(row))
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={resource}.csv"})
    return jsonify(data)


# ---------------------------------------------------------------------------
# API routes -- User management (console auth)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/preferences", methods=["POST"])
def api_update_preferences(user_id):
    data = request.get_json(silent=True) or {}
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    prefs = user.setdefault("preferences", {})
    for key, value in data.items():
        prefs[key] = value
    _save_users(users)
    return jsonify({"action": "updated", "preferences": prefs})


@blueprint.route("/api/users/<int:user_id>/save-query", methods=["POST"])
def api_save_query(user_id):
    data = request.get_json(silent=True) or {}
    query_text = data.get("query", "").strip()
    if not query_text:
        return jsonify({"error": "query required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_queries", [])
    if query_text in saved:
        saved.remove(query_text)
        action = "removed"
    else:
        saved.append(query_text)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "query": query_text, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/recent-service", methods=["POST"])
def api_add_recent_service(user_id):
    data = request.get_json(silent=True) or {}
    service_id = data.get("service_id", "").strip()
    if not service_id:
        return jsonify({"error": "service_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    recent = user.setdefault("recent_services", [])
    if service_id in recent:
        recent.remove(service_id)
    recent.insert(0, service_id)
    recent = recent[:10]
    user["recent_services"] = recent
    _save_users(users)
    return jsonify({"action": "added", "service_id": service_id, "recent": recent})
