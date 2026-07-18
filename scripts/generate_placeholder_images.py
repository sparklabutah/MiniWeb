"""Generate real images for every placeholder image in MiniWeb.

Buckets:
  covers   — books_comics_books.cover_url pointing at placehold.co (per book)
  avatars  — user-table avatar columns pointing at placehold.co
  missing  — /static/* paths referenced in the DB with no file on disk
  bizco    — business-company template images (placehold.co built in templates)

Images go under app/static/ at deterministic paths; existing files are
skipped, so the run is resumable. DB rows are only touched by --apply-db,
which writes a backup of every old value first. fts_* tables are external-
content FTS5 indexes over the base tables and are never written.

Usage:
  python scripts/generate_placeholder_images.py --pilot 4    # try a few, print token usage
  python scripts/generate_placeholder_images.py              # full generation run
  python scripts/generate_placeholder_images.py --apply-db   # repoint DB placeholder URLs
"""
import argparse
import io
import json
import re
import sqlite3
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
STATIC = ROOT / "app" / "static"
MODEL = "gemini-3.1-flash-image"
STYLE = "Simple, clean, flat illustration style with a muted palette. No text unless asked."

IMGCOL = re.compile(r"image|img|avatar|photo|thumbnail|thumb|logo|poster|cover|icon|picture|banner", re.I)
TXT_FIELDS = ["title", "name", "headline", "caption", "label", "description", "summary",
              "bio", "category", "type", "subject", "tags", "location"]


# ---------------------------------------------------------------------------
# Inventory
# ---------------------------------------------------------------------------

def _row_ctx(row, cols):
    return {k: str(row[k])[:150] for k in TXT_FIELDS if k in cols and row[k]}


