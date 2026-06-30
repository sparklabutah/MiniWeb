#!/usr/bin/env python3
"""
Generate realistic MOOC / language-learning data for the MiniWeb
moocs-language-learning site.

Outputs:
  - courses.json   (~200 courses)
  - users.json     (15 users with enrollments, carts, wishlists, progress)
  - reviews.json   (~60-80 reviews)
  - discussions.json (~15 discussion threads with replies)

All IDs are integers. Schema matches the existing gold-standard data exactly.
"""

import json
import random
import pathlib
from datetime import datetime, timedelta

random.seed(42)

DATA_DIR = pathlib.Path("/scratch/general/vast/u1653932/data_sources/moocs-language-learning")
PRISTINE_DIR = DATA_DIR / ".pristine"

# ── Language / Category / Instructor pools ──────────────────────────────────

LANGUAGE_INFO = {
    # language: (category, [instructors])
    "Spanish": ("Romance Languages", [
        "Maria Garcia", "Carlos Mendez", "Isabella Torres", "Pablo Ruiz",
        "Elena Navarro", "Diego Castillo"
    ]),
    "French": ("Romance Languages", [
        "Pierre Dubois", "Sophie Martin", "Jean-Luc Bernard", "Amelie Fontaine",
        "Nicolas Leroy"
    ]),
    "German": ("Germanic Languages", [
        "Klaus Mueller", "Hannah Braun", "Thomas Schneider", "Petra Fischer"
    ]),
    "Japanese": ("East Asian Languages", [
        "Yuki Tanaka", "Haruto Sato", "Akiko Yamamoto", "Kenji Mori"
    ]),
    "Mandarin": ("East Asian Languages", [
        "Wei Zhang", "Li Wei", "Mei Lin", "Jian Chen", "Xiao Huang"
    ]),
    "Korean": ("East Asian Languages", [
        "Soo-Jin Park", "Min-Jun Kim", "Hye-Won Lee", "Dong-Hyun Choi"
    ]),
    "Italian": ("Romance Languages", [
        "Lucia Romano", "Giuseppe Verdi Jr.", "Marco Bianchi", "Francesca Ricci"
    ]),
    "Portuguese": ("Romance Languages", [
        "Ana Silva", "Rafael Costa", "Beatriz Ferreira"
    ]),
    "Arabic": ("Semitic Languages", [
        "Omar Hassan", "Fatima Al-Rashid", "Youssef Mansour", "Layla Ibrahim"
    ]),
    "Hindi": ("Indo-Aryan Languages", [
        "Priya Sharma", "Arjun Patel", "Kavita Desai", "Vikram Singh"
    ]),
    "Russian": ("Slavic Languages", [
        "Natasha Ivanova", "Dmitri Volkov", "Anya Petrova"
    ]),
    "Turkish": ("Turkic Languages", [
        "Elif Yilmaz", "Ahmet Kaya", "Zeynep Demir"
    ]),
    "Dutch": ("Germanic Languages", [
        "Jan de Vries", "Marloes Bakker"
    ]),
    "Swedish": ("Germanic Languages", [
        "Anna Lindstrom", "Lars Eriksson"
    ]),
    "Norwegian": ("Germanic Languages", [
        "Erik Johansen", "Solveig Haugen"
    ]),
    "Greek": ("Hellenic Languages", [
        "Nikos Papadopoulos", "Eleni Alexiou"
    ]),
    "Polish": ("Slavic Languages", [
        "Katarzyna Nowak", "Marek Kowalczyk"
    ]),
    "Vietnamese": ("Austroasiatic Languages", [
        "Linh Nguyen", "Tuan Pham"
    ]),
    "Thai": ("Tai Languages", [
        "Somchai Rattana", "Ploy Siriwan"
    ]),
    "Hebrew": ("Semitic Languages", [
        "Miriam Levi", "Avi Cohen"
    ]),
    "Indonesian": ("Austronesian Languages", [
        "Budi Santoso", "Siti Rahayu"
    ]),
    "Tagalog": ("Austronesian Languages", [
        "Maria Santos", "Jose Reyes"
    ]),
    "Persian": ("Iranian Languages", [
        "Reza Ahmadi", "Shirin Hosseini"
    ]),
    "Swahili": ("Bantu Languages", [
        "Amina Juma", "Joseph Mwangi"
    ]),
    "Welsh": ("Celtic Languages", [
        "Rhys Davies", "Carys Evans"
    ]),
    "Esperanto": ("Constructed Languages", [
        "Luka Novak", "Emma Schmidt"
    ]),
    "Latin": ("Classical Languages", [
        "Dr. James Crawford", "Dr. Helen Foster"
    ]),
    "Cantonese": ("East Asian Languages", [
        "Wing Ho Chan", "Mei Ling Lau"
    ]),
    "ASL": ("Sign Languages", [
        "David Chen", "Sarah Miller"
    ]),
    "Ukrainian": ("Slavic Languages", [
        "Oksana Kovalenko", "Taras Shevchenko"
    ]),
    "Czech": ("Slavic Languages", [
        "Petra Novakova", "Jakub Dvorak"
    ]),
    "Romanian": ("Romance Languages", [
        "Elena Popescu", "Andrei Ionescu"
    ]),
    "Danish": ("Germanic Languages", [
        "Mads Andersen", "Ida Sorensen"
    ]),
    "Finnish": ("Uralic Languages", [
        "Aino Virtanen", "Mikko Korhonen"
    ]),
    "Hungarian": ("Uralic Languages", [
        "Eszter Nagy", "Gabor Toth"
    ]),
}

