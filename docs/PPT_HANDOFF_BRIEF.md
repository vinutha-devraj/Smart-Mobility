# PPT Handoff Brief

## Project

**Smart Mobility: Predictive Traffic Analytics & Congestion-Aware Route Advisory System for Bengaluru**

This brief is for preparing a 12–15 slide college presentation. Every claim below should be presented as an academic prototype result based on synthetic mobility simulation data.

## Recommended 14-slide sequence

### Slide 1 — Title and motivation

**Purpose:** Introduce the project and city context.

**Key points:**

- Predictive traffic analytics for future scenarios.
- Congestion-aware route assessment.
- Authority advisory from scenario predictions.
- Bengaluru-oriented academic prototype.

**Visual:** Project title, Bengaluru map image or project UI screenshot.

**Verified artifact:** `README.md`, frontend dashboard.

**Caveat:** Do not call it live traffic navigation.

### Slide 2 — Problem definition

**Purpose:** Explain why scenario-aware congestion matters.

**Key points:**

- Congestion varies by time, weekday, events, weather, roadwork, and direction.
- Weekend/festival outbound travel and post-holiday inbound travel are explicit scenarios.
- A future scenario should produce a reproducible risk estimate.

**Visual:** Scenario factors → congestion risk diagram.

**Artifact:** `prediction.py` scenario context and future feature construction.

**Caveat:** Motivation is not proof of real city-wide patterns.

### Slide 3 — Objectives and scope

**Purpose:** Define what the system does and does not do.

**Key points:**

- Generate/process synthetic mobility data.
- Train and persist Spark MLlib classification.
- Predict future scenarios.
- Assess OSRM routes and produce advisory.
- Present results through FastAPI and React.

**Visual:** In-scope/out-of-scope two-column list.

**Caveat:** Exclude GPS, cameras, sensors, signal control, and live traffic claims.

### Slide 4 — Dataset

**Purpose:** Establish data provenance.

**Key points:**

- `data/raw/mobility.csv`.
- 250,000 rows and 21 columns.
- Dates from 2024-01-01 to 2026-12-31.
- Synthetic records generated with seed 42.
- Target: LOW, MEDIUM, HIGH congestion level.

**Visual:** CSV header/schema screenshot and a small sample.

**Artifact:** `generate_mobility_data.py`, raw CSV header.

**Caveat:** Metrics describe the simulation process, not real-world accuracy.

### Slide 5 — Spark data pipeline

**Purpose:** Show the Big Data processing workflow.

**Key points:**

- Spark reads the CSV and writes processed Parquet.
- Spark derives features and corridor aggregates.
- Spark SQL/DataFrame aggregations create analytics.
- The pipeline runs locally with `local[*]`.

**Visual:** Mermaid-style pipeline: CSV → Spark SQL → Parquet → analytics/model.

**Artifact:** `preprocess.py`, `analytics.py`, `data/output/analytics.json`.

**Caveat:** No production Spark cluster or HDFS is implemented.

### Slide 6 — Feature engineering

**Purpose:** Explain how raw fields become model inputs.

**Key points:**

- Cyclical hour: `hour_sin`, `hour_cos`.
- Calendar and event flags.
- Weather, roadwork, incidents.
- Demand, capacity ratio, corridor risk.
- Outbound/inbound direction flags.

**Visual:** Feature groups diagram.

**Artifact:** `spark/feature_engineering.py`, `models/metadata.json`.

**Caveat:** Synthetic label construction is closely related to several inputs.

### Slide 7 — ML methodology

**Purpose:** Explain training and selection.

**Key points:**

- Multiclass classification: LOW/MEDIUM/HIGH.
- Candidates: Logistic Regression, Decision Tree, Random Forest.
- Chronological train/validation/test split.
- Selection by validation F1.
- Persisted model: Logistic Regression.

**Visual:** Candidate model comparison table.

**Artifact:** `models/metrics.json`, `train_model.py`.

**Caveat:** Selected model is not externally validated.

### Slide 8 — Evaluation results

**Purpose:** Present exact saved metrics.

**Key points:**

