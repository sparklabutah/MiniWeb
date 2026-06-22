"""TumblrVibe Blogging Platform — Tumblr-style blog with posts, comments, users.

Data is synthesized deterministically from config/config.json (num_data_points, random_seed).
Mutable state (users, comments, reports) lives in data/*.json with .pristine/ backup.
"""
import json
import pathlib
import random
import shutil
from datetime import datetime, timedelta

from flask import Blueprint, Response, abort, jsonify, redirect, render_template, request, session, url_for

SITE_DIR = pathlib.Path(__file__).resolve().parent
CONFIG_FILE = SITE_DIR / "config" / "config.json"
DATA_DIR = SITE_DIR / "data"
POSTS_FILE = DATA_DIR / "posts.json"
USERS_FILE = DATA_DIR / "users.json"
COMMENTS_FILE = DATA_DIR / "comments.json"
REPORTS_FILE = DATA_DIR / "reports.json"

blueprint = Blueprint(
    "blogs",
    __name__,
    template_folder=str(SITE_DIR / "templates"),
)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_FILE) as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Data synthesis
# ---------------------------------------------------------------------------

_AUTHORS = [
    {"id": 1, "username": "midnight_coder", "display_name": "Midnight Coder", "bio": "Full-stack dev writing about code at 2am", "avatar": "https://placehold.co/80x80/EEE/999?text=mc"},
    {"id": 2, "username": "wanderlust_jess", "display_name": "Wanderlust Jess", "bio": "Travel stories from every continent", "avatar": "https://placehold.co/80x80/EEE/999?text=wj"},
    {"id": 3, "username": "kitchen_sage", "display_name": "Kitchen Sage", "bio": "Recipes, tips, and kitchen disasters", "avatar": "https://placehold.co/80x80/EEE/999?text=ks"},
    {"id": 4, "username": "pixel_dreamer", "display_name": "Pixel Dreamer", "bio": "Digital artist and tutorial maker", "avatar": "https://placehold.co/80x80/EEE/999?text=pd"},
    {"id": 5, "username": "bookworm_alex", "display_name": "Bookworm Alex", "bio": "Reviewing books one chapter at a time", "avatar": "https://placehold.co/80x80/EEE/999?text=ba"},
    {"id": 6, "username": "fitness_nova", "display_name": "Fitness Nova", "bio": "Personal trainer sharing workout wisdom", "avatar": "https://placehold.co/80x80/EEE/999?text=fn"},
    {"id": 7, "username": "retro_vinyl", "display_name": "Retro Vinyl", "bio": "Music nerd. Vinyl collector. Concert goer.", "avatar": "https://placehold.co/80x80/EEE/999?text=rv"},
    {"id": 8, "username": "green_thumb", "display_name": "Green Thumb", "bio": "Urban gardening in a tiny apartment", "avatar": "https://placehold.co/80x80/EEE/999?text=gt"},
]

_CATEGORIES = ["Technology", "Travel", "Food", "Art", "Books", "Fitness", "Music", "Lifestyle", "Photography", "Gaming"]

_TAGS_POOL = {
    "Technology": ["python", "javascript", "webdev", "linux", "open-source", "api", "tutorial", "debugging", "docker", "ai"],
    "Travel": ["backpacking", "budget-travel", "europe", "asia", "road-trip", "hostel-life", "solo-travel", "hiking", "beach", "culture"],
    "Food": ["recipe", "vegan", "baking", "meal-prep", "comfort-food", "street-food", "dessert", "quick-meals", "fermentation", "spicy"],
    "Art": ["digital-art", "illustration", "procreate", "color-theory", "fan-art", "commission", "tutorial", "sketchbook", "animation", "typography"],
    "Books": ["book-review", "sci-fi", "fantasy", "non-fiction", "classic", "tbr", "reading-list", "ya", "horror", "memoir"],
    "Fitness": ["workout", "running", "yoga", "strength-training", "nutrition", "recovery", "home-gym", "marathon", "flexibility", "hiit"],
    "Music": ["vinyl", "indie", "playlist", "album-review", "concert", "guitar", "synthwave", "lo-fi", "jazz", "punk"],
    "Lifestyle": ["minimalism", "productivity", "self-care", "journaling", "morning-routine", "budgeting", "mental-health", "diy", "organization", "habits"],
    "Photography": ["landscape", "portrait", "street-photography", "editing", "lightroom", "film", "golden-hour", "macro", "urban", "wildlife"],
    "Gaming": ["indie-game", "retro", "pc-gaming", "review", "walkthrough", "speedrun", "pixel-art", "rpg", "sandbox", "multiplayer"],
}

