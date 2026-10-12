"""Print persisted validation/test metrics produced by train_model.py."""
import json
from pathlib import Path

metrics = Path(__file__).resolve().parents[1] / "models" / "metrics.json"
if not metrics.exists():
    raise RuntimeError("Run spark\\train_model.py first.")
print(json.dumps(json.loads(metrics.read_text(encoding="utf-8")), indent=2))
