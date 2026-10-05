"""Single-column teaser (Fig. 1), three bands:
  MiniWeb      six sites tagged with the skill they exercise; on each, a badge with the ten untrained agents' mean success
               on that skill (Tab. 2), coloured red (10%) to green (50%); drag & gesture, the weakest skill of every agent, is red;
  pipeline     MiniWebGen's verified single-skill data training MiniWebAgent's executor, as coloured chevrons;
  results      practice alone (single agent, untrained vs trained) and practice + compose (single agent vs MiniWebAgent),
               the change above each pair. Numbers are printed as Figs. 6-7 print them (MiniWebAgent with a decimal).
Numbers come from the paper's run lists: Tab. 2's judge files for the badges, tables_config.yaml for the bars (single
primitives average three runs, as in Fig. 6; held-out tasks and WebArena-Lite use each arm's first run, as in Fig. 7).
Screenshots and highlight boxes come from capture.py (a local MiniWeb server, 1280x800 viewport, 2x).

    python docs/figures/teaser/make_teaser.py
"""
import json, os, statistics as st, sys
import yaml
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, Polygon, Rectangle
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
sys.path.insert(0, os.path.join(HERE, "..", "rq1"))
from results import ROOT, task_rates, primitive_filter  # noqa: E402
from make_rq1_bars import collect  # noqa: E402  (also chdirs to the repo root)
SERIF = "--serif" in sys.argv                             # sans by default (user, 2026-10-05); --serif -> teaser_serif.*
FONT, MONO = ("Nimbus Roman", "Nimbus Mono PS") if SERIF else ("Nimbus Sans", "DejaVu Sans Mono")
plt.rcParams.update({"font.family": FONT, "font.size": 6.5, "pdf.fonttype": 42, "ps.fonttype": 42, "hatch.linewidth": 0.9,
                     "axes.linewidth": 0.6, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "xtick.major.size": 2.5, "ytick.major.size": 2.5, "xtick.minor.size": 1.5})
INK, MUTED, BLUE, GREY, OKC, RED = "#14213D", "#4A5568", "#2B5C9E", "#7D8798", "#2E7D32", "#C62828"
FAM = {"Drag & gesture": "#6B4C9A", "Discrete selection": "#2B5C9E", "Text entry": "#2E7D6B",
       "Form transaction": "#A8520F", "Out-of-page I/O": "#A33B4C", "Reasoning base": "#14213D"}
tint = lambda c, a: tuple(1 - a + a * v for v in matplotlib.colors.to_rgb(c))
SCALE = (10, 50)                                         # badge colour: red at 10% success, amber at 30%, green at 50%
_RYG = matplotlib.colors.LinearSegmentedColormap.from_list("ryg", ["#C62828", "#D98A00", "#2E8540"])
badge_color = lambda v: _RYG(min(max((v - SCALE[0]) / (SCALE[1] - SCALE[0]), 0), 1))

# ── data ────────────────────────────────────────────────────────────────────
RQ1 = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "rq1", "rq1_config.yaml")))
only = primitive_filter(RQ1.get("primitives"))
fam_r, op_r = {}, {}
for m in RQ1["models"]:
    r = collect(m["judge"], only)
    for f, (k, n) in r["family"].items():
        if n:
            fam_r.setdefault(f, []).append(100 * k / n)
    for o, (k, n) in r["op"].items():
        if n:
            op_r.setdefault(o, []).append(100 * k / n)
FAM_MEAN = {f: st.mean(v) for f, v in fam_r.items()}
OP_MEAN = {o: st.mean(v) for o, v in op_r.items()}

TCFG = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "tables", "tables_config.yaml")))


def rate(arm, bench, first=False):
    b, runs = TCFG["benchmarks"][bench], TCFG["runs"][arm][bench]
    runs = runs[:1] if first else runs
    return st.mean(task_rates(b["kind"], runs, b.get("tasks"), only=primitive_filter(b.get("primitives"))))


PRACTICE = [("single\nprimitives", rate("base", "single"), rate("pooled", "single")),
            ("held-out\ntasks", rate("base", "heldout"), rate("pooled", "heldout"))]      # MiniWeb: mean of 3 runs
COMPOSE = [("held-out\ntasks", rate("base", "heldout"), rate("planner_pooled", "heldout")),
           ("WebArena-\nLite", rate("base", "wa"), rate("planner_pooled", "wa")),          # WA: mean of 3 runs
           ("Web-\nVoyager", rate("base", "wv"), rate("planner_pooled", "wv")),
           ("Online-\nMind2Web", rate("base", "om2w"), rate("planner_pooled", "om2w"))]

