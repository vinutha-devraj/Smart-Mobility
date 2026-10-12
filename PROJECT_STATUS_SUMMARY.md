# Smart Mobility Bengaluru — Project Status Summary

**Audit type:** Read-only technical audit  
**Audit date:** 2026-10-08  
**Project root:** `C:\Users\vinus\OneDrive\Desktop\BDA`

## 1. Executive Summary

This project is a functional academic prototype for predictive traffic analytics and congestion-aware route advisory in Bengaluru. It combines:

- synthetic mobility-data generation
- Spark SQL preprocessing and analytics
- Spark MLlib model training and persistence
- FastAPI prediction and route endpoints
- OSRM/Nominatim route retrieval
- prototype corridor associations
- deterministic authority advisory rules
- React/Vite frontend screens

The principal demonstrated flow is implemented:

```text
Future user scenario
→ new feature vector
→ persisted Spark MLlib PipelineModel
→ corridor congestion predictions
→ OSRM candidate routes
→ configured prototype corridor associations
→ congestion-adjusted route comparison
→ recommended route
→ advisory generated from the same prediction list
```

The strongest evidence is the persisted Spark pipeline and the passing real Spark integration test. The project is demoable as an academic prototype, but it is not a production traffic system. The original audit identified several weaknesses; the controlled implementation update below addresses the highest-priority semantics and presentation issues. Remaining limitations are:

1. the synthetic target is generated from variables closely related to the model features, producing near-perfect but non-real-world metrics;
2. corridor association uses approximate representative points, not GPS-level road-segment matching;
3. route scoring remains heuristic and external OSRM/Nominatim services can fail;
4. the frontend route map is a prototype geometry view, not live traffic visualization.

## 2. Original Idea vs Current Implementation

| Intended feature | Current implementation | Status | Evidence |
|---|---|---|---|
| Future journey input | Date, time, source, destination, festival, holiday, weather, and roadwork are accepted by `ScenarioRequest`. | DONE | `backend/app/models/schemas.py` |
| Future scenario feature generation | `future_features()` creates a new row from the request instead of selecting a historical row. | DONE | `backend/app/services/prediction.py` |
| Spark MLlib prediction | Persisted Spark `PipelineModel` is loaded and transformed for API inference. | DONE, with fallback caveat | `backend/app/services/prediction.py`, `models/spark_best` |
| Persisted model | Spark pipeline artifact contains `VectorAssembler` and `LogisticRegression` stages. | DONE | `models/spark_best/stages` |
| Candidate route generation | Nominatim geocodes locations and OSRM requests alternatives. | DONE, externally dependent | `backend/app/services/routing.py` |
| Corridor mapping | Routes are assigned configured prototype corridor lists by route index. | PARTIAL | `backend/app/services/routing.py` |
| Route-level congestion prediction | Corridor predictions are aggregated into route scores. | PARTIAL | `backend/app/services/routing.py` |
| Route comparison | Candidate routes expose distance, base duration, adjusted duration, risk, and score. | DONE as a prototype | `backend/app/services/routing.py` |
| Best-route recommendation | Lowest calculated route score is selected dynamically. | DONE as a prototype | `backend/app/services/routing.py` |
| Authority advisory | High/medium/low counts and deterministic operational actions are returned. | DONE as a prototype | `backend/app/services/advisory.py` |
| Same predictions reused by advisory | `/api/route/recommend` passes its prediction list to both routing and advisory. | DONE for route endpoint | `backend/app/main.py` |
| Analytics | Spark-generated aggregates are persisted to JSON and served by the API. | DONE, descriptive only | `spark/analytics.py`, `data/output/analytics.json` |
| Explainability | Scenario-factor strings are returned. | DONE as a factor layer | `backend/app/services/prediction.py` |
| SHAP explanations | No SHAP implementation was found. | NOT IMPLEMENTED | Source inspection |
| Frontend journey flow | React form and route/advisory/analytics views exist. | DONE as a prototype | `frontend/src/main.jsx` |
| API integration | Frontend calls route, prediction, advisory, and analytics endpoints. | DONE | `frontend/src/main.jsx` |
| Real-time traffic | No live traffic source is used. | NOT IMPLEMENTED | Architecture/source inspection |
| GPS-level corridor matching | No spatial geometry-to-corridor matching exists. | NOT IMPLEMENTED | `backend/app/services/routing.py` |

