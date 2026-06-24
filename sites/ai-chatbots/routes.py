"""AI Chatbots Hub — chat interface backed by OpenAI API (gpt-5.4-nano-2026-03-17).

Falls back to rule-based responses when no API key is available.
Conversations are stored in-memory per session.
"""
import json
import os
import pathlib
import re
import uuid
from datetime import datetime, timezone

from flask import (Blueprint, Response, abort, jsonify, redirect, render_template,
                   request, session, url_for)


def _get_openai_key():
    """Load API key lazily, handling 'export KEY=val' format in .env."""
    env_path = pathlib.Path(__file__).resolve().parent.parent.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if line.startswith("export "):
                line = line[7:]
            if line.startswith("OPENAI_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return os.environ.get("OPENAI_API_KEY", "")

SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"
KB_FILE = SITE_DIR / "data" / "knowledge_base.json"
FAQ_FILE = SITE_DIR / "data" / "faq.json"
USERS_FILE = SITE_DIR / "data" / "users.json"
CONVS_FILE = SITE_DIR / "data" / "conversations.json"
PROMPTS_FILE = SITE_DIR / "data" / "prompts_library.json"

blueprint = Blueprint(
    "ai-chatbots",
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
# Data loading
# ---------------------------------------------------------------------------

_kb = None
_faq = None
_prompts = None


def _load_kb():
    global _kb
    if _kb is None:
        with open(KB_FILE) as f:
            _kb = json.load(f)
    return _kb


def _load_faq():
    global _faq
    if _faq is None:
        with open(FAQ_FILE) as f:
            _faq = json.load(f)
    return _faq


def _load_prompts():
    global _prompts
    if _prompts is None:
        with open(PROMPTS_FILE) as f:
            _prompts = json.load(f)
    return _prompts


def _load_users():
    if USERS_FILE.exists():
        return json.loads(USERS_FILE.read_text())
    return []


def _save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


def _load_conversations():
    if CONVS_FILE.exists():
        return json.loads(CONVS_FILE.read_text())
    return []


def _save_conversations(convs):
    CONVS_FILE.write_text(json.dumps(convs, indent=2))


# ---------------------------------------------------------------------------
# RAG — keyword-based retrieval from knowledge base
# ---------------------------------------------------------------------------

def _rag_retrieve(query, top_k=3):
    """Retrieve the top-k most relevant knowledge base entries for a query."""
    kb = _load_kb()
    query_lower = query.lower()
    query_terms = set(re.findall(r'\w+', query_lower))

    scored = []
    for entry in kb:
        score = 0
        # Keyword matching
        for kw in entry.get("keywords", []):
            kw_lower = kw.lower()
            if kw_lower in query_lower:
                score += 3
            elif any(t in kw_lower for t in query_terms):
                score += 1
        # Topic matching
        if entry["topic"].lower() in query_lower:
            score += 5
        for term in query_terms:
            if term in entry["topic"].lower():
                score += 2
            if term in entry["content"].lower():
                score += 0.5
        if score > 0:
            scored.append((entry, score))

    scored.sort(key=lambda x: -x[1])
    return [e for e, _ in scored[:top_k]]


def _rag_retrieve_faq(query, top_k=2):
    """Retrieve matching FAQ entries."""
    faq = _load_faq()
    query_lower = query.lower()
    query_terms = set(re.findall(r'\w+', query_lower))

    scored = []
    for entry in faq:
        score = 0
        q_lower = entry["question"].lower()
        a_lower = entry["answer"].lower()
        for term in query_terms:
            if term in q_lower:
                score += 2
            if term in a_lower:
                score += 0.5
        if score > 0:
            scored.append((entry, score))

    scored.sort(key=lambda x: -x[1])
    return [e for e, _ in scored[:top_k]]


# ---------------------------------------------------------------------------
# Rule-based chatbot engine
# ---------------------------------------------------------------------------

_GREETINGS = {"hello", "hi", "hey", "greetings", "good morning", "good afternoon",
              "good evening", "howdy", "sup", "what's up", "yo"}
_FAREWELLS = {"bye", "goodbye", "see you", "later", "farewell", "quit", "exit"}

_GENERIC_RESPONSES = [
    "That's an interesting question! Let me think about that.",
    "I'd be happy to help you explore that topic further.",
    "Could you provide more details so I can give you a better answer?",
    "That's a great topic! Here's what I can share based on my knowledge.",
]


def _call_openai(user_message, bot_name="Assistant", conversation_history=None):
    """Call OpenAI gpt-5.4-nano-2026-03-17 API. Returns response text or None on failure."""
    key = _get_openai_key()
    if not key:
        return None
    try:
        import urllib.request
        messages = [{"role": "system", "content": f"You are a helpful AI assistant. Keep responses concise (2-3 paragraphs max)."}]
        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({"role": msg["role"], "content": msg["content"]})
        messages.append({"role": "user", "content": user_message})

        payload = json.dumps({
            "model": "gpt-5.4-nano-2026-03-17",
            "messages": messages,
            "max_completion_tokens": 500,
            "temperature": 0.7,
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=payload,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
            return data["choices"][0]["message"]["content"]
    except Exception as e:
        return None


def _generate_response(user_message, bot_name="Assistant", conversation_history=None):
    """Generate response using OpenAI API (gpt-5.4-nano-2026-03-17), with rule-based fallback."""
    # Try OpenAI API first
    api_response = _call_openai(user_message, bot_name, conversation_history)
    if api_response:
        return api_response

    # --- Fallback: rule-based response ---
    msg_lower = user_message.lower().strip()
    config = _load_config()

    # Greeting — only match if the message is purely a greeting
    words = set(msg_lower.replace("!", "").replace("?", "").replace(",", "").split())
    if words & _GREETINGS and len(words) <= 3:
        return f"Hello! I'm {bot_name}, your AI assistant. How can I help you today?"

    # Farewell
    if words & _FAREWELLS and len(words) <= 4:
        return f"Goodbye! It was great chatting with you. Feel free to come back anytime!"

    # Help
    if msg_lower in ("help", "what can you do", "what can you do?", "/help"):
        return (f"I'm {bot_name}, and I can help you with many topics including:\n"
                "- Programming (Python, JavaScript, Web Development)\n"
                "- Machine Learning and AI\n"
                "- Data Science and Databases\n"
                "- Cloud Computing and DevOps\n"
                "- Cybersecurity\n"
                "- Software Testing\n"
                "- And much more!\n\n"
                "Just ask me a question and I'll do my best to help!")

    # Identity questions
    if any(q in msg_lower for q in ["who are you", "what are you", "your name"]):
        return (f"I'm {bot_name}, an AI assistant powered by advanced language models. "
                "I can help answer questions, explain concepts, write code, and assist "
                "with a wide range of tasks. How can I help you?")

    # RAG-augmented response
    kb_results = _rag_retrieve(user_message, top_k=config.get("rag_top_k", 3))
    faq_results = _rag_retrieve_faq(user_message, top_k=2)

    if faq_results:
        best_faq = faq_results[0]
        return best_faq["answer"]

    if kb_results:
        best = kb_results[0]
        response = best["content"]
        if best.get("follow_up"):
            response += "\n\n" + best["follow_up"]
        return response

    # Context-aware fallback using conversation history
    if conversation_history and len(conversation_history) > 0:
        last_assistant = None
        for msg in reversed(conversation_history):
            if msg["role"] == "assistant":
                last_assistant = msg["content"]
                break
        if last_assistant:
            return (f"Building on our conversation, I'd say that's a thoughtful follow-up. "
                    f"Could you tell me more specifically what aspect you'd like to explore? "
                    f"I want to make sure I give you the most helpful answer.")

    # Generic fallback
    import hashlib
    idx = int(hashlib.md5(msg_lower.encode()).hexdigest(), 16) % len(_GENERIC_RESPONSES)
    return _GENERIC_RESPONSES[idx]


# ---------------------------------------------------------------------------
# Semantic search over knowledge base
# ---------------------------------------------------------------------------

def _search_kb(query, semantic=False):
    """Search knowledge base entries."""
    kb = _load_kb()
    if not query:
        return kb
    q = query.lower().strip()
    if semantic:
        return _rag_retrieve(query, top_k=len(kb))
    return [e for e in kb if q in e["topic"].lower() or
            q in e["content"].lower() or
            any(q in kw.lower() for kw in e.get("keywords", []))]


def _search_prompts(query):
    """Search prompts library."""
    prompts = _load_prompts()
    if not query:
        return prompts
    q = query.lower().strip()
    return [p for p in prompts if q in p["title"].lower() or
            q in p["prompt"].lower() or
            q in p.get("category", "").lower() or
            any(q in t.lower() for t in p.get("tags", []))]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    config = _load_config()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    convs = _load_conversations()
    user_convs = []
    if user:
        user_convs = [c for c in convs if c["user_id"] == user["id"] and not c.get("archived")]
    return render_template("ai-chatbots/index.html",
                           config=config, user=user,
                           conversations=user_convs,
                           bots=config.get("available_bots", ["Assistant"]))


@blueprint.route("/chat")
@blueprint.route("/chat/<conv_id>")
def chat_page(conv_id=None):
    config = _load_config()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    convs = _load_conversations()
    user_convs = []
    if user:
        user_convs = [c for c in convs if c["user_id"] == user["id"] and not c.get("archived")]

    current_conv = None
    if conv_id:
        current_conv = next((c for c in convs if c["id"] == conv_id), None)

    bot = request.args.get("bot", config.get("default_bot", "Assistant"))
    return render_template("ai-chatbots/chat.html",
                           config=config, user=user,
                           conversations=user_convs,
                           current_conv=current_conv,
                           bot=bot,
                           bots=config.get("available_bots", ["Assistant"]))


@blueprint.route("/prompts")
def prompts_page():
    config = _load_config()
    prompts = _load_prompts()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    if q:
        prompts = _search_prompts(q)
    if category:
        prompts = [p for p in prompts if p.get("category") == category]

    categories = sorted(set(p.get("category", "") for p in _load_prompts()))
    return render_template("ai-chatbots/prompts.html",
                           config=config, user=user,
                           prompts=prompts, q=q, category=category,
                           categories=categories)


@blueprint.route("/knowledge")
def knowledge_page():
    config = _load_config()
    kb = _load_kb()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    if q:
        kb = _search_kb(q)
    if category:
        kb = [e for e in kb if e.get("category") == category]

    categories = sorted(set(e.get("category", "") for e in _load_kb()))
    return render_template("ai-chatbots/knowledge.html",
                           config=config, user=user,
                           entries=kb, q=q, category=category,
                           categories=categories)


@blueprint.route("/faq")
def faq_page():
    config = _load_config()
    faq = _load_faq()
    q = request.args.get("q", "").strip()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    if q:
        q_lower = q.lower()
        faq = [f for f in faq if q_lower in f["question"].lower() or
               q_lower in f["answer"].lower()]
    categories = sorted(set(f.get("category", "") for f in _load_faq()))
    return render_template("ai-chatbots/faq.html",
                           config=config, user=user,
                           entries=faq, q=q, categories=categories)


@blueprint.route("/settings")
def settings_page():
    config = _load_config()
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    if not user:
        return redirect(url_for("ai-chatbots.login_page"))
    return render_template("ai-chatbots/settings.html",
                           config=config, user=user,
                           bots=config.get("available_bots", ["Assistant"]))


@blueprint.route("/login", methods=["GET"])
def login_page():
    config = _load_config()
    return render_template("ai-chatbots/login.html", error=None, config=config)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    config = _load_config()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("ai-chatbots/login.html",
                               error="Invalid username or password", config=config)
    session["user_id"] = user["id"]
    convs = _load_conversations()
    user_convs = [c for c in convs if c["user_id"] == user["id"] and not c.get("archived")]
    return render_template("ai-chatbots/index.html",
                           config=config, user=user,
                           conversations=user_convs,
                           bots=config.get("available_bots", ["Assistant"]))


@blueprint.route("/register", methods=["GET"])
def register_page():
    config = _load_config()
    return render_template("ai-chatbots/register.html", error=None, config=config)


@blueprint.route("/register", methods=["POST"])
def register_submit():
    config = _load_config()
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    email = request.form.get("email", "").strip()
    display_name = request.form.get("display_name", "").strip()

    if not username or not password:
        return render_template("ai-chatbots/register.html",
                               error="Username and password are required", config=config)

    users = _load_users()
    if any(u["username"] == username for u in users):
        return render_template("ai-chatbots/register.html",
                               error="Username already exists", config=config)

    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "display_name": display_name or username,
        "email": email,
        "preferences": {
            "default_bot": config.get("default_bot", "Assistant"),
            "theme": "dark",
            "font_size": "medium",
            "notifications": True,
            "save_history": True
        },
        "subscription": "free",
        "saved_prompts": [],
        "shared_conversations": []
    }
    users.append(new_user)
    _save_users(users)
    session["user_id"] = new_id
    return render_template("ai-chatbots/index.html",
                           config=config, user=new_user,
                           conversations=[],
                           bots=config.get("available_bots", ["Assistant"]))


@blueprint.route("/logout")
def logout():
    config = _load_config()
    session.pop("user_id", None)
    return render_template("ai-chatbots/login.html", error=None, config=config)


# ---------------------------------------------------------------------------
# Form-based POST routes (for browser automation compatibility)
# ---------------------------------------------------------------------------

@blueprint.route("/form/chat", methods=["POST"])
def form_chat():
    """Send a chat message via HTML form POST. Creates/updates conversation."""
    message = request.form.get("message", "").strip()
    bot = request.form.get("bot", "Assistant")
    conv_id = request.form.get("conversation_id", "").strip() or None

    if not message:
        return redirect(url_for("ai-chatbots.chat_page"))

    convs = _load_conversations()

    if conv_id:
        conv = next((c for c in convs if c["id"] == conv_id), None)
    else:
        conv = None

    if not conv:
        conv_id = f"conv_{uuid.uuid4().hex[:8]}"
        user_id = session.get("user_id", 0)
        conv = {
            "id": conv_id,
            "user_id": user_id,
            "title": message[:50],
            "bot": bot,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
            "shared": False,
            "archived": False,
        }
        convs.append(conv)

    conv["messages"].append({"role": "user", "content": message})
    response = _generate_response(message, bot_name=bot,
                                  conversation_history=conv["messages"])
    conv["messages"].append({"role": "assistant", "content": response})
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()
    _save_conversations(convs)

    return redirect(url_for("ai-chatbots.chat_page", conv_id=conv_id))


@blueprint.route("/form/conversation/<conv_id>/edit-title", methods=["POST"])
def form_edit_title(conv_id):
    """Update conversation title via form POST."""
    new_title = request.form.get("title", "").strip()
    if not new_title:
        return redirect(url_for("ai-chatbots.chat_page", conv_id=conv_id))

    convs = _load_conversations()
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if conv:
        conv["title"] = new_title
        conv["updated_at"] = datetime.now(timezone.utc).isoformat()
        _save_conversations(convs)

    return redirect(url_for("ai-chatbots.chat_page", conv_id=conv_id))


@blueprint.route("/form/conversation/<conv_id>/delete", methods=["POST"])
def form_delete_conversation(conv_id):
    """Delete a conversation via form POST."""
    convs = _load_conversations()
    convs = [c for c in convs if c["id"] != conv_id]
    _save_conversations(convs)
    return redirect(url_for("ai-chatbots.chat_page"))


@blueprint.route("/form/conversation/<conv_id>/share", methods=["POST"])
def form_share_conversation(conv_id):
    """Share a conversation via form POST."""
    share_with = request.form.get("share_with", "public")

    convs = _load_conversations()
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if not conv:
        return redirect(url_for("ai-chatbots.chat_page"))

    conv["shared"] = True
    conv["share_with"] = share_with
    _save_conversations(convs)

    user_id = conv.get("user_id")
    if user_id:
        users = _load_users()
        user = next((u for u in users if u["id"] == user_id), None)
        if user:
            shared_list = user.setdefault("shared_conversations", [])
            if conv_id not in shared_list:
                shared_list.append(conv_id)
            _save_users(users)

    return redirect(url_for("ai-chatbots.chat_page", conv_id=conv_id))


@blueprint.route("/form/settings", methods=["POST"])
def form_save_settings():
    """Save user preferences and subscription via form POST."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("ai-chatbots.login_page"))

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return redirect(url_for("ai-chatbots.login_page"))

    prefs = user.setdefault("preferences", {})
    prefs["default_bot"] = request.form.get("default_bot", prefs.get("default_bot", "Assistant"))
    prefs["theme"] = request.form.get("theme", prefs.get("theme", "dark"))
    prefs["font_size"] = request.form.get("font_size", prefs.get("font_size", "medium"))
    prefs["notifications"] = request.form.get("notifications") == "on"
    prefs["save_history"] = request.form.get("save_history") == "on"

    sub = request.form.get("subscription", user.get("subscription", "free"))
    user["subscription"] = sub

    _save_users(users)
    return redirect(url_for("ai-chatbots.settings_page"))


@blueprint.route("/form/upload", methods=["POST"])
def form_upload():
    """Upload a document to the knowledge base via form POST."""
    topic = request.form.get("topic", "").strip()
    category = request.form.get("category", "uploaded").strip()
    content = request.form.get("content", "").strip()
    keywords_str = request.form.get("keywords", "").strip()
    keywords = [k.strip() for k in keywords_str.split(",") if k.strip()]

    if not topic or not content:
        return redirect(url_for("ai-chatbots.settings_page"))

    kb = _load_kb()
    new_id = max((e["id"] for e in kb), default=0) + 1
    new_entry = {
        "id": new_id,
        "topic": topic,
        "category": category or "uploaded",
        "keywords": keywords,
        "content": content,
        "follow_up": "",
    }
    kb.append(new_entry)

    global _kb
    _kb = kb
    with open(KB_FILE, "w") as f:
        json.dump(kb, f, indent=2)

    return redirect(url_for("ai-chatbots.settings_page"))


@blueprint.route("/form/delete-all-conversations", methods=["POST"])
def form_delete_all_conversations():
    """Delete all conversations for the current user via form POST."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("ai-chatbots.login_page"))

    convs = _load_conversations()
    convs = [c for c in convs if c["user_id"] != user_id]
    _save_conversations(convs)
    return redirect(url_for("ai-chatbots.settings_page"))


@blueprint.route("/form/save-prompt", methods=["POST"])
def form_save_prompt():
    """Save/unsave a prompt for the current user via form POST."""
    user_id = session.get("user_id")
    if not user_id:
        return redirect(url_for("ai-chatbots.login_page"))

    prompt_id = request.form.get("prompt_id", type=int)
    if prompt_id is None:
        return redirect(url_for("ai-chatbots.prompts_page"))

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        return redirect(url_for("ai-chatbots.prompts_page"))

    saved = user.setdefault("saved_prompts", [])
    if prompt_id in saved:
        saved.remove(prompt_id)
    else:
        saved.append(prompt_id)
    _save_users(users)

    return redirect(url_for("ai-chatbots.prompts_page"))


# ---------------------------------------------------------------------------
# API routes — Chat
# ---------------------------------------------------------------------------

@blueprint.route("/api/chat", methods=["POST"])
def api_chat():
    """Send a message and get a response. Creates/updates conversation."""
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    bot = data.get("bot", "Assistant")
    conv_id = data.get("conversation_id")

    if not message:
        return jsonify({"error": "message required"}), 400

    convs = _load_conversations()
    conversation_history = []

    if conv_id:
        conv = next((c for c in convs if c["id"] == conv_id), None)
        if conv:
            conversation_history = conv.get("messages", [])
    else:
        conv_id = f"conv_{uuid.uuid4().hex[:8]}"
        user_id = session.get("user_id", 0)
        conv = {
            "id": conv_id,
            "user_id": user_id,
            "title": message[:50],
            "bot": bot,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "messages": [],
            "shared": False,
            "archived": False
        }
        convs.append(conv)

    # Add user message
    conv["messages"].append({"role": "user", "content": message})

    # Generate response
    response = _generate_response(message, bot_name=bot,
                                  conversation_history=conv["messages"])

    # Add assistant response
    conv["messages"].append({"role": "assistant", "content": response})
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()

    _save_conversations(convs)

    return jsonify({
        "conversation_id": conv_id,
        "response": response,
        "bot": bot,
        "message_count": len(conv["messages"])
    })


@blueprint.route("/api/conversations")
def api_conversations():
    """List conversations, optionally filtered by user_id."""
    convs = _load_conversations()
    user_id = request.args.get("user_id", type=int)
    if user_id is not None:
        convs = [c for c in convs if c["user_id"] == user_id]
    archived = request.args.get("archived")
    if archived is not None:
        show_archived = archived.lower() in ("true", "1")
        convs = [c for c in convs if c.get("archived", False) == show_archived]
    return jsonify(convs)


@blueprint.route("/api/conversations/<conv_id>")
def api_conversation(conv_id):
    """Get a single conversation by ID."""
    convs = _load_conversations()
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if not conv:
        abort(404)
    return jsonify(conv)


@blueprint.route("/api/conversations/<conv_id>", methods=["PUT"])
def api_update_conversation(conv_id):
    """Update conversation metadata (title, archived, shared)."""
    data = request.get_json(silent=True) or {}
    convs = _load_conversations()
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    if "title" in data:
        conv["title"] = data["title"]
    if "archived" in data:
        conv["archived"] = bool(data["archived"])
    if "shared" in data:
        conv["shared"] = bool(data["shared"])
    if "bot" in data:
        conv["bot"] = data["bot"]
    conv["updated_at"] = datetime.now(timezone.utc).isoformat()

    _save_conversations(convs)
    return jsonify(conv)


@blueprint.route("/api/conversations/<conv_id>", methods=["DELETE"])
def api_delete_conversation(conv_id):
    """Delete a conversation."""
    convs = _load_conversations()
    before = len(convs)
    convs = [c for c in convs if c["id"] != conv_id]
    if len(convs) == before:
        abort(404)
    _save_conversations(convs)
    return jsonify({"deleted": conv_id, "remaining": len(convs)})


@blueprint.route("/api/conversations/<conv_id>/messages")
def api_conversation_messages(conv_id):
    """Get messages for a conversation."""
    convs = _load_conversations()
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if not conv:
        abort(404)
    return jsonify(conv.get("messages", []))


# ---------------------------------------------------------------------------
# API routes — Knowledge Base / RAG
# ---------------------------------------------------------------------------

@blueprint.route("/api/knowledge")
def api_knowledge():
    """Search knowledge base. ?q=query&semantic=true"""
    q = request.args.get("q", "").strip()
    semantic = request.args.get("semantic", "").lower() in ("true", "1")
    category = request.args.get("category", "").strip()
    kb = _load_kb()

    if q:
        if semantic:
            kb = _rag_retrieve(q, top_k=len(kb))
        else:
            kb = [e for e in kb if q.lower() in e["topic"].lower() or
                  q.lower() in e["content"].lower() or
                  any(q.lower() in kw.lower() for kw in e.get("keywords", []))]
    if category:
        kb = [e for e in kb if e.get("category") == category]

    return jsonify(kb)


@blueprint.route("/api/knowledge/<int:entry_id>")
def api_knowledge_entry(entry_id):
    """Get a single knowledge base entry."""
    kb = _load_kb()
    entry = next((e for e in kb if e["id"] == entry_id), None)
    if not entry:
        abort(404)
    return jsonify(entry)


@blueprint.route("/api/knowledge/search")
def api_knowledge_search():
    """Search knowledge base with keyword matching."""
    q = request.args.get("q", "").strip()
    kb = _load_kb()
    if not q:
        return jsonify(kb)
    return jsonify(_search_kb(q))


@blueprint.route("/api/knowledge/semantic")
def api_knowledge_semantic():
    """Semantic search over knowledge base."""
    q = request.args.get("q", "").strip()
    if not q:
        return jsonify(_load_kb())
    results = _rag_retrieve(q, top_k=len(_load_kb()))
    return jsonify(results)


@blueprint.route("/api/knowledge/categories")
def api_knowledge_categories():
    """List knowledge base categories with counts."""
    kb = _load_kb()
    cats = {}
    for e in kb:
        cat = e.get("category", "uncategorized")
        cats[cat] = cats.get(cat, 0) + 1
    return jsonify([{"name": k, "count": v} for k, v in sorted(cats.items())])


# ---------------------------------------------------------------------------
# API routes — FAQ
# ---------------------------------------------------------------------------

@blueprint.route("/api/faq")
def api_faq():
    """List FAQ entries, optionally filtered by category."""
    faq = _load_faq()
    category = request.args.get("category", "").strip()
    if category:
        faq = [f for f in faq if f.get("category") == category]
    return jsonify(faq)


@blueprint.route("/api/faq/search")
def api_faq_search():
    """Search FAQ entries."""
    q = request.args.get("q", "").strip()
    faq = _load_faq()
    if not q:
        return jsonify(faq)
    q_lower = q.lower()
    return jsonify([f for f in faq if q_lower in f["question"].lower() or
                    q_lower in f["answer"].lower()])


# ---------------------------------------------------------------------------
# API routes — Prompts Library
# ---------------------------------------------------------------------------

@blueprint.route("/api/prompts")
def api_prompts():
    """List prompts, optionally filtered."""
    prompts = _load_prompts()
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()
    sort = request.args.get("sort", "").strip()

    if q:
        prompts = _search_prompts(q)
    if category:
        prompts = [p for p in prompts if p.get("category") == category]
    if sort == "popularity":
        prompts.sort(key=lambda p: -p.get("popularity", 0))
    elif sort == "title":
        prompts.sort(key=lambda p: p["title"].lower())

    return jsonify(prompts)


@blueprint.route("/api/prompts/<int:prompt_id>")
def api_prompt(prompt_id):
    """Get a single prompt."""
    prompts = _load_prompts()
    prompt = next((p for p in prompts if p["id"] == prompt_id), None)
    if not prompt:
        abort(404)
    return jsonify(prompt)


# ---------------------------------------------------------------------------
# API routes — Users
# ---------------------------------------------------------------------------

@blueprint.route("/api/login", methods=["POST"])
def api_login():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return jsonify({"error": "Invalid credentials"}), 401
    session["user_id"] = user["id"]
    return jsonify({"user_id": user["id"], "username": user["username"],
                    "display_name": user.get("display_name", "")})


@blueprint.route("/api/register", methods=["POST"])
def api_register():
    data = request.get_json(silent=True) or {}
    username = data.get("username", "").strip()
    password = data.get("password", "").strip()
    email = data.get("email", "").strip()
    display_name = data.get("display_name", "").strip()

    if not username or not password:
        return jsonify({"error": "Username and password required"}), 400

    users = _load_users()
    if any(u["username"] == username for u in users):
        return jsonify({"error": "Username already exists"}), 409

    config = _load_config()
    new_id = max((u["id"] for u in users), default=0) + 1
    new_user = {
        "id": new_id,
        "username": username,
        "password": password,
        "display_name": display_name or username,
        "email": email,
        "preferences": {
            "default_bot": config.get("default_bot", "Assistant"),
            "theme": "dark",
            "font_size": "medium",
            "notifications": True,
            "save_history": True
        },
        "subscription": "free",
        "saved_prompts": [],
        "shared_conversations": []
    }
    users.append(new_user)
    _save_users(users)
    session["user_id"] = new_id
    return jsonify({"user_id": new_id, "username": username}), 201


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/preferences", methods=["PUT"])
def api_update_preferences(user_id):
    """Update user preferences."""
    data = request.get_json(silent=True) or {}
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    prefs = user.setdefault("preferences", {})
    for key in ("default_bot", "theme", "font_size", "notifications", "save_history"):
        if key in data:
            prefs[key] = data[key]

    _save_users(users)
    return jsonify({"preferences": prefs})


@blueprint.route("/api/users/<int:user_id>/save-prompt", methods=["POST"])
def api_save_prompt(user_id):
    """Save/unsave a prompt to user's library."""
    data = request.get_json(silent=True) or {}
    prompt_id = data.get("prompt_id")
    if prompt_id is None:
        return jsonify({"error": "prompt_id required"}), 400

    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)

    saved = user.setdefault("saved_prompts", [])
    if prompt_id in saved:
        saved.remove(prompt_id)
        action = "unsaved"
    else:
        saved.append(prompt_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "prompt_id": prompt_id, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/subscription", methods=["PUT"])
def api_update_subscription(user_id):
    """Toggle subscription status."""
    data = request.get_json(silent=True) or {}
    plan = data.get("plan", "free")
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    user["subscription"] = plan
    _save_users(users)
    return jsonify({"user_id": user_id, "subscription": plan})


# ---------------------------------------------------------------------------
# API routes — Share
# ---------------------------------------------------------------------------

@blueprint.route("/api/conversations/<conv_id>/share", methods=["POST"])
def api_share_conversation(conv_id):
    """Share a conversation. Sets shared=true and returns a share link."""
    data = request.get_json(silent=True) or {}
    share_with = data.get("share_with", "public")

    convs = _load_conversations()
    conv = next((c for c in convs if c["id"] == conv_id), None)
    if not conv:
        abort(404)

    conv["shared"] = True
    conv["share_with"] = share_with
    _save_conversations(convs)

    # Also add to user's shared list
    user_id = conv.get("user_id")
    if user_id:
        users = _load_users()
        user = next((u for u in users if u["id"] == user_id), None)
        if user:
            shared_list = user.setdefault("shared_conversations", [])
            if conv_id not in shared_list:
                shared_list.append(conv_id)
            _save_users(users)

    return jsonify({"shared": True, "conversation_id": conv_id,
                    "share_with": share_with})


# ---------------------------------------------------------------------------
# API routes — Export
# ---------------------------------------------------------------------------

@blueprint.route("/api/export")
def api_export():
    """Export conversations or knowledge base."""
    fmt = request.args.get("format", "json").lower()
    what = request.args.get("type", "conversations").lower()

    if what == "knowledge":
        data = _load_kb()
    elif what == "prompts":
        data = _load_prompts()
    elif what == "faq":
        data = _load_faq()
    else:
        data = _load_conversations()
        user_id = request.args.get("user_id", type=int)
        if user_id is not None:
            data = [c for c in data if c["user_id"] == user_id]

    if fmt == "csv":
        if what == "knowledge":
            lines = ["id,topic,category,content"]
            for e in data:
                topic = e["topic"].replace('"', '""')
                content = e["content"][:100].replace('"', '""')
                lines.append(f'{e["id"]},"{topic}","{e.get("category", "")}","{content}"')
        elif what == "prompts":
            lines = ["id,title,category,popularity"]
            for p in data:
                title = p["title"].replace('"', '""')
                lines.append(f'{p["id"]},"{title}","{p.get("category", "")}",{p.get("popularity", 0)}')
        else:
            lines = ["id,title,bot,user_id,message_count,created_at"]
            for c in data:
                title = c.get("title", "").replace('"', '""')
                lines.append(f'"{c["id"]}","{title}","{c.get("bot", "")}",{c.get("user_id", 0)},{len(c.get("messages", []))},"{c.get("created_at", "")}"')
        return Response("\n".join(lines), mimetype="text/csv",
                        headers={"Content-Disposition": f"attachment; filename={what}.csv"})
    return jsonify(data)


# ---------------------------------------------------------------------------
# API routes — Upload (for RAG documents)
# ---------------------------------------------------------------------------

@blueprint.route("/api/upload", methods=["POST"])
def api_upload():
    """Upload a text document to the knowledge base."""
    if "file" not in request.files:
        # Check for JSON body fallback
        data = request.get_json(silent=True) or {}
        topic = data.get("topic", "").strip()
        content = data.get("content", "").strip()
        category = data.get("category", "general").strip()
        keywords = data.get("keywords", [])
    else:
        f = request.files["file"]
        content = f.read().decode("utf-8", errors="replace")
        topic = request.form.get("topic", f.filename or "Uploaded Document")
        category = request.form.get("category", "uploaded")
        keywords = request.form.get("keywords", "").split(",")

    if not topic or not content:
        return jsonify({"error": "topic and content required"}), 400

    kb = _load_kb()
    new_id = max((e["id"] for e in kb), default=0) + 1
    new_entry = {
        "id": new_id,
        "topic": topic,
        "category": category,
        "keywords": [k.strip() for k in keywords if k.strip()],
        "content": content,
        "follow_up": ""
    }
    kb.append(new_entry)

    global _kb
    _kb = kb
    with open(KB_FILE, "w") as f:
        json.dump(kb, f, indent=2)

    return jsonify({"id": new_id, "topic": topic, "status": "uploaded"}), 201


# ---------------------------------------------------------------------------
# API routes — Stats
# ---------------------------------------------------------------------------

@blueprint.route("/api/stats")
def api_stats():
    """Overall statistics."""
    kb = _load_kb()
    faq = _load_faq()
    prompts = _load_prompts()
    convs = _load_conversations()
    users = _load_users()

    total_messages = sum(len(c.get("messages", [])) for c in convs)
    bots_used = {}
    for c in convs:
        b = c.get("bot", "Unknown")
        bots_used[b] = bots_used.get(b, 0) + 1

    return jsonify({
        "knowledge_entries": len(kb),
        "faq_entries": len(faq),
        "prompts": len(prompts),
        "conversations": len(convs),
        "total_messages": total_messages,
        "users": len(users),
        "bots_used": bots_used,
        "kb_categories": sorted(set(e.get("category", "") for e in kb))
    })
