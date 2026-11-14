"""Downstream path for one point. No API key.

The line comes from the public MERIT river-runner service. Local names that
MERIT leaves blank are filled from OpenStreetMap when a named waterway lies
on the path.
"""

from __future__ import annotations

import json
import math
import urllib.parse
import urllib.request

MERIT_URL = "https://merit.internetofwater.app/processes/river-runner/execution"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "sars-globe/1.0 (educational drought and runoff map)"
_CACHE: dict[tuple[float, float], dict] = {}


def downstream(lat: float, lon: float) -> dict:
    """Return a simplified path, river labels, and a one-line summary."""

    key = (round(lat, 3), round(lon, 3))
    cached = _CACHE.get(key)
    if cached is not None:
        return cached
    try:
        merit = _get_json(f"{MERIT_URL}?lat={lat}&lng={lon}", timeout=25)
        features = _features(merit)
        coords = _coordinates(features)
        osm = _named_waterways(coords) if coords else []
        result = build_path(merit, osm)
    except Exception:
        result = {
            "coordinates": [],
            "rivers": [],
            "summary": "The downstream path is unavailable right now.",
            "credit": "MERIT-Basins",
        }
    if result["coordinates"]:
        _CACHE[key] = result
    return result


def build_path(merit: dict, osm_elements: list | None = None) -> dict:
    """Turn a MERIT payload and optional Overpass elements into globe JSON."""

    features = _features(merit)
    coordinates = _coordinates(features)
    if len(coordinates) < 2:
        return {
            "coordinates": [],
            "rivers": [],
            "summary": "No downstream path was found for this spot.",
            "credit": "MERIT-Basins",
        }
    candidates: list[tuple[int, str, float, float]] = []
    cursor = 0
    merit_named = False
    for feature in features:
        coords = _line(feature.get("geometry") or {})
        props = feature.get("properties") or {}
        name = _clean_name(props.get("gnis_name")) or _clean_name(props.get("nameid"))
        if name and coords:
            merit_named = True
            mid = cursor + len(coords) // 2
            lon, lat = coordinates[min(mid, len(coordinates) - 1)]
            candidates.append((mid, name, lon, lat))
        cursor += len(coords)
    osm_named = False
    for element in osm_elements or []:
        tags = element.get("tags") or {}
        name = _clean_name(tags.get("name"))
        geometry = element.get("geometry") or []
        if not name or not geometry:
            continue
        nearest = _nearest_index(coordinates, geometry)
        if nearest is None:
            continue
        osm_named = True
        lon, lat = coordinates[nearest[0]]
        candidates.append((nearest[0], name, lon, lat))
    simplified = _simplify(coordinates)
    rivers = _spaced(candidates, len(coordinates))
    rivers = _remap_labels(rivers, coordinates, simplified)
    length = _length(coordinates)
    if rivers:
        listed = _join([river["name"] for river in rivers[:4]])
        summary = f"Rain from this spot runs downstream through {listed}."
    elif length < 1.5:
        summary = "This spot is already near the downstream end, so the path on the globe is short."
    else:
        summary = "Rain from this spot has a downstream path. This stretch has no named river in the source data."
    credit = "MERIT-Basins and OpenStreetMap" if osm_named or merit_named else "MERIT-Basins"
    if merit_named and not osm_named:
        credit = "MERIT-Basins"
    return {
        "coordinates": [[round(lon, 5), round(lat, 5)] for lon, lat in simplified],
        "rivers": rivers,
        "summary": summary,
        "credit": credit,
    }


def _features(merit: dict) -> list:
    value = merit.get("value", merit)
    if isinstance(value, dict):
        return list(value.get("features") or [])
    return []


def _coordinates(features: list) -> list[tuple[float, float]]:
    coordinates: list[tuple[float, float]] = []
    for feature in features:
        coordinates.extend(_line(feature.get("geometry") or {}))
    return coordinates


def _line(geometry: dict) -> list[tuple[float, float]]:
    kind = geometry.get("type")
    raw = geometry.get("coordinates") or []
    if kind == "LineString":
        return [_pair(pair) for pair in raw if _pair(pair)]
    if kind == "MultiLineString":
        points: list[tuple[float, float]] = []
        for line in raw:
            points.extend(_pair(pair) for pair in line if _pair(pair))
        return points
    return []


def _pair(pair) -> tuple[float, float] | None:
    if not isinstance(pair, (list, tuple)) or len(pair) < 2:
        return None
    try:
        return float(pair[0]), float(pair[1])
    except (TypeError, ValueError):
        return None


def _clean_name(value) -> str | None:
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or name.casefold() in {"unknown", "null", "none"}:
        return None
    return name


