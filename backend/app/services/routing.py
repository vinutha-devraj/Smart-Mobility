import json
import logging
import time
from typing import Any, TypedDict
import httpx

from .config import CORRIDORS, EXIT_CORRIDORS
from .prediction import predict_corridor, scenario_context

logger = logging.getLogger(__name__)

PROTOTYPE_CORRIDOR_POINTS = {
    "Tumkur Road": (13.028, 77.540), "Yeshwanthpur": (13.020, 77.550),
    "Mysore Road": (12.960, 77.520), "Outer Ring Road": (13.000, 77.620),
    "Marathahalli": (12.960, 77.700), "Hosur Road": (12.920, 77.620),
    "Silk Board": (12.920, 77.620), "Sarjapur Road": (12.910, 77.680),
    "Whitefield Road": (12.970, 77.750), "ITPL Main Road": (12.990, 77.740),
    "Bellary Road": (13.060, 77.590), "Hebbal": (13.035, 77.600),
    "Electronic City": (12.845, 77.660),
}

CORRIDOR_ROAD_TERMS = {
    "Tumkur Road": ("tumkur", "tumakuru"),
    "Mysore Road": ("mysore", "mysuru"),
    "Outer Ring Road": ("outer ring", "orr"),
    "Hosur Road": ("hosur",),
    "Sarjapur Road": ("sarjapur",),
    "Whitefield Road": ("whitefield",),
    "ITPL Main Road": ("itpl",),
    "Bellary Road": ("bellary", "ballari"),
}


class GeocodingError(ValueError):
    """Raised when a place cannot be resolved to a semantically valid location."""


class RoutingError(ValueError):
    """Raised when a genuine OSRM route cannot be obtained."""


class GeocodedPlace(TypedDict):
    name: str
    latitude: float
    longitude: float
    display_name: str
    address: dict[str, Any]
    geocoding_source: str


def _normalise_place(value: str) -> str:
    return " ".join(value.casefold().replace(",", " ").split())


def _requested_locality(place: str) -> str:
    return _normalise_place(place.split(",", 1)[0])


def _valid_geocoding_result(place: str, result: dict[str, Any]) -> bool:
    address = result.get("address") or {}
    requested = _requested_locality(place)
    locality_values = [
        address.get("city"),
        address.get("town"),
        address.get("municipality"),
        address.get("village"),
        address.get("county"),
    ]
    locality_values = [_normalise_place(str(value)) for value in locality_values if value]
    if requested not in locality_values:
        first_display_part = _normalise_place(str(result.get("display_name", "")).split(",", 1)[0])
        addressable_values = [
            address.get("road"), address.get("neighbourhood"), address.get("suburb"),
            address.get("amenity"), address.get("shop"), address.get("building"),
        ]
        addressable_values = [_normalise_place(str(value)) for value in addressable_values if value]
        if first_display_part != requested and not addressable_values:
            return False
    country = _normalise_place(str(address.get("country", "")))
    state = _normalise_place(str(address.get("state", "")))
    return country == "india" and state == "karnataka"


def _geocode(place: str) -> GeocodedPlace:
    if not place.strip():
        raise GeocodingError("A source and destination are required for routing")

    queries = [f"{place}, Karnataka, India", f"{place}, India", place]
    candidates: list[dict[str, Any]] = []
    for query in queries:
        try:
            response = httpx.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "json",
                    "addressdetails": 1,
                    "countrycodes": "in",
                    "limit": 5,
                },
                headers={"User-Agent": "smart-mobility-academic-prototype/1.0"},
                timeout=8,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise GeocodingError(f"Nominatim geocoding failed for '{place}'") from exc
        candidates.extend(response.json())
        valid = next((item for item in candidates if _valid_geocoding_result(place, item)), None)
        if valid:
            address = valid.get("address") or {}
            locality = (
                address.get("city")
                or address.get("town")
                or address.get("municipality")
                or address.get("village")
                or address.get("county")
            )
            return {
                "name": str(locality or place).strip(),
                "latitude": float(valid["lat"]),
                "longitude": float(valid["lon"]),
                "display_name": str(valid.get("display_name", "")).strip(),
                "address": address,
                "geocoding_source": "Nominatim",
            }

    raise GeocodingError(
        f"Nominatim returned no semantically consistent Karnataka, India city or town for '{place}'"
    )


