#!/usr/bin/env python3
"""
Fetch real article data from WikiNews (CC BY) and transform it into
the MiniWeb news site schema.

Produces: articles.json, categories.json, users.json, comments.json, reports.json
Output dir: sites/news/data/

WikiNews API docs: https://en.wikinews.org/w/api.php
"""

import json
import os
import random
import re
import sys
import time
import urllib.request
import urllib.parse
import urllib.error
from datetime import datetime, timedelta
from html import unescape
from pathlib import Path

WIKINEWS_API = "https://en.wikinews.org/w/api.php"
TARGET_ARTICLES = 200
OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "sites" / "news" / "data"

# ── Category mapping ────────────────────────────────────────────────────────
# Map WikiNews categories to our 8 site categories
CATEGORY_MAP = {
    "Politics and conflicts": "Politics",
    "Politics": "Politics",
    "Crime and law": "Politics",
    "Law": "Politics",
    "Elections": "Politics",
    "United States": "Politics",
    "Europe": "World",
    "Asia": "World",
    "Africa": "World",
    "South America": "World",
    "Middle East": "World",
    "Oceania": "World",
    "North America": "World",
    "International relations": "World",
    "Economy and business": "Business",
    "Economy": "Business",
    "Business": "Business",
    "Finance": "Business",
    "Science and technology": "Science",
    "Science": "Science",
    "Technology": "Technology",
    "Internet": "Technology",
    "Computing": "Technology",
    "Health": "Health",
    "Medicine": "Health",
    "Environment": "Science",
    "Weather": "Science",
    "Disasters and accidents": "World",
    "Sports": "Sports",
    "Football (soccer)": "Sports",
    "Cricket": "Sports",
    "Olympics": "Sports",
    "Basketball": "Sports",
    "Tennis": "Sports",
    "Culture and entertainment": "Entertainment",
    "Entertainment": "Entertainment",
    "Film": "Entertainment",
    "Music": "Entertainment",
    "Education": "Science",
    "Obituaries": "World",
}

SITE_CATEGORIES = [
    {"id": 1, "name": "Politics", "slug": "politics",
     "description": "Government, elections, policy, and law"},
    {"id": 2, "name": "Technology", "slug": "technology",
     "description": "Tech industry, gadgets, computing, and innovation"},
    {"id": 3, "name": "Business", "slug": "business",
     "description": "Markets, economy, and corporate news"},
    {"id": 4, "name": "Science", "slug": "science",
     "description": "Research, discoveries, environment, and space"},
    {"id": 5, "name": "Health", "slug": "health",
     "description": "Medicine, wellness, and public health"},
    {"id": 6, "name": "Sports", "slug": "sports",
     "description": "Professional and amateur athletics"},
    {"id": 7, "name": "Entertainment", "slug": "entertainment",
     "description": "Movies, music, TV, and celebrity news"},
    {"id": 8, "name": "World", "slug": "world",
     "description": "International affairs and global events"},
]

CATEGORY_NAMES = [c["name"] for c in SITE_CATEGORIES]

# Realistic author names for synthesizing authorship
AUTHORS = [
    "Maria Chen", "James Rodriguez", "Sarah Kim", "David Park",
    "Emily Watson", "Carlos Mendez", "Priya Sharma", "Alex Thompson",
    "Rachel Green", "Michael Foster",
]

SOURCES = [
    "DailyPulse Washington Bureau", "DailyPulse Tech Desk",
    "DailyPulse Finance", "DailyPulse Science", "DailyPulse World Desk",
    "DailyPulse Health", "DailyPulse Sports", "DailyPulse Entertainment",
    "DailyPulse Investigations", "DailyPulse Special Reports",
]

SUBCATEGORY_MAP = {
    "Politics": ["Legislation", "Elections", "Policy", "Government", "Diplomacy"],
    "Technology": ["Industry", "AI", "Cybersecurity", "Software", "Hardware"],
    "Business": ["Markets", "Economy", "Corporate", "Trade", "Startups"],
    "Science": ["Space", "Research", "Environment", "Climate", "Discovery"],
    "Health": ["Medicine", "Public Health", "Research", "Wellness", "Policy"],
    "Sports": ["Football", "Basketball", "Tennis", "Olympics", "Cricket"],
    "Entertainment": ["Film", "Music", "Television", "Celebrity", "Gaming"],
    "World": ["Conflict", "Diplomacy", "Humanitarian", "Regional", "Migration"],
}


