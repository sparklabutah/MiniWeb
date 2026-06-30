"""Dictionaries & Language Tools -- Merriam-Webster / Dictionary.com style dictionary.

Data is stored in SQLite: wiktionary entries in the raw_data table, users in a
per-site typed table.  Queried through app.db.
"""
import math
import pathlib
import random
import re
from collections import Counter
from datetime import date

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for
from app import db

SITE = "dictionaries-language-tools"
SITE_DIR = pathlib.Path(__file__).resolve().parent

# Use db's row deserializer to auto-parse JSON columns (senses, head_templates, etc.)
from app.db import _deserialize_row

blueprint = Blueprint(
    "dictionaries-language-tools",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Data interpreter -- reads raw JSONL, never modifies it
# ---------------------------------------------------------------------------

def _g(raw, key, default=None):
    """Get a value from a dict, coalescing None to the default.

    SQLite NULL columns come back as None even with dict.get(key, default),
    because the key exists with value None.
    """
    val = raw.get(key, default)
    return val if val is not None else default


def _extract_ipa(raw):
    """Extract IPA pronunciation strings from the sounds field."""
    sounds = _g(raw, "sounds", [])
    if not sounds:
        return []
    ipas = []
    for s in sounds:
        if isinstance(s, dict):
            ipa = s.get("ipa")
            if ipa:
                ipas.append(ipa)
    return ipas


def _extract_definitions(raw):
    """Extract numbered definitions with examples from senses."""
    senses = raw.get("senses", [])
    definitions = []
    for sense in senses:
        glosses = sense.get("glosses", [])
        if not glosses:
            continue
        gloss = glosses[0] if isinstance(glosses, list) else str(glosses)
        # Skip form-of entries that are just inflections
        tags = sense.get("tags", [])

        examples = []
        for ex in sense.get("examples", []):
            if isinstance(ex, dict):
                text = ex.get("text", "")
                if text:
                    examples.append(text)
            elif isinstance(ex, str):
                examples.append(ex)

        synonyms_in_sense = []
        for syn in sense.get("synonyms", []):
            if isinstance(syn, dict):
                w = syn.get("word", "")
                if w:
                    synonyms_in_sense.append(w)

        definitions.append({
            "gloss": gloss,
            "examples": examples[:3],
            "tags": tags,
            "synonyms": synonyms_in_sense,
        })
    return definitions


def _extract_synonyms(raw):
    """Collect all synonyms from the entry."""
    syns = set()
    for syn in raw.get("synonyms", []):
        if isinstance(syn, dict):
            w = syn.get("word", "")
            if w:
                syns.add(w)
    # Also collect from senses
    for sense in raw.get("senses", []):
        for syn in sense.get("synonyms", []):
            if isinstance(syn, dict):
                w = syn.get("word", "")
                if w:
                    syns.add(w)
    return sorted(syns)


def _extract_antonyms(raw):
    """Collect all antonyms from the entry."""
    ants = set()
    for ant in raw.get("antonyms", []):
        if isinstance(ant, dict):
            w = ant.get("word", "")
            if w:
                ants.add(w)
    return sorted(ants)


def _extract_related(raw):
    """Collect related words from related, derived, hypernyms, hyponyms."""
    related = set()
    for field in ("related", "derived", "hypernyms", "hyponyms"):
        for item in raw.get(field, []):
            if isinstance(item, dict):
                w = item.get("word", "")
                if w:
                    related.add(w)
    # Also from senses
    for sense in raw.get("senses", []):
        for field in ("hypernyms", "hyponyms", "coordinate_terms"):
            for item in sense.get(field, []):
                if isinstance(item, dict):
                    w = item.get("word", "")
                    if w:
                        related.add(w)
    return sorted(related)


def _format_pos(pos_code):
    """Convert short POS codes to human-readable labels."""
    pos_map = {
        "noun": "noun",
        "verb": "verb",
        "adj": "adjective",
        "adv": "adverb",
        "name": "proper noun",
        "proverb": "proverb",
        "prefix": "prefix",
        "contraction": "contraction",
        "phrase": "phrase",
        "prep_phrase": "prepositional phrase",
        "intj": "interjection",
    }
    return pos_map.get(pos_code, pos_code)


def _interpret_entry(raw, idx):
    """Interpret a raw JSONL record into a normalized dictionary entry."""
    # Coalesce NULL values from SQLite — .get("key", []) returns None
    # when the key exists with value None, so fix them here.
    for k, v in list(raw.items()):
        if v is None:
            raw[k] = [] if k in ("senses", "head_templates", "sounds",
                                  "synonyms", "antonyms", "related", "derived",
                                  "hypernyms", "hyponyms", "forms",
                                  "hyphenations", "categories") else ""
    word = raw.get("word", "").strip()
    pos_code = raw.get("pos", "")
    pos = _format_pos(pos_code)
    lang = raw.get("lang", "English")

    ipas = _extract_ipa(raw)
    definitions = _extract_definitions(raw)
    synonyms = _extract_synonyms(raw)
    antonyms = _extract_antonyms(raw)
    related = _extract_related(raw)
    etymology = raw.get("etymology_text", "")
    if etymology:
        etymology = re.sub(r'\s+', ' ', etymology.replace("\n", " ")).strip()

    hyphenations = raw.get("hyphenations", [])
    categories = raw.get("categories", [])

    # Forms (e.g. plural, past tense)
    forms = []
    for form in raw.get("forms", []):
        if isinstance(form, dict):
            f_word = form.get("form", "")
            f_tags = form.get("tags", [])
            if f_word and f_word != word:
                forms.append({"form": f_word, "tags": f_tags})

    return {
        "id": idx,
        "word": word,
        "word_lower": word.lower(),
        "pos": pos,
        "pos_code": pos_code,
        "lang": lang,
        "ipa": ipas,
        "definitions": definitions,
        "num_definitions": len(definitions),
        "synonyms": synonyms,
        "antonyms": antonyms,
        "related": related,
        "etymology": etymology,
        "hyphenations": hyphenations,
        "categories": categories,
        "forms": forms,
        "first_letter": word[0].upper() if word and word[0].isalpha() else "#",
    }


# ---------------------------------------------------------------------------
# DB-backed data access — queries dictionaries_language_tools_entries directly
# ---------------------------------------------------------------------------

_TABLE = "dictionaries_language_tools_entries"


def _db_conn():
    return db.get_conn()

def _db_search_words(query, pos=None, letter=None, limit=50, offset=0):
    """Search entries with filters on real columns."""
    conn = _db_conn()
    q = query.lower().strip() if query else ""
    clauses = []
    params = []

    if q:
        clauses.append("LOWER(word) LIKE ?")
        params.append(f"%{q}%")
    if pos:
        clauses.append("pos = ?")
        params.append(pos)
    if letter:
        clauses.append("UPPER(SUBSTR(word, 1, 1)) = ?")
        params.append(letter.upper())

    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = f"SELECT rowid, * FROM [{_TABLE}]{where} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(sql, params).fetchall()
    return [_interpret_entry(_deserialize_row(r), offset + i + 1) for i, r in enumerate(rows)]


def _db_search_words_scored(query, limit=50, offset=0):
    """Search with relevance scoring: exact > prefix > contains."""
    conn = _db_conn()
    q = query.lower().strip()
    if not q:
        return []

    results = []
    seen = set()

    # 1. Exact match (score 100)
    for r in conn.execute(f"SELECT rowid, * FROM [{_TABLE}] WHERE LOWER(word) = ? LIMIT ?", (q, limit)).fetchall():
        key = r["rowid"]
        if key not in seen:
            seen.add(key)
            results.append((_interpret_entry(_deserialize_row(r), len(results) + 1), 100))

    remaining = limit - len(results)
    if remaining <= 0:
        return [e for e, _ in results]

    # 2. Prefix match (score 50)
    for r in conn.execute(f"SELECT rowid, * FROM [{_TABLE}] WHERE LOWER(word) LIKE ? AND LOWER(word) != ? LIMIT ?", (f"{q}%", q, remaining)).fetchall():
        key = r["rowid"]
        if key not in seen:
            seen.add(key)
            results.append((_interpret_entry(_deserialize_row(r), len(results) + 1), 50))

    remaining = limit - len(results)
    if remaining <= 0:
        results.sort(key=lambda x: (-x[1], x[0]["word_lower"]))
        return [e for e, _ in results]

    # 3. Contains match (score 20)
    for r in conn.execute(f"SELECT rowid, * FROM [{_TABLE}] WHERE LOWER(word) LIKE ? AND LOWER(word) NOT LIKE ? LIMIT ?", (f"%{q}%", f"{q}%", remaining)).fetchall():
        key = r["rowid"]
        if key not in seen:
            seen.add(key)
            results.append((_interpret_entry(_deserialize_row(r), len(results) + 1), 20))

    results.sort(key=lambda x: (-x[1], x[0]["word_lower"]))
    return [e for e, _ in results]


def _db_count_search(query="", pos=None, letter=None):
    """Count matching entries."""
    conn = _db_conn()
    clauses = []
    params = []
    if query:
        clauses.append("LOWER(word) LIKE ?")
        params.append(f"%{query.lower().strip()}%")
    if pos:
        clauses.append("pos = ?")
        params.append(pos)
    if letter:
        clauses.append("UPPER(SUBSTR(word, 1, 1)) = ?")
        params.append(letter.upper())
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    return conn.execute(f"SELECT COUNT(*) FROM [{_TABLE}]{where}", params).fetchone()[0]


def _db_get_word(word_text):
    """Look up entries for a word (case-insensitive)."""
    conn = _db_conn()
    rows = conn.execute(f"SELECT rowid, * FROM [{_TABLE}] WHERE LOWER(word) = ?", (word_text.lower(),)).fetchall()
    if not rows:
        rows = conn.execute(f"SELECT rowid, * FROM [{_TABLE}] WHERE LOWER(word) LIKE ? LIMIT 10", (f"{word_text.lower()}%",)).fetchall()
    return [_interpret_entry(_deserialize_row(r), i + 1) for i, r in enumerate(rows)]


def _db_browse_by_letter(letter, limit=50, offset=0):
    """Browse entries starting with a given letter."""
    conn = _db_conn()
    rows = conn.execute(
        f"SELECT rowid, * FROM [{_TABLE}] WHERE UPPER(SUBSTR(word, 1, 1)) = ? ORDER BY LOWER(word) LIMIT ? OFFSET ?",
        (letter.upper(), limit, offset),
    ).fetchall()
    return [_interpret_entry(_deserialize_row(r), offset + i + 1) for i, r in enumerate(rows)]


_letters_cache = None

def _db_get_letters():
    global _letters_cache
    if _letters_cache is not None:
        return _letters_cache
    _letters_cache = [chr(c) for c in range(ord('A'), ord('Z') + 1)]
    return _letters_cache


_total_entries_cache = None

def _db_total_entries():
    global _total_entries_cache
    if _total_entries_cache is None:
        conn = _db_conn()
        _total_entries_cache = conn.execute(f"SELECT COUNT(*) FROM [{_TABLE}]").fetchone()[0]
    return _total_entries_cache

_min_rowid_cache = None

def _db_min_rowid():
    global _min_rowid_cache
    if _min_rowid_cache is not None:
        return _min_rowid_cache
    conn = _db_conn()
    _min_rowid_cache = conn.execute(f"SELECT MIN(rowid) FROM [{_TABLE}]").fetchone()[0] or 0
    return _min_rowid_cache



_wotd_cache = None
_wotd_cache_date = None

def _db_word_of_the_day():
    """Pick a word of the day from DB deterministically. Cached per day."""
    global _wotd_cache, _wotd_cache_date
    today = date.today()
    if _wotd_cache is not None and _wotd_cache_date == today:
        return _wotd_cache
    seed = 42
    day_of_year = today.timetuple().tm_yday
    year = today.year

    rng = random.Random(seed + year * 1000 + day_of_year)
    conn = _db_conn()
    total = _db_total_entries()
    if total == 0:
        return None
    pick = rng.randint(0, total - 1)
    # Use rowid for O(1) lookup instead of slow OFFSET scan on millions of rows
    min_rowid = _db_min_rowid()
    row = conn.execute(
        f"SELECT rowid, * FROM [{_TABLE}] WHERE rowid >= ? LIMIT 1",
        (min_rowid + pick,),
    ).fetchone()
    if not row:
        return None
    _wotd_cache = _interpret_entry(_deserialize_row(row), pick + 1)
    _wotd_cache_date = today
    return _wotd_cache


def _db_random_word(extra_seed=0):
    """Return a random word entry from DB."""
    rng = random.Random(42 + extra_seed)
    conn = _db_conn()
    total = _db_total_entries()
    if total == 0:
        return None
    pick = rng.randint(0, total - 1)
    min_rowid = _db_min_rowid()
    row = conn.execute(
        f"SELECT rowid, * FROM [{_TABLE}] WHERE rowid >= ? LIMIT 1",
        (min_rowid + pick,),
    ).fetchone()
    if not row:
        return None
    return _interpret_entry(_deserialize_row(row), pick + 1)


def _db_compute_stats():
    """Compute aggregate statistics from DB (sampled for performance)."""
    conn = _db_conn()
    total = _db_total_entries()
    sample_limit = min(total, 10000)
    rows = conn.execute(f"SELECT rowid, * FROM [{_TABLE}] LIMIT ?", (sample_limit,)).fetchall()

    pos_counts = Counter()
    letter_counts = Counter()
    with_ipa = 0
    with_etymology = 0
    with_synonyms = 0
    total_defs = 0

    for row in rows:
        entry = _interpret_entry(_deserialize_row(row), 0)
        pos_counts[entry["pos"]] += 1
        letter_counts[entry["first_letter"]] += 1
        if entry["ipa"]:
            with_ipa += 1
        if entry["etymology"]:
            with_etymology += 1
        if entry["synonyms"]:
            with_synonyms += 1
        total_defs += entry["num_definitions"]

    avg_defs = round(total_defs / sample_limit, 2) if sample_limit > 0 else 0
    scale = total / sample_limit if sample_limit > 0 else 1
    return {
        "total_words": total,
        "total_definitions": int(total_defs * scale),
        "avg_definitions_per_word": avg_defs,
        "words_with_pronunciation": int(with_ipa * scale),
        "words_with_etymology": int(with_etymology * scale),
        "words_with_synonyms": int(with_synonyms * scale),
        "pos_distribution": {k: int(v * scale) for k, v in pos_counts.most_common()},
        "letter_distribution": {k: int(letter_counts[k] * scale) for k in sorted(letter_counts.keys())},
        "unique_letters": len(letter_counts),
    }


def _db_check_word_exists(word_text):
    """Check if a word exists in DB."""
    conn = _db_conn()
    row = conn.execute(
        f"SELECT COUNT(*) FROM [{_TABLE}] WHERE LOWER(word) = ?",
        (word_text.lower(),),
    ).fetchone()
    return row[0] > 0




# ---------------------------------------------------------------------------
# Word-of-the-day -- deterministic based on day of year + seed
# ---------------------------------------------------------------------------

def _word_of_the_day(entries=None):
    """Pick a word of the day deterministically."""
    return _db_word_of_the_day()


# ---------------------------------------------------------------------------
# Users (mutable state -- stored in per-site SQLite table)
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")


def _save_users(users):
    db.save_collection(SITE, "users", users)


def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)