def search_places(place: str) -> list[GeocodedPlace]:
    if not place.strip():
        return []
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/search",
            params={
                "q": f"{place}, Karnataka, India", "format": "json",
                "addressdetails": 1, "countrycodes": "in", "limit": 8,
            },
            headers={"User-Agent": "smart-mobility-academic-prototype/1.0"},
            timeout=8,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeocodingError("Nominatim search failed") from exc
    places = []
    for item in response.json():
        if not _valid_geocoding_result(place, item):
            continue
        address = item.get("address") or {}
        locality = (
            address.get("city") or address.get("town") or address.get("municipality")
            or address.get("village") or address.get("suburb") or place
        )
        places.append({
            "name": str(locality).strip(),
            "latitude": float(item["lat"]),
            "longitude": float(item["lon"]),
            "display_name": str(item.get("display_name", "")).strip(),
            "address": address,
            "geocoding_source": "Nominatim",
        })
    return places


def reverse_geocode(latitude: float, longitude: float) -> GeocodedPlace:
    try:
        response = httpx.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": latitude, "lon": longitude, "format": "json",
                "addressdetails": 1, "zoom": 18,
            },
            headers={"User-Agent": "smart-mobility-academic-prototype/1.0"},
            timeout=8,
        )
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise GeocodingError("Nominatim reverse geocoding failed") from exc
    item = response.json()
    if not _valid_geocoding_result(str(item.get("display_name", "")), item):
        raise GeocodingError("Selected map location is not a valid Karnataka, India location")
    address = item.get("address") or {}
    locality = (
        address.get("city") or address.get("town") or address.get("municipality")
        or address.get("village") or address.get("suburb") or "Selected map location"
    )
    return {
        "name": str(locality).strip(),
        "latitude": latitude,
        "longitude": longitude,
        "display_name": str(item.get("display_name", "")).strip(),
        "address": address,
        "geocoding_source": "Nominatim",
    }


def _osrm_routes(
    scenario: dict[str, Any],
) -> tuple[list[dict[str, Any]], tuple[float, float], tuple[float, float], list[GeocodedPlace]]:
    source_coordinates = scenario.get("source_coordinates")
    destination_coordinates = scenario.get("destination_coordinates")
    source_place = (
        _geocode(scenario["source"]) if not source_coordinates else {
            "name": scenario["source"], "latitude": float(source_coordinates[0]),
            "longitude": float(source_coordinates[1]), "display_name": scenario["source"],
            "address": {}, "geocoding_source": "coordinates",
        }
    )
    destination_place = (
        _geocode(scenario["destination"]) if not destination_coordinates else {
            "name": scenario["destination"], "latitude": float(destination_coordinates[0]),
            "longitude": float(destination_coordinates[1]), "display_name": scenario["destination"],
            "address": {}, "geocoding_source": "coordinates",
        }
    )
    source = (
        (float(source_coordinates[1]), float(source_coordinates[0]))
        if source_coordinates else (source_place["longitude"], source_place["latitude"])
    )
    destination = (
        (float(destination_coordinates[1]), float(destination_coordinates[0]))
        if destination_coordinates else (destination_place["longitude"], destination_place["latitude"])
    )
    candidates = _candidate_gateways(scenario, source_place, destination_place)
    routes: list[dict[str, Any]] = []
    try:
        automatic_routes = _request_osrm_routes(source, destination, alternatives=True)
        for route_index, route in enumerate(automatic_routes, 1):
            route["_candidate_name"] = f"Automatic OSRM route {route_index}"
        routes.extend(automatic_routes)
        if not automatic_routes:
            _log_candidate_debug({
                "candidate": "automatic OSRM",
                "request_coordinates": [list(source), list(destination)],
                "routing_status": "no_route",
                "accepted": False,
                "rejection_reason": "OSRM returned no routes",
            })
    except httpx.HTTPError as exc:
        _log_candidate_debug({
            "candidate": "automatic OSRM",
            "request_coordinates": [list(source), list(destination)],
            "routing_status": "error",
            "accepted": False,
            "rejection_reason": f"OSRM request failed: {type(exc).__name__}",
        })
    for candidate in candidates:
        waypoints = candidate.get("waypoints") or [candidate["gateway"]]
        try:
            waypoint_routes = _request_osrm_routes(
                source, destination, alternatives=False, waypoint=waypoints,
            )
        except httpx.HTTPError as exc:
            _log_candidate_debug({
                "candidate": candidate["name"],
                "request_coordinates": [list(source), *waypoints, list(destination)],
                "routing_status": "error",
                "accepted": False,
                "rejection_reason": f"OSRM request failed: {type(exc).__name__}",
            })
            continue
        if not waypoint_routes:
            _log_candidate_debug({
                "candidate": candidate["name"],
                "request_coordinates": [list(source), *waypoints, list(destination)],
                "routing_status": "no_route",
                "accepted": False,
                "rejection_reason": "OSRM returned no routes through gateway",
            })
        for route_index, route in enumerate(waypoint_routes, 1):
            route["_candidate_name"] = candidate["name"]
            route["_candidate_corridor"] = candidate["corridor"]
            route["_requested_waypoints"] = waypoints
            routes.append(route)
            route["_candidate_index"] = route_index
    routes = _deduplicate_routes(routes, source, destination)
    if not routes:
        raise ValueError("OSRM returned no verified routes")
    return routes, source, destination, [source_place, destination_place]


