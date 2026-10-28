import type { RiskValue } from "../api/types";

export type RGB = [number, number, number];
export type RGBA = [number, number, number, number];

/**
 * Single-hue ordinal ramp, light -> dark. Validated (dataviz validate_palette --ordinal):
 * monotone lightness, visible adjacent steps, lightest step >= 2:1 on the basemap, so the
 * order reads by lightness alone and survives every form of colour blindness.
 * Colour is never the only cue: every use is paired with the text label.
 */
export const RISK_LEVELS: ReadonlyArray<{ value: RiskValue; label: string; color: string }> = [
  { value: 0, label: "Low", color: "#ee9a6a" },
  { value: 1, label: "Moderate", color: "#dd6f38" },
  { value: 2, label: "High", color: "#bb4a1a" },
  { value: 3, label: "Severe", color: "#88300f" },
  { value: 4, label: "No Travel", color: "#4f1806" },
];

export const UNKNOWN_COLOR = "#9b9b96";
export const RECOMMENDED_ROUTE_COLOR = "#2a78d6";
export const ALTERNATIVE_ROUTE_COLOR = "#8d8d87";

export function hexToRgb(hex: string): RGB {
  const n = parseInt(hex.replace("#", ""), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

export function riskColor(level: RiskValue | null): string {
  return level === null ? UNKNOWN_COLOR : RISK_LEVELS[level]!.color;
}

export function riskLabel(level: RiskValue | null): string {
  return level === null ? "Forecast unavailable" : RISK_LEVELS[level]!.label;
}

const RAMP_RGB = RISK_LEVELS.map((level) => hexToRgb(level.color));

/**
 * Heatmap colour for a continuous risk index (0-4). Hue follows the same ramp as the
 * checkpoints; opacity rises with risk so calm weather stays out of the way of the map.
 */
export function heatColor(index: number | null): RGBA {
  // Empty cells keep the ramp's base hue at zero opacity (not transparent black), so the
  // GPU's linear filtering fades edges out instead of smearing dark halos into them.
  if (index === null || Number.isNaN(index)) return [...RAMP_RGB[0]!, 0];
  const x = Math.min(Math.max(index, 0), 4);
  const i = Math.min(Math.floor(x), 3);
  const t = x - i;
  const [a, b] = [RAMP_RGB[i]!, RAMP_RGB[i + 1]!];
  // Calm air (index < 0.4, e.g. wind under 10 mph) is fully transparent.
  const alpha = x <= 1 ? (Math.max(0, x - 0.4) / 0.6) * 60 : 60 + ((x - 1) / 3) * 150;
  return [
    Math.round(a[0] + (b[0] - a[0]) * t),
    Math.round(a[1] + (b[1] - a[1]) * t),
    Math.round(a[2] + (b[2] - a[2]) * t),
    Math.round(alpha),
  ];
}
