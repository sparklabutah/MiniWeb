"""Generate seed media/PDF assets for the simulated file explorer (filesystem/).

- A real, rendered Resume PDF (reportlab).
- Dummy but well-formed MP3s (silent MPEG-1 Layer III frames) for Music/.
- Dummy but ISO-recognizable MP4s for Movies/.

Re-runnable; safe to re-run. Run:
    ~/.conda/envs/miniweb/bin/python scripts/gen_filesystem_assets.py
"""
import struct
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


# ── Silent but valid MP3 (MPEG-1 Layer III, 44.1kHz, 128kbps) ────────────────
def _mp3_bytes(seconds=6):
    # Frame header: FF FB 90 00  (MPEG1, LayerIII, no CRC, 128k, 44.1k, stereo)
    header = bytes([0xFF, 0xFB, 0x90, 0x00])
    frame = header + b"\x00" * (417 - 4)          # 417-byte frame, silent
    frames_per_sec = 44100 / 1152                 # ≈ 38.28
    n = int(seconds * frames_per_sec)
    return frame * n


def make_mp3(path: Path, seconds=6):
    path.write_bytes(_mp3_bytes(seconds))
    print("wrote", path, f"({path.stat().st_size} B)")


# ── Minimal ISO-recognizable MP4 (dummy) ─────────────────────────────────────
def _box(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", 8 + len(payload)) + kind + payload


def _mp4_bytes(kb=40):
    ftyp = _box(b"ftyp", b"isom" + struct.pack(">I", 0x200) + b"isomiso2avc1mp41")
    mdat = _box(b"mdat", b"\x00" * (kb * 1024))
    return ftyp + mdat


def make_mp4(path: Path, kb=40):
    path.write_bytes(_mp4_bytes(kb))
    print("wrote", path, f"({path.stat().st_size} B)")


if __name__ == "__main__":
    (ROOT / "Documents").mkdir(parents=True, exist_ok=True)
    (ROOT / "Music").mkdir(parents=True, exist_ok=True)
    (ROOT / "Movies").mkdir(parents=True, exist_ok=True)

    make_resume_pdf(ROOT / "Documents" / "Resume.pdf")

    for name, secs in [("Summer Vibes.mp3", 7), ("Acoustic Morning.mp3", 6),
                       ("Focus Flow.mp3", 8), ("Late Night Drive.mp3", 7),
                       ("Coffee Shop Jazz.mp3", 6)]:
        make_mp3(ROOT / "Music" / name, secs)

    for name, kb in [("Beach Sunset.mp4", 60), ("Birthday Party.mp4", 90),
                     ("Product Demo.mp4", 48), ("City Timelapse.mp4", 72),
                     ("Hiking Trip.mp4", 80)]:
        make_mp4(ROOT / "Movies" / name, kb)
