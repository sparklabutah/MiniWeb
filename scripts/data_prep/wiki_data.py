#!/usr/bin/env python3
"""
Fetch real Wikipedia article data and prepare it for the MiniWeb wiki site.

Uses the Wikipedia API to get ~200 articles across varied topics, then
synthesizes users, edit history, and categories to match the wiki site schema.

Output: articles.json, categories.json, users.json, edit_history.json
"""

import json
import random
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

WIKI_API = "https://en.wikipedia.org/w/api.php"

OUTPUT_DIR = Path("/scratch/general/vast/u1653932/data_sources/wikis")

# Topic seeds for varied coverage
TOPIC_SEEDS = {
    "Science": {
        "subcategories": {
            "Biology": ["Photosynthesis", "DNA", "Evolution", "Mitochondria", "Cell biology",
                        "Genetics", "Ecology", "Biodiversity", "Virus", "Bacteria",
                        "Immune system", "Enzyme", "Protein", "Chromosome", "RNA"],
            "Physics": ["Quantum mechanics", "General relativity", "Thermodynamics",
                        "Electromagnetism", "Nuclear physics", "Dark matter", "Black hole",
                        "Particle physics", "Speed of light", "Higgs boson"],
            "Chemistry": ["Periodic table", "Chemical bond", "Organic chemistry",
                          "Electrochemistry", "Polymer", "Catalysis", "Acid", "Oxidation"],
            "Earth Science": ["Plate tectonics", "Volcano", "Earthquake", "Climate change",
                              "Ocean current", "Glacier", "Atmosphere", "Water cycle"],
        }
    },
    "History": {
        "subcategories": {
            "Ancient Civilizations": ["Ancient Egypt", "Roman Empire", "Ancient Greece",
                                       "Mesopotamia", "Indus Valley Civilisation", "Maya civilization",
                                       "Persian Empire", "Byzantine Empire"],
            "Modern History": ["French Revolution", "Industrial Revolution", "World War I",
                               "World War II", "Cold War", "Space Race", "Renaissance"],
            "Historical Figures": ["Alexander the Great", "Cleopatra", "Julius Caesar",
                                   "Napoleon", "Genghis Khan", "Leonardo da Vinci"],
        }
    },
    "Geography": {
        "subcategories": {
            "Countries": ["Japan", "Brazil", "Australia", "India", "Egypt",
                          "South Africa", "Canada", "Germany", "Mexico", "Indonesia"],
            "Natural Features": ["Amazon rainforest", "Great Barrier Reef", "Sahara",
                                 "Himalayas", "Nile", "Grand Canyon", "Mount Everest"],
            "Cities": ["Tokyo", "Paris", "New York City", "Cairo", "Mumbai",
                       "London", "Rome", "Sydney"],
        }
    },
    "Technology": {
        "subcategories": {
            "Computing": ["Artificial intelligence", "Machine learning", "Internet",
                          "World Wide Web", "Computer science", "Algorithm",
                          "Cloud computing", "Cybersecurity", "Programming language"],
            "Engineering": ["3D printing", "Robotics", "Renewable energy",
                            "Nuclear power", "Semiconductor", "Satellite"],
            "Digital Innovation": ["Blockchain", "Cryptocurrency", "Virtual reality",
                                    "5G", "Internet of things", "Quantum computing"],
        }
    },
    "Arts": {
        "subcategories": {
            "Visual Arts": ["Mona Lisa", "Impressionism", "Cubism", "Photography",
                            "Sculpture", "Renaissance art"],
            "Music": ["Classical music", "Jazz", "Rock music", "Symphony",
                      "Ludwig van Beethoven", "Johann Sebastian Bach"],
            "Literature": ["William Shakespeare", "Novel", "Poetry",
                           "Greek mythology", "Epic poetry", "Hamlet"],
        }
    },
    "Mathematics": {
        "subcategories": {
            "Pure Mathematics": ["Calculus", "Number theory", "Algebra",
                                 "Geometry", "Topology", "Set theory"],
            "Applied Mathematics": ["Statistics", "Probability", "Game theory",
                                    "Cryptography", "Linear algebra"],
            "Famous Problems": ["Riemann hypothesis", "Fermat's Last Theorem",
                                "Pythagorean theorem", "Pi"],
        }
    },
    "Philosophy": {
        "subcategories": {
            "Western Philosophy": ["Socrates", "Plato", "Aristotle", "Immanuel Kant",
                                   "Friedrich Nietzsche", "Existentialism", "Stoicism"],
            "Ethics": ["Utilitarianism", "Deontological ethics", "Virtue ethics",
                       "Social contract", "Free will"],
            "Eastern Philosophy": ["Buddhism", "Confucianism", "Taoism", "Zen"],
        }
    },
    "Medicine": {
        "subcategories": {
            "Diseases": ["Cancer", "Diabetes", "Malaria", "Tuberculosis",
                         "Alzheimer's disease", "HIV/AIDS"],
            "Medical Science": ["Vaccine", "Antibiotic", "Surgery", "CRISPR",
                                "Stem cell", "Neuroscience"],
            "Public Health": ["Epidemiology", "World Health Organization",
                              "Pandemic", "Mental health"],
        }
    },
}


