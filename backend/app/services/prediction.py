from datetime import date
from math import cos, pi, sin
from pathlib import Path
from typing import Any
import json
import os
import sys

from .config import CORRIDORS, FESTIVALS

ROOT = Path(__file__).resolve().parents[3]
MODEL_PATH = ROOT / "models" / "spark_best"
METADATA_PATH = ROOT / "models" / "metadata.json"
FEATURE_NAMES = [
    "hour_sin", "hour_cos", "is_weekend", "is_friday", "is_saturday",
    "is_sunday", "is_pre_holiday", "is_post_holiday", "is_festival",
    "is_holiday", "is_rain", "roadwork", "incident_count",
    "travel_demand", "traffic_capacity_ratio", "corridor_risk_profile",
    "direction_outbound", "direction_inbound",
]
_SPARK = None
_MODEL = None
_MODEL_LOADED = False
_MODEL_ERROR: Exception | None = None


def _level(score: float) -> str:
    return "HIGH" if score >= 0.67 else "MEDIUM" if score >= 0.42 else "LOW"


def _fallback_enabled() -> bool:
    return os.getenv("ALLOW_DEVELOPMENT_FALLBACK", "false").lower() == "true"


def calendar_flags(scenario: dict[str, Any]) -> dict[str, Any]:
    selected_date = str(scenario["date"])
    event = next((item for item in FESTIVALS if item["date"] == selected_date), None)
    manual = str(scenario.get("scenario_mode", "MANUAL")).upper() == "MANUAL"
    if manual:
        return {
            "festival": bool(scenario.get("festival")),
            "holiday": bool(scenario.get("holiday")),
            "festival_name": None,
            "festival_source": "manual_scenario_input",
            "holiday_source": "manual_scenario_input",
            "weather_source": (
                "explicit_scenario_input"
                if scenario.get("weather") in {"Clear", "Cloudy", "Rain"} else "unknown"
            ),
        }
    return {
        "festival": bool(event and event.get("is_festival")),
        "holiday": bool(event and event.get("is_holiday")),
        "festival_name": event.get("festival_name") if event else None,
        "festival_source": "configured_calendar" if event else "configured_calendar_no_event",
        "holiday_source": "configured_calendar" if event else "configured_calendar_no_event",
        "weather_source": (
            "explicit_scenario_input"
            if scenario.get("weather") in {"Clear", "Cloudy", "Rain"} else "unknown"
        ),
    }


def scenario_context(scenario: dict[str, Any]) -> dict[str, Any]:
    flags = calendar_flags(scenario)
    festival = flags["festival"]
    holiday = flags["holiday"]
    day = date.fromisoformat(str(scenario["date"])).weekday()
    hour = int(scenario["time"].split(":")[0])
    requested_direction = str(scenario.get("direction", "AUTO")).upper()
    if requested_direction in {"OUTBOUND", "INBOUND"}:
        direction = requested_direction
        pattern = f"Selected {direction.title()} journey"
        explanation = f"The scenario explicitly models travel {direction.lower()} Bengaluru."
    elif day in (4, 5) and hour >= 15:
        direction = "OUTBOUND"
        pattern = "Festival Outbound" if festival else "Weekend Outbound"
        explanation = (
            "High outbound surge risk — festival and Friday/Saturday evening travel pattern."
            if festival else
            "High outbound surge risk — Friday/Saturday evening travel pattern."
        )
    elif day in (6, 0) and hour >= 15:
        direction = "INBOUND"
        pattern = "Post-holiday Inbound" if holiday else "Weekend Inbound"
        explanation = (
            "High inbound surge risk — Sunday/Monday post-holiday return pattern."
            if holiday else
            "Inbound demand pattern — Sunday/Monday return travel."
        )
    elif festival or holiday:
        direction = "OUTBOUND" if day in (4, 5) else "LOCAL"
        pattern = "Festival/Holiday Travel"
        explanation = "Festival/holiday demand is included in the scenario factors."
    else:
        direction = "LOCAL"
        pattern = "Normal Local Travel"
        explanation = "No major weekend, festival, or post-holiday directional pattern was detected."
    if direction == "LOCAL":
        level = "MODERATE" if hour in (7, 8, 9, 17, 18, 19) else "LOW"
    elif festival or holiday or hour in (7, 8, 9, 17, 18, 19):
        level = "HIGH"
    else:
        level = "MODERATE"
    return {
        "travel_direction": direction,
        "travel_surge_level": level,
        "surge_pattern": pattern,
        "surge_explanation": explanation,
        "festival": festival,
        "holiday": holiday,
        "festival_name": flags["festival_name"],
        "festival_source": flags["festival_source"],
        "holiday_source": flags["holiday_source"],
        "weather_source": flags["weather_source"],
    }


