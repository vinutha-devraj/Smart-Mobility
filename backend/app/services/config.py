import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
with (ROOT / "config" / "corridors.json").open(encoding="utf-8") as handle:
    CORRIDORS: dict[str, dict] = json.load(handle)
with (ROOT / "config" / "festivals.json").open(encoding="utf-8") as handle:
    FESTIVALS: list[dict] = json.load(handle)
with (ROOT / "config" / "exit_corridors.json").open(encoding="utf-8") as handle:
    EXIT_CORRIDORS: list[dict] = json.load(handle)