LEVELS = ["Beginner", "Intermediate", "Advanced"]

# Course-title templates per level
TITLE_TEMPLATES = {
    "Beginner": [
        "{lang} for Beginners",
        "{lang} Complete Beginner",
        "Introduction to {lang}",
        "{lang} A1-A2",
        "{lang} Foundations",
        "{lang} From Zero",
        "Start Speaking {lang}",
        "{lang} for Travelers",
        "{lang} Crash Course",
        "Essential {lang}",
        "{lang} First Steps",
        "{lang}: Your First 100 Words",
    ],
    "Intermediate": [
        "{lang} Conversation Mastery",
        "{lang} Intermediate Grammar",
        "{lang} B1-B2",
        "{lang} Reading & Comprehension",
        "{lang} Through Culture",
        "{lang} Listening Skills",
        "Fluent {lang} Conversations",
        "{lang} Media & News",
        "{lang} Writing Workshop",
        "{lang} Intermediate Immersion",
    ],
    "Advanced": [
        "{lang} Advanced Grammar",
        "{lang} for Business",
        "{lang} Literature & Poetry",
        "{lang} Advanced Composition",
        "{lang} Exam Preparation",
        "{lang} Professional Communication",
        "{lang} Academic Writing",
        "Mastering {lang}",
        "{lang} C1-C2",
        "{lang} for Professionals",
    ],
}

DESCRIPTION_TEMPLATES = {
    "Beginner": [
        "Start your {lang} journey with conversational basics, grammar fundamentals, and cultural insights.",
        "Build a solid {lang} foundation with structured lessons covering essential vocabulary and grammar patterns.",
        "Learn {lang} from scratch with practical dialogues, pronunciation drills, and everyday phrases.",
        "A comprehensive introduction to {lang} covering the alphabet, basic grammar, and survival phrases.",
        "Master the fundamentals of {lang} with interactive exercises, audio practice, and cultural context.",
        "Begin speaking {lang} from day one with our immersive, communication-first approach.",
    ],
    "Intermediate": [
        "Elevate your {lang} skills with real-world dialogues, idioms, and advanced pronunciation practice.",
        "Bridge the gap between basic and fluent {lang} with structured conversation and grammar deepening.",
        "Expand your {lang} vocabulary and tackle complex grammar while exploring authentic media content.",
        "Strengthen your {lang} reading, writing, and listening skills through engaging cultural topics.",
        "Take your {lang} to the next level with intensive practice in all four language skills.",
    ],
    "Advanced": [
        "Deep-dive into complex {lang} structures for near-native fluency and professional competence.",
        "Professional {lang} for the workplace: emails, presentations, negotiations, and formal correspondence.",
        "Master the nuances of {lang} through literature, academic texts, and sophisticated discourse.",
        "Prepare for advanced {lang} certification exams with comprehensive practice and expert guidance.",
        "Refine your {lang} to a professional level with advanced grammar, style, and register awareness.",
    ],
}

