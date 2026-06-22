#!/usr/bin/env python3
"""
Data preparation script for the qa-knowledge MiniWeb site.

Fetches real data from the Stack Exchange API (Stack Overflow) and transforms
it into the JSON format expected by the qa-knowledge site routes.

Stack Exchange API docs: https://api.stackexchange.com/docs

No authentication needed for basic read access.
API responses are gzip-compressed by default.
"""

import gzip
import io
import json
import pathlib
import random
import time
import urllib.request
from datetime import datetime, timedelta

# ── Config ───────────────────────────────────────────────────────────────────

SITE_DATA_DIR = pathlib.Path(__file__).resolve().parent.parent.parent / "sites" / "qa-knowledge" / "data"
PRISTINE_DIR = SITE_DATA_DIR / ".pristine"

BASE_URL = "https://api.stackexchange.com/2.3"

# Tags to fetch questions for (varied programming topics)
TAGS_TO_FETCH = [
    "python", "javascript", "java", "c#", "css",
    "html", "react", "node.js", "sql", "git",
    "docker", "linux", "typescript", "postgresql", "aws",
]

# Map SO tags to our topic categories
TAG_TO_CATEGORY = {
    "python": "Programming",
    "java": "Programming",
    "c#": "Programming",
    "c++": "Programming",
    "typescript": "Programming",
    "javascript": "Web Development",
    "css": "Web Development",
    "html": "Web Development",
    "react": "Web Development",
    "reactjs": "Web Development",
    "node.js": "Web Development",
    "angular": "Web Development",
    "vue.js": "Web Development",
    "sql": "Data Science",
    "postgresql": "Data Science",
    "mysql": "Data Science",
    "mongodb": "Data Science",
    "pandas": "Data Science",
    "machine-learning": "Data Science",
    "docker": "DevOps",
    "linux": "DevOps",
    "aws": "Cloud Computing",
    "azure": "Cloud Computing",
    "git": "DevOps",
    "kubernetes": "DevOps",
    "security": "Security",
    "authentication": "Security",
    "encryption": "Security",
    "algorithm": "Algorithms",
    "data-structures": "Algorithms",
    "sorting": "Algorithms",
    "ios": "Mobile Development",
    "android": "Mobile Development",
    "flutter": "Mobile Development",
    "react-native": "Mobile Development",
    "system-design": "System Design",
    "design-patterns": "System Design",
    "scalability": "System Design",
}

# Our site topics (must match topics.json IDs)
CATEGORY_TO_TOPIC_ID = {
    "Web Development": 1,
    "DevOps": 2,
    "Programming": 3,
    "Security": 4,
    "Algorithms": 5,
    "Data Science": 6,
    "Cloud Computing": 7,
    "Mobile Development": 8,
    "System Design": 9,
    "Career & Learning": 10,
}


def api_request(endpoint, params=None):
    """Make a request to the Stack Exchange API with gzip handling."""
    url = f"{BASE_URL}{endpoint}"
    if params:
        query = "&".join(f"{k}={v}" for k, v in params.items())
        url = f"{url}?{query}"

    req = urllib.request.Request(url)
    req.add_header("Accept-Encoding", "gzip")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.headers.get("Content-Encoding") == "gzip":
                buf = io.BytesIO(resp.read())
                with gzip.GzipFile(fileobj=buf) as f:
                    data = json.loads(f.read().decode("utf-8"))
            else:
                data = json.loads(resp.read().decode("utf-8"))

        quota = data.get("quota_remaining", "?")
        print(f"  API quota remaining: {quota}")
        if data.get("backoff"):
            wait = data["backoff"]
            print(f"  Backoff requested: {wait}s")
            time.sleep(wait)
        return data
    except Exception as e:
        print(f"  API error for {url}: {e}")
        return None


def fetch_questions_for_tag(tag, page=1, pagesize=20):
    """Fetch top-voted questions for a specific tag."""
    params = {
        "order": "desc",
        "sort": "votes",
        "site": "stackoverflow",
        "tagged": tag,
        "pagesize": str(pagesize),
        "page": str(page),
        "filter": "withbody",
    }
    return api_request("/questions", params)


