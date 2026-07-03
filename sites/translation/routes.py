"""LinguaBridge Translator -- translate text using LLM (same as AI chatbot).

Inspired by Google Translate. Uses OpenAI gpt-5.4-nano for actual translation.
"""
import csv
import io
import json
import pathlib
from collections import Counter
from datetime import datetime

from flask import (
    Blueprint, Response, abort, jsonify, redirect, render_template, request,
    session, url_for,
)
from app import db

SITE = "translation"
SITE_DIR = pathlib.Path(__file__).resolve().parent
UPLOADS_DIR = SITE_DIR / "data" / "uploads"

blueprint = Blueprint(
    "translation",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
    static_folder=str(SITE_DIR / "static"),
    static_url_path="/static",
)

# ---------------------------------------------------------------------------
# LLM Translation (same API as AI chatbot)
# ---------------------------------------------------------------------------

_LANG_NAMES = {
    "en": "English", "es": "Spanish", "fr": "French", "de": "German",
    "it": "Italian", "pt": "Portuguese", "ja": "Japanese", "zh": "Chinese",
    "ko": "Korean", "ar": "Arabic", "vi": "Vietnamese",
}


def _get_openai_key():
    """Load API key from .env file or environment (same as AI chatbot)."""
    import os
    env_path = SITE_DIR.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OPENAI_API_KEY", "")


def _translate_text(text, source_lang, target_lang, user_glossary=None):
    """Translate using Groq/Claude LLM."""
    if not text or not text.strip():
        return ""
    if source_lang == target_lang:
        return text

    from app.llm import call_llm

    src_name = _LANG_NAMES.get(source_lang, source_lang)
    tgt_name = _LANG_NAMES.get(target_lang, target_lang)
    system = f"You are a translator. Translate from {src_name} to {tgt_name}. Output ONLY the translation, nothing else."

    result = call_llm(text, system=system, max_tokens=500, temperature=0.3)
    if result:
        return result

    # Last resort
    return f"[{tgt_name}] {text}"


def _detect_language(text):
    """Simple language detection based on common words."""
    text_lower = text.lower()
    scores = {}
    lang_words = {
        "en": ["the", "is", "are", "have", "and", "for", "with", "this", "that", "hello", "good", "thank"],
        "es": ["el", "es", "son", "hola", "donde", "como", "pero", "para", "gracias", "buenos"],
        "fr": ["le", "est", "sont", "bonjour", "merci", "avec", "pour", "dans", "mais", "oui"],
        "de": ["der", "ist", "sind", "hallo", "danke", "bitte", "und", "aber", "nicht", "gut"],
        "it": ["il", "sono", "ciao", "grazie", "buono", "questo", "notte", "giorno", "casa"],
        "pt": ["o", "sao", "ola", "obrigado", "sim", "nao", "bom", "hoje", "agua"],
        "ja": ["konnichiwa", "arigatou", "sayonara", "hai", "watashi", "ohayou"],
        "zh": ["nihao", "xiexie", "zaijian", "shi", "bu", "wo", "ni"],
        "ko": ["annyeonghaseyo", "gamsahamnida", "ne", "aniyo", "annyeong"],
        "ar": ["marhaba", "shukran", "salam", "na'am", "la", "ana"],
    }
    for lang, words in lang_words.items():
        score = sum(1 for w in words if w in text_lower.split())
        if score > 0:
            scores[lang] = score
    if scores:
        detected = max(scores, key=scores.get)
        return detected, scores[detected] / max(len(text.split()), 1)
    return "en", 0.1  # default to English with low confidence


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

def _load_users():
    return db.query(SITE, "users")

def _load_languages():
    return db.query(SITE, "languages")

def _load_history():
    return db.query(SITE, "history")

def _save_history(data):
    db.save_collection(SITE, "history", data)

def _load_saved():
    return db.query(SITE, "saved")

def _save_saved(data):
    db.save_collection(SITE, "saved", data)

def _load_glossaries():
    return db.query(SITE, "glossaries")

def _save_glossaries(data):
    db.save_collection(SITE, "glossaries", data)

def _load_settings():
    rows = db.query(SITE, "settings")
    if rows and isinstance(rows[0], dict):
        return rows[0]
    return {}

