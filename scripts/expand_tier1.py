"""Tier-1 data expansion: email, team-chat, instant-messaging,
multimedia-posting, music.

These sites carry ZERO annotated tasks (verified 2026-07-13), so expansion
cannot invalidate any expected answer. Deterministic (seeded); existing rows
untouched; safe to rerun against another DB copy (skips if already expanded).
"""
import sqlite3, json, random
from datetime import datetime, timedelta

DB = 'data/trimmed_miniweb.db'
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
rng = random.Random(20260714)

def ts(start_days_ago, span_days):
    t = datetime(2026, 6, 26) - timedelta(days=rng.uniform(start_days_ago - span_days, start_days_ago))
    return t

FIRST = ['Ava', 'Ben', 'Chloe', 'Dan', 'Elena', 'Femi', 'Grace', 'Hugo', 'Iris', 'Jon',
         'Kira', 'Leo', 'Mona', 'Nils', 'Omar', 'Pia', 'Quinn', 'Rae', 'Sven', 'Tess',
         'Uma', 'Vik', 'Wren', 'Ximena', 'Yara', 'Zane']
LAST = ['Adler', 'Brooks', 'Castillo', 'Dietrich', 'Eze', 'Fontaine', 'Grimaldi', 'Hale',
        'Iversen', 'Jha', 'Kowalski', 'Lindgren', 'Moreau', 'Nakamura', 'Obi', 'Petrova',
        'Quist', 'Rocha', 'Sandoval', 'Tanaka', 'Ueda', 'Vance', 'Weiss', 'Xu', 'Yilmaz', 'Zeman']

# ════════════════════════════════════════════════════════════════════════════
# 1. EMAIL — 500 → ~8,000 raw messages
# ════════════════════════════════════════════════════════════════════════════
n_email = db.execute('SELECT COUNT(*) FROM email_emails').fetchone()[0]
if n_email < 2000:
    users = [dict(r) for r in db.execute('SELECT * FROM email_users')]
    addrs = [u['email_address'] for u in users if u.get('email_address')]
    SENDERS = ([f'{f.lower()}.{l.lower()}@meridiansystems.com' for f, l in zip(FIRST, LAST)] +
               ['billing@cloudcore.io', 'noreply@streamhub.tv', 'updates@lakeportwiki.org',
                'newsletter@formflow.app', 'support@tradevista.com', 'alerts@callhub.io',
                'no-reply@skylodge.travel', 'team@knowledgehub.dev', 'receipts@shopmart.com',
                'security@meridiansystems.com'])
    SUBJ = ['Re: {t} follow-up', '{t} — action needed', 'Weekly digest: {t}', 'Invoice #{n} for {t}',
            'Your {t} receipt', 'Reminder: {t} on {d}', 'Fwd: {t} notes', '{t} status update',
            'Question about {t}', '[{tag}] {t} review request', 'Meeting notes — {t}', 'RE: RE: {t}']
    TOPICS = ['Q3 planning', 'the API migration', 'sprint 48', 'the offsite', 'expense report',
              'the design review', 'onboarding docs', 'security training', 'the demo environment',
              'contract renewal', 'the marketing site', 'database upgrade', 'the beta launch',
              'performance reviews', 'the conference talk', 'load testing', 'customer feedback',
              'the roadmap deck', 'hiring pipeline', 'incident 4821']
    BODY_BITS = [
        'Just wanted to follow up on this before the end of the week.',
        'Let me know if you have any questions or need more context.',
        'Attached are the notes from our last discussion.',
        'Can you review this by Thursday? It blocks the next step.',
        'Thanks for your patience while we sorted this out.',
        'Quick summary below — full details in the thread.',
        'This should only take a few minutes to confirm.',
        'Flagging this since the deadline moved up.',
        'No action needed if you already responded to the earlier thread.',
        'Adding the wider team so everyone has visibility.',
    ]
    rows = []
    mid_base = 900000
    for i in range(7500):
        topic = rng.choice(TOPICS)
        subj = rng.choice(SUBJ).format(t=topic, n=rng.randint(10000, 99999),
                                       d=ts(rng.randint(1, 300), 1).strftime('%b %d'),
                                       tag=rng.choice(['design', 'eng', 'ops', 'finance']))
        to_addr = rng.choice(addrs)
        sender = rng.choice(SENDERS)
        cc = rng.choice(addrs) if rng.random() < 0.15 and len(addrs) > 1 else ''
        if cc == to_addr:
            cc = ''
        body = ' '.join(rng.sample(BODY_BITS, rng.randint(2, 4)))
        body = f'Hi,\n\n{body}\n\nBest,\n{sender.split("@")[0].split(".")[0].title()}'
        when = ts(rng.uniform(1, 540), 1)
        rows.append((sender, to_addr, cc, subj,
                     when.strftime('%a, %d %b %Y %H:%M:%S -0700'),
                     body, f'<gen-{mid_base + i}@miniweb.local>', ''))
    db.executemany('INSERT INTO email_emails (from_, [to], cc, subject, date, body, message_id, path) '
                   'VALUES (?,?,?,?,?,?,?,?)', rows)
    print('email_emails:', db.execute('SELECT COUNT(*) FROM email_emails').fetchone()[0])
