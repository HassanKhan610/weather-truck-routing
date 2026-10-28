# Assumptions

## Risk band boundaries
The spec's bands touch at their edges (e.g. rain 0.25 appears in both Moderate and High).
Bands are **lower-inclusive**: a value equal to a boundary belongs to the higher band.
`>` is used only where the spec writes `>`.

| Factor | Low | Moderate | High | Severe | No Travel |
|---|---|---|---|---|---|
| Wind (mph) | < 25 | [25, 35) | [35, 45) | [45, 55) | ≥ 55 |
| Rain (in/hr) | < 0.10 | [0.10, 0.25) | [0.25, 0.50) | [0.50, 1.00] | > 1.00 |
| Snow (in/hr) | < 0.5 | [0.5, 1.0) | [1.0, 2.0) | [2.0, 3.0] | > 3.0 |

Wind is a continuous forecast value, so "25–34" is read as [25, 35); 34.6 mph is Moderate.

## Load rules
- "> 30,000 lb" and "> 40,000 lb" are strict: exactly 30,000 lb at 45 mph stays Severe.
- Load rules can only raise a checkpoint's level, never lower it.
- Checkpoint level = max over wind, rain, snow and applicable load rules.

## Scoring and ranking
- Each checkpoint represents the road between the midpoints to its neighbours, so mile
  totals don't depend on the sampling interval.
- "Severe miles" includes No Travel miles. Any route with a No Travel checkpoint is ranked
  last regardless of other criteria.
- Average risk = mile-weighted mean of level values (Low=0 … No Travel=4).
- Comparisons round miles to 0.1 mi and average risk to 0.001 so float noise can't decide
  a ranking. Exact ties keep the routing API's order.
- Checkpoints whose ETA is beyond the forecast horizon are "forecast unavailable": reported
  as unknown miles and excluded from the average, never silently treated as Low.

## Routes and checkpoints
- Routes use the OpenRouteService `driving-hgv` (heavy goods vehicle) profile.
- The public ORS API only returns alternative routes for trips under ~100 km. For longer
  trips we request the main route, then detours through points offset perpendicular from
  the midpoint (12% then 25% of the trip length, left then right). Detours within 2% of an
  existing route on both distance and duration are discarded as duplicates. If no distinct
  detour exists, fewer than 3 routes are shown rather than fake ones.
- Checkpoints are placed at mile 0, every N miles, and at the destination.
- Checkpoint ETA = departure + elapsed time, where elapsed time is interpolated from the
  routing API's per-step durations (so slow city streets and fast highways are respected).
- Mile markers are scaled to the API's reported odometer distance.

## Weather
- Source: Open-Meteo hourly forecast (no key), requested in mph and inches, UTC, 7 days.
- Rain rate = `rain + showers` for the hour (liquid only; snow is scored separately).
  Open-Meteo hourly precipitation is the total over the preceding hour, so it is used
  directly as in/hr. `snowfall` is in inches when `precipitation_unit=inch`.
- Weather at a checkpoint is linearly interpolated between the two hourly values around
  its ETA. If the ETA is outside the forecast, or either value is missing, the checkpoint
  is "Forecast unavailable".
- Checkpoints are snapped to a 0.1° grid (~7 mi) before fetching; nearby checkpoints
  share a forecast. All routes' points go in one batched request (chunks of 100), and
  each grid cell is cached for `WEATHER_CACHE_TTL_SECONDS` (default 10 minutes).
- Departure must be between 1 hour ago and 5 days ahead, so the trip fits in the forecast.
- Load weight is accepted from 0 to 150,000 lb.
- If every route has a No Travel checkpoint, no route is recommended.
