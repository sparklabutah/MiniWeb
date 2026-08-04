#!/usr/bin/env python
"""Classify World News (Wikinews) articles into browsable sub-topics — OFFLINE.

Adds a `subcategory` column to news_articles (idempotent) and assigns each
category='world' article a topic slug via deterministic keyword scoring over its
title + body. Lets the World News section be browsed by topic instead of a flat
list. Never runs build_db; only ALTER (add column) + UPDATE world rows.
"""
import re
import sqlite3
from pathlib import Path

DB = str(Path(__file__).resolve().parent.parent / "data" / "trimmed_miniweb.db")

# slug -> keyword list. An article is scored by how many distinct keywords hit
# its (title + body); highest score wins, ties broken by this dict's order.
TOPICS = {
    "sports": ["olympic", "world cup", "football", "soccer", "cricket", "tennis",
               "basketball", "baseball", "rugby", "championship", "tournament",
               "league", "athlet", "fifa", "medal", " match ", "grand prix",
               "formula one", "marathon", "coach", "striker"],
    "environment": ["earthquake", "tsunami", "hurricane", "typhoon", "cyclone",
                    "flood", "wildfire", "volcano", "eruption", "drought",
                    "climate", "quake", "storm", "landslide", "emissions",
                    "endangered", "wildlife", "pollution"],
    "health": ["disease", "virus", "vaccine", "outbreak", "epidemic", "pandemic",
               "influenza", " flu ", "cancer", "hospital", "medical", "patients",
               "infection", "malaria", "hiv", "health organization", "surgery"],
    "science_tech": ["nasa", "space", "satellite", "spacecraft", "astronaut",
                     "telescope", "scientist", "research", "physics", "genome",
                     "dna", "software", "internet", "computer", "technology",
                     "discovery", "probe", "orbit", "quantum", "experiment"],
    "conflict": ["war", "troops", "military", "soldier", "insurgent", "militant",
                 "rebel", "airstrike", "bombing", "explosion", "terror",
                 "hostage", "ceasefire", "gunmen", "missile", "invasion", "coup",
                 "casualties", "killed in", "armed forces", "offensive"],
    "law_crime": ["court", "trial", "judge", "convicted", "verdict", "arrest",
                  "police", "murder", "lawsuit", "sentenced", "prosecut",
                  "charged", "prison", "jail", "fraud", "smuggling", "kidnap"],
    "business": ["economy", "economic", "market", "stock", "shares", "trade",
                 "company", "corporation", "bank", "oil price", "inflation",
                 "billion", "merger", "bankrupt", "gdp", "currency", "investors",
                 "profit", "exports"],
    "politics": ["election", "president", "minister", "parliament", "government",
                 "senate", "congress", "referendum", "diplomat", "treaty",
                 "summit", "sanctions", "coalition", "campaign", "vote", "policy",
                 "cabinet", "ambassador", "resign"],
    "culture": ["film", "movie", "music", "album", "actor", "actress", "artist",
                "festival", "award", " book ", "celebrity", "concert", "singer",
                "oscar", "museum", "fashion", "director", "novel", "grammy"],
}
ORDER = list(TOPICS)


def classify(text):
    text = " " + text.lower() + " "
    best, best_score = "general", 0
    for slug in ORDER:
        score = sum(1 for kw in TOPICS[slug] if kw in text)
        if score > best_score:
            best, best_score = slug, score
    return best


def main():
    conn = sqlite3.connect(DB, timeout=60)
    cols = [r[1] for r in conn.execute("PRAGMA table_info(news_articles)")]
    if "subcategory" not in cols:
        conn.execute("ALTER TABLE news_articles ADD COLUMN subcategory TEXT DEFAULT ''")
        conn.commit()
        print("added subcategory column")

    rows = conn.execute(
        "SELECT id, title, substr(body,1,1200) FROM news_articles WHERE category='world'").fetchall()
    print(f"classifying {len(rows):,} world articles...")
    updates = [(classify((t or "") + " " + (b or "")), aid) for aid, t, b in rows]
    conn.executemany("UPDATE news_articles SET subcategory=? WHERE id=?", updates)
    conn.commit()

    print("distribution:")
    for r in conn.execute(
        "SELECT subcategory, COUNT(*) c FROM news_articles WHERE category='world' "
        "GROUP BY subcategory ORDER BY c DESC"):
        print(f"  {r[0]:14s} {r[1]:,}")
    conn.close()


if __name__ == "__main__":
    main()
