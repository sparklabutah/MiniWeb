"""Make the cloud-dev-consoles 'currently erroring service' log data realistic.

The pinned burst behind task cloud-dev-consoles_c1d5dc was six unrelated
failure templates in 14 minutes, sitting in an artificially silent stream,
on top of a 10% background error rate across 103 services. This rewrites it:

1. The burst becomes ONE coherent incident: a meridianflow-api memory leak —
   warning lead-in, OOM kill, failing health checks, restart loop, and an
   escalating 5xx spike, with consistent trace ids and instance sources.
2. Routine INFO/WARN rows from other services are interleaved through the
   incident window so the stream looks live.
3. Non-meridianflow ERRORs in the 48h before the incident are demoted to
   WARNs with warning-flavored wording (the lone pixelforge-exporter OOM at
   23:40 stays as a plausible red herring). Deep history is untouched.

Invariant (task 7166bc): the newest connection/timeout log row must belong to
meridianflow-api / i-0a1b2c3d4e5f00001 — asserted at the end.
Instances and metrics tables are not touched (five other tasks depend on them).

Old rows are backed up to data/backups/clouddev-incident-2026-07-22/.
"""
import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "trimmed_miniweb.db"
BACKUP = ROOT / "data" / "backups" / "clouddev-incident-2026-07-22"

# ids of the old synthetic burst (inserted 2026-07-20, task-fix data pin)
OLD_BURST_IDS = [f"log-3000{i}" for i in range(1, 7)]

INCIDENT = [
    # (ts, level, message, source)
    ("2026-06-25T23:49:12Z", "WARN",
     "Memory usage above 80% on meridianflow-api (rss 3.2G/4G)", "i-0a1b2c3d4e5f00001"),
    ("2026-06-25T23:57:40Z", "WARN",
     "Memory usage above 92% on meridianflow-api (rss 3.7G/4G)", "i-0a1b2c3d4e5f00001"),
    ("2026-06-26T00:04:12Z", "ERROR",
     "OOM kill on meridianflow-api: worker pid 4142 (rss 4.0G)", "i-0a1b2c3d4e5f00001"),
    ("2026-06-26T00:05:03Z", "ERROR",
     "Health check failed for meridianflow-api: connect timeout after 5s", "svc-001"),
    ("2026-06-26T00:07:45Z", "ERROR",
     "meridianflow-api restarting (3rd restart in 5 minutes)", "i-0a1b2c3d4e5f00001"),
    ("2026-06-26T00:10:03Z", "ERROR",
     "Health check failed for meridianflow-api: connect timeout after 5s", "svc-001"),
    ("2026-06-26T00:12:58Z", "ERROR",
     "5xx spike on meridianflow-api: 62 errors/min", "svc-001"),
    ("2026-06-26T00:15:21Z", "ERROR",
     "5xx spike on meridianflow-api: 118 errors/min", "svc-001"),
    ("2026-06-26T00:18:40Z", "ERROR",
     "Upstream connection timeout from meridianflow-api (10s), request queue growing", "i-0a1b2c3d4e5f00002"),
]

# routine chatter interleaved through the incident window (other services)
NOISE = [
    ("2026-06-25T23:44:31Z", "INFO", "torrentmq-api", "Scheduled snapshot for torrentmq-api finished"),
    ("2026-06-25T23:51:07Z", "INFO", "redwoodci-stream", "Deployment completed for redwoodci-stream"),
    ("2026-06-25T23:55:44Z", "INFO", "Document Store", "Config reloaded on Document Store"),
    ("2026-06-26T00:01:19Z", "INFO", "polarisdb", "Autovacuum finished on polarisdb (12 tables)"),
    ("2026-06-26T00:06:28Z", "WARN", "nimbusdata", "Retry rate elevated on nimbusdata (2.1%)"),
    ("2026-06-26T00:09:15Z", "INFO", "skyvault-webhook", "Certificate rotation completed for skyvault-webhook"),
    ("2026-06-26T00:13:36Z", "INFO", "telemetra-webhook", "Deployment completed for telemetra-webhook"),
    ("2026-06-26T00:16:52Z", "INFO", "torrentmq", "Queue depth back to normal on torrentmq"),
]

# warning-flavored rewordings for demoted recent errors
DEMOTE_MAP = [
    ("OOM kill on ", "Memory usage above 90% on "),
    ("5xx spike on ", "Elevated error rate on "),
    ("Unhandled exception in ", "Recovered exception in "),
    ("Connection refused from ", "Slow responses from "),
    ("Timeout calling upstream from ", "Latency above SLO calling upstream from "),
]
DEMOTE_WINDOW = ("2026-06-24T00:00:00Z", "2026-06-26T23:59:59Z")
KEEP_ERROR = {"meridianflow-api"}
KEEP_ROW_IDS = set()  # filled below with the pixelforge red herring


