"""Expand cloud-dev-consoles data ~10x with task-answer preservation.

Constraints honored:
- New instance/service names all start with letters n-z, so name-sorted
  orderings keep existing rows first (protects "3rd production instance"
  and "meridianflow-api-prod count" style task answers).
- No new metrics rows for the four existing instance ids.
- No new database with storage_gb >= 1000 or monthly_cost >= 356.40
  (protects "largest database cost" = meridianlens-analytics-store $356.40).
- Existing rows untouched.
Deterministic RNG.
"""
import sqlite3, json, random
from datetime import datetime, timedelta

db = sqlite3.connect('data/trimmed_miniweb.db')
rng = random.Random(20260713)

REGIONS = ['us-west-2', 'us-east-1', 'eu-central-1', 'ap-southeast-1', 'global']
CATS = ['Analytics', 'Compute', 'Database', 'DevTools', 'Integration',
        'Monitoring', 'Networking', 'Security', 'Storage']
# names sort AFTER 'm' by construction
STEMS = ['nebulaops', 'nightowl', 'nimbusdata', 'novatrace', 'obsidian', 'octoserve',
         'orionflow', 'ozonesync', 'packetwise', 'pathfinder', 'pixelforge', 'polarisdb',
         'pulsegrid', 'quasarml', 'quillnotify', 'ravenqueue', 'redwoodci', 'rocketapi',
         'sagegate', 'sentine1x', 'signalhub', 'skyvault', 'stellarcache', 'stormrelay',
         'summitedge', 'sundialcron', 'tangramviz', 'telemetra', 'thunderbolt', 'tidalstream',
         'topazauth', 'torrentmq', 'tundrastore', 'umbragate', 'unisonsync', 'upliftcdn',
         'vantagelog', 'vectorpipe', 'velocitydb', 'vergemedia', 'vortexcompute', 'wavecrest',
         'westwindetl', 'whisperbus', 'wildfireml', 'yellowstonefs', 'zenithapi', 'zephyrmail',
         'zincsearch', 'zodiacsched']
SUFFIXES = ['api', 'worker', 'ingest', 'scheduler', 'gateway', 'renderer', 'indexer',
            'exporter', 'webhook', 'batch', 'stream', 'cache']

def ts(days_back_max=180):
    t = datetime(2026, 6, 26) - timedelta(days=rng.uniform(0, days_back_max),
                                          hours=rng.uniform(0, 24))
    return t.strftime('%Y-%m-%dT%H:%M:%SZ')

# ── services 25 → 100 ────────────────────────────────────────────────────────
svc_rows = []
next_snum = 26
used_names = {r[0] for r in db.execute('SELECT name FROM cloud_dev_consoles_services')}
new_services = []
for stem in STEMS:
    for variant in ('', '-' + rng.choice(SUFFIXES)):
        name = stem + variant
        if name in used_names or len(new_services) >= 75: continue
        used_names.add(name); new_services.append(name)
for name in new_services:
    sid = f'svc-{next_snum:03d}'; next_snum += 1
    cat = rng.choice(CATS)
    svc_rows.append((sid, name, cat,
                     f'{cat} service for the {name} workload.',
                     rng.choices(['active', 'warning', 'stopped'], [8, 1, 1])[0],
                     rng.choice(REGIONS), round(rng.uniform(8, 900), 2),
                     ts(700)[:10],
                     json.dumps({'env': rng.choices(['production', 'staging', 'development'], [5, 3, 2])[0],
                                 'team': rng.choice(['data', 'platform', 'ml', 'web', 'infra'])})))
db.executemany('INSERT INTO cloud_dev_consoles_services VALUES (?,?,?,?,?,?,?,?,?)', svc_rows)

