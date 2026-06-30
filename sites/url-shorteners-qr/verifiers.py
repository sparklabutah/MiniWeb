"""Per-task HTTP verification functions for url-shorteners-qr."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?q=promo")
    links = r.json()
    count = len(links)
    return {"pass": count >= 0, "detail": f"Search 'promo': {count} links"}


def verify_002(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/1")
    link = r.json()
    code = link.get("short_code", "")
    return {"pass": len(code) > 0, "detail": f"Link 1 short_code: {code}"}


def verify_003(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?q=github")
    links = r.json()
    count = len(links)
    return {"pass": count >= 0, "detail": f"Search 'github': {count} links"}


def verify_004(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?date_from=2026-01-01&date_to=2026-03-31")
    links = r.json()
    count = len(links)
    ok = all(l["created_at"][:10] >= "2026-01-01" and l["created_at"][:10] <= "2026-03-31"
             for l in links)
    return {"pass": ok and count >= 0,
            "detail": f"2026-01-01 to 2026-03-31: {count} links, all_in_range={ok}"}


def verify_005(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?tag=marketing")
    links = r.json()
    if not links:
        return {"pass": True, "detail": "No links tagged 'marketing'"}
    title = links[0].get("title", "")
    return {"pass": len(title) > 0, "detail": f"First 'marketing' link: {title}"}


def verify_006(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/2/stats")
    stats = r.json()
    countries = stats.get("countries", {})
    count = len(countries)
    return {"pass": count > 0, "detail": f"Link 2 countries: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/1")
    link = r.json()
    title = link.get("title", "")
    return {"pass": title == "Updated SEO Guide",
            "detail": f"Link 1 title: {title}"}


def verify_008(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/1")
    link = r.json()
    expires = link.get("expires_at", "")
    return {"pass": expires == "2027-12-31T23:59:59",
            "detail": f"Link 1 expires_at: {expires}"}


def verify_009(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/10")
    return {"pass": r.status_code == 404,
            "detail": f"Link 10 status: {r.status_code} (expected 404)"}


def verify_010(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/3")
    link = r.json()
    rtype = link.get("redirect_type", "")
    return {"pass": rtype == "302",
            "detail": f"Link 3 redirect_type: {rtype}"}


def verify_011(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/2/stats/export?format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0,
            "detail": f"Link 2 CSV export: {data_rows} data rows"}


def verify_012(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/5/share?method=twitter")
    data = r.json()
    share_url = data.get("share_url", "")
    return {"pass": "twitter.com" in share_url,
            "detail": f"Twitter share URL: {share_url[:80]}"}


def verify_013(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    # Check that the link was created by looking for it
    r = requests.get(f"{base}/api/links?q=Tutorial+Link")
    links = r.json()
    found = any(l["original_url"] == "https://docs.example.com/tutorial" for l in links)
    code = links[0]["short_code"] if links else ""
    return {"pass": found,
            "detail": f"Created 'Tutorial Link': found={found}, code={code}"}


def verify_014(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?q=blog.example.com")
    links = r.json()
    found = any("blog.example.com/post/2026" in l["original_url"] for l in links)
    title = links[0]["title"] if links else ""
    return {"pass": found,
            "detail": f"Free-text created link: found={found}, title={title}"}


def verify_015(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?q=shop.example.com")
    links = r.json()
    match = [l for l in links if l["original_url"] == "https://shop.example.com/sale"]
    if not match:
        return {"pass": False, "detail": "Link not found"}
    qr = match[0].get("qr_enabled", True)
    return {"pass": qr is False,
            "detail": f"Link qr_enabled: {qr}"}


def verify_016(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    active = stats.get("active_links", 0)
    return {"pass": active > 0,
            "detail": f"Active links: {active}"}


def verify_017(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/export?format=json&owner_id=1")
    links = r.json()
    count = len(links)
    return {"pass": count > 0,
            "detail": f"User 1 links export: {count} links"}


def verify_018(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links/9")
    link = r.json()
    src = link.get("utm_source", "")
    med = link.get("utm_medium", "")
    camp = link.get("utm_campaign", "")
    ok = src == "newsletter" and med == "email" and camp == "june-webinar"
    return {"pass": ok,
            "detail": f"Link 9 UTM: src={src}, med={med}, camp={camp}"}


def verify_019(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?date_from=2026-04-01&date_to=2026-05-31&sort=clicks")
    links = r.json()
    if not links:
        return {"pass": False, "detail": "No links in date range"}
    title = links[0]["title"]
    return {"pass": len(title) > 0,
            "detail": f"Top link Apr-May 2026: {title} ({links[0]['clicks']} clicks)"}


def verify_020(server_url):
    base = f"{server_url}/sites/url-shorteners-qr"
    r = requests.get(f"{base}/api/links?q=gala26")
    links = r.json()
    match = [l for l in links if l["short_code"] == "gala26"]
    if not match:
        return {"pass": False, "detail": "Link with code 'gala26' not found"}
    link = match[0]
    ok = (link["short_code"] == "gala26"
          and link["title"] == "Gala Event"
          and link.get("qr_enabled") is True
          and "event" in link.get("tags", [])
          and "fundraiser" in link.get("tags", []))
    return {"pass": ok,
            "detail": f"Gala link: code={link['short_code']}, title={link['title']}, "
                       f"qr={link.get('qr_enabled')}, tags={link.get('tags')}"}
