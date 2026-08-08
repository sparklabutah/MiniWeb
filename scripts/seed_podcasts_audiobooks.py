#!/usr/bin/env python3
"""Seed more podcasts, episodes, audiobooks and reviews into the
podcasts-audiobooks site's BASE tables (the pristine shared data every session
sees — NOT the per-session overlay that db.save_item writes to).

Deterministic + idempotent: fully fixed ids + `INSERT OR REPLACE`, so re-running
never duplicates. A fixed RNG seed drives only cosmetic numbers (listens, etc.).
Dates stay in the site's existing 2022-2024 past range (project rule: never
shift site dates to "today"). Does NOT touch build_db.py.

Run: PYTHONPATH=. ~/.conda/envs/miniweb/bin/python scripts/seed_podcasts_audiobooks.py
"""
import random

import app.db as db

RNG = random.Random(20240807)
T = "podcasts_audiobooks_"   # base table prefix

COLORS = ["#dc2626", "#2563eb", "#1e1b4b", "#059669", "#92400e", "#7c3aed",
          "#0f172a", "#eab308", "#db2777", "#f97316", "#0891b2", "#65a30d",
          "#0d9488", "#4f46e5", "#b45309", "#be123c", "#15803d", "#7e22ce"]

# (title, host, category, rating, subscribers, created_date)  -> ids 13..32
PODCASTS = [
    ("The Deep End", "Olivia Bennett", "Society & Culture", 4.4, 61000, "2023-05-12"),
    ("Trailblazers", "Andre Cole", "Business", 4.5, 78000, "2023-02-28"),
    ("Quantum Leaps", "Dr. Priya Nair", "Science", 4.8, 134000, "2022-10-18"),
    ("Field Notes", "Sam Rivera", "Nature", 4.3, 47000, "2023-07-09"),
    ("Courtside", "DeShawn Miller", "Sports", 4.2, 88000, "2023-01-22"),
    ("Ink & Ideas", "Fiona Clarke", "Arts", 4.6, 39000, "2022-12-03"),
    ("The Money Desk", "Victor Huang", "Finance", 4.5, 102000, "2023-03-30"),
    ("Small Town Secrets", "Hannah Boyd", "True Crime", 4.7, 176000, "2022-08-25"),
    ("Future Classroom", "Dr. Omar Haddad", "Education", 4.4, 53000, "2023-09-14"),
    ("Pixel Perfect", "Riley Nguyen", "Gaming", 4.3, 71000, "2023-06-19"),
    ("Around the World", "Camila Rossi", "Travel", 4.5, 64000, "2023-04-05"),
    ("The Founders Room", "Grace Park", "Business", 4.6, 91000, "2022-11-11"),
    ("Mind Matters", "Dr. Leah Sorensen", "Health & Wellness", 4.4, 58000, "2023-08-01"),
    ("Ancient Echoes", "Prof. Daniel Osei", "History", 4.7, 83000, "2022-09-27"),
    ("The Green Shift", "Dr. Maya Lindqvist", "Science", 4.6, 69000, "2023-05-23"),
    ("Stage Left", "Theo Marsh", "Arts", 4.2, 31000, "2023-10-08"),
    ("Full Court Press", "Bianca Torres", "Sports", 4.4, 96000, "2022-12-30"),
    ("Bytes & Bots", "Ken Ito", "Technology", 4.8, 148000, "2024-01-16"),
    ("Kitchen Confidential", "Chef Amara Diallo", "Food", 4.3, 44000, "2024-02-20"),
    ("The Long Game", "Nathan Brooks", "Business", 4.5, 75000, "2024-03-28"),
]

