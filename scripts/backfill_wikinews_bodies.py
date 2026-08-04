#!/usr/bin/env python
"""Backfill real WikiNews article bodies + dates into the news site — OFFLINE.

The trimmed DB kept ~20k WikiNews articles as title-only stubs (empty body/date,
category=''). This streams the LOCAL enwikinews bz2 XML dump (no network),
matches pages to those stubs by pageid, cleans the wikitext to plain text,
extracts the real publish date, and updates the rows in place — categorising the
successfully-filled ones as 'world' so they surface as the International section.

Idempotent (re-running recomputes the same values) and deterministic. Never runs
build_db.py; only UPDATEs existing news_articles rows (by id) + the world
category row. Reads data/enwikinews/...-pages-articles1.xml-p1p1500000.bz2.
"""
import bz2
import datetime
import json
import re
import sqlite3
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = str(ROOT / "data" / "trimmed_miniweb.db")
DUMP = ROOT / "data" / "enwikinews" / "enwikinews-20260501-pages-articles1.xml-p1p1500000.bz2"

MIN_WORDS = 40
BATCH = 2000

_DATE_RE = re.compile(r"\{\{\s*date\s*\|\s*([^}|]+?)\s*\}\}", re.I)
_BYLINE_DATE_RE = re.compile(r"\{\{\s*byline[^}]*?\bdate\s*=\s*([^|}]+?)\s*[|}]", re.I)
_CAT_DATE_RE = re.compile(r"\[\[Category:\s*([A-Z][a-z]+ \d{1,2}, \d{4})\s*\]\]")


def parse_date(wikitext):
    """Return YYYY-MM-DD from a {{date|...}}, {{byline|date=...}} or dated
    category, or None."""
    for rx in (_DATE_RE, _BYLINE_DATE_RE, _CAT_DATE_RE):
        m = rx.search(wikitext)
        if m:
            raw = m.group(1).strip()
            for fmt in ("%B %d, %Y", "%b %d, %Y", "%d %B %Y", "%B %d %Y"):
                try:
                    return datetime.datetime.strptime(raw, fmt).strftime("%Y-%m-%d")
                except ValueError:
                    continue
    return None


def _strip_templates(text):
    """Remove {{...}} templates, innermost first (handles simple nesting)."""
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\{[^{}]*\}\}", "", text)
    return text


def _strip_tables(text):
    prev = None
    while prev != text:
        prev = text
        text = re.sub(r"\{\|.*?\|\}", "", text, flags=re.S)
    return text


def clean_wikitext(text):
    # Cut trailing apparatus sections (Sources / Related news / References / etc.)
    text = re.split(
        r"\n=+\s*(?:Sources?|Related news|External links?|See also|References)\s*=+",
        text, maxsplit=1, flags=re.I)[0]
    text = re.sub(r"<!--.*?-->", "", text, flags=re.S)          # comments
    text = re.sub(r"<ref[^>]*?/>", "", text, flags=re.I)         # self-closing refs
    text = re.sub(r"<ref[^>]*?>.*?</ref>", "", text, flags=re.S | re.I)
    # {{w|Target|Display}} -> Display ; {{w|Target}} -> Target  (interwiki shortcuts)
    text = re.sub(r"\{\{\s*w\s*\|[^|}]*\|([^}]+)\}\}", r"\1", text, flags=re.I)
    text = re.sub(r"\{\{\s*w\s*\|([^}]+)\}\}", r"\1", text, flags=re.I)
    text = _strip_tables(text)
    text = _strip_templates(text)
    # media / category links (drop entirely)
    text = re.sub(r"\[\[(?:File|Image|Category):[^\[\]]*\]\]", "", text, flags=re.I)
    # wiki links -> display text
    text = re.sub(r"\[\[[^|\]]*\|([^\]]+)\]\]", r"\1", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    # external links -> label
    text = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", text)
    text = re.sub(r"\[https?://\S+\]", "", text)
    text = text.replace("'''", "").replace("''", "")            # bold/italic
    text = re.sub(r"</?[a-zA-Z][^>]*>", "", text)                # stray html tags
    text = text.replace("[[", "").replace("]]", "").replace("{{", "").replace("}}", "")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def main():
    if not DUMP.exists():
        raise SystemExit(f"dump not found: {DUMP}")
    conn = sqlite3.connect(DB, timeout=60)

    stub_ids = {r[0] for r in conn.execute(
        "SELECT id FROM news_articles WHERE category='' ")}
    print(f"{len(stub_ids):,} title-stub articles to try to fill")

    updates = []
    filled = 0
    scanned = 0
    with bz2.open(DUMP, "rb") as f:
        ctx = ET.iterparse(f, events=("end",))
        ns = ""
        for _ev, elem in ctx:
            if not ns and "}" in elem.tag:
                ns = elem.tag.split("}")[0] + "}"
            if elem.tag != f"{ns}page":
                continue
            nse = elem.find(f"{ns}ns")
            ide = elem.find(f"{ns}id")
            if nse is None or nse.text != "0" or ide is None:
                elem.clear(); continue
            pid = int(ide.text)
            if pid not in stub_ids:
                elem.clear(); continue
            scanned += 1
            title_e = elem.find(f"{ns}title")
            rev = elem.find(f"{ns}revision")
            text_e = rev.find(f"{ns}text") if rev is not None else None
            raw = (text_e.text or "") if text_e is not None else ""
            elem.clear()
            if not raw or raw.startswith("#REDIRECT") or len(raw) < 200:
                continue
            date = parse_date(raw)
            if not date:                      # real published stories carry a date
                continue
            title = title_e.text or ""
            body = clean_wikitext(raw)
            wc = len(body.split())
            if wc < MIN_WORDS:
                continue
            url = "https://en.wikinews.org/wiki/" + title.replace(" ", "_")
            body = body + "\n\nSource: " + url
            updates.append((body, date, "Wikinews contributors", "Wikinews",
                            json.dumps(["world"]), wc, pid))
            filled += 1
            if len(updates) >= BATCH:
                conn.executemany(
                    "UPDATE news_articles SET body=?, date=?, author=?, source=?, "
                    "tags=?, word_count=?, category='world' WHERE id=?", updates)
                conn.commit(); updates.clear()
                print(f"  scanned {scanned:,} stubs, filled {filled:,}")
    if updates:
        conn.executemany(
            "UPDATE news_articles SET body=?, date=?, author=?, source=?, "
            "tags=?, word_count=?, category='world' WHERE id=?", updates)
        conn.commit()

    # Ensure the World News category exists + set its count.
    n_world = conn.execute(
        "SELECT COUNT(*) FROM news_articles WHERE category='world'").fetchone()[0]
    row = conn.execute("SELECT id FROM news_categories WHERE slug='world'").fetchone()
    if row:
        conn.execute("UPDATE news_categories SET article_count=? WHERE slug='world'",
                     (n_world,))
    else:
        nid = (conn.execute("SELECT MAX(id) FROM news_categories").fetchone()[0] or 0) + 1
        conn.execute(
            "INSERT INTO news_categories (id, slug, name, description, color, article_count) "
            "VALUES (?,?,?,?,?,?)",
            (nid, "world", "World News",
             "International and world news from Wikinews.", "#0E7490", n_world))
    conn.commit()

    dr = conn.execute(
        "SELECT MIN(date), MAX(date) FROM news_articles WHERE category='world'").fetchone()
    print(f"\nDONE: {n_world:,} world articles (date range {dr[0]} .. {dr[1]})")
    conn.close()


if __name__ == "__main__":
    main()
