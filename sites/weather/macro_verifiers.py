"""Per-macro verification functions for the weather site.

Each function tests that the corresponding macro works end-to-end.
"""
import requests


def _base(server_url):
    return f"{server_url}/sites/weather"


def verify_macro_navigate_by_query(server_url):
    """Verify navigation to a location's weather by query name."""
    r = requests.get(f"{_base(server_url)}/api/current?location=Seattle,+WA")
    data = r.json()
    ok = data.get("location") == "Seattle, WA" and "temp_f" in data
    return {"pass": ok,
            "detail": f"navigate_by_query Seattle: location={data.get('location')}, temp={data.get('temp_f')}"}


def verify_macro_navigate_by_date_range(server_url):
    """Verify navigation to historical weather for a specific date."""
    r = requests.get(f"{_base(server_url)}/api/history/date/2026-06-10")
    data = r.json()
    ok = data.get("date") == "2026-06-10" and "high_f" in data
    return {"pass": ok,
            "detail": f"navigate_by_date_range: date={data.get('date')}, high={data.get('high_f')}"}


def verify_macro_navigate_by_pan_zoom(server_url):
    """Verify location list endpoint for map/pan-zoom interaction."""
    r = requests.get(f"{_base(server_url)}/api/locations/all")
    data = r.json()
    locations = data.get("locations", [])
    ok = len(locations) > 0 and all("lat" in l and "lng" in l for l in locations)
    return {"pass": ok,
            "detail": f"navigate_by_pan_zoom: {len(locations)} locations with coordinates"}


def verify_macro_search_by_query(server_url):
    """Verify location search by text query."""
    r = requests.get(f"{_base(server_url)}/api/search?q=bell")
    data = r.json()
    results = data.get("results", [])
    ok = len(results) > 0 and any("Bellingham" in r["name"] for r in results)
    return {"pass": ok,
            "detail": f"search_by_query 'bell': {len(results)} results"}


def verify_macro_search_by_proximity(server_url):
    """Verify proximity-based location search."""
    r = requests.get(f"{_base(server_url)}/api/nearby?lat=47.5&lng=-122.3&radius=20")
    data = r.json()
    results = data.get("results", [])
    ok = len(results) > 0 and all("distance_mi" in r for r in results)
    # Verify sorted by distance
    if len(results) > 1:
        ok = ok and all(results[i]["distance_mi"] <= results[i+1]["distance_mi"]
                        for i in range(len(results)-1))
    return {"pass": ok,
            "detail": f"search_by_proximity: {len(results)} results, sorted by distance"}


def verify_macro_filter_by_toggle(server_url):
    """Verify toggling between unit systems and alert severity filters."""
    # Test unit toggle
    r1 = requests.get(f"{_base(server_url)}/api/current/units?units=imperial")
    r2 = requests.get(f"{_base(server_url)}/api/current/units?units=metric")
    d1 = r1.json()
    d2 = r2.json()
    units_ok = d1.get("wind_unit") == "mph" and d2.get("wind_unit") == "km/h"
    # Test severity filter
    r3 = requests.get(f"{_base(server_url)}/api/alerts/filter?severity=Moderate")
    d3 = r3.json()
    sev_ok = all(a["severity"].lower() == "moderate" for a in d3.get("alerts", []))
    return {"pass": units_ok and sev_ok,
            "detail": f"filter_by_toggle: units_ok={units_ok}, severity_filter_ok={sev_ok}"}


def verify_macro_extract_by_dropdown(server_url):
    """Verify extracting forecast for a configurable number of days."""
    r = requests.get(f"{_base(server_url)}/api/forecast?days=3")
    data = r.json()
    forecast = data.get("forecast", [])
    ok = len(forecast) == 3
    return {"pass": ok,
            "detail": f"extract_by_dropdown (3 days): got {len(forecast)} days"}


def verify_macro_extract_by_toggle(server_url):
    """Verify extended info toggle on forecast."""
    r_off = requests.get(f"{_base(server_url)}/api/forecast/extended?extended=false")
    r_on = requests.get(f"{_base(server_url)}/api/forecast/extended?extended=true")
    d_off = r_off.json()
    d_on = r_on.json()
    f_off = d_off.get("forecast", [{}])[0]
    f_on = d_on.get("forecast", [{}])[0]
    ok = "uv_index" not in f_off and "uv_index" in f_on
    return {"pass": ok,
            "detail": f"extract_by_toggle: extended_off has uv={'uv_index' in f_off}, extended_on has uv={'uv_index' in f_on}"}


