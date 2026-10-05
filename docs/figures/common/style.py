"""The diagrams' visual language for every plot (2026-10-04): the palette and fonts of method/make_method.py and
construction/make_construction.py, their header (bold name + muted subtitle) and their rounded light panels.

    from style import INK, MUTED, EDGE, PANEL, BLUE, OK, BAD, FAM, UNTRAINED, TRAINED, FS, rc, header, panel, swatch, bar,
        wordmark
"""
import matplotlib.pyplot as plt
from matplotlib.colors import to_rgb
from matplotlib.patches import FancyBboxPatch, Rectangle

# Sans-serif (user, 2026-10-05: tried serif, kept the original font). SERIF_FIGS = True switches every plot to Times-like
# text and Courier-like code, with the product names in small caps.
SERIF_FIGS = False
FONT, MONO, GLYPH = ("Nimbus Roman", "Nimbus Mono PS", "DejaVu Sans") if SERIF_FIGS else ("Nimbus Sans", "DejaVu Sans Mono", "DejaVu Sans")
INK, MUTED, EDGE, PANEL, BLUE = "#14213D", "#4A5568", "#9AA3B2", "#EEF2F7", "#2B5C9E"
OK, BAD = "#2E7D32", "#B3261E"
GRID = "#E6E9EE"
FAM = {"Drag & gesture": "#6B4C9A", "Discrete selection": "#2B5C9E", "Text entry": "#2E7D6B",
       "Form transaction": "#A8520F", "Navigation": "#8A6D0B", "Out-of-page I/O": "#A33B4C", "Reasoning base": "#14213D"}
UNTRAINED, TRAINED = "#7D8798", BLUE     # the arms: grey before MiniWeb training (a shade darker than EDGE, so it
                                         # holds up in print), the diagrams' blue after it
# Print sizes (pt), 2026-10-05 (user: the plots were hard to read on paper): a column-wide plot is read at 1:1, next to
# 9 pt captions, so no text below 6 pt.
FS = dict(title=8.5, sub=7.2, legend=6.8, label=7.0, tick=6.5, value=6.3, small=6.0)
# Figure headings (bold title + muted subtitle) are off since 2026-10-05: the user moves them into the captions.
# HEADINGS = True draws them again; save() then keeps the heading strip instead of trimming it.
HEADINGS = False
HEAD_STRIP = 0.19                                        # inches at the top that a heading occupies


def save(fig, out, strip=HEAD_STRIP, bottom=0.0):
    """Save out.pdf and out.png; without headings, trim the empty heading strip off the top. `bottom`: inches of empty
    space to trim off the bottom as well."""
    from matplotlib.transforms import Bbox
    W, H = fig.get_size_inches()
    box = None if HEADINGS and not bottom else Bbox([[0, bottom], [W, H - (0 if HEADINGS else strip)]])
    for ext in ("pdf", "png"):
        fig.savefig(f"{out}.{ext}", dpi=600, bbox_inches=box)


def rc():
    plt.rcParams.update({"font.family": FONT, "font.size": FS["label"], "pdf.fonttype": 42, "ps.fonttype": 42,
                         "hatch.linewidth": 0.9, "mathtext.fontset": "stix" if SERIF_FIGS else "stixsans"})


def tint(c, a):
    r, g, b = to_rgb(c)
    return (1 - a + a * r, 1 - a + a * g, 1 - a + a * b)


def _w(fig, t):
    return t.get_window_extent(fig.canvas.get_renderer()).width / fig.dpi


def logo(fig, x, y, path, size=0.13):
    """A model's logo, centered at (x, y) in inches from the figure's top-left corner."""
    from PIL import Image
    W, H = fig.get_size_inches()
    la = fig.add_axes([(x - size / 2) / W, 1 - (y + size / 2) / H, size / W, size / H])
    la.imshow(Image.open(path).convert("RGBA"), interpolation="lanczos"); la.axis("off")


def header(fig, A, x, y, name, rest="", tag=None, logo_path=None):
    """The diagrams' panel title: an optional bold tag, a bold name, an optional logo, a muted subtitle. A's
    coordinates are inches from the top-left corner."""
    if not HEADINGS:
        return
    if tag:
        t = A.text(x, y, tag, fontsize=FS["title"], weight="bold", color=INK, va="center")
        x += _w(fig, t) + 0.05
    n = A.text(x, y, name, fontsize=FS["title"], weight="bold", color=INK, va="center")
    x += _w(fig, n) + 0.08
    if logo_path:
        logo(fig, x + 0.065, y, logo_path)
        x += 0.17
    if rest:
        A.text(x, y, rest, fontsize=FS["sub"], color=MUTED, va="center")


def panel(A, x, y, w, h, fc=PANEL, ec="none", lw=0.6, r=0.025, z=1):
    """A rounded light box, as the diagrams group things: legends sit on a light grey panel (user, 2026-10-05: keep the
    grey blocks)."""
    A.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=z))


def wordmark(fig, A, x, y, text, color, size=11.0):
    """A product name (MiniWeb, MiniWebAgent, ...) in bold small caps, as the paper's \\miniweb{} macros set it: capitals at
    full size, lower case as smaller capitals (serif figures; plain bold otherwise). Left edge at x, capitals centred on
    y; returns the right edge."""
    if not SERIF_FIGS:
        t = A.text(x, y, text, fontsize=size, weight="bold", color=color, va="center", zorder=4)
        return x + _w(fig, t)
    base = y + 0.34 * size / 72
    i = 0
    while i < len(text):
        j = i
        while j < len(text) and text[j].isupper() == text[i].isupper():
            j += 1
        run = text[i:j]
        t = A.text(x, base, run.upper(), fontsize=size if run[0].isupper() else size * 0.78, weight="bold", color=color,
                   va="baseline", zorder=4)
        x += _w(fig, t) - 0.011 * size / 11              # close the side bearings between runs
        i = j
    return x


def swatch(A, x, y, color, hatched=False, w=0.15, h=0.095):
    """A legend swatch, drawn like the bars (see bar())."""
    A.add_patch(Rectangle((x, y - h / 2), w, h, fc=tint(color, 0.28) if hatched else color, ec=color, lw=1.0,
                          hatch="////" if hatched else None, zorder=3))


def bar(ax, x, h, w, color, hatched=False, z=2):
    """A bar: solid (single agents), or a light fill of the color with its hatching and edge (the planner arms)."""
    ax.bar(x, h, w, color=tint(color, 0.28) if hatched else color, edgecolor=color, hatch="////" if hatched else None,
           lw=1.0 if hatched else 0, zorder=z)


def style_axes(ax):
    ax.grid(axis="y", color=GRID, lw=0.6); ax.set_axisbelow(True)
    for sp in ("top", "right"):
        ax.spines[sp].set_visible(False)
    for sp in ("left", "bottom"):
        ax.spines[sp].set_linewidth(0.8); ax.spines[sp].set_color(MUTED)
    ax.tick_params(length=2.5, width=0.8, pad=2, colors=MUTED, labelsize=FS["tick"])
