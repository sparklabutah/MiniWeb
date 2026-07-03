"""Annotation database — separate SQLite for multi-annotator work.

Stores annotation tasks, trajectories, HTML snapshots, reviews, and reports
in a shared SQLite DB so multiple annotators can see each other's work.

Core API
--------
    save_task(task_dict)           -> task_id
    load_all_tasks()              -> list[dict]
    load_task(task_id)            -> dict | None
    delete_all_tasks()            -> int
    get_macro_coverage()          -> {macro: site_count}
    get_cell_counts()             -> {(n_sites, n_macros): count}
    count_tasks_by_site()         -> {site_id: count}
    save_review(site_id, ...)     -> int (review id)
    load_reviews(site_id)         -> list[dict]
    count_reviews_by_site()       -> {site_id: count}
    save_report(data)             -> int (report id)
    load_task_html(task_id, step) -> str
"""

import json
import os
import pathlib
import sqlite3
import threading

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DB_PATH = os.environ.get(
    "ANNOTATION_DB",
    str(pathlib.Path(__file__).resolve().parent / "annotation.db"),
)

# ---------------------------------------------------------------------------
# Connection — one per thread, WAL mode
# ---------------------------------------------------------------------------

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA busy_timeout=30000")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        # Auto-create tables if DB was deleted/fresh
        conn.executescript(_SCHEMA)
        conn.commit()
        _local.conn = conn
    return conn


def close():
    conn = getattr(_local, "conn", None)
    if conn is not None:
        try:
            conn.close()
        except Exception:
            pass
        _local.conn = None


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------

_SCHEMA = """
CREATE TABLE IF NOT EXISTS annotation_tasks (
    task_id TEXT PRIMARY KEY,
    site TEXT NOT NULL,
    sites TEXT NOT NULL DEFAULT '[]',
    instruction TEXT NOT NULL,
    macros TEXT NOT NULL DEFAULT '[]',
    num_sites INTEGER NOT NULL DEFAULT 1,
    num_macros INTEGER NOT NULL DEFAULT 1,
    expected_answer TEXT NOT NULL DEFAULT '',
    expected_answer_type TEXT NOT NULL DEFAULT 'string',
    alternatives TEXT NOT NULL DEFAULT '[]',
    eval TEXT NOT NULL DEFAULT '[]',
    eval_logic TEXT NOT NULL DEFAULT 'all',
    difficulty TEXT NOT NULL DEFAULT '',
    annotator TEXT NOT NULL DEFAULT 'anonymous',
    trajectory_steps INTEGER NOT NULL DEFAULT 0,
    chain_id TEXT NOT NULL DEFAULT '',
    requires_login INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_tasks_site ON annotation_tasks(site);
CREATE INDEX IF NOT EXISTS idx_tasks_annotator ON annotation_tasks(annotator);

CREATE TABLE IF NOT EXISTS annotation_task_macros (
    task_id TEXT NOT NULL,
    macro TEXT NOT NULL,
    PRIMARY KEY (task_id, macro),
    FOREIGN KEY (task_id) REFERENCES annotation_tasks(task_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_task_macros_macro ON annotation_task_macros(macro);

CREATE TABLE IF NOT EXISTS annotation_trajectories (
    task_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    type TEXT NOT NULL,
    url TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL DEFAULT '',
    ax_tree TEXT NOT NULL DEFAULT '',
    has_html INTEGER NOT NULL DEFAULT 0,
    has_screenshot INTEGER NOT NULL DEFAULT 0,
    timestamp TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (task_id, step, type),
    FOREIGN KEY (task_id) REFERENCES annotation_tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS annotation_html_snapshots (
    task_id TEXT NOT NULL,
    step INTEGER NOT NULL,
    html TEXT NOT NULL DEFAULT '',
    PRIMARY KEY (task_id, step),
    FOREIGN KEY (task_id) REFERENCES annotation_tasks(task_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS annotation_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    site_id TEXT NOT NULL,
    annotator TEXT NOT NULL DEFAULT 'anonymous',
    feedback TEXT NOT NULL,
    timestamp TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_reviews_site ON annotation_reviews(site_id);

CREATE TABLE IF NOT EXISTS annotation_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sites TEXT NOT NULL DEFAULT '[]',
    macros TEXT NOT NULL DEFAULT '[]',
    reason TEXT NOT NULL DEFAULT '',
    details TEXT NOT NULL DEFAULT '',
    annotator TEXT NOT NULL DEFAULT 'anonymous',
    timestamp TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS annotation_graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source TEXT NOT NULL,
    target TEXT NOT NULL,
    event_type TEXT NOT NULL,
    builtin INTEGER NOT NULL DEFAULT 0,
    UNIQUE(source, target, event_type)
);

CREATE TABLE IF NOT EXISTS annotation_graph_positions (
    site_id TEXT PRIMARY KEY,
    x REAL NOT NULL DEFAULT 0,
    y REAL NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS annotation_macros_na (
    site_id TEXT NOT NULL,
    macro TEXT NOT NULL,
    count INTEGER NOT NULL DEFAULT 1,
    PRIMARY KEY (site_id, macro)
);
"""


