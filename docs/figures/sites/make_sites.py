"""Websites figure (double column): (a) the site graph, (b) all 65 sites as a collage, (c) the data mix.

(a) The ring holds the 59 non-hub sites, grouped by domain; the centre holds the six hub sites. Gray edges are event-bus
links read from the site code: an event a site emits and the hub whose handler records it (app/handlers), plus 2FA codes
(request_2fa), card charges (charge_card) and direct emails (_add_email). Sign-ups (nearly every site -> VaultGuard and
WebMail) and the share button (every page -> ForumHub, PixShare, QuickChat) are noted, not drawn. Blue links are the site
sets of the cross-site human tasks (data/annotations).
Domains come from docs/MiniWeb-brainstorm-sheet.xlsx ("Website Sheet (refined)"). (b) shows the supplement's
screenshots of all 65 sites.
(c) Data sources come from each site's doc/README.md and the database build; record counts from site_records.json.
"""
import glob, json, math, os, re, sys
from collections import Counter, defaultdict

# The ring layout iterates sets of site names, whose order follows Python's per-process string-hash seed: pin it so
# every run draws the same figure (the paper's version up to 2026-10-05 came from one unrecorded seed).
if os.environ.get("PYTHONHASHSEED") != "0":
    os.execve(sys.executable, [sys.executable] + sys.argv, {**os.environ, "PYTHONHASHSEED": "0"})
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Arc, Circle, FancyBboxPatch, PathPatch, Rectangle
from matplotlib.path import Path
from matplotlib.colors import to_rgb

HERE = os.path.dirname(os.path.abspath(__file__))
import sys as _sys
_sys.path.insert(0, os.path.join(HERE, "..", "common"))   # style.py: HEADINGS, save
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
plt.rcParams.update({"font.family": "Nimbus Sans", "font.size": 6.5, "pdf.fonttype": 42, "ps.fonttype": 42})
GLYPH = "DejaVu Sans"
INK, MUTED, EDGE, BLUE, PANEL = "#14213D", "#4A5568", "#98A2B3", "#2B5C9E", "#EEF2F7"

DOMAINS = [  # (name, ring label, sites) in the sheet's order
    ("Search & reference", "Search", ["academic-paper-db", "comparison-aggregators", "qa-knowledge", "visual-how-to-guides", "wikis"]),
    ("Informational", "Info", ["business-company", "documentation-api-docs", "personal-portfolio", "project-homepages",
                               "university-academic"]),
    ("News & feeds", "Feeds", ["blogs", "news", "sports-esports", "weather"]),
    ("Shopping & transactions", "Shopping", ["auctions-p2p-marketplaces", "crowdfunding-donations", "e-commerce", "flights-hotels",
                                             "insurance-loans", "job-sites", "real-estate-buy-rent", "software-marketplace",
                                             "ticketing-events"]),
    ("Finance", "Finance", ["banking", "brokerage"]),
    ("Health", "Health", ["health-fitness-tracking", "health-portals"]),
    ("Communication", "Comms", ["ai-chatbots", "dating", "email", "instant-messaging", "remote-calls", "team-chat-workspace"]),
    ("Social media", "Social", ["forums", "multimedia-posting", "rating-review"]),
    ("Streaming & media", "Media", ["books-comics", "live", "music", "podcasts-audiobooks", "video"]),
    ("Editing", "Editing", ["code-editor-execution", "documents", "handwritten-notes-whiteboards", "spreadsheets-slides"]),
    ("Productivity", "Productivity", ["calendar-todo", "cloud-dev-consoles", "cloud-storage-file-transfer", "crm", "design-creative",
                                      "forms-surveys", "project-mgmt-issue-tracking", "version-control"]),
    ("Maps & navigation", "Maps", ["map-services", "transit-directions"]),
    ("Education", "Education", ["conference-review-submission", "course-sites-classrooms"]),
    ("Government & civic", "Civic", ["agency-portals", "petitions-voting-info", "tax-filing-dmv-permits"]),
    ("Utilities", "Utilities", ["converters-calculators", "dictionaries-language-tools", "password-managers", "translation",
                                "url-shorteners-qr"]),
]
HUBS = {"email": "WebMail", "banking": "SecureBank", "calendar-todo": "CalendarTodo",
        "cloud-storage-file-transfer": "MeridianCloud", "instant-messaging": "QuickChat", "password-managers": "VaultGuard"}
