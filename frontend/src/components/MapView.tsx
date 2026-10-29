import { COORDINATE_SYSTEM, type PickingInfo } from "@deck.gl/core";
import { BitmapLayer, PathLayer, ScatterplotLayer } from "@deck.gl/layers";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from "maplibre-gl";
// MapLibre 6 finds its worker next to its own module, which no longer exists once bundled.
// Let Vite build the worker as a real worker chunk and hand MapLibre its URL.
import maplibreWorkerUrl from "maplibre-gl/dist/maplibre-gl-worker.mjs?worker&url";
import "maplibre-gl/dist/maplibre-gl.css";
import { useEffect, useMemo, useRef, useState } from "react";

import type { Analysis, Checkpoint, Heatmap, RouteResult } from "../api/types";
import { formatDateTime, formatMiles } from "../lib/format";
import { buildHeatRaster } from "../lib/heatRaster";
import {
  ALTERNATIVE_ROUTE_COLOR,
  hexToRgb,
  RECOMMENDED_ROUTE_COLOR,
  riskColor,
  riskLabel,
  type RGB,
} from "../lib/risk";

setWorkerUrl(maplibreWorkerUrl);

const STYLE_URL =
  import.meta.env.VITE_MAP_STYLE_URL ??
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";
const INITIAL_VIEW = { center: [-98.5, 39.5] as [number, number], zoom: 3.6 };
const WHITE: RGB = [255, 255, 255];
const RECOMMENDED_RGB = hexToRgb(RECOMMENDED_ROUTE_COLOR);
const ALTERNATIVE_RGB = hexToRgb(ALTERNATIVE_ROUTE_COLOR);
const SELECTED_ALTERNATIVE_RGB: RGB = [88, 88, 84];

interface Props {
  analysis: Analysis | null;
  heatmap: Heatmap | null;
  hour: number;
  heatmapVisible: boolean;
  selectedId: string | null;
  onSelect: (routeId: string) => void;
}

interface CheckpointDatum extends Checkpoint {
  routeId: string;
  selected: boolean;
}

