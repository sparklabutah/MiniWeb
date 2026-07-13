"""Expand brokerage: ~500 new securities + per-symbol price history table.

- Creates brokerage_price_data (symbol PK, data JSON) and migrates the 26
  existing symbols into it; the legacy one-row price_history table is left
  untouched as backup.
- Adds ~500 synthetic tickers (stocks/ETFs/crypto/futures) with a year of
  daily bars and one day of intraday bars each, matching existing formats.
- Adds option chains for the 60 largest new stocks.
- Deterministic (seeded per symbol) so regeneration is reproducible.
- Existing 26 tickers, orders, portfolios, users, watchlists are untouched.
"""
import sqlite3, json, math, random, itertools, string
from datetime import date, timedelta

DB = 'data/trimmed_miniweb.db'
db = sqlite3.connect(DB)

existing = {r[0] for r in db.execute('SELECT symbol FROM brokerage_tickers')}
print('existing symbols:', len(existing))

# ── trading calendar: reuse AAPL's dates so all symbols align ────────────────
aapl = json.loads(db.execute("SELECT aapl FROM brokerage_price_history").fetchone()[0])
DATES = [d['date'] for d in aapl['daily']]
INTRA_TIMES = [p['time'] for p in aapl['intraday']]
LAST_DAY = aapl['intraday'][0]['date']
print('calendar:', DATES[0], '->', DATES[-1], f'({len(DATES)} days), intraday', LAST_DAY)

SECTORS = {
    'Technology': 70, 'Healthcare': 45, 'Financial Services': 45,
    'Consumer Cyclical': 40, 'Industrials': 40, 'Energy': 25,
    'Consumer Defensive': 25, 'Communication Services': 20,
    'Utilities': 20, 'Real Estate': 20, 'Basic Materials': 20,
}
PREFIX = {
    'Technology': ['Quantum', 'Nexa', 'Cyber', 'Data', 'Cloud', 'Neuro', 'Photon', 'Vertex', 'Silicon', 'Hyper'],
    'Healthcare': ['Bio', 'Gene', 'Medi', 'Cura', 'Vital', 'Helix', 'Nova', 'Thera', 'Onco', 'Pharma'],
    'Financial Services': ['Summit', 'Anchor', 'Meridian', 'Pinnacle', 'Sterling', 'Granite', 'Harbor', 'Crown', 'Fort', 'Legacy'],
    'Consumer Cyclical': ['Urban', 'Style', 'Peak', 'Drive', 'Luxe', 'Trend', 'Swift', 'Metro', 'Prime', 'Volt'],
    'Industrials': ['Iron', 'Forge', 'Titan', 'Mach', 'Steel', 'Apex', 'Core', 'Dyna', 'Grid', 'Bolt'],
    'Energy': ['Petro', 'Solar', 'Wind', 'Terra', 'Fuel', 'Ridge', 'Basin', 'Delta', 'Crest', 'Flare'],
    'Consumer Defensive': ['Fresh', 'Farm', 'Daily', 'Pantry', 'Pure', 'Golden', 'Harvest', 'Home', 'Value', 'Crisp'],
    'Communication Services': ['Signal', 'Echo', 'Wave', 'Link', 'Cast', 'Stream', 'Pulse', 'Voice', 'Beam', 'Relay'],
    'Utilities': ['Amp', 'Hydro', 'Volt', 'Power', 'Current', 'Spark', 'Meter', 'Utility', 'Line', 'Charge'],
    'Real Estate': ['Land', 'Brick', 'Tower', 'Estate', 'Plaza', 'Haven', 'Keystone', 'Gate', 'Park', 'Domain'],
    'Basic Materials': ['Ore', 'Alloy', 'Quarry', 'Timber', 'Mineral', 'Carbon', 'Silica', 'Copper', 'Ferro', 'Chem'],
}
SUFFIX = ['Systems', 'Holdings', 'Group', 'Corp', 'Industries', 'Labs', 'Technologies', 'Partners',
          'Dynamics', 'Works', 'Solutions', 'Networks', 'Capital', 'Sciences', 'Materials', 'Energy',
          'Health', 'Media', 'Logistics', 'Robotics']

rng = random.Random(20260713)
used_syms = set(existing)

def make_symbol(name):
    base = ''.join(c for c in name.upper() if c.isalpha())
    for ln in (3, 4, 5):
        for start in range(0, min(4, len(base) - ln + 1)):
            cand = base[start:start + ln]
            if cand not in used_syms and len(cand) == ln:
                used_syms.add(cand); return cand
    while True:
        cand = ''.join(rng.choice(string.ascii_uppercase) for _ in range(4))
        if cand not in used_syms:
            used_syms.add(cand); return cand

