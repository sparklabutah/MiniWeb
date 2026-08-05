"""Reusable in-network MiniWeb ads.

Ads shown across MiniWeb sites are real MiniWeb content, not external banners.
This module pulls real products (with images) from the ShopHub e-commerce site
and shapes them into sponsored image-ad cards that any site can render.

Usage from any template (product_ads is registered as a Jinja global):

    {% set ads = product_ads(3, seed=request.path) %}
    {% include "ads/_product_ads.html" %}

`seed` makes the selection deterministic per page (stable across reloads) while
letting different pages show different products.
"""
import hashlib
import importlib

from flask import url_for

_PLACEHOLDER = "transparent-pixel"
_IMG_EXT = (".jpg", ".jpeg", ".png", ".webp", ".gif")
_ecom = None


def _products():
    """Reuse the e-commerce site's own product loader (correct ids + parsing)."""
    global _ecom
    if _ecom is None:
        _ecom = importlib.import_module("sites.e-commerce.routes")
    return _ecom._get_products()


def _first_image(p):
    for url in (p.get("images") or []):
        u = (url or "")
        if u and _PLACEHOLDER not in u and u.lower().split("?")[0].endswith(_IMG_EXT):
            return u
    return None


def _clean_brand(brand):
    b = (brand or "").strip()
    for junk in ("Brand:", "Visit the", "Brand"):
        b = b.replace(junk, "")
    b = b.replace(" Store", "").strip(" :·-—")
    return b or "ShopHub"


def product_ads(n=3, seed="", categories=None):
    """Return up to `n` sponsored product-ad dicts.

    Each ad: {title, image, price, brand, category, rating, reviews, url}.
    `categories` optionally restricts to a set of top-level categories.
    Deterministic given the same (seed, catalog).
    """
    try:
        prods = _products()
    except Exception:
        return []

    cat_set = set(categories) if categories else None
    pool = []
    for p in prods:
        img = _first_image(p)
        if not img or not p.get("price"):
            continue
        if cat_set and p.get("top_category") not in cat_set:
            continue
        pool.append((p, img))
    if not pool:
        return []

    pool.sort(key=lambda it: hashlib.md5(
        (str(seed) + "|" + (it[0].get("asin") or "")).encode()).hexdigest())

    ads = []
    for p, img in pool[:max(0, int(n))]:
        try:
            link = url_for("e-commerce.product_detail", product_id=p["id"])
        except Exception:
            link = "/sites/e-commerce/"
        name = p.get("name") or ""
        ads.append({
            "title": name if len(name) <= 72 else name[:69] + "…",
            "image": img,
            "price": p.get("price"),
            "brand": _clean_brand(p.get("brand")),
            "category": p.get("top_category") or "",
            "rating": p.get("rating") or 0,
            "reviews": p.get("total_reviews") or 0,
            "url": link,
        })
    return ads