def main():
    db = sqlite3.connect(DB, timeout=60)
    db.row_factory = sqlite3.Row
    BACKUP.mkdir(parents=True, exist_ok=True)

    # red herring to preserve: the lone pixelforge OOM at 23:40
    rh = db.execute("""SELECT id FROM cloud_dev_consoles_logs
        WHERE service='pixelforge-exporter' AND level='ERROR'
        AND timestamp='2026-06-25T23:40:00Z'""").fetchone()
    if rh:
        KEEP_ROW_IDS.add(rh["id"])

    # ---- backup everything we delete or modify --------------------------
    burst_rows = [dict(r) for r in db.execute(
        f"SELECT * FROM cloud_dev_consoles_logs WHERE id IN ({','.join('?' * len(OLD_BURST_IDS))})",
        OLD_BURST_IDS)]
    demote_rows = [dict(r) for r in db.execute(
        """SELECT * FROM cloud_dev_consoles_logs
           WHERE level='ERROR' AND timestamp BETWEEN ? AND ?
           AND service NOT IN ('meridianflow-api')""", DEMOTE_WINDOW)]
    demote_rows = [r for r in demote_rows if r["id"] not in KEEP_ROW_IDS]
    (BACKUP / "replaced_rows.json").write_text(json.dumps(
        {"deleted_burst": burst_rows, "demoted": demote_rows}, indent=1))

    # ---- 1. replace the burst -------------------------------------------
    db.execute(f"DELETE FROM cloud_dev_consoles_logs WHERE id IN ({','.join('?' * len(OLD_BURST_IDS))})",
               OLD_BURST_IDS)
    seq = 30100
    trace = "trace-mf-incident-0626"
    for ts, level, msg, source in INCIDENT:
        db.execute("""INSERT INTO cloud_dev_consoles_logs
            (id, timestamp, level, service, message, source, category, trace_id)
            VALUES (?, ?, ?, 'meridianflow-api', ?, ?, 'application', ?)""",
                   (f"log-{seq}", ts, level, msg, source, trace))
        seq += 1
    for ts, level, service, msg in NOISE:
        db.execute("""INSERT INTO cloud_dev_consoles_logs
            (id, timestamp, level, service, message, source, category, trace_id)
            VALUES (?, ?, ?, ?, ?, 'svc-001', 'platform', ?)""",
                   (f"log-{seq}", ts, level, service, msg, f"trace-{seq}"))
        seq += 1

    # ---- 2. demote recent background errors -----------------------------
    demoted = 0
    for r in demote_rows:
        msg = r["message"]
        for old, new in DEMOTE_MAP:
            if msg.startswith(old):
                msg = new + msg[len(old):]
                break
        db.execute("UPDATE cloud_dev_consoles_logs SET level='WARN', message=? WHERE id=?",
                   (msg, r["id"]))
        demoted += 1
    db.commit()

    # ---- 3. invariants ---------------------------------------------------
    # newest timeout-ish row must be meridianflow's (task 7166bc)
    r = db.execute("""SELECT service, source FROM cloud_dev_consoles_logs
        WHERE message LIKE '%timeout%' OR message LIKE '%Timeout%'
        ORDER BY timestamp DESC LIMIT 1""").fetchone()
    assert r["service"] == "meridianflow-api", f"7166bc invariant broken: {dict(r)}"
    # newest ERROR rows are the incident; next foreign ERROR is the red herring
    top = db.execute("""SELECT service FROM cloud_dev_consoles_logs
        WHERE level='ERROR' ORDER BY timestamp DESC LIMIT 8""").fetchall()
    services = [t["service"] for t in top]
    assert set(services[:7]) == {"meridianflow-api"}, services
    assert services[7] == "pixelforge-exporter", services

    # fts sync
    if db.execute("SELECT name FROM sqlite_master WHERE name='fts_cloud_dev_consoles_logs'").fetchone():
        db.execute("INSERT INTO fts_cloud_dev_consoles_logs(fts_cloud_dev_consoles_logs) VALUES('rebuild')")
        db.commit()

    n_err = db.execute("SELECT COUNT(*) FROM cloud_dev_consoles_logs WHERE level='ERROR'").fetchone()[0]
    print(f"burst replaced ({len(INCIDENT)} incident rows + {len(NOISE)} noise rows), "
          f"{demoted} recent errors demoted to WARN, ERROR total now {n_err}; "
          f"backup at {BACKUP}/replaced_rows.json")


if __name__ == "__main__":
    main()