# tile: screenshot key, site name, skill tag, family, badge value (the agents' mean success on that skill), crop box,
# badge corner (kept clear of the highlighted control)
TILES = [
    ("shop", "ShopHub", "filter_by_slider", "Drag & gesture", FAM_MEAN["Drag & gesture"], (0, 200, 576, 560), "tr"),
    ("bank", "SecureBank", "pay_by_form", "Form transaction", FAM_MEAN["Form transaction"], (472, 210, 1080, 590), "bl"),
    ("calendar", "CalendarTodo", "report_information · count", "Reasoning base", OP_MEAN["count"], (500, 58, 1108, 438), "tr"),
    ("travel", "SkyLodge", "filter_by_date_range", "Discrete selection", FAM_MEAN["Discrete selection"], (470, 440, 1046, 800), "tl"),
    ("sheet", "SheetDeck", "edit_by_cell", "Text entry", FAM_MEAN["Text entry"], (0, 0, 576, 360), "tr"),
    ("video", "StreamHub", "upload_file", "Out-of-page I/O", FAM_MEAN["Out-of-page I/O"], (300, 85, 980, 510), "tr"),
]
BOX = json.load(open(os.path.join(HERE, "boxes.json")))

# ── canvas: inches from the top-left corner; O is an overlay for badges, pills, and chevrons ────────────────────
from style import HEADINGS  # noqa: E402  (headings move into the caption, 2026-10-05)
W, FH = 3.25, (4.19 if HEADINGS else 3.51)
LY0 = 0.27 if HEADINGS else 0.1                         # the badge key's row
fig = plt.figure(figsize=(W, FH))
ax_at = lambda x, y, w, h: fig.add_axes([x / W, 1 - (y + h) / FH, w / W, h / FH])
O = fig.add_axes([0, 0, 1, 1], zorder=10); O.set_xlim(0, W); O.set_ylim(FH, 0); O.axis("off"); O.patch.set_alpha(0)
width = lambda t: t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi


def pill(x, y, text, fc, size=6.4):
    """A rounded coloured label, white bold text, left edge at x, centred on y; returns its right edge."""
    t = O.text(x + 0.07, y, text, fontsize=size, weight="bold", color="white", va="center", zorder=3)
    w = width(t) + 0.14
    O.add_patch(FancyBboxPatch((x, y - 0.075), w, 0.15, boxstyle="round,pad=0,rounding_size=0.075", fc=fc, ec="none",
                               zorder=2))
    return x + w


WEB_C, AGENT_C = "#5B2E91", BLUE                        # the two names, flat and largest in the figure


def wordmark(x, y, text, color, size=11.0):
    """A product name as large bold flat text, left edge at x, centred on y; returns its right edge. In the serif variant
    it is set in bold small caps, as the paper's \\miniweb{} and \\miniwebagent{} macros set it."""
    if not SERIF:
        t = O.text(x, y, text, fontsize=size, weight="bold", color=color, va="center", zorder=4)
        return x + width(t)
    base = y + 0.34 * size / 72                          # the baseline that centres the capitals on y
    i = 0
    while i < len(text):                                 # runs of capitals at full size, lower case as smaller capitals
        j = i
        while j < len(text) and text[j].isupper() == text[i].isupper():
            j += 1
        run = text[i:j]
        t = O.text(x, base, run.upper(), fontsize=size if run[0].isupper() else size * 0.78, weight="bold", color=color,
                   va="baseline", zorder=4)
        x += width(t) - 0.011 * size / 11                # close the side bearings between runs
        i = j
    return x


# ── MiniWeb: sites, skills, and the agents' success on each skill ───────────
if HEADINGS:
    x = wordmark(0.02, 0.12, "MiniWeb", WEB_C)
    O.text(x + 0.09, 0.135, "65 synthetic sites built around 37 skills", fontsize=6.8, color=INK, va="center")
x = 0.02                                                 # legend: what a badge is, its red-to-green key, the finding
for txt, kw in (("badge: 10 untrained agents' mean success", dict(color=MUTED)), ("10%", dict(color=MUTED, fontsize=5.0))):
    t = O.text(x, LY0, txt, va="center", **{"fontsize": 5.9, **kw})
    x += width(t) + (0.05 if SERIF else 0.025)
for k in range(40):
    O.add_patch(Rectangle((x + 0.0062 * k, LY0 - 0.03), 0.0066, 0.06, fc=_RYG(k / 39), ec="none"))