TAG_POOL = {
    "Beginner": [
        "basics", "grammar", "vocabulary", "pronunciation", "alphabet", "phrases",
        "travel", "culture", "conversational", "script", "tones", "flashcards",
        "listening", "speaking", "reading", "writing", "a1", "a2", "survival",
        "introduction", "easy", "communication", "daily-life", "food",
    ],
    "Intermediate": [
        "conversation", "idioms", "grammar", "reading", "writing", "listening",
        "culture", "media", "news", "vocabulary", "b1", "b2", "fluency",
        "pronunciation", "cinema", "literature", "exam-prep", "practice",
        "immersion", "debate", "storytelling",
    ],
    "Advanced": [
        "advanced", "grammar", "business", "professional", "writing", "academic",
        "literature", "poetry", "formal", "c1", "c2", "exam-prep", "composition",
        "negotiation", "translation", "interpreting", "register", "style",
    ],
}

# ── Helper functions ────────────────────────────────────────────────────────

def _random_date(start_str="2023-01-01", end_str="2025-06-01"):
    start = datetime.strptime(start_str, "%Y-%m-%d")
    end = datetime.strptime(end_str, "%Y-%m-%d")
    delta = (end - start).days
    return (start + timedelta(days=random.randint(0, delta))).strftime("%Y-%m-%d")


def _pick_tags(level, n=3):
    return random.sample(TAG_POOL[level], min(n, len(TAG_POOL[level])))


# ── Generate courses ────────────────────────────────────────────────────────

def generate_courses(target=200):
    courses = []
    used_titles = set()
    course_id = 1

    # Ensure broad coverage: every language gets at least 3 courses (one per level)
    language_list = list(LANGUAGE_INFO.keys())
    random.shuffle(language_list)

    # Phase 1: one course per (language, level) combo to guarantee coverage
    for lang in language_list:
        cat, instructors = LANGUAGE_INFO[lang]
        for level in LEVELS:
            if course_id > target:
                break
            templates = TITLE_TEMPLATES[level]
            title = None
            random.shuffle(templates)
            for t in templates:
                candidate = t.format(lang=lang)
                if candidate not in used_titles:
                    title = candidate
                    break
            if title is None:
                title = f"{lang} {level} Course"
            if title in used_titles:
                title = f"{lang} {level} Course {course_id}"
            used_titles.add(title)

            instructor = random.choice(instructors)
            desc_templates = DESCRIPTION_TEMPLATES[level]
            description = random.choice(desc_templates).format(lang=lang)

            num_lessons = random.choice(range(10, 50, 2))
            duration = int(num_lessons * random.uniform(1.2, 2.5))
            # Some free courses
            if random.random() < 0.06:
                price = 0.00
            else:
                base = {"Beginner": 34.99, "Intermediate": 44.99, "Advanced": 59.99}
                price = round(base[level] + random.uniform(-15, 35), 2)
                price = max(9.99, price)

            rating = round(random.uniform(3.5, 5.0), 1)
            rating = min(rating, 5.0)
            num_reviews = random.randint(80, 5000)
            enrolled = random.randint(num_reviews, num_reviews * 8)

            courses.append({
                "id": course_id,
                "title": title,
                "language": lang,
                "level": level,
                "category": cat,
                "instructor": instructor,
                "price": price,
                "rating": rating,
                "num_reviews": num_reviews,
                "duration_hours": duration,
                "num_lessons": num_lessons,
                "enrolled": enrolled,
                "description": description,
                "tags": _pick_tags(level),
                "created": _random_date(),
            })
            course_id += 1

    # Phase 2: fill remaining slots with extra courses for popular languages
    popular_langs = [
        "Spanish", "French", "German", "Japanese", "Mandarin", "Korean",
        "Italian", "Portuguese", "Arabic", "Hindi", "Russian",
    ]
    # Additional specialty templates
    specialty_titles = [
        "{lang} for Healthcare Workers",
        "{lang} Pronunciation Clinic",
        "{lang} Grammar Bootcamp",
        "{lang} Through Music",
        "{lang} Through Cooking",
        "{lang} for Kids (Parent Guide)",
        "{lang} News & Media",
        "{lang} Test Preparation",
        "{lang} Vocabulary Builder",
        "{lang} Debate & Discussion",
        "{lang} Storytelling",
        "{lang} for Science & Tech",
        "{lang} Slang & Informal Speech",
        "{lang} for Diplomats",
        "{lang} Accent Reduction",
        "{lang} Poetry & Song",
        "{lang} for Hospitality",
        "{lang} Writing Masterclass",
        "{lang} Phonetics Deep Dive",
        "{lang} Cultural Immersion",
    ]

    while course_id <= target:
        lang = random.choice(popular_langs if random.random() < 0.7 else language_list)
        cat, instructors = LANGUAGE_INFO[lang]
        level = random.choice(LEVELS)

        # Try specialty title first, then generic
        title = None
        random.shuffle(specialty_titles)
        for t in specialty_titles:
            candidate = t.format(lang=lang)
            if candidate not in used_titles:
                title = candidate
                break
        if title is None:
            title = f"{lang} {level} Course #{course_id}"
        used_titles.add(title)

        instructor = random.choice(instructors)
        desc_templates = DESCRIPTION_TEMPLATES[level]
        description = random.choice(desc_templates).format(lang=lang)

        num_lessons = random.choice(range(10, 50, 2))
        duration = int(num_lessons * random.uniform(1.2, 2.5))
        if random.random() < 0.05:
            price = 0.00
        else:
            base = {"Beginner": 34.99, "Intermediate": 44.99, "Advanced": 59.99}
            price = round(base[level] + random.uniform(-15, 35), 2)
            price = max(9.99, price)

        rating = round(random.uniform(3.5, 5.0), 1)
        rating = min(rating, 5.0)
        num_reviews = random.randint(80, 5000)
        enrolled = random.randint(num_reviews, num_reviews * 8)

        courses.append({
            "id": course_id,
            "title": title,
            "language": lang,
            "level": level,
            "category": cat,
            "instructor": instructor,
            "price": price,
            "rating": rating,
            "num_reviews": num_reviews,
            "duration_hours": duration,
            "num_lessons": num_lessons,
            "enrolled": enrolled,
            "description": description,
            "tags": _pick_tags(level),
            "created": _random_date(),
        })
        course_id += 1

    return courses


