#!/usr/bin/env python3
"""Build miniweb.db from all data sources.

Scans data_sources/ and indexes everything into a single SQLite database.
Run on a compute node for large datasets (arxiv, wiktionary, stackexchange, etc.).

Usage:
    # Build everything
    python scripts/build_db.py

    # Build only small JSON sites (fast, for dev)
    python scripts/build_db.py --small-only

    # Build a specific large dataset
    python scripts/build_db.py --only arxiv
    python scripts/build_db.py --only wiktionary
    python scripts/build_db.py --only stackexchange
    python scripts/build_db.py --only indeed
    python scripts/build_db.py --only hotels
    python scripts/build_db.py --only realtor
    python scripts/build_db.py --only wikinews

Output:
    miniweb.db in project root (or MINIWEB_DB env var)
"""

import argparse
import bz2
import csv
import json
import os
import pathlib
import re
import sqlite3
import sys
import time
import xml.etree.ElementTree as ET

csv.field_size_limit(10_000_000)  # some GitLab fields exceed 131KB default

PROJECT_ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

DATA_SOURCES = pathlib.Path(
    os.environ.get("MINIWEB_DATA_SOURCES", "/scratch/general/vast/u1653932/data_sources")
)
DB_PATH = os.environ.get("MINIWEB_DB", str(PROJECT_ROOT / "miniweb.db"))

BATCH_SIZE = 5000  # rows per INSERT batch for large datasets
MAX_RAW_RECORDS = 1_000_000  # cap per raw_data collection (overridable via --max-raw)
_max_raw = MAX_RAW_RECORDS  # mutable runtime value, set by main()
_force = False  # skip existing data checks when True

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _progress(msg: str):
    print(f"  {msg}", flush=True)


def _detect_id_field(items: list) -> str:
    if not items:
        return "id"
    sample = items[0] if isinstance(items[0], dict) else {}
    for candidate in ("id", "Id", "ID", "pageid", "item_id", "entry_id", "slug"):
        if candidate in sample:
            return candidate
    return "id"



# ---------------------------------------------------------------------------
# Per-site tables — real columns from schema.py
# ---------------------------------------------------------------------------

SITES_DIR = PROJECT_ROOT / "sites"

# Reuse site→data_sources mapping from generate_schemas.py
from scripts.generate_schemas import SITE_TO_DATA_DIR, RAW_DATA_SOURCES, SECONDARY_JSON, SKIP_FILES


def _read_json_with_unwrap(path):
    """Read a JSON file, unwrapping overlay wrapper dicts.
    Returns (collection_name_override | None, records_list)."""
    with open(path) as f:
        data = json.load(f)
    if isinstance(data, dict) and "_overlay_meta" in data:
        for key, val in data.items():
            if key == "_overlay_meta":
                continue
            if isinstance(val, list):
                return key, val
        return None, []
    if isinstance(data, dict):
        return None, [data]
    if isinstance(data, list):
        return None, data
    return None, []


def _read_csv_records(path, max_records=None):
    """Read CSV file, coerce types. Returns list of dicts."""
    records = []
    with open(path, newline="", encoding="utf-8", errors="replace") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = {k.strip(): v for k, v in row.items() if k}
            # Coerce numeric values
            for k, v in list(rec.items()):
                if v is None or v == "":
                    rec[k] = None
                    continue
                try:
                    rec[k] = int(v)
                    continue
                except (ValueError, TypeError):
                    pass
                try:
                    rec[k] = float(v)
                    continue
                except (ValueError, TypeError):
                    pass
            records.append(rec)
            if max_records and len(records) >= max_records:
                break
    return records


def _read_jsonl_records(path, max_records=None):
    """Read JSONL file. Returns list of dicts."""
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
            if max_records and len(records) >= max_records:
                break
    return records


def _stream_raw_into_table(conn, raw_path, fmt, table_name, col_names,
                            col_list, placeholders, max_records):
    """Stream a large CSV/JSONL file into a per-site table in batches.
    Returns the number of records inserted."""
    count = 0
    batch = []
    t0 = time.time()

    if fmt == "csv":
        try:
            f = open(raw_path, newline="", encoding="utf-8", errors="replace")
            reader = csv.DictReader(f)
        except Exception as e:
            _progress(f"  WARNING: cannot read {raw_path}: {e}")
            return 0
        try:
            for row in reader:
                # Lowercase keys to match sanitized column names
                rec = {k.strip().lower(): v for k, v in row.items() if k}
                # Coerce numeric values
                _SQLITE_INT_MAX = 9223372036854775807
                for k, v in list(rec.items()):
                    if v is None or v == "":
                        rec[k] = None
                        continue
                    try:
                        iv = int(v)
                        if abs(iv) <= _SQLITE_INT_MAX:
                            rec[k] = iv
                        # else keep as string
                        continue
                    except (ValueError, TypeError):
                        pass
                    try:
                        rec[k] = float(v)
                        continue
                    except (ValueError, TypeError):
                        pass

                vals = []
                for c in col_names:
                    val = rec.get(c)
                    if isinstance(val, (list, dict)):
                        val = json.dumps(val, ensure_ascii=False)
                    vals.append(val)
                batch.append(tuple(vals))
                count += 1

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                        batch,
                    )
                    batch.clear()
                    if count % 100000 == 0:
                        conn.commit()
                        _progress(f"  {table_name}: {count:,} raw records ({time.time()-t0:.0f}s)")
                if count >= max_records:
                    break
        finally:
            f.close()

    elif fmt in ("jsonl", "json_stream"):
        try:
            f = open(raw_path)
        except Exception as e:
            _progress(f"  WARNING: cannot read {raw_path}: {e}")
            return 0
        try:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue

                vals = []
                for c in col_names:
                    val = rec.get(c)
                    if isinstance(val, (list, dict)):
                        val = json.dumps(val, ensure_ascii=False)
                    vals.append(val)
                batch.append(tuple(vals))
                count += 1

                if len(batch) >= BATCH_SIZE:
                    conn.executemany(
                        f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                        batch,
                    )
                    batch.clear()
                    if count % 100000 == 0:
                        conn.commit()
                        _progress(f"  {table_name}: {count:,} raw records ({time.time()-t0:.0f}s)")
                if count >= max_records:
                    break
        finally:
            f.close()

    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()

    if count > 0:
        _progress(f"  {table_name}: {count:,} raw records streamed ({time.time()-t0:.0f}s)")
    return count