# ---------------------------------------------------------------------------
# Search helpers (file-based fallback)
# ---------------------------------------------------------------------------

def _search_words(entries, query):
    """Search entries by word, definitions, and etymology."""
    if not query:
        return entries
    q = query.lower().strip()
    scored = []
    for e in entries:
        score = 0
        # Exact match on word
        if e["word_lower"] == q:
            score += 100
        # Starts with query
        elif e["word_lower"].startswith(q):
            score += 50
        # Contains query in word
        elif q in e["word_lower"]:
            score += 20
        # Check definitions
        for d in e["definitions"]:
            if q in d["gloss"].lower():
                score += 5
        # Check etymology
        if q in e.get("etymology", "").lower():
            score += 2
        # Check synonyms
        for s in e.get("synonyms", []):
            if q in s.lower():
                score += 3
        if score > 0:
            scored.append((e, score))
    scored.sort(key=lambda x: (-x[1], x[0]["word_lower"]))
    return [e for e, _ in scored]


def _browse_by_letter(entries, letter):
    """Filter entries by first letter."""
    letter = letter.upper()
    return [e for e in entries if e["first_letter"] == letter]


# ---------------------------------------------------------------------------
# Statistics helpers (file-based fallback)
# ---------------------------------------------------------------------------

def _compute_stats(entries):
    """Compute aggregate statistics about the dictionary."""
    total = len(entries)
    pos_counts = Counter(e["pos"] for e in entries)
    letter_counts = Counter(e["first_letter"] for e in entries)
    with_ipa = sum(1 for e in entries if e["ipa"])
    with_etymology = sum(1 for e in entries if e["etymology"])
    with_synonyms = sum(1 for e in entries if e["synonyms"])
    total_defs = sum(e["num_definitions"] for e in entries)
    avg_defs = round(total_defs / total, 2) if total > 0 else 0

    return {
        "total_words": total,
        "total_definitions": total_defs,
        "avg_definitions_per_word": avg_defs,
        "words_with_pronunciation": with_ipa,
        "words_with_etymology": with_etymology,
        "words_with_synonyms": with_synonyms,
        "pos_distribution": dict(pos_counts.most_common()),
        "letter_distribution": {k: letter_counts[k] for k in sorted(letter_counts.keys())},
        "unique_letters": len(letter_counts),
    }


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    q = request.args.get("q", "").strip()

    wotd = _db_word_of_the_day()
    letters = _db_get_letters()

    results = None
    total_results = 0
    page = 1
    total_pages = 1
    if q:
        PER_PAGE = 20
        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1
        total_results = _db_count_search(query=q)
        total_pages = max(1, math.ceil(total_results / PER_PAGE))
        if page > total_pages:
            page = total_pages
        offset = (page - 1) * PER_PAGE
        results = _db_search_words_scored(q, limit=PER_PAGE, offset=0)
        if page > 1 or len(results) == 0:
            results = _db_search_words(q, limit=PER_PAGE, offset=offset)

    return render_template("dictionaries-language-tools/index.html",
                           q=q, results=results, wotd=wotd,
                           letters=letters, user=user,
                           total_results=total_results, page=page,
                           total_pages=total_pages)