else:
    print('email already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 2. TEAM CHAT — 85 → ~3,000 messages
# ════════════════════════════════════════════════════════════════════════════
n_msg = db.execute('SELECT COUNT(*) FROM team_chat_workspace_messages').fetchone()[0]
if n_msg < 1000:
    channels = [r['id'] for r in db.execute('SELECT id FROM team_chat_workspace_channels')]
    tc_users = [r['id'] for r in db.execute('SELECT id FROM team_chat_workspace_users')]
    CHAT = ['Anyone looked at the failing build on main?', 'Merged — thanks for the quick review!',
            "I'll take that ticket.", 'Standup in 5.', 'The staging deploy is done.',
            'Can someone sanity-check my numbers in the sheet?', 'PSA: office closed Friday.',
            'That fixed it, nice catch.', 'Pushing the fix now.', 'Lunch orders due at 11:30.',
            'New dashboard is live, feedback welcome.', 'Who owns the on-call rotation this week?',
            'Docs updated with the new endpoints.', 'Retro notes posted in the wiki.',
            'Heads up: dependency bump coming.', 'Demo went great — recording shared.',
            "Let's move this to a thread.", 'Reminder to fill out the survey.',
            'The metrics look off since the deploy — investigating.', '+1, ship it.']
    mmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM team_chat_workspace_messages').fetchone()[0] or 0
    rows = []
    for ch in channels:
        base = datetime(2026, 6, 26) - timedelta(days=200)
        t = base
        for i in range(290):
            mmax += 1
            t += timedelta(minutes=rng.uniform(20, 900))
            rows.append((str(mmax), ch, rng.choice(tc_users), t.strftime('%Y-%m-%dT%H:%M:%SZ'),
                         rng.choice(CHAT), 0, rng.choice([0, 0, 0, 1, 2]), rng.choice([0, 0, 0, 0, 1])))
    db.executemany('INSERT INTO team_chat_workspace_messages VALUES (?,?,?,?,?,?,?,?)', rows)
    print('team_chat messages:', db.execute('SELECT COUNT(*) FROM team_chat_workspace_messages').fetchone()[0])
else:
    print('team-chat already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 3. INSTANT MESSAGING — 96 → ~2,600 messages
# ════════════════════════════════════════════════════════════════════════════
n_im = db.execute('SELECT COUNT(*) FROM instant_messaging_messages').fetchone()[0]
if n_im < 1000:
    convs = [dict(r) for r in db.execute('SELECT * FROM instant_messaging_conversations')]
    TALK = ['On my way!', 'Did you see the game last night?', 'Running 10 min late, sorry',
            'Can you send me that photo?', 'haha exactly', 'What time works for you?',
            "Let's do Thursday instead", 'Just landed ✈️', 'Happy birthday!! 🎉',
            'Did you get my last message?', 'Call me when you can', 'That place was amazing',
            'ok sounds good', 'Thanks again for yesterday', 'Movie tonight?', 'yes!!',
            'I will check and get back to you', 'lol', 'See you soon', 'Where are we meeting?']
    immax = db.execute('SELECT MAX(CAST(id AS INT)) FROM instant_messaging_messages').fetchone()[0] or 0
    rows = []
    for cv in convs:
        parts = json.loads(cv['participants']) if isinstance(cv['participants'], str) else cv['participants']
        base = datetime(2026, 6, 26) - timedelta(days=180)
        t = base
        for i in range(rng.randint(220, 360)):
            immax += 1
            t += timedelta(minutes=rng.uniform(3, 700))
            rows.append((str(immax), cv['id'], str(rng.choice(parts)),
                         t.strftime('%Y-%m-%dT%H:%M:%SZ'), rng.choice(TALK), 1, ''))
    db.executemany('INSERT INTO instant_messaging_messages VALUES (?,?,?,?,?,?,?)', rows)
    print('im messages:', db.execute('SELECT COUNT(*) FROM instant_messaging_messages').fetchone()[0])
else:
    print('instant-messaging already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 4. MULTIMEDIA POSTING — 40 → ~600 posts, 50 → ~2,400 comments
# ════════════════════════════════════════════════════════════════════════════
n_posts = db.execute('SELECT COUNT(*) FROM multimedia_posting_posts').fetchone()[0]
if n_posts < 300:
    mp_users = [r['id'] for r in db.execute('SELECT id FROM multimedia_posting_users')]
    CAPTIONS = ['Golden hour never disappoints', 'Weekend vibes', 'New recipe attempt — verdict below',
                'Trail views from this morning', 'Coffee first ☕', 'Throwback to last summer',
                'Finally finished this project!', 'City lights', 'Fresh from the farmers market',
                'Study buddy', 'Rainy day reads', 'Game night!', 'First attempt at pottery',
                'Sunset from the pier', 'New personal record today', 'Little garden update']
    LOCS = ['Lakeport Waterfront', 'Downtown Lakeport', 'North Shore Trail', 'Harbor Marina',
            'Cedar Park', '', '', '']
    TAGS = ['photography', 'foodie', 'hiking', 'fitness', 'art', 'travel', 'books', 'music',
            'coffee', 'sunset', 'diy', 'nature']
    COMMENTS = ['Love this! 😍', 'Where is this?', 'Incredible shot', 'Recipe please!',
                'This made my day', 'Goals!', 'So jealous right now', 'Amazing colors',
                'We need to go here together', 'Congrats!!', '🔥🔥🔥', 'Beautiful',
                'Saving this for later', 'How long did it take?', 'Teach me your ways']
    pmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM multimedia_posting_posts').fetchone()[0] or 0
    cmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM multimedia_posting_comments').fetchone()[0] or 0
    posts, comments = [], []
    for i in range(560):
        pmax += 1
        author = rng.choice(mp_users)
        when = ts(rng.uniform(1, 500), 1)
        n_c = rng.choice([0, 0, 1, 2, 3, 4, 6])
        posts.append((str(pmax), author, 'image', f'/static/generated/mp_{pmax}.jpg',
                      rng.choice(CAPTIONS), rng.choice(LOCS), rng.randint(0, 900), n_c,
                      when.strftime('%Y-%m-%dT%H:%M:%SZ'),
                      json.dumps(rng.sample(TAGS, rng.randint(1, 3))), '', ''))
        for k in range(n_c):
            cmax += 1
            comments.append((str(cmax), str(pmax), rng.choice(mp_users), rng.choice(COMMENTS),
                             rng.randint(0, 40),
                             (when + timedelta(hours=rng.uniform(0.2, 90))).strftime('%Y-%m-%dT%H:%M:%SZ'),
                             ''))
    db.executemany('INSERT INTO multimedia_posting_posts VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', posts)
    db.executemany('INSERT INTO multimedia_posting_comments VALUES (?,?,?,?,?,?,?)', comments)
    print('mp posts:', db.execute('SELECT COUNT(*) FROM multimedia_posting_posts').fetchone()[0],
          '| comments:', db.execute('SELECT COUNT(*) FROM multimedia_posting_comments').fetchone()[0])
else:
    print('multimedia already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 5. MUSIC — 25 artists / 30 albums / 60 tracks → 85 / ~190 / ~1,300
# ════════════════════════════════════════════════════════════════════════════
n_tracks = db.execute('SELECT COUNT(*) FROM music_tracks').fetchone()[0]
if n_tracks < 500:
    GENRES = ['Indie Rock', 'Synthwave', 'Jazz', 'Lo-fi', 'Folk', 'Electronic', 'Hip-Hop',
              'Classical', 'Ambient', 'R&B', 'Post-Rock', 'House']
    A1 = ['Velvet', 'Neon', 'Paper', 'Silver', 'Wild', 'Golden', 'Midnight', 'Electric',
          'Hollow', 'Crystal', 'Static', 'Lunar', 'Coral', 'Ember', 'Glass']
    A2 = ['Foxes', 'Harbor', 'Arcade', 'Meridian', 'Pines', 'Motive', 'Tides', 'Parade',
          'Signals', 'Gardens', 'Youth', 'Mirrors', 'Council', 'Anthem', 'Fields']
    T1 = ['Falling', 'Northern', 'Golden', 'Empty', 'Silent', 'Racing', 'Paper', 'Hollow',
          'Electric', 'Fading', 'Distant', 'Broken', 'Winter', 'Neon', 'Slow']
    T2 = ['Lights', 'Hearts', 'Streets', 'Rivers', 'Echoes', 'Motion', 'Skies', 'Weekend',
          'Youth', 'Shadows', 'Signals', 'Horizon', 'Currents', 'Reverie', 'Bloom']
    amax = db.execute('SELECT MAX(CAST(id AS INT)) FROM music_artists').fetchone()[0] or 0
    almax = db.execute('SELECT MAX(CAST(id AS INT)) FROM music_albums').fetchone()[0] or 0
    tmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM music_tracks').fetchone()[0] or 0
    artists, albums, tracks = [], [], []
    seen_names = {r['name'] for r in db.execute('SELECT name FROM music_artists')}
    while len(artists) < 60:
        name = f'{rng.choice(A1)} {rng.choice(A2)}'
        if name in seen_names: continue
        seen_names.add(name)
        amax += 1
        g = rng.choice(GENRES)
        n_albums = rng.randint(1, 4)
        artists.append((str(amax), name, g, f'{name} is a {g.lower()} project from the Pacific Northwest.',
                        n_albums, rng.randint(1200, 2_400_000), rng.random() < 0.3))
        for a in range(n_albums):
            almax += 1
            n_tr = rng.randint(6, 12)
            year = rng.randint(2015, 2026)
            albums.append((str(almax), str(amax), f'{rng.choice(T1)} {rng.choice(T2)}',
                           f'{year}-{rng.randint(1,12):02d}-{rng.randint(1,28):02d}', g, n_tr,
                           0, f'#{rng.randint(0, 0xFFFFFF):06x}'))
            total_min = 0
            for tn in range(1, n_tr + 1):
                tmax += 1
                dur = rng.randint(140, 420)
                total_min += dur
                tracks.append((str(tmax), str(almax), str(amax),
                               f'{rng.choice(T1)} {rng.choice(T2)}', dur, tn,
                               rng.randint(500, 5_000_000), '[]'))
            albums[-1] = albums[-1][:6] + (round(total_min / 60), albums[-1][7])
    db.executemany('INSERT INTO music_artists VALUES (?,?,?,?,?,?,?)', artists)
    db.executemany('INSERT INTO music_albums VALUES (?,?,?,?,?,?,?,?)', albums)
    db.executemany('INSERT INTO music_tracks VALUES (?,?,?,?,?,?,?,?)', tracks)
    print('music artists:', db.execute('SELECT COUNT(*) FROM music_artists').fetchone()[0],
          '| albums:', db.execute('SELECT COUNT(*) FROM music_albums').fetchone()[0],
          '| tracks:', db.execute('SELECT COUNT(*) FROM music_tracks').fetchone()[0])
else:
    print('music already expanded, skipping')

db.commit()
print('tier 1 done')