# ── Generate users ──────────────────────────────────────────────────────────

USER_PROFILES = [
    {"username": "polyglot_anna", "name": "Anna Kowalski", "email": "anna.k@example.com"},
    {"username": "lang_lover_42", "name": "Marcus Chen", "email": "marcus.c@example.com"},
    {"username": "world_traveler", "name": "Sofia Andersson", "email": "sofia.a@example.com"},
    {"username": "romance_linguist", "name": "Jean-Pierre Moreau", "email": "jp.moreau@example.com"},
    {"username": "nordic_fan", "name": "Ingrid Olsen", "email": "ingrid.o@example.com"},
    {"username": "kanji_master", "name": "Takeshi Yamada", "email": "takeshi.y@example.com"},
    {"username": "arabic_dreamer", "name": "Leila Mansour", "email": "leila.m@example.com"},
    {"username": "globetrotter99", "name": "Ryan O'Brien", "email": "ryan.ob@example.com"},
    {"username": "lingua_franca", "name": "Priyanka Gupta", "email": "priyanka.g@example.com"},
    {"username": "slavic_spirit", "name": "Tomasz Wozniak", "email": "tomasz.w@example.com"},
    {"username": "k_culture_fan", "name": "Emily Park", "email": "emily.p@example.com"},
    {"username": "mediterranean_sun", "name": "Giulia Rossi", "email": "giulia.r@example.com"},
    {"username": "code_and_speak", "name": "Alex Rivera", "email": "alex.r@example.com"},
    {"username": "heritage_learner", "name": "Mei-Ling Wu", "email": "meiling.w@example.com"},
    {"username": "new_horizons", "name": "Fatou Diallo", "email": "fatou.d@example.com"},
]


