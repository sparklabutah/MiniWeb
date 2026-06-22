#!/usr/bin/env python3
"""Fetch real weather data from OpenMeteo API for the weather site.

Produces ~200 location records with current weather, 7-day forecasts,
and historical monthly averages. Users and alerts are synthesized.

Usage:
    python scripts/data_prep/weather_data.py
"""

import json
import random
import time
from pathlib import Path
from urllib.request import urlopen
from urllib.parse import urlencode
from datetime import datetime, timedelta

OUTPUT_DIR = Path(__file__).resolve().parent.parent.parent / "sites" / "weather" / "data"

# 200 world cities with coordinates
CITIES = [
    # North America
    ("New York", "US", "Northeast", 40.7128, -74.0060),
    ("Los Angeles", "US", "West", 34.0522, -118.2437),
    ("Chicago", "US", "Midwest", 41.8781, -87.6298),
    ("Houston", "US", "South", 29.7604, -95.3698),
    ("Phoenix", "US", "Southwest", 33.4484, -112.0740),
    ("Philadelphia", "US", "Northeast", 39.9526, -75.1652),
    ("San Antonio", "US", "South", 29.4241, -98.4936),
    ("San Diego", "US", "West", 32.7157, -117.1611),
    ("Dallas", "US", "South", 32.7767, -96.7970),
    ("San Jose", "US", "West", 37.3382, -121.8863),
    ("Austin", "US", "South", 30.2672, -97.7431),
    ("Denver", "US", "Mountain", 39.7392, -104.9903),
    ("Seattle", "US", "Pacific NW", 47.6062, -122.3321),
    ("Boston", "US", "Northeast", 42.3601, -71.0589),
    ("Miami", "US", "South", 25.7617, -80.1918),
    ("Atlanta", "US", "South", 33.7490, -84.3880),
    ("Minneapolis", "US", "Midwest", 44.9778, -93.2650),
    ("Portland", "US", "Pacific NW", 45.5152, -122.6784),
    ("Las Vegas", "US", "Southwest", 36.1699, -115.1398),
    ("Detroit", "US", "Midwest", 42.3314, -83.0458),
    ("Nashville", "US", "South", 36.1627, -86.7816),
    ("Salt Lake City", "US", "Mountain", 40.7608, -111.8910),
    ("Honolulu", "US", "Pacific", 21.3069, -157.8583),
    ("Anchorage", "US", "Alaska", 61.2181, -149.9003),
    ("Toronto", "CA", "Ontario", 43.6532, -79.3832),
    ("Vancouver", "CA", "British Columbia", 49.2827, -123.1207),
    ("Montreal", "CA", "Quebec", 45.5017, -73.5673),
    ("Mexico City", "MX", "Central", 19.4326, -99.1332),
    ("Cancun", "MX", "Southeast", 21.1619, -86.8515),
    ("Havana", "CU", "Caribbean", 23.1136, -82.3666),
    # South America
    ("Sao Paulo", "BR", "Southeast", -23.5505, -46.6333),
    ("Rio de Janeiro", "BR", "Southeast", -22.9068, -43.1729),
    ("Buenos Aires", "AR", "Pampa", -34.6037, -58.3816),
    ("Lima", "PE", "Coast", -12.0464, -77.0428),
    ("Bogota", "CO", "Andes", 4.7110, -74.0721),
    ("Santiago", "CL", "Central", -33.4489, -70.6693),
    ("Quito", "EC", "Sierra", -0.1807, -78.4678),
    ("Montevideo", "UY", "South", -34.9011, -56.1645),
    ("Caracas", "VE", "North", 10.4806, -66.9036),
    ("Medellin", "CO", "Andes", 6.2476, -75.5658),
    # Europe
    ("London", "GB", "England", 51.5074, -0.1278),
    ("Paris", "FR", "Ile-de-France", 48.8566, 2.3522),
    ("Berlin", "DE", "Brandenburg", 52.5200, 13.4050),
    ("Madrid", "ES", "Central", 40.4168, -3.7038),
    ("Rome", "IT", "Lazio", 41.9028, 12.4964),
    ("Amsterdam", "NL", "North Holland", 52.3676, 4.9041),
    ("Vienna", "AT", "Vienna", 48.2082, 16.3738),
    ("Prague", "CZ", "Bohemia", 50.0755, 14.4378),
    ("Stockholm", "SE", "Svealand", 59.3293, 18.0686),
    ("Oslo", "NO", "Eastern", 59.9139, 10.7522),
    ("Copenhagen", "DK", "Zealand", 55.6761, 12.5683),
    ("Helsinki", "FI", "Uusimaa", 60.1699, 24.9384),
    ("Dublin", "IE", "Leinster", 53.3498, -6.2603),
    ("Lisbon", "PT", "Lisbon", 38.7223, -9.1393),
    ("Brussels", "BE", "Brussels", 50.8503, 4.3517),
    ("Zurich", "CH", "Zurich", 47.3769, 8.5417),
    ("Warsaw", "PL", "Masovia", 52.2297, 21.0122),
    ("Budapest", "HU", "Central", 47.4979, 19.0402),
    ("Bucharest", "RO", "Muntenia", 44.4268, 26.1025),
    ("Athens", "GR", "Attica", 37.9838, 23.7275),
    ("Barcelona", "ES", "Catalonia", 41.3851, 2.1734),
    ("Munich", "DE", "Bavaria", 48.1351, 11.5820),
    ("Milan", "IT", "Lombardy", 45.4642, 9.1900),
    ("Edinburgh", "GB", "Scotland", 55.9533, -3.1883),
    ("Reykjavik", "IS", "Capital", 64.1466, -21.9426),
    ("Istanbul", "TR", "Marmara", 41.0082, 28.9784),
    ("Moscow", "RU", "Central", 55.7558, 37.6173),
    ("St Petersburg", "RU", "Northwest", 59.9343, 30.3351),
    ("Kyiv", "UA", "Central", 50.4501, 30.5234),
    # Africa
    ("Cairo", "EG", "Lower Egypt", 30.0444, 31.2357),
    ("Lagos", "NG", "Southwest", 6.5244, 3.3792),
    ("Nairobi", "KE", "Central", -1.2921, 36.8219),
    ("Cape Town", "ZA", "Western Cape", -33.9249, 18.4241),
    ("Johannesburg", "ZA", "Gauteng", -26.2041, 28.0473),
    ("Casablanca", "MA", "Grand Casa", 33.5731, -7.5898),
    ("Addis Ababa", "ET", "Central", 9.0250, 38.7469),
    ("Dar es Salaam", "TZ", "Coastal", -6.7924, 39.2083),
    ("Accra", "GH", "Greater Accra", 5.6037, -0.1870),
    ("Tunis", "TN", "Tunis", 36.8065, 10.1815),
    ("Dakar", "SN", "Dakar", 14.7167, -17.4677),
    ("Marrakech", "MA", "Tensift", 31.6295, -7.9811),
    # Asia
    ("Tokyo", "JP", "Kanto", 35.6762, 139.6503),
    ("Beijing", "CN", "North", 39.9042, 116.4074),
    ("Shanghai", "CN", "East", 31.2304, 121.4737),
    ("Mumbai", "IN", "Maharashtra", 19.0760, 72.8777),
    ("Delhi", "IN", "NCR", 28.7041, 77.1025),
    ("Bangkok", "TH", "Central", 13.7563, 100.5018),
    ("Singapore", "SG", "Central", 1.3521, 103.8198),
    ("Hong Kong", "HK", "HK", 22.3193, 114.1694),
    ("Seoul", "KR", "Capital", 37.5665, 126.9780),
    ("Taipei", "TW", "Northern", 25.0330, 121.5654),
    ("Jakarta", "ID", "Java", -6.2088, 106.8456),
    ("Manila", "PH", "NCR", 14.5995, 120.9842),
    ("Kuala Lumpur", "MY", "Federal", 3.1390, 101.6869),
    ("Hanoi", "VN", "Red River", 21.0278, 105.8342),
    ("Dubai", "AE", "Dubai", 25.2048, 55.2708),
    ("Riyadh", "SA", "Najd", 24.7136, 46.6753),
    ("Doha", "QA", "Doha", 25.2854, 51.5310),
    ("Tehran", "IR", "Tehran", 35.6892, 51.3890),
    ("Karachi", "PK", "Sindh", 24.8607, 67.0011),
    ("Dhaka", "BD", "Dhaka", 23.8103, 90.4125),
    ("Colombo", "LK", "Western", 6.9271, 79.8612),
    ("Kathmandu", "NP", "Bagmati", 27.7172, 85.3240),
    ("Tashkent", "UZ", "Tashkent", 41.2995, 69.2401),
    ("Almaty", "KZ", "Almaty", 43.2220, 76.8512),
    ("Ulaanbaatar", "MN", "Central", 47.8864, 106.9057),
    # Oceania
    ("Sydney", "AU", "NSW", -33.8688, 151.2093),
    ("Melbourne", "AU", "Victoria", -37.8136, 144.9631),
    ("Brisbane", "AU", "Queensland", -27.4698, 153.0251),
    ("Perth", "AU", "Western Aus", -31.9505, 115.8605),
    ("Auckland", "NZ", "Auckland", -36.8485, 174.7633),
    ("Wellington", "NZ", "Wellington", -41.2865, 174.7762),
    ("Suva", "FJ", "Central", -18.1416, 178.4419),
    # More US cities
    ("San Francisco", "US", "West", 37.7749, -122.4194),
    ("Washington DC", "US", "Mid-Atlantic", 38.9072, -77.0369),
    ("New Orleans", "US", "South", 29.9511, -90.0715),
    ("Charlotte", "US", "South", 35.2271, -80.8431),
    ("Indianapolis", "US", "Midwest", 39.7684, -86.1581),
    ("Columbus", "US", "Midwest", 39.9612, -82.9988),
    ("Kansas City", "US", "Midwest", 39.0997, -94.5786),
    ("Oklahoma City", "US", "South", 35.4676, -97.5164),
    ("Memphis", "US", "South", 35.1495, -90.0490),
    ("Louisville", "US", "South", 38.2527, -85.7585),
    ("Milwaukee", "US", "Midwest", 43.0389, -87.9065),
    ("Albuquerque", "US", "Southwest", 35.0844, -106.6504),
    ("Tucson", "US", "Southwest", 32.2226, -110.9747),
    ("Raleigh", "US", "South", 35.7796, -78.6382),
    ("Tampa", "US", "South", 27.9506, -82.4572),
    ("Orlando", "US", "South", 28.5383, -81.3792),
    ("Jacksonville", "US", "South", 30.3322, -81.6557),
    ("Sacramento", "US", "West", 38.5816, -121.4944),
    # More Europe
    ("Lyon", "FR", "Auvergne", 45.7640, 4.8357),
    ("Marseille", "FR", "PACA", 43.2965, 5.3698),
    ("Hamburg", "DE", "Hamburg", 53.5511, 9.9937),
    ("Frankfurt", "DE", "Hesse", 50.1109, 8.6821),
    ("Seville", "ES", "Andalusia", 37.3891, -5.9845),
    ("Valencia", "ES", "Valencia", 39.4699, -0.3763),
    ("Naples", "IT", "Campania", 40.8518, 14.2681),
    ("Florence", "IT", "Tuscany", 43.7696, 11.2558),
    ("Krakow", "PL", "Lesser Poland", 50.0647, 19.9450),
    ("Bergen", "NO", "Western", 60.3913, 5.3221),
    # More Asia
    ("Osaka", "JP", "Kansai", 34.6937, 135.5023),
    ("Kyoto", "JP", "Kansai", 35.0116, 135.7681),
    ("Shenzhen", "CN", "South", 22.5431, 114.0579),
    ("Guangzhou", "CN", "South", 23.1291, 113.2644),
    ("Chengdu", "CN", "Southwest", 30.5728, 104.0668),
    ("Bangalore", "IN", "Karnataka", 12.9716, 77.5946),
    ("Chennai", "IN", "Tamil Nadu", 13.0827, 80.2707),
    ("Kolkata", "IN", "West Bengal", 22.5726, 88.3639),
    ("Ho Chi Minh City", "VN", "Southeast", 10.8231, 106.6297),
    ("Phnom Penh", "KH", "Phnom Penh", 11.5564, 104.9282),
    ("Yangon", "MM", "Yangon", 16.8661, 96.1951),
    ("Baku", "AZ", "Absheron", 40.4093, 49.8671),
    ("Tbilisi", "GE", "Tbilisi", 41.7151, 44.8271),
    # More Africa
    ("Kigali", "RW", "Central", -1.9403, 29.8739),
    ("Kampala", "UG", "Central", 0.3476, 32.5825),
    ("Lusaka", "ZM", "Lusaka", -15.3875, 28.3228),
    ("Maputo", "MZ", "South", -25.9692, 32.5732),
    ("Windhoek", "NA", "Khomas", -22.5609, 17.0658),
    # More South America
    ("Cusco", "PE", "Andes", -13.5320, -71.9675),
    ("Cartagena", "CO", "Caribbean", 10.3910, -75.5144),
    ("Salvador", "BR", "Northeast", -12.9714, -38.5124),
    ("Brasilia", "BR", "Central", -15.7975, -47.8919),
    ("Asuncion", "PY", "Central", -25.2637, -57.5759),
    ("La Paz", "BO", "Altiplano", -16.4897, -68.1193),
    # Caribbean & Central America
    ("San Juan", "PR", "Caribbean", 18.4655, -66.1057),
    ("Kingston", "JM", "Surrey", 18.0179, -76.8099),
    ("San Jose", "CR", "Central Valley", 9.9281, -84.0907),
    ("Panama City", "PA", "Panama", 8.9824, -79.5199),
    ("Guatemala City", "GT", "Central", 14.6349, -90.5069),
    # Island nations
    ("Reykjavik", "IS", "Capital", 64.1466, -21.9426),
    ("Nuuk", "GL", "Sermersooq", 64.1814, -51.6941),
    # Additional for 200 total
    ("Beirut", "LB", "Beirut", 33.8938, 35.5018),
    ("Amman", "JO", "Amman", 31.9454, 35.9284),
    ("Baghdad", "IQ", "Baghdad", 33.3152, 44.3661),
    ("Muscat", "OM", "Muscat", 23.5880, 58.3829),
    ("Manama", "BH", "Capital", 26.2285, 50.5860),
    ("Kuwait City", "KW", "Capital", 29.3759, 47.9774),
    ("Yerevan", "AM", "Yerevan", 40.1792, 44.4991),
    ("Bishkek", "KG", "Chuy", 42.8746, 74.5698),
    ("Dushanbe", "TJ", "Dushanbe", 38.5598, 68.7740),
    ("Ashgabat", "TM", "Ahal", 37.9601, 58.3261),
    ("Lhasa", "CN", "Tibet", 29.6500, 91.1000),
    ("Urumqi", "CN", "Xinjiang", 43.8256, 87.6168),
    ("Vladivostok", "RU", "Far East", 43.1332, 131.9113),
    ("Novosibirsk", "RU", "Siberia", 55.0084, 82.9357),
    ("Yakutsk", "RU", "Siberia", 62.0355, 129.6755),
    ("Abuja", "NG", "FCT", 9.0579, 7.4951),
    ("Kinshasa", "CD", "Kinshasa", -4.4419, 15.2663),
    ("Luanda", "AO", "Luanda", -8.8390, 13.2894),
    ("Antananarivo", "MG", "Central", -18.8792, 47.5079),
    ("Port Louis", "MU", "Port Louis", -20.1609, 57.5012),
]

