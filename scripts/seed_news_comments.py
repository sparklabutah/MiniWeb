"""Seed realistic threaded comment discussions for the Lakeport Tribune (news).

Populates the base `news_comments` table so curated local articles carry real
threaded discussions (top-level comments + nested replies) with per-user
upvotes, instead of a bare denormalized comments_count with zero backing rows.

Idempotent: skips if the table already has rows. Re-run after a DB rebuild.
Run:  MINIWEB_DB=data/trimmed_miniweb.db python scripts/seed_news_comments.py
"""
import json
import os
import sqlite3
from datetime import datetime, timedelta

DB = os.environ.get("MINIWEB_DB", "data/trimmed_miniweb.db")

# Commenters (news_users): id -> display_name
USERS = {1: ("alex_rivera", "Alex Rivera"),
         2: ("rachel_kim", "Rachel Kim"),
         3: ("samantha_liu", "Samantha Liu"),
         4: ("elena_vasquez", "Elena Vasquez")}

# Per-article threads. Each entry: (author_uid, body, upvoter_uids, [replies]).
# A reply is (author_uid, body, upvoter_uids).
THREADS = {
    1: [  # Meridian Systems $42M Series B
        (2, "Huge win for a Lakeport company. Curious whether the new hiring will be local or remote.", [1, 3, 4],
         [(3, "They mentioned expanding the Cedar Blvd office, so hopefully local roles.", [2]),
          (2, "That would be great for the downtown economy.", [])]),
        (4, "$42M is a serious raise for a workflow automation play. Who led the round?", [1],
         [(1, "Article says a coastal growth fund led it with the existing seed investors following on.", [4])]),
        (3, "Automation is eating back-office work everywhere. Smart bet.", [2]),
    ],
    2: [  # Farmers Market year-round
        (1, "Finally! Winter Saturdays without the market have been rough.", [2, 3, 4],
         [(4, "Agreed. Hope the root-vegetable and cheese vendors stay on through January.", [1, 3])]),
        (3, "Will the year-round schedule keep the same Riverside Park location?", [],
         [(2, "Yes, same spot, just moving under the pavilion for the cold months.", [3])]),
    ],
    4: [  # Cedar Blvd protected bike lanes 5-2
        (3, "5-2 is a clearer margin than I expected. Protected lanes save lives.", [1, 2, 4],
         [(1, "The two no votes were worried about parking loss on the 400 block.", [3]),
          (4, "Parking studies showed occupancy under 60% there, so the tradeoff seems fair.", [1, 3])]),
        (2, "Great for kids biking to Lakeport High. That stretch was genuinely dangerous.", [3, 4]),
        (4, "Any timeline on construction starting?", [],
         [(3, "Council notes say striping begins in spring, full barriers by summer.", [2])]),
    ],
    5: [  # Drama club state win
        (4, "So proud of these students! An original play winning state is no small thing.", [1, 2, 3],
         [(2, "The writing award on top of the overall win is incredible.", [4])]),
        (1, "Anyone know if they'll do a community performance before the season ends?", [3]),
    ],
    6: [  # Lake cleanup 200 volunteers
        (2, "1.2 tons is staggering. Thank you to everyone who showed up.", [1, 3, 4]),
        (3, "Would love a recurring monthly cleanup instead of just the annual one.", [4],
         [(4, "The organizers hinted at a spring follow-up. Fingers crossed.", [2])]),
    ],
    7: [  # Cedar & Sage best new restaurant
        (1, "Well deserved. The mushroom toast alone is worth the wait for a table.", [2, 4],
         [(3, "The wait is the only downside. Two weeks out for a Friday now.", [1])]),
        (4, "Great to see a local spot beat out the coastal chains for this.", [3]),
    ],
    11: [  # Record October rainfall flooding
        (3, "The Maple Ln underpass floods every heavy rain. When does the drainage fix happen?", [1, 2],
         [(2, "Public works said the culvert upgrade is in next year's budget.", [3])]),
        (4, "Stay safe everyone, turn around don't drown on the low crossings.", [1, 2, 3]),
    ],
    12: [  # Budget flat property tax
        (2, "Third year flat is impressive given inflation. Curious what got cut to hold the line.", [4],
         [(1, "Mostly deferred capital projects, per the finance director's summary.", [2])]),
        (3, "Flat rate is nice but I'd rather they fully fund the library expansion.", [1]),
    ],
    15: [  # Board game convention 400
        (1, "400 people! The tabletop scene here is way bigger than folks realize.", [2, 3]),
        (4, "The cooperative-games tournament was the highlight for me this year.", [1],
         [(3, "Same. Hoping they add a legacy-campaign track next year.", [4])]),
    ],
    18: [  # Library maker space
        (3, "A 3D printer AND a laser cutter at the public library? Incredible resource.", [1, 2, 4],
         [(2, "And it's free with a library card. Take that, expensive maker memberships.", [1, 3])]),
        (4, "Hope they run beginner workshops so it's not just for the already-experienced.", [1]),
    ],
    19: [  # Coffee roasters 10th anniversary
        (2, "Ten years already! Their single-origin Ethiopian pour-over is a Lakeport staple.", [1, 3, 4]),
        (1, "The block party was packed. Great to see Main Street that lively on a Saturday.", [4],
         [(4, "The live music plus free samples was a perfect combo.", [1, 2])]),
    ],
}