def _request_osrm_routes(
    source: tuple[float, float],
    destination: tuple[float, float],
    alternatives: bool,
    waypoint: list[list[float]] | None = None,
) -> list[dict[str, Any]]:
    coordinates = [source]
    if waypoint:
        coordinates.extend(tuple(point) for point in waypoint)
    coordinates.append(destination)
    coordinate_path = ";".join(f"{lon},{lat}" for lon, lat in coordinates)
    timeout_seconds = 45 if waypoint else 15
    request_params = {
        "overview": "full", "geometries": "geojson",
        "alternatives": "true" if alternatives else "false", "steps": "true",
    }
    attempts = 2 if waypoint else 1
    response = None
    for attempt in range(attempts):
        try:
            response = httpx.get(
                f"https://router.project-osrm.org/route/v1/driving/{coordinate_path}",
                params=request_params,
                timeout=timeout_seconds,
            )
            response.raise_for_status()
            break
        except httpx.HTTPError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.5)
    if response is None:
        return []
    routes = response.json().get("routes", [])
    request_coordinates = [list(coordinate) for coordinate in coordinates]
    for route in routes:
        route["_request_coordinates"] = request_coordinates
        route["_request_timeout_seconds"] = timeout_seconds
        route["_road_names"] = _route_road_names(route)
    return routes


def _route_road_names(route: dict[str, Any]) -> list[str]:
    names = []
    for leg in route.get("legs", []):
        for step in leg.get("steps", []):
            name = str(step.get("name") or "").strip()
            if name and name not in names:
                names.append(name)
    return names


def _candidate_gateways(
    scenario: dict[str, Any],
    source_place: GeocodedPlace,
    destination_place: GeocodedPlace,
) -> list[dict[str, Any]]:
    journey_places = _normalise_place(
        f"{scenario['source']} {source_place['display_name']} "
        f"{scenario['destination']} {destination_place['display_name']}"
    )
    direction = str(scenario.get("direction", "AUTO")).upper()
    candidates = []
    for candidate in EXIT_CORRIDORS:
        if direction != "AUTO" and direction not in candidate.get("directions", []):
            continue
        if any(_normalise_place(keyword) in journey_places for keyword in candidate["destination_keywords"]):
            candidates.append(candidate)
    return candidates


def _geometry_key(route: dict[str, Any]) -> tuple[tuple[float, float], ...]:
    coordinates = route.get("geometry", {}).get("coordinates", [])
    return tuple((float(point[0]), float(point[1])) for point in coordinates)


def _route_endpoints_valid(
    route: dict[str, Any],
    source: tuple[float, float],
    destination: tuple[float, float],
) -> bool:
    coordinates = route.get("geometry", {}).get("coordinates", [])
    if len(coordinates) < 2:
        return False
    first, last = coordinates[0], coordinates[-1]
    valid = (
        abs(float(first[0]) - source[0]) < 0.02
        and abs(float(first[1]) - source[1]) < 0.02
        and abs(float(last[0]) - destination[0]) < 0.02
        and abs(float(last[1]) - destination[1]) < 0.02
        and float(route.get("distance", 0)) > 0
        and float(route.get("duration", 0)) > 0
    )
    return valid


