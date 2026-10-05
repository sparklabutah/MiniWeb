"""Method figure (double column, 50 | 50): (a) MiniWebGen, (b) MiniWebAgent.

(a) uses a real kept trajectory: data/datagen/runs/scale100a, filter_by_slider-e-commerce-558e4ce3 (ShopHub, a training
site), with its probed backend check from tasks.jsonl. (b) uses a real planner trace of the reported agent (planner v6 +
one pooled adapter, seed 2; MiniWebAgent since 2026-10-04) on the held-out SnapLink task url-shorteners-qr_1a792b,
which it solved: data/webmix/eval/pagent_pooled_s2/<task>/subtasks.json. Counts come from docs/RESEARCH.md.
"""
import json, os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, FancyArrowPatch, FancyBboxPatch, Rectangle
from matplotlib.colors import to_rgb
from PIL import Image
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "common"))
from sprites import robot, person, image  # noqa: E402
QWEN = os.path.join(HERE, "..", "logos", "qwen.png")                # MiniWebAgent's planner and executor are Qwen3.5-4B
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
plt.rcParams.update({"font.family": "Nimbus Sans", "font.size": 6.5, "pdf.fonttype": 42, "ps.fonttype": 42,
                     "mathtext.fontset": "stixsans"})
MONO, GLYPH = "DejaVu Sans Mono", "DejaVu Sans"
GEN_C = "#A8520F"                                        # MiniWebGen: the data colour of the teaser
INK, MUTED, EDGE, PANEL, BLUE, OK = "#14213D", "#4A5568", "#9AA3B2", "#EEF2F7", "#2B5C9E", "#2E7D32"
FAM = {"Drag & gesture": "#6B4C9A", "Discrete selection": "#2B5C9E", "Text entry": "#2E7D6B",
       "Form transaction": "#A8520F", "Navigation": "#8A6D0B", "Out-of-page I/O": "#A33B4C", "Reasoning base": "#14213D"}
SHORT_FAM = {"Reasoning base": "Reasoning"}

GEN_TASK = "filter_by_slider-e-commerce-558e4ce3"
GEN_RUN = os.path.join(ROOT, "data", "datagen", "runs", "scale100a")
AGENT_RUN = os.path.join(ROOT, "data", "webmix", "eval", "pagent_pooled_s2")
AGENT_TASK = "url-shorteners-qr_1a792b"
traj = json.load(open(os.path.join(GEN_RUN, "accepted", GEN_TASK, "trajectory.json")))
gen_task = next(json.loads(l) for l in open(os.path.join(GEN_RUN, "tasks.jsonl")) if GEN_TASK in l)
trace = json.load(open(os.path.join(AGENT_RUN, AGENT_TASK, "subtasks.json")))["trace"]
result = next(json.loads(l) for l in open(os.path.join(AGENT_RUN, "results_regraded.jsonl")) if AGENT_TASK in l)
human = json.load(open(next(os.path.join(dp, "task.json") for dp, _, fs in os.walk(os.path.join(ROOT, "data", "annotations"))
                            if dp.endswith(AGENT_TASK) and "task.json" in fs)))
assert result["ok"], "the shown agent episode must be a solved one"
# the planner's instructions, shortened for print (same order, same family, same adapter)
SHORT = ["Click ‘My Links’", "Type ‘archived’ in the search field", "Open ‘Old Blog Post (Archived)’",
         "Click the red ‘Delete’ button", "Click ‘Create’", "Type ‘https://facebook.com’ into the URL field"]
FAMSHORT = {"Navigation": "nav", "Text entry": "text", "Discrete selection": "select", "Form transaction": "form",
            "Out-of-page I/O": "io", "Drag & gesture": "drag", "Reasoning base": "reason"}
assert len(SHORT) == len(trace)

W, H = 7.0, 2.78
fig = plt.figure(figsize=(W, H))
A = fig.add_axes([0, 0, 1, 1]); A.set_xlim(0, W); A.set_ylim(H, 0); A.axis("off")
R = fig.canvas.get_renderer()


def width(t):
    return t.get_window_extent(R).width / fig.dpi


def tint(c, a):
    r, g, b = to_rgb(c)
    return (1 - a + a * r, 1 - a + a * g, 1 - a + a * b)


