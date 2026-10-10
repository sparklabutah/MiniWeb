"""Download the external media the sites display, so they render without the internet: the images that site data links
to on other hosts (wikiHow step images, phone photos, product images, images inside posts, issues and book text) and
the map's basemap tiles over the map's area. Files land in data/media/<host>/<path>, with manifest.jsonl recording each
URL's status; the app serves /media/... from there (miniweb.app.media) and rewrites the pages' links to it.

Audio that no page plays (the dictionary's pronunciation files) is left out unless --audio is given.

    python scripts/fetch_site_media.py --db $MINIWEB_DB                 # images, then tiles; resumable
    python scripts/fetch_site_media.py --db $MINIWEB_DB --tiles-only
"""
import argparse, hashlib, json, math, os, re, sqlite3, threading, time, urllib.error, urllib.parse, urllib.request
from concurrent.futures import ThreadPoolExecutor

import yaml

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
AGENT = "MiniWeb-media-archiver/1.0 (research benchmark; one-time archive of linked media)"
EXT = r"(?:jpe?g|png|gif|webp|svg|bmp|ico|avif|mp4|webm|mov|m4v|mp3|m4a|ogg|oga|opus|wav|flac)"
URL_RX = re.compile(r"https?://([A-Za-z0-9.-]+)(/[^\"'\s<>)\]]*?\." + EXT + r")(?=[\"'\s<>)\],?#]|$)", re.I)
AUDIO = re.compile(r"\.(mp3|ogg|oga|opus|wav|flac|m4a)$", re.I)
TILES = "https://cartodb-basemaps-{s}.global.ssl.fastly.net/light_nolabels/{z}/{x}/{y}.png"
TILE_HOST = "cartodb-basemaps.global.ssl.fastly.net"


def local_path(url):
    """data/media-relative path for a URL: <host>/<path>, with long or query-bearing names hashed."""
    u = urllib.parse.urlsplit(url)
    path = urllib.parse.unquote(u.path).lstrip("/")
    if u.query or len(path) > 180 or ".." in path:
        stem, ext = os.path.splitext(path)
        path = f"{stem[:120]}__{hashlib.sha1(url.encode()).hexdigest()[:16]}{ext[:8]}"
    return os.path.join(u.netloc.lower(), path)


def media_urls(db, sites_yaml, audio=False):
    sites = [s["id"] for s in yaml.safe_load(open(sites_yaml))["sites"]]
    prefixes = tuple(s.replace("-", "_") + "_" for s in sites)
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    tables = [t for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table'")
              if t.startswith(prefixes) and not t.startswith("fts_")]
    urls = set()
    for t in tables:
        try:
            cols = [r[1] for r in con.execute(f'PRAGMA table_info("{t}")') if (r[2] or "").upper() in ("TEXT", "")]
        except sqlite3.Error:
            continue
        if not cols:
            continue
        for row in con.execute(f'SELECT {", ".join(f"[{c}]" for c in cols)} FROM "{t}"'):
            for v in row:
                if isinstance(v, str) and "http" in v:
                    for m in URL_RX.finditer(v):
                        if audio or not AUDIO.search(m.group(0)):
                            urls.add(m.group(0))
    return sorted(urls)