_POST_TEMPLATES = [
    ("So I Tried {thing} and Here's What Happened", "Let me tell you about the time I decided to try {thing}. It started as a random weekend experiment, but it turned into something I genuinely enjoy now. Here's the full story, the good parts and the embarrassing parts included.\n\nFirst off, I had zero experience with {thing}. Like, literally none. I watched a few YouTube videos, read some blog posts, and convinced myself that I was basically an expert already. Spoiler: I was not.\n\nThe first attempt was a disaster. I messed up the basics, spent way too long troubleshooting, and almost gave up. But something kept pulling me back. Maybe it was stubbornness, maybe curiosity.\n\nBy the third try, things started clicking. I found my rhythm, developed a little workflow, and actually started producing results I was proud of. The key was patience and not being afraid to fail spectacularly.\n\nIf you're thinking about getting into {thing}, my advice is: just start. Don't wait until you feel ready. You'll never feel ready. Dive in, make mistakes, and learn as you go."),
    ("{count} Tips for Better {topic}", "Alright friends, let's talk about {topic}. I've been doing this for a while now and I've picked up some tricks along the way. Here are my top {count} tips:\n\n1. Start with the basics. I know it sounds obvious, but so many people skip the fundamentals and wonder why they're struggling later.\n\n2. Consistency beats intensity. Showing up every day for 30 minutes is way more effective than one marathon session per week.\n\n3. Find a community. Whether it's online or IRL, having people who share your interest makes everything more fun and keeps you accountable.\n\n4. Document your progress. Take notes, photos, whatever. You'll be amazed looking back at how far you've come.\n\n5. Don't compare yourself to experts. Everyone started somewhere. Focus on YOUR journey.\n\nThese aren't groundbreaking revelations, but they work. Trust the process."),
    ("A Beginner's Guide to {subject}", "Hey everyone! I've been getting a lot of questions about {subject} lately, so I figured I'd put together a comprehensive beginner's guide. Whether you're completely new or just need a refresher, this post has you covered.\n\nLet's start with the absolute basics. {subject} might seem intimidating at first, but I promise it's more approachable than you think. The key is breaking it down into manageable pieces.\n\nStep 1: Understand why {subject} matters. Before diving into the how, it helps to know the why. {subject} has been gaining traction because it solves real problems that people face every day.\n\nStep 2: Gather your tools. You don't need anything fancy to get started. Most of what you need is either free or very affordable.\n\nStep 3: Follow a structured path. Random learning leads to random results. Pick one resource and stick with it until you've built a solid foundation.\n\nStep 4: Practice, practice, practice. Theory is great, but nothing beats hands-on experience.\n\nI'll be posting follow-up tutorials, so stay tuned!"),
    ("My {time_period} {activity} Journey", "It's been {time_period} since I started {activity}, and wow, what a ride it's been. I wanted to share my honest experience - the highs, the lows, and everything in between.\n\nWhen I first started, I had these grand visions of what {activity} would be like. Reality was... different. The learning curve was steeper than I expected, and there were days when I seriously questioned if this was for me.\n\nBut here's the thing about {activity} - once you push through that initial frustration, it becomes genuinely rewarding. Around the third week, I had my first real breakthrough moment. That feeling of accomplishment? Absolutely addictive.\n\nThe biggest challenges I faced were time management and staying motivated when progress felt slow. What helped was setting small, achievable goals instead of focusing on the big picture all the time.\n\nNow, {time_period} later, I can confidently say that starting {activity} was one of the best decisions I've made. It's changed how I think, how I spend my free time, and honestly, how I see myself.\n\nTo anyone on the fence - just go for it. Future you will thank present you."),
    ("Why Everyone Is Wrong About {controversial}", "Okay, hot take incoming. I've seen a lot of discourse about {controversial} lately, and I think most people are missing the point entirely. Let me explain.\n\nThe mainstream opinion is that {controversial} is straightforward - you're either for it or against it. But the reality is way more nuanced than that. There are legitimate arguments on both sides that deserve consideration.\n\nFirst, let's look at why people support it. They have valid reasons, and dismissing their perspective outright isn't productive. Understanding where they're coming from helps us have better conversations.\n\nOn the flip side, the criticism isn't unfounded either. There are real concerns that need to be addressed, and pretending they don't exist doesn't help anyone.\n\nMy take? The truth is somewhere in the middle. Instead of picking sides, maybe we should be asking better questions. What specific aspects work? What needs improvement? How can we make it better for everyone?\n\nI know this isn't the spicy take you might have been expecting, but nuance is underrated. Fight me in the comments."),
    ("Today I Learned: {fact}", "You know those moments when you learn something and your entire worldview shifts slightly? Had one of those today.\n\nSo I was reading about {fact}, and I went down the most incredible rabbit hole. Three hours and seventeen browser tabs later, here's what I discovered.\n\nThe basics: {fact} is one of those things that most people have heard of but few really understand. I certainly didn't before today.\n\nWhat blew my mind: the implications are way bigger than I initially thought. This connects to so many other things - history, science, everyday life. Once you see the connections, you can't unsee them.\n\nI've included some links below if you want to explore further. Fair warning: this rabbit hole is deep and fascinating. Don't say I didn't warn you.\n\nHave you encountered anything mind-blowing lately? Drop it in the comments - I'm always looking for new rabbit holes to fall into."),
    ("{topic} Changed My Life (Not Clickbait)", "I know the title sounds dramatic, but hear me out. I genuinely believe that getting into {topic} has had a transformative effect on my life, and I want to tell you why.\n\nBefore {topic}, I was in a rut. Same routine every day, no creative outlet, nothing to look forward to. Then a friend casually mentioned {topic}, and something clicked.\n\nThe first few weeks were exciting but chaotic. I was absorbing information like a sponge, spending every spare moment reading, watching, and experimenting. My friends probably thought I'd lost it.\n\nBut here's where it gets interesting. The skills and mindset I developed through {topic} started bleeding into other areas of my life. I became more patient, more curious, more willing to embrace failure as part of the learning process.\n\nSix months in, I'm a different person. Not in some dramatic movie-montage way, but in subtle, meaningful ways. I'm more confident, more creative, and genuinely happier.\n\nIf you're looking for that one thing that could shake up your routine, give {topic} a shot. It might just surprise you."),
    ("Unpopular Opinion: {opinion}", "Brace yourselves. This is going to be controversial.\n\n{opinion}. There, I said it. Now before you come at me with pitchforks, let me explain my reasoning.\n\nI've been thinking about this for a while, and the more I dig into it, the more I believe this is a conversation we need to have. Not because I want to be contrarian for the sake of it, but because I think the prevailing wisdom might be wrong.\n\nHere's my evidence. I've spent the last few months really examining this from every angle, and the data tells an interesting story that contradicts what most people assume.\n\nNow, I'm not saying I have all the answers. I could absolutely be wrong, and I'm open to having my mind changed. But I think it's important to challenge assumptions, even popular ones.\n\nWhat do you think? Am I completely off base here, or does this resonate with you too? Let's have a respectful conversation about it in the comments."),
]