def _save_settings(data):
    db.save_collection(SITE, "settings", [data])

def _get_user_settings(user_id):
    settings = _load_settings()
    key = str(user_id)
    if key not in settings:
        settings[key] = {
            "auto_detect": False,
            "formal_mode": False,
            "auto_pronounce": False,
        }
        _save_settings(settings)
    return settings[key]

def _set_user_settings(user_id, updates):
    settings = _load_settings()
    key = str(user_id)
    if key not in settings:
        settings[key] = {
            "auto_detect": False,
            "formal_mode": False,
            "auto_pronounce": False,
        }
    settings[key].update(updates)
    _save_settings(settings)
    return settings[key]

def _get_user(user_id):
    return db.get_item(SITE, "users", user_id)

def _get_current_user():
    if "user_id" in session:
        return _get_user(session["user_id"])
    return None

def _get_browsing_user():
    user = _get_current_user()
    if user:
        return user, True
    return _get_user(1), False


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    user, logged_in = _get_browsing_user()
    languages = _load_languages()
    return render_template("translation/index.html", user=user,
                           languages=languages, logged_in=logged_in)


@blueprint.route("/history")
def history_page():
    user, logged_in = _get_browsing_user()
    history = [h for h in _load_history() if h["user_id"] == user["id"]]
    history.sort(key=lambda h: h["timestamp"], reverse=True)
    q = request.args.get("q", "").strip().lower()
    lang = request.args.get("lang", "").strip()
    if q:
        history = [h for h in history if q in h["source_text"].lower()
                   or q in h["translated_text"].lower()]
    if lang:
        history = [h for h in history if h["source_lang"] == lang
                   or h["target_lang"] == lang]
    languages = _load_languages()
    return render_template("translation/history.html", user=user,
                           history=history, languages=languages,
                           logged_in=logged_in, q=q, lang=lang)


@blueprint.route("/saved")
def saved_page():
    user, logged_in = _get_browsing_user()
    saved = [s for s in _load_saved() if s["user_id"] == user["id"]]
    label = request.args.get("label", "").strip()
    if label:
        saved = [s for s in saved if s.get("label", "") == label]
    labels = sorted(set(s.get("label", "") for s in _load_saved()
                        if s["user_id"] == user["id"] and s.get("label")))
    languages = _load_languages()
    return render_template("translation/saved.html", user=user,
                           saved=saved, labels=labels, languages=languages,
                           logged_in=logged_in, selected_label=label)


@blueprint.route("/glossaries")
def glossaries_page():
    user, logged_in = _get_browsing_user()
    glossaries = [g for g in _load_glossaries() if g["user_id"] == user["id"]]
    languages = _load_languages()
    return render_template("translation/glossaries.html", user=user,
                           glossaries=glossaries, languages=languages,
                           logged_in=logged_in)


