"""Train and evaluate Spark MLlib models with chronological date splits."""
import json
import sys
import setuptools._distutils as _distutils
from setuptools._distutils import version as _distutils_version
sys.modules.setdefault("distutils", _distutils)
sys.modules.setdefault("distutils.version", _distutils_version)
from pathlib import Path
 
from pyspark.sql import SparkSession, functions as F
from pyspark.ml import Pipeline
from pyspark.ml.classification import DecisionTreeClassifier, LogisticRegression, RandomForestClassifier
from pyspark.ml.evaluation import MulticlassClassificationEvaluator
from pyspark.ml.feature import VectorAssembler
from feature_engineering import FEATURES, CATEGORICAL_FEATURES

ROOT = Path(__file__).resolve().parents[1]
MODEL_DIR = ROOT / "models"
MODEL_DIR.mkdir(exist_ok=True)
spark = (SparkSession.builder.master("local[*]").appName("smart-mobility-training")
         .config("spark.pyspark.python", sys.executable)
         .config("spark.pyspark.driver.python", sys.executable).getOrCreate())
df = spark.read.parquet(str(ROOT / "data" / "processed" / "mobility")).withColumn("date", F.to_date("date"))
df = df.withColumn("label", F.when(F.col("congestion_level") == "LOW", 0.0)
                  .when(F.col("congestion_level") == "MEDIUM", 1.0).otherwise(2.0))
dates = [row.date for row in df.select("date").distinct().orderBy("date").collect()]
if len(dates) < 10:
    raise RuntimeError("Need at least 10 distinct dates for chronological train/validation/test splits.")
train_end, validation_end = dates[int(len(dates) * 0.70)], dates[int(len(dates) * 0.85)]
train = df.filter(F.col("date") < train_end)
validation = df.filter((F.col("date") >= train_end) & (F.col("date") < validation_end))
test = df.filter(F.col("date") >= validation_end)

assembler = VectorAssembler(inputCols=FEATURES,
                            outputCol="features", handleInvalid="keep")
classifiers = {
    "logistic_regression": LogisticRegression(featuresCol="features", labelCol="label", maxIter=50),
    "decision_tree": DecisionTreeClassifier(featuresCol="features", labelCol="label", maxDepth=8),
    "random_forest": RandomForestClassifier(featuresCol="features", labelCol="label", numTrees=40, maxDepth=10),
}
metrics = {}
evaluator_names = ["accuracy", "weightedPrecision", "weightedRecall", "f1"]
for name, classifier in classifiers.items():
    pipeline = Pipeline(stages=[assembler, classifier]).fit(train)
    validation_predictions = pipeline.transform(validation).cache()
    test_predictions = pipeline.transform(test).cache()
    metrics[name] = {
        "validation": {metric: MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName=metric).evaluate(validation_predictions)
                       for metric in evaluator_names},
        "test": {metric: MulticlassClassificationEvaluator(labelCol="label", predictionCol="prediction", metricName=metric).evaluate(test_predictions)
                 for metric in evaluator_names},
        "confusion_matrix": test_predictions.groupBy("label", "prediction").count().orderBy("label", "prediction").collect(),
    }
    validation_predictions.unpersist()
    test_predictions.unpersist()
best_name = max(metrics, key=lambda name: metrics[name]["validation"]["f1"])
best_pipeline = Pipeline(stages=[assembler, classifiers[best_name]]).fit(train.union(validation))
best_pipeline.write().overwrite().save(str(MODEL_DIR / "spark_best"))
serializable = {name: {split: values for split, values in result.items() if split != "confusion_matrix"}
                for name, result in metrics.items()}
(MODEL_DIR / "metrics.json").write_text(json.dumps(serializable, indent=2), encoding="utf-8")
(MODEL_DIR / "metadata.json").write_text(json.dumps({
    "model_type": best_name, "training_period": [str(dates[0]), str(train_end)],
    "validation_period": [str(train_end), str(validation_end)],
    "test_period": [str(validation_end), str(dates[-1])],
    "features": FEATURES, "categorical_features": CATEGORICAL_FEATURES,
    "class_labels": ["LOW", "MEDIUM", "HIGH"], "metrics": serializable[best_name],
}, indent=2), encoding="utf-8")
print(json.dumps({"selected_model": best_name, "metrics": serializable[best_name]}, indent=2))
spark.stop()