@blueprint.route("/word/<path:word_text>")
def word_detail(word_text):
    matches = _db_get_word(word_text)

    if not matches:
        abort(404)

    entry = matches[0]
    all_entries = matches

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    # Check if word is saved
    is_saved = False
    if user:
        is_saved = word_text.lower() in [w.lower() for w in user.get("saved_words", [])]

    # Find cross-references: words that appear in related/synonyms that exist in our dictionary
    linked_synonyms = [s for s in entry["synonyms"] if _db_check_word_exists(s)]
    linked_related = [r for r in entry["related"] if _db_check_word_exists(r)]

    return render_template("dictionaries-language-tools/word.html",
                           entry=entry, all_entries=all_entries,
                           user=user, is_saved=is_saved,
                           linked_synonyms=linked_synonyms,
                           linked_related=linked_related)


@blueprint.route("/browse/<letter>")
def browse(letter):
    letter = letter.upper()
    if not letter.isalpha() or len(letter) != 1:
        abort(404)

    PER_PAGE = 20
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1

    total = _db_count_search(letter=letter)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    if page > total_pages:
        page = total_pages
    offset = (page - 1) * PER_PAGE
    words = _db_browse_by_letter(letter, limit=PER_PAGE, offset=offset)
    letters = _db_get_letters()

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("dictionaries-language-tools/browse.html",
                           letter=letter, words=words, letters=letters, user=user,
                           page=page, total_pages=total_pages, total_words=total)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("dictionaries-language-tools/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("dictionaries-language-tools/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("dictionaries-language-tools.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("dictionaries-language-tools.index"))


@blueprint.route("/dashboard")
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("dictionaries-language-tools.login_page"))
    user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("dictionaries-language-tools.login_page"))

    # Resolve saved words to full entries
    saved_entries = []
    for w in user.get("saved_words", []):
        matches = _db_get_word(w)
        if matches:
            saved_entries.append(matches[0])

    # Resolve vocabulary list words
    vocab_lists = []
    for vl in user.get("vocabulary_lists", []):
        resolved = []
        for w in vl.get("words", []):
            matches = _db_get_word(w)
            if matches:
                resolved.append(matches[0])
        vocab_lists.append({
            "name": vl["name"],
            "words": resolved,
            "count": len(vl.get("words", [])),
        })

    return render_template("dictionaries-language-tools/dashboard.html",
                           user=user, saved_entries=saved_entries,
                           vocab_lists=vocab_lists)