def api_request(params, retries=3):
    """Make a request to the WikiNews API with retries."""
    params["format"] = "json"
    url = WIKINEWS_API + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "MiniWebDataPrep/1.0 (research; contact@example.com)"
            })
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (urllib.error.URLError, urllib.error.HTTPError, Exception) as e:
            print(f"  API request failed (attempt {attempt+1}/{retries}): {e}")
            if attempt < retries - 1:
                time.sleep(2 * (attempt + 1))
    return None


def fetch_published_titles(limit=500):
    """Fetch article titles from the Published category using continuation."""
    titles = []
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": "Category:Published",
        "cmlimit": "50",
        "cmnamespace": "0",
        "cmsort": "timestamp",
        "cmdir": "desc",
    }

    while len(titles) < limit:
        print(f"  Fetching published articles... ({len(titles)} so far)")
        data = api_request(params)
        if not data or "query" not in data:
            break

        for member in data["query"].get("categorymembers", []):
            titles.append(member["title"])

        if "continue" in data:
            params["cmcontinue"] = data["continue"]["cmcontinue"]
        else:
            break

        time.sleep(0.5)  # Be polite to the API

    return titles


def fetch_article_content(title):
    """Fetch parsed content and categories for a single article."""
    data = api_request({
        "action": "parse",
        "page": title,
        "prop": "text|categories|revid",
        "disabletoc": "true",
    })
    if not data or "parse" not in data:
        return None
    return data["parse"]


def strip_html(html_text):
    """Remove HTML tags and clean up text."""
    # Remove script/style
    text = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html_text, flags=re.DOTALL)
    # Remove tags
    text = re.sub(r'<[^>]+>', ' ', text)
    # Decode entities
    text = unescape(text)
    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    # Remove [edit] links and references
    text = re.sub(r'\[edit\]', '', text)
    text = re.sub(r'\[\d+\]', '', text)
    return text


def classify_article(wiki_categories, title):
    """Map WikiNews categories to our site categories."""
    for wc in wiki_categories:
        cat_name = wc.get("*", "")
        if cat_name in CATEGORY_MAP:
            return CATEGORY_MAP[cat_name]

    # Keyword-based fallback
    title_lower = title.lower()
    keyword_map = {
        "Politics": ["election", "president", "senate", "congress", "parliament",
                      "vote", "law", "court", "judge", "government", "minister",
                      "political", "democrat", "republican", "legislation", "bill",
                      "governor", "mayor", "policy"],
        "Technology": ["tech", "google", "apple", "microsoft", "software", "ai ",
                       "artificial intelligence", "computer", "cyber", "internet",
                       "app", "digital", "robot", "data", "hack"],
        "Business": ["stock", "market", "trade", "economic", "bank", "company",
                     "business", "profit", "revenue", "gdp", "inflation",
                     "unemployment", "merger", "acquisition"],
        "Science": ["scientist", "research", "study", "nasa", "space", "climate",
                    "environment", "species", "fossil", "planet", "earthquake",
                    "volcano", "discovery", "experiment"],
        "Health": ["health", "medical", "doctor", "hospital", "disease", "virus",
                   "vaccine", "cancer", "drug", "patient", "pandemic", "who",
                   "treatment", "surgery"],
        "Sports": ["football", "soccer", "basketball", "tennis", "olympic",
                   "championship", "tournament", "league", "match", "game",
                   "player", "coach", "team", "cricket", "rugby", "medal",
                   "world cup", "fifa"],
        "Entertainment": ["film", "movie", "music", "album", "award", "oscar",
                         "grammy", "actor", "actress", "celebrity", "show",
                         "concert", "festival", "broadway"],
        "World": ["war", "conflict", "refugee", "humanitarian", "united nations",
                  "earthquake", "tsunami", "flood", "hurricane", "disaster",
                  "attack", "bomb", "terror", "protest", "riot"],
    }

    best_cat = None
    best_score = 0
    for cat, keywords in keyword_map.items():
        score = sum(1 for kw in keywords if kw in title_lower)
        if score > best_score:
            best_score = score
            best_cat = cat

    return best_cat or random.choice(CATEGORY_NAMES)


