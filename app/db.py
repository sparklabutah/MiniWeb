"""SQLite data access layer for MiniWeb — per-site tables.

Each site has its own tables (e.g., banking_users, banking_transactions)
with real columns and indexes.  Session mutations are stored in a generic
session_overlay table and merged at query time.

Core API
--------
    query(site, collection, **filters) -> list[dict]
    get_item(site, collection, item_id) -> dict | None
    count(site, collection, **filters) -> int
    save_item(site, collection, item_id, data) -> None
    delete_item(site, collection, item_id) -> None

Session management
------------------
    reset_session(sid)   — revert session to pristine state
    reset_all()          — clear all sessions
    get_stats()          — overlay statistics

Schema & build
--------------
    init_db()            — create infrastructure tables
    create_site_table()  — create a per-site table from schema
    get_table_name()     — look up (site, collection) -> SQL table name
"""

import json
import os
import pathlib
import sqlite3
import threading
import time

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_DB_PATH = os.environ.get(
    "MINIWEB_DB",
    str(pathlib.Path(__file__).resolve().parent.parent / "miniweb.db"),
)
_SESSION_TTL = 3600  # 1 hour

# ---------------------------------------------------------------------------
# Connection pool — one connection per thread (SQLite requirement)
# ---------------------------------------------------------------------------

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection."""
    conn = getattr(_local, "conn", None)
    if conn is None:
        conn = sqlite3.connect(_DB_PATH, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=-64000")  # 64 MB cache
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.row_factory = sqlite3.Row
        _local.conn = conn
    return conn


def get_conn() -> sqlite3.Connection:
    """Public access to the thread-local connection."""
    return _get_conn()


def close():
    """Close the thread-local connection (call at teardown)."""
    conn = getattr(_local, "conn", None)
    if conn is not None:
        conn.close()
        _local.conn = None


# ---------------------------------------------------------------------------
# Infrastructure schema
# ---------------------------------------------------------------------------

_INFRA_SCHEMA = """
CREATE TABLE IF NOT EXISTS site_registry (
    site TEXT NOT NULL,
    collection TEXT NOT NULL,
    table_name TEXT NOT NULL,
    pk_column TEXT NOT NULL DEFAULT 'id',
    PRIMARY KEY (site, collection)
);

CREATE TABLE IF NOT EXISTS session_overlay (
    session_id TEXT NOT NULL,
    site TEXT NOT NULL,
    collection TEXT NOT NULL,
    item_id TEXT NOT NULL,
    op TEXT NOT NULL DEFAULT 'upsert',
    data TEXT,
    PRIMARY KEY (session_id, site, collection, item_id)
);

CREATE TABLE IF NOT EXISTS session_collection_replaced (
    session_id TEXT NOT NULL,
    site TEXT NOT NULL,
    collection TEXT NOT NULL,
    PRIMARY KEY (session_id, site, collection)
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    last_access TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_overlay_session
    ON session_overlay (session_id);

CREATE INDEX IF NOT EXISTS idx_overlay_site_coll
    ON session_overlay (site, collection, session_id);

CREATE TABLE IF NOT EXISTS event_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    session_id TEXT NOT NULL,
    event_type TEXT NOT NULL,
    source_site TEXT NOT NULL DEFAULT '',
    payload TEXT NOT NULL DEFAULT '{}',
    handlers_called INTEGER NOT NULL DEFAULT 0,
    errors TEXT NOT NULL DEFAULT ''
);

CREATE INDEX IF NOT EXISTS idx_event_log_type ON event_log (event_type);
CREATE INDEX IF NOT EXISTS idx_event_log_session ON event_log (session_id);