_THINGS = ["sourdough baking", "mechanical keyboards", "bullet journaling", "cold showers", "intermittent fasting",
           "learning Rust", "film photography", "composting", "meditation", "speed cubing",
           "urban sketching", "thrift flipping", "mushroom foraging", "home brewing", "calligraphy"]
_TOPICS = ["Photography", "Cooking at Home", "Running", "Web Development", "Drawing",
           "Budgeting", "Morning Routines", "Writing Fiction", "Guitar Playing", "Indoor Plants",
           "Meal Prepping", "Yoga", "Podcast Production", "Watercolor Painting", "Home Organization"]
_SUBJECTS = ["CSS Grid Layout", "Sourdough Starters", "Film Photography", "Container Gardening",
             "Vinyl Record Care", "Meditation", "Python Decorators", "Espresso Making",
             "Watercolor Techniques", "Home Networking", "Fermentation", "Trail Running"]
_TIME_PERIODS = ["6 months", "1 year", "3 months", "100 days", "2 years"]
_ACTIVITIES = ["journaling", "running", "learning piano", "vegetable gardening", "digital illustration",
               "rock climbing", "home cooking", "weight training", "reading 50 books", "daily sketching"]
_CONTROVERSIALS = ["social media", "remote work", "AI art", "minimalism", "hustle culture",
                   "self-help books", "college degrees", "meal kits", "standing desks", "cold brew"]
