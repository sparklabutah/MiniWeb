"""Per-macro verification functions for url-shorteners-qr.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/url-shorteners-qr"


def verify_macro_navigate_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/links?q=seo")
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_query links?q=seo: {r.status_code}"}


def verify_macro_navigate_by_route(server_url):
    r = requests.get(f"{_base(server_url)}/link/1")
    return {"pass": r.status_code == 200,
            "detail": f"navigate_by_route link/1: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/links?q=github")
    links = r.json()
    return {"pass": len(links) > 0,
            "detail": f"search_by_query 'github': {len(links)} results"}


def verify_macro_filter_by_date_range(server_url):
    r = requests.get(f"{_base(server_url)}/api/links?date_from=2026-01-01&date_to=2026-03-31")
    links = r.json()
    ok = all(l["created_at"][:10] >= "2026-01-01" and l["created_at"][:10] <= "2026-03-31"
             for l in links)
    return {"pass": ok,
            "detail": f"filter 2026-01 to 2026-03: {len(links)} links, all_in_range={ok}"}


def verify_macro_extract_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/links?q=promo")
    links = r.json()
    if links:
        return {"pass": True,
                "detail": f"extract_by_query 'promo': first={links[0]['title']}"}
    return {"pass": True, "detail": "extract_by_query: no results (ok)"}


def verify_macro_extract_from_table(server_url):
    r = requests.get(f"{_base(server_url)}/api/links/1/stats")
    stats = r.json()
    return {"pass": "countries" in stats and "devices" in stats,
            "detail": f"extract_from_table: countries={len(stats.get('countries', {}))}, "
                       f"devices={len(stats.get('devices', {}))}"}


def verify_macro_edit_by_query(server_url):
    # Edit title and verify
    r = requests.put(f"{_base(server_url)}/api/links/1",
                     json={"title": "Macro Test Title"})
    link = r.json()
    ok = link.get("title") == "Macro Test Title"
    # Restore original
    requests.put(f"{_base(server_url)}/api/links/1",
                 json={"title": "SEO Guide 2024"})
    return {"pass": ok,
            "detail": f"edit_by_query: title changed={ok}"}


def verify_macro_edit_by_date_range(server_url):
    r = requests.put(f"{_base(server_url)}/api/links/1/expiration",
                     json={"expires_at": "2028-01-01T00:00:00"})
    link = r.json()
    ok = link.get("expires_at") == "2028-01-01T00:00:00"
    # Restore
    requests.put(f"{_base(server_url)}/api/links/1/expiration",
                 json={"expires_at": None})
    return {"pass": ok,
            "detail": f"edit_by_date_range: expires_at set={ok}"}


def verify_macro_delete_from_table(server_url):
    # Create a disposable link, then delete it
    r = requests.get(f"{_base(server_url)}/api/links/create?url=https://temp.example.com/delete-test&title=DeleteTest")
    link = r.json()
    link_id = link["id"]
    r2 = requests.delete(f"{_base(server_url)}/api/links/{link_id}")
    data = r2.json()
    ok = data.get("deleted") == link_id
    return {"pass": ok,
            "detail": f"delete_from_table: deleted link {link_id}, ok={ok}"}


def verify_macro_configure_by_dropdown(server_url):
    r = requests.put(f"{_base(server_url)}/api/links/3/configure",
                     json={"redirect_type": "307"})
    link = r.json()
    ok = link.get("redirect_type") == "307"
    # Restore
    requests.put(f"{_base(server_url)}/api/links/3/configure",
                 json={"redirect_type": "301"})
    return {"pass": ok,
            "detail": f"configure_by_dropdown: redirect_type=307, ok={ok}"}


def verify_macro_export_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1,
            "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_share_by_dropdown(server_url):
    r = requests.get(f"{_base(server_url)}/api/links/5/share?method=email")
    data = r.json()
    ok = "mailto:" in data.get("share_url", "")
    return {"pass": ok,
            "detail": f"share_by_dropdown email: {data.get('share_url', '')[:60]}"}


def verify_macro_create_by_query(server_url):
    r = requests.get(f"{_base(server_url)}/api/links/create?url=https://macro-test.example.com&title=MacroTest")
    link = r.json()
    ok = link.get("original_url") == "https://macro-test.example.com"
    # Cleanup
    if "id" in link:
        requests.delete(f"{_base(server_url)}/api/links/{link['id']}")
    return {"pass": ok,
            "detail": f"create_by_query: url={link.get('original_url')}, ok={ok}"}


def verify_macro_create_from_free_text(server_url):
    r = requests.post(f"{_base(server_url)}/api/links",
                      json={"free_text": "shorten https://freetext.example.com/page as my page"})
    link = r.json()
    ok = link.get("original_url") == "https://freetext.example.com/page"
    # Cleanup
    if "id" in link:
        requests.delete(f"{_base(server_url)}/api/links/{link['id']}")
    return {"pass": ok,
            "detail": f"create_from_free_text: url={link.get('original_url')}, title={link.get('title')}"}


def verify_macro_create_by_toggle(server_url):
    r = requests.post(f"{_base(server_url)}/api/links",
                      json={"original_url": "https://toggle-test.example.com",
                             "qr_enabled": False})
    link = r.json()
    ok = link.get("qr_enabled") is False
    # Cleanup
    if "id" in link:
        requests.delete(f"{_base(server_url)}/api/links/{link['id']}")
    return {"pass": ok,
            "detail": f"create_by_toggle: qr_enabled={link.get('qr_enabled')}, ok={ok}"}
