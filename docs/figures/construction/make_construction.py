"""Construction figure: skills -> websites -> tasks, drawn as one tree in the teaser's style.

Two layouts from the same parts: construction.pdf (single column: the skill families as an indented tree) and
construction_2col.pdf (double column: every primitive listed under its family, website and task side by side).

Skill families come from datagen.viewer.FAMILIES, restricted to the well-covered primitives the paper reports
(docs/figures/common/results.py: 37 primitives, 7 families). The worked example is the
annotated SnapLink task url-shorteners-qr_74e00a: its demonstration spans per primitive come from its task.json and the
per-primitive verdicts from a real Qwen3.5-4B run (repeat 2 in evaluation/results/qwen35_4b_all_x3/macro_judge_flash_v3.jsonl).
Screenshots come from capture.py.
"""
import glob, json, os, sys
from collections import Counter
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyBboxPatch, PathPatch, Rectangle
from matplotlib.path import Path
from matplotlib.colors import to_rgb
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
from datagen.viewer import FAMILIES  # noqa: E402
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from style import HEADINGS, save as style_save  # noqa: E402
from sprites import robot, person, claude_spark, image, CLAUDE  # noqa: E402
CLAUDE_DARK = "#B4532F"                                  # Claude's terracotta, dark enough for text
from results import well_covered  # noqa: E402
_KEEP = well_covered()                                  # the paper's primitive set, after the post-annotation refinement
FAMILIES = {f: [m for m in ms if m in _KEEP] for f, ms in FAMILIES.items()}

plt.rcParams.update({"font.family": "Nimbus Sans", "font.size": 6.5, "pdf.fonttype": 42, "ps.fonttype": 42})
MONO, GLYPH = "DejaVu Sans Mono", "DejaVu Sans"
INK, MUTED, EDGE, PANEL, BLUE = "#14213D", "#4A5568", "#9AA3B2", "#EEF2F7", "#2B5C9E"
OK, BAD = "#2E7D32", "#B3261E"
FAM = {"Drag & gesture": "#6B4C9A", "Discrete selection": "#2B5C9E", "Text entry": "#2E7D6B",
       "Form transaction": "#A8520F", "Navigation": "#8A6D0B", "Out-of-page I/O": "#A33B4C", "Reasoning base": "#14213D"}
NAME = {f: f for f in FAMILIES} | {"Reasoning base": "Reasoning"}
# one labelled primitive per family (single column); the example task's three are drawn solid and run down the tree
CHIP = {"Drag & gesture": "filter_by_slider", "Discrete selection": "sort_by_form", "Text entry": "edit_by_cell",
        "Form transaction": "share_by_form", "Navigation": "get_nav_route", "Out-of-page I/O": "upload_file",
        "Reasoning base": "report_information"}
# the tree's root: the first pass over WebArena, WebShop, WebVoyager and Mind2Web tasks (docs/MiniWeb-brainstorm-sheet.xlsx)
ROOT_TEXT = "139 candidate macros from 15.7K benchmark tasks"
STAGE1 = ("Primitives", f"")
# font sizes (pt)
HEAD, SUB, FAMF, CHIPF, LISTF, PILLF, ROLEF, CARDF, CCHIPF = 7.5, 6.2, 5.6, 5.2, 5.0, 5.4, 4.8, 5.2, 5.0

# ── data ────────────────────────────────────────────────────────────────────
TASK_ID = "url-shorteners-qr_74e00a"
TASK_FILES = glob.glob(os.path.join(ROOT, "data", "annotations", "*", "*", "task.json"))
task = json.load(open(next(p for p in TASK_FILES if f"/{TASK_ID}/" in p)))
TAGS = [t for t in task["macro_tags"] if t.get("required", True)]
USED = {t["macro"] for t in TAGS}
FAM_OF = {m: f for f, ms in FAMILIES.items() for m in ms}
site_tasks = Counter(json.load(open(p))["site"] for p in TASK_FILES)
annotators = {os.path.basename(os.path.dirname(os.path.dirname(p))).lower().replace("á", "a") for p in TASK_FILES}
run = next(json.loads(l) for l in open(os.path.join(ROOT, "evaluation", "results", "qwen35_4b_all_x3", "macro_judge_flash_v3.jsonl"))
           if TASK_ID in l and json.loads(l)["repeat"] == 2)
