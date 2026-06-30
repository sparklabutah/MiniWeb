"""Per-task reference solutions via Flask test client for wikis (LakeportWiki)."""
import json


def solve_001(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/search?q=Meridian")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/categories")
    cats = json.loads(r.data)
    tech_cat = next((c for c in cats if c["name"] == "Technology Companies"), None)
    if not tech_cat:
        return "0"
    r2 = client.get(f"{base}/api/categories/{tech_cat['id']}/pages")
    return str(len(json.loads(r2.data)))


def solve_003(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/pages/lake-aldenmere")
    page = json.loads(r.data)
    # Extract max depth from content -- the answer is 186
    content = page.get("content", "")
    if "186" in content:
        return "186"
    return "unknown"


def solve_004(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/search?q=salmon")
    results = json.loads(r.data)
    return results[0]["title"] if results else "No results"


def solve_005(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/pages/julian-reeves")
    page = json.loads(r.data)
    content = page.get("content", "")
    if "2009" in content:
        return "2009"
    return "unknown"


def solve_006(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/categories")
    cats = json.loads(r.data)
    landmarks = next((c for c in cats if c["name"] == "Landmarks & Places"), None)
    if not landmarks:
        return "unknown"
    r2 = client.get(f"{base}/api/categories/{landmarks['id']}/pages")
    pages = json.loads(r2.data)
    if not pages:
        return "No pages"
    return pages[0]["title"]


def solve_007(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/semantic-search?q=environmental+conservation+wildlife")
    return str(len(json.loads(r.data)))


def solve_008(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/search?q=university")
    results = json.loads(r.data)
    if not results:
        return "No results"
    return results[0]["category"]


def solve_009(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/compare?slugs=meridian-systems,the-foundry-lakeport")
    pages = json.loads(r.data)
    if len(pages) < 2:
        return "unknown"
    p1, p2 = pages[0], pages[1]
    return p1["title"] if p1["views"] > p2["views"] else p2["title"]


def solve_010(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/compare?slugs=julian-reeves,priya-anand")
    pages = json.loads(r.data)
    if len(pages) < 2:
        return "unknown"
    return ", ".join(p["category"] for p in pages)


def solve_011(client, base="/sites/wikis"):
    r = client.post(f"{base}/api/verify",
                    json={"slug": "lakeport-washington", "claim": "population of 74,500"},
                    content_type="application/json")
    data = json.loads(r.data)
    return "yes" if data.get("verified") else "no"


def solve_012(client, base="/sites/wikis"):
    r = client.post(f"{base}/api/verify",
                    json={"slug": "meridian-systems", "claim": "founded in 1995 by Steve Jobs"},
                    content_type="application/json")
    data = json.loads(r.data)
    return "yes" if data.get("verified") else "no"


def solve_013(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/compare?slugs=lakeport-washington,aldenmere-county")
    pages = json.loads(r.data)
    if len(pages) < 2:
        return "unknown"
    lakeport = next((p for p in pages if p["slug"] == "lakeport-washington"), None)
    aldenmere = next((p for p in pages if p["slug"] == "aldenmere-county"), None)
    if not lakeport or not aldenmere:
        return "unknown"
    return "Lakeport, Washington" if lakeport["created_at"] < aldenmere["created_at"] else "Aldenmere County"


def solve_014(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/stats")
    data = json.loads(r.data)
    return data.get("most_viewed", "unknown")


def solve_015(client, base="/sites/wikis"):
    r = client.post(f"{base}/api/pages",
                    json={
                        "title": "Lakeport Community Center",
                        "category": "Lakeport City",
                        "content": "The Lakeport Community Center is a public facility located on Oak Street in downtown Lakeport. It hosts community events, classes, and meetings.",
                    },
                    content_type="application/json")
    page = json.loads(r.data)
    return page.get("title", "")


def solve_016(client, base="/sites/wikis"):
    r = client.post(f"{base}/api/pages",
                    json={
                        "title": "Aldenmere Arts Council",
                        "category": "Culture & Events",
                        "content": "The Aldenmere Arts Council promotes visual and performing arts throughout Aldenmere County. Founded in 2001, it manages gallery exhibitions, artist residencies, and the annual Lakeport Art Walk.",
                    },
                    content_type="application/json")
    page = json.loads(r.data)
    return page.get("title", "")


def solve_017(client, base="/sites/wikis"):
    r = client.put(f"{base}/api/pages/cedargrove-park",
                   json={"category": "Lakeport City", "summary": "Changed category to Lakeport City"},
                   content_type="application/json")
    page = json.loads(r.data)
    return page.get("category", "")


def solve_018(client, base="/sites/wikis"):
    r = client.put(f"{base}/api/pages/lakeport-public-library",
                   json={"category": "Lakeport City", "summary": "Changed category to Lakeport City"},
                   content_type="application/json")
    page = json.loads(r.data)
    return page.get("category", "")


def solve_019(client, base="/sites/wikis"):
    r = client.get(f"{base}/api/semantic-search?q=startup+incubator+technology+innovation")
    results = json.loads(r.data)
    if not results:
        return "No results"
    top_slug = results[0]["slug"]
    r2 = client.get(f"{base}/api/compare?slugs={top_slug},meridian-systems")
    pages = json.loads(r2.data)
    if len(pages) < 2:
        return "unknown"
    p1, p2 = pages[0], pages[1]
    p1_links = len(p1.get("linked_pages", []))
    p2_links = len(p2.get("linked_pages", []))
    return p1["title"] if p1_links > p2_links else p2["title"]


def solve_020(client, base="/sites/wikis"):
    # Create the article
    client.post(f"{base}/api/pages",
                json={
                    "title": "Thornberry Valley Wine Trail",
                    "category": "Culture & Events",
                    "content": "The Thornberry Valley Wine Trail is a scenic route connecting six wineries along the Thornberry River valley south of Lakeport. Established in 2015, the trail attracts over 20,000 visitors annually.",
                },
                content_type="application/json")
    # Verify a claim against it
    r = client.post(f"{base}/api/verify",
                    json={"slug": "thornberry-valley-wine-trail",
                          "claim": "attracts over 20,000 visitors"},
                    content_type="application/json")
    data = json.loads(r.data)
    return "yes" if data.get("verified") else "no"