def generate_users(courses):
    course_ids = [c["id"] for c in courses]
    course_map = {c["id"]: c for c in courses}
    users = []

    for uid, profile in enumerate(USER_PROFILES, start=1):
        # Each user enrolled in 3-8 courses
        n_enrolled = random.randint(3, 8)
        enrolled = sorted(random.sample(course_ids, min(n_enrolled, len(course_ids))))

        # 0-3 completed courses (subset of enrolled)
        n_completed = random.randint(0, min(3, len(enrolled)))
        completed = sorted(random.sample(enrolled, n_completed))

        # Cart: 0-3 courses not enrolled
        available_for_cart = [c for c in course_ids if c not in enrolled]
        n_cart = random.randint(0, 3)
        cart = sorted(random.sample(available_for_cart, min(n_cart, len(available_for_cart))))

        # Wishlist: 0-4 courses not enrolled and not in cart
        available_for_wish = [c for c in course_ids if c not in enrolled and c not in cart]
        n_wish = random.randint(0, 4)
        wishlist = sorted(random.sample(available_for_wish, min(n_wish, len(available_for_wish))))

        # Progress for each enrolled course
        progress = {}
        for cid in enrolled:
            total_lessons = course_map[cid]["num_lessons"]
            if cid in completed:
                comp = total_lessons
            else:
                comp = random.randint(0, total_lessons - 1)
            progress[str(cid)] = {
                "completed_lessons": comp,
                "last_lesson": comp,
                "score": random.randint(55, 98),
            }

        users.append({
            "id": uid,
            "username": profile["username"],
            "name": profile["name"],
            "email": profile["email"],
            "enrolled_courses": enrolled,
            "completed_courses": completed,
            "cart": cart,
            "wishlist": wishlist,
            "progress": progress,
        })

    return users


# ── Generate reviews ────────────────────────────────────────────────────────

REVIEW_TEXTS = {
    5: [
        "Outstanding course! The instructor explains everything with clarity and passion.",
        "Best {lang} course I have taken online. Highly recommended for anyone serious about learning.",
        "Loved every lesson. The cultural context makes this course truly special.",
        "Exceeded my expectations. The exercises are practical and the pacing is perfect.",
        "Finished the entire course and feel confident using {lang} in real conversations.",
        "A masterpiece of online education. Every module is carefully crafted.",
        "The instructor's enthusiasm is infectious. I looked forward to every session.",
        "This course transformed my {lang} skills. Worth every penny.",
        "Brilliant structure and engaging content. I recommended it to all my friends.",
    ],
    4: [
        "Very good course with solid content. A few sections could use more examples.",
        "Great overall. The grammar explanations are thorough, though pacing is a bit fast.",
        "Really enjoyed the course. Wish there were more audio practice exercises.",
        "Solid {lang} instruction. The instructor is knowledgeable and approachable.",
        "Good value for money. I learned a lot but wanted more speaking opportunities.",
        "Well-structured curriculum. Some lessons felt a bit short.",
        "Helpful course with practical vocabulary. Could benefit from more review quizzes.",
    ],
    3: [
        "Decent course but some topics feel rushed. More examples would help.",
        "Average. The content is accurate but the presentation could be more engaging.",
        "Okay for the price, but I expected more interactive exercises.",
        "Some good sections, some weak ones. The later modules need improvement.",
        "The content is fine but the course feels like it was put together quickly.",
    ],
    2: [
        "Below expectations. Too theoretical, not enough practical application.",
        "Disappointing. The audio quality is poor and the explanations are confusing.",
    ],
}


def generate_reviews(courses, users):
    reviews = []
    review_id = 1
    course_map = {c["id"]: c for c in courses}

    for user in users:
        # Each user reviews 2-5 of their enrolled courses
        n_reviews = random.randint(2, min(5, len(user["enrolled_courses"])))
        reviewed_courses = random.sample(user["enrolled_courses"], n_reviews)
        for cid in reviewed_courses:
            rating = random.choices([5, 4, 3, 2], weights=[40, 35, 18, 7])[0]
            templates = REVIEW_TEXTS[rating]
            lang = course_map[cid]["language"]
            text = random.choice(templates).format(lang=lang)

            reviews.append({
                "id": review_id,
                "course_id": cid,
                "user_id": user["id"],
                "rating": rating,
                "text": text,
                "date": _random_date("2024-01-01", "2025-06-01"),
            })
            review_id += 1

    return reviews


# ── Generate discussions ────────────────────────────────────────────────────