TOPICS = {
    "Society & Culture": ["The Loneliness Epidemic", "Cancel Culture, Revisited", "Why We Collect Things", "The New Etiquette", "Nostalgia as a Drug", "Third Places"],
    "Business": ["Scaling Past 100 Employees", "The Pricing Trap", "Founder Burnout", "Bootstrapped vs VC", "Hiring Your First Manager", "When to Pivot", "Reading a Term Sheet"],
    "Science": ["The Standard Model, Explained", "CRISPR's Next Decade", "Dark Matter Hunts", "The Physics of Time", "Fusion's Long Road", "How Vaccines Are Made"],
    "Nature": ["Return of the Wolves", "Coral in Crisis", "The Secret Life of Fungi", "Migratory Birds", "Rewilding Britain", "Deep Sea Discoveries"],
    "Sports": ["Trade Deadline Fallout", "The Analytics Revolution", "Playoff Preview", "Rookie of the Year Race", "Coaching Carousel", "The Salary Cap Explained"],
    "Arts": ["The Comeback of Vinyl", "Curating a First Show", "Color Theory in Practice", "Writing a Second Novel", "The Business of Galleries", "Sound Design 101"],
    "Finance": ["Reading the Yield Curve", "Index Funds 101", "The Housing Market Now", "Understanding Inflation", "Your First Budget", "Bonds Are Back"],
    "True Crime": ["The Cold Case File", "A Town's Silence", "The Witness Recants", "Forensics Breakthrough", "The Missing Hiker", "Behind the Verdict"],
    "Education": ["Grading Without Grades", "AI in the Classroom", "The Reading Wars", "Teaching Critical Thinking", "Homework, Reconsidered", "The Case for Play"],
    "Gaming": ["The Indie Boom", "Speedrun Science", "Preserving Old Games", "Live Service Fatigue", "The Art of Level Design", "Handhelds Are Back"],
    "Travel": ["Slow Travel in Japan", "The Overtourism Problem", "Packing Light", "Night Trains of Europe", "Street Food Crawls", "Off-Season Escapes"],
    "History": ["The Library of Alexandria", "Silk Road Traders", "The Fall of Rome", "Forgotten Empires", "Plagues That Changed Us", "Maps and Power"],
    "Health & Wellness": ["The Science of Sleep", "Rethinking Willpower", "Gut Health Basics", "Anxiety Toolkit", "Strength After 40", "The Loneliness Cure"],
    "Technology": ["The Chip Wars", "What Is a Transformer", "Privacy by Design", "The Open Source Economy", "Robots at Work", "The End of Passwords"],
    "Food": ["Mastering the Sear", "Fermentation at Home", "The Perfect Loaf", "Regional Curries", "Knife Skills", "Cooking for One"],
}
GENERIC = ["A Conversation With a Legend", "Listener Questions", "Behind the Scenes", "The Year in Review", "A Live Recording", "The Origins Story"]

# (title, author, narrator, genre, rating, price, duration_hours, chapters, publish_date) -> ids 16..40
AUDIOBOOKS = [
    ("The Name of the Wind", "Patrick Rothfuss", "Nick Podehl", "Fantasy", 4.8, 17.99, 27.5, 92, "2023-03-11"),
    ("Gone Girl", "Gillian Flynn", "Julia Whelan", "Thriller", 4.5, 13.99, 19.0, 45, "2022-09-18"),
    ("The Silent Patient", "Alex Michaelides", "Jack Hawkins", "Mystery", 4.4, 12.99, 8.5, 30, "2023-05-02"),
    ("Circe", "Madeline Miller", "Perdita Weeks", "Fantasy", 4.7, 15.49, 12.0, 27, "2023-01-27"),
    ("Where the Crawdads Sing", "Delia Owens", "Cassandra Campbell", "Fiction", 4.6, 14.49, 12.5, 33, "2022-10-09"),
    ("The Body Keeps the Score", "Bessel van der Kolk", "Sean Pratt", "Self-Help", 4.6, 16.99, 16.5, 20, "2023-07-21"),
    ("A Short History of Nearly Everything", "Bill Bryson", "Bill Bryson", "Science", 4.5, 15.99, 18.0, 30, "2022-11-14"),
    ("The Great Gatsby", "F. Scott Fitzgerald", "Jake Gyllenhaal", "Classics", 4.3, 9.99, 5.0, 9, "2022-06-30"),
    ("Born a Crime", "Trevor Noah", "Trevor Noah", "Memoir", 4.9, 14.99, 8.5, 18, "2023-02-15"),
    ("The Silmarillion", "J.R.R. Tolkien", "Martin Shaw", "Fantasy", 4.4, 18.49, 15.0, 24, "2022-08-19"),
    ("Little Fires Everywhere", "Celeste Ng", "Jennifer Lim", "Fiction", 4.5, 12.99, 11.0, 30, "2023-09-06"),
    ("Meditations", "Marcus Aurelius", "Duncan Steen", "Philosophy", 4.6, 8.99, 6.5, 12, "2022-12-01"),
    ("The Martian", "Andy Weir", "R.C. Bray", "Science Fiction", 4.8, 16.49, 10.5, 26, "2023-04-12"),
    ("Verity", "Colleen Hoover", "Vanessa Johansson", "Thriller", 4.5, 11.99, 8.0, 22, "2023-06-24"),
    ("The Subtle Art of Not Giving a F*ck", "Mark Manson", "Roger Wayne", "Self-Help", 4.3, 10.99, 5.0, 9, "2022-10-27"),
    ("A Game of Thrones", "George R.R. Martin", "Roy Dotrice", "Fantasy", 4.7, 19.99, 33.5, 73, "2022-07-03"),
    ("Bad Blood", "John Carreyrou", "Will Damron", "Business", 4.7, 14.49, 11.5, 24, "2023-08-14"),
    ("The Alchemist", "Paulo Coelho", "Jeremy Irons", "Fiction", 4.4, 9.49, 4.0, 16, "2022-11-22"),
    ("Cosmos", "Carl Sagan", "LeVar Burton", "Science", 4.8, 15.49, 14.5, 13, "2023-03-19"),
    ("The Seven Husbands of Evelyn Hugo", "Taylor Jenkins Reid", "Alma Cuervo", "Fiction", 4.7, 13.49, 12.0, 30, "2023-05-30"),
    ("Man's Search for Meaning", "Viktor Frankl", "Simon Vance", "Philosophy", 4.7, 10.49, 4.5, 8, "2022-09-08"),
    ("The Girl with the Dragon Tattoo", "Stieg Larsson", "Simon Vance", "Mystery", 4.5, 14.99, 16.5, 29, "2022-12-16"),
    ("Outliers", "Malcolm Gladwell", "Malcolm Gladwell", "Business", 4.4, 12.99, 7.5, 9, "2023-01-10"),
    ("Mexican Gothic", "Silvia Moreno-Garcia", "Frankie Corzo", "Horror", 4.2, 12.49, 10.5, 30, "2023-10-03"),
    ("The Odyssey", "Homer", "Claire Danes", "Classics", 4.5, 13.99, 13.5, 24, "2024-01-25"),
]

