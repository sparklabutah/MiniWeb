"""Figure 1, benchmark-first (2026-10-06, user: the paper is a benchmark paper; MiniWebAgent acts on its diagnosis).

Top: one real RQ1 episode graded per primitive. Fara1.5-4B searches CascadiaMaps for coffee and opens the right cafe, but
leaves the rating slider at "Any": a task score only says the task failed, MiniWeb says which skill did (judge verdicts
from rq1_fara15_4b_all/judge.jsonl). Bottom, one of two variants:
  families  the ten untrained agents' mean share of primitive instances passed per skill family (Tab. 2's agents)
  profiles  two agents with nearly the same task success and different skill profiles (Qwen3.5-9B, Fara1.5-4B)
Optional last line: MiniWebAgent's held-out result (acting on the diagnosis). All text >= 9 pt at the printed width.

    python docs/figures/teaser/make_teaser_v2.py --variant families|profiles [--no-agent]
"""
import argparse, json, os, statistics as st, sys

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import yaml
from matplotlib.patches import Circle, FancyBboxPatch, Rectangle
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "docs", "figures", "common"))
sys.path.insert(0, os.path.join(ROOT, "docs", "figures", "rq1"))
from datagen.viewer import FAMILY_OF  # noqa: E402
from style import BAD, COL_W, FAM, FS, GLYPH, INK, MONO, MUTED, OK, PANEL, rc, save, tint  # noqa: E402
import text_numbers as T  # noqa: E402

rc()
RUN, TASK = "rq1_fara15_4b_all", "map-services_345e3d"
EP = os.path.join(ROOT, "data", "webmix", "eval", RUN, TASK, "fara")
INSTRUCTION = ("“Search CascadiaMaps for ‘coffee’, set the minimum rating to 4.0 stars, "
               "and open Cedar Cup Coffee.”")
SHORT = {"Navigation": "Navigation", "Text entry": "Text entry", "Reasoning base": "Reasoning",
         "Form transaction": "Form", "Discrete selection": "Selection", "Out-of-page I/O": "I/O",
         "Drag & gesture": "Drag & gesture"}
# (primitive, frame of the episode = screenshot_<k>_post.png at 1440 x 900, sidebar region it shows, note)
STEPS = [("search", 4, (0, 55, 300, 170), "searched ‘coffee’"),
         ("filter_by_slider", 6, (0, 150, 260, 250), "rating left at Any, not 4.0"),
         ("navigate_by_route", 8, (0, 60, 300, 175), "opened Cedar Cup Coffee")]
KNOB = (110, 25)                       # the slider knob inside the second crop: it never left "Any"
AGENTS = [("Qwen3.5-9B", "#2B5C9E", "o"), ("Fara1.5-4B", "#A8520F", "s")]
ABBR = {"Navigation": "Nav.", "Text entry": "Text", "Discrete selection": "Select", "Form transaction": "Form",
        "Out-of-page I/O": "I/O", "Drag & gesture": "Drag", "Reasoning base": "Reason"}     # Tab. 2's headers
GAINS = [("heldout", "Held-out sites"), ("wa", "WebArena-Lite"), ("wv", "WebVoyager"), ("om2w", "Online-Mind2Web")]
BASE_C, AGENT_C = "#7D8798", "#2B5C9E"


class Canvas:
    """A figure with an inch-based overlay axis (y grows downward)."""

    def __init__(self, W, H):
        self.W, self.H = W, H
        self.fig = plt.figure(figsize=(W, H))
        self.A = self.fig.add_axes([0, 0, 1, 1])
        self.A.axis("off"); self.A.set_xlim(0, W); self.A.set_ylim(H, 0)

    def text(self, x, y, s, size=None, **kw):
        kw.setdefault("color", INK); kw.setdefault("va", "center")
        return self.A.text(x, y, s, fontsize=size or FS["label"], **kw)

    def width(self, t):
        return t.get_window_extent(self.fig.canvas.get_renderer()).width / self.fig.dpi

    def wrap(self, x, y, s, maxw, lh=0.165, **kw):
        """s from (x, y), wrapped to maxw inches by measured width; returns the y below the last line."""
        line = ""
        for w in s.split():
            trial = (line + " " + w).strip()
            t = self.text(-10, -10, trial, **kw); fits = self.width(t) <= maxw; t.remove()
            if fits or not line:
                line = trial
            else:
                self.text(x, y, line, **kw); y += lh; line = w
        self.text(x, y, line, **kw)
        return y + lh

    def mark(self, x, y, passed):
        return self.text(x, y, "✓" if passed else "✗", color=OK if passed else BAD, weight="bold",
                         family=GLYPH)

    def image(self, x, y, w, h, im):
        ax = self.fig.add_axes([x / self.W, 1 - (y + h) / self.H, w / self.W, h / self.H])
        ax.imshow(im, aspect="auto", interpolation="lanczos"); ax.set_xticks([]); ax.set_yticks([])
        return ax