"""


def init_db(db_path: str = None):
    """Create infrastructure tables. Called once at app startup."""
    global _DB_PATH
    if db_path:
        _DB_PATH = db_path
    conn = _get_conn()
    conn.executescript(_INFRA_SCHEMA)
    conn.commit()


# ---------------------------------------------------------------------------
# Site registry — maps (site, collection) to SQL table names
# ---------------------------------------------------------------------------

# In-memory cache for fast lookups
_registry_cache = {}  # (site, collection) -> (table_name, pk_column)


def _load_registry():
    """Load the site registry into memory."""
    global _registry_cache
    conn = _get_conn()
    try:
        rows = conn.execute("SELECT site, collection, table_name, pk_column FROM site_registry").fetchall()
        _registry_cache = {
            (row[0], row[1]): (row[2], row[3]) for row in rows
        }
    except sqlite3.OperationalError:
        _registry_cache = {}


def get_table_name(site: str, collection: str) -> str | None:
    """Look up the SQL table name for a (site, collection) pair."""
    if not _registry_cache:
        _load_registry()
    entry = _registry_cache.get((site, collection))
    return entry[0] if entry else None


def get_pk_column(site: str, collection: str) -> str:
    """Get the primary key column name for a (site, collection) pair."""
    if not _registry_cache:
        _load_registry()
    entry = _registry_cache.get((site, collection))
    return entry[1] if entry else "id"


def list_collections(site: str) -> list[str]:
    """List all collections for a site."""
    if not _registry_cache:
        _load_registry()
    return [coll for (s, coll) in _registry_cache if s == site]


def register_table(site: str, collection: str, table_name: str, pk_column: str = "id",
                   conn: sqlite3.Connection = None):
    """Register a site table in the registry."""
    if conn is None:
        conn = _get_conn()
    conn.execute(
        "INSERT OR REPLACE INTO site_registry (site, collection, table_name, pk_column) "
        "VALUES (?, ?, ?, ?)",
        (site, collection, table_name, pk_column),
    )
    _registry_cache[(site, collection)] = (table_name, pk_column)


# ---------------------------------------------------------------------------
# Session helpers
# ---------------------------------------------------------------------------

def _get_session_id() -> str:
    """Get the current Flask session ID, or '_no_session' outside request."""
    try:
        from flask import session, has_request_context
        if has_request_context():
            sid = session.get("_data_overlay_sid")
            if not sid:
                import uuid
                sid = str(uuid.uuid4())[:12]
                session["_data_overlay_sid"] = sid
            return sid
    except (ImportError, RuntimeError):
        pass
    return "_no_session"


def _touch_session(conn: sqlite3.Connection, sid: str):
    """Update session last_access timestamp."""
    now = time.strftime("%Y-%m-%dT%H:%M:%S")
    conn.execute(
        "INSERT INTO sessions (session_id, last_access) VALUES (?, ?) "
        "ON CONFLICT(session_id) DO UPDATE SET last_access = excluded.last_access",
        (sid, now),
    )


def reset_session(sid: str = None):
    """Clear a session's overlay (revert to pristine)."""
    if sid is None:
        sid = _get_session_id()
    conn = _get_conn()
    conn.execute("DELETE FROM session_overlay WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM session_collection_replaced WHERE session_id = ?", (sid,))
    conn.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
    conn.commit()


def reset_all():
    """Clear all session overlays."""
    conn = _get_conn()
    conn.execute("DELETE FROM session_overlay")
    conn.execute("DELETE FROM session_collection_replaced")
    conn.execute("DELETE FROM sessions")
    conn.commit()


def evict_stale_sessions():
    """Remove sessions idle longer than TTL."""
    conn = _get_conn()
    cutoff = time.strftime(
        "%Y-%m-%dT%H:%M:%S",
        time.localtime(time.time() - _SESSION_TTL),
    )
    stale = [
        row[0]
        for row in conn.execute(
            "SELECT session_id FROM sessions WHERE last_access < ?", (cutoff,)
        ).fetchall()
    ]
    if stale:
        placeholders = ",".join("?" * len(stale))
        conn.execute(
            f"DELETE FROM session_overlay WHERE session_id IN ({placeholders})",
            stale,
        )
        conn.execute(
            f"DELETE FROM session_collection_replaced WHERE session_id IN ({placeholders})",
            stale,
        )
        conn.execute(
            f"DELETE FROM sessions WHERE session_id IN ({placeholders})",
            stale,
        )
        conn.commit()