## 3. Data Pipeline

### Dataset and generation

`generate_mobility_data.py` generates 250,000 synthetic records by default. The raw CSV contains 250,001 lines including its header. Generation begins at `2024-01-01` and covers dates through `2026-12-31` in the current artifact.

The generator includes:

- configured Bengaluru corridors
- corridor direction
- date and hour
- traffic volume
- baseline capacity
- average speed
- festival and holiday indicators
- weather/rain
- roadwork
- incident count
- travel demand
- congestion level

Corridor selection is deterministic by row index. Direction is based on the configured corridor direction, with every fifth row assigned `LOCAL`. Festival, holiday, rain, roadwork, and incident values are also generated by deterministic rules and modular patterns.

### Relationships and realism

The synthetic variables have meaningful directional relationships for a classroom prototype: demand, capacity pressure, incidents, rain, roadwork, and corridor risk increase congestion. However, the target is directly calculated from closely related generated variables. This makes the learning problem close to recovering the generator's formula rather than learning an independently observed traffic process.

The data must therefore be described as **synthetic mobility simulation data**. It is not evidence of actual Bengaluru traffic behavior.

### Preprocessing

`preprocess.py` uses Spark DataFrames/SQL to:

- parse and derive date/time fields;
- calculate weekday/weekend and holiday features;
- derive rain and direction flags;
- calculate traffic-capacity ratios;
- derive corridor risk profiles;
- calculate historical corridor aggregates;
- persist processed data as Parquet.

The processed output is under `data/processed/mobility`.

`historical_corridor_congestion` and `historical_average_speed` are computed, but they are not included in the model's final feature list. This is unnecessary computation and can confuse reviewers about which features actually reach the model.

### Features and target

The model feature order is defined in `spark/feature_engineering.py`:

```text
hour_sin
hour_cos
is_weekend
is_friday
is_saturday
is_sunday
is_pre_holiday
is_post_holiday
is_festival
is_holiday
is_rain
roadwork
incident_count
travel_demand
traffic_capacity_ratio
corridor_risk_profile
direction_outbound
direction_inbound
```

The target is `congestion_level`, represented by the classes `LOW`, `MEDIUM`, and `HIGH`.

### Splitting and leakage

`train_model.py` uses a chronological split:

- 70% training
- 15% validation
- 15% test

The persisted metadata records:

- training period: `2024-01-01` to `2026-02-06`
- validation period: `2026-02-06` to `2026-07-20`
- test period: `2026-07-20` to `2026-12-31`

Chronological splitting is appropriate for the intended future-prediction framing. It does not, however, remove the more fundamental synthetic target leakage: the target is formula-generated from variables that are also supplied to the model.

## 4. Spark Usage

### Spark SQL / Data Processing

Spark is used in `spark/preprocess.py` for parsing, deriving fields, aggregating corridor statistics, and writing Parquet output. This is substantive Spark DataFrame/SQL usage rather than a superficial Spark wrapper.

### Spark MLlib

`train_model.py` trains:

- Logistic Regression
- Decision Tree
- Random Forest

Validation F1 is used to select the best model.

### Spark Pipeline

The selected model is persisted as `models/spark_best`. The artifact contains at least:

- `VectorAssembler`
- `LogisticRegression`

The selected model recorded in metadata is `logistic_regression`.

### Spark Prediction

`backend/app/services/prediction.py` loads the persisted pipeline, creates a one-row future scenario DataFrame, calls `PipelineModel.transform()`, and extracts `prediction` and `probability`. The real integration test confirms one-row persisted-model inference in the supported Python 3.11/PySpark 3.5.4 environment.

