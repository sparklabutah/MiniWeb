"""Generate seed media/PDF assets for the simulated file explorer (filesystem/).

- A real, rendered Resume PDF (reportlab).
- Real, audible MP3s (Music/) and real, playable VP9/WebM clips (Movies/).

Dev-only asset generation (the app just serves the committed files at runtime).
Deps: pip install reportlab pillow numpy imageio imageio-ffmpeg
Re-runnable; safe to re-run. Run:
    ~/.conda/envs/miniweb/bin/python scripts/gen_filesystem_assets.py
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "filesystem"


# ── Resume PDF (real, rendered) ──────────────────────────────────────────────
def make_resume_pdf(path: Path):
    from reportlab.lib.pagesizes import LETTER
    from reportlab.lib.units import inch
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    HRFlowable)

    styles = getSampleStyleSheet()
    name = ParagraphStyle("name", parent=styles["Title"], fontSize=22,
                          spaceAfter=2, textColor=colors.HexColor("#1a2b4a"))
    contact = ParagraphStyle("contact", parent=styles["Normal"], fontSize=9.5,
                             alignment=TA_CENTER, textColor=colors.HexColor("#555"))
    head = ParagraphStyle("head", parent=styles["Heading2"], fontSize=12,
                          spaceBefore=12, spaceAfter=4,
                          textColor=colors.HexColor("#2a6"))
    body = ParagraphStyle("body", parent=styles["Normal"], fontSize=10, leading=14)
    role = ParagraphStyle("role", parent=body, fontName="Helvetica-Bold", spaceBefore=6)

    doc = SimpleDocTemplate(str(path), pagesize=LETTER,
                            leftMargin=0.9 * inch, rightMargin=0.9 * inch,
                            topMargin=0.8 * inch, bottomMargin=0.8 * inch)
    E = []
    E.append(Paragraph("Jordan Avery", ParagraphStyle("n", parent=name, alignment=TA_CENTER)))
    E.append(Paragraph("Lakeport, WA &nbsp;·&nbsp; jordan.avery@lakemail.com &nbsp;·&nbsp; (555) 018-2245", contact))
    E.append(Spacer(1, 6))
    E.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#2a6")))

    E.append(Paragraph("Summary", head))
    E.append(Paragraph(
        "Product-minded software engineer with 6 years building web platforms and "
        "data tooling. Comfortable across the stack; happiest turning fuzzy problems "
        "into shipped, measurable features.", body))

    E.append(Paragraph("Experience", head))
    E.append(Paragraph("Senior Software Engineer — Meridian Systems (2022–present)", role))
    E.append(Paragraph("• Led the checkout re-architecture that cut payment errors 38%.<br/>"
                       "• Mentored 4 engineers; owned the internal design-system migration.", body))
    E.append(Paragraph("Software Engineer — Northlake Labs (2019–2022)", role))
    E.append(Paragraph("• Built the analytics ingestion pipeline (2B events/day).<br/>"
                       "• Cut p95 dashboard load from 4.1s to 900ms.", body))

    E.append(Paragraph("Education", head))
    E.append(Paragraph("B.S. Computer Science — Cascadia University, 2019", body))

    E.append(Paragraph("Skills", head))
    E.append(Paragraph("Python · TypeScript · SQL · Flask · React · Playwright · PostgreSQL", body))

    doc.build(E)
    print("wrote", path, f"({path.stat().st_size} B)")


# ── Real, audible MP3 (bundled ffmpeg + libmp3lame) ──────────────────────────
def make_mp3(path: Path, seconds=6, freq=220.0, wobble=0.0):
    import subprocess
    import imageio_ffmpeg
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    # A soft sine (optionally vibrato'd) at low volume — real audio, not silence.
    src = f"sine=frequency={freq}:duration={seconds}"
    flt = "tremolo=f=5:d=0.3,volume=0.35" if wobble else "volume=0.35"
    subprocess.run([ff, "-y", "-f", "lavfi", "-i", src, "-af", flt,
                    "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
                   check=True, capture_output=True)
    print("wrote", path, f"({path.stat().st_size} B)")


# ── Real, playable VP9/WebM video (themed animated frames via imageio) ───────
def _gradient(w, h, c1, c2):
    import numpy as np
    ys = np.linspace(0, 1, h)[:, None, None]
    g = (np.array(c1) * (1 - ys) + np.array(c2) * ys)   # (h,1,3)
    return np.repeat(g, w, axis=1).astype("uint8")       # (h,w,3)


def _video_frames(title, c1, c2, motif, n=30, w=320, h=240):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    try:
        font = ImageFont.load_default(size=24)
        small = ImageFont.load_default(size=13)
    except TypeError:                                    # older Pillow
        font = small = ImageFont.load_default()
    frames = []
    for i in range(n):
        t = i / (n - 1)
        img = Image.fromarray(_gradient(w, h, c1, c2))
        d = ImageDraw.Draw(img, "RGBA")
        if motif == "sun":
            d.ellipse([w - 90, 24 + int(t * 120), w - 30, 84 + int(t * 120)], fill=(255, 236, 150))
        elif motif == "mountains":
            d.polygon([(0, h), (110, 120), (200, h)], fill=(0, 0, 0, 60))
            d.polygon([(120, h), (230, 90), (w, h)], fill=(0, 0, 0, 90))
        elif motif == "buildings":
            for bx, bh in [(30, 120), (80, 80), (140, 150), (210, 100), (270, 130)]:
                d.rectangle([bx, h - bh, bx + 36, h], fill=(0, 0, 0, 90))
        elif motif == "confetti":
            rng = np.random.RandomState(7)
            for _ in range(40):
                cx = int(rng.rand() * w); cy = int((rng.rand() + t) % 1 * h)
                col = tuple(int(c) for c in rng.randint(120, 255, 3))
                d.ellipse([cx, cy, cx + 6, cy + 6], fill=col + (220,))
        # title with a translucent bar
        d.rectangle([0, h - 40, w, h], fill=(0, 0, 0, 110))
        d.text((12, h - 32), title, font=font, fill=(255, 255, 255))
        d.text((12, 10), "● REC  0:%02d" % int(t * 6), font=small, fill=(255, 90, 90))
        frames.append(np.asarray(img))
    return frames


def make_video(path: Path, title, c1, c2, motif):
    # VP9/WebM, not H.264/MP4: the open-source Chromium that browser agents run in
    # omits the proprietary H.264 codec, so an .mp4 won't decode there — WebM plays
    # in Chromium AND in every modern user browser.
    import imageio
    frames = _video_frames(title, c1, c2, motif)
    imageio.mimwrite(str(path), frames, fps=12, codec="libvpx-vp9",
                     macro_block_size=8, output_params=["-pix_fmt", "yuv420p", "-b:v", "400k"])
    print("wrote", path, f"({path.stat().st_size} B)")


if __name__ == "__main__":
    (ROOT / "Documents").mkdir(parents=True, exist_ok=True)
    (ROOT / "Music").mkdir(parents=True, exist_ok=True)
    (ROOT / "Movies").mkdir(parents=True, exist_ok=True)

    make_resume_pdf(ROOT / "Documents" / "Resume.pdf")

    for name, secs, freq, wob in [("Summer Vibes.mp3", 7, 330, 1), ("Acoustic Morning.mp3", 6, 262, 0),
                                  ("Focus Flow.mp3", 8, 196, 0), ("Late Night Drive.mp3", 7, 147, 1),
                                  ("Coffee Shop Jazz.mp3", 6, 294, 1)]:
        make_mp3(ROOT / "Music" / name, secs, freq, wob)

    for name, c1, c2, motif in [
        ("Beach Sunset.webm", (255, 140, 60), (120, 40, 110), "sun"),
        ("Birthday Party.webm", (90, 40, 160), (230, 90, 150), "confetti"),
        ("Product Demo.webm", (30, 60, 120), (10, 20, 45), "plain"),
        ("City Timelapse.webm", (40, 55, 90), (10, 12, 28), "buildings"),
        ("Hiking Trip.webm", (120, 200, 120), (30, 90, 60), "mountains"),
    ]:
        make_video(ROOT / "Movies" / name, name[:-5], c1, c2, motif)
