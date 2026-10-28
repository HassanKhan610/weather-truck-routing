import { heatColor, hexToRgb, RISK_LEVELS, riskColor, riskLabel, UNKNOWN_COLOR } from "./risk";

describe("risk palette", () => {
  it("has one colour per level in order", () => {
    expect(RISK_LEVELS.map((l) => l.label)).toEqual([
      "Low",
      "Moderate",
      "High",
      "Severe",
      "No Travel",
    ]);
  });

  it("maps unknown forecast to the neutral colour and label", () => {
    expect(riskColor(null)).toBe(UNKNOWN_COLOR);
    expect(riskLabel(null)).toBe("Forecast unavailable");
    expect(riskColor(3)).toBe("#88300f");
  });

  it("parses hex", () => {
    expect(hexToRgb("#2a78d6")).toEqual([42, 120, 214]);
  });
});

describe("heatColor", () => {
  it("is transparent for missing data and calm weather", () => {
    expect(heatColor(null)).toEqual([...hexToRgb(RISK_LEVELS[0]!.color), 0]);
    expect(heatColor(0)[3]).toBe(0);
  });

  it("hits each level's palette colour at whole numbers", () => {
    RISK_LEVELS.forEach((level) => {
      expect(heatColor(level.value).slice(0, 3)).toEqual(hexToRgb(level.color));
    });
  });

  it("gets more opaque as risk rises and clamps out-of-range values", () => {
    const alphas = [0.5, 1, 2, 3, 4].map((x) => heatColor(x)[3]);
    expect([...alphas].sort((a, b) => a - b)).toEqual(alphas);
    expect(heatColor(9)).toEqual(heatColor(4));
    expect(heatColor(-1)).toEqual(heatColor(0));
  });
});