def title(x, y, name, rest, color):
    """A part's name as a small-caps wordmark in its colour (no panel letters), then a muted subtitle. Off while
    style.HEADINGS is False (2026-10-05: the headings move into the caption)."""
    from style import wordmark, HEADINGS
    if not HEADINGS:
        return
    x = wordmark(fig, A, x, y, name, color, size=9.0)
    A.text(x + 0.08, y, rest, fontsize=6.2, color=MUTED, va="center")


def box(x, y, w, h, fc=PANEL, ec="none", lw=0.6, ls="-", r=0.025, z=2):
    A.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, ls=ls, zorder=z))


def arrow(p0, p1, color=MUTED, lw=0.7, ls="-", z=3, ms=5):
    A.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=ms, color=color, lw=lw, linestyle=ls, zorder=z,
                                shrinkA=0, shrinkB=0))


def chip(x, y, text, color, fs=4.8, ha="left"):
    if ha == "left":
        x += 0.25 * fs / 72
    t = A.text(x, y, text, fontsize=fs, family=MONO, color="white", ha=ha, va="center", zorder=6,
               bbox=dict(boxstyle="round,pad=0.25,rounding_size=0.3", fc=color, ec="none"))
    return (len(text) * 0.602 + 0.5) * fs / 72


# ── (a) MiniWebGen ─────────────────────────────────────────────────────────
title(0.02, 0.1, "MiniWebGen", "verified trajectories for each primitive", GEN_C)
# privileged inputs, incl. the one-time summarization of human demonstrations into a guide per primitive
box(0.02, 0.21, 3.36, 0.38, fc="none", ec=EDGE, lw=0.6, ls=(0, (3, 2)))
A.text(0.07, 0.255, "privileged inputs: decide what to generate and how, never enter a trajectory", fontsize=4.9,
       color=MUTED, style="italic", va="center")
pills = [("site map", "controls $c$ + their requests", 0.08, 0.8), ("dry runs", "data changes $\\rightarrow\\ \\kappa$", 0.96, 0.66),
         ("human demos", "spans $H_m$ of $m$", 1.68, 0.68)]
for h, d, x, w in pills:
    box(x, 0.3, w, 0.24, fc=tint(GEN_C, 0.13))           # privileged inputs, in MiniWebGen's colour (no grey)
    tx = x + w / 2 + (0.07 if h == "human demos" else 0)
    A.text(tx, 0.365, h, fontsize=5.3, weight="bold", color=INK, ha="center", va="center", zorder=4)
    A.text(tx, 0.465, d, fontsize=4.8, color=MUTED, ha="center", va="center", zorder=4)
person(A, 1.765, 0.37, 0.095, accessory="mouse")         # the human demonstrator
smx, smw = 2.44, 0.9                                    # Summarize: an LLM step, drawn like a stage
box(smx, 0.29, smw, 0.26, fc="white", ec=INK, lw=0.7)
A.text(smx + smw / 2 + 0.07, 0.345, "Summarize", fontsize=5.6, weight="bold", color=INK, ha="center", va="center", zorder=4)
A.text(smx + smw / 2 + 0.07, 0.45, "LLM: $H_m \\rightarrow$ guide $G_m$", fontsize=4.9, color=MUTED, ha="center",
       va="center", zorder=4)
robot(A, smx + 0.11, 0.37, 0.115, "#7C8DB5", accessory="book")      # the summarizer
arrow((1.68 + 0.68 + 0.012, 0.42), (smx - 0.012, 0.42), color=INK)
# stages, one run per task
stages = [("Sample", "$(w, c, x, s_0)$", "site, control,\nargument, start"),
          ("Suggest", "$g,\\ \\kappa$", "instruction +\nexpected check"),
          ("Execute", "$\\tau = (o_t, a_t)_{t \\leq T}$", "LLM script with $G_m$:\nDOM $\\rightarrow$ mouse, keys"),
          ("Gate", "$\\kappa(s_0){=}0,\\ \\kappa(s_T){=}1$", "keep in\n$\\mathcal{D}_{\\mathrm{gen}}$")]
