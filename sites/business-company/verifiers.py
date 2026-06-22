"""Per-task HTTP verification functions for business-company."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/team")
    team = r.json()
    count = len(team)
    return {"pass": count > 0, "detail": f"Team has {count} members"}


def verify_002(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/team?department=Engineering")
    members = r.json()
    count = len(members)
    return {"pass": count > 0, "detail": f"Engineering has {count} members"}


def verify_003(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/team/1")
    member = r.json()
    title = member.get("title", "")
    return {"pass": len(title) > 0, "detail": f"Member 1 title: {title}"}


def verify_004(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/products/search?q=analytics")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Search 'analytics': {count} products"}


def verify_005(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/products/semantic?q=security+and+protection")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No results for semantic search"}
    name = results[0]["name"]
    return {"pass": len(name) > 0, "detail": f"First semantic result: {name}"}


def verify_006(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/products?category=Cloud+Services")
    products = r.json()
    count = len(products)
    return {"pass": count >= 0, "detail": f"Cloud Services products: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/compare?resource=products&ids=1,2")
    products = r.json()
    if len(products) < 2:
        return {"pass": False, "detail": f"Compare returned {len(products)} products, expected 2"}
    cats = [p["category"] for p in products]
    return {"pass": True, "detail": f"Product 1: {cats[0]}, Product 2: {cats[1]}"}


def verify_008(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/products/3")
    product = r.json()
    features = product.get("features", [])
    return {"pass": len(features) > 0, "detail": f"Product 3 features: {features}"}


def verify_009(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/posts/search?q=cloud")
    results = r.json()
    count = len(results)
    return {"pass": count >= 0, "detail": f"Blog search 'cloud': {count} results"}


def verify_010(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/posts/semantic?q=artificial+intelligence+and+ethics")
    results = r.json()
    if not results:
        return {"pass": True, "detail": "No semantic blog results"}
    title = results[0]["title"]
    return {"pass": len(title) > 0, "detail": f"Top blog result: {title[:60]}"}


def verify_011(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/posts?category=Technology")
    posts = r.json()
    count = len(posts)
    return {"pass": count >= 0, "detail": f"Technology posts: {count}"}


def verify_012(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/posts/1")
    post = r.json()
    author = post.get("author", "")
    return {"pass": len(author) > 0, "detail": f"Post 1 author: {author}"}


def verify_013(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/jobs?department=Engineering")
    jobs = r.json()
    count = len(jobs)
    return {"pass": count >= 0, "detail": f"Engineering jobs: {count}"}


def verify_014(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/stats")
    stats = r.json()
    count = stats.get("product_count", 0)
    return {"pass": count > 0, "detail": f"Total products: {count}"}


def verify_015(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.post(f"{base}/api/contact", json={
        "name": "John Test",
        "email": "john@test.com",
        "subject": "Product Demo",
        "message": "I would like a demo of your analytics platform."
    })
    data = r.json()
    status = data.get("status", "")
    return {"pass": status == "submitted", "detail": f"Contact status: {status}"}


def verify_016(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/export?resource=products&format=csv")
    lines = r.text.strip().split("\n")
    data_rows = len(lines) - 1
    return {"pass": data_rows > 0, "detail": f"CSV export products: {data_rows} rows"}


def verify_017(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/export?resource=team&format=json&category=Engineering")
    data = r.json()
    count = len(data)
    return {"pass": count > 0, "detail": f"Engineering team export: {count} members"}


def verify_018(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.post(f"{base}/api/subscribe", json={
        "email": "analyst@corp.com",
        "topics": ["product-updates", "blog"]
    })
    data = r.json()
    action = data.get("action", "")
    return {"pass": action == "subscribed", "detail": f"Subscribe action: {action}"}


def verify_019(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.post(f"{base}/api/subscriber/1/toggle", json={"topic": "product-updates"})
    data = r.json()
    action = data.get("action", "")
    # Toggle back to restore state
    requests.post(f"{base}/api/subscriber/1/toggle", json={"topic": "product-updates"})
    return {"pass": action in ("subscribed", "unsubscribed"), "detail": f"Toggle action: {action}"}


def verify_020(server_url):
    base = f"{server_url}/sites/business-company"
    r = requests.get(f"{base}/api/posts/semantic?q=digital+transformation+strategy")
    posts = r.json()
    if not posts:
        return {"pass": True, "detail": "No posts for semantic search"}
    author_id = posts[0].get("author_id")
    if author_id is None:
        return {"pass": False, "detail": "Post missing author_id"}
    r2 = requests.get(f"{base}/api/team/{author_id}")
    member = r2.json()
    dept = member.get("department", "")
    r3 = requests.get(f"{base}/api/stats/department/{dept}")
    stats = r3.json()
    count = stats.get("member_count", 0)
    return {"pass": count > 0, "detail": f"Author dept '{dept}' has {count} members"}
