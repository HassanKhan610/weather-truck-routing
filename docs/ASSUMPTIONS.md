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