sw, sg, sy, sh = 0.7, 0.135, 0.7, 0.43
sx = [0.08 + i * (sw + sg) for i in range(4)]
for (h, m, d), x in zip(stages, sx):
    gate = h == "Gate"
    box(x, sy, sw, sh, fc=tint(OK, 0.14) if gate else "white", ec=OK if gate else INK, lw=0.7)
    A.text(x + sw / 2, sy + 0.075, h, fontsize=5.6, weight="bold", color=INK, ha="center", va="center", zorder=4)
    A.text(x + sw / 2, sy + 0.18, m, fontsize=5.2, color=INK, ha="center", va="center", zorder=4)
    A.text(x + sw / 2, sy + 0.32, d, fontsize=4.5, color=MUTED, ha="center", va="center", linespacing=1.05, zorder=4)
for i in range(3):
    arrow((sx[i] + sw + 0.012, sy + sh / 2), (sx[i + 1] - 0.012, sy + sh / 2), color=INK)
arrow((0.08 + 0.4, 0.54), (sx[0] + sw / 2, sy - 0.01), color=EDGE, lw=0.6, ls=(0, (2, 1.5)))      # site map -> Sample
arrow((0.96 + 0.33, 0.54), (sx[1] + sw / 2, sy - 0.01), color=EDGE, lw=0.6, ls=(0, (2, 1.5)))     # dry runs -> Suggest
arrow((smx + smw / 2, 0.55), (sx[2] + sw / 2 + 0.1, sy - 0.01), color=INK, lw=0.7)               # guide -> Execute
A.text(2.78, 0.655, "$G_m$", fontsize=5.2, color=INK, va="center")
# helpers peeking over their stages: the executor (with a pointer) and the gatekeeper (with a magnifier)
robot(A, sx[2] + 0.16, sy - 0.035, 0.17, BLUE, mood="focused", body=False, z=-10)
A.add_patch(matplotlib.patches.Polygon([(sx[2] + 0.285 + u * 0.06, sy - 0.1 + v * 0.06) for u, v in
                                        [(0, 0), (0, 1), (0.27, 0.76), (0.45, 1.12), (0.58, 1.05), (0.4, 0.7), (0.72, 0.7)]],
                                       closed=True, fc="white", ec=INK, lw=0.6, zorder=6))
robot(A, sx[3] + sw - 0.16, sy - 0.035, 0.17, OK, body=False, z=-10)
A.add_patch(Circle((sx[3] + sw - 0.035, sy - 0.07), 0.022, fc="#DDF1FF", ec=INK, lw=0.7, zorder=7))
A.plot([sx[3] + sw - 0.02, sx[3] + sw], [sy - 0.055, sy - 0.032], color=INK, lw=1.3, zorder=6,
       solid_capstyle="round")
# the example
ey = 1.24
A.text(0.04, ey, "“" + traj["instruction"] + "”", fontsize=5.6, style="italic", color=INK, va="center")
chk = gen_task["check"]["params"]["max_price"]["value"]
A.text(3.38, ey, f"check: GET ?max_price ∈ [{chk[0]:g}, {chk[1]:g}]", fontsize=4.7, family=MONO, color=MUTED,
       ha="right", va="center")