inst = json.loads(run["instances"]) if isinstance(run["instances"], str) else run["instances"]
VERDICT = {k: v["passed"] for k, v in inst.items()}
BOX = json.load(open(os.path.join(HERE, "boxes.json")))
VW = BOX["_viewport"]
CHECK = {"sort_by_form": "request log: ?sort=clicks", "share_by_form": "request log: /share",
         "report_information": "Gemini 3.5 Flash"}
WHY = {"sort_by_form": "chose Most Clicks, not applied", "share_by_form": "sharing left off",
       "report_information": "answer right"}

# SnapLink tile: My Links sorted by clicks, as two bands of the page (filter bar, top row); inset: the link's buttons
LINKS_X, LINKS_BANDS, BAND_GAP = (24, 536), [(140, 258), (376, 500)], 8
INSET = (290, 268, 496, 316)
TILE_BAR = 0.1
TILE_RATIO = (sum(b - a for a, b in LINKS_BANDS) + BAND_GAP * (len(LINKS_BANDS) - 1)) / (LINKS_X[1] - LINKS_X[0])
CARD_H = 0.92


def tint(c, a=0.13):
    r, g, b = to_rgb(c)
    return (1 - a + a * r, 1 - a + a * g, 1 - a + a * b)


def chip_w(text, fs):                         # DejaVu Sans Mono advance is 0.602 em; bbox pad 0.25 em each side
    return (len(text) * 0.602 + 0.5) * fs / 72


class Canvas:
    """A figure whose main axes are in inches from the top-left corner."""

    def __init__(self, W, FH):
        self.W, self.FH = W, FH
        self.fig = plt.figure(figsize=(W, FH))
        self.A = self.fig.add_axes([0, 0, 1, 1])
        self.A.set_xlim(0, W); self.A.set_ylim(FH, 0); self.A.axis("off")
        self.R = self.fig.canvas.get_renderer()

    def ax_at(self, x, y, w, h, z=2):
        a = self.fig.add_axes([x / self.W, 1 - (y + h) / self.FH, w / self.W, h / self.FH]); a.set_zorder(z)
        return a

    def width(self, t):
        return t.get_window_extent(self.R).width / self.fig.dpi

    def chip(self, x, y, text, color, solid=True, fs=CHIPF, ha="center"):
        if ha == "left":
            x += 0.25 * fs / 72
        self.A.text(x, y, text, fontsize=fs, family=MONO, ha=ha, va="center", color="white" if solid else color, zorder=6,
                    bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.3", fc=color if solid else tint(color, 0.12),
                              ec="none" if solid else tint(color, 0.5), lw=0.5))

    def header(self, x, y, n, name, rest=""):
        if not HEADINGS:                                 # headings move into the caption (2026-10-05)
            return x
        self.A.add_patch(Circle((x + 0.06, y), 0.06, fc=INK, ec="none", zorder=5))
        self.A.text(x + 0.06, y + 0.003, str(n), fontsize=6.0, weight="bold", color="white", ha="center", va="center", zorder=6)
        t = self.A.text(x + 0.155, y, name, fontsize=HEAD, weight="bold", color=INK, va="center")
        end = x + 0.155 + self.width(t)
        if rest:
            r = self.A.text(end + 0.07, y, rest, fontsize=SUB, color=MUTED, va="center")
            end += 0.07 + self.width(r)
        return end

    def lane(self, pts, color, lw=1.0, r=0.04, z=3):
        """Orthogonal polyline with rounded corners, ending in a dot."""
        verts, codes = [pts[0]], [Path.MOVETO]
        for (x0, y0), (x1, y1), (x2, y2) in zip(pts, pts[1:], pts[2:]):
            l0, l1 = abs(x1 - x0) + abs(y1 - y0), abs(x2 - x1) + abs(y2 - y1)
            d0, d1 = ((x1 - x0) / (l0 or 1), (y1 - y0) / (l0 or 1)), ((x2 - x1) / (l1 or 1), (y2 - y1) / (l1 or 1))
            rr = min(r, l0 / 2, l1 / 2)
            verts += [(x1 - d0[0] * rr, y1 - d0[1] * rr), (x1, y1), (x1 + d1[0] * rr, y1 + d1[1] * rr)]
            codes += [Path.LINETO, Path.CURVE3, Path.CURVE3]
        verts.append(pts[-1]); codes.append(Path.LINETO)
        self.A.add_patch(PathPatch(Path(verts, codes), fc="none", ec=color, lw=lw, zorder=z, capstyle="round"))
        self.A.add_patch(Circle(pts[-1], 0.017, fc=color, ec="none", zorder=z + 1))

    def elbow(self, x0, y0, xs, y1, color=EDGE, lw=0.6, z=1):   # parent (x0, y0) -> children at xs, y1, dendrogram style
        yb = (y0 + y1) / 2
        A = self.A
        A.plot([x0, x0], [y0, yb], color=color, lw=lw, zorder=z, solid_capstyle="butt")
        A.plot([min(xs + [x0]), max(xs + [x0])], [yb, yb], color=color, lw=lw, zorder=z, solid_capstyle="butt")
        for x in xs:
            A.plot([x, x], [yb, y1], color=color, lw=lw, zorder=z, solid_capstyle="butt")

    def save(self, name):
        out = os.path.join(HERE, name)
        style_save(self.fig, out, strip=0.17)               # trims the heading strip at the top
        print("wrote", out + ".pdf/.png")


