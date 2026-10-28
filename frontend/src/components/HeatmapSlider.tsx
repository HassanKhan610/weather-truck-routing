import { useEffect, useRef, useState } from "react";

import { formatDateTime } from "../lib/format";
import { heatColor, RISK_LEVELS } from "../lib/risk";

const PLAY_FRAME_MS = 250;

interface Props {
  start: string | null; // ISO time of hour 0; null while loading or unavailable
  hours: number;
  hour: number;
  onHourChange: (hour: number) => void;
  visible: boolean;
  onVisibleChange: (visible: boolean) => void;
  status: "idle" | "loading" | "ready" | "error";
}

const GRADIENT = `linear-gradient(to right, ${[0, 1, 2, 3, 4]
  .map((x) => {
    const [r, g, b, a] = heatColor(x === 0 ? 0.25 : x);
    return `rgba(${r},${g},${b},${Math.max(a, 50) / 255})`;
  })
  .join(", ")})`;

export function HeatmapSlider({
  start,
  hours,
  hour,
  onHourChange,
  visible,
  onVisibleChange,
  status,
}: Props) {
  const [playing, setPlaying] = useState(false);
  const hourRef = useRef(hour);
  hourRef.current = hour;

  useEffect(() => {
    if (!playing) return;
    const timer = setInterval(
      () => onHourChange((hourRef.current + 1) % (hours + 1)),
      PLAY_FRAME_MS,
    );
    return () => clearInterval(timer);
  }, [playing, hours, onHourChange]);

  const ready = status === "ready" && start !== null;
  const time = ready ? new Date(new Date(start).getTime() + hour * 3_600_000).toISOString() : null;

  return (
    <div className="heatmap-slider map-panel">
      <div className="slider-header">
        <label className="toggle">
          <input
            type="checkbox"
            checked={visible}
            onChange={(event) => onVisibleChange(event.target.checked)}
          />
          Weather risk heatmap
        </label>
        <span className="slider-time" aria-live="polite">
          {status === "loading" && "Loading forecast…"}
          {status === "error" && "Heatmap unavailable"}
          {time && `+${hour} h · ${formatDateTime(time)}`}
        </span>
      </div>
      <div className="slider-controls">
        <button
          type="button"
          className="icon"
          disabled={!ready}
          onClick={() => setPlaying((p) => !p)}
          aria-label={playing ? "Pause" : "Play forecast"}
        >
          {playing ? "❚❚" : "▶"}
        </button>
        <input
          type="range"
          min={0}
          max={hours}
          step={1}
          value={hour}
          disabled={!ready}
          aria-label="Forecast hour after departure"
          aria-valuetext={
            time ? `${hour} hours after departure, ${formatDateTime(time)}` : undefined
          }
          onChange={(event) => {
            setPlaying(false);
            onHourChange(Number(event.target.value));
          }}
        />
      </div>
      <div className="heat-scale" aria-hidden>
        <div className="bar" style={{ background: GRADIENT }} />
        <div className="ticks">
          {RISK_LEVELS.map((level) => (
            <span key={level.value}>{level.label}</span>
          ))}
        </div>
      </div>
    </div>
  );
}
