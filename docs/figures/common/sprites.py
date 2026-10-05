"""Small vector mascots for the paper figures: robots (agents, LLM steps) and people (annotators).

All functions draw on an axes whose units are inches and whose y axis points DOWN (ylim(H, 0)), the convention of the
figure scripts. (x, y) is the centre of the head; s is the head width in inches.
"""
import math
from matplotlib.patches import Circle, Ellipse, FancyBboxPatch, Polygon, Rectangle, Wedge
from matplotlib.colors import to_rgb

INK = "#14213D"
CHEEK = "#F4A3B4"
GOLD = "#E6B54A"
SKIN = "#F2C9A0"
HAIR = "#5A3E2B"


def _shade(c, k):
    r, g, b = to_rgb(c)
    return (r * k, g * k, b * k) if k < 1 else (1 - (1 - r) / k, 1 - (1 - g) / k, 1 - (1 - b) / k)


def _rbox(ax, x, y, w, h, r, fc, ec="none", lw=0.0, z=10):
    ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle=f"round,pad=0,rounding_size={r}", fc=fc, ec=ec, lw=lw, zorder=z))


def _curve(ax, x, y, w, depth, color, lw, z, n=16):
    """A smile when depth > 0 (the middle sags down the page), a frown when depth < 0."""
    pts = [(x - w / 2 + w * i / n, y + depth * math.sin(math.pi * i / n)) for i in range(n + 1)]
    ax.plot(*zip(*pts), color=color, lw=lw, solid_capstyle="round", zorder=z)