x += 0.25 + 0.025
t = O.text(x, LY0, "50%", fontsize=5.0, color=MUTED, va="center")
x += width(t) + 0.06
O.text(x, LY0, "drag: weakest for all 10", fontsize=5.8, color=RED, weight="bold", va="center")
gap, left, top = 0.05, 0.02, (0.38 if HEADINGS else 0.21)
tw = (W - 2 * left - 2 * gap) / 3
th = tw * 0.625
cb = 0.085                                   # browser-window bar above each screenshot, with the site name
pitch = cb + th + 0.15
for i, (key, site, macro, fam, badge, (x0, y0, x1, y1), corner) in enumerate(TILES):
    r, c = divmod(i, 3)
    tx, ty = left + c * (tw + gap), top + r * pitch
    bar = ax_at(tx, ty, tw, cb)
    bar.set_xlim(0, tw); bar.set_ylim(cb, 0); bar.set_xticks([]); bar.set_yticks([])
    bar.set_facecolor(tint(FAM[fam], 0.16))
    for sp in bar.spines.values(): sp.set_color(tint(FAM[fam], 0.45)); sp.set_linewidth(0.6)
    for k, dc in enumerate(("#E0675E", "#E6B54A", "#6BBF6A")):
        bar.add_patch(matplotlib.patches.Circle((0.045 + k * 0.045, cb / 2), 0.0135, color=dc, lw=0))
    bar.text(tw / 2, cb / 2 + 0.002, site, ha="center", va="center", fontsize=5.0, weight="bold", color=INK)
    ax = ax_at(tx, ty + cb, tw, th)
    im = Image.open(os.path.join(HERE, "shots", f"t_{key}.png")).convert("RGB")
    s = im.width / 1280
    ax.imshow(im.crop((int(x0 * s), int(y0 * s), int(x1 * s), int(y1 * s))), extent=(x0, x1, y1, y0), interpolation="lanczos")
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color(tint(FAM[fam], 0.45)); sp.set_linewidth(0.6)
    bx = BOX.get(key)
    if bx:
        bx_x, bx_y, bw, bh = bx; pad = 4
        ax.add_patch(Rectangle((bx_x - pad, bx_y - pad), bw + 2 * pad, bh + 2 * pad, fill=False, ec=FAM[fam], lw=1.3))
    O.text(tx + 0.025, ty + cb + th + 0.075, macro, fontsize=4.6, family=MONO, weight="bold" if SERIF else "normal",
           color="white", va="center", ha="left", bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.3", fc=FAM[fam], ec="none"))
    weak = fam == "Drag & gesture"                      # the badge: the agents' mean success on this skill
    rb = 0.125 if weak else 0.105
    bxc = tx + tw - rb - 0.03 if corner[1] == "r" else tx + rb + 0.03
    byc = ty + cb + rb + 0.03 if corner[0] == "t" else ty + cb + th - rb - 0.03
    O.add_patch(Circle((bxc, byc), rb, fc=badge_color(badge), ec="white", lw=1.0, zorder=4))
    O.text(bxc, byc + 0.003, f"{badge:.0f}%", fontsize=6.2 if weak else 5.4, weight="bold", color="white", ha="center",
           va="center", zorder=5)

# ── pipeline: coloured chevrons ─────────────────────────────────────────────
sy = top + 2 * pitch - 0.15 + 0.33
steps = [("one generator\nper skill", "#6B4C9A"), ("3.1K verified\ntrajectories", "#A8520F"),
         ("27.6K training\nsteps", "#2E7D6B"), ("4B planner +\ntrained executor", AGENT_C)]
n, cw, ch, notch = len(steps), (W - 0.04 + 3 * 0.07) / 4, 0.28, 0.09
for j, (t, col) in enumerate(steps):
    x0 = 0.02 + j * (cw - 0.07)
    pts = [(x0, sy - ch / 2), (x0 + cw - notch, sy - ch / 2), (x0 + cw, sy), (x0 + cw - notch, sy + ch / 2),
           (x0, sy + ch / 2)] + ([(x0 + notch, sy)] if j else [])
    last = j == len(steps) - 1                           # the data steps in light tints; the executor in MiniWebAgent blue
    O.add_patch(Polygon(pts, closed=True, fc=col if last else tint(col, 0.22), ec="white", lw=1.2, zorder=2))
    O.text(x0 + cw / 2 + (0.03 if j else -0.01), sy, t, fontsize=5.7, color="white" if last else col,
           weight="bold" if last else "normal", ha="center", va="center", linespacing=1.0, zorder=3)

# ── results: practice alone, and practice + compose ─────────────────────────
py = sy + (0.28 if HEADINGS else 0.2)
if HEADINGS:
    O.text(0.02, py + 0.06, "Practice alone", fontsize=7.4, weight="bold", color="#2E7D6B", va="center")
    O.text(0.02, py + 0.27, "primitives improve,\ntasks do not", fontsize=6.4, color=INK, va="center", linespacing=1.05)
    x = wordmark(1.3, py + 0.05, "MiniWebAgent", AGENT_C)
    O.text(x + 0.06, py + 0.065, "practice + compose", fontsize=6.0, color=MUTED, va="center")
    O.text(1.3, py + 0.27, "tasks improve,\non the real web too", fontsize=6.4, color=INK, va="center", linespacing=1.05)
ly, x = py + (0.53 if HEADINGS else 0.1), 0.26                                    # one legend row: the bars' three arms
for lab, col, hatch, bold in (("single agent, untrained", GREY, False, False), ("trained", BLUE, False, False),
                              ("MiniWebAgent", BLUE, True, True)):
    O.add_patch(Rectangle((x, ly - 0.045), 0.14, 0.09, fc=tint(col, 0.28) if hatch else col, ec=col, lw=1.0,
                          hatch="////" if hatch else None))
    t = O.text(x + 0.19, ly, lab, va="center", fontsize=6.8 if bold else 6.5, color=BLUE if bold else INK,
               weight="bold" if bold else "normal")
    x += 0.19 + width(t) + 0.2
top_b = py + (0.68 if HEADINGS else 0.25)
ph = FH - top_b - 0.33


def pairs(ax, rows, after_hatch):
    """Two bars per group, untrained single agent (grey) and the trained arm (blue), the change above in bold."""
    for gi, (lab, b, a) in enumerate(rows):
        for k, (v, col, hatch) in enumerate(((b, GREY, False), (a, BLUE, after_hatch))):
            x = gi + (k - 0.5) * 0.38
            ax.bar(x, v, 0.34, color=tint(col, 0.28) if hatch else col, edgecolor=col, hatch="////" if hatch else None,
                   lw=1.0 if hatch else 0, zorder=2)
            lab_v = f"{v:.1f}" if (k and after_hatch) else f"{v:.0f}"   # as Fig. 7 prints them: MiniWebAgent with a decimal
            ax.text(x, v + 2, lab_v, ha="center", va="bottom", fontsize=6.0,
                    color=(BLUE if after_hatch else INK) if k else MUTED, weight="bold" if k else "normal")
        d = a - b
        ax.text(gi, max(a, b) + 15, f"{d:+.0f}", ha="center", va="bottom", fontsize=7.0, weight="bold",
                color=OKC if d >= 3 else MUTED, clip_on=False)
        ax.text(gi, -6, lab, ha="center", va="top", fontsize=6.3, color=INK, linespacing=1.0, clip_on=False)
    ax.set_xlim(-0.55, len(rows) - 0.45); ax.set_ylim(0, 100); ax.set_xticks([])
    ax.set_yticks([0, 50, 100]); ax.grid(axis="y", color="#E6E9EE", lw=0.6); ax.set_axisbelow(True)
    ax.tick_params(labelsize=6.3, pad=2, length=2.5, width=0.8, colors=MUTED)
    for sp in ("top", "right"): ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"): ax.spines[sp].set_linewidth(0.8); ax.spines[sp].set_color(MUTED)


axb = ax_at(0.36, top_b, 0.86, ph)
pairs(axb, PRACTICE, False)
axb.set_yticklabels(["0", "50", "100%"])
axc = ax_at(1.42, top_b, 1.79, ph)
pairs(axc, COMPOSE, True)
axc.set_yticklabels([]); axc.spines["left"].set_visible(False); axc.tick_params(axis="y", length=0)
O.text(0.07, top_b + ph / 2, "success", rotation=90, va="center", ha="center", fontsize=6.5, color=MUTED)

out = os.path.join(HERE, "teaser_serif" if SERIF else "teaser")
fig.savefig(out + ".pdf", dpi=600); fig.savefig(out + ".png", dpi=600)
print("wrote", out + ".pdf/.png")
print("  badges", {t[0]: round(t[4], 1) for t in TILES})
print("  practice", [(l.replace(chr(10), " "), round(b, 1), round(a, 1)) for l, b, a in PRACTICE])
print("  compose ", [(l.replace(chr(10), " "), round(b, 1), round(a, 1)) for l, b, a in COMPOSE])
