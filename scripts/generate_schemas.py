#!/usr/bin/env python3
"""Generate schema.py files for every site from existing data.

Scans data_sources/<dir>/*.json, infers column types, and writes
sites/<site>/schema.py with CREATE TABLE definitions.

Also samples raw CSV/JSONL files to include large-dataset columns.

Usage:
    python scripts/generate_schemas.py          # generate all
    python scripts/generate_schemas.py banking  # generate one site
"""

import csv
import json
import os
import pathlib
import sys
import textwrap

csv.field_size_limit(10_000_000)

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
SITES_DIR = PROJECT_ROOT / "sites"
DATA_SOURCES = pathlib.Path(
    os.environ.get("MINIWEB_DATA_SOURCES", "/scratch/general/vast/u1653932/data_sources")
)

# ---------------------------------------------------------------------------
# Site → data_sources directory mapping (extracted from each routes.py)
# ---------------------------------------------------------------------------

SITE_TO_DATA_DIR = {
    "academic-paper-db": "academic-paper-db",
    "agency-portals": "agency-portals",
    "ai-chatbots": "ai-chatbots",
    "auctions-p2p-marketplaces": "auctions-p2p-marketplaces",
    "banking": "banking",
    "blogs": "blogs",
    "books-comics": "books-comics",
    "brokerage": "brokerage",
    "business-company": "business-company",
    "calendar-todo": "calendar-todo",
    "cloud-dev-consoles": "cloud-dev-consoles",
    "cloud-storage-file-transfer": "cloud-storage-file-transfer",
    "code-editor-execution": "code-editor-execution",
    "comparison-aggregators": "comparison-aggregators",
    "conference-review-submission": "conference-review-submission",
    "converters-calculators": "converters-calculators",
    "course-sites-classrooms": "course-sites-classrooms",
    "crm": "crm",
    "crowdfunding-donations": "crowdfunding-donations",
    "dating": "dating",
    "design-creative": "design-creative",
    "dictionaries-language-tools": "dictionaries-language-tools",
    "documentation-api-docs": "documentation-api-docs",
    "documents": "documents",
    "e-commerce": "e-commerce",
    "email": "email",
    "flights-hotels": "flights-hotels",
    "forms-surveys": "forms-surveys",
    "forums": "reddit-augment",
    "handwritten-notes-whiteboards": "handwritten-notes-whiteboards",
    "health-fitness-tracking": "health-fitness",
    "health-portals": "health-portals",
    "instant-messaging": "instant-messaging",
    "insurance-loans": "insurance-loans",
    "job-sites": "indeed-jobs-augment",
    "live": "live",
    "map-services": "map-services",
    "multimedia-posting": "multimedia-posting",
    "music": "music",
    "news": "news",
    "password-managers": "password-managers",
    "personal-portfolio": "personal-portfolio",
    "petitions-voting-info": "petitions-voting",
    "podcasts-audiobooks": "podcasts-audiobooks",
    "project-homepages": "project-homepages",
    "project-mgmt-issue-tracking": "project-mgmt-issue-tracking",
    "qa-knowledge": "stackexchange-augment",
    "rating-review": "rating-review",
    "real-estate-buy-rent": "real-estate-buy-rent",
    "remote-calls": "remote-calls",
    "software-marketplace": "software-marketplace",
    "sports-esports": "sports-esports",
    "spreadsheets-slides": "spreadsheets-slides",
    "tax-filing-dmv-permits": "tax-dmv",
    "team-chat-workspace": "team-chat",
    "ticketing-events": "ticketing-events",
    "transit-directions": "transit-directions",
    "translation": "translation",
    "university-academic": "university-academic",
    "url-shorteners-qr": "url-shorteners-qr",
    "version-control": "gitlab-augment",
    "video": "video",
    "visual-how-to-guides": "visual-how-to-guides",  # also reads from wikihow zip
    "weather": "weather",
    "wikis": "wikis",
}

