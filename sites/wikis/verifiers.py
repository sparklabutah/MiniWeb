"""Per-task HTTP verification functions for wikis (LakeportWiki)."""
import requests


def _base(server_url):
    return f"{server_url}/sites/wikis"


def verify_001(server_url):
    """Search for 'Meridian' -- count results."""
    r = requests.get(f"{_base(server_url)}/api/search?q=Meridian")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Search 'Meridian': {count} results"}


def verify_002(server_url):
    """Technology Companies category -- count pages."""
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    tech_cat = next((c for c in cats if c["name"] == "Technology Companies"), None)
    if not tech_cat:
        return {"pass": False, "detail": "Technology Companies category not found"}
    r2 = requests.get(f"{_base(server_url)}/api/categories/{tech_cat['id']}/pages")
    pages = r2.json()
    count = len(pages)
    return {"pass": count > 0, "detail": f"Technology Companies: {count} articles"}


def verify_003(server_url):
    """Lake Aldenmere article -- check max depth 186."""
    r = requests.get(f"{_base(server_url)}/api/pages/lake-aldenmere")
    page = r.json()
    has_186 = "186" in page.get("content", "")
    return {"pass": has_186, "detail": f"Lake Aldenmere content mentions 186: {has_186}"}


def verify_004(server_url):
    """Search 'salmon' -- first result title."""
    r = requests.get(f"{_base(server_url)}/api/search?q=salmon")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'salmon'"}
    first = results[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First 'salmon' result: {first}"}


def verify_005(server_url):
    """Julian Reeves article -- Meridian founded in 2009."""
    r = requests.get(f"{_base(server_url)}/api/pages/julian-reeves")
    page = r.json()
    has_2009 = "2009" in page.get("content", "")
    return {"pass": has_2009, "detail": f"Julian Reeves mentions 2009: {has_2009}"}


def verify_006(server_url):
    """Landmarks & Places category -- first article alphabetically."""
    r = requests.get(f"{_base(server_url)}/api/categories")
    cats = r.json()
    landmarks = next((c for c in cats if c["name"] == "Landmarks & Places"), None)
    if not landmarks:
        return {"pass": False, "detail": "Landmarks & Places not found"}
    r2 = requests.get(f"{_base(server_url)}/api/categories/{landmarks['id']}/pages")
    pages = r2.json()
    if not pages:
        return {"pass": False, "detail": "No pages in Landmarks & Places"}
    first = pages[0]["title"]
    return {"pass": len(first) > 0, "detail": f"First Landmarks article: {first}"}


def verify_007(server_url):
    """Semantic search 'environmental conservation wildlife' -- count."""
    r = requests.get(f"{_base(server_url)}/api/semantic-search?q=environmental+conservation+wildlife")
    results = r.json()
    count = len(results)
    return {"pass": count > 0, "detail": f"Semantic search conservation: {count} results"}


def verify_008(server_url):
    """Search 'university' -- category of first result."""
    r = requests.get(f"{_base(server_url)}/api/search?q=university")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No results for 'university'"}
    cat = results[0]["category"]
    return {"pass": len(cat) > 0, "detail": f"First 'university' result category: {cat}"}


def verify_009(server_url):
    """Compare Meridian Systems vs The Foundry -- Meridian has more views."""
    r = requests.get(f"{_base(server_url)}/api/compare?slugs=meridian-systems,the-foundry-lakeport")
    pages = r.json()
    if len(pages) < 2:
        return {"pass": False, "detail": f"Compare returned {len(pages)} pages"}
    p1, p2 = pages[0], pages[1]
    more = p1["title"] if p1["views"] > p2["views"] else p2["title"]
    return {"pass": more == "Meridian Systems",
            "detail": f"{p1['title']}: {p1['views']} vs {p2['title']}: {p2['views']}"}


def verify_010(server_url):
    """Compare Julian Reeves vs Priya Anand -- both Notable People."""
    r = requests.get(f"{_base(server_url)}/api/compare?slugs=julian-reeves,priya-anand")
    pages = r.json()
    if len(pages) < 2:
        return {"pass": False, "detail": f"Compare returned {len(pages)} pages"}
    cats = [p["category"] for p in pages]
    both_np = all(c == "Notable People" for c in cats)
    return {"pass": both_np, "detail": f"Categories: {cats}"}


def verify_011(server_url):
    """Verify claim 'population of 74,500' against Lakeport page -- should pass."""
    r = requests.post(f"{_base(server_url)}/api/verify",
                       json={"slug": "lakeport-washington", "claim": "population of 74,500"})
    data = r.json()
    return {"pass": data.get("verified") is True,
            "detail": f"Verified: {data.get('verified')}, ratio: {data.get('match_ratio')}"}


def verify_012(server_url):
    """Verify claim 'founded in 1995 by Steve Jobs' -- should fail."""
    r = requests.post(f"{_base(server_url)}/api/verify",
                       json={"slug": "meridian-systems", "claim": "founded in 1995 by Steve Jobs"})
    data = r.json()
    # "Steve Jobs" won't appear, "1995" won't appear -- low match ratio
    return {"pass": data.get("verified") is False or data.get("match_ratio", 1) < 0.5,
            "detail": f"Verified: {data.get('verified')}, ratio: {data.get('match_ratio')}"}


def verify_013(server_url):
    """Compare Lakeport vs Aldenmere County -- Lakeport created first."""
    r = requests.get(f"{_base(server_url)}/api/compare?slugs=lakeport-washington,aldenmere-county")
    pages = r.json()
    if len(pages) < 2:
        return {"pass": False, "detail": f"Compare returned {len(pages)} pages"}
    lakeport = next((p for p in pages if p["slug"] == "lakeport-washington"), None)
    aldenmere = next((p for p in pages if p["slug"] == "aldenmere-county"), None)
    if not lakeport or not aldenmere:
        return {"pass": False, "detail": "Could not find both pages"}
    first = "Lakeport, Washington" if lakeport["created_at"] < aldenmere["created_at"] else "Aldenmere County"
    return {"pass": first == "Lakeport, Washington",
            "detail": f"Lakeport: {lakeport['created_at']}, Aldenmere: {aldenmere['created_at']}"}


def verify_014(server_url):
    """Stats API -- most viewed is Lakeport, Washington."""
    r = requests.get(f"{_base(server_url)}/api/stats")
    stats = r.json()
    mv = stats.get("most_viewed", "")
    return {"pass": mv == "Lakeport, Washington",
            "detail": f"Most viewed: {mv}"}


def verify_015(server_url):
    """Created 'Lakeport Community Center' -- check it exists."""
    r = requests.get(f"{_base(server_url)}/api/pages/lakeport-community-center")
    if r.status_code == 404:
        return {"pass": False, "detail": "Page not found"}
    page = r.json()
    ok = page.get("title") == "Lakeport Community Center" and page.get("category") == "Lakeport City"
    return {"pass": ok,
            "detail": f"Title: {page.get('title')}, Category: {page.get('category')}"}


def verify_016(server_url):
    """Created 'Aldenmere Arts Council' -- check it exists."""
    r = requests.get(f"{_base(server_url)}/api/pages/aldenmere-arts-council")
    if r.status_code == 404:
        return {"pass": False, "detail": "Page not found"}
    page = r.json()
    ok = (page.get("title") == "Aldenmere Arts Council"
          and page.get("category") == "Culture & Events"
          and "visual and performing arts" in page.get("content", ""))
    return {"pass": ok,
            "detail": f"Title: {page.get('title')}, Category: {page.get('category')}"}


def verify_017(server_url):
    """Cedargrove Park category changed to 'Lakeport City'."""
    r = requests.get(f"{_base(server_url)}/api/pages/cedargrove-park")
    page = r.json()
    cat = page.get("category", "")
    return {"pass": cat == "Lakeport City",
            "detail": f"Cedargrove Park category: {cat}"}


def verify_018(server_url):
    """Lakeport Public Library category changed to 'Lakeport City'."""
    r = requests.get(f"{_base(server_url)}/api/pages/lakeport-public-library")
    page = r.json()
    cat = page.get("category", "")
    return {"pass": cat == "Lakeport City",
            "detail": f"Lakeport Public Library category: {cat}"}


def verify_019(server_url):
    """Semantic search for startup/innovation, compare top result with Meridian."""
    r = requests.get(f"{_base(server_url)}/api/semantic-search?q=startup+incubator+technology+innovation")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No semantic search results"}
    top_slug = results[0]["slug"]
    r2 = requests.get(f"{_base(server_url)}/api/compare?slugs={top_slug},meridian-systems")
    pages = r2.json()
    if len(pages) < 2:
        return {"pass": False, "detail": f"Compare returned {len(pages)} pages"}
    p1, p2 = pages[0], pages[1]
    more = p1["title"] if len(p1.get("linked_pages", [])) > len(p2.get("linked_pages", [])) else p2["title"]
    return {"pass": True,
            "detail": f"Top result: {results[0]['title']}, more links: {more}"}


def verify_020(server_url):
    """Created 'Thornberry Valley Wine Trail' and verified claim."""
    r = requests.get(f"{_base(server_url)}/api/pages/thornberry-valley-wine-trail")
    if r.status_code == 404:
        return {"pass": False, "detail": "Page not found"}
    page = r.json()
    if page.get("title") != "Thornberry Valley Wine Trail":
        return {"pass": False, "detail": f"Wrong title: {page.get('title')}"}
    # Verify the claim against the page
    r2 = requests.post(f"{_base(server_url)}/api/verify",
                        json={"slug": "thornberry-valley-wine-trail",
                              "claim": "attracts over 20,000 visitors"})
    data = r2.json()
    return {"pass": data.get("verified") is True,
            "detail": f"Page exists, claim verified: {data.get('verified')}"}
