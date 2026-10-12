from datetime import date
import pytest
from backend.app.services.advisory import build_advisory
from backend.app.services.prediction import future_features, scenario_predictions
from backend.app.services.routing import recommend
from fastapi.testclient import TestClient
from backend.app.main import app, _scenario
from pydantic import ValidationError
from backend.app.models.schemas import ScenarioRequest
from backend.app.services.prediction import scenario_context
from backend.app.services import prediction as prediction_service
from backend.app.services.routing import (
    _candidate_gateways,
    _deduplicate_routes,
    _match_corridors,
    _shared_segment_ratio,
)
from backend.app.services.routing import _valid_geocoding_result
from backend.app.services import routing as routing_service
from backend.app.services.routing import RoutingError


def scenario():
    return {"date": date(2026, 10, 17), "time": "17:00", "source": "Bengaluru",
            "destination": "Tumakuru", "festival": True, "holiday": True, "weather": "Rain", "roadwork": True}


def fake_geocoding():
    return [
        {"name": "Bengaluru", "latitude": 12.97, "longitude": 77.59,
         "display_name": "Bengaluru, Karnataka, India", "address": {},
         "geocoding_source": "Nominatim"},
        {"name": "Tumakuru", "latitude": 13.42, "longitude": 76.88,
         "display_name": "Tumakuru, Karnataka, India", "address": {},
         "geocoding_source": "Nominatim"},
    ]


def fake_routes(count):
    return [
        {
            "distance": 10000 + index * 2000,
            "duration": 600 + index * 120,
            "geometry": {"coordinates": [
                [77.54 + index * 0.01, 13.028],
                [77.55 + index * 0.01, 13.02],
            ]},
        }
        for index in range(count)
    ]


def prediction_cache():
    return {
        corridor: {
            "severity_score": 0.3,
            "probability_high": 0.05,
            "prediction_source": "spark_mllib",
        }
        for corridor in ("Tumkur Road", "Yeshwanthpur", "Mysore Road")
    }


def test_future_features_are_new_scenario_features():
    features = future_features({**scenario(), "date": "2026-10-20"}, "Tumkur Road", "OUTBOUND")
    assert features["is_festival"] == 1 and "hour_sin" in features


def test_route_recommendation_and_advisory_flow(monkeypatch):
    request = scenario()
    monkeypatch.setattr(
        routing_service,
        "_osrm_routes",
        lambda _: (fake_routes(2), (77.59, 12.97), (76.88, 13.42), fake_geocoding()),
    )
    route = recommend(request, prediction_cache())
    predictions = scenario_predictions(request)
    advisory = build_advisory(predictions, request)
    assert route["recommended_route"]["recommendation"] == "BEST ROUTE"
    assert len(route["alternatives"]) >= 1
    assert route["geocoding"][0]["geocoding_source"] == "Nominatim"
    assert advisory["corridors"] and advisory["high_priority_corridors"]


def test_api_end_to_end_flow(monkeypatch):
    monkeypatch.setattr(
        routing_service,
        "_osrm_routes",
        lambda _: (fake_routes(2), (77.59, 12.97), (76.88, 13.42), fake_geocoding()),
    )
    response = TestClient(app).post("/api/route/recommend", json={
        **scenario(), "date": "2026-10-17",
    })
    assert response.status_code == 200
    body = response.json()
    assert body["recommended_route"]["recommendation"] == "BEST ROUTE"
    assert body["advisory"]["corridors"]
    assert body["corridor_predictions"][0]["prediction_source"] in {"spark_mllib", "development_fallback"}
    assert body["travel_surge_level"] in {"LOW", "MODERATE", "HIGH"}
    assert body["travel_direction"] in {"OUTBOUND", "INBOUND", "LOCAL"}


def test_invalid_time_and_weather_are_rejected():
    with pytest.raises(ValidationError):
        ScenarioRequest(date="2026-10-17", time="25:99")
    with pytest.raises(ValidationError):
        ScenarioRequest(date="2026-10-17", time="17:00", weather="Haze")