DISCUSSION_TEMPLATES = [
    {
        "title": "Best resources for practicing {lang} outside class?",
        "body": "I want to supplement this course with extra practice. Any recommendations for {lang} resources?",
    },
    {
        "title": "How long did it take you to feel comfortable in {lang}?",
        "body": "I am about halfway through and wondering when things start to click. Curious about others' experiences.",
    },
    {
        "title": "Study group for this {lang} course?",
        "body": "Would anyone like to form a weekly study group? We could practice together via video calls.",
    },
    {
        "title": "Pronunciation tips for {lang}?",
        "body": "I am struggling with some sounds. Any techniques that helped you improve your {lang} pronunciation?",
    },
    {
        "title": "Is this course enough for the {lang} certification exam?",
        "body": "Planning to take the official exam. Do I need additional materials beyond this course?",
    },
    {
        "title": "Favorite lesson in this course?",
        "body": "Which lesson or module has been your favorite so far? I really enjoyed the cultural section.",
    },
    {
        "title": "{lang} immersion tips",
        "body": "How do you create an immersion environment at home for {lang} practice?",
    },
    {
        "title": "Flashcard decks for this course?",
        "body": "Has anyone created Anki or Quizlet decks that align with the vocabulary in this course?",
    },
    {
        "title": "Struggling with {lang} grammar - need help",
        "body": "The grammar in the recent modules is really challenging. Any tips for breaking it down?",
    },
    {
        "title": "Cultural context in {lang} learning",
        "body": "I love how this course incorporates culture. What other cultural aspects of {lang}-speaking countries fascinate you?",
    },
    {
        "title": "Apps to complement this {lang} course?",
        "body": "What mobile apps do you use alongside this course to practice {lang} on the go?",
    },
    {
        "title": "How to stay motivated learning {lang}?",
        "body": "I hit a plateau around lesson 15. How do you keep your motivation up when progress feels slow?",
    },
    {
        "title": "Native {lang} content recommendations",
        "body": "Looking for movies, podcasts, or YouTube channels in {lang} suitable for my current level.",
    },
    {
        "title": "Writing practice for {lang}",
        "body": "Does anyone have tips for practicing {lang} writing? I feel my reading is much stronger.",
    },
    {
        "title": "Differences between formal and informal {lang}",
        "body": "The course covers formal {lang}, but how different is casual everyday speech?",
    },
]

REPLY_TEMPLATES = [
    "Great question! I found that watching {lang} content on YouTube with subtitles really helps.",
    "I had the same struggle. Keep at it, it gets easier around lesson 20!",
    "Try the shadowing technique - repeat after native speakers. It worked wonders for me.",
    "I use Anki flashcards alongside this course and it has made a huge difference.",
    "The instructor actually addressed this in the bonus materials. Check lesson {n}!",
    "I recommend joining a language exchange platform to find native {lang} speakers.",
    "For me, consistent daily practice (even just 15 minutes) was more effective than long sessions.",
    "Check out the {lang} subreddit - tons of helpful resources there.",
    "I second this! Music in {lang} is also a fantastic way to learn vocabulary.",
    "The key is not to compare yourself with others. Everyone learns at their own pace.",
]