# ── instances 15 → ~120 ──────────────────────────────────────────────────────
inst_rows = []
inum = 9000
new_instance_ids = []
for sid, name, cat, *_ in svc_rows:
    for k in range(rng.choice([1, 1, 1, 2, 2, 3])):
        inum += 1
        iid = f'i-9f{inum:012d}'
        env = rng.choices(['production', 'staging', 'development'], [5, 3, 2])[0]
        status = rng.choices(['running', 'stopped'], [4, 1])[0]
        vc = rng.choice([2, 2, 4, 4, 8, 16]); mem = vc * rng.choice([2, 4, 8])
        region = rng.choice(REGIONS[:4])
        inst_rows.append((iid, f'{name}-{env[:4]}-{k+1}',
                          rng.choice(['t3.medium', 'm5.large', 'm5.xlarge', 'c5.2xlarge', 'r5.large']),
                          vc, mem, status, region, region + rng.choice(['a', 'b', 'c']),
                          f'10.{rng.randint(1,9)}.{rng.randint(0,255)}.{rng.randint(1,254)}',
                          '' if env != 'production' else f'54.{rng.randint(1,254)}.{rng.randint(0,255)}.{rng.randint(1,254)}',
                          rng.choice(['Amazon Linux 2023', 'Ubuntu 24.04', 'Debian 12']),
                          sid, ts(500), round(vc * rng.uniform(18, 40), 2),
                          json.dumps({'env': env})))
        if status == 'stopped':
            new_instance_ids.append(iid)
db.executemany('INSERT INTO cloud_dev_consoles_instances VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', inst_rows)

# ── logs 25 → ~2000 ──────────────────────────────────────────────────────────
MSGS = {
    'INFO': ['Deployment completed for {s}', 'Health check passed for {s}', 'Autoscaling event: {s} scaled to {n} replicas',
             'Config reloaded on {s}', 'Certificate renewed for {s}', 'Scheduled snapshot for {s} finished'],
    'WARN': ['Elevated latency on {s}: p99 {n}ms', 'Memory usage above 80% on {s}', 'Retry storm detected on {s}',
             'Throttling requests on {s}', 'Disk usage at {n}% on {s}'],
    'ERROR': ['Connection refused from {s}', 'Unhandled exception in {s} worker', 'Timeout calling upstream from {s}',
              '5xx spike on {s}: {n} errors/min', 'OOM kill on {s}'],
}
all_service_names = [r[0] for r in db.execute('SELECT name FROM cloud_dev_consoles_services')]
log_rows = []
lid = db.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INT)) FROM cloud_dev_consoles_logs").fetchone()[0] or 25
for i in range(1975):
    lid += 1
    level = rng.choices(['INFO', 'WARN', 'ERROR'], [7, 2, 1])[0]
    svc = rng.choice(all_service_names)
    msg = rng.choice(MSGS[level]).format(s=svc, n=rng.randint(2, 97))
    log_rows.append((f'log-{lid:05d}', ts(30), level, svc, msg,
                     rng.choice(['app', 'system', 'network', 'deploy']),
                     rng.choice(CATS), f'trace-{rng.randint(100000, 999999)}'))
db.executemany('INSERT INTO cloud_dev_consoles_logs VALUES (?,?,?,?,?,?,?,?)', log_rows)

# ── metrics: history for new stopped instances only ─────────────────────────
mrow = db.execute('SELECT MAX(row_id) FROM cloud_dev_consoles_metrics').fetchone()[0]
met_rows = []
for iid in new_instance_ids[:50]:
    base = datetime(2026, 6, 26, 8, 0)
    for j in range(12):
        mrow += 1
        met_rows.append((mrow, (base + timedelta(minutes=5 * j)).strftime('%Y-%m-%dT%H:%M:%SZ'),
                         iid, round(rng.uniform(3, 96), 1), round(rng.uniform(10, 92), 1),
                         round(rng.uniform(0.5, 400), 1), round(rng.uniform(0.5, 380), 1),
                         rng.randint(10, 4000), rng.randint(10, 3500), rng.randint(50, 90000)))
db.executemany('INSERT INTO cloud_dev_consoles_metrics VALUES (?,?,?,?,?,?,?,?,?,?)', met_rows)

# ── alerts 10 → 80 ───────────────────────────────────────────────────────────
arow = 10
alert_rows = []
CONDS = ['CPU > {n}% for 5m', 'error rate > {n}%', 'latency p99 > {n}ms', 'disk > {n}%', '5xx count > {n}/min']
for i in range(70):
    arow += 1
    svc = rng.choice(all_service_names)
    sev = rng.choices(['critical', 'high', 'medium', 'low'], [1, 2, 4, 3])[0]
    alert_rows.append((f'alert-{arow:03d}', f'{svc} {rng.choice(["cpu", "latency", "errors", "disk", "memory"])} alert',
                       sev, rng.choices(['firing', 'resolved'], [1, 2])[0], f'svc-{rng.randint(1, 100):03d}', svc,
                       rng.choice(CONDS).format(n=rng.choice([70, 80, 85, 90, 95, 250, 500])),
                       ts(20), rng.random() < 0.5, rng.choice(CATS)))
