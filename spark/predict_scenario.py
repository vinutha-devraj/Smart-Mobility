import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from backend.app.services.prediction import scenario_predictions

scenario = {
    "date": "2026-10-17", "time": "17:00", "festival": True,
    "holiday": True, "weather": "Rain", "roadwork": False,
}
for prediction in scenario_predictions(scenario):
    print(prediction)