def _route_checkpoints_valid(route: dict[str, Any]) -> bool:
    waypoints = route.get("_requested_waypoints", [])
    coordinates = route.get("geometry", {}).get("coordinates", [])
    return all(
        min(
            (float(point[0]) - float(checkpoint[0])) ** 2
            + (float(point[1]) - float(checkpoint[1])) ** 2
            for point in coordinates
        ) <= 0.003 ** 2
        for checkpoint in waypoints
    )


def _segment_keys(route: dict[str, Any], cell_size: float = 0.0005) -> set[tuple[tuple[int, int], tuple[int, int]]]:
    coordinates = route.get("geometry", {}).get("coordinates", [])
    quantized = [
        (round(float(point[0]) / cell_size), round(float(point[1]) / cell_size))
        for point in coordinates
    ]
    return set(zip(quantized, quantized[1:]))


def _shared_segment_ratio(first: dict[str, Any], second: dict[str, Any]) -> float:
    first_segments = _segment_keys(first)
    second_segments = _segment_keys(second)
    if not first_segments or not second_segments:
        return 0.0
    return len(first_segments & second_segments) / min(len(first_segments), len(second_segments))


def _divergence_rejoin_summary(
    first: dict[str, Any],
    second: dict[str, Any],
) -> str:
    first_points = first.get("geometry", {}).get("coordinates", [])
    second_segments = _segment_keys(second)
    if not first_points:
        return "Unavailable"
    different_points = []
    for point in first_points:
        cell = (round(float(point[0]) / 0.0005), round(float(point[1]) / 0.0005))
        if any(segment[0] == cell or segment[1] == cell for segment in second_segments):
            continue
        different_points.append(point)
    if not different_points:
        return "No measurable divergence"
    start = different_points[0]
    end = different_points[-1]
    return f"Approx. divergence/rejoin: ({start[1]:.3f}, {start[0]:.3f}) to ({end[1]:.3f}, {end[0]:.3f})"


def _log_candidate_debug(details: dict[str, Any]) -> None:
    logger.info("route_candidate=%s", json.dumps(details, sort_keys=True))


def _deduplicate_routes(
    routes: list[dict[str, Any]],
    source: tuple[float, float],
    destination: tuple[float, float],
) -> list[dict[str, Any]]:
    verified: list[dict[str, Any]] = []
    seen: set[tuple[tuple[float, float], ...]] = set()
    for route in routes:
        coordinates = route.get("geometry", {}).get("coordinates", [])
        endpoint_valid = _route_endpoints_valid(route, source, destination)
        checkpoint_valid = _route_checkpoints_valid(route)
        details = {
            "candidate": route.get("_candidate_name", "unknown"),
            "candidate_index": route.get("_candidate_index"),
            "request_coordinates": route.get("_request_coordinates"),
            "request_timeout_seconds": route.get("_request_timeout_seconds"),
            "routing_status": "success",
            "distance_m": route.get("distance"),
            "duration_s": route.get("duration"),
            "geometry_point_count": len(coordinates),
            "endpoint_validation": endpoint_valid,
            "checkpoint_validation": checkpoint_valid,
            "accepted": False,
        }
        if not endpoint_valid:
            details["rejection_reason"] = "route geometry does not connect the requested endpoints"
            _log_candidate_debug(details)
            continue
        if not checkpoint_valid:
            details["rejection_reason"] = "route geometry does not pass through all requested checkpoints"
            _log_candidate_debug(details)
            continue
        key = _geometry_key(route)
        if not key or key in seen:
            details["rejection_reason"] = "exact normalized geometry duplicate"
            _log_candidate_debug(details)
            continue
        overlap = max((_shared_segment_ratio(route, existing) for existing in verified), default=0.0)
        details["maximum_shared_segment_ratio"] = round(overlap, 3)
        if overlap >= 0.98:
            details["rejection_reason"] = "route follows the same normalized road segments as an accepted route"
            _log_candidate_debug(details)
            continue
        seen.add(key)
        verified.append(route)
        details["accepted"] = True
        details["rejection_reason"] = None
        _log_candidate_debug(details)
    return verified


