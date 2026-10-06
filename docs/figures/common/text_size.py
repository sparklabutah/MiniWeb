"""The smallest printed text in a figure PDF: each text run's font size times its transform, scaled to the width the
paper prints the figure at. 2026-10-06 (user): no text smaller than the captions (9 pt, style.MIN_PT).

    python docs/figures/common/text_size.py docs/figures/chain/chain_length.pdf --width 3.117   # printed width, inches
    python docs/figures/common/text_size.py --paper docs/paper/MiniWeb                          # every included figure
"""
import argparse
import glob
import os
import re
import sys

from pypdf import PdfReader

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from style import MIN_PT  # noqa: E402

COL_PT, TEXT_PT = 236.25, 495.0          # CVPR column and text width


def runs(pdf):
    """[(size in the PDF's own points, text)] of every text run on the first page, and the page width."""
    page = PdfReader(pdf).pages[0]
    out = []

    def visit(text, cm, tm, font, size):
        if text.strip():
            c, d = tm[2], tm[3]
            sy = ((c * cm[0] + d * cm[2]) ** 2 + (c * cm[1] + d * cm[3]) ** 2) ** 0.5
            out.append((size * sy, text.strip()))
    page.extract_text(visitor_text=visit)
    return out, float(page.mediabox.width)


def check(pdf, printed_pt, limit=MIN_PT, show=8):
    rs, w = runs(pdf)
    k = printed_pt / w
    small = sorted((round(s * k, 2), t) for s, t in rs if 0 < s * k < limit - 0.01)   # 0.01 pt: width rounding
    low = min((s * k for s, _ in rs if s > 0), default=float("nan"))
    print(f"{pdf}: printed at {printed_pt:.1f} pt (x{k:.2f}), smallest text {low:.1f} pt, "
          f"{len(small)} of {len(rs)} runs below {limit:g} pt" + ("" if not small else
          ": " + ", ".join(f"{t[:20]!r} {s}" for s, t in small[:show])))
    return not small


def paper_figures(paper):
    """{figure pdf: printed width in pt} from the paper source's \\includegraphics widths."""
    out = {}
    for f in [os.path.join(paper, "main.tex")] + glob.glob(os.path.join(paper, "sections", "**", "*.tex"), recursive=True):
        for m in re.finditer(r"\\begin\{(figure\*?)\}(.*?)\\end\{\1\}", open(f).read(), re.S):
            env, body = m.group(1), m.group(2)
            for g in re.finditer(r"\\includegraphics\[width=([0-9.]*)\\linewidth\]\{([^}]*\.pdf)\}", body):
                in_col = env == "figure" or ("\\begin{minipage}" in body and "\\columnwidth" in body)
                out[os.path.join(paper, g.group(2))] = float(g.group(1) or 1) * (COL_PT if in_col else TEXT_PT)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pdf", nargs="?")
    ap.add_argument("--width", type=float, help="printed width in inches")
    ap.add_argument("--paper", help="check every figure the paper source includes")
    a = ap.parse_args()
    if a.paper:
        ok = all([check(p, w) for p, w in sorted(paper_figures(a.paper).items())])
    else:
        ok = check(a.pdf, a.width * 72)
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