### Spark Analytics

`analytics.py` reads processed Spark data and writes `data/output/analytics.json`, containing hourly, weekday/weekend, festival/normal, direction, corridor, traffic-volume, and average-speed aggregates.

Spark is genuinely important to the current project: it performs the main data processing, MLlib training, persisted inference, and analytics generation. The model quality is limited by synthetic data design, not by Spark being merely decorative.

## 5. Machine Learning

### Models and selection

The training script compares Logistic Regression, Decision Tree, and Random Forest. It selects the model with the highest validation F1 and persists the selected full pipeline under `models/spark_best`.

The current selected model is Logistic Regression.

### Setup

- task: multiclass classification
- target: `congestion_level`
- classes: `LOW`, `MEDIUM`, `HIGH`
- features: 18 numeric engineered features
- split: chronological train/validation/test

### Metrics

The persisted metrics report:

| Model | Validation F1 | Test F1 |
|---|---:|---:|
| Logistic Regression | 0.999839 | 0.999867 |
| Decision Tree | 0.983081 | 0.983667 |
| Random Forest | 0.983794 | 0.984426 |

These metrics are valid measurements of the generated synthetic experiment, but they must not be presented as real-world traffic accuracy. There is no real traffic holdout set, no external validation, and the target is constructed from the same underlying factors supplied as features.

### Persisted artifact and metadata

The model artifact exists at `models/spark_best`. `models/metadata.json` records the selected model, class labels, feature ordering, time periods, and metrics. `models/metrics.json` records candidate-model metrics.

### Probability handling

Spark returns a class-probability vector. The prediction service calculates:

```text
sum(class_index * class_probability) / 2
```

This is an expected class-severity position normalized to approximately `[0, 1]`. It is not the probability of `HIGH`, and it is not a calibrated probability that congestion will occur. The implementation now exposes it as `severity_score` / `congestion_severity_score`, and exposes Spark's actual HIGH-class probability separately as `probability_high` when available. Advisory thresholds use the clearly named severity score.

### Genuine new-scenario inference

Yes, the primary inference path performs genuine persisted-model inference for a new scenario when fallback is disabled:

1. `future_features()` builds a new row from the request.
2. `predict_corridor()` loads `PipelineModel`.
3. The service calls `model.transform(df)`.
4. It extracts the Spark prediction and probability vector.
5. It maps the class to `LOW`, `MEDIUM`, or `HIGH`.

No historical row lookup is used in the API prediction path. A deterministic fallback exists and is labeled `development_fallback`, but the environment must explicitly set `ALLOW_DEVELOPMENT_FALLBACK=false` to prevent it from being used for model verification. The default fallback setting remains enabled in code, which is a demo-integrity weakness.

## 6. Model Quality

### Strengths

- Chronological validation is more appropriate than a random split for future scenarios.
- Multiple MLlib classifiers are compared.
- The selected pipeline and metadata are persisted.
- The synthetic generator encodes plausible directional effects.

### Weaknesses

- The target is directly derived from feature-related variables.
- The model can learn the synthetic construction rather than general traffic dynamics.
- No real-world or independently sourced holdout data exists.
- No class-distribution report is exposed in the final metadata.
- No probability calibration analysis is provided.
- Near-perfect F1 is suspiciously high for a traffic prediction task and should be explained as synthetic consistency, not predictive accuracy.
- The generated records are deterministic in several dimensions.

The correct evaluator-facing statement is:

> The metrics demonstrate consistency with the synthetic simulation regime; they do not measure real-world Bengaluru traffic prediction accuracy.

## 7. Future Scenario Prediction

### Complete request path

```text
User form
→ POST /api/predict/scenario or POST /api/route/recommend
→ ScenarioRequest validation
→ future_features()
→ one-row Spark DataFrame
→ persisted PipelineModel.transform()
→ prediction and probability vector
→ class/risk/scenario factors
→ route aggregation
```