@blueprint.route("/word/<path:word_text>/save", methods=["POST"])
def form_save_word(word_text):
    """Toggle saving a word to user's saved list (form-based)."""
    if "user_id" not in session:
        return redirect(url_for("dictionaries-language-tools.login_page"))
    users = _load_users()
    user = next((u for u in users if u["id"] == session["user_id"]), None)
    if not user:
        return redirect(url_for("dictionaries-language-tools.login_page"))

    saved = user.setdefault("saved_words", [])
    existing = [w for w in saved if w.lower() == word_text.lower()]
    if existing:
        for w in existing:
            saved.remove(w)
    else:
        saved.append(word_text)
    _save_users(users)
    return redirect(url_for("dictionaries-language-tools.word_detail", word_text=word_text))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/words")
def api_words():
    """Search words. Query params: q, pos, letter, limit, page, per_page."""
    q = request.args.get("q", "").strip()
    pos = request.args.get("pos", "").strip()
    letter = request.args.get("letter", "").strip().upper()
    limit = request.args.get("limit", type=int)

    effective_limit = limit if limit else 50
    results = _db_search_words(q if q else None, pos=pos if pos else None,
                               letter=letter if letter else None,
                               limit=effective_limit)
    out = []
    for e in results:
        out.append({
            "id": e["id"],
            "word": e["word"],
            "pos": e["pos"],
            "pos_code": e["pos_code"],
            "num_definitions": e["num_definitions"],
            "first_letter": e["first_letter"],
            "has_pronunciation": len(e["ipa"]) > 0,
            "has_etymology": len(e["etymology"]) > 0,
        })
    return jsonify(out)