def api_call(params, retries=5):
    """Make a Wikipedia API call with retries and exponential backoff."""
    params["format"] = "json"
    url = WIKI_API + "?" + urllib.parse.urlencode(params)
    for attempt in range(retries):
        try:
            req = urllib.request.Request(url, headers={
                "User-Agent": "MiniWebResearchBot/1.0 (https://github.com/miniweb; miniweb@example.org) Python/3"
            })
            with urllib.request.urlopen(req, timeout=20) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait = 5 * (2 ** attempt)  # 5, 10, 20, 40, 80 seconds
                print(f"    Rate limited, waiting {wait}s (attempt {attempt+1}/{retries})...")
                time.sleep(wait)
                continue
            if attempt < retries - 1:
                time.sleep(2 + attempt * 2)
                continue
            print(f"  WARN: API call failed after {retries} attempts: {e}")
            return None
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 + attempt * 2)
                continue
            print(f"  WARN: API call failed after {retries} attempts: {e}")
            return None


def fetch_articles_batch(titles):
    """Fetch detailed info for multiple articles in one API call (up to 20 titles)."""
    data = api_call({
        "action": "query",
        "titles": "|".join(titles),
        "prop": "extracts|categories|info",
        "exintro": "",
        "explaintext": "",
        "inprop": "url",
        "cllimit": "20",
        "redirects": "1",
    })
    if not data or "query" not in data:
        return {}

    results = {}
    # Build redirect map so we can match back to the original requested title
    redirect_map = {}
    for r in data["query"].get("redirects", []):
        redirect_map[r["to"]] = r["from"]
    normalized_map = {}
    for n in data["query"].get("normalized", []):
        normalized_map[n["to"]] = n["from"]

    pages = data["query"].get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1" or "missing" in page:
            continue
        extract = page.get("extract", "").strip()
        if not extract or len(extract) < 50:
            continue
        actual_title = page.get("title", "")
        cats = [c["title"].replace("Category:", "") for c in page.get("categories", [])]
        # Find the original requested title
        orig = actual_title
        if actual_title in redirect_map:
            orig = redirect_map[actual_title]
        if orig in normalized_map:
            orig = normalized_map[orig]

        results[orig] = {
            "title": actual_title,
            "extract": extract,
            "categories_raw": cats,
            "length": page.get("length", 0),
            "touched": page.get("touched", ""),
            "pageid": int(page_id),
        }
    return results