# Additional raw data sources per site.
# Format: {site: [(raw_dir, filename_or_glob, format, collection_name), ...]}
# format: "jsonl", "csv", "json_stream" (one JSON object per line, like arxiv)
RAW_DATA_SOURCES = {
    "academic-paper-db": [
        ("arxiv", "arxiv-metadata-oai-snapshot.json", "json_stream", "papers"),
    ],
    "books-comics": [
        ("pressbooks", "pressbooks-0000.json.gz", "skip", "books"),  # special ingestor
    ],
    "comparison-aggregators": [
        ("gsmarena", "phones.csv", "csv", "phones"),
    ],
    "conference-review-submission": [
        ("PeerRead", "peerread_reviews.jsonl", "skip", "papers"),  # special ingestor adds venue_id
    ],
    "dictionaries-language-tools": [
        ("wikidictionary", "raw-wiktextract-data.jsonl", "jsonl", "entries"),
    ],
    "e-commerce": [
        ("webshop", "products_sample.jsonl", "jsonl", "products"),
    ],
    "email": [
        ("enron", "enron_sample.jsonl", "jsonl", "emails"),
    ],
    "flights-hotels": [
        ("kaggle_flights", "US Airline Flight Routes and Fares 1993-2024.csv", "csv", "flights"),
        ("kaggle_hotels", "hotels.csv", "csv", "hotels"),
    ],
    "forums": [
        ("reddit", "reddit_posts.csv", "csv", "posts"),
        ("reddit", "reddit_comments.csv", "csv", "comments"),
        ("reddit", "reddit_users.csv", "csv", "reddit_users"),
        ("reddit", "reddit_forums.csv", "csv", "subreddits"),
    ],
    "job-sites": [
        ("indeed-jobs", "job_descriptions.csv", "csv", "jobs"),
    ],
    "music": [
        ("musicbrainz", "artist.tar.xz", "skip", "artists_raw"),  # needs special tar.xz extraction
    ],
    "news": [
        # enwikinews needs special bz2 XML extraction — handled by build_db.py ingestor
    ],
    "podcasts-audiobooks": [
        ("podcasts-audiobooks/books_data", "books.csv", "csv", "books_raw"),
        ("podcasts-audiobooks/books_data", "ratings.csv", "csv", "ratings_raw"),
    ],
    "qa-knowledge": [
        # stackexchange Posts.xml (81GB) needs special XML parsing — handled by build_db.py ingestor
        # The ingestor splits into questions + answers collections
    ],
    "real-estate-buy-rent": [
        ("realtor", "realtor-data.zip.csv", "csv", "listings_raw"),
    ],
    "software-marketplace": [
        ("kaggle_google_play", "googleplaystore.csv", "csv", "apps"),
        ("kaggle_google_play", "googleplaystore_user_reviews.csv", "csv", "app_reviews"),
    ],
    "version-control": [
        ("gitlab", "gitlab_issues.csv", "csv", "issues_raw"),
        ("gitlab", "gitlab_merge_requests.csv", "csv", "merge_requests_raw"),
        ("gitlab", "gitlab_notes.csv", "csv", "notes_raw"),
        ("gitlab", "gitlab_projects.csv", "csv", "projects_raw"),
        ("gitlab", "gitlab_users.csv", "csv", "users_raw"),
        ("gitlab", "gitlab_labels.csv", "csv", "labels_raw"),
    ],
    "wikis": [
        ("wiki", "wiki_articles.jsonl", "jsonl", "articles"),
    ],
}

# Additional JSON data from secondary data_sources dirs.
# Format: {site: [(data_dir, [json_filenames])]}
SECONDARY_JSON = {
    "banking": [
        ("credit-card", ["users.json", "transactions.json", "statements.json", "payments.json"]),
    ],
    "auctions-p2p-marketplaces": [
        ("webshop", ["products_sample.jsonl"]),  # handled via RAW_DATA_SOURCES pattern
    ],
}

# Skip these files — not real data collections
SKIP_FILES = {"_overlay_meta.json"}

# ---------------------------------------------------------------------------
# Type inference
# ---------------------------------------------------------------------------

def _py_type(val):
    """Map a Python value to a SQLite column type."""
    if val is None:
        return None
    if isinstance(val, bool):
        return "INTEGER"  # SQLite has no bool
    if isinstance(val, int):
        return "INTEGER"
    if isinstance(val, float):
        return "REAL"
    if isinstance(val, str):
        return "TEXT"
    if isinstance(val, (list, dict)):
        return "TEXT"  # stored as JSON string
    return "TEXT"


def _merge_types(existing, new):
    """Merge two column types, preferring the more general one."""
    if existing is None:
        return new
    if new is None:
        return existing
    if existing == new:
        return existing
    # INTEGER + REAL → REAL
    if {existing, new} == {"INTEGER", "REAL"}:
        return "REAL"
    # Anything + TEXT → TEXT
    return "TEXT"