db.executemany('INSERT INTO cloud_dev_consoles_alerts VALUES (?,?,?,?,?,?,?,?,?,?)', alert_rows)

# ── api endpoints 10 → 60 ────────────────────────────────────────────────────
erow = 10
ep_rows = []
for i in range(50):
    erow += 1
    svc = rng.choice(all_service_names)
    res = rng.choice(['items', 'users', 'jobs', 'events', 'reports', 'files', 'sessions', 'orders'])
    method = rng.choices(['GET', 'POST', 'PUT', 'DELETE'], [5, 3, 1, 1])[0]
    ep_rows.append((f'ep-{erow:03d}', f'{svc} {res} endpoint', f'/v1/{svc}/{res}', method,
                    'gw-main', rng.choices(['active', 'deprecated'], [9, 1])[0],
                    rng.choice([100, 500, 1000, 5000]), rng.randint(12, 900),
                    rng.randint(100, 2_000_000), round(rng.uniform(0, 4.5), 2),
                    rng.choice(['api_key', 'oauth2', 'none']),
                    f'{method} endpoint for {res} on {svc}.'))
db.executemany('INSERT INTO cloud_dev_consoles_api_endpoints VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', ep_rows)

# ── storage buckets 7 → 40 ───────────────────────────────────────────────────
brow = 7
b_rows = []
for i in range(33):
    brow += 1
    stem = rng.choice(STEMS)
    b_rows.append((f'bucket-{brow:03d}', f'{stem}-{rng.choice(["assets", "backups", "logs", "exports", "raw", "models"])}',
                   rng.choice(REGIONS[:4]), rng.choice(['STANDARD', 'STANDARD_IA', 'GLACIER']),
                   round(rng.uniform(1, 5000), 1), rng.randint(10, 2_000_000),
                   rng.random() < 0.4, rng.random() < 0.9, rng.random() < 0.1,
                   rng.randint(0, 3), round(rng.uniform(0.5, 120), 2), ts(700)[:10], ts(10)[:10],
                   json.dumps({'env': rng.choice(['production', 'staging'])})))
db.executemany('INSERT INTO cloud_dev_consoles_storage_buckets VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', b_rows)

# ── databases 7 → 35 (storage < 1000, cost < 356.40 preserved) ──────────────
drow = 7
d_rows = []
for i in range(28):
    drow += 1
    stem = rng.choice(STEMS)
    engine = rng.choice(['postgres', 'mysql', 'mongodb', 'redis'])
    storage = rng.choice([20, 50, 100, 200, 400, 800])
    d_rows.append((f'db-{drow:03d}', f'{stem}-{engine}-{rng.choice(["primary", "replica", "store"])}',
                   engine, rng.choice(['16.2', '15.4', '8.0', '7.2']),
                   rng.choice(['db.t3.medium', 'db.m5.large', 'db.r5.large']),
                   storage, round(storage * rng.uniform(0.1, 0.9), 1),
                   rng.choices(['available', 'stopped'], [9, 1])[0], rng.choice(REGIONS[:4]),
                   rng.random() < 0.4, rng.random() < 0.9, rng.choice([1, 7, 14, 30]),
                   rng.randint(0, 180), rng.choice([100, 200, 500]), rng.choice([1000, 3000, 6000]),
                   round(rng.uniform(15, 340), 2), ts(700)[:10],
                   json.dumps({'env': rng.choice(['production', 'staging'])})))
db.executemany('INSERT INTO cloud_dev_consoles_databases VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', d_rows)