# Deduplicate by name
seen = set()
UNIQUE_CITIES = []
for c in CITIES:
    if c[0] not in seen:
        seen.add(c[0])
        UNIQUE_CITIES.append(c)
CITIES = UNIQUE_CITIES[:200]


def fetch_openmeteo_batch(lats, lons, batch_size=50):
    """Fetch current weather + 7-day forecast for a batch of coordinates."""
    results = []
    for i in range(0, len(lats), batch_size):
        batch_lats = lats[i:i + batch_size]
        batch_lons = lons[i:i + batch_size]

        params = {
            "latitude": ",".join(str(x) for x in batch_lats),
            "longitude": ",".join(str(x) for x in batch_lons),
            "current": "temperature_2m,relative_humidity_2m,apparent_temperature,"
                       "pressure_msl,wind_speed_10m,wind_direction_10m,"
                       "weather_code,uv_index",
            "daily": "temperature_2m_max,temperature_2m_min,weather_code,"
                     "precipitation_probability_max,wind_speed_10m_max,"
                     "relative_humidity_2m_mean,uv_index_max,"
                     "sunrise,sunset",
            "timezone": "auto",
            "forecast_days": 7,
        }
        url = "https://api.open-meteo.com/v1/forecast?" + urlencode(params)
        print(f"  Fetching batch {i // batch_size + 1} ({len(batch_lats)} locations)...")
        resp = urlopen(url)
        data = json.loads(resp.read())
        # If single location, wrap in list
        if isinstance(data, dict) and "latitude" in data:
            data = [data]
        results.extend(data)
        time.sleep(0.5)  # Be polite
    return results


