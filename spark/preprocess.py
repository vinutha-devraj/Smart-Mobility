from pathlib import Path
import sys
from pyspark.sql import SparkSession, Window, functions as F

ROOT = Path(__file__).resolve().parents[1]
spark = (SparkSession.builder.master("local[*]").appName("smart-mobility-preprocess")
         .config("spark.pyspark.python", sys.executable)
         .config("spark.pyspark.driver.python", sys.executable).getOrCreate())
df = spark.read.option("header", True).option("inferSchema", True).csv(str(ROOT / "data" / "raw" / "mobility.csv"))
processed = (
    df.withColumn("hour_sin", F.sin(2 * F.lit(3.1415926535) * F.col("hour") / 24))
    .withColumn("hour_cos", F.cos(2 * F.lit(3.1415926535) * F.col("hour") / 24))
    .withColumn("is_pre_holiday", (F.col("is_friday") * F.col("is_holiday")).cast("double"))
    .withColumn("is_post_holiday", (F.col("is_sunday") * F.col("is_holiday")).cast("double"))
    .withColumn("is_rain", (F.col("weather") == "Rain").cast("double"))
    .withColumn("direction_outbound", (F.col("direction") == "OUTBOUND").cast("double"))
    .withColumn("direction_inbound", (F.col("direction") == "INBOUND").cast("double"))
    .withColumn("travel_demand", F.col("travel_demand").cast("double"))
    .withColumn("traffic_capacity_ratio", F.col("traffic_volume") / F.col("road_capacity"))
    .withColumn("corridor_risk_profile", F.col("traffic_volume") / F.col("road_capacity"))
    .withColumn("historical_corridor_congestion",
                F.avg("congestion_index").over(Window.partitionBy("corridor")))
    .withColumn("historical_average_speed",
                F.avg("average_speed").over(Window.partitionBy("corridor")))
)
processed.write.mode("overwrite").parquet(str(ROOT / "data" / "processed" / "mobility"))
spark.stop()
