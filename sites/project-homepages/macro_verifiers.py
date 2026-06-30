"""Per-macro verification functions for project-homepages.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/project-homepages"


def verify_macro_navigate_by_query(server_url):
    """Verify that ?section=<key> on the index page redirects to the correct page."""
    r = requests.get(f"{_base(server_url)}/?section=team", allow_redirects=False)
    redirect_ok = r.status_code in (301, 302)
    r2 = requests.get(f"{_base(server_url)}/?section=abstract", allow_redirects=False)
    redirect_ok2 = r2.status_code in (301, 302)
    return {"pass": redirect_ok and redirect_ok2,
            "detail": f"navigate_by_query: team redirect={redirect_ok}, abstract redirect={redirect_ok2}"}


def verify_macro_navigate_by_semantic(server_url):
    """Verify that semantic search returns navigable results."""
    r = requests.get(f"{_base(server_url)}/api/semantic?q=workflow+optimization")
    results = r.json()
    has_results = len(results) > 0
    has_url = all("url" in item for item in results) if results else False
    return {"pass": has_results and has_url,
            "detail": f"navigate_by_semantic: {len(results)} results, all have urls={has_url}"}


def verify_macro_navigate_by_dropdown(server_url):
    """Verify that the section dropdown targets work (section pages load)."""
    r = requests.get(f"{_base(server_url)}/api/sections")
    sections = r.json()
    if not sections:
        return {"pass": False, "detail": "No sections returned"}
    key = sections[0]["key"]
    r2 = requests.get(f"{_base(server_url)}/section/{key}")
    return {"pass": r2.status_code == 200,
            "detail": f"navigate_by_dropdown: section '{key}' page status={r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Verify that direct route navigation works."""
    pages = ["/", "/paper", "/team", "/resources", "/updates", "/stats"]
    results = {}
    for page in pages:
        r = requests.get(f"{_base(server_url)}{page}")
        results[page] = r.status_code
    all_ok = all(code == 200 for code in results.values())
    return {"pass": all_ok, "detail": f"navigate_by_route: {results}"}


def verify_macro_search_by_query(server_url):
    """Verify that keyword search returns results."""
    r = requests.get(f"{_base(server_url)}/api/search?q=FlowNet")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'FlowNet': {len(results)} results"}


def verify_macro_extract_by_semantic(server_url):
    """Verify that semantic search results contain extractable data."""
    r = requests.get(f"{_base(server_url)}/api/semantic?q=latency+reduction+results")
    results = r.json()
    if not results:
        return {"pass": False, "detail": "No semantic results"}
    first = results[0]
    has_fields = "title" in first and "type" in first and "score" in first
    return {"pass": has_fields,
            "detail": f"extract_by_semantic: top result '{first.get('title', '')[:40]}', score={first.get('score')}"}


def verify_macro_extract_by_dropdown(server_url):
    """Verify that resource stats can be extracted by type filter."""
    r = requests.get(f"{_base(server_url)}/api/resources/stats?type=slides")
    stats = r.json()
    has_count = "count" in stats
    has_size = "total_size_mb" in stats
    return {"pass": has_count and has_size and stats["count"] > 0,
            "detail": f"extract_by_dropdown: slides count={stats.get('count')}, size={stats.get('total_size_mb')}"}


def verify_macro_extract_from_table(server_url):
    """Verify that the stats page loads with table data."""
    r = requests.get(f"{_base(server_url)}/stats")
    page_ok = r.status_code == 200
    # Also verify the API provides the data
    r2 = requests.get(f"{_base(server_url)}/api/stats")
    stats = r2.json()
    has_metrics = "key_metrics" in stats and len(stats["key_metrics"]) > 0
    has_team = stats.get("team_count", 0) > 0
    return {"pass": page_ok and has_metrics and has_team,
            "detail": f"extract_from_table: page={page_ok}, metrics={has_metrics}, team={has_team}"}


def verify_macro_extract_by_route(server_url):
    """Verify that section content can be extracted via API route."""
    r = requests.get(f"{_base(server_url)}/api/sections/abstract")
    data = r.json()
    has_content = "content" in data and len(data["content"]) > 0
    has_key = data.get("key") == "abstract"
    return {"pass": has_content and has_key,
            "detail": f"extract_by_route: abstract content length={len(data.get('content', ''))}"}


def verify_macro_export_by_dropdown(server_url):
    """Verify that export works for all formats."""
    formats_ok = {}
    # BibTeX
    r = requests.get(f"{_base(server_url)}/api/export?format=bibtex")
    formats_ok["bibtex"] = r.status_code == 200 and "inproceedings" in r.text
    # APA
    r = requests.get(f"{_base(server_url)}/api/export?format=apa")
    formats_ok["apa"] = r.status_code == 200 and "Rivera" in r.text
    # JSON
    r = requests.get(f"{_base(server_url)}/api/export?format=json")
    data = r.json()
    formats_ok["json"] = "team" in data and "resources" in data
    # CSV
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    formats_ok["csv"] = len(lines) > 1
    all_ok = all(formats_ok.values())
    return {"pass": all_ok, "detail": f"export_by_dropdown: {formats_ok}"}