def _sanitize_col(name):
    """Make a column name safe for SQL."""
    # Replace hyphens, dots, spaces with underscores
    s = name.replace("-", "_").replace(".", "_").replace(" ", "_")
    # Lowercase to avoid case-insensitive collisions (SQLite is case-insensitive)
    s = s.lower()
    # Remove non-alphanumeric (except underscore)
    s = "".join(c for c in s if c.isalnum() or c == "_")
    # Can't start with digit
    if s and s[0].isdigit():
        s = "_" + s
    # Reserved words
    if s.upper() in {"ORDER", "GROUP", "SELECT", "FROM", "WHERE", "INDEX",
                      "TABLE", "DROP", "CREATE", "INSERT", "UPDATE", "DELETE",
                      "JOIN", "LIKE", "IN", "AND", "OR", "NOT", "NULL",
                      "PRIMARY", "KEY", "DEFAULT", "CHECK", "REFERENCES",
                      "FOREIGN", "UNIQUE", "CONSTRAINT", "ALTER", "ADD",
                      "COLUMN", "SET", "VALUES", "INTO", "AS", "ON", "BY",
                      "ASC", "DESC", "LIMIT", "OFFSET", "HAVING", "UNION",
                      "EXCEPT", "CASE", "WHEN", "THEN", "ELSE", "END",
                      "EXISTS", "BETWEEN", "IS", "DISTINCT", "ALL", "ANY",
                      "TRANSACTION", "BEGIN", "COMMIT", "ROLLBACK",
                      "REPLACE", "TRIGGER", "VIEW", "TEMP", "TEMPORARY"}:
        s = s + "_"
    return s or "col"


def _sanitize_table(site, collection):
    """Create a SQL-safe table name from site + collection."""
    s = site.replace("-", "_") + "_" + collection.replace("-", "_")
    return _sanitize_col(s)


# Fields that should be auto-indexed
_INDEX_FIELDS = {
    "user_id", "author_id", "seller_id", "sender_id", "owner_id",
    "creator_id", "patient_id", "buyer_id", "reviewer_id", "provider_id",
    "root_user_id", "account_id", "project_id", "post_id", "parent_id",
    "album_id", "artist_id", "track_id", "campaign_id", "listing_id",
    "subreddit", "category", "type", "status", "state", "folder",
    "genre", "department", "role",
    "date", "created_at", "timestamp", "posted_at", "sent_at",
    "updated_at", "opened_date",
}


# ---------------------------------------------------------------------------
# Data readers
# ---------------------------------------------------------------------------

def _read_json_file(path, max_records=None):
    """Read a JSON file (array, object, or overlay-wrapped dict).

    Overlay-wrapped dicts look like:
        {"_overlay_meta": {...}, "posts": [...]}
    We unwrap them and return the list under the non-meta key.
    Returns: (collection_name_override | None, list_of_dicts)
    """
    with open(path) as f:
        data = json.load(f)

    # Overlay-wrapped dict: {"_overlay_meta": {...}, "posts": [...]}
    if isinstance(data, dict) and "_overlay_meta" in data:
        for key, val in data.items():
            if key == "_overlay_meta":
                continue
            if isinstance(val, list):
                coll_override = key  # e.g., "posts", "users"
                records = val[:max_records] if max_records else val
                return coll_override, records
        return None, []

    if isinstance(data, dict):
        return None, [data]
    if isinstance(data, list):
        if max_records:
            return None, data[:max_records]
        return None, data
    return None, []


def _read_jsonl_file(path, max_records=100):
    """Read a JSONL file, sampling first N records."""
    records = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if len(records) >= max_records:
                break
    return records


def _read_csv_file(path, max_records=100):
    """Read a CSV file, sampling first N records."""
    records = []
    try:
        with open(path, newline="", errors="replace") as f:
            reader = csv.DictReader(f)
            for row in reader:
                # Clean up keys (strip whitespace)
                cleaned = {k.strip(): v for k, v in row.items() if k}
                records.append(cleaned)
                if len(records) >= max_records:
                    break
    except Exception as e:
        print(f"  WARNING: Could not read CSV {path}: {e}")
    return records