def _match_corridors(
    geometry: list[list[float]],
    road_names: list[str] | None = None,
) -> list[str]:
    """Return only corridors supported by names on the returned OSRM road steps."""
    del geometry
    normalized_names = [_normalise_place(name) for name in (road_names or [])]
    return [
        corridor for corridor, terms in CORRIDOR_ROAD_TERMS.items()
        if any(term in road_name for term in terms for road_name in normalized_names)
    ]


def _approximate_corridors(geometry: list[list[float]]) -> list[str]:
    """Report nearby representative points as approximate, never as verified matches."""
    if not geometry:
        return []
    distances = [
        (
            min((point[0] - lon) ** 2 + (point[1] - lat) ** 2 for point in geometry),
            name,
        )
        for name, (lat, lon) in PROTOTYPE_CORRIDOR_POINTS.items()
    ]
    nearby = [name for distance, name in sorted(distances) if distance <= 0.003 ** 2]
    return nearby[:2]


def _route_options(scenario: dict[str, Any], routes: list[dict[str, Any]], source: str,
                   prediction_cache: dict[str, dict[str, Any]] | None = None,
                   endpoints: tuple[tuple[float, float], tuple[float, float]] | None = None) -> list[dict[str, Any]]:
    options = []
    for index, route in enumerate(routes):
        geometry = route.get("geometry", {}).get("coordinates", [])
        geometry_latlon = [[point[1], point[0]] for point in geometry]
        corridors = _match_corridors(geometry_latlon, route.get("_road_names"))
        approximate_corridors = [] if corridors else _approximate_corridors(geometry_latlon)
        corridor_status = (
            "matched" if corridors else
            "approximate" if approximate_corridors else
            "unmatched"
        )
        name = f"OSRM candidate route {index + 1}"
        scenario_direction = scenario.get("direction")
        predictions = [
            prediction_cache.get(corridor) if prediction_cache else
            predict_corridor(
                scenario, corridor,
                scenario_direction if scenario_direction in {"OUTBOUND", "INBOUND"}
                else CORRIDORS[corridor]["typical_direction"],
            )
            for corridor in corridors
        ]
        predictions = [prediction for prediction in predictions if prediction]
        severity_score = max((p["severity_score"] for p in predictions), default=None)
        probability_high = max(
            (p["probability_high"] for p in predictions if p["probability_high"] is not None),
            default=None,
        )
        risk = (
            "HIGH" if severity_score is not None and severity_score >= 0.67 else
            "MEDIUM" if severity_score is not None and severity_score >= 0.42 else
            "LOW" if severity_score is not None else "UNAVAILABLE"
        )
        base_minutes = float(route["duration"]) / 60
        adjusted_minutes = (
            base_minutes * (1 + severity_score * ROUTE_SCORING["severity_time_multiplier"])
            if severity_score is not None else base_minutes
        )
        score = _route_score(
            distance_km=float(route["distance"]) / 1000,
            base_minutes=base_minutes,
            severity_score=severity_score,
            risk=risk,
        )
        options.append({
            "route_id": f"route-{index + 1}",
            "name": route.get("_candidate_name") or name,
            "corridors": corridors,
            "approximate_corridors": approximate_corridors,
            "corridor_status": corridor_status,
            "distance_km": round(float(route["distance"]) / 1000, 2),
            "base_duration_minutes": round(base_minutes, 1), "adjusted_duration_minutes": round(adjusted_minutes, 1),
            "congestion_severity_score": round(severity_score, 3) if severity_score is not None else None,
            "predicted_level": risk,
            "probability_high": round(probability_high, 3) if probability_high is not None else None,
            "risk": risk, "score": round(score, 2),
            "prediction_source": predictions[0]["prediction_source"] if predictions else "unavailable",
            "recommendation": "", "selected": False, "rank": None,
            "explanation": "Corridor assessment unavailable; route ranked using OSRM base distance and duration."
            if not predictions else "",
            "geometry": [[point[1], point[0]] for point in geometry],
            "shared_segment_ratio": None,
            "overlap_note": "",
            "_raw_geometry": route,
            "source_coordinates": [endpoints[0][1], endpoints[0][0]] if endpoints else None,
            "destination_coordinates": [endpoints[1][1], endpoints[1][0]] if endpoints else None,
            "route_source": source,
            "mapping_note": (
                "Matched from returned OSRM road names; route-specific Spark features are supported."
                if corridors else
                f"Nearby corridor only (approximate): {', '.join(approximate_corridors)}; "
                "not used for route-specific Spark prediction."
                if approximate_corridors else
                "No reliable corridor match from returned road names or configured geometry; "
                "route-specific congestion prediction is unavailable."
            ),
        })
    return options