def init_db(db_path=None):
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path
    conn = _get_conn()
    conn.executescript(_SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------

def save_task(task: dict) -> str:
    conn = _get_conn()
    task_id = task.get("task_id", "")
    macros = task.get("macros", [])
    sites = task.get("sites", [task.get("site", "")])

    conn.execute(
        """INSERT OR REPLACE INTO annotation_tasks
           (task_id, site, sites, instruction, macros, num_sites, num_macros,
            expected_answer, expected_answer_type, alternatives,
            eval, eval_logic, difficulty, annotator, trajectory_steps,
            chain_id, requires_login, created_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            task_id,
            task.get("site", sites[0] if sites else ""),
            json.dumps(sites),
            task.get("instruction", ""),
            json.dumps(macros),
            task.get("num_sites", len(sites)),
            task.get("num_macros", len(macros)),
            task.get("expected_answer", "") or "",
            task.get("expected_answer_type", "string") or "string",
            json.dumps(task.get("alternatives", [])),
            json.dumps(task.get("eval", [])),
            task.get("eval_logic", "all") or "all",
            task.get("difficulty", "") or "",
            task.get("annotator", "anonymous") or "anonymous",
            task.get("trajectory_steps", 0),
            task.get("chain_id", "") or "",
            1 if task.get("requires_login") else 0,
            task.get("created_at", ""),
        ),
    )

    # Junction table for macros
    conn.execute("DELETE FROM annotation_task_macros WHERE task_id=?", (task_id,))
    for m in macros:
        conn.execute(
            "INSERT OR IGNORE INTO annotation_task_macros (task_id, macro) VALUES (?,?)",
            (task_id, m),
        )

    conn.commit()
    return task_id


def save_trajectory(task_id: str, trajectory: list):
    conn = _get_conn()
    conn.execute("DELETE FROM annotation_trajectories WHERE task_id=?", (task_id,))
    conn.execute("DELETE FROM annotation_html_snapshots WHERE task_id=?", (task_id,))

    step_num = 0
    for entry in trajectory:
        entry_type = entry.get("type", "")

        if entry_type == "action":
            step_num += 1
            # Store the full action data (action type, target, selector, etc.) in ax_tree as JSON
            action_data = json.dumps({
                k: v for k, v in entry.items()
                if k not in ("type", "timestamp", "raw_html") and v
            })
            conn.execute(
                """INSERT OR REPLACE INTO annotation_trajectories
                   (task_id, step, type, url, title, ax_tree, has_html, has_screenshot, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (task_id, step_num, "action",
                 entry.get("url", entry.get("target", "")),
                 entry.get("action", ""),  # store action verb in title field
                 action_data,  # full action details in ax_tree field
                 0, 0,
                 entry.get("timestamp", "")),
            )

        elif entry_type == "observation":
            raw_html = entry.get("raw_html", "")
            has_html = bool(raw_html)
            if has_html:
                conn.execute(
                    "INSERT OR REPLACE INTO annotation_html_snapshots (task_id, step, html) VALUES (?,?,?)",
                    (task_id, step_num, raw_html),
                )
            conn.execute(
                """INSERT OR REPLACE INTO annotation_trajectories
                   (task_id, step, type, url, title, ax_tree, has_html, has_screenshot, timestamp)
                   VALUES (?,?,?,?,?,?,?,?,?)""",
                (task_id, step_num, "observation",
                 entry.get("url", ""),
                 entry.get("title", ""),
                 entry.get("ax_tree", ""),
                 1 if has_html else 0,
                 0,
                 entry.get("timestamp", "")),
            )

    conn.commit()
    return step_num


def load_all_tasks() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM annotation_tasks ORDER BY created_at DESC"
    ).fetchall()
    return [_task_from_row(r) for r in rows]


def load_task(task_id: str) -> dict | None:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM annotation_tasks WHERE task_id=?", (task_id,)
    ).fetchone()
    if not row:
        return None
    task = _task_from_row(row)
    # Attach trajectory
    traj_rows = conn.execute(
        "SELECT * FROM annotation_trajectories WHERE task_id=? ORDER BY step, type",
        (task_id,),
    ).fetchall()
    task["trajectory"] = [dict(r) for r in traj_rows]
    return task


def load_task_html(task_id: str, step: int) -> str:
    conn = _get_conn()
    row = conn.execute(
        "SELECT html FROM annotation_html_snapshots WHERE task_id=? AND step=?",
        (task_id, step),
    ).fetchone()
    return row["html"] if row else ""


def delete_all_tasks() -> int:
    conn = _get_conn()
    count = conn.execute("SELECT COUNT(*) FROM annotation_tasks").fetchone()[0]
    conn.execute("DELETE FROM annotation_tasks")
    # CASCADE handles task_macros, trajectories, html_snapshots
    conn.commit()
    return count


def _task_from_row(row) -> dict:
    d = dict(row)
    # Deserialize JSON fields
    for field in ("sites", "macros", "alternatives", "eval"):
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                d[field] = []
    # Convert requires_login int to bool
    d["requires_login"] = bool(d.get("requires_login", 0))
    return d