def fetch_article_revisions(title, limit=10):
    """Fetch recent revision history for an article."""
    data = api_call({
        "action": "query",
        "titles": title,
        "prop": "revisions",
        "rvlimit": str(limit),
        "rvprop": "timestamp|user|comment|size",
    })
    if not data or "query" not in data:
        return []

    pages = data["query"].get("pages", {})
    for page_id, page in pages.items():
        if page_id == "-1":
            return []
        return page.get("revisions", [])
    return []


def make_slug(title):
    """Create a URL-friendly slug from a title."""
    return title.lower().replace(" ", "-").replace("'", "").replace(",", "")


def generate_infobox(title, extract, category, subcategory):
    """Generate an infobox from article data."""
    infobox = {"type": subcategory or category}

    # Extract some facts from the intro text
    sentences = extract.split(". ")
    if len(sentences) > 0:
        infobox["description"] = sentences[0].strip()[:200]

    # Add category-specific fields
    if category == "Science":
        infobox["field"] = subcategory
        infobox["discipline"] = category
    elif category == "History":
        infobox["period"] = subcategory
        infobox["subject_type"] = "Historical"
    elif category == "Geography":
        infobox["region_type"] = subcategory
        infobox["subject"] = title
    elif category == "Technology":
        infobox["domain"] = subcategory
        infobox["innovation_type"] = "Technology"
    elif category == "Arts":
        infobox["art_form"] = subcategory
        infobox["medium"] = subcategory
    elif category == "Mathematics":
        infobox["branch"] = subcategory
        infobox["field"] = "Mathematics"
    elif category == "Philosophy":
        infobox["tradition"] = subcategory
        infobox["discipline"] = "Philosophy"
    elif category == "Medicine":
        infobox["medical_field"] = subcategory
        infobox["discipline"] = "Medical Science"

    # Word count of extract
    word_count = len(extract.split())
    infobox["word_count"] = word_count

    return infobox


def generate_references(title, category):
    """Generate plausible references for an article."""
    refs = []
    base_refs = [
        {"title": f"Encyclopedia Britannica: {title}", "author": "Britannica Editors",
         "year": random.randint(2018, 2024),
         "url": f"https://www.britannica.com/topic/{make_slug(title)}"},
        {"title": f"{title} - A Comprehensive Overview", "author": "Academic Press",
         "year": random.randint(2015, 2023),
         "url": f"https://doi.org/10.1000/{random.randint(10000,99999)}"},
    ]
    refs.extend(base_refs)

    # Add category-specific references
    cat_refs = {
        "Science": {"title": "Nature", "url": "https://www.nature.com"},
        "Technology": {"title": "IEEE Spectrum", "url": "https://spectrum.ieee.org"},
        "History": {"title": "Journal of World History", "url": "https://www.jstor.org"},
        "Geography": {"title": "National Geographic", "url": "https://www.nationalgeographic.com"},
        "Arts": {"title": "The Art Newspaper", "url": "https://www.theartnewspaper.com"},
        "Mathematics": {"title": "Annals of Mathematics", "url": "https://annals.math.princeton.edu"},
        "Philosophy": {"title": "Stanford Encyclopedia of Philosophy", "url": "https://plato.stanford.edu"},
        "Medicine": {"title": "The Lancet", "url": "https://www.thelancet.com"},
    }
    if category in cat_refs:
        ref = cat_refs[category]
        refs.append({
            "title": f"{ref['title']}: {title}",
            "author": f"{ref['title']} Editorial Board",
            "year": random.randint(2019, 2024),
            "url": ref["url"],
        })
    return refs