_FACTS = ["how maps distort reality", "the history of color blue", "how fungi communicate",
          "the science of nostalgia", "why cats purr", "how music affects memory",
          "the origins of zero", "why we dream", "how languages die", "the psychology of fonts"]
_OPINIONS = ["Tabs are better than spaces and I will die on this hill",
             "Physical books are overrated for learning",
             "Morning routines are mostly performative",
             "You don't need a gym membership to get fit",
             "Most productivity advice is counterproductive",
             "Cooking from scratch every day is unsustainable",
             "Vinyl sounds worse than digital and that's okay",
             "Side projects don't need to become businesses"]

_COMMENT_TEMPLATES = [
    "This is so relatable! I had the exact same experience.",
    "Great post! I've been wanting to try this for a while.",
    "Bookmarking this for later. Such useful info.",
    "I disagree with point 3, but otherwise solid advice.",
    "Can you do a follow-up on this topic?",
    "This is the content I come here for. Thank you!",
    "I shared this with my friend who's into this stuff.",
    "Been doing this for years and can confirm - spot on.",
    "The part about consistency really hit home.",
    "Hot take but I think you're onto something here.",
    "I tried this last week and it actually worked!",
    "More posts like this please!",
    "Okay but the real question is - where do I start?",
    "This changed my perspective completely.",
    "Adding this to my reading list. Quality content.",
    "Your writing style is so engaging. Keep it up!",
    "I needed this today. Thanks for posting.",
    "The comments section is just as good as the post.",
    "I respectfully disagree but appreciate the nuance.",
    "This is way more helpful than most tutorials out there.",
]


def _synthesize_data():
    """Generate blog posts, users, and comments deterministically."""
    config = _load_config()
    n = config.get("num_data_points", 50)
    if n <= 0:
        n = 50
    seed = config.get("random_seed", 42)
    rng = random.Random(seed)

    # --- Users ---
    users = []
    for a in _AUTHORS:
        users.append({
            "id": a["id"],
            "username": a["username"],
            "password": f"pass{a['id']}23",
            "display_name": a["display_name"],
            "bio": a["bio"],
            "avatar": a["avatar"],
            "followed_blogs": [],
            "saved_posts": [],
            "subscribed_tags": [],
        })

    # --- Posts ---
    base_date = datetime(2025, 12, 1)
    posts = []
    for i in range(1, n + 1):
        template_title, template_body = rng.choice(_POST_TEMPLATES)
        author = rng.choice(_AUTHORS)
        category = rng.choice(_CATEGORIES)
        tags = rng.sample(_TAGS_POOL.get(category, ["general"]), min(3, len(_TAGS_POOL.get(category, ["general"]))))

        replacements = {
            "thing": rng.choice(_THINGS),
            "count": str(rng.choice([5, 7, 10])),
            "topic": rng.choice(_TOPICS),
            "subject": rng.choice(_SUBJECTS),
            "time_period": rng.choice(_TIME_PERIODS),
            "activity": rng.choice(_ACTIVITIES),
            "controversial": rng.choice(_CONTROVERSIALS),
            "fact": rng.choice(_FACTS),
            "opinion": rng.choice(_OPINIONS),
        }

        title = template_title
        body = template_body
        for key, val in replacements.items():
            title = title.replace("{" + key + "}", val)
            body = body.replace("{" + key + "}", val)

        days_ago = rng.randint(0, 365)
        post_date = base_date - timedelta(days=days_ago)
        has_image = rng.random() < 0.6
        image_url = f"https://placehold.co/600x400/EEE/999?text=post{i}" if has_image else None

        notes_count = rng.randint(0, 500)

        posts.append({
            "id": i,
            "title": title,
            "body": body,
            "author_id": author["id"],
            "author_username": author["username"],
            "author_display_name": author["display_name"],
            "author_avatar": author["avatar"],
            "category": category,
            "tags": tags,
            "image_url": image_url,
            "date": post_date.strftime("%Y-%m-%d"),
            "notes_count": notes_count,
            "is_pinned": i <= 2,
            "shared_count": rng.randint(0, 100),
        })

    posts.sort(key=lambda p: p["date"], reverse=True)
    for idx, p in enumerate(posts, 1):
        p["id"] = idx

    # --- Comments ---
    comments = []
    comment_id = 1
    for post in posts:
        num_comments = rng.randint(0, 8)
        for _ in range(num_comments):
            commenter = rng.choice(_AUTHORS)
            comment_date_offset = rng.randint(0, 30)
            cdate = datetime.strptime(post["date"], "%Y-%m-%d") + timedelta(days=comment_date_offset)
            comments.append({
                "id": comment_id,
                "post_id": post["id"],
                "author_username": commenter["username"],
                "author_display_name": commenter["display_name"],
                "body": rng.choice(_COMMENT_TEMPLATES),
                "date": cdate.strftime("%Y-%m-%d"),
            })
            comment_id += 1

    return posts, users, comments