def _coerce_csv_types(records):
    """Try to coerce CSV string values to int/float where appropriate."""
    if not records:
        return records
    for rec in records:
        for k, v in list(rec.items()):
            if v is None or v == "":
                rec[k] = None
                continue
            # Try int
            try:
                rec[k] = int(v)
                continue
            except (ValueError, TypeError):
                pass
            # Try float
            try:
                rec[k] = float(v)
                continue
            except (ValueError, TypeError):
                pass
            # Keep as string
    return records


# ---------------------------------------------------------------------------
# Schema inference
# ---------------------------------------------------------------------------

def infer_columns(records):
    """Infer column names and types from a list of dicts.

    Returns: dict of {col_name: sql_type}
    """
    columns = {}  # col_name -> sql_type
    for rec in records:
        if not isinstance(rec, dict):
            continue
        for key, val in rec.items():
            col = _sanitize_col(key)
            vtype = _py_type(val)
            if col in columns:
                columns[col] = _merge_types(columns[col], vtype)
            else:
                columns[col] = vtype

    # Fill in any None types as TEXT
    for col in columns:
        if columns[col] is None:
            columns[col] = "TEXT"

    return columns


def pick_primary_key(columns):
    """Detect the primary key field."""
    # All columns are already lowercased by _sanitize_col
    for candidate in ("id", "pageid", "item_id", "entry_id", "asin",
                       "slug", "message_id", "word"):
        if candidate in columns:
            return candidate
    return None


def pick_indexes(columns, pk):
    """Pick which columns should be indexed."""
    indexes = []
    for col in columns:
        if col == pk:
            continue
        if col in _INDEX_FIELDS:
            indexes.append(col)
    return sorted(indexes)


# ---------------------------------------------------------------------------
# Schema file writer
# ---------------------------------------------------------------------------

def write_schema(site, tables, output_path):
    """Write a schema.py file for a site."""
    lines = [
        '"""Database schema for %s.' % site,
        '',
        'Auto-generated by scripts/generate_schemas.py — edit freely.',
        '"""',
        '',
        'TABLES = {',
    ]

    for coll_name, info in sorted(tables.items()):
        table_name = _sanitize_table(site, coll_name)
        columns = info["columns"]
        pk = info.get("pk")
        indexes = info.get("indexes", [])

        lines.append(f'    "{coll_name}": {{')
        lines.append(f'        "table_name": "{table_name}",')

        # Columns — add NOT NULL DEFAULT to prevent NULLs
        lines.append('        "columns": [')
        for col, ctype in columns.items():
            if col == pk:
                suffix = " PRIMARY KEY"
            elif "INTEGER" in ctype:
                suffix = " NOT NULL DEFAULT 0"
            elif "REAL" in ctype:
                suffix = " NOT NULL DEFAULT 0.0"
            else:  # TEXT
                suffix = " NOT NULL DEFAULT ''"
            lines.append(f'            ("{col}", "{ctype}{suffix}"),')
        lines.append('        ],')

        # Indexes
        if indexes:
            lines.append('        "indexes": [')
            for idx in indexes:
                lines.append(f'            "{idx}",')
            lines.append('        ],')

        lines.append('    },')

    lines.append('}')
    lines.append('')

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines))
    print(f"  Wrote {output_path} ({len(tables)} tables)")


# ---------------------------------------------------------------------------
# Per-site schema generation
# ---------------------------------------------------------------------------

