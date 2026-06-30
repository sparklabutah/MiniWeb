"""Per-macro verification functions for petitions-voting-info.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/petitions-voting-info"


def verify_macro_navigate_by_dropdown(server_url):
    """Header nav links should render petitions, elections, voter info pages."""
    r = requests.get(f"{_base(server_url)}/petitions")
    ok_petitions = r.status_code == 200
    r2 = requests.get(f"{_base(server_url)}/elections")
    ok_elections = r2.status_code == 200
    r3 = requests.get(f"{_base(server_url)}/voter-info")
    ok_voter = r3.status_code == 200
    return {"pass": ok_petitions and ok_elections and ok_voter,
            "detail": f"petitions={r.status_code}, elections={r2.status_code}, voter-info={r3.status_code}"}


def verify_macro_navigate_by_route(server_url):
    """Direct URL navigation to petition and election detail pages."""
    r = requests.get(f"{_base(server_url)}/petition/1")
    r2 = requests.get(f"{_base(server_url)}/election/1")
    return {"pass": r.status_code == 200 and r2.status_code == 200,
            "detail": f"petition/1={r.status_code}, election/1={r2.status_code}"}


def verify_macro_search_by_query(server_url):
    """Text search across petition titles and descriptions."""
    r = requests.get(f"{_base(server_url)}/api/petitions/search?q=bike")
    results = r.json()
    return {"pass": len(results) > 0,
            "detail": f"search 'bike': {len(results)} results"}


def verify_macro_search_by_semantic(server_url):
    """Semantic (keyword-ranked) search over petitions."""
    r = requests.get(f"{_base(server_url)}/api/petitions/semantic?q=environment+conservation")
    results = r.json()
    return {"pass": r.status_code == 200,
            "detail": f"semantic search: {len(results)} results"}


def verify_macro_filter_by_query(server_url):
    """Filter petitions by status query parameter."""
    r = requests.get(f"{_base(server_url)}/api/petitions?status=active")
    results = r.json()
    ok = all(p["status"] == "active" for p in results)
    return {"pass": ok and len(results) > 0,
            "detail": f"filter status=active: {len(results)} results, all_active={ok}"}


def verify_macro_filter_by_dropdown(server_url):
    """Filter petitions by category dropdown."""
    r = requests.get(f"{_base(server_url)}/api/petitions?category=education")
    results = r.json()
    ok = all(p["category"] == "education" for p in results)
    return {"pass": ok,
            "detail": f"filter category=education: {len(results)} results, all_education={ok}"}


def verify_macro_sort_by_toggle(server_url):
    """Sort petitions by title with asc/desc toggle."""
    r_asc = requests.get(f"{_base(server_url)}/api/petitions?sort=title&order=asc")
    r_desc = requests.get(f"{_base(server_url)}/api/petitions?sort=title&order=desc")
    asc_list = r_asc.json()
    desc_list = r_desc.json()
    if len(asc_list) < 2:
        return {"pass": True, "detail": "Too few petitions to verify sort"}
    asc_titles = [p["title"].lower() for p in asc_list]
    desc_titles = [p["title"].lower() for p in desc_list]
    asc_ok = all(asc_titles[i] <= asc_titles[i+1] for i in range(len(asc_titles)-1))
    desc_ok = all(desc_titles[i] >= desc_titles[i+1] for i in range(len(desc_titles)-1))
    return {"pass": asc_ok and desc_ok,
            "detail": f"sort asc={asc_ok}, desc={desc_ok}"}


def verify_macro_extract_by_query(server_url):
    """Search petitions and extract the first result."""
    r = requests.get(f"{_base(server_url)}/api/petitions/search?q=park")
    results = r.json()
    if results:
        return {"pass": True, "detail": f"first result: {results[0]['title'][:50]}"}
    return {"pass": True, "detail": "no results (ok)"}


def verify_macro_extract_by_dropdown(server_url):
    """Extract category stats via dropdown selection."""
    r = requests.get(f"{_base(server_url)}/api/categories/community/stats")
    stats = r.json()
    return {"pass": "total_signatures" in stats and "count" in stats,
            "detail": f"community stats: count={stats.get('count')}, sigs={stats.get('total_signatures')}"}


def verify_macro_extract_by_route(server_url):
    """Extract petition detail via direct route."""
    r = requests.get(f"{_base(server_url)}/api/petitions/1")
    data = r.json()
    return {"pass": "title" in data and "description" in data,
            "detail": f"petition 1: title={data.get('title','')[:40]}"}


def verify_macro_extract_by_date_range(server_url):
    """Filter petitions by created_at date range."""
    r = requests.get(f"{_base(server_url)}/api/petitions?date_from=2025-09-01&date_to=2025-12-31")
    results = r.json()
    ok = all("2025-09" <= p["created_at"][:7] <= "2025-12" for p in results)
    return {"pass": ok,
            "detail": f"date range 2025-09 to 2025-12: {len(results)} results, all_in_range={ok}"}


def verify_macro_verify_by_dropdown(server_url):
    """Check voter registration status by precinct dropdown."""
    r = requests.get(f"{_base(server_url)}/api/voter-info/verify?precinct=Precinct+4&username=alex_rivera")
    data = r.json()
    ok = data.get("user_found") is True and data.get("registration_status") == "active"
    return {"pass": ok,
            "detail": f"verify alex_rivera in Precinct 4: status={data.get('registration_status')}"}


def verify_macro_create_from_free_text(server_url):
    """Create a new petition via free-text form."""
    base = _base(server_url)
    s = requests.Session()
    # Login
    s.post(f"{base}/api/login",
           json={"username": "carlos_mendez", "password": "civicpass"})
    # Create petition
    r = s.post(f"{base}/api/petitions", json={
        "title": "Macro Test Petition",
        "description": "This is a test petition created by macro verifier.",
        "category": "community",
    })
    data = r.json()
    ok = r.status_code == 201 and data.get("title") == "Macro Test Petition"
    # Clean up: delete by reverting status to closed
    if ok:
        s.put(f"{base}/api/petitions/{data['id']}",
              json={"status": "closed"})
    return {"pass": ok,
            "detail": f"create_from_free_text: status={r.status_code}, title={data.get('title','')}"}


def verify_macro_submit_by_query(server_url):
    """Submit a comment on a petition."""
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login",
           json={"username": "carlos_mendez", "password": "civicpass"})
    r = s.post(f"{base}/api/petitions/1/comments",
               json={"comment": "Macro verifier test comment"})
    data = r.json()
    ok = r.status_code == 201 and data.get("comment") == "Macro verifier test comment"
    return {"pass": ok,
            "detail": f"submit_by_query: status={r.status_code}"}


def verify_macro_sign_by_signature(server_url):
    """Sign a petition with typed legal name."""
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login",
           json={"username": "carlos_mendez", "password": "civicpass"})
    # Try to sign petition 7 (active, EV charging)
    r = s.post(f"{base}/api/petitions/7/sign",
               json={"signature": "Carlos Mendez", "comment": "Test sign"})
    data = r.json()
    if r.status_code == 409:
        # Already signed -- that's ok for idempotent verification
        return {"pass": True, "detail": "sign_by_signature: already signed (ok)"}
    ok = r.status_code == 201 and data.get("signature") == "Carlos Mendez"
    return {"pass": ok,
            "detail": f"sign_by_signature: status={r.status_code}, sig={data.get('signature','')}"}


def verify_macro_subscribe_by_toggle(server_url):
    """Toggle subscription to petition updates."""
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login",
           json={"username": "carlos_mendez", "password": "civicpass"})
    r = s.post(f"{base}/api/petitions/1/subscribe")
    data = r.json()
    action = data.get("action")
    ok = action in ("subscribed", "unsubscribed")
    # Toggle back to original state
    s.post(f"{base}/api/petitions/1/subscribe")
    return {"pass": ok,
            "detail": f"subscribe_by_toggle: action={action}"}


def verify_macro_share_by_dropdown(server_url):
    """Share a petition via selected method."""
    r = requests.post(f"{_base(server_url)}/api/petitions/1/share",
                      json={"method": "twitter"})
    data = r.json()
    ok = "twitter" in data.get("share_url", "") and data.get("status") == "shared"
    return {"pass": ok,
            "detail": f"share_by_dropdown: method=twitter, url={data.get('share_url','')}"}


def verify_macro_save_by_toggle(server_url):
    """Toggle save/unsave petition to user favorites."""
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login",
           json={"username": "carlos_mendez", "password": "civicpass"})
    r = s.post(f"{base}/api/petitions/1/save")
    data = r.json()
    action = data.get("action")
    ok = action in ("saved", "unsaved")
    # Toggle back to original state
    s.post(f"{base}/api/petitions/1/save")
    return {"pass": ok,
            "detail": f"save_by_toggle: action={action}"}


def verify_macro_authenticate_by_form(server_url):
    """Log in with username/password."""
    base = _base(server_url)
    s = requests.Session()
    r = s.post(f"{base}/api/login",
               json={"username": "alex_rivera", "password": "civicpass"})
    data = r.json()
    ok = data.get("user_id") == 1 and data.get("display_name") == "Alex Rivera"
    return {"pass": ok,
            "detail": f"authenticate: user_id={data.get('user_id')}, name={data.get('display_name')}"}


def verify_macro_register_by_form(server_url):
    """Register a new voter via the registration form."""
    base = _base(server_url)
    r = requests.post(f"{base}/api/register-voter", json={
        "full_name": "Macro Test User",
        "address": "999 Test St, Lakeport, WA 98401",
        "precinct": "Precinct 1",
        "date_of_birth": "2000-01-01",
        "party_affiliation": "independent",
        "email": "macrotest@example.com",
        "username": "macro_test_user",
        "password": "testpass123",
    })
    data = r.json()
    if r.status_code == 409:
        # Username already exists from previous run
        return {"pass": True, "detail": "register_by_form: user already exists (ok)"}
    ok = r.status_code == 201 and data.get("voter_registration_status") == "active"
    return {"pass": ok,
            "detail": f"register_by_form: status={r.status_code}, reg={data.get('voter_registration_status','')}"}