def example(c, y):
    judge = next(json.loads(l) for l in open(os.path.join(ROOT, "data", "webmix", "eval", RUN, "judge.jsonl"))
                 if json.loads(l)["task_id"] == TASK)["instances"]
    y = c.wrap(0.02, y + 0.09, INSTRUCTION, c.W - 0.06, style="italic") - 0.02
    cw, ch, gap = 1.0, 0.37, 0.05
    for i, (name, k, box, note) in enumerate(STEPS):
        yy = y + i * (ch + gap)
        ax = c.image(0.02, yy, cw, ch, Image.open(os.path.join(EP, f"screenshot_{k}_post.png")).convert("RGB").crop(box))
        passed = bool(judge[name]["passed"])
        for s in ax.spines.values():
            s.set_color(OK if passed else BAD); s.set_linewidth(1.0 if passed else 1.6)
        if not passed:
            ax.add_patch(Circle(KNOB, 14, fill=False, ec=BAD, lw=1.6))
        tx = 0.02 + cw + 0.1
        t = c.text(tx, yy + 0.1, name, family=MONO, color="white",
                   bbox=dict(boxstyle="round,pad=0.12,rounding_size=0.06", fc=FAM[FAMILY_OF[name]], ec="none"))
        c.mark(tx + c.width(t) + 0.08, yy + 0.1, passed)
        c.text(tx, yy + 0.3, note, color=INK if passed else BAD)
    y += 3 * ch + 2 * gap + 0.07
    c.A.add_patch(FancyBboxPatch((0.02, y), c.W - 0.04, 0.42, boxstyle="round,pad=0,rounding_size=0.03",
                                 fc=PANEL, ec="none"))
    c.text(0.1, y + 0.11, "Task score", color=MUTED)
    c.mark(0.95, y + 0.11, False); c.text(1.1, y + 0.11, "failed", color=BAD, weight="bold")
    c.text(0.1, y + 0.31, "MiniWeb", color=MUTED)
    c.mark(0.95, y + 0.31, False); c.text(1.1, y + 0.31, "failed at the slider (drag)", color=BAD, weight="bold")
    return y + 0.5


def rq1():
    cfg = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "rq1", "rq1_config.yaml")))
    return T.load(cfg), cfg["table"]["families"]


def families(c, y):
    data, fams = rq1()
    mean = {f: st.mean(T.rate(data[a], f) for a in data) for f in fams}
    order = sorted(mean, key=mean.get, reverse=True)
    c.text(0.02, y + 0.08, "Ten agents: primitives passed, by skill family", weight="bold")
    y += 0.24
    bx, rh = 1.12, 0.16
    bw = c.W - bx - 0.42
    for i, f in enumerate(order):
        yy, weak = y + i * rh, f == order[-1]
        c.text(0.02, yy + rh / 2, SHORT[f], color=FAM[f], weight="bold" if weak else "normal")
        c.A.add_patch(Rectangle((bx, yy + 0.03), bw, rh - 0.06, fc=tint(FAM[f], 0.12), ec="none"))
        c.A.add_patch(Rectangle((bx, yy + 0.03), bw * mean[f] / 100, rh - 0.06, fc=FAM[f], ec="none"))
        c.text(bx + bw * mean[f] / 100 + 0.05, yy + rh / 2, f"{mean[f]:.0f}%", color=FAM[f],
               weight="bold" if weak else "normal")
    y += len(order) * rh + 0.05
    c.text(0.02, y + 0.08, "Drag & gesture: weakest for every agent", color=FAM["Drag & gesture"], weight="bold")
    return y + 0.22