@blueprint.route("/api/words/<path:word_text>")
def api_word(word_text):
    """Get full details for a word."""
    matches = _db_get_word(word_text)
    if not matches:
        return jsonify({"error": "Word not found"}), 404
    # Return all matching entries (could be multiple POS)
    if len(matches) == 1:
        return jsonify(matches[0])
    return jsonify(matches)


@blueprint.route("/api/words/<path:word_text>/synonyms")
def api_word_synonyms(word_text):
    """Get synonyms for a specific word."""
    matches = _db_get_word(word_text)
    if not matches:
        return jsonify({"error": "Word not found"}), 404
    entry = matches[0]
    return jsonify({
        "word": entry["word"],
        "synonyms": entry["synonyms"],
        "antonyms": entry["antonyms"],
    })


@blueprint.route("/api/words/random")
def api_random_word():
    """Return a random word entry."""
    timestamp_str = request.args.get("seed", "0")
    try:
        extra_seed = int(timestamp_str)
    except ValueError:
        extra_seed = 0

    entry = _db_random_word(extra_seed)
    if entry is None:
        return jsonify({"error": "No entries available"}), 404
    return jsonify(entry)


@blueprint.route("/api/word-of-the-day")
def api_word_of_the_day():
    """Return the word of the day."""
    wotd = _word_of_the_day()
    return jsonify(wotd)