def build_jobs():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    jobs = []

    # covers — one per book row so every book gets a distinct cover
    for r in db.execute("SELECT id, title, author, category, subject, year FROM books_comics_books "
                        "WHERE cover_url LIKE '%placehold%'"):
        jobs.append({
            "out": f"generated/covers/book_{r['id']}.jpg",
            "aspect": "3:4",
            "prompt": (f"Book cover for \"{r['title']}\" by {r['author'] or 'unknown author'}. "
                       f"Topic: {r['category'] or r['subject'] or 'general'}. "
                       f"Flat modern minimal cover art with the title as clear typography. Muted colors."),
            "db": {"table": "books_comics_books", "pk": r["id"], "col": "cover_url",
                   "new": f"/static/generated/covers/book_{r['id']}.jpg"},
            "bucket": "covers",
        })

    # placehold avatars in user tables
    for t in [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                       "AND name LIKE '%users' AND name NOT LIKE 'fts%'")]:
        cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])")]
        acol = next((c for c in cols if c in ("avatar", "avatar_url")), None)
        if not acol:
            continue
        for r in db.execute(f"SELECT * FROM [{t}] WHERE [{acol}] LIKE '%placehold%'"):
            out = f"generated/avatar_{t}_{r['id']}.jpg"
            jobs.append({
                "out": out, "aspect": "1:1",
                "prompt": (f"Flat vector profile avatar, head and shoulders, of a person named "
                           f"{r['name'] if 'name' in cols and r['name'] else r['username']}. "
                           f"Friendly, neutral solid background."),
                "db": {"table": t, "pk": r["id"], "col": acol, "new": f"/static/{out}"},
                "bucket": "avatars",
            })

    # missing static files — dedupe by path, prompt from first referencing base row
    seen = {}
    for t in [r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type='table' "
                                       "AND name NOT LIKE 'fts%'")]:
        cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])")]
        icols = [c for c in cols if IMGCOL.search(c)]
        if not icols:
            continue
        for r in db.execute(f"SELECT * FROM [{t}]"):
            for c in icols:
                v = r[c]
                if not isinstance(v, str) or not v.startswith("/static") or (ROOT / "app" / v.lstrip("/")).exists():
                    continue
                if v in seen:
                    continue
                ctx = _row_ctx(r, cols)
                desc = ctx.get("caption") or ctx.get("title") or ctx.get("name") or ctx.get("description") or ""
                extra = ", ".join(f"{k}: {ctx[k]}" for k in ("tags", "location", "category", "type") if k in ctx)
                if "avatar" in c or "avatar" in v:
                    prompt, aspect = (f"Flat vector profile avatar, head and shoulders. "
                                      f"{desc or 'A friendly person'}. Neutral solid background."), "1:1"
                elif "thumb" in c or "thumb" in v:
                    prompt, aspect = f"Video thumbnail illustration for: {desc or t}. {extra}", "16:9"
                else:
                    prompt, aspect = (f"Casual social-media photo-style image. {desc or 'everyday scene'}. "
                                      f"{extra}"), "1:1"
                seen[v] = True
                jobs.append({"out": v.replace("/static/", "", 1), "aspect": aspect,
                             "prompt": prompt, "db": None, "bucket": "missing"})

    # business-company template images (URLs are built in templates, not the DB)
    biz = []
    for r in db.execute("SELECT id, name, description FROM business_company_products"):
        biz.append((f"generated/business-company/product-{r['id']}.jpg", "16:9",
                    f"Marketing product image: {r['name']}. {str(r['description'] or '')[:120]}"))
    for r in db.execute("SELECT name, description FROM business_company_services"):
        slug = re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")
        biz.append((f"generated/business-company/service-{slug}.jpg", "16:9",
                    f"Corporate service illustration: {r['name']}. {str(r['description'] or '')[:120]}"))
    for r in db.execute("SELECT name, title FROM business_company_team"):
        slug = re.sub(r"[^a-z0-9]+", "-", r["name"].lower()).strip("-")
        biz.append((f"generated/business-company/team-{slug}.jpg", "1:1",
                    f"Professional headshot-style flat portrait of {r['name']}, {r['title'] or 'employee'}. "
                    f"Neutral background."))
    for r in db.execute("SELECT id, title FROM business_company_posts"):
        biz.append((f"generated/business-company/blog-{r['id']}.jpg", "16:9",
                    f"Blog header illustration for: {r['title']}"))
    for slug, prompt in [
        ("apex-hero-banner", "Wide corporate hero banner, modern office building exterior, abstract tech overlay"),
        ("apex-office", "Wide shot of a modern open-plan office interior"),
        ("apex-team-group", "Group photo style illustration of a diverse corporate team in an office"),
        ("apex-careers-office", "Bright modern office culture scene, people collaborating"),
        ("apex-office-culture", "Casual office culture scene, team at a whiteboard"),
    ]:
        biz.append((f"generated/business-company/{slug}.jpg", "16:9", prompt))
    for out, aspect, prompt in biz:
        jobs.append({"out": out, "aspect": aspect, "prompt": prompt, "db": None, "bucket": "bizco"})

    db.close()
    return jobs


# ---------------------------------------------------------------------------
# Generation
# ---------------------------------------------------------------------------

_client = None
_client_lock = threading.Lock()


def client():
    global _client
    with _client_lock:
        if _client is None:
            from google import genai
            from google.oauth2 import service_account
            from app.llm import _get_env
            info = json.loads(_get_env("GOOGLE_CREDENTIALS_JSON"))
            creds = service_account.Credentials.from_service_account_info(
                info, scopes=["https://www.googleapis.com/auth/cloud-platform"])
            _client = genai.Client(vertexai=True, credentials=creds,
                                   project=_get_env("GOOGLE_CLOUD_PROJECT"),
                                   location=_get_env("GOOGLE_CLOUD_LOCATION") or "global")
        return _client


