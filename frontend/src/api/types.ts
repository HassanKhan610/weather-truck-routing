// Mirrors the JSON produced by backend/routing/services/{analysis,heatmap}.py.

export type RiskValue = 0 | 1 | 2 | 3 | 4;
export type IntervalMiles = 10 | 25 | 50;
export type LatLon = [lat: number, lon: number];

export interface Place {
  label: string;
  lat: number;
  lon: number;
}

export interface CheckpointWeather {
  wind_mph: number;
  rain_in_hr: number;
  snow_in_hr: number;
}

export interface Checkpoint {
  position_mi: number;
  lat: number;
  lon: number;
  eta: string;
  weather: CheckpointWeather | null; // null when the ETA is beyond the forecast
  level: RiskValue | null;
  level_label: string;
  reasons: string[];
}

export interface RouteScore {
  severe_miles: number;
  high_miles: number;
  no_travel_miles: number;
  unknown_miles: number;
  average_risk: number | null;
  has_no_travel: boolean;
}

export interface RouteResult {
  id: string;
  rank: number;
  recommended: boolean;
  distance_mi: number;
  duration_s: number;
  arrival: string;
  geometry: LatLon[];
  checkpoints: Checkpoint[];
  worst_level: RiskValue | null;
  score: RouteScore;
}

export interface Analysis {
  origin: Place;
  destination: Place;
  departure: string;
  load_lb: number;
  interval_mi: IntervalMiles;
  recommended_route_id: string | null;
  explanation: string;
  routes: RouteResult[]; // best first
}

export interface Heatmap {
  start: string;
  hours: number;
  step_deg: number;
  lat: number[];
  lon: number[];
  frames: (number | null)[][]; // frames[hour][cell], risk index 0-4
  value_range: [number, number];
}

export interface TripInput {
  origin: Place | string;
  destination: Place | string;
  departure: string; // ISO 8601 with offset
  load_lb: number;
  interval_mi: IntervalMiles;
}