- Logistic Regression test accuracy: `0.999867`.
- Logistic Regression test F1: `0.999867`.
- Decision Tree test F1: `0.983667`.
- Random Forest test F1: `0.984426`.
- Test period follows the chronological split.

**Visual:** Bar chart of test F1 by model.

**Artifact:** `models/metrics.json`.

**Caveat:** Explain synthetic dependency and possible leakage-like behavior immediately.

### Slide 9 — Future scenario inference

**Purpose:** Show the actual prediction path.

**Key points:**

- User selects future date/time, journey, events, weather, and roadwork.
- Backend builds a new feature vector.
- Persisted PipelineModel performs one-row Spark inference.
- Output includes predicted level, severity score, HIGH probability, and source.

**Visual:** Form → feature vector → Spark PipelineModel → prediction.

**Artifact:** `/api/predict/scenario` response and `prediction.py`.

**Caveat:** This is scenario-based prediction, not live forecasting.

### Slide 10 — Geocoding and OSRM routing

**Purpose:** Clarify external routing responsibilities.

**Key points:**

- Nominatim resolves and validates Karnataka, India locations.
- OSRM returns driving geometry, base distance, and base duration.
- Leaflet renders actual OSRM geometry on OpenStreetMap tiles.
- OSRM does not provide Spark congestion prediction.

**Visual:** Nominatim → OSRM → Leaflet diagram.

**Artifact:** `/api/route/recommend` response and map screenshot.

**Caveat:** OSRM base duration is not live traffic duration.

### Slide 11 — Route recommendation

**Purpose:** Explain route scoring.

**Key points:**

- Route geometry is associated with approximate corridor representative points.
- Associated corridor predictions are reused from the scenario cache.
- Adjusted duration and heuristic score combine route and congestion values.
- Lowest score becomes the recommended route.
- Only routes actually returned by OSRM are shown.

**Visual:** Route map plus score formula.

**Artifact:** `routing.py`, route response.

**Caveat:** Corridor matching is prototype-level and alternatives are not guaranteed.

### Slide 12 — Authority advisory

**Purpose:** Show how authorities use the same prediction results.

**Key points:**

- Same scenario predictions feed route assessment and advisory.
- HIGH/MEDIUM/LOW rules rank priority corridors.
- Example actions include monitoring, diversion preparation, and commuter advisory.
- Actions are deterministic rules.

**Visual:** Prediction list → risk ranking → advisory card.

**Artifact:** `advisory.py`, route response `advisory` field.

**Caveat:** No automatic operational control is performed.

### Slide 13 — Working demo

**Purpose:** Demonstrate the complete integrated flow.

**Key points:**

- From Bengaluru to Tumakuru.
- 17 October 2026 at 5:00 PM.
- Festival and holiday: Yes.
- Weather: Rain; roadwork can be selected for a stronger scenario.
- Verify Spark source and fallback disabled.

**Visual:** Journey form, Leaflet map, recommendation, advisory screenshots.

**Artifact:** Fresh browser and `/api/health` screenshots.

**Caveat:** Capture results from the current run; do not reuse an unverified browser state.

### Slide 14 — Limitations and conclusion

**Purpose:** End honestly and identify future work.

**Key points:**

- Synthetic data and no real-world validation.
- Approximate corridor matching.
- External Nominatim/OSRM dependence.
- Local Spark prototype, not production-scale deployment.
- Future work: real data, calibrated validation, precise road segments, stronger route alternatives.

**Visual:** Completed versus future-work matrix.

**Artifact:** Project summary limitations section and README.

**Caveat:** Do not present future enhancements as implemented.

## Suggested speaking points

### Introduction

“Our project is an academic decision-support prototype for Bengaluru-oriented traffic scenarios. It does not observe live traffic. Instead, it generates a reproducible synthetic mobility dataset, trains Spark MLlib models, and allows a user to test how a future scenario may affect congestion risk and route assessment.”

### Methodology

“Spark reads and transforms the mobility records, creates cyclical time and scenario features, and produces analytics. We compare Logistic Regression, Decision Tree, and Random Forest using chronological splits. Logistic Regression is selected by validation F1 and persisted as a Spark PipelineModel.”

### Results

