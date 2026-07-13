"""Tier-2 data expansion with task-answer invariants (2026-07-13 audit).

Sites: banking, cloud-storage, cloud-dev logs, calendar-todo, remote-calls,
crm, wikis. Each section states the invariant that protects the annotated
tasks touching that site. Deterministic; existing rows untouched; rerunnable.
"""
import sqlite3, json, random
from datetime import datetime, timedelta

DB = 'data/trimmed_miniweb.db'
db = sqlite3.connect(DB)
db.row_factory = sqlite3.Row
rng = random.Random(20260714)

# ════════════════════════════════════════════════════════════════════════════
# 1. BANKING — transactions 220 → ~4,200, cc_transactions 130 → ~1,900
#    INVARIANT: all new rows dated 2023-01-01 .. 2024-12-31, before any
#    window referenced by annotated tasks.
# ════════════════════════════════════════════════════════════════════════════
if db.execute('SELECT COUNT(*) FROM banking_transactions').fetchone()[0] < 1000:
    accounts = [dict(r) for r in db.execute('SELECT id, user_id FROM banking_accounts')]
    MERCH = ['Lakeport Grocers', 'Cascade Coffee Roasters', 'Northshore Utilities', 'StreamHub',
             'Pacific Gas', 'Trailhead Outfitters', 'Metro Transit', 'Lakeport Pharmacy',
             'Harbor Bistro', 'CloudCore Hosting', 'BookNook', 'Peak Fitness', 'City Parking',
             'SkyLodge Travel', 'Evergreen Insurance', 'Corner Hardware', 'Fresh Farms Market',
             'The Daily Grind', 'Lakeport Cinema', 'AutoCare Plus']
    CATS = ['groceries', 'dining', 'utilities', 'entertainment', 'transport', 'health',
            'shopping', 'travel', 'insurance', 'subscriptions']
    tmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM banking_transactions').fetchone()[0] or 0
    rows = []
    for i in range(4000):
        tmax += 1
        acct = rng.choice(accounts)
        day = datetime(2023, 1, 1) + timedelta(days=rng.uniform(0, 729))
        debit = rng.random() < 0.82
        amount = round(-rng.uniform(3, 240), 2) if debit else round(rng.uniform(200, 3200), 2)
        merch = rng.choice(MERCH)
        rows.append((tmax, acct['id'], acct['user_id'], day.strftime('%Y-%m-%d'),
                     merch if debit else rng.choice(['Payroll — Meridian Systems', 'Transfer in', 'Refund — ' + merch]),
                     amount, 'debit' if debit else 'credit',
                     rng.choice(CATS) if debit else 'income',
                     'posted', f'TXN-{tmax:07d}'))
    db.executemany('INSERT INTO banking_transactions VALUES (?,?,?,?,?,?,?,?,?,?)', rows)

    cmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM banking_cc_transactions').fetchone()[0] or 0
    cc_users = [r['user_id'] for r in db.execute('SELECT DISTINCT user_id FROM banking_cc_transactions')]
    cc_rows = []
    for i in range(1800):
        cmax += 1
        day = datetime(2023, 1, 1) + timedelta(days=rng.uniform(0, 729))
        cc_rows.append((cmax, rng.choice(cc_users), day.strftime('%Y-%m-%d'), rng.choice(MERCH),
                        round(rng.uniform(4, 380), 2), rng.choice(CATS), 'posted',
                        rng.choice(['Card purchase', 'Online purchase', 'Recurring charge'])))
    db.executemany('INSERT INTO banking_cc_transactions VALUES (?,?,?,?,?,?,?,?)', cc_rows)
    print('banking txns:', db.execute('SELECT COUNT(*) FROM banking_transactions').fetchone()[0],
          '| cc txns:', db.execute('SELECT COUNT(*) FROM banking_cc_transactions').fetchone()[0])
