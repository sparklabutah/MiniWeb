"""Expand music (SoundWave) base data: artists, albums, tracks.

The site ships with 85 artists / 166 albums / 1277 tracks (1548 rows total
across music_* tables), which makes browse/filter/search macros thin. This
adds a deterministic (seeded) synthetic catalog of new artists with full
discographies (EPs, LPs, deluxe editions, live albums and anthologies),
reusing the existing vocabulary: two-word band/track names in the current
style, the same 21 genres, hex cover_color convention (no image files),
YYYY-MM-DD dates, JSON-string liked_by ('[]').

Task-safety guardrails (see annotation task music_94c9a5 "Add the newest
playlist to the library and play the first song"):
  * music_playlists / music_library / music_users are NOT touched, so the
    newest playlist (id 8, 2025-06-01; newest visible: id 6) and its first
    song are unchanged.
  * New album release_dates are capped at 2026-06-30, strictly older than
    the current 6th-newest album (2026-10-13), so the homepage "New
    Releases" row is unchanged.
  * New artists' monthly_listeners < 2,300,000 (current 6th-highest is
    2,369,513), so "Featured Artists" is unchanged.
  * New tracks' plays are 8,000-4,500,000 (current 10th-highest is
    5,400,000; min 7,593), so "Popular Tracks" and min/max extremums are
    unchanged.

Insert-only — existing rows are never touched. Inserted ids are recorded in
data/backups/music-expansion-2026-07-20/inserted_ids.json for rollback.

Usage: ~/.conda/envs/miniweb/bin/python scripts/expand_music_data.py [--dry-run]
"""
import json
import random
import sqlite3
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB_PATH = ROOT / "data" / "trimmed_miniweb.db"

rng = random.Random(20260720)

N_ARTISTS = 55
N_ALBUMS = 230
TRACK_BUDGET = 3250  # promote albums to deluxe until at least this many tracks

# Existing artist-genre vocabulary (weights ~ current distribution)
GENRES = [
    ("Synthwave", 10), ("Jazz", 9), ("Folk", 7), ("Ambient", 6),
    ("Electronic", 6), ("Post-Rock", 6), ("R&B", 6), ("Hip-Hop", 5),
    ("House", 5), ("Classical", 4), ("Lo-fi", 4), ("Indie", 3),
    ("Indie Rock", 3), ("Metal", 2), ("Pop", 2), ("Rock", 2),
    ("Afrobeats", 1), ("Blues", 1), ("Country", 1), ("Funk", 1), ("Latin", 1),
]

BAND_A = ["Amber", "Ashen", "Cobalt", "Copper", "Crystal", "Driftwood", "Echo",
          "Ember", "Feral", "Gilded", "Harbor", "Hazel", "Indigo", "Ivory",
          "Juniper", "Marble", "Midnight", "Mossy", "Neon", "Northern",
          "Obsidian", "Opal", "Pale", "Prairie", "Quartz", "Saffron", "Scarlet",
          "Silent", "Slate", "Sable", "Thunder", "Twilight", "Umber", "Wandering",
          "Willow", "Winter"]
BAND_B = ["Arcade", "Atlas", "Aviary", "Ballads", "Canyons", "Chorus", "Circuit",
          "Comets", "Current", "Drift", "Embers", "Frontier", "Gardens", "Harbors",
          "Herons", "Hollow", "Lanterns", "Meadows", "Mirage", "Orchard",
          "Parade", "Pines", "Prism", "Ravens", "Reverie", "Signals", "Sparrows",
          "Spectrum", "Static", "Summit", "Tides", "Vanguard", "Wolves", "Wires"]
FIRST = ["Amara", "Bruno", "Celia", "Dario", "Elena", "Farid", "Greta", "Hiro",
         "Imani", "Jonas", "Keiko", "Lorenzo", "Maja", "Nadia", "Omar", "Priya",
         "Quinn", "Rosa", "Stellan", "Tomas", "Uma", "Viktor", "Wren", "Yara", "Zane"]
LAST = ["Abadi", "Bergstrom", "Castillo", "Duarte", "Eriksen", "Fontaine",
        "Grieco", "Haruki", "Iwata", "Jansen", "Kaplan", "Lindqvist", "Moreau",
        "Nakamura", "Okonkwo", "Petrov", "Quintana", "Reyes", "Soderberg",
        "Takahashi", "Uzoma", "Valdez", "Winther", "Yamada", "Zetterlund"]

CITIES = [("Seattle", "Pacific Northwest storyteller"), ("Portland", "rain-soaked"),
          ("Berlin", "club-forged"), ("London", "genre-bending"),
          ("Tokyo", "meticulous"), ("Montreal", "bilingual"),
          ("Chicago", "warehouse-honed"), ("Austin", "road-tested"),
          ("Reykjavik", "glacial"), ("Melbourne", "sun-bleached"),
          ("Oslo", "minimalist"), ("Lisbon", "coastal"),
          ("Detroit", "hardware-driven"), ("New Orleans", "brass-steeped"),
          ("Copenhagen", "understated"), ("Sao Paulo", "polyrhythmic")]

