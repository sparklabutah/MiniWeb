"""Reusable in-network MiniWeb ads.

Ads across MiniWeb are real MiniWeb content, not external banners. Ads are
pulled from SEVERAL source sites (so no single advertiser dominates) and shaped
into a common schema the ad component can render in any format:

    {source, kind, title, image, url, price, meta, cta, rating, reviews, accent}

Sources (all have real images + working detail links):
    ShopHub   — e-commerce products        -> /sites/e-commerce/product/<id>
    BidBarn   — auction listings           -> /sites/auctions-p2p-marketplaces/listing/<id>
    StreamHub — trending videos            -> /sites/video/watch/<id>
    PageTurner— books                      -> /sites/books-comics/book/<id>

Templates call `product_ads(n, seed, sources)` (a Jinja global). It mixes the
sources round-robin, deterministically by `seed`, so different pages show
different, varied ads. Name kept as `product_ads` for backwards compatibility;
`ads` is an alias.
"""
import hashlib
import importlib
import json

from flask import url_for
from app import db

_PLACEHOLDER = "transparent-pixel"
_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")

_ACCENT = {
    "ShopHub": "#0b7a3b",
    "BidBarn": "#c2410c",
    "StreamHub": "#db2777",
    "PageTurner": "#7c3aed",
}


def _seeded_order(items, seed, keyfn):
    """Deterministic shuffle: sort by hash(seed + item-key)."""
    return sorted(items, key=lambda it: hashlib.md5(
        (str(seed) + "|" + keyfn(it)).encode()).hexdigest())


def _is_real_img(u):
    u = (u or "")
    return bool(u) and _PLACEHOLDER not in u and u.lower().split("?")[0].endswith(_IMG_EXT)


def _clean_brand(brand):
    b = (brand or "").strip()
    for junk in ("Brand:", "Visit the", "Brand"):
        b = b.replace(junk, "")
    return b.replace(" Store", "").strip(" :·-—")


def _fmt_int(n):
    try:
        n = int(float(n))
    except (TypeError, ValueError):
        return "0"
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}".rstrip("0").rstrip(".") + "M"
    if n >= 1_000:
        return f"{n/1_000:.1f}".rstrip("0").rstrip(".") + "K"
    return str(n)


def _trim(s, n=70):
    s = (s or "").strip()
    return s if len(s) <= n else s[:n - 1] + "…"


def _safe_url(endpoint, fallback, **kw):
    try:
        return url_for(endpoint, **kw)
    except Exception:
        return fallback


# ---------------------------------------------------------------------------
# Per-source providers — each returns a list of raw candidate ad dicts
# ---------------------------------------------------------------------------

def _shop_pool():
    try:
        ecom = importlib.import_module("sites.e-commerce.routes")
        prods = ecom._get_products()
    except Exception:
        return []
    out = []
    for p in prods:
        img = next((u for u in (p.get("images") or []) if _is_real_img(u)), None)
        if not img or not p.get("price"):
            continue
        out.append({
            "source": "ShopHub", "kind": "product", "_key": p.get("asin") or str(p.get("id")),
            "title": _trim(p.get("name")), "image": img,
            "url": _safe_url("e-commerce.product_detail", "/sites/e-commerce/", product_id=p["id"]),
            "price": f"${p['price']:.2f}", "meta": _clean_brand(p.get("brand")) or "ShopHub",
            "cta": "Shop now", "rating": p.get("rating") or 0, "reviews": p.get("total_reviews") or 0,
        })
    return out