# ---------------------------------------------------------------------------
# Macro coverage & cell counts
# ---------------------------------------------------------------------------

def get_macro_coverage() -> dict:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT tm.macro, COUNT(DISTINCT t.site) as site_count
           FROM annotation_task_macros tm
           JOIN annotation_tasks t ON tm.task_id = t.task_id
           GROUP BY tm.macro"""
    ).fetchall()
    return {r["macro"]: r["site_count"] for r in rows}


def get_cell_counts() -> dict:
    conn = _get_conn()
    rows = conn.execute(
        """SELECT num_sites, num_macros, COUNT(*) as cnt
           FROM annotation_tasks
           GROUP BY num_sites, num_macros"""
    ).fetchall()
    return {(r["num_sites"], r["num_macros"]): r["cnt"] for r in rows}


def count_tasks_by_site() -> dict:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT site, COUNT(*) as cnt FROM annotation_tasks GROUP BY site"
    ).fetchall()
    return {r["site"]: r["cnt"] for r in rows}


# ---------------------------------------------------------------------------
# Reviews
# ---------------------------------------------------------------------------

def save_review(site_id: str, annotator: str, feedback: str, timestamp: str) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT INTO annotation_reviews (site_id, annotator, feedback, timestamp) VALUES (?,?,?,?)",
        (site_id, annotator, feedback, timestamp),
    )
    conn.commit()
    return cur.lastrowid


def load_reviews(site_id: str) -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM annotation_reviews WHERE site_id=? ORDER BY timestamp DESC",
        (site_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def count_reviews_by_site() -> dict:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT site_id, COUNT(*) as cnt FROM annotation_reviews GROUP BY site_id"
    ).fetchall()
    return {r["site_id"]: r["cnt"] for r in rows}


# ---------------------------------------------------------------------------
# Reports (skip reports)
# ---------------------------------------------------------------------------

def save_report(data: dict) -> int:
    conn = _get_conn()
    cur = conn.execute(
        """INSERT INTO annotation_reports
           (sites, macros, reason, details, annotator, timestamp)
           VALUES (?,?,?,?,?,?)""",
        (
            json.dumps(data.get("sites", [])),
            json.dumps(data.get("macros", [])),
            data.get("reason", ""),
            data.get("details", ""),
            data.get("annotator", "anonymous"),
            data.get("timestamp", ""),
        ),
    )
    conn.commit()
    return cur.lastrowid


# ---------------------------------------------------------------------------
# Graph (site affinity edges + node positions)
# ---------------------------------------------------------------------------

def load_graph_edges() -> list:
    conn = _get_conn()
    rows = conn.execute(
        "SELECT id, source, target, event_type, builtin FROM annotation_graph_edges ORDER BY source, target"
    ).fetchall()
    return [dict(r) for r in rows]


def save_graph_edge(source: str, target: str, event_type: str, builtin: bool = False) -> int:
    conn = _get_conn()
    cur = conn.execute(
        "INSERT OR IGNORE INTO annotation_graph_edges (source, target, event_type, builtin) VALUES (?,?,?,?)",
        (source, target, event_type, 1 if builtin else 0),
    )
    conn.commit()
    return cur.lastrowid or 0


def delete_graph_edge(edge_id: int):
    conn = _get_conn()
    conn.execute("DELETE FROM annotation_graph_edges WHERE id=?", (edge_id,))
    conn.commit()


def load_graph_positions() -> dict:
    conn = _get_conn()
    rows = conn.execute("SELECT site_id, x, y FROM annotation_graph_positions").fetchall()
    return {r["site_id"]: {"x": r["x"], "y": r["y"]} for r in rows}


def save_graph_positions(positions: dict):
    conn = _get_conn()
    for site_id, pos in positions.items():
        conn.execute(
            "INSERT OR REPLACE INTO annotation_graph_positions (site_id, x, y) VALUES (?,?,?)",
            (site_id, pos["x"], pos["y"]),
        )
    conn.commit()


# ---------------------------------------------------------------------------
# Macros N/A (not applicable to site)
# ---------------------------------------------------------------------------

def record_macros_na(na_dict: dict):
    """Record macros marked as N/A. na_dict: {macro: site_id}."""
    conn = _get_conn()
    for macro, site_id in na_dict.items():
        conn.execute(
            """INSERT INTO annotation_macros_na (site_id, macro, count) VALUES (?, ?, 1)
               ON CONFLICT(site_id, macro) DO UPDATE SET count = count + 1""",
            (site_id, macro),
        )
    conn.commit()


def get_na_macros_for_sites(site_ids: list, threshold: int = 2) -> set:
    """Return macros marked N/A at least `threshold` times for any of the given sites."""
    conn = _get_conn()
    placeholders = ",".join("?" for _ in site_ids)
    rows = conn.execute(
        f"SELECT macro FROM annotation_macros_na WHERE site_id IN ({placeholders}) AND count >= ?",
        (*site_ids, threshold),
    ).fetchall()
    return {r["macro"] for r in rows}