@blueprint.route("/glossary/<int:glossary_id>")
def glossary_detail(glossary_id):
    user, logged_in = _get_browsing_user()
    glossaries = _load_glossaries()
    glossary = next((g for g in glossaries if g["id"] == glossary_id), None)
    if not glossary:
        abort(404)
    languages = _load_languages()
    return render_template("translation/glossary_detail.html", user=user,
                           glossary=glossary, languages=languages,
                           logged_in=logged_in)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("translation/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("translation/login.html",
                               error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("translation.index"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return redirect(url_for("translation.index"))


@blueprint.route("/translate", methods=["POST"])
def translate_form():
    """Form-based translation (from the main page)."""
    user, logged_in = _get_browsing_user()
    languages = _load_languages()
    text = request.form.get("text", "").strip()
    source = request.form.get("source_lang", "en").strip()
    target = request.form.get("target_lang", "es").strip()

    if not text:
        return render_template("translation/index.html", user=user,
                               languages=languages, logged_in=logged_in,
                               error="Please enter text to translate")

    # Check for user glossary
    glossary = None
    glossaries = _load_glossaries()
    for g in glossaries:
        if (g["user_id"] == user["id"] and
            g.get("source_lang") == source and g.get("target_lang") == target):
            glossary = g
            break

    translated = _translate_text(text, source, target, glossary)

    # Save to history
    history = _load_history()
    new_id = max((h["id"] for h in history), default=0) + 1
    history.append({
        "id": new_id,
        "user_id": user["id"],
        "source_lang": source,
        "target_lang": target,
        "source_text": text,
        "translated_text": translated,
        "timestamp": datetime.now().isoformat(),
    })
    _save_history(history)

    return render_template("translation/index.html", user=user,
                           languages=languages, logged_in=logged_in,
                           source_text=text, translated_text=translated,
                           source_lang=source, target_lang=target)


@blueprint.route("/saved/add", methods=["POST"])
def save_translation_form():
    user = _get_current_user()
    if not user:
        return redirect(url_for("translation.login_page"))
    source_text = request.form.get("source_text", "").strip()
    translated_text = request.form.get("translated_text", "").strip()
    source_lang = request.form.get("source_lang", "").strip()
    target_lang = request.form.get("target_lang", "").strip()
    label = request.form.get("label", "").strip() or "Unlabeled"

    saved = _load_saved()
    new_id = max((s["id"] for s in saved), default=0) + 1
    saved.append({
        "id": new_id,
        "user_id": user["id"],
        "source_lang": source_lang,
        "target_lang": target_lang,
        "source_text": source_text,
        "translated_text": translated_text,
        "label": label,
    })
    _save_saved(saved)
    return redirect(url_for("translation.saved_page"))


@blueprint.route("/saved/<int:saved_id>/delete", methods=["POST"])
def delete_saved_form(saved_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("translation.login_page"))
    saved = _load_saved()
    saved = [s for s in saved if s["id"] != saved_id]
    _save_saved(saved)
    return redirect(url_for("translation.saved_page"))


@blueprint.route("/glossaries/create", methods=["POST"])
def create_glossary_form():
    user = _get_current_user()
    if not user:
        return redirect(url_for("translation.login_page"))
    name = request.form.get("name", "").strip()
    source_lang = request.form.get("source_lang", "").strip()
    target_lang = request.form.get("target_lang", "").strip()
    if not name:
        return redirect(url_for("translation.glossaries_page"))
    glossaries = _load_glossaries()
    new_id = max((g["id"] for g in glossaries), default=0) + 1
    glossaries.append({
        "id": new_id,
        "user_id": user["id"],
        "name": name,
        "source_lang": source_lang,
        "target_lang": target_lang,
        "entries": [],
    })
    _save_glossaries(glossaries)
    return redirect(url_for("translation.glossary_detail", glossary_id=new_id))


@blueprint.route("/glossary/<int:glossary_id>/add-entry", methods=["POST"])
def add_glossary_entry_form(glossary_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("translation.login_page"))
    source = request.form.get("source", "").strip()
    target = request.form.get("target", "").strip()
    if not source or not target:
        return redirect(url_for("translation.glossary_detail", glossary_id=glossary_id))
    glossaries = _load_glossaries()
    glossary = next((g for g in glossaries if g["id"] == glossary_id), None)
    if glossary:
        glossary["entries"].append({"source": source, "target": target})
        _save_glossaries(glossaries)
    return redirect(url_for("translation.glossary_detail", glossary_id=glossary_id))


@blueprint.route("/glossary/<int:glossary_id>/delete", methods=["POST"])
def delete_glossary_form(glossary_id):
    user = _get_current_user()
    if not user:
        return redirect(url_for("translation.login_page"))
    glossaries = _load_glossaries()
    glossaries = [g for g in glossaries if g["id"] != glossary_id]
    _save_glossaries(glossaries)
    return redirect(url_for("translation.glossaries_page"))


# ---------------------------------------------------------------------------
# API routes
# ---------------------------------------------------------------------------

@blueprint.route("/api/translate", methods=["POST"])
def api_translate():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    source = data.get("source", "").strip()
    target = data.get("target", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    if not source or not target:
        return jsonify({"error": "source and target language codes are required"}), 400
    if source == target:
        return jsonify({"error": "source and target must be different"}), 400

    languages = _load_languages()
    valid_codes = {l["code"] for l in languages}
    if source not in valid_codes or target not in valid_codes:
        return jsonify({"error": "Invalid language code"}), 400

    # Check for user glossary
    glossary = None
    user = _get_current_user()
    user_id = user["id"] if user else data.get("user_id", 1)
    glossaries = _load_glossaries()
    for g in glossaries:
        if (g["user_id"] == user_id and
            g.get("source_lang") == source and g.get("target_lang") == target):
            glossary = g
            break

    translated = _translate_text(text, source, target, glossary)

    # Save to history
    history = _load_history()
    new_id = max((h["id"] for h in history), default=0) + 1
    record = {
        "id": new_id,
        "user_id": user_id,
        "source_lang": source,
        "target_lang": target,
        "source_text": text,
        "translated_text": translated,
        "timestamp": datetime.now().isoformat(),
    }
    history.append(record)
    _save_history(history)

    return jsonify({
        "translated_text": translated,
        "source_lang": source,
        "target_lang": target,
        "source_text": text,
        "id": new_id,
    })


@blueprint.route("/api/languages")
def api_languages():
    return jsonify(_load_languages())


@blueprint.route("/api/history", methods=["GET"])
def api_history_list():
    history = _load_history()
    user_id = request.args.get("user_id", type=int)
    source_lang = request.args.get("source_lang", "").strip()
    target_lang = request.args.get("target_lang", "").strip()
    q = request.args.get("q", "").strip().lower()
    limit = request.args.get("limit", type=int)

    if user_id:
        history = [h for h in history if h["user_id"] == user_id]
    if source_lang:
        history = [h for h in history if h["source_lang"] == source_lang]
    if target_lang:
        history = [h for h in history if h["target_lang"] == target_lang]
    if q:
        history = [h for h in history if q in h["source_text"].lower()
                   or q in h["translated_text"].lower()]

    history.sort(key=lambda h: h["timestamp"], reverse=True)
    if limit:
        history = history[:limit]
    return jsonify(history)


@blueprint.route("/api/history", methods=["POST"])
def api_history_create():
    data = request.get_json(silent=True) or {}
    required = ["user_id", "source_lang", "target_lang", "source_text", "translated_text"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    history = _load_history()
    new_id = max((h["id"] for h in history), default=0) + 1
    record = {
        "id": new_id,
        "user_id": data["user_id"],
        "source_lang": data["source_lang"],
        "target_lang": data["target_lang"],
        "source_text": data["source_text"],
        "translated_text": data["translated_text"],
        "timestamp": data.get("timestamp", datetime.now().isoformat()),
    }
    history.append(record)
    _save_history(history)
    return jsonify(record), 201


@blueprint.route("/api/saved", methods=["GET"])
def api_saved_list():
    saved = _load_saved()
    user_id = request.args.get("user_id", type=int)
    label = request.args.get("label", "").strip()
    source_lang = request.args.get("source_lang", "").strip()
    target_lang = request.args.get("target_lang", "").strip()
    if user_id:
        saved = [s for s in saved if s["user_id"] == user_id]
    if label:
        saved = [s for s in saved if s.get("label") == label]
    if source_lang:
        saved = [s for s in saved if s["source_lang"] == source_lang]
    if target_lang:
        saved = [s for s in saved if s["target_lang"] == target_lang]
    return jsonify(saved)


@blueprint.route("/api/saved", methods=["POST"])
def api_saved_create():
    data = request.get_json(silent=True) or {}
    required = ["user_id", "source_lang", "target_lang", "source_text", "translated_text"]
    for field in required:
        if not data.get(field):
            return jsonify({"error": f"{field} is required"}), 400

    saved = _load_saved()
    new_id = max((s["id"] for s in saved), default=0) + 1
    record = {
        "id": new_id,
        "user_id": data["user_id"],
        "source_lang": data["source_lang"],
        "target_lang": data["target_lang"],
        "source_text": data["source_text"],
        "translated_text": data["translated_text"],
        "label": data.get("label", "Unlabeled"),
    }
    saved.append(record)
    _save_saved(saved)
    return jsonify(record), 201


@blueprint.route("/api/saved/<int:saved_id>", methods=["DELETE"])
def api_saved_delete(saved_id):
    saved = _load_saved()
    item = next((s for s in saved if s["id"] == saved_id), None)
    if not item:
        abort(404)
    saved = [s for s in saved if s["id"] != saved_id]
    _save_saved(saved)
    return jsonify({"deleted": saved_id})


@blueprint.route("/api/glossaries", methods=["GET"])
def api_glossaries_list():
    glossaries = _load_glossaries()
    user_id = request.args.get("user_id", type=int)
    if user_id:
        glossaries = [g for g in glossaries if g["user_id"] == user_id]
    return jsonify(glossaries)


@blueprint.route("/api/glossaries", methods=["POST"])
def api_glossaries_create():
    data = request.get_json(silent=True) or {}
    name = data.get("name", "").strip()
    user_id = data.get("user_id")
    if not name or not user_id:
        return jsonify({"error": "name and user_id are required"}), 400

    glossaries = _load_glossaries()
    new_id = max((g["id"] for g in glossaries), default=0) + 1
    glossary = {
        "id": new_id,
        "user_id": user_id,
        "name": name,
        "source_lang": data.get("source_lang", "en"),
        "target_lang": data.get("target_lang", "es"),
        "entries": data.get("entries", []),
    }
    glossaries.append(glossary)
    _save_glossaries(glossaries)
    return jsonify(glossary), 201


@blueprint.route("/api/glossaries/<int:glossary_id>", methods=["GET"])
def api_glossary_get(glossary_id):
    glossaries = _load_glossaries()
    glossary = next((g for g in glossaries if g["id"] == glossary_id), None)
    if not glossary:
        abort(404)
    return jsonify(glossary)


@blueprint.route("/api/glossaries/<int:glossary_id>", methods=["PUT"])
def api_glossary_update(glossary_id):
    data = request.get_json(silent=True) or {}
    glossaries = _load_glossaries()
    glossary = next((g for g in glossaries if g["id"] == glossary_id), None)
    if not glossary:
        abort(404)
    for field in ("name", "source_lang", "target_lang", "entries"):
        if field in data:
            glossary[field] = data[field]
    _save_glossaries(glossaries)
    return jsonify(glossary)


@blueprint.route("/api/glossaries/<int:glossary_id>", methods=["DELETE"])
def api_glossary_delete(glossary_id):
    glossaries = _load_glossaries()
    glossary = next((g for g in glossaries if g["id"] == glossary_id), None)
    if not glossary:
        abort(404)
    glossaries = [g for g in glossaries if g["id"] != glossary_id]
    _save_glossaries(glossaries)
    return jsonify({"deleted": glossary_id})


@blueprint.route("/api/detect", methods=["POST"])
def api_detect():
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    if not text:
        return jsonify({"error": "text is required"}), 400
    lang, confidence = _detect_language(text)
    languages = _load_languages()
    lang_info = next((l for l in languages if l["code"] == lang), None)
    return jsonify({
        "detected_language": lang,
        "language_name": lang_info["name"] if lang_info else lang,
        "confidence": round(confidence, 3),
    })


@blueprint.route("/api/stats")
def api_stats():
    history = _load_history()
    saved = _load_saved()
    glossaries = _load_glossaries()
    user_id = request.args.get("user_id", type=int)
    if user_id:
        history = [h for h in history if h["user_id"] == user_id]
        saved = [s for s in saved if s["user_id"] == user_id]
        glossaries = [g for g in glossaries if g["user_id"] == user_id]

    lang_pairs = Counter(
        f"{h['source_lang']}->{h['target_lang']}" for h in history
    )
    source_langs = Counter(h["source_lang"] for h in history)
    target_langs = Counter(h["target_lang"] for h in history)

    return jsonify({
        "total_translations": len(history),
        "saved_translations": len(saved),
        "glossaries": len(glossaries),
        "top_language_pairs": dict(lang_pairs.most_common(10)),
        "source_languages": dict(source_langs.most_common(10)),
        "target_languages": dict(target_langs.most_common(10)),
    })


# ---------------------------------------------------------------------------
# API: Settings / configure_by_toggle
# ---------------------------------------------------------------------------

@blueprint.route("/api/settings", methods=["GET"])
def api_settings_get():
    user_id = request.args.get("user_id", 1, type=int)
    return jsonify(_get_user_settings(user_id))


@blueprint.route("/api/settings", methods=["PUT"])
def api_settings_update():
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", 1)
    allowed = {"auto_detect", "formal_mode", "auto_pronounce"}
    updates = {k: v for k, v in data.items() if k in allowed}
    if not updates:
        return jsonify({"error": "No valid settings provided. "
                        "Valid keys: auto_detect, formal_mode, auto_pronounce"}), 400
    result = _set_user_settings(user_id, updates)
    return jsonify(result)


@blueprint.route("/api/settings/toggle", methods=["POST"])
def api_settings_toggle():
    """Toggle a single setting on/off. Body: {"user_id": 1, "setting": "auto_detect"}"""
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id", 1)
    setting = data.get("setting", "").strip()
    allowed = {"auto_detect", "formal_mode", "auto_pronounce"}
    if setting not in allowed:
        return jsonify({"error": f"Invalid setting '{setting}'. "
                        f"Valid: {', '.join(sorted(allowed))}"}), 400
    current = _get_user_settings(user_id)
    new_val = not current.get(setting, False)
    result = _set_user_settings(user_id, {setting: new_val})
    return jsonify({"setting": setting, "value": new_val, "all_settings": result})


# ---------------------------------------------------------------------------
# HTML: Settings page
# ---------------------------------------------------------------------------

@blueprint.route("/settings")
def settings_page():
    user, logged_in = _get_browsing_user()
    user_settings = _get_user_settings(user["id"])
    languages = _load_languages()
    return render_template("translation/settings.html", user=user,
                           settings=user_settings, languages=languages,
                           logged_in=logged_in)


# ---------------------------------------------------------------------------
# API: Playback / play_by_playback  (placeholder TTS)
# ---------------------------------------------------------------------------

@blueprint.route("/api/playback", methods=["POST"])
def api_playback():
    """Return a placeholder audio URL for TTS playback of given text.
    Real TTS is not implemented; this returns metadata about the request."""
    data = request.get_json(silent=True) or {}
    text = data.get("text", "").strip()
    lang = data.get("lang", "en").strip()
    speed = data.get("speed", 1.0)
    if not text:
        return jsonify({"error": "text is required"}), 400
    languages = _load_languages()
    valid_codes = {l["code"] for l in languages}
    if lang not in valid_codes:
        return jsonify({"error": f"Invalid language code '{lang}'"}), 400
    # Placeholder: return metadata about the audio that would be generated
    word_count = len(text.split())
    duration_sec = round(word_count * 0.4 / max(speed, 0.1), 2)
    return jsonify({
        "status": "ready",
        "text": text,
        "lang": lang,
        "speed": speed,
        "word_count": word_count,
        "estimated_duration_sec": duration_sec,
        "audio_url": f"/sites/translation/static/tts_placeholder.mp3",
    })


# ---------------------------------------------------------------------------
# API: Export / export_by_dropdown
# ---------------------------------------------------------------------------

@blueprint.route("/api/export", methods=["GET"])
def api_export():
    """Export translation history in different formats: json, csv, txt."""
    fmt = request.args.get("format", "json").strip().lower()
    user_id = request.args.get("user_id", type=int)
    source_lang = request.args.get("source_lang", "").strip()
    target_lang = request.args.get("target_lang", "").strip()

    history = _load_history()
    if user_id:
        history = [h for h in history if h["user_id"] == user_id]
    if source_lang:
        history = [h for h in history if h["source_lang"] == source_lang]
    if target_lang:
        history = [h for h in history if h["target_lang"] == target_lang]

    if fmt == "csv":
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["id", "user_id", "source_lang", "target_lang",
                         "source_text", "translated_text", "timestamp"])
        for h in history:
            writer.writerow([h["id"], h["user_id"], h["source_lang"],
                             h["target_lang"], h["source_text"],
                             h["translated_text"], h["timestamp"]])
        return Response(buf.getvalue(), mimetype="text/csv",
                        headers={"Content-Disposition": "attachment; filename=translations.csv"})
    elif fmt == "txt":
        lines = []
        for h in history:
            lines.append(f"[{h['source_lang']}->{h['target_lang']}] "
                         f"{h['source_text']} => {h['translated_text']}")
        return Response("\n".join(lines), mimetype="text/plain",
                        headers={"Content-Disposition": "attachment; filename=translations.txt"})
    else:
        # Default: JSON
        return jsonify(history)


# ---------------------------------------------------------------------------
# API: Upload / upload_by_upload
# ---------------------------------------------------------------------------

@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload a text file for batch translation."""
    if "file" not in request.files:
        return jsonify({"error": "No file uploaded. Use multipart form field 'file'."}), 400
    f = request.files["file"]
    if not f.filename:
        return jsonify({"error": "Empty filename"}), 400

    source = request.form.get("source", "en").strip()
    target = request.form.get("target", "es").strip()
    user_id = request.form.get("user_id", "1").strip()
    try:
        user_id = int(user_id)
    except ValueError:
        user_id = 1

    languages = _load_languages()
    valid_codes = {l["code"] for l in languages}
    if source not in valid_codes or target not in valid_codes:
        return jsonify({"error": "Invalid language code"}), 400
    if source == target:
        return jsonify({"error": "source and target must be different"}), 400

    # Read file content
    try:
        content = f.read().decode("utf-8", errors="replace")
    except Exception as e:
        return jsonify({"error": f"Could not read file: {e}"}), 400

    # Translate each non-empty line
    lines = content.strip().split("\n")
    results = []
    history = _load_history()
    for line in lines:
        line = line.strip()
        if not line:
            continue
        translated = _translate_text(line, source, target)
        new_id = max((h["id"] for h in history), default=0) + 1
        record = {
            "id": new_id,
            "user_id": user_id,
            "source_lang": source,
            "target_lang": target,
            "source_text": line,
            "translated_text": translated,
            "timestamp": datetime.now().isoformat(),
        }
        history.append(record)
        results.append({"source": line, "translated": translated, "id": new_id})
    _save_history(history)

    # Save uploaded file
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOADS_DIR / f.filename
    save_path.write_text(content)

    return jsonify({
        "filename": f.filename,
        "lines_translated": len(results),
        "source_lang": source,
        "target_lang": target,
        "translations": results,
    })


# ---------------------------------------------------------------------------
# API: Image submit / submit_by_image  (placeholder OCR)
# ---------------------------------------------------------------------------

@blueprint.route("/api/image-translate", methods=["POST"])
def api_image_translate():
    """Submit an image for OCR + translation (placeholder).
    Accepts an image file and returns a mock OCR extraction + translation."""
    if "image" not in request.files:
        return jsonify({"error": "No image uploaded. Use multipart form field 'image'."}), 400
    img = request.files["image"]
    if not img.filename:
        return jsonify({"error": "Empty filename"}), 400

    target = request.form.get("target", "es").strip()
    source = request.form.get("source", "en").strip()

    languages = _load_languages()
    valid_codes = {l["code"] for l in languages}
    if source not in valid_codes or target not in valid_codes:
        return jsonify({"error": "Invalid language code"}), 400

    # Save the image
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOADS_DIR / img.filename
    img.save(str(save_path))

    # Placeholder OCR: extract "text" from filename or return mock text
    # In a real system this would use OCR. We simulate by reading the
    # filename as a hint or returning a default phrase.
    mock_ocr_text = "Hello good morning"
    translated = _translate_text(mock_ocr_text, source, target)

    return jsonify({
        "filename": img.filename,
        "ocr_text": mock_ocr_text,
        "source_lang": source,
        "target_lang": target,
        "translated_text": translated,
        "confidence": 0.85,
    })


# ---------------------------------------------------------------------------
# API: Semantic search in history / extract_by_semantic
# ---------------------------------------------------------------------------

@blueprint.route("/api/history/semantic", methods=["GET"])
def api_history_semantic():
    """Fuzzy/semantic search across translation history.
    Matches partial words and checks both source and translated text."""
    q = request.args.get("q", "").strip().lower()
    user_id = request.args.get("user_id", type=int)
    if not q:
        return jsonify({"error": "q parameter is required"}), 400

    history = _load_history()
    if user_id:
        history = [h for h in history if h["user_id"] == user_id]

    # Semantic: score each entry by number of query words that appear
    # anywhere in source or translated text (substring match, not exact)
    query_words = q.split()
    scored = []
    for h in history:
        combined = (h["source_text"] + " " + h["translated_text"]).lower()
        score = sum(1 for w in query_words if w in combined)
        if score > 0:
            scored.append((score, h))
    scored.sort(key=lambda x: x[0], reverse=True)
    results = [item for _, item in scored]
    return jsonify(results)


# ---------------------------------------------------------------------------
# API: Login (JSON API)
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid username or password"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "name": user["name"]})