def get_stats() -> dict:
    """Return overlay statistics for debugging."""
    conn = _get_conn()
    sessions = conn.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
    total_files = conn.execute("SELECT COUNT(*) FROM session_overlay").fetchone()[0]
    details = {}
    for row in conn.execute(
        "SELECT s.session_id, "
        "  (SELECT COUNT(*) FROM session_overlay o WHERE o.session_id = s.session_id) AS files, "
        "  s.last_access "
        "FROM sessions s"
    ).fetchall():
        details[row[0]] = {"files": row[1], "last_access": row[2]}
    return {
        "sessions": sessions,
        "total_files": total_files,
        "session_ttl_seconds": _SESSION_TTL,
        "sessions_detail": details,
    }


# ---------------------------------------------------------------------------
# Overlay helpers — fetch the (tiny) session mutations
# ---------------------------------------------------------------------------

def _get_overlay(sid: str, site: str, collection: str, conn: sqlite3.Connection):
    """Return (deletes: set[str], upserts: dict[str, dict]) for this session."""
    rows = conn.execute(
        "SELECT item_id, op, data FROM session_overlay "
        "WHERE session_id = ? AND site = ? AND collection = ?",
        (sid, site, collection),
    ).fetchall()

    deletes = set()
    upserts = {}
    for row in rows:
        item_id, op, data_str = row[0], row[1], row[2]
        if op == "delete":
            deletes.add(str(item_id))
        else:
            upserts[str(item_id)] = json.loads(data_str)

    return deletes, upserts


def _is_collection_replaced(sid: str, site: str, collection: str, conn: sqlite3.Connection) -> bool:
    """Check if this session fully replaced the collection."""
    return conn.execute(
        "SELECT 1 FROM session_collection_replaced "
        "WHERE session_id = ? AND site = ? AND collection = ?",
        (sid, site, collection),
    ).fetchone() is not None


# ---------------------------------------------------------------------------
# Query API — the main interface sites use
# ---------------------------------------------------------------------------

def query(
    site: str,
    collection: str,
    *,
    where: dict = None,
    sort: str = None,
    limit: int = None,
    offset: int = 0,
    sid: str = None,
) -> list[dict]:
    """Query items from a site table with SQL-level filtering.

    Args:
        site: Site name (e.g., "banking")
        collection: Collection name (e.g., "transactions")
        where: Filter dict, e.g., {"user_id": 1, "status": "posted"}
        sort: Column to sort by. Prefix with "-" for DESC (e.g., "-date")
        limit: Max rows to return
        offset: Skip this many rows
        sid: Session ID (auto-detected if None)

    Returns:
        List of dicts, one per matching row.
    """
    if sid is None:
        sid = _get_session_id()
    conn = _get_conn()
    _touch_session(conn, sid)

    table = get_table_name(site, collection)
    if table is None:
        conn.commit()
        return []

    pk_col = get_pk_column(site, collection)
    replaced = _is_collection_replaced(sid, site, collection, conn)
    deletes, upserts = _get_overlay(sid, site, collection, conn)

    if replaced:
        # Session owns the full collection — return only overlay data
        items = list(upserts.values())
        items = _apply_filters(items, where)
        items = _apply_sort(items, sort)
        if offset:
            items = items[offset:]
        if limit is not None:
            items = items[:limit]
        conn.commit()
        return items

    # Build SQL query against the base table
    sql = f"SELECT * FROM [{table}]"
    params = []
    clauses = []

    if where:
        for col, val in where.items():
            clauses.append(f"[{col}] = ?")
            params.append(val)

    # Exclude deleted items
    if deletes:
        placeholders = ",".join("?" * len(deletes))
        clauses.append(f"[{pk_col}] NOT IN ({placeholders})")
        params.extend(deletes)

    # Exclude items that have been upserted (we'll add the new version later)
    if upserts:
        placeholders = ",".join("?" * len(upserts))
        clauses.append(f"CAST([{pk_col}] AS TEXT) NOT IN ({placeholders})")
        params.extend(upserts.keys())

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    if sort:
        desc = sort.startswith("-")
        col = sort.lstrip("-")
        direction = "DESC" if desc else "ASC"
        sql += f" ORDER BY [{col}] {direction}"

    if limit is not None:
        # Fetch extra to account for upserts we'll merge in
        fetch_limit = limit + len(upserts) + offset
        sql += f" LIMIT {fetch_limit}"

    try:
        rows = conn.execute(sql, params).fetchall()
    except sqlite3.OperationalError:
        conn.commit()
        return []

    results = [_deserialize_row(row) for row in rows]

    # Merge upserts that match the filters
    if upserts:
        matching_upserts = _apply_filters(list(upserts.values()), where)
        results.extend(matching_upserts)
        results = _apply_sort(results, sort)

    # Apply offset and limit after merge
    if offset:
        results = results[offset:]
    if limit is not None:
        results = results[:limit]

    conn.commit()
    return results


