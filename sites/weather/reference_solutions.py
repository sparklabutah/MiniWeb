"""Per-task reference solutions via Flask test client for the weather site."""
import json


def solve_001(client, base="/sites/weather"):
    r = client.get(f"{base}/api/search?q=portland")
    data = json.loads(r.data)
    results = data["results"]
    return results[0]["name"] if results else "No results"


def solve_002(client, base="/sites/weather"):
    r = client.get(f"{base}/api/current?location=Lakeport,+WA")
    data = json.loads(r.data)
    return str(data["temp_f"])


def solve_003(client, base="/sites/weather"):
    r = client.get(f"{base}/api/forecast")
    data = json.loads(r.data)
    for day in data["forecast"]:
        if day["day"] == "Tuesday":
            return str(day["high_f"])
    return "N/A"


def solve_004(client, base="/sites/weather"):
    r = client.get(f"{base}/api/history/date/2026-06-14")
    data = json.loads(r.data)
    return str(data["high_f"])


def solve_005(client, base="/sites/weather"):
    r = client.get(f"{base}/api/alerts")
    data = json.loads(r.data)
    return str(len(data["alerts"]))


def solve_006(client, base="/sites/weather"):
    r = client.get(f"{base}/api/locations/all")
    data = json.loads(r.data)
    return str(len(data["locations"]))


def solve_007(client, base="/sites/weather"):
    r = client.get(f"{base}/api/current/units?units=metric")
    data = json.loads(r.data)
    return str(data["wind_display"])


def solve_008(client, base="/sites/weather"):
    r = client.get(f"{base}/api/forecast/extended?extended=true")
    data = json.loads(r.data)
    return str(data["forecast"][0]["uv_index"])


def solve_009(client, base="/sites/weather"):
    r = client.get(f"{base}/api/historical?date_from=2026-06-01&date_to=2026-06-07")
    data = json.loads(r.data)
    return str(len(data["historical"]))


def solve_010(client, base="/sites/weather"):
    r = client.get(f"{base}/api/nearby?lat=47.5&lng=-122.3&radius=30")
    data = json.loads(r.data)
    return str(len(data["results"]))


def solve_011(client, base="/sites/weather"):
    r = client.get(f"{base}/api/compare?locations=Seattle,+WA,Portland,+OR")
    data = json.loads(r.data)
    comp = data["comparison"]
    temps = [c["temp_f"] for c in comp if "temp_f" in c]
    return str(abs(temps[0] - temps[1]))


def solve_012(client, base="/sites/weather"):
    r = client.get(f"{base}/api/verify_temp?temp_f=70")
    data = json.loads(r.data)
    return str(data["match"])


def solve_013(client, base="/sites/weather"):
    r = client.get(f"{base}/api/alerts/filter?severity=Severe")
    data = json.loads(r.data)
    return str(data["count"])


def solve_014(client, base="/sites/weather"):
    r = client.get(f"{base}/api/forecast?days=3")
    data = json.loads(r.data)
    return str(data["forecast"][2]["high_f"])


def solve_015(client, base="/sites/weather"):
    client.post(f"{base}/api/login",
                json={"username": "mchen", "password": "weather2026"})
    client.post(f"{base}/api/users/1/settings",
                json={"high_temp_threshold_f": 85})
    r = client.get(f"{base}/api/users/1")
    data = json.loads(r.data)
    return str(data["settings"]["high_temp_threshold_f"])


def solve_016(client, base="/sites/weather"):
    client.post(f"{base}/api/login",
                json={"username": "jnordgren", "password": "rainydays"})
    r = client.post(f"{base}/api/users/2/subscribe",
                    json={"alert_type": "Wind Advisory"})
    data = json.loads(r.data)
    return data.get("action", "")


def solve_017(client, base="/sites/weather"):
    client.post(f"{base}/api/login",
                json={"username": "apatel", "password": "sunshine99"})
    r = client.post(f"{base}/api/users/3/save_location",
                    json={"query": "Spokane"})
    data = json.loads(r.data)
    return data["location"]["name"]


def solve_018(client, base="/sites/weather"):
    r = client.get(f"{base}/api/historical?date_from=2026-06-18&date_to=2026-06-20")
    data = json.loads(r.data)
    total = round(sum(d["precip_in"] for d in data["historical"]), 2)
    return str(total)


def solve_019(client, base="/sites/weather"):
    client.post(f"{base}/api/login",
                json={"username": "treeves", "password": "pnwlife"})
    r = client.post(f"{base}/api/users/4/subscribe",
                    json={"subscribe_all": True})
    data = json.loads(r.data)
    return str(len(data["subscriptions"]))


def solve_020(client, base="/sites/weather"):
    r = client.get(f"{base}/api/compare?locations=Lakeport,+WA,Bellingham,+WA")
    data = json.loads(r.data)
    comp = data["comparison"]
    temps = [(c["name"], c["temp_f"]) for c in comp if "temp_f" in c]
    higher = max(temps, key=lambda x: x[1])
    diff = abs(temps[0][1] - temps[1][1])
    return f"{higher[0]}, {diff}F"
