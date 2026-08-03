"""LinguaBridge Translator -- translate text using LLM (same as AI chatbot).

Inspired by Google Translate. Uses OpenAI gpt-5.4-nano for actual translation.
"""
import csv
import io
import json
import pathlib
import re
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
    """Deterministic word-by-word translation using built-in dictionaries.

    Replaces each known word with its target-language equivalent, preserving
    punctuation and unknown words. User glossary entries take priority.
    """
    if not text or not text.strip():
        return ""
    if source_lang == target_lang:
        return text

    # User glossary entries take priority over built-in dictionaries.
    glossary = {}
    if user_glossary and user_glossary.get("entries"):
        for entry in user_glossary["entries"]:
            glossary[entry["source"].lower()] = entry["target"]

    # A direct dictionary for this pair (en->X, or an inverted X->en).
    direct = _DICTIONARIES.get(f"{source_lang}->{target_lang}")
    if direct is None:
        direct = _REVERSE_DICTIONARIES.get(f"{source_lang}->{target_lang}")
    # Pieces to pivot through English when there is no direct dictionary.
    src_to_en = None if source_lang == "en" else _REVERSE_DICTIONARIES.get(f"{source_lang}->en")
    en_to_tgt = None if target_lang == "en" else _DICTIONARIES.get(f"en->{target_lang}")

    def _resolve(low):
        if low in glossary:
            return glossary[low]
        if direct and low in direct:
            return direct[low]
        # Pivot: source -> English -> target.
        en_word = low if source_lang == "en" else (src_to_en.get(low) if src_to_en else None)
        if en_word is None:
            return None
        if target_lang == "en":
            return en_word
        if en_to_tgt and en_word in en_to_tgt:
            return en_to_tgt[en_word]
        return None

    tokens = re.findall(r"[\w']+|[^\w\s]|\s+", text)
    result = []
    for token in tokens:
        replacement = _resolve(token.lower())
        if replacement:
            # Preserve original capitalization for alphabetic scripts.
            if len(token) > 1 and token[0].isupper() and token[1:].islower():
                replacement = replacement[0].upper() + replacement[1:]
            elif token.isupper() and token.isalpha():
                replacement = replacement.upper()
            result.append(replacement)
        else:
            result.append(token)
    return "".join(result)