def gen_history(sym, base_price, vol):
    r = random.Random(sym)
    price = base_price * r.uniform(0.7, 1.1)
    daily = []
    for dt in DATES:
        drift = r.gauss(0.0004, vol)
        o = price
        c = max(0.5, o * (1 + drift))
        hi = max(o, c) * (1 + abs(r.gauss(0, vol / 2)))
        lo = min(o, c) * (1 - abs(r.gauss(0, vol / 2)))
        daily.append({'date': dt, 'open': round(o, 2), 'high': round(hi, 2),
                      'low': round(lo, 2), 'close': round(c, 2),
                      'volume': int(abs(r.gauss(1, 0.5)) * 2_000_000) + 50_000})
        price = c
    intra = []
    p = daily[-1]['open']
    for t in INTRA_TIMES:
        p = max(0.5, p * (1 + r.gauss(0, vol / 3)))
        intra.append({'time': t, 'price': round(p, 2),
                      'volume': int(abs(r.gauss(1, 0.4)) * 300_000) + 10_000, 'date': LAST_DAY})
    return {'daily': daily, 'intraday': intra}

new_tickers, price_rows = [], []
row_id = db.execute('SELECT MAX(row_id) FROM brokerage_tickers').fetchone()[0]

# stocks
for sector, count in SECTORS.items():
    for _ in range(count):
        name = f"{rng.choice(PREFIX[sector])}{rng.choice(['', ' '])}{rng.choice(SUFFIX)}"
        sym = make_symbol(name.replace(' ', ''))
        base = round(rng.choice([rng.uniform(4, 40), rng.uniform(20, 150), rng.uniform(80, 900)]), 2)
        cap = round(rng.choice([rng.uniform(0.4, 8), rng.uniform(5, 80), rng.uniform(50, 600), rng.uniform(300, 2400)]), 1)
        row_id += 1
        new_tickers.append((row_id, sym, name, 'stock', sector,
                            rng.choice(['NYSE', 'NASDAQ']), base, cap, 0, ''))
        price_rows.append((sym.lower(), json.dumps(gen_history(sym, base, 0.02))))

# ETFs
ETF_THEMES = ['Dividend', 'Growth', 'Value', 'Clean Energy', 'Semiconductor', 'Biotech', 'Bond',
              'Emerging Markets', 'Europe', 'Japan', 'Gold Miners', 'Infrastructure', 'AI & Robotics',
              'Cybersecurity', 'Cloud Computing', 'Small Cap Value', 'Mid Cap', 'REIT', 'Utilities Select', 'Momentum']
for i in range(60):
    theme = ETF_THEMES[i % len(ETF_THEMES)]
    name = f"{rng.choice(['Meridian', 'Cascade', 'Summit', 'Pioneer', 'Northstar'])} {theme} ETF"
    sym = make_symbol(name.replace(' ', ''))
    base = round(rng.uniform(18, 320), 2)
    row_id += 1
    new_tickers.append((row_id, sym, name, 'index_fund', 'Broad Market' if 'Cap' in theme else theme,
                        'NYSE ARCA', base, round(rng.uniform(1, 120), 1), 0, ''))
    price_rows.append((sym.lower(), json.dumps(gen_history(sym, base, 0.011))))

# crypto
CRYPTOS = ['Lumen', 'Nebula', 'Cinder', 'Raptor', 'Glyph', 'Orbit', 'Prism', 'Quark', 'Ember', 'Drift',
           'Vortex', 'Zephyr', 'Onyx', 'Krypton', 'Falcon', 'Comet', 'Nimbus', 'Pylon', 'Rune', 'Atlas',
           'Beacon', 'Cipher', 'Dune', 'Flux', 'Gale', 'Halo', 'Ion', 'Jade', 'Karma', 'Loom']
for cname in CRYPTOS:
    name = f'{cname} Coin' if rng.random() < 0.5 else cname
    sym = make_symbol(cname)
    base = round(rng.choice([rng.uniform(0.01, 2), rng.uniform(1, 80), rng.uniform(50, 4000)]), 4)
    row_id += 1
    new_tickers.append((row_id, sym, name, 'crypto', 'Cryptocurrency', 'Crypto', base,
                        round(rng.uniform(0.1, 90), 1), 0, ''))
    price_rows.append((sym.lower(), json.dumps(gen_history(sym, base, 0.045))))

