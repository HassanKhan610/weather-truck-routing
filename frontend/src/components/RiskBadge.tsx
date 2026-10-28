import type { RiskValue } from "../api/types";
import { riskColor, riskLabel } from "../lib/risk";

/** Colour swatch + text: risk is never conveyed by colour alone. */
export function RiskBadge({ level }: { level: RiskValue | null }) {
  return (
    <span className="risk-badge">
      <span className="swatch" style={{ background: riskColor(level) }} aria-hidden />
      {riskLabel(level)}
    </span>
  );
}