WORD_A = ["Amber", "Broken", "Burning", "Copper", "Distant", "Electric",
          "Fading", "Falling", "Frozen", "Gilded", "Golden", "Hidden", "Hollow",
          "Lonely", "Lunar", "Midnight", "Neon", "Northern", "Paper", "Quiet",
          "Restless", "Rising", "Scattered", "Silent", "Silver", "Slow",
          "Static", "Velvet", "Wandering", "Winter"]
WORD_B = ["Anthem", "Arrows", "Avenues", "Bloom", "Borders", "Bridges",
          "Currents", "Daylight", "Echoes", "Embers", "Fires", "Gardens",
          "Harbors", "Hearts", "Horizon", "Lanterns", "Lights", "Mirrors",
          "Motion", "Orbit", "Reverie", "Rivers", "Shadows", "Signals",
          "Skies", "Streets", "Tides", "Weekend", "Windows", "Youth"]

ALBUM_ONE = ["Afterglow", "Ampersand", "Anhedonia", "Archipelago", "Bloomfield",
             "Cartography", "Chrysalis", "Cinders", "Duskline", "Evergreen",
             "Firmament", "Gossamer", "Halcyon", "Heliograph", "Hinterland",
             "Kaleido", "Lodestar", "Meridian", "Monsoon", "Nocturne",
             "Overgrowth", "Parallax", "Penumbra", "Riptide", "Saltwater",
             "Solstice", "Sonder", "Tessellate", "Undertow", "Vellum",
             "Waypoint", "Zephyr"]

ALBUM_KINDS = [
    # (kind, track range, weight)
    ("ep", (5, 7), 12),
    ("lp", (9, 13), 45),
    ("deluxe", (14, 17), 28),
    ("live", (19, 24), 8),
    ("anthology", (22, 28), 7),
]


def _hex_color(r):
    return "#%06x" % r.randint(0, 0xFFFFFF)


def _date(r, y0=2015, y1=2026):
    """YYYY-MM-DD, capped at 2026-06-30 so New Releases (>= 2026-10-13) is safe."""
    y = r.randint(y0, y1)
    m = r.randint(1, 12) if y < 2026 else r.randint(1, 6)
    return f"{y}-{m:02d}-{r.randint(1, 28):02d}"