# ── parts ───────────────────────────────────────────────────────────────────
def family_box(cv, x, y, w, h, f, center=False):
    col, A = FAM[f], cv.A
    A.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.025", fc=tint(col, 0.12), ec=col,
                               lw=0.7, zorder=4))
    A.text(x + (w - 0.1) / 2 if center else x + 0.045, y + h / 2 + 0.004, NAME[f], fontsize=FAMF, weight="bold", color=col,
           ha="center" if center else "left", va="center", zorder=5)
    A.add_patch(Circle((x + w - 0.065, y + h / 2), 0.043, fc=col, ec="none", zorder=6))
    A.text(x + w - 0.065, y + h / 2 + 0.003, str(len(FAMILIES[f])), fontsize=4.6, weight="bold", color="white",
           ha="center", va="center", zorder=7)


def skills_indented(cv, x0, y0, pitch):
    """Root -> families (rows) -> leaf dots -> one chip per family. Returns {macro: chip right end (x, y)}, last row y."""
    A = cv.A
    A.text(x0 + 0.02, y0, ROOT_TEXT, fontsize=5.8, color=INK, va="center", ha="left", zorder=4,
           bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.5", fc="white", ec=INK, lw=0.6))
    trunk = x0 + 0.1
    ys = [y0 + 0.165 + i * pitch for i in range(len(FAMILIES))]
    A.plot([trunk, trunk], [y0 + 0.05, ys[-1]], color=EDGE, lw=0.6, zorder=1)
    bx, bw, bh, P = trunk + 0.08, 1.03, 0.115, 0.05
    dx0 = bx + bw + 0.07
    cx0 = dx0 + (max(len(ms) for ms in FAMILIES.values()) - 1) * P + 0.1
    ends = {}
    for f, y in zip(FAMILIES, ys):
        col, ms, m = FAM[f], FAMILIES[f], CHIP[f]
        A.plot([trunk, bx], [y, y], color=EDGE, lw=0.6, zorder=1)
        family_box(cv, bx, y - bh / 2, bw, bh, f)
        xs = [dx0 + i * P for i in range(len(ms))]
        A.plot([bx + bw, xs[-1]], [y, y], color=tint(col, 0.5), lw=0.6, zorder=2)
        A.plot([xs[-1], cx0 - 0.02], [y, y], color=tint(col, 0.5), lw=0.6, ls=(0, (1, 1.5)), zorder=2)
        for mm, lx in zip(ms, xs):
            A.add_patch(Circle((lx, y), 0.019 if mm == m else 0.013, fc=col if mm == m else tint(col, 0.6), ec="none", zorder=4))
        cv.chip(cx0, y, m, col, solid=m in USED, ha="left")
        ends[m] = (cx0 + chip_w(m, CHIPF) + 0.01, y)
    return ends, ys[-1]


def skills_columns(cv, x0, y0, width, order, pitch):
    """Root -> families (columns) -> every primitive listed. Example primitives go last in their list and are drawn as solid
    chips. Returns {macro: chip bottom centre (x, y)}, bottom y of the longest list."""
    A, indent = cv.A, 0.11
    lists = {f: [m for m in FAMILIES[f] if m not in USED] + [m for m in FAMILIES[f] if m in USED] for f in order}
    lab = {f: A.text(0, 0, NAME[f], fontsize=FAMF, weight="bold") for f in order}
    lab_w = {f: cv.width(t) for f, t in lab.items()}
    for t in lab.values(): t.remove()
    col_w = {f: max(lab_w[f] + 0.17, indent + max(chip_w(m, LISTF) for m in lists[f])) for f in order}
    gap = (width - sum(col_w.values())) / (len(order) - 1)
    xs, x = {}, x0
    for f in order:
        xs[f] = x; x += col_w[f] + gap
    y_box, bh = y0 + 0.16, 0.13
    A.text(x0 + width / 2, y0, ROOT_TEXT, fontsize=5.8, color=INK, ha="center", va="center",
           zorder=4, bbox=dict(boxstyle="round,pad=0.35,rounding_size=0.5", fc="white", ec=INK, lw=0.6))
    cv.elbow(x0 + width / 2, y0 + 0.05, [xs[f] + col_w[f] / 2 for f in order], y_box)
    anchors, bottom = {}, 0
    for f in order:
        col, x = FAM[f], xs[f]
        family_box(cv, x, y_box, col_w[f], bh, f, center=True)
        ys = [y_box + bh + 0.1 + i * pitch for i in range(len(lists[f]))]
        tx = x + 0.045
        A.plot([tx, tx], [y_box + bh, ys[-1]], color=tint(col, 0.55), lw=0.6, zorder=2)
        for m, y in zip(lists[f], ys):
            A.plot([tx, tx + indent - 0.035], [y, y], color=tint(col, 0.55), lw=0.6, zorder=2)
            if m in USED:
                cv.chip(tx + indent - 0.02, y, m, col, ha="left", fs=LISTF)
                anchors[m] = (tx + indent - 0.02 + chip_w(m, LISTF) / 2, y + 0.045)
            else:
                A.text(tx + indent - 0.02 + 0.25 * LISTF / 72, y, m, fontsize=LISTF, family=MONO, color=col, va="center")
        bottom = max(bottom, ys[-1])
    return anchors, bottom


def site_tile(cv, x, y, w):
    """SnapLink in a browser window; boxes mark each primitive's control. Returns the tile height."""
    browser = cv.ax_at(x, y, w, TILE_BAR)
    browser.set_xlim(0, w); browser.set_ylim(TILE_BAR, 0); browser.set_xticks([]); browser.set_yticks([])
    browser.set_facecolor("#E4E8EE")
    for sp in browser.spines.values(): sp.set_color("#C9CED6"); sp.set_linewidth(0.5)
    for k, dc in enumerate(("#E0675E", "#E6B54A", "#6BBF6A")):
        browser.add_patch(Circle((0.055 + k * 0.055, TILE_BAR / 2), 0.017, color=dc, lw=0))
    browser.text(w / 2, TILE_BAR / 2 + 0.003, "SnapLink", ha="center", va="center", fontsize=6.3, weight="bold", color=INK)
    browser.text(w - 0.05, TILE_BAR / 2 + 0.003, f"1 of {len(site_tasks)} sites", ha="right", va="center", fontsize=5.0,
                 color=MUTED)
    # page: two bands of My Links
    im = Image.open(os.path.join(HERE, "shots", "c_links.png")).convert("RGB"); s = im.width / VW
    x0, x1 = LINKS_X
    ch = sum(b - a for a, b in LINKS_BANDS) + BAND_GAP * (len(LINKS_BANDS) - 1)
    page = Image.new("RGB", (int((x1 - x0) * s), int(ch * s)), "#F8FAFC")
    off, starts = 0, []
    for a, b in LINKS_BANDS:
        page.paste(im.crop((int(x0 * s), int(a * s), int(x1 * s), int(b * s))), (0, int(off * s)))
        starts.append((a, b, off)); off += b - a + BAND_GAP
    ymap = lambda v: next(o + v - a for a, b, o in starts if a <= v <= b)
    th = w * TILE_RATIO
    ax = cv.ax_at(x, y + TILE_BAR, w, th)
    ax.imshow(page, extent=(x0, x1, ch, 0), interpolation="lanczos")
    ax.set_xlim(x0, x1); ax.set_ylim(ch, 0); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color("#C9CED6"); sp.set_linewidth(0.5)
    for key, f in (("sort", "Discrete selection"), ("filter", "Discrete selection"), ("top", "Reasoning base")):
        bx, by, bw, bh = BOX[key]
        p = 1.5 if key == "top" else 3
        ax.add_patch(Rectangle((bx - p, ymap(by) - p), bw + 2 * p, bh + 2 * p, fill=False, ec=FAM[f], lw=1.3))
    # inset: the link page's Delete / Sharing buttons, over the empty right of the top row
    ix0, iy0, ix1, iy1 = INSET
    det = Image.open(os.path.join(HERE, "shots", "c_detail.png")).convert("RGB"); s = det.width / VW
    iw = 0.42 * w; ih = iw * (iy1 - iy0) / (ix1 - ix0)
    ia = cv.ax_at(x + w - iw - 0.05, y + TILE_BAR + th - ih - 0.06, iw, ih, z=3)
    ia.imshow(det.crop((int(ix0 * s), int(iy0 * s), int(ix1 * s), int(iy1 * s))), extent=(ix0, ix1, iy1, iy0),
              interpolation="lanczos")
    ia.set_xlim(ix0, ix1); ia.set_ylim(iy1, iy0); ia.set_xticks([]); ia.set_yticks([])
    for sp in ia.spines.values(): sp.set_color(FAM["Form transaction"]); sp.set_linewidth(0.6)
    bx, by, bw, bh = BOX["share"]
    ia.add_patch(Rectangle((bx - 3, by - 3), bw + 6, bh + 6, fill=False, ec=FAM["Form transaction"], lw=1.3))
    return TILE_BAR + th


def build_steps(cv, x, y, w, h):
    """How a site gets built, and who does each step."""
    steps = [("primitives to support", "humans + coding agent"), ("seed data", "public datasets + synthetic"),
             ("frontend + backend", "coding agent"), ("close review", "humans")]
    gap = 0.07
    ph = (h - gap * (len(steps) - 1)) / len(steps)
    for j, (what, who) in enumerate(steps):
        agent = who == "coding agent"
        yy = y + j * (ph + gap)
        cv.A.add_patch(FancyBboxPatch((x, yy), w, ph, boxstyle="round,pad=0,rounding_size=0.025",
                                      fc="#F9E3D9" if agent else "#E5EDF8", ec="none", zorder=2))   # coding agent: Claude's tint; humans: light blue
        both = "humans" in who and "agent" in who
        if "humans" in who:
            person(cv.A, x + 0.075, yy + ph * 0.36, 0.075, z=4)
        if "agent" in who:
            claude_spark(cv.A, x + (0.175 if both else 0.08), yy + ph * 0.36, 0.1, z=4)   # the coding agent (Claude)
        tx = x + w / 2 + (0.1 if both else 0.06)
        cv.A.text(tx, yy + ph * 0.36, what, fontsize=PILLF, color=CLAUDE_DARK if agent else INK,
                  weight="bold" if agent else "normal", ha="center", va="center", zorder=3)
        cv.A.text(tx, yy + ph * 0.73, who, fontsize=ROLEF, color=CLAUDE_DARK if "agent" in who else MUTED, style="italic",
                  ha="center", va="center", zorder=3)
        if j < len(steps) - 1:
            cv.A.annotate("", xy=(x + w / 2, yy + ph + gap - 0.006), xytext=(x + w / 2, yy + ph + 0.006),
                          arrowprops=dict(arrowstyle="-|>", color=MUTED, lw=0.6, mutation_scale=5))


def task_card(cv, x, y, w, h=CARD_H):
    """The expanded task: instruction, demo segmented by primitive, how each is checked, and a real run's verdicts."""
    A = cv.A
    A.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0,rounding_size=0.03", fc="white", ec=INK, lw=0.7,
                               zorder=1))
    A.text(x + 0.06, y + 0.13 * h, "“" + task["instruction"].replace("most clicks, ", "most clicks,\n") + "”",
           fontsize=6.0, style="italic", color=INK, va="center", linespacing=1.2)
    labels = [A.text(x + 0.17, 0, lab, fontsize=CARDF - 0.2, color=MUTED, va="center") for lab in ("demo", "check", "Qwen3.5-4B")]
    X0, X1 = x + 0.17 + max(cv.width(t) for t in labels) + 0.06, x + w - 0.06
    n_act = max(t["span"][1] for t in TAGS)
    cw = (X1 - X0) / n_act
    y_hi, y_lo, y_cells, y_check, y_run = (y + f * h for f in (0.305, 0.43, 0.55, 0.68, 0.79))
    for t, yy in zip(labels, (y_cells, y_check, y_run)):
        t.set_y(yy)
    person(A, x + 0.09, y_cells - 0.012, 0.075, z=4)
    image(A, x + 0.09, y_run + 0.005, 0.11, os.path.join(HERE, "..", "logos", "qwen.png"), z=4)            # the evaluated agent, Qwen3.5-4B
    seg = [(X0 + (t["span"][0] - 1) * cw, X0 + t["span"][1] * cw) for t in TAGS]
    for t, (s0, s1) in zip(TAGS, seg):
        col = FAM[FAM_OF[t["macro"]]]
        for a in range(t["span"][0], t["span"][1] + 1):
            A.add_patch(FancyBboxPatch((X0 + (a - 1) * cw + 0.009, y_cells - 0.05), cw - 0.018, 0.1,
                                       boxstyle="round,pad=0,rounding_size=0.014", fc=col, ec="none", alpha=0.88, zorder=2))
            A.text(X0 + (a - 0.5) * cw, y_cells + 0.003, str(a), fontsize=4.4, color="white", ha="center", va="center", zorder=3)
        A.plot([s0 + 0.01, s1 - 0.01], [y_cells - 0.075] * 2, color=col, lw=0.8, zorder=2)
        # chip over its segment, or above the row (right-aligned, with a leader) when it does not fit
        text = t["macro"] + (f" · {t['op']}" if t.get("op") else "")
        cwid = chip_w(text, CCHIPF)
        if cwid <= s1 - s0 - 0.02:
            cv.chip((s0 + s1) / 2, y_lo, text, col, fs=CCHIPF)
        else:
            cv.chip(min(X1 - cwid / 2, (s0 + s1) / 2), y_hi, text, col, fs=CCHIPF)
            A.plot([(s0 + s1) / 2] * 2, [y_hi + 0.045, y_cells - 0.075], color=col, lw=0.8, zorder=2)
        m = t["macro"]
        A.text((s0 + s1) / 2, y_check, CHECK[m], fontsize=CARDF, color=INK, ha="center", va="center")
        good = VERDICT[m]; vc = OK if good else BAD
        mark = A.text(0, y_run, "✓" if good else "✗", fontsize=5.8, family=GLYPH, color=vc, va="center", weight="bold")
        why = A.text(0, y_run, WHY[m], fontsize=CARDF, color=vc, va="center")
        mw, ww = cv.width(mark), cv.width(why)
        x0 = min((s0 + s1) / 2 - (mw + 0.03 + ww) / 2, X1 - mw - 0.03 - ww)
        mark.set_x(x0); why.set_x(x0 + mw + 0.03)
    A.text(x + w / 2, y + h - 0.09, "task fails, yet the answer was right → train sorting and sharing",
           fontsize=5.6, color=BLUE, style="italic", ha="center", va="center")


