"""Dictionaries & Language Tools -- Merriam-Webster / Dictionary.com style dictionary.

Data interpreter: reads the original Wiktionary JSONL snapshot,
loads all entries based on config/config.json, and serves through Flask routes.
The raw data file is never modified.
"""
import json
import math
import pathlib
import random
import re
from collections import Counter, defaultdict
from datetime import date

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
DATA_FILE = SITE_DIR / "data" / "wiktionary_sample.jsonl"
USERS_FILE = SITE_DIR / "data" / "users.json"
CONFIG_FILE = SITE_DIR / "config" / "config.json"

blueprint = Blueprint(
    "dictionaries-language-tools",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Data interpreter -- reads raw JSONL, never modifies it
# ---------------------------------------------------------------------------

def _extract_ipa(raw):
    """Extract IPA pronunciation strings from the sounds field."""
    sounds = raw.get("sounds", [])
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


def _load_words():
    """Read JSONL dataset. num_data_points=-1 loads all records; positive N
    uses reservoir sampling to pick N records."""
    config = _load_config()
    n = config.get("num_data_points", -1)
    seed = config.get("random_seed", 42)
    rng = random.Random(seed)

    if n > 0:
        reservoir = []
        with open(DATA_FILE) as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if len(reservoir) < n:
                    reservoir.append(raw)
                else:
                    j = rng.randint(0, i)
                    if j < n:
                        reservoir[j] = raw
        selected = reservoir
    else:
        selected = []
        with open(DATA_FILE) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    selected.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    entries = []
    for idx, raw in enumerate(selected, 1):
        entries.append(_interpret_entry(raw, idx))

    entries.sort(key=lambda e: e["word_lower"])
    for i, e in enumerate(entries, 1):
        e["id"] = i

    return entries


# ---------------------------------------------------------------------------
# Caching
# ---------------------------------------------------------------------------

_entries = None


def _ensure_loaded():
    global _entries
    if _entries is None:
        _entries = _load_words()


def _get_entries():
    _ensure_loaded()
    return _entries


# ---------------------------------------------------------------------------
# Word-of-the-day — deterministic based on day of year + seed
# ---------------------------------------------------------------------------

def _word_of_the_day(entries=None):
    """Pick a word of the day deterministically from entries with definitions."""
    if entries is None:
        entries = _get_entries()
    config = _load_config()
    seed = config.get("random_seed", 42)
    today = date.today()
    day_of_year = today.timetuple().tm_yday
    year = today.year

    # Filter to entries that have at least one real definition
    candidates = [e for e in entries if e["num_definitions"] > 0 and len(e["word"]) > 2]
    if not candidates:
        candidates = entries

    rng = random.Random(seed + year * 1000 + day_of_year)
    return rng.choice(candidates)


# ---------------------------------------------------------------------------
# Users (mutable state)
# ---------------------------------------------------------------------------

def _load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return []


def _save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


# ---------------------------------------------------------------------------
# Search helpers
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
# Statistics helpers
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
    entries = _get_entries()
    q = request.args.get("q", "").strip()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    wotd = _word_of_the_day(entries)

    results = None
    total_results = 0
    page = 1
    total_pages = 1
    if q:
        all_results = _search_words(entries, q)
        total_results = len(all_results)
        PER_PAGE = 20
        page = request.args.get("page", 1, type=int)
        if page < 1:
            page = 1
        total_pages = max(1, math.ceil(total_results / PER_PAGE))
        if page > total_pages:
            page = total_pages
        start = (page - 1) * PER_PAGE
        results = all_results[start:start + PER_PAGE]

    # Alphabet letters present in the data
    letters = sorted(set(e["first_letter"] for e in entries if e["first_letter"].isalpha()))

    return render_template("dictionaries-language-tools/index.html",
                           q=q, results=results, wotd=wotd,
                           letters=letters, user=user,
                           total_results=total_results, page=page,
                           total_pages=total_pages)


@blueprint.route("/word/<path:word_text>")
def word_detail(word_text):
    entries = _get_entries()
    # Find matching entry (case-insensitive)
    matches = [e for e in entries if e["word_lower"] == word_text.lower()]
    if not matches:
        # Try partial match
        matches = [e for e in entries if e["word_lower"].startswith(word_text.lower())]
    if not matches:
        abort(404)

    # If multiple entries (same word, different POS), show all
    entry = matches[0]
    all_entries = matches  # All POS entries for this word

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    # Check if word is saved
    is_saved = False
    if user:
        is_saved = word_text.lower() in [w.lower() for w in user.get("saved_words", [])]

    # Find cross-references: words that appear in related/synonyms that exist in our dictionary
    word_set = {e["word_lower"] for e in entries}
    linked_synonyms = [s for s in entry["synonyms"] if s.lower() in word_set]
    linked_related = [r for r in entry["related"] if r.lower() in word_set]

    return render_template("dictionaries-language-tools/word.html",
                           entry=entry, all_entries=all_entries,
                           user=user, is_saved=is_saved,
                           linked_synonyms=linked_synonyms,
                           linked_related=linked_related)


@blueprint.route("/browse/<letter>")
def browse(letter):
    entries = _get_entries()
    letter = letter.upper()
    if not letter.isalpha() or len(letter) != 1:
        abort(404)

    all_words = _browse_by_letter(entries, letter)
    letters = sorted(set(e["first_letter"] for e in entries if e["first_letter"].isalpha()))

    # Pagination
    PER_PAGE = 20
    page = request.args.get("page", 1, type=int)
    if page < 1:
        page = 1
    total = len(all_words)
    total_pages = max(1, math.ceil(total / PER_PAGE))
    if page > total_pages:
        page = total_pages
    start = (page - 1) * PER_PAGE
    words = all_words[start:start + PER_PAGE]

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

    entries = _get_entries()
    word_map = {e["word_lower"]: e for e in entries}

    # Resolve saved words to full entries
    saved_entries = []
    for w in user.get("saved_words", []):
        e = word_map.get(w.lower())
        if e:
            saved_entries.append(e)

    # Resolve vocabulary list words
    vocab_lists = []
    for vl in user.get("vocabulary_lists", []):
        resolved = []
        for w in vl.get("words", []):
            e = word_map.get(w.lower())
            if e:
                resolved.append(e)
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
    entries = _get_entries()
    q = request.args.get("q", "").strip()
    pos = request.args.get("pos", "").strip()
    letter = request.args.get("letter", "").strip().upper()
    limit = request.args.get("limit", type=int)

    results = list(entries)
    if q:
        results = _search_words(results, q)
    if pos:
        results = [e for e in results if e["pos_code"] == pos or e["pos"] == pos]
    if letter:
        results = [e for e in results if e["first_letter"] == letter]
    if limit:
        results = results[:limit]

    # Lightweight response: omit full definitions
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
    entries = _get_entries()
    matches = [e for e in entries if e["word_lower"] == word_text.lower()]
    if not matches:
        return jsonify({"error": "Word not found"}), 404
    # Return all matching entries (could be multiple POS)
    if len(matches) == 1:
        return jsonify(matches[0])
    return jsonify(matches)


@blueprint.route("/api/words/<path:word_text>/synonyms")
def api_word_synonyms(word_text):
    """Get synonyms for a specific word."""
    entries = _get_entries()
    matches = [e for e in entries if e["word_lower"] == word_text.lower()]
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
    entries = _get_entries()
    config = _load_config()
    seed = config.get("random_seed", 42)
    # Use a seed + current request to be somewhat varied but reproducible
    timestamp_str = request.args.get("seed", "0")
    try:
        extra_seed = int(timestamp_str)
    except ValueError:
        extra_seed = 0
    rng = random.Random(seed + extra_seed)
    entry = rng.choice(entries)
    return jsonify(entry)


@blueprint.route("/api/word-of-the-day")
def api_word_of_the_day():
    """Return the word of the day."""
    wotd = _word_of_the_day()
    return jsonify(wotd)


@blueprint.route("/api/browse/<letter>")
def api_browse(letter):
    """Browse words by starting letter."""
    entries = _get_entries()
    letter = letter.upper()
    if not letter.isalpha() or len(letter) != 1:
        return jsonify({"error": "Invalid letter"}), 400
    words = _browse_by_letter(entries, letter)
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
    entries = _get_entries()
    stats = _compute_stats(entries)
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