CROP = [((0, 320, 270, 470), "click"), ((0, 320, 270, 470), "scroll"), ((0, 190, 270, 340), "click")]
cw, ch, cg = 0.86, 0.86 * 150 / 270, 0.075
cy = ey + 0.1
for i, (s, (bxy, label)) in enumerate(zip(traj["steps"], CROP)):
    x0, y0, x1, y1 = bxy
    x = 0.04 + i * (cw + cg)
    ax = fig.add_axes([x / W, 1 - (cy + ch) / H, cw / W, ch / H]); ax.set_zorder(3)
    im = Image.open(os.path.join(GEN_RUN, "accepted", GEN_TASK, s["screenshot"])).convert("RGB")
    k = im.width / 1280
    ax.imshow(im.crop((int(x0 * k), int(y0 * k), int(x1 * k), int(y1 * k))), extent=(x0, x1, y1, y0), interpolation="lanczos")
    ax.set_xlim(x0, x1); ax.set_ylim(y1, y0); ax.set_xticks([]); ax.set_yticks([])
    for sp in ax.spines.values(): sp.set_color("#C9CED6"); sp.set_linewidth(0.5)
    a = s["action"]
    if a["type"] == "click":
        ax.add_patch(Circle((a["x"], a["y"]), 9, fill=False, ec="#E0402F", lw=1.3))
        ax.add_patch(Circle((a["x"], a["y"]), 2.2, fc="#E0402F", ec="none"))
    else:
        ax.annotate("", xy=(250, y1 - 12), xytext=(250, y0 + 14),
                    arrowprops=dict(arrowstyle="-|>", color="#E0402F", lw=1.3, mutation_scale=7))
    A.text(x + 0.02, cy + ch + 0.075, f"{i + 1}", fontsize=5.0, weight="bold", color=INK, va="center")
    A.text(x + 0.09, cy + ch + 0.075, f"{a['type']}" + (f" ({a['x']:.0f}, {a['y']:.0f})" if a["type"] == "click" else f" dy={a['dy']:.0f}"),
           fontsize=4.7, family=MONO, color=MUTED, va="center")
gx = 0.04 + 3 * (cw + cg) - 0.01
box(gx, cy + 0.06, 3.38 - gx, ch - 0.12, fc=tint(OK, 0.14), ec=OK, lw=0.7)
A.text(gx + (3.38 - gx) / 2, cy + ch / 2 - 0.07, "✓", fontsize=9, family=GLYPH, color=OK, ha="center", va="center",
       weight="bold", zorder=4)
A.text(gx + (3.38 - gx) / 2, cy + ch / 2 + 0.1, "max_price\n=1650", fontsize=4.6, family=MONO, color=INK, ha="center",
       va="center", linespacing=1.1, zorder=4)
# executor script (verbatim lines of this attempt's target.py, with omissions marked)
SCRIPT = ['s = dom.one(css=task["target_css"])', "act.click(s, at=(frac, 0.5))", "...", "act.click(btn)",
          "expect.backend()"]
ky, kh = 2.0, 0.44
box(0.04, ky, 1.95, kh, fc=tint(GEN_C, 0.06), ec=tint(GEN_C, 0.35), lw=0.5)
A.text(0.08, ky + 0.045, "executor script (excerpt)", fontsize=4.6, color=MUTED, style="italic", va="center", zorder=4)
A.text(0.08, ky + 0.085, "\n".join(SCRIPT), fontsize=4.3, family=MONO, color=INK, va="top", linespacing=1.12, zorder=4)
A.text(2.07, ky + 0.03, "dom: read-only queries\nact: mouse and keys at jittered\n  points on visible elements\nexpect: the backend check",
       fontsize=4.7, family=MONO, color=MUTED, va="top", linespacing=1.25)
# output
oy = 2.56
A.text(0.04, oy, "3,128 kept trajectories · 52 training sites · ≈$0.04 each",
       fontsize=5.5, color=INK, va="center", weight="bold")
A.text(0.04, oy + 0.13, "A trajectory holds only screenshots and pixel actions; failed attempts are kept as negatives.",
       fontsize=4.9, color=MUTED, va="center", style="italic")
# divider
A.plot([3.5, 3.5], [0.05, H - 0.05], color="#D5DAE1", lw=0.6)

# ── (b) MiniWebAgent ───────────────────────────────────────────────────────
X0, X1 = 3.62, W - 0.02
title(X0, 0.1, "MiniWebAgent", "one base model: planner + one trained executor", BLUE)
box(X0 + 0.55, 0.21, 2.25, 0.33, fc="white", ec=INK, lw=0.8)
image(A, X0 + 0.27, 0.355, 0.26, QWEN)                                # the planner (Qwen3.5-4B)
A.text(X0 + 0.55 + 1.125, 0.29, "Planner $\\pi_0$ (untrained base model)", fontsize=5.6, weight="bold", color=INK,
       ha="center", va="center", zorder=4)
A.text(X0 + 0.55 + 1.125, 0.43, "sees $o$ (URL, elements, screenshot), cannot act;\neach turn emits $u_n = (\\gamma, \\iota)$ to delegate, or done($\\alpha$)",
       fontsize=4.7, color=MUTED, ha="center", va="center", linespacing=1.1, zorder=4)
