"""Create backend-consumable analytics from the processed Spark dataset."""
import json
from pathlib import Path
import sys
from pyspark.sql import SparkSession, functions as F

ROOT = Path(__file__).resolve().parents[1]
spark = (SparkSession.builder.master("local[*]").appName("smart-mobility-analytics")
         .config("spark.pyspark.python", sys.executable)
         .config("spark.pyspark.driver.python", sys.executable).getOrCreate())
df = spark.read.parquet(str(ROOT / "data" / "processed" / "mobility"))
def rows(frame):
    return [row.asDict() for row in frame.collect()]

date_summary = df.agg(F.min("date").alias("date_start"), F.max("date").alias("date_end"),
                       F.count("*").alias("row_count")).first().asDict()
output = {
    "provenance": {
        "data_source": "Synthetic mobility simulation",
        "purpose": "Academic BDA prototype",
        "processing": "Apache Spark / Spark SQL",
        "prediction": "Spark MLlib",
        "row_count": date_summary["row_count"],
        "date_start": str(date_summary["date_start"]),
        "date_end": str(date_summary["date_end"]),
    },
    "hourly": rows(df.groupBy("hour").agg(F.round(F.avg("congestion_index"), 3).alias("congestion")).orderBy("hour")),
    "weekday_weekend": rows(df.withColumn("category", F.when(F.col("is_weekend") == 1, "Weekend").otherwise("Weekday"))
                             .groupBy("category").agg(F.round(F.avg("congestion_index"), 3).alias("congestion"))),
    "festival_normal": rows(df.withColumn("category", F.when(F.col("is_festival") == 1, "Festival").otherwise("Normal"))
                            .groupBy("category").agg(F.round(F.avg("congestion_index"), 3).alias("congestion"))),
    "direction": rows(df.groupBy("direction").agg(F.round(F.avg("congestion_index"), 3).alias("congestion"))),
    "friday_saturday_outbound": rows(
        df.filter(((F.col("direction") == "OUTBOUND") & (F.col("is_friday") == 1)) |
                  ((F.col("direction") == "OUTBOUND") & (F.col("is_saturday") == 1)))
        .groupBy("hour").agg(F.round(F.avg("congestion_index"), 3).alias("congestion")).orderBy("hour")
    ),
    "sunday_post_holiday_inbound": rows(
        df.filter(((F.col("direction") == "INBOUND") & (F.col("is_sunday") == 1)) |
                  ((F.col("direction") == "INBOUND") & (F.col("is_post_holiday") == 1)))
        .groupBy("hour").agg(F.round(F.avg("congestion_index"), 3).alias("congestion")).orderBy("hour")
    ),
    "day_type_hour": rows(
        df.withColumn("day_type", F.when(F.col("is_weekend") == 1, "Weekend").otherwise("Weekday"))
        .groupBy("day_type", "hour")
        .agg(F.round(F.avg("congestion_index"), 3).alias("congestion"))
        .orderBy("day_type", "hour")
    ),
    "corridors": rows(df.groupBy("corridor").agg(F.round(F.avg("congestion_index"), 3).alias("congestion"),
                                                 F.round(F.avg("traffic_volume"), 1).alias("traffic_volume"),
                                                 F.round(F.avg("average_speed"), 1).alias("average_speed"))
                    .orderBy(F.desc("congestion"))),
}
(ROOT / "data" / "output").mkdir(parents=True, exist_ok=True)
(ROOT / "data" / "output" / "analytics.json").write_text(json.dumps(output), encoding="utf-8")
spark.stop()