def robot(ax, x, y, s, color, mood="happy", accessory=None, body=True, z=10, lw=0.6):
    """A rounded robot. mood: happy | focused | oops. accessory: hat | cursor | book | magnifier | check | None."""
    dark = _shade(color, 0.72)
    if body:                                             # body, arms, chest light
        _rbox(ax, x - 0.32 * s, y + 0.43 * s, 0.64 * s, 0.42 * s, 0.12 * s, color, INK, lw, z)
        ax.add_patch(Circle((x, y + 0.62 * s), 0.07 * s, fc=GOLD, ec="none", zorder=z + 1))
        for sx in (-1, 1):
            ax.plot([x + sx * 0.32 * s, x + sx * 0.46 * s], [y + 0.55 * s, y + 0.72 * s], color=INK, lw=lw * 1.4,
                    solid_capstyle="round", zorder=z - 1)
            ax.add_patch(Circle((x + sx * 0.47 * s, y + 0.74 * s), 0.065 * s, fc=dark, ec=INK, lw=lw * 0.6, zorder=z))
    for sx in (-1, 1):                                   # ears
        _rbox(ax, x + sx * 0.5 * s - 0.07 * s, y - 0.14 * s, 0.14 * s, 0.28 * s, 0.05 * s, dark, INK, lw * 0.7, z - 1)
    if accessory != "hat":                               # antenna
        ax.plot([x, x], [y - 0.4 * s, y - 0.6 * s], color=INK, lw=lw, zorder=z - 1)
        ax.add_patch(Circle((x, y - 0.64 * s), 0.075 * s, fc=GOLD, ec=INK, lw=lw * 0.6, zorder=z))
    _rbox(ax, x - s / 2, y - 0.4 * s, s, 0.8 * s, 0.2 * s, color, INK, lw, z)          # head
    _rbox(ax, x - 0.37 * s, y - 0.25 * s, 0.74 * s, 0.5 * s, 0.14 * s, "white", "none", 0, z + 1)   # face plate
    ey = y - 0.04 * s
    for sx in (-1, 1):                                   # eyes with a highlight
        ax.add_patch(Ellipse((x + sx * 0.16 * s, ey), 0.12 * s, 0.17 * s if mood != "focused" else 0.07 * s, fc=INK,
                             ec="none", zorder=z + 2))
        if mood != "focused":
            ax.add_patch(Circle((x + sx * 0.16 * s + 0.025 * s, ey - 0.035 * s), 0.025 * s, fc="white", ec="none",
                                zorder=z + 3))
        ax.add_patch(Circle((x + sx * 0.27 * s, y + 0.1 * s), 0.05 * s, fc=CHEEK, ec="none", alpha=0.85, zorder=z + 2))
    if mood == "oops":
        _curve(ax, x, y + 0.15 * s, 0.14 * s, -0.035 * s, INK, lw, z + 2)
        ax.add_patch(Ellipse((x + 0.58 * s, y - 0.3 * s), 0.09 * s, 0.14 * s, fc="#8EC5F2", ec=INK, lw=lw * 0.5,
                             zorder=z + 3))                # sweat drop
    else:
        _curve(ax, x, y + 0.11 * s, 0.18 * s, 0.06 * s, INK, lw, z + 2)
    if accessory == "hat":                               # captain's cap
        _rbox(ax, x - 0.42 * s, y - 0.62 * s, 0.84 * s, 0.26 * s, 0.1 * s, INK, INK, lw, z + 4)
        ax.add_patch(Rectangle((x - 0.55 * s, y - 0.4 * s), 1.1 * s, 0.06 * s, fc=INK, ec="none", zorder=z + 4))
        ax.add_patch(Circle((x, y - 0.5 * s), 0.075 * s, fc=GOLD, ec="none", zorder=z + 5))
    elif accessory == "cursor":                          # a mouse pointer in the right hand
        px, py, k = x + 0.52 * s, y + 0.6 * s, 0.42 * s
        pts = [(0, 0), (0, 1), (0.27, 0.76), (0.45, 1.12), (0.58, 1.05), (0.4, 0.7), (0.72, 0.7)]
        ax.add_patch(Polygon([(px + u * k, py + v * k) for u, v in pts], closed=True, fc="white", ec=INK, lw=lw, zorder=z + 5))
    elif accessory == "book":                            # an open book held in front
        bx, by, bw, bh = x - 0.36 * s, y + 0.5 * s, 0.72 * s, 0.32 * s
        for k2 in (0, 1):
            ax.add_patch(Polygon([(bx + k2 * bw / 2, by + 0.03 * s), (bx + (k2 + 1) * bw / 2, by + (0.03 if k2 else 0) * s),
                                  (bx + (k2 + 1) * bw / 2, by + bh), (bx + k2 * bw / 2, by + bh - (0.03 if k2 else 0) * s)],
                                 closed=True, fc="#FFF8E7", ec=INK, lw=lw * 0.8, zorder=z + 5))
        for k2 in range(3):
            ax.plot([bx + 0.06 * s, bx + 0.3 * s], [by + (0.12 + 0.06 * k2) * s] * 2, color=MUTED_LINE, lw=lw * 0.6, zorder=z + 6)
    elif accessory == "magnifier":
        mx, my = x + 0.6 * s, y + 0.55 * s
        ax.plot([mx + 0.08 * s, mx + 0.22 * s], [my + 0.08 * s, my + 0.24 * s], color=INK, lw=lw * 2.2,
                solid_capstyle="round", zorder=z + 5)
        ax.add_patch(Circle((mx, my), 0.13 * s, fc="#DDF1FF", ec=INK, lw=lw * 1.1, zorder=z + 6))
    elif accessory == "check":                           # a little flag with a tick
        fx, fy = x + 0.55 * s, y + 0.75 * s
        ax.plot([fx, fx], [fy, fy - 0.6 * s], color=INK, lw=lw, zorder=z + 5)
        ax.add_patch(Polygon([(fx, fy - 0.6 * s), (fx + 0.4 * s, fy - 0.48 * s), (fx, fy - 0.36 * s)], closed=True,
                             fc="#2E7D32", ec="none", zorder=z + 5))


MUTED_LINE = "#9AA3B2"