# sites seeded from a public dataset (the rest are synthetic and deterministic)
DATASET = {"academic-paper-db": "arXiv", "comparison-aggregators": "GSMArena", "qa-knowledge": "StackExchange",
           "visual-how-to-guides": "WikiHow", "wikis": "Wikipedia", "news": "Wikinews", "auctions-p2p-marketplaces": "WebShop",
           "e-commerce": "WebShop", "flights-hotels": "US flights, TBO hotels", "job-sites": "Kaggle Job Dataset",
           "real-estate-buy-rent": "Zillow, Realtor.com", "software-marketplace": "Google Play",
           "health-fitness-tracking": "USDA, Zenodo", "email": "Enron", "forums": "WebArena Reddit", "books-comics": "Common Pile",
           "project-mgmt-issue-tracking": "Jira", "version-control": "WebArena GitLab", "map-services": "OpenStreetMap",
           "conference-review-submission": "PeerRead", "dictionaries-language-tools": "Wiktionary"}
SHORT = {"banking": "SecureBank", "blogs": "TumblrVibe", "business-company": "Apex Dynamics", "cloud-dev-consoles": "CloudCore",
         "dictionaries-language-tools": "WordRef", "documentation-api-docs": "MeridianFlow Docs", "flights-hotels": "SkyLodge",
         "health-portals": "Lakeport Medical", "insurance-loans": "Cascadia Insurance", "petitions-voting-info": "Civic Hub",
         "project-homepages": "FlowNet", "software-marketplace": "AppVault", "sports-esports": "Lakeport Sports",
         "tax-filing-dmv-permits": "Gov. Services", "transit-directions": "Lakeport Transit", "translation": "LinguaBridge",
         "university-academic": "Meridian State U.", "url-shorteners-qr": "SnapLink", "visual-how-to-guides": "StepVista",
         "real-estate-buy-rent": "Lakeport Realty", "agency-portals": "City of Lakeport", "news": "Lakeport Tribune",
         "weather": "Lakeport Weather", "ai-chatbots": "AI Chatbots Hub", "personal-portfolio": "Alex Rivera (portfolio)",
         "project-mgmt-issue-tracking": "Meridian Tracker", "team-chat-workspace": "Meridian Chat",
         "ticketing-events": "Lakeport Events", "course-sites-classrooms": "EduPortal"}
# one hue per hub (dataviz reference palette; all-pairs: CVD dE 6.9 / normal dE 15.6, so hubs are always direct-labelled);
# aqua and yellow are under 3:1 on white, so hub labels stay in ink
HUB_COLOR = {"email": "#2a78d6", "banking": "#008300", "calendar-todo": "#e34948",
             "cloud-storage-file-transfer": "#1baf7a", "instant-messaging": "#4a3aa7", "password-managers": "#eda100"}
# held-out evaluation sites: the persisted train/test site split, fixed before any data was generated
HELD_OUT = set(json.load(open(os.path.join(ROOT, "data", "datagen", "site_split.json")))["test"])
HALO = "#F2C2D5"                                       # light tint of the palette's magenta, used by no hub
HUB_OF = {"purchase": ["banking", "email"], "payment": ["banking"], "trade": ["banking"], "account_reveal": ["banking"],
          "booking": ["calendar-todo", "email"], "file_created": ["cloud-storage-file-transfer", "email"], "subscribe": ["email"],
          "inquiry": ["email"], "message": ["instant-messaging"], "2fa": ["email"], "charge": ["banking"], "mail": ["email"]}


def name(s):
    if s in SHORT:
        return SHORT[s]
    t = open(os.path.join(ROOT, "sites", s, "doc", "README.md")).readline()
    return re.sub(r"^# |\s*\(`.*$", "", t).strip()


