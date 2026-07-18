"""Second placeholder-image pass: fake CDN domains + missing local files
that pass 1 missed (media_url-style columns, JSON array columns, .svg refs,
and site-scoped /sites/<site>/static paths).

Buckets:
  fake    — image columns pointing at made-up hosts (pixshare.io,
            streamhub.tv, callhub.io); generate + repoint the DB.
  missing — local refs (/static/... or /sites/<site>/static/...) with no file
            on disk. .jpg/.png are generated at the exact referenced path
            (no DB change); .svg refs get a sibling .jpg + a DB repoint.
Handles both plain string columns and JSON array columns.

Usage: python scripts/generate_placeholder_images_pass2.py [--dry-run]
DB values are backed up to data/backups/placeholder-images-<date>/pass2_backup.json
"""
import io
import json
import re
import sqlite3
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.generate_placeholder_images import client, MODEL, STYLE  # noqa: E402

DB_PATH = ROOT / "data" / "trimmed_miniweb.db"
FAKE_HOSTS = ("pixshare.io", "streamhub.tv", "callhub.io")
IMGCOL = re.compile(r"image|img|avatar|photo|thumbnail|thumb|logo|poster|cover|icon|picture|banner|media", re.I)


def local_path(url):
    """Filesystem path for a /static or /sites/<site>/static url, else None."""
    if url.startswith("/static/"):
        # data/static (volume) shadows app/static for generated content
        p = ROOT / "data" / url.lstrip("/")
        if p.exists():
            return p
        bundled = ROOT / "app" / url.lstrip("/")
        return bundled if bundled.exists() else p
    if url.startswith("/sites/"):
        return ROOT / url.lstrip("/")
    return None


def aspect_for(col, url):
    if "avatar" in col or "avatar" in url or "profile" in url:
        return "1:1"
    if "thumb" in col or "thumb" in url:
        return "16:9"
    return "1:1"


def prompt_for(table, col, url, ctx):
    desc = ctx.get("caption") or ctx.get("title") or ctx.get("name") or ""
    person = ctx.get("name") or ctx.get("username") or "a person"
    bio = (ctx.get("bio") or ctx.get("description") or "")[:100]
    if "avatar" in col or "profile" in url:
        return (f"Flat vector profile avatar, head and shoulders, of {person}."
                f" {bio}. Neutral solid background.")
    if "photo" in col and table.startswith("dating"):
        return (f"Portrait-style flat illustration of {person} for a dating profile."
                f" {bio}. Warm, friendly.")
    if "thumb" in col:
        return f"Video thumbnail illustration for: {desc or table}."
    return f"Casual social-media photo-style image. {desc or 'everyday moment'}. {bio}"