def task_dots(cv, xs, y, pick=1):
    for i, x in enumerate(xs):
        cv.A.add_patch(Circle((x, y), 0.025, fc=INK if i == pick else "white", ec=INK, lw=0.7, zorder=4))


# ── single column ───────────────────────────────────────────────────────────
def single():
    W, pitch = 3.25, 0.133
    y_last = 0.27 + 0.165 + 6 * pitch
    y_turn = [y_last + 0.07 + k * 0.05 for k in range(3)]       # report, share, sort (inner lane turns first)
    y_tile, tx, tw = y_turn[-1] + 0.08, 1.12, 2.11
    tile_h = TILE_BAR + tw * TILE_RATIO
    y_dots = y_tile + tile_h + 0.15
    y_card = y_dots + 0.11
    cv = Canvas(W, y_card + CARD_H + 0.02)
    end = cv.header(0.02, 0.1, 1, *STAGE1)
    for k in range(2 if HEADINGS else 0):                # group brainstorming, next to the heading
        person(cv.A, end + 0.14 + k * 0.17, 0.075, 0.085, shirt=("#2E7D6B", "#A8520F")[k], z=4)
    ends, _ = skills_indented(cv, 0.02, 0.27, pitch)
    # example chips -> right-hand lanes -> SnapLink's top bar; lanes keep their order, so none cross
    order = sorted(USED, key=lambda m: ends[m][1], reverse=True)                  # bottom row first = inner lane
    entry = {m: tx + tw * p for m, p in zip(order, (0.14, 0.5, 0.86))}
    for k, m in enumerate(order):
        xe, ye = ends[m]
        bus = 2.98 + 0.1 * k
        cv.lane([(xe, ye), (bus, ye), (bus, y_turn[k]), (entry[m], y_turn[k]), (entry[m], y_tile)], FAM[FAM_OF[m]])
    site_tile(cv, tx, y_tile, tw)
    cv.header(0.02, y_tile + 0.06, 2, "Websites")
    hb = 0.16 if HEADINGS else 0.0                       # without the heading the build steps start at the tile's top
    build_steps(cv, 0.03, y_tile + hb, tx - 0.11, tile_h - hb)
    n = site_tasks["url-shorteners-qr"]
    fx = tx + tw * 0.4
    dx = [fx + (i - (n - 1) / 2) * 0.15 for i in range(n)]
    cv.elbow(fx, y_tile + tile_h, dx, y_dots - 0.025)
    task_dots(cv, dx, y_dots)
    cv.A.text(dx[-1] + 0.07, y_dots, f"{n} on SnapLink", fontsize=5.4, color=MUTED, va="center")
    cv.header(0.02, y_dots, 3, "Tasks", f"{len(TASK_FILES)}, by {len(annotators)} annotators")
    cv.A.plot([dx[1]] * 2, [y_dots + 0.025, y_card], color=INK, lw=0.7, zorder=2)
    task_card(cv, 0.02, y_card, W - 0.04)
    cv.save("construction")


