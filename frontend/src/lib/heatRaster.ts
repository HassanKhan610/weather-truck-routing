import type { Heatmap } from "../api/types";
import { heatColor } from "./risk";

export interface HeatRaster {
  width: number;
  height: number;
  /** [west, south, east, north] in degrees: cell centres sit at pixel centres. */
  bounds: [number, number, number, number];
  /** One RGBA pixel buffer per hour, row 0 = north. */
  frames: Uint8ClampedArray[];
}

/**
 * Lay the corridor cells out as a tiny image (one pixel per grid cell) for every hour.
 *
 * Done once per heatmap response. The slider then just picks a precomputed frame, and the
 * GPU's linear texture filtering turns the coarse pixels into a smooth gradient for free.
 * Cells outside the corridor stay transparent, so the heatmap follows the routes' shape.
 */
export function buildHeatRaster(heatmap: Heatmap): HeatRaster | null {
  const { lat, lon, step_deg: step, frames } = heatmap;
  if (!lat.length) return null;

  const west = Math.min(...lon);
  const east = Math.max(...lon);
  const south = Math.min(...lat);
  const north = Math.max(...lat);
  const width = Math.round((east - west) / step) + 1;
  const height = Math.round((north - south) / step) + 1;

  const pixelIndex = lat.map((cellLat, i) => {
    const col = Math.round((lon[i]! - west) / step);
    const row = Math.round((north - cellLat) / step);
    return (row * width + col) * 4;
  });

  const empty = heatColor(null);
  const rasters = frames.map((values) => {
    const pixels = new Uint8ClampedArray(width * height * 4);
    for (let i = 0; i < pixels.length; i += 4) pixels.set(empty, i);
    values.forEach((value, cell) => pixels.set(heatColor(value), pixelIndex[cell]!));
    return pixels;
  });

  const half = step / 2;
  return {
    width,
    height,
    bounds: [west - half, south - half, east + half, north + half],
    frames: rasters,
  };
}