“The saved test F1 for Logistic Regression is approximately 0.999867. Because the target is generated from rules closely related to the features, this shows consistency with the simulator, not proven real-world Bengaluru accuracy.”

### Demo

“The user enters a future journey. FastAPI builds a new feature vector and calls the persisted Spark model. Nominatim resolves the places, OSRM supplies route geometry and base route data, Leaflet displays the actual geometry, and the route score uses the model's corridor risk.”

### Advisory

“The authority advisory consumes the same scenario prediction list used for route evaluation. It applies transparent deterministic rules to identify high-priority corridors and example actions.”

### Limitations

“The main limitations are synthetic data, no live measurements, approximate corridor matching, external-service availability, limited route alternatives, and local rather than production-scale deployment.”

### Conclusion

“The contribution is the integration of Spark processing, persisted ML inference, external route geometry, route assessment, and advisory presentation in one reproducible academic workflow.”

## Short abstract

Smart Mobility is an academic predictive traffic analytics and congestion-aware route advisory prototype for Bengaluru-oriented travel scenarios. The system generates a repeatable synthetic mobility dataset containing time, corridor, direction, weather, event, roadwork, incident, demand, capacity, speed, and congestion attributes. Apache Spark and Spark SQL process the data and produce analytical aggregates. Spark MLlib compares Logistic Regression, Decision Tree, and Random Forest classifiers using chronological train, validation, and test periods; the selected Logistic Regression pipeline is persisted for future inference. A FastAPI service converts a user-selected future scenario into a new feature vector and returns congestion classes, severity, and HIGH-class probability. Nominatim resolves validated Karnataka locations, OSRM supplies actual route geometry and base route information, and a prototype corridor association supports route scoring. A React/Vite interface with Leaflet and OpenStreetMap presents the route, prediction, analytics, and rule-based authority advisory. The project is not live navigation: its dataset is synthetic, its metrics are not real-world validation, OSRM is not a traffic predictor, and corridor matching remains approximate.

## Technology stack

| Technology | Verified use |
|---|---|
| Python 3.11 | Project runtime |
| PySpark 3.5.4 | Spark processing and ML integration |
| Apache Spark local mode | DataFrames, SQL-style transforms, Parquet, MLlib |
| Spark SQL/DataFrames | Preprocessing and analytics |
| Spark MLlib | Logistic Regression, Decision Tree, Random Forest |
| FastAPI | Backend API |
| Pydantic | Request validation |
| React | Frontend interface |
| Vite | Frontend development/build |
| Leaflet / React Leaflet | Interactive route map |
| OpenStreetMap | Map tile layer |
| Nominatim | Place geocoding |
| OSRM | Driving route geometry/base route data |

## Facts that must not be exaggerated

- The data is synthetic.
- OSRM does not provide the project's congestion prediction.
- OSRM base duration is not live traffic duration.
- Spark runs locally; no production cluster is demonstrated.
- High metrics do not establish real-world Bengaluru accuracy.
- Corridor association uses approximate representative points.
- Multiple route alternatives are not guaranteed.
- The advisory is rule-based and does not control field operations.
- The system does not use GPS, cameras, sensors, or live traffic feeds.
- A successful frontend build is not the same as a captured browser-runtime demonstration.

## Evidence/screenshots to request from the developer

1. Fresh `/api/health` response with `fallback_enabled=false`.
2. `/api/predict/scenario` response showing `prediction_source=spark_mllib`.
3. `/api/route/recommend` response showing geocoding, OSRM geometry, route source, corridor predictions, and advisory.
4. Browser screenshot of the Leaflet map with source/destination markers.
5. Browser screenshot of the recommended route card.
6. Browser screenshot of the authority advisory.
7. Browser screenshot of Spark analytics charts.
8. Terminal output from Spark preprocessing/training/evaluation.
9. Model comparison chart created from `models/metrics.json`.
10. Raw CSV header/sample and processed Parquet evidence.

## Final handoff note

The presentation is demo-ready as an academic prototype if the presenter uses the supported local environment, confirms the persisted model is available, disables development fallback, captures fresh browser/API evidence, and states the synthetic-data and routing limitations clearly.