def extract_tags(title, body, category):
    """Extract relevant tags from article content."""
    # Common tag keywords by category
    tag_pools = {
        "Politics": ["politics", "government", "legislation", "policy", "election",
                     "democracy", "congress", "senate"],
        "Technology": ["tech", "AI", "software", "innovation", "digital",
                      "cybersecurity", "internet", "computing"],
        "Business": ["markets", "economy", "trade", "finance", "corporate",
                    "stocks", "investment", "business"],
        "Science": ["research", "discovery", "climate", "space", "environment",
                   "science", "study", "NASA"],
        "Health": ["medicine", "health", "disease", "treatment", "vaccine",
                  "public health", "medical", "wellness"],
        "Sports": ["sports", "competition", "championship", "athletes",
                  "tournament", "league", "match", "team"],
        "Entertainment": ["entertainment", "film", "music", "culture",
                         "celebrity", "awards", "media", "art"],
        "World": ["international", "global", "conflict", "diplomacy",
                 "humanitarian", "UN", "crisis", "world"],
    }

    # Pick 3-5 tags: some from the pool, some from title words
    pool = tag_pools.get(category, ["news", "current events"])
    tags = random.sample(pool, min(2, len(pool)))

    # Extract significant words from title
    stop_words = {"the", "a", "an", "in", "on", "at", "to", "for", "of", "and",
                  "is", "are", "was", "were", "be", "been", "by", "with", "from",
                  "as", "or", "but", "not", "has", "have", "had", "its", "it",
                  "this", "that", "over", "after", "new", "says", "said"}
    title_words = [w.strip(".,!?:;'\"()") for w in title.split()
                   if len(w) > 3 and w.lower() not in stop_words]
    if title_words:
        tags.extend(random.sample(title_words, min(2, len(title_words))))

    return list(set(tags))[:5]


def make_slug(title):
    """Convert title to URL slug."""
    slug = title.lower()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug).strip('-')
    return slug[:80]


def generate_summary(body, max_len=200):
    """Extract first meaningful sentence(s) as summary."""
    if not body:
        return ""
    sentences = re.split(r'(?<=[.!?])\s+', body)
    summary = ""
    for s in sentences:
        if len(summary) + len(s) > max_len:
            break
        summary += s + " "
    return summary.strip() or body[:max_len]


def synthesize_users(authors):
    """Create synthetic user accounts."""
    users = [
        {
            "id": 1,
            "username": "jdoe_reader",
            "name": "John Doe",
            "email": "john.doe@example.com",
            "password_hash": "pbkdf2:sha256:260000$abc123$e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            "subscribed_categories": ["Politics", "Technology"],
            "saved_articles": [4, 9],
            "following_authors": [authors[0], authors[1]],
            "notification_preferences": {
                "breaking_news": True, "daily_digest": True, "comment_replies": True
            },
            "joined": "2024-01-15"
        },
        {
            "id": 2,
            "username": "sarah_news",
            "name": "Sarah Johnson",
            "email": "sarah.j@example.com",
            "password_hash": "pbkdf2:sha256:260000$def456$a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6",
            "subscribed_categories": ["Science", "Health"],
            "saved_articles": [5, 11, 14],
            "following_authors": [authors[3], authors[4]],
            "notification_preferences": {
                "breaking_news": True, "daily_digest": False, "comment_replies": True
            },
            "joined": "2024-03-22"
        },
        {
            "id": 3,
            "username": "techfan42",
            "name": "Marcus Lee",
            "email": "marcus.l@example.com",
            "password_hash": "pbkdf2:sha256:260000$ghi789$c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2",
            "subscribed_categories": ["Technology", "Business"],
            "saved_articles": [2, 8],
            "following_authors": [authors[1], authors[5]],
            "notification_preferences": {
                "breaking_news": False, "daily_digest": True, "comment_replies": True
            },
            "joined": "2024-05-10"
        },
        {
            "id": 4,
            "username": "world_watcher",
            "name": "Amara Okafor",
            "email": "amara.o@example.com",
            "password_hash": "pbkdf2:sha256:260000$jkl012$d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3",
            "subscribed_categories": ["World", "Politics"],
            "saved_articles": [16, 22],
            "following_authors": [authors[0], authors[6]],
            "notification_preferences": {
                "breaking_news": True, "daily_digest": True, "comment_replies": False
            },
            "joined": "2024-07-08"
        },
        {
            "id": 5,
            "username": "sports_daily",
            "name": "Kevin Walsh",
            "email": "kevin.w@example.com",
            "password_hash": "pbkdf2:sha256:260000$mno345$e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4e5f6a1b2c3d4",
            "subscribed_categories": ["Sports", "Entertainment"],
            "saved_articles": [6, 15],
            "following_authors": [authors[5], authors[7]],
            "notification_preferences": {
                "breaking_news": True, "daily_digest": False, "comment_replies": True
            },
            "joined": "2024-09-30"
        },
    ]
    return users