def _km(start: tuple[float, float], end: tuple[float, float]) -> float:
    lon1, lat1 = start
    lon2, lat2 = end
    mean = math.radians((lat1 + lat2) / 2)
    east = (lon2 - lon1) * 111.32 * math.cos(mean)
    north = (lat2 - lat1) * 110.54
    return math.hypot(east, north)


def _length(coordinates: list[tuple[float, float]]) -> float:
    return sum(_km(start, end) for start, end in zip(coordinates, coordinates[1:]))


def _nearest_index(
    path: list[tuple[float, float]], geometry: list
) -> tuple[int, float] | None:
    samples = []
    for node in geometry:
        if not isinstance(node, dict):
            continue
        try:
            samples.append((float(node["lon"]), float(node["lat"])))
        except (KeyError, TypeError, ValueError):
            continue
    if not samples:
        return None
    best_index = 0
    best = float("inf")
    step = max(1, len(path) // 250)
    for node in samples[:: max(1, len(samples) // 40)]:
        for index in range(0, len(path), step):
            distance = _km(path[index], node)
            if distance < best:
                best = distance
                best_index = index
    if best > 2.5:
        return None
    return best_index, best


def _simplify(
    coordinates: list[tuple[float, float]], min_km: float = 1.2, limit: int = 420
) -> list[tuple[float, float]]:
    if len(coordinates) < 3:
        return coordinates
    kept = [coordinates[0]]
    for point in coordinates[1:]:
        if _km(kept[-1], point) >= min_km:
            kept.append(point)
    if kept[-1] != coordinates[-1]:
        kept.append(coordinates[-1])
    if len(kept) <= limit:
        return kept
    stride = math.ceil(len(kept) / limit)
    trimmed = kept[::stride]
    if trimmed[-1] != kept[-1]:
        trimmed.append(kept[-1])
    return trimmed


def _spaced(candidates: list[tuple[int, str, float, float]], count: int) -> list[dict]:
    ordered = sorted(candidates, key=lambda item: item[0])
    gap = 0 if count < 12 else max(4, count // 10)
    kept: list[dict] = []
    used: set[str] = set()
    last = -10_000
    for index, name, lon, lat in ordered:
        key = name.casefold()
        if key in used:
            continue
        if kept and index - last < gap:
            continue
        used.add(key)
        kept.append({"name": name, "lon": round(lon, 5), "lat": round(lat, 5)})
        last = index
        if len(kept) == 6:
            break
    return kept


def _remap_labels(
    rivers: list[dict], original: list[tuple[float, float]], simplified: list[tuple[float, float]]
) -> list[dict]:
    """Move a label onto the simplified line so it sits on the drawn path."""

    if not rivers or not simplified:
        return rivers
    moved = []
    for river in rivers:
        point = (float(river["lon"]), float(river["lat"]))
        nearest = min(simplified, key=lambda item: _km(item, point))
        moved.append({"name": river["name"], "lon": round(nearest[0], 5), "lat": round(nearest[1], 5)})
    return moved


def _join(names: list[str]) -> str:
    if len(names) == 1:
        return names[0]
    if len(names) == 2:
        return f"{names[0]} and {names[1]}"
    return f"{', '.join(names[:-1])}, and {names[-1]}"


def _named_waterways(coordinates: list[tuple[float, float]]) -> list:
    if len(coordinates) < 2:
        return []
    query = _osm_query(coordinates)
    body = urllib.parse.urlencode({"data": query}).encode()
    request = urllib.request.Request(
        OVERPASS_URL,
        data=body,
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(request, timeout=16) as response:
            payload = json.loads(response.read().decode())
    except Exception:
        return []
    return list(payload.get("elements") or [])


def _osm_query(coordinates: list[tuple[float, float]]) -> str:
    lons = [lon for lon, _lat in coordinates]
    lats = [lat for _lon, lat in coordinates]
    span = max(max(lons) - min(lons), max(lats) - min(lats))
    if span <= 0.45:
        south = min(lats) - 0.03
        north = max(lats) + 0.03
        west = min(lons) - 0.03
        east = max(lons) + 0.03
        body = f'way["waterway"]["name"]({south},{west},{north},{east});'
    else:
        parts = []
        step = max(1, len(coordinates) // 5)
        for index in range(0, len(coordinates), step):
            lon, lat = coordinates[index]
            parts.append(f'way["waterway"]["name"](around:2500,{lat},{lon});')
            if len(parts) == 5:
                break
        body = "".join(parts)
    return f"[out:json][timeout:12];({body});out tags geom 30;"


def _get_json(url: str, timeout: int) -> dict:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode())