# ---------------------------------------------------------------------------
# Special ingestors for formats that can't use the generic CSV/JSONL streamer
# ---------------------------------------------------------------------------

# Map of (site, collection) -> special ingestor function
# These are called instead of _stream_raw_into_table for specific collections
_SPECIAL_INGESTORS = {}


def _register_special(site, collection):
    """Decorator to register a special ingestor for a (site, collection) pair."""
    def decorator(fn):
        _SPECIAL_INGESTORS[(site, collection)] = fn
        return fn
    return decorator


@_register_special("qa-knowledge", "questions")
def _ingest_stackexchange_questions(conn, table_name, col_names, col_list, placeholders, max_records):
    """Stream StackExchange questions from Posts.xml into per-site table."""
    xml_path = DATA_SOURCES / "stackexchange" / "_tmp_extract" / "Posts.xml"
    if not xml_path.exists():
        _progress(f"SKIP {table_name}: Posts.xml not found")
        return 0
    _progress(f"Streaming StackExchange questions from Posts.xml...")
    batch = []
    count = 0
    t0 = time.time()
    context = ET.iterparse(str(xml_path), events=("end",))
    for event, elem in context:
        if elem.tag != "row":
            continue
        if elem.get("PostTypeId") != "1":  # 1 = question
            elem.clear()
            continue
        tags_str = elem.get("Tags", "")
        tags = re.findall(r'<([^>]+)>', tags_str) if tags_str else []
        rec = {
            "id": int(elem.get("Id", 0)),
            "title": elem.get("Title", ""),
            "body": (elem.get("Body", "") or "")[:2000],
            "tags": json.dumps(tags),
            "score": int(elem.get("Score", 0)),
            "creation_date": elem.get("CreationDate", ""),
            "answer_count": int(elem.get("AnswerCount", 0) or 0),
            "accepted_answer_id": elem.get("AcceptedAnswerId"),
            "owner_id": elem.get("OwnerUserId"),
            "view_count": int(elem.get("ViewCount", 0) or 0),
        }
        vals = tuple(rec.get(c) for c in col_names)
        batch.append(vals)
        count += 1
        elem.clear()
        if len(batch) >= BATCH_SIZE:
            conn.executemany(
                f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                batch,
            )
            batch.clear()
            if count % 100000 == 0:
                conn.commit()
                _progress(f"  {table_name}: {count:,} questions ({time.time()-t0:.0f}s)")
        if count >= max_records:
            break
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})", batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {count:,} questions streamed ({time.time()-t0:.0f}s)")
    return count


@_register_special("qa-knowledge", "answers")
def _ingest_stackexchange_answers(conn, table_name, col_names, col_list, placeholders, max_records):
    """Stream StackExchange answers from Posts.xml into per-site table."""
    xml_path = DATA_SOURCES / "stackexchange" / "_tmp_extract" / "Posts.xml"
    if not xml_path.exists():
        _progress(f"SKIP {table_name}: Posts.xml not found")
        return 0
    _progress(f"Streaming StackExchange answers from Posts.xml...")
    batch = []
    count = 0
    t0 = time.time()
    context = ET.iterparse(str(xml_path), events=("end",))
    for event, elem in context:
        if elem.tag != "row":
            continue
        if elem.get("PostTypeId") != "2":  # 2 = answer
            elem.clear()
            continue
        rec = {
            "id": int(elem.get("Id", 0)),
            "question_id": int(elem.get("ParentId", 0) or 0),
            "body": (elem.get("Body", "") or "")[:2000],
            "score": int(elem.get("Score", 0)),
            "creation_date": elem.get("CreationDate", ""),
            "owner_id": elem.get("OwnerUserId"),
        }
        vals = tuple(rec.get(c) for c in col_names)
        batch.append(vals)
        count += 1
        elem.clear()
        if len(batch) >= BATCH_SIZE:
            conn.executemany(
                f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                batch,
            )
            batch.clear()
            if count % 100000 == 0:
                conn.commit()
                _progress(f"  {table_name}: {count:,} answers ({time.time()-t0:.0f}s)")
        if count >= max_records:
            break
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})", batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {count:,} answers streamed ({time.time()-t0:.0f}s)")
    return count


