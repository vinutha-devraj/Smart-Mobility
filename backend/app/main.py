import os
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from .models.schemas import ScenarioRequest
from .services.advisory import build_advisory
from .services.config import CORRIDORS
from .services.prediction import calendar_flags, scenario_predictions, scenario_context
from .services.routing import GeocodingError, RoutingError, recommend, reverse_geocode, search_places
from pathlib import Path
import json

app = FastAPI(title="Smart Mobility Bengaluru API", version="1.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


@app.get("/api/health")
def health() -> dict:
    model_available = (Path(__file__).resolve().parents[2] / "models" / "spark_best").exists()
    fallback = os.getenv("ALLOW_DEVELOPMENT_FALLBACK", "false").lower() == "true"
    return {
        "status": "ok", "mode": "predictive prototype",
        "data": "synthetic mobility simulation",
        "model_available": model_available,
        "model_type": "Spark MLlib PipelineModel" if model_available else None,
        "prediction_source": "development_fallback" if fallback else ("spark_mllib" if model_available else "unavailable"),
        "fallback_enabled": fallback,
    }


def _scenario(request: ScenarioRequest) -> dict:
    scenario = request.model_dump(mode="json")
    flags = calendar_flags(scenario)
    scenario.update({
        "festival": flags["festival"],
        "holiday": flags["holiday"],
        "festival_name": flags["festival_name"],
        "festival_source": flags["festival_source"],
        "holiday_source": flags["holiday_source"],
        "weather_source": flags["weather_source"],
    })
    return scenario


@app.post("/api/predict/scenario")
def predict(request: ScenarioRequest) -> dict:
    scenario = _scenario(request)
    predictions = scenario_predictions(scenario)
    return {"scenario": scenario, **scenario_context(scenario), "predictions": predictions}


@app.post("/api/route/recommend")
def route(request: ScenarioRequest) -> dict:
    scenario = _scenario(request)
    predictions = scenario_predictions(scenario)
    try:
        result = recommend(scenario, {item["corridor"]: item for item in predictions})
    except (GeocodingError, RoutingError) as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    result["corridor_predictions"] = predictions
    result["advisory"] = build_advisory(predictions, scenario)
    for route_option in result["alternatives"]:
        route_option["route_advisory"] = build_advisory(
            predictions, scenario, route_option.get("corridors", [])
        )
    return result


@app.get("/api/geocode/search")
def geocode_search(q: str = Query(min_length=1)) -> dict:
    try:
        return {"places": search_places(q)}
    except GeocodingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/geocode/reverse")
def geocode_reverse(lat: float, lon: float) -> dict:
    try:
        return {"place": reverse_geocode(lat, lon)}
    except GeocodingError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@app.get("/api/corridors")
def corridors() -> dict:
    return {"corridors": list(CORRIDORS)}


@app.get("/api/corridors/risk")
def corridor_risk() -> dict:
    default = ScenarioRequest(date="2026-10-17", time="17:00", festival=True, holiday=True)
    scenario = _scenario(default)
    return {"scenario": scenario, **scenario_context(scenario), "predictions": scenario_predictions(scenario)}


@app.post("/api/advisory")
def advisory(request: ScenarioRequest) -> dict:
    scenario = _scenario(request)
    return build_advisory(scenario_predictions(scenario), scenario)


@app.get("/api/advisory")
def advisory_default() -> dict:
    default = ScenarioRequest(date="2026-10-17", time="17:00", festival=True, holiday=True)
    scenario = _scenario(default)
    return build_advisory(scenario_predictions(scenario), scenario)


ANALYTICS_PATH = Path(__file__).resolve().parents[2] / "data" / "output" / "analytics.json"


def _analytics() -> dict:
    if not ANALYTICS_PATH.exists():
        raise HTTPException(status_code=503, detail="Analytics not generated. Run spark\\analytics.py after preprocessing.")
    return json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))


@app.get("/api/analytics")
def analytics() -> dict:
    return {"source": "Spark aggregation over synthetic mobility simulation", **_analytics()}