ROUTE_SCORING = {
    "severity_time_multiplier": 0.85,
    "severity_penalty": 20.0,
    "distance_penalty_per_km": 0.08,
    "high_risk_penalty": 10.0,
}


def _route_score(
    distance_km: float,
    base_minutes: float,
    severity_score: float | None,
    risk: str,
) -> float:
    adjusted_minutes = (
        base_minutes * (1 + severity_score * ROUTE_SCORING["severity_time_multiplier"])
        if severity_score is not None else base_minutes
    )
    severity_penalty = (
        severity_score * ROUTE_SCORING["severity_penalty"]
        if severity_score is not None else 0
    )
    high_risk_penalty = ROUTE_SCORING["high_risk_penalty"] if risk == "HIGH" else 0
    return (
        adjusted_minutes
        + severity_penalty
        + distance_km * ROUTE_SCORING["distance_penalty_per_km"]
        + high_risk_penalty
    )


def recommend(scenario: dict[str, Any], prediction_cache: dict[str, dict[str, Any]] | None = None) -> dict:
    try:
        routes, origin, destination, geocoding = _osrm_routes(scenario)
        options = _route_options(scenario, routes, "OSRM", prediction_cache, (origin, destination))
    except GeocodingError:
        raise
    except (httpx.HTTPError, ValueError, KeyError) as exc:
        raise RoutingError("OSRM could not return a genuine route for this journey.") from exc
    options.sort(key=lambda option: option["score"])
    selected_raw = options[0]["_raw_geometry"]
    for rank, option in enumerate(options, 1):
        option["rank"] = rank
        option["selected"] = rank == 1
        option["shared_segment_ratio"] = (
            round(_shared_segment_ratio(option["_raw_geometry"], selected_raw), 3)
            if len(options) > 1 else None
        )
        option["overlap_note"] = (
            "No alternative route available for comparison."
            if len(options) == 1 else
            "Selected route baseline."
            if rank == 1 else
            _divergence_rejoin_summary(option["_raw_geometry"], selected_raw)
        )
        option.pop("_raw_geometry", None)
    options[0]["recommendation"] = "BEST ROUTE"
    best = options[0]
    if len(options) == 1:
        explanation = ["Only one genuine OSRM route was returned for this journey."]
        best["explanation"] = explanation[0]
    else:
        explanation = _recommendation_explanation(best, options)
        best["explanation"] = explanation[0]
    for option in options:
        if option is not best:
            option["explanation"] = (
                f"Not selected: {option['shared_segment_ratio']:.0%} of normalized road segments "
                "are shared with the selected route; ranking also considers predicted congestion, "
                "OSRM base duration, and distance."
            )
    return {"recommended_route": best, "alternatives": options, "explanation": explanation,
            "scenario": scenario, "geocoding": geocoding, **scenario_context(scenario)}


def _recommendation_explanation(best: dict[str, Any], options: list[dict[str, Any]]) -> list[str]:
    assessed = [option for option in options if option["congestion_severity_score"] is not None]
    if not assessed:
        return ["Selected by the lowest OSRM base duration and distance among returned routes."]
    severity_scores = {option["congestion_severity_score"] for option in assessed}
    if len(severity_scores) == 1:
        return [
            "Routes have equal predicted congestion; selected using the OSRM base duration and distance trade-off.",
        ]
    lower_severity = min(option["congestion_severity_score"] for option in assessed)
    if best["congestion_severity_score"] == lower_severity:
        return ["Selected with the lowest predicted congestion among the assessed routes."]
    return ["Selected by the combined predicted-congestion, OSRM duration, and distance score."]