@_register_special("qa-knowledge", "tags_meta")
def _ingest_qa_tags_meta(conn, table_name, col_names, col_list, placeholders, max_records):
    """Pre-compute tag counts from the already-ingested questions table."""
    try:
        rows = conn.execute(
            "SELECT [tags] FROM [qa_knowledge_questions] WHERE [tags] IS NOT NULL AND [tags] != ''"
        ).fetchall()
    except Exception:
        _progress(f"  {table_name}: questions table not ready, skipping tags_meta")
        return 0

    from collections import Counter
    tag_counts = Counter()
    for row in rows:
        raw = row[0] if isinstance(row, (tuple, list)) else row.get("tags", "")
        if isinstance(raw, str) and raw.startswith("["):
            try:
                for t in json.loads(raw):
                    tag_counts[t] += 1
            except (json.JSONDecodeError, TypeError):
                pass
        elif isinstance(raw, str):
            tag_counts[raw] += 1

    batch = [(tag, count) for tag, count in tag_counts.most_common()]
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {len(batch)} unique tags pre-computed")
    return len(batch)


@_register_special("news", "articles")
def _ingest_wikinews(conn, table_name, col_names, col_list, placeholders, max_records):
    """Stream enwikinews articles from bz2 XML dump into per-site table."""
    dump_path = (
        DATA_SOURCES / "enwikinews"
        / "enwikinews-20260501-pages-articles1.xml-p1p1500000.bz2"
    )
    if not dump_path.exists():
        _progress(f"SKIP {table_name}: wikinews dump not found")
        return 0
    _progress(f"Streaming wikinews from bz2 XML...")
    batch = []
    count = 0
    t0 = time.time()
    with bz2.open(dump_path, "rb") as f:
        context = ET.iterparse(f, events=("end",))
        ns = ""
        for event, elem in context:
            if not ns and "}" in elem.tag:
                ns = elem.tag.split("}")[0] + "}"
            if elem.tag == f"{ns}page":
                ns_elem = elem.find(f"{ns}ns")
                if ns_elem is not None and ns_elem.text == "0":
                    title_elem = elem.find(f"{ns}title")
                    id_elem = elem.find(f"{ns}id")
                    rev = elem.find(f"{ns}revision")
                    text_elem = rev.find(f"{ns}text") if rev is not None else None
                    if title_elem is not None and text_elem is not None:
                        text = text_elem.text or ""
                        if text.startswith("#REDIRECT") or len(text) < 200:
                            elem.clear()
                            continue
                        rec = {
                            "id": int(id_elem.text) if id_elem is not None else count,
                            "title": title_elem.text or "",
                            "text": text[:5000],
                        }
                        vals = tuple(rec.get(c) for c in col_names)
                        batch.append(vals)
                        count += 1
                        if len(batch) >= BATCH_SIZE:
                            conn.executemany(
                                f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                                batch,
                            )
                            batch.clear()
                            conn.commit()
                elem.clear()
                if count >= max_records:
                    break
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})", batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {count:,} articles streamed ({time.time()-t0:.0f}s)")
    return count



@_register_special("job-sites", "jobs")
def _ingest_indeed_jobs(conn, table_name, col_names, col_list, placeholders, max_records):
    """Stream Indeed jobs CSV, mapping 'Job Title' -> 'job_title' etc."""
    raw_path = DATA_SOURCES / "indeed-jobs" / "job_descriptions.csv"
    if not raw_path.exists():
        _progress(f"SKIP {table_name}: job_descriptions.csv not found")
        return 0
    _progress("Streaming Indeed jobs with header mapping...")
    key_map = {
        'job id': 'job_id', 'salary range': 'salary_range',
        'work type': 'work_type', 'company size': 'company_size',
        'job posting date': 'job_posting_date', 'contact person': 'contact_person',
        'job title': 'job_title', 'job portal': 'job_portal',
        'job description': 'job_description', 'company profile': 'company_profile',
    }
    batch = []
    count = 0
    t0 = time.time()
    with open(raw_path, newline='', encoding='utf-8', errors='replace') as f:
        reader = csv.DictReader(f)
        for row in reader:
            rec = {}
            for k, v in row.items():
                if not k:
                    continue
                key = k.strip().lower()
                mapped = key_map.get(key, key)
                if v is None or v == '':
                    rec[mapped] = None
                else:
                    _SQLITE_INT_MAX = 9223372036854775807
                    try:
                        iv = int(v)
                        if abs(iv) <= _SQLITE_INT_MAX:
                            rec[mapped] = iv
                        continue
                    except (ValueError, TypeError):
                        pass
                    try:
                        rec[mapped] = float(v)
                        continue
                    except (ValueError, TypeError):
                        pass
                    rec[mapped] = v
            vals = []
            for c in col_names:
                val = rec.get(c)
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                vals.append(val)
            batch.append(tuple(vals))
            count += 1
            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})", batch)
                batch.clear()
                if count % 100000 == 0:
                    conn.commit()
                    _progress(f"  {table_name}: {count:,} jobs ({time.time()-t0:.0f}s)")
            if count >= max_records:
                break
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})", batch)
    conn.commit()
    _progress(f"  {table_name}: {count:,} jobs streamed ({time.time()-t0:.0f}s)")
    return count