### Files and functions

- Request schema: `backend/app/models/schemas.py`, `ScenarioRequest`
- Future feature construction: `backend/app/services/prediction.py`, `future_features()`
- Single-corridor prediction: `backend/app/services/prediction.py`, `predict_corridor()`
- All configured corridor predictions: `backend/app/services/prediction.py`, `scenario_predictions()`
- Route orchestration: `backend/app/main.py`, `route()`

### Input coverage

- Date: parsed as a date and used for weekday/weekend, Friday/Saturday/Sunday, pre-holiday, and post-holiday derivations.
- Time: hour is parsed from the `HH:MM` string and converted to cyclical features.
- Festival: included.
- Holiday: included.
- Weather: only the exact case-insensitive value `Rain` activates the rain flag; arbitrary other strings behave like clear weather.
- Roadwork: included.
- Direction: corridor direction is used; `LOCAL` is encoded implicitly as both outbound and inbound flags being zero.
- Corridor: configured corridor risk profile is used.
- Incident count: approximated from the scenario rules rather than supplied by the user.
- Travel demand: derived from scenario date/time/direction/festival/holiday rules rather than observed future demand.

### Validation limitations

Time validation checks the `HH:MM` pattern but does not reject invalid clock values such as `25:99`. Source and destination are not strongly validated, weather is not an enum, and the API does not enforce that the requested date is in the future.

## 8. Route Recommendation

### Source and destination geocoding

`_geocode()` in `backend/app/services/routing.py` calls public Nominatim. The result depends on internet connectivity, geocoder quality, rate limits, and user-provided place names.

### Candidate routes and OSRM

`_osrm_routes()` calls public OSRM with alternatives enabled. Returned routes provide:

- route geometry
- distance
- base duration

The service then applies model-derived congestion to estimate adjusted duration and route score.

### Corridor mapping

The current mapping is configured as an approximate prototype geometry matcher. The code contains representative points for configured corridors such as:

```text
Tumkur Road prototype association → Tumkur Road, Yeshwanthpur
Mysore Road prototype association → Mysore Road
Outer Ring Road prototype association → Outer Ring Road, Marathahalli
```

For each OSRM route, the nearest representative corridor points are selected from the route coordinates. The actual road network is not intersected with surveyed corridor polylines, so this remains prototype-level, not GPS-level mapping.

### Route-level aggregation

For each associated corridor, the service uses the prediction score and risk. It aggregates those values into a route-level congestion/risk result, then calculates:

```text
adjusted_duration = base_duration × (1 + score × 0.85)
```

The `0.85` adjustment factor is hardcoded and not calibrated against observed travel times. The route score also uses hardcoded weights for adjusted duration, congestion score, distance, and high-risk status.

### Recommendation

The route with the lowest calculated score is selected. Alternatives include their route name, distance, base duration, predicted congestion, risk, adjusted duration, score, and mapping note.

### Explicit conclusion

The system does recommend a route based on model-derived congestion values, but only within the limitations of the prototype corridor assignment. It does **not** genuinely prove that the selected physical OSRM route has the lowest future congestion because OSRM routes are assigned to corridors by index rather than mapped from geometry.

## 9. OSRM

OSRM is used for:

- route geometry
- distance
- base travel duration
- alternative route candidates

Spark MLlib is responsible for congestion prediction. OSRM is not a live traffic provider in this project and does not supply the predicted congestion value.

If OSRM or Nominatim is unavailable, the route service returns an explicit error. It does not present fabricated fallback route records as genuine routes.

## 10. Authority Advisory

### Prediction source

For `/api/route/recommend`, `main.py` obtains the corridor predictions once, passes them to route recommendation, and passes the same list to `build_advisory()`. This satisfies the same-predictions requirement for the main end-to-end route flow.

Standalone `/api/advisory` recomputes predictions for its request. It does not share an object with a previous route request, although it uses the same prediction implementation.

