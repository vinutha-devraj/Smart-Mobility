# Smart Mobility — Demo Run Guide

## 1. Project Setup

Open PowerShell and enter the project root:

```powershell
cd C:\Users\vinus\OneDrive\Desktop\BDA
```

## 2. Activate Environment

Activate the project-local Python 3.11 environment:

```powershell
.\.venv\Scripts\Activate.ps1
python --version
python -c "import pyspark; print('PySpark', pyspark.__version__)"
```

Expected versions:

```text
Python 3.11.x
PySpark 3.5.4
```

## 3. Spark / Hadoop Environment

The project runs Spark locally on Windows. It does not require HDFS.

```powershell
$env:HADOOP_HOME="$PWD\tools\hadoop"
$env:PATH="$env:HADOOP_HOME\bin;$env:PATH"
$env:PYSPARK_PYTHON=(Get-Command python).Source
$env:PYSPARK_DRIVER_PYTHON=$env:PYSPARK_PYTHON
$env:ALLOW_DEVELOPMENT_FALLBACK="false"
```

Confirm the important settings:

```powershell
Write-Host "HADOOP_HOME=$env:HADOOP_HOME"
Write-Host "PYSPARK_PYTHON=$env:PYSPARK_PYTHON"
Write-Host "ALLOW_DEVELOPMENT_FALLBACK=$env:ALLOW_DEVELOPMENT_FALLBACK"
Test-Path "$env:HADOOP_HOME\bin\winutils.exe"
Test-Path "$env:HADOOP_HOME\bin\hadoop.dll"
```

The last two commands should return `True`.

## 4. Verify Existing Model

The trained Spark model already exists. Verify the model directory and its metadata:

```powershell
Test-Path .\models\spark_best
Test-Path .\models\metadata.json
Test-Path .\models\metrics.json
Get-ChildItem .\models\spark_best -Recurse -File
Get-Content .\models\metadata.json
Get-Content .\models\metrics.json
```

The persisted model is loaded by the FastAPI prediction service. Demo mode keeps development fallback disabled:

```powershell
$env:ALLOW_DEVELOPMENT_FALLBACK="false"
```

## 5. Optional Full Rebuild

This is **optional**. Do not rebuild during a normal demo when the existing model and analytics artifacts are valid.

Run these commands from the project root if the synthetic data, processed data, analytics, or model artifacts need to be regenerated:

```powershell
python spark\generate_mobility_data.py --rows 250000
python spark\preprocess.py
python spark\analytics.py
python spark\train_model.py
python spark\evaluate_model.py
```

The rebuild creates or updates:

- `data\raw\mobility.csv`
- `data\processed\mobility`
- `data\output\analytics.json`
- `models\spark_best`
- `models\metadata.json`
- `models\metrics.json`

## 6. Start Backend

From the project root, with the environment variables from Section 3 set, start FastAPI:

```powershell
uvicorn backend.app.main:app --reload
```

Backend URL:

```text
http://localhost:8000
```

Swagger documentation:

```text
http://localhost:8000/docs
```

Optional health check:

```powershell
Invoke-RestMethod http://localhost:8000/api/health
```

The health response identifies the application as a predictive prototype using synthetic simulation data.

## 7. Start Frontend

Open a second PowerShell window:

```powershell
cd C:\Users\vinus\OneDrive\Desktop\BDA\frontend
npm install
npm run dev
```

Vite uses its default development port:

```text
http://localhost:5173
```

If Vite selects another available port, open the URL printed in the terminal.

## 8. Demo Scenario

On the **Plan my journey** page, enter:

| UI field | Value |
|---|---|
| From | Bengaluru (or search/pick any supported Karnataka locality, landmark, street, or address) |
| To | Tumakuru |
| Date | 17 October 2026 |
| Time | 5:00 PM |
| Festival | Yes |
| Holiday | Yes |
| Weather | Rain |
| Roadwork | No |

Click:

```text
Analyze traffic & routes
```

## 9. What to Demonstrate

Use this sequence while demonstrating the application:

```text
Future journey input
→ new scenario feature construction
→ persisted Spark MLlib PipelineModel
→ predicted congestion and risk
→ genuine OSRM route comparison when alternatives are returned
→ congestion-adjusted travel time and route score
→ recommended route and explanation
→ same corridor predictions reused by authority advisory
```

On the result screen, show:

1. The recommended route.
2. Predicted congestion, risk, distance, OSRM base duration, severity, and prediction source.
3. The **Compare routes** section.
4. The genuine OSRM route cards, if alternatives are returned.
5. The selectable Leaflet/OpenStreetMap route map.
6. The route explanation and corridor-matching limitation.

The service requests automatic OSRM alternatives plus relevant configured exit-corridor waypoint routes, including the western ORR/Nayandahalli/Sumanahalli approach for Tumakuru-direction journeys. It verifies every requested checkpoint and compares normalized road-segment overlap before displaying routes. If only one route is verified, the screen explicitly reports that one genuine route was returned; it does not fabricate Route 2 or Route 3.

Then open **Authority advisory** and show:

- high-, medium-, and low-risk counts
- corridor direction
- predicted probability
- scenario factors
- recommended operational actions

Finally, open **Analytics** and click **Load analytics**.

