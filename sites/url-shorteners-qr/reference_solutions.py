"""Per-task reference solutions via Flask test client for url-shorteners-qr."""
import json


def solve_001(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links?q=promo")
    return str(len(json.loads(r.data)))


def solve_002(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links/1")
    return json.loads(r.data)["short_code"]


def solve_003(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links?q=github")
    return str(len(json.loads(r.data)))


def solve_004(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links?date_from=2026-01-01&date_to=2026-03-31")
    return str(len(json.loads(r.data)))


def solve_005(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links?tag=marketing")
    links = json.loads(r.data)
    return links[0]["title"] if links else "No results"


def solve_006(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links/2/stats")
    stats = json.loads(r.data)
    return str(len(stats.get("countries", {})))


def solve_007(client, base="/sites/url-shorteners-qr"):
    client.post(f"{base}/api/login",
                json={"username": "alice_marketer", "password": "pass123"})
    client.put(f"{base}/api/links/1",
               json={"title": "Updated SEO Guide"})
    r = client.get(f"{base}/api/links/1")
    return json.loads(r.data)["title"]


def solve_008(client, base="/sites/url-shorteners-qr"):
    client.post(f"{base}/api/login",
                json={"username": "alice_marketer", "password": "pass123"})
    client.put(f"{base}/api/links/1/expiration",
               json={"expires_at": "2027-12-31T23:59:59"})
    r = client.get(f"{base}/api/links/1")
    return json.loads(r.data).get("expires_at", "")


def solve_009(client, base="/sites/url-shorteners-qr"):
    client.post(f"{base}/api/login",
                json={"username": "alice_marketer", "password": "pass123"})
    r = client.delete(f"{base}/api/links/10")
    data = json.loads(r.data)
    return "deleted" if data.get("deleted") == 10 else "failed"


def solve_010(client, base="/sites/url-shorteners-qr"):
    client.post(f"{base}/api/login",
                json={"username": "bob_dev", "password": "pass456"})
    client.put(f"{base}/api/links/3/configure",
               json={"redirect_type": "302"})
    r = client.get(f"{base}/api/links/3")
    return json.loads(r.data).get("redirect_type", "")


def solve_011(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links/2/stats/export?format=csv")
    lines = r.data.decode().strip().split("\n")
    return str(len(lines) - 1)


def solve_012(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links/5/share?method=twitter")
    data = json.loads(r.data)
    return data.get("share_url", "")


def solve_013(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links/create?url=https://docs.example.com/tutorial&title=Tutorial+Link")
    link = json.loads(r.data)
    return link.get("short_code", "")


def solve_014(client, base="/sites/url-shorteners-qr"):
    r = client.post(f"{base}/api/links",
                    json={"free_text": "shorten https://blog.example.com/post/2026 for my blog post"})
    link = json.loads(r.data)
    return link.get("title", "")


def solve_015(client, base="/sites/url-shorteners-qr"):
    r = client.post(f"{base}/api/links",
                    json={"original_url": "https://shop.example.com/sale",
                           "qr_enabled": False})
    link = json.loads(r.data)
    return str(link.get("qr_enabled", True)).lower()


def solve_016(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/stats")
    stats = json.loads(r.data)
    return str(stats.get("active_links", 0))


def solve_017(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/export?format=json&owner_id=1")
    return str(len(json.loads(r.data)))


def solve_018(client, base="/sites/url-shorteners-qr"):
    client.post(f"{base}/api/login",
                json={"username": "dave_agency", "password": "pass321"})
    client.put(f"{base}/api/links/9/configure",
               json={"utm_source": "newsletter", "utm_medium": "email",
                      "utm_campaign": "june-webinar"})
    r = client.get(f"{base}/api/links/9")
    link = json.loads(r.data)
    return f"{link['utm_source']},{link['utm_medium']},{link['utm_campaign']}"


def solve_019(client, base="/sites/url-shorteners-qr"):
    r = client.get(f"{base}/api/links?date_from=2026-04-01&date_to=2026-05-31&sort=clicks")
    links = json.loads(r.data)
    return links[0]["title"] if links else "No results"


def solve_020(client, base="/sites/url-shorteners-qr"):
    client.post(f"{base}/api/login",
                json={"username": "carol_social", "password": "pass789"})
    r = client.post(f"{base}/api/links",
                    json={"original_url": "https://event.example.com/gala",
                           "title": "Gala Event",
                           "short_code": "gala26",
                           "qr_enabled": True,
                           "tags": ["event", "fundraiser"]})
    link = json.loads(r.data)
    return link.get("short_code", "")