### Risk and actions

The advisory counts HIGH, MEDIUM, and LOW corridors and applies deterministic rules.

HIGH-risk actions include:

- deploy additional traffic personnel
- prepare diversion routes
- issue commuter advisories
- coordinate or pause non-critical roadwork
- enhance incident monitoring during rain

MEDIUM-risk actions include:

- monitor the corridor
- prepare standby personnel
- review diversion readiness

LOW-risk corridors receive normal monitoring.

### Direction and scenario logic

Direction, festival/holiday signals, weekend demand, rain, roadwork, incident count, and corridor risk factors are represented in the prediction factors and advisory actions. These are deterministic rules, not learned operational policy recommendations.

The advisory is therefore a coherent academic rules layer, but not a validated traffic-control system. Its risk thresholds inherit the probability/severity naming problem described above.

## 11. Frontend

### Screens

`frontend/src/main.jsx` implements:

- Plan my journey
- Traffic prediction
- Authority advisory
- Analytics

### Journey form

The primary flow exposes:

- From
- To
- Date
- Time
- Festival
- Holiday
- Weather
- Roadwork

The main action calls `POST /api/route/recommend`.

### Results

The route view displays:

- recommended route
- predicted congestion
- risk
- distance
- adjusted duration
- time saved
- alternatives
- route explanation
- best-route and avoid-if-possible labels

The UI also displays a textual placeholder for route geometry rather than rendering an actual map.

### Advisory and analytics

The advisory view displays risk counts, corridor information, factors, and recommended actions. The analytics view uses Recharts and loads persisted backend analytics.

### Frontend weaknesses

- The model status is now loaded from `/api/health` and the prediction source is shown.
- The frontend now renders returned route geometry in a prototype SVG map; it is not live traffic visualization.
- Error handling is stronger for the main journey request than for prediction, advisory, and analytics requests.
- Loading states are limited or absent.
- No frontend unit, integration, or browser tests were found.
- Mapped JSX elements do not consistently show visible React `key` properties.
- The traffic prediction view reuses some form state without clearly explaining that behavior.

Remaining UI improvements would be request loading states, richer analytics views, and browser-level contract tests.

## 12. Backend/API

The actual FastAPI entry point is `backend/app/main.py`.

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | Reports application/prototype health |
| POST | `/api/predict/scenario` | Predicts all configured corridor risks for a submitted scenario |
| POST | `/api/route/recommend` | Gets candidate routes, predicts corridors, ranks routes, and returns advisory |
| GET | `/api/corridors` | Returns configured corridor names |
| GET | `/api/corridors/risk` | Runs a hardcoded default scenario and returns corridor risks |
| POST | `/api/advisory` | Generates advisory for a submitted scenario |
| GET | `/api/advisory` | Generates advisory using a hardcoded default scenario |
| GET | `/api/analytics` | Loads `data/output/analytics.json` |

### API strengths

- Responsibilities are understandable.
- The main route endpoint returns route results, corridor predictions, and advisory data.
- Prediction provenance is included in backend responses.
- Analytics are served from Spark-generated output.

### API weaknesses

- CORS allows all origins, which is acceptable for a local demo but unsuitable for deployment.
- Exceptions are not centralized into structured API errors.
- Missing model/analytics artifacts can become generic server errors.
- Default advisory endpoints use a fixed scenario dated `2026-10-17`.
- No model-status endpoint reports whether the service is using Spark ML, fallback, or unavailable state.
- Time, weather, source, destination, and future-date validation is incomplete.
- Default fallback is enabled in code through `ALLOW_DEVELOPMENT_FALLBACK` unless explicitly set to false.

## 13. Analytics

Spark analytics are generated in `spark/analytics.py` and persisted to `data/output/analytics.json`.

The artifact contains:

- hourly congestion
- weekday versus weekend congestion
- festival versus normal congestion
- direction congestion
- corridor congestion
- traffic volume
- average speed