@_register_special("email", "emails")
def _ingest_enron_emails(conn, table_name, col_names, col_list, placeholders, max_records):
    """Stream Enron emails from JSONL, mapping 'from' -> 'from_' (SQL keyword)."""
    raw_path = DATA_SOURCES / "enron" / "enron_sample.jsonl"
    if not raw_path.exists():
        _progress(f"SKIP {table_name}: enron_sample.jsonl not found")
        return 0
    _progress(f"Streaming Enron emails...")
    batch = []
    count = 0
    t0 = time.time()
    # Map raw keys to schema columns: 'from' -> 'from_'
    key_map = {"from_": "from"}
    with open(raw_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            vals = []
            for c in col_names:
                raw_key = key_map.get(c, c)
                val = rec.get(raw_key)
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                vals.append(val)
            batch.append(tuple(vals))
            count += 1
            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                    batch,
                )
                batch.clear()
                if count % 100000 == 0:
                    conn.commit()
                    _progress(f"  {table_name}: {count:,} emails ({time.time()-t0:.0f}s)")
            if count >= max_records:
                break
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {count:,} emails streamed ({time.time()-t0:.0f}s)")
    return count


@_register_special("visual-how-to-guides", "guides")
def _ingest_wikihow_guides(conn, table_name, col_names, col_list, placeholders, max_records):
    """Parse WikiHow zip data into guides with real images and steps."""
    import random as _rng
    import zipfile
    _rng.seed(42)

    zip_path = DATA_SOURCES / "Visual How-20260627T163940Z-3-001.zip"
    if not zip_path.exists():
        _progress(f"SKIP {table_name}: WikiHow zip not found")
        return 0

    _progress("Parsing WikiHow data from zip...")
    z = zipfile.ZipFile(zip_path)
    with z.open('Visual How/wikiHow_data.json') as f:
        raw = json.load(f)

    # Deduplicate by article_id
    articles = {}
    for entry in raw.values():
        aid = entry['article_id']
        if aid not in articles:
            articles[aid] = {
                'title': entry['article_title'],
                'category': entry['category'],
                'sections': [],
            }
        articles[aid]['sections'].append({
            'problem_idx': int(entry.get('problem_idx', 0)),
            'image_url': entry.get('image_url', []),
            'step_list': entry.get('step_list', []),
        })
    for a in articles.values():
        a['sections'].sort(key=lambda s: s['problem_idx'])

    difficulties = ['Beginner', 'Intermediate', 'Advanced']
    dw = [50, 35, 15]
    times = ['5 min', '10 min', '15 min', '20 min', '30 min', '45 min', '1 hour']
    authors = ['WikiHow Team', 'Expert Contributors', 'Community Writers', 'Staff Editor']

    batch = []
    for i, (aid, a) in enumerate(sorted(articles.items()), 1):
        if i > max_records:
            break
        cats = a['category']
        top_cat = cats[0] if cats else 'General'
        sub_cat = cats[1] if len(cats) > 1 else ''
        steps = []
        images = []
        for sec in a['sections']:
            for j, txt in enumerate(sec['step_list']):
                img = sec['image_url'][j] if j < len(sec['image_url']) else ''
                steps.append({'number': len(steps)+1, 'title': txt[:80], 'description': txt, 'image': img})
                if img:
                    images.append(img)
        cover = images[0] if images else ''
        desc = '. '.join(s['description'] for s in steps[:3])[:300]
        rec = {
            'id': i, 'title': f'How to {a["title"]}', 'description': desc,
            'category': top_cat, 'subcategory': sub_cat,
            'difficulty': _rng.choices(difficulties, weights=dw, k=1)[0],
            'time_estimate': _rng.choice(times), 'author': _rng.choice(authors),
            'rating': round(_rng.uniform(3.5, 5.0), 1),
            'views': _rng.randint(100, 50000),
            'date_published': f'2026-{_rng.randint(1,6):02d}-{_rng.randint(1,28):02d}',
            'steps': json.dumps(steps), 'cover_image': cover,
            'tags': json.dumps(cats[1:3] if len(cats) > 1 else []),
        }
        vals = tuple(rec.get(c) for c in col_names)
        batch.append(vals)

    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})", batch)
    conn.commit()
    _progress(f"  {table_name}: {len(batch)} guides from WikiHow ({len(articles)} articles)")
    return len(batch)