def get_item(site: str, collection: str, item_id, sid: str = None) -> dict | None:
    """Fetch a single item by primary key.

    Checks session overlay first, then falls back to base table.
    """
    if sid is None:
        sid = _get_session_id()
    conn = _get_conn()
    _touch_session(conn, sid)

    item_id_str = str(item_id)

    # Check overlay first
    overlay_row = conn.execute(
        "SELECT op, data FROM session_overlay "
        "WHERE session_id = ? AND site = ? AND collection = ? AND item_id = ?",
        (sid, site, collection, item_id_str),
    ).fetchone()

    if overlay_row:
        if overlay_row[0] == "delete":
            conn.commit()
            return None
        conn.commit()
        return json.loads(overlay_row[1])

    # Check if collection was fully replaced (item not in overlay = doesn't exist)
    if _is_collection_replaced(sid, site, collection, conn):
        conn.commit()
        return None

    # Fetch from base table
    table = get_table_name(site, collection)
    if table is None:
        conn.commit()
        return None

    pk_col = get_pk_column(site, collection)
    try:
        row = conn.execute(
            f"SELECT * FROM [{table}] WHERE [{pk_col}] = ?", (item_id,)
        ).fetchone()
    except sqlite3.OperationalError:
        conn.commit()
        return None

    conn.commit()
    return _deserialize_row(row) if row else None


def count(
    site: str,
    collection: str,
    *,
    where: dict = None,
    sid: str = None,
) -> int:
    """Count matching items (base + overlay)."""
    if sid is None:
        sid = _get_session_id()
    conn = _get_conn()
    _touch_session(conn, sid)

    table = get_table_name(site, collection)
    if table is None:
        conn.commit()
        return 0

    pk_col = get_pk_column(site, collection)
    replaced = _is_collection_replaced(sid, site, collection, conn)
    deletes, upserts = _get_overlay(sid, site, collection, conn)

    if replaced:
        items = _apply_filters(list(upserts.values()), where)
        conn.commit()
        return len(items)

    # Count from base table
    sql = f"SELECT COUNT(*) FROM [{table}]"
    params = []
    clauses = []

    if where:
        for col, val in where.items():
            clauses.append(f"[{col}] = ?")
            params.append(val)

    if deletes:
        placeholders = ",".join("?" * len(deletes))
        clauses.append(f"[{pk_col}] NOT IN ({placeholders})")
        params.extend(deletes)

    if upserts:
        placeholders = ",".join("?" * len(upserts))
        clauses.append(f"CAST([{pk_col}] AS TEXT) NOT IN ({placeholders})")
        params.extend(upserts.keys())

    if clauses:
        sql += " WHERE " + " AND ".join(clauses)

    try:
        base_count = conn.execute(sql, params).fetchone()[0]
    except sqlite3.OperationalError:
        base_count = 0

    # Add matching upserts
    upsert_count = len(_apply_filters(list(upserts.values()), where))

    conn.commit()
    return base_count + upsert_count


def save_item(site: str, collection: str, item_id, data: dict, sid: str = None):
    """Save (upsert) a single item in the session overlay."""
    if sid is None:
        sid = _get_session_id()
    conn = _get_conn()
    _touch_session(conn, sid)

    conn.execute(
        "INSERT OR REPLACE INTO session_overlay "
        "(session_id, site, collection, item_id, op, data) "
        "VALUES (?, ?, ?, ?, 'upsert', ?)",
        (sid, site, collection, str(item_id), json.dumps(data, ensure_ascii=False)),
    )
    conn.commit()