else:
    print('banking already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 2. CLOUD STORAGE — files 53 → ~450 (+13 folders), with near-duplicate names
#    INVARIANTS: starred=0 on every new file (task a22a6a: starred count = 5);
#    nothing added to the 'Projects' folder (task 782835 enumerates its PDFs);
#    no 'roadmap'-like names (task a67234 searches 'Q4 roadmap').
# ════════════════════════════════════════════════════════════════════════════
if db.execute('SELECT COUNT(*) FROM cloud_storage_file_transfer_files').fetchone()[0] < 300:
    projects_id = db.execute("SELECT id FROM cloud_storage_file_transfer_folders WHERE name='Projects'").fetchone()
    projects_id = projects_id[0] if projects_id else -1
    fol_max = db.execute('SELECT MAX(CAST(id AS INT)) FROM cloud_storage_file_transfer_folders').fetchone()[0] or 0
    users = [r['id'] for r in db.execute('SELECT id FROM cloud_storage_file_transfer_users')]
    NEW_FOLDERS = ['Archive 2024', 'Design Assets', 'Meeting Notes', 'Vendor Contracts', 'Onboarding',
                   'Data Exports', 'Marketing', 'Legal', 'Screenshots', 'Templates', 'Budgets',
                   'Research', 'Recruiting']
    folder_ids = []
    frows = []
    for name in NEW_FOLDERS:
        fol_max += 1
        folder_ids.append(fol_max)
        frows.append((fol_max, name, 0, rng.choice(users),
                      (datetime(2024, 1, 1) + timedelta(days=rng.uniform(0, 800))).strftime('%Y-%m-%dT%H:%M:%SZ'),
                      rng.choice(['#4285f4', '#0f9d58', '#f4b400', '#db4437', '#ab47bc'])))
    db.executemany('INSERT INTO cloud_storage_file_transfer_folders VALUES (?,?,?,?,?,?)', frows)

    BASE_NAMES = ['Design review', 'Budget summary', 'Interview notes', 'Sprint retro', 'Vendor quote',
                  'Launch checklist', 'Meeting minutes', 'Performance report', 'Campaign brief',
                  'Onboarding checklist', 'Architecture sketch', 'Test plan', 'Salary bands',
                  'Offsite agenda', 'Security audit', 'API spec', 'Competitor analysis',
                  'Customer interviews', 'Brand guidelines', 'Quarterly metrics']
    # near-duplicate suffixes are the point — they punish sloppy target selection
    SUFFIX = ['', ' v2', ' v3', ' (final)', ' FINAL', ' (1)', ' — copy', ' draft', ' OLD', ' updated']
    EXT = [('.docx', 'document'), ('.pdf', 'document'), ('.xlsx', 'spreadsheet'),
           ('.pptx', 'presentation'), ('.png', 'image'), ('.csv', 'spreadsheet'), ('.txt', 'document')]
    fmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM cloud_storage_file_transfer_files').fetchone()[0] or 0
    rows = []
    for i in range(400):
        fmax += 1
        base = rng.choice(BASE_NAMES)
        ext, ftype = rng.choice(EXT)
        name = base + rng.choice(SUFFIX) + ext
        owner = rng.choice(users)
        fid = rng.choice(folder_ids + [0, 0])
        created = datetime(2024, 1, 1) + timedelta(days=rng.uniform(0, 850))
        rows.append((fmax, name, f'/files/{fmax}', rng.randint(4_000, 90_000_000), ftype,
                     '', owner, created.strftime('%Y-%m-%dT%H:%M:%SZ'),
                     (created + timedelta(days=rng.uniform(0, 200))).strftime('%Y-%m-%dT%H:%M:%SZ'),
                     '', fid, 0, 0, '', ''))
    assert all(r[11] == 0 for r in rows), 'starred invariant'
    assert all(r[10] != projects_id for r in rows), 'Projects folder invariant'
    assert not any('roadmap' in r[1].lower() for r in rows), 'roadmap name invariant'
    db.executemany('INSERT INTO cloud_storage_file_transfer_files VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    print('cloud files:', db.execute('SELECT COUNT(*) FROM cloud_storage_file_transfer_files').fetchone()[0],
          '| starred total:', db.execute('SELECT COUNT(*) FROM cloud_storage_file_transfer_files WHERE starred=1').fetchone()[0])
else:
    print('cloud-storage already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 3. CLOUD-DEV LOGS — 2,000 → ~30,000 (pagination already in place)
#    INVARIANT: only the logs table; no metrics/db/instance changes.
# ════════════════════════════════════════════════════════════════════════════
if db.execute('SELECT COUNT(*) FROM cloud_dev_consoles_logs').fetchone()[0] < 10000:
    CATS = ['Analytics', 'Compute', 'Database', 'DevTools', 'Integration',
            'Monitoring', 'Networking', 'Security', 'Storage']
    MSGS = {
        'INFO': ['Deployment completed for {s}', 'Health check passed for {s}',
                 'Autoscaling event: {s} scaled to {n} replicas', 'Config reloaded on {s}',
                 'Certificate renewed for {s}', 'Scheduled snapshot for {s} finished',
                 'Cache warmed for {s}', 'Job queue drained on {s}'],
        'WARN': ['Elevated latency on {s}: p99 {n}ms', 'Memory usage above 80% on {s}',
                 'Retry storm detected on {s}', 'Throttling requests on {s}',
                 'Disk usage at {n}% on {s}', 'Slow query detected on {s}'],
        'ERROR': ['Connection refused from {s}', 'Unhandled exception in {s} worker',
                  'Timeout calling upstream from {s}', '5xx spike on {s}: {n} errors/min',
                  'OOM kill on {s}', 'Deadlock detected on {s}'],
    }
    services = [r['name'] for r in db.execute('SELECT name FROM cloud_dev_consoles_services')]
    lid = db.execute("SELECT MAX(CAST(SUBSTR(id, 5) AS INT)) FROM cloud_dev_consoles_logs").fetchone()[0] or 0
    rows = []
    for i in range(28000):
        lid += 1
        level = rng.choices(['INFO', 'WARN', 'ERROR'], [7, 2, 1])[0]
        svc = rng.choice(services)
        when = datetime(2026, 6, 26) - timedelta(days=rng.uniform(0, 90), hours=rng.uniform(0, 24))
        rows.append((f'log-{lid:05d}', when.strftime('%Y-%m-%dT%H:%M:%SZ'), level, svc,
                     rng.choice(MSGS[level]).format(s=svc, n=rng.randint(2, 97)),
                     rng.choice(['app', 'system', 'network', 'deploy']),
                     rng.choice(CATS), f'trace-{rng.randint(100000, 999999)}'))
    db.executemany('INSERT INTO cloud_dev_consoles_logs VALUES (?,?,?,?,?,?,?,?)', rows)
    print('cloud-dev logs:', db.execute('SELECT COUNT(*) FROM cloud_dev_consoles_logs').fetchone()[0])
else:
    print('cloud-dev logs already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 4. CALENDAR — +700 events in 2025 and 2027 ONLY
#    INVARIANTS: nothing in 2026 (protects the Jul 6–19 window = 27 events,
#    event 334, and the Jun 16 morning slot).
# ════════════════════════════════════════════════════════════════════════════
n_2025_2027 = db.execute("SELECT COUNT(*) FROM calendar_todo_events WHERE start LIKE '2027%'").fetchone()[0]
if n_2025_2027 < 100:
    TITLES = [('Team sync', 'work'), ('Client call', 'work'), ('Design workshop', 'work'),
              ('Doctor appointment', 'health'), ('Gym session', 'health'), ('Yoga', 'health'),
              ('Dinner with friends', 'personal'), ('Movie night', 'personal'),
              ('Weekend hike', 'personal'), ('Budget review', 'work'), ('Dentist', 'health'),
              ('Book club', 'personal'), ('1:1 with manager', 'work'), ('Meal prep', 'personal')]
    CAL = {'work': 'Work', 'personal': 'Personal', 'health': 'Health'}
    COLORS = {'work': '#4285f4', 'personal': '#0b8043', 'health': '#d50000'}
    emax = db.execute('SELECT MAX(id) FROM calendar_todo_events').fetchone()[0]
    rows = []
    for i in range(700):
        emax += 1
        year = rng.choice([2025, 2025, 2027])
        month = rng.randint(1, 6 if year == 2025 else 12) if year == 2025 else rng.randint(1, 12)
        day = rng.randint(1, 28)
        h = rng.randint(6, 20)
        title, cat = rng.choice(TITLES)
        dur = rng.choice([30, 60, 60, 90, 120])
        start = datetime(year, month, day, h, rng.choice([0, 30]))
        end = start + timedelta(minutes=dur)
        rows.append((emax, rng.choice([1, 2, 3, 12, 16]), title, f'{title} ({CAL[cat]})', cat,
                     CAL[cat], start.strftime('%Y-%m-%dT%H:%M:%S'), end.strftime('%Y-%m-%dT%H:%M:%S'),
                     0, '', '', 15, rng.choice(['low', 'medium', 'high']), 'confirmed', '[]',
                     COLORS[cat], start.strftime('%Y-%m-%dT%H:%M:%S')))
    assert not any(r[6].startswith('2026') for r in rows), '2026 invariant'
    db.executemany('INSERT INTO calendar_todo_events VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)', rows)
    win = db.execute("SELECT COUNT(*) FROM calendar_todo_events WHERE start >= '2026-07-06' AND start < '2026-07-20'").fetchone()[0]
    print('calendar events:', db.execute('SELECT COUNT(*) FROM calendar_todo_events').fetchone()[0],
          '| protected window still:', win)
    assert win == 27, 'calendar window invariant broken!'
else:
    print('calendar already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 5. REMOTE CALLS — meetings 18 → ~160, call_log 25 → ~420, recordings 6 → ~46
#    INVARIANT: no new meeting titled like 'Engineering Standup' (task 707134:
#    Priya = most frequent completed-standup host).
# ════════════════════════════════════════════════════════════════════════════
if db.execute('SELECT COUNT(*) FROM remote_calls_meetings').fetchone()[0] < 100:
    rc_users = [r['id'] for r in db.execute('SELECT id FROM remote_calls_users')]
    M_TITLES = ['Design Critique', 'Customer Onboarding Call', 'Quarterly Review', 'Bug Triage',
                'Vendor Sync', 'Marketing Weekly', 'Data Review', 'Roadmap Session',
                'Hiring Debrief', 'Support Escalation', 'Release Go/No-Go', 'Budget Sync',
                'All Hands', 'Partner Demo', 'Security Review']
    mm = db.execute('SELECT COUNT(*) FROM remote_calls_meetings').fetchone()[0]
    mrows, rrows = [], []
    rec_n = db.execute('SELECT COUNT(*) FROM remote_calls_recordings').fetchone()[0]
    for i in range(140):
        mm += 1
        mid = f'mtg-{mm + 100:03d}'
        title = f'{rng.choice(M_TITLES)}'
        host = rng.choice(rc_users)
        parts = rng.sample(rc_users, rng.randint(2, 6))
        when = datetime(2026, 6, 26) - timedelta(days=rng.uniform(0, 400))
        dur = rng.choice([15, 25, 30, 45, 60, 90])
        status = 'completed' if when < datetime(2026, 6, 26) else 'scheduled'
        rec = rng.random() < 0.22 and status == 'completed'
        mrows.append((mid, title, host, json.dumps(parts), when.strftime('%Y-%m-%dT%H:%M:%S-07:00'),
                      dur, rng.choice(['video', 'video', 'audio']), rec, status))
        if rec:
            rec_n += 1
            rrows.append((f'rec-{rec_n:03d}', mid, title, host,
                          when.strftime('%Y-%m-%dT%H:%M:%S-07:00'), dur,
                          round(dur * rng.uniform(1.8, 3.2), 1), rng.choice(['mp4', 'mp4', 'webm']),
                          f'https://callhub.io/recordings/rec-{rec_n:03d}.mp4',
                          rng.random() < 0.6, rng.choice(['team', 'team', 'private']),
                          rng.randint(0, 30)))
    assert not any('standup' in r[1].lower() for r in mrows), 'standup invariant'
    db.executemany('INSERT INTO remote_calls_meetings VALUES (?,?,?,?,?,?,?,?,?)', mrows)
    db.executemany('INSERT INTO remote_calls_recordings VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', rrows)

    clmax = db.execute('SELECT COUNT(*) FROM remote_calls_call_log').fetchone()[0]
    clrows = []
    for i in range(395):
        clmax += 1
        a, b = rng.sample(rc_users, 2)
        when = datetime(2026, 6, 26) - timedelta(days=rng.uniform(0, 300))
        status = rng.choices(['completed', 'missed', 'declined'], [7, 2, 1])[0]
        clrows.append((f'rc-cl-{clmax:04d}', a, b, rng.choice(['video', 'audio']),
                       when.strftime('%Y-%m-%dT%H:%M:%S-07:00'),
                       rng.randint(30, 3600) if status == 'completed' else 0, status, ''))
    db.executemany('INSERT INTO remote_calls_call_log VALUES (?,?,?,?,?,?,?,?)', clrows)
    print('remote-calls meetings:', db.execute('SELECT COUNT(*) FROM remote_calls_meetings').fetchone()[0],
          '| recordings:', db.execute('SELECT COUNT(*) FROM remote_calls_recordings').fetchone()[0],
          '| call_log:', db.execute('SELECT COUNT(*) FROM remote_calls_call_log').fetchone()[0])
else:
    print('remote-calls already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 6. CRM — companies 10 → ~60, contacts 20 → ~160, deals 12 → ~90,
#    activities 30 → ~460
#    INVARIANT: no new activities for Lisa Engstrom's contact_id (task fd6aca:
#    her most recent meeting stays 'demo'); no new contact named Lisa Engstrom.
# ════════════════════════════════════════════════════════════════════════════
if db.execute('SELECT COUNT(*) FROM crm_contacts').fetchone()[0] < 100:
    lisa = db.execute("SELECT id FROM crm_contacts WHERE name LIKE '%Engstrom%'").fetchone()
    lisa_id = lisa[0] if lisa else -1
    FIRSTC = ['Noah', 'Petra', 'Rafael', 'Sana', 'Tobias', 'Ulrika', 'Victor', 'Willa', 'Xander',
              'Yvette', 'Zach', 'Nadia', 'Oskar', 'Paloma', 'Ruben', 'Selma', 'Tristan', 'Vera']
    LASTC = ['Nystrom', 'Okonkwo', 'Palacios', 'Qureshi', 'Ramsey', 'Solberg', 'Takeda',
             'Urbina', 'Voss', 'Whitfield', 'Yamada', 'Zellner', 'Norwood', 'Ortega', 'Pruitt']
    INDUSTRIES = ['SaaS', 'Manufacturing', 'Healthcare', 'Retail', 'Logistics', 'Finance', 'Education']
    PRODUCTS = ['SalesPro CRM', 'Analytics Suite', 'Support Desk', 'Data Pipeline', 'Mobile SDK']
    STAGES = ['prospecting', 'qualification', 'proposal', 'negotiation', 'closed_won', 'closed_lost']
    ACT_TYPES = ['call', 'email', 'meeting', 'demo', 'note']
    crm_users = [r['id'] for r in db.execute('SELECT id FROM crm_users')]

    co_max = db.execute('SELECT MAX(CAST(id AS INT)) FROM crm_companies').fetchone()[0] or 0
    ct_max = db.execute('SELECT MAX(CAST(id AS INT)) FROM crm_contacts').fetchone()[0] or 0
    dl_max = db.execute('SELECT MAX(CAST(id AS INT)) FROM crm_deals').fetchone()[0] or 0
    ac_max = db.execute('SELECT MAX(CAST(id AS INT)) FROM crm_activities').fetchone()[0] or 0

    cos, cts, dls, acs = [], [], [], []
    A1 = ['North', 'Blue', 'Iron', 'Summit', 'Cedar', 'Bright', 'Stone', 'Rapid', 'Clear', 'Grand']
    A2 = ['peak', 'field', 'works', 'line', 'bridge', 'forge', 'view', 'point', 'gate', 'haven']
    seen_co = {r['name'] for r in db.execute('SELECT name FROM crm_companies')}
    new_contact_ids = []
    for i in range(50):
        name = f'{rng.choice(A1)}{rng.choice(A2)}'.title() + rng.choice([' Inc', ' LLC', ' Group', ' Co'])
        if name in seen_co: continue
        seen_co.add(name)
        co_max += 1
        cos.append((str(co_max), name, rng.choice(INDUSTRIES), rng.choice(['1-50', '51-200', '201-1000', '1000+']),
                    f'https://{name.split()[0].lower()}.example.com', 'Lakeport, WA',
                    rng.randint(1, 400) * 100000, rng.choice(['active', 'active', 'prospect']),
                    '', rng.choice(crm_users),
                    (datetime(2024, 1, 1) + timedelta(days=rng.uniform(0, 800))).strftime('%Y-%m-%d'), ''))
        for k in range(rng.randint(1, 4)):
            ct_max += 1
            fn, ln = rng.choice(FIRSTC), rng.choice(LASTC)
            new_contact_ids.append(str(ct_max))
            cts.append((str(ct_max), fn, ln, f'{fn} {ln}',
                        f'{fn.lower()}.{ln.lower()}@{name.split()[0].lower()}.example.com',
                        f'(360) 555-{rng.randint(1000, 9999)}',
                        rng.choice(['CEO', 'CTO', 'VP Sales', 'Engineering Manager', 'Procurement Lead',
                                    'Operations Director', 'Product Manager']),
                        str(co_max), rng.choice(['active', 'active', 'lead']), rng.choice(crm_users),
                        (datetime(2024, 1, 1) + timedelta(days=rng.uniform(0, 800))).strftime('%Y-%m-%d'),
                        (datetime(2026, 1, 1) + timedelta(days=rng.uniform(0, 170))).strftime('%Y-%m-%d'), ''))
    for i in range(78):
        dl_max += 1
        cid = rng.choice(new_contact_ids)
        dls.append((str(dl_max), f'{rng.choice(PRODUCTS)} — {rng.choice(list(seen_co))}',
                    str(rng.randint(11, co_max)), cid, rng.choice(crm_users), rng.choice(PRODUCTS),
                    rng.choice(STAGES), rng.randint(2, 250) * 1000, rng.choice([10, 25, 50, 75, 90]),
                    (datetime(2026, 3, 1) + timedelta(days=rng.uniform(0, 300))).strftime('%Y-%m-%d'),
                    (datetime(2025, 6, 1) + timedelta(days=rng.uniform(0, 350))).strftime('%Y-%m-%d'), ''))
    for i in range(430):
        ac_max += 1
        cid = rng.choice(new_contact_ids)
        acs.append((str(ac_max), rng.choice(ACT_TYPES),
                    rng.choice(['Intro call', 'Follow-up', 'Pricing discussion', 'Renewal check-in',
                                'Technical questions', 'Contract review', 'Quarterly business review']),
                    cid, str(rng.randint(1, dl_max)), rng.choice(crm_users),
                    (datetime(2025, 1, 1) + timedelta(days=rng.uniform(0, 540))).strftime('%Y-%m-%d'),
                    rng.choice([15, 30, 30, 45, 60]), ''))
    assert not any(a[3] == str(lisa_id) for a in acs), 'Lisa Engstrom activity invariant'
    assert not any('Engstrom' in c[3] for c in cts), 'Lisa name invariant'
    db.executemany('INSERT INTO crm_companies VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', cos)
    db.executemany('INSERT INTO crm_contacts VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', cts)
    db.executemany('INSERT INTO crm_deals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)', dls)
    db.executemany('INSERT INTO crm_activities VALUES (?,?,?,?,?,?,?,?,?)', acs)
    print('crm companies:', db.execute('SELECT COUNT(*) FROM crm_companies').fetchone()[0],
          '| contacts:', db.execute('SELECT COUNT(*) FROM crm_contacts').fetchone()[0],
          '| deals:', db.execute('SELECT COUNT(*) FROM crm_deals').fetchone()[0],
          '| activities:', db.execute('SELECT COUNT(*) FROM crm_activities').fetchone()[0])
else:
    print('crm already expanded, skipping')

# ════════════════════════════════════════════════════════════════════════════
# 7. WIKIS — pages 31 → ~130 (+ revisions)
#    INVARIANTS: every new page's views > current minimum (task 301c31: the
#    least-viewed article stays the same); existing view counts untouched.
# ════════════════════════════════════════════════════════════════════════════
if db.execute('SELECT COUNT(*) FROM wikis_pages').fetchone()[0] < 100:
    min_views = db.execute('SELECT MIN(views) FROM wikis_pages').fetchone()[0]
    cats = [r['name'] for r in db.execute('SELECT name FROM wikis_categories')]
    wiki_users = [r['id'] for r in db.execute('SELECT id FROM wikis_users')]
    SUBJECTS = ['Lakeport Ferry System', 'Cascade Ridge Observatory', 'North Shore Farmers Market',
                'Lakeport Jazz Festival', 'Meridian Systems (company)', 'Cedar Park Amphitheater',
                'Lakeport Public Transit', 'Harbor Lighthouse', 'Washington Hiking Trails',
                'Lakeport City Council', 'Pacific Northwest Climate', 'Lakeport Historical Society',
                'StreamHub (streaming service)', 'Lakeport Marathon', 'Local Craft Breweries',
                'Community Garden Program', 'Lakeport School District', 'Regional Bird Species',
                'Waterfront Redevelopment', 'Lakeport Film Festival', 'Tech Industry in Lakeport',
                'Lakeport Bridges', 'Emergency Services', 'Public Art Installations', 'Annual Events']
    pmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM wikis_pages').fetchone()[0] or 0
    rmax = db.execute('SELECT MAX(CAST(id AS INT)) FROM wikis_revisions').fetchone()[0] or 0
    prows, rrows = [], []
    used_slugs = {r['slug'] for r in db.execute('SELECT slug FROM wikis_pages')}
    # bounded candidate list — a while-loop over a finite combo space can spin forever
    candidates = [s + v for v in ['', ' (history)', ' (overview)', ' (list)'] for s in SUBJECTS]
    for title in candidates:
        if len(prows) >= 100:
            break
        slug = title.lower().replace(' ', '-').replace('(', '').replace(')', '')
        if slug in used_slugs: continue
        used_slugs.add(slug)
        pmax += 1
        created = datetime(2024, 6, 1) + timedelta(days=rng.uniform(0, 700))
        content = (f'== {title} ==\n\n{title} is a notable part of the Lakeport region. '
                   f'This article covers its history, significance, and current status.\n\n'
                   f'=== History ===\nEstablished in {rng.randint(1902, 2018)}, it has grown steadily.\n\n'
                   f'=== See also ===\n* Lakeport, Washington\n* North Shore District')
        views = min_views + rng.randint(50, 12000)
        prows.append((str(pmax), title, slug, content, rng.choice(cats), rng.choice(wiki_users),
                      created.strftime('%Y-%m-%d'),
                      (created + timedelta(days=rng.uniform(0, 300))).strftime('%Y-%m-%d'),
                      views, '[]'))
        for k in range(rng.randint(1, 4)):
            rmax += 1
            rrows.append((str(rmax), str(pmax), rng.choice(wiki_users),
                          (created + timedelta(days=rng.uniform(0, 250))).strftime('%Y-%m-%dT%H:%M:%SZ'),
                          rng.choice(['Fixed typos', 'Added history section', 'Updated statistics',
                                      'Added references', 'Expanded intro', 'Reverted vandalism']),
                          rng.randint(1, 60), rng.randint(0, 25)))
    assert all(p[8] > min_views for p in prows), 'min-views invariant'
    db.executemany('INSERT INTO wikis_pages VALUES (?,?,?,?,?,?,?,?,?,?)', prows)
    db.executemany('INSERT INTO wikis_revisions VALUES (?,?,?,?,?,?,?)', rrows)
    new_min = db.execute('SELECT MIN(views) FROM wikis_pages').fetchone()[0]
    print('wiki pages:', db.execute('SELECT COUNT(*) FROM wikis_pages').fetchone()[0],
          '| revisions:', db.execute('SELECT COUNT(*) FROM wikis_revisions').fetchone()[0],
          '| min views unchanged:', new_min == min_views)
else:
    print('wikis already expanded, skipping')

db.commit()
print('tier 2 done')