def scan_edges():
    """{(site, hub): {event, ...}} from the site code, and the sites that emit sign-up."""
    pat = {"emit": r'emit\(\s*"([a-z_]+)"', "bridge": r"\bon_(purchase|payment|booking|message|file_created|trade|subscribe|inquiry)\(",
           "2fa": r"request_2fa\(", "charge": r"charge_card\(", "mail": r"_add_email\("}
    edges, signup = defaultdict(set), set()
    for d in sorted(glob.glob(os.path.join(ROOT, "sites", "*", ""))):
        s = os.path.basename(d.rstrip("/"))
        src = "".join(open(f, errors="ignore").read() for f in glob.glob(d + "**/*.py", recursive=True))
        evs = set(re.findall(pat["emit"], src)) | set(re.findall(pat["bridge"], src))
        evs |= {k for k in ("2fa", "charge", "mail") if re.search(pat[k], src)}
        if "signup" in evs:
            signup.add(s)
        for e in evs:
            for h in HUB_OF.get(e, []):
                if h != s:
                    edges[(s, h)].add(e)
    return edges, signup


TASKS = [json.load(open(p)) for p in glob.glob(os.path.join(ROOT, "data", "annotations", "*", "*", "task.json"))]
SITES = [s for _, _, ss in DOMAINS for s in ss]
assert len(SITES) == 65 and set(SITES) == {t["site"] for t in TASKS}
EDGES, SIGNUP = scan_edges()
EDGES = {k: v for k, v in EDGES.items() if k[0] in SITES}
cross = Counter()
for t in TASKS:
    if len(t["sites"]) > 1:
        ss = sorted(t["sites"])
        for i in range(len(ss)):
            for j in range(i + 1, len(ss)):
                cross[(ss[i], ss[j])] += 1
n_cross_tasks = sum(len(t["sites"]) > 1 for t in TASKS)
REC = {k: v for k, v in json.load(open(os.path.join(HERE, "site_records.json"))).items() if not k.startswith("_")}
linked = {s for s, _ in EDGES} | set(SIGNUP) | set(HUBS)

W, H = 7.0, 2.85
fig = plt.figure(figsize=(W, H))
A = fig.add_axes([0, 0, 1, 1]); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
R = fig.canvas.get_renderer()


def width(t):
    return t.get_window_extent(R).width / fig.dpi


def title(x, y, tag, text):
    """A panel title, bold; the panel letter (`tag`) is no longer drawn (user, 2026-10-05: no (a)/(b)/(c)). Off while
    style.HEADINGS is False (2026-10-05: the headings move into the caption)."""
    from style import HEADINGS
    if HEADINGS:
        A.text(x, y, text, fontsize=7, weight="bold", color=INK, va="center")


def tint(c, a):
    r, g, b = to_rgb(c)
    return (1 - a + a * r, 1 - a + a * g, 1 - a + a * b)


def quad(p0, c, p1, color, lw, alpha, z, ls="-"):
    A.add_patch(PathPatch(Path([p0, c, p1], [Path.MOVETO, Path.CURVE3, Path.CURVE3]), fc="none", ec=color, lw=lw,
                          alpha=alpha, zorder=z, capstyle="round", ls=ls))


# ── (a) site graph ──────────────────────────────────────────────────────────
title(0.02, 0.1, "(a)", f"Website graph: {len(EDGES)} event links, {n_cross_tasks} cross-site tasks")
cx, cy, RR = 1.47, 1.29, 0.82
gap = 1.3
ring = [(d, s) for d, _, ss in DOMAINS for s in ss if s not in HUBS]
total = len(ring) + gap * len(DOMAINS)
step = 2 * math.pi / total
pos, ang, k = {}, {}, gap / 2
dom_span = {}
for d, short, ss in DOMAINS:
    a0 = None
    for s in ss:
        if s in HUBS:
            continue
        a = math.pi / 2 - (k + 0.5) * step
        ang[s], pos[s] = a, (cx + RR * math.cos(a), cy - RR * math.sin(a))
        a0 = a if a0 is None else a0
        k += 1
    dom_span[d] = (a0, a, short, len(ss))
    k += gap