def fetch_answers_for_questions(question_ids):
    """Fetch answers for a batch of question IDs (up to 100 per call)."""
    ids_str = ";".join(str(qid) for qid in question_ids)
    params = {
        "order": "desc",
        "sort": "votes",
        "site": "stackoverflow",
        "pagesize": "100",
        "filter": "withbody",
    }
    return api_request(f"/questions/{ids_str}/answers", params)


def fetch_top_users(pagesize=50):
    """Fetch top SO users by reputation."""
    params = {
        "order": "desc",
        "sort": "reputation",
        "site": "stackoverflow",
        "pagesize": str(pagesize),
    }
    return api_request("/users", params)


def classify_category(tags):
    """Map a list of SO tags to one of our site categories."""
    for tag in tags:
        tag_lower = tag.lower()
        if tag_lower in TAG_TO_CATEGORY:
            return TAG_TO_CATEGORY[tag_lower]
    return "Programming"  # default


def strip_html(html_str):
    """Crude HTML tag removal for body text."""
    import re
    text = re.sub(r"<code>.*?</code>", "", html_str, flags=re.DOTALL)
    text = re.sub(r"<pre>.*?</pre>", "", text, flags=re.DOTALL)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"&lt;", "<", text)
    text = re.sub(r"&gt;", ">", text)
    text = re.sub(r"&amp;", "&", text)
    text = re.sub(r"&quot;", '"', text)
    text = re.sub(r"&#39;", "'", text)
    text = re.sub(r"\s+", " ", text).strip()
    # Truncate to reasonable length
    if len(text) > 600:
        text = text[:597] + "..."
    return text


def generate_date_in_range():
    """Generate a random date in the last ~6 months."""
    days_ago = random.randint(1, 180)
    dt = datetime.now() - timedelta(days=days_ago)
    return dt.strftime("%Y-%m-%d")