def profiles(c, y):
    data, fams = rq1()
    succ = {a: 100 * st.mean(p for p, _ in data[a].values()) for a, _, _ in AGENTS}
    c.text(0.02, y + 0.08, "Same task success, different skills", weight="bold")
    y += 0.24
    for a, col, mk in AGENTS:
        c.A.plot([0.09], [y + 0.08], marker=mk, color=col, ms=6.5, clip_on=False)
        c.text(0.2, y + 0.08, f"{a}: {succ[a]:.1f}% of tasks", color=col)
        y += 0.18
    y += 0.04
    bx, rh = 1.12, 0.16
    bw = c.W - bx - 0.14
    order = sorted(fams, key=lambda f: -st.mean(T.rate(data[a], f) for a, _, _ in AGENTS))
    for i, f in enumerate(order):
        yy = y + i * rh + rh / 2
        c.text(0.02, yy, SHORT[f], color=FAM[f])
        c.A.plot([bx, bx + bw], [yy, yy], color=tint(INK, 0.15), lw=0.8, zorder=1)
        v = [T.rate(data[a], f) for a, _, _ in AGENTS]
        c.A.plot([bx + bw * v[0] / 100, bx + bw * v[1] / 100], [yy, yy], color=tint(INK, 0.45), lw=1.4, zorder=2)
        for (a, col, mk), val in zip(AGENTS, v):
            c.A.plot([bx + bw * val / 100], [yy], marker=mk, color=col, ms=6.5, zorder=3, clip_on=False)
    y += len(order) * rh + 0.04
    for p in (0, 50, 100):
        c.text(bx + bw * p / 100, y + 0.1, f"{p}%", color=MUTED, ha="center" if p < 100 else "right")
    c.text(0.02, y + 0.1, "passed", color=MUTED)
    return y + 0.26


RMAX = 65.0                  # the spider plot's radial scale (task-success %): the families fill it, drag stands out
# clockwise from the bottom: drag & gesture at the bottom, the long labels (Reason, Select) near the top, short at the sides
RADAR_ORDER = ["Drag & gesture", "Out-of-page I/O", "Navigation", "Reasoning base", "Discrete selection",
               "Form transaction", "Text entry"]


def radar(c, x, y, w):
    """Ten agents' skill profiles on a spider plot (radius = share of instances passed, 0 to RMAX): one faint polygon
    per agent, their mean in bold, drag & gesture's sector shaded and placed at the bottom."""
    import math
    data, _ = rq1()
    fams = RADAR_ORDER
    c.text(x, y + 0.08, "Ten agents, by skill family", weight="bold")
    r, pad = 0.46, 0.08
    d = 0
    ang = [(math.pi + 2 * math.pi * i / len(fams)) % (2 * math.pi) for i in range(len(fams))]
    cx, cy = x + w / 2, y + 0.24 + 0.14 + r + pad
    pax = c.fig.add_axes([(cx - r) / c.W, 1 - (cy + r) / c.H, 2 * r / c.W, 2 * r / c.H], projection="polar")
    pax.set_theta_zero_location("N"); pax.set_theta_direction(-1)
    pax.set_xlim(0, 2 * math.pi)                          # the full circle (ticks outside [0, 2pi) shrink it)
    pax.set_ylim(0, RMAX); pax.set_xticks(ang); pax.set_xticklabels([]); pax.set_yticks([20, 40, 60])
    pax.set_yticklabels([]); pax.grid(color=tint(INK, 0.13), lw=0.6); pax.spines["polar"].set_color(tint(INK, 0.25))
    pax.set_facecolor("none")
    drag = FAM["Drag & gesture"]
    pax.bar([ang[d]], [RMAX], width=2 * math.pi / len(fams), color=tint(drag, 0.13), zorder=0)
    rates = {a: [min(T.rate(data[a], f), RMAX) for f in fams] for a in data}
    loop = lambda v: v + v[:1]  # noqa: E731
    for v in rates.values():
        pax.plot(loop(ang), loop(v), color=tint(INK, 0.22), lw=0.6, zorder=2)
    mean = [st.mean(T.rate(data[a], f) for a in data) for f in fams]
    pax.fill(loop(ang), loop(mean), color=tint(AGENT_C, 0.18), zorder=1)
    pax.plot(loop(ang), loop(mean), color=INK, lw=1.7, zorder=3)
    for a_, f, m in zip(ang, fams, mean):
        weak = f == "Drag & gesture"
        pax.plot([a_], [m], "o", color=FAM[f], ms=6 if weak else 4.5, zorder=4)
        sx, sy = math.sin(a_), -math.cos(a_)
        lx, ly = cx + (r + pad) * sx, cy + (r + pad) * sy + 0.05 * (1 if sy > 0.5 else 0)
        ha = "center" if abs(sx) < 0.3 else ("left" if sx > 0 else "right")
        c.text(lx, ly, ABBR[f] + (f" {m:.0f}%" if weak else ""), color=FAM[f], ha=ha,
               weight="bold" if weak else "normal")
    return cy + r + pad + 0.17