# domain arcs and labels
for d, (a0, a1, short, n) in dom_span.items():
    A.add_patch(Arc((cx, cy), 2 * (RR + 0.075), 2 * (RR + 0.075), theta1=-math.degrees(a0 + step * 0.45),
                    theta2=-math.degrees(a1 - step * 0.45), color=MUTED, lw=1.0, zorder=2))
    am = (a0 + a1) / 2
    lx, ly = cx + (RR + 0.13) * math.cos(am), cy - (RR + 0.13) * math.sin(am)
    ca, sa = math.cos(am), math.sin(am)
    A.text(lx, ly, f"{short} {n}", fontsize=5.4, color=INK, va="center" if abs(sa) < 0.6 else ("bottom" if sa > 0 else "top"),
           ha="left" if ca > 0.25 else ("right" if ca < -0.25 else "center"))
# hubs on an inner hexagon, each placed toward its own domain on the ring
home = {}
for d, (a0, a1, _, _) in dom_span.items():
    for s in next(ss for dd, _, ss in DOMAINS if dd == d):
        if s in HUBS:
            home[s] = (a0 + a1) / 2
slots = [math.pi / 2 - i * math.pi / 3 for i in range(6)]
order = sorted(HUBS, key=lambda h: (math.pi / 2 - home[h]) % (2 * math.pi))
best = min(range(6), key=lambda r: sum(abs(math.atan2(math.sin(home[h] - slots[(i + r) % 6]), math.cos(home[h] - slots[(i + r) % 6])))
                                      for i, h in enumerate(order)))
hub_pos = {}
for i, h in enumerate(order):
    a = slots[(i + best) % 6]
    hub_pos[h] = (cx + 0.4 * math.cos(a), cy - 0.36 * math.sin(a))
# event links: ring site -> hub (bundled toward the centre), hub -> hub straight
for (s, h), evs in EDGES.items():
    p1 = hub_pos[h]
    if s in HUBS:
        A.plot([hub_pos[s][0], p1[0]], [hub_pos[s][1], p1[1]], color=HUB_COLOR[h], lw=0.6, alpha=0.8, zorder=2)
        continue
    p0 = pos[s]
    quad(p0, (cx + 0.42 * (p0[0] - cx), cy + 0.42 * (p0[1] - cy)), p1, HUB_COLOR[h], 0.8, 0.85, 2)
# cross-site task links
for (a, b), n in cross.items():
    pa, pb = (hub_pos.get(a) or pos[a]), (hub_pos.get(b) or pos[b])
    if a in HUBS or b in HUBS:
        ring_p = pb if a in HUBS else pa
        c = (cx + 0.42 * (ring_p[0] - cx), cy + 0.42 * (ring_p[1] - cy))
    else:
        c = (cx + 0.12 * ((pa[0] + pb[0]) / 2 - cx), cy + 0.12 * ((pa[1] + pb[1]) / 2 - cy))
    quad(pa, c, pb, INK, 0.5 + 0.25 * (n - 1), 0.75, 3, ls=(0, (2.4, 1.3)))
# nodes
def node(x, y, pub, held, z=5):
    """Circle = training site, square on a halo = held-out site; filled = public data."""
    if held:
        A.add_patch(Circle((x, y), 0.052, fc=HALO, ec="none", zorder=z - 1))
        A.add_patch(Rectangle((x - 0.029, y - 0.029), 0.058, 0.058, fc=INK if pub else "white", ec=INK, lw=0.8, zorder=z))
    else:
        A.add_patch(Circle((x, y), 0.03, fc=INK if pub else "white", ec=INK, lw=0.7, zorder=z))


for s, (x, y) in pos.items():
    node(x, y, s in DATASET, s in HELD_OUT)
for h, (x, y) in hub_pos.items():
    t = A.text(x, y, HUBS[h], fontsize=5.3, weight="bold", color=INK, ha="center", va="center", zorder=7,
               bbox=dict(boxstyle="round,pad=0.3,rounding_size=0.4", fc=tint(HUB_COLOR[h], 0.22), ec=HUB_COLOR[h], lw=0.9))
