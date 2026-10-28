import { lazy, Suspense, useCallback, useRef, useState } from "react";

import { api, ApiError } from "./api/client";
import type { Analysis, Heatmap, TripInput } from "./api/types";
import { HeatmapSlider } from "./components/HeatmapSlider";
import { Legend } from "./components/Legend";
import { RouteCards } from "./components/RouteCards";
import { TripForm } from "./components/TripForm";
import { formatPounds } from "./lib/format";

// The map bundle (MapLibre + deck.gl) is most of the app's weight: load it in parallel so
// the form is usable immediately.
const MapView = lazy(() =>
  import("./components/MapView").then((module) => ({ default: module.MapView })),
);

type HeatmapStatus = "idle" | "loading" | "ready" | "error";

const isAbort = (error: unknown) => error instanceof DOMException && error.name === "AbortError";

export default function App() {
  const [analysis, setAnalysis] = useState<Analysis | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);
  const [heatmapStatus, setHeatmapStatus] = useState<HeatmapStatus>("idle");
  const [heatmapVisible, setHeatmapVisible] = useState(true);
  const [hour, setHour] = useState(0);

  const inFlight = useRef<AbortController | null>(null);

  const analyze = useCallback(async (trip: TripInput) => {
    inFlight.current?.abort(); // a new submission supersedes any pending one
    const controller = new AbortController();
    inFlight.current = controller;

    setAnalyzing(true);
    setError(null);
    setHeatmap(null);
    setHeatmapStatus("idle");
    let result: Analysis;
    try {
      result = await api.analyze(trip, controller.signal);
      setAnalysis(result);
      setSelectedId(result.recommended_route_id ?? result.routes[0]?.id ?? null);
      setHour(0);
    } catch (err) {
      if (!isAbort(err)) setError(err instanceof ApiError ? err.message : "Something went wrong.");
      return;
    } finally {
      if (inFlight.current === controller) setAnalyzing(false);
    }

    // Routes are on screen; the heatmap loads behind them.
    setHeatmapStatus("loading");
    try {
      const paths = result.routes.map((route) => route.geometry);
      const frames = await api.heatmap(paths, trip.departure, trip.load_lb, controller.signal);
      setHeatmap(frames);
      setHeatmapStatus("ready");
    } catch (err) {
      if (!isAbort(err)) setHeatmapStatus("error");
    }
  }, []);

  return (
    <div className="app">
      <aside className="sidebar">
        <header className="brand">
          <h1>Safe Haul</h1>
          <p>Compare truck routes by weather risk, load and travel time.</p>
        </header>
        <TripForm onSubmit={analyze} busy={analyzing} />
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        {analysis && (
          <>
            <p className="trip-summary">
              {analysis.origin.label} → {analysis.destination.label} ·{" "}
              {formatPounds(analysis.load_lb)} · every {analysis.interval_mi} mi
            </p>
            <RouteCards analysis={analysis} selectedId={selectedId} onSelect={setSelectedId} />
          </>
        )}
      </aside>
      <main className="map-area">
        <Suspense fallback={<div className="map map-loading">Loading map…</div>}>
          <MapView
            analysis={analysis}
            heatmap={heatmap}
            hour={hour}
            heatmapVisible={heatmapVisible}
            selectedId={selectedId}
            onSelect={setSelectedId}
          />
        </Suspense>
        <Legend />
        {analysis && (
          <HeatmapSlider
            start={heatmap?.start ?? null}
            hours={heatmap?.hours ?? 48}
            hour={hour}
            onHourChange={setHour}
            visible={heatmapVisible}
            onVisibleChange={setHeatmapVisible}
            status={heatmapStatus}
          />
        )}
      </main>
    </div>
  );
}