def test_coordinate_endpoints_are_supported_and_validated():
    request = ScenarioRequest(
        date="2026-10-17", time="17:00",
        source="A street address", destination="A landmark",
        source_coordinates=[12.9716, 77.5946],
        destination_coordinates=[13.4193, 76.8810],
    )
    assert request.source_coordinates == [12.9716, 77.5946]
    with pytest.raises(ValidationError):
        ScenarioRequest(date="2026-10-17", time="17:00", source_coordinates=[120, 77])


def test_osrm_uses_selected_coordinate_endpoints(monkeypatch):
    captured = []
    places = fake_geocoding()
    monkeypatch.setattr(routing_service, "_geocode", lambda place: places[0] if place == "From" else places[1])
    monkeypatch.setattr(routing_service, "_candidate_gateways", lambda *args: [])

    def fake_request(source, destination, alternatives, waypoint=None):
        captured.append((source, destination, alternatives))
        return [{
            "distance": 1000,
            "duration": 60,
            "geometry": {"coordinates": [
                [source[0], source[1]], [destination[0], destination[1]],
            ]},
        }]

    monkeypatch.setattr(routing_service, "_request_osrm_routes", fake_request)
    request = {**scenario(), "source": "From", "destination": "To",
               "source_coordinates": [12.5000, 77.1000],
               "destination_coordinates": [13.5000, 76.5000]}
    routing_service._osrm_routes(request)
    assert captured[0][:2] == ((77.1, 12.5), (76.5, 13.5))


def test_weekend_festival_direction_and_surge():
    context = scenario_context(scenario())
    assert context["travel_direction"] == "OUTBOUND"
    assert context["travel_surge_level"] == "HIGH"
    assert "Festival Outbound" in context["surge_pattern"]


def test_calendar_controls_festival_and_holiday_status():
    non_festival = scenario_context({**scenario(), "date": "2026-10-17", "scenario_mode": "CALENDAR", "festival": True, "holiday": True})
    assert non_festival["festival"] is False
    assert non_festival["holiday"] is False
    festival = scenario_context({**scenario(), "date": "2026-10-20", "scenario_mode": "CALENDAR", "festival": False, "holiday": False})
    assert festival["festival"] is True and festival["holiday"] is True


def test_manual_scenario_flags_survive_normalization():
    request = ScenarioRequest(
        date="2026-10-17", time="17:00", festival=True, holiday=True,
        scenario_mode="MANUAL",
    )
    normalized = _scenario(request)
    assert normalized["festival"] is True and normalized["holiday"] is True
    assert scenario_context(normalized)["festival"] is True
    assert scenario_context(normalized)["holiday"] is True


def test_calendar_mode_uses_configured_date_and_prediction_features_match():
    scenario_input = {
        **scenario(), "date": "2026-10-20", "scenario_mode": "CALENDAR",
        "festival": False, "holiday": False,
    }
    context = scenario_context(scenario_input)
    features = future_features(scenario_input, "Mysore Road", "OUTBOUND")
    assert context["festival"] is True and context["holiday"] is True
    assert features["is_festival"] == 1 and features["is_holiday"] == 1


def test_route_advisory_has_no_contradictory_action_for_unmatched_route():
    predictions = []
    advisory = build_advisory(predictions, scenario(), [])
    assert advisory["summary"] == "No reliable matched corridor is available for this route"
    assert advisory["directional_note"] == "No route-specific corridor recommendation is available for this route."


def test_unknown_weather_is_not_reported_as_rain():
    features = future_features({**scenario(), "weather": "Unknown"}, "Mysore Road", "OUTBOUND")
    assert features["is_rain"] == 0


def test_route_advisory_uses_selected_matched_corridor():
    predictions = [
        {**value, "corridor": corridor, "risk": "HIGH", "severity_score": 0.9,
         "factors": [], "direction": "OUTBOUND"}
        for corridor, value in prediction_cache().items()
    ]
    advisory = build_advisory(predictions, scenario(), ["Mysore Road"])
    assert [item["corridor"] for item in advisory["corridors"]] == ["Mysore Road"]
    assert all(item["corridor"] != "Tumkur Road" for item in advisory["corridors"])