# futures
FUTS = [('Wheat', 'W2'), ('Corn', 'C2'), ('Soybeans', 'S2'), ('Copper', 'HG'), ('Silver', 'SI'),
        ('Platinum', 'PL'), ('Natural Gas', 'NG'), ('Heating Oil', 'HO'), ('Coffee', 'KC'),
        ('Sugar', 'SB'), ('Cotton', 'CT'), ('Lumber', 'LB'), ('Cocoa', 'CC'), ('Oats', 'O2'),
        ('Palladium', 'PA'), ('Gasoline', 'RB'), ('Lean Hogs', 'HE'), ('Live Cattle', 'LE'),
        ('Rough Rice', 'RR'), ('Orange Juice', 'OJ')]
for fname, fsym in FUTS:
    if fsym in used_syms: fsym = make_symbol(fname)
    else: used_syms.add(fsym)
    base = round(rng.uniform(2, 2400), 2)
    row_id += 1
    new_tickers.append((row_id, fsym, f'{fname} Futures', 'futures', 'Commodity Futures',
                        'CME', base, 0, rng.choice([50, 100, 1000, 5000]), '2026-09-18'))
    price_rows.append((fsym.lower(), json.dumps(gen_history(fsym, base, 0.016))))

print('new tickers:', len(new_tickers), '| price rows:', len(price_rows))

# ── write: new price_data table + migrate existing 26 ───────────────────────
db.execute('CREATE TABLE IF NOT EXISTS brokerage_price_data (symbol TEXT PRIMARY KEY, data TEXT)')
old_cols = [d[1] for d in db.execute('PRAGMA table_info(brokerage_price_history)')][1:]
old_row = db.execute('SELECT * FROM brokerage_price_history').fetchone()[1:]
db.executemany('INSERT OR REPLACE INTO brokerage_price_data (symbol, data) VALUES (?, ?)',
               list(zip(old_cols, old_row)))
db.executemany('INSERT OR REPLACE INTO brokerage_price_data (symbol, data) VALUES (?, ?)', price_rows)
db.execute("INSERT OR REPLACE INTO site_registry (site, collection, table_name, pk_column) "
           "VALUES ('brokerage', 'price_data', 'brokerage_price_data', 'symbol')")

db.executemany('INSERT INTO brokerage_tickers (row_id, symbol, name, type, sector, exchange, '
               'base_price, market_cap_b, contract_size, expiry) VALUES (?,?,?,?,?,?,?,?,?,?)',
               new_tickers)

# ── option chains for 60 largest new stocks ─────────────────────────────────
oid = db.execute('SELECT MAX(id) FROM brokerage_options').fetchone()[0]
big = sorted([t for t in new_tickers if t[3] == 'stock'], key=lambda t: -t[7])[:60]
opt_rows = []
for t in big:
    sym, base = t[1], t[6]
    r = random.Random('opt' + sym)
    for expiry in ['2026-07-17', '2026-08-21', '2026-10-16']:
        for k in range(-3, 4):
            strike = round(base * (1 + k * 0.05), 1)
            for typ in ('call', 'put'):
                oid += 1
                itm = (base - strike) if typ == 'call' else (strike - base)
                prem = round(max(0.05, itm + base * r.uniform(0.01, 0.05)), 2)
                delta = round(min(0.99, max(0.01, 0.5 + (itm / base) * 2 + r.uniform(-0.05, 0.05))), 2)
                if typ == 'put': delta = round(-delta, 2)
                opt_rows.append((oid, sym, typ, strike, expiry, prem,
                                 round(r.uniform(0.15, 0.85), 2), delta,
                                 round(r.uniform(0.001, 0.05), 3), round(-r.uniform(0.01, 0.12), 3),
                                 round(r.uniform(0.05, 0.4), 3),
                                 int(r.uniform(50, 20000)), int(r.uniform(0, 5000))))
db.executemany('INSERT INTO brokerage_options VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', opt_rows)
print('options added:', len(opt_rows))

db.commit()
print('tickers now:', db.execute('SELECT COUNT(*) FROM brokerage_tickers').fetchone()[0])
print('price_data rows:', db.execute('SELECT COUNT(*) FROM brokerage_price_data').fetchone()[0])
print('options now:', db.execute('SELECT COUNT(*) FROM brokerage_options').fetchone()[0])
print('fin services cap now:', db.execute("SELECT SUM(market_cap_b) FROM brokerage_tickers WHERE sector='Financial Services'").fetchone()[0])