def tile_urls(db, zmin, zmax, pad=0.08):
    """Basemap tiles over the map site's places (lat/lng columns of its tables), zoom zmin..zmax."""
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    lat, lng = [], []
    for (t,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'map_services_%'"):
        cols = {r[1] for r in con.execute(f'PRAGMA table_info("{t}")')}
        la, lo = next((c for c in ("lat", "latitude") if c in cols), None), next((c for c in ("lng", "lon", "longitude") if c in cols), None)
        if la and lo:
            r = con.execute(f'SELECT MIN(CAST([{la}] AS REAL)), MAX(CAST([{la}] AS REAL)), MIN(CAST([{lo}] AS REAL)), '
                            f'MAX(CAST([{lo}] AS REAL)) FROM "{t}" WHERE [{la}] IS NOT NULL AND [{la}] != ""').fetchone()
            if r[0] is not None:
                lat += [r[0], r[1]]; lng += [r[2], r[3]]
    s, n, w, e = min(lat) - pad, max(lat) + pad, min(lng) - pad, max(lng) + pad
    out = []
    for z in range(zmin, zmax + 1):
        def xy(la, lo):
            x = int((lo + 180) / 360 * 2 ** z)
            y = int((1 - math.asinh(math.tan(math.radians(la))) / math.pi) / 2 * 2 ** z)
            return x, y
        x0, y1 = xy(s, w); x1, y0 = xy(n, e)
        for x in range(x0, x1 + 1):
            for y in range(y0, y1 + 1):
                out.append((z, x, y))
    return (s, n, w, e), out


class Fetcher:
    def __init__(self, out, per_host=8):
        self.out, self.per_host = out, per_host
        self.sem, self.lock = {}, threading.Lock()
        self.manifest = open(os.path.join(out, "manifest.jsonl"), "a")
        self.done = {json.loads(l)["url"] for l in open(os.path.join(out, "manifest.jsonl"))} \
            if os.path.getsize(os.path.join(out, "manifest.jsonl")) else set()

    def get(self, url, rel=None):
        if url in self.done:
            return
        rel = rel or local_path(url)
        host = urllib.parse.urlsplit(url).netloc
        with self.lock:
            sem = self.sem.setdefault(host, threading.Semaphore(self.per_host))
        status, size, ctype = None, 0, None
        with sem:
            for attempt in range(3):
                try:
                    req = urllib.request.Request(url, headers={"User-Agent": AGENT})
                    with urllib.request.urlopen(req, timeout=15) as r:
                        data, ctype, status = r.read(), r.headers.get("Content-Type"), r.status
                    path = os.path.join(self.out, rel)
                    os.makedirs(os.path.dirname(path), exist_ok=True)
                    with open(path, "wb") as f:
                        f.write(data)
                    size = len(data)
                    break
                except urllib.error.HTTPError as e:
                    status = e.code
                    if e.code in (429, 500, 502, 503, 504):
                        time.sleep(2 * (attempt + 1)); continue
                    break
                except Exception as e:  # noqa: BLE001 -- network errors: record and move on
                    status = type(e).__name__
                    reason = str(getattr(e, "reason", e)).lower()
                    if any(k in reason for k in ("name or service", "not known", "refused", "certificate", "no address")):
                        break                             # a host that is gone: retrying cannot help
                    time.sleep(1 + attempt)
        with self.lock:
            self.manifest.write(json.dumps({"url": url, "path": rel if size else None, "status": status, "bytes": size,
                                            "content_type": ctype}) + "\n")
            self.manifest.flush()
            self.done.add(url)


def run(fetcher, jobs, label, workers):
    t0, n = time.time(), len(jobs)
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(lambda j: fetcher.get(*j), jobs)):
            if i % 2000 == 0:
                print(f"{label}: {i}/{n} ({time.time() - t0:.0f}s)", flush=True)
    print(f"{label}: done {n} in {time.time() - t0:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=os.environ.get("MINIWEB_DB"))
    ap.add_argument("--sites", default=os.path.join(ROOT, "data", "sites.yaml"))
    ap.add_argument("--out", default=os.path.join(ROOT, "data", "media"))
    ap.add_argument("--audio", action="store_true", help="also the audio files no page plays")
    ap.add_argument("--tiles-only", action="store_true")
    ap.add_argument("--zoom", default="10-17", help="basemap tile zoom range")
    ap.add_argument("--workers", type=int, default=32)
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    open(os.path.join(a.out, "manifest.jsonl"), "a").close()
    f = Fetcher(a.out)
    if not a.tiles_only:
        urls = media_urls(a.db, a.sites, a.audio)
        print(f"{len(urls)} media URLs", flush=True)
        import random
        random.Random(0).shuffle(urls)                     # big live hosts interleave with the dead long tail
        run(f, [(u, None) for u in urls], "media", a.workers)
    z0, z1 = (int(x) for x in a.zoom.split("-"))
    bbox, tiles = tile_urls(a.db, z0, z1)
    print(f"{len(tiles)} basemap tiles over {bbox}, zoom {z0}-{z1}", flush=True)
    jobs = [(TILES.format(s="abcd"[(x + y) % 4], z=z, x=x, y=y), os.path.join(TILE_HOST, "light_nolabels", str(z), str(x),
                                                                              f"{y}.png")) for z, x, y in tiles]
    run(f, jobs, "tiles", min(a.workers, 8))


if __name__ == "__main__":
    main()