def main():
    random.seed(42)

    print("=== MiniWeb Wiki Data Preparation ===")
    print(f"Output directory: {OUTPUT_DIR}")
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Collect all topic titles with their assigned categories
    topic_queue = []  # (title, category, subcategory)
    for category, cat_data in TOPIC_SEEDS.items():
        for subcat, titles in cat_data["subcategories"].items():
            for title in titles:
                topic_queue.append((title, category, subcat))

    random.shuffle(topic_queue)
    # Limit to ~200 but keep variety
    # First ensure we get some from each category
    selected = []
    by_cat = {}
    for t, c, s in topic_queue:
        by_cat.setdefault(c, []).append((t, c, s))

    # Take up to 25 per category to aim for ~200 total
    for cat, items in by_cat.items():
        selected.extend(items[:25])

    print(f"\nWill attempt to fetch {len(selected)} articles across {len(by_cat)} categories")

    # Fetch article details in batches of 10
    articles = []
    article_id = 0
    failed = 0
    BATCH_SIZE = 10

    # Build lookup from title to (category, subcategory)
    title_meta = {title: (cat, subcat) for title, cat, subcat in selected}

    for batch_start in range(0, len(selected), BATCH_SIZE):
        batch = selected[batch_start:batch_start + BATCH_SIZE]
        batch_titles = [t for t, c, s in batch]
        batch_end = min(batch_start + BATCH_SIZE, len(selected))
        print(f"  Fetching batch {batch_start+1}-{batch_end} of {len(selected)}...")

        results = fetch_articles_batch(batch_titles)

        for title, category, subcategory in batch:
            detail = results.get(title)
            if not detail:
                failed += 1
                continue

            article_id += 1
            extract = detail["extract"]

            # Generate view count
            view_count = random.randint(500, 50000)

            # Generate dates
            created_date = datetime(2024, 1, 1) + timedelta(days=random.randint(0, 365))
            last_edited = created_date + timedelta(days=random.randint(1, 180))
            if last_edited > datetime(2025, 6, 1):
                last_edited = datetime(2025, 6, 1)

            article = {
                "id": article_id,
                "title": detail["title"],
                "slug": make_slug(detail["title"]),
                "content": extract,
                "summary": ". ".join(extract.split(". ")[:2]).strip() + "." if ". " in extract else extract[:200],
                "category": category,
                "subcategory": subcategory,
                "author": "",  # Will be assigned after users are created
                "created": created_date.strftime("%Y-%m-%d"),
                "last_edited": last_edited.strftime("%Y-%m-%d"),
                "view_count": view_count,
                "tags": [t.lower() for t in detail["categories_raw"][:5]] if detail["categories_raw"] else [category.lower(), subcategory.lower()],
                "infobox": generate_infobox(detail["title"], extract, category, subcategory),
                "references": generate_references(detail["title"], category),
                "related_articles": [],  # Will be filled in later
            }
            articles.append(article)

        # Rate limiting between batches - generous delay
        time.sleep(2)

    print(f"\n  Fetched {len(articles)} articles ({failed} failed)")

    # ---- Synthesize Users (editors) ----
    usernames = [
        ("dr_greenfield", "Dr. Sarah Greenfield", "admin"),
        ("prof_wave", "Prof. James Wave", "editor"),
        ("historian_rex", "Rex Martinez", "editor"),
        ("tech_writer", "Aisha Patel", "editor"),
        ("philosopher_k", "Klaus Richter", "contributor"),
        ("bio_coder", "Dr. Mei Chen", "editor"),
        ("atlas_nav", "Carlos Rivera", "contributor"),
        ("art_sage", "Isabelle Dupont", "editor"),
        ("math_mind", "Dr. Raj Patel", "contributor"),
        ("med_scholar", "Dr. Emma Larsson", "editor"),
        ("quantum_q", "Yuki Tanaka", "contributor"),
        ("earth_scribe", "Nadia Okonkwo", "contributor"),
    ]

    # Assign user specialties to categories
    user_specialties = {
        1: ["Science"],
        2: ["Science", "Mathematics"],
        3: ["History"],
        4: ["Technology"],
        5: ["Philosophy"],
        6: ["Science", "Technology"],
        7: ["Geography"],
        8: ["Arts"],
        9: ["Mathematics"],
        10: ["Medicine"],
        11: ["Science", "Technology"],
        12: ["Geography", "Science"],
    }

    users = []
    for uid, (uname, name, role) in enumerate(usernames, 1):
        users.append({
            "id": uid,
            "username": uname,
            "name": name,
            "email": f"{uname}@openknowledge.org",
            "role": role,
            "contributions": [],
            "watchlist": [],
        })

    # Assign authors to articles based on specialty
    for article in articles:
        cat = article["category"]
        # Find users who specialize in this category
        candidates = [uid for uid, specs in user_specialties.items() if cat in specs]
        if not candidates:
            candidates = list(range(1, len(users) + 1))
        chosen_uid = random.choice(candidates)
        article["author"] = users[chosen_uid - 1]["username"]
        users[chosen_uid - 1]["contributions"].append(article["id"])

    # Assign watchlists
    for user in users:
        n_watch = random.randint(3, 8)
        available = [a["id"] for a in articles if a["id"] not in user["contributions"]]
        user["watchlist"] = random.sample(available, min(n_watch, len(available)))

    # ---- Assign Related Articles ----
    # Group by category/subcategory for relatedness
    by_subcat = {}
    for a in articles:
        key = (a["category"], a["subcategory"])
        by_subcat.setdefault(key, []).append(a["id"])

    for article in articles:
        key = (article["category"], article["subcategory"])
        same_subcat = [aid for aid in by_subcat[key] if aid != article["id"]]
        # Also pick some from same category but different subcategory
        same_cat = [a["id"] for a in articles
                    if a["category"] == article["category"]
                    and a["subcategory"] != article["subcategory"]
                    and a["id"] != article["id"]]
        related_pool = same_subcat + random.sample(same_cat, min(2, len(same_cat)))
        article["related_articles"] = random.sample(related_pool, min(4, len(related_pool)))

    # ---- Build Categories ----
    cat_counts = {}
    for a in articles:
        cat_counts[a["category"]] = cat_counts.get(a["category"], 0) + 1

    categories = []
    for cid, (cat_name, cat_data) in enumerate(TOPIC_SEEDS.items(), 1):
        categories.append({
            "id": cid,
            "name": cat_name,
            "description": f"Articles about {cat_name.lower()} topics",
            "parent_id": None,
            "article_count": cat_counts.get(cat_name, 0),
        })

    # Update descriptions to be more specific
    cat_descriptions = {
        "Science": "Articles about natural sciences, physics, chemistry, and biology",
        "Technology": "Articles about computing, engineering, and digital innovation",
        "History": "Articles about historical events, periods, and civilizations",
        "Geography": "Articles about countries, cities, landforms, and natural features",
        "Arts": "Articles about visual arts, music, literature, and performing arts",
        "Mathematics": "Articles about mathematical concepts, theorems, and fields",
        "Philosophy": "Articles about philosophical traditions, thinkers, and concepts",
        "Medicine": "Articles about medical science, diseases, and health",
    }
    for cat in categories:
        if cat["name"] in cat_descriptions:
            cat["description"] = cat_descriptions[cat["name"]]

    # ---- Build Edit History ----
    edit_history = []
    edit_id = 0

    edit_summaries_by_cat = {
        "Science": [
            "Updated experimental data with latest findings",
            "Added recent research citations",
            "Corrected formula notation",
            "Expanded methodology section",
            "Added diagram descriptions",
            "Updated statistics to latest published figures",
        ],
        "Technology": [
            "Updated version numbers and release dates",
            "Added security considerations section",
            "Expanded comparison with alternatives",
            "Updated market adoption statistics",
            "Added industry standard references",
        ],
        "History": [
            "Added primary source citations",
            "Expanded timeline with key dates",
            "Corrected date attributions",
            "Added archaeological evidence details",
            "Updated with recent historical discoveries",
        ],
        "Geography": [
            "Updated population statistics",
            "Added climate data section",
            "Updated economic indicators",
            "Expanded cultural section",
            "Added recent census data",
        ],
        "Arts": [
            "Added exhibition history",
            "Updated provenance information",
            "Expanded influence section",
            "Added contemporary reception details",
            "Updated museum collection information",
        ],
        "Mathematics": [
            "Clarified proof steps",
            "Added visual proof illustration description",
            "Expanded applications section",
            "Added computational complexity notes",
            "Updated with recent proof developments",
        ],
        "Philosophy": [
            "Added contemporary interpretation",
            "Expanded primary source quotations",
            "Added cross-references to related schools",
            "Updated with recent scholarship",
            "Clarified key terminology definitions",
        ],
        "Medicine": [
            "Updated WHO statistics",
            "Added latest clinical trial results",
            "Expanded treatment options section",
            "Updated drug approval information",
            "Added epidemiological data",
        ],
    }

    for article in articles:
        # Each article gets 1-5 edits
        n_edits = random.randint(1, 5)
        cat = article["category"]
        summaries = edit_summaries_by_cat.get(cat, ["General update"])

        # Find users who could edit this
        cat_specialists = [uid for uid, specs in user_specialties.items() if cat in specs]
        all_users = list(range(1, len(users) + 1))

        for _ in range(n_edits):
            edit_id += 1
            # Prefer specialists but allow anyone
            if random.random() < 0.7 and cat_specialists:
                editor_id = random.choice(cat_specialists)
            else:
                editor_id = random.choice(all_users)

            # Edit timestamp between article creation and last_edited
            created_dt = datetime.strptime(article["created"], "%Y-%m-%d")
            edited_dt = datetime.strptime(article["last_edited"], "%Y-%m-%d")
            delta = (edited_dt - created_dt).days
            if delta <= 0:
                delta = 1
            edit_day = created_dt + timedelta(days=random.randint(0, delta))
            edit_time = edit_day.replace(
                hour=random.randint(8, 20),
                minute=random.randint(0, 59),
                second=random.randint(0, 59),
            )

            edit_history.append({
                "id": edit_id,
                "article_id": article["id"],
                "user_id": editor_id,
                "timestamp": edit_time.strftime("%Y-%m-%dT%H:%M:%S"),
                "summary": random.choice(summaries),
                "diff_size": random.randint(50, 800),
            })

    # Sort edit history by timestamp
    edit_history.sort(key=lambda h: h["timestamp"])
    # Re-assign sequential IDs after sorting
    for i, h in enumerate(edit_history, 1):
        h["id"] = i

    # ---- Print Summary ----
    print(f"\n=== Data Summary ===")
    print(f"Articles: {len(articles)}")
    print(f"Categories: {len(categories)}")
    print(f"Users: {len(users)}")
    print(f"Edit history entries: {len(edit_history)}")
    print(f"\nArticles per category:")
    for cat in categories:
        print(f"  {cat['name']}: {cat['article_count']}")

    # ---- Write Output ----
    def write_json(name, data):
        path = OUTPUT_DIR / name
        path.write_text(json.dumps(data, indent=4, ensure_ascii=False))
        print(f"  Wrote {path} ({len(data)} records)")

    print(f"\nWriting output files to {OUTPUT_DIR}...")
    write_json("articles.json", articles)
    write_json("categories.json", categories)
    write_json("users.json", users)
    write_json("edit_history.json", edit_history)

    # Also update .pristine if it exists
    pristine_dir = OUTPUT_DIR / ".pristine"
    if pristine_dir.exists():
        print(f"\nUpdating .pristine snapshot...")
        for name in ["articles.json", "categories.json", "users.json", "edit_history.json"]:
            src = OUTPUT_DIR / name
            dst = pristine_dir / name
            dst.write_text(src.read_text())
            print(f"  Copied to {dst}")

    print("\nDone!")


if __name__ == "__main__":
    main()
