import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import type { Analysis, RouteResult } from "../api/types";
import { RouteCards } from "./RouteCards";

function route(id: string, overrides: Partial<RouteResult> = {}): RouteResult {
  return {
    id,
    rank: 1,
    recommended: false,
    distance_mi: 780,
    duration_s: 12 * 3600,
    arrival: "2026-11-02T18:00:00Z",
    geometry: [],
    checkpoints: [],
    worst_level: 1,
    score: {
      severe_miles: 0,
      high_miles: 0,
      no_travel_miles: 0,
      unknown_miles: 0,
      average_risk: 0.4,
      has_no_travel: false,
    },
    ...overrides,
  };
}

const analysis: Analysis = {
  origin: { label: "Dallas", lat: 32.8, lon: -96.8 },
  destination: { label: "Denver", lat: 39.7, lon: -105 },
  departure: "2026-11-02T06:00:00Z",
  load_lb: 42000,
  interval_mi: 25,
  recommended_route_id: "Route B",
  explanation: "Fewest Severe-or-worse miles: 0.0 mi vs 25.0 mi on Route A.",
  routes: [
    route("Route B", { rank: 1, recommended: true }),
    route("Route A", {
      rank: 2,
      worst_level: 4,
      score: { ...route("x").score, severe_miles: 25, no_travel_miles: 25, has_no_travel: true },
    }),
  ],
};

describe("RouteCards", () => {
  it("shows the recommendation and why", () => {
    render(<RouteCards analysis={analysis} selectedId="Route B" onSelect={() => {}} />);
    expect(screen.getByRole("status")).toHaveTextContent("Route B recommended");
    expect(screen.getByRole("status")).toHaveTextContent("Fewest Severe-or-worse miles");
  });

  it("lists routes in rank order with risk as text, not just colour", () => {
    render(<RouteCards analysis={analysis} selectedId="Route B" onSelect={() => {}} />);
    const cards = screen.getAllByRole("button");
    expect(cards[0]).toHaveTextContent("Route B");
    expect(cards[0]).toHaveTextContent("Recommended");
    expect(cards[0]).toHaveAttribute("aria-pressed", "true");
    expect(cards[1]).toHaveTextContent("No Travel");
    expect(cards[1]).toHaveTextContent("25 mi");
  });

  it("selects a route on click", async () => {
    const onSelect = vi.fn();
    render(<RouteCards analysis={analysis} selectedId="Route B" onSelect={onSelect} />);
    await userEvent.click(screen.getAllByRole("button")[1]!);
    expect(onSelect).toHaveBeenCalledWith("Route A");
  });

  it("warns when no route is safe", () => {
    render(
      <RouteCards
        analysis={{ ...analysis, recommended_route_id: null, explanation: "Every route…" }}
        selectedId={null}
        onSelect={() => {}}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent("No safe route");
  });

  it("notes miles beyond the forecast", () => {
    const withUnknown = {
      ...analysis,
      routes: [route("Route B", { score: { ...route("x").score, unknown_miles: 40 } })],
    };
    render(<RouteCards analysis={withUnknown} selectedId={null} onSelect={() => {}} />);
    expect(screen.getByText(/40 mi beyond the forecast window/)).toBeInTheDocument();
  });
});