# legend (without headings: right under the ring's labels, and the empty bottom is trimmed on save)
from style import HEADINGS
ly = H - 0.4 if HEADINGS else 2.38
node(0.08, ly, True, False)
A.text(0.13, ly, "public data", fontsize=5.3, color=INK, va="center")
node(0.62, ly, False, False)
A.text(0.67, ly, "synthetic", fontsize=5.3, color=INK, va="center")
node(1.13, ly, False, True)
A.text(1.2, ly, f"held-out site, for evaluation ({len(HELD_OUT)})", fontsize=5.3, color=INK, va="center")
ly = ly + 0.1
y_leg_end = ly + 0.05
for i, c in enumerate(HUB_COLOR.values()):          # event links take their hub's color
        A.plot([0.05 + 0.035 * i, 0.08 + 0.035 * i], [ly, ly], color=c, lw=1.4, solid_capstyle="butt")
A.text(0.3, ly, "event link (to hub)", fontsize=5.3, color=INK, va="center")
A.plot([1.12, 1.3], [ly, ly], color=INK, lw=0.9, ls=(0, (2.4, 1.3)))
A.text(1.35, ly, "cross-site task", fontsize=5.3, color=INK, va="center")
# A.text(0.02, H - 0.36, f"Not drawn: sign-up on {len(SIGNUP)} sites → VaultGuard, WebMail; share button on every page.",
#        fontsize=4.9, color=MUTED, va="center", style="italic")

# ── (b) all 65 sites as a collage (user, 2026-10-06: show the benchmark's scale; replaces the list by domain) ────────
# An 11 x 8 grid of cells: DesignFlow over 3 x 3 cells, the user's other picks (sports, spreadsheet, cloud) and two
# held-out sites over 2 x 2, every other site in one cell (88 cells = 9 + 5 x 4 + 59). Held-out sites get a pink frame,
# a deeper shade of the ring's halo. The screenshots are the supplement's gallery (docs/figures/supp/figures/sites).
import random
from PIL import Image
FEATURED = {"design-creative": (0, 0, 3), "sports-esports": (0, 6, 2), "spreadsheets-slides": (2, 9, 2),   # (row, col,
            "cloud-storage-file-transfer": (3, 4, 2), "crowdfunding-donations": (5, 1, 2),             # span)
            "rating-review": (6, 7, 2)}
NCOL, NROW, GAP = 11, 8, 0.022
HELD_FRAME = "#D9528A"
bx0, bx1 = 3.12, W - 0.03
cw = (bx1 - bx0 - GAP * (NCOL - 1)) / NCOL
ch = cw * 800 / 1280                                     # the screenshots are 1280 x 800
title(bx0, 0.1, "(b)", f"All {len(SITES)} websites")
taken = set()
for r0, c0, k in FEATURED.values():
    taken |= {(r0 + i, c0 + j) for i in range(k) for j in range(k)}
rest = sorted(set(SITES) - set(FEATURED)); random.Random(0).shuffle(rest)   # a fixed mix of looks
free = [(r, c) for r in range(NROW) for c in range(NCOL) if (r, c) not in taken]
assert len(free) == len(rest), (len(free), len(rest))
place = {s: (r, c, 1) for s, (r, c) in zip(rest, free)} | FEATURED
y0 = 0.2                                                 # below the heading strip that save() trims
for s_, (r, c, k) in place.items():
    x, y = bx0 + c * (cw + GAP), y0 + r * (ch + GAP)
    w, h = k * cw + (k - 1) * GAP, k * ch + (k - 1) * GAP
    im = Image.open(os.path.join(HERE, "..", "supp", "figures", "sites", s_ + ".jpg")).convert("RGB")
    px = round(w * 450)                                  # about 1.5x the print resolution of each tile
    im = im.resize((px, round(px * 800 / 1280)), Image.LANCZOS)
    ia = fig.add_axes([x / W, 1 - (y + h) / H, w / W, h / H]); ia.imshow(im, interpolation="lanczos"); ia.axis("off")
    held = s_ in HELD_OUT
    A.add_patch(Rectangle((x, y), w, h, fc="none", ec=HELD_FRAME if held else EDGE, lw=1.1 if held else 0.4, zorder=6))