def generate_discussions(courses, users):
    discussions = []
    disc_id = 1
    course_map = {c["id"]: c for c in courses}
    user_ids = [u["id"] for u in users]

    # Pick ~15 courses to have discussions on
    disc_courses = random.sample(
        [c["id"] for c in courses],
        min(18, len(courses))
    )

    for cid in disc_courses:
        lang = course_map[cid]["language"]
        template = random.choice(DISCUSSION_TEMPLATES)
        poster = random.choice(user_ids)

        # Generate 1-3 replies
        n_replies = random.randint(1, 3)
        replies = []
        for _ in range(n_replies):
            replier = random.choice([u for u in user_ids if u != poster])
            reply_text = random.choice(REPLY_TEMPLATES).format(
                lang=lang, n=random.randint(5, 30)
            )
            replies.append({
                "user_id": replier,
                "body": reply_text,
                "date": _random_date("2024-06-01", "2025-06-01"),
                "likes": random.randint(0, 20),
            })

        discussions.append({
            "id": disc_id,
            "course_id": cid,
            "user_id": poster,
            "title": template["title"].format(lang=lang),
            "body": template["body"].format(lang=lang),
            "date": _random_date("2024-03-01", "2025-06-01"),
            "likes": random.randint(1, 30),
            "replies": replies,
        })
        disc_id += 1

    return discussions


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    print("Generating courses...")
    courses = generate_courses(target=200)
    print(f"  -> {len(courses)} courses")

    print("Generating users...")
    users = generate_users(courses)
    print(f"  -> {len(users)} users")

    print("Generating reviews...")
    reviews = generate_reviews(courses, users)
    print(f"  -> {len(reviews)} reviews")

    print("Generating discussions...")
    discussions = generate_discussions(courses, users)
    print(f"  -> {len(discussions)} discussions")

    # Write to data directory
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PRISTINE_DIR.mkdir(parents=True, exist_ok=True)

    for name, data in [
        ("courses.json", courses),
        ("users.json", users),
        ("reviews.json", reviews),
        ("discussions.json", discussions),
    ]:
        path = DATA_DIR / name
        path.write_text(json.dumps(data, indent=4))
        print(f"  Wrote {path}  ({len(data)} records)")

        pristine_path = PRISTINE_DIR / name
        pristine_path.write_text(json.dumps(data, indent=4))
        print(f"  Wrote {pristine_path}")

    # Validate schema consistency
    print("\nValidation:")
    c0 = courses[0]
    expected_keys = {"id", "title", "language", "level", "category", "instructor",
                     "price", "rating", "num_reviews", "duration_hours", "num_lessons",
                     "enrolled", "description", "tags", "created"}
    assert set(c0.keys()) == expected_keys, f"Course keys mismatch: {set(c0.keys())} vs {expected_keys}"
    assert isinstance(c0["id"], int), "Course id must be int"
    assert isinstance(c0["price"], float), "Price must be float"
    assert isinstance(c0["tags"], list), "Tags must be list"
    print("  Courses schema: OK")

    u0 = users[0]
    expected_user_keys = {"id", "username", "name", "email", "enrolled_courses",
                          "completed_courses", "cart", "wishlist", "progress"}
    assert set(u0.keys()) == expected_user_keys, f"User keys mismatch"
    assert isinstance(u0["id"], int), "User id must be int"
    assert isinstance(u0["progress"], dict), "Progress must be dict"
    print("  Users schema: OK")

    r0 = reviews[0]
    expected_review_keys = {"id", "course_id", "user_id", "rating", "text", "date"}
    assert set(r0.keys()) == expected_review_keys, f"Review keys mismatch"
    assert isinstance(r0["id"], int), "Review id must be int"
    print("  Reviews schema: OK")

    d0 = discussions[0]
    expected_disc_keys = {"id", "course_id", "user_id", "title", "body", "date", "likes", "replies"}
    assert set(d0.keys()) == expected_disc_keys, f"Discussion keys mismatch"
    assert isinstance(d0["replies"], list), "Replies must be list"
    if d0["replies"]:
        expected_reply_keys = {"user_id", "body", "date", "likes"}
        assert set(d0["replies"][0].keys()) == expected_reply_keys, "Reply keys mismatch"
    print("  Discussions schema: OK")

    # Summary stats
    langs = set(c["language"] for c in courses)
    cats = set(c["category"] for c in courses)
    levels = set(c["level"] for c in courses)
    free_count = sum(1 for c in courses if c["price"] == 0)
    print(f"\nSummary:")
    print(f"  Languages: {len(langs)} ({', '.join(sorted(langs)[:10])}...)")
    print(f"  Categories: {len(cats)}")
    print(f"  Levels: {sorted(levels)}")
    print(f"  Free courses: {free_count}")
    print(f"  Price range: ${min(c['price'] for c in courses):.2f} - ${max(c['price'] for c in courses):.2f}")
    print(f"  Rating range: {min(c['rating'] for c in courses)} - {max(c['rating'] for c in courses)}")
    print(f"  Total enrollments: {sum(c['enrolled'] for c in courses):,}")
    print(f"  Users with non-empty carts: {sum(1 for u in users if u['cart'])}")
    print(f"  Users with completed courses: {sum(1 for u in users if u['completed_courses'])}")
    print("\nDone!")


if __name__ == "__main__":
    main()