@blueprint.route("/api/browse/<letter>")
def api_browse(letter):
    """Browse words by starting letter."""
    letter = letter.upper()
    if not letter.isalpha() or len(letter) != 1:
        return jsonify({"error": "Invalid letter"}), 400

    words = _db_browse_by_letter(letter, limit=50)
    out = []
    for e in words:
        out.append({
            "id": e["id"],
            "word": e["word"],
            "pos": e["pos"],
            "num_definitions": e["num_definitions"],
            "first_definition": e["definitions"][0]["gloss"] if e["definitions"] else "",
        })
    return jsonify(out)


@blueprint.route("/api/stats")
def api_stats():
    """Return dictionary statistics."""
    stats = _db_compute_stats()
    return jsonify(stats)


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    """Get user profile (sans password)."""
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "User not found"}), 404
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_save_word(user_id):
    """Toggle saving a word for a user."""
    data = request.get_json(silent=True) or {}
    word = data.get("word", "").strip()
    if not word:
        return jsonify({"error": "word required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    saved = user.setdefault("saved_words", [])
    existing = [w for w in saved if w.lower() == word.lower()]
    if existing:
        for w in existing:
            saved.remove(w)
        action = "removed"
    else:
        saved.append(word)
        action = "saved"

    _save_users(users)
    return jsonify({"action": action, "word": word, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/vocab", methods=["POST"])
def api_add_to_vocab(user_id):
    """Add a word to a vocabulary list."""
    data = request.get_json(silent=True) or {}
    word = data.get("word", "").strip()
    list_name = data.get("list_name", "").strip()
    if not word or not list_name:
        return jsonify({"error": "word and list_name required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return jsonify({"error": "User not found"}), 404

    vocab_lists = user.setdefault("vocabulary_lists", [])
    target = next((vl for vl in vocab_lists if vl["name"] == list_name), None)
    if not target:
        target = {"name": list_name, "words": []}
        vocab_lists.append(target)

    words = target.setdefault("words", [])
    if word.lower() in [w.lower() for w in words]:
        words[:] = [w for w in words if w.lower() != word.lower()]
        action = "removed"
    else:
        words.append(word)
        action = "added"

    _save_users(users)
    return jsonify({"action": action, "word": word, "list_name": list_name, "list_size": len(words)})


@blueprint.route("/api/login", methods=["POST"])
def api_login():
    """API login."""
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"], "name": user["name"]})