const escapeHtml = (text: string) => text.replace(/[&<>"']/g, (c) => `&#${c.charCodeAt(0)};`);

function checkpointTooltip(cp: CheckpointDatum): string {
  const weather = cp.weather
    ? `Wind ${cp.weather.wind_mph} mph · Rain ${cp.weather.rain_in_hr} in/hr · Snow ${cp.weather.snow_in_hr} in/hr`
    : "No forecast for this arrival time";
  const reasons = cp.reasons.length
    ? `<div class="tt-muted">${cp.reasons.map(escapeHtml).join("; ")}</div>`
    : "";
  return `
    <div class="tt-title">${escapeHtml(cp.routeId)} · mile ${formatMiles(cp.position_mi)}</div>
    <div>ETA ${escapeHtml(formatDateTime(cp.eta))}</div>
    <div><span class="tt-swatch" style="background:${riskColor(cp.level)}"></span><strong>${escapeHtml(riskLabel(cp.level))}</strong></div>
    <div class="tt-muted">${weather}</div>${reasons}`;
}

function routeColor(route: RouteResult, selected: boolean): RGB {
  if (route.recommended) return RECOMMENDED_RGB;
  return selected ? SELECTED_ALTERNATIVE_RGB : ALTERNATIVE_RGB;
}

export function MapView({ analysis, heatmap, hour, heatmapVisible, selectedId, onSelect }: Props) {
  const container = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapLibreMap | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const onSelectRef = useRef(onSelect);
  onSelectRef.current = onSelect;

  // Create the map once.
  useEffect(() => {
    const map = new MapLibreMap({
      container: container.current!,
      style: STYLE_URL,
      ...INITIAL_VIEW,
      attributionControl: { compact: true },
    });
    map.addControl(new NavigationControl({ showCompass: false }), "top-right");
    const overlay = new MapboxOverlay({
      layers: [],
      getTooltip: ({ object, layer }: PickingInfo) =>
        layer?.id === "checkpoints" && object
          ? { html: checkpointTooltip(object as CheckpointDatum), className: "map-tooltip" }
          : null,
    });
    map.addControl(overlay);
    mapRef.current = map;
    overlayRef.current = overlay;
    return () => {
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  // Fit the view to the routes whenever a new analysis arrives.
  useEffect(() => {
    if (!analysis || !mapRef.current) return;
    const points = analysis.routes.flatMap((r) => r.geometry);
    if (!points.length) return;
    const lats = points.map(([lat]) => lat);
    const lons = points.map(([, lon]) => lon);
    mapRef.current.fitBounds(
      [
        [Math.min(...lons), Math.min(...lats)],
        [Math.max(...lons), Math.max(...lats)],
      ],
      { padding: { top: 60, bottom: 170, left: 60, right: 60 }, duration: 700 },
    );
  }, [analysis]);

  // Heatmap: decode all hourly frames to GPU-ready bitmaps once per heatmap response.
  const raster = useMemo(() => (heatmap ? buildHeatRaster(heatmap) : null), [heatmap]);
  const [bitmaps, setBitmaps] = useState<ImageBitmap[]>([]);
  useEffect(() => {
    if (!raster) {
      setBitmaps([]);
      return;
    }
    let cancelled = false;
    let created: ImageBitmap[] = [];
    Promise.all(
      raster.frames.map((pixels) =>
        createImageBitmap(
          new ImageData(new Uint8ClampedArray(pixels), raster.width, raster.height),
          { premultiplyAlpha: "none" }, // straight alpha: premultiplying darkens faint cells
        ),
      ),
    ).then((result) => {
      created = result;
      if (cancelled) result.forEach((b) => b.close());
      else setBitmaps(result);
    });
    return () => {
      cancelled = true;
      created.forEach((b) => b.close());
    };
  }, [raster]);

  // Static layers: rebuilt only when the analysis or selection changes, not per slider tick.
  const routeLayers = useMemo(() => {
    if (!analysis) return [];
    // Draw the selected and recommended routes last so they sit on top.
    const order = (r: RouteResult) => (r.id === selectedId ? 2 : r.recommended ? 1 : 0);
    const routes = [...analysis.routes].sort((a, b) => order(a) - order(b));
    const path = (r: RouteResult) => r.geometry.map(([lat, lon]): [number, number] => [lon, lat]);
    const width = (r: RouteResult) => (r.id === selectedId ? 6 : r.recommended ? 5 : 3);

    const checkpoints: CheckpointDatum[] = routes.flatMap((route) =>
      route.checkpoints.map((cp) => ({
        ...cp,
        routeId: route.id,
        selected: route.id === selectedId,
      })),
    );

    return [
      new PathLayer<RouteResult>({
        id: "route-casing", // white halo keeps routes legible over the heatmap
        data: routes,
        getPath: path,
        getColor: WHITE,
        getWidth: (r) => width(r) + 4,
        widthUnits: "pixels",
        capRounded: true,
        jointRounded: true,
        updateTriggers: { getWidth: selectedId },
      }),
      new PathLayer<RouteResult>({
        id: "routes",
        data: routes,
        getPath: path,
        getColor: (r) => routeColor(r, r.id === selectedId),
        getWidth: width,
        widthUnits: "pixels",
        capRounded: true,
        jointRounded: true,
        pickable: true,
        onClick: ({ object }) => object && onSelectRef.current(object.id),
        updateTriggers: { getColor: selectedId, getWidth: selectedId },
      }),
      new ScatterplotLayer<CheckpointDatum>({
        id: "checkpoints",
        data: checkpoints,
        getPosition: (cp) => [cp.lon, cp.lat],
        getRadius: (cp) => (cp.selected ? 6 : 4),
        radiusUnits: "pixels",
        filled: true,
        stroked: true,
        getFillColor: (cp) => (cp.level === null ? [255, 255, 255] : hexToRgb(riskColor(cp.level))),
        getLineColor: (cp) => (cp.level === null ? hexToRgb(riskColor(null)) : WHITE),
        getLineWidth: (cp) => (cp.level === null ? 2 : 1.5),
        lineWidthUnits: "pixels",
        opacity: 1,
        pickable: true,
        autoHighlight: true,
        highlightColor: [42, 120, 214, 200],
      }),
    ];
  }, [analysis, selectedId]);

  // Per-frame update: only the bitmap changes.
  useEffect(() => {
    const frame = bitmaps[hour];
    const heatLayer =
      raster && frame
        ? new BitmapLayer({
            id: "heatmap",
            image: frame,
            bounds: raster.bounds,
            _imageCoordinateSystem: COORDINATE_SYSTEM.LNGLAT,
            visible: heatmapVisible,
          })
        : null;
    overlayRef.current?.setProps({ layers: heatLayer ? [heatLayer, ...routeLayers] : routeLayers });
  }, [bitmaps, hour, heatmapVisible, raster, routeLayers]);

  return <div ref={container} className="map" role="region" aria-label="Route map" />;
}