def main():
    con = sqlite3.connect(DB)
    con.row_factory = sqlite3.Row
    existing = con.execute("SELECT COUNT(*) FROM news_comments").fetchone()[0]
    if existing:
        print(f"news_comments already has {existing} rows — skipping seed.")
        con.close()
        return

    # Anchor each article's comments just after its publish date (dates are
    # intentionally static/past — do not shift them).
    dates = {r["id"]: r["date"]
             for r in con.execute("SELECT id, date FROM news_articles")}

    rows = []
    cid = 0
    for aid in sorted(THREADS):
        base_date = dates.get(aid) or "2025-11-01"
        try:
            base_dt = datetime.strptime(base_date[:10], "%Y-%m-%d") + timedelta(hours=6)
        except ValueError:
            base_dt = datetime(2025, 11, 1, 6)
        offset = 0
        for entry in THREADS[aid]:
            author_uid, body, upvoters = entry[0], entry[1], entry[2]
            replies = entry[3] if len(entry) > 3 else []
            cid += 1
            parent_cid = cid
            uname, dname = USERS[author_uid]
            ts = (base_dt + timedelta(hours=offset)).isoformat() + "Z"
            offset += 3
            rows.append((parent_cid, aid, 0, author_uid, uname, dname, body, ts,
                         len(upvoters), json.dumps(upvoters)))
            for r_uid, r_body, r_upvoters in replies:
                cid += 1
                r_uname, r_dname = USERS[r_uid]
                r_ts = (base_dt + timedelta(hours=offset)).isoformat() + "Z"
                offset += 2
                rows.append((cid, aid, parent_cid, r_uid, r_uname, r_dname,
                             r_body, r_ts, len(r_upvoters), json.dumps(r_upvoters)))

    con.executemany(
        "INSERT INTO news_comments "
        "(id, article_id, parent_id, user_id, username, display_name, body, "
        " posted_at, upvotes, upvoted_by) VALUES (?,?,?,?,?,?,?,?,?,?)",
        rows,
    )
    con.commit()
    total = con.execute("SELECT COUNT(*) FROM news_comments").fetchone()[0]
    replies = con.execute("SELECT COUNT(*) FROM news_comments WHERE parent_id>0").fetchone()[0]
    arts = con.execute("SELECT COUNT(DISTINCT article_id) FROM news_comments").fetchone()[0]
    print(f"Seeded {total} comments ({replies} nested replies) across {arts} articles.")
    con.close()


if __name__ == "__main__":
    main()