The backend serves this artifact through `/api/analytics`, and the frontend renders charts from the response.

The analytics are genuinely generated from processed Spark output rather than hardcoded frontend chart arrays. They are descriptive synthetic-data aggregates, not live operational measurements.

Improvements would include a generation timestamp, source-data row count, schema validation, data-version metadata, dynamic filters, and a clearer distinction between historical descriptive analytics and future model predictions.

## 14. Tests and Verification

### Tests found

- `tests/test_flow.py`
- `tests/test_spark_integration.py`
- `pytest.ini` registers the integration marker.

### Verified successfully

The recorded project verification shows:

```text
4 passed, 1 warning
```

The tests cover:

- future feature construction
- route comparison/recommendation
- advisory generation
- FastAPI route flow
- one-row persisted Spark inference with fallback disabled

The supported environment used for the Spark integration path is Python 3.11 with PySpark 3.5.4.

### Not verified by the existing tests

- geographic correctness of route-to-corridor mapping
- OSRM and Nominatim behavior under service failure
- fallback geometry use
- browser rendering and frontend behavior
- invalid time rejection
- missing-model behavior across all endpoints
- analytics artifact failure behavior
- route-duration calibration
- probability calibration
- real-world traffic accuracy

No frontend automated tests were found. The project has manual demo functionality and source-level verification, but it does not have browser automation evidence.

## 15. Current Strengths

1. The architecture connects data generation, Spark processing, model training, persisted inference, APIs, routing, advisory, analytics, and UI.
2. The persisted MLlib artifact is real and contains a Spark pipeline rather than a placeholder model.
3. The API constructs a new future feature vector instead of retrieving a historical row for the requested future date.
4. Training compares three Spark MLlib classifiers and uses chronological validation.
5. The route endpoint reuses the same prediction list for route scoring and advisory generation.
6. The project clearly discloses synthetic-data and prototype limitations in its documentation.
7. The project includes a real Spark integration test rather than mocking the production inference path.
8. The project demonstrates substantive Spark SQL, MLlib, pipeline persistence, and analytics use.
9. The frontend presents the intended future-input → route-comparison → advisory narrative.

## 16. Current Weaknesses

### Critical

1. **Synthetic target leakage:** the model learns a formula derived from feature-related variables, so near-perfect metrics do not establish traffic prediction validity.
2. **Index-based corridor mapping:** OSRM geometry is not actually associated with the physical corridors used for prediction.
3. **Approximate corridor matching:** representative-point matching is not GPS-level road-segment mapping.

### Important

4. **External-service dependency:** public Nominatim and OSRM calls can fail or be rate-limited.
5. **Hardcoded heuristic route weights:** adjusted duration and scoring factors are not calibrated.
6. **No frontend test coverage:** UI behavior is not automatically verified.

### Minor

11. Analytics lack freshness and provenance metadata.
12. Advisory actions are fixed strings rather than configurable policy rules.
13. Mapped React elements need consistent keys and general polish.
14. Default advisory endpoints use a fixed scenario rather than a user-provided scenario.

## 17. Missing Features

Compared with the intended product idea, the following are missing or only partially implemented:

- GPS/geometry-based road-segment route-to-corridor matching
- live traffic, GPS, camera, or sensor integration
- calibrated congestion probabilities
- independent real-world validation data
- tiled geographic map visualization
- robust structured error handling
- strict date/time/weather validation
- frontend automated tests
- calibrated travel-time adjustment
- validated operational advisory policies
- real-time monitoring or signal-control functionality

These omissions are consistent with an academic prototype and should not be presented as implemented features.

## 18. Recommended Improvements

### Priority 1 — Must Fix

#### Correct prediction field semantics

- **Change:** return class probabilities separately, including `probability_high`, and rename the expected class score to `severity_score`.
- **Why:** prevents a severity index from being presented as a probability.
- **Modules:** `backend/app/services/prediction.py`, schemas, advisory/frontend response handling.
- **Impact:** improves technical correctness and viva defensibility.