def delete_item(site: str, collection: str, item_id, sid: str = None):
    """Mark an item as deleted in the session overlay."""
    if sid is None:
        sid = _get_session_id()
    conn = _get_conn()
    _touch_session(conn, sid)

    conn.execute(
        "INSERT OR REPLACE INTO session_overlay "
        "(session_id, site, collection, item_id, op, data) "
        "VALUES (?, ?, ?, ?, 'delete', NULL)",
        (sid, site, collection, str(item_id)),
    )
    conn.commit()


def save_collection(site: str, collection: str, items: list, sid: str = None):
    """Replace an entire collection for this session.

    The base table is NOT modified. The session is marked as having
    fully replaced this collection, and all items go into session_overlay.
    """
    if sid is None:
        sid = _get_session_id()
    conn = _get_conn()
    _touch_session(conn, sid)

    pk_col = get_pk_column(site, collection)

    conn.execute(
        "INSERT OR REPLACE INTO session_collection_replaced "
        "(session_id, site, collection) VALUES (?, ?, ?)",
        (sid, site, collection),
    )

    conn.execute(
        "DELETE FROM session_overlay "
        "WHERE session_id = ? AND site = ? AND collection = ?",
        (sid, site, collection),
    )

    conn.executemany(
        "INSERT INTO session_overlay "
        "(session_id, site, collection, item_id, op, data) "
        "VALUES (?, ?, ?, ?, 'upsert', ?)",
        [
            (sid, site, collection, str(item.get(pk_col, i)),
             json.dumps(item, ensure_ascii=False))
            for i, item in enumerate(items)
        ],
    )
    conn.commit()


# ---------------------------------------------------------------------------
# Raw SQL — for sites that need custom queries
# ---------------------------------------------------------------------------

def search(
    site: str,
    collection: str,
    q: str,
    *,
    where: dict = None,
    limit: int = 50,
    offset: int = 0,
) -> list[dict]:
    """Full-text search with BM25 ranking via FTS5.

    Falls back to LIKE-based search if FTS5 index doesn't exist.

    Args:
        site: Site name
        collection: Collection name
        q: Search query string
        where: Additional equality filters
        limit: Max results
        offset: Skip rows

    Returns:
        List of dicts ranked by relevance (best first).
    """
    if not q or not q.strip():
        return query(site, collection, where=where, limit=limit, offset=offset)

    conn = _get_conn()
    table = get_table_name(site, collection)
    if table is None:
        return []

    pk_col = get_pk_column(site, collection)
    fts_table = f"fts_{table}"

    # Sanitize query for FTS5: escape special chars, convert to prefix match
    terms = q.strip().split()
    fts_query = " ".join(f'"{t}"*' for t in terms if t)

    # Try FTS5 first
    try:
        # Check if FTS index is populated; skip to LIKE fallback if empty
        fts_count = conn.execute(
            f"SELECT COUNT(*) FROM [{fts_table}]"
        ).fetchone()[0]
        if fts_count > 0:
            sql_parts = [f"SELECT t.* FROM [{table}] t"]
            sql_parts.append(f"JOIN [{fts_table}] fts ON t.[{pk_col}] = fts.rowid")
            params = []

            where_clauses = [f"[{fts_table}] MATCH ?"]
            params.append(fts_query)

            if where:
                for col, val in where.items():
                    where_clauses.append(f"t.[{col}] = ?")
                    params.append(val)

            sql_parts.append("WHERE " + " AND ".join(where_clauses))
            sql_parts.append("ORDER BY fts.rank")
            sql_parts.append(f"LIMIT ? OFFSET ?")
            params.extend([limit, offset])

            sql = " ".join(sql_parts)
            rows = conn.execute(sql, params).fetchall()
            return [_deserialize_row(r) for r in rows]
    except sqlite3.OperationalError:
        pass

    # Fallback: LIKE-based search on all TEXT columns
    try:
        col_info = conn.execute(f"PRAGMA table_info([{table}])").fetchall()
        text_cols = [r[1] for r in col_info if "TEXT" in (r[2] or "").upper()]
    except sqlite3.OperationalError:
        return []

    if not text_cols:
        return []

    like_clauses = " OR ".join(f"[{c}] LIKE ?" for c in text_cols[:6])
    like_param = f"%{q}%"
    params = [like_param] * min(len(text_cols), 6)

    where_sql = f"({like_clauses})"
    if where:
        for col, val in where.items():
            where_sql += f" AND [{col}] = ?"
            params.append(val)

    sql = f"SELECT * FROM [{table}] WHERE {where_sql} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    try:
        rows = conn.execute(sql, params).fetchall()
        return [_deserialize_row(r) for r in rows]
    except sqlite3.OperationalError:
        return []