# Built-in word dictionaries (en->target)
_DICTIONARIES = {
    "en->es": {
        # Common words
        "the": "el", "a": "un", "an": "un", "is": "es", "are": "son", "was": "fue",
        "were": "fueron", "be": "ser", "been": "sido", "being": "siendo",
        "have": "tener", "has": "tiene", "had": "tenía", "having": "teniendo",
        "do": "hacer", "does": "hace", "did": "hizo", "will": "va a",
        "would": "haría", "could": "podría", "should": "debería",
        "may": "puede", "might": "podría", "must": "debe", "shall": "deberá",
        "can": "puede", "need": "necesitar", "want": "querer",
        "i": "yo", "you": "tú", "he": "él", "she": "ella", "it": "ello",
        "we": "nosotros", "they": "ellos", "me": "me", "him": "lo", "her": "la",
        "us": "nos", "them": "los", "my": "mi", "your": "tu", "his": "su",
        "its": "su", "our": "nuestro", "their": "su",
        "this": "este", "that": "ese", "these": "estos", "those": "esos",
        "and": "y", "but": "pero", "or": "o", "not": "no", "if": "si",
        "then": "entonces", "than": "que", "so": "así", "because": "porque",
        "when": "cuando", "where": "donde", "how": "cómo", "what": "qué",
        "who": "quién", "which": "cuál", "all": "todo", "each": "cada",
        "every": "cada", "both": "ambos", "few": "pocos", "more": "más",
        "most": "mayoría", "other": "otro", "some": "algunos", "such": "tal",
        "no": "no", "only": "solo", "same": "mismo", "very": "muy",
        "just": "solo", "also": "también", "now": "ahora", "here": "aquí",
        "there": "allí", "still": "todavía", "already": "ya",
        "about": "sobre", "after": "después", "again": "otra vez",
        "against": "contra", "at": "en", "before": "antes", "between": "entre",
        "by": "por", "down": "abajo", "during": "durante", "for": "para",
        "from": "de", "in": "en", "into": "en", "of": "de", "on": "en",
        "out": "fuera", "over": "sobre", "through": "a través", "to": "a",
        "under": "bajo", "up": "arriba", "with": "con", "without": "sin",
        # Nouns
        "pipeline": "tubería", "update": "actualización", "target": "objetivo",
        "week": "semana", "deals": "tratos", "deal": "trato",
        "stages": "etapas", "stage": "etapa", "final": "final",
        "opportunity": "oportunidad", "access": "acceso", "early": "temprano",
        "reports": "informes", "report": "informe", "custom": "personalizado",
        "compliance": "cumplimiento", "roadmap": "hoja de ruta",
        "quarter": "trimestre", "year": "año", "month": "mes", "day": "día",
        "time": "tiempo", "work": "trabajo", "people": "personas",
        "way": "camino", "world": "mundo", "life": "vida",
        "hand": "mano", "part": "parte", "place": "lugar", "case": "caso",
        "group": "grupo", "company": "empresa", "system": "sistema",
        "program": "programa", "question": "pregunta", "number": "número",
        "night": "noche", "point": "punto", "home": "hogar", "water": "agua",
        "room": "habitación", "mother": "madre", "area": "área",
        "money": "dinero", "story": "historia", "fact": "hecho",
        "price": "precio", "payment": "pago", "account": "cuenta",
        "order": "pedido", "product": "producto", "service": "servicio",
        "customer": "cliente", "market": "mercado", "team": "equipo",
        "name": "nombre", "email": "correo", "message": "mensaje",
        "file": "archivo", "page": "página", "search": "búsqueda",
        "data": "datos", "user": "usuario", "password": "contraseña",
        "hello": "hola", "goodbye": "adiós", "please": "por favor",
        "thank": "gracias", "thanks": "gracias", "yes": "sí",
        "good": "bueno", "great": "genial", "new": "nuevo", "old": "viejo",
        "big": "grande", "small": "pequeño", "long": "largo", "short": "corto",
        "high": "alto", "low": "bajo", "left": "izquierda", "right": "derecha",
        "think": "creo", "know": "saber", "get": "obtener", "go": "ir",
        "come": "venir", "make": "hacer", "take": "tomar", "see": "ver",
        "say": "decir", "give": "dar", "find": "encontrar", "tell": "decir",
        "ask": "preguntar", "use": "usar", "try": "intentar",
        "leave": "dejar", "call": "llamar", "keep": "mantener",
        "let": "dejar", "begin": "comenzar", "show": "mostrar",
        "hear": "escuchar", "play": "jugar", "run": "correr",
        "move": "mover", "live": "vivir", "believe": "creer",
        "close": "cerrar", "scheduled": "programado",
        "one": "uno", "two": "dos", "three": "tres",
        # Business terms
        "meeting": "reunión", "project": "proyecto", "budget": "presupuesto",
        "deadline": "fecha límite", "review": "revisión", "approval": "aprobación",
        "schedule": "horario", "conference": "conferencia",
    },
    "en->fr": {
        "the": "le", "a": "un", "is": "est", "are": "sont", "was": "était",
        "have": "avoir", "has": "a", "and": "et", "but": "mais", "or": "ou",
        "not": "pas", "i": "je", "you": "vous", "he": "il", "she": "elle",
        "we": "nous", "they": "ils", "my": "mon", "your": "votre",
        "this": "ce", "that": "ce", "with": "avec", "for": "pour",
        "from": "de", "in": "dans", "on": "sur", "at": "à", "to": "à",
        "of": "de", "hello": "bonjour", "goodbye": "au revoir",
        "please": "s'il vous plaît", "thank": "merci", "thanks": "merci",
        "yes": "oui", "no": "non", "good": "bon", "great": "formidable",
        "pipeline": "pipeline", "update": "mise à jour", "target": "objectif",
        "week": "semaine", "deal": "accord", "deals": "accords",
        "meeting": "réunion", "project": "projet", "report": "rapport",
    },
    "en->de": {
        "the": "der", "a": "ein", "is": "ist", "are": "sind", "was": "war",
        "have": "haben", "has": "hat", "and": "und", "but": "aber", "or": "oder",
        "not": "nicht", "i": "ich", "you": "du", "he": "er", "she": "sie",
        "we": "wir", "they": "sie", "my": "mein", "your": "dein",
        "this": "dies", "that": "das", "with": "mit", "for": "für",
        "from": "von", "in": "in", "on": "auf", "at": "bei", "to": "zu",
        "of": "von", "hello": "hallo", "goodbye": "auf Wiedersehen",
        "please": "bitte", "thank": "danke", "thanks": "danke",
        "yes": "ja", "no": "nein", "good": "gut",
        "pipeline": "Pipeline", "update": "Aktualisierung", "target": "Ziel",
        "week": "Woche", "deal": "Geschäft", "deals": "Geschäfte",
        "meeting": "Besprechung", "project": "Projekt", "report": "Bericht",
    },
    "en->pt": {
        "the": "o", "a": "um", "an": "um", "is": "é", "are": "são", "was": "era",
        "have": "ter", "has": "tem", "and": "e", "but": "mas", "or": "ou",
        "not": "não", "i": "eu", "you": "você", "he": "ele", "she": "ela",
        "we": "nós", "they": "eles", "my": "meu", "your": "seu",
        "this": "este", "that": "esse", "with": "com", "for": "para",
        "from": "de", "in": "em", "on": "em", "at": "em", "to": "para",
        "of": "de", "hello": "olá", "goodbye": "adeus", "please": "por favor",
        "thank": "obrigado", "thanks": "obrigado", "yes": "sim", "no": "não",
        "good": "bom", "great": "ótimo", "welcome": "bem-vindo", "sorry": "desculpe",
        "love": "amor", "water": "água", "food": "comida", "friend": "amigo",
        "day": "dia", "name": "nome", "morning": "manhã", "night": "noite",
        "big": "grande", "small": "pequeno", "new": "novo", "old": "velho",
        "happy": "feliz", "world": "mundo", "book": "livro", "house": "casa",
        "time": "tempo", "today": "hoje", "tomorrow": "amanhã",
        "week": "semana", "meeting": "reunião", "project": "projeto", "report": "relatório",
    },
    "en->it": {
        "the": "il", "a": "un", "an": "un", "is": "è", "are": "sono", "was": "era",
        "have": "avere", "has": "ha", "and": "e", "but": "ma", "or": "o",
        "not": "non", "i": "io", "you": "tu", "he": "lui", "she": "lei",
        "we": "noi", "they": "loro", "my": "mio", "your": "tuo",
        "this": "questo", "that": "quello", "with": "con", "for": "per",
        "from": "da", "in": "in", "on": "su", "at": "a", "to": "a",
        "of": "di", "hello": "ciao", "goodbye": "arrivederci", "please": "per favore",
        "thank": "grazie", "thanks": "grazie", "yes": "sì", "no": "no",
        "good": "buono", "great": "ottimo", "welcome": "benvenuto", "sorry": "scusa",
        "love": "amore", "water": "acqua", "food": "cibo", "friend": "amico",
        "day": "giorno", "name": "nome", "morning": "mattina", "night": "notte",
        "big": "grande", "small": "piccolo", "new": "nuovo", "old": "vecchio",
        "happy": "felice", "world": "mondo", "book": "libro", "house": "casa",
        "time": "tempo", "today": "oggi", "tomorrow": "domani",
        "week": "settimana", "meeting": "riunione", "project": "progetto", "report": "rapporto",
    },
    "en->vi": {
        "a": "một", "an": "một", "is": "là", "are": "là", "was": "đã",
        "have": "có", "has": "có", "and": "và", "but": "nhưng", "or": "hoặc",
        "not": "không", "i": "tôi", "you": "bạn", "he": "anh ấy", "she": "cô ấy",
        "we": "chúng tôi", "they": "họ", "my": "của tôi", "your": "của bạn",
        "this": "này", "that": "đó", "with": "với", "for": "cho",
        "from": "từ", "in": "trong", "on": "trên", "at": "tại", "to": "đến",
        "of": "của", "hello": "xin chào", "goodbye": "tạm biệt", "please": "làm ơn",
        "thank": "cảm ơn", "thanks": "cảm ơn", "yes": "vâng", "no": "không",
        "good": "tốt", "great": "tuyệt", "welcome": "chào mừng", "sorry": "xin lỗi",
        "love": "yêu", "water": "nước", "food": "thức ăn", "friend": "bạn bè",
        "day": "ngày", "name": "tên", "morning": "buổi sáng", "night": "đêm",
        "big": "lớn", "small": "nhỏ", "new": "mới", "old": "cũ",
        "happy": "vui", "world": "thế giới", "book": "sách", "house": "nhà",
        "time": "thời gian", "today": "hôm nay", "tomorrow": "ngày mai",
        "week": "tuần", "meeting": "cuộc họp", "project": "dự án", "report": "báo cáo",
    },
    "en->ja": {
        "is": "です", "are": "です", "have": "持つ", "and": "と", "but": "しかし",
        "or": "または", "not": "ない", "i": "私", "you": "あなた", "he": "彼",
        "she": "彼女", "we": "私たち", "they": "彼ら", "my": "私の", "your": "あなたの",
        "this": "これ", "that": "それ", "with": "と", "for": "のために",
        "from": "から", "in": "に", "on": "に", "at": "に", "to": "へ", "of": "の",
        "hello": "こんにちは", "goodbye": "さようなら", "please": "お願いします",
        "thank": "ありがとう", "thanks": "ありがとう", "yes": "はい", "no": "いいえ",
        "good": "良い", "great": "素晴らしい", "welcome": "ようこそ", "sorry": "ごめんなさい",
        "love": "愛", "water": "水", "food": "食べ物", "friend": "友達",
        "day": "日", "name": "名前", "morning": "朝", "night": "夜",
        "big": "大きい", "small": "小さい", "new": "新しい", "old": "古い",
        "happy": "幸せ", "world": "世界", "book": "本", "house": "家",
        "time": "時間", "today": "今日", "tomorrow": "明日",
        "week": "週", "meeting": "会議", "project": "プロジェクト", "report": "報告",
    },
    "en->zh": {
        "is": "是", "are": "是", "have": "有", "has": "有", "and": "和", "but": "但是",
        "or": "或", "not": "不", "i": "我", "you": "你", "he": "他", "she": "她",
        "we": "我们", "they": "他们", "my": "我的", "your": "你的",
        "this": "这", "that": "那", "with": "和", "for": "为", "from": "从",
        "in": "在", "on": "在", "at": "在", "to": "到", "of": "的",
        "hello": "你好", "goodbye": "再见", "please": "请", "thank": "谢谢",
        "thanks": "谢谢", "yes": "是", "no": "不", "good": "好", "great": "很好",
        "welcome": "欢迎", "sorry": "对不起", "love": "爱", "water": "水",
        "food": "食物", "friend": "朋友", "day": "天", "name": "名字",
        "morning": "早上", "night": "晚上", "big": "大", "small": "小",
        "new": "新", "old": "旧", "happy": "快乐", "world": "世界",
        "book": "书", "house": "房子", "time": "时间", "today": "今天", "tomorrow": "明天",
        "week": "星期", "meeting": "会议", "project": "项目", "report": "报告",
    },
    "en->ko": {
        "is": "입니다", "are": "입니다", "have": "있다", "and": "그리고", "but": "하지만",
        "or": "또는", "not": "아니다", "i": "나", "you": "너", "he": "그", "she": "그녀",
        "we": "우리", "they": "그들", "my": "나의", "your": "너의",
        "this": "이것", "that": "저것", "with": "와", "for": "위해", "from": "부터",
        "in": "안에", "on": "위에", "at": "에", "to": "에게", "of": "의",
        "hello": "안녕하세요", "goodbye": "안녕히 가세요", "please": "제발",
        "thank": "감사합니다", "thanks": "감사합니다", "yes": "네", "no": "아니요",
        "good": "좋은", "great": "훌륭한", "welcome": "환영합니다", "sorry": "미안합니다",
        "love": "사랑", "water": "물", "food": "음식", "friend": "친구",
        "day": "날", "name": "이름", "morning": "아침", "night": "밤",
        "big": "큰", "small": "작은", "new": "새로운", "old": "오래된",
        "happy": "행복한", "world": "세계", "book": "책", "house": "집",
        "time": "시간", "today": "오늘", "tomorrow": "내일",
        "week": "주", "meeting": "회의", "project": "프로젝트", "report": "보고서",
    },
    "en->ar": {
        "have": "يملك", "and": "و", "but": "لكن", "or": "أو", "not": "لا",
        "i": "أنا", "you": "أنت", "he": "هو", "she": "هي", "we": "نحن", "they": "هم",
        "my": "لي", "your": "لك", "this": "هذا", "that": "ذلك", "with": "مع",
        "for": "لـ", "from": "من", "in": "في", "on": "على", "at": "في",
        "to": "إلى", "of": "من", "hello": "مرحبا", "goodbye": "وداعا",
        "please": "من فضلك", "thank": "شكرا", "thanks": "شكرا", "yes": "نعم",
        "no": "لا", "good": "جيد", "great": "عظيم", "welcome": "أهلا", "sorry": "آسف",
        "love": "حب", "water": "ماء", "food": "طعام", "friend": "صديق",
        "day": "يوم", "name": "اسم", "morning": "صباح", "night": "ليل",
        "big": "كبير", "small": "صغير", "new": "جديد", "old": "قديم",
        "happy": "سعيد", "world": "عالم", "book": "كتاب", "house": "منزل",
        "time": "وقت", "today": "اليوم", "tomorrow": "غدا",
        "week": "أسبوع", "meeting": "اجتماع", "project": "مشروع", "report": "تقرير",
    },
}


def _reverse_dictionaries():
    """Build target->English dictionaries by inverting the en->X dicts, so
    translation works in reverse and can pivot through English for any pair."""
    rev = {}
    for pair, mapping in _DICTIONARIES.items():
        src, tgt = pair.split("->")
        rmap = rev.setdefault(f"{tgt}->{src}", {})
        for s, t in mapping.items():
            rmap.setdefault(t.lower(), s)  # first English word wins
    return rev


_REVERSE_DICTIONARIES = _reverse_dictionaries()


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