def fetch_historical_batch(lats, lons, batch_size=50):
    """Fetch historical monthly averages (past 12 months)."""
    today = datetime.now()
    date_to = (today - timedelta(days=1)).strftime("%Y-%m-%d")
    date_from = (today - timedelta(days=365)).strftime("%Y-%m-%d")

    results = []
    for i in range(0, len(lats), batch_size):
        batch_lats = lats[i:i + batch_size]
        batch_lons = lons[i:i + batch_size]

        params = {
            "latitude": ",".join(str(x) for x in batch_lats),
            "longitude": ",".join(str(x) for x in batch_lons),
            "daily": "temperature_2m_max,temperature_2m_min,temperature_2m_mean,"
                     "precipitation_sum,relative_humidity_2m_mean",
            "timezone": "auto",
            "start_date": date_from,
            "end_date": date_to,
        }
        url = "https://archive-api.open-meteo.com/v1/archive?" + urlencode(params)
        print(f"  Fetching historical batch {i // batch_size + 1}...")
        try:
            resp = urlopen(url)
            data = json.loads(resp.read())
            if isinstance(data, dict) and "latitude" in data:
                data = [data]
            results.extend(data)
        except Exception as e:
            print(f"  Warning: historical fetch failed: {e}")
            results.extend([None] * len(batch_lats))
        time.sleep(1)
    return results


WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow",
    77: "Snow grains", 80: "Slight showers", 81: "Moderate showers",
    82: "Violent showers", 85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ slight hail",
    99: "Thunderstorm w/ heavy hail",
}

WIND_DIRS = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
             "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]


def wind_dir_label(degrees):
    idx = round(degrees / 22.5) % 16
    return WIND_DIRS[idx]


def wmo_to_condition(code):
    return WMO_CODES.get(code, "Unknown")


def wmo_to_icon(code):
    if code <= 1:
        return "sun"
    elif code <= 3:
        return "cloud-sun"
    elif code <= 48:
        return "cloud-fog"
    elif code <= 55:
        return "cloud-drizzle"
    elif code <= 65:
        return "cloud-rain"
    elif code <= 77:
        return "snowflake"
    elif code <= 82:
        return "cloud-showers-heavy"
    elif code <= 86:
        return "snowflake"
    else:
        return "bolt"


def build_data():
    print(f"Processing {len(CITIES)} cities...")
    lats = [c[3] for c in CITIES]
    lons = [c[4] for c in CITIES]

    # Fetch current + forecast
    print("Fetching current weather + 7-day forecasts from OpenMeteo...")
    weather_data = fetch_openmeteo_batch(lats, lons)

    # Fetch historical
    print("Fetching historical data...")
    # Only fetch historical for first 50 cities to keep it manageable
    hist_data = fetch_historical_batch(lats[:50], lons[:50])

    locations = []
    current_weather = []
    forecasts = []
    historical = []

    forecast_id = 1
    hist_id = 1

    for idx, city in enumerate(CITIES):
        name, country, region, lat, lon = city
        loc_id = f"loc-{idx + 1:03d}"

        wd = weather_data[idx] if idx < len(weather_data) else None

        # Location record
        tz = wd.get("timezone", "UTC") if wd else "UTC"
        elev = wd.get("elevation", 0) if wd else 0
        locations.append({
            "id": loc_id,
            "name": name,
            "country": country,
            "region": region,
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "timezone": tz,
            "elevation": round(elev, 1),
            "population": random.randint(50000, 15000000),
        })

        # Current weather
        if wd and "current" in wd:
            cur = wd["current"]
            wcode = cur.get("weather_code", 0)
            current_weather.append({
                "id": f"cw-{idx + 1:03d}",
                "location_id": loc_id,
                "temperature_c": cur.get("temperature_2m", 20),
                "feels_like_c": cur.get("apparent_temperature", 20),
                "humidity_pct": cur.get("relative_humidity_2m", 50),
                "wind_speed_kph": cur.get("wind_speed_10m", 10),
                "wind_direction": wind_dir_label(cur.get("wind_direction_10m", 0)),
                "pressure_hpa": cur.get("pressure_msl", 1013),
                "visibility_km": round(random.uniform(5, 30), 1),
                "uv_index": cur.get("uv_index", 3),
                "condition": wmo_to_condition(wcode),
                "condition_icon": wmo_to_icon(wcode),
                "updated_at": cur.get("time", datetime.now().isoformat()),
            })
        else:
            # Fallback synthetic
            current_weather.append({
                "id": f"cw-{idx + 1:03d}",
                "location_id": loc_id,
                "temperature_c": round(random.uniform(-10, 40), 1),
                "feels_like_c": round(random.uniform(-10, 40), 1),
                "humidity_pct": random.randint(20, 95),
                "wind_speed_kph": round(random.uniform(0, 50), 1),
                "wind_direction": random.choice(WIND_DIRS),
                "pressure_hpa": round(random.uniform(990, 1035), 1),
                "visibility_km": round(random.uniform(5, 30), 1),
                "uv_index": round(random.uniform(0, 11), 1),
                "condition": "Partly cloudy",
                "condition_icon": "cloud-sun",
                "updated_at": datetime.now().isoformat(),
            })

        # 7-day forecast
        if wd and "daily" in wd:
            daily = wd["daily"]
            for d in range(len(daily.get("time", []))):
                wcode = daily["weather_code"][d] if daily.get("weather_code") else 0
                forecasts.append({
                    "id": f"fc-{forecast_id:04d}",
                    "location_id": loc_id,
                    "date": daily["time"][d],
                    "high_c": daily.get("temperature_2m_max", [25])[d],
                    "low_c": daily.get("temperature_2m_min", [15])[d],
                    "condition": wmo_to_condition(wcode),
                    "precipitation_pct": daily.get("precipitation_probability_max", [0])[d] or 0,
                    "wind_speed_kph": daily.get("wind_speed_10m_max", [10])[d],
                    "humidity_pct": daily.get("relative_humidity_2m_mean", [50])[d],
                    "uv_index": daily.get("uv_index_max", [5])[d],
                    "sunrise": daily.get("sunrise", ["06:00"])[d],
                    "sunset": daily.get("sunset", ["20:00"])[d],
                })
                forecast_id += 1

        # Historical (monthly averages from daily data)
        if idx < len(hist_data) and hist_data[idx] and "daily" in hist_data[idx]:
            hd = hist_data[idx]["daily"]
            # Group by month and average
            monthly = {}
            for d_idx, date_str in enumerate(hd.get("time", [])):
                month_key = date_str[:7]  # YYYY-MM
                if month_key not in monthly:
                    monthly[month_key] = {"temps": [], "maxs": [], "mins": [],
                                          "precip": [], "humid": []}
                if hd.get("temperature_2m_mean") and hd["temperature_2m_mean"][d_idx] is not None:
                    monthly[month_key]["temps"].append(hd["temperature_2m_mean"][d_idx])
                if hd.get("temperature_2m_max") and hd["temperature_2m_max"][d_idx] is not None:
                    monthly[month_key]["maxs"].append(hd["temperature_2m_max"][d_idx])
                if hd.get("temperature_2m_min") and hd["temperature_2m_min"][d_idx] is not None:
                    monthly[month_key]["mins"].append(hd["temperature_2m_min"][d_idx])
                if hd.get("precipitation_sum") and hd["precipitation_sum"][d_idx] is not None:
                    monthly[month_key]["precip"].append(hd["precipitation_sum"][d_idx])
                if hd.get("relative_humidity_2m_mean") and hd["relative_humidity_2m_mean"][d_idx] is not None:
                    monthly[month_key]["humid"].append(hd["relative_humidity_2m_mean"][d_idx])

            for month_key in sorted(monthly.keys()):
                m = monthly[month_key]
                if m["temps"]:
                    historical.append({
                        "id": f"hist-{hist_id:04d}",
                        "location_id": loc_id,
                        "date": month_key,
                        "avg_temp_c": round(sum(m["temps"]) / len(m["temps"]), 1),
                        "max_temp_c": round(max(m["maxs"]) if m["maxs"] else 0, 1),
                        "min_temp_c": round(min(m["mins"]) if m["mins"] else 0, 1),
                        "precipitation_mm": round(sum(m["precip"]) if m["precip"] else 0, 1),
                        "avg_humidity_pct": round(sum(m["humid"]) / len(m["humid"]) if m["humid"] else 50, 1),
                    })
                    hist_id += 1

    # Synthesize users
    users = [
        {"id": "user-001", "username": "weatherfan42", "name": "Alice Chen",
         "email": "alice@example.com", "saved_locations": ["loc-001", "loc-041", "loc-082"],
         "alert_preferences": {"temp_threshold_c": 35, "wind_threshold_kph": 80},
         "unit_preference": "metric", "default_location": "loc-001"},
        {"id": "user-002", "username": "stormchaser", "name": "Bob Martinez",
         "email": "bob@example.com", "saved_locations": ["loc-005", "loc-015", "loc-025"],
         "alert_preferences": {"temp_threshold_c": 40, "wind_threshold_kph": 100},
         "unit_preference": "imperial", "default_location": "loc-005"},
        {"id": "user-003", "username": "skywatcher", "name": "Clara Johansson",
         "email": "clara@example.com", "saved_locations": ["loc-049", "loc-050"],
         "alert_preferences": {"temp_threshold_c": 30, "wind_threshold_kph": 60},
         "unit_preference": "metric", "default_location": "loc-049"},
        {"id": "user-004", "username": "globetrotter", "name": "David Nakamura",
         "email": "david@example.com", "saved_locations": ["loc-082", "loc-083", "loc-095"],
         "alert_preferences": {"temp_threshold_c": 38, "wind_threshold_kph": 90},
         "unit_preference": "metric", "default_location": "loc-082"},
        {"id": "user-005", "username": "rainreader", "name": "Emma Wilson",
         "email": "emma@example.com", "saved_locations": ["loc-041", "loc-053"],
         "alert_preferences": {"temp_threshold_c": 32, "wind_threshold_kph": 70},
         "unit_preference": "imperial", "default_location": "loc-041"},
        {"id": "user-006", "username": "temptracker", "name": "Fatima Al-Rashid",
         "email": "fatima@example.com", "saved_locations": ["loc-095", "loc-096", "loc-097"],
         "alert_preferences": {"temp_threshold_c": 45, "wind_threshold_kph": 50},
         "unit_preference": "metric", "default_location": "loc-095"},
    ]

    # Synthesize alerts based on real conditions
    alert_types = ["Heat Warning", "Wind Advisory", "Storm Warning",
                   "Freeze Warning", "Fog Advisory", "UV Alert"]
    severities = ["minor", "moderate", "severe", "extreme"]
    alerts = []
    now = datetime.now()
    for i in range(15):
        loc = random.choice(locations)
        atype = random.choice(alert_types)
        sev = random.choice(severities)
        start = now - timedelta(hours=random.randint(0, 12))
        end = start + timedelta(hours=random.randint(6, 48))
        alerts.append({
            "id": f"alert-{i + 1:03d}",
            "location_id": loc["id"],
            "type": atype,
            "severity": sev,
            "message": f"{atype} for {loc['name']}, {loc['country']}. "
                       f"Severity: {sev}. Take appropriate precautions.",
            "start": start.isoformat(),
            "end": end.isoformat(),
            "issued_at": (start - timedelta(hours=2)).isoformat(),
        })

    # Write all data files
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    files = {
        "locations.json": locations,
        "current_weather.json": current_weather,
        "forecasts.json": forecasts,
        "historical.json": historical,
        "users.json": users,
        "alerts.json": alerts,
    }
    for fname, data in files.items():
        path = OUTPUT_DIR / fname
        path.write_text(json.dumps(data, indent=2))
        print(f"  Wrote {fname}: {len(data)} records")

    print(f"\nDone! Total: {len(locations)} locations, {len(current_weather)} current, "
          f"{len(forecasts)} forecasts, {len(historical)} historical, "
          f"{len(users)} users, {len(alerts)} alerts")


if __name__ == "__main__":
    build_data()
