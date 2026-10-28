import {
  ALTERNATIVE_ROUTE_COLOR,
  RECOMMENDED_ROUTE_COLOR,
  RISK_LEVELS,
  UNKNOWN_COLOR,
} from "../lib/risk";

export function Legend() {
  return (
    <div className="legend map-panel" aria-label="Map legend">
      <h3>Checkpoint risk</h3>
      <ul>
        {RISK_LEVELS.map((level) => (
          <li key={level.value}>
            <span className="dot" style={{ background: level.color }} aria-hidden />
            {level.label}
          </li>
        ))}
        <li>
          <span className="dot hollow" style={{ borderColor: UNKNOWN_COLOR }} aria-hidden />
          Forecast unavailable
        </li>
      </ul>
      <h3>Routes</h3>
      <ul>
        <li>
          <span className="line" style={{ background: RECOMMENDED_ROUTE_COLOR }} aria-hidden />
          Recommended
        </li>
        <li>
          <span className="line thin" style={{ background: ALTERNATIVE_ROUTE_COLOR }} aria-hidden />
          Alternative
        </li>
      </ul>
    </div>
  );
}