def synthesize_comments(articles, num_comments=60):
    """Generate realistic comments referencing actual article titles/topics."""
    comment_templates = [
        "Interesting article about {topic}. Worth following this story.",
        "This is significant news. The implications of {topic} are far-reaching.",
        "Thanks for the coverage on {topic}. More people need to be aware.",
        "I have concerns about {topic}. Hope to see follow-up reporting.",
        "Great journalism here. {topic} deserves more attention.",
        "Not sure I agree with the framing of {topic} in this piece.",
        "This changes everything regarding {topic}. What a development.",
        "Been following {topic} for a while. This is a major update.",
        "The data presented about {topic} is compelling.",
        "Would love to see a deeper dive into {topic}.",
        "This is why I read DailyPulse. Quality coverage of {topic}.",
        "How does {topic} affect ordinary citizens? Important question.",
        "Sharing this widely. Everyone should know about {topic}.",
        "The context provided here about {topic} is really helpful.",
        "Surprised this isn't getting more mainstream coverage. {topic} matters.",
    ]

    comments = []
    for i in range(num_comments):
        article = random.choice(articles[:50])  # Bias towards newer articles
        topic_words = article["title"].split()
        # Use a shortened topic reference
        topic = " ".join(topic_words[:min(6, len(topic_words))])

        template = random.choice(comment_templates)
        text = template.format(topic=topic)

        # Some comments are replies to earlier comments
        parent_id = None
        if comments and random.random() < 0.25:
            parent_candidates = [c for c in comments if c["article_id"] == article["id"]]
            if parent_candidates:
                parent_id = random.choice(parent_candidates)["id"]

        pub_date = article["published"]
        try:
            dt = datetime.strptime(pub_date, "%Y-%m-%d")
        except ValueError:
            dt = datetime.now() - timedelta(days=random.randint(1, 30))
        comment_dt = dt + timedelta(hours=random.randint(1, 48),
                                     minutes=random.randint(0, 59))

        comments.append({
            "id": i + 1,
            "article_id": article["id"],
            "user_id": random.randint(1, 5),
            "text": text,
            "created": comment_dt.strftime("%Y-%m-%dT%H:%M:%S"),
            "likes": random.randint(0, 50),
            "reported": random.random() < 0.03,
            "parent_id": parent_id,
        })

    return comments


def synthesize_reports(articles, comments):
    """Generate a few content reports."""
    reasons_article = [
        "Headline may be misleading about the actual facts",
        "Article contains potentially unverified claims",
        "Possible political bias in the reporting",
        "Source credibility is questionable",
        "Article may contain outdated information",
    ]
    reasons_comment = [
        "Potentially inflammatory language",
        "Possible misinformation in comment",
        "Comment appears to be spam",
    ]

    reports = []
    # 3 article reports
    for i in range(3):
        art = random.choice(articles[:30])
        reports.append({
            "id": i + 1,
            "content_type": "article",
            "content_id": art["id"],
            "reporter_id": random.randint(1, 5),
            "reason": reasons_article[i],
            "status": random.choice(["pending", "reviewed", "dismissed"]),
            "created": (datetime.now() - timedelta(days=random.randint(1, 20))).strftime("%Y-%m-%dT%H:%M:%S"),
        })
    # 2 comment reports
    for i in range(2):
        cmt = random.choice(comments[:20])
        reports.append({
            "id": i + 4,
            "content_type": "comment",
            "content_id": cmt["id"],
            "reporter_id": random.randint(1, 5),
            "reason": reasons_comment[i],
            "status": random.choice(["pending", "reviewed", "dismissed"]),
            "created": (datetime.now() - timedelta(days=random.randint(1, 15))).strftime("%Y-%m-%dT%H:%M:%S"),
        })

    return reports