y_b_end = y0 + NROW * (ch + GAP)

# ── (c) data mix ────────────────────────────────────────────────────────────
pub = [s for s in SITES if s in DATASET]
rec_pub, rec_syn = sum(REC[s] for s in pub), sum(REC[s] for s in SITES if s not in DATASET)
cy0 = y_b_end + (0.3 if HEADINGS else 0.2)
title(bx0, cy0, "(c)", "Data mix")
bh = 0.2


def mbar(x0, w, label, a, b, fa, fb):
    t = A.text(x0, cy0, label, fontsize=5.3, color=INK, va="center")
    x0 += width(t) + 0.05
    w -= width(t) + 0.05
    wa = w * a / (a + b)
    A.add_patch(FancyBboxPatch((x0, cy0 - bh / 2), wa - 0.012, bh, boxstyle="round,pad=0,rounding_size=0.015", fc=INK,
                               ec="none"))
    A.add_patch(FancyBboxPatch((x0 + wa + 0.012, cy0 - bh / 2), w - wa - 0.012, bh,
                               boxstyle="round,pad=0,rounding_size=0.015", fc=tint(INK, 0.14), ec=INK, lw=0.5))
    A.text(x0 + 0.04, cy0 + 0.003, fa, fontsize=5.0, color="white", va="center")
    tb = A.text(x0 + w - 0.04, cy0 + 0.003, fb, fontsize=5.0, color=INK, va="center", ha="right")
    if width(tb) + 0.06 > w - wa:                     # too narrow: label just past the bar
        tb.set_position((x0 + w + 0.04, cy0 + 0.003)); tb.set_ha("left")


from style import HEADINGS
mx = 0.72 if HEADINGS else 0                             # without the "Data mix" heading the bars start at the panel edge
mbar(bx0 + mx, 1.45 + (0 if HEADINGS else 0.3), "sites", len(pub), len(SITES) - len(pub), f"{len(pub)} public",
     f"{len(SITES) - len(pub)} synthetic")
mbar(bx0 + (2.35 if HEADINGS else 1.95), 1.3 + (0 if HEADINGS else 0.3), "records", rec_pub, rec_syn,
     f"{rec_pub / 1e6:.1f}M", f"{rec_syn / 1e6:.1f}M")
ds = sorted({p.strip() for v in DATASET.values() for p in v.split(",")}, key=str.lower)
# words, lines, cur = ("Public datasets: " + ", ".join(ds)).split(" "), [], ""
# for wd in words:                                       # wrap to the panel width
#     probe = A.text(0, 0, (cur + " " + wd).strip(), fontsize=5.0)
#     if width(probe) > bx1 - bx0 - 0.02 and cur:
#         lines.append(cur); cur = wd
#     else:
#         cur = (cur + " " + wd).strip()
#     probe.remove()
# lines.append(cur)
# A.text(bx0, cy0 + 0.09, "\n".join(lines), fontsize=5.0, color=MUTED, va="top", linespacing=1.25)

out = os.path.join(HERE, "sites")
from style import save
y_end = max(y_leg_end, cy0 + bh / 2) + 0.04              # lowest content (inches from the top)
save(fig, out, strip=0.18, bottom=0 if HEADINGS else max(0.0, H - y_end))   # trims the heading strip and empty bottom
print("wrote", out, f"| edges {len(EDGES)} from {len({s for s, _ in EDGES})} sites | signup {len(SIGNUP)} | linked {len(linked)}"
      f" | linked non-hub {len(linked - set(HUBS))} | cross pairs {len(cross)} tasks {n_cross_tasks} | public {len(pub)} rec {rec_pub:,}/{rec_syn:,} | b ends {y_b_end:.2f}")