BLURBS = ["Absolutely hooked from the first minute.", "Well produced and thoughtful.",
          "A bit slow at times but worth it.", "My new favorite — instant subscribe.",
          "Great narration, would recommend.", "Solid, if a little uneven.",
          "Couldn't stop listening.", "Insightful and entertaining."]


def _replace(table, cols, rows):
    """INSERT OR REPLACE into a BASE table and commit (idempotent by PK)."""
    conn = db._get_conn()
    ph = ",".join("?" * len(cols))
    conn.executemany(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({ph})", rows)
    conn.commit()


def main():
    pod_cols = ["id", "title", "host", "description", "category", "rating",
                "subscribers", "episodes_count", "language", "cover_color", "created_date"]
    ep_cols = ["id", "podcast_id", "episode_number", "title", "description",
               "duration_minutes", "publish_date", "listens", "liked_by"]
    ab_cols = ["id", "title", "author", "narrator", "description", "genre",
               "rating", "price", "duration_hours", "chapters", "publish_date", "liked_by"]
    rev_cols = ["id", "user_id", "item_type", "item_id", "rating", "text", "date"]

    pod_rows, ep_rows = [], []
    for i, (title, host, cat, rating, subs, created) in enumerate(PODCASTS):
        pid = 13 + i
        n_eps = RNG.randint(8, 15)
        pod_rows.append((pid, title, host,
                         f"{title} with {host} — a {cat.lower()} podcast bringing you sharp conversations and deep dives every week.",
                         cat, rating, subs, n_eps, "English", COLORS[i % len(COLORS)], created))
        pool = TOPICS.get(cat, []) + GENERIC
        year = int(created[:4])
        for ep_num in range(1, n_eps + 1):
            eid = 1000 + i * 100 + ep_num   # fixed, well above existing (max 82)
            topic = pool[(i + ep_num) % len(pool)]
            m = ((ep_num * 3) % 12) + 1
            d = ((ep_num * 7) % 27) + 1
            yr = min(2024, year + (ep_num // 12))
            ep_rows.append((eid, pid, ep_num, f"Ep {ep_num}: {topic}",
                            f"In this episode, {host} explores {topic.lower()} with guests and listener questions.",
                            RNG.randint(18, 74), f"{yr:04d}-{m:02d}-{d:02d}", RNG.randint(2000, 90000), ""))

    ab_rows = []
    for i, (title, author, narr, genre, rating, price, dur, ch, pub) in enumerate(AUDIOBOOKS):
        aid = 16 + i
        ab_rows.append((aid, title, author, narr,
                        f"{title} by {author}, narrated by {narr}. A standout {genre.lower()} listen.",
                        genre, rating, price, dur, ch, pub, ""))

    users = [u["id"] for u in db.query("podcasts-audiobooks", "users", limit=100)] or [1, 2, 3, 4, 5]
    rev_rows = []
    for k, (kind, iid) in enumerate([("podcast", p) for p in range(13, 33)] +
                                    [("audiobook", a) for a in range(16, 41)]):
        if RNG.random() > 0.5:
            continue
        rev_rows.append((2000 + k, RNG.choice(users), kind, iid, RNG.randint(3, 5),
                         RNG.choice(BLURBS), f"2024-{RNG.randint(1,10):02d}-{RNG.randint(1,27):02d}"))

    _replace(T + "podcasts", pod_cols, pod_rows)
    _replace(T + "episodes", ep_cols, ep_rows)
    _replace(T + "audiobooks", ab_cols, ab_rows)
    _replace(T + "reviews", rev_cols, rev_rows)

    ex = lambda q: db.execute(q, (), fetch="val")
    print(f"podcasts base:   {ex('SELECT COUNT(*) FROM %spodcasts' % T)}")
    print(f"episodes base:   {ex('SELECT COUNT(*) FROM %sepisodes' % T)}")
    print(f"audiobooks base: {ex('SELECT COUNT(*) FROM %saudiobooks' % T)}")
    print(f"reviews base:    {ex('SELECT COUNT(*) FROM %sreviews' % T)}")


if __name__ == "__main__":
    main()