def generate_one(job):
    """Generate one image; returns (job, usage_tokens or None, error or None)."""
    from google.genai import types
    out_path = STATIC / job["out"]
    if out_path.exists():
        return job, None, "exists"
    # "0.5K" is rejected by this endpoint; "512" is accepted and bills at the
    # 0.5K rate (747 output tokens/image). IMAGE-only modality is also rejected.
    cfg = types.GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=types.ImageConfig(aspect_ratio=job["aspect"], image_size="512"),
    )
    last_err = None
    for attempt in range(4):
        try:
            resp = client().models.generate_content(
                model=MODEL, contents=f"{job['prompt']} {STYLE}", config=cfg)
            img = next((p.inline_data for c in (resp.candidates or [])
                        for p in (c.content.parts or []) if p.inline_data), None)
            if img is None:
                # safety block or empty response — retry once with a generic prompt
                if attempt == 0:
                    job = dict(job, prompt=f"Abstract themed illustration, {job['bucket']} image.")
                    continue
                return job, None, f"no image in response ({resp.candidates and resp.candidates[0].finish_reason})"
            from PIL import Image
            im = Image.open(io.BytesIO(img.data)).convert("RGB")
            out_path.parent.mkdir(parents=True, exist_ok=True)
            if out_path.suffix.lower() == ".png":
                im.save(out_path, "PNG")
            else:
                im.save(out_path, "JPEG", quality=82)
            usage = getattr(resp, "usage_metadata", None)
            toks = getattr(usage, "candidates_token_count", None) if usage else None
            return job, toks, None
        except Exception as e:  # 429s, transient API errors
            last_err = e
            time.sleep(2 ** attempt * (1.5 if "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e) else 1))
    return job, None, f"failed after retries: {last_err}"


def run(jobs, workers, log_path):
    done = skipped = failed = 0
    t0 = time.time()
    with open(log_path, "a") as log, ThreadPoolExecutor(max_workers=workers) as ex:
        futs = [ex.submit(generate_one, j) for j in jobs]
        for f in as_completed(futs):
            job, toks, err = f.result()
            if err == "exists":
                skipped += 1
            elif err:
                failed += 1
                log.write(json.dumps({"out": job["out"], "error": err}) + "\n")
            else:
                done += 1
                log.write(json.dumps({"out": job["out"], "tokens": toks}) + "\n")
            log.flush()
            n = done + skipped + failed
            if n % 25 == 0 or n == len(jobs):
                rate = done / max(time.time() - t0, 1)
                print(f"[{n}/{len(jobs)}] ok={done} skip={skipped} fail={failed} "
                      f"({rate:.1f} img/s)", flush=True)
    return done, skipped, failed


# ---------------------------------------------------------------------------
# DB apply
# ---------------------------------------------------------------------------

def apply_db(jobs):
    """Repoint placeholder URLs at generated files. Only rows whose image
    exists on disk are updated; a JSON backup of old values is written first."""
    import datetime
    targets = [j for j in jobs if j["db"] and (STATIC / j["out"]).exists()]
    if not targets:
        print("nothing to apply (no generated files with a db target)")
        return
    db = sqlite3.connect(DB_PATH)
    backup_dir = ROOT / "data" / "backups" / f"placeholder-images-{datetime.date.today()}"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup, updated = [], 0
    for j in targets:
        d = j["db"]
        old = db.execute(f"SELECT [{d['col']}] FROM [{d['table']}] WHERE id=?", (d["pk"],)).fetchone()
        backup.append({**d, "old": old[0] if old else None})
        db.execute(f"UPDATE [{d['table']}] SET [{d['col']}]=? WHERE id=?", (d["new"], d["pk"]))
        updated += 1
    (backup_dir / "db_url_backup.json").write_text(json.dumps(backup, indent=1))
    db.commit()
    db.close()
    print(f"updated {updated} rows; backup at {backup_dir/'db_url_backup.json'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", type=int, default=0, help="generate only N jobs (spread across buckets)")
    ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--apply-db", action="store_true", help="repoint DB urls at generated files")
    ap.add_argument("--bucket", help="restrict to one bucket (covers/avatars/missing/bizco)")
    args = ap.parse_args()

    jobs = build_jobs()
    if args.bucket:
        jobs = [j for j in jobs if j["bucket"] == args.bucket]
    from collections import Counter
    print("jobs:", len(jobs), dict(Counter(j["bucket"] for j in jobs)))

    if args.apply_db:
        apply_db(jobs)
        sys.exit(0)

    if args.pilot:
        by_bucket = {}
        for j in jobs:
            by_bucket.setdefault(j["bucket"], []).append(j)
        picked = []
        while len(picked) < args.pilot and any(by_bucket.values()):
            for b in list(by_bucket):
                if by_bucket[b] and len(picked) < args.pilot:
                    picked.append(by_bucket[b].pop(0))
        jobs = picked
        print("pilot jobs:", [j["out"] for j in jobs])

    log_path = ROOT / "data" / "backups" / "imagegen_log.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    done, skipped, failed = run(jobs, args.workers, log_path)
    print(f"done={done} skipped={skipped} failed={failed}")
