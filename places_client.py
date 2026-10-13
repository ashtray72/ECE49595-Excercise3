"""
places_client.py
Searches Google Places API (New) for pickup-game locations near a point,
for a specific sport, and filters out places where a pickup game isn't realistic.

Requires a .env file (or environment variable) containing:
    GOOGLE_PLACES_KEY=your-key-here
"""

import math
import os

import requests
from dotenv import load_dotenv

load_dotenv()

TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"

# Only request the fields we use (keeps the request in a cheaper billing tier)
FIELD_MASK = "places.id,places.displayName,places.location,places.types"

# What we ask Google for, per sport (the three sports in our proposal)
SPORT_QUERIES = {
    "Basketball": "outdoor basketball court",
    "Pickleball": "pickleball court",
    "Flag Football": "park with open athletic field",
}

# Results with any of these Google place types are dropped
EXCLUDED_TYPES = {
    "golf_course",
    "fitness_center",
    "gym",
    "store",
    "sporting_goods_store",
    "shopping_mall",
    "bowling_alley",
    "restaurant",
    "bar",
}

# Results whose name contains any of these words are dropped
BLOCKED_KEYWORDS = ["golf", "country club", "store", "shop", "outlet", "grill"]


class PlacesAPIError(Exception):
    """Raised when the Places API request fails, so the GUI can show the message."""


def _get_api_key():
    key = os.getenv("GOOGLE_PLACES_KEY")
    if not key:
        raise PlacesAPIError(
            "GOOGLE_PLACES_KEY is not set. Add it to your .env file."
        )
    return key


def distance_m(lat1, lon1, lat2, lon2):
    """Straight-line distance between two coordinates in meters (haversine)."""
    r = 6371000  # Earth radius in meters
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def is_relevant(place):
    """True if a place looks like somewhere a free pickup game could happen."""
    types = set(place.get("types", []))
    if types & EXCLUDED_TYPES:
        return False
    name = place.get("displayName", {}).get("text", "").lower()
    return not any(word in name for word in BLOCKED_KEYWORDS)


def parse_places(response_json, center, radius_m):
    """
    Turns the raw API JSON into a list of clean dicts, applying the filters.
    Kept separate from the HTTP call so it can be unit-tested without the API.
    """
    results = []
    for place in response_json.get("places", []):
        name = place.get("displayName", {}).get("text")
        loc = place.get("location", {})
        lat, lon = loc.get("latitude"), loc.get("longitude")

        # Skip incomplete results
        if not name or lat is None or lon is None:
            continue
        if not is_relevant(place):
            continue

        # Text Search only *biases* toward our circle, so enforce the radius here
        dist = distance_m(center[0], center[1], lat, lon)
        if dist > radius_m:
            continue

        results.append({
            "id": place.get("id"),
            "name": name,
            "lat": lat,
            "lon": lon,
            "types": place.get("types", []),
            "distance_m": round(dist),
        })

    results.sort(key=lambda r: r["distance_m"])
    return results


def search_courts(center, sport, radius_m=3000, max_results=20):
    """
    Finds locations for `sport` near `center` (lat, lon).
    Returns a list of dicts sorted by distance:
        {"id", "name", "lat", "lon", "types", "distance_m"}
    Raises PlacesAPIError if the request fails.
    """
    if sport not in SPORT_QUERIES:
        raise ValueError(f"Unknown sport: {sport}")

    headers = {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _get_api_key(),
        "X-Goog-FieldMask": FIELD_MASK,
    }
    body = {
        "textQuery": SPORT_QUERIES[sport],
        "pageSize": max_results,
        "locationBias": {
            "circle": {
                "center": {"latitude": center[0], "longitude": center[1]},
                "radius": float(radius_m),
            }
        },
    }

    try:
        response = requests.post(TEXT_SEARCH_URL, headers=headers, json=body, timeout=10)
    except requests.RequestException as e:
        raise PlacesAPIError(f"Could not reach Google Places: {e}") from e

    if response.status_code != 200:
        try:
            message = response.json()["error"]["message"]
        except (ValueError, KeyError):
            message = response.text
        raise PlacesAPIError(f"Places API error {response.status_code}: {message}")

    return parse_places(response.json(), center, radius_m)
