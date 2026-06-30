"""Per-task HTTP verification functions for the weather site."""
import requests


def verify_001(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/search?q=portland")
    data = r.json()
    results = data.get("results", [])
    if not results:
        return {"pass": False, "detail": "No results for 'portland'"}
    name = results[0]["name"]
    return {"pass": "Portland" in name, "detail": f"Search 'portland': {name}"}


def verify_002(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/current?location=Lakeport,+WA")
    data = r.json()
    temp = data.get("temp_f")
    return {"pass": temp is not None, "detail": f"Current temp: {temp}F"}


def verify_003(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/forecast")
    data = r.json()
    forecast = data.get("forecast", [])
    tuesday = [d for d in forecast if d["day"] == "Tuesday"]
    if not tuesday:
        return {"pass": False, "detail": "No Tuesday in forecast"}
    high = tuesday[0]["high_f"]
    return {"pass": high is not None, "detail": f"Tuesday high: {high}F"}


def verify_004(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/history/date/2026-06-14")
    data = r.json()
    high = data.get("high_f")
    return {"pass": high is not None, "detail": f"2026-06-14 high: {high}F"}


def verify_005(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/alerts")
    data = r.json()
    alerts = data.get("alerts", [])
    count = len(alerts)
    return {"pass": count > 0, "detail": f"Active alerts: {count}"}


def verify_006(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/locations/all")
    data = r.json()
    locations = data.get("locations", [])
    count = len(locations)
    return {"pass": count > 0, "detail": f"Total locations: {count}"}


def verify_007(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/current/units?units=metric")
    data = r.json()
    wind = data.get("wind_display")
    unit = data.get("wind_unit")
    return {"pass": unit == "km/h" and wind is not None,
            "detail": f"Metric wind: {wind} {unit}"}


def verify_008(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/forecast/extended?extended=true")
    data = r.json()
    forecast = data.get("forecast", [])
    if not forecast:
        return {"pass": False, "detail": "No forecast data"}
    uv = forecast[0].get("uv_index")
    return {"pass": uv is not None, "detail": f"Saturday UV index: {uv}"}


def verify_009(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/historical?date_from=2026-06-01&date_to=2026-06-07")
    data = r.json()
    historical = data.get("historical", [])
    count = len(historical)
    ok = all("2026-06-01" <= d["date"] <= "2026-06-07" for d in historical)
    return {"pass": ok and count == 7,
            "detail": f"Jun 1-7: {count} days, all_in_range={ok}"}


def verify_010(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/nearby?lat=47.5&lng=-122.3&radius=30")
    data = r.json()
    results = data.get("results", [])
    count = len(results)
    return {"pass": count > 0, "detail": f"Nearby (30mi): {count} locations"}


def verify_011(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/compare?locations=Seattle,+WA,Portland,+OR")
    data = r.json()
    comp = data.get("comparison", [])
    if len(comp) < 2:
        return {"pass": False, "detail": f"Compare returned {len(comp)} entries"}
    temps = [c.get("temp_f") for c in comp if "temp_f" in c]
    if len(temps) < 2:
        return {"pass": False, "detail": "Missing temp data in comparison"}
    diff = abs(temps[0] - temps[1])
    return {"pass": True, "detail": f"Seattle {temps[0]}F vs Portland {temps[1]}F, diff={diff}F"}


def verify_012(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/verify_temp?temp_f=70")
    data = r.json()
    match = data.get("match")
    actual = data.get("actual_temp_f")
    return {"pass": match is not None,
            "detail": f"Verify 70F vs actual {actual}F: match={match}"}


def verify_013(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/alerts/filter?severity=Severe")
    data = r.json()
    alerts = data.get("alerts", [])
    count = len(alerts)
    ok = all(a["severity"].lower() == "severe" for a in alerts)
    return {"pass": ok, "detail": f"Severe alerts: {count}, all_severe={ok}"}


def verify_014(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/forecast?days=3")
    data = r.json()
    forecast = data.get("forecast", [])
    if len(forecast) < 3:
        return {"pass": False, "detail": f"Only {len(forecast)} days returned"}
    high = forecast[2]["high_f"]
    return {"pass": len(forecast) == 3, "detail": f"3-day forecast, day 3 high: {high}F"}


def verify_015(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/users/1")
    data = r.json()
    settings = data.get("settings", {})
    threshold = settings.get("high_temp_threshold_f")
    return {"pass": threshold == 85,
            "detail": f"User 1 high_temp_threshold: {threshold}"}


def verify_016(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/users/2")
    data = r.json()
    subs = data.get("subscriptions", [])
    return {"pass": "Wind Advisory" in subs,
            "detail": f"User 2 subscriptions: {subs}"}


def verify_017(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/users/3")
    data = r.json()
    saved = data.get("saved_locations", [])
    return {"pass": 7 in saved,
            "detail": f"User 3 saved locations: {saved}"}


def verify_018(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/historical?date_from=2026-06-18&date_to=2026-06-20")
    data = r.json()
    historical = data.get("historical", [])
    if len(historical) != 3:
        return {"pass": False, "detail": f"Expected 3 days, got {len(historical)}"}
    total = round(sum(d["precip_in"] for d in historical), 2)
    return {"pass": total > 0, "detail": f"Jun 18-20 total precip: {total} in"}


def verify_019(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/users/4")
    data = r.json()
    subs = data.get("subscriptions", [])
    return {"pass": len(subs) == 3,
            "detail": f"User 4 subscriptions ({len(subs)}): {subs}"}


def verify_020(server_url):
    base = f"{server_url}/sites/weather"
    r = requests.get(f"{base}/api/compare?locations=Lakeport,+WA,Bellingham,+WA")
    data = r.json()
    comp = data.get("comparison", [])
    if len(comp) < 2:
        return {"pass": False, "detail": f"Compare returned {len(comp)} entries"}
    temps = [(c["name"], c["temp_f"]) for c in comp if "temp_f" in c]
    if len(temps) < 2:
        return {"pass": False, "detail": "Missing temp data"}
    higher = max(temps, key=lambda x: x[1])
    diff = abs(temps[0][1] - temps[1][1])
    return {"pass": True,
            "detail": f"{higher[0]} is higher at {higher[1]}F, diff={diff}F"}