def main():
    print("=" * 60)
    print("QA-Knowledge Data Preparation Script")
    print("Fetching real Stack Overflow data via Stack Exchange API")
    print("=" * 60)

    all_raw_questions = []
    seen_ids = set()

    # ── Step 1: Fetch questions across varied tags ───────────────────────
    for tag in TAGS_TO_FETCH:
        print(f"\nFetching top questions for tag: {tag}")
        data = fetch_questions_for_tag(tag, pagesize=15)
        if data and "items" in data:
            for item in data["items"]:
                if item["question_id"] not in seen_ids:
                    seen_ids.add(item["question_id"])
                    all_raw_questions.append(item)
            print(f"  Got {len(data['items'])} questions ({len(all_raw_questions)} total unique)")
        else:
            print(f"  No data returned for tag: {tag}")

        # Rate limiting - be polite to the API
        time.sleep(1.5)

    print(f"\nTotal unique questions fetched: {len(all_raw_questions)}")

    # Sort by score descending, take up to 200
    all_raw_questions.sort(key=lambda q: q.get("score", 0), reverse=True)
    selected_questions = all_raw_questions[:200]

    # Deduplicate by keeping first occurrence per SO question_id
    print(f"Selected top {len(selected_questions)} questions by votes")

    # ── Step 2: Fetch answers for a subset of questions ──────────────────
    print("\nFetching answers for top questions...")
    # Get answers for the top 50 questions (to get good answer data)
    so_ids_for_answers = [q["question_id"] for q in selected_questions[:50]]
    all_raw_answers = []

    # API allows up to 100 IDs per request - batch by 30
    for i in range(0, len(so_ids_for_answers), 30):
        batch = so_ids_for_answers[i:i+30]
        print(f"  Fetching answers for questions {i+1}-{i+len(batch)}...")
        data = fetch_answers_for_questions(batch)
        if data and "items" in data:
            all_raw_answers.extend(data["items"])
            print(f"    Got {len(data['items'])} answers ({len(all_raw_answers)} total)")
        time.sleep(2)

    print(f"Total answers fetched: {len(all_raw_answers)}")

    # ── Step 3: Fetch top users for realistic user patterns ──────────────
    print("\nFetching top Stack Overflow users...")
    user_data = fetch_top_users(pagesize=50)
    raw_users = user_data.get("items", []) if user_data else []
    print(f"  Got {len(raw_users)} users")

    # ── Step 4: Transform data into site format ──────────────────────────
    print("\nTransforming data...")

    # --- Users ---
    # Synthesize 8 users based on real SO user patterns
    user_patterns = [
        ("dev_sarah", "Sarah Chen", "Full-stack developer with 8 years of experience. Passionate about clean code and web performance."),
        ("code_master_raj", "Raj Patel", "Backend engineer specializing in Python and distributed systems."),
        ("linux_lisa", "Lisa Nguyen", "DevOps engineer and Linux enthusiast. Loves automation and container orchestration."),
        ("algo_alex", "Alex Romero", "Computer science graduate student researching algorithm optimization and graph theory."),
        ("js_ninja_mike", "Mike Johnson", "JavaScript developer and open-source contributor. React and Node.js advocate."),
        ("data_diana", "Diana Kowalski", "Data scientist working with ML pipelines, NLP, and big data technologies."),
        ("secdev_omar", "Omar Hassan", "Application security engineer focused on secure coding practices and penetration testing."),
        ("cloud_kelly", "Kelly Zhang", "Cloud architect with AWS and GCP certifications. Serverless computing advocate."),
    ]

    # Pull reputation values from real SO users if available
    rep_values = sorted(
        [u.get("reputation", 1000) for u in raw_users[:20]],
        reverse=True
    ) if raw_users else [50000, 40000, 30000, 25000, 20000, 15000, 10000, 5000]

    # Scale down reputation to reasonable forum levels (divide by ~100)
    scaled_reps = [max(500, int(r / 100)) for r in rep_values[:8]]
    # If we didn't get enough, pad
    while len(scaled_reps) < 8:
        scaled_reps.append(random.randint(500, 3000))

    users = []
    join_dates = [
        "2024-06-15", "2024-07-20", "2024-05-10", "2024-08-01",
        "2024-09-12", "2024-10-05", "2024-04-20", "2024-11-01",
    ]

    for i, (username, name, bio) in enumerate(user_patterns):
        users.append({
            "id": i + 1,
            "username": username,
            "name": name,
            "email": f"{username.replace('_', '.')}@example.com",
            "password_hash": f"pbkdf2:sha256:{username.split('_')[0]}{''.join(str(random.randint(0,9)) for _ in range(3))}",
            "reputation": scaled_reps[i],
            "joined": join_dates[i],
            "questions_asked": 0,  # Will be updated
            "answers_given": 0,    # Will be updated
            "following_topics": random.sample(range(1, 11), random.randint(2, 4)),
            "following_users": [x for x in random.sample(range(1, 9), random.randint(1, 3)) if x != i + 1],
            "saved_questions": [],  # Will be updated
            "bio": bio,
        })

    # --- Questions ---
    questions = []
    question_so_to_local = {}  # Map SO question_id to local ID

    for idx, raw_q in enumerate(selected_questions):
        local_id = idx + 1
        so_qid = raw_q["question_id"]
        question_so_to_local[so_qid] = local_id

        tags = raw_q.get("tags", [])[:5]  # Keep up to 5 tags
        category = classify_category(tags)
        author_id = random.randint(1, 8)

        # Use real title, strip HTML from body
        title = raw_q.get("title", f"Question {local_id}")
        body = strip_html(raw_q.get("body", ""))
        if not body or len(body) < 20:
            body = f"I have a question about {title.lower()}. Can anyone help with this?"

        created = generate_date_in_range()
        updated = created

        questions.append({
            "id": local_id,
            "title": title,
            "body": body,
            "author_id": author_id,
            "category": category,
            "tags": tags,
            "created": created,
            "updated": updated,
            "vote_count": raw_q.get("score", 0),
            "view_count": raw_q.get("view_count", 0),
            "answer_count": 0,  # Will be updated from actual answers
            "is_resolved": False,  # Will be updated
            "accepted_answer_id": None,  # Will be updated
            "_so_id": so_qid,  # Temporary, removed later
        })

    # --- Answers ---
    answers = []
    answer_id = 1

    # Group raw answers by question
    answers_by_so_qid = {}
    for raw_a in all_raw_answers:
        so_qid = raw_a.get("question_id")
        if so_qid not in answers_by_so_qid:
            answers_by_so_qid[so_qid] = []
        answers_by_so_qid[so_qid].append(raw_a)

    # Sort answers within each question by score
    for so_qid in answers_by_so_qid:
        answers_by_so_qid[so_qid].sort(key=lambda a: a.get("score", 0), reverse=True)

    for so_qid, raw_answers in answers_by_so_qid.items():
        if so_qid not in question_so_to_local:
            continue
        local_qid = question_so_to_local[so_qid]
        question = next(q for q in questions if q["id"] == local_qid)

        # Take up to 3 answers per question
        for i, raw_a in enumerate(raw_answers[:3]):
            body = strip_html(raw_a.get("body", ""))
            if not body or len(body) < 20:
                continue

            is_accepted = raw_a.get("is_accepted", False)
            author_id = random.randint(1, 8)
            # Avoid same author as question
            while author_id == question["author_id"]:
                author_id = random.randint(1, 8)

            answers.append({
                "id": answer_id,
                "question_id": local_qid,
                "author_id": author_id,
                "body": body,
                "created": question["created"],
                "vote_count": raw_a.get("score", 0),
                "is_accepted": is_accepted,
            })

            if is_accepted:
                question["accepted_answer_id"] = answer_id
                question["is_resolved"] = True

            answer_id += 1

    # For questions without real answers, generate some synthetic answers
    # for questions that would logically have answers (high vote count)
    questions_with_answers = {a["question_id"] for a in answers}
    for q in questions:
        if q["id"] not in questions_with_answers and q["vote_count"] > 50:
            author_id = random.randint(1, 8)
            while author_id == q["author_id"]:
                author_id = random.randint(1, 8)
            answers.append({
                "id": answer_id,
                "question_id": q["id"],
                "author_id": author_id,
                "body": f"This is a well-known topic. For {q['tags'][0] if q['tags'] else 'this'}, "
                        f"the recommended approach involves understanding the core concepts first. "
                        f"Check the official documentation for the most up-to-date guidance.",
                "created": q["created"],
                "vote_count": random.randint(5, 30),
                "is_accepted": False,
            })
            answer_id += 1

    # Update answer counts on questions
    for q in questions:
        q["answer_count"] = sum(1 for a in answers if a["question_id"] == q["id"])

    # Ensure some questions without answers exist (for "unanswered" filter)
    # Already natural from the data

    # Mark some high-answer questions as resolved if they have accepted
    for q in questions:
        if q["accepted_answer_id"] is not None:
            q["is_resolved"] = True

    # Also mark some additional questions as resolved (about 40%)
    unresolved_with_answers = [
        q for q in questions
        if not q["is_resolved"] and q["answer_count"] > 0
    ]
    for q in random.sample(unresolved_with_answers, min(len(unresolved_with_answers), len(questions) // 5)):
        # Pick the highest-voted answer for this question
        q_answers = sorted(
            [a for a in answers if a["question_id"] == q["id"]],
            key=lambda a: a["vote_count"],
            reverse=True,
        )
        if q_answers:
            q_answers[0]["is_accepted"] = True
            q["accepted_answer_id"] = q_answers[0]["id"]
            q["is_resolved"] = True

    # Clean up temporary fields
    for q in questions:
        del q["_so_id"]

    # Update user stats
    for u in users:
        u["questions_asked"] = sum(1 for q in questions if q["author_id"] == u["id"])
        u["answers_given"] = sum(1 for a in answers if a["author_id"] == u["id"])
        # Save a few random questions
        u["saved_questions"] = random.sample(
            range(1, len(questions) + 1),
            min(random.randint(2, 5), len(questions)),
        )

    # --- Topics ---
    topics = [
        {"id": 1, "name": "Web Development", "description": "Frontend and backend web technologies, frameworks, and best practices", "question_count": 0, "follower_count": 245},
        {"id": 2, "name": "DevOps", "description": "CI/CD, containerization, cloud deployment, and infrastructure automation", "question_count": 0, "follower_count": 189},
        {"id": 3, "name": "Programming", "description": "General programming concepts, languages, and software engineering", "question_count": 0, "follower_count": 312},
        {"id": 4, "name": "Security", "description": "Application security, authentication, encryption, and vulnerability prevention", "question_count": 0, "follower_count": 167},
        {"id": 5, "name": "Algorithms", "description": "Data structures, algorithms, complexity analysis, and design patterns", "question_count": 0, "follower_count": 198},
        {"id": 6, "name": "Data Science", "description": "Machine learning, data analysis, databases, and statistical methods", "question_count": 0, "follower_count": 221},
        {"id": 7, "name": "Cloud Computing", "description": "AWS, GCP, Azure services, serverless architecture, and cloud-native design", "question_count": 0, "follower_count": 156},
        {"id": 8, "name": "Mobile Development", "description": "iOS, Android, React Native, Flutter, and cross-platform mobile apps", "question_count": 0, "follower_count": 134},
        {"id": 9, "name": "System Design", "description": "Scalable architecture, distributed systems, and infrastructure planning", "question_count": 0, "follower_count": 178},
        {"id": 10, "name": "Career & Learning", "description": "Career advice, learning paths, interview preparation, and professional growth", "question_count": 0, "follower_count": 143},
    ]

    # Update topic question counts
    for t in topics:
        t["question_count"] = sum(1 for q in questions if q["category"] == t["name"])

    # --- Reports ---
    # Keep existing reports but update content_ids to valid question IDs
    max_qid = len(questions)
    reports = [
        {"id": 1, "content_type": "question", "content_id": min(7, max_qid), "reporter_id": 6, "reason": "The question body contains a link to a suspicious external site that may be phishing.", "status": "pending", "created": "2025-11-15"},
        {"id": 2, "content_type": "answer", "content_id": min(14, len(answers)), "reporter_id": 3, "reason": "This answer contains outdated information that could be misleading.", "status": "reviewed", "created": "2025-11-16"},
        {"id": 3, "content_type": "question", "content_id": min(21, max_qid), "reporter_id": 8, "reason": "Duplicate question - this has already been asked and answered.", "status": "pending", "created": "2025-11-25"},
        {"id": 4, "content_type": "answer", "content_id": min(39, len(answers)), "reporter_id": 5, "reason": "The answer is incomplete and may mislead beginners.", "status": "dismissed", "created": "2025-11-27"},
        {"id": 5, "content_type": "question", "content_id": min(25, max_qid), "reporter_id": 7, "reason": "This reads more like an opinion poll than a technical question. Should be marked as discussion.", "status": "pending", "created": "2025-11-29"},
    ]

    # ── Step 5: Write output files ───────────────────────────────────────
    print("\n" + "=" * 60)
    print("Writing output files...")

    output = {
        "questions.json": questions,
        "answers.json": answers,
        "users.json": users,
        "topics.json": topics,
        "reports.json": reports,
    }

    for filename, data in output.items():
        filepath = SITE_DATA_DIR / filename
        filepath.write_text(json.dumps(data, indent=4))
        print(f"  {filepath}: {len(data)} records")

    # Also write to pristine directory
    print("\nWriting pristine copies...")
    PRISTINE_DIR.mkdir(parents=True, exist_ok=True)
    for filename, data in output.items():
        filepath = PRISTINE_DIR / filename
        filepath.write_text(json.dumps(data, indent=4))
        print(f"  {filepath}: {len(data)} records")

    # ── Summary ──────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("Summary:")
    print(f"  Questions: {len(questions)}")
    print(f"  Answers:   {len(answers)}")
    print(f"  Users:     {len(users)}")
    print(f"  Topics:    {len(topics)}")
    print(f"  Reports:   {len(reports)}")

    resolved = sum(1 for q in questions if q["is_resolved"])
    print(f"\n  Resolved questions: {resolved}/{len(questions)}")
    print(f"  Questions with answers: {len(questions_with_answers)}/{len(questions)}")

    cats = {}
    for q in questions:
        cats[q["category"]] = cats.get(q["category"], 0) + 1
    print("\n  Category distribution:")
    for cat, count in sorted(cats.items(), key=lambda x: x[1], reverse=True):
        print(f"    {cat}: {count}")

    tag_counts = {}
    for q in questions:
        for t in q["tags"]:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:10]
    print("\n  Top 10 tags:")
    for tag, count in top_tags:
        print(f"    {tag}: {count}")

    print("\n  Vote range: {} to {}".format(
        min(q["vote_count"] for q in questions),
        max(q["vote_count"] for q in questions),
    ))
    print("  View range: {} to {}".format(
        min(q["view_count"] for q in questions),
        max(q["view_count"] for q in questions),
    ))

    print("\nDone!")


if __name__ == "__main__":
    main()