## 10. What to Say During Demo

### Why Spark is used

“Apache Spark is used to process the synthetic mobility data, create predictive features, train and evaluate Spark MLlib models, and generate analytics aggregations.”

### How future prediction works

“The system creates a new feature vector from the selected future date, time, corridor, direction, festival, holiday, weather, and roadwork inputs. It does not retrieve a historical row for that date.”

### How route recommendation works

“Each candidate route is associated with configured Bengaluru corridors. The persisted Spark model predicts corridor congestion, route congestion is calculated from those predictions, travel time is adjusted, and a transparent route score ranks the alternatives.”

### What OSRM does

“OSRM provides route geometry, distance, and base duration. OSRM does not provide our traffic prediction and is not treated as a live traffic source.”

### What the authority advisory does

“The advisory uses the same corridor prediction results as the route recommendation. It ranks high-risk corridors and applies rule-based operational actions such as personnel deployment, diversion readiness, roadwork coordination, and commuter advisories.”

### Why this is not real-time navigation

“This is a predictive decision-support prototype for an upcoming scenario. It does not use live GPS, live camera feeds, live congestion, or automatic traffic-signal control, and it does not guarantee the fastest future route.”

## 11. Important Limitations

- The mobility records are synthetic/simulation data.
- The project does not provide live traffic.
- The project does not use real GPS traces or camera traffic data.
- Future traffic predictions are not guaranteed.
- Model metrics measured on synthetic data are not real-world accuracy.
- OSRM supplies route geometry, distance, and base duration only.
- Route-to-corridor mapping is prototype-level and does not claim exact GPS-level traffic matching.
- The project is an academic predictive traffic analytics and congestion-aware route advisory prototype.

## 12. Quick Demo Startup

### PowerShell Window 1 — Backend

```powershell
cd C:\Users\vinus\OneDrive\Desktop\BDA
.\.venv\Scripts\Activate.ps1
$env:HADOOP_HOME="$PWD\tools\hadoop"
$env:PATH="$env:HADOOP_HOME\bin;$env:PATH"
$env:PYSPARK_PYTHON=(Get-Command python).Source
$env:PYSPARK_DRIVER_PYTHON=$env:PYSPARK_PYTHON
$env:ALLOW_DEVELOPMENT_FALLBACK="false"
uvicorn backend.app.main:app --reload
```

### PowerShell Window 2 — Frontend

```powershell
cd C:\Users\vinus\OneDrive\Desktop\BDA\frontend
npm run dev
```

Open:

```text
http://localhost:5173
```

## 13. Troubleshooting

### Python version mismatch

Check the active interpreter:

```powershell
python --version
Get-Command python
```

Use Python 3.11. If the project environment is missing, recreate it with:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
```

### Spark/PySpark worker error

Check that Spark uses the active `.venv` interpreter:

```powershell
$env:PYSPARK_PYTHON=(Get-Command python).Source
$env:PYSPARK_DRIVER_PYTHON=$env:PYSPARK_PYTHON
python -c "import sys, pyspark; print(sys.executable); print(pyspark.__version__)"
```

The expected PySpark version is `3.5.4`.

### Hadoop/winutils issue

Check the Windows Spark helper:

```powershell
Write-Host $env:HADOOP_HOME
Test-Path "$env:HADOOP_HOME\bin\winutils.exe"
Test-Path "$env:HADOOP_HOME\bin\hadoop.dll"
```

If either file is missing:

```powershell
New-Item -ItemType Directory -Force tools\hadoop\bin
curl.exe -L https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.5/bin/winutils.exe -o tools\hadoop\bin\winutils.exe
curl.exe -L https://github.com/cdarlint/winutils/raw/master/hadoop-3.3.5/bin/hadoop.dll -o tools\hadoop\bin\hadoop.dll
```

Then reset the variables:

```powershell
$env:HADOOP_HOME="$PWD\tools\hadoop"
$env:PATH="$env:HADOOP_HOME\bin;$env:PATH"
```

### Backend not starting

Check the backend dependencies and import:

```powershell
pip install -r backend\requirements.txt
python -c "from backend.app.main import app; print(app.title)"
```

The expected title is:

```text
Smart Mobility Bengaluru API
```

### Frontend dependency issue

From the frontend directory, reinstall the declared npm dependencies:

```powershell
cd C:\Users\vinus\OneDrive\Desktop\BDA\frontend
npm install
npm run dev
```

### Model not found

Verify the persisted model and metadata:

```powershell
Test-Path C:\Users\vinus\OneDrive\Desktop\BDA\models\spark_best
Test-Path C:\Users\vinus\OneDrive\Desktop\BDA\models\metadata.json
Test-Path C:\Users\vinus\OneDrive\Desktop\BDA\models\metrics.json
```

If artifacts are missing, run the optional rebuild commands in Section 5. Keep fallback disabled for the actual demo:

```powershell
$env:ALLOW_DEVELOPMENT_FALLBACK="false"
```

## 14. Final Demo Checklist

- [ ] Backend running
- [ ] Frontend running
- [ ] Spark model loaded
- [ ] Fallback disabled
- [ ] Future scenario entered
- [ ] Route recommendation visible
- [ ] Map visible
- [ ] Authority advisory visible
- [ ] Analytics visible