@_register_special("real-estate-buy-rent", "listings")
def _ingest_realtor_listings(conn, table_name, col_names, col_list, placeholders, max_records):
    """Generate real estate listings from realtor raw data."""
    import random as _rng
    _rng.seed(42)

    raw_table = "real_estate_buy_rent_listings_raw"
    try:
        good = conn.execute(
            f"SELECT COUNT(*) FROM [{raw_table}] WHERE price > 0 AND city != '' AND bed > 0"
        ).fetchone()[0]
    except Exception:
        _progress(f"SKIP {table_name}: listings_raw not available yet")
        return 0
    if good == 0:
        return 0

    try:
        agents = conn.execute("SELECT id FROM real_estate_buy_rent_agents").fetchall()
        agent_ids = [a[0] for a in agents] or [1]
    except Exception:
        agent_ids = [1]

    types = ['Single Family', 'Condo', 'Townhouse', 'Multi-Family', 'Land']
    type_weights = [50, 20, 15, 10, 5]
    limit = min(5000, max_records)

    rows = conn.execute(
        f"SELECT row_id, price, bed, bath, acre_lot, city, state, zip_code, house_size, status "
        f"FROM [{raw_table}] WHERE price > 0 AND price < 50000000 AND city != '' AND bed > 0 "
        f"ORDER BY row_id LIMIT ?", (limit,)
    ).fetchall()

    batch = []
    for i, r in enumerate(rows, 1):
        price, bed, bath = r[1], r[2], r[3]
        city, state = r[5], r[6]
        zip_code = str(r[7]).zfill(5) if r[7] else ''
        sqft = int(r[8]) if r[8] else _rng.randint(800, 3000)
        lot_sqft = int(r[4] * 43560) if r[4] else 0
        status = 'for_sale' if r[9] in ('for_sale', '') else r[9]
        prop_type = _rng.choices(types, weights=type_weights, k=1)[0]
        title = f'{bed} Bed / {bath} Bath {prop_type} in {city}, {state}'
        desc = (f'Beautiful {prop_type.lower()} featuring {bed} bedrooms and {bath} bathrooms. '
                f'{sqft:,} sq ft. Located in {city}, {state} {zip_code}.')

        rec = {
            'id': i, 'title': title, 'address': f'{city} {state}', 'city': city,
            'state': state, 'zip': zip_code, 'type': prop_type, 'status': status,
            'price': int(price), 'rent_monthly': 0, 'bedrooms': bed, 'bathrooms': bath,
            'sqft': sqft, 'lot_sqft': lot_sqft, 'year_built': _rng.randint(1960, 2024),
            'description': desc, 'features': '["Central AC", "Garage", "Updated Kitchen"]',
            'agent_id': _rng.choice(agent_ids),
            'listed_date': f'2026-{_rng.randint(1,6):02d}-{_rng.randint(1,28):02d}',
            'photos_count': _rng.randint(3, 15),
        }
        vals = tuple(rec.get(c) for c in col_names)
        batch.append(vals)

    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})", batch)
    conn.commit()
    _progress(f"  {table_name}: {len(batch)} listings from realtor data")
    return len(batch)


@_register_special("books-comics", "books")
def _ingest_pressbooks(conn, table_name, col_names, col_list, placeholders, max_records):
    """Deduplicate pressbooks chapters into one row per book."""
    import gzip
    import hashlib
    import random as _rng
    _rng.seed(42)

    raw_path = DATA_SOURCES / "pressbooks" / "pressbooks-0000.json.gz"
    if not raw_path.exists():
        _progress(f"SKIP {table_name}: pressbooks data not found")
        return 0

    CATEGORY_MAP = {
        'nursing': 'health-sciences', 'health': 'health-sciences', 'medicine': 'health-sciences',
        'biology': 'science', 'chemistry': 'science', 'physics': 'science', 'science': 'science',
        'math': 'mathematics', 'calculus': 'mathematics', 'statistics': 'mathematics',
        'algebra': 'mathematics', 'computer': 'technology', 'programming': 'technology',
        'information': 'technology', 'engineering': 'engineering',
        'business': 'business', 'economics': 'business', 'management': 'business',
        'accounting': 'business', 'finance': 'business',
        'history': 'humanities', 'philosophy': 'humanities', 'literature': 'humanities',
        'english': 'humanities', 'writing': 'humanities',
        'art': 'arts', 'music': 'arts', 'design': 'arts',
        'psychology': 'social-sciences', 'sociology': 'social-sciences', 'political': 'social-sciences',
        'education': 'education', 'teaching': 'education', 'language': 'education',
        'law': 'law', 'criminal': 'law',
    }
    COVER_COLORS = {
        'health-sciences': '2ecc71', 'science': '3498db', 'mathematics': '9b59b6',
        'technology': '1abc9c', 'engineering': 'e67e22', 'business': 'f39c12',
        'humanities': 'e74c3c', 'arts': 'e91e63', 'social-sciences': '00bcd4',
        'education': '8bc34a', 'law': '795548', 'general': '607d8b',
    }

    def _map_cat(subject):
        s = subject.lower()
        for kw, cat in CATEGORY_MAP.items():
            if kw in s:
                return cat
        return 'general'

    _progress("Deduplicating pressbooks chapters into books...")
    books_by_title = {}
    with gzip.open(raw_path, 'rt') as f:
        for line in f:
            rec = json.loads(line)
            meta = rec.get('metadata', {})
            title = meta.get('title', '').strip()
            if not title:
                continue
            if title not in books_by_title:
                books_by_title[title] = {
                    'title': title,
                    'author': meta.get('author', '').strip(),
                    'subject': meta.get('subject', '').strip(),
                    'book_url': meta.get('book_url', '').strip(),
                    'institution': meta.get('institution', '').strip(),
                    'license': meta.get('license', '').strip(),
                    'description': rec.get('text', '')[:500].strip(),
                    'created': rec.get('created', ''),
                    'chapters': [],
                }
            ch_text = rec.get('text', '')
            ch_title = ch_text[:80].split('\n')[0].strip() if ch_text else f'Chapter {len(books_by_title[title]["chapters"]) + 1}'
            books_by_title[title]['chapters'].append({
                'chapter': len(books_by_title[title]['chapters']) + 1,
                'title': ch_title[:100],
            })

    batch = []
    for i, (title, book) in enumerate(sorted(books_by_title.items()), 1):
        cat = _map_cat(book['subject'])
        year = 2023
        if book['created']:
            try:
                year = int(book['created'][:4])
            except (ValueError, IndexError):
                pass
        color = COVER_COLORS.get(cat, '607d8b')
        cover_url = f'https://placehold.co/300x400/{color}/ffffff?text={title[:20].replace(" ", "+")}'

        rec = {
            'id': i, 'title': title, 'author': book['author'],
            'description': book['description'], 'subject': book['subject'],
            'category': cat, 'book_url': book['book_url'],
            'institution': book['institution'], 'license': book['license'],
            'cover_url': cover_url, 'rating': round(_rng.uniform(3.0, 5.0), 1),
            'price': 0.0, 'year': year, 'num_chapters': len(book['chapters']),
            'chapters': json.dumps(book['chapters'][:50]),
        }
        vals = tuple(rec.get(c) for c in col_names)
        batch.append(vals)
        if i >= max_records:
            break

    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {len(batch)} books from {len(books_by_title)} unique titles")
    return len(batch)