def future_features(scenario: dict[str, Any], corridor: str, direction: str | None = None) -> dict[str, float]:
    """Build a new feature vector; no historical row is read."""
    if direction is None:
        direction = corridor
        corridor = next(iter(CORRIDORS))
    flags = calendar_flags(scenario)
    hour = int(scenario["time"].split(":")[0])
    day = date.fromisoformat(str(scenario["date"])).weekday()
    config = CORRIDORS[corridor]
    peak = 0.30 if hour in (7, 8, 9, 17, 18, 19) else 0.08
    demand = 0.55 + peak + (0.12 if day >= 5 else 0) + (0.12 if flags["festival"] else 0)
    if direction == "OUTBOUND" and day in (4, 5) and hour >= 15:
        demand += 0.10
    if direction == "INBOUND" and day in (6, 0) and hour >= 15:
        demand += 0.08
    return {
        "hour_sin": sin(2 * pi * hour / 24), "hour_cos": cos(2 * pi * hour / 24),
        "is_weekend": float(day >= 5), "is_friday": float(day == 4),
        "is_saturday": float(day == 5), "is_sunday": float(day == 6),
        "is_pre_holiday": float(day == 4 and flags["holiday"]),
        "is_post_holiday": float(day == 0 and flags["holiday"]),
        "is_festival": float(flags["festival"]),
        "is_holiday": float(flags["holiday"]),
        "is_rain": float(str(scenario.get("weather", "Clear")).lower() == "rain"),
        "roadwork": float(scenario.get("roadwork", False)),
        "incident_count": 1.0 if scenario.get("incident", False) else 0.0,
        "travel_demand": demand,
        "traffic_capacity_ratio": demand * config["relative_risk"],
        "corridor_risk_profile": config["relative_risk"],
        "direction_outbound": float(direction == "OUTBOUND"),
        "direction_inbound": float(direction == "INBOUND"),
    }


def _factors(scenario: dict[str, Any], corridor: str, direction: str) -> list[str]:
    day = date.fromisoformat(str(scenario["date"])).weekday()
    hour = int(scenario["time"].split(":")[0])
    factors = [f"{direction.title()} corridor baseline", "configured corridor risk profile"]
    if hour in (7, 8, 9, 17, 18, 19):
        factors.append("peak-hour travel pattern")
    if day >= 5:
        factors.append("weekend travel period")
    if direction == "OUTBOUND" and day in (4, 5) and hour >= 15:
        factors.append("Friday/Saturday outbound demand")
    if direction == "INBOUND" and day in (6, 0) and hour >= 15:
        factors.append("Sunday/post-holiday inbound demand")
    flags = calendar_flags(scenario)
    if flags["festival"] or flags["holiday"]:
        factors.append("festival/holiday demand")
    if str(scenario.get("weather", "Clear")).lower() == "rain":
        factors.append("rain-related slowdown")
    if scenario.get("roadwork"):
        factors.append("roadwork active")
    return factors