def execute(sql: str, params: tuple = (), fetch: str = "all"):
    """Run arbitrary SQL and return results.

    fetch: "all" -> list[dict], "one" -> dict|None, "val" -> scalar
    """
    conn = _get_conn()
    try:
        cursor = conn.execute(sql, params)
    except sqlite3.OperationalError:
        return [] if fetch == "all" else None

    if fetch == "val":
        row = cursor.fetchone()
        return row[0] if row else None
    elif fetch == "one":
        row = cursor.fetchone()
        return _deserialize_row(row) if row else None
    else:
        return [_deserialize_row(r) for r in cursor.fetchall()]








# ---------------------------------------------------------------------------
# Build helpers — used by build_db.py
# ---------------------------------------------------------------------------

def create_site_table(conn: sqlite3.Connection, table_name: str, columns: list,
                      indexes: list = None):
    """Create a per-site table from a schema definition.

    columns: list of (col_name, col_type_with_constraints) tuples
    indexes: list of column names or tuples of column names
    """
    col_defs = ", ".join(f"[{col}] {ctype}" for col, ctype in columns)
    conn.execute(f"CREATE TABLE IF NOT EXISTS [{table_name}] ({col_defs})")

    if indexes:
        for idx in indexes:
            if isinstance(idx, (list, tuple)):
                idx_name = f"idx_{table_name}_{'_'.join(idx)}"
                cols = ", ".join(f"[{c}]" for c in idx)
            else:
                idx_name = f"idx_{table_name}_{idx}"
                cols = f"[{idx}]"
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{table_name}] ({cols})"
            )


def bulk_insert(conn: sqlite3.Connection, table_name: str, columns: list, records: list):
    """Insert records into a per-site table.

    columns: list of (col_name, col_type) tuples (from schema)
    records: list of dicts
    """
    col_names = [col for col, _ in columns]
    placeholders = ", ".join("?" * len(col_names))
    col_list = ", ".join(f"[{c}]" for c in col_names)

    rows = []
    for rec in records:
        row = []
        for col_name in col_names:
            val = rec.get(col_name)
            # Serialize lists/dicts to JSON strings
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            row.append(val)
        rows.append(tuple(row))

    conn.executemany(
        f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
        rows,
    )




# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _deserialize_row(row) -> dict:
    """Convert a sqlite3.Row to a dict, auto-parsing JSON string values.

    Columns that were stored as TEXT but contain JSON arrays/objects
    (e.g., notifications, tags, senses) are deserialized back to Python.
    """
    d = dict(row)
    for key, val in d.items():
        if isinstance(val, str) and len(val) >= 2:
            first = val[0]
            if (first == '[' and val[-1] == ']') or (first == '{' and val[-1] == '}'):
                try:
                    d[key] = json.loads(val)
                except (json.JSONDecodeError, ValueError):
                    pass
    return d


def _apply_filters(items: list, where: dict | None) -> list:
    """Filter a list of dicts by a where clause (Python-side)."""
    if not where:
        return items
    result = []
    for item in items:
        match = True
        for col, val in where.items():
            item_val = item.get(col)
            if item_val != val and str(item_val) != str(val):
                match = False
                break
        if match:
            result.append(item)
    return result


def _apply_sort(items: list, sort: str | None) -> list:
    """Sort a list of dicts by a column."""
    if not sort or not items:
        return items
    desc = sort.startswith("-")
    col = sort.lstrip("-")
    return sorted(items, key=lambda x: (x.get(col) is None, x.get(col)), reverse=desc)


def _detect_id_field(items: list) -> str:
    """Detect the primary key field name from a list of dicts."""
    if not items:
        return "id"
    sample = items[0] if isinstance(items[0], dict) else {}
    if "id" in sample:
        return "id"
    for candidate in ("Id", "ID", "pageid", "item_id", "entry_id", "slug"):
        if candidate in sample:
            return candidate
    return "id"
