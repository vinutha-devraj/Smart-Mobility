from datetime import date
from typing import Any, Literal
from pydantic import BaseModel, Field, field_validator


class ScenarioRequest(BaseModel):
    date: date
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    source: str = Field(default="Bengaluru", min_length=1)
    destination: str = Field(default="Tumakuru", min_length=1)
    festival: bool = False
    holiday: bool = False
    weather: str = "Clear"
    roadwork: bool = False
    direction: Literal["AUTO", "OUTBOUND", "INBOUND"] = "AUTO"
    scenario_mode: Literal["CALENDAR", "MANUAL"] = "MANUAL"
    source_coordinates: list[float] | None = Field(default=None, min_length=2, max_length=2)
    destination_coordinates: list[float] | None = Field(default=None, min_length=2, max_length=2)

    @field_validator("time")
    @classmethod
    def validate_time(cls, value: str) -> str:
        hour, minute = (int(part) for part in value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("time must be a valid 24-hour time")
        return value

    @field_validator("weather")
    @classmethod
    def validate_weather(cls, value: str) -> str:
        normalized = value.strip().title()
        if normalized not in {"Clear", "Cloudy", "Rain", "Unknown"}:
            raise ValueError("weather must be Clear, Cloudy, Rain, or Unknown")
        return normalized

    @field_validator("source_coordinates", "destination_coordinates")
    @classmethod
    def validate_coordinates(cls, value: list[float] | None) -> list[float] | None:
        if value is None:
            return value
        latitude, longitude = value
        if not -90 <= latitude <= 90 or not -180 <= longitude <= 180:
            raise ValueError("coordinates must be [latitude, longitude] within valid geographic bounds")
        return value


class Prediction(BaseModel):
    corridor: str
    direction: str
    severity_score: float
    probability_high: float | None
    prediction_source: str
    risk: str
    factors: list[str]
    action: str


class RouteOption(BaseModel):
    route_id: str = ""
    name: str
    corridors: list[str]
    approximate_corridors: list[str] = Field(default_factory=list)
    corridor_status: Literal["matched", "approximate", "unmatched"] = "unmatched"
    distance_km: float
    base_duration_minutes: float
    adjusted_duration_minutes: float
    congestion_severity_score: float | None
    predicted_level: str = "UNAVAILABLE"
    probability_high: float | None
    route_source: str
    mapping_note: str
    risk: str
    score: float
    recommendation: str
    selected: bool = False
    rank: int | None = None
    explanation: str = ""
    geometry: list[list[float]]
    source_coordinates: list[float] | None = None
    destination_coordinates: list[float] | None = None
    shared_segment_ratio: float | None = None
    overlap_note: str = ""


class RouteResponse(BaseModel):
    recommended_route: RouteOption
    alternatives: list[RouteOption]
    explanation: list[str]
    scenario: dict[str, Any]