#### Replace route-index mapping

- **Change:** associate route geometry with configured corridors using corridor polylines, bounding boxes, nearest-segment calculations, or an explicitly documented geometry-based approximation.
- **Why:** route recommendation currently does not know which physical corridors an OSRM route uses.
- **Module:** `backend/app/services/routing.py`.
- **Impact:** makes route comparison materially more credible.

#### Reduce synthetic target leakage

- **Change:** separate target-generation variables from observable model features, add stochastic/unobserved factors, and evaluate on an independent holdout regime.
- **Why:** near-perfect F1 currently measures reconstruction of the simulator.
- **Modules:** `spark/generate_mobility_data.py`, `spark/feature_engineering.py`, `spark/train_model.py`.
- **Impact:** produces more honest model-quality evidence.

### Priority 2 — Strong Improvement

#### Make production/demo fallback fail-closed

- **Change:** default `ALLOW_DEVELOPMENT_FALLBACK` to false for demo/production, expose mode through health, and display it in the UI.
- **Why:** prevents silent fallback-based demonstrations.
- **Modules:** prediction service, health endpoint, frontend.
- **Impact:** makes model provenance visible and reliable.

#### Verify map rendering and external-route behavior

- **Change:** retain genuine OSRM geometry only, and verify Leaflet rendering and clear routing errors when OSRM fails.
- **Why:** fabricated fallback geometry must not be presented as a real route.
- **Modules:** `backend/app/services/routing.py`, `frontend/src/main.jsx`.
- **Impact:** keeps route output geographically honest and inspectable.

#### Strengthen validation and error handling

- **Change:** validate real clock ranges, non-empty locations, allowed weather values, and structured missing-artifact/external-service errors.
- **Why:** prevents malformed requests from reaching Spark and gives users actionable failures.
- **Modules:** `backend/app/models/schemas.py`, `backend/app/main.py`, routing service, frontend.
- **Impact:** improves reliability.

### Priority 3 — Nice to Have

#### Improve analytics provenance

- **Change:** add generation timestamp, source row count, feature/data version, and UI filters.
- **Why:** makes Spark analytics easier to audit.
- **Modules:** `spark/analytics.py`, analytics API and frontend.
- **Impact:** improves evaluator confidence.

#### Add frontend/browser tests

- **Change:** add tests for form submission, route rendering, advisory rendering, error states, and model-source display.
- **Why:** current UI behavior is unverified.
- **Modules:** frontend test setup and test files.
- **Impact:** reduces demo regressions.

#### Calibrate route scoring

- **Change:** derive duration/scoring weights from a validation policy or document them as configurable prototype parameters.
- **Why:** current weights are arbitrary constants.
- **Module:** `backend/app/services/routing.py`.
- **Impact:** makes ranking more explainable and reproducible.

## 19. Demo Readiness

| Area | Score | Reason |
|---|---:|---|
| Technical correctness | 8/10 | Main flow works and probability/source semantics are explicit; corridor matching remains approximate. |
| Spark usage | 9/10 | Spark SQL, MLlib comparison, persisted pipeline, inference, and analytics are substantive. |
| ML quality | 5/10 | Chronological split and model comparison are good; synthetic leakage makes metrics unreliable for real traffic. |
| Prediction pipeline | 8/10 | New future features reach a persisted PipelineModel when fallback is disabled. |
| Route recommendation | 7/10 | Dynamic scoring and geometry-nearest association exist, but the matcher is prototype-level and external-service dependent. |
| Advisory system | 7/10 | Same predictions are reused in the main route flow, with clear deterministic actions. |
| Frontend | 7/10 | The intended screens, dynamic model status, prediction source, and prototype route geometry view exist; frontend tests are still absent. |
| Analytics | 7/10 | Spark-generated descriptive charts are served dynamically from persisted output. |
| Overall demo readiness | 8/10 | Suitable for a controlled college demonstration with internet access and explicit fallback disabling. |