def build_jobs():
    db = sqlite3.connect(DB_PATH)
    db.row_factory = sqlite3.Row
    jobs, seen_out = [], set()
    tabs = [r[0] for r in db.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'fts%'")]
    for t in tabs:
        cols = [c[1] for c in db.execute(f"PRAGMA table_info([{t}])")]
        icols = [c for c in cols if IMGCOL.search(c)]
        if not icols:
            continue
        pk = cols[0]
        for row in db.execute(f"SELECT * FROM [{t}]"):
            ctx = {k: str(row[k])[:150] for k in
                   ("caption", "title", "name", "username", "bio", "description")
                   if k in cols and row[k]}
            for c in icols:
                v = row[c]
                if not isinstance(v, str) or not v:
                    continue
                is_array = v.startswith("[")
                urls = []
                if is_array:
                    try:
                        urls = [u for u in json.loads(v) if isinstance(u, str)]
                    except (ValueError, TypeError):
                        continue
                else:
                    urls = [v]
                new_urls, patched = [], False
                for u in urls:
                    fake = any(h in u for h in FAKE_HOSTS)
                    lp = local_path(u)
                    missing_local = lp is not None and not lp.exists()
                    if not fake and not missing_local:
                        new_urls.append(u)
                        continue
                    if fake:
                        stem = re.sub(r"[^a-z0-9]+", "-", u.rsplit("/", 1)[-1].rsplit(".", 1)[0].lower())
                        new_u = f"/static/generated/pass2/{t}_{row[pk]}_{stem}.jpg"
                        out = ROOT / "app" / new_u.lstrip("/")
                    elif u.lower().endswith(".svg"):
                        new_u = u[:-4] + ".jpg"
                        out = local_path(new_u)
                    else:
                        new_u, out = u, lp  # regenerate at the exact path, no repoint
                    if str(out) not in seen_out:
                        seen_out.add(str(out))
                        jobs.append({"out": out, "aspect": aspect_for(c, u),
                                     "prompt": prompt_for(t, c, u, ctx)})
                    new_urls.append(new_u)
                    patched = patched or (new_u != u)
                if patched:
                    new_val = json.dumps(new_urls) if is_array else new_urls[0]
                    jobs.append({"db_only": True, "table": t, "pk_col": pk, "pk": row[pk],
                                 "col": c, "old": v, "new": new_val})
    db.close()
    return jobs


def generate_one(job):
    from google.genai import types
    from PIL import Image
    out = job["out"]
    if out.exists():
        return job, "exists"
    last = None
    for attempt in range(4):
        try:
            resp = client().models.generate_content(
                model=MODEL, contents=f"{job['prompt']} {STYLE}",
                config=types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config=types.ImageConfig(aspect_ratio=job["aspect"], image_size="512")))
            img = next((p.inline_data for c in (resp.candidates or [])
                        for p in (c.content.parts or []) if p.inline_data), None)
            if img is None:
                if attempt == 0:
                    job = dict(job, prompt="Simple abstract themed illustration.")
                    continue
                return job, "no image"
            im = Image.open(io.BytesIO(img.data)).convert("RGB")
            out.parent.mkdir(parents=True, exist_ok=True)
            if out.suffix.lower() == ".png":
                im.save(out, "PNG")
            else:
                im.save(out, "JPEG", quality=82)
            return job, None
        except Exception as e:
            last = e
            time.sleep(2 ** attempt)
    return job, f"failed: {last}"


if __name__ == "__main__":
    import datetime
    dry = "--dry-run" in sys.argv
    jobs = build_jobs()
    gen = [j for j in jobs if not j.get("db_only")]
    dbj = [j for j in jobs if j.get("db_only")]
    print(f"generate: {len(gen)} images, repoint: {len(dbj)} db values")
    if dry:
        for j in gen[:10]:
            print(" ", j["out"], j["aspect"], j["prompt"][:70])
        for j in dbj[:5]:
            print(" DB", j["table"], j["pk"], j["col"], "->", j["new"][:70])
        sys.exit(0)

    done = failed = 0
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(generate_one, j) for j in gen]
        for f in as_completed(futs):
            job, err = f.result()
            if err and err != "exists":
                failed += 1
                print("FAIL", job["out"], err, flush=True)
            else:
                done += 1
            if (done + failed) % 25 == 0:
                print(f"[{done + failed}/{len(gen)}]", flush=True)
    print(f"images: ok={done} failed={failed}")

    # apply DB repoints only for rows whose new local files all exist
    db = sqlite3.connect(DB_PATH)
    bdir = ROOT / "data" / "backups" / f"placeholder-images-{datetime.date.today()}"
    bdir.mkdir(parents=True, exist_ok=True)
    backup, updated, skipped = [], 0, 0
    for j in dbj:
        new_val = j["new"]
        urls = json.loads(new_val) if new_val.startswith("[") else [new_val]
        paths = [local_path(u) for u in urls]
        if any(p is not None and not p.exists() for p in paths):
            skipped += 1
            continue
        backup.append({k: j[k] for k in ("table", "pk", "col", "old", "new")})
        db.execute(f"UPDATE [{j['table']}] SET [{j['col']}]=? WHERE [{j['pk_col']}]=?",
                   (new_val, j["pk"]))
        updated += 1
    (bdir / "pass2_backup.json").write_text(json.dumps(backup, indent=1))
    db.commit()
    print(f"db: updated={updated} skipped(missing file)={skipped}; backup at {bdir}/pass2_backup.json")
