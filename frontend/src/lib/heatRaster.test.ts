import type { Heatmap } from "../api/types";
import { buildHeatRaster } from "./heatRaster";
import { heatColor } from "./risk";

function heatmap(overrides: Partial<Heatmap> = {}): Heatmap {
  return {
    start: "2026-11-02T06:00:00+00:00",
    hours: 1,
    step_deg: 0.5,
    // an L-shaped corridor: (30,-90) (30,-89.5) (31,-90)
    lat: [30, 30, 31],
    lon: [-90, -89.5, -90],
    frames: [
      [1, 2, null],
      [3, 4, 0.5],
    ],
    value_range: [0, 4],
    ...overrides,
  };
}

const pixel = (pixels: Uint8ClampedArray, width: number, row: number, col: number) =>
  Array.from(pixels.slice((row * width + col) * 4, (row * width + col) * 4 + 4));

describe("buildHeatRaster", () => {
  it("sizes the image to the cell grid and pads bounds by half a cell", () => {
    const raster = buildHeatRaster(heatmap())!;
    expect([raster.width, raster.height]).toEqual([2, 3]);
    expect(raster.bounds).toEqual([-90.25, 29.75, -89.25, 31.25]);
    expect(raster.frames).toHaveLength(2);
  });

  it("places cells with north at the top", () => {
    const { frames, width } = buildHeatRaster(heatmap())!;
    expect(pixel(frames[1]!, width, 2, 0)).toEqual(heatColor(3)); // 30N,-90 -> bottom-left
    expect(pixel(frames[1]!, width, 2, 1)).toEqual(heatColor(4)); // 30N,-89.5 -> bottom-right
    expect(pixel(frames[1]!, width, 0, 0)).toEqual(heatColor(0.5)); // 31N -> top row
  });

  it("leaves gaps and missing values transparent", () => {
    const { frames, width } = buildHeatRaster(heatmap())!;
    expect(pixel(frames[0]!, width, 0, 0)[3]).toBe(0); // null value
    expect(pixel(frames[0]!, width, 1, 1)).toEqual(heatColor(null)); // not in the corridor
  });

  it("returns null for an empty grid", () => {
    expect(buildHeatRaster(heatmap({ lat: [], lon: [], frames: [[]] }))).toBeNull();
  });
});
