"""Geospatial helpers."""
import math


def haversine(lat1, lng1, lat2, lng2, unit="km"):
    """Great-circle distance between two lat/lng points.

    unit: "km" (default) or "mi".
    """
    R = 3958.8 if unit == "mi" else 6371.0
    dlat = math.radians(lat2 - lat1)
    dlng = math.radians(lng2 - lng1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2))
         * math.sin(dlng / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