def person(ax, x, y, s, shirt="#2B5C9E", hair=HAIR, z=10, lw=0.6, accessory=None):
    """A small person; (x, y) is the centre of the head, s the head diameter."""
    _rbox(ax, x - 0.5 * s, y + 0.55 * s, s, 0.6 * s, 0.25 * s, shirt, INK, lw, z)           # shoulders
    ax.add_patch(Circle((x, y), 0.5 * s, fc=SKIN, ec=INK, lw=lw, zorder=z + 1))           # head
    ax.add_patch(Wedge((x, y), 0.52 * s, 180, 360, fc=hair, ec=INK, lw=lw, zorder=z + 2))  # hair (top, y down)
    for sx in (-1, 1):
        ax.add_patch(Circle((x + sx * 0.18 * s, y + 0.08 * s), 0.055 * s, fc=INK, ec="none", zorder=z + 3))
        ax.add_patch(Circle((x + sx * 0.3 * s, y + 0.22 * s), 0.06 * s, fc=CHEEK, ec="none", alpha=0.8, zorder=z + 3))
    _curve(ax, x, y + 0.24 * s, 0.18 * s, 0.07 * s, INK, lw, z + 3)
    if accessory == "pencil":
        px, py = x + 0.55 * s, y + 0.7 * s
        ax.plot([px, px + 0.35 * s], [py, py - 0.45 * s], color="#E6B54A", lw=lw * 3, solid_capstyle="butt", zorder=z + 4)
        ax.plot([px - 0.03 * s, px + 0.03 * s], [py + 0.04 * s, py - 0.04 * s], color=INK, lw=lw * 3, zorder=z + 4)
    elif accessory == "mouse":
        ax.add_patch(Ellipse((x + 0.62 * s, y + 0.95 * s), 0.22 * s, 0.32 * s, fc="white", ec=INK, lw=lw, zorder=z + 4))


CLAUDE = "#D97757"                                       # Claude's terracotta


def claude_spark(ax, x, y, s, color=CLAUDE, z=10):
    """Claude's starburst ("the spider"): tapered rays of uneven length around a small hub, centred on (x, y), s wide."""
    R = s / 2
    lengths = [1.0, 0.8, 0.95, 0.74, 0.98, 0.82, 0.9, 0.76, 1.0, 0.8, 0.93, 0.78]
    for k, L in enumerate(lengths):
        a = math.radians(k * 360 / len(lengths) + 8)
        ca, sa = math.cos(a), math.sin(a)
        r0, r1, w0, w1 = 0.1 * R, L * R, 0.17 * R, 0.07 * R      # inner and outer radius, half-widths
        px, py = -sa, ca                                      # the ray's normal
        pts = [(x + r0 * ca + w0 * px, y + r0 * sa + w0 * py), (x + r1 * ca + w1 * px, y + r1 * sa + w1 * py),
               (x + r1 * ca - w1 * px, y + r1 * sa - w1 * py), (x + r0 * ca - w0 * px, y + r0 * sa - w0 * py)]
        ax.add_patch(Polygon(pts, closed=True, fc=color, ec="none", zorder=z))
        ax.add_patch(Circle((x + r1 * ca, y + r1 * sa), w1, fc=color, ec="none", zorder=z))   # rounded tips
    ax.add_patch(Circle((x, y), 0.2 * R, fc=color, ec="none", zorder=z))


def image(ax, x, y, s, path, z=10):
    """An image (a model's logo) s inches wide, centred on (x, y), without moving the axes' limits."""
    from PIL import Image
    xl, yl = ax.get_xlim(), ax.get_ylim()
    im = Image.open(path).convert("RGBA")
    h = s * im.size[1] / im.size[0]
    ax.imshow(im, extent=(x - s / 2, x + s / 2, y + h / 2, y - h / 2), interpolation="lanczos", zorder=z)
    ax.set_xlim(xl); ax.set_ylim(yl)