def _model():
    global _SPARK, _MODEL, _MODEL_LOADED, _MODEL_ERROR
    if _MODEL_LOADED:
        return _MODEL
    _MODEL_LOADED = True
    if not MODEL_PATH.exists():
        return None
    try:
        hadoop_home = ROOT / "tools" / "hadoop"
        if (hadoop_home / "bin").exists():
            os.environ.setdefault("HADOOP_HOME", str(hadoop_home))
            os.environ["PATH"] = str(hadoop_home / "bin") + os.pathsep + os.environ.get("PATH", "")
        os.environ["PYSPARK_PYTHON"] = sys.executable
        os.environ["PYSPARK_DRIVER_PYTHON"] = sys.executable
        from pyspark.ml import PipelineModel
        from pyspark.sql import SparkSession
        from py4j.protocol import Py4JJavaError
        _SPARK = (SparkSession.builder.master("local[*]").appName("smart-mobility-api")
                  .config("spark.pyspark.python", sys.executable)
                  .config("spark.pyspark.driver.python", sys.executable)
                  .config("spark.python.worker.reuse", "true").getOrCreate())
        _MODEL = PipelineModel.load(str(MODEL_PATH))
        return _MODEL
    except (OSError, RuntimeError, ValueError, Py4JJavaError) as exc:
        _MODEL_ERROR = exc
        if _fallback_enabled():
            return None
        raise RuntimeError("Persisted Spark model could not be loaded.") from exc


def _fallback_score(features: dict[str, float]) -> float:
    score = 0.20 + features["traffic_capacity_ratio"] * 0.55
    score += 0.10 * features["is_holiday"] + 0.10 * features["is_festival"]
    score += 0.08 * features["is_rain"] + 0.09 * features["roadwork"]
    return max(0.04, min(0.96, score))


def predict_corridor(scenario: dict[str, Any], corridor: str, direction: str | None = None) -> dict[str, Any]:
    direction = direction or CORRIDORS[corridor]["typical_direction"]
    features = future_features(scenario, corridor, direction)
    model = _model()
    mode = "spark_mllib"
    probability_high: float | None = None
    if model is not None:
        from pyspark.sql import functions as F
        row = _SPARK.range(1).select(
            *[F.lit(value).alias(name) for name, value in features.items()],
            F.lit(corridor).alias("corridor"), F.lit(direction).alias("direction"),
        )
        try:
            from pyspark.ml.functions import vector_to_array
            result = model.transform(row).select(vector_to_array("probability").alias("probability")).first()
            probabilities = [float(value) for value in result["probability"]]
            severity_score = sum(index * value for index, value in enumerate(probabilities)) / 2.0
            probability_high = probabilities[2] if len(probabilities) > 2 else None
        except Exception as exc:
            if not _fallback_enabled():
                raise RuntimeError(
                    "Persisted Spark model inference failed. Development fallback is disabled."
                ) from exc
            mode = "development_fallback"
            severity_score = _fallback_score(features)
    elif _fallback_enabled():
        mode = "development_fallback"
        severity_score = _fallback_score(features)
    else:
        reason = f" ({_MODEL_ERROR})" if _MODEL_ERROR else ""
        raise RuntimeError("Persisted Spark model inference failed. Development fallback is disabled." + reason)
    risk = _level(severity_score)
    context = scenario_context(scenario)
    return {
        "corridor": corridor, "direction": direction,
        "severity_score": round(severity_score, 3),
        "congestion_severity_score": round(severity_score, 3),
        "probability_high": round(probability_high, 3) if probability_high is not None else None,
        "congestion_level": risk,
        "predicted_level": risk,
        "risk": risk, "factors": _factors(scenario, corridor, direction),
        "prediction_source": mode, "action": "Normal monitoring",
        **context,
    }


def scenario_predictions(scenario: dict[str, Any]) -> list[dict[str, Any]]:
    direction = scenario.get("direction")
    return [
        predict_corridor(
            scenario,
            name,
            direction if direction in {"OUTBOUND", "INBOUND"} else None,
        )
        for name in CORRIDORS
    ]