def main():
    dry = "--dry-run" in sys.argv
    db = sqlite3.connect(DB_PATH, timeout=60)
    db.row_factory = sqlite3.Row

    existing_artist_names = {r[0] for r in db.execute("SELECT name FROM music_artists")}
    next_artist = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM music_artists").fetchone()[0]
    next_album = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM music_albums").fetchone()[0]
    next_track = db.execute("SELECT COALESCE(MAX(id),0)+1 FROM music_tracks").fetchone()[0]

    genre_pool = [g for g, w in GENRES for _ in range(w)]

    # ---- artists --------------------------------------------------------
    new_artists = []
    used_names = set(existing_artist_names)
    while len(new_artists) < N_ARTISTS:
        style = rng.random()
        if style < 0.55:
            name = f"{rng.choice(BAND_A)} {rng.choice(BAND_B)}"
        elif style < 0.70:
            name = f"The {rng.choice(BAND_A)} {rng.choice(BAND_B)}"
        elif style < 0.82:
            name = f"{rng.choice(FIRST)} {rng.choice(LAST)}"
        elif style < 0.90:
            name = f"DJ {rng.choice(BAND_A)}"
        else:
            name = rng.choice(FIRST)
        if name in used_names:
            continue
        used_names.add(name)
        genre = rng.choice(genre_pool)
        city, flavor = rng.choice(CITIES)
        is_group = " " in name and not name.startswith("DJ")
        kind = ("Musical group" if is_group and rng.random() < 0.7 else "Solo artist")
        year = rng.randint(1998, 2023)
        bio_bits = [f"{kind} from {city}.",
                    f"Known for {flavor} {genre.lower()} with a devoted following.",
                    f"Active since {year}."]
        if rng.random() < 0.3:
            bio_bits.insert(2, rng.choice(
                ["Their live sets lean heavily on improvisation.",
                 "Self-releases everything through a home studio.",
                 "Collaborates widely across the label roster.",
                 "Built an audience through late-night radio play."]))
        new_artists.append({
            "id": next_artist, "name": name, "genre": genre,
            "bio": " ".join(bio_bits), "albums_count": 0,
            "monthly_listeners": rng.randint(9000, 2_300_000),
            "verified": 1 if rng.random() < 0.45 else 0,
        })
        next_artist += 1

    # ---- albums ---------------------------------------------------------
    kinds = [k for k, _, w in ALBUM_KINDS for _ in range(w)]
    ranges = {k: r for k, r, _ in ALBUM_KINDS}
    new_albums = []
    album_sizes = {}
    for i in range(N_ALBUMS):
        artist = new_artists[i % len(new_artists)] if i < len(new_artists) * 3 \
            else rng.choice(new_artists)
        kind = rng.choice(kinds)
        n_tracks = rng.randint(*ranges[kind])
        w1, w2 = rng.choice(WORD_A), rng.choice(WORD_B)
        style = rng.random()
        if style < 0.30:
            title = rng.choice(ALBUM_ONE)
        elif style < 0.75:
            title = f"{w1} {w2}"
        else:
            title = f"{w2} in {rng.choice(WORD_A)} Light" if rng.random() < 0.3 \
                else f"The {w1} Sessions"
        if kind == "ep":
            title += " (EP)"
        elif kind == "deluxe":
            title += " (Deluxe Edition)"
        elif kind == "live":
            title = f"Live at the {rng.choice(BAND_B)[:-1] if rng.random() < .5 else rng.choice(['Roxy', 'Paramount', 'Fillmore', 'Vera', 'Crocodile'])}"
        elif kind == "anthology":
            title = f"{artist['name']}: Anthology" if rng.random() < 0.5 else f"{title}: The Collection"
        album = {
            "id": next_album, "artist_id": artist["id"], "title": title,
            "release_date": _date(rng), "genre": artist["genre"],
            "tracks_count": n_tracks, "duration_minutes": 0,
            "cover_color": _hex_color(rng),
        }
        artist["albums_count"] += 1
        album_sizes[album["id"]] = [album, kind, n_tracks]
        new_albums.append(album)
        next_album += 1

    # Promote random LPs to deluxe until the track budget is met
    planned = sum(v[2] for v in album_sizes.values())
    promotable = [v for v in album_sizes.values() if v[1] in ("lp", "ep")]
    rng.shuffle(promotable)
    pi = 0
    while planned < TRACK_BUDGET and pi < len(promotable):
        extra = rng.randint(4, 8)
        promotable[pi][2] += extra
        promotable[pi][0]["tracks_count"] += extra
        if "(EP)" not in promotable[pi][0]["title"] and "(Deluxe" not in promotable[pi][0]["title"]:
            promotable[pi][0]["title"] += " (Deluxe Edition)"
        planned += extra
        pi += 1

    # ---- tracks ---------------------------------------------------------
    new_tracks = []
    title_pool = [f"{a} {b}" for a in WORD_A for b in WORD_B]
    rng.shuffle(title_pool)
    ti = 0
    for album, kind, n_tracks in album_sizes.values():
        live = kind == "live"
        total_secs = 0
        for tn in range(1, n_tracks + 1):
            if ti >= len(title_pool):
                rng.shuffle(title_pool)
                ti = 0
            title = title_pool[ti]
            ti += 1
            if live:
                title += " (Live)"
            elif tn > 12 and rng.random() < 0.2:
                title += rng.choice([" (Reprise)", " (Acoustic)", " (Demo)"])
            secs = rng.randint(150, 420) if not live else rng.randint(200, 540)
            total_secs += secs
            new_tracks.append({
                "id": next_track, "album_id": album["id"],
                "artist_id": album["artist_id"], "title": title,
                "duration_seconds": secs, "track_number": tn,
                # below the current 10th-highest (5,400,000), above the min (7,593)
                "plays": rng.randint(8000, 4_500_000),
                "liked_by": "[]",
            })
            next_track += 1
        album["duration_minutes"] = round(total_secs / 60)

    new = {"artists": new_artists, "albums": new_albums, "tracks": new_tracks}
    for t, rows in new.items():
        print(f"{t}: +{len(rows)}")
    if dry:
        for t, rows in new.items():
            for r in rows[:3]:
                print(" ", json.dumps(r, default=str)[:170])
        return

    bdir = ROOT / "data" / "backups" / "music-expansion-2026-07-20"
    bdir.mkdir(parents=True, exist_ok=True)
    (bdir / "inserted_ids.json").write_text(json.dumps(
        {t: [r["id"] for r in rows] for t, rows in new.items()}, indent=1))

    for t, rows in new.items():
        cols = list(rows[0].keys())
        sql = (f"INSERT INTO music_{t} ({', '.join(cols)}) "
               f"VALUES ({', '.join('?' * len(cols))})")
        db.executemany(sql, [[r[c] for c in cols] for r in rows])

    # Sync external-content FTS indexes
    for t in ("artists", "albums", "tracks"):
        db.execute(f"INSERT INTO fts_music_{t}(fts_music_{t}) VALUES('rebuild')")
    db.commit()
    print(f"inserted; rollback ids at {bdir}/inserted_ids.json")


if __name__ == "__main__":
    main()
