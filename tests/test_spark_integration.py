import os
from pathlib import Path

import pytest

from backend.app.services.prediction import predict_corridor


pytestmark = pytest.mark.integration


@pytest.mark.skipif(
    not (Path("models") / "spark_best").exists(),
    reason="Persisted Spark model is not available; run the Spark pipeline first.",
)
def test_one_row_future_spark_inference():
    root = Path(__file__).resolve().parents[1]
    os.environ.setdefault("HADOOP_HOME", str(root / "tools" / "hadoop"))
    os.environ["PATH"] = str(root / "tools" / "hadoop" / "bin") + os.pathsep + os.environ.get("PATH", "")
    os.environ["ALLOW_DEVELOPMENT_FALLBACK"] = "false"
    result = predict_corridor(
        {
            "date": "2026-10-17",
            "time": "17:00",
            "festival": True,
            "holiday": True,
            "weather": "Rain",
            "roadwork": False,
        },
        "Tumkur Road",
        "OUTBOUND",
    )
    assert result["prediction_source"] == "spark_mllib"
    assert result["congestion_level"] in {"LOW", "MEDIUM", "HIGH"}
    assert 0 <= result["severity_score"] <= 1
    assert result["probability_high"] is None or 0 <= result["probability_high"] <= 1