The project should be demonstrated with:

```powershell
$env:ALLOW_DEVELOPMENT_FALLBACK="false"
```

The presenter should show at least one response containing `prediction_source = "spark_mllib"` and explain the prototype corridor mapping honestly.

## 20. Viva Readiness

### Questions the project can support confidently

- Why is Spark used?
- How is the synthetic dataset generated?
- What preprocessing occurs in Spark?
- Which MLlib models are compared?
- Why is chronological splitting used?
- How is the selected model persisted?
- How is a new future feature vector constructed?
- How does the API call the persisted Spark pipeline?
- What does OSRM provide?
- How are route scores and adjusted durations calculated?
- How does the authority advisory reuse route predictions?
- Why is the project not real-time navigation?
- What are the limitations of synthetic data?

### Questions where the implementation has weaknesses

- Why are the model scores nearly 100%?
- Are the congestion values calibrated probabilities, and what is `probability_high`?
- How do you know which physical corridor an OSRM route uses?
- Is the recommended route guaranteed to be fastest?
- What happens when OSRM or Nominatim is unavailable?
- Does the frontend prove that Spark ML was used?
- What independent real-world data validates the model?
- Why is fallback enabled by default?
- How are route scoring weights calibrated?

The correct answers should acknowledge the synthetic-data, prototype-mapping, probability-semantics, and external-service limitations rather than overstating the system.

## 21. Final Verdict

1. **What is genuinely working?**  
   The project has a coherent and tested academic flow from a future scenario to new feature construction, persisted Spark MLlib inference, route comparison, recommendation, and same-predictions advisory generation.

2. **What is the biggest weakness?**  
   The central route claim is still limited by approximate representative-point corridor matching, while the near-perfect metrics are weakened by synthetic target leakage.

3. **What is the single most important improvement?**  
   Improve the prototype geometry matcher toward corridor polylines and continue to report severity and HIGH-class probability as separate fields.

4. **What would make the project significantly stronger?**  
   Use a less formula-leaky synthetic design or independent real/holdout data, add calibrated probabilities, render actual route geometry, fail closed when Spark is unavailable, and add frontend/API robustness tests.

5. **Is it ready for a college BDA project demonstration?**  
   Yes, as a clearly labeled academic prototype. It is ready for a controlled demonstration when the persisted model is verified, `ALLOW_DEVELOPMENT_FALLBACK=false` is set, and the presenter explicitly explains that data is synthetic, OSRM is not a live traffic source, corridor mapping is prototype-level, and metrics are not real-world accuracy.

### Recommended status wording

> End-to-end academic prototype complete and demoable, with persisted Spark MLlib inference and advisory integration verified by automated tests. Real-world predictive validity, calibrated probabilities, and GPS-level corridor-aware routing remain unimplemented.

## Post-audit implementation update

The controlled improvement pass following this audit implemented the highest-priority presentation and correctness improvements without replacing the Spark architecture:

- expected class severity is now exposed as `severity_score` / `congestion_severity_score`;
- Spark's actual `probability_high` is exposed separately when available;
- fallback now defaults to disabled and returns `development_fallback` only when explicitly enabled;
- `/api/health` reports model availability, model type, prediction source, and fallback status;
- future responses expose transparent travel-surge level, direction, pattern, and explanation;
- route matching now uses approximate geometry-nearest corridor representative points rather than route index;
- the frontend displays prediction source, surge/direction context, route geometry, corridor associations, and synthetic analytics provenance;
- request validation rejects invalid clock values and unsupported weather values;
- Spark analytics now include provenance, Friday/Saturday outbound, Sunday/post-holiday inbound, and day-type-by-hour views;
- tests cover validation, fallback labeling, surge classification, geometry association, and persisted Spark inference.

The implementation remains intentionally honest: representative-point matching is still an academic prototype approximation, route scoring remains heuristic, OSRM/Nominatim remain external services, and synthetic-model metrics are not real-world accuracy.