@_register_special("email", "sent_messages")
def _ingest_email_sent_messages(conn, table_name, col_names, col_list, placeholders, max_records):
    """Load email sent_messages from JSON, mapping 'from' -> 'from_' (SQL keyword)."""
    raw_path = DATA_SOURCES / "email" / "sent_messages.json"
    if not raw_path.exists():
        _progress(f"SKIP {table_name}: sent_messages.json not found")
        return 0
    with open(raw_path) as f:
        records = json.load(f)
    key_map = {"from_": "from"}
    batch = []
    for rec in records:
        vals = []
        for c in col_names:
            raw_key = key_map.get(c, c)
            val = rec.get(raw_key)
            if isinstance(val, (list, dict)):
                val = json.dumps(val, ensure_ascii=False)
            vals.append(val)
        batch.append(tuple(vals))
    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {len(batch)} sent_messages loaded")
    return len(batch)


@_register_special("conference-review-submission", "papers")
def _ingest_peerread_papers(conn, table_name, col_names, col_list, placeholders, max_records):
    """Stream PeerRead JSONL and tag all papers with venue_id='iclr-2017'."""
    raw_path = DATA_SOURCES / "PeerRead" / "peerread_reviews.jsonl"
    if not raw_path.exists():
        _progress(f"  WARNING: {raw_path} not found")
        return 0

    count = 0
    batch = []
    with open(raw_path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            # Tag with venue_id
            rec["venue_id"] = "iclr-2017"

            vals = []
            for c in col_names:
                val = rec.get(c)
                if isinstance(val, (list, dict)):
                    val = json.dumps(val, ensure_ascii=False)
                vals.append(val)
            batch.append(tuple(vals))
            count += 1

            if len(batch) >= BATCH_SIZE:
                conn.executemany(
                    f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                    batch,
                )
                batch.clear()
            if count >= max_records:
                break

    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {count} PeerRead papers (venue_id=iclr-2017)")
    return count


@_register_special("auctions-p2p-marketplaces", "products")
def _ingest_auction_products(conn, table_name, col_names, col_list, placeholders, max_records):
    """Generate auction products from webshop data (resale items below retail)."""
    import random as _rng
    import re as _re
    _rng.seed(42)

    ws_table = "auctions_p2p_marketplaces_webshop_products_samplel"
    try:
        rows = conn.execute(
            f"SELECT rowid, * FROM [{ws_table}] WHERE pricing != '' AND images != '' AND images != '[]'"
        ).fetchall()
    except Exception:
        _progress(f"SKIP {table_name}: webshop table not available yet")
        return 0

    if not rows:
        _progress(f"SKIP {table_name}: no webshop products with pricing/images")
        return 0

    def _parse_price(s):
        m = _re.search(r'[\d,]+\.?\d*', s.replace(',', ''))
        return float(m.group()) if m else 0.0

    def _first_img(imgs_str):
        try:
            imgs = json.loads(imgs_str)
            for img in imgs:
                if 'transparent-pixel' not in img:
                    return img
            return imgs[0] if imgs else ''
        except Exception:
            return ''

    # Lookup existing users for seller assignment
    try:
        users = conn.execute(
            "SELECT id, username FROM auctions_p2p_marketplaces_users"
        ).fetchall()
        user_list = [(u[0], u[1]) for u in users] or [(1, 'seller1')]
    except Exception:
        user_list = [(1, 'seller1')]

    conditions = ['New', 'Like New', 'Very Good', 'Good', 'Acceptable']
    cond_weights = [5, 30, 25, 30, 10]
    shipping_opts = ['Free Shipping', '$4.99 Standard', '$9.99 Express', 'Local Pickup']
    cities = ['Portland, OR', 'Austin, TX', 'Denver, CO', 'Seattle, WA', 'Chicago, IL',
              'Miami, FL', 'Boston, MA', 'Phoenix, AZ', 'Nashville, TN', 'San Diego, CA']
    return_policies = ['30-day returns', '14-day returns', 'No returns', '60-day returns']

    batch = []
    count = 0
    for i, r in enumerate(rows, 1):
        price = _parse_price(r['pricing'])
        if price <= 0:
            continue
        img = _first_img(r['images'])
        if not img:
            continue

        seller = _rng.choice(user_list)
        cond = _rng.choices(conditions, weights=cond_weights, k=1)[0]
        start = round(price * _rng.uniform(0.3, 0.6), 2)
        num_bids = _rng.choices(range(16), weights=[5]+[10]*5+[6]*5+[2]*5, k=1)[0]
        current = round(start + num_bids * _rng.uniform(0.5, price*0.03+0.5), 2) if num_bids > 0 else start
        current = min(current, round(price * 0.92, 2))
        buy_now = round(price * _rng.uniform(0.75, 0.95), 2)

        start_day = _rng.randint(20, 27)
        duration = _rng.randint(3, 10)
        status = 'ended' if _rng.random() < 0.10 else 'active'
        winner = str(_rng.choice(user_list)[0]) if status == 'ended' else ''
        end_day = start_day + duration
        end_month = '07' if end_day > 30 else '06'
        end_day_num = end_day - 30 if end_day > 30 else end_day

        rec = {
            'id': i, 'asin': r['asin'], 'name': r['name'], 'image_url': img,
            'category': r['category'], 'brand': r['brand'], 'condition': cond,
            'description': r['full_description'] or r['small_description'] or '',
            'start_price': start, 'current_price': current, 'buy_now_price': buy_now,
            'reserve_price': round(price * 0.5, 2), 'num_bids': num_bids,
            'seller_id': seller[0], 'seller_username': seller[1],
            'seller_rating': round(_rng.uniform(3.5, 5.0), 1),
            'auction_start': f'2026-06-{start_day:02d}T{_rng.randint(8,20):02d}:00:00Z',
            'auction_end': f'2026-{end_month}-{end_day_num:02d}T{_rng.randint(8,20):02d}:00:00Z',
            'status': status, 'winner_id': winner,
            'shipping': _rng.choice(shipping_opts), 'location': _rng.choice(cities),
            'views': _rng.randint(10, 500), 'watchers': _rng.randint(0, 20),
            'color_options': '[]', 'size_options': '[]',
            'return_policy': _rng.choice(return_policies),
            'payment_methods': '["Credit Card", "PayPal"]',
        }
        vals = tuple(rec.get(c) for c in col_names)
        batch.append(vals)
        count += 1

    if batch:
        conn.executemany(
            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
            batch,
        )
    conn.commit()
    _progress(f"  {table_name}: {count} auction products generated from webshop")
    return count


def build_site_tables(conn):
    """Create per-site tables from schema.py and populate with data."""
    print("\n=== Building per-site tables ===")
    total_tables = 0
    total_records = 0

    for site_dir in sorted(SITES_DIR.iterdir()):
        if not site_dir.is_dir():
            continue
        schema_file = site_dir / "schema.py"
        if not schema_file.exists():
            continue

        site_name = site_dir.name
        if site_name.startswith("_"):
            continue

        # Import the schema module
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"sites.{site_name}.schema", schema_file
        )
        schema_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(schema_mod)

        if not hasattr(schema_mod, "TABLES"):
            continue

        # Collect data from all sources for this site
        data_dir_name = SITE_TO_DATA_DIR.get(site_name)
        site_data = {}  # collection_name -> list of records

        # 1. Primary JSON files
        if data_dir_name:
            data_dir = DATA_SOURCES / data_dir_name
            if data_dir.exists():
                for json_file in sorted(data_dir.glob("*.json")):
                    if json_file.name in SKIP_FILES:
                        continue
                    try:
                        coll_override, records = _read_json_with_unwrap(json_file)
                    except (json.JSONDecodeError, OSError):
                        continue
                    if not records:
                        continue
                    coll_name = coll_override or json_file.stem
                    if coll_name.endswith("_overlay"):
                        coll_name = coll_name[:-8]
                    if coll_name in site_data:
                        site_data[coll_name].extend(records)
                    else:
                        site_data[coll_name] = list(records)

        # 2. Secondary JSON (e.g., banking reads credit-card)
        for sec_dir, sec_files in SECONDARY_JSON.get(site_name, []):
            sec_path = DATA_SOURCES / sec_dir
            if not sec_path.exists():
                continue
            for fname in sec_files:
                fpath = sec_path / fname
                if not fpath.exists():
                    continue
                coll_name = "cc_" + fname.replace(".json", "") if sec_dir == "credit-card" else sec_dir.replace("-", "_") + "_" + fname.replace(".json", "")
                if fname.endswith(".jsonl"):
                    records = _read_jsonl_records(fpath)
                else:
                    try:
                        _, records = _read_json_with_unwrap(fpath)
                    except (json.JSONDecodeError, OSError):
                        continue
                if records:
                    site_data[coll_name] = records

        # 3. Raw data sources (CSV, JSONL)
        # Large raw datasets are inserted in streaming batches below
        # (not loaded into site_data to avoid OOM)
        raw_sources_for_site = []
        for raw_dir, raw_file, fmt, coll_name in RAW_DATA_SOURCES.get(site_name, []):
            if fmt == "skip":
                continue
            raw_path = DATA_SOURCES / raw_dir / raw_file
            if not raw_path.exists():
                continue
            raw_sources_for_site.append((raw_path, fmt, coll_name))

        # Create tables and insert data
        site_table_count = 0
        site_record_count = 0
        for coll_name, table_def in schema_mod.TABLES.items():
            table_name = table_def["table_name"]
            columns = table_def["columns"]
            indexes = table_def.get("indexes", [])

            # Check if already exists and populated
            if not _force:
                try:
                    existing = conn.execute(
                        f"SELECT COUNT(*) FROM [{table_name}]"
                    ).fetchone()[0]
                    if existing > 0:
                        site_table_count += 1
                        site_record_count += existing
                        continue
                except sqlite3.OperationalError:
                    pass  # Table doesn't exist yet

            # Create table
            col_defs = ", ".join(f"[{col}] {ctype}" for col, ctype in columns)
            conn.execute(f"DROP TABLE IF EXISTS [{table_name}]")
            conn.execute(f"CREATE TABLE [{table_name}] ({col_defs})")

            # Create indexes
            for idx in indexes:
                if isinstance(idx, (list, tuple)):
                    idx_name = f"idx_{table_name}_{'_'.join(idx)}"
                    cols = ", ".join(f"[{c}]" for c in idx)
                else:
                    idx_name = f"idx_{table_name}_{idx}"
                    cols = f"[{idx}]"
                conn.execute(f"CREATE INDEX IF NOT EXISTS [{idx_name}] ON [{table_name}] ({cols})")

            # Detect PK column
            pk_col = "id"
            for col, ctype in columns:
                if "PRIMARY KEY" in ctype:
                    pk_col = col
                    break

            # Register in site_registry
            conn.execute(
                "INSERT OR REPLACE INTO site_registry (site, collection, table_name, pk_column) "
                "VALUES (?, ?, ?, ?)",
                (site_name, coll_name, table_name, pk_col),
            )

            # Insert small JSON data
            col_names = [col for col, _ in columns]
            placeholders = ", ".join("?" * len(col_names))
            col_list = ", ".join(f"[{c}]" for c in col_names)

            records = site_data.get(coll_name, [])
            if records:
                batch = []
                for rec in records:
                    row = []
                    for c in col_names:
                        val = rec.get(c)
                        if isinstance(val, (list, dict)):
                            val = json.dumps(val, ensure_ascii=False)
                        row.append(val)
                    batch.append(tuple(row))

                    if len(batch) >= BATCH_SIZE:
                        conn.executemany(
                            f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                            batch,
                        )
                        batch.clear()

                if batch:
                    conn.executemany(
                        f"INSERT OR REPLACE INTO [{table_name}] ({col_list}) VALUES ({placeholders})",
                        batch,
                    )

                site_record_count += len(records)

            # Check for special ingestors (XML, compressed archives, etc.)
            special_key = (site_name, coll_name)
            if special_key in _SPECIAL_INGESTORS:
                raw_count = _SPECIAL_INGESTORS[special_key](
                    conn, table_name, col_names, col_list, placeholders, _max_raw,
                )
                site_record_count += raw_count
            else:
                # Stream raw data directly into the table (avoids OOM)
                raw_match = [(p, f, c) for p, f, c in raw_sources_for_site if c == coll_name]
                for raw_path, fmt, _ in raw_match:
                    raw_count = _stream_raw_into_table(
                        conn, raw_path, fmt, table_name, col_names,
                        col_list, placeholders, _max_raw,
                    )
                    site_record_count += raw_count

            site_table_count += 1
            total_tables += 1

        conn.commit()
        if site_table_count > 0:
            _progress(f"{site_name}: {site_table_count} tables, {site_record_count:,} records")
        total_records += site_record_count

    print(f"  Total: {total_tables} tables, {total_records:,} records")