def generate_site_schema(site):
    """Generate schema.py for a single site."""
    data_dir_name = SITE_TO_DATA_DIR.get(site)
    if not data_dir_name:
        print(f"  SKIP {site}: no data directory mapping")
        return

    site_dir = SITES_DIR / site
    if not site_dir.exists():
        print(f"  SKIP {site}: site dir does not exist")
        return

    tables = {}  # collection_name -> {columns, pk, indexes}

    # 1. Read small JSON files from primary data_sources dir
    data_dir = DATA_SOURCES / data_dir_name
    if data_dir.exists():
        for json_file in sorted(data_dir.glob("*.json")):
            if json_file.name in SKIP_FILES:
                continue

            try:
                coll_override, records = _read_json_file(json_file)
            except (json.JSONDecodeError, OSError) as e:
                print(f"  WARNING: {json_file}: {e}")
                continue

            if not records:
                continue

            # Use collection name from overlay wrapper if available,
            # otherwise derive from filename (strip _overlay suffix)
            if coll_override:
                coll_name = coll_override
            else:
                coll_name = json_file.stem
                if coll_name.endswith("_overlay"):
                    coll_name = coll_name[:-8]

            columns = infer_columns(records)
            pk = pick_primary_key(columns)
            indexes = pick_indexes(columns, pk)

            if coll_name in tables:
                # Merge columns from multiple sources for same collection
                for col, ctype in columns.items():
                    if col in tables[coll_name]["columns"]:
                        tables[coll_name]["columns"][col] = _merge_types(
                            tables[coll_name]["columns"][col], ctype
                        )
                    else:
                        tables[coll_name]["columns"][col] = ctype
                # Merge indexes
                existing_idx = set(tables[coll_name].get("indexes", []))
                tables[coll_name]["indexes"] = sorted(existing_idx | set(indexes))
            else:
                tables[coll_name] = {"columns": columns, "pk": pk, "indexes": indexes}

    # 2. Read secondary JSON data (e.g., banking reads credit-card data)
    for sec_dir, sec_files in SECONDARY_JSON.get(site, []):
        sec_path = DATA_SOURCES / sec_dir
        if not sec_path.exists():
            continue
        for fname in sec_files:
            fpath = sec_path / fname
            if not fpath.exists():
                continue
            # Prefix collection name with secondary dir to avoid clashes
            coll_name = "cc_" + fname.replace(".json", "") if sec_dir == "credit-card" else sec_dir.replace("-", "_") + "_" + fname.replace(".json", "")

            if fname.endswith(".jsonl"):
                records = _read_jsonl_file(fpath, max_records=100)
            else:
                try:
                    _override, records = _read_json_file(fpath)
                except (json.JSONDecodeError, OSError):
                    continue

            if not records:
                continue

            columns = infer_columns(records)
            pk = pick_primary_key(columns)
            indexes = pick_indexes(columns, pk)
            tables[coll_name] = {"columns": columns, "pk": pk, "indexes": indexes}

    # 3. Read raw data sources (CSV, JSONL)
    for raw_dir, raw_file, fmt, coll_name in RAW_DATA_SOURCES.get(site, []):
        if fmt == "skip":
            continue
        raw_path = DATA_SOURCES / raw_dir / raw_file
        if not raw_path.exists():
            print(f"  WARNING: raw data not found: {raw_path}")
            continue

        if fmt == "csv":
            records = _read_csv_file(raw_path, max_records=100)
            records = _coerce_csv_types(records)
        elif fmt in ("jsonl", "json_stream"):
            records = _read_jsonl_file(raw_path, max_records=100)
        else:
            continue

        if not records:
            continue

        columns = infer_columns(records)
        pk = pick_primary_key(columns)
        indexes = pick_indexes(columns, pk)

        if coll_name in tables:
            # Merge with existing collection
            for col, ctype in columns.items():
                if col in tables[coll_name]["columns"]:
                    tables[coll_name]["columns"][col] = _merge_types(
                        tables[coll_name]["columns"][col], ctype
                    )
                else:
                    tables[coll_name]["columns"][col] = ctype
            existing_idx = set(tables[coll_name].get("indexes", []))
            tables[coll_name]["indexes"] = sorted(existing_idx | set(indexes))
        else:
            tables[coll_name] = {"columns": columns, "pk": pk, "indexes": indexes}

    if not tables:
        print(f"  SKIP {site}: no data found")
        return

    # Ensure every table has at least an id column
    for coll_name, info in tables.items():
        if not info.get("pk"):
            # No natural PK detected — add a synthetic row_id
            new_cols = {"row_id": "INTEGER"}
            new_cols.update(info["columns"])
            info["columns"] = new_cols
            info["pk"] = "row_id"

    output_path = site_dir / "schema.py"
    write_schema(site, tables, output_path)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    filter_sites = set(sys.argv[1:]) if len(sys.argv) > 1 else None

    sites = sorted(SITE_TO_DATA_DIR.keys())
    if filter_sites:
        sites = [s for s in sites if s in filter_sites]

    print(f"Generating schemas for {len(sites)} sites...")
    for site in sites:
        print(f"\n--- {site} ---")
        generate_site_schema(site)

    print(f"\nDone. Generated schema.py for {len(sites)} sites.")


if __name__ == "__main__":
    main()