# ── functions 8 → 50 ─────────────────────────────────────────────────────────
frow = 8
f_rows = []
for i in range(42):
    frow += 1
    stem = rng.choice(STEMS)
    act = rng.choice(['resize', 'notify', 'ingest', 'cleanup', 'transform', 'audit', 'rollup'])
    f_rows.append((f'fn-{frow:03d}', f'{stem}-{act}',
                   rng.choice(['python3.12', 'nodejs20.x', 'go1.x']),
                   rng.choice([128, 256, 512, 1024]), rng.choice([15, 30, 60, 300]),
                   rng.choices(['active', 'inactive'], [9, 1])[0], rng.choice(REGIONS[:4]),
                   f'{act}.handler', ts(7), rng.randint(0, 500000),
                   round(rng.uniform(8, 4000), 1), round(rng.uniform(0, 3), 2),
                   round(rng.uniform(0.2, 60), 2), json.dumps({'env': rng.choice(['production', 'staging'])})))
db.executemany('INSERT INTO cloud_dev_consoles_functions VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)', f_rows)

# ── iam users 5 → 25 ─────────────────────────────────────────────────────────
NAMES = [('nina.paulsen', 'Nina Paulsen'), ('omar.haddad', 'Omar Haddad'), ('petra.novak', 'Petra Novak'),
         ('quinn.harper', 'Quinn Harper'), ('rosa.delgado', 'Rosa Delgado'), ('sam.okafor', 'Sam Okafor'),
         ('tara.lindqvist', 'Tara Lindqvist'), ('umar.farouk', 'Umar Farouk'), ('vera.kimura', 'Vera Kimura'),
         ('wes.thornton', 'Wes Thornton'), ('xena.morales', 'Xena Morales'), ('yusuf.demir', 'Yusuf Demir'),
         ('zoe.castellanos', 'Zoe Castellanos'), ('noah.eriksen', 'Noah Eriksen'), ('priya.raman', 'Priya Raman'),
         ('ravi.subram', 'Ravi Subram'), ('sofia.marino', 'Sofia Marino'), ('tomas.vidal', 'Tomas Vidal'),
         ('ursula.beck', 'Ursula Beck'), ('victor.osei', 'Victor Osei')]
urow = 1
u_rows = []
for uname, disp in NAMES:
    urow += 1
    u_rows.append((f'iam-{urow + 4:03d}', uname, disp, uname + '@meridiansystems.com',
                   rng.choice(['developer', 'admin', 'read-only', 'ops', 'security-auditor']),
                   rng.choice(['data', 'platform', 'ml', 'web', 'infra']),
                   rng.choices(['active', 'suspended'], [9, 1])[0], rng.random() < 0.8,
                   ts(20), ts(700)[:10], rng.randint(0, 4),
                   json.dumps(rng.sample(['AdminAccess', 'ReadOnly', 'DeployPolicy', 'BillingView', 'LogsRead'], k=2)),
                   json.dumps(rng.sample(['engineering', 'oncall', 'platform', 'contractors'], k=1))))
db.executemany('INSERT INTO cloud_dev_consoles_iam_users VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', u_rows)

# ── billing: add 6 more months × categories ──────────────────────────────────
bill_max = db.execute('SELECT MAX(row_id) FROM cloud_dev_consoles_billing').fetchone()[0]
months = ['2025-07', '2025-08', '2025-09', '2025-10', '2025-11', '2025-12']
bill_rows = []
for m in months:
    for cat in CATS:
        bill_max += 1
        bill_rows.append((bill_max, m, cat, round(rng.uniform(200, 9000), 2),
                          round(rng.uniform(3000, 12000), 2)))
db.executemany('INSERT INTO cloud_dev_consoles_billing VALUES (?,?,?,?,?)', bill_rows)

db.commit()
for t in ['services', 'instances', 'logs', 'metrics', 'alerts', 'api_endpoints',
          'storage_buckets', 'databases', 'functions', 'iam_users', 'billing']:
    print(t, db.execute(f'SELECT COUNT(*) FROM cloud_dev_consoles_{t}').fetchone()[0])
# invariants
print('largest db still analytics-store:', db.execute(
    "SELECT name, monthly_cost FROM cloud_dev_consoles_databases ORDER BY storage_gb DESC LIMIT 1").fetchone())
print('3rd prod instance by name:', [r[0] for r in db.execute(
    "SELECT name FROM cloud_dev_consoles_instances WHERE tags LIKE '%production%' ORDER BY name LIMIT 3")])
print('meridianflow-api-prod count:', db.execute(
    "SELECT COUNT(*) FROM cloud_dev_consoles_instances WHERE name LIKE 'meridianflow-api-prod%'").fetchone()[0])