def test_unmatched_route_advisory_does_not_invent_corridor():
    predictions = list(prediction_cache().values())
    for index, item in enumerate(predictions):
        item["corridor"] = ("Tumkur Road", "Mysore Road", "Yeshwanthpur")[index]
        item["risk"] = "HIGH"
        item["severity_score"] = 0.9
        item["factors"] = []
        item["direction"] = "OUTBOUND"
    advisory = build_advisory(predictions, scenario(), [])
    assert advisory["corridors"] == []
    assert advisory["summary"] == "No reliable matched corridor is available for this route"


def test_development_fallback_is_explicit(monkeypatch):
    monkeypatch.setenv("ALLOW_DEVELOPMENT_FALLBACK", "true")
    monkeypatch.setattr(prediction_service, "_model", lambda: None)
    result = prediction_service.predict_corridor(scenario(), "Tumkur Road", "OUTBOUND")
    assert result["prediction_source"] == "development_fallback"
    assert "probability" not in result
    assert 0 <= result["severity_score"] <= 1


def test_route_corridor_association_uses_geometry():
    assert "Tumkur Road" in _match_corridors(
        [[13.028, 77.540], [13.02, 77.55]], ["Tumkur Road", "Service Road"]
    )
    assert _match_corridors([]) == []
    assert _match_corridors([[12.953, 77.500], [13.000, 77.500]]) == []


def test_unrelated_mysuru_route_cannot_inherit_tumkur_defaults():
    geometry = [[12.976, 77.590], [12.915, 77.484], [12.850, 77.300]]
    assert routing_service._match_corridors(geometry, ["Mysore Road"]) == ["Mysore Road"]
    assert "Tumkur Road" not in routing_service._match_corridors(geometry, [])
    assert "Yeshwanthpur" not in routing_service._match_corridors(geometry, [])


def test_unmatched_route_is_not_marked_verified():
    result = routing_service._route_options(
        scenario(),
        [_network_route(midpoint=(77.20, 12.70))],
        "OSRM",
        prediction_cache(),
        ((77.59, 12.97), (76.88, 13.42)),
    )[0]
    assert result["corridors"] == []
    assert result["corridor_status"] == "unmatched"
    assert result["prediction_source"] == "unavailable"
    assert "No reliable corridor match" in result["mapping_note"]


@pytest.mark.parametrize("count", [1, 2, 3])
def test_only_genuine_osrm_routes_are_preserved(monkeypatch, count):
    monkeypatch.setattr(
        routing_service,
        "_osrm_routes",
        lambda _: (fake_routes(count), (77.59, 12.97), (76.88, 13.42), fake_geocoding()),
    )
    result = recommend(scenario(), prediction_cache())
    assert len(result["alternatives"]) == count
    assert all(route["route_source"] == "OSRM" for route in result["alternatives"])
    assert all(route["geometry"] for route in result["alternatives"])


def test_osrm_failure_is_explicit_and_does_not_fabricate_routes(monkeypatch):
    def fail(_):
        raise ValueError("OSRM unavailable")

    monkeypatch.setattr(routing_service, "_osrm_routes", fail)
    with pytest.raises(RoutingError, match="genuine route"):
        recommend(scenario(), prediction_cache())


def test_geocoding_requires_matching_indian_locality():
    valid = {
        "display_name": "Tumakuru, Karnataka, India",
        "address": {"town": "Tumakuru", "state": "Karnataka", "country": "India"},
    }
    wrong_locality = {
        "display_name": "Tumkur, Rajasthan, India",
        "address": {"town": "Tumkur", "state": "Rajasthan", "country": "India"},
    }
    assert _valid_geocoding_result("Tumakuru", valid)
    assert not _valid_geocoding_result("Tumakuru", wrong_locality)


def _network_route(midpoint=(77.54, 13.02)):
    return {
        "distance": 100000,
        "duration": 6000,
        "geometry": {"coordinates": [[77.59, 12.97], list(midpoint), [76.88, 13.42]]},
    }