def gains(c, x, y, w):
    """Task success of the untrained base agent (grey) and MiniWebAgent (blue) on the held-out sites and the external
    benchmarks: one bar each, the blue part is the gain."""
    cfg = yaml.safe_load(open(os.path.join(ROOT, "docs", "figures", "tables", "tables_config.yaml")))
    B, R = cfg["benchmarks"], cfg["runs"]
    from results import task_rates
    rate = lambda arm, b: st.mean(task_rates(B[b]["kind"], R[arm][b], B[b].get("tasks")))  # noqa: E731
    c.text(x, y + 0.08, "MiniWebAgent", color=AGENT_C, weight="bold")
    y += 0.25
    bw, bh = w - 0.36, 0.15                               # bar scale: 0 to 66% success; room for the value after it
    sx = lambda v: x + bw * v / 66.0  # noqa: E731
    for b, name in GAINS:
        lo, hi = rate("base", b), rate("planner_pooled", b)
        c.text(x, y + 0.06, name)
        yy = y + 0.15
        c.A.add_patch(Rectangle((x, yy), sx(hi) - x, bh, fc=AGENT_C, ec="none", zorder=2))
        c.A.add_patch(Rectangle((x, yy), sx(lo) - x, bh, fc=BASE_C, ec="none", zorder=3))
        c.text(sx(lo) - 0.03, yy + bh / 2, f"{lo:.0f}", color="white", ha="right", zorder=4)   # as in Fig. 8
        c.text(sx(hi) + 0.04, yy + bh / 2, f"{hi:.1f}", color=AGENT_C, weight="bold")
        y += 0.37
    c.text(x, y + 0.03, "grey: base agent", color=BASE_C)
    return y + 0.16


def radar_row(c, y):
    lw = 1.66
    y1 = radar(c, 0.02, y, lw)
    y2 = gains(c, 0.02 + lw + 0.08, y, c.W - lw - 0.12)
    return max(y1, y2)


def agent_line(c, y):
    c.A.plot([0.02, c.W - 0.02], [y + 0.02, y + 0.02], color=tint(INK, 0.2), lw=0.6)
    t = c.text(0.02, y + 0.19, "MiniWebAgent:", color="#2B5C9E", weight="bold")
    c.text(0.02 + c.width(t) + 0.07, y + 0.19, "held-out tasks 37.0% → 54.5%")
    return y + 0.3


def draw(W, H, variant, agent):
    c = Canvas(W, H)
    y = example(c, 0.02)
    y = {"families": families, "profiles": profiles, "radar": radar_row}[variant](c, y + 0.1)
    if agent and variant != "radar":
        y = agent_line(c, y + 0.02)
    return c, y


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", choices=["families", "profiles", "radar"], default="families")
    ap.add_argument("--no-agent", action="store_true", help="leave out the MiniWebAgent line")
    a = ap.parse_args()
    c, H = draw(COL_W, 8.0, a.variant, not a.no_agent)     # measure the height, then draw at it
    plt.close(c.fig)
    c, _ = draw(COL_W, H, a.variant, not a.no_agent)
    out = os.path.join(HERE, f"teaser_v2_{a.variant}")
    save(c.fig, out, strip=0.0)
    print("wrote", out, f"({COL_W:.3f} x {H:.2f} in)")


if __name__ == "__main__":
    main()