def main():
    random.seed(42)
    print("=" * 60)
    print("WikiNews Data Preparation for MiniWeb News Site")
    print("=" * 60)

    # ── Step 1: Fetch article titles from WikiNews ──────────────────────
    print("\n[1/5] Fetching published article titles from WikiNews...")
    titles = fetch_published_titles(limit=TARGET_ARTICLES + 100)
    print(f"  Fetched {len(titles)} titles from WikiNews")

    if len(titles) < 50:
        print("  WARNING: Got fewer titles than expected. API may be slow.")

    # ── Step 2: Fetch content for each article ──────────────────────────
    print(f"\n[2/5] Fetching article content (targeting {TARGET_ARTICLES})...")
    raw_articles = []
    skipped = 0

    for i, title in enumerate(titles):
        if len(raw_articles) >= TARGET_ARTICLES:
            break

        if i % 20 == 0:
            print(f"  Processing {i+1}/{len(titles)} (got {len(raw_articles)} articles)...")

        content = fetch_article_content(title)
        if not content:
            skipped += 1
            continue

        # Extract text body
        html = content.get("text", {}).get("*", "")
        body = strip_html(html)

        # Skip very short or stub articles
        if len(body) < 100:
            skipped += 1
            continue

        # Trim overly long bodies
        if len(body) > 2000:
            # Cut at sentence boundary near 2000 chars
            cut_point = body.rfind('. ', 1500, 2000)
            if cut_point > 0:
                body = body[:cut_point + 1]
            else:
                body = body[:2000]

        # Get categories
        wiki_cats = content.get("categories", [])
        category = classify_article(wiki_cats, title)

        raw_articles.append({
            "title": title,
            "body": body,
            "wiki_categories": [c.get("*", "") for c in wiki_cats],
            "category": category,
        })

        time.sleep(0.3)  # Rate limiting

    print(f"  Collected {len(raw_articles)} articles, skipped {skipped}")

    # ── Step 3: Transform into site schema ──────────────────────────────
    print("\n[3/5] Transforming articles into site schema...")

    # Ensure balanced category distribution
    cat_counts = {c: 0 for c in CATEGORY_NAMES}
    for a in raw_articles:
        cat_counts[a["category"]] += 1
    print(f"  Category distribution: {dict(cat_counts)}")

    # If some categories are very sparse, reassign some from over-represented ones
    min_per_cat = max(5, len(raw_articles) // len(CATEGORY_NAMES) // 2)
    for a in raw_articles:
        if cat_counts[a["category"]] > min_per_cat * 4:
            # Find underrepresented category
            sparse = [c for c in CATEGORY_NAMES if cat_counts[c] < min_per_cat]
            if sparse:
                old_cat = a["category"]
                new_cat = random.choice(sparse)
                a["category"] = new_cat
                cat_counts[old_cat] -= 1
                cat_counts[new_cat] += 1

    # Assign authors with category affinity
    author_categories = {}
    for i, author in enumerate(AUTHORS):
        primary = CATEGORY_NAMES[i % len(CATEGORY_NAMES)]
        author_categories[author] = primary

    # Build articles list
    articles = []
    base_date = datetime(2025, 6, 15)

    for idx, raw in enumerate(raw_articles):
        article_id = idx + 1
        category = raw["category"]

        # Assign author with some category affinity
        preferred_authors = [a for a, c in author_categories.items() if c == category]
        if preferred_authors and random.random() < 0.6:
            author = random.choice(preferred_authors)
        else:
            author = random.choice(AUTHORS)

        # Stagger publication dates
        pub_date = base_date - timedelta(days=idx // 4, hours=random.randint(0, 12))
        pub_str = pub_date.strftime("%Y-%m-%d")

        subcategories = SUBCATEGORY_MAP.get(category, ["General"])
        subcategory = random.choice(subcategories)

        # Some articles have video
        has_video = random.random() < 0.15
        video_url = f"https://example.com/videos/{make_slug(raw['title'])}.mp4" if has_video else None
        video_duration = random.randint(120, 600) if has_video else None

        summary = generate_summary(raw["body"])
        tags = extract_tags(raw["title"], raw["body"], category)

        source_idx = CATEGORY_NAMES.index(category) if category in CATEGORY_NAMES else 0
        source = SOURCES[source_idx % len(SOURCES)]

        articles.append({
            "id": article_id,
            "title": raw["title"],
            "slug": make_slug(raw["title"]),
            "body": raw["body"],
            "summary": summary,
            "category": category,
            "subcategory": subcategory,
            "author": author,
            "published": pub_str,
            "updated": pub_str,
            "tags": tags,
            "image_url": "/static/img/placeholder.jpg",
            "video_url": video_url,
            "video_duration_sec": video_duration,
            "source": source,
            "view_count": random.randint(500, 50000),
            "comment_count": 0,  # Will be updated after comments
            "is_breaking": random.random() < 0.08,
            "is_featured": random.random() < 0.12,
        })

    # ── Step 4: Synthesize supporting data ──────────────────────────────
    print("\n[4/5] Synthesizing users, comments, and reports...")

    unique_authors = sorted(set(a["author"] for a in articles))
    users = synthesize_users(unique_authors)
    comments = synthesize_comments(articles, num_comments=60)
    reports = synthesize_reports(articles, comments)

    # Update article comment_count based on actual comments
    comment_counts = {}
    for c in comments:
        comment_counts[c["article_id"]] = comment_counts.get(c["article_id"], 0) + 1
    for a in articles:
        a["comment_count"] = comment_counts.get(a["id"], 0)

    # Update category article_count
    cat_article_counts = {}
    for a in articles:
        cat_article_counts[a["category"]] = cat_article_counts.get(a["category"], 0) + 1

    categories = []
    for sc in SITE_CATEGORIES:
        sc_copy = dict(sc)
        sc_copy["article_count"] = cat_article_counts.get(sc_copy["name"], 0)
        categories.append(sc_copy)

    # ── Step 5: Write output ────────────────────────────────────────────
    print(f"\n[5/5] Writing data files to {OUTPUT_DIR}/")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    def write_json(name, data):
        path = OUTPUT_DIR / name
        path.write_text(json.dumps(data, indent=4, ensure_ascii=False))
        print(f"  Wrote {name}: {len(data)} records")

    write_json("articles.json", articles)
    write_json("categories.json", categories)
    write_json("users.json", users)
    write_json("comments.json", comments)
    write_json("reports.json", reports)

    # Also update .pristine if it exists
    pristine_dir = OUTPUT_DIR / ".pristine"
    if pristine_dir.exists():
        print(f"\n  Updating .pristine snapshot...")
        for fname in ["articles.json", "categories.json", "users.json",
                       "comments.json", "reports.json"]:
            src = OUTPUT_DIR / fname
            dst = pristine_dir / fname
            dst.write_text(src.read_text())
            print(f"    Copied {fname} to .pristine/")

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Data preparation complete!")
    print(f"  Articles:   {len(articles)}")
    print(f"  Categories: {len(categories)}")
    print(f"  Users:      {len(users)}")
    print(f"  Comments:   {len(comments)}")
    print(f"  Reports:    {len(reports)}")
    print(f"\n  Category distribution:")
    for cat in categories:
        print(f"    {cat['name']:15s} {cat['article_count']:3d} articles")
    print(f"\n  Authors used: {len(unique_authors)}")
    print(f"  Articles with video: {sum(1 for a in articles if a['video_url'])}")
    print(f"  Breaking articles: {sum(1 for a in articles if a['is_breaking'])}")
    print(f"  Featured articles: {sum(1 for a in articles if a['is_featured'])}")
    print("=" * 60)


if __name__ == "__main__":
    main()