def test_relevant_exit_corridors_depend_on_destination():
    tumakuru = _candidate_gateways(scenario(), fake_geocoding()[0], fake_geocoding()[1])
    assert [candidate["corridor"] for candidate in tumakuru] == ["Tumkur Road", "Outer Ring Road"]

    mysuru_scenario = {**scenario(), "destination": "Mysuru"}
    mysuru_place = {**fake_geocoding()[1], "display_name": "Mysuru, Karnataka, India"}
    mysuru = _candidate_gateways(mysuru_scenario, fake_geocoding()[0], mysuru_place)
    assert [candidate["corridor"] for candidate in mysuru] == ["Mysore Road"]


def test_waypoint_candidates_are_routed_and_duplicate_geometry_is_removed(monkeypatch):
    calls = []

    class Response:
        def __init__(self, routes):
            self.routes = routes

        def raise_for_status(self):
            return None

        def json(self):
            return {"routes": self.routes}

    def fake_get(url, params, timeout):
        calls.append((url, params))
        if params["alternatives"] == "true":
            return Response([_network_route()])
        return Response([_network_route(midpoint=(77.54, 13.028)), _network_route()])

    monkeypatch.setattr(routing_service, "_geocode", lambda place: fake_geocoding()[0 if place == "Bengaluru" else 1])
    monkeypatch.setattr(routing_service.httpx, "get", fake_get)
    routes, _, _, _ = routing_service._osrm_routes(scenario())

    assert len(routes) == 2
    assert any(params["alternatives"] == "false" for _, params in calls)
    assert routes[1]["_candidate_name"] == "Tumkur Road / Gorguntepalya"


def test_invalid_candidate_geometry_is_not_returned():
    valid = _network_route()
    invalid = _network_route()
    invalid["geometry"]["coordinates"][0] = [0, 0]
    assert len(_deduplicate_routes([valid, invalid], (77.59, 12.97), (76.88, 13.42))) == 1


def test_genuinely_different_geometry_is_preserved():
    first = _network_route(midpoint=(77.54, 13.02))
    second = _network_route(midpoint=(77.50, 13.05))
    assert len(_deduplicate_routes([first, second], (77.59, 12.97), (76.88, 13.42))) == 2


def test_shared_segment_comparison_identifies_same_and_different_paths():
    first = _network_route(midpoint=(77.54, 13.02))
    same = _network_route(midpoint=(77.54, 13.02))
    different = _network_route(midpoint=(77.50, 13.05))
    assert _shared_segment_ratio(first, same) == 1.0
    assert _shared_segment_ratio(first, different) < 1.0


def test_western_orr_candidate_requires_all_checkpoints():
    route = _network_route(midpoint=(77.50, 13.000))
    route["_requested_waypoints"] = [[77.500, 12.953], [77.500, 13.000]]
    assert routing_service._route_checkpoints_valid(route) is False


def test_failed_waypoint_does_not_remove_automatic_route(monkeypatch):
    automatic = _network_route()

    def fake_request(source, destination, alternatives, waypoint=None):
        if waypoint:
            raise routing_service.httpx.ConnectTimeout("waypoint unavailable")
        return [automatic]

    monkeypatch.setattr(routing_service, "_geocode", lambda place: fake_geocoding()[0 if place == "Bengaluru" else 1])
    monkeypatch.setattr(routing_service, "_request_osrm_routes", fake_request)
    routes, _, _, _ = routing_service._osrm_routes(scenario())
    assert len(routes) == 1
    assert routes[0]["_candidate_name"] == "Automatic OSRM route 1"


def test_route_comparison_exposes_overlap_and_explanations(monkeypatch):
    routes = [
        _network_route(midpoint=(77.54, 13.02)),
        _network_route(midpoint=(77.50, 13.05)),
    ]
    monkeypatch.setattr(
        routing_service,
        "_osrm_routes",
        lambda _: (routes, (77.59, 12.97), (76.88, 13.42), fake_geocoding()),
    )
    result = recommend(scenario(), prediction_cache())
    assert all(route["geometry"] for route in result["alternatives"])
    assert all(route["shared_segment_ratio"] is not None for route in result["alternatives"])
    assert result["alternatives"][0]["selected"] is True
    assert result["alternatives"][1]["explanation"].startswith("Not selected:")


def test_explicit_inbound_direction_changes_context():
    context = scenario_context({**scenario(), "direction": "INBOUND"})
    assert context["travel_direction"] == "INBOUND"
