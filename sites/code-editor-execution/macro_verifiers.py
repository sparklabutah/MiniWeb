"""Per-macro verification functions for code-editor-execution.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/code-editor-execution"


def verify_macro_navigate_from_table(server_url):
    """Verify navigating from snippet gallery table to a snippet detail."""
    r = requests.get(f"{_base(server_url)}/api/snippets")
    snippets = r.json()
    if not snippets:
        return {"pass": False, "detail": "No snippets returned"}
    first = snippets[0]
    r2 = requests.get(f"{_base(server_url)}/snippet/{first['id']}")
    return {"pass": r2.status_code == 200,
            "detail": f"Navigate to snippet {first['id']}: {r2.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Verify direct URL navigation to a snippet page."""
    r = requests.get(f"{_base(server_url)}/snippet/1")
    return {"pass": r.status_code == 200,
            "detail": f"Snippet detail page: {r.status_code}"}


def verify_macro_search_by_query(server_url):
    """Verify searching snippets by keyword."""
    r = requests.get(f"{_base(server_url)}/api/snippets?q=sort")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search_by_query 'sort': {len(results)} results"}


def verify_macro_extract_from_table(server_url):
    """Verify extracting data from snippet listing/detail."""
    r = requests.get(f"{_base(server_url)}/api/snippets/1")
    snippet = r.json()
    return {"pass": "expected_output" in snippet and "code" in snippet,
            "detail": f"extract_from_table: snippet has code={len(snippet.get('code',''))} chars, expected_output present"}


def verify_macro_create_by_code(server_url):
    """Verify executing code through the editor."""
    r = requests.post(f"{_base(server_url)}/api/execute",
                      json={"code": "print('macro_test')"})
    data = r.json()
    ok = data.get("stdout", "").strip() == "macro_test"
    return {"pass": ok, "detail": f"create_by_code: stdout={data.get('stdout', '').strip()!r}"}


def verify_macro_edit_by_form(server_url):
    """Verify editing a snippet's metadata via the edit API."""
    base = _base(server_url)
    # Get original
    r = requests.get(f"{base}/api/snippets/2")
    original_title = r.json().get("title", "")
    # Edit
    r2 = requests.post(f"{base}/api/snippets/2/edit",
                       json={"title": "Fibonacci Sequence (edited)"})
    edited = r2.json()
    ok = edited.get("title") == "Fibonacci Sequence (edited)"
    # Restore
    requests.post(f"{base}/api/snippets/2/edit",
                  json={"title": original_title})
    return {"pass": ok,
            "detail": f"edit_by_form: title changed to {edited.get('title')!r}"}


def verify_macro_configure_by_slider(server_url):
    """Verify editor settings configuration (font size, tab size)."""
    base = _base(server_url)
    r = requests.post(f"{base}/api/users/4/settings",
                      json={"font_size": 16, "tab_size": 4})
    data = r.json()
    settings = data.get("settings", {})
    ok = settings.get("font_size") == 16 and settings.get("tab_size") == 4
    return {"pass": ok,
            "detail": f"configure_by_slider: settings={settings}"}


def verify_macro_export_by_dropdown(server_url):
    """Verify exporting snippets as CSV."""
    r = requests.get(f"{_base(server_url)}/api/export?format=csv")
    lines = r.text.strip().split("\n")
    return {"pass": len(lines) > 1,
            "detail": f"export CSV: {len(lines)} lines"}


def verify_macro_upload_by_query(server_url):
    """Verify uploading a new snippet."""
    base = _base(server_url)
    r = requests.post(f"{base}/api/snippets/upload",
                      json={"title": "Macro Test Snippet",
                            "code": "print('test')",
                            "description": "Macro verification test"})
    data = r.json()
    ok = data.get("id") is not None and data.get("title") == "Macro Test Snippet"
    return {"pass": ok,
            "detail": f"upload_by_query: id={data.get('id')}, title={data.get('title')}"}


def verify_macro_share_by_route(server_url):
    """Verify generating a share link for a snippet."""
    r = requests.get(f"{_base(server_url)}/api/share/1")
    data = r.json()
    ok = len(data.get("share_token", "")) > 0 and len(data.get("share_url", "")) > 0
    return {"pass": ok,
            "detail": f"share_by_route: token={data.get('share_token')}, url={data.get('share_url')}"}