ACTION = ["Navigation", "Text entry", "Discrete selection", "Form transaction", "Out-of-page I/O", "Drag & gesture"]
ay, aw = sy + sh / 2, 1.7
ax0 = X1 - aw - 0.35
for j, f in enumerate(ACTION):                           # one adapter for every action family: a stripe per family
    A.add_patch(Rectangle((ax0 + j * aw / len(ACTION), ay - 0.06), aw / len(ACTION), 0.12, fc=FAM[f], ec="none", zorder=3))
A.add_patch(FancyBboxPatch((ax0, ay - 0.06), aw, 0.12, boxstyle="round,pad=0,rounding_size=0.02", fc="none", ec="white",
                           lw=0.8, zorder=4))
A.text(ax0 + aw / 2, ay + 0.002, "pooled adapter $\\Delta_{\\mathrm{pool}}$", fontsize=5.2, color="white", ha="center",
       va="center", zorder=5, weight="bold")
image(A, ax0 + aw / 2, ay - 0.125, 0.14, QWEN)                         # the executor: Qwen3.5-4B + the adapter
arrow((X0 + 0.55 + 1.125, 0.545), (ax0 + aw / 2, ay - 0.225), color=EDGE, lw=0.5, ms=4)
A.text(ax0 + aw / 2, ay + 0.085, "every action family: navigation, text, selection, forms, I/O, drag", fontsize=4.5,
       color=MUTED, ha="center", va="top")
A.text(ax0 + aw / 2, ay + 0.3, "executor $\\pi_0 + \\Delta_{\\mathrm{pool}}$, trained on all of $\\mathcal{D}$; reasoning steps run on $\\pi_0$",
       fontsize=4.8, color=MUTED, style="italic", ha="center", va="center")
# data from (a) into the executor
arrow((sx[3] + sw + 0.012, sy + sh / 2), (ax0 - 0.03, ay), color=OK, lw=1.0, ms=6)
mx = (sx[3] + sw + ax0) / 2 - 0.05
A.text(mx, ay - 0.075, "$\\mathcal{D}$: 27.6K steps", fontsize=5.2, weight="bold", color=OK, ha="center", va="center")
A.text(mx, ay + 0.085, "replayed +\naugmented", fontsize=4.6, color=MUTED, ha="center", va="top", linespacing=1.05)
# the solved held-out task
ty = 1.37
A.text(X0, ty, "Held-out SnapLink task, solved in " + f"{result['steps']} steps:", fontsize=5.0, color=MUTED,
       style="italic", va="center")
instr = human["instruction"].replace(" Then", "\nThen")
A.text(X0, ty + 0.16, "“" + instr + "”", fontsize=5.4, style="italic", color=INK, va="center", linespacing=1.15)
ry, rp = ty + 0.36, 0.105
for i, (t, s) in enumerate(zip(trace, SHORT)):
    y = ry + i * rp
    A.text(X0 + 0.02, y, f"{i + 1}", fontsize=4.8, color=MUTED, va="center", ha="left")
    cwid = chip(X0 + 0.12, y, FAMSHORT[t["family"]], FAM[t["family"]])
    A.text(X0 + 0.12 + 0.55, y, s, fontsize=5.0, color=INK, va="center")
    A.text(X1, y, f"{t['steps']} step" + ("s" if t["steps"] > 1 else ""), fontsize=4.6, color=MUTED, ha="right",
           va="center")
y = ry + len(trace) * rp
image(A, X0 + 0.07, y + 0.01, 0.11, QWEN)                              # the planner, done
A.text(X0 + 0.2, y, "done", fontsize=4.8, family=MONO, color=INK, va="center", weight="bold")
A.text(X0 + 0.5, y, "✓", fontsize=6, family=GLYPH, color=OK, va="center", weight="bold")
A.text(X0 + 0.63, y, "verifier: links deleted, new link created", fontsize=4.9, color=OK, va="center")

out = os.path.join(HERE, "method")
from style import save
save(fig, out, strip=0.17)                               # trims the heading strip (the content starts at 0.21 in)
print("wrote", out, "| agent steps", result["steps"], [t["model"] for t in trace])