# ── double column ───────────────────────────────────────────────────────────
def double():
    W, pitch = 7.0, 0.092
    order = ["Drag & gesture", "Discrete selection", "Form transaction", "Reasoning base", "Text entry", "Navigation",
             "Out-of-page I/O"]
    y_lists_end = 0.3 + 0.16 + 0.13 + 0.1 + (max(len(v) for v in FAMILIES.values()) - 1) * pitch
    y_tile = y_lists_end + 0.13
    tx, tw = 1.2, 2.25
    tile_h = TILE_BAR + tw * TILE_RATIO
    cx = 3.92                                  # card left
    y_card = y_tile + 0.13
    cv = Canvas(W, y_tile + tile_h + 0.03)
    end = cv.header(0.02, 0.1, 1, *STAGE1)
    for k in range(2):                                   # group brainstorming
        person(cv.A, end + 0.14 + k * 0.17, 0.075, 0.085, shirt=("#2E7D6B", "#A8520F")[k], z=4)
    anchors, _ = skills_columns(cv, 0.02, 0.3, W - 0.04, order, pitch)
    for m, (ax_, ay) in anchors.items():                     # example chips drop straight into SnapLink's top bar
        ex = min(max(ax_, tx + 0.12), tx + tw - 0.12)
        yt = y_tile - 0.07
        cv.lane([(ax_, ay), (ax_, yt), (ex, yt), (ex, y_tile)] if abs(ex - ax_) > 1e-3 else [(ax_, ay), (ax_, y_tile)],
                FAM[FAM_OF[m]])
    site_tile(cv, tx, y_tile, tw)
    cv.header(0.02, y_tile + 0.06, 2, "Websites")
    build_steps(cv, 0.03, y_tile + 0.16, tx - 0.12, tile_h - 0.16)
    # SnapLink -> its tasks (a column of dots) -> the expanded card
    n = site_tasks["url-shorteners-qr"]
    card_h = y_tile + tile_h - y_card
    xd, ym = (tx + tw + cx) / 2 + 0.02, y_card + card_h / 2
    dy = [ym + (i - (n - 1) / 2) * 0.15 for i in range(n)]
    xb = tx + tw + 0.08
    cv.A.plot([tx + tw, xb], [ym, ym], color=EDGE, lw=0.6, zorder=1)
    cv.A.plot([xb, xb], [dy[0], dy[-1]], color=EDGE, lw=0.6, zorder=1)
    for yy in dy:
        cv.A.plot([xb, xd - 0.025], [yy, yy], color=EDGE, lw=0.6, zorder=1)
    for i, yy in enumerate(dy):
        cv.A.add_patch(Circle((xd, yy), 0.025, fc=INK if i == 1 else "white", ec=INK, lw=0.7, zorder=4))
    cv.A.plot([xd + 0.025, cx], [dy[1]] * 2, color=INK, lw=0.7, zorder=2)
    cv.A.text(xd, dy[-1] + 0.09, f"{n} on\nSnapLink", fontsize=5.0, color=MUTED, ha="center", va="top", linespacing=1.05)
    end = cv.header(cx, y_tile + 0.06, 3, "Tasks", f"{len(TASK_FILES)}, chained by {len(annotators)} annotators")
    person(cv.A, end + 0.14, y_tile + 0.035, 0.085, accessory="pencil", z=4)
    task_card(cv, cx, y_card, W - 0.02 - cx, card_h)
    cv.save("construction_2col")


single()
double()