def _ensure_data():
    """Write synthesized data to disk if not present."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not POSTS_FILE.exists():
        posts, users, comments = _synthesize_data()
        POSTS_FILE.write_text(json.dumps(posts, indent=2))
        USERS_FILE.write_text(json.dumps(users, indent=2))
        COMMENTS_FILE.write_text(json.dumps(comments, indent=2))
        REPORTS_FILE.write_text(json.dumps([], indent=2))
        # Create .pristine backup
        pristine = DATA_DIR / ".pristine"
        pristine.mkdir(exist_ok=True)
        for fname in ["posts.json", "users.json", "comments.json", "reports.json"]:
            shutil.copy2(DATA_DIR / fname, pristine / fname)


# ---------------------------------------------------------------------------
# Data access helpers
# ---------------------------------------------------------------------------

_posts_cache = None
_users_cache = None
_comments_cache = None


def _load_posts():
    _ensure_data()
    return json.loads(POSTS_FILE.read_text())


def _load_users():
    _ensure_data()
    return json.loads(USERS_FILE.read_text())


def _save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))


def _load_comments():
    _ensure_data()
    return json.loads(COMMENTS_FILE.read_text())


def _save_comments(comments):
    COMMENTS_FILE.write_text(json.dumps(comments, indent=2))


def _load_reports():
    _ensure_data()
    if REPORTS_FILE.exists():
        return json.loads(REPORTS_FILE.read_text())
    return []


def _save_reports(reports):
    REPORTS_FILE.write_text(json.dumps(reports, indent=2))


def _get_user(user_id):
    users = _load_users()
    return next((u for u in users if u["id"] == user_id), None)


# ---------------------------------------------------------------------------
# Search helpers
# ---------------------------------------------------------------------------

def _keyword_score(query, post):
    terms = query.lower().split()
    text = (post["title"] + " " + post["body"] + " " +
            post.get("author_username", "") + " " +
            post.get("category", "") + " " +
            " ".join(post.get("tags", []))).lower()
    return sum(1 for t in terms if t in text)


def _search_posts(posts, query, semantic=False):
    if not query:
        return posts
    q = query.lower().strip()
    if semantic:
        scored = [(p, _keyword_score(q, p)) for p in posts]
        scored = [(p, s) for p, s in scored if s > 0]
        scored.sort(key=lambda x: -x[1])
        return [p for p, _ in scored]
    else:
        return [p for p in posts if q in p["title"].lower() or
                q in p["body"].lower() or
                q in p.get("author_username", "").lower() or
                any(q in t.lower() for t in p.get("tags", []))]


# ---------------------------------------------------------------------------
# HTML routes
# ---------------------------------------------------------------------------

@blueprint.route("/")
def index():
    _ensure_data()
    posts = _load_posts()
    categories = sorted(set(p["category"] for p in posts))
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    tag = request.args.get("tag", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    author = request.args.get("author", "").strip()

    results = list(posts)

    if q:
        results = _search_posts(results, q)
    if cat:
        results = [p for p in results if p["category"] == cat]
    if tag:
        results = [p for p in results if tag in p.get("tags", [])]
    if author:
        results = [p for p in results if p["author_username"] == author]
    if date_from:
        results = [p for p in results if p["date"] >= date_from]
    if date_to:
        results = [p for p in results if p["date"] <= date_to]

    if sort == "date":
        results.sort(key=lambda p: p["date"], reverse=True)
    elif sort == "oldest":
        results.sort(key=lambda p: p["date"])
    elif sort == "popular":
        results.sort(key=lambda p: -p["notes_count"])
    elif sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))

    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])

    return render_template("blogs/index.html",
                           posts=results, categories=categories,
                           q=q, cat=cat, tag=tag, date_from=date_from,
                           date_to=date_to, sort=sort, author=author, user=user)


@blueprint.route("/post/<int:post_id>")
def post_detail(post_id):
    _ensure_data()
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        abort(404)
    comments = [c for c in _load_comments() if c["post_id"] == post_id]
    related = [p for p in posts if p["category"] == post["category"] and p["id"] != post_id][:5]
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/post.html", post=post, comments=comments,
                           related=related, user=user)


@blueprint.route("/category/<cat_name>")
def category_page(cat_name):
    _ensure_data()
    posts = _load_posts()
    filtered = [p for p in posts if p["category"] == cat_name]
    filtered.sort(key=lambda p: p["date"], reverse=True)
    categories = sorted(set(p["category"] for p in posts))
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/index.html", posts=filtered, categories=categories,
                           q="", cat=cat_name, tag="", date_from="", date_to="",
                           sort="date", author="", user=user)


@blueprint.route("/tag/<tag_name>")
def tag_page(tag_name):
    _ensure_data()
    posts = _load_posts()
    filtered = [p for p in posts if tag_name in p.get("tags", [])]
    filtered.sort(key=lambda p: p["date"], reverse=True)
    categories = sorted(set(p["category"] for p in posts))
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/index.html", posts=filtered, categories=categories,
                           q="", cat="", tag=tag_name, date_from="", date_to="",
                           sort="date", author="", user=user)


@blueprint.route("/dashboard")
def dashboard():
    _ensure_data()
    if "user_id" not in session:
        return render_template("blogs/login.html", error=None)
    user = _get_user(session["user_id"])
    if not user:
        return render_template("blogs/login.html", error=None)
    posts = _load_posts()
    saved = [p for p in posts if p["id"] in user.get("saved_posts", [])]
    my_posts = [p for p in posts if p["author_username"] == user["username"]]
    return render_template("blogs/dashboard.html", user=user,
                           saved_posts=saved, my_posts=my_posts)


@blueprint.route("/login", methods=["GET"])
def login_page():
    return render_template("blogs/login.html", error=None)


@blueprint.route("/login", methods=["POST"])
def login_submit():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "").strip()
    users = _load_users()
    user = next((u for u in users if u["username"] == username), None)
    if not user or user.get("password") != password:
        return render_template("blogs/login.html", error="Invalid username or password")
    session["user_id"] = user["id"]
    return redirect(url_for("blogs.dashboard"))


@blueprint.route("/logout")
def logout():
    session.pop("user_id", None)
    return render_template("blogs/login.html", error=None)


@blueprint.route("/compose", methods=["GET"])
def compose_page():
    _ensure_data()
    categories = _CATEGORIES
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/compose.html", categories=categories, user=user)


@blueprint.route("/report/<int:post_id>", methods=["GET"])
def report_page(post_id):
    _ensure_data()
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        abort(404)
    user = None
    if "user_id" in session:
        user = _get_user(session["user_id"])
    return render_template("blogs/report.html", post=post, user=user)


# ---------------------------------------------------------------------------
# API routes — read
# ---------------------------------------------------------------------------

@blueprint.route("/api/posts")
def api_posts():
    _ensure_data()
    posts = _load_posts()
    q = request.args.get("q", "").strip()
    cat = request.args.get("category", "").strip()
    tag = request.args.get("tag", "").strip()
    author = request.args.get("author", "").strip()
    date_from = request.args.get("date_from", "").strip()
    date_to = request.args.get("date_to", "").strip()
    sort = request.args.get("sort", "date").strip()
    limit = request.args.get("limit", type=int)

    results = list(posts)
    if q:
        results = _search_posts(results, q)
    if cat:
        results = [p for p in results if p["category"] == cat]
    if tag:
        results = [p for p in results if tag in p.get("tags", [])]
    if author:
        results = [p for p in results if p["author_username"] == author]
    if date_from:
        results = [p for p in results if p["date"] >= date_from]
    if date_to:
        results = [p for p in results if p["date"] <= date_to]
    if sort == "date":
        results.sort(key=lambda p: p["date"], reverse=True)
    elif sort == "oldest":
        results.sort(key=lambda p: p["date"])
    elif sort == "popular":
        results.sort(key=lambda p: -p["notes_count"])
    elif sort == "relevance" and q:
        results.sort(key=lambda p: -_keyword_score(q, p))
    if limit:
        results = results[:limit]
    return jsonify(results)


@blueprint.route("/api/posts/<int:post_id>")
def api_post(post_id):
    _ensure_data()
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if post is None:
        abort(404)
    return jsonify(post)


@blueprint.route("/api/posts/search")
def api_search():
    _ensure_data()
    q = request.args.get("q", "").strip()
    posts = _load_posts()
    return jsonify(_search_posts(posts, q))


@blueprint.route("/api/posts/semantic")
def api_semantic_search():
    _ensure_data()
    q = request.args.get("q", "").strip()
    posts = _load_posts()
    return jsonify(_search_posts(posts, q, semantic=True))


@blueprint.route("/api/categories")
def api_categories():
    _ensure_data()
    posts = _load_posts()
    from collections import Counter
    counts = Counter(p["category"] for p in posts)
    return jsonify([{"name": c, "count": n} for c, n in sorted(counts.items())])


@blueprint.route("/api/tags")
def api_tags():
    _ensure_data()
    posts = _load_posts()
    from collections import Counter
    tag_counts = Counter()
    for p in posts:
        for t in p.get("tags", []):
            tag_counts[t] += 1
    return jsonify([{"name": t, "count": n} for t, n in tag_counts.most_common()])


@blueprint.route("/api/posts/<int:post_id>/comments")
def api_post_comments(post_id):
    _ensure_data()
    comments = _load_comments()
    return jsonify([c for c in comments if c["post_id"] == post_id])


@blueprint.route("/api/authors")
def api_authors():
    _ensure_data()
    posts = _load_posts()
    from collections import Counter
    author_counts = Counter(p["author_username"] for p in posts)
    authors_info = {}
    for p in posts:
        if p["author_username"] not in authors_info:
            authors_info[p["author_username"]] = {
                "username": p["author_username"],
                "display_name": p["author_display_name"],
                "avatar": p["author_avatar"],
            }
    result = []
    for username, count in author_counts.most_common():
        info = authors_info[username]
        info["post_count"] = count
        result.append(info)
    return jsonify(result)


# ---------------------------------------------------------------------------
# API routes — write (mutable state)
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
    return jsonify({"user_id": user["id"], "username": user["username"]})


@blueprint.route("/api/users/<int:user_id>")
def api_user(user_id):
    _ensure_data()
    user = _get_user(user_id)
    if not user:
        abort(404)
    return jsonify({k: v for k, v in user.items() if k != "password"})


@blueprint.route("/api/users/<int:user_id>/save", methods=["POST"])
def api_save_post(user_id):
    data = request.get_json(silent=True) or {}
    post_id = data.get("post_id")
    if post_id is None:
        return jsonify({"error": "post_id required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    saved = user.setdefault("saved_posts", [])
    if post_id in saved:
        saved.remove(post_id)
        action = "unsaved"
    else:
        saved.append(post_id)
        action = "saved"
    _save_users(users)
    return jsonify({"action": action, "post_id": post_id, "total_saved": len(saved)})


@blueprint.route("/api/users/<int:user_id>/follow", methods=["POST"])
def api_follow_blog(user_id):
    data = request.get_json(silent=True) or {}
    blog = data.get("blog", "").strip()
    if not blog:
        return jsonify({"error": "blog username required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    followed = user.setdefault("followed_blogs", [])
    if blog in followed:
        followed.remove(blog)
        action = "unfollowed"
    else:
        followed.append(blog)
        action = "followed"
    _save_users(users)
    return jsonify({"action": action, "blog": blog, "total_followed": len(followed)})


@blueprint.route("/api/users/<int:user_id>/subscribe", methods=["POST"])
def api_subscribe_tag(user_id):
    data = request.get_json(silent=True) or {}
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"error": "tag required"}), 400
    users = _load_users()
    user = next((u for u in users if u["id"] == user_id), None)
    if not user:
        abort(404)
    subscribed = user.setdefault("subscribed_tags", [])
    if tag in subscribed:
        subscribed.remove(tag)
        action = "unsubscribed"
    else:
        subscribed.append(tag)
        action = "subscribed"
    _save_users(users)
    return jsonify({"action": action, "tag": tag, "total_subscribed": len(subscribed)})


@blueprint.route("/api/posts/<int:post_id>/share", methods=["POST"])
def api_share_post(post_id):
    data = request.get_json(silent=True) or {}
    platform = data.get("platform", "link").strip()
    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        abort(404)
    post["shared_count"] = post.get("shared_count", 0) + 1
    POSTS_FILE.write_text(json.dumps(posts, indent=2))
    return jsonify({
        "action": "shared",
        "post_id": post_id,
        "platform": platform,
        "share_url": f"/sites/blogs/post/{post_id}",
        "total_shares": post["shared_count"],
    })


@blueprint.route("/api/posts/create", methods=["POST"])
def api_create_post():
    _ensure_data()
    data = request.get_json(silent=True) or {}
    title = data.get("title", "").strip()
    body = data.get("body", "").strip()
    category = data.get("category", "Lifestyle").strip()
    tags = data.get("tags", [])
    author_username = data.get("author_username", "").strip()
    image_url = data.get("image_url", None)

    if not title or not body:
        return jsonify({"error": "title and body required"}), 400
    if not author_username:
        return jsonify({"error": "author_username required"}), 400

    users = _load_users()
    author = next((u for u in users if u["username"] == author_username), None)
    if not author:
        return jsonify({"error": "author not found"}), 404

    posts = _load_posts()
    new_id = max((p["id"] for p in posts), default=0) + 1

    new_post = {
        "id": new_id,
        "title": title,
        "body": body,
        "author_id": author["id"],
        "author_username": author["username"],
        "author_display_name": author["display_name"],
        "author_avatar": author["avatar"],
        "category": category,
        "tags": tags if isinstance(tags, list) else [tags],
        "image_url": image_url,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "notes_count": 0,
        "is_pinned": False,
        "shared_count": 0,
    }

    posts.insert(0, new_post)
    POSTS_FILE.write_text(json.dumps(posts, indent=2))
    return jsonify(new_post), 201


@blueprint.route("/api/posts/<int:post_id>/comment", methods=["POST"])
def api_add_comment(post_id):
    _ensure_data()
    data = request.get_json(silent=True) or {}
    body = data.get("body", "").strip()
    author_username = data.get("author_username", "").strip()

    if not body or not author_username:
        return jsonify({"error": "body and author_username required"}), 400

    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        abort(404)

    users = _load_users()
    author = next((u for u in users if u["username"] == author_username), None)
    if not author:
        return jsonify({"error": "author not found"}), 404

    comments = _load_comments()
    new_id = max((c["id"] for c in comments), default=0) + 1
    new_comment = {
        "id": new_id,
        "post_id": post_id,
        "author_username": author["username"],
        "author_display_name": author["display_name"],
        "body": body,
        "date": datetime.now().strftime("%Y-%m-%d"),
    }
    comments.append(new_comment)
    _save_comments(comments)
    return jsonify(new_comment), 201


@blueprint.route("/api/posts/<int:post_id>/report", methods=["POST"])
def api_report_post(post_id):
    _ensure_data()
    data = request.get_json(silent=True) or {}
    reason = data.get("reason", "").strip()
    details = data.get("details", "").strip()
    reporter = data.get("reporter_username", "anonymous").strip()

    if not reason:
        return jsonify({"error": "reason required"}), 400

    posts = _load_posts()
    post = next((p for p in posts if p["id"] == post_id), None)
    if not post:
        abort(404)

    reports = _load_reports()
    new_id = max((r["id"] for r in reports), default=0) + 1
    new_report = {
        "id": new_id,
        "post_id": post_id,
        "reporter_username": reporter,
        "reason": reason,
        "details": details,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "status": "pending",
    }
    reports.append(new_report)
    _save_reports(reports)
    return jsonify(new_report), 201


@blueprint.route("/api/reports")
def api_reports():
    _ensure_data()
    return jsonify(_load_reports())