def _auction_pool():
    t = db.get_table_name("auctions-p2p-marketplaces", "products")
    if not t:
        return []
    try:
        rows = db.execute(
            f'SELECT id,name,image_url,current_price,buy_now_price,num_bids,status '
            f'FROM "{t}" WHERE image_url LIKE "http%" AND status="active" LIMIT 400')
    except Exception:
        return []
    out = []
    for r in rows:
        if not _is_real_img(r.get("image_url")):
            continue
        try:
            bid = float(r.get("current_price") or r.get("buy_now_price") or 0)
        except (TypeError, ValueError):
            bid = 0
        out.append({
            "source": "BidBarn", "kind": "auction", "_key": str(r["id"]),
            "title": _trim(r.get("name")), "image": r["image_url"],
            "url": _safe_url("auctions-p2p-marketplaces.listing_detail",
                             "/sites/auctions-p2p-marketplaces/", listing_id=r["id"]),
            "price": f"${bid:.2f}", "meta": f"{r.get('num_bids') or 0} bids · auction",
            "cta": "View auction", "rating": 0, "reviews": 0,
        })
    return out


def _video_pool():
    t = db.get_table_name("video", "videos")
    if not t:
        return []
    try:
        rows = db.execute(
            f'SELECT id,title,thumbnail_url,views FROM "{t}" '
            f'WHERE thumbnail_url!="" AND status="published" ORDER BY views DESC LIMIT 300')
    except Exception:
        return []
    out = []
    for r in rows:
        if not r.get("thumbnail_url"):
            continue
        out.append({
            "source": "StreamHub", "kind": "video", "_key": str(r["id"]),
            "title": _trim(r.get("title")), "image": r["thumbnail_url"],
            "url": _safe_url("video.watch", "/sites/video/", video_id=r["id"]),
            "price": f"{_fmt_int(r.get('views'))} views", "meta": "Trending on StreamHub",
            "cta": "Watch now", "rating": 0, "reviews": 0,
        })
    return out


def _book_pool():
    t = db.get_table_name("books-comics", "books")
    if not t:
        return []
    try:
        rows = db.execute(
            f'SELECT id,title,author,cover_url,price,rating FROM "{t}" '
            f'WHERE cover_url!="" LIMIT 500')
    except Exception:
        return []
    out = []
    for r in rows:
        if not r.get("cover_url"):
            continue
        try:
            price = float(r.get("price") or 0)
        except (TypeError, ValueError):
            price = 0
        out.append({
            "source": "PageTurner", "kind": "book", "_key": str(r["id"]),
            "title": _trim(r.get("title")), "image": r["cover_url"],
            "url": _safe_url("books-comics.book_detail", "/sites/books-comics/", book_id=r["id"]),
            "price": "Free" if price <= 0 else f"${price:.2f}",
            "meta": ("by " + (r.get("author") or "").split(",")[0]) if r.get("author") else "eBook",
            "cta": "Read now", "rating": r.get("rating") or 0, "reviews": 0,
        })
    return out


_PROVIDERS = {
    "shop": _shop_pool,
    "auction": _auction_pool,
    "video": _video_pool,
    "book": _book_pool,
}
_DEFAULT_SOURCES = ("shop", "auction", "video", "book")


def product_ads(n=3, seed="", sources=None):
    """Return up to `n` mixed sponsored ads, balanced across sources.

    `sources` optionally restricts which providers to draw from (subset of
    'shop','auction','video','book'). Deterministic given the same seed.
    """
    names = [s for s in (sources or _DEFAULT_SOURCES) if s in _PROVIDERS]
    # Per-source seeded queues.
    queues = []
    for s in names:
        pool = _PROVIDERS[s]()
        if pool:
            queues.append(_seeded_order(pool, seed, lambda it: it["_key"]))
    if not queues:
        return []
    # Round-robin interleave so no single source dominates; order the sources
    # themselves by seed too, so the lead advertiser varies per page.
    queues = _seeded_order(queues, seed, lambda q: q[0]["_key"])
    out, i = [], 0
    while len(out) < int(n) and any(queues):
        q = queues[i % len(queues)]
        if q:
            ad = q.pop(0)
            ad = {k: v for k, v in ad.items() if k != "_key"}
            ad["accent"] = _ACCENT.get(ad["source"], "#1565c0")
            out.append(ad)
        i += 1
        # drop empty queues to avoid infinite loop
        if i % len(queues) == 0:
            queues = [q for q in queues if q]
            if not queues:
                break
    return out


# Alias
ads = product_ads
