import argparse, json, random
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
with (ROOT / "config" / "corridors.json").open(encoding="utf-8") as handle:
    CORRIDORS = json.load(handle)


def generate(rows: int = 250_000) -> Path:
    random.seed(42)
    start = date(2024, 1, 1)
    output = ROOT / "data" / "raw" / "mobility.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    fields = ["date", "hour", "corridor", "direction", "day_of_week", "is_weekend", "is_friday", "is_saturday",
              "is_sunday", "festival", "is_festival", "is_holiday", "weather", "roadwork", "incident_count",
              "traffic_volume", "average_speed", "road_capacity", "travel_demand", "congestion_index", "congestion_level"]
    with output.open("w", encoding="utf-8", newline="") as handle:
        handle.write(",".join(fields) + "\n")
        for index in range(rows):
            day = start + timedelta(days=index % 1096)
            hour = index % 24
            corridor = list(CORRIDORS)[index % len(CORRIDORS)]
            config = CORRIDORS[corridor]
            direction = config["typical_direction"] if index % 5 else "LOCAL"
            weekend = day.weekday() >= 5
            festival = index % 41 == 0
            holiday = festival or index % 67 == 0
            rain = index % 11 == 0
            roadwork = index % 29 == 0
            peak = 0.30 if hour in (8, 9, 17, 18, 19) else 0.08
            demand = 0.55 + peak + (0.12 if weekend else 0) + (0.12 if festival else 0) + random.uniform(-.06, .06)
            volume = int(config["baseline_capacity"] * demand * config["relative_risk"])
            incidents = 1 if index % 37 == 0 else 0
            congestion = min(.99, max(.02, volume / config["baseline_capacity"] * .55 + incidents * .10 + roadwork * .10 + rain * .08))
            speed = round(config["baseline_speed"] * (1 - congestion * .62), 2)
            level = "HIGH" if congestion >= .67 else "MEDIUM" if congestion >= .42 else "LOW"
            values = [str(day), str(hour), corridor, direction, str(day.weekday()), str(int(weekend)), str(int(day.weekday() == 4)),
                      str(int(day.weekday() == 5)), str(int(day.weekday() == 6)), str(int(festival)), str(int(festival)),
                      str(int(holiday)), "Rain" if rain else "Clear", str(int(roadwork)), str(incidents), str(volume),
                      str(speed), str(config["baseline_capacity"]), f"{demand:.3f}", f"{congestion:.3f}", level]
            handle.write(",".join(values) + "\n")
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=250_000)
    print(generate(parser.parse_args().rows))