def verify_macro_extract_from_table(server_url):
    """Verify extracting data from forecast and history tables."""
    r = requests.get(f"{_base(server_url)}/api/forecast")
    data = r.json()
    forecast = data.get("forecast", [])
    ok = len(forecast) > 0 and all("high_f" in d and "low_f" in d for d in forecast)
    return {"pass": ok,
            "detail": f"extract_from_table: {len(forecast)} forecast rows with temps"}


def verify_macro_extract_by_date_range(server_url):
    """Verify extracting historical data for a date range."""
    r = requests.get(f"{_base(server_url)}/api/historical?date_from=2026-06-05&date_to=2026-06-10")
    data = r.json()
    historical = data.get("historical", [])
    ok = len(historical) == 6 and all("2026-06-05" <= d["date"] <= "2026-06-10" for d in historical)
    return {"pass": ok,
            "detail": f"extract_by_date_range Jun 5-10: {len(historical)} days"}


def verify_macro_compare_by_query(server_url):
    """Verify comparing weather between two locations."""
    r = requests.get(f"{_base(server_url)}/api/compare?locations=Lakeport,+WA,Tacoma,+WA")
    data = r.json()
    comp = data.get("comparison", [])
    ok = len(comp) == 2 and all("temp_f" in c for c in comp)
    names = [c.get("name", "") for c in comp]
    return {"pass": ok,
            "detail": f"compare_by_query: {names[0]} vs {names[1] if len(names)>1 else '?'}"}


def verify_macro_verify_by_slider(server_url):
    """Verify temperature verification with slider input."""
    r = requests.get(f"{_base(server_url)}/api/verify_temp?temp_f=68&tolerance=5")
    data = r.json()
    ok = "match" in data and "actual_temp_f" in data and "difference_f" in data
    return {"pass": ok,
            "detail": f"verify_by_slider: actual={data.get('actual_temp_f')}, match={data.get('match')}"}


def verify_macro_configure_by_slider(server_url):
    """Verify configuring alert thresholds via slider."""
    base = _base(server_url)
    # Login as user 5
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "ktsukuda", "password": "forecast21"})
    # Set threshold
    r = s.post(f"{base}/api/users/5/settings",
               json={"high_temp_threshold_f": 80})
    data = r.json()
    ok = data.get("settings", {}).get("high_temp_threshold_f") == 80
    # Reset
    s.post(f"{base}/api/users/5/settings",
           json={"high_temp_threshold_f": 90})
    return {"pass": ok,
            "detail": f"configure_by_slider: set to 80, ok={ok}"}


def verify_macro_subscribe_by_toggle(server_url):
    """Verify subscribing/unsubscribing to alert types."""
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "ktsukuda", "password": "forecast21"})
    # Subscribe
    r = s.post(f"{base}/api/users/5/subscribe",
               json={"alert_type": "Flood Watch"})
    data = r.json()
    ok_sub = data.get("action") == "subscribed"
    # Unsubscribe (toggle back)
    r2 = s.post(f"{base}/api/users/5/subscribe",
                json={"alert_type": "Flood Watch"})
    data2 = r2.json()
    ok_unsub = data2.get("action") == "unsubscribed"
    return {"pass": ok_sub and ok_unsub,
            "detail": f"subscribe_by_toggle: sub={ok_sub}, unsub={ok_unsub}"}


def verify_macro_save_by_query(server_url):
    """Verify saving a location by searching for it by name."""
    base = _base(server_url)
    s = requests.Session()
    s.post(f"{base}/api/login", json={"username": "ktsukuda", "password": "forecast21"})
    # Save Tacoma (id=4) -- user 5 does not have it saved
    r = s.post(f"{base}/api/users/5/save_location",
               json={"query": "Tacoma"})
    data = r.json()
    ok = data.get("action") in ("saved", "already_saved")
    loc_name = data.get("location", {}).get("name", "")
    # Remove from saved list to reset
    s.delete(f"{base}/api/locations",
             json={"location_id": 4})
    return {"pass": ok,
            "detail": f"save_by_query 'Tacoma': action={data.get('action')}, name={loc_name}"}
