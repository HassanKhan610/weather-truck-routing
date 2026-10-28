import { useState } from "react";

import type { IntervalMiles, TripInput } from "../api/types";
import { nextQuarterHour, toLocalInputValue } from "../lib/format";
import { PlaceInput, type PlaceValue } from "./PlaceInput";

const INTERVALS: IntervalMiles[] = [10, 25, 50];
const MAX_LOAD_LB = 150_000;
const MAX_DAYS_AHEAD = 5;

interface Props {
  onSubmit: (trip: TripInput) => void;
  busy: boolean;
}

export function TripForm({ onSubmit, busy }: Props) {
  const [origin, setOrigin] = useState<PlaceValue>("");
  const [destination, setDestination] = useState<PlaceValue>("");
  const [departure, setDeparture] = useState(() => toLocalInputValue(nextQuarterHour()));
  const [load, setLoad] = useState("40000");
  const [interval, setInterval] = useState<IntervalMiles>(25);

  const now = new Date();
  const maxDeparture = new Date(now.getTime() + MAX_DAYS_AHEAD * 86_400_000);

  return (
    <form
      className="trip-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit({
          origin,
          destination,
          departure: new Date(departure).toISOString(), // local input -> UTC instant
          load_lb: Number(load),
          interval_mi: interval,
        });
      }}
    >
      <PlaceInput label="Origin" value={origin} onChange={setOrigin} placeholder="Dallas, TX" />
      <PlaceInput
        label="Destination"
        value={destination}
        onChange={setDestination}
        placeholder="Denver, CO"
      />

      <div className="field-row">
        <div className="field">
          <label htmlFor="departure">Departure</label>
          <input
            id="departure"
            type="datetime-local"
            required
            value={departure}
            min={toLocalInputValue(now)}
            max={toLocalInputValue(maxDeparture)}
            onChange={(event) => setDeparture(event.target.value)}
          />
        </div>
        <div className="field">
          <label htmlFor="load">Load weight (lb)</label>
          <input
            id="load"
            type="number"
            inputMode="numeric"
            required
            min={0}
            max={MAX_LOAD_LB}
            step={500}
            value={load}
            onChange={(event) => setLoad(event.target.value)}
          />
        </div>
      </div>

      <fieldset className="field segmented">
        <legend>Check weather every</legend>
        {INTERVALS.map((miles) => (
          <label key={miles} className={miles === interval ? "selected" : undefined}>
            <input
              type="radio"
              name="interval"
              value={miles}
              checked={miles === interval}
              onChange={() => setInterval(miles)}
            />
            {miles} mi
          </label>
        ))}
      </fieldset>

      <button type="submit" className="primary" disabled={busy}>
        {busy ? "Analyzing routes…" : "Find safest route"}
      </button>
    </form>
  );
}
