"""Per-macro verification functions for business-company.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/business-company"


def verify_macro_navigate_by_semantic(server_url):
    """Navigate to about page (semantic nav link)."""
    r = requests.get(f"{_base(server_url)}/about")
    return {"pass": r.status_code == 200, "detail": f"About page: {r.status_code}"}


def verify_macro_navigate_by_dropdown(server_url):
    """Filter team by department dropdown."""
    r = requests.get(f"{_base(server_url)}/api/team?department=Engineering")
    members = r.json()
    return {"pass": len(members) > 0, "detail": f"Engineering filter: {len(members)} members"}


def verify_macro_navigate_by_route(server_url):
    """Navigate to a specific team member page by URL."""
    r = requests.get(f"{_base(server_url)}/team/1")
    return {"pass": r.status_code == 200, "detail": f"Team member page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Search products by keyword."""
    r = requests.get(f"{_base(server_url)}/api/products/search?q=platform")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_query 'platform': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic search for blog posts."""
    r = requests.get(f"{_base(server_url)}/api/posts/semantic?q=digital+transformation")
    results = r.json()
    return {"pass": r.status_code == 200, "detail": f"search_by_semantic: {len(results)} results"}


def verify_macro_extract_by_dropdown(server_url):
    """Extract filtered data using category dropdown."""
    r = requests.get(f"{_base(server_url)}/api/products?category=Cloud+Services")
    products = r.json()
    return {"pass": r.status_code == 200, "detail": f"extract_by_dropdown Cloud Services: {len(products)} products"}


def verify_macro_extract_from_table(server_url):
    """Compare items via compare API (table extraction)."""
    r = requests.get(f"{_base(server_url)}/api/compare?resource=products&ids=1,2")
    products = r.json()
    return {"pass": len(products) == 2, "detail": f"extract_from_table: compare returned {len(products)} products"}


def verify_macro_extract_by_route(server_url):
    """Extract detail from a specific route."""
    r = requests.get(f"{_base(server_url)}/api/products/1")
    product = r.json()
    return {"pass": "features" in product, "detail": f"extract_by_route: product has {len(product.get('features', []))} features"}


def verify_macro_submit_by_query(server_url):
    """Submit a contact form via API."""
    r = requests.post(f"{_base(server_url)}/api/contact", json={
        "name": "Macro Test",
        "email": "macro@test.com",
        "subject": "Test",
        "message": "Testing contact form submission."
    })
    data = r.json()
    ok = data.get("status") == "submitted"
    return {"pass": ok, "detail": f"submit_by_query: status={data.get('status')}"}


def verify_macro_export_by_dropdown(server_url):
    """Export data as CSV via export API."""
    r = requests.get(f"{_base(server_url)}/api/export?resource=products&format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1, "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_subscribe_by_toggle(server_url):
    """Toggle a newsletter subscription."""
    base = _base(server_url)
    r = requests.post(f"{base}/api/subscribe", json={
        "email": "macro_test_toggle@example.com",
        "topics": ["blog"]
    })
    data = r.json()
    ok = data.get("action") == "subscribed"
    # Toggle back (unsubscribe)
    requests.post(f"{base}/api/subscribe", json={
        "email": "macro_test_toggle@example.com"
    })
    return {"pass": ok, "detail": f"subscribe_by_toggle: action={data.get('action')}"}
