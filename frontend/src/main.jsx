import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { MapContainer, Marker, Polyline, TileLayer, Tooltip as MapTooltip, useMap, useMapEvents } from "react-leaflet";
import "leaflet/dist/leaflet.css";
import "./styles.css";

const API = import.meta.env.VITE_API_URL || "http://localhost:8000";
const initial = {
  source: "Bengaluru", destination: "Tumakuru", date: "2026-10-17", time: "17:00",
  festival: false, holiday: false, weather: "Clear", roadwork: false, direction: "AUTO", scenario_mode: "MANUAL",
};

async function get(path) {
  const response = await fetch(API + path);
  if (!response.ok) throw Error("The API request failed");
  return response.json();
}

async function post(path, body) {
  const response = await fetch(API + path, {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  const bodyJson = await response.json().catch(() => ({}));
  if (!response.ok) throw Error(bodyJson.detail || "The API request failed");
  return bodyJson;
}

function Risk({ value }) {
  return <span className={"risk " + value.toLowerCase()}>{value}</span>;
}

function App() {
  const [page, setPage] = useState("journey");
  const [form, setForm] = useState(initial);
  const [result, setResult] = useState();
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState();

  useEffect(() => { get("/api/health").then(setStatus).catch(() => setStatus({ model_available: false })); }, []);
  const update = (key, value) => setForm(previous => ({ ...previous, [key]: value }));
  const analyze = async () => {
    setError("");
    setLoading(true);
    try { setResult(await post("/api/route/recommend", form)); setPage("journey"); }
    catch (exception) { setError(exception.message.includes("Nominatim") ? "Unable to resolve one or more locations." : "Unable to calculate an OSRM route or prediction for this journey."); }
    finally { setLoading(false); }
  };
  const modelText = status?.model_available && !status?.fallback_enabled ? "Spark MLlib Model: READY" :
    status?.fallback_enabled ? "Development Fallback: ENABLED" : "Spark MLlib Model: UNAVAILABLE";

  return <div className="shell">
    <aside>
      <b className="brand">↗ MobilityLens<small>BENGALURU PREDICTIVE TRAFFIC</small></b>
      <nav>{[["journey", "Plan my journey"], ["prediction", "Traffic prediction"], ["advisory", "Authority advisory"], ["analytics", "Analytics"]].map(([key, label]) =>
        <button key={key} className={page === key ? "active" : ""} onClick={() => setPage(key)}>{label}</button>)}</nav>
      <div className="disclaimer"><b>Predictive prototype</b><p>Synthetic mobility simulation data. Not live traffic or guaranteed travel time.</p></div>
    </aside>
    <main>
      <header><div><span className="eyebrow">SMART MOBILITY / DECISION SUPPORT</span>
        <h1>{page === "journey" ? "Plan your journey" : page === "prediction" ? "Traffic prediction" : page === "advisory" ? "Authority advisory" : "Network analytics"}</h1>
      </div><span className="pill">{modelText}</span></header>
      {page === "journey" ? <Journey form={form} update={update} analyze={analyze} result={result} error={error} loading={loading} /> :
        page === "prediction" ? <Prediction form={form} /> :
          page === "advisory" ? <Advisory form={form} /> : <Analytics />}
    </main>
  </div>;
}

function Field({ label, value, onChange, type = "text" }) {
  return <label>{label}<input type={type} value={value} onChange={event => onChange(event.target.value)} /></label>;
}

function LocationSearch({ label, value, onChange, coordinates, onCoordinates, onCurrentLocation, currentLoading, onSearch }) {
  const [results, setResults] = useState([]);
  const [searching, setSearching] = useState(false);
  const [message, setMessage] = useState("");
  const search = async () => {
    if (!value.trim()) return;
    setSearching(true); setMessage("");
    try {
      const response = await get(`/api/geocode/search?q=${encodeURIComponent(value)}`);
      setResults(response.places || []);
      if (!response.places?.length) setMessage("No matching Karnataka location was found.");
    } catch (exception) { setMessage(exception.message); }
    finally { setSearching(false); }
  };
  return <div className="location-field">
    <label>{label}
      <input value={value} onChange={event => { onChange(event.target.value); onCoordinates(null); setResults([]); }} onKeyDown={event => {
        if (event.key === "Enter") { event.preventDefault(); search(); }
      }} />
    </label>
    <div className="location-actions">
      <button type="button" className="secondary" onClick={search} disabled={searching}>{searching ? "Searching..." : "Search"}</button>
      {onCurrentLocation && <button type="button" className="secondary" onClick={onCurrentLocation} disabled={currentLoading}>
        {currentLoading ? "Locating..." : "Use my current location"}
      </button>}
    </div>
    {coordinates && <small className="location-confirmed">Selected coordinates: {coordinates[0].toFixed(5)}, {coordinates[1].toFixed(5)}</small>}
    {results.length > 0 && <div className="location-results">{results.map(place => <button type="button" key={`${place.latitude}-${place.longitude}`}
      onClick={() => { onChange(place.display_name); onCoordinates([place.latitude, place.longitude]); setResults([]); }}>
      {place.display_name}
    </button>)}</div>}
    {message && <small className="location-message">{message}</small>}
  </div>;
}

function EndpointClickHandler({ activeEndpoint, onPick }) {
  useMapEvents({ click: event => { if (activeEndpoint) onPick(activeEndpoint, [event.latlng.lat, event.latlng.lng]); } });
  return null;
}

function LocationPickerMap({ form, activeEndpoint, onPick }) {
  const source = form.source_coordinates || [12.9768, 77.5901];
  const destination = form.destination_coordinates;
  return <div className="picker-wrap">
    <div className="picker-help">Pick on map: <b>{activeEndpoint === "source" ? "From" : "To"}</b>. Click the map to place that endpoint.</div>
    <MapContainer center={source} zoom={11} scrollWheelZoom className="location-picker-map">
      <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      <EndpointClickHandler activeEndpoint={activeEndpoint} onPick={onPick} />
      {form.source_coordinates && <Marker position={form.source_coordinates}><MapTooltip permanent direction="top">From: {form.source}</MapTooltip></Marker>}
      {destination && <Marker position={destination}><MapTooltip permanent direction="top">To: {form.destination}</MapTooltip></Marker>}
    </MapContainer>
  </div>;
}

function Journey({ form, update, analyze, result, error, loading }) {
  const [activeEndpoint, setActiveEndpoint] = useState("source");
  const [locationLoading, setLocationLoading] = useState(false);
  const [locationError, setLocationError] = useState("");
  const setLocation = async (endpoint, coordinates, fallbackLabel) => {
    update(`${endpoint}_coordinates`, coordinates);
    try {
      const response = await get(`/api/geocode/reverse?lat=${coordinates[0]}&lon=${coordinates[1]}`);
      update(endpoint, response.place.display_name);
    } catch {
      update(endpoint, fallbackLabel);
    }
  };
  const useCurrentLocation = () => {
    setLocationError("");
    if (!window.isSecureContext || !navigator.geolocation) {
      setLocationError("Current location requires a secure browser context and location support.");
      return;
    }
    setLocationLoading(true);
    navigator.geolocation.getCurrentPosition(
      position => {
        const coordinates = [position.coords.latitude, position.coords.longitude];
        setLocation("source", coordinates, `Current location (${coordinates[0].toFixed(5)}, ${coordinates[1].toFixed(5)})`);
        setLocationLoading(false);
      },
      geolocationError => {
        const messages = {
          1: "Location permission was denied. Enter an origin or choose it on the map.",
          2: "Your location is unavailable. Check device location services and try again.",
          3: "Location lookup timed out. Try again or choose the origin on the map.",
        };
        setLocationError(messages[geolocationError.code] || "Unable to determine your current location.");
        setLocationLoading(false);
      },
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 },
    );
  };
  const swapLocations = () => {
    const source = form.source; const sourceCoordinates = form.source_coordinates;
    update("source", form.destination); update("source_coordinates", form.destination_coordinates);
    update("destination", source); update("destination_coordinates", sourceCoordinates);
  };
  const pickLocation = (endpoint, coordinates) => {
    setActiveEndpoint(endpoint);
    setLocation(endpoint, coordinates, `Map pin (${coordinates[0].toFixed(5)}, ${coordinates[1].toFixed(5)})`);
  };
  return <><section className="panel">
    <div className="section-title"><span>01</span><div><h2>Weekend/Festival Travel Surge Analysis</h2>
      <p>Future date/time → travel surge → directional demand → corridor congestion → route impact.</p></div></div>
    <div className="grid">
      <LocationSearch label="From" value={form.source} coordinates={form.source_coordinates}
        onChange={value => update("source", value)} onCoordinates={value => update("source_coordinates", value)}
        onCurrentLocation={useCurrentLocation} currentLoading={locationLoading} />
      <LocationSearch label="To" value={form.destination} coordinates={form.destination_coordinates}
        onChange={value => update("destination", value)} onCoordinates={value => update("destination_coordinates", value)} />
      <Field label="Date" value={form.date} onChange={value => update("date", value)} type="date" />
      <Field label="Time" value={form.time} onChange={value => update("time", value)} type="time" />
      <label>Direction<select value={form.direction} onChange={event => update("direction", event.target.value)}>
        <option value="AUTO">Auto-detect</option><option value="OUTBOUND">Leaving Bengaluru</option><option value="INBOUND">Entering Bengaluru</option>
      </select></label>
      <label>Scenario mode<select value={form.scenario_mode} onChange={event => update("scenario_mode", event.target.value)}>
        <option value="MANUAL">Manual scenario</option><option value="CALENDAR">Calendar-derived</option>
      </select></label>
      <label>Weather<select value={form.weather} onChange={event => update("weather", event.target.value)}>
        <option>Clear</option><option>Cloudy</option><option>Rain</option><option>Unknown</option>
      </select></label>
      {["festival", "holiday", "roadwork"].map(key => <label className="check" key={key}>
        <input type="checkbox" checked={form[key]} disabled={form.scenario_mode === "CALENDAR" && key !== "roadwork"}
          onChange={event => update(key, event.target.checked)} /> {key === "festival" ? "Festival" : key === "holiday" ? "Holiday" : "Roadwork"}
      </label>)}
    </div>
    <p className="scenario-mode-note">{form.scenario_mode === "MANUAL"
      ? "Festival and holiday use your manual selections."
      : "Festival and holiday follow the configured calendar for the selected date."}</p>
    <div className="location-controls">
      <button type="button" className={"secondary " + (activeEndpoint === "source" ? "active" : "")} onClick={() => setActiveEndpoint("source")}>Pick From on map</button>
      <button type="button" className={"secondary " + (activeEndpoint === "destination" ? "active" : "")} onClick={() => setActiveEndpoint("destination")}>Pick To on map</button>
      <button type="button" className="secondary" onClick={swapLocations}>Swap endpoints</button>
    </div>
    <LocationPickerMap form={form} activeEndpoint={activeEndpoint} onPick={pickLocation} />
    {locationError && <p className="error">{locationError}</p>}
    <button className="primary" onClick={analyze} disabled={loading}>{loading ? "Finding route and predicting congestion..." : "Analyze traffic & routes →"}</button>
    {error && <p className="error">{error}</p>}
  </section>{result ? <Results result={result} /> :
    <section className="empty">◎<h2>Your route analysis will appear here</h2><p>Choose an upcoming scenario to compare predicted routes.</p></section>}</>;
}

function ScenarioSummary({ result }) {
  return <div className="scenario-summary">
    <div><small>TRAVEL SURGE</small><strong>{result.travel_surge_level}</strong></div>
    <div><small>DIRECTION</small><strong>{result.travel_direction}</strong></div>
    <div><small>SURGE PATTERN</small><strong>{result.surge_pattern}</strong></div>
    <p>{result.surge_explanation}</p>
  </div>;
}

function FitRoute({ points }) {
  const map = useMap();
  useEffect(() => { if (points.length) map.fitBounds(points, { padding: [28, 28] }); }, [map, points]);
  return null;
}

function RouteMap({ routes, recommended, geocoding, selectedRouteId, onSelect }) {
  const realRoutes = routes.filter(route => route.geometry?.length > 1);
  const origin = recommended.source_coordinates;
  const destination = recommended.destination_coordinates;
  const points = realRoutes.flatMap(route => route.geometry);
  if (!points.length || !origin || !destination) return <div className="map fallback-map">Route geometry is unavailable for this journey.</div>;
  const sourceName = geocoding?.[0]?.name || "Source";
  const destinationName = geocoding?.[1]?.name || "Destination";
  return <div className="map route-map">
    <MapContainer bounds={[...points, origin, destination]} scrollWheelZoom className="leaflet-map">
      <TileLayer attribution='&copy; OpenStreetMap contributors' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
      {[...realRoutes].sort((a, b) => (a.route_id === selectedRouteId ? 1 : 0) - (b.route_id === selectedRouteId ? 1 : 0)).map((route) => {
        const index = realRoutes.findIndex(item => item.route_id === route.route_id);
        return <Polyline key={route.route_id || route.name} positions={route.geometry}
        eventHandlers={{ click: () => onSelect(route.route_id) }}
        pathOptions={{ color: route.route_id === selectedRouteId ? "#d96849" : ["#78918b", "#5978a8", "#8b6fa8", "#5c9a72"][index % 4], weight: route.route_id === selectedRouteId ? 7 : 4, opacity: route.route_id === selectedRouteId ? 0.95 : 0.7 }}>
        <MapTooltip>{route.name} · {route.distance_km} km</MapTooltip>
      </Polyline>;
      })}
      <Marker position={origin}><MapTooltip permanent direction="top">{sourceName}</MapTooltip></Marker>
      <Marker position={destination}><MapTooltip permanent direction="top">{destinationName}</MapTooltip></Marker>
      <FitRoute points={[...points, origin, destination]} />
    </MapContainer>
    <div className="map-legend">
      {realRoutes.map((route, index) => <span key={`legend-${route.route_id || route.name}`}>
        <i className={route.route_id === selectedRouteId ? "legend-recommended" : "legend-alternative"} style={route.route_id === selectedRouteId ? {} : { background: ["#78918b", "#5978a8", "#8b6fa8", "#5c9a72"][index % 4] }} />
        {route.route_id === selectedRouteId ? "Selected: " : "Alternative: "}{route.name}
      </span>)}
    </div>
    <small>OSRM route geometry on OpenStreetMap · base distance and duration only, not live traffic</small>
  </div>;
}

function Results({ result }) {
  const best = result.recommended_route;
  const sourceLabel = best.prediction_source === "development_fallback" ? "Development Fallback" : "Spark MLlib";
  const routes = result.alternatives || [];
  const [selectedRouteId, setSelectedRouteId] = useState(best.route_id);
  useEffect(() => setSelectedRouteId(best.route_id), [best.route_id]);
  const selectedRoute = routes.find(route => route.route_id === selectedRouteId) || best;
  const selectedAdvisory = selectedRoute.route_advisory;
  const factors = [
    `Festival: ${result.scenario?.festival ? "Yes" : "No"} (${result.scenario?.festival_source || "configured calendar"})`,
    `Holiday: ${result.scenario?.holiday ? "Yes" : "No"} (${result.scenario?.holiday_source || "configured calendar"})`,
    result.scenario?.weather === "Unknown"
      ? "Weather: Unknown"
      : `Weather: ${result.scenario?.weather || "Unknown"} (${result.scenario?.weather_source || "explicit scenario input"})`,
    result.scenario?.roadwork && "Roadwork",
    result.travel_surge_level && `${result.travel_surge_level} travel surge`,
    result.travel_direction && result.travel_direction,
  ].filter(Boolean);
  return <><ScenarioSummary result={result} /><section className="recommend">
    <div className="recommend-head"><span className="eyebrow">RECOMMENDED ROUTE</span><Risk value={best.risk} /></div>
    <h2>{result.geocoding?.[0]?.name || result.scenario.source} → {result.geocoding?.[1]?.name || result.scenario.destination}</h2>
    <p>{best.name} · {best.corridors.join(" • ")}</p>
    <div className="metrics">    <div><small>MODEL PREDICTED CONGESTION</small><strong>{best.predicted_level}</strong></div>
      <div><small>BASE TRAVEL TIME</small><strong>{Math.round(best.base_duration_minutes)} min</strong></div>
      <div><small>SEVERITY SCORE</small><strong>{best.congestion_severity_score == null ? "Unavailable" : best.congestion_severity_score.toFixed(2)}</strong></div>
      <div><small>PREDICTION SOURCE</small><strong>{sourceLabel}</strong></div>
    </div>
    <div className="why"><b>Route source</b><span>OSRM + OpenStreetMap</span><b>Predicted congestion</b><span>{best.risk} · HIGH probability {best.probability_high == null ? "unavailable" : best.probability_high.toFixed(2)}</span></div>
  </section><section className="panel"><h2>Compare routes</h2>
    <p>Only actual OSRM routes returned for this journey are shown. {routes.length === 1 ? "OSRM returned 1 route for this journey." : `${routes.length} OSRM routes returned.`}</p>
    <RouteMap routes={routes} recommended={best} geocoding={result.geocoding}
      selectedRouteId={selectedRouteId} onSelect={setSelectedRouteId} />
    <div className="route-cards">{routes.map(route => <div className="route-card-wrap" key={route.route_id || route.name}>
      <button type="button" className={"route-card " + (route.route_id === selectedRouteId ? "selected" : "")}
        onClick={() => setSelectedRouteId(route.route_id)}>
        <div className="route-card-head"><span>{route.recommendation || `Route ${route.rank}`}</span><Risk value={route.risk} /></div>
        <h3>{route.name}</h3>
        <div className="route-card-metrics"><span><b>{route.distance_km} km</b><small>OSRM distance</small></span>
          <span><b>{Math.round(route.base_duration_minutes)} min</b><small>OSRM base duration</small></span>
          <span><b>{route.congestion_severity_score == null ? "Unavailable" : route.congestion_severity_score.toFixed(2)}</b><small>Severity score</small></span>
        </div>
        <div className="route-card-section">
          <b>{route.corridor_status === "matched" ? "Matched corridors" : route.corridor_status === "approximate" ? "Approximate nearby corridors" : "Corridor evidence"}</b>
          <span>{route.corridors.length ? route.corridors.join(", ") :
            route.approximate_corridors?.length ? `${route.approximate_corridors.join(", ")} (approximate; not verified)` :
            "No reliable corridor match available"}</span>
        </div>
        <div className="route-card-section">
          <b>Route assessment</b>
          <span>{route.explanation || `${route.predicted_level} predicted congestion · ${route.prediction_source}`}</span>
        </div>
        <div className="route-card-section">
          <b>Shared road segments</b>
          <span>{route.shared_segment_ratio == null ? "No alternative route available for comparison" : `${(route.shared_segment_ratio * 100).toFixed(0)}% shared with selected route`}</span>
        </div>
        <div className="route-card-section">
          <b>Divergence / rejoin</b>
          <span>{route.shared_segment_ratio === 1 ? "No measurable divergence from selected route" : "A distinct geometry section is present; see technical details."}</span>
        </div>
      </button>
      {route.overlap_note && <details className="route-technical-details">
        <summary>Technical geometry details</summary>
        <span>{route.overlap_note}</span>
      </details>}
    </div>)}</div>
    <p className="mapping-note">{best.mapping_note}</p>
  </section>
  <section className="result-grid">
    <article className="panel result-card"><h2>Scenario Factors</h2><div className="chips">{factors.map(factor => <span key={factor}>{factor}</span>)}</div><h3>Travel surge</h3><strong>{result.travel_surge_level}</strong><p>{result.surge_explanation}</p><p>Direction: <b>{result.travel_direction}</b></p></article>
    <article className="panel result-card"><h2>Authority Advisory</h2>
      <p>{selectedAdvisory?.scope === "route" ? `Selected route advisory · ${selectedRoute.name}` : "General citywide scenario advisory"}</p>
      <Risk value={selectedAdvisory?.high_priority_corridors?.[0]?.risk || "LOW"} />
      <h3>{selectedAdvisory?.high_priority_corridors?.[0]?.corridor || "No route-specific corridor recommendation"}</h3>
      <p>{selectedAdvisory?.high_priority_corridors?.[0]?.actions?.[0] || selectedAdvisory?.summary || "Normal monitoring"}</p>
      {selectedAdvisory?.scope === "route" && selectedAdvisory?.corridors?.length > 0 &&
        <small>{selectedAdvisory.directional_note}</small>}
      {selectedAdvisory?.scope !== "route" && <small>Citywide advisory: {result.advisory?.directional_note}</small>}
      <small>Predictions are synthetic scenario estimates, not observed live traffic.</small>
    </article>
  </section></>;
}

function Prediction({ form }) {
  const [data, setData] = useState(); const [error, setError] = useState("");
  const refresh = async () => { try { setData(await post("/api/predict/scenario", form)); } catch (exception) { setError(exception.message); } };
  return <section className="panel"><h2>Corridor risk forecast</h2><p>Future scenario predictions for the configured network.</p>
    <button className="primary" onClick={refresh}>Refresh prediction</button>{error && <p className="error">{error}</p>}
    {data && <><ScenarioSummary result={data} /><p>Prediction source: <b>{data.predictions[0]?.prediction_source === "spark_mllib" ? "Spark MLlib" : "Development Fallback"}</b></p>
      <div className="table">{data.predictions.sort((a, b) => b.severity_score - a.severity_score).map(prediction => <div className="row" key={prediction.corridor}>
        <b>{prediction.corridor}</b><span>{prediction.direction}</span><Risk value={prediction.risk} /><span>{prediction.severity_score} severity</span><small>{prediction.factors.join(" · ")}</small>
      </div>)}</div></>}
  </section>;
}

function Advisory({ form }) {
  const [data, setData] = useState(); const [error, setError] = useState("");
  const load = async () => { try { setData(await post("/api/advisory", form)); } catch (exception) { setError(exception.message); } };
  return <section className="panel"><h2>Operational advisory</h2><p>Same future scenario inputs and corridor predictions used by route analysis.</p>
    <button className="primary" onClick={load}>Generate authority advisory</button>{error && <p className="error">{error}</p>}
    {data && <><div className="summary">{data.summary} · High {data.counts.HIGH} · Medium {data.counts.MEDIUM} · Low {data.counts.LOW}<br />{data.directional_note}</div>
      {data.corridors.slice(0, 6).map(prediction => <article className="advisory" key={prediction.corridor}><b>{prediction.corridor}</b> <span>{prediction.direction}</span> <Risk value={prediction.risk} />
        <p>{prediction.severity_score} severity · {prediction.factors.join(" · ")}</p><ul>{prediction.actions.map(action => <li key={action}>{action}</li>)}</ul>
      </article>)}</>}
  </section>;
}

function Analytics() {
  const [data, setData] = useState(); const [error, setError] = useState("");
  const load = async () => { try { setData(await get("/api/analytics")); } catch (exception) { setError(exception.message); } };
  return <section className="panel"><h2>Historical/Synthetic Mobility Simulation Analytics</h2>
    <p>Apache Spark / Spark SQL aggregates from synthetic mobility simulation data. This is not live Bengaluru traffic analytics.</p>
    <button className="primary" onClick={load}>Load analytics</button>{error && <p className="error">{error}</p>}
    {data && <><div className="provenance"><b>Data source:</b> Synthetic mobility simulation · <b>Purpose:</b> Academic BDA prototype · <b>Processing:</b> Apache Spark / Spark SQL · <b>Prediction:</b> Spark MLlib</div>
      <h3>Hour-wise congestion</h3><ResponsiveContainer width="100%" height={260}><BarChart data={data.hourly}><XAxis dataKey="hour" /><YAxis /><Tooltip /><Bar dataKey="congestion" fill="#d96849" /></BarChart></ResponsiveContainer>
      <h3>Corridor risk, volume, and speed</h3><div className="table">{data.corridors.slice(0, 8).map(row => <div className="row" key={row.corridor}><b>{row.corridor}</b><span>{row.congestion}</span><span>{row.traffic_volume} volume</span><span>{row.average_speed} speed</span></div>)}</div>
    </>}
  </section>;
}

createRoot(document.getElementById("root")).render(<App />);