def build_fts_indexes(db_path):
    """Build FTS5 indexes via standalone script."""
    from scripts.build_fts import build_fts_indexes as _build_fts
    _build_fts(db_path, force=_force)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--force", action="store_true",
                        help="Re-index even if data already exists in DB")
    parser.add_argument("--max-raw", type=int, default=MAX_RAW_RECORDS,
                        help=f"Max records per raw_data collection (default: {MAX_RAW_RECORDS:,})")
    parser.add_argument("--db", type=str, default=DB_PATH,
                        help=f"Output database path (default: {DB_PATH})")
    # Legacy aliases kept for backward compat
    parser.add_argument("--sites-only", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()

    global _max_raw, _force
    _max_raw = args.max_raw
    _force = args.force

    db_path = args.db
    print(f"Building {db_path}")
    print(f"Data sources: {DATA_SOURCES}")
    print(f"Max raw records per collection: {_max_raw:,}")

    conn = sqlite3.connect(db_path, timeout=60)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-256000")  # 256 MB cache for bulk insert

    from app.db import _INFRA_SCHEMA
    conn.executescript(_INFRA_SCHEMA)
    conn.commit()

    t0 = time.time()
    build_site_tables(conn)
    conn.close()
    build_fts_indexes(db_path)
    conn = sqlite3.connect(db_path, timeout=60)

    elapsed = time.time() - t0
    print(f"\n=== DONE in {elapsed:.0f}s ===")

    try:
        count = conn.execute("SELECT COUNT(*) FROM site_registry").fetchone()[0]
        print(f"  site_registry: {count:,} rows")
    except (sqlite3.OperationalError, sqlite3.DatabaseError):
        pass

    db_size = os.path.getsize(db_path)
    print(f"  DB size: {db_size / 1024 / 1024 / 1024:.2f} GB")

    conn.close()


if __name__ == "__main__":
    main()
