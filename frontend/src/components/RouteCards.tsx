import type { Analysis } from "../api/types";
import { formatDateTime, formatDuration, formatMiles } from "../lib/format";
import { RiskBadge } from "./RiskBadge";

interface Props {
  analysis: Analysis;
  selectedId: string | null;
  onSelect: (routeId: string) => void;
}

export function RouteCards({ analysis, selectedId, onSelect }: Props) {
  const noSafeRoute = analysis.recommended_route_id === null;
  return (
    <section className="route-cards" aria-label="Route options">
      <div className={`explanation ${noSafeRoute ? "warning" : ""}`} role="status">
        <strong>
          {noSafeRoute ? "No safe route" : `${analysis.recommended_route_id} recommended`}
        </strong>
        <p>{analysis.explanation}</p>
      </div>

      {analysis.routes.map((route) => {
        const { score } = route;
        return (
          <button
            key={route.id}
            type="button"
            className={`route-card ${route.id === selectedId ? "selected" : ""} ${
              route.recommended ? "recommended" : ""
            }`}
            aria-pressed={route.id === selectedId}
            onClick={() => onSelect(route.id)}
          >
            <header>
              <span className="route-name">
                <span className="rank">#{route.rank}</span> {route.id}
              </span>
              {route.recommended && <span className="tag">Recommended</span>}
              {score.has_no_travel && <span className="tag danger">No Travel</span>}
            </header>

            <dl className="stats">
              <div>
                <dt>Time</dt>
                <dd>{formatDuration(route.duration_s)}</dd>
              </div>
              <div>
                <dt>Distance</dt>
                <dd>{formatMiles(route.distance_mi)}</dd>
              </div>
              <div>
                <dt>Arrive</dt>
                <dd>{formatDateTime(route.arrival)}</dd>
              </div>
            </dl>

            <dl className="stats risk">
              <div>
                <dt>Worst</dt>
                <dd>
                  <RiskBadge level={route.worst_level} />
                </dd>
              </div>
              <div>
                <dt>Severe+ miles</dt>
                <dd>{formatMiles(score.severe_miles)}</dd>
              </div>
              <div>
                <dt>High miles</dt>
                <dd>{formatMiles(score.high_miles)}</dd>
              </div>
              <div>
                <dt>Avg risk</dt>
                <dd>{score.average_risk === null ? "–" : score.average_risk.toFixed(2)}</dd>
              </div>
            </dl>

            {score.unknown_miles > 0 && (
              <p className="note">
                {formatMiles(score.unknown_miles)} beyond the forecast window (not scored).
              </p>
            )}
          </button>
        );
      })}
    </section>
  );
}
